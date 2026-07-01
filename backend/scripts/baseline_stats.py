"""One-off baseline data coverage stats."""
from sqlalchemy import func, text
from app.db.session import SessionLocal
from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.technical_indicator import TechnicalIndicator
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.trade_signal import TradeSignal
from app.models.report import Report
from app.services.data_credibility import REAL_SCORE_SOURCE, DEMO_SCORE_SOURCE, REAL_SIGNAL_SOURCE, DEMO_SIGNAL_SOURCE

db = SessionLocal()
try:
    stocks = db.query(Stock).count()
    prices = db.query(DailyPrice).count()
    price_stocks = db.query(func.count(func.distinct(DailyPrice.stock_id))).scalar()
    latest_price = db.query(func.max(DailyPrice.trade_date)).scalar()

    for threshold in [30, 60, 120]:
        cnt = db.execute(
            text("SELECT COUNT(*) FROM (SELECT stock_id FROM daily_prices GROUP BY stock_id HAVING COUNT(*) >= :t)"),
            {"t": threshold},
        ).scalar()
        print(f"price_stocks>={threshold}: {cnt}")

    fm = db.query(FinancialMetric).count()
    fm_stocks = db.query(func.count(func.distinct(FinancialMetric.stock_id))).scalar()
    latest_fm = db.query(func.max(FinancialMetric.report_period)).scalar()

    ti = db.query(TechnicalIndicator).count()
    ti_stocks = db.query(func.count(func.distinct(TechnicalIndicator.stock_id))).scalar()
    latest_ti = db.query(func.max(TechnicalIndicator.trade_date)).scalar()

    real_scores = db.query(StockScore).filter(StockScore.score_source == REAL_SCORE_SOURCE).count()
    demo_scores = db.query(StockScore).filter(StockScore.score_source == DEMO_SCORE_SOURCE).count()
    real_signals = db.query(TradeSignal).filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE).count()
    demo_signals = db.query(TradeSignal).filter(TradeSignal.signal_source == DEMO_SIGNAL_SOURCE).count()

    reports = db.query(Report).count()

    has_bt = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='backtest_tasks'")).scalar()
    bt = db.execute(text("SELECT COUNT(*) FROM backtest_tasks")).scalar() if has_bt else 0
    has_wl = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='watchlist_items'")).scalar()
    wl = db.execute(text("SELECT COUNT(*) FROM watchlist_items")).scalar() if has_wl else 0

    print(f"stocks: {stocks}")
    print(f"daily_prices: {prices}")
    print(f"daily_prices_stocks: {price_stocks}")
    print(f"latest_price_date: {latest_price}")
    print(f"financial_metrics: {fm}")
    print(f"financial_metrics_stocks: {fm_stocks}")
    print(f"latest_financial_period: {latest_fm}")
    print(f"technical_indicators: {ti}")
    print(f"technical_indicators_stocks: {ti_stocks}")
    print(f"latest_technical_date: {latest_ti}")
    print(f"real_calculated_scores: {real_scores}")
    print(f"quick_seed_demo_scores: {demo_scores}")
    print(f"real_calculated_signals: {real_signals}")
    print(f"quick_seed_demo_signals: {demo_signals}")
    print(f"reports: {reports}")
    print(f"backtest_tasks: {bt}")
    print(f"watchlist_items: {wl}")
finally:
    db.close()
