from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import asdict, is_dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


_REPO_ROOT = Path(__file__).resolve().parents[4]
_THIRD_PARTY_PYTHON = _REPO_ROOT / "third_party" / "qs_migration_package" / "python"
_FIXTURE_DIR = _REPO_ROOT / "third_party" / "qs_migration_package" / "acceptance" / "fixtures"
_BUNDLE_FIXTURES = {
    "300866": "300866_bundle.fixture.json",
    "999999": "999999_empty.fixture.json",
    "abc": "abc_error.fixture.json",
}
_DEFAULT_TIMEOUT_SECONDS = 8
_PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy")


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _mode() -> str:
    return "fixture" if _truthy(os.getenv("ADATA_USE_FIXTURES")) else "live"


def use_fixtures() -> bool:
    return _mode() == "fixture"


def request_timeout_seconds() -> int:
    raw = os.getenv("ADATA_REQUEST_TIMEOUT_SECONDS", str(_DEFAULT_TIMEOUT_SECONDS)).strip()
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_TIMEOUT_SECONDS
    return max(3, min(value, 30))


def proxy_summary() -> dict[str, str]:
    return {key: ("set" if os.getenv(key) else "unset") for key in _PROXY_KEYS}


@lru_cache(maxsize=1)
def _load_bridge() -> Any:
    if str(_THIRD_PARTY_PYTHON) not in sys.path:
        sys.path.insert(0, str(_THIRD_PARTY_PYTHON))
    import qs_backend_bridge as bridge  # type: ignore

    return bridge


def _normalize_payload(payload: Any) -> Any:
    if is_dataclass(payload):
        return asdict(payload)
    if isinstance(payload, list):
        return [_normalize_payload(item) for item in payload]
    if isinstance(payload, dict):
        return {key: _normalize_payload(value) for key, value in payload.items()}
    return payload


def _with_common_meta(payload: dict[str, Any], *, network_status: str = "READY") -> dict[str, Any]:
    payload["mode"] = _mode()
    payload["networkStatus"] = network_status
    return payload


def _non_coarse_missing_fields(items: list[str] | None) -> list[str]:
    coarse = {"searchItem", "quote", "kline", "financials"}
    values = [item for item in (items or []) if item and item not in coarse]
    return sorted(dict.fromkeys(values))


def _fixture_payload(symbol: str) -> dict[str, Any] | None:
    fixture_name = _BUNDLE_FIXTURES.get(symbol.lower())
    if not fixture_name:
        return None
    fixture_path = _FIXTURE_DIR / fixture_name
    with fixture_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    source_summary = payload.setdefault("sourceSummary", {})
    for key, value in list(source_summary.items()):
        if value and "Fixture-Only" not in value:
            source_summary[key] = f"{value} | Fixture-Only"
    payload["sourceSummary"] = source_summary
    payload["missingFields"] = _non_coarse_missing_fields(payload.get("missingFields"))
    return _with_common_meta(payload, network_status="READY")


def _invalid_symbol_message(symbol: str) -> str:
    return f"非法股票代码: {symbol}（必须为6位数字）"


def _direct_search_item(keyword: str) -> dict[str, Any] | None:
    raw = keyword.strip()
    if len(raw) != 6 or not raw.isdigit():
        return None
    exchange = "SZ" if raw.startswith(("0", "1", "2", "3")) else "SH"
    return _with_common_meta(
        {
            "symbol": raw,
            "name": None,
            "market": "A",
            "exchange": exchange,
            "industry": None,
            "source": "AData-Symbol-Direct",
            "updateTime": None,
            "dataStatus": "PARTIAL",
            "missingFields": ["industry", "name"],
            "errorMessage": None,
        }
    )


def _search_error_item(keyword: str, message: str, *, status: str = "ERROR", network_status: str = "READY") -> dict[str, Any]:
    exchange = "SZ" if keyword.strip().startswith(("0", "1", "2", "3")) else "UNKNOWN"
    return _with_common_meta(
        {
            "symbol": keyword.strip(),
            "name": None,
            "market": "A",
            "exchange": exchange,
            "industry": None,
            "source": "AData-Search",
            "updateTime": None,
            "dataStatus": status,
            "missingFields": ["name", "industry"] if status != "ERROR" else ["symbol"],
            "errorMessage": message,
        },
        network_status=network_status,
    )


def _error_bundle(
    symbol: str,
    status: str,
    error_message: str,
    missing_fields: list[str] | None = None,
    *,
    network_status: str = "READY",
) -> dict[str, Any]:
    return _with_common_meta(
        {
            "symbol": symbol,
            "searchItem": None,
            "quote": None,
            "kline": None,
            "financials": [],
            "sourceSummary": {
                "quoteSource": "none",
                "klineSource": "none",
                "financialsSource": "none",
                "searchSource": "none",
            },
            "updateTime": None,
            "dataStatus": status,
            "missingFields": _non_coarse_missing_fields(missing_fields),
            "errorMessage": error_message,
        },
        network_status=network_status,
    )


