"""Quota checks and usage statistics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.api_config import ApiCallLog, UserApiConfig, UserApiQuota
from app.models.report import BacktestTask, Report, ReportEvent
from app.models.user import User


@dataclass(frozen=True)
class QuotaRule:
    limit: int
    used: int
    label: str

    @property
    def remaining(self) -> int:
        return max(self.limit - self.used, 0)

    @property
    def allowed(self) -> bool:
        return self.used < self.limit


def _today_filter(column):
    return func.date(column) == date.today()


def _quota_for(db: Session, user_id: int) -> UserApiQuota | None:
    return db.query(UserApiQuota).filter(UserApiQuota.user_id == user_id).first()


def _limit(quota: UserApiQuota | None, attr: str, default: int) -> int:
    value = getattr(quota, attr, None)
    return int(value if value is not None else default)


def is_unlimited(user: User | None) -> bool:
    return bool(user and user.role == "admin")


def usage_for_user(db: Session, user: User) -> dict:
    quota = _quota_for(db, user.id)
    report_used = db.query(Report).filter(Report.user_id == user.id, _today_filter(Report.created_at)).count()
    html_used = db.query(ReportEvent).filter(
        ReportEvent.user_id == user.id,
        ReportEvent.format == "html",
        ReportEvent.action == "view",
        _today_filter(ReportEvent.created_at),
    ).count()
    png_used = db.query(ReportEvent).filter(
        ReportEvent.user_id == user.id,
        ReportEvent.format == "png",
        ReportEvent.action == "download",
        _today_filter(ReportEvent.created_at),
    ).count()
    pdf_used = db.query(ReportEvent).filter(
        ReportEvent.user_id == user.id,
        ReportEvent.format == "pdf",
        ReportEvent.action == "download",
        _today_filter(ReportEvent.created_at),
    ).count()
    backtest_used = db.query(BacktestTask).filter(
        BacktestTask.user_id == user.id,
        _today_filter(BacktestTask.created_at),
    ).count()
    api_config_count = db.query(UserApiConfig).filter(UserApiConfig.owner_user_id == user.id).count()

    unlimited = is_unlimited(user)
    limits = {
        "reports": _limit(quota, "daily_report_limit", settings.DEFAULT_DAILY_REPORT_LIMIT),
        "html_views": settings.DEFAULT_DAILY_HTML_VIEW_LIMIT,
        "png_downloads": _limit(quota, "daily_png_limit", settings.DEFAULT_DAILY_PNG_LIMIT),
        "pdf_downloads": _limit(quota, "daily_pdf_limit", settings.DEFAULT_DAILY_PDF_LIMIT),
        "backtests": _limit(quota, "daily_backtest_limit", settings.DEFAULT_DAILY_BACKTEST_LIMIT),
        "api_configs": _limit(quota, "max_api_configs", settings.DEFAULT_MAX_API_CONFIGS),
    }
    used = {
        "reports": report_used,
        "html_views": html_used,
        "png_downloads": png_used,
        "pdf_downloads": pdf_used,
        "backtests": backtest_used,
        "api_configs": api_config_count,
    }

    items = {}
    labels = {
        "reports": "报告生成",
        "html_views": "HTML查看",
        "png_downloads": "PNG下载",
        "pdf_downloads": "PDF下载",
        "backtests": "回测运行",
        "api_configs": "API配置",
    }
    for key, limit_value in limits.items():
        used_value = used[key]
        items[key] = {
            "label": labels[key],
            "used": used_value,
            "limit": None if unlimited and key != "api_configs" else limit_value,
            "remaining": None if unlimited and key != "api_configs" else max(limit_value - used_value, 0),
            "unlimited": unlimited and key != "api_configs",
        }
    return {
        "date": str(date.today()),
        "role": user.role,
        "unlimited": unlimited,
        "items": items,
    }


def check_quota(db: Session, user: User, quota_type: str) -> tuple[bool, str]:
    if is_unlimited(user):
        return True, ""

    usage = usage_for_user(db, user)["items"]
    mapping = {
        "report": ("reports", "今日报告生成次数已达上限，请明日重试或联系管理员。"),
        "png": ("png_downloads", "今日PNG下载次数已达上限，请明日重试或联系管理员。"),
        "pdf": ("pdf_downloads", "今日PDF下载次数已达上限，请明日重试或联系管理员。"),
        "backtest": ("backtests", "今日回测次数已达上限，请明日重试或联系管理员。"),
        "api_config": ("api_configs", "用户API配置数量已达上限，请删除旧配置或联系管理员。"),
    }
    if quota_type not in mapping:
        return True, ""
    key, message = mapping[quota_type]
    item = usage[key]
    if item["limit"] is not None and item["used"] >= item["limit"]:
        return False, message
    return True, ""


def admin_usage_rankings(db: Session) -> dict:
    users = db.query(User).all()

    def row(user: User) -> dict:
        all_usage = usage_for_user(db, user)["items"]
        total_downloads = (
            db.query(ReportEvent)
            .filter(ReportEvent.user_id == user.id, ReportEvent.action == "download")
            .count()
        )
        report_total = db.query(Report).filter(Report.user_id == user.id).count()
        backtest_total = db.query(BacktestTask).filter(BacktestTask.user_id == user.id).count()
        latest_activity = db.query(func.max(ApiCallLog.called_at)).filter(ApiCallLog.user_id == user.id).scalar()
        latest_report_event = db.query(func.max(ReportEvent.created_at)).filter(ReportEvent.user_id == user.id).scalar()
        latest_backtest = db.query(func.max(BacktestTask.created_at)).filter(BacktestTask.user_id == user.id).scalar()
        latest = max([x for x in [latest_activity, latest_report_event, latest_backtest, user.last_login_at] if x] or [None])
        return {
            "user_id": user.id,
            "username": user.username,
            "phone": user.phone,
            "display_name": user.display_name,
            "role": user.role,
            "today_reports": all_usage["reports"]["used"],
            "today_downloads": all_usage["png_downloads"]["used"] + all_usage["pdf_downloads"]["used"],
            "today_backtests": all_usage["backtests"]["used"],
            "report_total": report_total,
            "download_total": total_downloads,
            "backtest_total": backtest_total,
            "last_active_at": str(latest) if latest else None,
        }

    rows = [row(user) for user in users]
    return {
        "top_reports": sorted(rows, key=lambda x: x["report_total"], reverse=True)[:10],
        "top_downloads": sorted(rows, key=lambda x: x["download_total"], reverse=True)[:10],
        "top_backtests": sorted(rows, key=lambda x: x["backtest_total"], reverse=True)[:10],
        "recent_active": sorted(rows, key=lambda x: x["last_active_at"] or "", reverse=True)[:10],
    }
