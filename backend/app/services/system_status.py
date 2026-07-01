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
from app.models.financial_metric import FinancialMetric
from app.models.report import Report
from app.models.research_report import ResearchReport
from app.models.setting import Setting
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.technical_indicator import TechnicalIndicator
from app.models.trade_signal import TradeSignal
from app.models.user import User
from app.services.data_credibility import (
    DEMO_SCORE_SOURCE,
    DEMO_SIGNAL_SOURCE,
    REAL_SCORE_SOURCE,
    REAL_SIGNAL_SOURCE,
)
from app.services.data_coverage import summarize_market_data_coverage
from app.services.real_pipeline import get_recent_refresh_job_runs, real_pipeline_status


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
    """仅检查已知默认用户名，不做全表 bcrypt 扫描"""
    username_candidates = {
        "admin": ["Admin123456", "admin123"],
        "analyst": ["Analyst123", "analyst123"],
        "demo": ["demo123"],
        "guest": ["guest123"],
    }
    users = db.query(User).filter(User.username.in_(username_candidates.keys())).all()
    for user in users:
        candidates = username_candidates.get(user.username, [])
        if not candidates or not user.password_hash:
            continue
        for candidate in candidates:
            try:
                if bcrypt.checkpw(candidate.encode("utf-8"), user.password_hash.encode("utf-8")):
                    return True
            except Exception:
                continue
    return False


