from datetime import date

from fastapi.testclient import TestClient

from app.api.reports import _build_data_status_report_v2
from app.db.session import SessionLocal
from app.main import app
from app.models.stock import Stock


client = TestClient(app)


def _login_analyst() -> str:
    response = client.post("/api/auth/login", json={"identifier": "analyst", "password": "Analyst123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_stock_603173_returns_no_data_instead_of_not_found():
    response = client.get("/api/stocks/603173")
    assert response.status_code == 200
    body = response.json()
    assert body["stock"]["symbol"] == "603173"
    assert body["data_readiness"]["readiness_level"] in {"no_data", "data_quality_limited"}
    assert body["latest_price"] is None
    assert body["score"] is None


def test_stock_300866_returns_no_data_instead_of_timeout():
    response = client.get("/api/stocks/300866")
    assert response.status_code == 200
    body = response.json()
    assert body["stock"]["symbol"] == "300866"
    assert body["data_readiness"]["readiness_level"] in {"no_data", "data_quality_limited"}


def test_data_status_report_contains_missing_fields_and_alternative_samples():
    db = SessionLocal()
    try:
        stock = db.query(Stock).filter(Stock.symbol == "603173").first()
        assert stock is not None
        report = _build_data_status_report_v2(db, stock, date.today(), None)
        assert "数据状态说明" in report.title
        assert "缺失数据" in report.content_markdown
        assert "002415 海康威视" in report.content_markdown
        assert "600519 贵州茅台" in report.content_markdown
    finally:
        db.close()


def test_backtest_basic_mode_runs_for_core_sample():
    token = _login_analyst()
    response = client.post(
        "/api/backtest/run",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "strategy": "qingshu_1_short",
            "stock_code": "002415",
            "market": "A_SHARE",
            "start_date": "2026-01-02",
            "end_date": "2026-01-09",
            "rebalance": "monthly",
            "initial_capital": 1000000,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "error" not in body
    assert body["stock_code"] == "002415"


def test_core_samples_still_return_full_detail():
    for symbol in ("002415", "600519"):
        response = client.get(f"/api/stocks/{symbol}")
        assert response.status_code == 200
        body = response.json()
        assert body["stock"]["symbol"] == symbol
        assert body["latest_price"] is not None
        assert body["price_history"]
