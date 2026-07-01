from __future__ import annotations

import json
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.integrations.adata import service as adata_service
from app.core.config import Settings


def test_adata_health_returns_mode_and_timeout(monkeypatch):
    monkeypatch.setenv("ADATA_USE_FIXTURES", "true")
    monkeypatch.setenv("ADATA_REQUEST_TIMEOUT_SECONDS", "11")
    client = TestClient(app)

    response = client.get("/api/adata/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "fixture"
    assert body["timeoutSeconds"] == 11
    assert body["fixturesEnabled"] is True


def test_search_route_uses_canonical_path(monkeypatch):
    def fake_search(keyword: str):
        assert keyword == "300866"
        return [
            {
                "symbol": "300866",
                "name": "安克创新",
                "market": "A",
                "exchange": "SZ",
                "industry": "消费电子",
                "source": "AData-Symbol-Direct",
                "updateTime": "2026-06-30T00:00:00",
                "dataStatus": "PARTIAL",
                "missingFields": ["name", "industry"],
                "errorMessage": None,
                "mode": "live",
                "networkStatus": "READY",
            }
        ]

    monkeypatch.setattr(adata_service, "search_stocks", fake_search)
    client = TestClient(app)

    ok_response = client.get("/api/adata/stocks/search?keyword=300866")
    assert ok_response.status_code == 200
    assert ok_response.json()[0]["symbol"] == "300866"

    wrong_response = client.get("/api/adata/stocks/300866/search?keyword=300866")
    assert wrong_response.status_code == 404


def test_fixture_mode_bundle_semantics(monkeypatch):
    monkeypatch.setenv("ADATA_USE_FIXTURES", "true")
    client = TestClient(app)

    ok_response = client.get("/api/adata/stocks/300866/bundle?period=daily")
    assert ok_response.status_code == 200
    ok_body = ok_response.json()
    assert ok_body["dataStatus"] in {"OK", "PARTIAL"}
    assert ok_body["mode"] == "fixture"
    assert "Fixture-Only" in (ok_body.get("sourceSummary", {}).get("quoteSource") or "")

    empty_response = client.get("/api/adata/stocks/999999/bundle?period=daily")
    assert empty_response.status_code == 200
    assert empty_response.json()["dataStatus"] == "EMPTY"

    error_response = client.get("/api/adata/stocks/abc/bundle?period=daily")
    assert error_response.status_code == 200
    assert error_response.json()["dataStatus"] == "ERROR"
    assert "非法股票代码" in error_response.json()["errorMessage"]


def test_financials_route_returns_array_in_fixture_mode(monkeypatch):
    monkeypatch.setenv("ADATA_USE_FIXTURES", "true")
    client = TestClient(app)

    response = client.get("/api/adata/stocks/300866/financials")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body

    empty_response = client.get("/api/adata/stocks/999999/financials")
    assert empty_response.status_code == 200
    assert empty_response.json() == []


def test_live_mode_has_no_fixture_only(monkeypatch):
    monkeypatch.delenv("ADATA_USE_FIXTURES", raising=False)
    monkeypatch.setattr(
        adata_service,
        "_call_bridge_with_timeout",
        lambda method_name, *args: {
            "symbol": "300866",
            "searchItem": {
                "symbol": "300866",
                "name": "安克创新",
                "market": "A",
                "exchange": "SZ",
                "industry": None,
                "source": "AData-code-csv",
                "updateTime": None,
                "dataStatus": "PARTIAL",
                "missingFields": ["industry"],
                "errorMessage": None,
            },
            "quote": {
                "symbol": "300866",
                "name": "安克创新",
                "market": "A",
                "exchange": "SZ",
                "tradeDate": "2026-06-30",
                "price": 104.5,
                "change": -4.52,
                "changePct": -4.15,
                "open": 108.12,
                "high": 110.82,
                "low": 103.85,
                "preClose": 109.02,
                "volume": 6217100,
                "amount": 658350091.34,
                "turnoverRate": 2.02,
                "source": "AData-Kline-Fallback",
                "isRealtime": False,
                "quoteStatusReason": "实时行情为空，使用最新K线构造延迟行情",
                "updateTime": None,
                "dataStatus": "PARTIAL",
                "missingFields": ["realtimeQuote"],
                "errorMessage": None,
            },
            "kline": {
                "symbol": "300866",
                "period": "daily",
                "items": [{"date": "2026-06-30", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "amount": 1}],
                "source": "adata",
                "updateTime": None,
                "dataStatus": "OK",
                "missingFields": [],
                "errorMessage": None,
            },
            "financials": [],
            "sourceSummary": {
                "quoteSource": "AData-Kline-Fallback",
                "klineSource": "AData-EastMoney",
                "financialsSource": "none",
                "searchSource": "AData-code-csv",
            },
            "updateTime": None,
            "dataStatus": "PARTIAL",
            "missingFields": ["realtimeQuote", "industry"],
            "errorMessage": None,
        } if method_name == "get_stock_data_bundle" else [],
    )
    client = TestClient(app)

    response = client.get("/api/adata/stocks/300866/bundle?period=daily")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "live"
    assert "Fixture-Only" not in str(body["sourceSummary"])
    assert body["quote"]["quoteStatusReason"]
    assert all(field not in {"searchItem", "quote", "kline", "financials"} for field in body["missingFields"])


def test_timeout_returns_network_warn_without_traceback(monkeypatch):
    monkeypatch.delenv("ADATA_USE_FIXTURES", raising=False)

    def timeout_call(*_args, **_kwargs):
        raise TimeoutError("timeout")

    monkeypatch.setattr(adata_service, "_call_bridge_with_timeout", timeout_call)
    client = TestClient(app)

    response = client.get("/api/adata/stocks/300866/bundle?period=daily")
    assert response.status_code == 200
    body = response.json()
    assert body["networkStatus"] == "NETWORK_WARN"
    assert body["dataStatus"] == "ERROR"
    assert "Traceback" not in response.text


def test_production_blocks_fixture_mode(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 48)
    monkeypatch.setenv("ADATA_USE_FIXTURES", "true")
    monkeypatch.setenv("DEBUG", "false")

    with pytest.raises(RuntimeError, match="ADATA_USE_FIXTURES"):
        Settings()


def test_smoke_strict_live_returns_nonzero_on_network_warn(monkeypatch):
    import importlib.util
    from pathlib import Path

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "smoke_adata_api.py"
    spec = importlib.util.spec_from_file_location("smoke_adata_api", script_path)
    assert spec and spec.loader
    smoke_adata_api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke_adata_api)

    class FakeResponse:
        def __init__(self, status_code=200, json_data=None):
            self.status_code = status_code
            self._json_data = {} if json_data is None else json_data

        def json(self):
            return self._json_data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"status={self.status_code}")

    def fake_get(url, timeout=0):
        if url.endswith("/api/adata/health"):
            return FakeResponse(json_data={"mode": "live", "networkStatus": "READY", "timeoutSeconds": 8})
        if url.endswith("/api/adata/stocks/search?keyword=300866"):
            return FakeResponse(json_data=[{"symbol": "300866", "dataStatus": "PARTIAL"}])
        if "/api/adata/stocks/300866/search?" in url:
            return FakeResponse(status_code=404, json_data={"detail": "not found"})
        if url.endswith("/api/adata/stocks/999999/bundle?period=daily"):
            return FakeResponse(json_data={"dataStatus": "EMPTY"})
        if url.endswith("/api/adata/stocks/abc/bundle?period=daily"):
            return FakeResponse(json_data={"dataStatus": "ERROR"})
        if url.endswith("/api/adata/stocks/300866/financials"):
            return FakeResponse(json_data=[])
        if url.endswith("/api/adata/stocks/300866/bundle?period=daily"):
            return FakeResponse(
                json_data={
                    "dataStatus": "ERROR",
                    "networkStatus": "NETWORK_WARN",
                    "sourceSummary": {"quoteSource": "timeout"},
                    "errorMessage": "AData live request timeout, likely network/proxy blocked",
                    "missingFields": ["price"],
                    "quote": {"dataStatus": "ERROR"},
                }
            )
        raise RuntimeError(url)

    monkeypatch.setattr(smoke_adata_api.requests, "get", fake_get)
    monkeypatch.setattr(smoke_adata_api.sys, "argv", ["smoke_adata_api.py", "--strict-live"])

    assert smoke_adata_api.main() == 3


