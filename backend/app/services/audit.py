"""Unified audit logging helpers."""

from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.api_config import OperationLog
from app.models.user import User


SECRET_MARKERS = ("password", "api_key", "apikey", "secret", "token", "sk-")


def sanitize_message(message: str | None) -> str | None:
    if not message:
        return message
    text = str(message)
    lower = text.lower()
    if any(marker in lower for marker in SECRET_MARKERS):
        return "操作已记录，敏感内容已脱敏"
    return text[:500]


def log_operation(
    db: Session,
    *,
    user: User | None = None,
    user_id: int | None = None,
    username: str | None = None,
    role: str | None = None,
    phone: str | None = None,
    action: str,
    target_type: str,
    target_id: str | int | None = None,
    status: str = "success",
    message: str | None = None,
    request: Request | None = None,
    commit: bool = True,
) -> OperationLog:
    if user is not None:
        user_id = user.id
        username = user.username
        role = user.role
        phone = user.phone

    log = OperationLog(
        user_id=user_id,
        username=username,
        phone=phone,
        role=role,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        status="failed" if status in ("error", "failed") else "success",
        message=sanitize_message(message),
        ip=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    db.add(log)
    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
    return log


def action_label(action: str) -> str:
    labels = {
        "login_success": "登录成功",
        "login_failed": "登录失败",
        "register": "用户注册",
        "report_generate": "生成报告",
        "report_html_view": "查看 HTML 报告",
        "report_png_download": "下载 PNG",
        "report_pdf_download": "下载 PDF",
        "backtest_run": "运行回测",
        "api_config_create": "新增 API 配置",
        "api_config_update": "编辑 API 配置",
        "api_config_delete": "删除 API 配置",
        "api_config_test": "测试 API 配置",
        "watchlist_add": "关注股票",
        "watchlist_remove": "取消关注",
        "watchlist_view_snapshot": "查看关注快照",
        "watchlist_refresh_snapshot": "刷新关注快照",
        "admin_reset_password": "管理员重置密码",
        "admin_export_users": "导出用户 Excel",
        "admin_export_audit_logs": "导出审计日志 Excel",
        "admin_api_config_save": "保存平台 API 配置",
        "admin_api_config_delete": "删除平台 API 配置",
        "admin_api_config_test": "测试平台 API 配置",
        "permission_denied": "无权限访问",
        "api_error": "接口失败",
    }
    return labels.get(action, action)


def status_label(status: str) -> str:
    return "失败" if status in ("failed", "error") else "成功"
