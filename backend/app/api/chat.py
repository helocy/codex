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
    use_code_analysis: bool = False  # 是否启用远程源码分析
    history: Optional[List[Dict[str, str]]] = None  # 对话历史
    local_context: Optional[List[str]] = None  # 用户本地文档搜索结果（存储在浏览器，不在服务端）
    user_llm_config: Optional[Dict] = None     # 用户自定义 LLM 配置（仅对该请求生效，不影响全局）


class ChatResponse(BaseModel):
    answer: str
    sources: list
    original_doc_status: Optional[str] = None  # 原始文档查找状态


class LLMConfigRequest(BaseModel):
    provider: str  # ollama, openai, doubao, qwen
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


class CodeAnalysisLLMConfigRequest(BaseModel):
    provider: str  # anthropic | openai | doubao | 留空禁用
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


def _safe_score(similarity) -> float:
    try:
        v = float(similarity)
        return 0.0 if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return 0.0


def _extract_rag_hints(results, original_contents: list) -> str:
    """从 RAG 结果和原始文档内容中提取关键线索，供代码分析 agent 使用。"""
    import re
    hints = []

    # 从 RAG chunks 提取
    for chunk, _ in (results or []):
        text = getattr(chunk, 'content', '') or ''
        # 文件路径（.c/.h/.dts/.dtsi/.mk 等）
        for m in re.findall(r'[\w./\-]+\.(?:c|h|dts|dtsi|mk|kconfig|S|cpp|cc)[\w./\-]*', text, re.IGNORECASE):
            hints.append(f'- 文件路径：{m}')
        # 函数名（snake_case 含 _init/_probe/_config/_setup/_enable 等）
        for m in re.findall(r'\b\w+(?:_init|_probe|_config|_setup|_enable|_disable|_open|_close|_ioctl|_ops)\b', text):
            hints.append(f'- 函数名：{m}')
        # 全大写宏/寄存器名（至少 3 字符）
        for m in re.findall(r'\b[A-Z][A-Z0-9_]{2,}\b', text):
            hints.append(f'- 宏/寄存器：{m}')

    # 从原始文档内容提取
    for orig in (original_contents or []):
        for m in re.findall(r'[\w./\-]+\.(?:c|h|dts|dtsi|mk)[\w./\-]*', orig, re.IGNORECASE):
            hints.append(f'- 文件路径：{m}')
        for m in re.findall(r'\b\w+(?:_init|_probe|_config|_setup|_enable|_disable|_open|_close|_ioctl|_ops)\b', orig):
            hints.append(f'- 函数名：{m}')
        for m in re.findall(r'\b[A-Z][A-Z0-9_]{2,}\b', orig):
            hints.append(f'- 宏/寄存器：{m}')

    if not hints:
        return ''

    # 去重，限制总长度
    seen = set()
    deduped = []
    for h in hints:
        if h not in seen:
            seen.add(h)
            deduped.append(h)

    result = '\n'.join(deduped)
    return result[:1000]


