from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base
from app.api import documents, search, chat, admin, embedding, api_
from app.services.llm_service import llm_service

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 自动配置 LLM（优先读取通用 LLM_* 变量，兼容旧版 DOUBAO_* 变量）
if settings.LLM_PROVIDER and settings.LLM_API_KEY:
    llm_service.configure(
        provider=settings.LLM_PROVIDER,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL or None,
        model=settings.LLM_MODEL or None,
    )
elif settings.DOUBAO_API_KEY:
    llm_service.configure(
        provider="doubao",
        api_key=settings.DOUBAO_API_KEY,
        model=settings.DOUBAO_MODEL,
    )

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(documents.router, prefix=f"{settings.API_V1_STR}/documents", tags=["documents"])
app.include_router(search.router, prefix=f"{settings.API_V1_STR}/search", tags=["search"])
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}/chat", tags=["chat"])
app.include_router(admin.router, prefix=f"{settings.API_V1_STR}/admin", tags=["admin"])
app.include_router(embedding.router, prefix=f"{settings.API_V1_STR}/embedding", tags=["embedding"])
app.include_router(api_.router, prefix=f"{settings.API_V1_STR}/api", tags=["external-api"])


@app.get("/")
async def root():
    return {
        "message": "Welcome to Codex API",
        "version": settings.VERSION,
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
