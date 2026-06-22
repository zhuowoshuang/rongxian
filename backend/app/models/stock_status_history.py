"""股票状态历史模型 — 记录股票的上市/退市/ST等状态变更"""
from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Index
from app.db.base import Base


class StockStatusHistory(Base):
    """
    股票状态变更历史
    用于回测时正确处理退市股票，消除生存偏差
    """
    __tablename__ = "stock_status_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False)  # ACTIVE, DELISTED, SUSPENDED, ST, *ST
    effective_date = Column(Date, nullable=False)  # 状态生效日期
    reason = Column(String(200), nullable=True)  # 变更原因
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_stock_status_stock_date", "stock_id", "effective_date"),
    )
