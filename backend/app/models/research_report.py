from sqlalchemy import Column, Integer, String, Float, Date, DateTime, func
from app.db.base import Base


class ResearchReport(Base):
    """券商研报表（来自东方财富）"""
    __tablename__ = "research_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    info_code = Column(String(50), unique=True, nullable=False, index=True, comment="东方财富研报编码")
    title = Column(String(500), nullable=False, comment="研报标题")
    stock_code = Column(String(20), index=True, comment="股票代码")
    stock_name = Column(String(100), comment="股票名称")
    org_name = Column(String(100), comment="发布机构")
    publish_date = Column(Date, nullable=False, index=True, comment="发布日期")
    rating = Column(String(50), comment="评级: 买入/增持/中性/减持/卖出")
    industry = Column(String(100), comment="行业")
    researcher = Column(String(200), comment="研究员")
    predict_this_year_eps = Column(Float, comment="今年预测EPS")
    predict_this_year_pe = Column(Float, comment="今年预测PE")
    predict_next_year_eps = Column(Float, comment="明年预测EPS")
    predict_next_year_pe = Column(Float, comment="明年预测PE")
    predict_next_two_year_eps = Column(Float, comment="后年预测EPS")
    predict_next_two_year_pe = Column(Float, comment="后年预测PE")
    url = Column(String(500), comment="原文链接")
    created_at = Column(DateTime, server_default=func.now())