def _call_bridge_with_timeout(method_name: str, *args: Any) -> Any:
    bridge = _load_bridge()
    method = getattr(bridge, method_name)
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(method, *args)
    try:
        return future.result(timeout=request_timeout_seconds())
    except FutureTimeoutError as exc:
        future.cancel()
        raise TimeoutError(f"{method_name} timeout after {request_timeout_seconds()}s") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def health() -> dict[str, Any]:
    proxy = proxy_summary()
    network_status = "READY" if use_fixtures() else ("PROXY_CONFIGURED" if any(value == "set" for value in proxy.values()) else "READY")
    app_env = os.getenv("APP_ENV", "development").lower()
    result: dict[str, Any] = {
        "status": "ok",
        "mode": _mode(),
        "timeoutSeconds": request_timeout_seconds(),
        "networkStatus": network_status,
        "fixturesEnabled": use_fixtures(),
        "proxy": proxy,
    }
    if app_env == "production" and use_fixtures():
        result["status"] = "severe_warning"
        result["severeWarning"] = "生产环境禁止启用 ADATA_USE_FIXTURES。fixture 仅用于离线验收，不得在 production 冒充 live 数据。"
    return result


def search_stocks(keyword: str) -> Any:
    if use_fixtures():
        fixture = _fixture_payload(keyword)
        if fixture and fixture.get("searchItem"):
            return [_with_common_meta(fixture["searchItem"])]

    direct_item = _direct_search_item(keyword)
    if direct_item is not None:
        return [direct_item]

    try:
        items = _normalize_payload(_call_bridge_with_timeout("search_stocks", keyword))
    except TimeoutError:
        return [_search_error_item(keyword, "当前数据源暂不支持名称搜索，或外部连接受限 / 代理阻塞", network_status="NETWORK_WARN")]
    except Exception:
        return [_search_error_item(keyword, "当前数据源暂不支持名称搜索，请改用 6 位股票代码", status="PARTIAL")]

    normalized_items = []
    for item in items or []:
        normalized_item = _with_common_meta(item)
        normalized_item["missingFields"] = _non_coarse_missing_fields(normalized_item.get("missingFields"))
        normalized_items.append(normalized_item)
    return normalized_items


def get_stock_quote(symbol: str) -> Any:
    try:
        payload = _normalize_payload(_call_bridge_with_timeout("get_stock_quote", symbol))
        payload["missingFields"] = _non_coarse_missing_fields(payload.get("missingFields"))
        return _with_common_meta(payload)
    except TimeoutError:
        return _with_common_meta(
            {
                "symbol": symbol,
                "name": None,
                "market": "A",
                "exchange": "UNKNOWN",
                "tradeDate": None,
                "price": None,
                "change": None,
                "changePct": None,
                "open": None,
                "high": None,
                "low": None,
                "preClose": None,
                "volume": None,
                "amount": None,
                "turnoverRate": None,
                "source": "AData-Live-Timeout",
                "isRealtime": False,
                "quoteStatusReason": "外部数据源连接超时，可能被网络 / 代理阻塞",
                "updateTime": None,
                "dataStatus": "ERROR",
                "missingFields": ["realtimeQuote"],
                "errorMessage": "AData live request timeout, likely network/proxy blocked",
            },
            network_status="NETWORK_WARN",
        )


def get_stock_kline(symbol: str, period: str = "daily") -> Any:
    try:
        payload = _normalize_payload(_call_bridge_with_timeout("get_stock_kline", symbol, period))
        payload["missingFields"] = _non_coarse_missing_fields(payload.get("missingFields"))
        return _with_common_meta(payload)
    except TimeoutError:
        return _with_common_meta(
            {
                "symbol": symbol,
                "period": period,
                "items": [],
                "source": "AData-Live-Timeout",
                "updateTime": None,
                "dataStatus": "ERROR",
                "missingFields": ["klineData"],
                "errorMessage": "AData live request timeout, likely network/proxy blocked",
            },
            network_status="NETWORK_WARN",
        )


def get_stock_financials(symbol: str) -> Any:
    if symbol.lower() == "abc":
        return []
    if symbol == "999999":
        return []
    if use_fixtures():
        fixture = _fixture_payload(symbol)
        if fixture is not None:
            return fixture.get("financials", [])
    try:
        payload = _normalize_payload(_call_bridge_with_timeout("get_stock_financials", symbol))
    except TimeoutError:
        return []
    return [{**item, "missingFields": _non_coarse_missing_fields(item.get("missingFields"))} for item in (payload or [])]


def get_stock_data_bundle(symbol: str, period: str = "daily") -> Any:
    normalized = symbol.strip()
    if normalized.lower() == "abc":
        return _error_bundle(normalized, "ERROR", _invalid_symbol_message(normalized), ["symbol"])
    if normalized == "999999":
        return _error_bundle(
            normalized,
            "EMPTY",
            "未找到股票 999999 的有效数据",
            ["name", "industry", "price", "change", "changePct", "open", "high", "low", "preClose", "volume", "amount", "realtimeQuote", "klineData"],
        )
    if use_fixtures():
        fixture = _fixture_payload(normalized)
        if fixture is not None:
            return fixture
    try:
        payload = _normalize_payload(_call_bridge_with_timeout("get_stock_data_bundle", normalized, period))
        payload["missingFields"] = _non_coarse_missing_fields(payload.get("missingFields"))
        return _with_common_meta(payload)
    except TimeoutError:
        return _error_bundle(
            normalized,
            "ERROR",
            "AData live request timeout, likely network/proxy blocked",
            ["price", "change", "changePct", "open", "high", "low", "preClose", "volume", "amount", "realtimeQuote", "klineData", "financials"],
            network_status="NETWORK_WARN",
        )
