from sqlalchemy.orm import Session
from app.models.document import Chunk
from app.services.embedding_service import embedding_service
from typing import List, Tuple, Dict
import numpy as np
from rank_bm25 import BM25Okapi
import re


def _tokenize(text: str) -> List[str]:
    """简单分词：按空白和标点拆分，转小写"""
    return re.findall(r'\w+', text.lower())


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
    def search(db: Session, query: str, top_k: int = 10) -> List[Tuple[Chunk, float]]:
        """BM25 + 向量混合检索，RRF 融合，相邻 chunk 合并"""
        chunks = db.query(Chunk).all()
        if not chunks:
            return []

        valid_chunks = [c for c in chunks if c.embedding]
        if not valid_chunks:
            return []

        # ── 1. 向量检索 ──────────────────────────────────────────────
        query_emb = embedding_service.encode_single(query)
        vec_scores: Dict[int, float] = {}
        for chunk in valid_chunks:
            emb = np.array(chunk.embedding, dtype=np.float32)
            vec_scores[chunk.id] = SearchService.cosine_similarity(query_emb, emb)

        vec_ranked = sorted(valid_chunks, key=lambda c: vec_scores[c.id], reverse=True)

        # ── 2. BM25 关键词检索 ────────────────────────────────────────
        corpus = [_tokenize(c.content) for c in valid_chunks]
        bm25 = BM25Okapi(corpus)
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
