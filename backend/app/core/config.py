from pydantic_settings import BaseSettings
from pydantic import model_validator
from typing import Optional
import os
import secrets
import logging

logger = logging.getLogger(__name__)


def _get_or_generate_secret() -> str:
    """从环境变量读取 JWT 密钥，若未配置则自动生成随机密钥"""
    key = os.getenv("JWT_SECRET_KEY", "")
    if key and key != "stock-agent-secret-key-change-in-production" and len(key) >= 32:
        return key
    # 自动生成并持久化到 .jwt_secret 文件（backend 目录下）
    secret_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".jwt_secret")
    if os.path.exists(secret_file):
        with open(secret_file, "r") as f:
            stored = f.read().strip()
            if stored and len(stored) >= 32:
                return stored
    new_key = secrets.token_urlsafe(48)
    try:
        with open(secret_file, "w") as f:
            f.write(new_key)
    except OSError as e:
        logger.warning(f"无法写入 .jwt_secret 文件，每次重启将生成新密钥: {e}")
    return new_key


class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "清数智算"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # 数据库配置
    DATABASE_URL: str = "sqlite:///./stock_agent.db"

    # JWT 配置（自动从 .jwt_secret 文件读取或生成随机密钥）
    JWT_SECRET_KEY: str = ""

    # Redis 配置（可选）
    REDIS_URL: Optional[str] = None

    # 数据源 API Key
    TUSHARE_TOKEN: Optional[str] = None
    FUTU_ACCESS_TOKEN: Optional[str] = None

    # CORS 配置
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://localhost:3003",
        "http://127.0.0.1:3000", "http://127.0.0.1:3001", "http://127.0.0.1:3002", "http://127.0.0.1:3003",
        "http://localhost:4100", "http://localhost:4101",
        "http://127.0.0.1:4100", "http://127.0.0.1:4101",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @model_validator(mode="after")
    def _ensure_jwt_secret(self) -> "Settings":
        """在模型构造阶段自动填充 JWT_SECRET_KEY，避免运行时篡改实例"""
        if not self.JWT_SECRET_KEY:
            object.__setattr__(self, "JWT_SECRET_KEY", _get_or_generate_secret())
        return self


settings = Settings()


# ==================== API Key 加解密 ====================
import hashlib
import base64

def _get_fernet():
    """基于 JWT 密钥派生 Fernet 实例"""
    from cryptography.fernet import Fernet
    key_bytes = hashlib.sha256(settings.JWT_SECRET_KEY.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)

def encrypt_api_key(plaintext: str) -> str:
    """加密 API Key 用于数据库存储"""
    if not plaintext:
        return plaintext
    try:
        f = _get_fernet()
        return f.encrypt(plaintext.encode()).decode()
    except Exception as e:
        logger.warning(f"API key 加密失败，回退明文存储: {e}")
        return plaintext

def decrypt_api_key(ciphertext: str) -> str:
    """解密 API Key"""
    if not ciphertext:
        return ciphertext
    try:
        f = _get_fernet()
        return f.decrypt(ciphertext.encode()).decode()
    except Exception as e:
        logger.debug(f"API key 解密失败（可能是旧明文数据）: {e}")
        return ciphertext
