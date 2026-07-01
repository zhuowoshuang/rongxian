"""P1 tests for investor demo readiness."""
import pytest
from app.db.session import SessionLocal
from app.services.score_diagnostics import diagnose_real_scores
from app.services.research_display_summary import build_research_display_summary
from app.services.data_credibility import REAL_SCORE_SOURCE


class TestAdminScoreDiagnostics:
    """P1-1: admin/score-diagnostics must return correct real_count."""

    def test_real_count_matches_db(self):
        db = SessionLocal()
        try:
            from app.models.stock_score import StockScore
            db_count = db.query(StockScore).filter(StockScore.score_source == REAL_SCORE_SOURCE).count()
            result = diagnose_real_scores(db)
            assert result["summary"]["real_count"] == db_count
            assert result["summary"]["real_score_count"] == db_count
        finally:
            db.close()

    def test_signal_distribution_not_empty(self):
        db = SessionLocal()
        try:
            result = diagnose_real_scores(db)
            sig_dist = result.get("signal_distribution", {})
            assert len(sig_dist) > 0
            total = sum(sig_dist.values())
            assert total > 0
        finally:
            db.close()


class TestSignalsRiskObservation:
    """P1-2: signals risk_observation_items must not be empty when count > 0."""

    def test_risk_items_returned(self):
        db = SessionLocal()
        try:
            summary = build_research_display_summary(db, include_demo=False)
            diag = summary.get("diagnostics", {})
            items = diag.get("items", [])
            assert len(items) > 0
            risk_items = [i for i in items if i.get("signal_type") in ("REDUCE", "SELL")]
            assert len(risk_items) > 0
        finally:
            db.close()


class TestStockDetailNoData:
    """P1-3: 300866 should return 200 with no price data."""

    def test_300866_exists_but_no_price(self):
        from app.models.stock import Stock
        from app.models.daily_price import DailyPrice
        db = SessionLocal()
        try:
            stock = db.query(Stock).filter(Stock.symbol == "300866").first()
            assert stock is not None
            assert stock.name == "安克创新"
            price_count = db.query(DailyPrice).filter(DailyPrice.stock_id == stock.id).count()
            assert price_count == 0
        finally:
            db.close()


class TestCoreStocksRegression:
    """P1: 002415/600519 must not regress."""

    @pytest.mark.parametrize("symbol,name", [("002415", "海康威视"), ("600519", "贵州茅台")])
    def test_ready_full(self, symbol, name):
        from app.models.stock import Stock
        from app.models.daily_price import DailyPrice
        from app.models.financial_metric import FinancialMetric
        from app.models.technical_indicator import TechnicalIndicator
        from app.models.stock_score import StockScore
        db = SessionLocal()
        try:
            stock = db.query(Stock).filter(Stock.symbol == symbol).first()
            assert stock is not None
            assert stock.name == name
            prices = db.query(DailyPrice).filter(DailyPrice.stock_id == stock.id).count()
            fins = db.query(FinancialMetric).filter(FinancialMetric.stock_id == stock.id).count()
            techs = db.query(TechnicalIndicator).filter(TechnicalIndicator.stock_id == stock.id).count()
            scores = db.query(StockScore).filter(
                StockScore.stock_id == stock.id, StockScore.score_source == REAL_SCORE_SOURCE
            ).count()
            assert prices >= 60, f"{symbol} prices={prices} < 60"
            assert fins >= 4, f"{symbol} fins={fins} < 4"
            assert techs >= 1, f"{symbol} techs={techs} < 1"
            assert scores >= 1, f"{symbol} real_scores={scores} < 1"
        finally:
            db.close()
