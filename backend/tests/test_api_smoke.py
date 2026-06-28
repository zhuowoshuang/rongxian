from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.report import Report
from app.models.research_report import ResearchReport
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.technical_indicator import TechnicalIndicator
from app.models.trade_signal import TradeSignal
from app.models.user import User


def _build_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    admin = User(username="admin", password_hash=hash_password("AdminPass123"), display_name="Admin", role="admin")
    analyst = User(username="analyst", password_hash=hash_password("AnalystPass123"), display_name="Analyst", role="analyst")
    user = User(username="viewer", password_hash=hash_password("ViewerPass123"), display_name="Viewer", role="user")
    db.add_all([admin, analyst, user])
    db.flush()

    stock = Stock(symbol="600519", name="测试样本", market="A_SHARE", exchange="SH", industry="消费", sector="白酒", status="ACTIVE")
    db.add(stock)
    db.flush()

    db.add_all(
        [
            DailyPrice(
                stock_id=stock.id,
                trade_date=date(2026, 1, 2),
                open=100,
                high=110,
                low=99,
                close=108,
                pre_close=100,
                volume=100000,
                turnover=1000000,
                pe=20,
                pb=3,
                market_cap=1000000000,
                dividend_yield=2.5,
            ),
            DailyPrice(
                stock_id=stock.id,
                trade_date=date(2026, 1, 3),
                open=108,
                high=112,
                low=107,
                close=111,
                pre_close=108,
                volume=120000,
                turnover=1200000,
                pe=21,
                pb=3.1,
                market_cap=1010000000,
                dividend_yield=2.6,
            ),
            FinancialMetric(
                stock_id=stock.id,
                report_period="2025Q4",
                report_date=date(2026, 1, 1),
                revenue=100,
                revenue_yoy=12,
                net_profit=20,
                net_profit_yoy=15,
                gross_margin=45,
                net_margin=18,
                roe=22,
                roa=10,
                debt_ratio=35,
                operating_cashflow=30,
                free_cashflow=22,
                eps=5.5,
                book_value_per_share=35,
            ),
            FinancialMetric(
                stock_id=stock.id,
                report_period="2025Q3",
                report_date=date(2025, 10, 1),
                revenue=90,
                revenue_yoy=10,
                net_profit=18,
                net_profit_yoy=12,
                gross_margin=43,
                net_margin=17,
                roe=20,
                roa=9,
                debt_ratio=36,
                operating_cashflow=28,
                free_cashflow=20,
                eps=5.0,
                book_value_per_share=33,
            ),
            TechnicalIndicator(
                stock_id=stock.id,
                trade_date=date(2026, 1, 3),
                ma20=105,
                ma60=98,
                ma120=90,
                macd=1.2,
                macd_signal=0.8,
                macd_hist=0.4,
                rsi14=61,
                boll_upper=115,
                boll_middle=105,
                boll_lower=95,
                volume_ma5=110000,
                volume_ma20=100000,
            ),
            StockScore(
                stock_id=stock.id,
                score_date=date(2026, 1, 3),
                total_score=82,
                quality_score=24,
                valuation_score=16,
                growth_score=17,
                trend_score=16,
                risk_score=9,
                rating="BUY",
                reason_summary="建议买入，目标价上调。",
            ),
            TradeSignal(
                stock_id=stock.id,
                signal_date=date(2026, 1, 3),
                signal_type="BUY",
                signal_strength=4,
                suggested_position=25,
                entry_price=110,
                target_price=125,
                stop_loss_price=98,
                holding_period="1-3 months",
                logic_json={"reason": "建议买入并加仓"},
                risk_json={"items": ["高估值回撤风险"]},
                status="ACTIVE",
            ),
            Report(
                report_date=date(2026, 1, 3),
                report_type="DAILY",
                style="steady",
                title="测试日报",
                summary="研究摘要",
                content_markdown="## 研究结论\n建议买入仅用于测试",
                content_json={"ok": True},
            ),
            ResearchReport(
                info_code="RR-1",
                title="机构研究样本",
                stock_code="600519",
                stock_name="测试样本",
                org_name="测试机构",
                publish_date=date(2026, 1, 2),
                rating="买入",
                industry="消费",
                researcher="研究员A",
                url="https://example.com/report",
            ),
        ]
    )
    db.commit()
    db.close()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_login_success():
    client = _build_client()
    response = client.post("/api/auth/login", json={"username": "admin", "password": "AdminPass123"})
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_unauthenticated_signals_blocked():
    client = _build_client()
    response = client.get("/api/signals")
    assert response.status_code == 401


def test_non_admin_cannot_access_admin_routes():
    client = _build_client()
    token = _login(client, "viewer", "ViewerPass123")
    response = client.get("/api/admin/system-status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_admin_can_access_system_status():
    client = _build_client()
    token = _login(client, "admin", "AdminPass123")
    response = client.get("/api/admin/system-status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert "counts" in response.json()


def test_pools_returns_rule_metadata():
    client = _build_client()
    response = client.get("/api/pools?type=quality")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["rules"]
    assert body["meta"]["research_only"] is True


def test_stock_detail_returns_traceability_fields():
    client = _build_client()
    response = client.get("/api/stocks/600519")
    assert response.status_code == 200
    body = response.json()
    assert body["data_source"]["scores"] == "数据库评分表（stock_scores）"
    assert "trace" in body["score"]
    assert "missing_fields" in body


def test_report_pdf_download_available():
    client = _build_client()
    token = _login(client, "admin", "AdminPass123")
    response = client.get("/api/reports/1/pdf", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 100


def test_backtest_out_of_range_returns_error():
    client = _build_client()
    token = _login(client, "analyst", "AnalystPass123")
    response = client.post(
        "/api/backtest/run",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "strategy": "quality",
            "market": "A_SHARE",
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "rebalance": "monthly",
            "initial_capital": 1000000,
        },
    )
    assert response.status_code == 400
