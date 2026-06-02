from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "融衔"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # 数据库配置
    DATABASE_URL: str = "sqlite:///./stock_agent.db"

    # JWT 配置
    JWT_SECRET_KEY: str = "stock-agent-secret-key-change-in-production"

    # Redis 配置（可选）
    REDIS_URL: Optional[str] = None

    # 数据源 API Key
    TUSHARE_TOKEN: Optional[str] = None
    FUTU_ACCESS_TOKEN: Optional[str] = None

    # CORS 配置
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
