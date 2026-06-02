"""股票池 API"""
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.daily_price import DailyPrice

router = APIRouter(prefix="/api/pools", tags=["股票池"])


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
        query = query.filter(StockScore.quality_score >= 22).order_by(StockScore.quality_score.desc())
    elif type == "undervalued":
        query = query.filter(StockScore.valuation_score >= 15).order_by(StockScore.valuation_score.desc())
    elif type == "trend":
        query = query.filter(StockScore.trend_score >= 15).order_by(StockScore.trend_score.desc())
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

    results = query.all()
    items = []
    for sc, st in results:
        price = (
            db.query(DailyPrice)
            .filter(DailyPrice.stock_id == st.id)
            .order_by(DailyPrice.trade_date.desc())
            .first()
        )
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

    return {"type": type, "date": str(latest), "count": len(items), "items": items}


def _get_volatile_pool(db) -> dict:
    """获取周波动>2%的活跃标的"""
    from sqlalchemy import func
    from datetime import date, timedelta

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

    # 获取所有股票在该时间段的价格
    stocks = db.query(Stock).filter(Stock.status == "ACTIVE").all()
    stock_map = {s.id: s for s in stocks}

    items = []
    for stock in stocks:
        prices = (
            db.query(DailyPrice)
            .filter(
                DailyPrice.stock_id == stock.id,
                DailyPrice.trade_date >= min_date,
                DailyPrice.trade_date <= latest_date,
            )
            .order_by(DailyPrice.trade_date)
            .all()
        )
        if len(prices) < 2:
            continue

        # 计算周波动率：(最高收盘 - 最低收盘) / 最低收盘 * 100
        closes = [p.close for p in prices]
        highs = [p.high for p in prices]
        lows = [p.low for p in prices]

        week_high = max(highs)
        week_low = min(lows)
        volatility = (week_high - week_low) / week_low * 100 if week_low > 0 else 0

        if volatility >= 2.0:
            price_change = (closes[-1] - closes[0]) / closes[0] * 100 if closes[0] > 0 else 0
            latest_price = prices[-1]
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
                "latest_close": latest_price.close,
                "pe": latest_price.pe,
                "pb": latest_price.pb,
                "volatility": round(volatility, 2),
                "price_change": round(price_change, 2),
            })

    # 按波动率降序排列
    items.sort(key=lambda x: x.get("volatility", 0), reverse=True)

    # 补充评分数据
    latest_score_date = db.query(func.max(StockScore.score_date)).scalar()
    if latest_score_date:
        for item in items:
            stock = db.query(Stock).filter(Stock.symbol == item["symbol"]).first()
            if stock:
                sc = db.query(StockScore).filter(
                    StockScore.stock_id == stock.id,
                    StockScore.score_date == latest_score_date,
                ).first()
                if sc:
                    item["total_score"] = sc.total_score
                    item["quality_score"] = sc.quality_score
                    item["valuation_score"] = sc.valuation_score
                    item["growth_score"] = sc.growth_score
                    item["trend_score"] = sc.trend_score
                    item["risk_score"] = sc.risk_score
                    item["rating"] = sc.rating

    return {"type": "volatile", "date": str(latest_date), "count": len(items), "items": items}
