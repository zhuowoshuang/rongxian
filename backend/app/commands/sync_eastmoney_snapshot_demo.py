"""Sync Eastmoney historical snapshot data for investor demo pool."""
from __future__ import annotations
import argparse, json, os, sys, time
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal
from app.models.stock import Stock
from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.technical_indicator import TechnicalIndicator
from app.models.stock_score import StockScore
from app.models.trade_signal import TradeSignal
from app.data_providers import get_provider
from app.services.data_credibility import DEMO_SCORE_SOURCE, DEMO_SIGNAL_SOURCE
from sqlalchemy import func
import numpy as np, statistics

CACHE_DIR = ROOT / "data_snapshots" / "eastmoney"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEMO_POOL = [
    "002415","600519","000776","600030","000858","000333","300750","601318",
    "000651","600036","000001","300059","002594","000063","603173","300866",
    "601899","000002","600900","601088","601857","002304","300760","603259",
    "688981","600276","601012","002475","000725","300274","600887","000568",
    "600809","002557","603288","000895","600600","600585","001979","600048",
    "600570","000063","002714","300498","600438","002311","300124","000100",
    "002230","600104","601166","600009","601336","000157","600690","000338",
    "601211","600196","002142","000876","600406","300433","002236","000661",
    "300450","300122","601628","601939","601398","601328","601288","002142",
    "603501","688111","300413","601668","600050","600031","000625","600809",
    "002027","601360","300408","688012","002415","600519","000858","300750",
    "601318","000333","000651","600036","600030","000001","601088","600900",
]

SUMMARY = {"processed": 0, "prices_updated": 0, "fin_updated": 0,
           "pe_filled": 0, "pb_filled": 0, "mc_filled": 0,
           "empty": 0, "network_warn": 0, "error": 0, "cached": 0}

def _cache_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol}_snapshot.json"

def _load_cache(symbol: str) -> dict | None:
    p = _cache_path(symbol)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None

def _save_cache(symbol: str, data: dict):
    _cache_path(symbol).write_text(json.dumps(data, ensure_ascii=False, default=str))

def _safe_float(v):
    if v is None or v == "-" or v == "": return None
    try: return float(v)
    except: return None

def _ema(data, period):
    m = 2/(period+1); r=[float(data[0])]
    for v in data[1:]: r.append(v*m+r[-1]*(1-m))
    return r

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--symbols", type=str)
    parser.add_argument("--demo-pool", action="store_true")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--use-cache", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.5)
    args = parser.parse_args()

    db = SessionLocal()
    provider = get_provider()
    today = date.today()

    symbols = args.symbols.split(",") if args.symbols else (DEMO_POOL[:args.limit] if args.demo_pool else DEMO_POOL[:10])
    print(f"Syncing {len(symbols)} stocks... dry_run={args.dry_run}")

    for i, sym in enumerate(symbols):
        try:
            stock = db.query(Stock).filter(Stock.symbol == sym).first()
            if not stock:
                stock = Stock(symbol=sym, name=sym, market="A_SHARE", exchange="SH" if sym.startswith("6") else "SZ", status="ACTIVE")
                if not args.dry_run: db.add(stock); db.flush()
            sid = stock.id

            # Try cache
            cached = _load_cache(sym) if args.use_cache else None

            # Fetch prices
            try:
                df = provider.fetch_daily_prices(sym, date(2025,12,1), today)
                if not df.empty:
                    new_prices = 0
                    for _, row in df.iterrows():
                        td = row["trade_date"]
                        if hasattr(td, "date"): td = td.date()
                        ex = db.query(DailyPrice).filter(DailyPrice.stock_id==sid, DailyPrice.trade_date==td).first()
                        if ex: continue
                        if args.dry_run: continue
                        dp = DailyPrice(
                            stock_id=sid, trade_date=td,
                            open=round(row.get("open",0),2) if row.get("open") else None,
                            high=round(row.get("high",0),2) if row.get("high") else None,
                            low=round(row.get("low",0),2) if row.get("low") else None,
                            close=round(row.get("close",0),2),
                            volume=round(row.get("volume",0) or 0, 0),
                            turnover=round(row.get("turnover",0) or 0, 0) if row.get("turnover") else 0,
                        )
                        db.add(dp); new_prices += 1
                    if new_prices > 0:
                        db.commit()
                        SUMMARY["prices_updated"] += new_prices
                        # Cache prices
                        lp = db.query(DailyPrice).filter(DailyPrice.stock_id==sid).order_by(DailyPrice.trade_date.desc()).all()[:120]
                        _save_cache(sym, {"prices_count": len(lp), "latest_date": str(lp[0].trade_date) if lp else None})
                        SUMMARY["cached"] += 1
            except Exception as e:
                SUMMARY["network_warn"] += 1
                if i < 3: print(f"  {sym} price fetch warn: {e}")

            # PE/PB/market_cap from financial
            lf = db.query(FinancialMetric).filter(FinancialMetric.stock_id==sid).order_by(FinancialMetric.report_period.desc()).first()
            lp = db.query(DailyPrice).filter(DailyPrice.stock_id==sid).order_by(DailyPrice.trade_date.desc()).first()
            if lf and lp and not args.dry_run:
                if lf.eps and lf.eps > 0 and (lp.pe is None or lp.pe <= 0):
                    lp.pe = round(lp.close / lf.eps, 2); SUMMARY["pe_filled"] += 1
                if lf.book_value_per_share and lf.book_value_per_share > 0 and (lp.pb is None or lp.pb <= 0):
                    lp.pb = round(lp.close / lf.book_value_per_share, 2); SUMMARY["pb_filled"] += 1
                db.commit()

            SUMMARY["processed"] += 1
            if (i+1) % 10 == 0:
                print(f"  {i+1}/{len(symbols)}: prices={SUMMARY['prices_updated']} fin={SUMMARY['fin_updated']} pe={SUMMARY['pe_filled']} pb={SUMMARY['pb_filled']}")
                db.commit()

            if not args.use_cache and args.sleep > 0:
                time.sleep(args.sleep)
        except Exception as e:
            SUMMARY["error"] += 1
            db.rollback()
            if i < 5: print(f"  {sym} error: {e}")

    db.close()
    print(json.dumps(SUMMARY, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
