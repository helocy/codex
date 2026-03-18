from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db, SessionLocal
from app.core.config import settings
from app.models.document import Document, FileType, Chunk
from app.services.file_processor import FileProcessor
from app.services.embedding_service import embedding_service
from app.services.page_index_service import page_index_service
from app.services.llm_service import llm_service
from pydantic import BaseModel
import os
import shutil
import json
from datetime import datetime
from typing import Generator

router = APIRouter()


class TextInput(BaseModel):
    content: str
    title: str = None


@router.post("/text")
async def save_text(
    text_input: TextInput,
    skip_duplicate: bool = False,  # 是否跳过相似文档检测（强制上传）
    overwrite: bool = False,       # 是否覆盖同名文档
    check_similar: bool = True,    # 是否检查相似文档
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """保存纯文本内容

    Args:
        text_input: 文本内容
        skip_duplicate: 是否跳过重复文档
        check_similar: 是否检查相似文档
    """
    try:
        content = text_input.content.strip()
        if not content:
            raise HTTPException(status_code=400, detail="内容不能为空")

        # 生成标题（如果没有提供）
        title = text_input.title or f"文本记录_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # ===== 重复检查 =====
        # 检查同名文档是否已存在
        existing_doc = db.query(Document).filter(Document.title == title).first()
        if existing_doc:
            if overwrite:
                # 覆盖模式：删除旧文档
                db.query(Chunk).filter(Chunk.document_id == existing_doc.id).delete()
                db.delete(existing_doc)
                db.commit()
            else:
                raise HTTPException(
                    status_code=409,
                    detail=f"文档「{title}」已存在，ID: {existing_doc.id}。如需覆盖，请勾选「覆盖上传」。"
                )

        # ===== 相似文档检查 =====
        similar_docs = []
        if check_similar:
            similar_docs = find_similar_documents(db, content, title)

        # 如果找到相似文档，提示用户
        if similar_docs and not skip_duplicate:
            return {
                "message": "发现相似文档",
                "similar_documents": similar_docs,
                "suggestion": "可以先查看相似文档，或使用 skip_duplicate=true 强制保存"
            }

        # 创建文档记录
        document = Document(
            title=title,
            content=content,
            file_type=FileType.TEXT,
            file_path=None,
            file_size=len(content.encode('utf-8'))
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        # 文本分块
        chunks = FileProcessor.chunk_text(content, chunk_size=1000)

        # 批量生成向量（一次 API 调用）并存储
        embeddings = embedding_service.encode(chunks)
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk = Chunk(
                document_id=document.id,
                content=chunk_text,
                embedding=embedding.tolist(),
                chunk_index=idx
            )
            db.add(chunk)

        db.commit()

        # 后台异步生成树形索引
        if background_tasks is not None:
            background_tasks.add_task(_build_tree_index_background, document.id)

        return {
            "message": "文本保存成功",
            "document_id": document.id,
            "title": document.title,
            "chunks_count": len(chunks),
            "tree_index_status": "pending"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def find_similar_documents(db: Session, content: str, title: str, threshold: float = 0.8, limit: int = 3) -> list:
    """查找相似的文档（只取每篇文档的第一个 chunk 做代表，避免全量扫描）"""
    import numpy as np

    # 对新文档内容生成 embedding
    query_embedding = embedding_service.encode_single(content[:5000])  # 取前 5000 字符

    # 只取每篇文档的第一个 chunk（chunk_index=0）作为代表
    chunks = db.query(Chunk).filter(Chunk.chunk_index == 0).all()

    similar_docs = []
    for chunk in chunks:
        if not chunk.embedding:
            continue

        chunk_emb = np.array(chunk.embedding)
        similarity = np.dot(query_embedding, chunk_emb) / (
            np.linalg.norm(query_embedding) * np.linalg.norm(chunk_emb) + 1e-8
        )

        if similarity >= threshold:
            doc_id = chunk.document_id
            if doc_id not in [d['id'] for d in similar_docs]:
                doc = db.query(Document).filter(Document.id == doc_id).first()
                if doc and doc.title != title:  # 排除自己
                    similar_docs.append({
                        "id": doc.id,
                        "title": doc.title,
                        "similarity": float(similarity)
                    })

    # 按相似度排序，返回 top N
    similar_docs.sort(key=lambda x: x['similarity'], reverse=True)
    return similar_docs[:limit]


async def _build_tree_index_background(document_id: int):
    """后台任务：为文档生成树形索引（不阻塞上传响应）"""
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document and llm_service.client:
            await page_index_service.build(document, db, llm_service)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"后台树形索引生成失败: {e}")
    finally:
        db.close()


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    skip_duplicate: bool = False,  # 是否跳过相似文档检测（强制上传）
    overwrite: bool = False,       # 是否覆盖同名文档
    check_similar: bool = True,    # 是否检查相似文档
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """上传文件并处理"""
    try:
        # 确定文件类型
        file_ext = os.path.splitext(file.filename)[1].lower()
        file_type_map = {
            ".txt": FileType.TEXT,
            ".pdf": FileType.PDF,
            ".docx": FileType.WORD,
            ".doc": FileType.WORD,
            ".md": FileType.MARKDOWN,
        }

        if file_ext not in file_type_map:
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file_ext}")

        file_type = file_type_map[file_ext]

        # ===== 重复检查 =====
        # 检查同名文档是否已存在
        existing_doc = db.query(Document).filter(Document.title == file.filename).first()
        if existing_doc:
            if overwrite:
                # 覆盖模式：删除旧文档
                db.query(Chunk).filter(Chunk.document_id == existing_doc.id).delete()
                db.delete(existing_doc)
                db.commit()
            else:
                raise HTTPException(
                    status_code=409,
                    detail=f"文档「{file.filename}」已存在，ID: {existing_doc.id}。如需覆盖，请勾选「覆盖上传」。"
                )

        # ===== 提取文本（用于相似度检查）=====
        # 先临时保存文件
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{os.path.basename(file.filename)}"
        temp_file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 提取文本
        try:
            if file_type == FileType.PDF:
                text = FileProcessor.extract_text_from_pdf(temp_file_path)
            elif file_type == FileType.WORD:
                text = FileProcessor.extract_text_from_docx(temp_file_path)
            elif file_type == FileType.MARKDOWN:
                text = FileProcessor.extract_text_from_markdown(temp_file_path)
            else:
                with open(temp_file_path, "r", encoding="utf-8") as f:
                    text = f.read()
        except Exception:
            text = ""

        # ===== 相似文档检查 =====
        similar_docs = []
        if check_similar and text.strip():
            similar_docs = find_similar_documents(db, text, file.filename)

        # 如果找到相似文档，提示用户
        if similar_docs and not skip_duplicate:
            # 删除临时文件
            os.remove(temp_file_path)
            return {
                "message": "发现相似文档",
                "similar_documents": similar_docs,
                "suggestion": "可以先查看相似文档，或使用 skip_duplicate=true 强制上传"
            }

        # 使用临时文件作为最终存储
        file_path = temp_file_path
        file_size = os.path.getsize(file_path)

        # 创建文档记录
        document = Document(
            title=file.filename,
            content=text,
            file_type=file_type,
            file_path=file_path,
            file_size=file_size
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        # 文本分块（Markdown/PDF 使用感知分块，其他格式字符分块）
        if file_type == FileType.MARKDOWN:
            chunks = FileProcessor.chunk_markdown(text)
        elif file_type == FileType.PDF:
            chunks = FileProcessor.chunk_pdf(file_path)
        else:
            chunks = FileProcessor.chunk_text(text)

        # 批量生成向量（一次 API 调用）并存储
        embeddings = embedding_service.encode(chunks)
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk = Chunk(
                document_id=document.id,
                content=chunk_text,
                embedding=embedding.tolist(),
                chunk_index=idx
            )
            db.add(chunk)

        db.commit()

        # 后台异步生成树形索引（不阻塞响应）
        if background_tasks is not None:
            background_tasks.add_task(_build_tree_index_background, document.id)

        return {
            "message": "文件上传成功",
            "document_id": document.id,
            "title": document.title,
            "chunks_count": len(chunks),
            "tree_index_status": "pending"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def generate_sse_events(directory_path: str, db: Session, skip_duplicate: bool = True) -> Generator[str, None, None]:
    """生成 SSE 事件流

    Args:
        directory_path: 要上传的目录路径
        db: 数据库会话
        skip_duplicate: 是否跳过重复文档（默认 True）
    """
    try:
        # 查找所有 Markdown 文件
        md_files = []
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file.endswith('.md'):
                    md_files.append(os.path.join(root, file))

        if not md_files:
            yield json.dumps({"type": "error", "message": "目录中没有找到 Markdown 文件"}) + "\n"
            return

        total_files = len(md_files)
        uploaded_count = 0
        skipped_count = 0
        total_chunks = 0
        errors = []

        yield json.dumps({
            "type": "start",
            "message": f"开始处理目录，共 {total_files} 个 Markdown 文件（skip_duplicate={skip_duplicate}）",
            "total": total_files
        }) + "\n"

        for idx, file_path in enumerate(md_files):
            try:
                file_name = os.path.basename(file_path)
                yield json.dumps({
                    "type": "progress",
                    "message": f"正在处理: {file_name}",
                    "current": idx + 1,
                    "total": total_files,
                    "file": file_name
                }) + "\n"

                # 读取 Markdown 文件
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()

                if not text.strip():
                    yield json.dumps({
                        "type": "skip",
                        "message": f"跳过空文件: {file_name}",
                        "file": file_name
                    }) + "\n"
                    continue

                # 使用相对路径作为标题
                rel_path = os.path.relpath(file_path, directory_path)
                title = rel_path

                # ===== 检查重复 =====
                existing_doc = db.query(Document).filter(Document.title == title).first()
                if existing_doc:
                    if skip_duplicate:
                        skipped_count += 1
                        yield json.dumps({
                            "type": "skip",
                            "message": f"跳过重复文档: {file_name}（已存在，ID: {existing_doc.id}）",
                            "file": file_name,
                            "existing_id": existing_doc.id
                        }) + "\n"
                        continue
                    else:
                        # 不跳过，删除旧文档
                        db.query(Chunk).filter(Chunk.document_id == existing_doc.id).delete()
                        db.delete(existing_doc)
                        db.commit()
                        yield json.dumps({
                            "type": "replacing",
                            "message": f"替换旧文档: {file_name}（旧 ID: {existing_doc.id}）",
                            "file": file_name,
                            "old_id": existing_doc.id
                        }) + "\n"

                file_size = os.path.getsize(file_path)

                # 创建文档记录
                document = Document(
                    title=title,
                    content=text,
                    file_type=FileType.MARKDOWN,
                    file_path=file_path,
                    file_size=file_size
                )
                db.add(document)
                db.commit()
                db.refresh(document)

                # Markdown 感知分块
                chunks = FileProcessor.chunk_markdown(text)

                # 生成向量并存储
                for chunk_idx, chunk_text in enumerate(chunks):
                    embedding = embedding_service.encode_single(chunk_text)
                    chunk = Chunk(
                        document_id=document.id,
                        content=chunk_text,
                        embedding=embedding.tolist(),
                        chunk_index=chunk_idx
                    )
                    db.add(chunk)

                db.commit()
                uploaded_count += 1
                total_chunks += len(chunks)

                yield json.dumps({
                    "type": "success",
                    "message": f"✓ 已处理: {file_name} ({len(chunks)} 个文本块)",
                    "file": file_name,
                    "chunks": len(chunks)
                }) + "\n"

            except Exception as e:
                error_msg = f"✗ 处理失败: {os.path.basename(file_path)} - {str(e)}"
                errors.append(error_msg)
                yield json.dumps({
                    "type": "error",
                    "message": error_msg,
                    "file": os.path.basename(file_path)
                }) + "\n"
                db.rollback()

        # 返回完成结果
        msg = f"处理完成！共上传 {uploaded_count} 个文件"
        if skipped_count > 0:
            msg += f"，跳过 {skipped_count} 个重复文档"
        msg += f"，{total_chunks} 个文本块"

        yield json.dumps({
            "type": "complete",
            "message": msg,
            "uploaded_count": uploaded_count,
            "skipped_count": skipped_count,
            "total_chunks": total_chunks,
            "errors": errors if errors else None
        }) + "\n"

    except Exception as e:
        yield json.dumps({"type": "error", "message": f"发生错误: {str(e)}"}) + "\n"


@router.get("/upload-directory")
async def upload_directory_sse(
    directory_path: str,
    skip_duplicate: bool = True,
    db: Session = Depends(get_db)
):
    """使用 SSE 流式上传整个 Markdown 目录

    Args:
        directory_path: 目录路径
        skip_duplicate: 是否跳过重复文档（默认 True）
    """
    try:
        if not os.path.exists(directory_path):
            raise HTTPException(status_code=400, detail=f"目录不存在: {directory_path}")

        if not os.path.isdir(directory_path):
            raise HTTPException(status_code=400, detail=f"路径不是目录: {directory_path}")

        return StreamingResponse(
            generate_sse_events(directory_path, db, skip_duplicate),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Expose-Headers": "*",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
async def list_documents(db: Session = Depends(get_db)):
    """获取所有文档列表"""
    documents = db.query(Document).order_by(Document.created_at.desc()).all()
    return {
        "documents": [
            {
                "id": doc.id,
                "title": doc.title,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "created_at": doc.created_at.isoformat(),
                "has_tree_index": doc.tree_index is not None,
            }
            for doc in documents
        ]
    }


@router.post("/batch-build-tree-index")
async def batch_build_tree_index(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """为所有没有树形索引的文档批量触发 PageIndex 构建（后台异步执行）"""
    docs_without_index = db.query(Document).filter(Document.tree_index == None).all()
    count = len(docs_without_index)
    for doc in docs_without_index:
        background_tasks.add_task(_build_tree_index_background, doc.id)
    return {
        "message": f"已触发 {count} 篇文档的树形索引构建",
        "triggered_count": count,
        "document_ids": [doc.id for doc in docs_without_index],
    }


@router.post("/documents/{document_id}/build-tree-index")
async def build_document_tree_index(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """手动触发为指定文档重建 PageIndex 树形索引"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    background_tasks.add_task(_build_tree_index_background, document_id)
    return {"message": f"已触发文档「{document.title}」的树形索引重建", "document_id": document_id}


@router.get("/documents/{document_id}/tree-index")
async def get_document_tree_index(document_id: int, db: Session = Depends(get_db)):
    """获取文档的 PageIndex 树形索引"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {
        "document_id": document_id,
        "title": document.title,
        "has_tree_index": document.tree_index is not None,
        "tree_index": document.tree_index,
    }


@router.get("/documents/{document_id}")
async def get_document(document_id: int, db: Session = Depends(get_db)):
    """获取文档详情"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    return {
        "id": document.id,
        "title": document.title,
        "content": document.content,
        "file_type": document.file_type,
        "created_at": document.created_at.isoformat()
    }
