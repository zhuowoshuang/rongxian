# -*- coding: utf-8 -*-
"""
清数智算数据适配层 —— AData → 清数智算统一接口

本模块对 AData 原生 API 进行封装，输出统一的 StockSearchItem、
StockQuote、StockKline、FinancialMetric、StockDataBundle 结构。

设计原则：
  1. 不修改 AData 原生行为。
  2. 缺失数据返回 EMPTY / PARTIAL，不编造。
  3. 所有函数对异常进行捕获，返回带 errorMessage 的 ERROR 状态。
"""

from qs_adapter.types import (
    DataStatus,
    StockSearchItem,
    StockQuote,
    KlineBar,
    StockKline,
    FinancialMetric,
    StockDataBundle,
)
from qs_adapter.stock_adapter import (
    search_stocks,
    get_stock_quote,
    get_stock_kline,
    get_stock_financials,
    get_stock_data_bundle,
)
from qs_adapter.errors import (
    QSAdapterError,
    DataNotAvailableError,
    NormalizationError,
)

__all__ = [
    # types
    "DataStatus",
    "StockSearchItem",
    "StockQuote",
    "KlineBar",
    "StockKline",
    "FinancialMetric",
    "StockDataBundle",
    # adapter functions
    "search_stocks",
    "get_stock_quote",
    "get_stock_kline",
    "get_stock_financials",
    "get_stock_data_bundle",
    # errors
    "QSAdapterError",
    "DataNotAvailableError",
    "NormalizationError",
]
