from datetime import datetime


def get_earnings_signal(financial) -> dict:
    if not financial:
        return {
            "status": "no_data",
            "signal": "unknown",
            "summary": "最新财报数据暂缺",
            "sources": [],
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

    revenue_yoy = financial.revenue_yoy or 0
    profit_yoy = financial.net_profit_yoy or 0
    if revenue_yoy > 0 and profit_yoy > 0:
        signal = "positive"
        summary = "营收与净利润同比均为正增长，需继续结合现金流与负债情况观察。"
    elif revenue_yoy < 0 or profit_yoy < 0:
        signal = "negative"
        summary = "营收或净利润同比转弱，需关注经营质量是否持续承压。"
    else:
        signal = "neutral"
        summary = "财报增速暂未形成明确方向。"
    return {
        "status": "connected",
        "signal": signal,
        "summary": summary,
        "sources": [],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
