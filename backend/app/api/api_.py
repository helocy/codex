"""
外部 API - 供 AI Agent 调用
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.core.database import get_db
from app.services.search_service import SearchService
from app.services.llm_service import llm_service
from app.services.web_search_service import web_search_service
from app.services.original_doc_service import original_doc_service
from app.api.api_keys import verify_api_key
from app.models.document import Document
import math

router = APIRouter()


# ── 请求模型 ────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class ChatRequest(BaseModel):
    query: str
    use_rag: bool = True
    use_web_search: bool = False
    use_original_doc: bool = True
    top_k: int = 5


class AddDocumentRequest(BaseModel):
    title: str
    content: str
    file_type: str = "text"


# ── 响应模型 ────────────────────────────────────────────────────────────────

class SearchResult(BaseModel):
    content: str
    document_id: int
    similarity: float


class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    web_sources: List[Dict[str, Any]]


# ── 工具函数 ────────────────────────────────────────────────────────────────

def _safe_score(similarity) -> float:
    try:
        v = float(similarity)
        return 0.0 if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return 0.0


# ── API 端点 ────────────────────────────────────────────────────────────────

@router.post("/search", response_model=List[SearchResult])
async def api_search(
    request: SearchRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    搜索知识库

    使用方式：
    ```bash
    curl -X POST http://localhost:8001/api/v1/api/search \\
      -H "Authorization: <API_KEY>" \\
      -H "Content-Type: application/json" \\
      -d '{"query": "什么是 RAG", "top_k": 5}'
    ```
    """
    results = SearchService.search(db, request.query, top_k=request.top_k)

    return [
        SearchResult(
            content=chunk.content,
            document_id=chunk.document_id,
            similarity=_safe_score(similarity)
        )
        for chunk, similarity in results
    ]


