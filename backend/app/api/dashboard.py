"""Dashboard API."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.redis import cache_backend_mode, cache_get, cache_set
from app.db.session import get_db
from app.models.trade_signal import TradeSignal
from app.services.dashboard import get_dashboard_data

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _available_signal_dates(db: Session, limit: int = 3) -> list[date]:
    rows = (
        db.query(TradeSignal.signal_date)
        .distinct()
        .order_by(TradeSignal.signal_date.desc())
        .limit(limit)
        .all()
    )
    return [row[0] for row in rows if row and row[0]]


@router.get("/available-dates")
def available_dates(db: Session = Depends(get_db)):
    dates = _available_signal_dates(db, limit=3)
    return {
        "available_dates": [str(item) for item in dates],
        "latest_date": str(dates[0]) if dates else None,
    }


@router.get("")
def dashboard(
    requested_date: str | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
):
    dates = _available_signal_dates(db, limit=3)
    if not dates:
        raise HTTPException(status_code=404, detail="当前没有可用于展示的策略总览数据")

    selected_date = dates[0]
    if requested_date:
        try:
            selected_date = date.fromisoformat(requested_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="日期格式无效，请使用 YYYY-MM-DD") from exc
        if selected_date not in dates:
            raise HTTPException(status_code=404, detail="该日期暂无策略总览数据，请切换到最近三个可用日期")

    cache_key = f"dashboard:{selected_date}"
    cached = cache_get(cache_key)
    if cached:
        cached.setdefault("meta", {})
        cached["meta"]["cache_mode"] = cache_backend_mode()
        cached["meta"]["cache_ttl_seconds"] = 300
        cached["meta"]["is_cached"] = True
        cached["meta"]["available_dates"] = [str(item) for item in dates]
        cached["meta"]["view_date"] = str(selected_date)
        return cached

    data = get_dashboard_data(db, selected_date)
    data.setdefault("meta", {})
    data["meta"]["cache_mode"] = cache_backend_mode()
    data["meta"]["cache_ttl_seconds"] = 300
    data["meta"]["is_cached"] = False
    data["meta"]["available_dates"] = [str(item) for item in dates]
    data["meta"]["view_date"] = str(selected_date)
    cache_set(cache_key, data, ttl=300)
    return data
