from sqlalchemy import Column, Integer, String, DateTime, func
from app.db.base import Base


class Stock(Base):
    """股票基础信息表"""
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), unique=True, nullable=False, index=True, comment="股票代码")
    name = Column(String(100), nullable=False, comment="股票名称")
    market = Column(String(20), nullable=False, index=True, comment="市场: A_SHARE / HK")
    exchange = Column(String(10), nullable=False, comment="交易所: SH / SZ / HK")
    industry = Column(String(100), comment="行业")
    sector = Column(String(100), comment="板块")
    currency = Column(String(10), default="CNY", comment="币种")
    status = Column(String(20), default="ACTIVE", comment="状态: ACTIVE / DELISTED / SUSPENDED")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
