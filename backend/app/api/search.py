from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.search_service import SearchService
from pydantic import BaseModel
import math

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/search")
async def search(request: SearchRequest, db: Session = Depends(get_db)):
    """搜索知识库"""
    try:
        results = SearchService.search(db, request.query, request.top_k)

        return {
            "query": request.query,
            "results": [
                {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "content": chunk.content,
                    "similarity": 0.0 if math.isnan(float(score)) else float(score),
                    "chunk_index": chunk.chunk_index
                }
                for chunk, score in results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
