from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 项目信息
    PROJECT_NAME: str = "Codex"
    VERSION: str = "0.4.1"
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

    # LLM 配置（通用，优先级高于下方 Doubao 字段）
    LLM_PROVIDER: Optional[str] = None   # doubao | qwen | openai | ollama | custom
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None
    LLM_MODEL: Optional[str] = None

    # 兼容旧版 Doubao 专用字段
    DOUBAO_API_KEY: Optional[str] = None
    DOUBAO_MODEL: str = "doubao-seed-1-6-251015"

    # 远程代码分析 SSH 配置
    CODE_SSH_HOST: str = "172.16.15.99"
    CODE_SSH_USER: str = "yzc"
    CODE_SSH_KEY_PATH: str = "~/.ssh/id_ed25519"
    CODE_SDK_ROOT: str = "/home/yzc/workspace/sdks"

    # 代码分析专用 LLM（默认用主 LLM，可单独配置 Claude）
    CODE_ANALYSIS_LLM_PROVIDER: Optional[str] = None   # anthropic | doubao | openai 等，为空则跟主 LLM
    CODE_ANALYSIS_API_KEY: Optional[str] = None
    CODE_ANALYSIS_BASE_URL: Optional[str] = None        # Anthropic API URL，留空使用默认
    CODE_ANALYSIS_MODEL: Optional[str] = "claude-sonnet-4-6"

    # CORS
    BACKEND_CORS_ORIGINS: list = ["*"]

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
