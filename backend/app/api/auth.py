"""认证 API"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from jose import jwt, JWTError
import bcrypt
import re
import logging

from app.db.session import get_db
from app.models.user import User
from app.core.config import settings
from app.core.redis import check_rate_limit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["认证"])

SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 小时（金融系统应配合 refresh token 使用）

# 速率限制配置
_REGISTER_LIMIT = 10  # 每小时最多注册次数
_LOGIN_LIMIT = 20     # 每分钟最多登录尝试
_LOGIN_WINDOW = 60    # 登录窗口（秒）
_REGISTER_WINDOW = 3600  # 注册窗口（秒）


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2 or len(v) > 30:
            raise ValueError("用户名长度需在 2-30 之间")
        if not v.isascii():
            raise ValueError("用户名仅支持英文字母、数字和下划线")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("密码长度至少 8 位")
        if not re.search(r"[A-Z]", v):
            raise ValueError("密码需包含至少一个大写字母")
        if not re.search(r"[a-z]", v):
            raise ValueError("密码需包含至少一个小写字母")
        if not re.search(r"\d", v):
            raise ValueError("密码需包含至少一个数字")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    display_name: str
    role: str


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_token(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": username, "role": role, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> User:
    """从 Authorization header 解析当前用户"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return user


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """用户登录"""
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"login:{client_ip}", _LOGIN_LIMIT, _LOGIN_WINDOW):
        raise HTTPException(status_code=429, detail="登录尝试过于频繁，请 1 分钟后再试")
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")
    token = create_token(user.username, user.role)
    return TokenResponse(
        access_token=token,
        username=user.username,
        display_name=user.display_name or user.username,
        role=user.role,
    )


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """用户注册"""
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"register:{client_ip}", _REGISTER_LIMIT, _REGISTER_WINDOW):
        raise HTTPException(status_code=429, detail="注册过于频繁，请稍后再试")
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        display_name=req.display_name or req.username,
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token(user.username, user.role)
    return TokenResponse(
        access_token=token,
        username=user.username,
        display_name=user.display_name or user.username,
        role=user.role,
    )


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """验证当前用户是否为管理员"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def get_current_analyst(user: User = Depends(get_current_user)) -> User:
    """验证当前用户是否为分析师或管理员"""
    if user.role not in ("admin", "analyst"):
        raise HTTPException(status_code=403, detail="需要分析师或管理员权限")
    return user


def get_member_user(user: User = Depends(get_current_user)) -> User:
    """验证当前用户是否为正式成员（排除 guest）"""
    if user.role == "guest":
        raise HTTPException(status_code=403, detail="访客无此权限，请使用正式账号登录")
    return user


@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "role": user.role,
        "created_at": str(user.created_at) if user.created_at else None,
    }
