from pydantic import BaseModel
from typing import Optional


class MarketIndex(BaseModel):
    name: str
    code: str
    current: float
    change: float
    change_pct: float


class StrategySummary(BaseModel):
    market_status: str  # 偏多 / 中性 / 偏空
    suggested_position: str  # 建议总仓位
    core_strategy: str
    risk_warning: str


class SignalDistribution(BaseModel):
    buy: int
    add: int
    watch: int
    reduce: int
    sell: int


class PortfolioSummary(BaseModel):
    monthly_return: float
    benchmark_return: float
    excess_return: float
    max_drawdown: float
    sharpe_ratio: float
    total_assets: float
    cash_ratio: float


class StockPoolItem(BaseModel):
    symbol: str
    name: str
    market: str
    score: Optional[float] = None
    rating: Optional[str] = None
    latest_close: Optional[float] = None
    change_pct: Optional[float] = None


class DashboardResponse(BaseModel):
    market_summary: list[MarketIndex]
    strategy_summary: StrategySummary
    top_signals: list[dict]
    signal_distribution: SignalDistribution
    portfolio_summary: PortfolioSummary
    stock_pools: dict
    risk_alerts: list[dict]
