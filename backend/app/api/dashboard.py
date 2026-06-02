"""仪表盘 API"""
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.dashboard import get_dashboard_data

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


@router.get("")
def dashboard(db: Session = Depends(get_db)):
    """
    获取仪表盘数据
    返回：市场概览、策略总结、Top信号、信号分布、组合表现、股票池、风险预警
    """
    today = date.today()
    # 如果今天没有数据，取最近有数据的日期
    from app.models.trade_signal import TradeSignal
    latest = db.query(TradeSignal.signal_date).order_by(TradeSignal.signal_date.desc()).first()
    if latest:
        today = latest[0]
    data = get_dashboard_data(db, today)
    return data
