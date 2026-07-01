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
from app.models.refresh_job_run import RefreshJobRun
from app.services.data_credibility import (
    DEMO_SCORE_SOURCE,
    DEMO_SIGNAL_SOURCE,
    REAL_SCORE_SOURCE,
    REAL_SIGNAL_SOURCE,
)
from app.services.real_pipeline import (
    compute_technical_indicators_for_stocks,
    generate_real_scores_for_stocks,
    generate_real_signals_for_stocks,
    refresh_financial_metrics_for_stocks,
    run_real_pipeline_sample,
    select_real_pipeline_sample_stocks,
    select_technical_refresh_universe,
    sync_core_stock_prices,
)


class FakeFrame:
    def __init__(self, rows):
        self._rows = rows

    @property
    def empty(self):
        return not self._rows

    def iterrows(self):
        for index, row in enumerate(self._rows):
            yield index, row


class FakeProvider:
    def fetch_financial_metrics(self, symbol: str):
        if symbol != "600519":
            return FakeFrame([])
        return FakeFrame(
            [
                {
                    "report_period": "2025Q4",
                    "report_date": date(2025, 12, 31),
                    "revenue": 1000,
                    "revenue_yoy": 12.5,
                    "net_profit": 300,
                    "net_profit_yoy": 18.0,
                    "gross_margin": 45.0,
                    "net_margin": 30.0,
                    "roe": 26.0,
                    "roa": 12.0,
                    "debt_ratio": 32.0,
                    "operating_cashflow": 360.0,
                    "free_cashflow": 240.0,
                    "eps": 22.0,
                    "book_value_per_share": 180.0,
                },
                {
                    "report_period": "2025Q3",
                    "report_date": date(2025, 9, 30),
                    "revenue": 900,
                    "revenue_yoy": 10.0,
                    "net_profit": 260,
                    "net_profit_yoy": 15.0,
                    "gross_margin": 43.0,
                    "net_margin": 28.0,
                    "roe": 24.0,
                    "roa": 11.0,
                    "debt_ratio": 34.0,
                    "operating_cashflow": 320.0,
                    "free_cashflow": 210.0,
                    "eps": 20.0,
                    "book_value_per_share": 170.0,
                },
            ]
        )


def _build_db():
    import app.models.user  # noqa: F401
    import app.models.report  # noqa: F401
    import app.models.watchlist  # noqa: F401
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def _seed_prices(db):
    stock_main = Stock(symbol="600519", name="茅台样本", market="A_SHARE", exchange="SH", industry="消费", status="ACTIVE")
    stock_small = Stock(symbol="000001", name="样本银行", market="A_SHARE", exchange="SZ", industry="金融", status="ACTIVE")
    stock_hk = Stock(symbol="00700", name="腾讯样本", market="HK", exchange="HK", industry="科技", status="ACTIVE")
    db.add_all([stock_main, stock_small, stock_hk])
    db.flush()

    start = date(2026, 1, 1)
    for day in range(140):
        trade_date = start + timedelta(days=day)
        close = 100 + day * 0.8
        db.add(
            DailyPrice(
                stock_id=stock_main.id,
                trade_date=trade_date,
                open=close - 1,
                high=close + 1,
                low=close - 2,
                close=close,
                pre_close=close - 0.5,
                volume=100000 + day * 100,
                turnover=1000000 + day * 1000,
                pe=25.0,
                pb=4.0,
                dividend_yield=1.5,
            )
        )
    for day in range(20):
        trade_date = start + timedelta(days=day)
        close = 20 + day * 0.2
        db.add(
            DailyPrice(
                stock_id=stock_small.id,
                trade_date=trade_date,
                open=close - 0.1,
                high=close + 0.2,
                low=close - 0.3,
                close=close,
                pre_close=close - 0.05,
                volume=50000 + day * 50,
                turnover=500000 + day * 500,
            )
        )
    for day in range(140):
        trade_date = start + timedelta(days=day)
        close = 300 + day * 1.5
        db.add(
            DailyPrice(
                stock_id=stock_hk.id,
                trade_date=trade_date,
                open=close - 1,
                high=close + 2,
                low=close - 3,
                close=close,
                pre_close=close - 0.5,
                volume=200000 + day * 100,
                turnover=2000000 + day * 1000,
            )
        )
    db.commit()

    latest_date = start + timedelta(days=139)
    db.add(
        StockScore(
            stock_id=stock_main.id,
            score_date=latest_date,
            total_score=66,
            quality_score=18,
            valuation_score=12,
            growth_score=12,
            trend_score=16,
            risk_score=8,
            rating="WATCH",
            score_source=DEMO_SCORE_SOURCE,
            reason_summary="演示评分",
        )
    )
    db.add(
        TradeSignal(
            stock_id=stock_main.id,
            signal_date=latest_date,
            signal_type="WATCH",
            signal_strength=2,
            suggested_position=0,
            signal_source=DEMO_SIGNAL_SOURCE,
            holding_period="-",
            logic_json={"reason": "演示信号"},
            risk_json={"items": ["演示"]},
            status="ACTIVE",
        )
    )
    db.commit()


