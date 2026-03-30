from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from app.core.database import get_db
from app.core.config import settings
from app.core.deps import get_current_user, require_admin
from app.models.user import User

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ChangeUsernameRequest(BaseModel):
    new_username: str
    current_password: str


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(username: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_user(db: Session, username: str, password: str, role: str = "user") -> User:
    user = User(
        username=username,
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not user.is_active or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.username, user.role)
    return {"access_token": token, "token_type": "bearer", "id": user.id, "username": user.username, "role": user.role}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "role": current_user.role, "created_at": current_user.created_at}


@router.get("/users")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    users = db.query(User).order_by(User.created_at).all()
    return [{"id": u.id, "username": u.username, "role": u.role, "is_active": u.is_active, "created_at": u.created_at} for u in users]


@router.post("/users", status_code=201)
def create_user_api(req: CreateUserRequest, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=409, detail="Username already exists")
    if req.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="role must be 'admin' or 'user'")
    user = create_user(db, req.username, req.password, req.role)
    return {"id": user.id, "username": user.username, "role": user.role}


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    db.delete(user)
    db.commit()


@router.put("/me/password")
def change_my_password(
    req: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(req.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="当前密码错误")
    if not req.new_password.strip():
        raise HTTPException(status_code=400, detail="新密码不能为空")
    current_user.hashed_password = hash_password(req.new_password)
    db.commit()
    return {"ok": True}


@router.put("/me/username")
def change_my_username(
    req: ChangeUsernameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(req.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="当前密码错误")
    new_username = req.new_username.strip()
    if not new_username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if db.query(User).filter(User.username == new_username, User.id != current_user.id).first():
        raise HTTPException(status_code=409, detail="用户名已被占用")
    current_user.username = new_username
    db.commit()
    return {"ok": True, "username": new_username}


@router.put("/users/{user_id}/password")
def change_password(
    user_id: int,
    req: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # 必须验证当前密码
    if not verify_password(req.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="当前密码错误")
    if not req.new_password.strip():
        raise HTTPException(status_code=400, detail="新密码不能为空")
    user.hashed_password = hash_password(req.new_password)
    db.commit()
    return {"ok": True}


@router.put("/users/{user_id}/username")
def change_username(
    user_id: int,
    req: ChangeUsernameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(req.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="当前密码错误")
    new_username = req.new_username.strip()
    if not new_username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if db.query(User).filter(User.username == new_username, User.id != user_id).first():
        raise HTTPException(status_code=409, detail="用户名已被占用")
    user.username = new_username
    db.commit()
    return {"ok": True, "username": new_username}
