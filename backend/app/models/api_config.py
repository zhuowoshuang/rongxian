"""API配置与调用管理模型"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, ForeignKey
from app.db.base import Base


class ApiConfig(Base):
    """API供应商配置表"""
    __tablename__ = "api_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(50), nullable=False, unique=True, comment="供应商: eastmoney/yahoo/akshare/llm")
    display_name = Column(String(100), comment="显示名称")
    api_key = Column(String(500), comment="API密钥（加密存储）")
    api_secret = Column(String(500), comment="API密钥")
    base_url = Column(String(500), comment="基础URL")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    daily_limit = Column(Integer, default=1000, comment="每日总调用上限")
    rate_limit = Column(Integer, default=10, comment="每分钟频率限制")
    config_json = Column(String(2000), comment="额外配置JSON")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class UserApiQuota(Base):
    """用户API配额表"""
    __tablename__ = "user_api_quotas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    daily_report_limit = Column(Integer, default=5, comment="每日报告生成上限")
    daily_backtest_limit = Column(Integer, default=3, comment="每日回测上限")
    daily_search_limit = Column(Integer, default=100, comment="每日搜索上限")
    daily_pdf_limit = Column(Integer, default=10, comment="每日PDF下载上限")
    can_download_pdf = Column(Boolean, default=True, comment="是否允许下载PDF")
    can_use_style_report = Column(Boolean, default=True, comment="是否允许风格报告")
    can_use_simulation = Column(Boolean, default=True, comment="是否允许模拟买入")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ApiCallLog(Base):
    """API调用日志表"""
    __tablename__ = "api_call_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, comment="用户ID")
    username = Column(String(50), comment="用户名")
    provider = Column(String(50), comment="API供应商")
    endpoint = Column(String(200), comment="调用接口")
    method = Column(String(10), comment="请求方法")
    status_code = Column(Integer, comment="响应状态码")
    response_time = Column(Integer, comment="响应时间(ms)")
    error_msg = Column(String(500), comment="错误信息")
    called_at = Column(DateTime, server_default=func.now(), index=True)
