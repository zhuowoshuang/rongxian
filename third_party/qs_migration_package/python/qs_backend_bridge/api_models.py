# -*- coding: utf-8 -*-
"""
清数智算后端 API 最终返回格式

这些格式与 frontend_contract/stock-data-types.ts 完全一致。
所有字段使用 camelCase，前端可直接反序列化。
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class StockSearchItemResponse:
    symbol: str
    name: Optional[str]
    market: str
    exchange: str
    industry: Optional[str] = None
    status: str = "active"
    source: str = "adata"
    updateTime: Optional[str] = None
    dataStatus: str = "OK"
    missingFields: List[str] = field(default_factory=list)
    errorMessage: Optional[str] = None


@dataclass
class StockQuoteResponse:
    symbol: str
    name: Optional[str]
    market: str
    exchange: str
    tradeDate: Optional[str] = None
    price: Optional[float] = None
    change: Optional[float] = None
    changePct: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    preClose: Optional[float] = None
    volume: Optional[int] = None
    amount: Optional[float] = None
    turnoverRate: Optional[float] = None
    source: str = "adata"
    isRealtime: bool = True
    quoteStatusReason: Optional[str] = None  # 例："实时行情为空，使用最新K线构造延迟行情"
    updateTime: Optional[str] = None
    dataStatus: str = "OK"
    missingFields: List[str] = field(default_factory=list)
    errorMessage: Optional[str] = None


@dataclass
class KlineBarResponse:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    turnoverRate: Optional[float] = None


@dataclass
class StockKlineResponse:
    symbol: str
    period: str
    items: List[KlineBarResponse] = field(default_factory=list)
    source: str = "adata"
    updateTime: Optional[str] = None
    dataStatus: str = "OK"
    missingFields: List[str] = field(default_factory=list)
    errorMessage: Optional[str] = None


@dataclass
class FinancialMetricResponse:
    period: str
    revenue: Optional[float] = None
    revenueYoy: Optional[float] = None
    netProfit: Optional[float] = None
    profitYoy: Optional[float] = None
    grossMargin: Optional[float] = None
    netMargin: Optional[float] = None
    roe: Optional[float] = None
    debtRatio: Optional[float] = None
    eps: Optional[float] = None
    source: str = "adata"
    updateTime: Optional[str] = None
    dataStatus: str = "OK"
    missingFields: List[str] = field(default_factory=list)
    errorMessage: Optional[str] = None


@dataclass
class SourceSummaryResponse:
    quoteSource: str = "unknown"
    klineSource: str = "unknown"
    financialsSource: str = "unknown"
    searchSource: str = "unknown"


@dataclass
class StockDataBundleResponse:
    symbol: str
    searchItem: Optional[StockSearchItemResponse] = None
    quote: Optional[StockQuoteResponse] = None
    kline: Optional[StockKlineResponse] = None
    financials: List[FinancialMetricResponse] = field(default_factory=list)
    sourceSummary: SourceSummaryResponse = field(default_factory=SourceSummaryResponse)
    updateTime: Optional[str] = None
    dataStatus: str = "OK"
    missingFields: List[str] = field(default_factory=list)
    errorMessage: Optional[str] = None
