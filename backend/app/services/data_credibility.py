"""Helpers for separating real-calculated data from demo seed data."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, inspect
from sqlalchemy.orm import Session

from app.models.stock_score import StockScore
from app.models.trade_signal import TradeSignal

REAL_SCORE_SOURCE = "real_calculated"
DEMO_SCORE_SOURCE = "quick_seed_demo"
UNKNOWN_SCORE_SOURCE = "unknown_legacy"

REAL_SIGNAL_SOURCE = "real_calculated"
DEMO_SIGNAL_SOURCE = "quick_seed_demo"
UNKNOWN_SIGNAL_SOURCE = "unknown_legacy"

VALUATION_READY = "ready"
VALUATION_PARTIAL = "partial"
VALUATION_MISSING = "missing"

REPORT_STATUS_REAL = "real_backed"
REPORT_STATUS_PARTIAL = "partial_real"
REPORT_STATUS_PARTIAL_NO_VALUATION = "partial_real_no_valuation"
REPORT_STATUS_DEMO = "demo_backed"
REPORT_STATUS_INSUFFICIENT = "data_insufficient"


def include_demo_enabled(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def score_label(source: str | None) -> str:
    if source == REAL_SCORE_SOURCE:
        return "真实评分"
    if source == DEMO_SCORE_SOURCE:
        return "演示评分"
    return "待生成"


def valuation_readiness(pe: float | None, pb: float | None) -> str:
    has_pe = isinstance(pe, (int, float)) and pe > 0
    has_pb = isinstance(pb, (int, float)) and pb > 0
    if has_pe and has_pb:
        return VALUATION_READY
    if has_pe or has_pb:
        return VALUATION_PARTIAL
    return VALUATION_MISSING


def report_data_status(source: str | None, *, pe: float | None = None, pb: float | None = None) -> str:
    readiness = valuation_readiness(pe, pb)
    if source == REAL_SCORE_SOURCE:
        if readiness == VALUATION_READY:
            return REPORT_STATUS_REAL
        if readiness == VALUATION_PARTIAL:
            return REPORT_STATUS_PARTIAL
        return REPORT_STATUS_PARTIAL_NO_VALUATION
    if source == DEMO_SCORE_SOURCE:
        return REPORT_STATUS_DEMO
    return REPORT_STATUS_INSUFFICIENT


def score_is_real(source: str | None) -> bool:
    return source == REAL_SCORE_SOURCE


def build_data_readiness(
    *,
    has_price: bool,
    has_financial: bool,
    has_technical: bool,
    has_score: bool,
    score_source: str | None,
) -> dict[str, Any]:
    is_real = score_is_real(score_source)
    if not has_price:
        readiness_level = "no_data"
    elif has_score and is_real and has_financial and has_technical:
        readiness_level = "ready_full"
    elif has_score and not is_real:
        readiness_level = "demo_score"
    elif has_price:
        readiness_level = "price_only"
    else:
        readiness_level = "no_data"

    return {
        "has_price": has_price,
        "has_financial": has_financial,
        "has_technical": has_technical,
        "has_score": has_score,
        "score_is_real": is_real,
        "readiness_level": readiness_level,
    }


def _has_column(db: Session, table: str, column: str) -> bool:
    inspector = inspect(db.get_bind())
    return any(item.get("name") == column for item in inspector.get_columns(table))


def mark_existing_scores_as_demo(db: Session) -> dict[str, int]:
    if not _has_column(db, "stock_scores", "score_source"):
        raise RuntimeError("stock_scores.score_source 字段不存在，无法标记历史评分来源")
    if not _has_column(db, "trade_signals", "signal_source"):
        raise RuntimeError("trade_signals.signal_source 字段不存在，无法标记历史信号来源")

    real_score_count = db.query(func.count(StockScore.id)).filter(StockScore.score_source == REAL_SCORE_SOURCE).scalar() or 0
    real_signal_count = db.query(func.count(TradeSignal.id)).filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE).scalar() or 0

    score_marked_count = (
        db.query(StockScore)
        .filter((StockScore.score_source.is_(None)) | (StockScore.score_source == UNKNOWN_SCORE_SOURCE))
        .update({StockScore.score_source: DEMO_SCORE_SOURCE}, synchronize_session=False)
    )
    signal_marked_count = (
        db.query(TradeSignal)
        .filter((TradeSignal.signal_source.is_(None)) | (TradeSignal.signal_source == UNKNOWN_SIGNAL_SOURCE))
        .update({TradeSignal.signal_source: DEMO_SIGNAL_SOURCE}, synchronize_session=False)
    )
    db.commit()

    demo_score_count = db.query(func.count(StockScore.id)).filter(StockScore.score_source == DEMO_SCORE_SOURCE).scalar() or 0
    demo_signal_count = db.query(func.count(TradeSignal.id)).filter(TradeSignal.signal_source == DEMO_SIGNAL_SOURCE).scalar() or 0

    return {
        "score_marked_count": int(score_marked_count or 0),
        "signal_marked_count": int(signal_marked_count or 0),
        "real_score_count": int(real_score_count),
        "demo_score_count": int(demo_score_count),
        "real_signal_count": int(real_signal_count),
        "demo_signal_count": int(demo_signal_count),
    }
