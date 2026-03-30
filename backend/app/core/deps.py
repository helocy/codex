from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from jose import JWTError, jwt
from app.core.database import get_db
from app.core.config import settings
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def _decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        return None


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """有 token 时解析并返回用户，无 token 或无效 token 返回 None（游客）"""
    if not credentials:
        return None
    payload = _decode_token(credentials.credentials)
    if not payload:
        return None
    username: str = payload.get("sub")
    if not username:
        return None
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        return None
    return user


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """必须登录，否则 401"""
    user = get_current_user_optional(credentials, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """必须是 admin，否则 403"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
