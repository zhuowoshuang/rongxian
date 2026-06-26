"""
Mock 数据提供器 - 用于 Docker 部署和离线开发
返回逼真的模拟数据，不依赖任何外部 API
"""
import random
import math
from datetime import datetime, timedelta, date
from typing import Optional
import pandas as pd
import numpy as np

from app.data_providers.base import DataProviderBase


# ==================== 15 只核心股票的模拟数据 ====================

MOCK_STOCKS = {
    # A 股 (10只)
    "600519": {"name": "贵州茅台", "market": "A_SHARE", "industry": "白酒", "sector": "消费",
               "base_price": 1680, "pe": 28.5, "pb": 8.2, "roe": 31.2, "revenue": 1505, "net_profit": 747,
               "revenue_yoy": 16.2, "profit_yoy": 18.5, "debt_ratio": 22.1, "eps": 59.5, "bvps": 204.8},
    "000858": {"name": "五粮液", "market": "A_SHARE", "industry": "白酒", "sector": "消费",
               "base_price": 152, "pe": 22.3, "pb": 5.8, "roe": 25.8, "revenue": 832, "net_profit": 302,
               "revenue_yoy": 12.1, "profit_yoy": 14.2, "debt_ratio": 28.5, "eps": 7.8, "bvps": 26.2},
    "601318": {"name": "中国平安", "market": "A_SHARE", "industry": "保险", "sector": "金融",
               "base_price": 48, "pe": 8.5, "pb": 1.1, "roe": 12.5, "revenue": 9137, "net_profit": 856,
               "revenue_yoy": 3.8, "profit_yoy": -5.2, "debt_ratio": 89.2, "eps": 4.7, "bvps": 43.6},
    "600036": {"name": "招商银行", "market": "A_SHARE", "industry": "银行", "sector": "金融",
               "base_price": 35, "pe": 6.2, "pb": 0.95, "roe": 15.8, "revenue": 3447, "net_profit": 1380,
               "revenue_yoy": 1.2, "profit_yoy": 3.5, "debt_ratio": 92.1, "eps": 5.5, "bvps": 36.8},
    "300750": {"name": "宁德时代", "market": "A_SHARE", "industry": "锂电池", "sector": "新能源",
               "base_price": 185, "pe": 18.5, "pb": 4.2, "roe": 22.8, "revenue": 4009, "net_profit": 441,
               "revenue_yoy": 22.0, "profit_yoy": 43.5, "debt_ratio": 65.8, "eps": 10.1, "bvps": 44.0},
    "601012": {"name": "隆基绿能", "market": "A_SHARE", "industry": "光伏", "sector": "新能源",
               "base_price": 22, "pe": 12.5, "pb": 1.8, "roe": 14.2, "revenue": 1294, "net_profit": 107,
               "revenue_yoy": -5.8, "profit_yoy": -27.5, "debt_ratio": 55.2, "eps": 1.4, "bvps": 12.2},
    "000001": {"name": "平安银行", "market": "A_SHARE", "industry": "银行", "sector": "金融",
               "base_price": 11, "pe": 4.8, "pb": 0.55, "roe": 11.2, "revenue": 1798, "net_profit": 464,
               "revenue_yoy": -2.1, "profit_yoy": -4.5, "debt_ratio": 93.5, "eps": 2.4, "bvps": 20.0},
    "600276": {"name": "恒瑞医药", "market": "A_SHARE", "industry": "医药", "sector": "医药",
               "base_price": 42, "pe": 52.5, "pb": 7.8, "roe": 14.8, "revenue": 228, "net_profit": 43,
               "revenue_yoy": 7.2, "profit_yoy": 10.8, "debt_ratio": 12.5, "eps": 0.7, "bvps": 5.4},
    "603259": {"name": "药明康德", "market": "A_SHARE", "industry": "CXO", "sector": "医药",
               "base_price": 58, "pe": 18.2, "pb": 3.5, "roe": 19.2, "revenue": 403, "net_profit": 96,
               "revenue_yoy": 2.5, "profit_yoy": -1.8, "debt_ratio": 38.5, "eps": 3.2, "bvps": 16.6},
    "600900": {"name": "长江电力", "market": "A_SHARE", "industry": "电力", "sector": "公用",
               "base_price": 28, "pe": 20.5, "pb": 3.8, "roe": 18.5, "revenue": 826, "net_profit": 272,
               "revenue_yoy": 5.2, "profit_yoy": 6.8, "debt_ratio": 62.5, "eps": 1.2, "bvps": 7.4},
    # 港股 (5只)
    "00700": {"name": "腾讯控股", "market": "HK", "industry": "互联网", "sector": "科技",
              "base_price": 380, "pe": 22.8, "pb": 5.2, "roe": 22.5, "revenue": 6090, "net_profit": 1180,
              "revenue_yoy": 7.5, "profit_yoy": 36.2, "debt_ratio": 42.8, "eps": 12.5, "bvps": 73.1},
    "09988": {"name": "阿里巴巴", "market": "HK", "industry": "电商", "sector": "科技",
              "base_price": 78, "pe": 10.5, "pb": 1.5, "roe": 14.2, "revenue": 9411, "net_profit": 795,
              "revenue_yoy": 1.8, "profit_yoy": -3.5, "debt_ratio": 45.2, "eps": 4.1, "bvps": 52.0},
    "09618": {"name": "京东集团", "market": "HK", "industry": "电商", "sector": "科技",
              "base_price": 128, "pe": 12.2, "pb": 1.8, "roe": 14.8, "revenue": 10845, "net_profit": 352,
              "revenue_yoy": 3.2, "profit_yoy": 132.5, "debt_ratio": 52.1, "eps": 11.2, "bvps": 71.1},
    "01810": {"name": "小米集团", "market": "HK", "industry": "消费电子", "sector": "科技",
              "base_price": 18, "pe": 22.5, "pb": 3.2, "roe": 14.2, "revenue": 2709, "net_profit": 174,
              "revenue_yoy": -3.2, "profit_yoy": 126.5, "debt_ratio": 55.8, "eps": 0.7, "bvps": 5.6},
    "02318": {"name": "中国平安H", "market": "HK", "industry": "保险", "sector": "金融",
              "base_price": 38, "pe": 6.8, "pb": 0.85, "roe": 12.5, "revenue": 9137, "net_profit": 856,
              "revenue_yoy": 3.8, "profit_yoy": -5.2, "debt_ratio": 89.2, "eps": 4.7, "bvps": 44.7},
}

