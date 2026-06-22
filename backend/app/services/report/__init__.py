"""
报告生成服务 — 融衔量化分析系统
从20年华尔街投资专家视角生成专业级投资研究报告
覆盖A股+港股全市场标的，每份报告不低于8000字，图文结合

子模块：
- style_config.py: 投资风格配置
- utils.py: 工具函数（评分条、信号图标、分布图等）
- daily.py: 每日策略报告
- stock.py: 个股深度分析报告
- style.py: 风格化投资策略报告
"""
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.trade_signal import TradeSignal
from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.technical_indicator import TechnicalIndicator
from app.models.report import Report
from app.core.constants import ReportType

# 从子模块导入共享代码
from app.services.report.style_config import STYLE_CONFIG
from app.services.report.utils import (
    rating_text, signal_icon, score_bar, spark_line,
    distribution_bar, market_breadth_chart,
    quality_comment, valuation_comment, growth_comment,
    trend_comment, risk_comment, suggested_position,
    market_index_summary,
)

# 从子模块导入三个主函数
from app.services.report.daily import generate_daily_report
from app.services.report.stock import generate_stock_report
from app.services.report.style import generate_style_report

# 向后兼容：保留原模块级名称
_rating_text = rating_text
_signal_icon = signal_icon
_score_bar = score_bar
_spark_line = spark_line
_distribution_bar = distribution_bar
_market_breadth_chart = market_breadth_chart
_quality_comment = quality_comment
_valuation_comment = valuation_comment
_growth_comment = growth_comment
_trend_comment = trend_comment
_risk_comment = risk_comment
_suggested_position = suggested_position
_market_index_summary = market_index_summary

__all__ = [
    "generate_daily_report",
    "generate_stock_report",
    "generate_style_report",
    "STYLE_CONFIG",
    "rating_text", "signal_icon", "score_bar", "spark_line",
    "distribution_bar", "market_breadth_chart",
    "quality_comment", "valuation_comment", "growth_comment",
    "trend_comment", "risk_comment", "suggested_position",
    "market_index_summary",
]
