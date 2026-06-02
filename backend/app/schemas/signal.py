from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class TradeSignalResponse(BaseModel):
    id: int
    stock_id: int
    signal_date: date
    signal_type: str
    signal_strength: Optional[int] = None
    suggested_position: Optional[float] = None
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    holding_period: Optional[str] = None
    logic_json: Optional[dict] = None
    risk_json: Optional[dict] = None
    status: str = "ACTIVE"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SignalWithStock(TradeSignalResponse):
    """信号 + 关联股票信息"""
    symbol: str
    name: str
    market: str
    latest_close: Optional[float] = None
    change_pct: Optional[float] = None


class SignalListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SignalWithStock]
