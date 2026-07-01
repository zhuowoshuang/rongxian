"""Tests for unified data coverage service."""

from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.technical_indicator import TechnicalIndicator
from app.models.trade_signal import TradeSignal
from app.services.data_coverage import (
    get_bulk_data_coverage,
    get_stock_data_coverage,
    summarize_market_data_coverage,
)
from app.services.data_credibility import DEMO_SCORE_SOURCE, REAL_SCORE_SOURCE, REAL_SIGNAL_SOURCE


def _build_db():
    import app.models.user  # noqa: F401
    import app.models.report  # noqa: F401
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def _seed_price_only(db):
    stock = Stock(symbol="600519", name="茅台", market="A_SHARE", exchange="SH", status="ACTIVE")
    db.add(stock)
    db.flush()
    start = date(2026, 1, 1)
    for day in range(40):
        trade_date = start + timedelta(days=day)
        db.add(
            DailyPrice(
                stock_id=stock.id,
                trade_date=trade_date,
                open=100,
                high=101,
                low=99,
                close=100 + day * 0.1,
                pre_close=100,
                volume=1000,
                turnover=10000,
            )
        )
    db.commit()
    return stock


def test_price_only_coverage():
    db = _build_db()
    stock = _seed_price_only(db)
    coverage = get_stock_data_coverage(db, stock.symbol)
    assert coverage["coverage_level"] == "price_only"
    assert coverage["has_price"] is True
    assert coverage["has_financial"] is False
    assert "财务数据未刷新" in coverage["blocking_reasons"]


def test_ready_full_coverage():
    db = _build_db()
    stock = _seed_price_only(db)
    db.add(
        FinancialMetric(
            stock_id=stock.id,
            report_period="2025Q4",
            report_date=date(2025, 12, 31),
            revenue=100,
            net_profit=20,
        )
    )
    db.add(
        TechnicalIndicator(
            stock_id=stock.id,
            trade_date=date(2026, 2, 9),
            ma5=100,
            ma10=99,
            ma20=98,
        )
    )
    db.add(
        StockScore(
            stock_id=stock.id,
            score_date=date(2026, 2, 9),
            total_score=70,
            quality_score=20,
            valuation_score=12,
            growth_score=12,
            trend_score=14,
            risk_score=8,
            rating="WATCH",
            score_source=REAL_SCORE_SOURCE,
        )
    )
    db.add(
        TradeSignal(
            stock_id=stock.id,
            signal_date=date(2026, 2, 9),
            signal_type="WATCH",
            signal_strength=2,
            signal_source=REAL_SIGNAL_SOURCE,
            status="ACTIVE",
        )
    )
    db.commit()

    coverage = get_stock_data_coverage(db, stock.symbol)
    assert coverage["coverage_level"] == "ready_full"
    assert coverage["has_real_score"] is True
    assert coverage["has_real_signal"] is True


def test_bulk_coverage_and_market_summary():
    db = _build_db()
    stock = _seed_price_only(db)
    db.add(
        StockScore(
            stock_id=stock.id,
            score_date=date(2026, 2, 9),
            total_score=60,
            quality_score=15,
            valuation_score=10,
            growth_score=10,
            trend_score=10,
            risk_score=5,
            rating="WATCH",
            score_source=DEMO_SCORE_SOURCE,
        )
    )
    db.commit()

    bulk = get_bulk_data_coverage(db, [stock.symbol, "000001"])
    assert bulk[stock.symbol]["coverage_level"] == "demo_only"
    summary = summarize_market_data_coverage(db)
    assert summary["stocks_total"] == 1
    assert summary["daily_prices_stocks"] == 1
    assert summary["quick_seed_demo_scores"] == 1
