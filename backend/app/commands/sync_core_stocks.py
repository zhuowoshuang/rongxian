from __future__ import annotations

import argparse
import json

from app.data_providers import get_provider
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.services.data_coverage import CORE_STOCKS, get_bulk_data_coverage
from app.services.real_pipeline import (
    backfill_latest_valuation_ratios,
    compute_technical_indicators_for_stocks,
    generate_real_scores_for_stocks,
    generate_real_signals_for_stocks,
    refresh_financial_metrics_for_stocks,
    select_real_pipeline_sample_stocks,
    sync_core_stock_prices,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync core stocks and run the real data chain.")
    parser.add_argument("--limit", type=int, default=30, help="Maximum core stocks to attempt.")
    args = parser.parse_args()

    import app.models.refresh_job_run  # noqa: F401
    import app.models.watchlist  # noqa: F401

    Base.metadata.create_all(bind=engine)
    provider = get_provider()

    db = SessionLocal()
    try:
        price_sync = sync_core_stock_prices(db, provider=provider, limit=min(args.limit, len(CORE_STOCKS)))
        samples = [sample for sample in select_real_pipeline_sample_stocks(db, limit=max(args.limit, 15)) if sample.symbol in CORE_STOCKS][: args.limit]
        financial = refresh_financial_metrics_for_stocks(db, samples, provider=provider)
        technical = compute_technical_indicators_for_stocks(db, samples)
        valuation = backfill_latest_valuation_ratios(db, samples)
        scores = generate_real_scores_for_stocks(db, samples)
        signals = generate_real_signals_for_stocks(db, samples)
        coverage = get_bulk_data_coverage(db, CORE_STOCKS)
        print(
            json.dumps(
                {
                    "core_stock_count": len(CORE_STOCKS),
                    "price_sync_attempted": price_sync.get("price_sync_attempted", 0),
                    "price_sync_success": price_sync.get("price_sync_success", 0),
                    "price_sync_failed": price_sync.get("price_sync_failed", 0),
                    "financial_success": financial.get("success", 0),
                    "technical_success": technical.get("success", 0),
                    "valuation_pe_updated": valuation.get("updated_pe", 0),
                    "valuation_pb_updated": valuation.get("updated_pb", 0),
                    "real_scores_success": scores.get("success", 0),
                    "real_signals_success": signals.get("success", 0),
                    "sample_selection": [{"symbol": sample.symbol, "reason": sample.selection_reason} for sample in samples],
                    "600519_status": coverage.get("600519"),
                    "failure_reasons": {
                        "price_sync": price_sync.get("failure_reasons", {}),
                        "financial": financial.get("failure_reasons", {}),
                        "technical": technical.get("failure_reasons", {}),
                        "scores": scores.get("failure_reasons", {}),
                        "signals": signals.get("failure_reasons", {}),
                    },
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
