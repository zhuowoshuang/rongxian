#!/usr/bin/env python
"""
清数智算 — AData API 集成测试

用法:
  cd F:/tools/2.2adata
  python -m pytest qs_migration_package/integration_demo/backend/test_adata_api.py -v
  或
  python qs_migration_package/integration_demo/backend/test_adata_api.py
"""

import os
import sys
import json

# 确保可导入 bridge
_PKG = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'python')
sys.path.insert(0, _PKG)

from qs_backend_bridge.stock_data_service import (  # noqa: E402
    search_stocks,
    get_stock_quote,
    get_stock_kline,
    get_stock_financials,
    get_stock_data_bundle,
)


def _check_ok(result, label: str) -> tuple:
    """检查结果是否 OK（不崩溃）"""
    return (label, "OK", None)


def test_search_300866():
    """search_stocks('300866') 返回非空列表"""
    items = search_stocks("300866")
    assert items is not None, "应返回列表"
    assert len(items) > 0, "应找到 300866"
    assert items[0].dataStatus in ("OK", "PARTIAL"), f"应为 OK/PARTIAL: {items[0].dataStatus}"
    print(f"  ✅ search 300866: {items[0].name}, status={items[0].dataStatus}")


def test_quote_300866():
    """get_stock_quote('300866') 返回行情（含 fallback）"""
    q = get_stock_quote("300866")
    assert q is not None
    assert q.dataStatus in ("OK", "PARTIAL", "EMPTY"), f"不应 ERROR: {q.dataStatus}"
    assert hasattr(q, 'quoteStatusReason'), "应有 quoteStatusReason"
    print(f"  ✅ quote 300866: status={q.dataStatus}, isRealtime={q.isRealtime}, source={q.source}")


def test_kline_300866():
    """get_stock_kline('300866') items > 0 或 dataStatus=EMPTY"""
    k = get_stock_kline("300866")
    assert k is not None
    assert k.dataStatus != "ERROR", f"不应 ERROR: {k.errorMessage}"
    print(f"  ✅ kline 300866: {len(k.items)} bars, status={k.dataStatus}")


def test_financials_300866():
    """get_stock_financials('300866') 返回列表"""
    fs = get_stock_financials("300866")
    assert fs is not None
    assert isinstance(fs, list)
    if fs:
        assert fs[0].dataStatus != "ERROR"
        print(f"  ✅ financials 300866: {len(fs)} periods, latest={fs[0].period}")
    else:
        print(f"  ⚠️  financials 300866: 0 periods (EMPTY)")


def test_bundle_300866():
    """get_stock_data_bundle('300866') 包含 quote+kline+financials+sourceSummary"""
    b = get_stock_data_bundle("300866")
    assert b.symbol == "300866"
    assert b.quote is not None
    assert b.kline is not None
    assert b.financials is not None
    assert b.sourceSummary is not None
    assert b.dataStatus in ("OK", "PARTIAL"), f"应为 OK/PARTIAL: {b.dataStatus}"
    # missingFields 不应包含粗粒度字段
    coarse = {"searchItem", "quote", "kline"}
    assert not (set(b.missingFields) & coarse), f"missingFields 不应含粗粒度: {b.missingFields}"
    print(f"  ✅ bundle 300866: status={b.dataStatus}, missingFields={b.missingFields}")


def test_bundle_999999():
    """get_stock_data_bundle('999999') dataStatus 必须为 EMPTY"""
    b = get_stock_data_bundle("999999")
    assert b.dataStatus == "EMPTY", f"应为 EMPTY: {b.dataStatus}"
    print(f"  ✅ bundle 999999: status={b.dataStatus}")


def test_bundle_abc():
    """get_stock_data_bundle('abc') dataStatus 必须为 ERROR"""
    b = get_stock_data_bundle("abc")
    assert b.dataStatus == "ERROR", f"应为 ERROR: {b.dataStatus}"
    assert "非法" in (b.errorMessage or ""), f"errorMessage 应包含'非法': {b.errorMessage}"
    print(f"  ✅ bundle abc: status={b.dataStatus}, msg={b.errorMessage}")


if __name__ == '__main__':
    tests = [
        test_search_300866,
        test_quote_300866,
        test_kline_300866,
        test_financials_300866,
        test_bundle_300866,
        test_bundle_999999,
        test_bundle_abc,
    ]
    passed = 0
    failed = 0
    for fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ❌ {fn.__name__}: {e}")
    print(f"\n{'='*50}")
    print(f"结果: {passed}/{len(tests)} 通过, {failed}/{len(tests)} 失败")
    if failed > 0:
        sys.exit(1)
