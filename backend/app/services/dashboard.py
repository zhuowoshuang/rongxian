"""Dashboard data aggregation service."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.data_providers import get_provider
from app.models.daily_price import DailyPrice
from app.models.portfolio import Portfolio, PortfolioPosition
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.trade_signal import TradeSignal
from app.services.compliance import sanitize_research_text


def _fallback_market_indices(market: str) -> list[dict]:
    if market == "A_SHARE":
        return [
            {"name": "上证指数", "code": "000001.SH", "current": 0, "change": 0, "change_pct": 0},
            {"name": "深证成指", "code": "399001.SZ", "current": 0, "change": 0, "change_pct": 0},
            {"name": "创业板指", "code": "399006.SZ", "current": 0, "change": 0, "change_pct": 0},
        ]
    return [
        {"name": "恒生指数", "code": "HSI", "current": 0, "change": 0, "change_pct": 0},
        {"name": "恒生科技", "code": "HSTECH", "current": 0, "change": 0, "change_pct": 0},
    ]


def _market_status_label(status: str) -> str:
    return {
        "bullish": "偏多",
        "mildly_bullish": "中性偏多",
        "neutral": "中性",
        "mildly_bearish": "中性偏谨慎",
        "bearish": "偏空",
    }.get(status, "中性")


def _strategy_summary(dist: dict[str, int]) -> dict:
    buy_add = dist["BUY"] + dist["ADD"]
    reduce_sell = dist["REDUCE"] + dist["SELL"]

    if buy_add > reduce_sell * 2:
        market_status = "bullish"
        suggested_pos = "70-80%"
    elif buy_add > reduce_sell:
        market_status = "mildly_bullish"
        suggested_pos = "50-70%"
    elif reduce_sell > buy_add * 2:
        market_status = "bearish"
        suggested_pos = "20-30%"
    elif reduce_sell > buy_add:
        market_status = "mildly_bearish"
        suggested_pos = "30-45%"
    else:
        market_status = "neutral"
        suggested_pos = "40-60%"

    return {
        "market_status": market_status,
        "market_status_label": _market_status_label(market_status),
        "suggested_position": suggested_pos,
        "core_strategy": "以基本面筛选、估值比较和趋势确认作为研究主线，优先观察评分与信号同步改善的标的。",
        "judgement_basis": [
            f"高关注与增强关注样本合计 {buy_add} 只，风险升高与回避观察样本合计 {reduce_sell} 只。",
            "优先观察五维评分靠前、估值与趋势同步改善的标的。",
            "研究组合表现仅用于模型研究，不代表真实账户收益。",
        ],
        "risk_warning": "研究仓位区间仅用于研究视图，请结合宏观、行业与个股风险独立判断，避免将模型输出视为交易指令。",
    }


def _latest_price_map(db: Session, stock_ids: list[int]) -> dict[int, DailyPrice]:
    if not stock_ids:
        return {}
    latest_date_sq = (
        db.query(DailyPrice.stock_id, func.max(DailyPrice.trade_date).label("max_date"))
        .filter(DailyPrice.stock_id.in_(stock_ids))
        .group_by(DailyPrice.stock_id)
        .subquery()
    )
    prices = (
        db.query(DailyPrice)
        .join(
            latest_date_sq,
            (DailyPrice.stock_id == latest_date_sq.c.stock_id)
            & (DailyPrice.trade_date == latest_date_sq.c.max_date),
        )
        .all()
    )
    return {item.stock_id: item for item in prices}


def get_dashboard_data(db: Session, today: date) -> dict:
    provider = get_provider()

    try:
        market_a = provider.fetch_market_index("A_SHARE")
    except Exception:
        market_a = _fallback_market_indices("A_SHARE")

    try:
        market_hk = provider.fetch_market_index("HK")
    except Exception:
        market_hk = _fallback_market_indices("HK")

    signals = db.query(TradeSignal).filter(TradeSignal.signal_date == today).all()
    dist = {"BUY": 0, "ADD": 0, "WATCH": 0, "REDUCE": 0, "SELL": 0}
    for signal in signals:
        if signal.signal_type in dist:
            dist[signal.signal_type] += 1

    strategy_summary = _strategy_summary(dist)

    top_signals = (
        db.query(TradeSignal, Stock)
        .join(Stock, TradeSignal.stock_id == Stock.id)
        .filter(TradeSignal.signal_date == today, TradeSignal.signal_type.in_(["BUY", "ADD"]))
        .order_by(TradeSignal.signal_strength.desc(), TradeSignal.id.desc())
        .limit(10)
        .all()
    )
    top_stock_ids = [stock.id for _, stock in top_signals]
    top_price_map = _latest_price_map(db, top_stock_ids)

    top_signal_list = []
    for sig, stock in top_signals:
        latest_price = top_price_map.get(stock.id)
        top_signal_list.append(
            {
                "symbol": stock.symbol,
                "name": stock.name,
                "market": stock.market,
                "signal_type": sig.signal_type,
                "signal_strength": sig.signal_strength,
                "suggested_position": sig.suggested_position,
                "logic": (
                    sanitize_research_text(sig.logic_json.get("reason", ""))
                    .replace("建议研究关注", "研究关注")
                    .replace("可适当增强关注", "增强关注")
                    if sig.logic_json
                    else ""
                ),
                "risk": [sanitize_research_text(item) for item in (sig.risk_json.get("items", []) if sig.risk_json else [])],
                "latest_close": latest_price.close if latest_price else None,
                "change_pct": (
                    round((latest_price.close - latest_price.pre_close) / latest_price.pre_close * 100, 2)
                    if latest_price and latest_price.pre_close and latest_price.pre_close != 0
                    else None
                ),
            }
        )

    portfolio = db.query(Portfolio).first()
    if portfolio:
        positions = db.query(PortfolioPosition).filter(PortfolioPosition.portfolio_id == portfolio.id).all()
        returns = []
        for position in positions:
            if position.cost_price and position.current_price and position.cost_price > 0:
                returns.append(round((position.current_price - position.cost_price) / position.cost_price * 100, 2))
        avg_return = round(sum(returns) / len(returns), 2) if returns else 0
        portfolio_summary = {
            "monthly_return": avg_return,
            "benchmark_return": 0,
            "excess_return": avg_return,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
            "total_assets": 1000000,
            "cash_ratio": portfolio.cash_ratio or 35.0,
            "position_count": len(returns),
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
            "name": "暂无研究组合",
        }

    scores = (
        db.query(StockScore, Stock)
        .join(Stock, StockScore.stock_id == Stock.id)
        .filter(StockScore.score_date == today)
        .all()
    )
    pools = {"quality": [], "undervalued": [], "trend": [], "risk": []}
    for score, stock in scores:
        item = {
            "symbol": stock.symbol,
            "name": stock.name,
            "market": stock.market,
            "score": score.total_score,
            "rating": score.rating,
            "latest_close": None,
            "change_pct": None,
        }
        if score.quality_score and score.quality_score >= 22:
            pools["quality"].append(item)
        if score.valuation_score and score.valuation_score >= 15:
            pools["undervalued"].append(item)
        if score.trend_score and score.trend_score >= 15:
            pools["trend"].append(item)
        if score.risk_score and score.risk_score < 5:
            pools["risk"].append(item)

    risk_alerts = []
    risk_signals = (
        db.query(TradeSignal, Stock)
        .join(Stock, TradeSignal.stock_id == Stock.id)
        .filter(TradeSignal.signal_date == today, TradeSignal.signal_type.in_(["REDUCE", "SELL"]))
        .order_by(TradeSignal.signal_strength.desc(), TradeSignal.id.desc())
        .limit(10)
        .all()
    )
    for sig, stock in risk_signals:
        if sig.risk_json and sig.risk_json.get("items"):
            risk_alerts.append(
                {
                    "symbol": stock.symbol,
                    "name": stock.name,
                    "market": stock.market,
                    "level": "high" if sig.signal_type == "SELL" else "medium",
                    "message": sanitize_research_text("；".join(sig.risk_json["items"])),
                }
            )

    return {
        "market_summary": market_a + market_hk,
        "strategy_summary": strategy_summary,
        "top_signals": top_signal_list,
        "signal_distribution": dist,
        "portfolio_summary": portfolio_summary,
        "stock_pools": pools,
        "risk_alerts": risk_alerts,
        "meta": {
            "signal_date": str(today),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
    }
