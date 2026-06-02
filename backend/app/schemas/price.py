from pydantic import BaseModel
from typing import Optional
from datetime import date


class DailyPriceResponse(BaseModel):
    trade_date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    pre_close: Optional[float] = None
    volume: Optional[float] = None
    turnover: Optional[float] = None
    turnover_rate: Optional[float] = None
    market_cap: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    dividend_yield: Optional[float] = None

    class Config:
        from_attributes = True
