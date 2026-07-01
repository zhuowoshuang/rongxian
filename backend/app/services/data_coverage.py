"""Unified data coverage assessment for stocks and market-wide summaries."""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.technical_indicator import TechnicalIndicator
from app.models.trade_signal import TradeSignal
from app.services.data_credibility import (
    DEMO_SCORE_SOURCE,
    DEMO_SIGNAL_SOURCE,
    REAL_SCORE_SOURCE,
    REAL_SIGNAL_SOURCE,
)
CORE_STOCKS = [
    "600519",
    "000001",
    "000002",
    "000858",
    "000333",
    "000651",
    "002594",
    "300750",
    "601318",
    "600036",
    "600030",
    "600276",
    "601899",
    "601012",
    "002415",
]

COVERAGE_LEVELS = (
    "no_data",
    "price_only",
    "technical_ready",
    "financial_ready",
    "score_ready",
    "signal_ready",
    "ready_full",
    "demo_only",
    "mixed_partial",
)

READINESS_LABELS = {
    "no_data": "无可用数据",
    "price_only": "仅行情可用",
    "technical_ready": "技术指标已就绪",
    "financial_ready": "财务数据已就绪",
    "score_ready": "真实评分已生成",
    "signal_ready": "真实信号已生成",
    "ready_full": "真实数据完整",
    "demo_only": "仅演示评分",
    "mixed_partial": "部分数据就绪",
}


def _resolve_coverage_level(
    *,
    has_price: bool,
    has_financial: bool,
    has_technical: bool,
    has_real_score: bool,
    has_real_signal: bool,
    has_demo_score: bool,
) -> str:
    if not has_price:
        return "no_data"
    if has_real_score and has_real_signal and has_financial and has_technical:
        return "ready_full"
    if has_real_signal and has_real_score:
        return "signal_ready"
    if has_real_score:
        return "score_ready"
    if has_financial and has_technical:
        return "mixed_partial"
    if has_financial:
        return "financial_ready"
    if has_technical:
        return "technical_ready"
    if has_demo_score:
        return "demo_only"
    return "price_only"


def _blocking_reasons(
    *,
    has_price: bool,
    has_financial: bool,
    has_technical: bool,
    has_real_score: bool,
    has_real_signal: bool,
    price_count: int,
) -> list[str]:
    reasons: list[str] = []
    if not has_price:
        reasons.append("行情数据缺失")
    elif price_count < 30:
        reasons.append("行情记录不足30条")
    if not has_financial:
        reasons.append("财务数据未刷新")
    if not has_technical:
        reasons.append("技术指标未计算")
    if not has_real_score:
        reasons.append("真实评分未生成")
    if has_real_score and not has_real_signal:
        reasons.append("真实信号未生成")
    return reasons


def _stock_id_from_code(db: Session, stock_code: str) -> int | None:
    row = db.query(Stock.id).filter(Stock.symbol == stock_code).first()
    return row[0] if row else None


