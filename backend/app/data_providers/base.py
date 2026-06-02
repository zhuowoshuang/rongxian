"""
数据源适配器基类
所有数据源（AkShare、Tushare、富途、Yahoo Finance）都实现此接口
"""
from abc import ABC, abstractmethod
from typing import Optional
from datetime import date
import pandas as pd


class DataProviderBase(ABC):
    """数据源基类 - 定义统一的数据获取接口"""

    @abstractmethod
    def fetch_stock_list(self, market: str) -> pd.DataFrame:
        """
        获取股票列表
        Args:
            market: 市场类型 (A_SHARE / HK)
        Returns:
            DataFrame: columns=[symbol, name, market, exchange, industry]
        """
        pass

    @abstractmethod
    def fetch_daily_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """
        获取日线行情数据
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
        Returns:
            DataFrame: columns=[trade_date, open, high, low, close, volume, turnover, ...]
        """
        pass

    @abstractmethod
    def fetch_financial_metrics(self, symbol: str) -> pd.DataFrame:
        """
        获取财务指标
        Args:
            symbol: 股票代码
        Returns:
            DataFrame: columns=[report_period, revenue, net_profit, roe, ...]
        """
        pass

    @abstractmethod
    def fetch_market_index(self, market: str) -> dict:
        """
        获取市场指数数据
        Args:
            market: 市场类型
        Returns:
            dict: {name, code, current, change, change_pct}
        """
        pass

    @abstractmethod
    def fetch_news(self, symbol: str, limit: int = 10) -> list[dict]:
        """
        获取股票相关新闻
        Args:
            symbol: 股票代码
            limit: 返回条数
        Returns:
            list[dict]: [{title, url, date, source}]
        """
        pass
