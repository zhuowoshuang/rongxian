"""Diagnostic helpers for explaining real score outcomes without changing weights."""

from __future__ import annotations

from collections import Counter
from datetime import date
from statistics import mean
from typing import Any

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.technical_indicator import TechnicalIndicator
from app.models.trade_signal import TradeSignal
from app.services.data_coverage import CORE_STOCKS, get_bulk_data_coverage, get_stock_data_coverage
from app.services.data_credibility import DEMO_SCORE_SOURCE, REAL_SCORE_SOURCE, REAL_SIGNAL_SOURCE
from app.services.scoring import _latest_financial_for_stock, _previous_financial_for_stock

DISPLAY_TIER_LABELS = {
    "formal_real": "正式真实",
    "real_observation": "真实观察",
    "data_quality_limited": "数据质量受限",
    "data_insufficient": "数据不足",
    "demo_only": "仅演示",
}

SIGNAL_DISPLAY_BUCKETS = {
    "BUY": "HIGH_ATTENTION",
    "ADD": "ENHANCED_ATTENTION",
    "WATCH": "WATCH",
    "REDUCE": "RISK_RISING",
    "SELL": "AVOID_OBSERVATION",
    "NO_SIGNAL": "NO_SIGNAL",
}


def _to_str(value: Any) -> str | None:
    return str(value) if value is not None else None


def _safe_mean(values: list[float | int | None]) -> float | None:
    filtered = [float(value) for value in values if value is not None]
    if not filtered:
        return None
    return round(mean(filtered), 2)


def _latest_real_signal_map(db: Session, score_date: date | None = None) -> dict[int, TradeSignal]:
    conditions = [TradeSignal.signal_source == REAL_SIGNAL_SOURCE]
    if score_date is not None:
        conditions.append(TradeSignal.signal_date <= score_date)

    latest_signal_subquery = (
        db.query(
            TradeSignal.stock_id.label("stock_id"),
            func.max(TradeSignal.signal_date).label("latest_signal_date"),
        )
        .filter(*conditions)
        .group_by(TradeSignal.stock_id)
        .subquery()
    )

    rows = (
        db.query(TradeSignal)
        .join(
            latest_signal_subquery,
            and_(
                TradeSignal.stock_id == latest_signal_subquery.c.stock_id,
                TradeSignal.signal_date == latest_signal_subquery.c.latest_signal_date,
            ),
        )
        .all()
    )
    return {row.stock_id: row for row in rows}


def _latest_price_map(db: Session, stock_ids: list[int], score_date: date | None = None) -> dict[int, DailyPrice]:
    if not stock_ids:
        return {}
    conditions = [DailyPrice.stock_id.in_(stock_ids)]
    if score_date is not None:
        conditions.append(DailyPrice.trade_date <= score_date)

    latest_price_subquery = (
        db.query(
            DailyPrice.stock_id.label("stock_id"),
            func.max(DailyPrice.trade_date).label("latest_trade_date"),
        )
        .filter(*conditions)
        .group_by(DailyPrice.stock_id)
        .subquery()
    )

    rows = (
        db.query(DailyPrice)
        .join(
            latest_price_subquery,
            and_(
                DailyPrice.stock_id == latest_price_subquery.c.stock_id,
                DailyPrice.trade_date == latest_price_subquery.c.latest_trade_date,
            ),
        )
        .all()
    )
    return {row.stock_id: row for row in rows}


def _latest_technical_map(db: Session, stock_ids: list[int], score_date: date | None = None) -> dict[int, TechnicalIndicator]:
    if not stock_ids:
        return {}
    conditions = [TechnicalIndicator.stock_id.in_(stock_ids)]
    if score_date is not None:
        conditions.append(TechnicalIndicator.trade_date <= score_date)

    latest_tech_subquery = (
        db.query(
            TechnicalIndicator.stock_id.label("stock_id"),
            func.max(TechnicalIndicator.trade_date).label("latest_trade_date"),
        )
        .filter(*conditions)
        .group_by(TechnicalIndicator.stock_id)
        .subquery()
    )

    rows = (
        db.query(TechnicalIndicator)
        .join(
            latest_tech_subquery,
            and_(
                TechnicalIndicator.stock_id == latest_tech_subquery.c.stock_id,
                TechnicalIndicator.trade_date == latest_tech_subquery.c.latest_trade_date,
            ),
        )
        .all()
    )
    return {row.stock_id: row for row in rows}


