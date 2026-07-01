from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import create_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.report import Report
from app.models.report import ReportEvent, BacktestTask
from app.models.research_report import ResearchReport
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.technical_indicator import TechnicalIndicator
from app.models.trade_signal import TradeSignal
from app.models.user import User
from app.models.api_config import UserApiQuota, UserApiConfig, OperationLog
from app.services.data_credibility import (
    DEMO_SCORE_SOURCE,
    DEMO_SIGNAL_SOURCE,
    REAL_SCORE_SOURCE,
    REAL_SIGNAL_SOURCE,
    mark_existing_scores_as_demo,
)


def _build_client():
    # Ensure newer audit/quota models are registered in metadata before creating the in-memory schema.
    from app.models.api_config import OperationLog as _OperationLog  # noqa: F401
    from app.core.redis import _memory_rate_limit_store

    _memory_rate_limit_store.clear()

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    _OperationLog.__table__.create(bind=engine, checkfirst=True)

    db = TestingSessionLocal()
    admin = User(username="admin", password_hash=hash_password("AdminPass123"), display_name="Admin", role="admin")
    analyst = User(username="analyst", password_hash=hash_password("AnalystPass123"), display_name="Analyst", role="analyst")
    user = User(username="viewer", password_hash=hash_password("ViewerPass123"), display_name="Viewer", role="user")
    other_user = User(username="other", password_hash=hash_password("OtherPass123"), display_name="Other", role="user")
    db.add_all([admin, analyst, user, other_user])
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
                ma5=109,
                ma10=107,
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
                volume_ratio_5_20=1.1,
                weekly_volatility_candidate=12.5,
                monthly_volatility_candidate=18.2,
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
                score_source=REAL_SCORE_SOURCE,
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
                signal_source=REAL_SIGNAL_SOURCE,
                logic_json={"reason": "建议买入并加仓"},
                risk_json={"items": ["高估值回撤风险"]},
                status="ACTIVE",
            ),
            Report(
                user_id=user.id,
                report_date=date(2026, 1, 3),
                report_type="DAILY",
                style="steady",
                title="测试日报",
                summary="研究摘要",
                content_markdown="## 研究结论\n建议买入仅用于测试",
                content_json={"ok": True},
            ),
            Report(
                user_id=other_user.id,
                report_date=date(2026, 1, 3),
                report_type="STOCK",
                style="steady",
                stock_code="600519",
                stock_name="测试样本",
                title="Other user report",
                summary="private",
                content_markdown="private",
                content_json={"ok": True},
            ),
            UserApiConfig(owner_user_id=other_user.id, name="Other config", provider="openai", base_url="https://api.example.com", model_name="gpt-test"),
            BacktestTask(user_id=other_user.id, stock_code="600519", stock_name="测试样本", market="A_SHARE", strategy="qingshu_1_short", start_date="2026-01-02", end_date="2026-01-03", status="success", result_json="{}"),
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


def _db_session_from_client(client: TestClient):
    override = app.dependency_overrides[get_db]
    gen = override()
    db = next(gen)
    return db, gen


def test_login_success():
    client = _build_client()
    response = client.post("/api/auth/login", json={"username": "admin", "password": "AdminPass123"})
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_admin_and_analyst_login_success():
    client = _build_client()
    admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "AdminPass123"})
    analyst_login = client.post("/api/auth/login", json={"username": "analyst", "password": "AnalystPass123"})
    assert admin_login.status_code == 200
    assert analyst_login.status_code == 200
    assert admin_login.json()["role"] == "admin"
    assert analyst_login.json()["role"] == "analyst"


def test_register_and_login_by_phone_or_user_id():
    client = _build_client()
    payload = {"phone": "13900001111", "user_id": "清数用户", "password": "ViewerPass123", "confirm_password": "ViewerPass123"}
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 200
    assert response.json()["user_id"] == "清数用户"
    phone_login = client.post("/api/auth/login", json={"identifier": "13900001111", "password": "ViewerPass123"})
    assert phone_login.status_code == 200
    id_login = client.post("/api/auth/login", json={"identifier": "清数用户", "password": "ViewerPass123"})
    assert id_login.status_code == 200


