from datetime import datetime


def get_company_news_summary(stock_code: str) -> dict:
    return {
        "status": "not_connected",
        "signal": "unknown",
        "summary": "公司消息源暂未接入",
        "sources": [],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "stock_code": stock_code,
    }