@router.post("/chat")
async def rag_chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """智能对话 - 支持 RAG 模式、网络搜索和直接对话模式"""
    import time
    t_start = time.time()
    _timings: dict = {}
    def _elapsed(label: str, t0: float = None):
        now = time.time()
        since = now - (t0 or t_start)
        total = now - t_start
        _timings[label] = round(since, 2)
        print(f"[Chat timing] {label}: +{since:.2f}s (total {total:.2f}s)", flush=True)
        return now

    try:
        history = request.history or []
        web_results = []

        # 如果用户提供了自定义 LLM 配置，创建临时实例（不影响全局配置）
        active_llm = llm_service
        if request.user_llm_config:
            from app.services.llm_service import LLMService
            _tmp = LLMService()
            try:
                _tmp.configure(
                    provider=request.user_llm_config.get('provider', 'custom'),
                    api_key=request.user_llm_config.get('api_key'),
                    base_url=request.user_llm_config.get('base_url'),
                    model=request.user_llm_config.get('model'),
                )
                active_llm = _tmp
            except Exception:
                pass  # 配置失败时回退到全局 LLM

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
                    answer = await active_llm.web_search_chat(request.query, web_context, history)
                else:
                    answer = await active_llm.plain_chat(request.query, history)
            else:
                answer = await active_llm.plain_chat(request.query, history)
            return {"answer": answer, "sources": [], "web_sources": web_results}

        # 使用 RAG 模式
        import re, asyncio
        comparison_keywords = ['对比', '比较', 'vs', 'versus', '区别', '差异']
        is_comparison = any(kw in request.query.lower() for kw in comparison_keywords)

        # 提取芯片型号（代码分析将在 RAG 完成后串行执行）
        chip_pattern = re.compile(r'[A-Z]{2,}[0-9]+[A-Z0-9]*', re.IGNORECASE)
        queried_models = chip_pattern.findall(request.query)
        t_code = time.time()

        # PageIndex 两阶段检索（有树形索引时优先使用）
        tree_referenced_nodes = []
        t_search = time.time()
        if request.use_tree_index and not is_comparison:
            results, tree_referenced_nodes = await SearchService.search_with_tree_index(
                db, request.query, active_llm,
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

        # 如果 query 中提到了特定芯片/产品型号，将匹配文档的 chunk 提到最前面
        if queried_models and results:
            from app.models.document import Document as _Doc
            result_doc_ids = list({c.document_id for c, _ in results})
            doc_titles = {d.id: d.title for d in db.query(_Doc).filter(_Doc.id.in_(result_doc_ids)).all()}
            def _matches_model(doc_id: int) -> bool:
                title = doc_titles.get(doc_id, '').upper()
                return any(m.upper() in title for m in queried_models)
            matched = [(c, s) for c, s in results if _matches_model(c.document_id)]
            others = [(c, s) for c, s in results if not _matches_model(c.document_id)]
            results = matched + others

        # 如果开启了网络搜索，同时搜索网络
        if request.use_web_search:
            web_results = web_search_service.search(request.query, num_results=5)

        if not results and not web_results and not request.local_context:
            answer = await active_llm.plain_chat(request.query, history)
            return {"answer": answer, "sources": [], "web_sources": []}

        # 构建上下文 - 增加更多上下文信息
        context_parts = []

        # 添加用户本地文档搜索结果（存储在浏览器端，非服务端）
        if request.local_context:
            context_parts.append("【我的文档（本地）】\n" + "\n\n---\n\n".join(request.local_context))

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
                # 查询文档标题，让 LLM 知道每个片段来自哪个文档
                from app.models.document import Document as Doc
                doc_ids_in_results = list({chunk.document_id for chunk, _ in results})
                doc_title_map_r = {d.id: d.title for d in db.query(Doc).filter(Doc.id.in_(doc_ids_in_results)).all()}
                context_chunks = [
                    f"[来源：{doc_title_map_r.get(chunk.document_id, str(chunk.document_id))}]\n{chunk.content}"
                    for chunk, _ in results
                ]
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

            # 查询文档标题和保存路径
            documents = db.query(Document).filter(Document.id.in_(doc_ids)).all()
            doc_title_map = {doc.id: doc.title for doc in documents}
            doc_file_path_map = {doc.id: doc.file_path for doc in documents}

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

                # 查找原始文档：优先用 file_path 直接命中，失败再搜索目录
                saved_path = doc_file_path_map.get(doc_id)
                original_content = original_doc_service.find_original_doc(
                    title, target_pages=expanded_pages, file_path=saved_path
                )
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

        # 串行执行代码分析（RAG + 原始文档完成后，提取线索再调用）
        code_analysis_result = None
        if request.use_code_analysis:
            from app.services.code_analysis_service import analyze_code_sync
            rag_hints = _extract_rag_hints(results, original_contents)
            t_code = time.time()
            try:
                code_analysis_result = await asyncio.to_thread(
                    analyze_code_sync, request.query, queried_models,
                    active_llm.client, active_llm.model, rag_hints,
                )
                _elapsed("code_analysis", t_code)
            except Exception as e:
                code_analysis_result = f"[代码分析异常] {e}"
                print(f"[CodeAnalysis] error: {e}", flush=True)

        # 组装完整上下文（代码分析结果追加在最后，过滤思考过程）
        import re as _re2
        def _clean_think(t: str) -> str:
            s = _re2.sub(r'<think(?:ing)?>[\s\S]*?</think(?:ing)?>', '', t, flags=_re2.IGNORECASE)
            s = _re2.sub(r'<think(?:ing)>[\s\S]*$', '', s, flags=_re2.IGNORECASE)
            return s.strip()
        if code_analysis_result:
            context_parts.append(f"【SDK 源码分析结果】\n{_clean_think(code_analysis_result)}")
        full_context = "\n\n".join(context_parts)

        # 调用 LLM（不包含原始文档状态）
        t_llm = time.time()
        if request.use_rag and web_results:
            answer = await active_llm.rag_chat_with_web(request.query, full_context, history)
        else:
            if is_comparison and results:
                answer = await active_llm.comparison_chat(request.query, full_context, history)
            elif request.use_original_doc and len(original_doc_info) > 0:
                answer = await active_llm.rag_chat_with_original(request.query, full_context, history)
            else:
                if code_analysis_result and not code_analysis_result.startswith("[代码分析"):
                    answer = await active_llm.rag_chat_with_original(request.query, full_context, history)
                elif context_parts:
                    answer = await active_llm.rag_chat_with_original(request.query, full_context, history)
                else:
                    context_chunks = [chunk.content for chunk, _ in results] if results else []
                    answer = await active_llm.rag_chat(request.query, context_chunks, history)

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

        is_code_error = code_analysis_result and code_analysis_result.startswith("[代码分析")
        # 过滤掉 <think>...</think> 内部推理块，只保留最终结论
        import re as _re
        def _strip_think(text: str) -> str:
            if not text:
                return text
            # 过滤完整闭合的 <think>...</think>
            stripped = _re.sub(r'<think(?:ing)?>[\s\S]*?</think(?:ing)?>', '', text, flags=_re.IGNORECASE)
            # 过滤未闭合的 <think> 到末尾
            stripped = _re.sub(r'<think(?:ing)?>[\.\s\S]*$', '', stripped, flags=_re.IGNORECASE)
            return stripped.strip()
        code_detail_clean = _strip_think(code_analysis_result) if code_analysis_result and not is_code_error else None
        return {
            "answer": answer,
            "sources": sources,
            "web_sources": web_results,
            "original_doc_status": original_doc_status,
            "tree_nodes": tree_referenced_nodes,
            "code_analysis_status": "" if not code_analysis_result or is_code_error else "已分析源码",
            "code_analysis_detail": code_detail_clean,
            "timings": _timings,
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


@router.post("/code-analysis-config")
async def configure_code_analysis_llm(config: CodeAnalysisLLMConfigRequest):
    """配置代码分析专用 LLM"""
    try:
        from app.core.config import settings
        settings.CODE_ANALYSIS_LLM_PROVIDER = config.provider
        settings.CODE_ANALYSIS_API_KEY = config.api_key or ""
        settings.CODE_ANALYSIS_BASE_URL = config.base_url or ""
        settings.CODE_ANALYSIS_MODEL = config.model or "claude-sonnet-4-6"
        return {
            "message": "代码分析 LLM 配置成功",
            "provider": config.provider,
            "model": config.model or "claude-sonnet-4-6",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置失败: {str(e)}")


@router.get("/code-analysis-config")
async def get_code_analysis_llm_config():
    """获取代码分析 LLM 配置"""
    from app.core.config import settings
    return {
        "provider": settings.CODE_ANALYSIS_LLM_PROVIDER or "",
        "model": settings.CODE_ANALYSIS_MODEL or "claude-sonnet-4-6",
        "base_url": settings.CODE_ANALYSIS_BASE_URL or "",
        "configured": bool(settings.CODE_ANALYSIS_LLM_PROVIDER and settings.CODE_ANALYSIS_API_KEY),
    }
