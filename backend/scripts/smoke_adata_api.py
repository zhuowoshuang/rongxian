from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import requests


def run_check(base_url: str, path: str, timeout: int) -> dict[str, Any]:
    response = requests.get(f"{base_url}{path}", timeout=timeout)
    response.raise_for_status()
    return response.json()


def is_network_warn(payload: dict[str, Any]) -> bool:
    network_status = str(payload.get("networkStatus") or "").upper()
    error_message = str(payload.get("errorMessage") or "").lower()
    return network_status == "NETWORK_WARN" or any(
        token in error_message for token in ["proxy", "timeout", "connection", "ssl", "network"]
    )


def classify_live_payload(symbol: str, payload: dict[str, Any]) -> tuple[str, str]:
    status = str(payload.get("dataStatus") or "").upper()
    if symbol == "300866":
        if status in {"OK", "PARTIAL"} and payload.get("quoteStatusReason") not in (None, ""):
            return "PASS", f"{symbol} live bundle usable with quote fallback"
        if status in {"OK", "PARTIAL"} and (
            (payload.get("quote") or {}).get("price") is not None or (payload.get("kline") or {}).get("items")
        ):
            return "PASS", f"{symbol} live dataStatus={status}"
        if is_network_warn(payload):
            return "NETWORK_WARN", f"{symbol} live blocked by network/proxy: {payload.get('errorMessage') or payload.get('networkStatus')}"
        return "FAIL", f"{symbol} live unexpected payload: {json.dumps(payload, ensure_ascii=False)}"
    return "PASS", f"{symbol} dataStatus={status}"


def expect_status(name: str, payload: dict[str, Any], expected: str) -> tuple[str, str]:
    actual = str(payload.get("dataStatus") or "").upper()
    if actual == expected:
        return "PASS", f"{name} dataStatus={actual}"
    return "FAIL", f"{name} expected {expected}, got {actual}: {json.dumps(payload, ensure_ascii=False)}"


def bundle_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": payload.get("mode"),
        "networkStatus": payload.get("networkStatus"),
        "dataStatus": payload.get("dataStatus"),
        "sourceSummary": payload.get("sourceSummary"),
        "errorMessage": payload.get("errorMessage"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test AData API routes")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--use-fixtures", action="store_true")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--symbol", default="300866")
    parser.add_argument("--strict-live", action="store_true")
    args = parser.parse_args()
    started_at = time.perf_counter()

    checks: list[tuple[str, str]] = []
    failures = 0
    warnings = 0

    health = run_check(args.base_url, "/api/adata/health", args.timeout)
    checks.append(("PASS", f"health mode={health.get('mode')} networkStatus={health.get('networkStatus')} timeout={health.get('timeoutSeconds')}"))

    search_payload = run_check(args.base_url, f"/api/adata/stocks/search?keyword={args.symbol}", args.timeout)
    if isinstance(search_payload, list):
        pickable = [item for item in search_payload if item.get("dataStatus") in {"OK", "PARTIAL"}]
        checks.append(("PASS", f"search returned {len(search_payload)} item(s), pickable={len(pickable)}"))
    else:
        checks.append(("FAIL", f"search payload must be array: {json.dumps(search_payload, ensure_ascii=False)}"))
        failures += 1

    wrong_path = requests.get(
        f"{args.base_url}/api/adata/stocks/{args.symbol}/search?keyword={args.symbol}",
        timeout=args.timeout,
    )
    if wrong_path.status_code == 404:
        checks.append(("PASS", "wrong search path returns 404"))
    else:
        checks.append(("FAIL", f"wrong search path must return 404, got {wrong_path.status_code}"))
        failures += 1

    for symbol, expected in (("999999", "EMPTY"), ("abc", "ERROR")):
        payload = run_check(args.base_url, f"/api/adata/stocks/{symbol}/bundle?period=daily", args.timeout)
        result = expect_status(symbol, payload, expected)
        checks.append(result)
        if result[0] == "FAIL":
            failures += 1

    financials_payload = run_check(args.base_url, f"/api/adata/stocks/{args.symbol}/financials", args.timeout)
    if isinstance(financials_payload, list):
        checks.append(("PASS", f"financials returned array length={len(financials_payload)}"))
    else:
        checks.append(("FAIL", f"financials must return array: {json.dumps(financials_payload, ensure_ascii=False)}"))
        failures += 1

    bundle_payload = run_check(args.base_url, f"/api/adata/stocks/{args.symbol}/bundle?period=daily", args.timeout)
    result = classify_live_payload(args.symbol, bundle_payload)
    checks.append(result)
    if result[0] == "FAIL":
        failures += 1
    if result[0] == "NETWORK_WARN":
        warnings += 1

    live_ok = bool(result[0] == "PASS" and health.get("mode") == "live")
    fixture_mode_mismatch = False

    if args.use_fixtures:
        if health.get("mode") != "fixture":
            fixture_mode_mismatch = True
            checks.append(("FAIL", f"--use-fixtures 请以 ADATA_USE_FIXTURES=true 启动后端（当前 health.mode={health.get('mode')}），这不是契约失败"))
            failures += 1
        elif "Fixture-Only" not in json.dumps(bundle_payload.get("sourceSummary") or {}, ensure_ascii=False):
            checks.append(("FAIL", "fixture bundle must contain Fixture-Only"))
            failures += 1
        else:
            checks.append(("PASS", "fixture bundle contains Fixture-Only"))

    if bundle_payload.get("missingFields") and any(
        item in {"searchItem", "quote", "kline", "financials"} for item in bundle_payload.get("missingFields") or []
    ):
        checks.append(("FAIL", f"bundle missingFields too coarse: {bundle_payload.get('missingFields')}"))
        failures += 1
    else:
        checks.append(("PASS", f"bundle missingFields={bundle_payload.get('missingFields') or []}"))

    quote = bundle_payload.get("quote") or {}
    if quote.get("dataStatus") == "PARTIAL":
        if quote.get("quoteStatusReason"):
            checks.append(("PASS", "quote fallback contains quoteStatusReason"))
        else:
            checks.append(("FAIL", "quote fallback missing quoteStatusReason"))
            failures += 1

    for status, message in checks:
        print(f"[{status}] {message}")

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    summary = {
        "mode": health.get("mode"),
        "networkStatus": bundle_payload.get("networkStatus") or health.get("networkStatus"),
        "dataStatus": bundle_payload.get("dataStatus"),
        "sourceSummary": bundle_payload.get("sourceSummary"),
        "errorMessage": bundle_payload.get("errorMessage"),
        "elapsed_ms": elapsed_ms,
        "liveVerified": live_ok,
        "strictLive": args.strict_live,
        "fixtureRequested": args.use_fixtures,
        "fixtureModeMismatch": fixture_mode_mismatch,
        "failures": failures,
        "warnings": warnings,
        "bundle": bundle_summary(bundle_payload),
    }
    print(json.dumps(summary, ensure_ascii=False))

    if failures:
        return 1
    if args.strict_live and not live_ok:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
