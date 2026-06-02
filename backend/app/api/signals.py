"""信号中心 API"""
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.trade_signal import TradeSignal
from app.models.stock import Stock
from app.models.daily_price import DailyPrice

router = APIRouter(prefix="/api/signals", tags=["信号"])


@router.get("")
def list_signals(
    market: str = Query(None, description="市场: A_SHARE / HK"),
    signal_type: str = Query(None, description="信号类型: BUY/ADD/WATCH/REDUCE/SELL"),
    min_score: float = Query(None, description="最低评分"),
    signal_date: str = Query(None, description="信号日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """获取信号列表"""
    query = db.query(TradeSignal, Stock).join(Stock, TradeSignal.stock_id == Stock.id)

    if signal_date:
        query = query.filter(TradeSignal.signal_date == signal_date)
    else:
        # 默认取最新日期
        from sqlalchemy import func
        latest = db.query(func.max(TradeSignal.signal_date)).scalar()
        if latest:
            query = query.filter(TradeSignal.signal_date == latest)

    if market:
        query = query.filter(Stock.market == market)
    if signal_type:
        query = query.filter(TradeSignal.signal_type == signal_type)

    total = query.count()
    results = query.order_by(TradeSignal.signal_strength.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for sig, stock in results:
        price = (
            db.query(DailyPrice)
            .filter(DailyPrice.stock_id == stock.id)
            .order_by(DailyPrice.trade_date.desc())
            .first()
        )
        items.append({
            "id": sig.id,
            "stock_id": stock.id,
            "symbol": stock.symbol,
            "name": stock.name,
            "market": stock.market,
            "signal_type": sig.signal_type,
            "signal_strength": sig.signal_strength,
            "suggested_position": sig.suggested_position,
            "entry_price": sig.entry_price,
            "target_price": sig.target_price,
            "stop_loss_price": sig.stop_loss_price,
            "holding_period": sig.holding_period,
            "logic": sig.logic_json,
            "risk": sig.risk_json,
            "status": sig.status,
            "signal_date": str(sig.signal_date),
            "latest_close": price.close if price else None,
            "change_pct": round((price.close - price.pre_close) / price.pre_close * 100, 2) if price and price.pre_close and price.pre_close != 0 else None,
        })

    return {"total": total, "page": page, "page_size": page_size, "items": items}
