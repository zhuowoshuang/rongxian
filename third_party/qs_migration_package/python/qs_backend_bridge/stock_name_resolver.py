# -*- coding: utf-8 -*-
"""
股票名称补齐

优先级：
  1. qs_adapter search_stocks 结果中的 name
  2. AData 本地缓存 code.csv
  3. quote 返回字段中的 name / short_name
  4. 仍为空 → name=None, dataStatus=PARTIAL, missingFields += ["name"]

注意：
  - 不写死股票名称映射表（除非 sample-only 明确标注）
  - 不编造名称
"""

import os
import csv
from typing import Optional


# AData 代码缓存路径（相对于项目根目录）
_CODE_CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    'adata', 'stock', 'cache', 'code.csv'
)


def resolve_stock_name(
    symbol: str,
    from_search: Optional[str] = None,
    from_quote: Optional[str] = None,
) -> tuple:
    """
    尽力补齐股票名称。

    Returns:
        (name: Optional[str], source: str, dataStatus: str, missingFields: list, errorMessage: Optional[str])
    """
    name = None
    source = "unknown"

    # 1. 搜索结果
    if from_search and from_search.strip():
        name = from_search.strip()
        source = "search_stocks"

    # 2. quote 返回
    if not name and from_quote and from_quote.strip():
        name = from_quote.strip()
        source = "stock_quote"

    # 3. 本地 code.csv
    if not name:
        csv_name = _lookup_code_csv(symbol)
        if csv_name:
            name = csv_name
            source = "AData-code-csv"

    # 4. 仍为空
    if not name:
        return (
            None,
            "none",
            "PARTIAL",
            ["name"],
            f"无法从 search/quote/code.csv 获取 {symbol} 的名称",
        )

    return (name, source, "OK", [], None)


def _lookup_code_csv(symbol: str) -> Optional[str]:
    """从 AData 本地 code.csv 查找股票名称"""
    sym = str(symbol).zfill(6)
    try:
        if not os.path.exists(_CODE_CSV_PATH):
            return None
        with open(_CODE_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row.get('stock_code', '').strip().zfill(6)
                if code == sym:
                    return row.get('short_name', '').strip() or None
    except Exception:
        pass
    return None
