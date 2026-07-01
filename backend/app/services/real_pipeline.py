"""Real data pipeline: financial refresh, technical indicators, scores, and signals."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import logging
import math
import os
import statistics
import time
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.data_providers import get_provider
from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.refresh_job_run import RefreshJobRun
from app.models.report import BacktestTask, Report
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.technical_indicator import TechnicalIndicator
from app.models.trade_signal import TradeSignal
from app.models.watchlist import WatchlistItem
from app.services.data_credibility import (
    DEMO_SCORE_SOURCE,
    DEMO_SIGNAL_SOURCE,
    REAL_SCORE_SOURCE,
    REAL_SIGNAL_SOURCE,
    UNKNOWN_SCORE_SOURCE,
    VALUATION_MISSING,
    VALUATION_PARTIAL,
    VALUATION_READY,
    valuation_readiness,
)
from app.services.financial_periods import normalize_report_date, normalize_report_period_to_date
from app.services.pipeline_lock import pipeline_lock
from app.services.scoring import (
    _compute_industry_stats,
    _latest_financial_for_stock,
    _previous_financial_for_stock,
    calculate_growth_score,
    calculate_quality_score,
    calculate_risk_score,
    calculate_trend_score,
    calculate_valuation_score,
    get_rating,
)
from app.services.signal import generate_signal_for_stock

logger = logging.getLogger(__name__)

DAILY_FINANCIAL_LIMIT = int(os.environ.get("DAILY_FINANCIAL_LIMIT", "300"))
DAILY_TECHNICAL_LIMIT = int(os.environ.get("DAILY_TECHNICAL_LIMIT", "500"))
REAL_PIPELINE_FINANCIAL_WORKERS = int(os.environ.get("REAL_PIPELINE_FINANCIAL_WORKERS", "3"))

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


@dataclass
class SampleStock:
    stock_id: int
    symbol: str
    name: str
    market: str
    industry: str | None
    price_count: int
    latest_trade_date: date | None
    selection_reason: str | None = None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def _normalize_trade_date(value: Any) -> date | None:
    return normalize_report_date(value)


def _normalize_report_date(report_period: str | None) -> date | None:
    return normalize_report_period_to_date(report_period)


def _ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    multiplier = 2 / (period + 1)
    series = [float(values[0])]
    for current in values[1:]:
        series.append(float(current) * multiplier + series[-1] * (1 - multiplier))
    return series


def _rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [delta if delta > 0 else 0 for delta in deltas]
    losses = [-delta if delta < 0 else 0 for delta in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for index in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[index]) / period
        avg_loss = (avg_loss * (period - 1) + losses[index]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _sample_from_row(row) -> SampleStock:
    return SampleStock(
        stock_id=row.id,
        symbol=row.symbol,
        name=row.name,
        market=row.market,
        industry=row.industry,
        price_count=int(getattr(row, "price_count", 0) or 0),
        latest_trade_date=getattr(row, "latest_trade_date", None),
        selection_reason=getattr(row, "selection_reason", None),
    )


def _priority_stock_rows(db: Session, limit: int) -> list:
    """Collect prioritized stock rows with price stats."""
    seen: set[int] = set()
    ordered: list = []

    def add_rows(rows):
        for row in rows:
            if row.id in seen:
                continue
            seen.add(row.id)
            ordered.append(row)
            if len(ordered) >= limit:
                return True
        return False

    price_base = (
        db.query(
            Stock.id,
            Stock.symbol,
            Stock.name,
            Stock.market,
            Stock.industry,
            func.count(DailyPrice.id).label("price_count"),
            func.max(DailyPrice.trade_date).label("latest_trade_date"),
        )
        .join(DailyPrice, DailyPrice.stock_id == Stock.id)
        .filter(Stock.status == "ACTIVE")
        .group_by(Stock.id, Stock.symbol, Stock.name, Stock.market, Stock.industry)
    )

    # 1. watchlist
    watchlist_codes = [item.stock_code for item in db.query(WatchlistItem.stock_code).distinct().all() if item.stock_code]
    if watchlist_codes:
        rows = price_base.filter(Stock.symbol.in_(watchlist_codes)).order_by(func.max(DailyPrice.trade_date).desc()).all()
        if add_rows(rows):
            return ordered[:limit]

    # 2. recent reports
    report_codes = [
        item[0]
        for item in db.query(Report.stock_code)
        .filter(Report.stock_code.isnot(None))
        .order_by(Report.created_at.desc())
        .limit(limit * 2)
        .all()
        if item[0]
    ]
    if report_codes:
        rows = price_base.filter(Stock.symbol.in_(report_codes)).order_by(func.max(DailyPrice.trade_date).desc()).all()
        if add_rows(rows):
            return ordered[:limit]

    # 3. recent backtests
    bt_codes = [
        item[0]
        for item in db.query(BacktestTask.stock_code)
        .filter(BacktestTask.stock_code.isnot(None))
        .order_by(BacktestTask.created_at.desc())
        .limit(limit * 2)
        .all()
        if item[0]
    ]
    if bt_codes:
        rows = price_base.filter(Stock.symbol.in_(bt_codes)).order_by(func.max(DailyPrice.trade_date).desc()).all()
        if add_rows(rows):
            return ordered[:limit]

    # 4-8 fallback: A-share with >=60 prices, then general
    rows = (
        price_base.having(func.count(DailyPrice.id) >= 60)
        .filter(Stock.market == "A_SHARE")
        .order_by(func.max(DailyPrice.trade_date).desc(), func.count(DailyPrice.id).desc(), Stock.symbol.asc())
        .limit(limit * 2)
        .all()
    )
    add_rows(rows)
    if len(ordered) < limit:
        rows = (
            price_base.having(func.count(DailyPrice.id) >= 30)
            .order_by(Stock.market.asc(), func.max(DailyPrice.trade_date).desc(), func.count(DailyPrice.id).desc())
            .limit(limit * 2)
            .all()
        )
        add_rows(rows)
    return ordered[:limit]


def select_financial_refresh_universe(db: Session, limit: int | None = None) -> list[SampleStock]:
    limit = limit or DAILY_FINANCIAL_LIMIT
    rows = _priority_stock_rows(db, limit)
    return [_sample_from_row(row) for row in rows]


def select_technical_refresh_universe(db: Session, limit: int | None = None) -> list[SampleStock]:
    limit = limit or DAILY_TECHNICAL_LIMIT
    rows = _priority_stock_rows(db, limit)
    return [_sample_from_row(row) for row in rows if int(getattr(row, "price_count", 0) or 0) >= 30]


def select_real_pipeline_sample_stocks(db: Session, limit: int = 30) -> list[SampleStock]:
    seen: set[int] = set()
    ordered: list[SampleStock] = []

    price_base = (
        db.query(
            Stock.id,
            Stock.symbol,
            Stock.name,
            Stock.market,
            Stock.industry,
            func.count(DailyPrice.id).label("price_count"),
            func.max(DailyPrice.trade_date).label("latest_trade_date"),
        )
        .join(DailyPrice, DailyPrice.stock_id == Stock.id)
        .filter(Stock.status == "ACTIVE", Stock.market == "A_SHARE")
        .group_by(Stock.id, Stock.symbol, Stock.name, Stock.market, Stock.industry)
    )

    def add_rows(rows: list, reason: str) -> None:
        for row in rows:
            if row.id in seen:
                continue
            seen.add(row.id)
            ordered.append(
                SampleStock(
                    stock_id=row.id,
                    symbol=row.symbol,
                    name=row.name,
                    market=row.market,
                    industry=row.industry,
                    price_count=int(getattr(row, "price_count", 0) or 0),
                    latest_trade_date=getattr(row, "latest_trade_date", None),
                    selection_reason=reason,
                )
            )
            if len(ordered) >= limit:
                return

    watchlist_codes = [item.stock_code for item in db.query(WatchlistItem.stock_code).distinct().all() if item.stock_code]
    if watchlist_codes:
        add_rows(
            price_base.filter(Stock.symbol.in_(watchlist_codes))
            .order_by(func.max(DailyPrice.trade_date).desc(), func.count(DailyPrice.id).desc())
            .all(),
            "watchlist",
        )

    if len(ordered) < limit:
        add_rows(
            price_base.filter(Stock.symbol.in_(CORE_STOCKS))
            .order_by(func.max(DailyPrice.trade_date).desc(), func.count(DailyPrice.id).desc(), Stock.symbol.asc())
            .all(),
            "core_stock",
        )

    if len(ordered) < limit:
        missing_core_rows = (
            db.query(Stock)
            .filter(
                Stock.symbol.in_(CORE_STOCKS),
                ~Stock.id.in_(db.query(DailyPrice.stock_id).distinct()),
            )
            .order_by(Stock.symbol.asc())
            .all()
        )
        add_rows(
            [
                type(
                    "CoreRow",
                    (),
                    {
                        "id": row.id,
                        "symbol": row.symbol,
                        "name": row.name,
                        "market": row.market,
                        "industry": row.industry,
                        "price_count": 0,
                        "latest_trade_date": None,
                    },
                )()
                for row in missing_core_rows
            ],
            "core_stock_no_price",
        )

    if len(ordered) < limit:
        report_codes = [
            item[0]
            for item in db.query(Report.stock_code)
            .filter(Report.stock_code.isnot(None))
            .order_by(Report.created_at.desc())
            .limit(limit * 2)
            .all()
            if item[0]
        ]
        if report_codes:
            add_rows(
                price_base.filter(Stock.symbol.in_(report_codes))
                .order_by(func.max(DailyPrice.trade_date).desc(), func.count(DailyPrice.id).desc())
                .all(),
                "recent_report",
            )

    if len(ordered) < limit:
        bt_codes = [
            item[0]
            for item in db.query(BacktestTask.stock_code)
            .filter(BacktestTask.stock_code.isnot(None))
            .order_by(BacktestTask.created_at.desc())
            .limit(limit * 2)
            .all()
            if item[0]
        ]
        if bt_codes:
            add_rows(
                price_base.filter(Stock.symbol.in_(bt_codes))
                .order_by(func.max(DailyPrice.trade_date).desc(), func.count(DailyPrice.id).desc())
                .all(),
                "recent_backtest",
            )

    if len(ordered) < limit:
        add_rows(
            price_base.filter(Stock.industry.isnot(None))
            .having(func.count(DailyPrice.id) >= 60)
            .order_by(func.max(DailyPrice.trade_date).desc(), func.count(DailyPrice.id).desc(), Stock.symbol.asc())
            .limit(limit * 3)
            .all(),
            "industry_ready",
        )

    if len(ordered) < limit:
        add_rows(
            price_base.having(func.count(DailyPrice.id) >= 60)
            .order_by(func.max(DailyPrice.trade_date).desc(), func.count(DailyPrice.id).desc(), Stock.symbol.asc())
            .limit(limit * 3)
            .all(),
            "history_60d",
        )

    if len(ordered) < limit:
        add_rows(
            price_base.having(func.count(DailyPrice.id) >= 30)
            .order_by(func.max(DailyPrice.trade_date).desc(), func.count(DailyPrice.id).desc(), Stock.symbol.asc())
            .limit(limit * 3)
            .all(),
            "history_30d",
        )

    if ordered:
        return ordered[:limit]
    return select_technical_refresh_universe(db, limit=limit)


def sync_core_stock_prices(
    db: Session,
    provider=None,
    *,
    max_days: int = 180,
    stale_days: int = 7,
    limit: int | None = None,
) -> dict[str, Any]:
    provider = provider or get_provider()
    today = date.today()
    start = today - timedelta(days=max_days)
    target_codes = CORE_STOCKS[: limit or len(CORE_STOCKS)]
    stocks = db.query(Stock).filter(Stock.symbol.in_(target_codes)).all()
    stock_map = {stock.symbol: stock for stock in stocks}

    attempted = 0
    success = 0
    failed = 0
    skipped_fresh = 0
    inserted_rows = 0
    updated_rows = 0
    failure_reasons: dict[str, int] = {}
    details: list[dict[str, Any]] = []

    for code in target_codes:
        stock = stock_map.get(code)
        if not stock:
            failed += 1
            reason = "missing_stock_record"
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            details.append({"symbol": code, "status": "failed", "reason": reason})
            continue

        latest_price = (
            db.query(DailyPrice)
            .filter(DailyPrice.stock_id == stock.id)
            .order_by(DailyPrice.trade_date.desc())
            .first()
        )
        if latest_price and latest_price.trade_date and (today - latest_price.trade_date).days <= stale_days:
            skipped_fresh += 1
            details.append({"symbol": code, "status": "skipped_fresh", "latest_price_date": str(latest_price.trade_date)})
            continue

        attempted += 1
        try:
            df = provider.fetch_daily_prices(code, start, today)
            if df is None or getattr(df, "empty", True):
                failed += 1
                reason = "empty_price_response"
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
                details.append({"symbol": code, "status": "failed", "reason": reason})
                continue

            rows_written = 0
            for _, row in df.iterrows():
                trade_date = row["trade_date"]
                if hasattr(trade_date, "date"):
                    trade_date = trade_date.date()
                existing = (
                    db.query(DailyPrice)
                    .filter(DailyPrice.stock_id == stock.id, DailyPrice.trade_date == trade_date)
                    .first()
                )
                payload = {
                    "open": round(float(row["open"]), 2) if row.get("open") is not None else None,
                    "high": round(float(row["high"]), 2) if row.get("high") is not None else None,
                    "low": round(float(row["low"]), 2) if row.get("low") is not None else None,
                    "close": round(float(row["close"]), 2) if row.get("close") is not None else None,
                    "pre_close": round(float(row["pre_close"]), 2) if row.get("pre_close") not in (None, "") else None,
                    "volume": round(float(row["volume"]), 0) if row.get("volume") not in (None, "") else 0,
                    "turnover": round(float(row["turnover"]), 0) if row.get("turnover") not in (None, "") else 0,
                    "turnover_rate": round(float(row["turnover_rate"]), 2) if row.get("turnover_rate") not in (None, "") else 0,
                    "market_cap": round(float(row["market_cap"]), 0) if row.get("market_cap") not in (None, "") else None,
                    "pe": round(float(row["pe"]), 2) if row.get("pe") not in (None, "") else None,
                    "pb": round(float(row["pb"]), 2) if row.get("pb") not in (None, "") else None,
                    "dividend_yield": round(float(row["dividend_yield"]), 2) if row.get("dividend_yield") not in (None, "") else None,
                }
                if existing:
                    for key, value in payload.items():
                        setattr(existing, key, value)
                    updated_rows += 1
                else:
                    db.add(DailyPrice(stock_id=stock.id, trade_date=trade_date, **payload))
                    inserted_rows += 1
                rows_written += 1
            db.commit()
            success += 1
            details.append({"symbol": code, "status": "synced", "rows_written": rows_written})
        except Exception as exc:
            db.rollback()
            failed += 1
            reason = str(exc)[:200]
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            details.append({"symbol": code, "status": "failed", "reason": reason})

    return {
        "core_stock_count": len(target_codes),
        "price_sync_attempted": attempted,
        "price_sync_success": success,
        "price_sync_failed": failed,
        "price_sync_skipped_fresh": skipped_fresh,
        "inserted_rows": inserted_rows,
        "updated_rows": updated_rows,
        "failure_reasons": failure_reasons,
        "details": details,
    }


def snapshot_real_pipeline_state(db: Session) -> dict[str, Any]:
    real_score_count = db.query(StockScore).filter(StockScore.score_source == REAL_SCORE_SOURCE).count()
    real_signal_count = db.query(TradeSignal).filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE).count()
    demo_score_count = db.query(StockScore).filter(StockScore.score_source == DEMO_SCORE_SOURCE).count()
    demo_signal_count = db.query(TradeSignal).filter(TradeSignal.signal_source == DEMO_SIGNAL_SOURCE).count()
    return {
        "stocks": db.query(Stock).count(),
        "prices": db.query(DailyPrice).count(),
        "financial_metrics": db.query(FinancialMetric).count(),
        "technical_indicators": db.query(TechnicalIndicator).count(),
        "scores_total": db.query(StockScore).count(),
        "signals_total": db.query(TradeSignal).count(),
        "real_scores": real_score_count,
        "real_signals": real_signal_count,
        "demo_scores": demo_score_count,
        "demo_signals": demo_signal_count,
        "latest_price_date": db.query(func.max(DailyPrice.trade_date)).scalar(),
        "latest_financial_date": db.query(func.max(FinancialMetric.report_date)).scalar(),
        "latest_technical_date": db.query(func.max(TechnicalIndicator.trade_date)).scalar(),
        "latest_real_score_date": db.query(func.max(StockScore.score_date)).filter(StockScore.score_source == REAL_SCORE_SOURCE).scalar(),
        "latest_real_signal_date": db.query(func.max(TradeSignal.signal_date)).filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE).scalar(),
    }


def _fetch_financial_worker(provider, symbol: str) -> tuple[str, list[dict[str, Any]] | None, str | None]:
    try:
        df = provider.fetch_financial_metrics(symbol)
    except Exception as exc:
        return symbol, None, str(exc)
    if df is None or getattr(df, "empty", True):
        return symbol, None, "empty_provider_response"
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        report_period = str(row.get("report_period") or "").strip()
        if not report_period:
            continue
        rows.append(dict(row))
    if not rows:
        return symbol, None, "no_report_period_rows"
    return symbol, rows, None


def refresh_financial_metrics_for_stocks(
    db: Session,
    stocks: list[SampleStock],
    provider=None,
    max_workers: int | None = None,
) -> dict[str, Any]:
    started = time.time()
    provider = provider or get_provider()
    max_workers = max_workers or REAL_PIPELINE_FINANCIAL_WORKERS
    symbol_map = {sample.symbol: sample for sample in stocks}

    attempted = len(stocks)
    success_symbols: set[str] = set()
    failed: list[dict[str, str]] = []
    failure_reasons: dict[str, int] = {}
    inserted = 0
    updated = 0
    skipped_existing = 0

    fetch_results: dict[str, tuple[list[dict[str, Any]] | None, str | None]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_fetch_financial_worker, provider, sample.symbol): sample.symbol
            for sample in stocks
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                sym, rows, error = future.result()
                fetch_results[sym] = (rows, error)
            except Exception as exc:
                fetch_results[symbol] = (None, str(exc))

    for sample in stocks:
        rows, error = fetch_results.get(sample.symbol, (None, "not_fetched"))
        if error or not rows:
            reason = error or "unknown"
            failed.append({"symbol": sample.symbol, "error": reason})
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            continue

        touched = False
        for row in rows:
            report_period = str(row.get("report_period") or "").strip()
            if not report_period:
                continue
            report_date = _normalize_trade_date(row.get("report_date")) or _normalize_report_date(report_period)
            existing = (
                db.query(FinancialMetric)
                .filter(
                    FinancialMetric.stock_id == sample.stock_id,
                    FinancialMetric.report_period == report_period,
                )
                .first()
            )
            payload = {
                "report_date": report_date,
                "revenue": _safe_float(row.get("revenue")),
                "revenue_yoy": _safe_float(row.get("revenue_yoy")),
                "net_profit": _safe_float(row.get("net_profit")),
                "net_profit_yoy": _safe_float(row.get("net_profit_yoy")),
                "gross_margin": _safe_float(row.get("gross_margin")),
                "net_margin": _safe_float(row.get("net_margin")),
                "roe": _safe_float(row.get("roe")),
                "roa": _safe_float(row.get("roa")),
                "debt_ratio": _safe_float(row.get("debt_ratio")),
                "operating_cashflow": _safe_float(row.get("operating_cashflow")),
                "free_cashflow": _safe_float(row.get("free_cashflow")),
                "eps": _safe_float(row.get("eps")),
                "book_value_per_share": _safe_float(row.get("book_value_per_share")),
            }
            if existing:
                changed = False
                for key, value in payload.items():
                    if getattr(existing, key) != value:
                        setattr(existing, key, value)
                        changed = True
                if changed:
                    updated += 1
                else:
                    skipped_existing += 1
            else:
                db.add(FinancialMetric(stock_id=sample.stock_id, report_period=report_period, **payload))
                inserted += 1
            touched = True
        if touched:
            success_symbols.add(sample.symbol)

    db.commit()
    return {
        "attempted": attempted,
        "success": len(success_symbols),
        "failed": len(failed),
        "skipped_existing": skipped_existing,
        "inserted_rows": inserted,
        "updated_rows": updated,
        "touched_symbols": sorted(success_symbols),
        "failed_items": failed,
        "failure_reasons": failure_reasons,
        "duration_seconds": round(time.time() - started, 2),
        # backward compat
        "inserted": inserted,
        "updated": updated,
    }


def backfill_latest_valuation_ratios(
    db: Session,
    stocks: list[SampleStock],
    score_date: date | None = None,
) -> dict[str, Any]:
    attempted = len(stocks)
    updated_pe = 0
    updated_pb = 0
    skipped_no_eps = 0
    skipped_no_bvps = 0
    skipped_no_close = 0
    skipped_missing_price = 0
    failed = 0
    failures: dict[str, int] = {}
    valuation_ready_count = 0
    valuation_partial_count = 0
    valuation_missing_count = 0

    for sample in stocks:
        try:
            latest_price = (
                db.query(DailyPrice)
                .filter(DailyPrice.stock_id == sample.stock_id)
                .order_by(DailyPrice.trade_date.desc())
                .first()
            )
            if not latest_price:
                skipped_missing_price += 1
                valuation_missing_count += 1
                continue

            latest_financial = _latest_financial_for_stock(db, sample.stock_id, score_date or latest_price.trade_date)
            has_valid_close = latest_price.close is not None and latest_price.close > 0
            if not has_valid_close:
                skipped_no_close += 1
            elif latest_financial and latest_financial.eps and latest_financial.eps > 0:
                if latest_price.pe is None or latest_price.pe <= 0:
                    latest_price.pe = round(float(latest_price.close) / float(latest_financial.eps), 2)
                    updated_pe += 1
            else:
                skipped_no_eps += 1

            if has_valid_close and latest_financial and latest_financial.book_value_per_share and latest_financial.book_value_per_share > 0:
                if latest_price.pb is None or latest_price.pb <= 0:
                    latest_price.pb = round(float(latest_price.close) / float(latest_financial.book_value_per_share), 2)
                    updated_pb += 1
            elif has_valid_close:
                skipped_no_bvps += 1

            readiness = valuation_readiness(latest_price.pe, latest_price.pb)
            if readiness == VALUATION_READY:
                valuation_ready_count += 1
            elif readiness == VALUATION_PARTIAL:
                valuation_partial_count += 1
            else:
                valuation_missing_count += 1
        except Exception as exc:
            failed += 1
            reason = str(exc)[:200]
            failures[reason] = failures.get(reason, 0) + 1
            db.rollback()

    db.commit()
    return {
        "attempted": attempted,
        "updated_pe": updated_pe,
        "updated_pb": updated_pb,
        "skipped_no_eps": skipped_no_eps,
        "skipped_no_bvps": skipped_no_bvps,
        "skipped_no_close": skipped_no_close,
        "skipped_missing_price": skipped_missing_price,
        "failed": failed,
        "failure_reasons": failures,
        "valuation_ready_count": valuation_ready_count,
        "valuation_partial_count": valuation_partial_count,
        "valuation_missing_count": valuation_missing_count,
    }


def _compute_indicator_payload(prices: list[DailyPrice]) -> dict[str, Any] | None:
    if len(prices) < 30:
        return None
    closes = [float(item.close) for item in prices if item.close is not None]
    volumes = [float(item.volume or 0) for item in prices]
    if len(closes) != len(prices):
        return None

    latest = prices[-1]
    ema12_series = _ema(closes, 12)
    ema26_series = _ema(closes, 26)
    macd_series = [ema12_series[i] - ema26_series[i] for i in range(len(closes))]
    signal_series = _ema(macd_series, 9)

    ma5 = sum(closes[-5:]) / min(5, len(closes))
    ma10 = sum(closes[-10:]) / min(10, len(closes))
    ma20 = sum(closes[-20:]) / min(20, len(closes))
    ma60 = sum(closes[-60:]) / 60 if len(closes) >= 60 else None
    ma120 = sum(closes[-120:]) / 120 if len(closes) >= 120 else None
    volume_ma5 = sum(volumes[-5:]) / min(5, len(volumes))
    volume_ma20 = sum(volumes[-20:]) / min(20, len(volumes))
    volume_ratio = (volume_ma5 / volume_ma20) if volume_ma20 else None

    boll_window = closes[-20:]
    boll_mid = ma20
    boll_std = statistics.stdev(boll_window) if len(boll_window) >= 2 else 0.0
    boll_upper = boll_mid + 2 * boll_std
    boll_lower = boll_mid - 2 * boll_std

    weekly_returns = [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(max(1, len(closes) - 5), len(closes))
        if closes[i - 1]
    ]
    monthly_returns = [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(max(1, len(closes) - 20), len(closes))
        if closes[i - 1]
    ]
    weekly_volatility = statistics.pstdev(weekly_returns) * math.sqrt(252) * 100 if len(weekly_returns) >= 2 else None
    monthly_volatility = statistics.pstdev(monthly_returns) * math.sqrt(252) * 100 if len(monthly_returns) >= 2 else None

    return {
        "trade_date": latest.trade_date,
        "payload": {
            "ma5": round(ma5, 2) if ma5 is not None else None,
            "ma10": round(ma10, 2) if ma10 is not None else None,
            "ma20": round(ma20, 2) if ma20 is not None else None,
            "ma60": round(ma60, 2) if ma60 is not None else None,
            "ma120": round(ma120, 2) if ma120 is not None else None,
            "macd": round(macd_series[-1], 4),
            "macd_signal": round(signal_series[-1], 4),
            "macd_hist": round(macd_series[-1] - signal_series[-1], 4),
            "rsi14": round(_rsi(closes, 14), 2),
            "boll_upper": round(boll_upper, 2),
            "boll_middle": round(boll_mid, 2),
            "boll_lower": round(boll_lower, 2),
            "volume_ma5": round(volume_ma5, 2),
            "volume_ma20": round(volume_ma20, 2),
            "volume_ratio_5_20": round(volume_ratio, 4) if volume_ratio is not None else None,
            "weekly_volatility_candidate": round(weekly_volatility, 4) if weekly_volatility is not None else None,
            "monthly_volatility_candidate": round(monthly_volatility, 4) if monthly_volatility is not None else None,
        },
    }


def compute_technical_indicators_for_stocks(
    db: Session,
    stocks: list[SampleStock],
    limit: int | None = None,
    commit_batch: int = 100,
) -> dict[str, Any]:
    started = time.time()
    limit = limit or len(stocks)
    stocks = stocks[:limit]

    attempted = len(stocks)
    success = 0
    failed = 0
    inserted = 0
    updated = 0
    skipped_insufficient_price = 0
    failure_reasons: dict[str, int] = {}
    computed_symbols: list[str] = []
    latest_technical_date: date | None = None

    for index, sample in enumerate(stocks, start=1):
        try:
            prices = (
                db.query(DailyPrice)
                .filter(DailyPrice.stock_id == sample.stock_id)
                .order_by(DailyPrice.trade_date.asc())
                .all()
            )
            if len(prices) < 30:
                skipped_insufficient_price += 1
                continue
            computed = _compute_indicator_payload(prices)
            if not computed:
                skipped_insufficient_price += 1
                continue

            trade_date = computed["trade_date"]
            payload = computed["payload"]
            latest_technical_date = trade_date

            existing = (
                db.query(TechnicalIndicator)
                .filter(
                    TechnicalIndicator.stock_id == sample.stock_id,
                    TechnicalIndicator.trade_date == trade_date,
                )
                .first()
            )
            if existing:
                for key, value in payload.items():
                    setattr(existing, key, value)
                updated += 1
            else:
                db.add(TechnicalIndicator(stock_id=sample.stock_id, trade_date=trade_date, **payload))
                inserted += 1
            success += 1
            computed_symbols.append(sample.symbol)

            if index % commit_batch == 0:
                db.commit()
        except Exception as exc:
            failed += 1
            reason = str(exc)[:200]
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            db.rollback()

    db.commit()
    return {
        "attempted": attempted,
        "success": success,
        "failed": failed,
        "inserted": inserted,
        "updated": updated,
        "skipped_insufficient_price": skipped_insufficient_price,
        "latest_technical_date": str(latest_technical_date) if latest_technical_date else None,
        "failure_reasons": failure_reasons,
        "computed_symbols": computed_symbols,
        "duration_seconds": round(time.time() - started, 2),
        # backward compat
        "inserted_rows": inserted,
        "updated_rows": updated,
        "skipped_symbols": [],
    }


def _build_reason_summary(details: list[dict[str, Any]]) -> str:
    strengths = [str(item.get("item")) for item in details if item.get("max") and item.get("score", 0) >= item.get("max", 0) * 0.7]
    weaknesses = [str(item.get("item")) for item in details if item.get("max") and item.get("score", 0) <= item.get("max", 0) * 0.3]
    summary = f"优势: {', '.join(strengths[:3])}" if strengths else "优势: 暂无明显优势"
    if weaknesses:
        summary += f" | 风险: {', '.join(weaknesses[:3])}"
    return summary


def generate_real_scores_for_stocks(
    db: Session,
    stocks: list[SampleStock],
    score_date: date | None = None,
) -> dict[str, Any]:
    latest_price_date = score_date or db.query(func.max(DailyPrice.trade_date)).scalar()
    if not latest_price_date:
        return {
            "score_date": None,
            "attempted": len(stocks),
            "success": 0,
            "failed": 0,
            "skipped_no_financial": len(stocks),
            "skipped_no_technical": len(stocks),
            "skipped_insufficient_price": len(stocks),
            "real_score_count_after": 0,
            "created": 0,
            "updated": 0,
            "skipped": [],
        }

    stock_ids = [sample.stock_id for sample in stocks]
    industry_stats = _compute_industry_stats(db, stock_ids)

    attempted = len(stocks)
    success = 0
    failed = 0
    skipped_no_financial = 0
    skipped_no_technical = 0
    skipped_insufficient_price = 0
    skipped_no_valuation_data = 0
    created = 0
    updated = 0
    skipped: list[dict[str, str]] = []
    failure_reasons: dict[str, int] = {}
    valuation_ready_count = 0
    valuation_partial_count = 0

    for sample in stocks:
        try:
            price_count = (
                db.query(func.count(DailyPrice.id))
                .filter(DailyPrice.stock_id == sample.stock_id)
                .scalar()
                or 0
            )
            if price_count < 30:
                skipped_insufficient_price += 1
                skipped.append({"symbol": sample.symbol, "reason": "insufficient_price"})
                continue

            price = (
                db.query(DailyPrice)
                .filter(DailyPrice.stock_id == sample.stock_id, DailyPrice.trade_date <= latest_price_date)
                .order_by(DailyPrice.trade_date.desc())
                .first()
            )
            financial = _latest_financial_for_stock(db, sample.stock_id, latest_price_date)
            tech = (
                db.query(TechnicalIndicator)
                .filter(TechnicalIndicator.stock_id == sample.stock_id, TechnicalIndicator.trade_date <= latest_price_date)
                .order_by(TechnicalIndicator.trade_date.desc())
                .first()
            )
            if not financial:
                skipped_no_financial += 1
                skipped.append({"symbol": sample.symbol, "reason": "no_financial"})
                continue
            if not tech:
                skipped_no_technical += 1
                skipped.append({"symbol": sample.symbol, "reason": "no_technical"})
                continue
            if not price:
                skipped_insufficient_price += 1
                skipped.append({"symbol": sample.symbol, "reason": "insufficient_price"})
                continue

            prev_financial = _previous_financial_for_stock(db, sample.stock_id, financial)
            readiness = valuation_readiness(price.pe, price.pb)
            if readiness == VALUATION_MISSING:
                stale_real_score = (
                    db.query(StockScore)
                    .filter(
                        StockScore.stock_id == sample.stock_id,
                        StockScore.score_date == latest_price_date,
                        StockScore.score_source == REAL_SCORE_SOURCE,
                    )
                    .first()
                )
                if stale_real_score:
                    db.delete(stale_real_score)
                    db.flush()
                skipped_no_valuation_data += 1
                skipped.append({"symbol": sample.symbol, "reason": "no_pe_pb"})
                continue
            if readiness == VALUATION_READY:
                valuation_ready_count += 1
            else:
                valuation_partial_count += 1
            ind_stats = industry_stats.get(sample.industry) if sample.industry else None
            quality_score, quality_details = calculate_quality_score(financial, prev_financial, ind_stats)
            valuation_score, valuation_details = calculate_valuation_score(price, financial, ind_stats)
            growth_score, growth_details = calculate_growth_score(financial)
            trend_score, trend_details = calculate_trend_score(price, tech)
            risk_score, risk_details = calculate_risk_score(financial, price, tech, ind_stats)
            total_score = round(quality_score + valuation_score + growth_score + trend_score + risk_score, 2)
            rating = get_rating(total_score)
            reason_summary = _build_reason_summary(
                quality_details + valuation_details + growth_details + trend_details + risk_details
            )

            existing = (
                db.query(StockScore)
                .filter(
                    StockScore.stock_id == sample.stock_id,
                    StockScore.score_date == latest_price_date,
                )
                .first()
            )
            if existing and existing.score_source == DEMO_SCORE_SOURCE:
                db.delete(existing)
                db.flush()
                existing = None

            if existing and existing.score_source not in (None, UNKNOWN_SCORE_SOURCE, REAL_SCORE_SOURCE):
                skipped.append({"symbol": sample.symbol, "reason": "existing_non_demo_score"})
                continue

            if existing:
                existing.total_score = total_score
                existing.quality_score = quality_score
                existing.valuation_score = valuation_score
                existing.growth_score = growth_score
                existing.trend_score = trend_score
                existing.risk_score = risk_score
                existing.rating = rating
                existing.reason_summary = reason_summary
                existing.score_source = REAL_SCORE_SOURCE
                updated += 1
            else:
                db.add(
                    StockScore(
                        stock_id=sample.stock_id,
                        score_date=latest_price_date,
                        total_score=total_score,
                        quality_score=quality_score,
                        valuation_score=valuation_score,
                        growth_score=growth_score,
                        trend_score=trend_score,
                        risk_score=risk_score,
                        rating=rating,
                        reason_summary=reason_summary,
                        score_source=REAL_SCORE_SOURCE,
                    )
                )
                created += 1
            success += 1
        except Exception as exc:
            failed += 1
            reason = f"calculation_error:{exc}"[:200]
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            skipped.append({"symbol": sample.symbol, "reason": "calculation_error"})
            db.rollback()

    db.commit()
    real_score_count_after = db.query(StockScore).filter(StockScore.score_source == REAL_SCORE_SOURCE).count()
    return {
        "score_date": latest_price_date.isoformat(),
        "attempted": attempted,
        "success": success,
        "failed": failed,
        "skipped_no_financial": skipped_no_financial,
        "skipped_no_technical": skipped_no_technical,
        "skipped_insufficient_price": skipped_insufficient_price,
        "skipped_no_valuation_data": skipped_no_valuation_data,
        "valuation_ready_count": valuation_ready_count,
        "valuation_partial_count": valuation_partial_count,
        "real_score_count_after": real_score_count_after,
        "failure_reasons": failure_reasons,
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }


def generate_real_signals_for_stocks(
    db: Session,
    stocks: list[SampleStock],
    signal_date: date | None = None,
) -> dict[str, Any]:
    latest_signal_date = signal_date or db.query(func.max(DailyPrice.trade_date)).scalar()
    if not latest_signal_date:
        return {
            "signal_date": None,
            "attempted": len(stocks),
            "success": 0,
            "failed": 0,
            "skipped_demo_score": 0,
            "skipped_unknown_score": 0,
            "real_signal_count_after": 0,
            "created_or_updated": 0,
            "skipped": [],
        }

    attempted = len(stocks)
    success = 0
    failed = 0
    skipped_demo_score = 0
    skipped_unknown_score = 0
    skipped_no_valuation_data = 0
    skipped: list[dict[str, str]] = []
    failure_reasons: dict[str, int] = {}
    created_or_updated = 0

    for sample in stocks:
        score = (
            db.query(StockScore)
            .filter(
                StockScore.stock_id == sample.stock_id,
                StockScore.score_date == latest_signal_date,
            )
            .first()
        )
        if not score:
            skipped.append({"symbol": sample.symbol, "reason": "missing_score"})
            continue
        if score.score_source == DEMO_SCORE_SOURCE:
            skipped_demo_score += 1
            skipped.append({"symbol": sample.symbol, "reason": "skipped_demo_score"})
            continue
        if score.score_source != REAL_SCORE_SOURCE:
            skipped_unknown_score += 1
            skipped.append({"symbol": sample.symbol, "reason": "skipped_unknown_score"})
            continue

        latest_price = (
            db.query(DailyPrice)
            .filter(DailyPrice.stock_id == sample.stock_id, DailyPrice.trade_date <= latest_signal_date)
            .order_by(DailyPrice.trade_date.desc())
            .first()
        )
        if latest_price and valuation_readiness(latest_price.pe, latest_price.pb) == VALUATION_MISSING:
            stale_real_signals = (
                db.query(TradeSignal)
                .filter(
                    TradeSignal.stock_id == sample.stock_id,
                    TradeSignal.signal_date == latest_signal_date,
                    TradeSignal.signal_source == REAL_SIGNAL_SOURCE,
                )
                .all()
            )
            for item in stale_real_signals:
                db.delete(item)
            db.flush()
            skipped_no_valuation_data += 1
            skipped.append({"symbol": sample.symbol, "reason": "no_pe_pb"})
            continue

        try:
            demo_signals = (
                db.query(TradeSignal)
                .filter(
                    TradeSignal.stock_id == sample.stock_id,
                    TradeSignal.signal_date == latest_signal_date,
                    TradeSignal.signal_source == DEMO_SIGNAL_SOURCE,
                )
                .all()
            )
            for item in demo_signals:
                db.delete(item)
            db.flush()

            signal = generate_signal_for_stock(db, sample.stock_id, latest_signal_date, commit=False)
            if not signal:
                db.rollback()
                failed += 1
                skipped.append({"symbol": sample.symbol, "reason": "signal_generation_failed"})
                continue
            signal.signal_source = REAL_SIGNAL_SOURCE
            db.commit()
            success += 1
            created_or_updated += 1
        except Exception as exc:
            db.rollback()
            failed += 1
            reason = str(exc)[:200]
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            skipped.append({"symbol": sample.symbol, "reason": "signal_generation_failed"})

    real_signal_count_after = db.query(TradeSignal).filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE).count()
    return {
        "signal_date": latest_signal_date.isoformat(),
        "attempted": attempted,
        "success": success,
        "failed": failed,
        "skipped_demo_score": skipped_demo_score,
        "skipped_unknown_score": skipped_unknown_score,
        "skipped_no_valuation_data": skipped_no_valuation_data,
        "real_signal_count_after": real_signal_count_after,
        "failure_reasons": failure_reasons,
        "created_or_updated": created_or_updated,
        "skipped": skipped,
    }


def _start_refresh_job(
    db: Session,
    *,
    requested_limit: int,
    trigger_source: str,
    created_by: str | None = None,
) -> RefreshJobRun:
    job = RefreshJobRun(
        job_type="real_pipeline_sample",
        status="running",
        requested_limit=requested_limit,
        trigger_source=trigger_source,
        created_by=created_by,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _finalize_refresh_job(
    db: Session,
    job: RefreshJobRun,
    *,
    status: str,
    sample_size: int,
    financial: dict[str, Any],
    technical: dict[str, Any],
    valuation: dict[str, Any],
    scores: dict[str, Any],
    signals: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> RefreshJobRun:
    job.status = status
    job.finished_at = datetime.now()
    job.sample_size = sample_size
    job.financial_attempted = financial.get("attempted", 0)
    job.financial_success = financial.get("success", 0)
    job.financial_failed = financial.get("failed", 0)
    job.technical_attempted = technical.get("attempted", 0)
    job.technical_success = technical.get("success", 0)
    job.technical_failed = technical.get("failed", 0)
    job.scores_attempted = scores.get("attempted", 0)
    job.scores_success = scores.get("success", 0)
    job.scores_failed = scores.get("failed", 0)
    job.signals_attempted = signals.get("attempted", 0)
    job.signals_success = signals.get("success", 0)
    job.signals_failed = signals.get("failed", 0)
    if job.started_at:
        job.duration_seconds = (job.finished_at - job.started_at).total_seconds()
    summary = {
        "financial_failure_reasons": financial.get("failure_reasons", {}),
        "technical_failure_reasons": technical.get("failure_reasons", {}),
        "valuation_summary": valuation,
        "scores_skipped": {
            "no_financial": scores.get("skipped_no_financial", 0),
            "no_technical": scores.get("skipped_no_technical", 0),
            "insufficient_price": scores.get("skipped_insufficient_price", 0),
            "no_valuation_data": scores.get("skipped_no_valuation_data", 0),
        },
        "signals_skipped": {
            "demo_score": signals.get("skipped_demo_score", 0),
            "unknown_score": signals.get("skipped_unknown_score", 0),
            "no_valuation_data": signals.get("skipped_no_valuation_data", 0),
        },
    }
    if extra:
        summary.update(extra)
    job.failure_summary_json = json.dumps(summary, ensure_ascii=False)
    db.commit()
    db.refresh(job)
    return job


def cleanup_invalid_real_scores_and_signals(db: Session) -> dict[str, int]:
    removed_scores = 0
    removed_signals = 0

    real_scores = db.query(StockScore).filter(StockScore.score_source == REAL_SCORE_SOURCE).all()
    for score in real_scores:
        latest_price = (
            db.query(DailyPrice)
            .filter(
                DailyPrice.stock_id == score.stock_id,
                DailyPrice.trade_date <= score.score_date,
            )
            .order_by(DailyPrice.trade_date.desc())
            .first()
        )
        if latest_price and valuation_readiness(latest_price.pe, latest_price.pb) != VALUATION_MISSING:
            continue
        db.delete(score)
        removed_scores += 1

    real_signals = db.query(TradeSignal).filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE).all()
    for signal in real_signals:
        latest_price = (
            db.query(DailyPrice)
            .filter(
                DailyPrice.stock_id == signal.stock_id,
                DailyPrice.trade_date <= signal.signal_date,
            )
            .order_by(DailyPrice.trade_date.desc())
            .first()
        )
        if latest_price and valuation_readiness(latest_price.pe, latest_price.pb) != VALUATION_MISSING:
            continue
        db.delete(signal)
        removed_signals += 1

    if removed_scores or removed_signals:
        db.commit()

    return {
        "removed_scores": removed_scores,
        "removed_signals": removed_signals,
    }


def run_real_pipeline_sample(
    db: Session,
    limit: int = 30,
    provider=None,
    trigger_source: str = "command",
    created_by: str | None = None,
) -> dict[str, Any]:
    with pipeline_lock(owner=trigger_source) as lock:
        if not lock.acquired:
            return {
                "status": "skipped_locked",
                "reason": lock.reason,
                "sample_size": 0,
            }

        provider = provider or get_provider()
        before = snapshot_real_pipeline_state(db)
        job = _start_refresh_job(db, requested_limit=limit, trigger_source=trigger_source, created_by=created_by)
        core_price_sync = sync_core_stock_prices(db, provider=provider, limit=min(len(CORE_STOCKS), max(limit, 15)))

        samples = select_real_pipeline_sample_stocks(db, limit=limit)
        if not samples:
            samples = select_technical_refresh_universe(db, limit=limit)

        financial_result = refresh_financial_metrics_for_stocks(db, samples, provider=provider)
        technical_result = compute_technical_indicators_for_stocks(db, samples)
        valuation_result = backfill_latest_valuation_ratios(db, samples)
        score_result = generate_real_scores_for_stocks(db, samples)
        signal_result = generate_real_signals_for_stocks(db, samples)
        cleanup_result = cleanup_invalid_real_scores_and_signals(db)
        after = snapshot_real_pipeline_state(db)

        provider_failed = financial_result.get("success", 0) == 0 and financial_result.get("attempted", 0) > 0
        status = "success"
        if provider_failed and after["real_scores"] == 0:
            status = "provider_failed"
        elif after["real_scores"] == 0:
            status = "partial"

        job = _finalize_refresh_job(
            db,
            job,
            status=status,
            sample_size=len(samples),
            financial=financial_result,
            technical=technical_result,
            valuation=valuation_result,
            scores=score_result,
            signals=signal_result,
            extra={
                "pipeline_status": real_pipeline_status(db),
                "cleanup": cleanup_result,
                "core_price_sync": core_price_sync,
            },
        )

        return {
            "status": status,
            "sample_size": len(samples),
            "sample_count": len(samples),
            "sample_symbols": [sample.symbol for sample in samples],
            "refresh_job_run_id": job.id,
            "before": before,
            "core_price_sync": core_price_sync,
            "financial": financial_result,
            "technical": technical_result,
            "valuation": valuation_result,
            "scores": score_result,
            "signals": signal_result,
            "cleanup": cleanup_result,
            "after": after,
            "real_calculated_scores_after": after["real_scores"],
            "real_calculated_signals_after": after["real_signals"],
            "quick_seed_demo_scores_after": after["demo_scores"],
            "quick_seed_demo_signals_after": after["demo_signals"],
            "core_stock_count": sum(1 for sample in samples if sample.symbol in CORE_STOCKS),
            "selected_core_symbols": [sample.symbol for sample in samples if sample.symbol in CORE_STOCKS],
            "sample_selection": [{"symbol": sample.symbol, "reason": sample.selection_reason} for sample in samples],
        }


def get_recent_refresh_job_runs(db: Session, limit: int = 10) -> list[dict[str, Any]]:
    rows = db.query(RefreshJobRun).order_by(RefreshJobRun.started_at.desc()).limit(limit).all()
    result = []
    for row in rows:
        summary = {}
        if row.failure_summary_json:
            try:
                summary = json.loads(row.failure_summary_json)
            except json.JSONDecodeError:
                summary = {"raw": row.failure_summary_json}
        result.append(
            {
                "id": row.id,
                "job_type": row.job_type,
                "status": row.status,
                "started_at": str(row.started_at) if row.started_at else None,
                "finished_at": str(row.finished_at) if row.finished_at else None,
                "duration_seconds": row.duration_seconds,
                "requested_limit": row.requested_limit,
                "sample_size": row.sample_size,
                "financial_attempted": row.financial_attempted,
                "financial_success": row.financial_success,
                "financial_failed": row.financial_failed,
                "technical_attempted": row.technical_attempted,
                "technical_success": row.technical_success,
                "technical_failed": row.technical_failed,
                "scores_attempted": row.scores_attempted,
                "scores_success": row.scores_success,
                "scores_failed": row.scores_failed,
                "signals_attempted": row.signals_attempted,
                "signals_success": row.signals_success,
                "signals_failed": row.signals_failed,
                "trigger_source": row.trigger_source,
                "valuation_summary": summary.get("valuation_summary", {}),
                "core_price_sync": summary.get("core_price_sync", {}),
                "failure_summary": summary,
            }
        )
    return result


def real_pipeline_status(db: Session) -> str:
    snapshot = snapshot_real_pipeline_state(db)
    if snapshot["real_scores"] > 0 and snapshot["real_signals"] > 0:
        return "ready"
    if snapshot["real_scores"] > 0:
        return "partial_ready"
    if snapshot["financial_metrics"] > 0 and snapshot["technical_indicators"] > 0:
        return "partial_ready"
    if snapshot["technical_indicators"] > 0 and snapshot["financial_metrics"] == 0:
        return "financial_missing"
    if snapshot["financial_metrics"] > 0 and snapshot["technical_indicators"] == 0:
        return "financial_ready_only"
    if snapshot["technical_indicators"] > 0:
        return "technical_ready_only"
    if snapshot["prices"] > 0 and snapshot["financial_metrics"] == 0:
        return "financial_missing"
    if snapshot["prices"] > 0:
        return "not_started"
    return "not_started"
