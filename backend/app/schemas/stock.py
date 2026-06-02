from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class StockBase(BaseModel):
    symbol: str
    name: str
    market: str
    exchange: str
    industry: Optional[str] = None
    sector: Optional[str] = None
    currency: str = "CNY"
    status: str = "ACTIVE"


class StockResponse(StockBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StockSearchResult(BaseModel):
    id: int
    symbol: str
    name: str
    market: str
    exchange: str
    industry: Optional[str] = None
