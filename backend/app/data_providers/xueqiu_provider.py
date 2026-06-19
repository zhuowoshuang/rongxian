"""
雪球(Xueqiu)数据提供者
需要配置 xq_a_token 才能使用，token 通过管理后台 API 配置设置
"""
import json
import logging
import pandas as pd
from datetime import date, datetime
from typing import Optional
from app.data_providers.base import DataProviderBase
from app.data_providers.http_client import get_json

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://xueqiu.com",
    "Referer": "https://xueqiu.com/",
}


def _get_token() -> Optional[str]:
    """从数据库获取雪球 token"""
    try:
        from app.db.session import SessionLocal
        from app.models.api_config import ApiConfig
        from app.core.config import decrypt_api_key
        db = SessionLocal()
        config = db.query(ApiConfig).filter(ApiConfig.provider == "xueqiu").first()
        db.close()
        if config and config.is_enabled and config.api_key:
            return decrypt_api_key(config.api_key)
    except Exception:
        pass
    return None


def _xq_request(url: str, token: str, timeout: int = 15) -> dict:
    """发送雪球 API 请求（统一 HTTP 客户端）"""
    headers = {**_HEADERS, "Cookie": f"xq_a_token={token}"}
    return get_json(url, headers=headers, timeout=timeout)


def _to_xueqiu_symbol(symbol: str) -> str:
    """转换为雪球符号格式"""
    if len(symbol) == 5 and symbol.isdigit():
        return symbol  # 港股
    if symbol.startswith(("6", "5")):
        return f"SH{symbol}"
    return f"SZ{symbol}"


