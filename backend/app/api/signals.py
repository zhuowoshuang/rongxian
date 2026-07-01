"""信号中心 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.daily_price import DailyPrice
from app.models.stock import Stock
from app.models.trade_signal import TradeSignal
from app.services.data_credibility import (
    DEMO_SIGNAL_SOURCE,
    REAL_SIGNAL_SOURCE,
    include_demo_enabled,
)
from app.services.compliance import signal_display_label, sanitize_research_text
from app.services.research_display_summary import build_research_display_summary

router = APIRouter(prefix="/api/signals", tags=["信号"])


@router.get("")
def list_signals(
    market: str = Query(None, description="市场: A_SHARE / HK"),
    signal_type: str = Query(None, description="信号类型: BUY/ADD/WATCH/REDUCE/SELL"),
    min_score: float = Query(None, description="最低评分"),
    signal_date: str = Query(None, description="信号日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_demo: bool = Query(False, description="是否包含演示信号"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """获取信号列表，默认仅返回真实信号。"""
    include_demo = include_demo_enabled(include_demo)
    query = db.query(TradeSignal, Stock).join(Stock, TradeSignal.stock_id == Stock.id)
    if include_demo:
        latest = db.query(func.max(TradeSignal.signal_date)).scalar()
    else:
        query = query.filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE)
        latest = db.query(func.max(TradeSignal.signal_date)).filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE).scalar()

    if signal_date:
        query = query.filter(TradeSignal.signal_date == signal_date)
    elif latest:
        query = query.filter(TradeSignal.signal_date == latest)

    if market:
        query = query.filter(Stock.market == market)
    if signal_type:
        query = query.filter(TradeSignal.signal_type == signal_type)
    elif not include_demo:
        query = query.filter(TradeSignal.signal_type.in_(["BUY", "ADD", "WATCH"]))

    total = query.count()
    results = query.order_by(TradeSignal.signal_strength.desc(), TradeSignal.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    stock_ids = [stock.id for _, stock in results]
    price_map = {}
    if stock_ids:
        latest_date_sq = (
            db.query(DailyPrice.stock_id, func.max(DailyPrice.trade_date).label("max_date"))
            .filter(DailyPrice.stock_id.in_(stock_ids))
            .group_by(DailyPrice.stock_id)
            .subquery()
        )
        prices = (
            db.query(DailyPrice)
            .join(latest_date_sq, (DailyPrice.stock_id == latest_date_sq.c.stock_id) & (DailyPrice.trade_date == latest_date_sq.c.max_date))
            .all()
        )
        price_map = {price.stock_id: price for price in prices}

    items = []
    for sig, stock in results:
        price = price_map.get(stock.id)
        items.append(
            {
                "id": sig.id,
                "stock_id": stock.id,
                "symbol": stock.symbol,
                "name": stock.name,
                "market": stock.market,
                "signal_type": sig.signal_type,
                "signal_strength": sig.signal_strength,
                "suggested_position": sig.suggested_position,
                "entry_price": sig.entry_price,
                "target_price": sig.target_price,
                "stop_loss_price": sig.stop_loss_price,
                "holding_period": sig.holding_period,
                "logic": sig.logic_json,
                "risk": sig.risk_json,
                "status": sig.status,
                "signal_date": str(sig.signal_date),
                "latest_close": price.close if price else None,
                "change_pct": round((price.close - price.pre_close) / price.pre_close * 100, 2) if price and price.pre_close and price.pre_close != 0 else None,
                "signal_source": sig.signal_source,
                "updated_at": str(sig.signal_date) if sig.signal_date else None,
                "source_type": "研究信号",
                "source_name": "trade_signals",
            }
        )

    summary = build_research_display_summary(db, include_demo=include_demo)
    diagnostics = summary["diagnostics"]
    system_status = summary["system"]
    latest_real_signal_date = (
        db.query(func.max(TradeSignal.signal_date))
        .filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE)
        .scalar()
    )
    risk_rising_count = 0
    avoid_observation_count = 0
    if latest_real_signal_date:
        risk_rising_count = (
            db.query(func.count(TradeSignal.id))
            .filter(
                TradeSignal.signal_source == REAL_SIGNAL_SOURCE,
                TradeSignal.signal_date == latest_real_signal_date,
                TradeSignal.signal_type == "REDUCE",
            )
            .scalar()
            or 0
        )
        avoid_observation_count = (
            db.query(func.count(TradeSignal.id))
            .filter(
                TradeSignal.signal_source == REAL_SIGNAL_SOURCE,
                TradeSignal.signal_date == latest_real_signal_date,
                TradeSignal.signal_type == "SELL",
            )
            .scalar()
            or 0
        )
    real_observation_count = risk_rising_count + avoid_observation_count
    formal_signal_count = sum(1 for item in items if item.get("signal_source") == REAL_SIGNAL_SOURCE) if include_demo else total
    risk_observation_items = []
    for item in diagnostics.get("items", []):
        signal_type_value = item.get("signal_type")
        if signal_type_value not in {"REDUCE", "SELL"}:
            continue
        risk_observation_items.append(
            {
                "symbol": item.get("stock_code"),
                "name": sanitize_research_text(item.get("stock_name")),
                "signal_type": signal_type_value,
                "signal_label": signal_display_label(signal_type_value),
                "score": item.get("total_score"),
                "score_source": item.get("score_source"),
                "primary_low_score_reason": sanitize_research_text(item.get("primary_low_score_reason")),
                "display_tier": item.get("display_tier"),
            }
        )
    risk_observation_items = sorted(
        risk_observation_items,
        key=lambda item: (0 if item.get("signal_type") == "SELL" else 1, item.get("score") or 999, item.get("symbol") or ""),
    )[:8]
    data_quality_limited_items = []
    for item in diagnostics.get("items", []):
        if item.get("display_tier") != "data_quality_limited":
            continue
        data_quality_limited_items.append(
            {
                "symbol": item.get("stock_code"),
                "name": sanitize_research_text(item.get("stock_name")),
                "signal_type": item.get("signal_type"),
                "signal_label": signal_display_label(item.get("signal_type")) if item.get("signal_type") else None,
                "score": item.get("total_score"),
                "score_source": item.get("score_source"),
                "primary_low_score_reason": sanitize_research_text(item.get("primary_low_score_reason")),
                "display_tier": item.get("display_tier"),
                "blocking_reasons": item.get("blocking_reasons") or [],
            }
        )
    data_quality_limited_items = sorted(
        data_quality_limited_items,
        key=lambda item: (item.get("score") or 999, item.get("symbol") or ""),
    )[:8]
    message = None
    if not include_demo and total == 0:
        message = "当前暂无正式研究信号。真实样本仍以风险观察和数据质量受限样本为主，请先查看风险观察样本或前往个股评分库。"

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
        "message": message,
        "risk_observation_count": real_observation_count,
        "risk_observation_summary": {
            "risk_rising_count": risk_rising_count,
            "avoid_observation_count": avoid_observation_count,
        },
        "risk_observation_items": risk_observation_items,
        "data_quality_limited_items": data_quality_limited_items,
        "meta": {
            "include_demo": include_demo,
            "real_signal_count": system_status.get("real_signal_count", 0),
            "demo_signal_count": system_status.get("demo_signal_count", 0),
            "data_mode": system_status.get("data_mode"),
            "warning": system_status.get("warning"),
            "demo_isolated": not include_demo and system_status.get("demo_signal_count", 0) > 0,
            "demo_source_key": DEMO_SIGNAL_SOURCE,
            "summary": {
                "real_signal_count": system_status.get("real_signal_count", 0),
                "formal_signal_count": formal_signal_count,
                "demo_signal_count": system_status.get("demo_signal_count", 0),
                "risk_rising_count": risk_rising_count,
                "avoid_observation_count": avoid_observation_count,
                "data_quality_limited_count": diagnostics.get("data_quality_limited_count", 0),
            },
            "message": message,
        },
        "diagnostics": {
            "real_score_count": diagnostics.get("real_count", 0),
            "formal_real_count": diagnostics.get("formal_real_count", 0),
            "real_observation_count": real_observation_count,
            "risk_observation_count": real_observation_count,
            "risk_rising_count": risk_rising_count,
            "avoid_observation_count": avoid_observation_count,
            "data_quality_limited_count": diagnostics.get("data_quality_limited_count", 0),
            "top_reasons": diagnostics.get("top_reasons", []),
            "launch_data_status": diagnostics.get("launch_data_status"),
        },
    }
