from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    strategy: str = "qingshu_1_short"
    strategy_id: str | None = None
    stock_symbol: str | None = None
    stock_code: str | None = None
    stock_name: str | None = None
    market: str = "A_SHARE"
    start_date: str = "2020-01-01"
    end_date: str = "2025-12-31"
    rebalance: str = "monthly"
    rebalance_frequency: str | None = None
    initial_capital: float = 1000000.0

    @property
    def resolved_strategy_id(self) -> str:
        return self.strategy_id or self.strategy

    @property
    def resolved_stock_code(self) -> str | None:
        return self.stock_code or self.stock_symbol

    @property
    def resolved_rebalance_frequency(self) -> str:
        return self.rebalance_frequency or self.rebalance


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
    buy_date: str
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
