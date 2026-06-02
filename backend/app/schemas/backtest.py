from pydantic import BaseModel
from typing import Optional


class BacktestRequest(BaseModel):
    strategy: str = "fundamental_medium_long"
    market: str = "A_SHARE"
    start_date: str = "2020-01-01"
    end_date: str = "2025-12-31"
    rebalance: str = "monthly"  # monthly / quarterly
    initial_capital: float = 1000000.0


class BacktestResult(BaseModel):
    total_return: float
    annual_return: float
    benchmark_return: float
    excess_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    equity_curve: list[dict]
    monthly_returns: list[dict]
    trade_log: list[dict]


class HoldingItem(BaseModel):
    symbol: str
    buy_date: str  # YYYY-MM-DD
    shares: int


class SimulateRequest(BaseModel):
    holdings: list[HoldingItem]


class SimulateResult(BaseModel):
    total_invested: float
    current_value: float
    total_return: float
    total_pnl: float
    benchmark_return: float
    excess_return: float
    holdings: list[dict]
    equity_curve: list[dict]
    monthly_returns: list[dict]
