from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.embedding_service import embedding_service

router = APIRouter()


class EmbeddingConfigRequest(BaseModel):
    provider: str   # local | openai | doubao
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None


@router.get("/config")
async def get_embedding_config():
    """获取当前嵌入模型配置"""
    return embedding_service.get_config()


@router.post("/config")
async def configure_embedding(config: EmbeddingConfigRequest):
    """配置嵌入模型（本地或云端）"""
    try:
        embedding_service.configure(
            provider=config.provider,
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url
        )
        # 测试一下是否能正常工作
        try:
            test_vec = embedding_service.encode_single("测试")
            return {
                "message": "嵌入模型配置成功",
                "provider": config.provider,
                "model": config.model,
                "dimension": len(test_vec)
            }
        except Exception as e:
            import traceback
            error_msg = str(e)
            print(f"[ERROR] Embedding test failed: {error_msg}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            raise Exception(error_msg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"配置失败: {str(e)}")
