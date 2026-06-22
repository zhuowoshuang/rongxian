"""
Yahoo Finance 数据源
用于获取 A 股和港股的行情、财务、估值数据
A 股代码格式: 600519.SS (沪) / 000001.SZ (深)
港股代码格式: 0700.HK
"""
import os
import logging
from datetime import date, timedelta
from typing import Optional
import pandas as pd

# 保存并临时清除代理环境变量（仅影响 yfinance 导入阶段）
_PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")
_saved_proxy = {}
for _var in _PROXY_VARS:
    _saved_proxy[_var] = os.environ.pop(_var, None)

import yfinance as yf

# 恢复代理环境变量
for _var, _val in _saved_proxy.items():
    if _val is not None:
        os.environ[_var] = _val

from app.data_providers.base import DataProviderBase

logger = logging.getLogger(__name__)


def _to_yahoo_symbol(symbol: str) -> str:
    """将内部代码转为 Yahoo Finance 格式"""
    if len(symbol) == 5 and symbol.isdigit():
        # 港股: 00700 -> 0700.HK (去掉前导零)
        return f"{int(symbol):04d}.HK"
    if symbol.startswith(("6", "5")):
        return f"{symbol}.SS"
    return f"{symbol}.SZ"


class YahooFinanceProvider(DataProviderBase):
    """Yahoo Finance 数据源 - 支持 A 股和港股"""

    def fetch_stock_list(self, market: str) -> pd.DataFrame:
        # Yahoo Finance 没有好的全量股票列表 API
        # 由 stock_sync 模块使用 Sina/Tencent 获取
        return pd.DataFrame()

    def fetch_daily_prices(
        self, symbol: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        yahoo_sym = _to_yahoo_symbol(symbol)
        try:
            df = yf.download(
                yahoo_sym,
                start=start_date.isoformat(),
                end=end_date.isoformat(),
                progress=False,
                auto_adjust=False,
            )
        except Exception as e:
            logger.warning(f"Yahoo download failed for {yahoo_sym}: {e}")
            return pd.DataFrame()

        if df.empty:
            return pd.DataFrame()

        # yfinance 返回的 columns 可能是 MultiIndex (symbol, field)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        rows = []
        for idx, row in df.iterrows():
            trade_date = idx
            if hasattr(trade_date, "date"):
                trade_date = trade_date.date()
            # 使用 None 替代 0 表示缺失值，防止下游误将 0 当作真实价格
            open_val = row.get("Open")
            high_val = row.get("High")
            low_val = row.get("Low")
            close_val = row.get("Close")
            vol_val = row.get("Volume")
            rows.append({
                "trade_date": trade_date,
                "open": float(open_val) if pd.notna(open_val) and open_val else None,
                "high": float(high_val) if pd.notna(high_val) and high_val else None,
                "low": float(low_val) if pd.notna(low_val) and low_val else None,
                "close": float(close_val) if pd.notna(close_val) and close_val else None,
                "volume": float(vol_val) if pd.notna(vol_val) and vol_val else 0,
                "turnover": 0,
                "turnover_rate": 0,
                "pre_close": None,
                "market_cap": None,
                "pe": None,
                "pb": None,
                "dividend_yield": None,
            })
        # 过滤掉关键字段为 None 的行
        return pd.DataFrame([r for r in rows if r["close"] is not None])

    def fetch_financial_metrics(self, symbol: str) -> pd.DataFrame:
        yahoo_sym = _to_yahoo_symbol(symbol)
        try:
            ticker = yf.Ticker(yahoo_sym)
            financials = ticker.financials
            balance = ticker.balance_sheet
        except Exception as e:
            logger.warning(f"Yahoo financials failed for {yahoo_sym}: {e}")
            return pd.DataFrame()

        if financials is None or financials.empty:
            return pd.DataFrame()

        rows = []
        for col in financials.columns[:8]:
            period = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
            fin = financials[col] if col in financials.columns else pd.Series()
            bal = balance[col] if balance is not None and col in balance.columns else pd.Series()

            revenue = _safe_get(fin, "Total Revenue")
            net_income = _safe_get(fin, "Net Income")
            gross_profit = _safe_get(fin, "Gross Profit")
            operating_income = _safe_get(fin, "Operating Income")
            total_assets = _safe_get(bal, "Total Assets")
            total_equity = _safe_get(bal, "Stockholders Equity")
            total_debt = _safe_get(bal, "Total Debt")

            revenue_yi = revenue / 1e8 if revenue else None
            net_profit_yi = net_income / 1e8 if net_income else None
            gross_margin = (gross_profit / revenue * 100) if gross_profit and revenue else None
            net_margin = (net_income / revenue * 100) if net_income and revenue else None
            roe = (net_income / total_equity * 100) if net_income and total_equity else None
            roa = (net_income / total_assets * 100) if net_income and total_assets else None
            debt_ratio = (total_debt / total_assets * 100) if total_debt and total_assets else None

            rows.append({
                "report_period": period,
                "revenue": round(revenue_yi, 2) if revenue_yi else None,
                "revenue_yoy": None,
                "net_profit": round(net_profit_yi, 2) if net_profit_yi else None,
                "net_profit_yoy": None,
                "gross_margin": round(gross_margin, 2) if gross_margin else None,
                "net_margin": round(net_margin, 2) if net_margin else None,
                "roe": round(roe, 2) if roe else None,
                "roa": round(roa, 2) if roa else None,
                "debt_ratio": round(debt_ratio, 2) if debt_ratio else None,
                "operating_cashflow": None,
                "free_cashflow": None,
                "eps": _safe_get(fin, "Diluted EPS"),
                "book_value_per_share": None,
            })
        return pd.DataFrame(rows)

    def fetch_market_index(self, market: str) -> list:
        if market == "A_SHARE":
            symbols = [
                ("000001.SS", "上证指数", "000001.SH"),
                ("399001.SZ", "深证成指", "399001.SZ"),
                ("399006.SZ", "创业板指", "399006.SZ"),
            ]
        else:
            symbols = [
                ("^HSI", "恒生指数", "HSI"),
                ("^HSTECH", "恒生科技", "HSTECH"),
            ]

        indices = []
        for yahoo_sym, name, code in symbols:
            try:
                df = yf.download(yahoo_sym, period="5d", progress=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                if df.empty:
                    raise ValueError("No data")
                current = float(df["Close"].iloc[-1])
                prev = float(df["Close"].iloc[-2]) if len(df) > 1 else current
                change = current - prev
                change_pct = (change / prev * 100) if prev else 0
                indices.append({
                    "name": name,
                    "code": code,
                    "current": round(current, 2),
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                })
            except Exception as e:
                logger.warning(f"Yahoo index failed for {yahoo_sym}: {e}")
                indices.append({"name": name, "code": code, "current": 0, "change": 0, "change_pct": 0})
        return indices

    def fetch_valuation(self, symbol: str) -> dict:
        """获取估值数据 - 从已有的行情和财务数据计算 PE/PB"""
        yahoo_sym = _to_yahoo_symbol(symbol)
        try:
            # 获取最新价格
            df = yf.download(yahoo_sym, period="5d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df.empty:
                return {}
            latest_close = float(df["Close"].iloc[-1])

            # 获取财务数据计算 PE
            ticker = yf.Ticker(yahoo_sym)
            financials = ticker.financials
            balance = ticker.balance_sheet

            pe = None
            pb = None
            market_cap = None

            if financials is not None and not financials.empty:
                col = financials.columns[0]
                fin = financials[col]
                eps = _safe_get(fin, "Diluted EPS")
                if eps and eps > 0:
                    pe = round(latest_close / eps, 2)

                # 从资产负债表获取每股净资产计算 PB
                if balance is not None and not balance.empty:
                    bal = balance[col] if col in balance.columns else pd.Series()
                    total_equity = _safe_get(bal, "Stockholders Equity")
                    shares = _safe_get(fin, "Diluted Average Shares")
                    if total_equity and shares and shares > 0:
                        bvps = total_equity / shares
                        pb = round(latest_close / bvps, 2) if bvps > 0 else None
                        market_cap = round(latest_close * shares / 1e8, 2)

            return {
                "pe": pe,
                "pb": pb,
                "market_cap": market_cap,
                "float_market_cap": None,
                "dividend_yield": None,
            }
        except Exception as e:
            logger.warning(f"Yahoo valuation failed for {yahoo_sym}: {e}")
            return {}

    def fetch_news(self, symbol: str, limit: int = 10) -> list:
        yahoo_sym = _to_yahoo_symbol(symbol)
        try:
            ticker = yf.Ticker(yahoo_sym)
            news = ticker.news or []
            results = []
            for item in news[:limit]:
                content = item.get("content", {})
                results.append({
                    "title": content.get("title", item.get("title", "")),
                    "url": content.get("canonicalUrl", {}).get("url", item.get("link", "")),
                    "date": content.get("pubDate", ""),
                    "source": content.get("provider", {}).get("displayName", ""),
                })
            return results
        except Exception as e:
            logger.warning(f"Yahoo news failed for {yahoo_sym}: {e}")
            return []


def _safe_get(series, key):
    try:
        val = series.get(key)
        if val is None or pd.isna(val):
            return None
        return float(val)
    except (ValueError, TypeError, AttributeError):
        return None


def _safe_float(val):
    if val is None:
        return None
    try:
        f = float(val)
        return f if not pd.isna(f) else None
    except (ValueError, TypeError):
        return None


def _safe_div(val, divisor):
    f = _safe_float(val)
    if f is None:
        return None
    return f / divisor
