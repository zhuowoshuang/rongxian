from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

WEAK_JWT_SECRETS = {
    "",
    "stock-agent-secret-key-change-in-production",
    "please-change-this-in-production",
}


class ApiKeyCryptoError(RuntimeError):
    """Raised when encrypted API keys cannot be safely encoded or decoded."""


def _secret_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), ".jwt_secret")


def _is_strong_secret(value: str | None) -> bool:
    return bool(value and value not in WEAK_JWT_SECRETS and len(value) >= 32)


def _get_or_generate_secret(app_env: str) -> str:
    env_value = os.getenv("JWT_SECRET_KEY", "")
    if _is_strong_secret(env_value):
        return env_value

    if app_env == "production":
        raise RuntimeError("生产环境必须显式配置长度不少于 32 位的 JWT_SECRET_KEY")

    secret_file = _secret_file_path()
    if os.path.exists(secret_file):
        with open(secret_file, "r", encoding="utf-8") as file:
            stored = file.read().strip()
            if _is_strong_secret(stored):
                return stored

    new_key = secrets.token_urlsafe(48)
    try:
        with open(secret_file, "w", encoding="utf-8") as file:
            file.write(new_key)
    except OSError as exc:
        logger.warning("无法写入 .jwt_secret 文件，本次进程将使用临时 JWT 密钥: %s", exc)
    return new_key


def _truthy_env(name: str) -> bool:
    return str(os.getenv(name, "")).strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseSettings):
    APP_NAME: str = "清数智算"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = False
    DATABASE_URL: str = "sqlite:///./stock_agent.db"
    JWT_SECRET_KEY: str = ""

    REDIS_URL: Optional[str] = None
    DEFAULT_DAILY_REPORT_LIMIT: int = 20
    DEFAULT_DAILY_PDF_LIMIT: int = 30
    DEFAULT_DAILY_PNG_LIMIT: int = 30
    DEFAULT_DAILY_BACKTEST_LIMIT: int = 20
    DEFAULT_DAILY_HTML_VIEW_LIMIT: int = 1000
    DEFAULT_MAX_API_CONFIGS: int = 5
    DAILY_FINANCIAL_LIMIT: int = 300
    DAILY_TECHNICAL_LIMIT: int = 500
    REAL_PIPELINE_FINANCIAL_WORKERS: int = 3

    TUSHARE_TOKEN: Optional[str] = None
    FUTU_ACCESS_TOKEN: Optional[str] = None

    CORS_ORIGINS: list[str] = [
        "http://127.0.0.1:4101",
        "http://localhost:4101",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @model_validator(mode="after")
    def _normalize_runtime_settings(self) -> "Settings":
        app_env = (self.APP_ENV or "development").lower()
        object.__setattr__(self, "APP_ENV", app_env)
        object.__setattr__(self, "JWT_SECRET_KEY", self.JWT_SECRET_KEY or _get_or_generate_secret(app_env))

        if app_env == "production":
            if self.DEBUG:
                raise RuntimeError("生产环境禁止启用 DEBUG=true")
            if not _is_strong_secret(self.JWT_SECRET_KEY):
                raise RuntimeError("生产环境 JWT_SECRET_KEY 配置不安全")
            if _truthy_env("ADATA_USE_FIXTURES"):
                raise RuntimeError("生产环境禁止启用 ADATA_USE_FIXTURES=true")
        return self


settings = Settings()


def _get_fernet():
    from cryptography.fernet import Fernet

    key_bytes = hashlib.sha256(settings.JWT_SECRET_KEY.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_api_key(plaintext: str) -> str:
    if not plaintext:
        return plaintext
    try:
        return _get_fernet().encrypt(plaintext.encode()).decode()
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("API key 加密失败，已拒绝保存明文: %s", exc)
        raise ApiKeyCryptoError("API Key 加密失败，请检查系统密钥配置后重试") from exc


def decrypt_api_key(ciphertext: str) -> str:
    if not ciphertext:
        return ciphertext
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except Exception as exc:
        logger.warning("API key 解密失败，需要重新保存该配置: %s", exc)
        raise ApiKeyCryptoError("API Key 无法解密，需重新保存该配置") from exc