def test_user_api_config_is_saved_and_masked():
    client = _build_client()
    token = _login(client, "viewer", "ViewerPass123")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/profile/api-configs",
        headers=headers,
        json={"name": "主模型", "provider": "openai", "base_url": "https://api.example.com", "api_key": "sk-testabcd", "model_name": "gpt-test", "is_default": True},
    )
    assert response.status_code == 200
    assert response.json()["api_key"] == "sk-***abcd"
    listing = client.get("/api/profile/api-configs", headers=headers)
    assert listing.status_code == 200
    assert listing.json()[0]["api_key"] == "sk-***abcd"
    forbidden = client.get("/api/admin/api-configs", headers=headers)
    assert forbidden.status_code == 403


def test_unauthenticated_signals_blocked():
    client = _build_client()
    response = client.get("/api/signals")
    assert response.status_code == 401


def test_non_admin_cannot_access_admin_routes():
    client = _build_client()
    token = _login(client, "viewer", "ViewerPass123")
    response = client.get("/api/admin/system-status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_analyst_cannot_access_admin_routes():
    client = _build_client()
    token = _login(client, "analyst", "AnalystPass123")
    response = client.get("/api/admin/system-status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_admin_can_access_system_status():
    client = _build_client()
    token = _login(client, "admin", "AdminPass123")
    response = client.get("/api/admin/system-status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert "counts" in response.json()


def test_permission_denied_is_audited_for_admin_attack_path():
    client = _build_client()
    token = _login(client, "viewer", "ViewerPass123")
    response = client.get("/api/admin/system-status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    admin_token = _login(client, "admin", "AdminPass123")
    audit = client.get("/api/admin/audit-logs?action=permission_denied", headers={"Authorization": f"Bearer {admin_token}"})
    assert audit.status_code == 200
    assert audit.json()["total"] >= 1


def test_pools_returns_rule_metadata():
    client = _build_client()
    response = client.get("/api/pools?type=quality")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["rules"]
    assert body["meta"]["research_only"] is True
    assert body["meta"]["display_limit"] == 30


def test_stock_search_supports_chinese_name():
    client = _build_client()
    db, gen = _db_session_from_client(client)
    try:
        extra = Stock(symbol="002415", name="海康威视", market="A_SHARE", exchange="SZ", industry="安防", status="ACTIVE")
        extra2 = Stock(symbol="300866", name="安克创新", market="A_SHARE", exchange="SZ", industry="消费电子", status="ACTIVE")
        db.add_all([extra, extra2])
        db.commit()
    finally:
        db.close()
        gen.close()

    hik = client.get("/api/stocks/search?keyword=海康威视")
    anker = client.get("/api/stocks/search?keyword=安克创新")
    assert hik.status_code == 200
    assert anker.status_code == 200
    assert any(item["symbol"] == "002415" for item in hik.json())
    assert any(item["symbol"] == "300866" for item in anker.json())


def test_stock_detail_returns_traceability_fields():
    client = _build_client()
    response = client.get("/api/stocks/600519")
    assert response.status_code == 200
    body = response.json()
    assert body["data_source"]["scores"] == "数据库评分表（stock_scores）"
    assert "trace" in body["score"]
    assert "missing_fields" in body
    assert body["technical_indicators"]["ma5"] == 109
    assert body["technical_indicators"]["ma10"] == 107
    assert body["technical_indicators"]["volume_ratio_5_20"] == 1.1
    assert "trend_score_v2" in body["technical_indicators"]
    assert body["score"]["trend_v2"] is not None
    assert "analysis_status" in body
    assert body["score"]["score_source"] == REAL_SCORE_SOURCE
    assert body["data_readiness"]["score_is_real"] is True
    assert body["data_readiness"]["readiness_level"] == "ready_full"


def test_mark_existing_scores_as_demo_marks_unknown_legacy_only():
    client = _build_client()
    db, gen = _db_session_from_client(client)
    try:
        stock = db.query(Stock).filter(Stock.symbol == "600519").first()
        legacy_score = StockScore(
            stock_id=stock.id,
            score_date=date(2026, 1, 2),
            total_score=55,
            quality_score=15,
            valuation_score=10,
            growth_score=10,
            trend_score=10,
            risk_score=10,
            rating="WATCH",
            score_source=None,
            reason_summary="legacy",
        )
        legacy_signal = TradeSignal(
            stock_id=stock.id,
            signal_date=date(2026, 1, 2),
            signal_type="WATCH",
            signal_strength=2,
            suggested_position=0,
            signal_source=None,
            status="ACTIVE",
        )
        db.add_all([legacy_score, legacy_signal])
        db.commit()
        result = mark_existing_scores_as_demo(db)
        assert result["score_marked_count"] >= 1
        assert result["signal_marked_count"] >= 1
        assert db.query(StockScore).filter(StockScore.id == legacy_score.id).first().score_source == DEMO_SCORE_SOURCE
        assert db.query(TradeSignal).filter(TradeSignal.id == legacy_signal.id).first().signal_source == DEMO_SIGNAL_SOURCE
        assert db.query(StockScore).filter(StockScore.rating == "BUY").first().score_source == REAL_SCORE_SOURCE
    finally:
        db.close()
        gen.close()


def test_quick_seed_scores_default_rejects_without_demo_flag(monkeypatch):
    from quick_seed_scores import _ensure_allowed

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("MOCK_DATA", "true")
    with pytest.raises(SystemExit):
        _ensure_allowed(SimpleNamespace(demo=False, allow_demo_random=False))


def test_signals_default_excludes_demo_and_include_demo_can_show_it():
    client = _build_client()
    db, gen = _db_session_from_client(client)
    try:
        stock = db.query(Stock).filter(Stock.symbol == "600519").first()
        db.add(
            TradeSignal(
                stock_id=stock.id,
                signal_date=date(2026, 1, 3),
                signal_type="SELL",
                signal_strength=5,
                suggested_position=0,
                signal_source=DEMO_SIGNAL_SOURCE,
                status="ACTIVE",
            )
        )
        db.commit()
    finally:
        db.close()
        gen.close()

    token = _login(client, "viewer", "ViewerPass123")
    headers = {"Authorization": f"Bearer {token}"}
    default_response = client.get("/api/signals", headers=headers)
    assert default_response.status_code == 200
    default_body = default_response.json()
    assert default_body["total"] == 1
    assert all(item["signal_source"] == REAL_SIGNAL_SOURCE for item in default_body["items"])

    demo_response = client.get("/api/signals?include_demo=true", headers=headers)
    assert demo_response.status_code == 200
    demo_body = demo_response.json()
    assert demo_body["total"] >= 2
    assert any(item["signal_source"] == DEMO_SIGNAL_SOURCE for item in demo_body["items"])


def test_signals_returns_risk_observation_summary_when_formal_items_empty():
    client = _build_client()
    db, gen = _db_session_from_client(client)
    try:
        signal = db.query(TradeSignal).filter(TradeSignal.signal_type == "BUY").first()
        signal.signal_type = "SELL"
        db.commit()
    finally:
        db.close()
        gen.close()

    token = _login(client, "viewer", "ViewerPass123")
    response = client.get("/api/signals", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["risk_observation_count"] >= 1
    assert "risk_observation_summary" in body
    assert body["meta"]["summary"]["formal_signal_count"] == 0


def test_dashboard_meta_returns_counts_and_mode():
    client = _build_client()
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["real_score_count"] >= 1
    assert body["meta"]["real_signal_count"] >= 1
    assert body["meta"]["data_mode"] in {"real_ready", "real_partial", "price_only", "demo_contaminated", "unknown"}
    assert body["meta"]["launch_data_status"] in {"ready_for_internal", "limited_real_data", "data_quality_limited", "demo_only", "not_ready"}
    assert "avg_total_score" in body["meta"]
    assert "low_score_reasons" in body["meta"]


def test_dashboard_cache_hit_and_fallback(monkeypatch):
    import app.api.dashboard as dashboard_api

    dashboard_api._clear_dashboard_cache()
    client = _build_client()

    first = client.get("/api/dashboard")
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["meta"]["cache"]["hit"] is False
    assert first_body["meta"]["cache"]["fallback_used"] is False
    assert first_body["meta"]["cache"]["generated_at"]

    second = client.get("/api/dashboard")
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["meta"]["cache"]["hit"] is True
    assert second_body["meta"]["cache"]["fallback_used"] is False

    cache_key = next(iter(dashboard_api._dashboard_summary_cache.keys()))
    dashboard_api._dashboard_summary_cache[cache_key]["expires_at"] = datetime.now() - timedelta(seconds=1)
    monkeypatch.setattr(dashboard_api, "get_dashboard_data", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    fallback = client.get("/api/dashboard")
    assert fallback.status_code == 200
    fallback_body = fallback.json()
    assert fallback_body["meta"]["cache"]["hit"] is False
    assert fallback_body["meta"]["cache"]["fallback_used"] is True
    assert fallback_body["meta"]["cache"]["stale"] is True
    assert "Traceback" not in fallback.text


def test_pools_default_excludes_demo_scores():
    client = _build_client()
    db, gen = _db_session_from_client(client)
    try:
        score = db.query(StockScore).filter(StockScore.score_date == date(2026, 1, 3)).first()
        score.score_source = DEMO_SCORE_SOURCE
        db.commit()
    finally:
        db.close()
        gen.close()
    response = client.get("/api/pools?type=quality")
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["message"]
    assert "diagnostics" in response.json()
    assert "demo_score_count" in response.json()["diagnostics"]


def test_stock_library_summary_exposes_result_counts():
    client = _build_client()
    token = _login(client, "viewer", "ViewerPass123")
    response = client.get("/api/stocks?page=1&page_size=1", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["current_result_count"] >= 1
    assert body["summary"]["current_page_count"] == len(body["items"])


def test_score_diagnostics_returns_summary_and_single_stock_trace():
    client = _build_client()
    token = _login(client, "admin", "AdminPass123")
    headers = {"Authorization": f"Bearer {token}"}
    diagnostics = client.get("/api/stocks/diagnostics", headers=headers)
    assert diagnostics.status_code == 200
    body = diagnostics.json()
    assert body["summary"]["real_count"] >= 1
    assert body["summary"]["launch_data_status"] in {"ready_for_internal", "limited_real_data", "data_quality_limited", "demo_only", "not_ready"}
    assert "avg_quality_score" in body["summary"]
    assert isinstance(body["low_score_reasons"], list)

    detail = client.get("/api/stocks/600519", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["diagnostics"]["primary_low_score_reason"]


def test_signals_returns_diagnostics_when_no_formal_signal():
    client = _build_client()
    db, gen = _db_session_from_client(client)
    try:
        signal = db.query(TradeSignal).filter(TradeSignal.signal_type == "BUY").first()
        signal.signal_type = "SELL"
        db.commit()
    finally:
        db.close()
        gen.close()

    token = _login(client, "viewer", "ViewerPass123")
    response = client.get("/api/signals", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["message"]
    assert body["diagnostics"]["avoid_observation_count"] >= 1


def test_report_generation_downgrades_demo_backed_stock_report():
    client = _build_client()
    db, gen = _db_session_from_client(client)
    try:
        stock = db.query(Stock).filter(Stock.symbol == "600519").first()
        score = db.query(StockScore).filter(StockScore.stock_id == stock.id).first()
        score.score_source = DEMO_SCORE_SOURCE
        db.commit()
    finally:
        db.close()
        gen.close()

    token = _login(client, "admin", "AdminPass123")
    response = client.post("/api/reports/generate?report_type=STOCK&stock_symbol=600519", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["report_data_status"] in {"demo_backed", "data_insufficient"}


def test_system_status_returns_real_and_demo_counts():
    client = _build_client()
    db, gen = _db_session_from_client(client)
    try:
        stock = db.query(Stock).filter(Stock.symbol == "600519").first()
        db.add(
            StockScore(
                stock_id=stock.id,
                score_date=date(2026, 1, 2),
                total_score=61,
                quality_score=18,
                valuation_score=11,
                growth_score=11,
                trend_score=11,
                risk_score=10,
                rating="WATCH",
                score_source=DEMO_SCORE_SOURCE,
                reason_summary="demo status row",
            )
        )
        db.add(
            TradeSignal(
                stock_id=stock.id,
                signal_date=date(2026, 1, 2),
                signal_type="WATCH",
                signal_strength=2,
                suggested_position=0,
                signal_source=DEMO_SIGNAL_SOURCE,
                status="ACTIVE",
            )
        )
        db.commit()
    finally:
        db.close()
        gen.close()

    token = _login(client, "admin", "AdminPass123")
    response = client.get("/api/admin/system-status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["real_score_count"] >= 1
    assert body["demo_score_count"] >= 1
    assert body["real_signal_count"] >= 1
    assert body["demo_signal_count"] >= 1


def test_available_for_backtest_returns_real_samples():
    client = _build_client()
    db, gen = _db_session_from_client(client)
    try:
        stock = db.query(Stock).filter(Stock.symbol == "600519").first()
        for offset in range(36):
            trade_day = date(2026, 1, 4) + timedelta(days=offset)
            db.add(
                DailyPrice(
                    stock_id=stock.id,
                    trade_date=trade_day,
                    open=114 + offset,
                    high=115 + offset,
                    low=113 + offset,
                    close=114 + offset,
                    pre_close=113 + offset,
                    volume=100000 + offset,
                    turnover=1000000 + offset,
                    pe=20,
                    pb=3,
                    market_cap=1000000000,
                    dividend_yield=2.5,
                )
            )
        db.commit()
    finally:
        db.close()
        gen.close()
    token = _login(client, "viewer", "ViewerPass123")
    response = client.get("/api/stocks/available-for-backtest?market=A_SHARE&limit=5", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "summary" in body
    assert isinstance(body["items"], list)
    assert body["items"][0]["support_level"] in {"preview", "basic", "full", "insufficient", "no_price"}
    assert body["summary"]["supported_count"] >= 1
    assert body["summary"]["diagnosis"]


def test_report_pdf_download_available():
    client = _build_client()
    token = _login(client, "admin", "AdminPass123")
    headers = {"Authorization": f"Bearer {token}"}
    html = client.get("/api/reports/1", headers=headers)
    assert html.status_code == 200
    response = client.get("/api/reports/1/pdf", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 100
    users = client.get("/api/admin/users", headers=headers)
    assert users.status_code == 200
    assert users.json()[0]["html_views"] >= 1
    assert users.json()[0]["pdf_downloads"] >= 1


def test_report_png_download_and_event_recorded():
    client = _build_client()
    token = _login(client, "admin", "AdminPass123")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/reports/1/png", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    users = client.get("/api/admin/users", headers=headers)
    assert users.status_code == 200
    assert users.json()[0]["png_downloads"] >= 1


def test_normal_user_cannot_read_other_users_report_or_config():
    client = _build_client()
    token = _login(client, "viewer", "ViewerPass123")
    headers = {"Authorization": f"Bearer {token}"}
    own = client.get("/api/reports", headers=headers)
    assert own.status_code == 200
    assert all(item["id"] == 1 for item in own.json()["items"])
    other_report = client.get("/api/reports/2", headers=headers)
    assert other_report.status_code in (403, 404)
    other_config_update = client.put(
        "/api/profile/api-configs/1",
        headers=headers,
        json={"name": "steal", "provider": "openai", "base_url": "https://api.example.com", "model_name": "gpt-test"},
    )
    assert other_config_update.status_code in (403, 404)


def test_download_events_belong_to_current_user():
    client = _build_client()
    token = _login(client, "viewer", "ViewerPass123")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/reports/1/png", headers=headers).status_code == 200
    assert client.get("/api/reports/1/pdf", headers=headers).status_code == 200
    db, gen = _db_session_from_client(client)
    try:
        viewer = db.query(User).filter(User.username == "viewer").first()
        events = db.query(ReportEvent).filter(ReportEvent.report_id == 1, ReportEvent.action == "download").all()
        assert events
        assert {event.user_id for event in events} == {viewer.id}
    finally:
        db.close()
        gen.close()


def test_backtest_strategies_and_admin_excel_export():
    client = _build_client()
    token = _login(client, "admin", "AdminPass123")
    headers = {"Authorization": f"Bearer {token}"}
    strategies = client.get("/api/backtest/strategies", headers=headers)
    assert strategies.status_code == 200
    assert len(strategies.json()["items"]) == 4
    export = client.get("/api/admin/users/export", headers=headers)
    assert export.status_code == 200
    assert "spreadsheetml" in export.headers["content-type"]


def test_backtest_task_is_saved_for_user():
    client = _build_client()
    token = _login(client, "viewer", "ViewerPass123")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/backtest/run",
        headers=headers,
        json={
            "strategy": "qingshu_1_short",
            "stock_symbol": "600519",
            "market": "A_SHARE",
            "start_date": "2026-01-02",
            "end_date": "2026-01-03",
            "rebalance": "monthly",
            "initial_capital": 1000000,
        },
    )
    assert response.status_code == 200
    history = client.get("/api/profile/backtests", headers=headers)
    assert history.status_code == 200
    assert history.json()[0]["stock_code"] == "600519"
    assert all(item["id"] != 1 for item in history.json())


def test_normal_user_only_reads_own_backtests():
    client = _build_client()
    token = _login(client, "viewer", "ViewerPass123")
    history = client.get("/api/profile/backtests", headers={"Authorization": f"Bearer {token}"})
    assert history.status_code == 200
    assert history.json() == []


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


def test_report_generation_quota_for_normal_user():
    client = _build_client()
    token = _login(client, "viewer", "ViewerPass123")
    db, gen = _db_session_from_client(client)
    try:
        user = db.query(User).filter(User.username == "viewer").first()
        db.add(UserApiQuota(user_id=user.id, daily_report_limit=0))
        db.commit()
    finally:
        db.close()
        gen.close()
    response = client.post("/api/reports/generate?report_type=STOCK&stock_symbol=600519", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 429
    assert "报告生成次数" in response.json()["detail"]


def test_png_and_pdf_download_quota_for_normal_user():
    client = _build_client()
    token = _login(client, "viewer", "ViewerPass123")
    headers = {"Authorization": f"Bearer {token}"}
    db, gen = _db_session_from_client(client)
    try:
        user = db.query(User).filter(User.username == "viewer").first()
        db.add(UserApiQuota(user_id=user.id, daily_pdf_limit=0, daily_png_limit=0))
        db.commit()
    finally:
        db.close()
        gen.close()
    pdf = client.get("/api/reports/1/pdf", headers=headers)
    png = client.get("/api/reports/1/png", headers=headers)
    assert pdf.status_code == 429
    assert png.status_code == 429
    assert "PDF下载次数" in pdf.json()["detail"]
    assert "PNG下载次数" in png.json()["detail"]


def test_backtest_quota_for_normal_user():
    client = _build_client()
    token = _login(client, "viewer", "ViewerPass123")
    db, gen = _db_session_from_client(client)
    try:
        user = db.query(User).filter(User.username == "viewer").first()
        db.add(UserApiQuota(user_id=user.id, daily_backtest_limit=0))
        db.commit()
    finally:
        db.close()
        gen.close()
    response = client.post(
        "/api/backtest/run",
        headers={"Authorization": f"Bearer {token}"},
        json={"strategy": "qingshu_1_short", "stock_symbol": "600519", "market": "A_SHARE", "start_date": "2026-01-02", "end_date": "2026-01-03", "rebalance": "monthly", "initial_capital": 1000000},
    )
    assert response.status_code == 429
    assert "回测次数" in response.json()["detail"]


def test_backtest_requires_stock_code_and_returns_chinese_error():
    client = _build_client()
    token = _login(client, "viewer", "ViewerPass123")
    response = client.post(
        "/api/backtest/run",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "strategy": "qingshu_1_short",
            "market": "A_SHARE",
            "start_date": "2026-01-02",
            "end_date": "2026-01-03",
            "rebalance": "monthly",
            "initial_capital": 1000000,
        },
    )
    assert response.status_code == 200
    assert "请先选择具体股票" in response.json()["error"]


def test_user_api_config_limit_and_test_status():
    client = _build_client()
    token = _login(client, "viewer", "ViewerPass123")
    headers = {"Authorization": f"Bearer {token}"}
    db, gen = _db_session_from_client(client)
    try:
        user = db.query(User).filter(User.username == "viewer").first()
        db.add(UserApiQuota(user_id=user.id, max_api_configs=1))
        db.add(UserApiConfig(owner_user_id=user.id, name="已有", provider="openai", base_url="https://api.example.com", model_name="gpt-test"))
        db.commit()
    finally:
        db.close()
        gen.close()
    blocked = client.post("/api/profile/api-configs", headers=headers, json={"name": "第二套", "provider": "openai", "base_url": "https://api.example.com", "model_name": "gpt-test"})
    assert blocked.status_code == 429
    listing = client.get("/api/profile/api-configs", headers=headers).json()
    tested = client.post(f"/api/profile/api-configs/{listing[0]['id']}/test", headers=headers)
    assert tested.status_code == 200
    assert tested.json()["status"] in {"format_valid", "ok", "unsupported"}


def test_watchlist_add_refresh_remove_and_admin_stats():
    client = _build_client()
    token = _login(client, "viewer", "ViewerPass123")
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/profile/watchlist",
        headers=headers,
        json={"stock_code": "600519", "stock_name": "娴嬭瘯鏍锋湰", "market": "A_SHARE", "industry": "娑堣垂"},
    )
    assert created.status_code == 200
    item_id = created.json()["id"]
    assert created.json()["snapshot"]["stock_code"] == "600519" if "stock_code" in created.json()["snapshot"] else True

    listing = client.get("/api/profile/watchlist", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    snapshot = client.get(f"/api/profile/watchlist/{item_id}/snapshot", headers=headers)
    assert snapshot.status_code == 200
    assert "shareholder_signal" in snapshot.json()["snapshot"]

    refreshed = client.post(f"/api/profile/watchlist/{item_id}/refresh", headers=headers)
    assert refreshed.status_code == 200

    admin_token = _login(client, "admin", "AdminPass123")
    stats = client.get("/api/admin/watchlist-stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert stats.status_code == 200
    assert stats.json()["summary"]["total_items"] >= 1
    assert "industry_distribution" in stats.json()
    assert "reports_after_watch" in stats.json()["summary"]

    deleted = client.delete(f"/api/profile/watchlist/{item_id}", headers=headers)
    assert deleted.status_code == 200
    assert client.get("/api/profile/watchlist", headers=headers).json() == []


def test_admin_is_not_limited_by_quota():
    client = _build_client()
    token = _login(client, "admin", "AdminPass123")
    db, gen = _db_session_from_client(client)
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        db.add(UserApiQuota(user_id=admin.id, daily_report_limit=0, daily_pdf_limit=0, daily_png_limit=0, daily_backtest_limit=0))
        db.commit()
    finally:
        db.close()
        gen.close()
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/reports/generate?report_type=STOCK&stock_symbol=600519", headers=headers)
    assert response.status_code == 200


def test_event_log_and_audit_log_are_written_and_filterable():
    client = _build_client()
    token = _login(client, "viewer", "ViewerPass123")
    headers = {"Authorization": f"Bearer {token}"}
    report = client.get("/api/reports/1", headers=headers)
    assert report.status_code == 200
    admin_token = _login(client, "admin", "AdminPass123")
    audit = client.get("/api/admin/audit-logs?action=report_html_view", headers={"Authorization": f"Bearer {admin_token}"})
    assert audit.status_code == 200
    assert audit.json()["total"] >= 1
    db, gen = _db_session_from_client(client)
    try:
        assert db.query(ReportEvent).count() >= 1
        assert db.query(OperationLog).count() >= 1
    finally:
        db.close()
        gen.close()


def test_audit_log_excel_export_and_usage_rankings():
    client = _build_client()
    admin_token = _login(client, "admin", "AdminPass123")
    headers = {"Authorization": f"Bearer {admin_token}"}
    rankings = client.get("/api/admin/usage-rankings", headers=headers)
    assert rankings.status_code == 200
    assert "top_reports" in rankings.json()
    export = client.get("/api/admin/audit-logs/export?status=success", headers=headers)
    assert export.status_code == 200
    assert "spreadsheetml" in export.headers["content-type"]


def test_admin_api_config_check_status():
    client = _build_client()
    admin_token = _login(client, "admin", "AdminPass123")
    headers = {"Authorization": f"Bearer {admin_token}"}
    saved = client.post("/api/admin/api-configs", headers=headers, json={"provider": "eastmoney", "display_name": "东方财富", "is_enabled": True})
    assert saved.status_code == 200
    checked = client.post(f"/api/admin/api-configs/{saved.json()['id']}/check", headers=headers)
    assert checked.status_code == 200
    assert checked.json()["status"] in {"unsupported", "format_valid", "ok"}


def test_redis_unavailable_status_and_mysql_example_present():
    client = _build_client()
    token = create_token("admin", "admin")
    status = client.get("/api/admin/system-status", headers={"Authorization": f"Bearer {token}"})
    assert status.status_code == 200
    assert "redis" in status.json()
    assert "redis_impact" in status.json()
    with open("../.env.example", "r", encoding="utf-8") as f:
        env_text = f.read()
    assert "mysql+pymysql://" in env_text


# ━━━━━━━━━━━━━━ 注册链路测试 ━━━━━━━━━━━━━━


def test_register_with_chinese_user_id_succeeds():
    client = _build_client()
    payload = {"phone": "13900010001", "user_id": "张三", "password": "Zhangsan1", "confirm_password": "Zhangsan1"}
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["user_id"] == "张三"
    assert "access_token" in body
    # 注册成功自动登录 → token 存在
    assert len(body["access_token"]) > 10


def test_login_by_phone_after_register():
    client = _build_client()
    client.post("/api/auth/register", json={"phone": "13900010002", "user_id": "李四", "password": "LisiPass1", "confirm_password": "LisiPass1"})
    resp = client.post("/api/auth/login", json={"identifier": "13900010002", "password": "LisiPass1"})
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "李四"


def test_login_by_user_id_after_register():
    client = _build_client()
    client.post("/api/auth/register", json={"phone": "13900010003", "user_id": "王五", "password": "WangwuPass1", "confirm_password": "WangwuPass1"})
    resp = client.post("/api/auth/login", json={"identifier": "王五", "password": "WangwuPass1"})
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "王五"


def test_register_duplicate_phone_returns_chinese_error():
    client = _build_client()
    payload = {"phone": "13900010004", "user_id": "赵六", "password": "Zhaoliu1", "confirm_password": "Zhaoliu1"}
    assert client.post("/api/auth/register", json=payload).status_code == 200
    # 重复手机号
    resp = client.post("/api/auth/register", json={"phone": "13900010004", "user_id": "赵七", "password": "Zhaoliu1", "confirm_password": "Zhaoliu1"})
    assert resp.status_code == 400
    detail = resp.json().get("detail", "")
    assert isinstance(detail, str) and len(detail) > 0
    assert "object Object" not in detail
    assert "手机号" in detail


def test_register_duplicate_user_id_returns_chinese_error():
    client = _build_client()
    payload = {"phone": "13900020001", "user_id": "孙八", "password": "Sunba1234", "confirm_password": "Sunba1234"}
    assert client.post("/api/auth/register", json=payload).status_code == 200
    # 重复用户ID
    resp = client.post("/api/auth/register", json={"phone": "13900020002", "user_id": "孙八", "password": "Sunba1234", "confirm_password": "Sunba1234"})
    assert resp.status_code == 400
    detail = resp.json().get("detail", "")
    assert isinstance(detail, str) and len(detail) > 0
    assert "object Object" not in detail
    assert "用户ID" in detail or "已存在" in detail


def test_register_missing_user_id_returns_readable_error():
    client = _build_client()
    resp = client.post("/api/auth/register", json={"phone": "13900030001", "password": "Test1234", "confirm_password": "Test1234"})
    assert resp.status_code in (400, 422)
    detail = resp.json().get("detail", "")
    assert isinstance(detail, str) and len(detail) > 0
    assert "object Object" not in detail


def test_frontend_user_id_maps_to_backend_user_id():
    """前端字段 userId 正确映射为后端 user_id"""
    client = _build_client()
    # 模拟前端实际发送的 payload（auth.tsx register 函数发送 user_id）
    payload = {"phone": "13900040001", "user_id": "钱九", "password": "Qianjiu1", "confirm_password": "Qianjiu1"}
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "钱九"


def test_register_failure_does_not_leak_password():
    client = _build_client()
    resp = client.post("/api/auth/register", json={"phone": "13900050001", "user_id": "周十", "password": "Zhou10Pass", "confirm_password": "Zhou10Mismatch"})
    assert resp.status_code == 400
    text = resp.text.lower()
    assert "zhou10pass" not in text


def test_register_failure_does_not_leak_python_traceback():
    client = _build_client()
    resp = client.post("/api/auth/register", json={"phone": "13900060001", "user_id": "吴十一", "password": "Wu11Pass"})
    text = resp.text
    assert "Traceback" not in text
    assert "File \"" not in text
    assert "raise " not in text


def test_error_detail_never_shows_object_object():
    """所有注册错误响应绝不包含 [object Object]"""
    client = _build_client()
    test_cases = [
        {},  # 全空
        {"phone": "13900070001"},  # 缺少 user_id 和 password
        {"phone": "13900070002", "user_id": "a"},  # user_id 太短 + 缺 password
        {"phone": "13900070003", "user_id": "郑十二", "password": "ab"},  # password 太短
    ]
    for payload in test_cases:
        resp = client.post("/api/auth/register", json=payload)
        body = resp.text
        assert "[object Object]" not in body, f"Failed for payload {payload}: {body}"
        assert "object Object" not in body, f"Failed for payload {payload}: {body}"


def test_login_with_nonexistent_identifier_returns_chinese():
    client = _build_client()
    resp = client.post("/api/auth/login", json={"username": "nobody", "password": "Nobody123"})
    assert resp.status_code == 401
    detail = resp.json().get("detail", "")
    assert isinstance(detail, str)
    assert "手机号" in detail or "错误" in detail
