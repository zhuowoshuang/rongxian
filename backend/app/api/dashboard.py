"""Dashboard API."""

from __future__ import annotations

import copy
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.redis import cache_backend_mode
from app.db.session import get_db
from app.models.trade_signal import TradeSignal
from app.services.dashboard import _empty_dashboard, get_dashboard_data
from app.services.data_credibility import REAL_SIGNAL_SOURCE, include_demo_enabled
from app.services.score_diagnostics import diagnose_real_scores
from app.services.system_status import build_system_status

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

DASHBOARD_CACHE_TTL_SECONDS = 300
_dashboard_summary_cache: dict[str, dict] = {}


def _available_signal_dates(db: Session, limit: int = 3, include_demo: bool = False) -> list[date]:
    query = db.query(TradeSignal.signal_date)
    if not include_demo:
        query = query.filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE)
    rows = query.distinct().order_by(TradeSignal.signal_date.desc()).limit(limit).all()
    return [row[0] for row in rows if row and row[0]]


@router.get("/available-dates")
def available_dates(include_demo: bool = Query(False), db: Session = Depends(get_db)):
    include_demo = include_demo_enabled(include_demo)
    dates = _available_signal_dates(db, limit=3, include_demo=include_demo)
    return {
        "available_dates": [str(item) for item in dates],
        "latest_date": str(dates[0]) if dates else None,
    }


def _dashboard_cache_key(selected_date: date, include_demo: bool) -> str:
    return f"{selected_date.isoformat()}:include_demo={str(include_demo).lower()}"


def _dashboard_cache_payload(
    payload: dict,
    *,
    generated_at: str,
    hit: bool,
    stale: bool,
    fallback_used: bool,
) -> dict:
    result = copy.deepcopy(payload)
    result.setdefault("meta", {})
    result["meta"]["cache_mode"] = cache_backend_mode()
    result["meta"]["cache_ttl_seconds"] = DASHBOARD_CACHE_TTL_SECONDS
    result["meta"]["is_cached"] = hit or fallback_used
    result["meta"]["cache"] = {
        "enabled": True,
        "hit": hit,
        "generated_at": generated_at,
        "ttl_seconds": DASHBOARD_CACHE_TTL_SECONDS,
        "stale": stale,
        "fallback_used": fallback_used,
    }
    return result


def _read_dashboard_cache(cache_key: str) -> tuple[dict | None, bool]:
    entry = _dashboard_summary_cache.get(cache_key)
    if not entry:
        return None, False
    stale = datetime.now() >= entry["expires_at"]
    return entry, stale


def _write_dashboard_cache(cache_key: str, payload: dict) -> dict:
    generated_at = payload.get("meta", {}).get("generated_at") or datetime.now().isoformat(timespec="seconds")
    entry = {
        "payload": copy.deepcopy(payload),
        "generated_at": generated_at,
        "expires_at": datetime.now() + timedelta(seconds=DASHBOARD_CACHE_TTL_SECONDS),
    }
    _dashboard_summary_cache[cache_key] = entry
    return entry


def _clear_dashboard_cache() -> None:
    _dashboard_summary_cache.clear()


@router.get("")
def dashboard(
    requested_date: str | None = Query(None, alias="date"),
    include_demo: bool = Query(False),
    refresh: bool = Query(False, description="Skip cache and force refresh"),
    db: Session = Depends(get_db),
):
    include_demo = include_demo_enabled(include_demo)
    dates = _available_signal_dates(db, limit=3, include_demo=include_demo)
    system_status = build_system_status(db)

    if not dates and not include_demo:
        diagnostics = diagnose_real_scores(db)
        diagnostics_summary = diagnostics.get("summary", {})
        data = _empty_dashboard(
            {
                "signal_date": None,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "available_dates": [],
                "view_date": None,
                "data_mode": system_status.get("data_mode"),
                "data_mode_label": system_status.get("data_mode_label"),
                "warning": system_status.get("warning"),
                "real_score_count": system_status.get("real_score_count", 0),
                "demo_score_count": system_status.get("demo_score_count", 0),
                "real_signal_count": system_status.get("real_signal_count", 0),
                "demo_signal_count": system_status.get("demo_signal_count", 0),
                "demo_contaminated": system_status.get("data_mode") == "demo_contaminated",
                "formal_real_count": diagnostics_summary.get("formal_real_count", 0),
                "real_observation_count": diagnostics_summary.get("real_observation_count", 0),
                "data_quality_limited_count": diagnostics_summary.get("data_quality_limited_count", 0),
                "data_insufficient_count": diagnostics_summary.get("data_insufficient_count", 0),
                "core_total": diagnostics_summary.get("core_total", 0),
                "core_ready_full_count": diagnostics_summary.get("core_ready_full_count", 0),
                "latest_real_score_date": diagnostics_summary.get("score_date"),
                "avg_total_score": diagnostics_summary.get("avg_total_score"),
                "avg_quality_score": diagnostics_summary.get("avg_quality_score"),
                "avg_valuation_score": diagnostics_summary.get("avg_valuation_score"),
                "avg_growth_score": diagnostics_summary.get("avg_growth_score"),
                "avg_trend_score": diagnostics_summary.get("avg_trend_score"),
                "avg_risk_score": diagnostics_summary.get("avg_risk_score"),
                "low_score_reasons": diagnostics.get("low_score_reasons", [])[:5],
                "launch_data_status": diagnostics_summary.get("launch_data_status"),
                "data_quality_warning": diagnostics_summary.get("message"),
            }
        )
        data["meta"]["cache_mode"] = cache_backend_mode()
        data["meta"]["cache_ttl_seconds"] = DASHBOARD_CACHE_TTL_SECONDS
        data["meta"]["is_cached"] = False
        data["meta"]["cache"] = {
            "enabled": True,
            "hit": False,
            "generated_at": data["meta"]["generated_at"],
            "ttl_seconds": DASHBOARD_CACHE_TTL_SECONDS,
            "stale": False,
            "fallback_used": False,
        }
        return data

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

    cache_key = _dashboard_cache_key(selected_date, include_demo)
    cached_entry, stale = _read_dashboard_cache(cache_key)
    if cached_entry and not stale and not refresh:
        cached = _dashboard_cache_payload(
            cached_entry["payload"],
            generated_at=cached_entry["generated_at"],
            hit=True,
            stale=False,
            fallback_used=False,
        )
        cached["meta"]["available_dates"] = [str(item) for item in dates]
        cached["meta"]["view_date"] = str(selected_date)
        return cached

    try:
        data = get_dashboard_data(db, selected_date, include_demo=include_demo)
    except Exception as exc:
        if cached_entry:
            fallback = _dashboard_cache_payload(
                cached_entry["payload"],
                generated_at=cached_entry["generated_at"],
                hit=False,
                stale=stale,
                fallback_used=True,
            )
            fallback["meta"]["available_dates"] = [str(item) for item in dates]
            fallback["meta"]["view_date"] = str(selected_date)
            fallback["meta"]["warning"] = "当前显示最近一次成功聚合结果，最新聚合暂时失败。"
            fallback["meta"]["cache_warning"] = str(exc)
            return fallback
        raise HTTPException(status_code=503, detail="投研驾驶舱聚合暂时不可用，请稍后重试。") from exc

    data.setdefault("meta", {})
    data["meta"]["available_dates"] = [str(item) for item in dates]
    data["meta"]["view_date"] = str(selected_date)
    entry = _write_dashboard_cache(cache_key, data)
    return _dashboard_cache_payload(
        entry["payload"],
        generated_at=entry["generated_at"],
        hit=False,
        stale=False,
        fallback_used=False,
    )
