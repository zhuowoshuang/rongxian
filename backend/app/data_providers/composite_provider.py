"""
组合数据源 - 路由各方法到最优数据源
行情: 腾讯 (快速, 无限流, 通过 EastMoneyProvider)
财务: Yahoo Finance (A股 + 港股) -> 东方财富 fallback
研报: 东方财富
指数: 腾讯 (通过 EastMoneyProvider)
股票列表: Sina + Tencent (在 stock_sync 模块中)
"""
from datetime import date
import pandas as pd

from app.data_providers.base import DataProviderBase
from app.data_providers.yahoo_provider import YahooFinanceProvider
from app.data_providers.eastmoney_provider import EastMoneyProvider


class CompositeProvider(DataProviderBase):
    """组合数据源 - 自动选择最优数据源"""

    def __init__(self):
        self.yahoo = YahooFinanceProvider()
        self.eastmoney = EastMoneyProvider()

    def fetch_stock_list(self, market: str) -> pd.DataFrame:
        return self.eastmoney.fetch_stock_list(market)

    def fetch_daily_prices(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        return self.eastmoney.fetch_daily_prices(symbol, start_date, end_date)

    def fetch_financial_metrics(self, symbol: str) -> pd.DataFrame:
        df = self.yahoo.fetch_financial_metrics(symbol)
        if df.empty:
            df = self.eastmoney.fetch_financial_metrics(symbol)
        return df

    def fetch_market_index(self, market: str) -> list:
        return self.eastmoney.fetch_market_index(market)

    def fetch_news(self, symbol: str, limit: int = 10) -> list:
        return self.yahoo.fetch_news(symbol, limit)

    def fetch_valuation(self, symbol: str) -> dict:
        val = self.yahoo.fetch_valuation(symbol)
        if not val:
            val = self.eastmoney.fetch_valuation(symbol)
        return val

    def fetch_reports(self, symbol: str = None, page: int = 1, page_size: int = 20) -> dict:
        return self.eastmoney.fetch_reports(symbol, page, page_size)
