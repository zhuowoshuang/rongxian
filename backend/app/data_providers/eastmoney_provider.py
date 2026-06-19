"""
混合数据源 - 东方财富 + 腾讯 API
东方财富: 股票列表、财务数据
腾讯: 日线行情、实时行情、市场指数
"""
import re
import json
import logging
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.parse import urlencode
from app.data_providers.base import DataProviderBase
from app.data_providers.http_client import get_json, get_text

logger = logging.getLogger(__name__)


def _curl_get(url: str, timeout: int = 15) -> dict:
    """GET 请求并返回 JSON（统一 HTTP 客户端）"""
    return get_json(url, timeout=timeout)


def _curl_get_text(url: str, timeout: int = 15) -> str:
    """GET 请求并返回文本（统一 HTTP 客户端）"""
    return get_text(url, timeout=timeout)


class EastMoneyProvider(DataProviderBase):
    """混合数据源：东方财富 + 腾讯（全部通过 curl）"""

    # ==================== 股票列表 (东方财富) ====================

    def fetch_stock_list(self, market: str) -> pd.DataFrame:
        if market == "A_SHARE":
            return self._fetch_a_share_list()
        else:
            return self._fetch_hk_list()

    def _fetch_a_share_list(self) -> pd.DataFrame:
        """获取全部 A 股列表（分页）"""
        url = "https://82.push2.eastmoney.com/api/qt/clist/get"
        all_rows = []
        page = 1
        while True:
            params = urlencode({
                "pn": page, "pz": 5000, "po": 1, "np": 1,
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": 2, "invt": 2, "fid": "f12",
                "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
                "fields": "f12,f14,f2,f3,f9,f23,f115,f116,f117",
            })
            data = _curl_get(f"{url}?{params}")
            items = data.get("data", {}).get("diff", [])
            if not items:
                break
            for item in items:
                code = item.get("f12", "")
                name = item.get("f14", "")
                if not code or not name:
                    continue
                exchange = "SH" if code.startswith(("6", "5")) else "SZ"
                all_rows.append({
                    "symbol": code, "name": name, "market": "A_SHARE",
                    "exchange": exchange, "industry": "", "sector": "",
                })
            if len(items) < 5000:
                break
            page += 1
            import time
            time.sleep(0.2)
        logger.info(f"A 股列表获取完成: {len(all_rows)} 只")
        return pd.DataFrame(all_rows)

    def _fetch_hk_list(self) -> pd.DataFrame:
        """获取全部港股列表（分页）"""
        url = "https://82.push2.eastmoney.com/api/qt/clist/get"
        all_rows = []
        page = 1
        while True:
            params = urlencode({
                "pn": page, "pz": 5000, "po": 1, "np": 1,
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": 2, "invt": 2, "fid": "f12",
                "fs": "m:128+t:3,m:128+t:4,m:128+t:1,m:128+t:2",
                "fields": "f12,f14,f2,f3",
            })
            data = _curl_get(f"{url}?{params}")
            items = data.get("data", {}).get("diff", [])
            if not items:
                break
            for item in items:
                code = item.get("f12", "")
                name = item.get("f14", "")
                if not code or not name:
                    continue
                all_rows.append({
                    "symbol": code, "name": name, "market": "HK",
                    "exchange": "HK", "industry": "", "sector": "",
                })
            if len(items) < 5000:
                break
            page += 1
            import time
            time.sleep(0.2)
        logger.info(f"港股列表获取完成: {len(all_rows)} 只")
        return pd.DataFrame(all_rows)

    # ==================== 日线行情 (腾讯) ====================

    def fetch_daily_prices(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        if len(symbol) == 5 and symbol.isdigit():
            return self._fetch_hk_daily(symbol, start_date, end_date)
        else:
            return self._fetch_a_daily(symbol, start_date, end_date)

    def _tencent_code(self, symbol: str) -> str:
        if len(symbol) == 5 and symbol.isdigit():
            return f"hk{symbol}"
        elif symbol.startswith(("6", "5")):
            return f"sh{symbol}"
        else:
            return f"sz{symbol}"

    def _fetch_a_daily(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        # 优先用腾讯 API，失败则用 baostock
        try:
            tc = self._tencent_code(symbol)
            url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tc},day,{start_date},{end_date},500,qfq"
            data = _curl_get(url)
            stock_data = data.get("data", {}).get(tc, {})
            klines = stock_data.get("qfqday", stock_data.get("day", []))
            if klines:
                return self._parse_klines(klines)
        except Exception:
            pass
        # baostock 备选
        return self._fetch_a_daily_baostock(symbol, start_date, end_date)

    def _fetch_a_daily_baostock(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        """使用 baostock 获取 A 股日线数据"""
        try:
            import baostock as bs
            lg = bs.login()
            if lg.error_code != '0':
                return pd.DataFrame()
            bs_code = f"sh.{symbol}" if symbol.startswith(("6", "5", "9")) else f"sz.{symbol}"
            rs = bs.query_history_k_data_plus(
                bs_code,
                fields="date,open,high,low,close,volume,amount",
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                frequency="d",
                adjustflag="2",  # 前复权
            )
            rows = []
            while rs.next():
                row = rs.get_row_data()
                if row and len(row) >= 6:
                    try:
                        rows.append({
                            "trade_date": datetime.strptime(row[0], "%Y-%m-%d").date(),
                            "open": float(row[1]),
                            "high": float(row[2]),
                            "low": float(row[3]),
                            "close": float(row[4]),
                            "volume": int(float(row[5])) if row[5] else 0,
                            "turnover": int(float(row[6])) if len(row) > 6 and row[6] else 0,
                        })
                    except (ValueError, IndexError):
                        continue
            bs.logout()
            return pd.DataFrame(rows) if rows else pd.DataFrame()
        except Exception as e:
            logger.debug(f"baostock fetch failed for {symbol}: {e}")
            return pd.DataFrame()

    def _fetch_hk_daily(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        # 优先用腾讯 API，失败则用 akshare
        try:
            tc = f"hk{symbol}"
            url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tc},day,{start_date},{end_date},500,"
            data = _curl_get(url)
            stock_data = data.get("data", {}).get(tc, {})
            klines = stock_data.get("day", stock_data.get("qfqday", []))
            if klines:
                return self._parse_klines(klines)
        except Exception:
            pass
        # akshare 备选
        return self._fetch_hk_daily_akshare(symbol, start_date, end_date)

    def _fetch_hk_daily_akshare(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        """使用 akshare 获取港股日线数据"""
        try:
            import akshare as ak
            df = ak.stock_hk_daily(symbol=symbol, adjust="qfq")
            if df.empty:
                return pd.DataFrame()
            # 过滤日期范围
            df["date"] = pd.to_datetime(df["date"])
            mask = (df["date"].dt.date >= start_date) & (df["date"].dt.date <= end_date)
            df = df[mask].copy()
            if df.empty:
                return pd.DataFrame()
            rows = []
            for _, row in df.iterrows():
                rows.append({
                    "trade_date": row["date"].date(),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": int(float(row["volume"])) if row.get("volume") else 0,
                    "turnover": 0,
                    "turnover_rate": 0,
                    "market_cap": None,
                    "pe": None,
                    "pb": None,
                    "dividend_yield": None,
                })
            return pd.DataFrame(rows)
        except Exception as e:
            logger.debug(f"akshare HK fetch failed for {symbol}: {e}")
            return pd.DataFrame()

    def _parse_klines(self, klines: list) -> pd.DataFrame:
        rows = []
        for line in klines:
            if len(line) < 6:
                continue
            rows.append({
                "trade_date": pd.to_datetime(line[0]).date(),
                "open": float(line[1]),
                "close": float(line[2]),
                "high": float(line[3]),
                "low": float(line[4]),
                "volume": float(line[5]),
                "turnover": 0,
                "turnover_rate": 0,
                "pre_close": None,
                "market_cap": None,
                "pe": None,
                "pb": None,
                "dividend_yield": None,
            })
        return pd.DataFrame(rows)

    # ==================== 实时行情 (腾讯) ====================

    def fetch_realtime_quote(self, symbol: str) -> dict:
        tc = self._tencent_code(symbol)
        url = f"https://qt.gtimg.cn/q={tc}"
        text = _curl_get_text(url)

        match = re.search(r'"([^"]*)"', text)
        if not match:
            return {}
        fields = match.group(1).split("~")
        if len(fields) < 50:
            return {}

        try:
            return {
                "close": float(fields[3]) if fields[3] else None,
                "high": float(fields[33]) if len(fields) > 33 and fields[33] else None,
                "low": float(fields[34]) if len(fields) > 34 and fields[34] else None,
                "open": float(fields[5]) if fields[5] else None,
                "volume": float(fields[6]) if fields[6] else None,
                "turnover": None,
                "pe": float(fields[39]) if len(fields) > 39 and fields[39] else None,
                "pb": None,
                "market_cap": float(fields[45]) if len(fields) > 45 and fields[45] else None,
                "change_pct": float(fields[32]) if len(fields) > 32 and fields[32] else None,
            }
        except (ValueError, IndexError):
            return {}

    # ==================== 财务数据 (东方财富) ====================

    def fetch_financial_metrics(self, symbol: str) -> pd.DataFrame:
        if len(symbol) == 5 and symbol.isdigit():
            return pd.DataFrame()
        return self._fetch_a_financial(symbol)

    def _fetch_a_financial(self, symbol: str) -> pd.DataFrame:
        code = f"SH{symbol}" if symbol.startswith(("6", "5")) else f"SZ{symbol}"
        url = f"https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew?type=0&code={code}"
        try:
            data = _curl_get(url)
        except Exception:
            return pd.DataFrame()

        reports = data.get("data", [])
        rows = []
        for r in reports[:8]:
            rows.append({
                "report_period": r.get("REPORT_DATE_NAME", ""),
                "revenue": self._safe_div(r.get("TOTALOPERATEREVE"), 1e8),
                "revenue_yoy": self._safe_float(r.get("TOTALOPERATEREVETZ")),
                "net_profit": self._safe_div(r.get("PARENTNETPROFIT"), 1e8),
                "net_profit_yoy": self._safe_float(r.get("PARENTNETPROFITTZ")),
                "gross_margin": self._safe_float(r.get("XSMGLL")),
                "net_margin": self._safe_float(r.get("XSJLL")),
                "roe": self._safe_float(r.get("ROEJQ")),
                "roa": self._safe_float(r.get("ROA")),
                "debt_ratio": self._safe_float(r.get("ZCFZL")),
                "operating_cashflow": self._safe_div(r.get("MGJYXJJE"), 1),
                "free_cashflow": None,
                "eps": self._safe_float(r.get("EPSJB")),
                "book_value_per_share": self._safe_float(r.get("BPS")),
            })
        return pd.DataFrame(rows)

    def _safe_float(self, val) -> Optional[float]:
        if val is None or val == "-" or val == "":
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _safe_div(self, val, divisor) -> Optional[float]:
        f = self._safe_float(val)
        if f is None:
            return None
        return f / divisor

    # ==================== 市场指数 (腾讯) ====================

    def fetch_market_index(self, market: str) -> list:
        if market == "A_SHARE":
            codes = [
                ("sh000001", "上证指数", "000001.SH"),
                ("sz399001", "深证成指", "399001.SZ"),
                ("sz399006", "创业板指", "399006.SZ"),
            ]
        else:
            codes = [
                ("hkHSI", "恒生指数", "HSI"),
                ("hkHSTECH", "恒生科技", "HSTECH"),
            ]

        tc_codes = ",".join(c[0] for c in codes)
        url = f"https://qt.gtimg.cn/q={tc_codes}"
        try:
            text = _curl_get_text(url)
        except Exception:
            return [{"name": c[1], "code": c[2], "current": 0, "change": 0, "change_pct": 0} for c in codes]

        indices = []
        for tc, name, code in codes:
            pattern = f'v_{tc}="([^"]*)"'
            match = re.search(pattern, text)
            if not match:
                indices.append({"name": name, "code": code, "current": 0, "change": 0, "change_pct": 0})
                continue
            fields = match.group(1).split("~")
            try:
                current = float(fields[3]) if fields[3] else 0
                pre_close = float(fields[4]) if fields[4] else 0
                change = current - pre_close
                change_pct = float(fields[32]) if len(fields) > 32 and fields[32] else 0
                indices.append({
                    "name": name,
                    "code": code,
                    "current": current,
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                })
            except (ValueError, IndexError):
                indices.append({"name": name, "code": code, "current": 0, "change": 0, "change_pct": 0})
        return indices

    # ==================== 估值数据 (东方财富) ====================

    def fetch_valuation(self, symbol: str) -> dict:
        """获取单只股票的 PE/PB/市值等估值数据"""
        if len(symbol) == 5 and symbol.isdigit():
            return self._fetch_hk_valuation(symbol)
        return self._fetch_a_valuation(symbol)

    def _fetch_a_valuation(self, symbol: str) -> dict:
        """A股估值数据"""
        if symbol.startswith(("6", "5")):
            secid = f"1.{symbol}"
        else:
            secid = f"0.{symbol}"
        url = (
            f"https://push2.eastmoney.com/api/qt/stock/get?"
            f"secid={secid}&fields=f57,f58,f43,f162,f167,f116,f117,f173"
        )
        try:
            data = _curl_get(url)
            d = data.get("data", {})
            if not d:
                return {}
            # 注意: f162(PE), f167(PB) 返回值需要除以100
            pe_raw = self._safe_float(d.get("f162"))
            pb_raw = self._safe_float(d.get("f167"))
            return {
                "pe": round(pe_raw / 100, 2) if pe_raw is not None else None,
                "pb": round(pb_raw / 100, 2) if pb_raw is not None else None,
                "market_cap": self._safe_div(d.get("f116"), 1e8),  # 总市值(亿)
                "float_market_cap": self._safe_div(d.get("f117"), 1e8),
                "dividend_yield": self._safe_float(d.get("f173")),
            }
        except Exception:
            return {}

    def _fetch_hk_valuation(self, symbol: str) -> dict:
        """港股估值数据"""
        secid = f"116.{symbol}"
        url = (
            f"https://push2.eastmoney.com/api/qt/stock/get?"
            f"secid={secid}&fields=f57,f58,f43,f162,f167,f116,f117,f173"
        )
        try:
            data = _curl_get(url)
            d = data.get("data", {})
            if not d:
                return {}
            pe_raw = self._safe_float(d.get("f162"))
            pb_raw = self._safe_float(d.get("f167"))
            return {
                "pe": round(pe_raw / 100, 2) if pe_raw is not None else None,
                "pb": round(pb_raw / 100, 2) if pb_raw is not None else None,
                "market_cap": self._safe_div(d.get("f116"), 1e8),
                "float_market_cap": self._safe_div(d.get("f117"), 1e8),
                "dividend_yield": self._safe_float(d.get("f173")),
            }
        except Exception:
            return {}

    # ==================== 研究报告 (东方财富) ====================

    def fetch_reports(self, symbol: str = None, page: int = 1, page_size: int = 20) -> dict:
        """
        获取券商研究报告列表
        symbol: 股票代码（None 则获取全市场最新报告）
        返回: {"total": int, "reports": [...]}
        """
        from datetime import datetime, timedelta
        end_time = datetime.now().strftime("%Y-%m-%d")
        start_time = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        params = {
            "industryCode": "*",
            "pageNo": page,
            "pageSize": page_size,
            "beginTime": start_time,
            "endTime": end_time,
            "qType": 0,
        }
        if symbol:
            params["code"] = symbol

        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"https://reportapi.eastmoney.com/report/list?{param_str}"

        try:
            data = _curl_get(url)
        except Exception as e:
            return {"total": 0, "reports": [], "error": str(e)}

        reports = []
        for r in data.get("data", []):
            reports.append({
                "title": r.get("title", ""),
                "stock_name": r.get("stockName", ""),
                "stock_code": r.get("stockCode", ""),
                "org_name": r.get("orgSName", ""),
                "publish_date": r.get("publishDate", "")[:10],
                "rating": r.get("emRatingName", ""),
                "industry": r.get("indvInduName", ""),
                "researcher": r.get("researcher", ""),
                "info_code": r.get("infoCode", ""),
                "predict_this_year_eps": self._safe_float(r.get("predictThisYearEps")),
                "predict_this_year_pe": self._safe_float(r.get("predictThisYearPe")),
                "predict_next_year_eps": self._safe_float(r.get("predictNextYearEps")),
                "predict_next_year_pe": self._safe_float(r.get("predictNextYearPe")),
                "predict_next_two_year_eps": self._safe_float(r.get("predictNextTwoYearEps")),
                "predict_next_two_year_pe": self._safe_float(r.get("predictNextTwoYearPe")),
                "url": f"https://data.eastmoney.com/report/info/{r.get('infoCode', '')}.html",
            })

        return {
            "total": data.get("hits", 0),
            "reports": reports,
        }

    # ==================== 新闻 ====================

    def fetch_news(self, symbol: str, limit: int = 10) -> list:
        return []
