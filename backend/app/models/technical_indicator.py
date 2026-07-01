from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Index, Integer, func

from app.db.base import Base


class TechnicalIndicator(Base):
    __tablename__ = "technical_indicators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    ma5 = Column(Float, comment="5-day moving average")
    ma10 = Column(Float, comment="10-day moving average")
    ma20 = Column(Float, comment="20-day moving average")
    ma60 = Column(Float, comment="60-day moving average")
    ma120 = Column(Float, comment="120-day moving average")
    macd = Column(Float, comment="MACD DIF")
    macd_signal = Column(Float, comment="MACD DEA")
    macd_hist = Column(Float, comment="MACD histogram")
    rsi14 = Column(Float, comment="14-day RSI")
    boll_upper = Column(Float, comment="Bollinger upper band")
    boll_middle = Column(Float, comment="Bollinger middle band")
    boll_lower = Column(Float, comment="Bollinger lower band")
    volume_ma5 = Column(Float, comment="5-day volume MA")
    volume_ma20 = Column(Float, comment="20-day volume MA")
    volume_ratio_5_20 = Column(Float, comment="volume ma5 / ma20")
    weekly_volatility_candidate = Column(Float, comment="candidate weekly volatility")
    monthly_volatility_candidate = Column(Float, comment="candidate monthly volatility")
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_tech_stock_date", "stock_id", "trade_date", unique=True),
    )
