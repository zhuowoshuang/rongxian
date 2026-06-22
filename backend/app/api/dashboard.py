"""仪表盘 API"""
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.dashboard import get_dashboard_data
from app.core.redis import cache_get, cache_set

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


@router.get("")
def dashboard(db: Session = Depends(get_db)):
    """
    获取仪表盘数据
    返回：市场概览、策略总结、Top信号、信号分布、组合表现、股票池、风险预警
    带 5 分钟缓存（Redis 或内存）
    """
    today = date.today()
    # 如果今天没有数据，取最近有数据的日期
    from app.models.trade_signal import TradeSignal
    latest = db.query(TradeSignal.signal_date).order_by(TradeSignal.signal_date.desc()).first()
    if latest:
        today = latest[0]

    # 尝试从缓存读取
    cache_key = f"dashboard:{today}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    data = get_dashboard_data(db, today)

    # 写入缓存（5 分钟）
    cache_set(cache_key, data, ttl=300)
    return data
