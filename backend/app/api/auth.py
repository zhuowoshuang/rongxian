"""Authentication APIs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import re

import bcrypt
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from jose import JWTError, jwt
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.redis import check_rate_limit
from app.db.session import get_db
from app.models.user import User
from app.services.audit import log_operation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["认证"])

SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480
_REGISTER_LIMIT = 10
_LOGIN_LIMIT = 20
_LOGIN_WINDOW = 60
_REGISTER_WINDOW = 3600


class LoginRequest(BaseModel):
    username: str | None = None
    identifier: str | None = None
    password: str


class RegisterRequest(BaseModel):
    username: str | None = None
    phone: str | None = None
    user_id: str | None = None
    password: str
    confirm_password: str | None = None
    display_name: str = ""

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if len(normalized) < 2 or len(normalized) > 32:
            raise ValueError("用户ID长度需在 2-32 个字符之间")
        if re.search(r"[<>{}'\";\\]", normalized):
            raise ValueError("用户ID包含不允许的字符")
        return normalized

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = re.sub(r"\s+", "", value).strip()
        if not normalized:
            raise ValueError("手机号不能为空")
        if not re.fullmatch(r"(?:\+?86)?1\d{10}", normalized):
            raise ValueError("手机号格式不正确，请输入 11 位手机号")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("密码长度至少 8 位")
        if not re.search(r"[A-Z]", value):
            raise ValueError("密码需包含至少一个大写字母")
        if not re.search(r"[a-z]", value):
            raise ValueError("密码需包含至少一个小写字母")
        if not re.search(r"\d", value):
            raise ValueError("密码需包含至少一个数字")
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    phone: str | None = None
    user_id: str | None = None
    display_name: str
    role: str


class VerificationRequest(BaseModel):
    phone: str
    code: str | None = None


class VerificationService:
    enabled = False

    def send_code(self, phone: str) -> dict:
        return {"status": "disabled", "message": "短信验证暂未启用，当前不会发送真实短信", "phone": phone}

    def verify_code(self, phone: str, code: str | None) -> dict:
        return {"status": "disabled", "verified": False, "message": "短信验证暂未启用，当前不校验验证码", "phone": phone}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_token(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": username, "role": role, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def _normalize_identifier(req: LoginRequest) -> str:
    value = (req.identifier or req.username or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="请输入手机号或用户ID")
    return value


def verify_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已被禁用，请重新登录")
    return user


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"login:{client_ip}", _LOGIN_LIMIT, _LOGIN_WINDOW):
        raise HTTPException(status_code=429, detail="登录尝试过于频繁，请 1 分钟后再试")

    identifier = _normalize_identifier(req)
    user = db.query(User).filter((User.phone == identifier) | (User.user_id == identifier) | (User.username == identifier)).first()

    if not user or not verify_password(req.password, user.password_hash):
        log_operation(
            db,
            user=user if user else None,
            username=identifier if not user else user.username,
            action="login_failed",
            target_type="auth",
            target_id=identifier,
            status="failed",
            message="login failed",
            request=request,
        )
        raise HTTPException(status_code=401, detail="手机号、用户ID或密码错误，请检查后重试")

    if not user.is_active:
        log_operation(
            db,
            user=user,
            action="login_failed",
            target_type="auth",
            target_id=user.id,
            status="failed",
            message="account disabled",
            request=request,
        )
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")

    user.last_login_at = datetime.now()
    db.commit()
    log_operation(db, user=user, action="login_success", target_type="auth", target_id=user.id, message="login success", request=request)
    token = create_token(user.username, user.role)
    return TokenResponse(
        access_token=token,
        username=user.username,
        phone=user.phone,
        user_id=user.user_id or user.username,
        display_name=user.display_name or user.username,
        role=user.role,
    )


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"register:{client_ip}", _REGISTER_LIMIT, _REGISTER_WINDOW):
        raise HTTPException(status_code=429, detail="注册过于频繁，请稍后再试")

    raw_phone = (req.phone or "").strip()
    raw_user_id = (req.user_id or req.username or "").strip()
    if not raw_phone:
        raise HTTPException(status_code=400, detail="手机号不能为空")
    if not raw_user_id:
        raise HTTPException(status_code=400, detail="用户ID不能为空")
    phone = RegisterRequest.validate_phone(raw_phone)
    user_id = RegisterRequest.validate_user_id(raw_user_id)
    if req.confirm_password is not None and req.confirm_password != req.password:
        raise HTTPException(status_code=400, detail="两次输入的密码不一致")

    if db.query(User).filter(User.phone == phone).first():
        log_operation(db, username=user_id, phone=phone, action="register", target_type="user", target_id=user_id, status="failed", message="phone exists", request=request)
        raise HTTPException(status_code=400, detail="手机号已注册，请直接登录或更换手机号")

    if db.query(User).filter((User.user_id == user_id) | (User.username == user_id)).first():
        log_operation(db, username=user_id, phone=phone, action="register", target_type="user", target_id=user_id, status="failed", message="user id exists", request=request)
        raise HTTPException(status_code=400, detail="用户ID已存在，请更换一个用户ID")

    user = User(
        username=user_id,
        phone=phone,
        user_id=user_id,
        password_hash=hash_password(req.password),
        display_name=req.display_name or user_id,
        role="user",
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_operation(db, user=user, action="register", target_type="user", target_id=user.id, message="register success", request=request)

    token = create_token(user.username, user.role)
    return TokenResponse(
        access_token=token,
        username=user.username,
        phone=user.phone,
        user_id=user.user_id,
        display_name=user.display_name or user.username,
        role=user.role,
    )


@router.post("/send-code")
def send_code(req: VerificationRequest):
    return VerificationService().send_code(req.phone)


@router.post("/verify-code")
def verify_code_api(req: VerificationRequest):
    return VerificationService().verify_code(req.phone, req.code)


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def get_current_analyst(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("admin", "analyst"):
        raise HTTPException(status_code=403, detail="需要分析师或管理员权限")
    return user


def get_member_user(user: User = Depends(get_current_user)) -> User:
    if user.role == "guest":
        raise HTTPException(status_code=403, detail="访客无此权限，请使用正式账号登录")
    return user


@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "phone": user.phone,
        "user_id": user.user_id or user.username,
        "display_name": user.display_name,
        "email": user.email,
        "role": user.role,
        "status": user.status or ("active" if user.is_active else "disabled"),
        "created_at": str(user.created_at) if user.created_at else None,
        "last_login_at": str(user.last_login_at) if user.last_login_at else None,
    }
