"""股票相关 API"""
from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.stock import Stock
from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.technical_indicator import TechnicalIndicator
from app.api.auth import get_current_admin
from app.models.stock_score import StockScore
from app.models.trade_signal import TradeSignal
from app.models.report import Report
from app.models.research_report import ResearchReport
from app.core.constants import ReportType

router = APIRouter(prefix="/api/stocks", tags=["股票"])


@router.get("/search")
def search_stocks(
    keyword: str = Query(..., description="股票代码/名称/关键词"),
    market: str = Query(None, description="市场: A_SHARE / HK"),
    db: Session = Depends(get_db),
):
    """搜索股票"""
    query = db.query(Stock).filter(Stock.status == "ACTIVE")
    if market:
        query = query.filter(Stock.market == market)
    query = query.filter(
        (Stock.symbol.like(f"%{keyword}%")) | (Stock.name.like(f"%{keyword}%"))
    )
    stocks = query.limit(20).all()
    return [
        {
            "id": s.id,
            "symbol": s.symbol,
            "name": s.name,
            "market": s.market,
            "exchange": s.exchange,
            "industry": s.industry,
        }
        for s in stocks
    ]


@router.post("/sync")
def sync_stocks(
    market: str = Query("ALL", description="同步市场: A_SHARE / HK / ALL"),
    db: Session = Depends(get_db),
    user=Depends(get_current_admin),
):
    """从东方财富同步全部股票列表到数据库"""
    from app.services.stock_sync import sync_stock_list
    result = sync_stock_list(db, market=market)
    return {
        "status": "ok",
        "message": f"同步完成: 新增 {result['added']}，更新 {result['updated']}，共 {result['total']}",
        **result,
    }


@router.get("/count")
def stock_count(db: Session = Depends(get_db)):
    """获取数据库中的股票数量"""
    total = db.query(Stock).filter(Stock.status == "ACTIVE").count()
    a_share = db.query(Stock).filter(Stock.status == "ACTIVE", Stock.market == "A_SHARE").count()
    hk = db.query(Stock).filter(Stock.status == "ACTIVE", Stock.market == "HK").count()
    return {"total": total, "a_share": a_share, "hk": hk}


@router.get("/{symbol}")
def get_stock_detail(symbol: str, db: Session = Depends(get_db)):
    """获取股票详情：基本信息、行情、财务、评分、信号、报告"""
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # 最新行情
    latest_price = (
        db.query(DailyPrice)
        .filter(DailyPrice.stock_id == stock.id)
        .order_by(DailyPrice.trade_date.desc())
        .first()
    )

    # 历史行情（近 120 日）
    prices = (
        db.query(DailyPrice)
        .filter(DailyPrice.stock_id == stock.id)
        .order_by(DailyPrice.trade_date.desc())
        .limit(120)
        .all()
    )

    # 财务指标
    financials = (
        db.query(FinancialMetric)
        .filter(FinancialMetric.stock_id == stock.id)
        .order_by(FinancialMetric.report_period.desc())
        .limit(8)
        .all()
    )

    # 技术指标
    tech = (
        db.query(TechnicalIndicator)
        .filter(TechnicalIndicator.stock_id == stock.id)
        .order_by(TechnicalIndicator.trade_date.desc())
        .first()
    )

    # 评分
    score = (
        db.query(StockScore)
        .filter(StockScore.stock_id == stock.id)
        .order_by(StockScore.score_date.desc())
        .first()
    )

    # 最新信号
    signal = (
        db.query(TradeSignal)
        .filter(TradeSignal.stock_id == stock.id)
        .order_by(TradeSignal.signal_date.desc())
        .first()
    )

    # 相关报告（从研报表查询该股票的研报）
    research_reports = (
        db.query(ResearchReport)
        .filter(ResearchReport.stock_code == symbol)
        .order_by(ResearchReport.publish_date.desc())
        .limit(10)
        .all()
    )

    return {
        "stock": {
            "id": stock.id,
            "symbol": stock.symbol,
            "name": stock.name,
            "market": stock.market,
            "exchange": stock.exchange,
            "industry": stock.industry,
            "sector": stock.sector,
        },
        "latest_price": {
            "trade_date": str(latest_price.trade_date) if latest_price else None,
            "close": latest_price.close if latest_price else None,
            "open": latest_price.open if latest_price else None,
            "high": latest_price.high if latest_price else None,
            "low": latest_price.low if latest_price else None,
            "volume": latest_price.volume if latest_price else None,
            "turnover": latest_price.turnover if latest_price else None,
            "pe": latest_price.pe if latest_price else None,
            "pb": latest_price.pb if latest_price else None,
            "market_cap": latest_price.market_cap if latest_price else None,
            "dividend_yield": latest_price.dividend_yield if latest_price else None,
        } if latest_price else None,
        "price_history": [
            {
                "date": str(p.trade_date),
                "open": p.open,
                "high": p.high,
                "low": p.low,
                "close": p.close,
                "volume": p.volume,
            }
            for p in reversed(prices)
        ],
        "financial_metrics": [
            {
                "period": f.report_period,
                "revenue": f.revenue,
                "revenue_yoy": f.revenue_yoy,
                "net_profit": f.net_profit,
                "net_profit_yoy": f.net_profit_yoy,
                "gross_margin": f.gross_margin,
                "roe": f.roe,
                "debt_ratio": f.debt_ratio,
                "eps": f.eps,
            }
            for f in financials
        ],
        "technical_indicators": {
            "ma20": tech.ma20 if tech else None,
            "ma60": tech.ma60 if tech else None,
            "ma120": tech.ma120 if tech else None,
            "macd": tech.macd if tech else None,
            "macd_signal": tech.macd_signal if tech else None,
            "rsi14": tech.rsi14 if tech else None,
        } if tech else None,
        "score": {
            "total": score.total_score,
            "quality": score.quality_score,
            "valuation": score.valuation_score,
            "growth": score.growth_score,
            "trend": score.trend_score,
            "risk": score.risk_score,
            "rating": score.rating,
            "reason": score.reason_summary,
            "date": str(score.score_date),
        } if score else None,
        "signal": {
            "type": signal.signal_type,
            "strength": signal.signal_strength,
            "position": signal.suggested_position,
            "entry_price": signal.entry_price,
            "target_price": signal.target_price,
            "stop_loss": signal.stop_loss_price,
            "holding_period": signal.holding_period,
            "logic": signal.logic_json,
            "risk": signal.risk_json,
            "date": str(signal.signal_date),
        } if signal else None,
        "reports": [
            {
                "title": r.title,
                "org_name": r.org_name,
                "publish_date": str(r.publish_date) if r.publish_date else "",
                "rating": r.rating,
                "researcher": r.researcher,
                "url": r.url,
            }
            for r in research_reports
        ],
    }
