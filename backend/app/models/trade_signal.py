from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, DateTime, func, JSON
from app.db.base import Base


class TradeSignal(Base):
    """交易信号表"""
    __tablename__ = "trade_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    signal_date = Column(Date, nullable=False, index=True)
    signal_type = Column(String(20), nullable=False, comment="信号类型: BUY/ADD/WATCH/REDUCE/SELL")
    signal_strength = Column(Integer, comment="信号强度 1-5")
    suggested_position = Column(Float, comment="建议仓位百分比")
    entry_price = Column(Float, comment="建议入场价")
    target_price = Column(Float, comment="目标价")
    stop_loss_price = Column(Float, comment="止损价")
    holding_period = Column(String(50), comment="建议持有期")
    logic_json = Column(JSON, comment="信号逻辑 JSON")
    risk_json = Column(JSON, comment="风险提示 JSON")
    status = Column(String(20), default="ACTIVE", comment="状态: ACTIVE/EXPIRED/EXECUTED")
    created_at = Column(DateTime, server_default=func.now())