def _latest_financial_map(db: Session, stock_ids: list[int], score_date: date | None = None) -> dict[int, FinancialMetric]:
    result: dict[int, FinancialMetric] = {}
    for stock_id in stock_ids:
        item = _latest_financial_for_stock(db, stock_id, score_date=score_date)
        if item is not None:
            result[stock_id] = item
    return result


def _previous_financial_map(db: Session, latest_financials: dict[int, FinancialMetric]) -> dict[int, FinancialMetric]:
    result: dict[int, FinancialMetric] = {}
    for stock_id, current in latest_financials.items():
        item = _previous_financial_for_stock(db, stock_id, current)
        if item is not None:
            result[stock_id] = item
    return result


def _score_rows(db: Session, score_date: date | None = None) -> list[StockScore]:
    conditions = [StockScore.score_source.in_([REAL_SCORE_SOURCE, DEMO_SCORE_SOURCE])]
    if score_date is not None:
        conditions.append(StockScore.score_date == score_date)

    latest_score_subquery = (
        db.query(
            StockScore.stock_id.label("stock_id"),
            func.max(StockScore.score_date).label("latest_score_date"),
        )
        .filter(*conditions)
        .group_by(StockScore.stock_id)
        .subquery()
    )

    query = (
        db.query(StockScore)
        .join(
            latest_score_subquery,
            and_(
                StockScore.stock_id == latest_score_subquery.c.stock_id,
                StockScore.score_date == latest_score_subquery.c.latest_score_date,
            ),
        )
    )
    return query.all()


def _blocking_reasons_for_item(
    stock: Stock,
    coverage: dict[str, Any],
    latest_price: DailyPrice | None,
    latest_financial: FinancialMetric | None,
    tech: TechnicalIndicator | None,
) -> list[str]:
    reasons = list(coverage.get("blocking_reasons") or [])
    if latest_price is None:
        return list(dict.fromkeys(reasons))
    if latest_price.pe is None and latest_price.pb is None:
        reasons.append("估值字段缺失")
    elif latest_price.pe is None or latest_price.pb is None:
        reasons.append("估值字段不完整")
    if not stock.industry:
        reasons.append("行业标签缺失")
    if latest_financial is None:
        reasons.append("缺少最新财务快照")
    if tech is None:
        reasons.append("缺少最新技术快照")
    if latest_price.market_cap is None:
        reasons.append("市值字段缺失")
    return list(dict.fromkeys(reasons))


def _primary_reason(
    score: StockScore,
    latest_price: DailyPrice | None,
    blocking_reasons: list[str],
) -> str:
    if blocking_reasons:
        prioritized = [
            "缺少最新财务快照",
            "缺少最新技术快照",
            "估值字段缺失",
            "估值字段不完整",
            "行情数据缺失",
            "行情记录不足30条",
        ]
        for reason in prioritized:
            if reason in blocking_reasons:
                return reason
        return blocking_reasons[0]

    dimensions = {
        "质量评分偏低": score.quality_score if score.quality_score is not None else 999,
        "估值性价比不足": score.valuation_score if score.valuation_score is not None else 999,
        "成长动能偏弱": score.growth_score if score.growth_score is not None else 999,
        "趋势评分偏低": score.trend_score if score.trend_score is not None else 999,
        "风险承压": score.risk_score if score.risk_score is not None else 999,
    }

    if latest_price is not None and latest_price.pe is not None and latest_price.pe < 0:
        return "处于亏损状态"
    if latest_price is not None and latest_price.pe is not None and latest_price.pe >= 60:
        return "估值偏高"

    return min(dimensions.items(), key=lambda item: item[1])[0]