class XueqiuProvider(DataProviderBase):
    """雪球数据提供者"""

    def __init__(self):
        self._token = None

    def _ensure_token(self):
        if not self._token:
            self._token = _get_token()
        if not self._token:
            raise ValueError("雪球 token 未配置，请在管理后台 API 配置中设置 xq_a_token")

    def fetch_stock_list(self, market: str) -> pd.DataFrame:
        """获取股票列表"""
        self._ensure_token()
        xq_market = "CN" if market == "A_SHARE" else "HK"
        xq_type = "sh_sz" if market == "A_SHARE" else "hk_main"
        all_stocks = []
        page = 1
        while True:
            url = (
                f"https://stock.xueqiu.com/v5/stock/screener/quote/list.json"
                f"?page={page}&size=5000&order_by=symbol&order=asc"
                f"&market={xq_market}&type={xq_type}"
            )
            data = _xq_request(url, self._token)
            items = data.get("data", {}).get("list", [])
            if not items:
                break
            for item in items:
                symbol = item.get("symbol", "")
                # 去掉前缀 SH/SZ
                code = symbol[2:] if symbol.startswith(("SH", "SZ")) else symbol
                all_stocks.append({
                    "symbol": code,
                    "name": item.get("name", ""),
                    "market": market,
                    "exchange": "SH" if symbol.startswith("SH") else "SZ" if symbol.startswith("SZ") else "HK",
                    "industry": item.get("industry", ""),
                })
            if len(items) < 5000:
                break
            page += 1
        return pd.DataFrame(all_stocks)

    def fetch_daily_prices(self, symbol: str, start_date, end_date) -> pd.DataFrame:
        """获取日线数据（兼容 str 和 date 类型参数）"""
        self._ensure_token()
        # 兼容 str 和 date 类型
        if isinstance(start_date, str):
            sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        else:
            sd = start_date
        if isinstance(end_date, str):
            ed = datetime.strptime(end_date, "%Y-%m-%d").date()
        else:
            ed = end_date

        xq_symbol = _to_xueqiu_symbol(symbol)
        begin_ts = int(datetime(sd.year, sd.month, sd.day).timestamp() * 1000)
        url = (
            f"https://stock.xueqiu.com/v5/stock/chart/kline.json"
            f"?symbol={xq_symbol}&begin={begin_ts}&period=day&type=before&count=-500"
        )
        data = _xq_request(url, self._token)
        items = data.get("data", {}).get("item", [])
        columns = data.get("data", {}).get("column", [])
        if not items or not columns:
            return pd.DataFrame()
        rows = []
        for item in items:
            row = dict(zip(columns, item))
            rows.append({
                "trade_date": datetime.fromtimestamp(row.get("timestamp", 0) / 1000).date(),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("volume"),
                "turnover": row.get("amount"),
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df[(df["trade_date"] >= sd) & (df["trade_date"] <= ed)]
        return df

    def fetch_financial_metrics(self, symbol: str) -> pd.DataFrame:
        """获取财务数据"""
        self._ensure_token()
        xq_symbol = _to_xueqiu_symbol(symbol)
        url = (
            f"https://stock.xueqiu.com/v5/finance/income/stock.json"
            f"?symbol={xq_symbol}&type=all&is_detail=true&count=8"
        )
        data = _xq_request(url, self._token)
        items = data.get("data", {}).get("list", [])
        if not items:
            return pd.DataFrame()
        rows = []
        for item in items:
            rows.append({
                "report_period": item.get("report_date_name", ""),
                "revenue": item.get("revenue", 0) / 1e8 if item.get("revenue") else None,
                "net_profit": item.get("net_profit", 0) / 1e8 if item.get("net_profit") else None,
                "gross_margin": item.get("gross_margin"),
                "net_margin": item.get("net_margin"),
                "roe": item.get("roe"),
                "eps": item.get("eps"),
            })
        return pd.DataFrame(rows)

    def fetch_market_index(self, market: str) -> list:
        """获取市场指数"""
        self._ensure_token()
        if market == "A_SHARE":
            symbols = "SH000001,SZ399001,SZ399006"
            names = ["上证指数", "深证成指", "创业板指"]
        else:
            symbols = "HKHSI,HKHSTECH"
            names = ["恒生指数", "恒生科技"]
        url = f"https://stock.xueqiu.com/v5/stock/batch/quote.json?symbol={symbols}"
        data = _xq_request(url, self._token)
        items = data.get("data", {}).get("items", [])
        result = []
        for i, item in enumerate(items):
            quote = item.get("quote", {})
            result.append({
                "name": names[i] if i < len(names) else quote.get("name", ""),
                "code": quote.get("symbol", ""),
                "current": quote.get("current"),
                "change": quote.get("chg"),
                "change_pct": quote.get("percent"),
            })
        return result

    def fetch_news(self, symbol: str, limit: int = 10) -> list:
        """获取新闻"""
        self._ensure_token()
        xq_symbol = _to_xueqiu_symbol(symbol)
        url = f"https://xueqiu.com/query/v1/symbol/search/status.json?symbol={xq_symbol}&count={limit}"
        data = _xq_request(url, self._token)
        items = data.get("list", [])
        return [{"title": i.get("title", ""), "url": i.get("target", ""), "date": i.get("created_at", ""), "source": "雪球"} for i in items]

    def fetch_valuation(self, symbol: str) -> dict:
        """获取估值数据"""
        self._ensure_token()
        xq_symbol = _to_xueqiu_symbol(symbol)
        url = f"https://stock.xueqiu.com/v5/stock/quote.json?symbol={xq_symbol}&extend=detail"
        data = _xq_request(url, self._token)
        quote = data.get("data", {}).get("quote", {})
        return {
            "pe": quote.get("pe_ttm"),
            "pb": quote.get("pb"),
            "market_cap": quote.get("market_capital", 0) / 1e8 if quote.get("market_capital") else None,
            "dividend_yield": quote.get("dividend_yield"),
        }

    def fetch_reports(self, symbol: str = None, page: int = 1, page_size: int = 20) -> dict:
        """获取研报（雪球不提供研报，返回空）"""
        return {"total": 0, "reports": []}
