from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, DateTime, func
from app.db.base import Base


class FinancialMetric(Base):
    """财务指标表"""
    __tablename__ = "financial_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    report_period = Column(String(10), nullable=False, comment="报告期: 2024Q4")
    report_date = Column(Date, comment="报告发布日期")
    revenue = Column(Float, comment="营业收入(亿)")
    revenue_yoy = Column(Float, comment="营收同比增长率")
    net_profit = Column(Float, comment="净利润(亿)")
    net_profit_yoy = Column(Float, comment="净利润同比增长率")
    gross_margin = Column(Float, comment="毛利率")
    net_margin = Column(Float, comment="净利率")
    roe = Column(Float, comment="净资产收益率")
    roa = Column(Float, comment="总资产收益率")
    debt_ratio = Column(Float, comment="资产负债率")
    operating_cashflow = Column(Float, comment="经营现金流(亿)")
    free_cashflow = Column(Float, comment="自由现金流(亿)")
    eps = Column(Float, comment="每股收益")
    book_value_per_share = Column(Float, comment="每股净资产")
    created_at = Column(DateTime, server_default=func.now())
