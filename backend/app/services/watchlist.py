import json
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.trade_signal import TradeSignal
from app.models.watchlist import WatchlistItem, WatchlistSnapshot
from app.services.company_news_service import get_company_news_summary
from app.services.earnings_signal_service import get_earnings_signal
from app.services.industry_news_service import get_industry_support
from app.services.shareholder_signal_service import get_shareholder_signal
from app.services.scoring import _latest_financial_for_stock
from app.services.volatility_signal_service import get_volatility_signal


def _latest_stock_context(db: Session, stock_code: str) -> dict | None:
    stock = db.query(Stock).filter(Stock.symbol == stock_code).first()
    if not stock:
        return None
    latest_price = db.query(DailyPrice).filter(DailyPrice.stock_id == stock.id).order_by(DailyPrice.trade_date.desc()).first()
    score = db.query(StockScore).filter(StockScore.stock_id == stock.id).order_by(StockScore.score_date.desc()).first()
    signal = db.query(TradeSignal).filter(TradeSignal.stock_id == stock.id).order_by(TradeSignal.signal_date.desc()).first()
    financial = _latest_financial_for_stock(db, stock.id)
    recent_prices = db.query(DailyPrice).filter(DailyPrice.stock_id == stock.id).order_by(DailyPrice.trade_date.desc()).limit(30).all()
    closes = [item.close for item in reversed(recent_prices) if item.close is not None]
    return {
        "stock": stock,
        "latest_price": latest_price,
        "score": score,
        "signal": signal,
        "financial": financial,
        "closes": closes,
    }


def build_watch_snapshot_payload(db: Session, stock_code: str) -> dict:
    context = _latest_stock_context(db, stock_code)
    if not context:
        raise ValueError("未找到该股票，无法创建关注快照")

    stock = context["stock"]
    latest_price = context["latest_price"]
    score = context["score"]
    signal = context["signal"]
    financial = context["financial"]
    closes = context["closes"]

    news = get_company_news_summary(stock.symbol)
    industry_support = get_industry_support(stock.symbol, stock.industry)
    shareholder_signal = get_shareholder_signal(db, stock.symbol)
    earnings_signal = get_earnings_signal(financial)
    volatility_signal = get_volatility_signal(closes)

    risk_flags = []
    if score and score.risk_score is not None and score.risk_score < 4:
        risk_flags.append("风险评分偏低")
    if latest_price and latest_price.pe is not None and latest_price.pe >= 60:
        risk_flags.append("估值偏高")

    return {
        "stock_code": stock.symbol,
        "stock_name": stock.name,
        "snapshot_date": date.today(),
        "price": str(latest_price.close) if latest_price and latest_price.close is not None else None,
        "change_pct": None,
        "market": stock.market,
        "industry": stock.industry,
        "sector": stock.sector,
        "total_score": str(score.total_score) if score and score.total_score is not None else None,
        "quality_score": str(score.quality_score) if score and score.quality_score is not None else None,
        "valuation_score": str(score.valuation_score) if score and score.valuation_score is not None else None,
        "growth_score": str(score.growth_score) if score and score.growth_score is not None else None,
        "trend_score": str(score.trend_score) if score and score.trend_score is not None else None,
        "risk_score": str(score.risk_score) if score and score.risk_score is not None else None,
        "rating": score.rating if score else None,
        "signal_type": signal.signal_type if signal else None,
        "risk_flags": json.dumps(risk_flags, ensure_ascii=False),
        "key_metrics_json": json.dumps(
            {
                "pe": getattr(latest_price, "pe", None),
                "pb": getattr(latest_price, "pb", None),
                "roe": getattr(financial, "roe", None),
                "revenue_yoy": getattr(financial, "revenue_yoy", None),
                "net_profit_yoy": getattr(financial, "net_profit_yoy", None),
            },
            ensure_ascii=False,
        ),
        "news_summary_json": json.dumps(news, ensure_ascii=False),
        "industry_support_json": json.dumps(industry_support, ensure_ascii=False),
        "shareholder_signal_json": json.dumps(shareholder_signal, ensure_ascii=False),
        "earnings_signal_json": json.dumps(earnings_signal, ensure_ascii=False),
        "volatility_signal_json": json.dumps(volatility_signal, ensure_ascii=False),
    }


def create_or_refresh_watch_snapshot(db: Session, watch_item: WatchlistItem) -> WatchlistSnapshot:
    payload = build_watch_snapshot_payload(db, watch_item.stock_code)
    snapshot = (
        db.query(WatchlistSnapshot)
        .filter(WatchlistSnapshot.watchlist_id == watch_item.id, WatchlistSnapshot.snapshot_date == payload["snapshot_date"])
        .order_by(WatchlistSnapshot.created_at.desc())
        .first()
    )
    if snapshot:
        for key, value in payload.items():
            setattr(snapshot, key, value)
    else:
        snapshot = WatchlistSnapshot(
            watchlist_id=watch_item.id,
            user_id=watch_item.user_id,
            **payload,
        )
        db.add(snapshot)
    watch_item.last_snapshot_at = datetime.now()
    db.commit()
    db.refresh(snapshot)
    return snapshot