def test_health_returns_severe_warning_when_production_and_fixtures(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADATA_USE_FIXTURES", "true")
    health = adata_service.health()
    assert health["status"] == "severe_warning"
    assert "severeWarning" in health
    assert "生产环境" in health["severeWarning"]

    # Clean: production without fixtures should be ok
    monkeypatch.setenv("ADATA_USE_FIXTURES", "false")
    health2 = adata_service.health()
    assert health2["status"] == "ok"


def test_smoke_fixture_flag_requires_fixture_backend(monkeypatch, capsys):
    import importlib.util
    from pathlib import Path

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "smoke_adata_api.py"
    spec = importlib.util.spec_from_file_location("smoke_adata_api", script_path)
    assert spec and spec.loader
    smoke_adata_api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke_adata_api)

    class FakeResponse:
        def __init__(self, status_code=200, json_data=None):
            self.status_code = status_code
            self._json_data = {} if json_data is None else json_data

        def json(self):
            return self._json_data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"status={self.status_code}")

    def fake_get(url, timeout=0):
        if url.endswith("/api/adata/health"):
            return FakeResponse(json_data={"mode": "live", "networkStatus": "READY", "timeoutSeconds": 8})
        if url.endswith("/api/adata/stocks/search?keyword=300866"):
            return FakeResponse(json_data=[{"symbol": "300866", "dataStatus": "PARTIAL"}])
        if "/api/adata/stocks/300866/search?" in url:
            return FakeResponse(status_code=404, json_data={"detail": "not found"})
        if url.endswith("/api/adata/stocks/999999/bundle?period=daily"):
            return FakeResponse(json_data={"dataStatus": "EMPTY"})
        if url.endswith("/api/adata/stocks/abc/bundle?period=daily"):
            return FakeResponse(json_data={"dataStatus": "ERROR"})
        if url.endswith("/api/adata/stocks/300866/financials"):
            return FakeResponse(json_data=[])
        if url.endswith("/api/adata/stocks/300866/bundle?period=daily"):
            return FakeResponse(
                json_data={
                    "dataStatus": "ERROR",
                    "networkStatus": "NETWORK_WARN",
                    "sourceSummary": {"quoteSource": "timeout"},
                    "errorMessage": "AData live request timeout, likely network/proxy blocked",
                    "missingFields": ["price"],
                    "quote": {"dataStatus": "ERROR"},
                }
            )
        raise RuntimeError(url)

    monkeypatch.setattr(smoke_adata_api.requests, "get", fake_get)
    monkeypatch.setattr(smoke_adata_api.sys, "argv", ["smoke_adata_api.py", "--use-fixtures"])

    assert smoke_adata_api.main() == 1
    stdout = capsys.readouterr().out
    assert "ADATA_USE_FIXTURES=true" in stdout
    assert "不是契约失败" in stdout