def _default_password_accounts(db: Session) -> list[str]:
    username_candidates = {
        "admin": ["Admin123456", "admin123"],
        "analyst": ["Analyst123", "analyst123"],
        "demo": ["demo123"],
        "guest": ["guest123"],
    }
    risky_accounts: list[str] = []
    for user in db.query(User).all():
        candidates = username_candidates.get(user.username, [])
        if not candidates or not user.password_hash:
            continue
        for candidate in candidates:
            try:
                if bcrypt.checkpw(candidate.encode("utf-8"), user.password_hash.encode("utf-8")):
                    risky_accounts.append(user.username)
                    break
            except Exception:
                continue
    return sorted(set(risky_accounts))


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
    redis_ok = is_redis_available()

    counts = {
        "stocks": db.query(Stock).count(),
        "prices": db.query(DailyPrice).count(),
        "financial_metrics": db.query(FinancialMetric).count(),
        "technical_indicators": db.query(TechnicalIndicator).count(),
        "scores": db.query(StockScore).count(),
        "signals": db.query(TradeSignal).count(),
        "reports": db.query(Report).count(),
        "research_reports": db.query(ResearchReport).count(),
    }
    real_score_count = db.query(StockScore).filter(StockScore.score_source == REAL_SCORE_SOURCE).count()
    demo_score_count = db.query(StockScore).filter(StockScore.score_source == DEMO_SCORE_SOURCE).count()
    real_signal_count = db.query(TradeSignal).filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE).count()
    demo_signal_count = db.query(TradeSignal).filter(TradeSignal.signal_source == DEMO_SIGNAL_SOURCE).count()

    warning = None
    if is_mock_mode:
        data_mode = "mock"
        data_mode_label = "模拟数据"
    elif counts["prices"] > 0 and real_score_count == 0 and demo_score_count > 0:
        data_mode = "demo_contaminated"
        data_mode_label = "真实行情 + 演示评分"
        warning = "当前评分和信号来自演示种子数据，不能视为真实投研结果。"
    elif counts["prices"] > 0 and real_score_count == 0:
        data_mode = "price_only"
        data_mode_label = "真实行情已接入，评分待生成"
        warning = "当前已接入真实行情，但尚未生成真实评分与真实信号。"
    elif real_score_count > 0 and (demo_score_count > 0 or demo_signal_count > 0):
        data_mode = "mixed_real_demo"
        data_mode_label = "真实小样本 + 演示评分并存"
        warning = "当前仅有部分样本完成真实财务、技术指标、评分与信号闭环，其余评分或信号仍为演示数据，不能视为全市场真实投研结果。"
    elif real_score_count > 0 and (counts["financial_metrics"] == 0 or counts["technical_indicators"] == 0 or real_signal_count == 0):
        data_mode = "real_partial"
        data_mode_label = "真实评分部分就绪"
        warning = "真实评分链路仅部分完成，仍需财务、技术指标或真实信号补齐。"
    elif real_score_count > 0 and real_signal_count > 0 and counts["financial_metrics"] > 0 and counts["technical_indicators"] > 0:
        data_mode = "real_ready"
        data_mode_label = "真实数据已就绪"
    else:
        data_mode = "unknown"
        data_mode_label = "待核验"
        warning = "当前数据链路状态未完全确认，请结合后台计数和更新时间复核。"

    latest_real_score_date = db.query(func.max(StockScore.score_date)).filter(StockScore.score_source == REAL_SCORE_SOURCE).scalar()
    latest_real_signal_date = db.query(func.max(TradeSignal.signal_date)).filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE).scalar()
    pipeline_status = real_pipeline_status(db)
    coverage_summary = summarize_market_data_coverage(db)
    recent_refresh_jobs = get_recent_refresh_job_runs(db, limit=10)
    pe_non_null_count = coverage_summary.get("pe_non_null_count", 0)
    pb_non_null_count = coverage_summary.get("pb_non_null_count", 0)
    valuation_zero_real_scores = coverage_summary.get("valuation_zero_real_scores", 0)

    real_pipeline_label = {
        "ready": "真实评分链路已小样本跑通",
        "partial_ready": "部分真实评分已生成",
        "financial_missing": "财务数据待刷新",
        "technical_missing": "技术指标待计算",
        "technical_ready_only": "技术指标已就绪，财务待补",
        "financial_ready_only": "财务已就绪，技术指标待补",
        "not_started": "尚未启动真实流水线",
        "provider_failed": "财务 Provider 失败",
        "locked_running": "流水线运行中",
    }.get(pipeline_status, pipeline_status)

    if real_score_count == 0:
        coverage_message = "真实评分尚未生成，C 端只展示行情和数据状态。"
    else:
        coverage_message = f"真实评分已小样本跑通，覆盖 {coverage_summary.get('real_calculated_scores', 0)} 条评分记录。"

    default_password_accounts = _default_password_accounts(db)
    default_password_warning = bool(default_password_accounts)
    default_password_risk_level = (
        "critical" if os.environ.get("APP_ENV", "development").lower() == "production" and default_password_warning else
        "warning" if default_password_warning else
        "none"
    )

    return {
        "status": "ok" if db_ok else "error",
        "database": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "unavailable",
        "redis_label": "正常" if redis_ok else "不可用",
        "redis_impact": "Redis 不可用时，缓存、异步任务、任务队列能力降级；演示环境可继续使用，生产环境建议启用 Redis。",
        "provider_mode": "mock" if is_mock_mode else "live",
        "data_mode": data_mode,
        "data_mode_label": data_mode_label,
        "provider": os.environ.get("DATA_PROVIDER", "auto"),
        "cache_mode": cache_backend_mode(),
        "app_env": os.environ.get("APP_ENV", "development").lower(),
        "db_size": _db_size(),
        "db_path": _db_path(),
        "real_score_count": real_score_count,
        "demo_score_count": demo_score_count,
        "real_signal_count": real_signal_count,
        "demo_signal_count": demo_signal_count,
        "financial_metrics_count": counts["financial_metrics"],
        "technical_indicators_count": counts["technical_indicators"],
        "real_pipeline_status": pipeline_status,
        "real_pipeline_label": real_pipeline_label,
        "coverage_message": coverage_message,
        "data_coverage": coverage_summary,
        "recent_refresh_jobs": recent_refresh_jobs,
        "valuation_coverage": {
            "pe_non_null_count": pe_non_null_count,
            "pb_non_null_count": pb_non_null_count,
            "valuation_zero_real_scores": valuation_zero_real_scores,
        },
        "warning": warning,
        "api_configured": {
            "enabled": enabled_api_configs,
            "total": total_api_configs,
        },
        "latest_updates": {
            "prices": _safe_scalar_date(db, DailyPrice, "trade_date"),
            "scores": _safe_scalar_date(db, StockScore, "score_date"),
            "signals": _safe_scalar_date(db, TradeSignal, "signal_date"),
            "financials": _safe_scalar_date(db, FinancialMetric, "report_date"),
            "technicals": _safe_scalar_date(db, TechnicalIndicator, "trade_date"),
            "latest_real_score_date": str(latest_real_score_date) if latest_real_score_date else None,
            "latest_real_signal_date": str(latest_real_signal_date) if latest_real_signal_date else None,
            "reports": str(latest_report) if latest_report else None,
            "research_reports": _safe_scalar_date(db, ResearchReport, "publish_date"),
            "settings": str(latest_settings_update) if latest_settings_update else None,
            "api_logs": str(latest_log) if latest_log else None,
        },
        "counts": {
            **counts,
            "stock_scores_total": counts["scores"],
            "stock_scores_real_count": real_score_count,
            "stock_scores_demo_count": demo_score_count,
            "trade_signals_total": counts["signals"],
            "trade_signals_real_count": real_signal_count,
            "trade_signals_demo_count": demo_signal_count,
        },
        "security": {
            "default_password_warning": default_password_warning,
            "default_password_accounts": default_password_accounts,
            "default_password_risk_level": default_password_risk_level,
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
