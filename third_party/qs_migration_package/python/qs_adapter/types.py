# -*- coding: utf-8 -*-
"""
清数智算统一数据结构

所有输出结构遵循以下规则：
  - dataStatus 必须包含（OK / PARTIAL / EMPTY / ERROR）
  - missingFields 列出缺失字段名（空列表表示齐全）
  - errorMessage 在非 OK 状态时必须给出原因
  - 缺失数值字段统一为 None，不填 0
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class DataStatus(str, Enum):
    OK = "OK"
    PARTIAL = "PARTIAL"
    EMPTY = "EMPTY"
    ERROR = "ERROR"


# ==================== 个股搜索 ====================

@dataclass
class StockSearchItem:
    """个股搜索结果条目"""
    symbol: str                     # 归一化代码，如 "300866"
    name: str                       # 股票简称，如 "安克创新"
    market: str                     # 市场：A / HK / US
    exchange: str                   # 交易所：SH / SZ / BJ
    industry: Optional[str] = None  # 申万一级行业（AData 可能无）
    status: str = "active"          # active / delisted / suspended

    # 元信息
    source: str = "adata"
    update_time: Optional[str] = None
    data_status: DataStatus = DataStatus.OK
    missing_fields: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


# ==================== 实时行情 ====================

@dataclass
class StockQuote:
    """个股实时/最新行情"""
    symbol: str
    name: Optional[str] = None
    market: str = "A"
    exchange: str = "SZ"

    trade_date: Optional[str] = None
    price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    pre_close: Optional[float] = None
    volume: Optional[int] = None           # 成交量（股）
    amount: Optional[float] = None         # 成交额（元）
    turnover_rate: Optional[float] = None  # 换手率（%）

    source: str = "adata"
    is_realtime: bool = True
    update_time: Optional[str] = None
    data_status: DataStatus = DataStatus.OK
    missing_fields: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


# ==================== K 线 ====================

@dataclass
class KlineBar:
    """单根 K 线"""
    date: str               # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: int             # 成交量（股）
    amount: float           # 成交额（元）
    turnover_rate: Optional[float] = None  # 换手率（%）


@dataclass
class StockKline:
    """个股 K 线序列"""
    symbol: str
    period: str                     # daily / weekly / monthly
    items: List[KlineBar] = field(default_factory=list)

    source: str = "adata"
    update_time: Optional[str] = None
    data_status: DataStatus = DataStatus.OK
    missing_fields: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


# ==================== 财务指标 ====================

@dataclass
class FinancialMetric:
    """单期财务指标"""
    period: str                 # 报告期，如 "2024-12-31"
    revenue: Optional[float] = None             # 营业总收入（元）
    revenue_yoy: Optional[float] = None         # 营收同比（%）
    net_profit: Optional[float] = None          # 归母净利润（元）
    profit_yoy: Optional[float] = None          # 净利润同比（%）
    gross_margin: Optional[float] = None        # 毛利率（%）
    net_margin: Optional[float] = None          # 净利率（%）
    roe: Optional[float] = None                 # ROE（%）
    debt_ratio: Optional[float] = None          # 资产负债率（%）
    eps: Optional[float] = None                 # 基本每股收益（元）

    source: str = "adata"
    update_time: Optional[str] = None
    data_status: DataStatus = DataStatus.OK
    missing_fields: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


# ==================== 综合数据包 ====================

@dataclass
class StockDataBundle:
    """个股综合数据包 —— 清数智算前端一次获取"""
    symbol: str

    search_item: Optional[StockSearchItem] = None
    quote: Optional[StockQuote] = None
    kline: Optional[StockKline] = None
    financials: List[FinancialMetric] = field(default_factory=list)

    source_summary: str = "adata"
    update_time: Optional[str] = None
    data_status: DataStatus = DataStatus.OK
    missing_fields: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