def classify_display_tier(
    *,
    score_source: str | None,
    signal_type: str | None,
    total_score: float | None,
    blocking_reasons: list[str],
    coverage_level: str | None,
) -> str:
    if score_source == DEMO_SCORE_SOURCE:
        return "demo_only"

    if coverage_level in {"no_data", "price_only"} or total_score is None:
        return "data_insufficient"

    # Only block on critical missing data, not on PE/PB/market_cap/industry gaps
    critical_blocking = [
        r for r in blocking_reasons
        if r in ("缺少最新财务快照", "缺少最新技术快照", "行情数据缺失", "行情记录不足30条")
    ]
    if critical_blocking:
        return "data_quality_limited"

    if signal_type in {"REDUCE", "SELL", "DATA_INSUFFICIENT"} or (total_score is not None and total_score < 55):
        return "real_observation"

    return "formal_real"


def _build_item(
    *,
    stock: Stock,
    score: StockScore,
    signal: TradeSignal | None,
    latest_price: DailyPrice | None,
    latest_financial: FinancialMetric | None,
    previous_financial: FinancialMetric | None,
    tech: TechnicalIndicator | None,
    coverage: dict[str, Any],
) -> dict[str, Any]:
    blocking_reasons = _blocking_reasons_for_item(stock, coverage, latest_price, latest_financial, tech)
    display_tier = classify_display_tier(
        score_source=score.score_source,
        signal_type=getattr(signal, "signal_type", None),
        total_score=score.total_score,
        blocking_reasons=blocking_reasons,
        coverage_level=coverage.get("coverage_level"),
    )
    primary_low_score_reason = _primary_reason(score, latest_price, blocking_reasons)

    return {
        "stock_code": stock.symbol,
        "stock_name": stock.name,
        "market": stock.market,
        "industry": stock.industry,
        "score_date": _to_str(score.score_date),
        "signal_date": _to_str(getattr(signal, "signal_date", None)),
        "signal_type": getattr(signal, "signal_type", None),
        "signal_strength": getattr(signal, "signal_strength", None),
        "signal_source": getattr(signal, "signal_source", None),
        "score_source": score.score_source,
        "total_score": score.total_score,
        "quality_score": score.quality_score,
        "valuation_score": score.valuation_score,
        "growth_score": score.growth_score,
        "trend_score": score.trend_score,
        "risk_score": score.risk_score,
        "latest_close": getattr(latest_price, "close", None),
        "latest_trade_date": _to_str(getattr(latest_price, "trade_date", None)),
        "market_cap": getattr(latest_price, "market_cap", None),
        "pe": getattr(latest_price, "pe", None),
        "pb": getattr(latest_price, "pb", None),
        "dividend_yield": getattr(latest_price, "dividend_yield", None),
        "turnover_rate": getattr(latest_price, "turnover_rate", None),
        "report_period": getattr(latest_financial, "report_period", None),
        "report_date": _to_str(getattr(latest_financial, "report_date", None)),
        "revenue_yoy": getattr(latest_financial, "revenue_yoy", None),
        "net_profit_yoy": getattr(latest_financial, "net_profit_yoy", None),
        "roe": getattr(latest_financial, "roe", None),
        "gross_margin": getattr(latest_financial, "gross_margin", None),
        "debt_ratio": getattr(latest_financial, "debt_ratio", None),
        "operating_cashflow": getattr(latest_financial, "operating_cashflow", None),
        "free_cashflow": getattr(latest_financial, "free_cashflow", None),
        "eps": getattr(latest_financial, "eps", None),
        "book_value_per_share": getattr(latest_financial, "book_value_per_share", None),
        "previous_roe": getattr(previous_financial, "roe", None),
        "ma5": getattr(tech, "ma5", None),
        "ma10": getattr(tech, "ma10", None),
        "ma20": getattr(tech, "ma20", None),
        "ma60": getattr(tech, "ma60", None),
        "ma120": getattr(tech, "ma120", None),
        "macd": getattr(tech, "macd", None),
        "macd_signal": getattr(tech, "macd_signal", None),
        "macd_hist": getattr(tech, "macd_hist", None),
        "rsi14": getattr(tech, "rsi14", None),
        "volume_ratio_5_20": getattr(tech, "volume_ratio_5_20", None),
        "weekly_volatility": getattr(tech, "weekly_volatility_candidate", None),
        "monthly_volatility": getattr(tech, "monthly_volatility_candidate", None),
        "coverage_level": coverage.get("coverage_level"),
        "readiness_label": coverage.get("readiness_label"),
        "display_tier": display_tier,
        "display_tier_label": DISPLAY_TIER_LABELS.get(display_tier, display_tier),
        "data_quality_level": display_tier,
        "primary_low_score_reason": primary_low_score_reason,
        "blocking_reasons": blocking_reasons,
    }


