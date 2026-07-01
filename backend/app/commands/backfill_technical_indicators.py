"""
Backfill technical indicators from local daily_prices data.
No external API calls - purely local computation.

Usage:
  python -m app.commands.backfill_technical_indicators --all-priced --min-days 60 --limit 200 --dry-run
  python -m app.commands.backfill_technical_indicators --all-priced --min-days 60 --limit 200
  python -m app.commands.backfill_technical_indicators --financial-covered --min-days 60 --dry-run
"""
from __future__ import annotations
import argparse, json, logging, sys
from datetime import date
from typing import Optional

import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.stock import Stock
from app.models.technical_indicator import TechnicalIndicator

logger = logging.getLogger(__name__)


def _ema(data: list, period: int) -> list:
    if not data:
        return []
    multiplier = 2 / (period + 1)
    ema = [float(data[0])]
    for v in data[1:]:
        ema.append(float(v) * multiplier + ema[-1] * (1 - multiplier))
    return ema


def _compute_indicators(closes: list, volumes: list) -> dict | None:
    if len(closes) < 26:
        return None
    i = len(closes) - 1
    arr = np.array(closes, dtype=float)

    # MA
    ma20 = float(np.mean(closes[max(0, i - 19):i + 1])) if i >= 19 else None
    ma60 = float(np.mean(closes[max(0, i - 59):i + 1])) if i >= 59 else None
    ma120 = float(np.mean(closes[max(0, i - 119):i + 1])) if i >= 119 else None

    # Volume MA
    vol_ma5 = float(np.mean(volumes[max(0, i - 4):i + 1])) if len(volumes) > i else None
    vol_ma20 = float(np.mean(volumes[max(0, i - 19):i + 1])) if len(volumes) > i and i >= 19 else None

    # MACD
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26) if len(closes) >= 26 else ema12
    dif = [ema12[j] - ema26[j] for j in range(len(closes))]
    dea = _ema(dif, 9)
    macd = dif[-1]
    macd_signal = dea[-1]

    # RSI14
    if len(closes) >= 15:
        deltas = [closes[j] - closes[j - 1] for j in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas[-14:]]
        losses = [-d if d < 0 else 0 for d in deltas[-14:]]
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        rsi14 = round(100 - 100 / (1 + avg_gain / avg_loss), 2) if avg_loss > 0 else (100.0 if avg_gain > 0 else 50.0)
    else:
        rsi14 = None

    # Bollinger
    if i >= 19:
        boll_std = float(np.std(closes[max(0, i - 19):i + 1], ddof=1))
        boll_upper = ma20 + 2 * boll_std
        boll_lower = ma20 - 2 * boll_std
    else:
        boll_upper = boll_lower = None

    return {
        "ma20": round(ma20, 2) if ma20 else None,
        "ma60": round(ma60, 2) if ma60 else None,
        "ma120": round(ma120, 2) if ma120 else None,
        "macd": round(macd, 4),
        "macd_signal": round(macd_signal, 4),
        "macd_hist": round(macd - macd_signal, 4),
        "rsi14": rsi14,
        "boll_upper": round(boll_upper, 2) if boll_upper else None,
        "boll_middle": round(ma20, 2) if ma20 else None,
        "boll_lower": round(boll_lower, 2) if boll_lower else None,
        "volume_ma5": round(vol_ma5, 0) if vol_ma5 else None,
        "volume_ma20": round(vol_ma20, 0) if vol_ma20 else None,
    }


def main():
    parser = argparse.ArgumentParser(description="Backfill technical indicators from local daily_prices")
    parser.add_argument("--all-priced", action="store_true", help="Process all stocks with enough price data")
    parser.add_argument("--financial-covered", action="store_true", help="Only process stocks with financial data")
    parser.add_argument("--min-days", type=int, default=60, help="Minimum days of price data required")
    parser.add_argument("--limit", type=int, default=200, help="Max stocks to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    args = parser.parse_args()

    if not args.all_priced and not args.financial_covered:
        parser.error("Must specify --all-priced or --financial-covered")

    db = SessionLocal()
    try:
        # Find eligible stocks
        price_sq = (
            db.query(
                DailyPrice.stock_id,
                func.max(DailyPrice.trade_date).label("max_date"),
                func.count(DailyPrice.id).label("cnt"),
            )
            .group_by(DailyPrice.stock_id)
            .having(func.count(DailyPrice.id) >= args.min_days)
            .subquery()
        )

        query = db.query(Stock, price_sq.c.cnt, price_sq.c.max_date).join(
            price_sq, Stock.id == price_sq.c.stock_id
        ).filter(Stock.status == "ACTIVE")

        if args.financial_covered:
            fin_stock_ids = db.query(FinancialMetric.stock_id).distinct().subquery()
            query = query.filter(Stock.id.in_(fin_stock_ids))

        stocks = query.order_by(Stock.symbol).limit(args.limit).all()
        logger.info(f"Selected {len(stocks)} stocks for technical indicator backfill")

        results = {"processed": 0, "created": 0, "skipped": 0, "errors": 0, "dry_run": args.dry_run, "details": []}

        for stock, price_count, latest_date in stocks:
            results["processed"] += 1
            try:
                # Check if already exists
                existing = db.query(TechnicalIndicator).filter(
                    TechnicalIndicator.stock_id == stock.id,
                    TechnicalIndicator.trade_date == latest_date,
                ).first()
                if existing:
                    results["skipped"] += 1
                    results["details"].append({"symbol": stock.symbol, "status": "skipped_existing"})
                    continue

                # Get price data
                prices = (
                    db.query(DailyPrice)
                    .filter(DailyPrice.stock_id == stock.id)
                    .order_by(DailyPrice.trade_date)
                    .all()
                )
                closes = [p.close for p in prices if p.close]
                volumes = [p.volume for p in prices if p.volume is not None]

                if len(closes) < 26:
                    results["skipped"] += 1
                    results["details"].append({"symbol": stock.symbol, "status": "skipped_insufficient_data"})
                    continue

                indicators = _compute_indicators(closes, volumes)
                if not indicators:
                    results["skipped"] += 1
                    results["details"].append({"symbol": stock.symbol, "status": "skipped_compute_failed"})
                    continue

                if not args.dry_run:
                    ti = TechnicalIndicator(stock_id=stock.id, trade_date=latest_date, **indicators)
                    db.add(ti)
                    db.commit()

                results["created"] += 1
                results["details"].append({
                    "symbol": stock.symbol,
                    "status": "created" if not args.dry_run else "would_create",
                    "ma20": indicators["ma20"],
                    "rsi14": indicators["rsi14"],
                })
            except Exception as e:
                results["errors"] += 1
                results["details"].append({"symbol": stock.symbol, "status": "error", "error": str(e)[:100]})
                db.rollback()

        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