MOCK_INDICES = [
    {"name": "上证指数", "code": "000001.SH", "base": 3150, "market": "A_SHARE"},
    {"name": "深证成指", "code": "399001.SZ", "base": 9800, "market": "A_SHARE"},
    {"name": "创业板指", "code": "399006.SZ", "base": 1950, "market": "A_SHARE"},
    {"name": "恒生指数", "code": "HSI", "base": 17800, "market": "HK"},
]

MOCK_NEWS_TEMPLATES = [
    {"title": "{name}发布2024年度业绩报告，净利润同比增长{pct}%", "source": "东方财富"},
    {"title": "机构调研{name}：看好公司长期发展前景", "source": "证券时报"},
    {"title": "{name}获北向资金连续{days}日净买入", "source": "上海证券报"},
    {"title": "{name}宣布新一轮回购计划，彰显管理层信心", "source": "中国证券报"},
    {"title": "券商最新研报：{name}目标价上调至{price}元", "source": "Wind资讯"},
    {"title": "{name}与{partner}签署战略合作协议", "source": "财联社"},
    {"title": "外资机构上调{name}评级至\"买入\"", "source": "彭博社"},
]


def _generate_price_series(base_price: float, days: int = 120, volatility: float = 0.02) -> pd.DataFrame:
    """生成逼真的价格时间序列 - 返回列名匹配 seed.py 期望"""
    rng = np.random.RandomState(int(base_price * 100) % 2**31)
    dates = pd.bdate_range(end=date.today(), periods=days)
    n = len(dates)

    returns = rng.normal(0.0003, volatility, n)
    prices = base_price * np.cumprod(1 + returns)

    # 用 base_price 派生一致的 PE/PB（而非随机）
    # 假设 EPS = base_price / PE_target，然后 PE 随价格波动
    pe_base = max(8, min(60, 1000 / base_price))  # 低价股 PE 偏高，高价股 PE 偏低
    pb_base = max(0.5, min(12, 50 / base_price))

    df = pd.DataFrame({
        "trade_date": dates,
        "open": prices * (1 + rng.uniform(-0.01, 0.01, n)),
        "high": prices * (1 + rng.uniform(0, 0.03, n)),
        "low": prices * (1 - rng.uniform(0, 0.03, n)),
        "close": prices,
        "pre_close": np.roll(prices, 1),
        "volume": rng.uniform(5e6, 5e8, n),
        "turnover": rng.uniform(1e8, 1e10, n),
        "turnover_rate": rng.uniform(0.5, 5, n),
        "market_cap": prices * rng.uniform(1e9, 1e11, n),
        "pe": pe_base * (prices / base_price) * (1 + rng.uniform(-0.05, 0.05, n)),  # PE 随价格变化
        "pb": pb_base * (prices / base_price) * (1 + rng.uniform(-0.05, 0.05, n)),  # PB 随价格变化
        "dividend_yield": rng.uniform(0, 4, n),
    })
    df.iloc[0, df.columns.get_loc("pre_close")] = base_price
    return df