def diagnose_real_scores(db: Session, score_date: date | None = None) -> dict[str, Any]:
    score_rows = _score_rows(db, score_date=score_date)
    if not score_rows:
        return {
            "summary": {
                "score_date": _to_str(score_date),
                "included_count": 0,
                "real_count": 0,
                "demo_count": 0,
                "message": "当前没有可诊断的评分样本。",
            },
            "items": [],
            "low_score_reasons": [],
            "display_tier_distribution": {},
            "signal_distribution": {},
        }

    stock_ids = [row.stock_id for row in score_rows]
    stocks = db.query(Stock).filter(Stock.id.in_(stock_ids)).all()
    stock_map = {stock.id: stock for stock in stocks}
    price_map = _latest_price_map(db, stock_ids, score_date=score_date)
    financial_map = _latest_financial_map(db, stock_ids, score_date=score_date)
    previous_financial_map = _previous_financial_map(db, financial_map)
    technical_map = _latest_technical_map(db, stock_ids, score_date=score_date)
    signal_map = _latest_real_signal_map(db, score_date=score_date)
    coverage_map = get_bulk_data_coverage(db, [stock.symbol for stock in stocks])

    items: list[dict[str, Any]] = []
    for score in score_rows:
        stock = stock_map.get(score.stock_id)
        if stock is None:
            continue
        items.append(
            _build_item(
                stock=stock,
                score=score,
                signal=signal_map.get(stock.id),
                latest_price=price_map.get(stock.id),
                latest_financial=financial_map.get(stock.id),
                previous_financial=previous_financial_map.get(stock.id),
                tech=technical_map.get(stock.id),
                coverage=coverage_map.get(stock.symbol, {}),
            )
        )

    real_items = [item for item in items if item.get("score_source") == REAL_SCORE_SOURCE]
    demo_items = [item for item in items if item.get("score_source") == DEMO_SCORE_SOURCE]
    tier_counter = Counter(item["display_tier"] for item in items)
    reason_counter = Counter(item["primary_low_score_reason"] for item in real_items)
    signal_counter = Counter(
        SIGNAL_DISPLAY_BUCKETS.get(item.get("signal_type") or "NO_SIGNAL", item.get("signal_type") or "NO_SIGNAL")
        for item in real_items
    )
    core_items = [item for item in real_items if item.get("stock_code") in CORE_STOCKS]
    core_ready_full_count = sum(1 for item in core_items if item.get("coverage_level") == "ready_full")

    averages = {
        "total_score": _safe_mean([item.get("total_score") for item in real_items]),
        "quality_score": _safe_mean([item.get("quality_score") for item in real_items]),
        "valuation_score": _safe_mean([item.get("valuation_score") for item in real_items]),
        "growth_score": _safe_mean([item.get("growth_score") for item in real_items]),
        "trend_score": _safe_mean([item.get("trend_score") for item in real_items]),
        "risk_score": _safe_mean([item.get("risk_score") for item in real_items]),
    }

    formal_real_count = sum(1 for item in real_items if item.get("display_tier") == "formal_real")
    real_observation_count = sum(1 for item in real_items if item.get("display_tier") == "real_observation")
    data_quality_limited_count = sum(1 for item in real_items if item.get("display_tier") == "data_quality_limited")
    data_insufficient_count = sum(1 for item in real_items if item.get("display_tier") == "data_insufficient")

    if formal_real_count > 0:
        launch_data_status = "ready_for_internal"
        summary_message = "当前已有可正式展示的真实研究样本，但仍需结合研究解释与风险提示阅读。"
    elif real_observation_count > 0:
        launch_data_status = "limited_real_data"
        summary_message = "当前真实样本已形成研究观察结果，但暂未形成正式高关注信号，整体仍偏谨慎。"
    elif data_quality_limited_count > 0:
        launch_data_status = "data_quality_limited"
        summary_message = "真实评分链路已接通，但多数样本仍受估值、行业或覆盖字段限制，当前以数据质量诊断与研究观察为主。"
    elif demo_items and not real_items:
        launch_data_status = "demo_only"
        summary_message = "当前仍以演示评分为主，真实评分链路尚未形成稳定可展示样本。"
    else:
        launch_data_status = "not_ready"
        summary_message = "当前真实评分样本不足，系统仅能展示数据状态与待补齐项。"

    return {
        "summary": {
            "score_date": _to_str(score_date or max((row.score_date for row in score_rows), default=None)),
            "included_count": len(items),
            "real_count": len(real_items),
            "real_score_count": len(real_items),
            "demo_count": len(demo_items),
            "demo_score_count": len(demo_items),
            "formal_real_count": formal_real_count,
            "real_observation_count": real_observation_count,
            "data_quality_limited_count": data_quality_limited_count,
            "data_insufficient_count": data_insufficient_count,
            "core_total": len(CORE_STOCKS),
            "core_ready_full_count": core_ready_full_count,
            "launch_data_status": launch_data_status,
            "avg_total_score": averages["total_score"],
            "avg_quality_score": averages["quality_score"],
            "avg_valuation_score": averages["valuation_score"],
            "avg_growth_score": averages["growth_score"],
            "avg_trend_score": averages["trend_score"],
            "avg_risk_score": averages["risk_score"],
            "averages": averages,
            "message": summary_message,
        },
        "display_tier_distribution": dict(tier_counter),
        "signal_distribution": dict(signal_counter),
        "low_score_reasons": [{"reason": reason, "count": count} for reason, count in reason_counter.most_common(8)],
        "items": sorted(
            items,
            key=lambda item: (
                0 if item.get("score_source") == REAL_SCORE_SOURCE else 1,
                item.get("total_score") if item.get("total_score") is not None else -999,
            ),
            reverse=True,
        ),
    }


