from sqlalchemy import Column, Integer, Date, Float, ForeignKey, DateTime, func, Index
from app.db.base import Base


class TechnicalIndicator(Base):
    """技术指标表"""
    __tablename__ = "technical_indicators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    ma20 = Column(Float, comment="20日均线")
    ma60 = Column(Float, comment="60日均线")
    ma120 = Column(Float, comment="120日均线")
    macd = Column(Float, comment="MACD")
    macd_signal = Column(Float, comment="MACD信号线")
    macd_hist = Column(Float, comment="MACD柱状图")
    rsi14 = Column(Float, comment="14日RSI")
    boll_upper = Column(Float, comment="布林上轨")
    boll_middle = Column(Float, comment="布林中轨")
    boll_lower = Column(Float, comment="布林下轨")
    volume_ma5 = Column(Float, comment="5日成交量均线")
    volume_ma20 = Column(Float, comment="20日成交量均线")
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_tech_stock_date", "stock_id", "trade_date", unique=True),
    )
