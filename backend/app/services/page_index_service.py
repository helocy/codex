"""
PageIndex 服务 - 受 VectifyAI/PageIndex 启发的树形索引生成器

核心思路：
  - 不依赖向量相似度，而是将文档解析成层次化的目录树（TreeIndex）
  - 每个节点携带 title / summary / start_index / end_index（页码或行号）
  - 检索时先让 LLM 推理哪些节点相关，再在对应节点范围的 chunks 中做精细检索
"""

import re
import json
import logging
from typing import Optional

from app.models.document import Document, Chunk, FileType

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────

def _node_id(idx: int) -> str:
    return str(idx).zfill(4)


def _parse_json_from_llm(text: str) -> list | dict:
    """从 LLM 输出中提取 JSON（兼容 ```json ... ``` 包裹和裸 JSON）"""
    text = text.strip()
    # 去掉 ```json ... ```
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if m:
        text = m.group(1)
    text = text.replace("None", "null").replace("True", "true").replace("False", "false")
    try:
        return json.loads(text)
    except Exception:
        # 尝试找第一个 [ 或 {
        for start_char, end_char in [("[", "]"), ("{", "}")]:
            s = text.find(start_char)
            e = text.rfind(end_char)
            if s != -1 and e != -1 and e > s:
                try:
                    return json.loads(text[s:e + 1])
                except Exception:
                    pass
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Markdown 树形索引（无需 LLM，直接解析标题层级）
# ─────────────────────────────────────────────────────────────────────────────

def _build_tree_from_markdown(content: str) -> list:
    """
    解析 Markdown 标题（# ~ ###），构建层次树。
    节点的 start_index / end_index 是字符偏移（行号近似）。
    """
    lines = content.splitlines()
    heading_re = re.compile(r"^(#{1,3})\s+(.+)$")

    flat = []  # [{level, title, line_start, line_end}]
    for i, line in enumerate(lines):
        m = heading_re.match(line)
        if m:
            flat.append({
                "level": len(m.group(1)),
                "title": m.group(2).strip(),
                "line_start": i + 1,
                "line_end": len(lines),  # 先填末尾，后面修正
            })

    # 修正 line_end
    for i in range(len(flat) - 1):
        flat[i]["line_end"] = flat[i + 1]["line_start"] - 1

    if not flat:
        # 无标题文档：整体作为一个根节点
        return [{
            "title": "全文",
            "node_id": "0000",
            "start_index": 1,
            "end_index": len(lines),
            "summary": content[:200],
            "nodes": []
        }]

    # 构建层次树
    node_counter = [0]

    def make_node(item: dict) -> dict:
        nid = _node_id(node_counter[0])
        node_counter[0] += 1
        return {
            "title": item["title"],
            "node_id": nid,
            "start_index": item["line_start"],
            "end_index": item["line_end"],
            "summary": "",   # 后续可选填
            "nodes": []
        }

    root_nodes: list = []
    stack: list = []  # [(level, node_dict)]

    for item in flat:
        node = make_node(item)
        # 找到合适的父节点
        while stack and stack[-1][0] >= item["level"]:
            stack.pop()
        if stack:
            stack[-1][1]["nodes"].append(node)
        else:
            root_nodes.append(node)
        stack.append((item["level"], node))

    # 清理空 nodes 列表
    def _clean(nodes):
        for n in nodes:
            if n["nodes"]:
                _clean(n["nodes"])
            else:
                del n["nodes"]
        return nodes

    return _clean(root_nodes)


# ─────────────────────────────────────────────────────────────────────────────
# PDF / 纯文本树形索引（调用 LLM）
# ─────────────────────────────────────────────────────────────────────────────

async def _build_tree_from_pdf_pages(pages: list[tuple[int, str]], llm_service) -> list:
    """
    pages: [(page_num, text), ...]
    返回 PageIndex 风格的树形结构列表。
    """
    # 把页面内容拼成带 <page_N> 标签的文本（每次最多处理 30 页避免超 token）
    BATCH = 30
    flat_sections = []

    for batch_start in range(0, len(pages), BATCH):
        batch = pages[batch_start: batch_start + BATCH]
        tagged = ""
        for pnum, ptext in batch:
            tagged += f"<page_{pnum}>\n{ptext[:1500]}\n</page_{pnum}>\n\n"

        prompt = f"""你是文档结构分析专家。给定以下带页码标签的文档内容，提取其层次化章节结构。

要求：
- 识别所有章节标题及其层级（用 "1", "1.1", "1.1.1" 等表示层级路径）
- 记录每个章节的起始页码（对应 <page_N> 中的 N）
- 仅提取真实的章节标题，不要捏造

文档内容：
{tagged}

返回 JSON 数组（不要输出其他内容）：
[
  {{"structure": "1", "title": "章节名称", "page": 起始页码}},
  {{"structure": "1.1", "title": "子章节名称", "page": 起始页码}},
  ...
]"""

        try:
            resp = await llm_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=2000
            )
            batch_sections = _parse_json_from_llm(resp)
            if isinstance(batch_sections, list):
                flat_sections.extend(batch_sections)
        except Exception as e:
            logger.warning(f"LLM 生成树形索引失败（batch {batch_start}）: {e}")

    if not flat_sections:
        return _fallback_page_tree(pages)

    return _flat_sections_to_tree(flat_sections, total_pages=pages[-1][0] if pages else 1)


