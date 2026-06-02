from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, func
from app.db.base import Base


class Portfolio(Base):
    """投资组合表"""
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="组合名称")
    strategy_type = Column(String(50), comment="策略类型")
    target_position = Column(Float, comment="目标仓位百分比")
    cash_ratio = Column(Float, comment="现金比例")
    created_at = Column(DateTime, server_default=func.now())


class PortfolioPosition(Base):
    """组合持仓表"""
    __tablename__ = "portfolio_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    position_ratio = Column(Float, comment="持仓比例")
    cost_price = Column(Float, comment="成本价")
    current_price = Column(Float, comment="现价")
    unrealized_return = Column(Float, comment="未实现收益率")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
