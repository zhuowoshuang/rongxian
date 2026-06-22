"""
股票列表同步服务 - 从 akshare 拉取全部A股+港股代码入库
研报同步服务 - 从东方财富拉取研报入库
"""
import json
import time
import os
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.stock import Stock
from app.models.research_report import ResearchReport
from app.data_providers import get_provider

logger = logging.getLogger(__name__)


def _fetch_akshare_stock_list(market: str) -> list:
    """从 akshare 获取全量股票列表
    market: A_SHARE 或 HK
    返回: [{"symbol": "600519", "name": "贵州茅台", "exchange": "SH"}, ...]
    """
    import akshare as ak

    all_stocks = []

    if market == "A_SHARE":
        # A 股：使用 stock_info_a_code_name 获取全量代码
        df = ak.stock_info_a_code_name()
        for _, row in df.iterrows():
            code = str(row["code"]).zfill(6)
            name = str(row["name"]).strip()
            if not code or not name:
                continue
            exchange = "SH" if code.startswith(("6", "5", "9")) else "SZ"
            all_stocks.append({
                "symbol": code,
                "name": name,
                "exchange": exchange,
            })
    else:
        # 港股：使用 stock_hk_spot 获取全量代码
        df = ak.stock_hk_spot()
        # 列名可能是中文或英文，按位置取
        cols = list(df.columns)
        code_col = cols[1] if len(cols) > 1 else "代码"  # 第二列是代码
        name_col = cols[2] if len(cols) > 2 else "名称"  # 第三列是中文名称
        for _, row in df.iterrows():
            code = str(row[code_col]).zfill(5)
            name = str(row[name_col]).strip()
            if not code or not name or code == "nan":
                continue
            all_stocks.append({
                "symbol": code,
                "name": name,
                "exchange": "HK",
            })

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
            stocks = _fetch_akshare_stock_list(mkt)
            logger.info(f"{mkt}: 获取到 {len(stocks)} 只股票")

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
            logger.error(f"{mkt} 同步失败: {e}")
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
