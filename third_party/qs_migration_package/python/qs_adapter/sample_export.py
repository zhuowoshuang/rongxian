# -*- coding: utf-8 -*-
"""
样例导出工具

用法：
  python -m qs_adapter.sample_export

将 300866（安克创新）的综合数据包导出为 examples/qs_stock_bundle_300866.json
"""

import json
import os
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum

from qs_adapter.stock_adapter import get_stock_data_bundle


def _snake_to_camel(name: str) -> str:
    """snake_case → camelCase"""
    parts = name.split('_')
    return parts[0] + ''.join(p.title() for p in parts[1:])


def _camelize_dict(d: dict) -> dict:
    """递归将 dict 的 key 从 snake_case 转为 camelCase"""
    result = {}
    for k, v in d.items():
        new_key = _snake_to_camel(k)
        if isinstance(v, dict):
            result[new_key] = _camelize_dict(v)
        elif isinstance(v, list):
            result[new_key] = [
                _camelize_dict(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            result[new_key] = v
    return result


def _to_dict(obj) -> dict:
    """将 dataclass / Enum / datetime 转为可 JSON 序列化的字典"""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, '__dataclass_fields__'):
        return asdict(obj)
    return str(obj)


def _json_serializer(obj):
    """自定义 JSON 序列化"""
    return _to_dict(obj)


def export_bundle(symbol: str = "300866", output_dir: str = None):
    """
    导出个股综合数据包为 JSON。

    Args:
        symbol: 股票代码
        output_dir: 输出目录，默认为项目根目录下的 examples/
    """
    if output_dir is None:
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'examples'
        )
    os.makedirs(output_dir, exist_ok=True)

    print(f"正在获取 {symbol} 综合数据包...")
    bundle = get_stock_data_bundle(symbol)

    # 转为 camelCase JSON
    raw = _to_dict(bundle)
    camel = raw  # asdict 保留了 snake_case，这里保持原始命名
    # 可选：如需 camelCase 输出，取消下行注释
    # camel = _camelize_dict(raw)

    output_path = os.path.join(output_dir, f'qs_stock_bundle_{symbol}.json')

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(camel, f, ensure_ascii=False, indent=2, default=_json_serializer)

    print(f"✅ 已导出: {output_path}")
    print(f"   symbol:         {bundle.symbol}")
    print(f"   dataStatus:     {bundle.data_status}")
    print(f"   sourceSummary:  {bundle.source_summary}")
    print(f"   missingFields:  {bundle.missing_fields}")
    if bundle.error_message:
        print(f"   errorMessage:   {bundle.error_message}")
    if bundle.quote:
        q = bundle.quote
        print(f"   quote.price:    {q.price}")
        print(f"   quote.status:   {q.data_status}")
    if bundle.kline:
        print(f"   kline.items:    {len(bundle.kline.items)} 条")
        print(f"   kline.status:   {bundle.kline.data_status}")
    print(f"   financials:     {len(bundle.financials)} 期")

    return output_path


if __name__ == '__main__':
    export_bundle("300866")
