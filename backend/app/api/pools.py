"""股票池 API"""
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.daily_price import DailyPrice

router = APIRouter(prefix="/api/pools", tags=["股票池"])

POOL_DISPLAY_LIMIT = 70  # 每类股票池默认展示上限


@router.get("")
def get_stock_pool(
    type: str = Query("quality", description="池类型: quality/undervalued/trend/risk/steady/aggressive/conservative/volatile"),
    db: Session = Depends(get_db),
):
    """获取股票池"""
    from sqlalchemy import func
    from datetime import timedelta

    latest = db.query(func.max(StockScore.score_date)).scalar()
    if not latest:
        return {"type": type, "items": []}

    # 周波动>2%池：基于最近5个交易日价格计算
    if type == "volatile":
        return _get_volatile_pool(db)

    query = (
        db.query(StockScore, Stock)
        .join(Stock, StockScore.stock_id == Stock.id)
        .filter(StockScore.score_date == latest, Stock.status == "ACTIVE")
    )

    if type == "quality":
        query = query.filter(StockScore.quality_score >= 10).order_by(StockScore.quality_score.desc())
    elif type == "undervalued":
        query = query.filter(StockScore.valuation_score >= 5).order_by(StockScore.valuation_score.desc())
    elif type == "trend":
        query = query.filter(StockScore.trend_score >= 8).order_by(StockScore.trend_score.desc())
    elif type == "risk":
        query = query.filter(StockScore.risk_score < 5).order_by(StockScore.risk_score.asc())
    elif type == "steady":
        # 稳健优选：质量分>=20 且 风险分>=6
        query = query.filter(
            StockScore.quality_score >= 20,
            StockScore.risk_score >= 6,
        ).order_by(StockScore.total_score.desc())
    elif type == "aggressive":
        # 进取优选：成长分>=15 且 趋势分>=15
        query = query.filter(
            StockScore.growth_score >= 15,
            StockScore.trend_score >= 15,
        ).order_by(StockScore.total_score.desc())
    elif type == "conservative":
        # 保守优选：估值分>=15 且 质量分>=18
        query = query.filter(
            StockScore.valuation_score >= 15,
            StockScore.quality_score >= 18,
        ).order_by(StockScore.total_score.desc())
    else:
        query = query.order_by(StockScore.total_score.desc())

    results = query.limit(POOL_DISPLAY_LIMIT * 2).all()  # 多取一些，后面还要过滤

    # 批量查询最新价格（消除 N+1）
    stock_ids = [st.id for _, st in results]
    price_map = {}
    if stock_ids:
        latest_date_sq = db.query(
            DailyPrice.stock_id,
            func.max(DailyPrice.trade_date).label("max_date")
        ).filter(DailyPrice.stock_id.in_(stock_ids)).group_by(DailyPrice.stock_id).subquery()
        prices = db.query(DailyPrice).join(
            latest_date_sq,
            (DailyPrice.stock_id == latest_date_sq.c.stock_id) &
            (DailyPrice.trade_date == latest_date_sq.c.max_date)
        ).all()
        price_map = {p.stock_id: p for p in prices}

    items = []
    for sc, st in results:
        price = price_map.get(st.id)
        # 稳健池额外过滤PE<60（排除高估值）
        if type == "steady" and price and price.pe and price.pe >= 60:
            continue
        items.append({
            "symbol": st.symbol,
            "name": st.name,
            "market": st.market,
            "industry": st.industry,
            "total_score": sc.total_score,
            "quality_score": sc.quality_score,
            "valuation_score": sc.valuation_score,
            "growth_score": sc.growth_score,
            "trend_score": sc.trend_score,
            "risk_score": sc.risk_score,
            "rating": sc.rating,
            "reason": sc.reason_summary,
            "latest_close": price.close if price else None,
            "pe": price.pe if price else None,
            "pb": price.pb if price else None,
        })

    # 限制展示数量
    items = items[:POOL_DISPLAY_LIMIT]
    return {"type": type, "date": str(latest), "count": len(items), "items": items, "has_more": len(items) >= POOL_DISPLAY_LIMIT}


