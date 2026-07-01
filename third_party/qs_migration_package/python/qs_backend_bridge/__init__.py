# -*- coding: utf-8 -*-
"""
清数智算 Backend Bridge

本层在 qs_adapter 之上提供：
  - 非交易时段 quote fallback
  - 股票名称补齐
  - 统一 camelCase API 返回格式
"""

from .stock_data_service import (
    search_stocks,
    get_stock_quote,
    get_stock_kline,
    get_stock_financials,
    get_stock_data_bundle,
)
from .api_models import (
    StockSearchItemResponse,
    StockQuoteResponse,
    KlineBarResponse,
    StockKlineResponse,
    FinancialMetricResponse,
    StockDataBundleResponse,
    SourceSummaryResponse,
)
from .data_status import DataStatus
