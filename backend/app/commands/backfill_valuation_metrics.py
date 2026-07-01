"""
Backfill missing PE/PB/market_cap fields in daily_prices table.

Uses the existing CompositeProvider (Eastmoney/Xueqiu/Yahoo) for real valuation
data, with fallback to FinancialMetric-based computation.

Usage:
    python -m app.commands.backfill_valuation_metrics --dry-run --limit 5
    python -m app.commands.backfill_valuation_metrics --core-only --limit 45
    python -m app.commands.backfill_valuation_metrics --symbols "002415,600519" --force
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from typing import Any, Dict, List, Optional

from app.data_providers import get_provider
from app.db.session import SessionLocal
from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.stock import Stock
from app.models.stock_score import StockScore

logger = logging.getLogger(__name__)


def _select_targets(
    db,
    symbols: Optional[List[str]] = None,
    core_only: bool = False,
    all_ready: bool = False,
    limit: int = 20,
) -> List[Stock]:
    """Select target stocks based on command-line flags.

    Priority order: --symbols > --core-only > --all-ready
    """
    if symbols:
        targets = (
            db.query(Stock)
            .filter(Stock.symbol.in_(symbols), Stock.status == "ACTIVE")
            .limit(limit)
            .all()
        )
        return targets

    if core_only:
        subquery = (
            db.query(StockScore.stock_id)
            .filter(StockScore.score_source == "real_calculated")
            .distinct()
            .subquery()
        )
        targets = (
            db.query(Stock)
            .join(subquery, Stock.id == subquery.c.stock_id)
            .filter(Stock.status == "ACTIVE")
            .limit(limit)
            .all()
        )
        return targets

    if all_ready:
        subquery = db.query(DailyPrice.stock_id).distinct().subquery()
        targets = (
            db.query(Stock)
            .join(subquery, Stock.id == subquery.c.stock_id)
            .filter(Stock.status == "ACTIVE")
            .limit(limit)
            .all()
        )
        return targets

    return []


def _compute_pe_pb_from_financials(
    db, stock_id: int, close_price: float,
) -> Dict[str, Optional[float]]:
    """Compute PE/PB from the latest FinancialMetric row as a fallback.

    PE = close / EPS  (when EPS > 0)
    PB = close / book_value_per_share  (when BVPS > 0)
    """
    result: Dict[str, Optional[float]] = {"pe": None, "pb": None}

    latest_fin = (
        db.query(FinancialMetric)
        .filter(FinancialMetric.stock_id == stock_id)
        .order_by(FinancialMetric.report_period.desc())
        .first()
    )
    if not latest_fin:
        return result

    if latest_fin.eps and latest_fin.eps > 0 and close_price:
        result["pe"] = round(close_price / latest_fin.eps, 2)
    if (
        latest_fin.book_value_per_share
        and latest_fin.book_value_per_share > 0
        and close_price
    ):
        result["pb"] = round(close_price / latest_fin.book_value_per_share, 2)

    return result


def _build_record(
    symbol: str,
    trade_date: Any,
    old_pe: Optional[float],
    new_pe: Optional[float],
    old_pb: Optional[float],
    new_pb: Optional[float],
    old_market_cap: Optional[float],
    new_market_cap: Optional[float],
    source: str,
) -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "date": trade_date.isoformat() if hasattr(trade_date, "isoformat") else str(trade_date),
        "old_pe": old_pe,
        "new_pe": new_pe,
        "old_pb": old_pb,
        "new_pb": new_pb,
        "old_market_cap": old_market_cap,
        "new_market_cap": new_market_cap,
        "source": source,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill missing PE/PB/market_cap fields in daily_prices table."
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help='Comma-separated stock symbols (e.g. "002415,600519")',
    )
    parser.add_argument(
        "--core-only",
        action="store_true",
        help="Only process stocks that have real_calculated scores",
    )
    parser.add_argument(
        "--all-ready",
        action="store_true",
        help="Process stocks with daily_prices data",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max stocks to process (default 20)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be updated, don't write",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        dest="sleep_sec",
        help="Sleep between API calls in seconds (default 0.5)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing non-null PE/PB values (default: skip existing)",
    )

    args = parser.parse_args()

    # Parse --symbols into a list
    symbol_list: Optional[List[str]] = None
    if args.symbols:
        symbol_list = [s.strip() for s in args.symbols.split(",") if s.strip()]

    if not symbol_list and not args.core_only and not args.all_ready:
        print("Error: Must specify --symbols, --core-only, or --all-ready")
        sys.exit(1)

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    db = SessionLocal()
    provider = get_provider()

    summary = {
        "processed_symbols": 0,
        "updated_rows": 0,
        "pe_filled": 0,
        "pb_filled": 0,
        "market_cap_filled": 0,
        "empty": 0,
        "network_warn": 0,
        "error": 0,
    }

    records: List[Dict[str, Any]] = []

    try:
        targets = _select_targets(
            db,
            symbols=symbol_list,
            core_only=args.core_only,
            all_ready=args.all_ready,
            limit=args.limit,
        )

        if not targets:
            output = {
                "message": "No target stocks found matching the given criteria.",
                **summary,
                "dry_run": args.dry_run,
                "records": [],
            }
            print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
            return

        print(
            f"[INFO] Selected {len(targets)} target stock(s) for valuation backfill."
        )

        for stock in targets:
            summary["processed_symbols"] += 1

            try:
                # --- Step a: get latest daily_price row ---
                latest_price = (
                    db.query(DailyPrice)
                    .filter(DailyPrice.stock_id == stock.id)
                    .order_by(DailyPrice.trade_date.desc())
                    .first()
                )
                if not latest_price:
                    logger.debug("No daily_price row for %s", stock.symbol)
                    summary["empty"] += 1
                    continue

                # --- Step b: skip if already filled (unless --force) ---
                has_pe = latest_price.pe is not None
                has_pb = latest_price.pb is not None
                has_market_cap = latest_price.market_cap is not None

                if not args.force and has_pe and has_pb and has_market_cap:
                    logger.debug(
                        "%s: PE/PB/market_cap already filled, skipping", stock.symbol,
                    )
                    continue

                # --- Step c: try provider valuation data ---
                valuation: Dict[str, Any] = {}
                network_ok = True
                try:
                    valuation = provider.fetch_valuation(stock.symbol) or {}
                except Exception as exc:
                    logger.warning(
                        "Network error fetching valuation for %s: %s",
                        stock.symbol,
                        exc,
                    )
                    network_ok = False
                    summary["network_warn"] += 1

                old_pe = latest_price.pe
                old_pb = latest_price.pb
                old_market_cap = latest_price.market_cap

                new_pe: Optional[float] = valuation.get("pe")
                new_pb: Optional[float] = valuation.get("pb")
                new_market_cap: Optional[float] = valuation.get("market_cap")
                source = "provider" if valuation else "unknown"

                # --- Step d: fallback to FinancialMetric if provider returned nothing ---
                if (new_pe is None or new_pb is None) and latest_price.close:
                    fin = _compute_pe_pb_from_financials(
                        db, stock.id, latest_price.close,
                    )
                    if new_pe is None:
                        new_pe = fin.get("pe")
                    if new_pb is None:
                        new_pb = fin.get("pb")
                    if (new_pe is not None or new_pb is not None) and source == "unknown":
                        source = "financial_fallback"

                # Determine which fields actually changed
                pe_changed = new_pe is not None and (args.force or not has_pe)
                pb_changed = new_pb is not None and (args.force or not has_pb)
                mc_changed = new_market_cap is not None and (args.force or not has_market_cap)

                if not pe_changed and not pb_changed and not mc_changed:
                    logger.debug(
                        "%s: no new PE/PB/market_cap data available", stock.symbol,
                    )
                    summary["empty"] += 1
                    records.append(
                        _build_record(
                            stock.symbol,
                            latest_price.trade_date,
                            old_pe,
                            None,
                            old_pb,
                            None,
                            old_market_cap,
                            None,
                            source="none_available",
                        )
                    )
                    continue

                # --- Step e: record and update ---
                record = _build_record(
                    stock.symbol,
                    latest_price.trade_date,
                    old_pe,
                    new_pe if pe_changed else old_pe,
                    old_pb,
                    new_pb if pb_changed else old_pb,
                    old_market_cap,
                    new_market_cap if mc_changed else old_market_cap,
                    source=source,
                )
                records.append(record)

                if not args.dry_run:
                    if pe_changed:
                        latest_price.pe = new_pe
                        summary["pe_filled"] += 1
                    if pb_changed:
                        latest_price.pb = new_pb
                        summary["pb_filled"] += 1
                    if mc_changed:
                        latest_price.market_cap = new_market_cap
                        summary["market_cap_filled"] += 1
                    db.add(latest_price)
                    summary["updated_rows"] += 1

                # Sleep between API calls to avoid rate-limiting
                if args.sleep_sec > 0:
                    time.sleep(args.sleep_sec)

            except Exception as exc:
                logger.error("Error processing %s: %s", stock.symbol, exc)
                summary["error"] += 1
                # Do NOT rollback the whole transaction; just skip this stock
                continue

        # Commit all updates at once (dry-run skips this)
        if not args.dry_run:
            db.commit()
        else:
            db.rollback()

    finally:
        db.close()

    # Print summary as JSON
    output = {
        **summary,
        "dry_run": args.dry_run,
        "records": records if records else [],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
