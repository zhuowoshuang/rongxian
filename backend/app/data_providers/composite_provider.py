"""
组合数据源 - 路由各方法到最优数据源
行情: 腾讯 (快速, 无限流, 通过 EastMoneyProvider)
财务: 雪球 (A股+港股) -> Yahoo Finance -> 东方财富 fallback
研报: 东方财富
指数: 腾讯 (通过 EastMoneyProvider)
股票列表: 东方财富批量API (全量覆盖)
"""
from datetime import date
import logging
import pandas as pd

from app.data_providers.base import DataProviderBase
from app.data_providers.eastmoney_provider import EastMoneyProvider

# YahooFinanceProvider 延迟导入，避免 yfinance 的循环导入问题
_YahooFinanceProvider = None

def _get_yahoo_provider():
    global _YahooFinanceProvider
    if _YahooFinanceProvider is None:
        try:
            from app.data_providers.yahoo_provider import YahooFinanceProvider
            _YahooFinanceProvider = YahooFinanceProvider
        except ImportError as e:
            logger.warning(f"YahooFinanceProvider 不可用: {e}")
            return None
    return _YahooFinanceProvider

logger = logging.getLogger(__name__)


class CompositeProvider(DataProviderBase):
    """组合数据源 - 自动选择最优数据源"""

    def __init__(self):
        self._yahoo = None  # 延迟加载
        self.eastmoney = EastMoneyProvider()
        self._xueqiu = None

    @property
    def yahoo(self):
        """延迟加载 Yahoo 提供者"""
        if self._yahoo is None:
            yahoo_cls = _get_yahoo_provider()
            if yahoo_cls:
                self._yahoo = yahoo_cls()
        return self._yahoo

    @property
    def xueqiu(self):
        """延迟加载雪球提供者"""
        if self._xueqiu is None:
            try:
                from app.data_providers.xueqiu_provider import XueqiuProvider
                self._xueqiu = XueqiuProvider()
            except Exception as e:
                logger.warning(f"雪球提供者初始化失败: {e}")
                self._xueqiu = False  # 标记为不可用
        return self._xueqiu if self._xueqiu is not False else None

    def fetch_stock_list(self, market: str) -> pd.DataFrame:
        return self.eastmoney.fetch_stock_list(market)

    def fetch_daily_prices(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        return self.eastmoney.fetch_daily_prices(symbol, start_date, end_date)

    def fetch_financial_metrics(self, symbol: str) -> pd.DataFrame:
        """财务数据: 雪球 -> Yahoo -> 东方财富"""
        # 优先雪球（覆盖 A 股+港股）
        if self.xueqiu:
            try:
                df = self.xueqiu.fetch_financial_metrics(symbol)
                if not df.empty:
                    return df
            except Exception as e:
                logger.debug(f"雪球财务数据失败 {symbol}: {e}")

        # 其次 Yahoo
        try:
            df = self.yahoo.fetch_financial_metrics(symbol)
            if not df.empty:
                return df
        except Exception:
            pass

        # 最后东方财富
        return self.eastmoney.fetch_financial_metrics(symbol)

    def fetch_market_index(self, market: str) -> list:
        return self.eastmoney.fetch_market_index(market)

    def fetch_news(self, symbol: str, limit: int = 10) -> list:
        """新闻: 雪球 -> Yahoo"""
        if self.xueqiu:
            try:
                news = self.xueqiu.fetch_news(symbol, limit)
                if news:
                    return news
            except Exception:
                pass
        if self.yahoo:
            return self.yahoo.fetch_news(symbol, limit)
        return []

    def fetch_valuation(self, symbol: str) -> dict:
        """估值: 雪球 -> Yahoo -> 东方财富"""
        if self.xueqiu:
            try:
                val = self.xueqiu.fetch_valuation(symbol)
                if val and val.get("pe"):
                    return val
            except Exception as e:
                logger.debug(f"雪球估值失败 {symbol}: {e}")

        val = None
        if self.yahoo:
            try:
                val = self.yahoo.fetch_valuation(symbol)
            except Exception:
                pass
        if not val:
            val = self.eastmoney.fetch_valuation(symbol)
        return val

    def fetch_reports(self, symbol: str = None, page: int = 1, page_size: int = 20) -> dict:
        return self.eastmoney.fetch_reports(symbol, page, page_size)