@router.post("/chat", response_model=ChatResponse)
async def api_chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    对话（支持 RAG 和网络搜索）

    使用方式：
    ```bash
    curl -X POST http://localhost:8001/api/v1/api/chat \\
      -H "Authorization: <API_KEY>" \\
      -H "Content-Type: application/json" \\
      -d '{"query": "什么是 RAG", "use_rag": true, "use_web_search": false}'
    ```
    """
    web_results = []

    # 如果不使用 RAG
    if not request.use_rag:
        if request.use_web_search:
            web_results = web_search_service.search(request.query, num_results=5)
            if web_results:
                web_context = "\n\n".join([
                    f"来源 {i+1}: {r['title']}\n{r['snippet']}"
                    for i, r in enumerate(web_results)
                ])
                answer = await llm_service.web_search_chat(request.query, web_context, [])
            else:
                answer = await llm_service.plain_chat(request.query, [])
        else:
            answer = await llm_service.plain_chat(request.query, [])

        return ChatResponse(answer=answer, sources=[], web_sources=web_results)

    # 使用 RAG
    # 检测是否是对比类查询
    import re
    comparison_keywords = ['对比', '比较', 'vs', 'versus', '区别', '差异']
    is_comparison = any(kw in request.query.lower() for kw in comparison_keywords)

    # 如果是对比查询，提取实体并使用多查询检索
    if is_comparison:
        entities = re.findall(r'[A-Z]{2,}[0-9]+[A-Z0-9]*', request.query)
        if len(entities) >= 2:
            # 使用多查询检索
            results = SearchService.search_multi_query(db, entities, top_k=request.top_k)
        else:
            # 使用更大的 top_k
            results = SearchService.search(db, request.query, top_k=request.top_k * 2)
    else:
        results = SearchService.search(db, request.query, top_k=request.top_k)

    if request.use_web_search:
        web_results = web_search_service.search(request.query, num_results=5)

    if not results and not web_results:
        answer = await llm_service.plain_chat(request.query, [])
        return ChatResponse(answer=answer, sources=[], web_sources=[])

    context_parts = []

    if results:
        # 对于对比查询，按文档分组
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
    original_doc_info = []  # 记录原始文档查找情况
    original_contents = []  # 原始文档内容
    if request.use_original_doc and results:
        # 获取所有涉及的文档 ID
        doc_ids = list(set([chunk.document_id for chunk, _ in results]))

        # 查询文档标题
        documents = db.query(Document).filter(Document.id.in_(doc_ids)).all()
        doc_title_map = {doc.id: doc.title for doc in documents}

        # 尝试查找原始文档
        for doc_id in doc_ids:
            title = doc_title_map.get(doc_id)
            if not title:
                continue

            # 查找原始文档
            original_content = original_doc_service.find_original_doc(title)
            if original_content:
                # 提取该文档相关的 chunks 中提到的页码
                doc_chunks = [chunk.content for chunk, _ in results if chunk.document_id == doc_id]
                page_numbers = set()
                for chunk_content in doc_chunks:
                    # 匹配 [第 X 页] 格式
                    pages = re.findall(r'\[第\s*(\d+)\s*页\]', chunk_content)
                    page_numbers.update([int(p) for p in pages])

                if page_numbers:
                    # 扩展页码范围（前后各加1页）
                    expanded_pages = set()
                    for page in page_numbers:
                        expanded_pages.add(max(1, page - 1))
                        expanded_pages.add(page)
                        expanded_pages.add(page + 1)

                    page_info = f"（涉及页码：{', '.join(map(str, sorted(expanded_pages)))}）"
                else:
                    page_info = ""

                # 限制原始文档长度，避免超出 token 限制
                max_length = 8000
                if len(original_content) > max_length:
                    original_content = original_content[:max_length] + "\n\n...(内容过长，已截断)"

                original_contents.append(f"【原始文档：{title}】{page_info}\n{original_content}")
                original_doc_info.append({
                    "title": title,
                    "found": True,
                    "pages": sorted(expanded_pages) if page_numbers else None
                })
            else:
                # 未找到原始文档
                original_doc_info.append({
                    "title": title,
                    "found": False
                })

        if original_contents:
            context_parts.append("\n\n".join(original_contents))

    if web_results:
        web_context = "\n\n".join([
            f"来源 {i+1}: {r['title']}\n{r['snippet']}"
            for i, r in enumerate(web_results)
        ])
        context_parts.append("【网络搜索结果】\n" + web_context)

    full_context = "\n\n".join(context_parts)

    # 构建原始文档查找情况说明
    original_doc_status = ""
    if request.use_original_doc and results:
        if original_doc_info:
            found_docs = [info for info in original_doc_info if info["found"]]
            not_found_docs = [info for info in original_doc_info if not info["found"]]

            if found_docs:
                original_doc_status = "【原始文档查找情况】\n"
                for info in found_docs:
                    if info["pages"]:
                        original_doc_status += f"✓ 已找到原始文档：{info['title']}（参考页码：{', '.join(map(str, info['pages']))}）\n"
                    else:
                        original_doc_status += f"✓ 已找到原始文档：{info['title']}\n"

            if not_found_docs:
                if not original_doc_status:
                    original_doc_status = "【原始文档查找情况】\n"
                for info in not_found_docs:
                    original_doc_status += f"✗ 未找到原始文档：{info['title']}（仅使用知识库片段）\n"
        else:
            original_doc_status = "【原始文档查找情况】\n✗ 未找到任何原始文档（仅使用知识库片段）\n"

        # 将原始文档状态添加到上下文开头
        if original_doc_status:
            full_context = original_doc_status + "\n" + full_context

    if request.use_rag and web_results:
        answer = await llm_service.rag_chat_with_web(request.query, full_context, [])
    elif is_comparison and results:
        # 对比查询使用特殊 prompt
        answer = await llm_service.comparison_chat(request.query, full_context, [])
    else:
        # 如果启用了原始文档搜索且找到了原始文档，使用专门的 prompt
        if request.use_original_doc and len(original_doc_info) > 0:
            # 使用包含原始文档的完整上下文
            answer = await llm_service.rag_chat_with_original(request.query, full_context, [])
        else:
            context_chunks = [chunk.content for chunk, _ in results] if results else []
            answer = await llm_service.rag_chat(request.query, context_chunks, [])

    sources = [
        {
            "document_id": chunk.document_id,
            "content": chunk.content,
            "similarity": _safe_score(similarity)
        }
        for chunk, similarity in results
    ]

    return ChatResponse(answer=answer, sources=sources, web_sources=web_results)


@router.post("/documents")
async def api_add_document(
    request: AddDocumentRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    添加文档到知识库

    使用方式：
    ```bash
    curl -X POST http://localhost:8001/api/v1/api/documents \\
      -H "Authorization: <API_KEY>" \\
      -H "Content-Type: application/json" \\
      -d '{"title": "我的文档", "content": "文档内容", "file_type": "text"}'
    ```
    """
    from app.models.document import Document, Chunk
    from app.services.embedding_service import embedding_service

    # 创建文档
    document = Document(
        title=request.title,
        content=request.content,
        file_type=request.file_type,
        file_path=None
    )
    db.add(document)
    db.flush()

    # 生成 embedding
    chunks_text = [request.content]
    embeddings = embedding_service.encode(chunks_text)

    # 创建 chunk
    chunk = Chunk(
        document_id=document.id,
        content=request.content,
        chunk_index=0,
        embedding=embeddings[0].tolist() if hasattr(embeddings[0], 'tolist') else embeddings[0]
    )
    db.add(chunk)
    db.commit()

    return {
        "message": "文档添加成功",
        "document_id": document.id,
        "chunk_count": 1
    }


