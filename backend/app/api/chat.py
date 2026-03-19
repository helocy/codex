from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict
import math
import logging
from app.core.database import get_db
from app.services.search_service import SearchService
from app.services.llm_service import llm_service
from app.services.web_search_service import web_search_service
from app.services.original_doc_service import original_doc_service

router = APIRouter()
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    query: str
    top_k: int = 50
    use_rag: bool = True
    use_web_search: bool = False  # 是否使用网络搜索
    use_original_doc: bool = True  # 是否使用原始文档
    use_tree_index: bool = True    # 是否启用 PageIndex 两阶段检索
    history: Optional[List[Dict[str, str]]] = None  # 对话历史


class ChatResponse(BaseModel):
    answer: str
    sources: list
    original_doc_status: Optional[str] = None  # 原始文档查找状态


class LLMConfigRequest(BaseModel):
    provider: str  # ollama, openai, doubao, qwen
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


def _safe_score(similarity) -> float:
    try:
        v = float(similarity)
        return 0.0 if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return 0.0


@router.post("/chat")
async def rag_chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """智能对话 - 支持 RAG 模式、网络搜索和直接对话模式"""
    import time
    t_start = time.time()
    def _elapsed(label: str, t0: float = None):
        now = time.time()
        since = now - (t0 or t_start)
        total = now - t_start
        print(f"[Chat timing] {label}: +{since:.2f}s (total {total:.2f}s)", flush=True)
        return now

    try:
        history = request.history or []
        web_results = []

        # 如果不使用 RAG，直接调用 LLM
        if not request.use_rag:
            # 如果开启了网络搜索，先搜索网络
            if request.use_web_search:
                web_results = web_search_service.search(request.query, num_results=5)
                if web_results:
                    # 构建网络搜索上下文
                    web_context = "\n\n".join([
                        f"来源 {i+1}: {r['title']}\nURL: {r['url']}\n摘要: {r['snippet']}"
                        for i, r in enumerate(web_results)
                    ])
                    answer = await llm_service.web_search_chat(request.query, web_context, history)
                else:
                    answer = await llm_service.plain_chat(request.query, history)
            else:
                answer = await llm_service.plain_chat(request.query, history)
            return {"answer": answer, "sources": [], "web_sources": web_results}

        # 使用 RAG 模式
        # 检测是否是对比类查询（包含"对比"、"比较"、"vs"、"和"等关键词）
        import re
        comparison_keywords = ['对比', '比较', 'vs', 'versus', '区别', '差异']
        is_comparison = any(kw in request.query.lower() for kw in comparison_keywords)

        # PageIndex 两阶段检索（有树形索引时优先使用）
        tree_referenced_nodes = []
        t_search = time.time()
        if request.use_tree_index and not is_comparison:
            results, tree_referenced_nodes = await SearchService.search_with_tree_index(
                db, request.query, llm_service,
                top_k=request.top_k,
                use_tree=True
            )
        elif is_comparison:
            entities = re.findall(r'[A-Z]{2,}[0-9]+[A-Z0-9]*', request.query)
            if len(entities) >= 2:
                results = SearchService.search_multi_query(db, entities, top_k=request.top_k)
            else:
                results = SearchService.search(db, request.query, top_k=request.top_k * 2)
        else:
            results = SearchService.search(db, request.query, top_k=request.top_k)
        t_search = _elapsed("search/tree_index", t_search)

        # 如果开启了网络搜索，同时搜索网络
        if request.use_web_search:
            web_results = web_search_service.search(request.query, num_results=5)

        if not results and not web_results:
            answer = await llm_service.plain_chat(request.query, history)
            return {"answer": answer, "sources": [], "web_sources": []}

        # 构建上下文 - 增加更多上下文信息
        context_parts = []

        # 添加 RAG 文档内容
        if results:
            # 对于对比查询，按文档分组显示
            if is_comparison:
                doc_groups = {}
                for chunk, score in results:
                    doc_id = chunk.document_id
                    if doc_id not in doc_groups:
                        doc_groups[doc_id] = []
                    doc_groups[doc_id].append(chunk.content)

                # 按文档组织上下文
                for doc_id, contents in doc_groups.items():
                    merged_content = "\n\n".join(contents)
                    context_parts.append(f"【文档 {doc_id}】\n{merged_content}")
            else:
                context_chunks = [chunk.content for chunk, _ in results]
                context_parts.append("【知识库文档】\n" + "\n\n---\n\n".join(context_chunks))

        # 如果启用了原始文档搜索
        from app.models.document import Document
        original_doc_info = []  # 记录原始文档查找情况
        original_contents = []  # 原始文档内容
        t_origdoc = time.time()
        if request.use_original_doc and results:
            # 获取所有涉及的文档 ID，按出现频次排序，只取 top-5
            from collections import Counter
            doc_id_counts = Counter(chunk.document_id for chunk, _ in results)
            doc_ids = [doc_id for doc_id, _ in doc_id_counts.most_common(5)]

            # 查询文档标题
            documents = db.query(Document).filter(Document.id.in_(doc_ids)).all()
            doc_title_map = {doc.id: doc.title for doc in documents}

            # 尝试查找原始文档
            for doc_id in doc_ids:
                title = doc_title_map.get(doc_id)
                if not title:
                    continue

                # 先从 chunks 中提取页码，再传给 find_original_doc
                doc_chunks = [chunk.content for chunk, _ in results if chunk.document_id == doc_id]
                page_numbers = set()
                for chunk_content in doc_chunks:
                    pages = re.findall(r'\[第\s*(\d+)\s*页\]', chunk_content)
                    page_numbers.update([int(p) for p in pages])

                # 扩展页码范围（前后各加1页），无页码时传 None（读全文）
                if page_numbers:
                    expanded_pages = set()
                    for page in page_numbers:
                        expanded_pages.add(max(1, page - 1))
                        expanded_pages.add(page)
                        expanded_pages.add(page + 1)
                    page_info = f"（涉及页码：{', '.join(map(str, sorted(expanded_pages)))}）"
                else:
                    expanded_pages = None
                    page_info = ""

                # 查找原始文档，PDF 只解析目标页
                original_content = original_doc_service.find_original_doc(title, target_pages=expanded_pages)
                if original_content:
                    # 限制原始文档长度，避免超出 token 限制
                    max_length = 8000
                    if len(original_content) > max_length:
                        original_content = original_content[:max_length] + "\n\n...(内容过长，已截断)"

                    original_contents.append(f"【原始文档：{title}】{page_info}\n{original_content}")
                    original_doc_info.append({
                        "title": title,
                        "found": True,
                        "pages": sorted(expanded_pages) if expanded_pages else None
                    })
                else:
                    # 未找到原始文档
                    original_doc_info.append({
                        "title": title,
                        "found": False
                    })

            if original_contents:
                context_parts.append("\n\n".join(original_contents))

        # 添加网络搜索结果
        if web_results:
            web_context = "\n\n".join([
                f"来源 {i+1}: {r['title']}\nURL: {r['url']}\n摘要: {r['snippet']}"
                for i, r in enumerate(web_results)
            ])
            context_parts.append("【网络搜索结果】\n" + web_context)

        # 组合上下文
        full_context = "\n\n".join(context_parts)

        # 构建原始文档查找情况说明（不放入 LLM 上下文，单独返回给前端）
        original_doc_status = ""
        if request.use_original_doc and results:
            if original_doc_info:
                found_docs = [info for info in original_doc_info if info["found"]]
                not_found_docs = [info for info in original_doc_info if not info["found"]]

                if found_docs:
                    original_doc_status = "原始文档查找情况：\n"
                    for info in found_docs:
                        if info["pages"]:
                            original_doc_status += f"✓ 已找到：{info['title']}（参考页码：{', '.join(map(str, info['pages']))}）\n"
                        else:
                            original_doc_status += f"✓ 已找到：{info['title']}\n"

                if not_found_docs:
                    if not original_doc_status:
                        original_doc_status = "原始文档查找情况：\n"
                    for info in not_found_docs:
                        original_doc_status += f"✗ 未找到：{info['title']}（仅使用知识库片段）\n"
            else:
                original_doc_status = "原始文档查找情况：\n✗ 未找到任何原始文档（仅使用知识库片段）"

        t_origdoc = _elapsed("original_doc_lookup", t_origdoc)

        # 调用 LLM（不包含原始文档状态）
        t_llm = time.time()
        if request.use_rag and web_results:
            # 两者都启用时，给出更详细的提示
            answer = await llm_service.rag_chat_with_web(request.query, full_context, history)
        else:
            # 对于对比查询，使用特殊的 prompt
            if is_comparison and results:
                answer = await llm_service.comparison_chat(request.query, full_context, history)
            elif request.use_original_doc and len(original_doc_info) > 0:
                # 如果启用了原始文档搜索且找到了原始文档，使用专门的 prompt
                answer = await llm_service.rag_chat_with_original(request.query, full_context, history)
            else:
                context_chunks = [chunk.content for chunk, _ in results] if results else []
                answer = await llm_service.rag_chat(request.query, context_chunks, history)

        _elapsed("llm_generate", t_llm)
        _elapsed("total", t_start)

        sources = [
            {
                "document_id": chunk.document_id,
                "content": chunk.content,
                "similarity": _safe_score(similarity),
                "section_id": getattr(chunk, 'section_id', None),
                "content_source": getattr(chunk, '_content_source', '知识库')
            }
            for chunk, similarity in results
        ]

        return {
            "answer": answer,
            "sources": sources,
            "web_sources": web_results,
            "original_doc_status": original_doc_status,
            "tree_nodes": tree_referenced_nodes,  # PageIndex 命中的章节节点
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}")


@router.post("/config")
async def configure_llm(config: LLMConfigRequest):
    """配置 LLM 提供商"""
    try:
        llm_service.configure(
            provider=config.provider,
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model
        )
        return {
            "message": "LLM 配置成功",
            "provider": config.provider,
            "model": config.model or "默认模型"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置失败: {str(e)}")


@router.get("/config")
async def get_llm_config():
    """获取当前 LLM 配置"""
    return {
        "provider": llm_service.provider,
        "model": llm_service.model,
        "configured": llm_service.client is not None
    }
