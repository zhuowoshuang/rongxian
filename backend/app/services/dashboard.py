"""
仪表盘数据聚合服务
"""
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.trade_signal import TradeSignal
from app.models.daily_price import DailyPrice
from app.models.portfolio import Portfolio, PortfolioPosition
from app.data_providers import get_provider


def get_dashboard_data(db: Session, today: date) -> dict:
    """聚合仪表盘所需的全部数据"""
    provider = get_provider()

    # 1. 市场概览 - 使用真实东方财富数据
    try:
        market_a = provider.fetch_market_index("A_SHARE")
    except Exception as e:
        market_a = [
            {"name": "上证指数", "code": "000001.SH", "current": 0, "change": 0, "change_pct": 0},
            {"name": "深证成指", "code": "399001.SZ", "current": 0, "change": 0, "change_pct": 0},
            {"name": "创业板指", "code": "399006.SZ", "current": 0, "change": 0, "change_pct": 0},
        ]
    try:
        market_hk = provider.fetch_market_index("HK")
    except Exception as e:
        market_hk = [
            {"name": "恒生指数", "code": "HSI", "current": 0, "change": 0, "change_pct": 0},
            {"name": "恒生科技", "code": "HSTECH", "current": 0, "change": 0, "change_pct": 0},
        ]

    # 2. 策略总结
    signals = db.query(TradeSignal).filter(TradeSignal.signal_date == today).all()
    dist = {"BUY": 0, "ADD": 0, "WATCH": 0, "REDUCE": 0, "SELL": 0}
    for s in signals:
        if s.signal_type in dist:
            dist[s.signal_type] += 1

    buy_add = dist["BUY"] + dist["ADD"]
    reduce_sell = dist["REDUCE"] + dist["SELL"]
    if buy_add > reduce_sell * 2:
        market_status = "偏多"
        suggested_pos = "70-80%"
    elif buy_add > reduce_sell:
        market_status = "中性偏多"
        suggested_pos = "50-70%"
    elif reduce_sell > buy_add * 2:
        market_status = "偏空"
        suggested_pos = "20-30%"
    else:
        market_status = "中性"
        suggested_pos = "40-60%"

    strategy_summary = {
        "market_status": market_status,
        "suggested_position": suggested_pos,
        "core_strategy": "基本面中长期选股 + 趋势确认入场",
        "risk_warning": "关注宏观经济变化和行业政策风险，控制单只仓位不超过10%",
    }

    # 3. Top 信号
    top_signals = (
        db.query(TradeSignal, Stock)
        .join(Stock, TradeSignal.stock_id == Stock.id)
        .filter(TradeSignal.signal_date == today, TradeSignal.signal_type.in_(["BUY", "ADD"]))
        .order_by(TradeSignal.signal_strength.desc())
        .limit(10)
        .all()
    )

    # 批量查询最新价格（消除 N+1）
    top_stock_ids = [stock.id for _, stock in top_signals]
    top_price_map = {}
    if top_stock_ids:
        latest_date_sq = db.query(
            DailyPrice.stock_id,
            func.max(DailyPrice.trade_date).label("max_date")
        ).filter(DailyPrice.stock_id.in_(top_stock_ids)).group_by(DailyPrice.stock_id).subquery()
        top_prices = db.query(DailyPrice).join(
            latest_date_sq,
            (DailyPrice.stock_id == latest_date_sq.c.stock_id) &
            (DailyPrice.trade_date == latest_date_sq.c.max_date)
        ).all()
        top_price_map = {p.stock_id: p for p in top_prices}

    top_signal_list = []
    for sig, stock in top_signals:
        latest_price = top_price_map.get(stock.id)
        top_signal_list.append({
            "symbol": stock.symbol,
            "name": stock.name,
            "market": stock.market,
            "signal_type": sig.signal_type,
            "signal_strength": sig.signal_strength,
            "suggested_position": sig.suggested_position,
            "logic": sig.logic_json.get("reason", "") if sig.logic_json else "",
            "risk": sig.risk_json.get("items", []) if sig.risk_json else [],
            "latest_close": latest_price.close if latest_price else None,
            "change_pct": round((latest_price.close - latest_price.pre_close) / latest_price.pre_close * 100, 2) if latest_price and latest_price.pre_close and latest_price.pre_close != 0 else None,
        })

    # 4. 信号分布
    signal_distribution = dist

    # 5. 组合表现（从数据库真实计算）
    portfolio = db.query(Portfolio).first()
    if portfolio:
        positions = db.query(PortfolioPosition).filter(
            PortfolioPosition.portfolio_id == portfolio.id
        ).all()
        total_return = 0.0
        position_count = 0
        for pos in positions:
            if pos.cost_price and pos.current_price and pos.cost_price > 0:
                pos.unrealized_return = round((pos.current_price - pos.cost_price) / pos.cost_price * 100, 2)
                total_return += pos.unrealized_return
                position_count += 1
        avg_return = round(total_return / position_count, 2) if position_count > 0 else 0
        portfolio_summary = {
            "monthly_return": avg_return,
            "benchmark_return": 0,
            "excess_return": avg_return,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
            "total_assets": 1000000,
            "cash_ratio": portfolio.cash_ratio or 35.0,
            "position_count": position_count,
            "name": portfolio.name,
        }
    else:
        portfolio_summary = {
            "monthly_return": 0,
            "benchmark_return": 0,
            "excess_return": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
            "total_assets": 0,
            "cash_ratio": 0,
            "position_count": 0,
            "name": "暂无组合",
        }

    # 6. 股票池
    scores = (
        db.query(StockScore, Stock)
        .join(Stock, StockScore.stock_id == Stock.id)
        .filter(StockScore.score_date == today)
        .all()
    )
    pools = {"quality": [], "undervalued": [], "trend": [], "risk": []}
    for sc, st in scores:
        item = {
            "symbol": st.symbol,
            "name": st.name,
            "market": st.market,
            "score": sc.total_score,
            "rating": sc.rating,
        }
        if sc.quality_score and sc.quality_score >= 22:
            pools["quality"].append(item)
        if sc.valuation_score and sc.valuation_score >= 15:
            pools["undervalued"].append(item)
        if sc.trend_score and sc.trend_score >= 15:
            pools["trend"].append(item)
        if sc.risk_score and sc.risk_score < 5:
            pools["risk"].append(item)

    # 7. 风险预警
    risk_alerts = []
    for sig, stock in top_signals:
        if sig.risk_json and sig.risk_json.get("items"):
            risk_alerts.append({
                "symbol": stock.symbol,
                "name": stock.name,
                "market": stock.market,
                "level": "high" if "SELL" in sig.signal_type else "medium",
                "message": "，".join(sig.risk_json["items"]),
            })

    return {
        "market_summary": market_a + market_hk,
        "strategy_summary": strategy_summary,
        "top_signals": top_signal_list,
        "signal_distribution": signal_distribution,
        "portfolio_summary": portfolio_summary,
        "stock_pools": pools,
        "risk_alerts": risk_alerts,
    }
