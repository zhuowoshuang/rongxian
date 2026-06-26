"""系统设置 API"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db
from app.models.setting import Setting
from app.api.auth import get_current_admin, get_current_user

router = APIRouter(prefix="/api/settings", tags=["设置"])


class SettingUpdate(BaseModel):
    key: str
    value: str


class NotificationConfig(BaseModel):
    email_smtp_host: Optional[str] = None
    email_smtp_port: Optional[str] = None
    email_sender: Optional[str] = None
    email_password: Optional[str] = None
    email_recipient: Optional[str] = None
    feishu_webhook: Optional[str] = None
    feishu_enabled: Optional[str] = None


@router.get("")
def get_settings(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """获取所有设置"""
    settings = db.query(Setting).all()
    return {s.key: {"value": s.value, "description": s.description} for s in settings}


@router.get("/notification")
def get_notification_config(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """获取通知配置"""
    keys = [
        "email_smtp_host", "email_smtp_port", "email_sender", "email_password",
        "email_recipient", "feishu_webhook", "feishu_enabled",
    ]
    settings = db.query(Setting).filter(Setting.key.in_(keys)).all()
    result = {s.key: s.value for s in settings}
    # 隐藏密码
    if result.get("email_password"):
        result["email_password"] = "***"
    return result


@router.post("/notification")
def update_notification_config(config: NotificationConfig, db: Session = Depends(get_db), user=Depends(get_current_admin)):
    """更新通知配置"""
    defaults = {
        "email_smtp_host": ("SMTP 服务器", "smtp.qq.com"),
        "email_smtp_port": ("SMTP 端口", "465"),
        "email_sender": ("发件邮箱", ""),
        "email_password": ("邮箱授权码", ""),
        "email_recipient": ("收件邮箱", ""),
        "feishu_webhook": ("飞书 Webhook URL", ""),
        "feishu_enabled": ("启用飞书推送", "false"),
    }

    for key, value in config.model_dump(exclude_none=True).items():
        if key == "email_password" and value == "***":
            continue
        existing = db.query(Setting).filter(Setting.key == key).first()
        desc = defaults.get(key, ("", ""))[0]
        if existing:
            existing.value = value
        else:
            db.add(Setting(key=key, value=value, description=desc))

    db.commit()
    return {"status": "ok", "message": "通知配置已保存"}


@router.post("/test-notification")
def test_notification(
    type: str = Query("email", description="测试类型: email / feishu"),
    db: Session = Depends(get_db),
    user=Depends(get_current_admin),
):
    """测试通知推送"""
    from app.services.notification import get_notification_service

    service = get_notification_service(db)

    test_signals = [
        {"symbol": "600519", "name": "贵州茅台", "type": "BUY", "score": 88, "position": 8},
        {"symbol": "300750", "name": "宁德时代", "type": "WATCH", "score": 68, "position": 0},
    ]
    test_indices = [
        {"name": "上证指数", "current": 3200.50, "change_pct": 0.85},
        {"name": "深证成指", "current": 10500.30, "change_pct": 1.20},
    ]

    if type == "email":
        recipient = service.config.get("email_recipient", "")
        if not recipient:
            raise HTTPException(status_code=400, detail="未配置收件邮箱")
        result = service.send_email(
            recipient,
            "清数智算 测试邮件",
            service.build_daily_email("中性偏多", test_signals, test_indices),
        )
        if result:
            return {"status": "ok", "message": f"测试邮件已发送至 {recipient}"}
        else:
            raise HTTPException(status_code=500, detail="邮件发送失败，请检查配置")

    elif type == "feishu":
        result = service.send_feishu(
            "清数智算 测试消息",
            service.build_daily_feishu("中性偏多", test_signals, test_indices),
        )
        if result:
            return {"status": "ok", "message": "飞书测试消息已发送"}
        else:
            raise HTTPException(status_code=500, detail="飞书发送失败，请检查 Webhook URL")

    raise HTTPException(status_code=400, detail="不支持的通知类型")


@router.post("/save")
def save_setting(setting: SettingUpdate, db: Session = Depends(get_db), user=Depends(get_current_admin)):
    """保存单个设置"""
    existing = db.query(Setting).filter(Setting.key == setting.key).first()
    if existing:
        existing.value = setting.value
    else:
        db.add(Setting(key=setting.key, value=setting.value))
    db.commit()
    return {"status": "ok"}
