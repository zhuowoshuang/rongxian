#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
契约验证脚本 v1.1

验证 examples/ 下所有 JSON：
  - 是否包含 dataStatus / source / updateTime / missingFields / errorMessage
  - quote 是否包含 isRealtime
  - fallback quote 是否包含 realtimeQuote 缺失
  - 999999 是否不是 PARTIAL
  - abc 非法代码是否为 ERROR

用法：
  python qs_migration_package/contract_tests/validate_examples.py
"""

import json
import os
import sys
from typing import Dict, Any, List, Tuple

_EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'examples')

# 期望的字段集
COMMON_KEYS = {'dataStatus', 'missingFields', 'errorMessage'}
QUOTE_KEYS = COMMON_KEYS | {'symbol', 'name', 'price', 'change', 'changePct',
                              'open', 'high', 'low', 'preClose', 'volume', 'amount',
                              'turnoverRate', 'source', 'isRealtime', 'tradeDate',
                              'market', 'exchange', 'updateTime', 'quoteStatusReason'}
KLINE_KEYS = COMMON_KEYS | {'symbol', 'period', 'items', 'source', 'updateTime'}
BAR_KEYS = {'date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'turnoverRate'}
BUNDLE_KEYS = COMMON_KEYS | {'symbol', 'searchItem', 'quote', 'kline', 'financials',
                               'sourceSummary', 'updateTime'}
FIN_KEYS = COMMON_KEYS | {'period', 'revenue', 'revenueYoy', 'netProfit', 'profitYoy',
                            'grossMargin', 'netMargin', 'roe', 'debtRatio', 'eps',
                            'source', 'updateTime'}


def load_json(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_keys(data: Any, required: set, label: str) -> List[str]:
    """检查 dict 是否包含所有 required key"""
    if not isinstance(data, dict):
        return [f"{label}: 不是 dict"]
    missing = required - set(data.keys())
    return [f"{label}: 缺少字段 {m}" for m in sorted(missing)]


def check_status(data: Dict, label: str, expected_not: List[str]) -> List[str]:
    """检查 dataStatus 是否不等于 expected_not"""
    errors = []
    status = data.get('dataStatus')
    if not status:
        errors.append(f"{label}: 缺少 dataStatus")
        return errors
    for s in expected_not:
        if status == s:
            errors.append(f"{label}: dataStatus 不应为 {s}")
    return errors


def validate_all() -> Tuple[int, int]:
    errors: List[str] = []
    warnings: List[str] = []

    files = [f for f in os.listdir(_EXAMPLES_DIR) if f.endswith('.json')]
    if not files:
        errors.append("examples/ 目录下没有 JSON 文件")
        return len(errors), 0

    print(f"验证 {len(files)} 个样例文件...\n")

    for fname in sorted(files):
        path = os.path.join(_EXAMPLES_DIR, fname)
        data = load_json(path)
        print(f"  📄 {fname}")

        # 根据文件名推断类型
        is_bundle = 'bundle' in fname
        is_quote = 'quote' in fname
        is_kline = 'kline' in fname
        is_fin = 'financials' in fname
        is_error = 'error' in fname

        if is_bundle:
            errs = check_keys(data, BUNDLE_KEYS, fname)
            errors.extend(errs)
            for e in errs: print(f"    ❌ {e}")

            # 检查子结构
            if data.get('quote'):
                errors.extend(check_keys(data['quote'], QUOTE_KEYS, f"{fname}.quote"))
            if data.get('kline') and data['kline'].get('items'):
                for i, bar in enumerate(data['kline']['items'][:3]):
                    errors.extend(check_keys(bar, BAR_KEYS, f"{fname}.kline.items[{i}]"))

            # 状态验证
            if is_error:
                errors.extend(check_status(data, fname, ["PARTIAL"]))  # 错误示例不应是 PARTIAL
            elif '999999' in fname:
                errors.extend(check_status(data, fname, ["PARTIAL", "OK"]))

        elif is_quote:
            errs = check_keys(data, QUOTE_KEYS, fname)
            errors.extend(errs)
            for e in errs: print(f"    ❌ {e}")

            # Fallback 检查
            if data.get('source') == 'AData-Kline-Fallback':
                if data.get('isRealtime') is not False:
                    errors.append(f"{fname}: fallback quote isRealtime 应为 false")
                if 'realtimeQuote' not in data.get('missingFields', []):
                    errors.append(f"{fname}: fallback quote missingFields 应包含 realtimeQuote")
                if data.get('dataStatus') != 'PARTIAL':
                    errors.append(f"{fname}: fallback quote dataStatus 应为 PARTIAL")
                if not data.get('quoteStatusReason'):
                    errors.append(f"{fname}: fallback quote 缺少 quoteStatusReason")

        elif is_kline:
            errs = check_keys(data, KLINE_KEYS, fname)
            errors.extend(errs)
            for e in errs: print(f"    ❌ {e}")
            if data.get('items'):
                for i, bar in enumerate(data['items'][:1]):
                    errors.extend(check_keys(bar, BAR_KEYS, f"{fname}.items[{i}]"))

        elif is_fin:
            if isinstance(data, list):
                for i, item in enumerate(data[:2]):
                    errors.extend(check_keys(item, FIN_KEYS, f"{fname}[{i}]"))
            else:
                errors.append(f"{fname}: 应为 list 而非 dict")

        # 通用检查
        if 'dataStatus' not in data:
            errors.append(f"{fname}: 缺少 dataStatus")
        else:
            valid_statuses = {'OK', 'PARTIAL', 'EMPTY', 'ERROR'}
            if data['dataStatus'] not in valid_statuses:
                errors.append(f"{fname}: 非法 dataStatus={data['dataStatus']}")

        if 'source' not in data and 'sourceSummary' not in data:
            warnings.append(f"{fname}: 缺少 source/sourceSummary")

        ok_count = sum(1 for e in errors if fname in e)
        if ok_count == 0:
            print(f"    ✅ 通过")

    # 汇总
    print(f"\n{'='*50}")
    print(f"结果: {len(errors)} 错误, {len(warnings)} 警告")
    if errors:
        print("\n❌ 错误详情:")
        for e in errors:
            print(f"  - {e}")
    if warnings:
        print("\n⚠️ 警告:")
        for w in warnings:
            print(f"  - {w}")

    return len(errors), len(warnings)


def run_smoke_with_code(code: str):
    """对单个代码运行 smoke test 并生成样例"""
    print(f"\n{'='*60}")
    print(f"Smoke: {code}")
    print(f"{'='*60}")

    # 添加路径
    _here = os.path.dirname(os.path.abspath(__file__))
    _pkg = os.path.join(_here, '..', 'python')
    sys.path.insert(0, os.path.abspath(_pkg))

    from qs_backend_bridge.stock_data_service import get_stock_data_bundle

    bundle = get_stock_data_bundle(code)
    print(f"  dataStatus: {bundle.dataStatus}")
    print(f"  missingFields: {bundle.missingFields}")
    if bundle.errorMessage:
        print(f"  errorMessage: {bundle.errorMessage}")
    if bundle.quote:
        print(f"  quote.status: {bundle.quote.dataStatus}")
        print(f"  quote.isRealtime: {bundle.quote.isRealtime}")
        print(f"  quote.source: {bundle.quote.source}")
    if bundle.kline:
        print(f"  kline.items: {len(bundle.kline.items)}")
    print(f"  financials: {len(bundle.financials)} 期")

    # 写入样例
    out_dir = _EXAMPLES_DIR
    if code == "999999":
        fname = "error_state_example.json"
    elif code == "abc":
        fname = "illegal_code_example.json"
    else:
        fname = f"bundle_{code}_validated.json"

    out_path = os.path.join(out_dir, fname)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2,
                  default=lambda o: o.value if hasattr(o, 'value') else (
                      o.isoformat() if hasattr(o, 'isoformat') else str(o)))

    print(f"  样例: {out_path}")
    return bundle


if __name__ == '__main__':
    # 1. 验证已有样例
    errors, warnings = validate_all()

    # 2. 生成 300866 / 999999 / abc 的验证样例
    print("\n" + "="*60)
    print("生成验证样例")
    print("="*60)

    for code in ["300866", "999999", "abc"]:
        try:
            run_smoke_with_code(code)
        except Exception as e:
            print(f"  ❌ {code} 失败: {e}")

    if errors > 0:
        sys.exit(1)
    else:
        print("\n✅ 所有样例验证通过")
