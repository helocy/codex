from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 项目信息
    PROJECT_NAME: str = "Codex"
    VERSION: str = "0.2.3"
    API_V1_STR: str = "/api/v1"

    # 数据库配置
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "codex"
    POSTGRES_PASSWORD: str = "codex123"
    POSTGRES_DB: str = "codex_db"
    POSTGRES_PORT: int = 5432

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # 文件存储
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB

    # AI 模型配置
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIM: int = 384

    # LLM 配置
    DOUBAO_API_KEY: Optional[str] = None
    DOUBAO_MODEL: str = "doubao-seed-1-6-251015"

    # CORS
    BACKEND_CORS_ORIGINS: list = ["*"]

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
