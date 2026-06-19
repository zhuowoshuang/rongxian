"""
股票列表同步服务 - 从东方财富拉取全部A股+港股代码入库
研报同步服务 - 从东方财富拉取研报入库
"""
import json
import time
import os
import requests
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.stock import Stock
from app.models.research_report import ResearchReport
from app.data_providers import get_provider

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def _fetch_eastmoney_stock_list(market: str) -> list:
    """从东方财富批量获取股票列表
    market: A_SHARE 或 HK
    返回: [{"symbol": "600519", "name": "贵州茅台", "exchange": "SH"}, ...]
    """
    if market == "A_SHARE":
        fs = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
    else:
        fs = "m:128+t:3,m:128+t:4,m:128+t:1,m:128+t:2"

    session = requests.Session()
    session.trust_env = True  # 自动使用系统代理
    all_stocks = []
    page = 1
    while True:
        url = (
            f"https://82.push2.eastmoney.com/api/qt/clist/get"
            f"?pn={page}&pz=5000&po=1&np=1"
            f"&ut=bd1d9ddb04089700cf9c27f6f7426281"
            f"&fltt=2&invt=2&fid=f12"
            f"&fs={fs}"
            f"&fields=f12,f14"
        )
        for retry in range(3):
            try:
                resp = session.get(url, headers=_HEADERS, timeout=30)
                data = resp.json()
                break
            except Exception as e:
                if retry == 2:
                    raise
                time.sleep(1)

        items = data.get("data", {}).get("diff", [])
        if not items:
            break

        for item in items:
            code = str(item.get("f12", ""))
            name = item.get("f14", "")
            if not code or not name:
                continue
            if market == "A_SHARE":
                exchange = "SH" if code.startswith(("6", "5")) else "SZ"
            else:
                exchange = "HK"
            all_stocks.append({
                "symbol": code,
                "name": name,
                "exchange": exchange,
            })

        if len(items) < 5000:
            break
        page += 1
        time.sleep(0.2)

    return all_stocks


def sync_stock_list(db: Session, market: str = "ALL") -> dict:
    """同步股票列表到数据库
    market: A_SHARE / HK / ALL
    返回: {"added": int, "updated": int, "total": int}
    """
    added = 0
    updated = 0
    total = 0

    markets = []
    if market in ("A_SHARE", "ALL"):
        markets.append(("A_SHARE", "CNY"))
    if market in ("HK", "ALL"):
        markets.append(("HK", "HKD"))

    for mkt, currency in markets:
        try:
            stocks = _fetch_eastmoney_stock_list(mkt)
            print(f"[stock_sync] {mkt}: 获取到 {len(stocks)} 只股票")

            for s in stocks:
                existing = db.query(Stock).filter(Stock.symbol == s["symbol"]).first()
                if existing:
                    if existing.name != s["name"]:
                        existing.name = s["name"]
                    if not existing.industry and s.get("industry"):
                        existing.industry = s["industry"]
                    updated += 1
                else:
                    db.add(Stock(
                        symbol=s["symbol"],
                        name=s["name"],
                        market=mkt,
                        exchange=s["exchange"],
                        currency=currency,
                        status="ACTIVE",
                    ))
                    added += 1
                total += 1

            db.commit()
        except Exception as e:
            print(f"[stock_sync] {mkt} 同步失败: {e}")
            db.rollback()

    return {"added": added, "updated": updated, "total": total}


def sync_research_reports(db: Session, symbol: str = None, max_pages: int = 3) -> dict:
    """从东方财富同步研报到数据库"""
    provider = get_provider()
    added = 0
    skipped = 0

    for page in range(1, max_pages + 1):
        result = provider.fetch_reports(symbol=symbol, page=page, page_size=50)
        reports = result.get("reports", [])
        if not reports:
            break

        for r in reports:
            info_code = r.get("info_code", "")
            if not info_code:
                skipped += 1
                continue

            existing = db.query(ResearchReport).filter(
                ResearchReport.info_code == info_code
            ).first()
            if existing:
                skipped += 1
                continue

            pub_date = None
            pd_str = r.get("publish_date", "")
            if pd_str:
                try:
                    pub_date = datetime.strptime(pd_str[:10], "%Y-%m-%d").date()
                except ValueError:
                    pub_date = None

            db.add(ResearchReport(
                info_code=info_code,
                title=r.get("title", ""),
                stock_code=r.get("stock_code", ""),
                stock_name=r.get("stock_name", ""),
                org_name=r.get("org_name", ""),
                publish_date=pub_date,
                rating=r.get("rating", ""),
                industry=r.get("industry", ""),
                researcher=r.get("researcher", ""),
                predict_this_year_eps=r.get("predict_this_year_eps"),
                predict_this_year_pe=r.get("predict_this_year_pe"),
                predict_next_year_eps=r.get("predict_next_year_eps"),
                predict_next_year_pe=r.get("predict_next_year_pe"),
                predict_next_two_year_eps=r.get("predict_next_two_year_eps"),
                predict_next_two_year_pe=r.get("predict_next_two_year_pe"),
                url=r.get("url", ""),
            ))
            added += 1

        db.commit()
        time.sleep(1)

    return {"added": added, "skipped": skipped}