def test_smoke_summary_marks_live_verified_false_for_warn(monkeypatch, capsys):
    import importlib.util
    from pathlib import Path

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "smoke_adata_api.py"
    spec = importlib.util.spec_from_file_location("smoke_adata_api", script_path)
    assert spec and spec.loader
    smoke_adata_api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke_adata_api)

    class FakeResponse:
        def __init__(self, status_code=200, json_data=None):
            self.status_code = status_code
            self._json_data = {} if json_data is None else json_data

        def json(self):
            return self._json_data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"status={self.status_code}")

    def fake_get(url, timeout=0):
        if url.endswith("/api/adata/health"):
            return FakeResponse(json_data={"mode": "live", "networkStatus": "READY", "timeoutSeconds": 8})
        if url.endswith("/api/adata/stocks/search?keyword=300866"):
            return FakeResponse(json_data=[{"symbol": "300866", "dataStatus": "PARTIAL"}])
        if "/api/adata/stocks/300866/search?" in url:
            return FakeResponse(status_code=404, json_data={"detail": "not found"})
        if url.endswith("/api/adata/stocks/999999/bundle?period=daily"):
            return FakeResponse(json_data={"dataStatus": "EMPTY"})
        if url.endswith("/api/adata/stocks/abc/bundle?period=daily"):
            return FakeResponse(json_data={"dataStatus": "ERROR"})
        if url.endswith("/api/adata/stocks/300866/financials"):
            return FakeResponse(json_data=[])
        if url.endswith("/api/adata/stocks/300866/bundle?period=daily"):
            return FakeResponse(
                json_data={
                    "dataStatus": "ERROR",
                    "networkStatus": "NETWORK_WARN",
                    "sourceSummary": {"quoteSource": "timeout"},
                    "errorMessage": "AData live request timeout, likely network/proxy blocked",
                    "missingFields": ["price"],
                    "quote": {"dataStatus": "ERROR"},
                }
            )
        raise RuntimeError(url)

    monkeypatch.setattr(smoke_adata_api.requests, "get", fake_get)
    monkeypatch.setattr(smoke_adata_api.sys, "argv", ["smoke_adata_api.py"])

    assert smoke_adata_api.main() == 0
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["liveVerified"] is False
    assert summary["strictLive"] is False
    assert summary["warnings"] == 1
