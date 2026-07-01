from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, func

from app.db.base import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stock_code = Column(String(20), nullable=False, index=True)
    stock_name = Column(String(100), nullable=False)
    market = Column(String(30), nullable=True)
    industry = Column(String(100), nullable=True)
    status = Column(String(20), default="active", nullable=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    last_snapshot_at = Column(DateTime, nullable=True)


class WatchlistSnapshot(Base):
    __tablename__ = "watchlist_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    watchlist_id = Column(Integer, ForeignKey("watchlist_items.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stock_code = Column(String(20), nullable=False, index=True)
    stock_name = Column(String(100), nullable=False)
    snapshot_date = Column(Date, nullable=False, index=True)
    price = Column(String(40), nullable=True)
    change_pct = Column(String(40), nullable=True)
    market = Column(String(30), nullable=True)
    industry = Column(String(100), nullable=True)
    sector = Column(String(100), nullable=True)
    total_score = Column(String(40), nullable=True)
    quality_score = Column(String(40), nullable=True)
    valuation_score = Column(String(40), nullable=True)
    growth_score = Column(String(40), nullable=True)
    trend_score = Column(String(40), nullable=True)
    risk_score = Column(String(40), nullable=True)
    rating = Column(String(40), nullable=True)
    signal_type = Column(String(40), nullable=True)
    risk_flags = Column(Text, nullable=True)
    key_metrics_json = Column(Text, nullable=True)
    news_summary_json = Column(Text, nullable=True)
    industry_support_json = Column(Text, nullable=True)
    shareholder_signal_json = Column(Text, nullable=True)
    earnings_signal_json = Column(Text, nullable=True)
    volatility_signal_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)


class ShareholderStructure(Base):
    __tablename__ = "shareholder_structures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True)
    shareholder_name = Column(String(200), nullable=False)
    shareholder_type = Column(String(40), nullable=False)
    holding_ratio = Column(String(40), nullable=True)
    report_period = Column(String(40), nullable=True)
    is_state_background = Column(String(10), nullable=True)
    source = Column(String(200), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
