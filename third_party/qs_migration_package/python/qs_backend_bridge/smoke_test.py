#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清数智算 Backend Bridge Smoke Test

用法：
  python qs_migration_package/python/qs_backend_bridge/smoke_test.py --symbol 300866
  python qs_migration_package/python/qs_backend_bridge/smoke_test.py
"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime

# 确保可导入
_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.join(_HERE, '..')
if _PKG not in sys.path:
    sys.path.insert(0, os.path.abspath(_PKG))

from qs_backend_bridge.stock_data_service import (  # noqa: E402
    search_stocks,
    get_stock_quote,
    get_stock_kline,
    get_stock_financials,
    get_stock_data_bundle,
)
from qs_backend_bridge.api_models import (  # noqa: E402
    StockKlineResponse,
)


def _json_dumps(obj, indent=2):
    """JSON 序列化（处理 dataclass / Enum）"""
    def _ser(o):
        if hasattr(o, 'value'): return o.value
        if isinstance(o, datetime): return o.isoformat()
        if hasattr(o, '__dataclass_fields__'): return asdict(o)
        return str(o)
    return json.dumps(obj, ensure_ascii=False, indent=indent, default=_ser)


def run_smoke(symbol: str, output_dir: str = None):
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(_HERE), '..', '..', 'examples')
        output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print(f"清数智算 Backend Bridge Smoke Test — {symbol}")
    print("=" * 60)

    results = []

    # 1. search
    print(f"\n🔍 search_stocks('{symbol}')")
    try:
        s = search_stocks(symbol)
        print(f"   结果: {len(s)} 条")
        if s:
            print(f"   name: {s[0].name}, status: {s[0].dataStatus}")
        results.append(("search", "OK" if s and s[0].dataStatus != "ERROR" else "FAIL"))
    except Exception as e:
        print(f"   [FAIL] 异常: {e}")
        results.append(("search", "FAIL"))

    # 2. quote
    print(f"\n📊 get_stock_quote('{symbol}')")
    try:
        q = get_stock_quote(symbol)
        is_fallback = "Kline-Fallback" in (q.source or "")
        print(f"   status: {q.dataStatus}")
        print(f"   price: {q.price}")
        print(f"   isRealtime: {q.isRealtime}")
        print(f"   source: {q.source}")
        print(f"   fallback触发: {'[PASS] 是' if is_fallback else '[FAIL] 否'}")
        with open(os.path.join(output_dir, f'quote_{symbol}.json'), 'w', encoding='utf-8') as f:
            f.write(_json_dumps(q))
        results.append(("quote", "OK"))
    except Exception as e:
        print(f"   [FAIL] 异常: {e}")
        results.append(("quote", "FAIL"))

    # 3. kline
    print(f"\n📈 get_stock_kline('{symbol}', 'daily')")
    try:
        k = get_stock_kline(symbol, "daily")
        print(f"   status: {k.dataStatus}")
        print(f"   items: {len(k.items)} 条")
        if k.items:
            print(f"   最新: {k.items[-1].date} O={k.items[-1].open} C={k.items[-1].close}")
        # 最近 120 条
        trimmed = StockKlineResponse(
            symbol=k.symbol, period=k.period,
            items=k.items[-120:] if len(k.items) > 120 else k.items,
            source=k.source, updateTime=k.updateTime,
            dataStatus=k.dataStatus, missingFields=k.missingFields,
            errorMessage=k.errorMessage,
        )
        with open(os.path.join(output_dir, f'kline_{symbol}_daily.json'), 'w', encoding='utf-8') as f:
            f.write(_json_dumps(trimmed))
        results.append(("kline", "OK"))
    except Exception as e:
        print(f"   [FAIL] 异常: {e}")
        results.append(("kline", "FAIL"))

    # 4. financials
    print(f"\n💰 get_stock_financials('{symbol}')")
    try:
        fins = get_stock_financials(symbol)
        print(f"   期数: {len(fins)}")
        if fins:
            print(f"   最新: {fins[0].period} EPS={fins[0].eps} ROE={fins[0].roe}")
        # 最近 8 期
        with open(os.path.join(output_dir, f'financials_{symbol}.json'), 'w', encoding='utf-8') as f:
            f.write(_json_dumps(fins[:8]))
        results.append(("financials", "OK"))
    except Exception as e:
        print(f"   [FAIL] 异常: {e}")
        results.append(("financials", "FAIL"))

    # 5. bundle
    print(f"\n📦 get_stock_data_bundle('{symbol}')")
    try:
        b = get_stock_data_bundle(symbol)
        print(f"   status: {b.dataStatus}")
        print(f"   missingFields: {b.missingFields}")
        print(f"   sourceSummary: {b.sourceSummary}")
        with open(os.path.join(output_dir, f'qs_stock_bundle_{symbol}.json'), 'w', encoding='utf-8') as f:
            f.write(_json_dumps(b))
        results.append(("bundle", "OK"))
    except Exception as e:
        print(f"   [FAIL] 异常: {e}")
        results.append(("bundle", "FAIL"))

    # 6. error example
    print(f"\n[FAIL] 错误示例: get_stock_data_bundle('999999')")
    try:
        eb = get_stock_data_bundle("999999")
        print(f"   status: {eb.dataStatus}")
        print(f"   missingFields: {eb.missingFields}")
        with open(os.path.join(output_dir, 'error_state_example.json'), 'w', encoding='utf-8') as f:
            f.write(_json_dumps(eb))
        results.append(("error_example", "OK"))
    except Exception as e:
        print(f"   [FAIL] 异常: {e}")
        results.append(("error_example", "FAIL"))

    # 状态语义验证
    print(f"\n🔬 状态语义验证")
    bundle = get_stock_data_bundle(symbol)

    # 300866: 应为 OK 或 PARTIAL
    if symbol == "300866":
        if bundle.dataStatus in ("OK", "PARTIAL"):
            print(f"   [PASS] 300866 dataStatus={bundle.dataStatus} (符合预期: OK/PARTIAL)")
        else:
            print(f"   [FAIL] 300866 dataStatus={bundle.dataStatus} (应为 OK 或 PARTIAL)")
            results.append(("300866_semantic", "FAIL"))

    # 999999: 应为 EMPTY
    if symbol == "999999":
        if bundle.dataStatus == "EMPTY":
            print(f"   [PASS] 999999 dataStatus=EMPTY (符合预期)")
        else:
            print(f"   [FAIL] 999999 dataStatus={bundle.dataStatus} (应为 EMPTY)")
            results.append(("999999_semantic", "FAIL"))

    # abc: 应为 ERROR
    if symbol == "abc":
        if bundle.dataStatus == "ERROR":
            print(f"   [PASS] abc dataStatus=ERROR (符合预期)")
        else:
            print(f"   [FAIL] abc dataStatus={bundle.dataStatus} (应为 ERROR)")
            results.append(("abc_semantic", "FAIL"))

    # missingFields 粒度检查：不应包含粗粒度字段
    coarse_fields = {"searchItem", "quote", "kline"}
    if bundle.missingFields:
        coarse_found = set(bundle.missingFields) & coarse_fields
        if coarse_found:
            print(f"   [FAIL] missingFields 包含粗粒度字段: {coarse_found}")
            results.append(("missingFields_granularity", "FAIL"))
        else:
            print(f"   [PASS] missingFields 不包含粗粒度字段（粒度OK）")
    else:
        print(f"   [PASS] missingFields 为空（数据完整）")

    # 汇总
    print(f"\n{'='*60}")
    passed = sum(1 for _, r in results if r == "OK")
    failed = len(results) - passed
    print(f"结果: {passed}/{len(results)} 通过, {failed}/{len(results)} 失败")
    print(f"样例输出: {output_dir}")
    if failed > 0:
        sys.exit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', default='300866', help='股票代码')
    parser.add_argument('--output-dir', default=None, help='样例输出目录')
    args = parser.parse_args()
    run_smoke(args.symbol, args.output_dir)