def _generate_financial_metrics(info: dict) -> pd.DataFrame:
    """生成模拟财务数据 - 列名匹配 seed.py 期望"""
    rng = np.random.RandomState(int(info["base_price"] * 7) % 2**31)
    rows = []
    for i in range(4):
        year = 2024 - i
        period = f"{year}-12-31"
        noise = lambda: rng.uniform(0.95, 1.05)
        rows.append({
            "report_period": period,
            "revenue": round(info["revenue"] * noise() * (1 - i * 0.02), 2),
            "revenue_yoy": round(info["revenue_yoy"] * noise(), 2),
            "net_profit": round(info["net_profit"] * noise() * (1 - i * 0.03), 2),
            "net_profit_yoy": round(info["profit_yoy"] * noise(), 2),
            "gross_margin": round(rng.uniform(25, 65), 2),
            "net_margin": round(info["net_profit"] / max(info["revenue"], 1) * 100 * noise(), 2),
            "roe": round(info["roe"] * noise(), 2),
            "roa": round(info["roe"] * 0.6 * noise(), 2),
            "debt_ratio": round(info["debt_ratio"] * noise(), 2),
            "operating_cashflow": round(info["net_profit"] * 0.8 * noise(), 2),
            "free_cashflow": round(info["net_profit"] * 0.5 * noise(), 2),
            "eps": round(info["eps"] * noise() * (1 - i * 0.02), 2),
            "book_value_per_share": round(info["bvps"] * noise() * (1 + i * 0.03), 2),
        })
    return pd.DataFrame(rows)