def _get_volatile_pool(db) -> dict:
    """获取周波动>2%的活跃标的（SQL 层过滤，避免全量加载）"""
    from sqlalchemy import func

    # 获取最新交易日
    latest_date = db.query(func.max(DailyPrice.trade_date)).scalar()
    if not latest_date:
        return {"type": "volatile", "items": [], "date": None}

    # 取最近5个交易日
    recent_dates = (
        db.query(DailyPrice.trade_date)
        .distinct()
        .order_by(DailyPrice.trade_date.desc())
        .limit(5)
        .all()
    )
    if len(recent_dates) < 2:
        return {"type": "volatile", "items": [], "date": str(latest_date)}

    min_date = recent_dates[-1][0]

    # SQL 层聚合：按 stock_id 计算波动率，直接过滤 >= 2%
    stats = db.query(
        DailyPrice.stock_id,
        func.max(DailyPrice.high).label("week_high"),
        func.min(DailyPrice.low).label("week_low"),
        func.max(DailyPrice.close).label("latest_close"),
        func.count().label("day_count"),
    ).join(
        Stock, Stock.id == DailyPrice.stock_id
    ).filter(
        Stock.status == "ACTIVE",
        DailyPrice.trade_date >= min_date,
        DailyPrice.trade_date <= latest_date,
    ).group_by(
        DailyPrice.stock_id
    ).having(
        func.count() >= 2
    ).all()

    # 内存中仅保留波动率 >= 2% 的记录（已大幅减少数据量）
    items = []
    stock_ids_in_items = []
    for row in stats:
        volatility = (row.week_high - row.week_low) / row.week_low * 100 if row.week_low > 0 else 0
        if volatility >= 2.0:
            stock_ids_in_items.append(row.stock_id)

    if not stock_ids_in_items:
        return {"type": "volatile", "date": str(latest_date), "count": 0, "items": []}

    # 批量查询这些 stock 的信息
    stock_objs = db.query(Stock).filter(Stock.id.in_(stock_ids_in_items)).all()
    stock_map = {s.id: s for s in stock_objs}

    # 批量查询最新价格（用于 close/pe/pb）
    latest_price_subq = db.query(
        DailyPrice.stock_id,
        func.max(DailyPrice.trade_date).label("max_date")
    ).filter(DailyPrice.stock_id.in_(stock_ids_in_items)).group_by(DailyPrice.stock_id).subquery()
    latest_prices = db.query(DailyPrice).join(
        latest_price_subq,
        (DailyPrice.stock_id == latest_price_subq.c.stock_id) &
        (DailyPrice.trade_date == latest_price_subq.c.max_date)
    ).all()
    price_map = {p.stock_id: p for p in latest_prices}

    # 计算价格变动需要首尾价格
    first_price_subq = db.query(
        DailyPrice.stock_id,
        func.min(DailyPrice.trade_date).label("min_date")
    ).filter(
        DailyPrice.stock_id.in_(stock_ids_in_items),
        DailyPrice.trade_date >= min_date,
    ).group_by(DailyPrice.stock_id).subquery()
    first_prices = db.query(DailyPrice).join(
        first_price_subq,
        (DailyPrice.stock_id == first_price_subq.c.stock_id) &
        (DailyPrice.trade_date == first_price_subq.c.min_date)
    ).all()
    first_price_map = {p.stock_id: p.close for p in first_prices}

    for row in stats:
        if row.stock_id not in stock_ids_in_items:
            continue
        stock = stock_map.get(row.stock_id)
        if not stock:
            continue
        volatility = (row.week_high - row.week_low) / row.week_low * 100 if row.week_low > 0 else 0
        first_close = first_price_map.get(row.stock_id, row.latest_close)
        price_change = (row.latest_close - first_close) / first_close * 100 if first_close and first_close > 0 else 0
        latest_price = price_map.get(row.stock_id)

        items.append({
            "symbol": stock.symbol,
            "name": stock.name,
            "market": stock.market,
            "industry": stock.industry,
            "total_score": 0,
            "quality_score": 0,
            "valuation_score": 0,
            "growth_score": 0,
            "trend_score": 0,
            "risk_score": 0,
            "rating": "N/A",
            "reason": f"周波动率 {volatility:.1f}% | 涨跌幅 {price_change:+.1f}%",
            "latest_close": latest_price.close if latest_price else row.latest_close,
            "pe": latest_price.pe if latest_price else None,
            "pb": latest_price.pb if latest_price else None,
            "volatility": round(volatility, 2),
            "price_change": round(price_change, 2),
        })

    items.sort(key=lambda x: x.get("volatility", 0), reverse=True)
    items = items[:POOL_DISPLAY_LIMIT]

    # 批量补充评分数据
    if items:
        latest_score_date = db.query(func.max(StockScore.score_date)).scalar()
        if latest_score_date:
            scores = db.query(StockScore).filter(
                StockScore.stock_id.in_(stock_ids_in_items),
                StockScore.score_date == latest_score_date,
            ).all()
            score_map = {sc.stock_id: sc for sc in scores}
            for item in items:
                stock_obj = None
                for s in stock_objs:
                    if s.symbol == item["symbol"]:
                        stock_obj = s
                        break
                sc = score_map.get(stock_obj.id) if stock_obj else None
                if sc:
                    item["total_score"] = sc.total_score
                    item["quality_score"] = sc.quality_score
                    item["valuation_score"] = sc.valuation_score
                    item["growth_score"] = sc.growth_score
                    item["trend_score"] = sc.trend_score
                    item["risk_score"] = sc.risk_score
                    item["rating"] = sc.rating

    return {"type": "volatile", "date": str(latest_date), "count": len(items), "items": items, "has_more": len(items) >= POOL_DISPLAY_LIMIT}
