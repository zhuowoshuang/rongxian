from sqlalchemy import Column, Integer, String, Date, DateTime, func, JSON, Text, ForeignKey
from app.db.base import Base


class Report(Base):
    """分析报告表"""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    stock_code = Column(String(20), nullable=True, index=True)
    stock_name = Column(String(100), nullable=True)
    market = Column(String(30), nullable=True)
    report_date = Column(Date, nullable=False, index=True)
    report_type = Column(String(20), nullable=False, comment="报告类型: DAILY/WEEKLY/STOCK/STYLE")
    style = Column(String(20), nullable=True, comment="投资风格: steady/aggressive/conservative")
    title = Column(String(200), nullable=False)
    summary = Column(Text, comment="报告摘要")
    content_markdown = Column(Text, comment="报告内容 Markdown")
    content_json = Column(JSON, comment="报告结构化内容 JSON")
    created_at = Column(DateTime, server_default=func.now())


class ReportEvent(Base):
    """报告生成、查看、下载事件。"""
    __tablename__ = "report_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=True, index=True)
    stock_code = Column(String(20), nullable=True, index=True)
    report_type = Column(String(30), nullable=True)
    format = Column(String(20), nullable=False)
    action = Column(String(20), nullable=False)
    ip = Column(String(64), nullable=True)
    user_agent = Column(String(300), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)


class BacktestTask(Base):
    """用户回测历史。"""
    __tablename__ = "backtest_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stock_code = Column(String(20), nullable=True, index=True)
    stock_name = Column(String(100), nullable=True)
    market = Column(String(30), nullable=True)
    strategy = Column(String(80), nullable=False)
    strategy_name = Column(String(120), nullable=True)
    rebalance_frequency = Column(String(30), nullable=True)
    start_date = Column(String(20), nullable=False)
    end_date = Column(String(20), nullable=False)
    status = Column(String(20), default="success")
    error_message = Column(String(500), nullable=True)
    result_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
