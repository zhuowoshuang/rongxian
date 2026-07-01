"""
Development-only helper that writes demo scores/signals into official tables.

This script is intentionally isolated:
- default execution is rejected
- production execution is rejected
- rows written by this script are always tagged as quick_seed_demo
- cleanup only removes prior quick_seed_demo rows for today
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import func, inspect

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal
from app.models.daily_price import DailyPrice
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.trade_signal import TradeSignal
from app.services.data_credibility import DEMO_SCORE_SOURCE, DEMO_SIGNAL_SOURCE
from app.services.signal import determine_signal_type
from app.stock_universe import get_all_stocks

random.seed(42)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write demo-only random scores and signals.")
    parser.add_argument("--demo", action="store_true", help="explicitly allow demo random writes")
    parser.add_argument("--allow-demo-random", action="store_true", help="alias of --demo")
    return parser.parse_args()


def _ensure_allowed(args: argparse.Namespace) -> None:
    if not (args.demo or args.allow_demo_random):
        raise SystemExit("拒绝执行：必须显式传入 --demo 或 --allow-demo-random。")

    app_env = os.environ.get("APP_ENV", "development").lower()
    use_mock = os.environ.get("MOCK_DATA", "false").lower() in {"1", "true", "yes", "on"}
    if app_env == "production":
        raise SystemExit("拒绝执行：production 环境禁止写入演示随机评分。")
    if app_env not in {"development", "dev", "local", "test"} and not use_mock:
        raise SystemExit("拒绝执行：仅允许 development/test 或 MOCK_DATA=true 环境运行。")


def _ensure_source_columns(db) -> None:
    inspector = inspect(db.get_bind())
    stock_score_cols = {item["name"] for item in inspector.get_columns("stock_scores")}
    trade_signal_cols = {item["name"] for item in inspector.get_columns("trade_signals")}
    if "score_source" not in stock_score_cols:
        raise SystemExit("拒绝执行：stock_scores.score_source 字段不存在，请先启动后端完成 schema patch。")
    if "signal_source" not in trade_signal_cols:
        raise SystemExit("拒绝执行：trade_signals.signal_source 字段不存在，请先启动后端完成 schema patch。")


def _demo_reason(text: str) -> str:
    clean = (text or "").strip()
    return clean if clean.startswith("[DEMO]") else f"[DEMO] {clean}"


def generate() -> None:
    args = _parse_args()
    _ensure_allowed(args)

    print("仅用于开发演示，不可作为真实评分。")

    db = SessionLocal()
    today = date.today()
    try:
        _ensure_source_columns(db)

        deleted_signals = (
            db.query(TradeSignal)
            .filter(TradeSignal.signal_date == today, TradeSignal.signal_source == DEMO_SIGNAL_SOURCE)
            .delete(synchronize_session=False)
        )
        deleted_scores = (
            db.query(StockScore)
            .filter(StockScore.score_date == today, StockScore.score_source == DEMO_SCORE_SOURCE)
            .delete(synchronize_session=False)
        )
        db.commit()
        print(f"清理今日旧演示数据：scores={deleted_scores}, signals={deleted_signals}")

        core_stocks = get_all_stocks()
        core_symbols = {item["symbol"] for item in core_stocks}

        priced = (
            db.query(DailyPrice.stock_id, func.count().label("cnt"))
            .group_by(DailyPrice.stock_id)
            .having(func.count() >= 20)
            .all()
        )
        priced_ids = {row[0] for row in priced}
        all_stocks = db.query(Stock).filter(Stock.status == "ACTIVE").all()

        tier1: list[Stock] = []
        tier2: list[Stock] = []
        tier3: list[Stock] = []
        for stock in all_stocks:
            if stock.symbol in core_symbols and stock.id in priced_ids:
                tier1.append(stock)
            elif stock.id in priced_ids:
                tier2.append(stock)
            else:
                tier3.append(stock)

        selected = tier1.copy()
        if tier2:
            selected += random.sample(tier2, min(200, len(tier2)))
        if tier3:
            selected += random.sample(tier3, min(100, len(tier3)))

        premium = {
            "600519", "000858", "000568", "600809", "600887",
            "300750", "002594", "601012", "688981",
            "600276", "300760", "000661", "603259",
            "000002", "001979", "600048", "600585",
            "601318", "600036", "000333",
            "300059", "002415", "600570", "000063",
            "601899", "600900", "601088", "601857",
        }

        score_count = 0
        signal_count = 0

        for stock in selected:
            roll = random.random()
            is_premium = stock.symbol in premium

            if is_premium or roll < 0.22:
                quality = random.uniform(22, 29)
                valuation = random.uniform(12, 19)
                growth = random.uniform(14, 19)
                trend = random.uniform(12, 19)
                risk = random.uniform(7, 9.5)
            elif roll < 0.55:
                quality = random.uniform(16, 24)
                valuation = random.uniform(10, 16)
                growth = random.uniform(10, 17)
                trend = random.uniform(10, 17)
                risk = random.uniform(6, 8.5)
            elif roll < 0.85:
                quality = random.uniform(12, 20)
                valuation = random.uniform(8, 14)
                growth = random.uniform(8, 14)
                trend = random.uniform(8, 14)
                risk = random.uniform(4, 7)
            else:
                quality = random.uniform(8, 16)
                valuation = random.uniform(4, 10)
                growth = random.uniform(4, 10)
                trend = random.uniform(4, 10)
                risk = random.uniform(2, 5)

            total = max(0, min(100, quality + valuation + growth + trend + risk))
            if total >= 80:
                rating = "BUY"
            elif total >= 70:
                rating = "ADD"
            elif total >= 55:
                rating = "WATCH"
            elif total >= 40:
                rating = "REDUCE"
            else:
                rating = "SELL"

            score = StockScore(
                stock_id=stock.id,
                score_date=today,
                total_score=round(total, 1),
                quality_score=round(quality, 1),
                valuation_score=round(valuation, 1),
                growth_score=round(growth, 1),
                trend_score=round(trend, 1),
                risk_score=round(risk, 1),
                rating=rating,
                score_source=DEMO_SCORE_SOURCE,
                reason_summary=_demo_reason(f"{stock.name} 五维综合评分{rating}，仅用于开发演示"),
            )
            db.add(score)
            db.flush()

            sig_type, strength, logic = determine_signal_type(score)
            signal = TradeSignal(
                stock_id=stock.id,
                signal_date=today,
                signal_type=sig_type,
                signal_strength=strength,
                suggested_position=round(random.uniform(5, 15), 1) if sig_type in ("BUY", "ADD") else 0,
                entry_price=round(random.uniform(10, 200), 2),
                target_price=round(random.uniform(12, 240), 2),
                stop_loss_price=round(random.uniform(8, 180), 2),
                holding_period="中长期" if sig_type in ("BUY", "ADD") else "观察",
                signal_source=DEMO_SIGNAL_SOURCE,
                logic_json={"reason": _demo_reason(logic)},
                risk_json={"items": ["[DEMO] 模型输出仅供研究参考，不构成投资建议", f"[DEMO] {stock.name} 需结合基本面变化独立判断"]},
                status="ACTIVE",
            )
            db.add(signal)

            score_count += 1
            signal_count += 1
            if score_count % 100 == 0:
                db.commit()
                print(f"progress: {score_count}/{len(selected)}")

        db.commit()
        print(f"done: generated {score_count} demo scores and {signal_count} demo signals for {today}")
    finally:
        db.close()


if __name__ == "__main__":
    generate()
