from sqlalchemy import Column, Integer, String, Date, DateTime, func, JSON, Text
from app.db.base import Base


class Report(Base):
    """分析报告表"""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_date = Column(Date, nullable=False, index=True)
    report_type = Column(String(20), nullable=False, comment="报告类型: DAILY/WEEKLY/STOCK/STYLE")
    style = Column(String(20), nullable=True, comment="投资风格: steady/aggressive/conservative")
    title = Column(String(200), nullable=False)
    summary = Column(Text, comment="报告摘要")
    content_markdown = Column(Text, comment="报告内容 Markdown")
    content_json = Column(JSON, comment="报告结构化内容 JSON")
    created_at = Column(DateTime, server_default=func.now())
