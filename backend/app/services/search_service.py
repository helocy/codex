from sqlalchemy.orm import Session
from app.models.document import Chunk, Document
from app.services.embedding_service import embedding_service
from typing import List, Tuple, Dict, Optional, Set
import numpy as np
from rank_bm25 import BM25Okapi
import re
import json
import logging

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> List[str]:
    """简单分词：按空白和标点拆分，转小写"""
    return re.findall(r'\w+', text.lower())


# ── 全局 BM25 缓存 ───────────────────────────────────────────────────────────
class _BM25Cache:
    """缓存 BM25 索引，chunk 集合不变时复用，避免每次搜索重建"""
    def __init__(self):
        self._bm25: Optional[BM25Okapi] = None
        self._chunk_ids: List[int] = []
        self._chunks: List = []

    def get(self, chunks: List) -> Tuple[BM25Okapi, List]:
        ids = [c.id for c in chunks]
        if ids != self._chunk_ids:
            corpus = [_tokenize(c.content) for c in chunks]
            self._bm25 = BM25Okapi(corpus)
            self._chunk_ids = ids
            self._chunks = chunks
            logger.debug(f"[BM25Cache] 重建索引，共 {len(chunks)} 个 chunk")
        return self._bm25, self._chunks

    def invalidate(self):
        self._chunk_ids = []
        self._bm25 = None


_bm25_cache = _BM25Cache()


# ── 全局 Embedding 内存缓存 ──────────────────────────────────────────────────
class _EmbeddingCache:
    """将所有 chunk embedding 缓存为 numpy 矩阵，避免每次从数据库全量读取"""
    def __init__(self):
        self._matrix: Optional[np.ndarray] = None   # shape: (N, dim)
        self._norms: Optional[np.ndarray] = None    # shape: (N,)
        self._chunk_ids: List[int] = []
        self._chunks: List = []  # 仅元数据（不含 embedding）

    def _is_valid(self, chunks: List) -> bool:
        if self._matrix is None:
            return False
        return [c.id for c in chunks] == self._chunk_ids

    def load(self, chunks: List) -> Tuple[np.ndarray, np.ndarray, List]:
        """返回 (matrix, norms, chunks)，命中缓存直接返回，否则重建"""
        if self._is_valid(chunks):
            return self._matrix, self._norms, self._chunks

        logger.info(f"[EmbeddingCache] 重建矩阵，共 {len(chunks)} 个 chunk")
        matrix = np.array([c.embedding for c in chunks], dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1)
        norms[norms == 0] = 1e-9
        self._matrix = matrix
        self._norms = norms
        self._chunk_ids = [c.id for c in chunks]
        self._chunks = chunks
        return self._matrix, self._norms, self._chunks

    def invalidate(self):
        self._matrix = None
        self._norms = None
        self._chunk_ids = []
        self._chunks = []


_emb_cache = _EmbeddingCache()


