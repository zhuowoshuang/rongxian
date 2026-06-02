from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, DateTime, func, Index
from app.db.base import Base


class DailyPrice(Base):
    """日线行情数据表"""
    __tablename__ = "daily_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    open = Column(Float, comment="开盘价")
    high = Column(Float, comment="最高价")
    low = Column(Float, comment="最低价")
    close = Column(Float, comment="收盘价")
    pre_close = Column(Float, comment="昨收价")
    volume = Column(Float, comment="成交量")
    turnover = Column(Float, comment="成交额")
    turnover_rate = Column(Float, comment="换手率")
    market_cap = Column(Float, comment="总市值")
    pe = Column(Float, comment="市盈率")
    pb = Column(Float, comment="市净率")
    dividend_yield = Column(Float, comment="股息率")
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_stock_date", "stock_id", "trade_date", unique=True),
    )
