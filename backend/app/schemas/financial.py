from pydantic import BaseModel
from typing import Optional
from datetime import date


class FinancialMetricResponse(BaseModel):
    report_period: str
    report_date: Optional[date] = None
    revenue: Optional[float] = None
    revenue_yoy: Optional[float] = None
    net_profit: Optional[float] = None
    net_profit_yoy: Optional[float] = None
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    debt_ratio: Optional[float] = None
    operating_cashflow: Optional[float] = None
    free_cashflow: Optional[float] = None
    eps: Optional[float] = None
    book_value_per_share: Optional[float] = None

    class Config:
        from_attributes = True
