from pydantic import BaseModel
from typing import Optional
from datetime import date


class StockScoreResponse(BaseModel):
    score_date: date
    total_score: Optional[float] = None
    quality_score: Optional[float] = None
    valuation_score: Optional[float] = None
    growth_score: Optional[float] = None
    trend_score: Optional[float] = None
    risk_score: Optional[float] = None
    rating: Optional[str] = None
    reason_summary: Optional[str] = None

    class Config:
        from_attributes = True


class ScoreBreakdown(BaseModel):
    category: str
    score: float
    max_score: float
    details: list[dict]