def _fallback_page_tree(pages: list[tuple[int, str]]) -> list:
    """LLM 失败时的降级：按每 5 页一组构建树"""
    GROUP = 5
    nodes = []
    for i in range(0, len(pages), GROUP):
        group = pages[i: i + GROUP]
        start = group[0][0]
        end = group[-1][0]
        nodes.append({
            "title": f"第 {start}–{end} 页",
            "node_id": _node_id(i // GROUP),
            "start_index": start,
            "end_index": end,
            "summary": group[0][1][:100],
        })
    return nodes


def _flat_sections_to_tree(flat: list, total_pages: int) -> list:
    """
    将 [{structure, title, page}, ...] 平铺列表转换为嵌套树，
    并补全 start_index / end_index / node_id。
    """
    if not flat:
        return []

    # 排序（按 structure 字符串数字比较）
    def sort_key(item):
        parts = str(item.get("structure", "0")).split(".")
        try:
            return [int(p) for p in parts]
        except Exception:
            return [0]

    flat = sorted(flat, key=sort_key)

    # 补充 end_index：下一个同级或更高级节点的 page - 1
    for i, item in enumerate(flat):
        cur_page = item.get("page") or 1
        item["start_index"] = cur_page
        # 找下一个节点页码
        next_page = total_pages
        for j in range(i + 1, len(flat)):
            np = flat[j].get("page")
            if np and np > cur_page:
                next_page = np
                break
        item["end_index"] = next_page

    # 构建嵌套结构
    nodes: dict = {}
    root_nodes: list = []
    counter = [0]

    def get_parent_key(structure: str) -> str | None:
        parts = str(structure).split(".")
        if len(parts) <= 1:
            return None
        return ".".join(parts[:-1])

    for item in flat:
        nid = _node_id(counter[0])
        counter[0] += 1
        node = {
            "title": item.get("title", "未命名"),
            "node_id": nid,
            "start_index": item["start_index"],
            "end_index": item["end_index"],
            "summary": "",
            "nodes": []
        }
        key = str(item.get("structure", counter[0]))
        nodes[key] = node

        parent_key = get_parent_key(key)
        if parent_key and parent_key in nodes:
            nodes[parent_key]["nodes"].append(node)
        else:
            root_nodes.append(node)

    # 清理空 nodes
    def _clean(ns):
        for n in ns:
            if n.get("nodes"):
                _clean(n["nodes"])
            else:
                n.pop("nodes", None)
        return ns

    return _clean(root_nodes)


async def _build_tree_from_text(content: str, llm_service) -> list:
    """
    对纯文本 / Word 文档，让 LLM 按逻辑段落生成粗粒度结构。
    start_index / end_index 用字符偏移（粗粒度）。
    """
    preview = content[:4000]
    prompt = f"""你是文档结构分析专家。给定以下文本内容，请将其划分为若干逻辑章节。

要求：
- 识别主要逻辑章节，给出标题
- 每个章节提供一句话摘要
- 用层级编号表示章节关系（如 "1", "1.1"）

文本内容（前 4000 字）：
{preview}

返回 JSON 数组（不要输出其他内容）：
[
  {{"structure": "1", "title": "章节标题", "summary": "一句话摘要"}},
  {{"structure": "1.1", "title": "子章节", "summary": "一句话摘要"}},
  ...
]"""

    try:
        resp = await llm_service.chat(
            [{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=1500
        )
        sections = _parse_json_from_llm(resp)
    except Exception as e:
        logger.warning(f"LLM 文本分段失败: {e}")
        sections = []

    if not isinstance(sections, list) or not sections:
        # 降级：整体作为一个节点
        return [{
            "title": "全文",
            "node_id": "0000",
            "start_index": 1,
            "end_index": len(content.splitlines()),
            "summary": content[:200],
        }]

    # 均匀分配行号范围
    total_lines = len(content.splitlines())
    step = max(1, total_lines // max(len(sections), 1))
    flat = []
    for i, s in enumerate(sections):
        s["page"] = i * step + 1
        flat.append(s)

    tree = _flat_sections_to_tree(flat, total_pages=total_lines)

    # 将 LLM 提供的 summary 写回节点
    def _fill_summary(nodes, sections_map):
        for n in nodes:
            match = sections_map.get(n["title"])
            if match:
                n["summary"] = match
            if n.get("nodes"):
                _fill_summary(n["nodes"], sections_map)

    summary_map = {s.get("title", ""): s.get("summary", "") for s in sections}
    _fill_summary(tree, summary_map)
    return tree


# ─────────────────────────────────────────────────────────────────────────────
# 为节点生成摘要（可选，丰富树形索引质量）
# ─────────────────────────────────────────────────────────────────────────────

async def _fill_summaries(tree: list, content_getter, llm_service, max_nodes: int = 20):
    """
    遍历树，为缺少 summary 的节点调用 LLM 生成摘要。
    content_getter(start, end) -> str  取对应范围的文本。
    max_nodes: 避免对超大文档产生过多 LLM 调用。
    """
    from app.services.page_index_service import _node_list_flat
    nodes = _node_list_flat(tree)
    filled = 0
    for node in nodes:
        if filled >= max_nodes:
            break
        if node.get("summary"):
            continue
        text = content_getter(node.get("start_index", 1), node.get("end_index", 1))
        if not text.strip():
            continue
        prompt = f"用一句话概括以下文档片段的核心内容（不超过 80 字）：\n\n{text[:2000]}"
        try:
            summary = await llm_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=150
            )
            node["summary"] = summary.strip()
            filled += 1
        except Exception:
            pass


def _node_list_flat(tree) -> list:
    """递归展开树，返回所有节点的平铺列表（不含子节点引用）"""
    result = []
    if isinstance(tree, list):
        for item in tree:
            result.extend(_node_list_flat(item))
    elif isinstance(tree, dict):
        result.append(tree)
        for child in tree.get("nodes", []):
            result.extend(_node_list_flat(child))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 将 Chunk 关联到树节点（写入 section_id）
# ─────────────────────────────────────────────────────────────────────────────

def _assign_chunks_to_nodes(chunks: list, tree: list, file_type: FileType):
    """
    根据 chunk_index（对应页码或行号范围）将 chunk.section_id 写入最匹配的叶节点。
    对 PDF 文件用页码匹配，对其他文件用 chunk_index 行号近似匹配。
    """
    flat_nodes = _node_list_flat(tree)

    def find_node(idx: int) -> Optional[str]:
        """找到包含 idx 的最深节点"""
        best = None
        best_range = float("inf")
        for node in flat_nodes:
            s = node.get("start_index", 0)
            e = node.get("end_index", float("inf"))
            if s <= idx <= e:
                span = e - s
                if span < best_range:
                    best_range = span
                    best = node.get("node_id")
        return best

    for chunk in chunks:
        # 从 content 中提取页码（PDF 格式 "[第 N 页]"）
        if file_type == FileType.PDF:
            m = re.search(r"\[第\s*(\d+)\s*页\]", chunk.content)
            idx = int(m.group(1)) if m else (chunk.chunk_index + 1)
        else:
            idx = chunk.chunk_index + 1

        chunk.section_id = find_node(idx)


# ─────────────────────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────────────────────

class PageIndexService:
    """
    为已上传的文档生成 PageIndex 树形索引，并将 Chunk 关联到对应节点。

    使用方式（在文档上传后异步调用）：
        await page_index_service.build(document, db, llm_service)
    """

    async def build(self, document: Document, db, llm_service=None) -> bool:
        """
        生成树形索引并持久化到 document.tree_index，
        同时更新 document 下所有 chunks 的 section_id。

        Returns:
            True 表示成功，False 表示跳过（无 LLM 配置但又需要 LLM）
        """
        try:
            tree = await self._generate_tree(document, llm_service)
            if not tree:
                return False

            # 写入 document
            document.tree_index = tree
            db.add(document)

            # 更新所有 chunks 的 section_id
            chunks = db.query(Chunk).filter(Chunk.document_id == document.id).all()
            _assign_chunks_to_nodes(chunks, tree, document.file_type)
            for chunk in chunks:
                db.add(chunk)

            db.commit()
            logger.info(f"[PageIndex] 文档 {document.id}「{document.title}」树形索引生成完成，"
                        f"共 {len(_node_list_flat(tree))} 个节点")
            return True

        except Exception as e:
            logger.error(f"[PageIndex] 文档 {document.id} 索引生成失败: {e}", exc_info=True)
            db.rollback()
            return False

    async def _generate_tree(self, document: Document, llm_service) -> list:
        if document.file_type == FileType.MARKDOWN:
            # Markdown 直接解析标题，无需 LLM
            return _build_tree_from_markdown(document.content or "")

        if llm_service is None or not llm_service.client:
            logger.warning(f"[PageIndex] LLM 未配置，跳过文档 {document.id} 的树形索引")
            return []

        if document.file_type == FileType.PDF and document.file_path:
            pages = self._extract_pdf_pages(document.file_path)
            return await _build_tree_from_pdf_pages(pages, llm_service)

        # TEXT / WORD / 其他：基于 content 文本
        return await _build_tree_from_text(document.content or "", llm_service)

    @staticmethod
    def _extract_pdf_pages(file_path: str) -> list[tuple[int, str]]:
        import warnings
        from PyPDF2 import PdfReader
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                reader = PdfReader(file_path)
                if reader.is_encrypted:
                    reader.decrypt("")
                pages = []
                for i, page in enumerate(reader.pages):
                    text = (page.extract_text() or "").strip()
                    if text:
                        pages.append((i + 1, text))
                return pages
        except Exception as e:
            logger.error(f"[PageIndex] PDF 解析失败: {e}")
            return []


page_index_service = PageIndexService()
