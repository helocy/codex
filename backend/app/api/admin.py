from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from app.core.database import get_db
from app.models.document import Document, Chunk
from app.services.embedding_service import embedding_service
from app.services.original_doc_service import original_doc_service
import os
import json
import io
from datetime import datetime

router = APIRouter()


# ========== 原始文档路径管理 ==========

@router.get("/original-doc-paths")
async def get_original_doc_paths():
    """获取原始文档搜索路径列表"""
    return {"paths": original_doc_service.get_paths()}


@router.post("/original-doc-paths")
async def add_original_doc_path(path: str):
    """添加原始文档搜索路径"""
    result = original_doc_service.add_path(path)
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])
    return result


@router.delete("/original-doc-paths")
async def remove_original_doc_path(path: str):
    """删除原始文档搜索路径"""
    result = original_doc_service.remove_path(path)
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])
    return result


@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """获取数据库统计信息"""
    doc_count = db.query(func.count(Document.id)).scalar()
    chunk_count = db.query(func.count(Chunk.id)).scalar()

    # 获取 PostgreSQL 数据库大小
    try:
        result = db.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))")).fetchone()
        db_size = result[0] if result else "未知"
    except Exception:
        db_size = "未知"

    # 计算各类型文档数量
    type_counts = (
        db.query(Document.file_type, func.count(Document.id))
        .group_by(Document.file_type)
        .all()
    )

    # 获取当前 embedding 配置
    embedding_config = embedding_service.get_config()

    return {
        "document_count": doc_count,
        "chunk_count": chunk_count,
        "db_size": db_size,
        "type_counts": {str(t): c for t, c in type_counts},
        "embedding_provider": embedding_config["provider"],
        "embedding_model": embedding_config["model"],
    }


@router.delete("/documents/{document_id}")
async def delete_document(document_id: int, db: Session = Depends(get_db)):
    """删除指定文档及其所有向量块"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 删除文件
    if document.file_path and os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except Exception:
            pass

    # 删除 chunks 和 document
    db.query(Chunk).filter(Chunk.document_id == document_id).delete()
    db.delete(document)
    db.commit()

    return {"message": f"文档 #{document_id} 已删除"}


@router.delete("/reset")
async def reset_database(db: Session = Depends(get_db)):
    """重置知识库，清空所有数据"""
    # 查出所有文件路径，删除文件
    documents = db.query(Document).all()
    for doc in documents:
        if doc.file_path and os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
            except Exception:
                pass

    db.query(Chunk).delete()
    db.query(Document).delete()
    db.commit()

    return {"message": "知识库已重置，所有数据已清空"}


@router.get("/export")
async def export_database(db: Session = Depends(get_db)):
    """导出数据库为 JSON 文件"""
    try:
        # 导出所有文档和向量块
        documents = db.query(Document).all()

        export_data = {
            "version": "1.0",
            "export_time": datetime.now().isoformat(),
            "embedding_config": embedding_service.get_config(),
            "documents": []
        }

        for doc in documents:
            chunks = db.query(Chunk).filter(Chunk.document_id == doc.id).all()

            doc_data = {
                "title": doc.title,
                "file_type": doc.file_type.value if hasattr(doc.file_type, 'value') else str(doc.file_type),
                "content": doc.content,
                "created_at": doc.created_at.isoformat(),
                "chunks": []
            }

            for chunk in chunks:
                # 安全地转换 embedding
                embedding_list = None
                if chunk.embedding is not None:
                    try:
                        import numpy as np
                        if isinstance(chunk.embedding, np.ndarray):
                            embedding_list = chunk.embedding.tolist()
                        elif hasattr(chunk.embedding, 'tolist'):
                            embedding_list = chunk.embedding.tolist()
                        else:
                            embedding_list = list(chunk.embedding)
                    except Exception as e:
                        print(f"[WARNING] Failed to convert embedding for chunk {chunk.id}: {e}")
                        embedding_list = None

                doc_data["chunks"].append({
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "embedding": embedding_list
                })

            export_data["documents"].append(doc_data)

        # 生成 JSON 字符串
        json_str = json.dumps(export_data, ensure_ascii=False, indent=2)

        # 创建文件流
        file_stream = io.BytesIO(json_str.encode('utf-8'))

        # 生成文件名
        filename = f"codex_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        return StreamingResponse(
            file_stream,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        import traceback
        print(f"[ERROR] Export failed: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.post("/import")
async def import_database(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """从 JSON 文件导入数据库"""
    try:
        # 读取上传的文件
        content = await file.read()
        import_data = json.loads(content.decode('utf-8'))

        # 验证数据格式
        if "documents" not in import_data:
            raise HTTPException(status_code=400, detail="无效的备份文件格式")

        # 检查 embedding 模型是否匹配
        current_config = embedding_service.get_config()
        backup_config = import_data.get("embedding_config", {})

        if backup_config:
            backup_provider = backup_config.get("provider")
            backup_model = backup_config.get("model")

            if backup_provider != current_config["provider"] or backup_model != current_config["model"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Embedding 模型不匹配！\n\n"
                           f"备份文件使用: {backup_provider} / {backup_model}\n"
                           f"当前数据库使用: {current_config['provider']} / {current_config['model']}\n\n"
                           f"请在「设置」页面切换到相同的 embedding 模型，或使用匹配的备份文件。"
                )

        # 统计信息
        imported_docs = 0
        imported_chunks = 0

        # 导入文档和向量块
        for doc_data in import_data["documents"]:
            # 创建文档
            document = Document(
                title=doc_data["title"],
                file_type=doc_data["file_type"],
                content=doc_data.get("content", ""),
                file_path=None  # 导入的文档没有原始文件
            )
            db.add(document)
            db.flush()  # 获取 document.id

            # 创建向量块
            for chunk_data in doc_data.get("chunks", []):
                embedding = None
                if chunk_data["embedding"]:
                    # 转换为 Python list，避免 numpy 类型问题
                    embedding = [float(x) for x in chunk_data["embedding"]]

                chunk = Chunk(
                    document_id=document.id,
                    content=chunk_data["content"],
                    chunk_index=chunk_data["chunk_index"],
                    embedding=embedding
                )
                db.add(chunk)
                imported_chunks += 1

            imported_docs += 1

        db.commit()

        return {
            "message": "导入成功",
            "imported_documents": imported_docs,
            "imported_chunks": imported_chunks
        }
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="无效的 JSON 文件")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")
