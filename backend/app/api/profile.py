"""User profile, personal API configs, reports, backtests and watchlist."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import ApiKeyCryptoError, decrypt_api_key, encrypt_api_key
from app.db.session import get_db
from app.models.api_config import UserApiConfig
from app.models.report import BacktestTask, Report, ReportEvent
from app.models.user import User
from app.models.watchlist import WatchlistItem, WatchlistSnapshot
from app.services.api_config_test import test_provider_config
from app.services.audit import log_operation
from app.services.quota import check_quota, usage_for_user
from app.services.watchlist import create_or_refresh_watch_snapshot

router = APIRouter(prefix="/api/profile", tags=["profile"])


def mask_key(value: str | None) -> str | None:
    if not value:
        return None
    try:
        plain = decrypt_api_key(value)
    except ApiKeyCryptoError:
        return "需重新保存"
    if not plain:
        return None
    if len(plain) <= 8:
        return "***"
    return f"{plain[:3]}***{plain[-4:]}"


def _loads(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _snapshot_to_dict(snapshot: WatchlistSnapshot | None) -> dict | None:
    if not snapshot:
        return None
    return {
        "id": snapshot.id,
        "stock_code": snapshot.stock_code,
        "stock_name": snapshot.stock_name,
        "snapshot_date": str(snapshot.snapshot_date) if snapshot.snapshot_date else None,
        "price": snapshot.price,
        "change_pct": snapshot.change_pct,
        "market": snapshot.market,
        "industry": snapshot.industry,
        "sector": snapshot.sector,
        "total_score": snapshot.total_score,
        "quality_score": snapshot.quality_score,
        "valuation_score": snapshot.valuation_score,
        "growth_score": snapshot.growth_score,
        "trend_score": snapshot.trend_score,
        "risk_score": snapshot.risk_score,
        "rating": snapshot.rating,
        "signal_type": snapshot.signal_type,
        "risk_flags": _loads(snapshot.risk_flags, []),
        "key_metrics": _loads(snapshot.key_metrics_json, {}),
        "news_summary": _loads(snapshot.news_summary_json, {"status": "not_connected", "summary": "公司新闻源暂未接入"}),
        "industry_support": _loads(snapshot.industry_support_json, {"status": "not_connected", "summary": "行业消息源暂未接入"}),
        "shareholder_signal": _loads(snapshot.shareholder_signal_json, {"status": "not_connected", "summary": "股东结构数据暂未接入或暂缺"}),
        "earnings_signal": _loads(snapshot.earnings_signal_json, {"status": "no_data", "summary": "财务趋势样本不足"}),
        "volatility_signal": _loads(snapshot.volatility_signal_json, {"status": "placeholder", "summary": "波动率阈值待交易员确认"}),
        "created_at": str(snapshot.created_at) if snapshot.created_at else None,
    }


def _watch_item_to_dict(item: WatchlistItem, snapshot: WatchlistSnapshot | None) -> dict:
    return {
        "id": item.id,
        "stock_code": item.stock_code,
        "stock_name": item.stock_name,
        "market": item.market,
        "industry": item.industry,
        "status": item.status,
        "created_at": str(item.created_at) if item.created_at else None,
        "last_snapshot_at": str(item.last_snapshot_at) if item.last_snapshot_at else None,
        "snapshot": _snapshot_to_dict(snapshot),
    }


class UserApiConfigRequest(BaseModel):
    name: str
    provider: str
    base_url: str | None = None
    api_key: str | None = None
    model_name: str | None = None
    is_default: bool = False
    note: str | None = None


class WatchlistRequest(BaseModel):
    stock_code: str
    stock_name: str | None = None
    market: str | None = None
    industry: str | None = None


def serialize_config(config: UserApiConfig) -> dict:
    return {
        "id": config.id,
        "name": config.name,
        "provider": config.provider,
        "base_url": config.base_url,
        "api_key": mask_key(config.api_key),
        "model_name": config.model_name,
        "is_default": config.is_default,
        "note": config.note,
        "status": config.status,
        "created_at": str(config.created_at) if config.created_at else None,
        "updated_at": str(config.updated_at) if config.updated_at else None,
    }


@router.get("")
def get_profile(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "phone": user.phone,
        "user_id": user.user_id or user.username,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "status": user.status or ("active" if user.is_active else "disabled"),
        "created_at": str(user.created_at) if user.created_at else None,
        "last_login_at": str(user.last_login_at) if user.last_login_at else None,
    }


@router.get("/usage")
def get_my_usage(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return usage_for_user(db, user)


@router.get("/api-configs")
def list_user_api_configs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    configs = db.query(UserApiConfig).filter(UserApiConfig.owner_user_id == user.id).order_by(UserApiConfig.id.desc()).all()
    return [serialize_config(c) for c in configs]


@router.post("/api-configs")
def create_user_api_config(req: UserApiConfigRequest, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    allowed, msg = check_quota(db, user, "api_config")
    if not allowed:
        log_operation(db, user=user, action="api_config_create", target_type="user_api_config", status="failed", message=msg, request=request)
        raise HTTPException(status_code=429, detail=msg)
    if not req.name.strip() or not req.provider.strip():
        raise HTTPException(status_code=400, detail="配置名称和供应商不能为空")
    if req.api_key is not None and not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API Key 留空时请删除该字段，或填写有效 Key")
    if req.is_default:
        db.query(UserApiConfig).filter(UserApiConfig.owner_user_id == user.id).update({"is_default": False})
    data = req.model_dump()
    if data.get("api_key"):
        try:
            data["api_key"] = encrypt_api_key(data["api_key"])
        except ApiKeyCryptoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    config = UserApiConfig(owner_user_id=user.id, **data)
    db.add(config)
    db.commit()
    db.refresh(config)
    log_operation(db, user=user, action="api_config_create", target_type="user_api_config", target_id=config.id, message=f"provider={config.provider}", request=request)
    return serialize_config(config)


@router.put("/api-configs/{config_id}")
def update_user_api_config(config_id: int, req: UserApiConfigRequest, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    config = db.query(UserApiConfig).filter(UserApiConfig.id == config_id, UserApiConfig.owner_user_id == user.id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    if req.is_default:
        db.query(UserApiConfig).filter(UserApiConfig.owner_user_id == user.id, UserApiConfig.id != config_id).update({"is_default": False})
    config.name = req.name
    config.provider = req.provider
    config.base_url = req.base_url
    if req.api_key:
        try:
            config.api_key = encrypt_api_key(req.api_key)
        except ApiKeyCryptoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    config.model_name = req.model_name
    config.is_default = req.is_default
    config.note = req.note
    db.commit()
    db.refresh(config)
    log_operation(db, user=user, action="api_config_update", target_type="user_api_config", target_id=config.id, message=f"provider={config.provider}", request=request)
    return serialize_config(config)


@router.delete("/api-configs/{config_id}")
def delete_user_api_config(config_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    config = db.query(UserApiConfig).filter(UserApiConfig.id == config_id, UserApiConfig.owner_user_id == user.id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    provider = config.provider
    db.delete(config)
    db.commit()
    log_operation(db, user=user, action="api_config_delete", target_type="user_api_config", target_id=config_id, message=f"provider={provider}", request=request)
    return {"status": "ok", "message": "配置已删除"}


@router.post("/api-configs/{config_id}/test")
def test_user_api_config(config_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    config = db.query(UserApiConfig).filter(UserApiConfig.id == config_id, UserApiConfig.owner_user_id == user.id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    try:
        api_key = decrypt_api_key(config.api_key)
    except ApiKeyCryptoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = test_provider_config(config.provider, config.base_url, config.model_name, api_key)
    log_operation(db, user=user, action="api_config_test", target_type="user_api_config", target_id=config.id, status="failed" if result.status == "failed" else "success", message=result.message, request=request)
    return {"status": result.status, "message": result.message}


@router.get("/reports")
def my_reports(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reports = db.query(Report).filter(Report.user_id == user.id).order_by(Report.created_at.desc()).limit(100).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "report_type": r.report_type,
            "style": r.style,
            "stock_code": r.stock_code,
            "stock_name": r.stock_name,
            "created_at": str(r.created_at) if r.created_at else None,
            "download_count": db.query(ReportEvent).filter(ReportEvent.report_id == r.id, ReportEvent.action == "download").count(),
        }
        for r in reports
    ]


@router.get("/backtests")
def my_backtests(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tasks = db.query(BacktestTask).filter(BacktestTask.user_id == user.id).order_by(BacktestTask.created_at.desc()).limit(100).all()
    return [
        {
            "id": t.id,
            "stock_code": t.stock_code,
            "stock_name": t.stock_name,
            "market": t.market,
            "strategy": t.strategy,
            "strategy_name": t.strategy_name,
            "rebalance_frequency": t.rebalance_frequency,
            "start_date": t.start_date,
            "end_date": t.end_date,
            "status": t.status,
            "error_message": t.error_message,
            "created_at": str(t.created_at) if t.created_at else None,
        }
        for t in tasks
    ]


@router.get("/watchlist")
def list_watchlist(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).order_by(WatchlistItem.created_at.desc()).all()
    response = []
    for item in items:
        snapshot = (
            db.query(WatchlistSnapshot)
            .filter(WatchlistSnapshot.watchlist_id == item.id)
            .order_by(WatchlistSnapshot.snapshot_date.desc(), WatchlistSnapshot.id.desc())
            .first()
        )
        response.append(_watch_item_to_dict(item, snapshot))
    return response


@router.post("/watchlist")
def create_watchlist_item(req: WatchlistRequest, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stock_code = req.stock_code.strip()
    if not stock_code:
        raise HTTPException(status_code=400, detail="请先选择股票后再加入关注")
    existing = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user.id, WatchlistItem.stock_code == stock_code, WatchlistItem.status == "active")
        .first()
    )
    if existing:
        snapshot = create_or_refresh_watch_snapshot(db, existing)
        log_operation(db, user=user, action="watchlist_refresh_snapshot", target_type="watchlist", target_id=existing.id, message=stock_code, request=request)
        return _watch_item_to_dict(existing, snapshot)

    item = WatchlistItem(
        user_id=user.id,
        stock_code=stock_code,
        stock_name=(req.stock_name or stock_code).strip(),
        market=req.market,
        industry=req.industry,
        status="active",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    snapshot = create_or_refresh_watch_snapshot(db, item)
    log_operation(db, user=user, action="watchlist_add", target_type="watchlist", target_id=item.id, message=stock_code, request=request)
    return _watch_item_to_dict(item, snapshot)


@router.post("/watchlist/{item_id}/refresh")
def refresh_watchlist_snapshot(item_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id, WatchlistItem.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="关注记录不存在")
    snapshot = create_or_refresh_watch_snapshot(db, item)
    log_operation(db, user=user, action="watchlist_refresh_snapshot", target_type="watchlist", target_id=item.id, message=item.stock_code, request=request)
    return _watch_item_to_dict(item, snapshot)


@router.get("/watchlist/{item_id}/snapshot")
def get_watchlist_snapshot(item_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id, WatchlistItem.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="关注记录不存在")
    snapshot = (
        db.query(WatchlistSnapshot)
        .filter(WatchlistSnapshot.watchlist_id == item.id)
        .order_by(WatchlistSnapshot.snapshot_date.desc(), WatchlistSnapshot.id.desc())
        .first()
    )
    if snapshot is None:
        snapshot = create_or_refresh_watch_snapshot(db, item)
    log_operation(db, user=user, action="watchlist_view_snapshot", target_type="watchlist", target_id=item.id, message=item.stock_code, request=request)
    return {"item": _watch_item_to_dict(item, snapshot), "snapshot": _snapshot_to_dict(snapshot)}


@router.delete("/watchlist/{item_id}")
def delete_watchlist_item(item_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id, WatchlistItem.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="关注记录不存在")
    stock_code = item.stock_code
    db.query(WatchlistSnapshot).filter(WatchlistSnapshot.watchlist_id == item.id).delete()
    db.delete(item)
    db.commit()
    log_operation(db, user=user, action="watchlist_remove", target_type="watchlist", target_id=item_id, message=stock_code, request=request)
    return {"status": "ok", "message": "已取消关注"}