@router.get("/documents")
async def api_list_documents(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    列出知识库中的文档

    使用方式：
    ```bash
    curl -X GET "http://localhost:8001/api/v1/api/documents?limit=10&offset=0" \\
      -H "Authorization: <API_KEY>"
    ```
    """
    from app.models.document import Document

    total = db.query(Document).count()
    documents = db.query(Document).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "documents": [
            {
                "id": doc.id,
                "title": doc.title,
                "file_type": doc.file_type,
                "created_at": doc.created_at.isoformat()
            }
            for doc in documents
        ]
    }


@router.delete("/documents/{document_id}")
async def api_delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    删除文档

    使用方式：
    ```bash
    curl -X DELETE http://localhost:8001/api/v1/api/documents/123 \\
      -H "Authorization: <API_KEY>"
    ```
    """
    from app.models.document import Document, Chunk
    import os

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 删除文件
    if document.file_path and os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except Exception:
            pass

    # 删除 chunks
    db.query(Chunk).filter(Chunk.document_id == document_id).delete()
    db.delete(document)
    db.commit()

    return {"message": f"文档 {document_id} 已删除"}


@router.get("/stats")
async def api_stats(
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    获取知识库统计信息

    使用方式：
    ```bash
    curl -X GET http://localhost:8001/api/v1/api/stats \\
      -H "Authorization: <API_KEY>"
    ```
    """
    from sqlalchemy import func
    from app.models.document import Document, Chunk
    from app.services.embedding_service import embedding_service

    doc_count = db.query(func.count(Document.id)).scalar()
    chunk_count = db.query(func.count(Chunk.id)).scalar()
    embedding_config = embedding_service.get_config()

    return {
        "document_count": doc_count,
        "chunk_count": chunk_count,
        "embedding_provider": embedding_config["provider"],
        "embedding_model": embedding_config["model"]
    }


@router.get("/health")
async def api_health(
    api_key: str = Depends(verify_api_key)
):
    """
    健康检查

    使用方式：
    ```bash
    curl -X GET http://localhost:8001/api/v1/api/health \\
      -H "Authorization: <API_KEY>"
    ```
    """
    return {
        "status": "ok",
        "service": "Codex API",
        "version": "0.2.0"
    }
