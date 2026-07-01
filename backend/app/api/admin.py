"""管理员 API"""
import os
import time
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect, func
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db
from app.models.user import User
from app.models.api_config import ApiConfig, UserApiQuota, ApiCallLog, UserApiConfig, OperationLog
from app.models.report import Report, ReportEvent, BacktestTask
from app.models.watchlist import WatchlistItem, WatchlistSnapshot
from app.api.auth import get_current_admin
from app.services.api_config_test import test_provider_config
from app.services.audit import action_label, log_operation, status_label
from app.services.quota import admin_usage_rankings, check_quota as service_check_quota, usage_for_user
from app.services.score_diagnostics import diagnose_real_scores
from app.services.system_status import build_system_status

router = APIRouter(prefix="/api/admin", tags=["管理"])


class UserUpdateRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class ResetPasswordRequest(BaseModel):
    password: str


@router.get("/stats")
def get_stats(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """系统统计数据"""
    from app.models.stock import Stock
    from app.models.trade_signal import TradeSignal
    from app.models.report import Report
    from app.models.research_report import ResearchReport

    total_stocks = db.query(Stock).count()
    total_signals = db.query(TradeSignal).count()
    total_users = db.query(User).count()
    total_reports = db.query(Report).count()
    total_research = db.query(ResearchReport).count()

    # DB file size
    db_size = "N/A"
    # Try common locations
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    for candidate in ["stock_agent.db", "data/rongxian.db", "data/stock_agent.db"]:
        db_path = os.path.join(backend_dir, candidate)
        if os.path.exists(db_path):
            size_bytes = os.path.getsize(db_path)
            if size_bytes > 1024 * 1024:
                db_size = f"{size_bytes / 1024 / 1024:.1f} MB"
            else:
                db_size = f"{size_bytes / 1024:.1f} KB"
            break
    # db_size remains "N/A" if no candidate file found

    return {
        "total_stocks": total_stocks,
        "total_signals": total_signals,
        "total_users": total_users,
        "total_reports": total_reports,
        "total_research_reports": total_research,
        "db_size": db_size,
    }


@router.get("/system-status")
def get_system_status(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """管理员系统健康与数据新鲜度视图。"""
    return build_system_status(db)


@router.get("/data-coverage")
def get_data_coverage(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """真实数据覆盖中心摘要。"""
    from app.services.data_coverage import summarize_market_data_coverage
    from app.services.real_pipeline import get_recent_refresh_job_runs, real_pipeline_status

    summary = summarize_market_data_coverage(db)
    status = build_system_status(db)
    return {
        **summary,
        "real_pipeline_status": real_pipeline_status(db),
        "recent_refresh_jobs": get_recent_refresh_job_runs(db, limit=10),
        "coverage_message": status.get("coverage_message"),
        "financial_failure_top_reasons": _top_failure_reasons(status.get("recent_refresh_jobs", []), "financial_failure_reasons"),
        "technical_failure_top_reasons": _top_failure_reasons(status.get("recent_refresh_jobs", []), "technical_failure_reasons"),
    }


@router.get("/score-diagnostics")
def get_score_diagnostics(
    score_date: Optional[date] = Query(None),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """真实评分解释摘要，不改评分，只解释当前结果结构。"""
    return diagnose_real_scores(db, score_date=score_date)


def _top_failure_reasons(jobs: list[dict], key: str, limit: int = 5) -> list[dict[str, int | str]]:
    from collections import Counter

    counter: Counter[str] = Counter()
    for job in jobs:
        summary = job.get("failure_summary") or {}
        reasons = summary.get(key) or {}
        for reason, count in reasons.items():
            counter[str(reason)] += int(count or 0)
    return [{"reason": reason, "count": count} for reason, count in counter.most_common(limit)]


@router.post("/run-real-pipeline")
def admin_run_real_pipeline(
    limit: int = Query(30, ge=1, le=300),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员手动触发真实小样本流水线。"""
    from app.services.real_pipeline import run_real_pipeline_sample

    result = run_real_pipeline_sample(
        db,
        limit=limit,
        trigger_source="admin_manual",
        created_by=admin.username,
    )
    if result.get("status") == "skipped_locked":
        raise HTTPException(status_code=409, detail="真实流水线正在运行，请稍后再试")
    return result


@router.get("/users")
def list_users(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """列出所有用户"""
    users = db.query(User).order_by(User.id).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "phone": u.phone,
            "user_id": u.user_id or u.username,
            "display_name": u.display_name,
            "email": u.email,
            "role": u.role,
            "status": u.status or ("active" if u.is_active else "disabled"),
            "is_active": u.is_active,
            "report_count": db.query(Report).filter(Report.user_id == u.id).count(),
            "api_config_count": db.query(UserApiConfig).filter(UserApiConfig.owner_user_id == u.id).count(),
            "pdf_downloads": db.query(ReportEvent).filter(ReportEvent.user_id == u.id, ReportEvent.format == "pdf", ReportEvent.action == "download").count(),
            "png_downloads": db.query(ReportEvent).filter(ReportEvent.user_id == u.id, ReportEvent.format == "png", ReportEvent.action == "download").count(),
            "html_views": db.query(ReportEvent).filter(ReportEvent.user_id == u.id, ReportEvent.format == "html", ReportEvent.action == "view").count(),
            "last_report_at": str(db.query(func.max(Report.created_at)).filter(Report.user_id == u.id).scalar() or ""),
            "created_at": str(u.created_at) if u.created_at else None,
            "last_login_at": str(u.last_login_at) if u.last_login_at else None,
            "updated_at": str(u.updated_at) if u.updated_at else None,
        }
        for u in users
    ]


@router.post("/users/{user_id}/reset-password")
def reset_user_password(user_id: int, req: ResetPasswordRequest, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    from app.api.auth import hash_password
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="新密码至少 8 位")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.password_hash = hash_password(req.password)
    db.commit()
    return {"status": "ok", "message": "密码已重置"}


@router.get("/users/export")
def export_users(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    from openpyxl import Workbook
    from io import BytesIO
    import urllib.parse
    wb = Workbook()
    ws = wb.active
    ws.title = "用户运营统计"
    headers = ["手机号", "用户ID", "角色", "状态", "注册时间", "最近登录", "报告总数", "PDF下载", "PNG下载", "HTML查看", "API配置数", "最近报告时间"]
    ws.append(headers)
    for u in db.query(User).order_by(User.id).all():
        ws.append([
            u.phone,
            u.user_id or u.username,
            u.role,
            u.status or ("active" if u.is_active else "disabled"),
            str(u.created_at) if u.created_at else "",
            str(u.last_login_at) if u.last_login_at else "",
            db.query(Report).filter(Report.user_id == u.id).count(),
            db.query(ReportEvent).filter(ReportEvent.user_id == u.id, ReportEvent.format == "pdf", ReportEvent.action == "download").count(),
            db.query(ReportEvent).filter(ReportEvent.user_id == u.id, ReportEvent.format == "png", ReportEvent.action == "download").count(),
            db.query(ReportEvent).filter(ReportEvent.user_id == u.id, ReportEvent.format == "html", ReportEvent.action == "view").count(),
            db.query(UserApiConfig).filter(UserApiConfig.owner_user_id == u.id).count(),
            str(db.query(func.max(Report.created_at)).filter(Report.user_id == u.id).scalar() or ""),
        ])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = "用户运营统计.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(filename)}"})


@router.put("/users/{user_id}")
def update_user(user_id: int, req: UserUpdateRequest, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """更新用户角色或状态"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if req.role is not None:
        if req.role not in ("admin", "analyst", "user", "guest"):
            raise HTTPException(status_code=400, detail="角色必须是 admin、analyst、user 或 guest")
        user.role = req.role
    if req.is_active is not None:
        user.is_active = req.is_active
    db.commit()
    log_api_call(db, admin.id, admin.username, "system", f"/api/admin/users/{user_id}", "PUT", 200, 0, None)
    return {"status": "ok", "message": "用户已更新"}


@router.delete("/users/{user_id}")
def disable_user(user_id: int, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """禁用用户（软删除）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="不能禁用自己")
    user.is_active = False
    db.commit()
    log_api_call(db, admin.id, admin.username, "system", f"/api/admin/users/{user_id}", "DELETE", 200, 0, None)
    return {"status": "ok", "message": "用户已禁用"}


@router.get("/tables")
def list_tables(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """列出所有数据库表及行数"""
    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    result = []
    for table in sorted(tables):
        try:
            safe_name = table.replace('"', '""')
            count = db.execute(text(f'SELECT COUNT(*) FROM "{safe_name}"')).scalar()
        except Exception:
            count = 0
        result.append({"name": table, "row_count": count})
    return result


@router.get("/tables/{table_name}")
def get_table_data(table_name: str, page: int = 1, page_size: int = 50, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """查看指定表的数据（分页）"""
    inspector = inspect(db.bind)
    # 先验证表名是否存在于数据库中（白名单校验，防止 SQL 注入）
    allowed_tables = set(inspector.get_table_names())
    if table_name not in allowed_tables:
        raise HTTPException(status_code=404, detail=f"表 {table_name} 不存在")

    # Get columns
    columns = [col["name"] for col in inspector.get_columns(table_name)]

    # 敏感字段列表：读取时脱敏
    SENSITIVE_FIELDS = {"password_hash", "api_key", "api_secret", "api_password", "token", "secret"}

    # 使用 SQLAlchemy 的 quoted_name 安全引用标识符（转义表名中的双引号防止注入）
    safe_name = table_name.replace('"', '""')
    total = db.execute(text(f'SELECT COUNT(*) FROM "{safe_name}"')).scalar()

    # Get paginated data
    offset = (page - 1) * page_size
    rows = db.execute(text(f'SELECT * FROM "{safe_name}" LIMIT :limit OFFSET :offset'), {"limit": page_size, "offset": offset}).fetchall()

    # Convert rows to list of dicts（敏感字段脱敏）
    data = []
    for row in rows:
        row_dict = {}
        for i, col in enumerate(columns):
            val = row[i]
            if col in SENSITIVE_FIELDS and val:
                row_dict[col] = "***"
            elif val is None:
                row_dict[col] = None
            elif isinstance(val, (int, float, bool, str)):
                row_dict[col] = val
            else:
                row_dict[col] = str(val)
        data.append(row_dict)

    return {
        "columns": columns,
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": data,
    }


# ==================== API配置管理 ====================

class ApiConfigRequest(BaseModel):
    provider: str
    display_name: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: Optional[str] = None
    is_enabled: Optional[bool] = None
    daily_limit: Optional[int] = None
    rate_limit: Optional[int] = None
    config_json: Optional[str] = None


class UserQuotaRequest(BaseModel):
    daily_report_limit: Optional[int] = None
    daily_backtest_limit: Optional[int] = None
    daily_search_limit: Optional[int] = None
    daily_pdf_limit: Optional[int] = None
    can_download_pdf: Optional[bool] = None
    can_use_style_report: Optional[bool] = None
    can_use_simulation: Optional[bool] = None


@router.get("/api-configs")
def list_api_configs(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """获取所有API配置"""
    configs = db.query(ApiConfig).order_by(ApiConfig.id).all()
    return [
        {
            "id": c.id,
            "provider": c.provider,
            "display_name": c.display_name,
            "api_key": _mask_key(c.api_key),
            "api_secret": _mask_key(c.api_secret),
            "base_url": c.base_url,
            "is_enabled": c.is_enabled,
            "daily_limit": c.daily_limit,
            "rate_limit": c.rate_limit,
            "config_json": c.config_json,
            "created_at": str(c.created_at) if c.created_at else None,
            "updated_at": str(c.updated_at) if c.updated_at else None,
        }
        for c in configs
    ]


@router.post("/api-configs")
def create_or_update_api_config(req: ApiConfigRequest, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """创建或更新API配置"""
    from app.core.config import ApiKeyCryptoError, encrypt_api_key

    start_time = time.time()

    existing = db.query(ApiConfig).filter(ApiConfig.provider == req.provider).first()
    if existing:
        if req.display_name is not None: existing.display_name = req.display_name
        try:
            if req.api_key is not None and req.api_key != "***": existing.api_key = encrypt_api_key(req.api_key)
            if req.api_secret is not None and req.api_secret != "***": existing.api_secret = encrypt_api_key(req.api_secret)
        except ApiKeyCryptoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if req.base_url is not None: existing.base_url = req.base_url
        if req.is_enabled is not None: existing.is_enabled = req.is_enabled
        if req.daily_limit is not None: existing.daily_limit = req.daily_limit
        if req.rate_limit is not None: existing.rate_limit = req.rate_limit
        if req.config_json is not None: existing.config_json = req.config_json
        db.commit()
        log_api_call(db, admin.id, admin.username, "system", f"/api/admin/api-configs/{existing.id}", "POST", 200, int((time.time() - start_time) * 1000), None)
        return {"status": "ok", "message": f"{req.provider} 配置已更新", "id": existing.id}
    else:
        try:
            config = ApiConfig(
                provider=req.provider,
                display_name=req.display_name or req.provider,
                api_key=encrypt_api_key(req.api_key) if req.api_key else None,
                api_secret=encrypt_api_key(req.api_secret) if req.api_secret else None,
                base_url=req.base_url,
                is_enabled=req.is_enabled if req.is_enabled is not None else True,
                daily_limit=req.daily_limit or 1000,
                rate_limit=req.rate_limit or 10,
                config_json=req.config_json,
            )
        except ApiKeyCryptoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        db.add(config)
        db.commit()
        db.refresh(config)
        log_api_call(db, admin.id, admin.username, "system", f"/api/admin/api-configs/{config.id}", "POST", 200, int((time.time() - start_time) * 1000), None)
        return {"status": "ok", "message": f"{req.provider} 配置已创建", "id": config.id}


@router.delete("/api-configs/{config_id}")
def delete_api_config(config_id: int, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """删除API配置"""
    import time
    start_time = time.time()
    config = db.query(ApiConfig).filter(ApiConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    provider = config.provider
    db.delete(config)
    db.commit()
    log_api_call(db, admin.id, admin.username, "system", f"/api/admin/api-configs/{config_id}", "DELETE", 200, int((time.time() - start_time) * 1000), None)
    return {"status": "ok", "message": f"{provider} 配置已删除"}


@router.post("/api-configs/{config_id}/test")
def test_api_config(config_id: int, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """测试API连接"""
    start_time = time.time()
    config = db.query(ApiConfig).filter(ApiConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    # 根据供应商类型测试连接
    if config.provider == "eastmoney":
        try:
            import requests
            resp = requests.get("https://push2.eastmoney.com/api/qt/clist/get", timeout=5,
                                params={"pn": 1, "pz": 1, "fs": "m:1+t:2", "fields": "f12,f14"})
            if resp.status_code == 200:
                log_api_call(db, admin.id, admin.username, "system", f"/api/admin/api-configs/{config_id}/test", "POST", 200, int((time.time() - start_time) * 1000), None)
                return {"status": "ok", "message": "东方财富API连接正常"}
            message = f"连接失败: HTTP {resp.status_code}"
            log_api_call(db, admin.id, admin.username, "system", f"/api/admin/api-configs/{config_id}/test", "POST", resp.status_code, int((time.time() - start_time) * 1000), message)
            return {"status": "error", "message": message}
        except Exception as e:
            message = f"连接失败: {str(e)}"
            log_api_call(db, admin.id, admin.username, "system", f"/api/admin/api-configs/{config_id}/test", "POST", 500, int((time.time() - start_time) * 1000), message)
            return {"status": "error", "message": message}
    elif config.provider == "yahoo":
        try:
            import requests
            resp = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/000001.SS", timeout=5)
            if resp.status_code == 200:
                log_api_call(db, admin.id, admin.username, "system", f"/api/admin/api-configs/{config_id}/test", "POST", 200, int((time.time() - start_time) * 1000), None)
                return {"status": "ok", "message": "Yahoo Finance连接正常"}
            message = f"连接失败: HTTP {resp.status_code}"
            log_api_call(db, admin.id, admin.username, "system", f"/api/admin/api-configs/{config_id}/test", "POST", resp.status_code, int((time.time() - start_time) * 1000), message)
            return {"status": "error", "message": message}
        except Exception as e:
            message = f"连接失败: {str(e)}"
            log_api_call(db, admin.id, admin.username, "system", f"/api/admin/api-configs/{config_id}/test", "POST", 500, int((time.time() - start_time) * 1000), message)
            return {"status": "error", "message": message}
    else:
        message = f"{config.provider} 暂不支持自动测试"
        log_api_call(db, admin.id, admin.username, "system", f"/api/admin/api-configs/{config_id}/test", "POST", 200, int((time.time() - start_time) * 1000), message)
        return {"status": "ok", "message": message}


def _mask_key(key: str) -> str:
    """掩码显示密钥"""
    if not key:
        return ""
    if len(key) <= 8:
        return "***"
    return key[:4] + "***" + key[-4:]


# ==================== 用户配额管理 ====================

@router.get("/user-quotas")
def list_user_quotas(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """获取所有用户配额"""
    users = db.query(User).order_by(User.id).all()
    result = []
    for u in users:
        quota = db.query(UserApiQuota).filter(UserApiQuota.user_id == u.id).first()
        # 统计今日调用次数
        today = date.today()
        today_calls = db.query(ApiCallLog).filter(
            ApiCallLog.user_id == u.id,
            func.date(ApiCallLog.called_at) == today,
        ).count()

        today_reports = db.query(ApiCallLog).filter(
            ApiCallLog.user_id == u.id,
            func.date(ApiCallLog.called_at) == today,
            ApiCallLog.endpoint.like("/api/reports/generate%"),
        ).count()

        today_backtests = db.query(ApiCallLog).filter(
            ApiCallLog.user_id == u.id,
            func.date(ApiCallLog.called_at) == today,
            ApiCallLog.endpoint.like("/api/backtest%"),
        ).count()

        result.append({
            "user_id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "role": u.role,
            "is_active": u.is_active,
            "daily_report_limit": quota.daily_report_limit if quota else 5,
            "daily_backtest_limit": quota.daily_backtest_limit if quota else 3,
            "daily_search_limit": quota.daily_search_limit if quota else 100,
            "daily_pdf_limit": quota.daily_pdf_limit if quota else 10,
            "can_download_pdf": quota.can_download_pdf if quota else True,
            "can_use_style_report": quota.can_use_style_report if quota else True,
            "can_use_simulation": quota.can_use_simulation if quota else True,
            "today_calls": today_calls,
            "today_reports": today_reports,
            "today_backtests": today_backtests,
        })
    return result


@router.put("/user-quotas/{user_id}")
def update_user_quota(user_id: int, req: UserQuotaRequest, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """更新用户配额"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    quota = db.query(UserApiQuota).filter(UserApiQuota.user_id == user_id).first()
    if not quota:
        quota = UserApiQuota(user_id=user_id)
        db.add(quota)

    if req.daily_report_limit is not None: quota.daily_report_limit = req.daily_report_limit
    if req.daily_backtest_limit is not None: quota.daily_backtest_limit = req.daily_backtest_limit
    if req.daily_search_limit is not None: quota.daily_search_limit = req.daily_search_limit
    if req.daily_pdf_limit is not None: quota.daily_pdf_limit = req.daily_pdf_limit
    if req.can_download_pdf is not None: quota.can_download_pdf = req.can_download_pdf
    if req.can_use_style_report is not None: quota.can_use_style_report = req.can_use_style_report
    if req.can_use_simulation is not None: quota.can_use_simulation = req.can_use_simulation

    db.commit()
    return {"status": "ok", "message": f"{user.username} 配额已更新"}


# ==================== 调用日志 ====================

@router.get("/api-logs")
def list_api_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = Query(None),
    provider: Optional[str] = Query(None),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取API调用日志"""
    query = db.query(ApiCallLog)
    if user_id:
        query = query.filter(ApiCallLog.user_id == user_id)
    if provider:
        query = query.filter(ApiCallLog.provider == provider)

    total = query.count()
    logs = query.order_by(ApiCallLog.called_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": l.id,
                "user_id": l.user_id,
                "username": l.username,
                "provider": l.provider,
                "endpoint": l.endpoint,
                "method": l.method,
                "status_code": l.status_code,
                "response_time": l.response_time,
                "error_msg": l.error_msg,
                "called_at": str(l.called_at) if l.called_at else None,
            }
            for l in logs
        ],
    }


@router.get("/api-stats")
def get_api_stats(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """获取API调用统计"""
    today = date.today()

    # 今日总调用
    today_total = db.query(ApiCallLog).filter(func.date(ApiCallLog.called_at) == today).count()

    # 今日按供应商统计
    by_provider = db.query(
        ApiCallLog.provider, func.count(ApiCallLog.id)
    ).filter(
        func.date(ApiCallLog.called_at) == today
    ).group_by(ApiCallLog.provider).all()

    # 今日按用户统计
    by_user = db.query(
        ApiCallLog.username, func.count(ApiCallLog.id)
    ).filter(
        func.date(ApiCallLog.called_at) == today
    ).group_by(ApiCallLog.username).all()

    # 今日错误数
    today_errors = db.query(ApiCallLog).filter(
        func.date(ApiCallLog.called_at) == today,
        ApiCallLog.status_code >= 400,
    ).count()

    # 平均响应时间
    avg_time = db.query(func.avg(ApiCallLog.response_time)).filter(
        func.date(ApiCallLog.called_at) == today
    ).scalar()

    return {
        "today_total": today_total,
        "today_errors": today_errors,
        "avg_response_time": round(avg_time or 0),
        "by_provider": {p: c for p, c in by_provider},
        "by_user": {u: c for u, c in by_user},
    }


# ==================== 调用记录工具函数 ====================

def log_api_call(db: Session, user_id: int, username: str, provider: str, endpoint: str, method: str, status_code: int, response_time: int = 0, error_msg: str = None):
    """记录API调用（供其他模块调用）"""
    log = ApiCallLog(
        user_id=user_id,
        username=username,
        provider=provider,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        response_time=response_time,
        error_msg=error_msg,
    )
    db.add(log)
    db.commit()


def check_user_quota(db: Session, user_id: int, quota_type: str) -> tuple[bool, str]:
    """检查用户配额，返回 (allowed, message)"""
    from sqlalchemy import func as sqlfunc

    # admin 和 guest 不限制
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.role in ("admin", "guest"):
        return True, ""

    quota = db.query(UserApiQuota).filter(UserApiQuota.user_id == user_id).first()
    today = date.today()

    if quota_type == "report":
        limit = quota.daily_report_limit if quota else 5
        used = db.query(ApiCallLog).filter(
            ApiCallLog.user_id == user_id,
            func.date(ApiCallLog.called_at) == today,
            ApiCallLog.endpoint.like("/api/reports/generate%"),
        ).count()
        if used >= limit:
            return False, f"今日报告生成次数已达上限（{limit}次）"

    elif quota_type == "backtest":
        limit = quota.daily_backtest_limit if quota else 3
        used = db.query(ApiCallLog).filter(
            ApiCallLog.user_id == user_id,
            func.date(ApiCallLog.called_at) == today,
            ApiCallLog.endpoint.like("/api/backtest%"),
        ).count()
        if used >= limit:
            return False, f"今日回测次数已达上限（{limit}次）"

    elif quota_type == "pdf":
        if quota and not quota.can_download_pdf:
            return False, "无PDF下载权限"
        limit = quota.daily_pdf_limit if quota else 10
        used = db.query(ApiCallLog).filter(
            ApiCallLog.user_id == user_id,
            func.date(ApiCallLog.called_at) == today,
            ApiCallLog.endpoint.like("/api/reports/%/pdf"),
        ).count()
        if used >= limit:
            return False, f"今日PDF下载次数已达上限（{limit}次）"

    elif quota_type == "style_report":
        if quota and not quota.can_use_style_report:
            return False, "无风格报告权限"

    elif quota_type == "simulation":
        if quota and not quota.can_use_simulation:
            return False, "无模拟买入权限"

    return True, ""


# ==================== 股票管理 ====================

class StockUpdateRequest(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    sector: Optional[str] = None
    status: Optional[str] = None


@router.get("/stocks")
def admin_list_stocks(
    keyword: str = Query("", description="搜索关键词"),
    market: str = Query(None, description="市场筛选"),
    status: str = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员股票列表"""
    from app.models.stock import Stock
    query = db.query(Stock)
    if keyword:
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter((Stock.symbol.like(f"%{escaped}%", escape="\\")) | (Stock.name.like(f"%{escaped}%", escape="\\")))
    if market:
        query = query.filter(Stock.market == market)
    if status:
        query = query.filter(Stock.status == status)
    total = query.count()
    stocks = query.order_by(Stock.id).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": s.id, "symbol": s.symbol, "name": s.name,
                "market": s.market, "exchange": s.exchange,
                "industry": s.industry, "sector": s.sector,
                "status": s.status, "currency": s.currency,
                "created_at": str(s.created_at) if s.created_at else None,
            }
            for s in stocks
        ],
    }


@router.put("/stocks/{stock_id}")
def admin_update_stock(stock_id: int, req: StockUpdateRequest, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """编辑股票信息"""
    from app.models.stock import Stock
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="股票不存在")
    if req.name is not None:
        stock.name = req.name
    if req.industry is not None:
        stock.industry = req.industry
    if req.sector is not None:
        stock.sector = req.sector
    if req.status is not None:
        if req.status not in ("ACTIVE", "DELISTED", "SUSPENDED"):
            raise HTTPException(status_code=400, detail="状态必须是 ACTIVE、DELISTED 或 SUSPENDED")
        stock.status = req.status
    db.commit()
    return {"status": "ok", "message": f"{stock.symbol} 已更新"}


@router.delete("/stocks/{stock_id}")
def admin_delete_stock(stock_id: int, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """删除股票及其关联数据"""
    from app.models.stock import Stock
    from app.models.daily_price import DailyPrice
    from app.models.financial_metric import FinancialMetric
    from app.models.technical_indicator import TechnicalIndicator
    from app.models.stock_score import StockScore
    from app.models.trade_signal import TradeSignal
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="股票不存在")
    symbol = stock.symbol
    for model in [DailyPrice, FinancialMetric, TechnicalIndicator, StockScore, TradeSignal]:
        db.query(model).filter(model.stock_id == stock_id).delete()
    db.delete(stock)
    db.commit()
    return {"status": "ok", "message": f"{symbol} 及关联数据已删除"}


@router.post("/stocks/sync")
def admin_sync_stocks(
    market: str = Query("ALL", description="同步市场: A_SHARE / HK / ALL"),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """从东方财富同步股票列表"""
    from app.services.stock_sync import sync_stock_list
    result = sync_stock_list(db, market=market)
    return {"status": "ok", "message": f"同步完成: 新增{result['added']}，更新{result['updated']}，共{result['total']}", **result}


@router.post("/stocks/fetch")
def admin_fetch_stock(
    symbol: str = Query(..., description="股票代码"),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """添加单只股票并获取全部数据"""
    from app.api.stocks import add_stock_and_fetch
    return add_stock_and_fetch(symbol=symbol, db=db, user=admin)


# ==================== 评分管理 ====================

class ScoreUpdateRequest(BaseModel):
    quality_score: Optional[float] = None
    valuation_score: Optional[float] = None
    growth_score: Optional[float] = None
    trend_score: Optional[float] = None
    risk_score: Optional[float] = None
    rating: Optional[str] = None
    reason_summary: Optional[str] = None


@router.get("/scores")
def admin_list_scores(
    keyword: str = Query("", description="搜索代码/名称"),
    rating: str = Query(None, description="评级筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员评分列表"""
    from app.models.stock_score import StockScore
    from app.models.stock import Stock
    query = db.query(StockScore, Stock).join(Stock, StockScore.stock_id == Stock.id)
    if keyword:
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter((Stock.symbol.like(f"%{escaped}%", escape="\\")) | (Stock.name.like(f"%{escaped}%", escape="\\")))
    if rating:
        query = query.filter(StockScore.rating == rating)
    total = query.count()
    results = query.order_by(StockScore.score_date.desc(), StockScore.total_score.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": score.id, "stock_id": stock.id, "symbol": stock.symbol, "name": stock.name,
                "total_score": score.total_score, "quality_score": score.quality_score,
                "valuation_score": score.valuation_score, "growth_score": score.growth_score,
                "trend_score": score.trend_score, "risk_score": score.risk_score,
                "rating": score.rating, "reason_summary": score.reason_summary,
                "score_date": str(score.score_date),
            }
            for score, stock in results
        ],
    }


@router.put("/scores/{score_id}")
def admin_update_score(score_id: int, req: ScoreUpdateRequest, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """手动调整评分"""
    from app.models.stock_score import StockScore
    score = db.query(StockScore).filter(StockScore.id == score_id).first()
    if not score:
        raise HTTPException(status_code=404, detail="评分记录不存在")
    if req.quality_score is not None:
        score.quality_score = req.quality_score
    if req.valuation_score is not None:
        score.valuation_score = req.valuation_score
    if req.growth_score is not None:
        score.growth_score = req.growth_score
    if req.trend_score is not None:
        score.trend_score = req.trend_score
    if req.risk_score is not None:
        score.risk_score = req.risk_score
    if req.rating is not None:
        score.rating = req.rating
    if req.reason_summary is not None:
        score.reason_summary = req.reason_summary
    score.total_score = round((score.quality_score or 0) + (score.valuation_score or 0) + (score.growth_score or 0) + (score.trend_score or 0) + (score.risk_score or 0), 1)
    db.commit()
    return {"status": "ok", "message": "评分已更新", "total_score": score.total_score}


# ==================== 信号管理 ====================

class SignalUpdateRequest(BaseModel):
    signal_type: Optional[str] = None
    signal_strength: Optional[int] = None
    suggested_position: Optional[float] = None
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    holding_period: Optional[str] = None
    status: Optional[str] = None


@router.get("/signals")
def admin_list_signals(
    keyword: str = Query("", description="搜索代码/名称"),
    signal_type: str = Query(None, description="信号类型"),
    status: str = Query(None, description="状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员信号列表"""
    from app.models.trade_signal import TradeSignal
    from app.models.stock import Stock
    query = db.query(TradeSignal, Stock).join(Stock, TradeSignal.stock_id == Stock.id)
    if keyword:
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter((Stock.symbol.like(f"%{escaped}%", escape="\\")) | (Stock.name.like(f"%{escaped}%", escape="\\")))
    if signal_type:
        query = query.filter(TradeSignal.signal_type == signal_type)
    if status:
        query = query.filter(TradeSignal.status == status)
    total = query.count()
    results = query.order_by(TradeSignal.signal_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": sig.id, "stock_id": stock.id, "symbol": stock.symbol, "name": stock.name,
                "signal_type": sig.signal_type, "signal_strength": sig.signal_strength,
                "suggested_position": sig.suggested_position,
                "entry_price": sig.entry_price, "target_price": sig.target_price,
                "stop_loss_price": sig.stop_loss_price, "holding_period": sig.holding_period,
                "status": sig.status, "signal_date": str(sig.signal_date),
            }
            for sig, stock in results
        ],
    }


@router.put("/signals/{signal_id}")
def admin_update_signal(signal_id: int, req: SignalUpdateRequest, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """编辑信号"""
    from app.models.trade_signal import TradeSignal
    sig = db.query(TradeSignal).filter(TradeSignal.id == signal_id).first()
    if not sig:
        raise HTTPException(status_code=404, detail="信号不存在")
    if req.signal_type is not None:
        sig.signal_type = req.signal_type
    if req.signal_strength is not None:
        sig.signal_strength = req.signal_strength
    if req.suggested_position is not None:
        sig.suggested_position = req.suggested_position
    if req.entry_price is not None:
        sig.entry_price = req.entry_price
    if req.target_price is not None:
        sig.target_price = req.target_price
    if req.stop_loss_price is not None:
        sig.stop_loss_price = req.stop_loss_price
    if req.holding_period is not None:
        sig.holding_period = req.holding_period
    if req.status is not None:
        if req.status not in ("ACTIVE", "EXPIRED", "EXECUTED"):
            raise HTTPException(status_code=400, detail="状态必须是 ACTIVE、EXPIRED 或 EXECUTED")
        sig.status = req.status
    db.commit()
    return {"status": "ok", "message": "信号已更新"}


@router.delete("/signals/{signal_id}")
def admin_delete_signal(signal_id: int, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """删除信号"""
    from app.models.trade_signal import TradeSignal
    sig = db.query(TradeSignal).filter(TradeSignal.id == signal_id).first()
    if not sig:
        raise HTTPException(status_code=404, detail="信号不存在")
    db.delete(sig)
    db.commit()
    return {"status": "ok", "message": "信号已删除"}
def _log_to_summary(log: ApiCallLog | None) -> dict | None:
    if not log:
        return None
    return {
        "time": str(log.called_at) if log.called_at else None,
        "actor": log.username or "system",
        "status": "error" if (log.status_code or 0) >= 400 else "ok",
        "duration_ms": log.response_time or 0,
        "summary": log.endpoint,
        "error": log.error_msg,
        "status_code": log.status_code,
    }


def _event_to_summary(event: ReportEvent | None) -> dict | None:
    if not event:
        return None
    return {
        "time": str(event.created_at) if event.created_at else None,
        "actor": str(event.user_id or "system"),
        "status": "ok",
        "duration_ms": 0,
        "summary": f"report_id={event.report_id} {event.action} {event.format}",
        "error": None,
        "status_code": 200,
    }


@router.get("/operation-logs")
def get_operation_logs(
    limit: int = Query(30, ge=1, le=100),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    logs = db.query(ApiCallLog).order_by(ApiCallLog.called_at.desc()).limit(limit).all()
    items = []
    for log in logs:
        endpoint = log.endpoint or ""
        if "/backtest/" in endpoint:
            log_type = "backtest"
        elif "/reports/" in endpoint and endpoint.endswith("/pdf"):
            log_type = "report_export"
        elif "/reports/" in endpoint:
            log_type = "report_generate"
        elif "/stocks/sync" in endpoint:
            log_type = "stock_sync"
        elif "/admin/" in endpoint:
            log_type = "admin_action"
        else:
            log_type = "system"
        items.append(
            {
                "time": str(log.called_at) if log.called_at else None,
                "type": log_type,
                "status": "error" if (log.status_code or 0) >= 400 else "ok",
                "actor": log.username or "system",
                "duration_ms": log.response_time or 0,
                "summary": endpoint,
                "error": log.error_msg,
                "status_code": log.status_code,
            }
        )
    return {"items": items}


@router.get("/operation-logs/summary")
def get_operation_log_summary(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    def latest_like(pattern: str):
        return db.query(ApiCallLog).filter(ApiCallLog.endpoint.like(pattern)).order_by(ApiCallLog.called_at.desc()).first()

    def latest_event(fmt: str, action: str):
        return db.query(ReportEvent).filter(ReportEvent.format == fmt, ReportEvent.action == action).order_by(ReportEvent.created_at.desc()).first()

    return {
        "latest_stock_sync": _log_to_summary(latest_like("%/stocks/sync%")),
        "latest_report_generate": _log_to_summary(latest_like("/api/reports/generate%")),
        "latest_html_view": _event_to_summary(latest_event("html", "view")),
        "latest_png_export": _event_to_summary(latest_event("png", "download")),
        "latest_pdf_export": _log_to_summary(latest_like("/api/reports/%/pdf")),
        "latest_backtest": _log_to_summary(latest_like("/api/backtest/%")),
        "latest_error": _log_to_summary(db.query(ApiCallLog).filter(ApiCallLog.status_code >= 400).order_by(ApiCallLog.called_at.desc()).first()),
        "latest_admin_action": _log_to_summary(latest_like("/api/admin/%")),
    }


@router.get("/usage-rankings")
def get_usage_rankings(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return admin_usage_rankings(db)


@router.get("/watchlist-stats")
def get_watchlist_stats(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    total_items = db.query(WatchlistItem).count()
    total_users = db.query(func.count(func.distinct(WatchlistItem.user_id))).scalar() or 0
    today_added = db.query(WatchlistItem).filter(func.date(WatchlistItem.created_at) == date.today()).count()

    top_rows = (
        db.query(
            WatchlistItem.stock_code,
            func.max(WatchlistItem.stock_name).label("stock_name"),
            func.count(WatchlistItem.id).label("watch_count"),
            func.max(WatchlistItem.industry).label("industry"),
        )
        .group_by(WatchlistItem.stock_code)
        .order_by(func.count(WatchlistItem.id).desc(), WatchlistItem.stock_code.asc())
        .limit(20)
        .all()
    )

    latest_snapshot_subquery = (
        db.query(
            WatchlistSnapshot.watchlist_id.label("watchlist_id"),
            func.max(WatchlistSnapshot.id).label("latest_id"),
        )
        .group_by(WatchlistSnapshot.watchlist_id)
        .subquery()
    )
    recent_snapshot_count = (
        db.query(WatchlistSnapshot)
        .join(latest_snapshot_subquery, WatchlistSnapshot.id == latest_snapshot_subquery.c.latest_id)
        .count()
    )

    industry_rows = (
        db.query(
            func.coalesce(WatchlistItem.industry, "未分类").label("industry"),
            func.count(WatchlistItem.id).label("watch_count"),
        )
        .group_by(func.coalesce(WatchlistItem.industry, "未分类"))
        .order_by(func.count(WatchlistItem.id).desc(), func.coalesce(WatchlistItem.industry, "未分类").asc())
        .limit(8)
        .all()
    )

    positive_volatility_count = 0
    latest_snapshots = (
        db.query(WatchlistSnapshot)
        .join(latest_snapshot_subquery, WatchlistSnapshot.id == latest_snapshot_subquery.c.latest_id)
        .all()
    )
    for snapshot in latest_snapshots:
        try:
            payload = json.loads(snapshot.volatility_signal_json or "{}")
        except Exception:
            payload = {}
        if payload.get("signal") == "positive":
            positive_volatility_count += 1

    watch_created_subquery = (
        db.query(
            WatchlistItem.user_id.label("user_id"),
            WatchlistItem.stock_code.label("stock_code"),
            func.min(WatchlistItem.created_at).label("watched_at"),
        )
        .group_by(WatchlistItem.user_id, WatchlistItem.stock_code)
        .subquery()
    )

    reports_after_watch = (
        db.query(func.count(Report.id))
        .join(
            watch_created_subquery,
            (watch_created_subquery.c.user_id == Report.user_id)
            & (watch_created_subquery.c.stock_code == Report.stock_code),
        )
        .filter(Report.created_at >= watch_created_subquery.c.watched_at)
        .scalar()
        or 0
    )
    backtests_after_watch = (
        db.query(func.count(BacktestTask.id))
        .join(
            watch_created_subquery,
            (watch_created_subquery.c.user_id == BacktestTask.user_id)
            & (watch_created_subquery.c.stock_code == BacktestTask.stock_code),
        )
        .filter(BacktestTask.created_at >= watch_created_subquery.c.watched_at)
        .scalar()
        or 0
    )

    return {
        "summary": {
            "total_items": total_items,
            "total_users": total_users,
            "today_added": today_added,
            "snapshots_ready": recent_snapshot_count,
            "high_volatility_watch_count": positive_volatility_count,
            "reports_after_watch": int(reports_after_watch),
            "backtests_after_watch": int(backtests_after_watch),
        },
        "top_watched": [
            {
                "stock_code": row.stock_code,
                "stock_name": row.stock_name,
                "watch_count": int(row.watch_count or 0),
                "industry": row.industry,
            }
            for row in top_rows
        ],
        "industry_distribution": [
            {"industry": row.industry, "watch_count": int(row.watch_count or 0)}
            for row in industry_rows
        ],
    }


def _serialize_audit_log(log: OperationLog) -> dict:
    actor = log.phone or log.username or (str(log.user_id) if log.user_id else "系统")
    return {
        "id": log.id,
        "user_id": log.user_id,
        "phone": log.phone,
        "username": log.username,
        "role": log.role or "-",
        "action": log.action,
        "action_label": action_label(log.action),
        "target_type": log.target_type,
        "target_id": log.target_id,
        "status": log.status,
        "status_label": status_label(log.status),
        "message": log.message or "",
        "actor": actor,
        "created_at": str(log.created_at) if log.created_at else None,
        "ip": log.ip,
    }


def _audit_query(
    db: Session,
    range: str = "all",
    user_keyword: str | None = None,
    action: str | None = None,
    status: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    query = db.query(OperationLog)
    now = datetime.now()
    if range == "7":
        query = query.filter(OperationLog.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7))
    elif range == "30":
        query = query.filter(OperationLog.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30))
    elif range == "custom":
        if start_date:
            query = query.filter(func.date(OperationLog.created_at) >= start_date)
        if end_date:
            query = query.filter(func.date(OperationLog.created_at) <= end_date)
    if user_keyword:
        keyword = f"%{user_keyword}%"
        conditions = [OperationLog.username.like(keyword), OperationLog.phone.like(keyword)]
        if user_keyword.isdigit():
            conditions.append(OperationLog.user_id == int(user_keyword))
        query = query.filter(conditions[0] | conditions[1] | (conditions[2] if len(conditions) > 2 else conditions[0]))
    if action:
        query = query.filter(OperationLog.action == action)
    if status:
        query = query.filter(OperationLog.status == status)
    return query


@router.get("/audit-logs")
def get_audit_logs(
    range: str = Query("all"),
    user_keyword: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = _audit_query(db, range, user_keyword, action, status, start_date, end_date)
    total = query.count()
    logs = query.order_by(OperationLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [_serialize_audit_log(log) for log in logs]}


@router.get("/audit-logs/export")
def export_audit_logs(
    request: Request,
    range: str = Query("all"),
    user_keyword: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    from io import BytesIO
    import urllib.parse
    from openpyxl import Workbook

    query = _audit_query(db, range, user_keyword, action, status, start_date, end_date)
    wb = Workbook()
    ws = wb.active
    ws.title = "审计日志"
    ws.append(["时间", "用户", "角色", "操作", "对象", "状态", "摘要"])
    for item in query.order_by(OperationLog.created_at.desc()).limit(5000).all():
        row = _serialize_audit_log(item)
        ws.append([row["created_at"], row["actor"], row["role"], row["action_label"], f'{row["target_type"]}:{row["target_id"] or "-"}', row["status_label"], row["message"]])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    log_operation(db, user=admin, action="admin_export_audit_logs", target_type="audit", message="export audit logs", request=request)
    filename = "审计日志.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(filename)}"})


@router.post("/api-configs/{config_id}/check")
def check_api_config(config_id: int, request: Request, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    from app.core.config import decrypt_api_key

    config = db.query(ApiConfig).filter(ApiConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    model_name = None
    if config.config_json and "model" in config.config_json:
        model_name = config.config_json
    try:
        api_key = decrypt_api_key(config.api_key)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = test_provider_config(config.provider, config.base_url, model_name, api_key)
    log_operation(db, user=admin, action="admin_api_config_test", target_type="api_config", target_id=config.id, status="failed" if result.status == "failed" else "success", message=result.message, request=request)
    return {"status": result.status, "message": result.message}
