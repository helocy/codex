"""
API Key 认证模块
"""
import os
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db

# 简单的内存存储（生产环境建议使用数据库）
_api_keys_db = {}


class APIKey(BaseModel):
    key: str
    name: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool = True


def hash_api_key(key: str) -> str:
    """对 API Key 进行哈希存储"""
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(authorization: str = Header(None)) -> str:
    """验证 API Key"""
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少 Authorization 头")

    # 支持两种格式：
    # 1. Bearer <api_key>
    # 2. <api_key> (直接传递 key)
    if authorization.startswith("Bearer "):
        api_key = authorization[7:]
    else:
        api_key = authorization

    # 验证 key 是否有效
    key_hash = hash_api_key(api_key)
    key_data = _api_keys_db.get(key_hash)

    if not key_data:
        # 允许使用预设的管理 key
        admin_key = os.environ.get("CODEX_ADMIN_KEY", "codex-admin-key")
        if api_key != admin_key:
            raise HTTPException(status_code=401, detail="无效的 API Key")

    return api_key


def create_api_key(name: str, expires_days: Optional[int] = None) -> tuple[str, str]:
    """创建新的 API Key

    Returns:
        (plain_key, hashed_key) - 返回明文 key（只显示一次）和哈希后的 key
    """
    plain_key = f"cdx_{secrets.token_urlsafe(32)}"
    hashed_key = hash_api_key(plain_key)

    expires_at = None
    if expires_days:
        expires_at = datetime.now() + timedelta(days=expires_days)

    _api_keys_db[hashed_key] = APIKey(
        key=hashed_key,
        name=name,
        created_at=datetime.now(),
        expires_at=expires_at,
        is_active=True
    )

    return plain_key, hashed_key


def list_api_keys() -> List[dict]:
    """列出所有 API Keys（不包含明文）"""
    return [
        {
            "name": v.name,
            "created_at": v.created_at.isoformat(),
            "expires_at": v.expires_at.isoformat() if v.expires_at else None,
            "is_active": v.is_active
        }
        for v in _api_keys_db.values()
    ]


# 创建内置的管理 key
ADMIN_KEY = os.environ.get("CODEX_ADMIN_KEY", "codex-admin-key")
print(f"[API] Admin key configured: {ADMIN_KEY[:10]}...")
