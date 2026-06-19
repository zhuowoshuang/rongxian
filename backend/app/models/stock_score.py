from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, DateTime, func, Index, CheckConstraint
from app.db.base import Base


class StockScore(Base):
    """股票评分表"""
    __tablename__ = "stock_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    score_date = Column(Date, nullable=False, index=True)
    total_score = Column(Float, comment="总分 0-100")
    quality_score = Column(Float, comment="质量分 0-30")
    valuation_score = Column(Float, comment="估值分 0-20")
    growth_score = Column(Float, comment="成长分 0-20")
    trend_score = Column(Float, comment="趋势分 0-20")
    risk_score = Column(Float, comment="风险分 0-10")
    rating = Column(String(20), comment="评级: BUY/ADD/WATCH/REDUCE/SELL")
    reason_summary = Column(String(500), comment="评分理由摘要")
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_score_stock_date", "stock_id", "score_date", unique=True),
        # M-18: 评分范围约束
        CheckConstraint("total_score >= 0 AND total_score <= 100", name="ck_total_score_range"),
        CheckConstraint("quality_score >= 0 AND quality_score <= 30", name="ck_quality_score_range"),
        CheckConstraint("valuation_score >= 0 AND valuation_score <= 20", name="ck_valuation_score_range"),
        CheckConstraint("growth_score >= 0 AND growth_score <= 20", name="ck_growth_score_range"),
        CheckConstraint("trend_score >= 0 AND trend_score <= 20", name="ck_trend_score_range"),
        CheckConstraint("risk_score >= 0 AND risk_score <= 10", name="ck_risk_score_range"),
    )
