"""System status helpers used by admin and settings APIs."""

from __future__ import annotations

import os
from typing import Any

import bcrypt
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.redis import cache_backend_mode, is_redis_available
from app.db.session import SessionLocal
from app.models.api_config import ApiCallLog, ApiConfig
from app.models.daily_price import DailyPrice
from app.models.report import Report
from app.models.research_report import ResearchReport
from app.models.setting import Setting
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.trade_signal import TradeSignal
from app.models.user import User


def _safe_scalar_date(db: Session, model, field_name: str) -> str | None:
    field = getattr(model, field_name)
    value = db.query(func.max(field)).scalar()
    return str(value) if value else None


def _db_ok() -> bool:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        db.close()


def _db_path() -> str:
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    for candidate in ("stock_agent.db", "data/rongxian.db", "data/stock_agent.db"):
        db_path = os.path.join(backend_dir, candidate)
        if os.path.exists(db_path):
            return db_path
    return "N/A"


def _db_size() -> str:
    db_path = _db_path()
    if db_path == "N/A":
        return "N/A"
    size_bytes = os.path.getsize(db_path)
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.1f} MB"
    return f"{size_bytes / 1024:.1f} KB"


def _has_default_passwords(db: Session) -> bool:
    defaults = {
        "admin": "admin123",
        "demo": "demo123",
        "analyst": "analyst123",
        "guest": "guest123",
    }
    for user in db.query(User).all():
        default_password = defaults.get(user.username)
        if not default_password or not user.password_hash:
            continue
        try:
            if bcrypt.checkpw(default_password.encode("utf-8"), user.password_hash.encode("utf-8")):
                return True
        except Exception:
            continue
    return False


def build_system_status(db: Session) -> dict[str, Any]:
    provider_mode = os.environ.get("MOCK_DATA", "false").lower()
    is_mock_mode = provider_mode in ("true", "1", "yes")
    db_ok = _db_ok()
    enabled_api_configs = db.query(ApiConfig).filter(ApiConfig.is_enabled.is_(True)).count()
    total_api_configs = db.query(ApiConfig).count()
    latest_log = db.query(func.max(ApiCallLog.called_at)).scalar()
    latest_report = db.query(func.max(Report.created_at)).scalar()
    latest_settings_update = db.query(func.max(Setting.updated_at)).scalar()
    latest_error = (
        db.query(ApiCallLog)
        .filter(ApiCallLog.status_code >= 400)
        .order_by(ApiCallLog.called_at.desc())
        .first()
    )

    return {
        "status": "ok" if db_ok else "error",
        "database": "ok" if db_ok else "error",
        "redis": "ok" if is_redis_available() else "unavailable",
        "provider_mode": "mock" if is_mock_mode else "live",
        "data_mode": "模拟数据" if is_mock_mode else "真实/混合数据",
        "provider": os.environ.get("DATA_PROVIDER", "auto"),
        "cache_mode": cache_backend_mode(),
        "app_env": os.environ.get("APP_ENV", "development").lower(),
        "db_size": _db_size(),
        "db_path": _db_path(),
        "api_configured": {
            "enabled": enabled_api_configs,
            "total": total_api_configs,
        },
        "latest_updates": {
            "prices": _safe_scalar_date(db, DailyPrice, "trade_date"),
            "scores": _safe_scalar_date(db, StockScore, "score_date"),
            "signals": _safe_scalar_date(db, TradeSignal, "signal_date"),
            "reports": str(latest_report) if latest_report else None,
            "research_reports": _safe_scalar_date(db, ResearchReport, "publish_date"),
            "settings": str(latest_settings_update) if latest_settings_update else None,
            "api_logs": str(latest_log) if latest_log else None,
        },
        "counts": {
            "stocks": db.query(Stock).count(),
            "prices": db.query(DailyPrice).count(),
            "scores": db.query(StockScore).count(),
            "signals": db.query(TradeSignal).count(),
            "reports": db.query(Report).count(),
            "research_reports": db.query(ResearchReport).count(),
        },
        "security": {
            "default_password_warning": _has_default_passwords(db),
        },
        "latest_error": {
            "endpoint": latest_error.endpoint if latest_error else None,
            "status_code": latest_error.status_code if latest_error else None,
            "error_msg": latest_error.error_msg if latest_error else None,
            "called_at": str(latest_error.called_at) if latest_error and latest_error.called_at else None,
        },
        "notes": [
            "信号、评分和股票池来自数据库记录与研究规则，不构成实时交易建议。",
            "研究组合表现和模拟结果仅用于研究视图，不代表真实券商账户表现。",
            "当 Redis 不可用时，Dashboard 会退回进程内演示缓存，属于非实时聚合结果。",
        ],
    }
