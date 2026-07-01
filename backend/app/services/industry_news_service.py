from datetime import datetime


def get_industry_support(stock_code: str, industry: str | None) -> dict:
    return {
        "status": "not_connected",
        "signal": "unknown",
        "summary": "行业消息源暂未接入",
        "sources": [],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "industry": industry,
        "stock_code": stock_code,
    }