class MockProvider(DataProviderBase):
    """模拟数据提供器 - 用于 Docker 部署和离线开发"""

    def fetch_stock_list(self, market: str) -> pd.DataFrame:
        rows = []
        for symbol, info in MOCK_STOCKS.items():
            if market != "ALL" and info["market"] != market:
                continue
            rows.append({
                "symbol": symbol,
                "name": info["name"],
                "market": info["market"],
                "exchange": "SSE" if symbol.startswith("6") else "SZSE" if info["market"] == "A_SHARE" else "HKEX",
                "industry": info["industry"],
                "sector": info["sector"],
            })
        return pd.DataFrame(rows)

    def fetch_daily_prices(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        info = MOCK_STOCKS.get(symbol)
        if not info:
            # 为未知股票生成随机基础数据
            rng = random.Random(hash(symbol) % 2**31)
            base_price = rng.uniform(5, 500)
            info = {"base_price": base_price, "sector": "其他"}
        volatility = 0.025 if info.get("sector") == "科技" else 0.018
        df = _generate_price_series(info["base_price"], days=180, volatility=volatility)
        if start_date:
            df = df[df["trade_date"] >= pd.Timestamp(start_date)]
        if end_date:
            df = df[df["trade_date"] <= pd.Timestamp(end_date)]
        return df

    def fetch_financial_metrics(self, symbol: str) -> pd.DataFrame:
        info = MOCK_STOCKS.get(symbol)
        if not info:
            # 为未知股票生成随机财务数据
            rng = random.Random(hash(symbol) % 2**31)
            info = {
                "base_price": rng.uniform(5, 500),
                "revenue": rng.uniform(100, 5000),
                "revenue_yoy": rng.uniform(-10, 30),
                "net_profit": rng.uniform(10, 500),
                "profit_yoy": rng.uniform(-15, 40),
                "debt_ratio": rng.uniform(20, 80),
                "eps": rng.uniform(0.5, 10),
                "bvps": rng.uniform(3, 50),
                "roe": rng.uniform(5, 25),
            }
        return _generate_financial_metrics(info)

    def fetch_market_index(self, market: str) -> list:
        rows = []
        for idx in MOCK_INDICES:
            if market != "ALL" and idx["market"] != market:
                continue
            rng = np.random.RandomState(int(idx["base"]) % 2**31)
            change_pct = round(rng.uniform(-1.5, 1.8), 2)
            current = round(idx["base"] * (1 + change_pct / 100), 2)
            rows.append({
                "name": idx["name"],
                "code": idx["code"],
                "current": current,
                "change": round(current - idx["base"], 2),
                "change_pct": change_pct,
            })
        return rows

    def fetch_news(self, symbol: str, limit: int = 10) -> list[dict]:
        info = MOCK_STOCKS.get(symbol)
        if not info:
            return []
        rng = np.random.RandomState(int(info["base_price"] * 11) % 2**31)
        news = []
        for i in range(min(limit, len(MOCK_NEWS_TEMPLATES))):
            template = MOCK_NEWS_TEMPLATES[i]
            title = template["title"].format(
                name=info["name"],
                pct=round(rng.uniform(5, 30), 1),
                days=rng.randint(3, 15),
                price=round(info["base_price"] * np.random.uniform(1.1, 1.3), 0),
                partner=np.random.choice(["华为", "腾讯", "阿里", "字节跳动", "中科院"]),
            )
            news.append({
                "title": title,
                "url": f"https://finance.eastmoney.com/a/mock_{symbol}_{i}.html",
                "date": (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d"),
                "source": template["source"],
            })
        return news

    def fetch_valuation(self, symbol: str) -> dict:
        info = MOCK_STOCKS.get(symbol)
        if not info:
            return {}
        rng = np.random.RandomState(int(info["base_price"] * 3) % 2**31)
        return {
            "pe": round(info["pe"] * rng.uniform(0.95, 1.05), 2),
            "pb": round(info["pb"] * rng.uniform(0.95, 1.05), 2),
            "market_cap": round(info["base_price"] * rng.uniform(1e8, 5e10), 0),
            "dividend_yield": round(rng.uniform(0.5, 4.0), 2),
        }

    def fetch_reports(self, symbol: str = None, page: int = 1, page_size: int = 20) -> dict:
        info = MOCK_STOCKS.get(symbol) if symbol else None
        if not info:
            return {"total": 0, "items": []}
        rng = np.random.RandomState(int(info["base_price"] * 13) % 2**31)
        orgs = ["中信证券", "华泰证券", "国泰君安", "招商证券", "中金公司", "海通证券", "申万宏源"]
        ratings = ["买入", "增持", "买入", "增持", "强推", "买入", "增持"]
        researchers = ["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九"]
        reports = []
        for i in range(5):
            org = orgs[i % len(orgs)]
            reports.append({
                "info_code": f"MOCK{symbol}{i:03d}",
                "title": f"{info['name']}：{rng.choice(['业绩稳健增长', '行业龙头地位稳固', '新业务放量可期', '估值修复空间大', '回购彰显信心'])}",
                "stock_code": symbol,
                "stock_name": info["name"],
                "org_name": org,
                "publish_date": (datetime.now() - timedelta(days=np.random.randint(1, 60))).strftime("%Y-%m-%d"),
                "rating": ratings[i % len(ratings)],
                "industry": info["industry"],
                "researcher": researchers[i % len(researchers)],
                "predict_this_year_eps": round(info["eps"] * np.random.uniform(1.0, 1.2), 2),
                "predict_this_year_pe": round(info["pe"] * np.random.uniform(0.9, 1.1), 1),
                "predict_next_year_eps": round(info["eps"] * np.random.uniform(1.1, 1.4), 2),
                "predict_next_year_pe": round(info["pe"] * np.random.uniform(0.8, 1.0), 1),
                "predict_next_two_year_eps": round(info["eps"] * np.random.uniform(1.2, 1.6), 2),
                "predict_next_two_year_pe": round(info["pe"] * np.random.uniform(0.7, 0.9), 1),
                "url": f"https://data.eastmoney.com/report/mock/{symbol}_{i}.html",
            })
        return {"total": len(reports), "reports": reports}