def diagnose_single_stock_score(db: Session, stock_code: str, score_date: date | None = None) -> dict[str, Any] | None:
    stock = db.query(Stock).filter(Stock.symbol == stock_code).first()
    if stock is None:
        return None

    conditions = [StockScore.stock_id == stock.id]
    if score_date is not None:
        conditions.append(StockScore.score_date == score_date)

    score = (
        db.query(StockScore)
        .filter(*conditions)
        .order_by(StockScore.score_date.desc())
        .first()
    )
    if score is None:
        return {
            "stock_code": stock.symbol,
            "stock_name": stock.name,
            "display_tier": "data_insufficient",
            "display_tier_label": DISPLAY_TIER_LABELS["data_insufficient"],
            "data_quality_level": "data_insufficient",
            "primary_low_score_reason": "尚未生成评分",
            "blocking_reasons": ["尚未生成评分"],
        }

    latest_price = _latest_price_map(db, [stock.id], score_date=score_date).get(stock.id)
    latest_financial = _latest_financial_for_stock(db, stock.id, score_date=score_date)
    previous_financial = _previous_financial_for_stock(db, stock.id, latest_financial)
    tech = _latest_technical_map(db, [stock.id], score_date=score_date).get(stock.id)
    signal = _latest_real_signal_map(db, score_date=score_date).get(stock.id)
    coverage = get_stock_data_coverage(db, stock.symbol)

    return _build_item(
        stock=stock,
        score=score,
        signal=signal,
        latest_price=latest_price,
        latest_financial=latest_financial,
        previous_financial=previous_financial,
        tech=tech,
        coverage=coverage,
    )