class SearchService:
    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    @staticmethod
    def search_multi_query(db: Session, queries: List[str], top_k: int = 10) -> List[Tuple[Chunk, float]]:
        """多查询检索：对每个查询分别检索，然后合并结果（用于对比类查询）"""
        all_results = {}

        for query in queries:
            results = SearchService.search(db, query, top_k=top_k)
            for chunk, score in results:
                if chunk.id in all_results:
                    # 如果已存在，取最高分
                    all_results[chunk.id] = (chunk, max(all_results[chunk.id][1], score))
                else:
                    all_results[chunk.id] = (chunk, score)

        # 按分数排序
        sorted_results = sorted(all_results.values(), key=lambda x: x[1], reverse=True)
        return sorted_results[:top_k * 2]  # 返回更多结果

    @staticmethod
    def invalidate_cache():
        """文档增删后调用，使 BM25 和 embedding 缓存失效"""
        _bm25_cache.invalidate()
        _emb_cache.invalidate()

    @staticmethod
    def search(db: Session, query: str, top_k: int = 10) -> List[Tuple[Chunk, float]]:
        """BM25 + 向量混合检索，RRF 融合，相邻 chunk 合并"""
        # 缓存命中时直接用内存数据，跳过 DB 全量读取
        if _emb_cache._matrix is not None and _emb_cache._chunks:
            valid_chunks = _emb_cache._chunks
        else:
            chunks = db.query(Chunk).all()
            if not chunks:
                return []
            valid_chunks = [c for c in chunks if c.embedding]
            if not valid_chunks:
                return []

        # ── 1. 向量检索（内存矩阵缓存，避免重复从 DB 读取 embedding）──
        query_emb = embedding_service.encode_single(query)
        emb_matrix, norms, _ = _emb_cache.load(valid_chunks)
        query_norm = float(np.linalg.norm(query_emb)) or 1e-9
        cos_scores = emb_matrix.dot(query_emb) / (norms * query_norm)
        vec_scores: Dict[int, float] = {
            valid_chunks[i].id: float(cos_scores[i]) for i in range(len(valid_chunks))
        }
        vec_ranked = sorted(valid_chunks, key=lambda c: vec_scores[c.id], reverse=True)

        # ── 2. BM25 关键词检索（使用缓存索引）───────────────────────
        bm25, _ = _bm25_cache.get(valid_chunks)
        query_tokens = _tokenize(query)
        bm25_raw = bm25.get_scores(query_tokens)
        bm25_scores: Dict[int, float] = {
            valid_chunks[i].id: float(bm25_raw[i]) for i in range(len(valid_chunks))
        }
        bm25_ranked = sorted(valid_chunks, key=lambda c: bm25_scores[c.id], reverse=True)

        # ── 3. RRF 融合（k=60）─────────────────────────────────────────
        k = 60
        rrf: Dict[int, float] = {}
        for rank, chunk in enumerate(vec_ranked):
            rrf[chunk.id] = rrf.get(chunk.id, 0.0) + 1.0 / (k + rank + 1)
        for rank, chunk in enumerate(bm25_ranked):
            rrf[chunk.id] = rrf.get(chunk.id, 0.0) + 1.0 / (k + rank + 1)

        chunk_map = {c.id: c for c in valid_chunks}
        top_ids = sorted(rrf, key=lambda cid: rrf[cid], reverse=True)[:top_k * 2]

        # ── 4. 相邻 chunk 合并（同一文档的连续 chunk_index 合并）────────
        # 按 document_id 和 chunk_index 整理
        doc_chunks: Dict[int, Dict[int, Chunk]] = {}
        for cid in top_ids:
            c = chunk_map[cid]
            doc_chunks.setdefault(c.document_id, {})[c.chunk_index] = c

        merged: List[Tuple[Chunk, float]] = []
        used_ids: set = set()

        for cid in top_ids:
            if cid in used_ids:
                continue
            chunk = chunk_map[cid]
            doc_idx_map = doc_chunks.get(chunk.document_id, {})

            # 找连续邻居
            group = [chunk.chunk_index]
            prev_idx = chunk.chunk_index - 1
            while prev_idx in doc_idx_map and doc_idx_map[prev_idx].id in set(top_ids):
                group.insert(0, prev_idx)
                prev_idx -= 1
            next_idx = chunk.chunk_index + 1
            while next_idx in doc_idx_map and doc_idx_map[next_idx].id in set(top_ids):
                group.append(next_idx)
                next_idx += 1

            group_chunks = [doc_idx_map[i] for i in group if i in doc_idx_map]
            for gc in group_chunks:
                used_ids.add(gc.id)

            if len(group_chunks) > 1:
                # 合并为虚拟 chunk
                merged_content = "\n\n".join(gc.content for gc in group_chunks)
                virtual = Chunk()
                virtual.id = group_chunks[0].id
                virtual.document_id = chunk.document_id
                virtual.content = merged_content
                virtual.embedding = chunk.embedding
                virtual.chunk_index = chunk.chunk_index
                score = rrf[cid]
                merged.append((virtual, score))
            else:
                merged.append((chunk, rrf[cid]))

        return merged[:top_k]

    # ─── PageIndex 两阶段检索 ────────────────────────────────────────────────

    @staticmethod
    async def search_with_tree_index(
        db: Session,
        query: str,
        llm_service,
        top_k: int = 10,
        use_tree: bool = True,
    ) -> Tuple[List[Tuple[Chunk, float]], List[dict]]:
        """
        PageIndex 风格的两阶段检索：
          阶段1：LLM 分析所有文档的 tree_index，推理出相关节点（section_id）
          阶段2：只在相关节点的 chunks 中做向量 + BM25 混合检索

        Returns:
            (chunks_with_scores, referenced_nodes)
            referenced_nodes: [{doc_title, node_title, node_id, summary}, ...]
        """
        # 收集有树形索引的文档
        docs_with_tree = (
            db.query(Document)
            .filter(Document.tree_index.isnot(None))
            .all()
        ) if use_tree else []

        relevant_node_ids: Optional[Set[str]] = None
        referenced_nodes: List[dict] = []

        if docs_with_tree and use_tree:
            # 预筛选：用 BM25 在文档标题上过滤，只取最相关的 Top-N 个文档送给 LLM
            # 避免全量文档目录超出 LLM context 限制
            filtered_docs = SearchService._prefilter_docs(query, docs_with_tree, max_docs=15)
            relevant_node_ids, referenced_nodes = await SearchService._tree_search_phase(
                query, filtered_docs, llm_service
            )

        # 阶段2：在相关节点范围内检索，并与全量检索结果混合兜底
        chunks = SearchService._get_candidate_chunks(db, relevant_node_ids)
        if not chunks:
            # 无命中节点，降级到全量检索
            return SearchService.search(db, query, top_k=top_k), referenced_nodes

        # 树形结果占前半部分（精准），全量检索兜底后半部分（保证召回）
        tree_k = max(top_k // 2, 1)
        fallback_k = top_k - tree_k

        tree_results = SearchService._hybrid_search(query, chunks, top_k=tree_k)
        fallback_results = SearchService.search(db, query, top_k=top_k * 2)

        # 先放树形结果（至多 tree_k 个），再从全量结果中补齐剩余 fallback_k 个
        seen: set[int] = set()
        results: list = []
        for chunk, score in tree_results[:tree_k]:
            if chunk.id not in seen:
                seen.add(chunk.id)
                results.append((chunk, score))

        added = 0
        for chunk, score in fallback_results:
            if added >= fallback_k:
                break
            if chunk.id not in seen:
                seen.add(chunk.id)
                results.append((chunk, score))
                added += 1

        return results, referenced_nodes

    @staticmethod
    async def _tree_search_phase(
        query: str,
        docs: List[Document],
        llm_service,
    ) -> Tuple[Set[str], List[dict]]:
        """
        让 LLM 分析每个文档的 tree_index，推理哪些节点可能包含答案。
        返回 (相关 node_id 集合, 引用节点描述列表)
        """
        # 构建文档目录摘要（只传 title + summary，不传正文，节省 token）
        tree_summaries = []
        for doc in docs:
            tree = doc.tree_index
            if not tree:
                continue
            compact = SearchService._compact_tree(tree)
            tree_summaries.append({
                "doc_id": doc.id,
                "doc_title": doc.title,
                "tree": compact
            })

        if not tree_summaries:
            return set(), []

        prompt = f"""你是文档检索专家。给定用户问题和多个文档的层次化目录结构，判断哪些章节节点可能包含答案。

用户问题：{query}

文档目录结构（JSON）：
{json.dumps(tree_summaries, ensure_ascii=False, indent=2)}

任务：
1. 分析每个节点的 title 和 summary，判断是否与问题相关
2. 返回所有相关节点的 node_id 列表

返回格式（JSON 数组，不要输出其他内容）：
[
  {{"doc_id": 1, "node_id": "0001", "reason": "该节点包含..."}},
  ...
]

注意：
- 宁可多选几个相关节点，不要遗漏
- 如果整个文档都不相关，不要选该文档的节点
- 最多返回 15 个节点"""

        try:
            resp = await llm_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=800
            )
            selected = SearchService._parse_json(resp)
            if not isinstance(selected, list):
                return set(), []
        except Exception as e:
            logger.warning(f"[PageIndex] 树形检索阶段失败，降级到全量检索: {e}")
            return set(), []

        node_ids: Set[str] = set()
        referenced_nodes: List[dict] = []

        # 构建 doc_id -> doc 映射
        doc_map = {doc.id: doc for doc in docs}

        for item in selected:
            if not isinstance(item, dict):
                continue
            nid = item.get("node_id")
            doc_id = item.get("doc_id")
            if nid:
                node_ids.add(nid)
                doc = doc_map.get(doc_id)
                if doc:
                    # 在树中找到节点详情
                    node_detail = SearchService._find_node_in_tree(doc.tree_index, nid)
                    referenced_nodes.append({
                        "doc_id": doc_id,
                        "doc_title": doc.title,
                        "node_id": nid,
                        "node_title": node_detail.get("title", "") if node_detail else "",
                        "summary": node_detail.get("summary", "") if node_detail else "",
                        "reason": item.get("reason", ""),
                    })

        logger.info(f"[PageIndex] 树形检索命中 {len(node_ids)} 个节点: {node_ids}")
        return node_ids, referenced_nodes

    @staticmethod
    def _get_candidate_chunks(db: Session, node_ids: Optional[Set[str]]) -> List[Chunk]:
        """根据 section_id 过滤 chunks；node_ids=None 表示不过滤"""
        if node_ids is None:
            return db.query(Chunk).all()
        if not node_ids:
            return []
        return (
            db.query(Chunk)
            .filter(Chunk.section_id.in_(node_ids))
            .all()
        )

    @staticmethod
    def _hybrid_search(
        query: str, chunks: List[Chunk], top_k: int = 10
    ) -> List[Tuple[Chunk, float]]:
        """在给定 chunks 上执行向量 + BM25 + RRF 混合检索（与 search() 逻辑一致）"""
        valid_chunks = [c for c in chunks if c.embedding]
        if not valid_chunks:
            return []

        query_emb = embedding_service.encode_single(query)

        # 向量检索（矩阵化）
        emb_matrix = np.array([c.embedding for c in valid_chunks], dtype=np.float32)
        norms = np.linalg.norm(emb_matrix, axis=1)
        norms[norms == 0] = 1e-9
        query_norm = np.linalg.norm(query_emb) or 1e-9
        cos_scores = emb_matrix.dot(query_emb) / (norms * query_norm)
        vec_scores: Dict[int, float] = {
            valid_chunks[i].id: float(cos_scores[i]) for i in range(len(valid_chunks))
        }
        vec_ranked = sorted(valid_chunks, key=lambda c: vec_scores[c.id], reverse=True)

        # BM25（_hybrid_search 用于 section 内检索，chunk 集合小且每次不同，不用全局缓存）
        corpus = [_tokenize(c.content) for c in valid_chunks]
        bm25 = BM25Okapi(corpus)
        bm25_raw = bm25.get_scores(_tokenize(query))
        bm25_scores: Dict[int, float] = {
            valid_chunks[i].id: float(bm25_raw[i]) for i in range(len(valid_chunks))
        }
        bm25_ranked = sorted(valid_chunks, key=lambda c: bm25_scores[c.id], reverse=True)

        # RRF
        k = 60
        rrf: Dict[int, float] = {}
        for rank, chunk in enumerate(vec_ranked):
            rrf[chunk.id] = rrf.get(chunk.id, 0.0) + 1.0 / (k + rank + 1)
        for rank, chunk in enumerate(bm25_ranked):
            rrf[chunk.id] = rrf.get(chunk.id, 0.0) + 1.0 / (k + rank + 1)

        chunk_map = {c.id: c for c in valid_chunks}
        top_ids = sorted(rrf, key=lambda cid: rrf[cid], reverse=True)[: top_k * 2]

        results = [(chunk_map[cid], rrf[cid]) for cid in top_ids if cid in chunk_map]
        return results[:top_k]

    # ─── 工具方法 ────────────────────────────────────────────────────────────

    @staticmethod
    def _prefilter_docs(query: str, docs: List[Document], max_docs: int = 15) -> List[Document]:
        """
        用 BM25 对文档标题打分，返回最相关的 max_docs 个文档。
        若文档总数 <= max_docs，直接返回全部。
        若 BM25 全部得分为 0（查询词与标题完全不重叠），则返回前 max_docs 个。
        """
        if len(docs) <= max_docs:
            return docs

        titles = [_tokenize(doc.title) for doc in docs]
        bm25 = BM25Okapi(titles)
        scores = bm25.get_scores(_tokenize(query))

        top_indices = sorted(range(len(docs)), key=lambda i: scores[i], reverse=True)[:max_docs]
        return [docs[i] for i in top_indices]

    @staticmethod
    def _compact_tree(tree, depth: int = 0, max_depth: int = 3) -> list:
        """将完整树压缩为只含 node_id / title / summary 的精简版（降低 token 消耗）"""
        result = []
        nodes = tree if isinstance(tree, list) else [tree]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            compact = {
                "node_id": node.get("node_id"),
                "title": node.get("title", ""),
                "summary": (node.get("summary") or "")[:100],
            }
            children = node.get("nodes", [])
            if children and depth < max_depth:
                compact["nodes"] = SearchService._compact_tree(children, depth + 1, max_depth)
            result.append(compact)
        return result

    @staticmethod
    def _find_node_in_tree(tree, node_id: str) -> Optional[dict]:
        """在树中查找指定 node_id 的节点"""
        nodes = tree if isinstance(tree, list) else [tree]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("node_id") == node_id:
                return node
            found = SearchService._find_node_in_tree(node.get("nodes", []), node_id)
            if found:
                return found
        return None

    @staticmethod
    def _parse_json(text: str):
        text = text.strip()
        m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
        if m:
            text = m.group(1)
        try:
            return json.loads(text)
        except Exception:
            for sc, ec in [("[", "]"), ("{", "}")]:
                s = text.find(sc)
                e = text.rfind(ec)
                if s != -1 and e > s:
                    try:
                        return json.loads(text[s:e + 1])
                    except Exception:
                        pass
        return []
