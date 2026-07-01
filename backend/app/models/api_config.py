"""API configuration, quota and audit models."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.db.base import Base


class ApiConfig(Base):
    """Platform-level provider configuration."""
    __tablename__ = "api_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(50), nullable=False, unique=True, comment="provider key")
    display_name = Column(String(100), comment="display name")
    api_key = Column(String(500), comment="encrypted api key")
    api_secret = Column(String(500), comment="encrypted api secret")
    base_url = Column(String(500), comment="base url")
    is_enabled = Column(Boolean, default=True, comment="enabled")
    daily_limit = Column(Integer, default=1000, comment="daily call limit")
    rate_limit = Column(Integer, default=10, comment="per-minute rate limit")
    config_json = Column(String(2000), comment="extra json config")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class UserApiQuota(Base):
    """Per-user quota overrides."""
    __tablename__ = "user_api_quotas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    daily_report_limit = Column(Integer, default=20, comment="daily report generation limit")
    daily_backtest_limit = Column(Integer, default=20, comment="daily backtest limit")
    daily_search_limit = Column(Integer, default=100, comment="daily search limit")
    daily_pdf_limit = Column(Integer, default=30, comment="daily PDF download limit")
    daily_png_limit = Column(Integer, default=30, comment="daily PNG download limit")
    max_api_configs = Column(Integer, default=5, comment="max user API configs")
    can_download_pdf = Column(Boolean, default=True, comment="can download PDF")
    can_use_style_report = Column(Boolean, default=True, comment="can use style report")
    can_use_simulation = Column(Boolean, default=True, comment="can use simulation")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ApiCallLog(Base):
    """Low-level API call log kept for compatibility with existing stats."""
    __tablename__ = "api_call_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, comment="user id")
    username = Column(String(50), comment="username")
    provider = Column(String(50), comment="provider")
    endpoint = Column(String(200), comment="endpoint")
    method = Column(String(10), comment="method")
    status_code = Column(Integer, comment="status code")
    response_time = Column(Integer, comment="response time ms")
    error_msg = Column(String(500), comment="error message")
    called_at = Column(DateTime, server_default=func.now(), index=True)


class OperationLog(Base):
    """Unified audit log for user, report, backtest and admin operations."""
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=True)
    username = Column(String(80), nullable=True)
    phone = Column(String(32), nullable=True)
    role = Column(String(30), nullable=True)
    action = Column(String(80), nullable=False, index=True)
    target_type = Column(String(80), nullable=False, index=True)
    target_id = Column(String(80), nullable=True)
    status = Column(String(20), nullable=False, default="success", index=True)
    message = Column(String(500), nullable=True)
    ip = Column(String(64), nullable=True)
    user_agent = Column(String(300), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)


class UserApiConfig(Base):
    """User-owned API/LLM configuration. API keys are masked in responses."""
    __tablename__ = "user_api_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    provider = Column(String(80), nullable=False)
    base_url = Column(String(500), nullable=True)
    api_key = Column(String(500), nullable=True)
    model_name = Column(String(120), nullable=True)
    is_default = Column(Boolean, default=False)
    note = Column(Text, nullable=True)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
