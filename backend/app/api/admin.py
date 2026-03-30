from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.models.document import Document, Chunk
from app.services.embedding_service import embedding_service
from app.services.original_doc_service import original_doc_service
from app.services.search_service import SearchService
import os
import json
import io
from datetime import datetime

router = APIRouter(dependencies=[Depends(require_admin)])


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
    # 清理死元组，确保 pg_database_size 准确
    try:
        db.execute(text("VACUUM chunks, documents"))
        db.commit()
    except Exception:
        pass

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


@router.get("/duplicates")
async def find_duplicates(threshold: float = 0.97, db: Session = Depends(get_db)):
    """检测冗余文档：用每篇文档前5个chunk的平均向量做两两比较，返回高度相似的文档对"""
    import numpy as np
    from collections import defaultdict

    # 取每篇文档前5个chunk，计算平均向量作为文档代表
    all_chunks = (
        db.query(Chunk)
        .filter(Chunk.chunk_index < 5)
        .all()
    )

    # 按文档分组，计算平均 embedding
    doc_chunks: dict = defaultdict(list)
    for c in all_chunks:
        if c.embedding:
            doc_chunks[c.document_id].append(np.array(c.embedding, dtype=np.float32))

    if len(doc_chunks) < 2:
        return {"groups": [], "threshold": threshold}

    doc_ids = list(doc_chunks.keys())
    # 平均向量并归一化
    avg_vecs = []
    for did in doc_ids:
        v = np.mean(doc_chunks[did], axis=0)
        norm = np.linalg.norm(v)
        avg_vecs.append(v / (norm if norm > 1e-9 else 1.0))
    matrix = np.array(avg_vecs, dtype=np.float32)

    # 两两余弦相似度
    sim_matrix = matrix @ matrix.T

    # 查询文档元信息和 chunk 数量
    doc_map = {doc.id: doc for doc in db.query(Document).all()}
    chunk_count_map = {
        row[0]: row[1]
        for row in db.query(Chunk.document_id, func.count(Chunk.id)).group_by(Chunk.document_id).all()
    }

    # 文件名相似度（取 basename，字符级 bigram Jaccard）
    import os
    def _name_sim(a: str, b: str) -> float:
        a = os.path.basename(a).lower()
        b = os.path.basename(b).lower()
        if a == b:
            return 1.0
        sa = {a[i:i+2] for i in range(len(a) - 1)}
        sb = {b[i:i+2] for i in range(len(b) - 1)}
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

    titles = [doc_map.get(did, None) for did in doc_ids]
    title_strs = [t.title if t else '' for t in titles]

    # 综合得分 = embedding_sim * 0.7 + name_sim * 0.3
    # 只要综合得分 >= threshold 就视为冗余
    def _combined(i, j):
        emb = float(sim_matrix[i, j])
        name = _name_sim(title_strs[i], title_strs[j])
        return emb * 0.7 + name * 0.3

    # 用 union-find 合并
    parent = list(range(len(doc_ids)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for i in range(len(doc_ids)):
        for j in range(i + 1, len(doc_ids)):
            if _combined(i, j) >= threshold:
                union(i, j)

    # 按根节点分组
    groups_map: dict = defaultdict(set)
    for i in range(len(doc_ids)):
        root = find(i)
        # 检查该文档是否真的与组内某个成员相似（避免孤立节点混入）
        if any(i != j and _combined(i, j) >= threshold for j in range(len(doc_ids))):
            groups_map[root].add(i)

    groups = []
    for indices in groups_map.values():
        if len(indices) < 2:
            continue
        # 限制每组最多显示 20 个，按 chunk 数降序
        idx_list = sorted(indices, key=lambda i: chunk_count_map.get(doc_ids[i], 0), reverse=True)[:20]
        docs_in_group = []
        for idx in idx_list:
            doc_id = doc_ids[idx]
            doc = doc_map.get(doc_id)
            if not doc:
                continue
            max_sim = max(
                (_combined(idx, j) for j in indices if j != idx),
                default=0.0
            )
            emb_sim = max(
                (float(sim_matrix[idx, j]) for j in indices if j != idx),
                default=0.0
            )
            docs_in_group.append({
                "id": doc.id,
                "title": doc.title,
                "file_type": doc.file_type,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "chunk_count": chunk_count_map.get(doc_id, 0),
                "max_similarity": round(max_sim, 4),
                "emb_similarity": round(emb_sim, 4),
            })
        if len(docs_in_group) >= 2:
            groups.append(docs_in_group)

    # 按组内最高相似度降序
    groups.sort(key=lambda g: max(d["max_similarity"] for d in g), reverse=True)
    return {"groups": groups, "threshold": threshold}


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
    # 回收死元组占用的空间，使 pg_database_size 及时反映变化
    db.execute(text("VACUUM chunks, documents"))
    db.commit()
    SearchService.invalidate_cache()

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
    SearchService.invalidate_cache()

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
                "file_size": doc.file_size,
                "tree_index": doc.tree_index,
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
                    "section_id": chunk.section_id,
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
                file_size=doc_data.get("file_size"),
                tree_index=doc_data.get("tree_index"),
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
                    section_id=chunk_data.get("section_id"),
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