def test_select_real_pipeline_sample_stocks_filters_to_a_share_with_history():
    db = _build_db()
    _seed_prices(db)

    samples = select_real_pipeline_sample_stocks(db, limit=10)

    symbols = {sample.symbol for sample in samples}
    assert "600519" in symbols
    assert all(sample.market == "A_SHARE" for sample in samples)
    main_sample = next(sample for sample in samples if sample.symbol == "600519")
    assert main_sample.price_count >= 120
    assert main_sample.selection_reason in {"core_stock", "history_60d", "watchlist", "recent_report", "recent_backtest", "industry_ready"}


def test_run_real_pipeline_sample_creates_real_scores_and_signals():
    db = _build_db()
    _seed_prices(db)

    result = run_real_pipeline_sample(db, limit=10, provider=FakeProvider())

    assert result["sample_count"] >= 1
    assert "600519" in {item["symbol"] for item in result["sample_selection"]}
    assert result["financial"]["inserted_rows"] >= 2
    assert result["technical"]["inserted_rows"] >= 1
    assert result["scores"]["created"] + result["scores"]["updated"] >= 1
    assert result["signals"]["created_or_updated"] >= 1

    real_score = db.query(StockScore).filter(StockScore.score_source == REAL_SCORE_SOURCE).one()
    real_signal = db.query(TradeSignal).filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE).one()
    assert real_score.stock_id == real_signal.stock_id
    assert db.query(StockScore).filter(StockScore.score_source == DEMO_SCORE_SOURCE).count() == 0
    assert db.query(TradeSignal).filter(TradeSignal.signal_source == DEMO_SIGNAL_SOURCE).count() == 0
    assert db.query(RefreshJobRun).count() == 1


def test_technical_indicators_generate_ma_and_volume_ratio():
    db = _build_db()
    _seed_prices(db)
    samples = select_technical_refresh_universe(db, limit=5)
    result = compute_technical_indicators_for_stocks(db, samples)
    assert result["success"] >= 1
    tech = db.query(TechnicalIndicator).first()
    assert tech.ma5 is not None
    assert tech.ma10 is not None
    assert tech.volume_ratio_5_20 is not None
    assert tech.weekly_volatility_candidate is not None
    assert tech.monthly_volatility_candidate is not None


def test_financial_zero_does_not_generate_real_score():
    db = _build_db()
    _seed_prices(db)
    samples = select_real_pipeline_sample_stocks(db, limit=5)
    compute_technical_indicators_for_stocks(db, samples)
    scores = generate_real_scores_for_stocks(db, samples)
    assert scores["success"] == 0
    assert scores["skipped_no_financial"] >= 1
    assert db.query(StockScore).filter(StockScore.score_source == REAL_SCORE_SOURCE).count() == 0


def test_demo_score_does_not_generate_real_signal():
    db = _build_db()
    _seed_prices(db)
    samples = select_real_pipeline_sample_stocks(db, limit=5)
    signals = generate_real_signals_for_stocks(db, samples)
    assert signals["skipped_demo_score"] >= 1
    assert db.query(TradeSignal).filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE).count() == 0


def test_sync_core_stock_prices_can_fill_missing_sh_price_history():
    db = _build_db()
    _seed_prices(db)
    sh_stock = db.query(Stock).filter(Stock.symbol == "600519").first()
    db.query(DailyPrice).filter(DailyPrice.stock_id == sh_stock.id).delete()
    db.commit()

    result = sync_core_stock_prices(db, provider=FakeProviderWithPrices(), limit=5)

    assert result["price_sync_success"] >= 1
    assert db.query(DailyPrice).filter(DailyPrice.stock_id == sh_stock.id).count() > 0


class FakeProviderWithPrices(FakeProvider):
    def fetch_daily_prices(self, symbol, start_date, end_date):
        rows = []
        current = start_date
        price = 100.0
        while current <= end_date and len(rows) < 40:
            rows.append(
                {
                    "trade_date": current,
                    "open": price,
                    "high": price + 1,
                    "low": price - 1,
                    "close": price + 0.5,
                    "pre_close": price - 0.5,
                    "volume": 100000,
                    "turnover": 1000000,
                    "turnover_rate": 1.0,
                    "market_cap": None,
                    "pe": None,
                    "pb": None,
                    "dividend_yield": None,
                }
            )
            current += timedelta(days=1)
            price += 1
        return FakeFrame(rows)


def test_financial_provider_failure_writes_no_fake_data():
    db = _build_db()
    _seed_prices(db)
    samples = select_real_pipeline_sample_stocks(db, limit=5)

    class FailingProvider:
        def fetch_financial_metrics(self, symbol: str):
            raise RuntimeError("provider down")

    result = refresh_financial_metrics_for_stocks(db, samples, provider=FailingProvider())
    assert result["success"] == 0
    assert result["failed"] >= 1
    assert db.query(FinancialMetric).count() == 0


def test_select_technical_universe_skips_insufficient_prices():
    db = _build_db()
    _seed_prices(db)
    samples = select_technical_refresh_universe(db, limit=10)
    symbols = {sample.symbol for sample in samples}
    assert "600519" in symbols
    assert "000001" not in symbols
