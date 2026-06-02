from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class ReportResponse(BaseModel):
    id: int
    report_date: date
    report_type: str
    title: str
    summary: Optional[str] = None
    content_markdown: Optional[str] = None
    content_json: Optional[dict] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReportGenerateRequest(BaseModel):
    type: str  # DAILY / WEEKLY / STOCK
    market: list[str] = ["A_SHARE", "HK"]
    strategy: str = "fundamental_medium_long"
