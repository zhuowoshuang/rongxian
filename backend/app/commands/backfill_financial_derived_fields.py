"""
Backfill financial derived fields (gross_margin) from local data.
gross_margin = gross_profit / revenue * 100  (if gross_profit exists)
gross_margin = (revenue - operating_cost) / revenue * 100  (if operating_cost exists)

Usage:
  python -m app.commands.backfill_financial_derived_fields --financial-covered --dry-run
  python -m app.commands.backfill_financial_derived_fields --financial-covered
"""
from __future__ import annotations
import argparse, json, logging
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.financial_metric import FinancialMetric
from app.models.stock import Stock

logger = logging.getLogger(__name__)


def _safe_float(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser(description="Backfill financial derived fields")
    parser.add_argument("--financial-covered", action="store_true", help="Only process stocks with financial data")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    parser.add_argument("--force", action="store_true", help="Overwrite existing non-null values")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(FinancialMetric)
        if not args.force:
            query = query.filter(FinancialMetric.gross_margin.is_(None))

        records = query.all()
        results = {"processed": 0, "updated": 0, "skipped": 0, "errors": 0, "dry_run": args.dry_run, "details": []}

        for fin in records:
            results["processed"] += 1
            try:
                revenue = _safe_float(fin.revenue)
                if not revenue or revenue <= 0:
                    results["skipped"] += 1
                    continue

                gross_profit = _safe_float(getattr(fin, "gross_profit", None))
                operating_cost = _safe_float(getattr(fin, "operating_cost", None))
                calculated_gm = None

                if gross_profit and gross_profit > 0:
                    calculated_gm = round(gross_profit / revenue * 100, 2)
                elif operating_cost is not None and revenue > 0:
                    gp = revenue - operating_cost
                    if gp > 0:
                        calculated_gm = round(gp / revenue * 100, 2)

                if calculated_gm is None:
                    results["skipped"] += 1
                    continue

                if not args.dry_run:
                    fin.gross_margin = calculated_gm
                    db.commit()

                results["updated"] += 1
                if len(results["details"]) < 10:
                    results["details"].append({
                        "id": fin.id, "stock_id": fin.stock_id,
                        "revenue": revenue, "gross_margin": calculated_gm,
                    })
            except Exception as e:
                results["errors"] += 1
                db.rollback()

        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