def _bulk_price_stats(db: Session, stock_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not stock_ids:
        return {}
    rows = (
        db.query(
            DailyPrice.stock_id,
            func.count(DailyPrice.id),
            func.max(DailyPrice.trade_date),
        )
        .filter(DailyPrice.stock_id.in_(stock_ids))
        .group_by(DailyPrice.stock_id)
        .all()
    )
    return {
        stock_id: {"price_count": int(count or 0), "latest_price_date": latest}
        for stock_id, count, latest in rows
    }


def _bulk_financial_stats(db: Session, stock_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not stock_ids:
        return {}
    rows = db.query(FinancialMetric).filter(FinancialMetric.stock_id.in_(stock_ids)).all()
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        payload = result.setdefault(
            row.stock_id,
            {
                "financial_count": 0,
                "latest_financial_period": None,
                "latest_financial_date": None,
                "_sort_key": (date.min, 0),
            },
        )
        payload["financial_count"] += 1
        sort_date = row.report_date or date.min
        sort_key = (sort_date, row.id or 0)
        if sort_key >= payload["_sort_key"]:
            payload["_sort_key"] = sort_key
            payload["latest_financial_period"] = row.report_period
            payload["latest_financial_date"] = row.report_date
    for payload in result.values():
        payload.pop("_sort_key", None)
    return result


def _bulk_technical_stats(db: Session, stock_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not stock_ids:
        return {}
    rows = (
        db.query(
            TechnicalIndicator.stock_id,
            func.count(TechnicalIndicator.id),
            func.max(TechnicalIndicator.trade_date),
        )
        .filter(TechnicalIndicator.stock_id.in_(stock_ids))
        .group_by(TechnicalIndicator.stock_id)
        .all()
    )
    return {
        stock_id: {"technical_count": int(count or 0), "latest_technical_date": latest}
        for stock_id, count, latest in rows
    }


def _bulk_real_score_stats(db: Session, stock_ids: list[int]) -> dict[int, date | None]:
    if not stock_ids:
        return {}
    rows = (
        db.query(StockScore.stock_id, func.max(StockScore.score_date))
        .filter(
            StockScore.stock_id.in_(stock_ids),
            StockScore.score_source == REAL_SCORE_SOURCE,
        )
        .group_by(StockScore.stock_id)
        .all()
    )
    return {stock_id: latest for stock_id, latest in rows}


def _bulk_real_signal_stats(db: Session, stock_ids: list[int]) -> dict[int, date | None]:
    if not stock_ids:
        return {}
    rows = (
        db.query(TradeSignal.stock_id, func.max(TradeSignal.signal_date))
        .filter(
            TradeSignal.stock_id.in_(stock_ids),
            TradeSignal.signal_source == REAL_SIGNAL_SOURCE,
        )
        .group_by(TradeSignal.stock_id)
        .all()
    )
    return {stock_id: latest for stock_id, latest in rows}


def _bulk_demo_score_flags(db: Session, stock_ids: list[int]) -> set[int]:
    if not stock_ids:
        return set()
    rows = (
        db.query(StockScore.stock_id)
        .filter(
            StockScore.stock_id.in_(stock_ids),
            StockScore.score_source == DEMO_SCORE_SOURCE,
        )
        .distinct()
        .all()
    )
    return {row[0] for row in rows}


def build_coverage_record(
    stock_code: str,
    *,
    price_count: int = 0,
    latest_price_date: date | None = None,
    latest_financial_period: str | None = None,
    latest_technical_date: date | None = None,
    latest_real_score_date: date | None = None,
    latest_real_signal_date: date | None = None,
    has_demo_score: bool = False,
) -> dict[str, Any]:
    has_price = price_count > 0
    has_financial = latest_financial_period is not None
    has_technical = latest_technical_date is not None
    has_real_score = latest_real_score_date is not None
    has_real_signal = latest_real_signal_date is not None
    coverage_level = _resolve_coverage_level(
        has_price=has_price,
        has_financial=has_financial,
        has_technical=has_technical,
        has_real_score=has_real_score,
        has_real_signal=has_real_signal,
        has_demo_score=has_demo_score,
    )
    blocking = _blocking_reasons(
        has_price=has_price,
        has_financial=has_financial,
        has_technical=has_technical,
        has_real_score=has_real_score,
        has_real_signal=has_real_signal,
        price_count=price_count,
    )
    return {
        "stock_code": stock_code,
        "has_price": has_price,
        "price_count": price_count,
        "latest_price_date": str(latest_price_date) if latest_price_date else None,
        "has_financial": has_financial,
        "latest_financial_period": latest_financial_period,
        "has_technical": has_technical,
        "latest_technical_date": str(latest_technical_date) if latest_technical_date else None,
        "has_real_score": has_real_score,
        "latest_real_score_date": str(latest_real_score_date) if latest_real_score_date else None,
        "has_real_signal": has_real_signal,
        "latest_real_signal_date": str(latest_real_signal_date) if latest_real_signal_date else None,
        "coverage_level": coverage_level,
        "readiness_label": READINESS_LABELS.get(coverage_level, coverage_level),
        "blocking_reasons": blocking,
    }


def get_stock_data_coverage(db: Session, stock_code: str) -> dict[str, Any]:
    stock = db.query(Stock).filter(Stock.symbol == stock_code).first()
    if not stock:
        return build_coverage_record(stock_code)

    bulk = get_bulk_data_coverage(db, [stock_code])
    return bulk.get(stock_code) or build_coverage_record(stock_code)


def get_bulk_data_coverage(db: Session, stock_codes: list[str]) -> dict[str, dict[str, Any]]:
    if not stock_codes:
        return {}
    stocks = db.query(Stock.id, Stock.symbol).filter(Stock.symbol.in_(stock_codes)).all()
    id_to_code = {stock_id: symbol for stock_id, symbol in stocks}
    stock_ids = list(id_to_code.keys())

    price_stats = _bulk_price_stats(db, stock_ids)
    fin_stats = _bulk_financial_stats(db, stock_ids)
    tech_stats = _bulk_technical_stats(db, stock_ids)
    real_scores = _bulk_real_score_stats(db, stock_ids)
    real_signals = _bulk_real_signal_stats(db, stock_ids)
    demo_flags = _bulk_demo_score_flags(db, stock_ids)

    result: dict[str, dict[str, Any]] = {}
    for stock_id, symbol in id_to_code.items():
        price = price_stats.get(stock_id, {})
        fin = fin_stats.get(stock_id, {})
        tech = tech_stats.get(stock_id, {})
        result[symbol] = build_coverage_record(
            symbol,
            price_count=int(price.get("price_count") or 0),
            latest_price_date=price.get("latest_price_date"),
            latest_financial_period=fin.get("latest_financial_period"),
            latest_technical_date=tech.get("latest_technical_date"),
            latest_real_score_date=real_scores.get(stock_id),
            latest_real_signal_date=real_signals.get(stock_id),
            has_demo_score=stock_id in demo_flags,
        )

    for code in stock_codes:
        result.setdefault(code, build_coverage_record(code))
    return result


def summarize_market_data_coverage(db: Session) -> dict[str, Any]:
    stocks_total = db.query(Stock).count()
    prices_total = db.query(DailyPrice).count()
    price_stocks = db.query(func.count(func.distinct(DailyPrice.stock_id))).scalar() or 0
    latest_price_date = db.query(func.max(DailyPrice.trade_date)).scalar()

    fm_total = db.query(FinancialMetric).count()
    fm_stocks = db.query(func.count(func.distinct(FinancialMetric.stock_id))).scalar() or 0
    latest_financial_row = (
        db.query(FinancialMetric)
        .filter(FinancialMetric.report_date.isnot(None))
        .order_by(FinancialMetric.report_date.desc(), FinancialMetric.id.desc())
        .first()
    )
    latest_financial_period = latest_financial_row.report_period if latest_financial_row else None
    latest_financial_date = latest_financial_row.report_date if latest_financial_row else None

    ti_total = db.query(TechnicalIndicator).count()
    ti_stocks = db.query(func.count(func.distinct(TechnicalIndicator.stock_id))).scalar() or 0
    latest_technical_date = db.query(func.max(TechnicalIndicator.trade_date)).scalar()

    real_score_count = (
        db.query(StockScore).filter(StockScore.score_source == REAL_SCORE_SOURCE).count()
    )
    demo_score_count = (
        db.query(StockScore).filter(StockScore.score_source == DEMO_SCORE_SOURCE).count()
    )
    real_signal_count = (
        db.query(TradeSignal).filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE).count()
    )
    demo_signal_count = (
        db.query(TradeSignal).filter(TradeSignal.signal_source == DEMO_SIGNAL_SOURCE).count()
    )
    pe_non_null_count = db.query(DailyPrice).filter(DailyPrice.pe.isnot(None)).count()
    pb_non_null_count = db.query(DailyPrice).filter(DailyPrice.pb.isnot(None)).count()
    valuation_zero_real_scores = (
        db.query(StockScore)
        .filter(StockScore.score_source == REAL_SCORE_SOURCE, StockScore.valuation_score == 0)
        .count()
    )
    latest_real_score_date = (
        db.query(func.max(StockScore.score_date))
        .filter(StockScore.score_source == REAL_SCORE_SOURCE)
        .scalar()
    )
    latest_real_signal_date = (
        db.query(func.max(TradeSignal.signal_date))
        .filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE)
        .scalar()
    )

    scoreable = 0
    not_scoreable_reasons: Counter[str] = Counter()
    active_stocks = db.query(Stock.id, Stock.symbol).filter(Stock.status == "ACTIVE").limit(5000).all()
    if active_stocks:
        ids = [item[0] for item in active_stocks]
        price_stats = _bulk_price_stats(db, ids)
        fin_stats = _bulk_financial_stats(db, ids)
        tech_stats = _bulk_technical_stats(db, ids)
        for stock_id, _symbol in active_stocks:
            price_count = int(price_stats.get(stock_id, {}).get("price_count") or 0)
            has_fin = stock_id in fin_stats
            has_tech = stock_id in tech_stats
            if price_count >= 30 and has_fin and has_tech:
                scoreable += 1
            else:
                if price_count < 30:
                    not_scoreable_reasons["insufficient_price"] += 1
                if not has_fin:
                    not_scoreable_reasons["no_financial"] += 1
                if not has_tech:
                    not_scoreable_reasons["no_technical"] += 1

    core_stock_coverage = get_bulk_data_coverage(db, CORE_STOCKS)

    return {
        "stocks_total": stocks_total,
        "daily_prices_total": prices_total,
        "daily_prices_stocks": price_stocks,
        "latest_price_date": str(latest_price_date) if latest_price_date else None,
        "financial_metrics_total": fm_total,
        "financial_metrics_stocks": fm_stocks,
        "latest_financial_period": latest_financial_period,
        "latest_financial_date": str(latest_financial_date) if latest_financial_date else None,
        "technical_indicators_total": ti_total,
        "technical_indicators_stocks": ti_stocks,
        "latest_technical_date": str(latest_technical_date) if latest_technical_date else None,
        "real_calculated_scores": real_score_count,
        "quick_seed_demo_scores": demo_score_count,
        "real_calculated_signals": real_signal_count,
        "quick_seed_demo_signals": demo_signal_count,
        "pe_non_null_count": pe_non_null_count,
        "pb_non_null_count": pb_non_null_count,
        "valuation_zero_real_scores": valuation_zero_real_scores,
        "latest_real_score_date": str(latest_real_score_date) if latest_real_score_date else None,
        "latest_real_signal_date": str(latest_real_signal_date) if latest_real_signal_date else None,
        "scoreable_stock_count": scoreable,
        "not_scoreable_reason_distribution": dict(not_scoreable_reasons),
        "core_stock_coverage": core_stock_coverage,
    }


def _blocking_reasons(
    *,
    has_price: bool,
    has_financial: bool,
    has_technical: bool,
    has_real_score: bool,
    has_real_signal: bool,
    has_valuation: bool,
    price_count: int,
) -> list[str]:
    reasons: list[str] = []
    if not has_price:
        reasons.append("行情数据缺失")
    elif price_count < 30:
        reasons.append("行情记录不足30条")
    if not has_financial:
        reasons.append("财务数据未刷新")
    if has_price and not has_valuation:
        reasons.append("PE/PB 估值数据缺失")
    if not has_technical:
        reasons.append("技术指标未计算")
    if not has_real_score:
        reasons.append("真实评分未生成")
    if has_real_score and not has_real_signal:
        reasons.append("真实信号未生成")
    return reasons


def build_coverage_record(
    stock_code: str,
    *,
    price_count: int = 0,
    latest_price_date: date | None = None,
    latest_pe: float | None = None,
    latest_pb: float | None = None,
    latest_financial_period: str | None = None,
    latest_technical_date: date | None = None,
    latest_real_score_date: date | None = None,
    latest_real_signal_date: date | None = None,
    has_demo_score: bool = False,
) -> dict[str, Any]:
    has_price = price_count > 0
    has_valuation = latest_pe is not None or latest_pb is not None
    has_financial = latest_financial_period is not None
    has_technical = latest_technical_date is not None
    has_real_score = latest_real_score_date is not None
    has_real_signal = latest_real_signal_date is not None
    coverage_level = _resolve_coverage_level(
        has_price=has_price,
        has_financial=has_financial,
        has_technical=has_technical,
        has_real_score=has_real_score,
        has_real_signal=has_real_signal,
        has_demo_score=has_demo_score,
    )
    blocking = _blocking_reasons(
        has_price=has_price,
        has_financial=has_financial,
        has_technical=has_technical,
        has_real_score=has_real_score,
        has_real_signal=has_real_signal,
        has_valuation=has_valuation,
        price_count=price_count,
    )
    return {
        "stock_code": stock_code,
        "has_price": has_price,
        "price_count": price_count,
        "latest_price_date": str(latest_price_date) if latest_price_date else None,
        "latest_pe": latest_pe,
        "latest_pb": latest_pb,
        "has_valuation": has_valuation,
        "has_financial": has_financial,
        "latest_financial_period": latest_financial_period,
        "has_technical": has_technical,
        "latest_technical_date": str(latest_technical_date) if latest_technical_date else None,
        "has_real_score": has_real_score,
        "latest_real_score_date": str(latest_real_score_date) if latest_real_score_date else None,
        "has_real_signal": has_real_signal,
        "latest_real_signal_date": str(latest_real_signal_date) if latest_real_signal_date else None,
        "coverage_level": coverage_level,
        "readiness_label": READINESS_LABELS.get(coverage_level, coverage_level),
        "blocking_reasons": blocking,
    }


def get_bulk_data_coverage(db: Session, stock_codes: list[str]) -> dict[str, dict[str, Any]]:
    if not stock_codes:
        return {}
    stocks = db.query(Stock.id, Stock.symbol).filter(Stock.symbol.in_(stock_codes)).all()
    id_to_code = {stock_id: symbol for stock_id, symbol in stocks}
    stock_ids = list(id_to_code.keys())

    price_stats = _bulk_price_stats(db, stock_ids)
    latest_price_subq = (
        db.query(DailyPrice.stock_id, func.max(DailyPrice.trade_date).label("max_date"))
        .filter(DailyPrice.stock_id.in_(stock_ids))
        .group_by(DailyPrice.stock_id)
        .subquery()
    )
    latest_price_rows = (
        db.query(DailyPrice)
        .join(
            latest_price_subq,
            (DailyPrice.stock_id == latest_price_subq.c.stock_id)
            & (DailyPrice.trade_date == latest_price_subq.c.max_date),
        )
        .all()
    )
    latest_price_map = {row.stock_id: row for row in latest_price_rows}
    fin_stats = _bulk_financial_stats(db, stock_ids)
    tech_stats = _bulk_technical_stats(db, stock_ids)
    real_scores = _bulk_real_score_stats(db, stock_ids)
    real_signals = _bulk_real_signal_stats(db, stock_ids)
    demo_flags = _bulk_demo_score_flags(db, stock_ids)

    result: dict[str, dict[str, Any]] = {}
    for stock_id, symbol in id_to_code.items():
        price = price_stats.get(stock_id, {})
        latest_price = latest_price_map.get(stock_id)
        fin = fin_stats.get(stock_id, {})
        tech = tech_stats.get(stock_id, {})
        result[symbol] = build_coverage_record(
            symbol,
            price_count=int(price.get("price_count") or 0),
            latest_price_date=price.get("latest_price_date"),
            latest_pe=getattr(latest_price, "pe", None),
            latest_pb=getattr(latest_price, "pb", None),
            latest_financial_period=fin.get("latest_financial_period"),
            latest_technical_date=tech.get("latest_technical_date"),
            latest_real_score_date=real_scores.get(stock_id),
            latest_real_signal_date=real_signals.get(stock_id),
            has_demo_score=stock_id in demo_flags,
        )

    for code in stock_codes:
        result.setdefault(code, build_coverage_record(code))
    return result
