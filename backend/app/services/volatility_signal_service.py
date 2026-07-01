from datetime import datetime
from math import sqrt


def calculate_volatility_candidates(closes: list[float]) -> dict:
    if len(closes) < 6:
        return {"weekly_volatility_candidate": None, "monthly_volatility_candidate": None}
    returns = []
    for prev_close, close in zip(closes[:-1], closes[1:]):
        if prev_close and prev_close > 0:
            returns.append((close - prev_close) / prev_close)
    if len(returns) < 5:
        return {"weekly_volatility_candidate": None, "monthly_volatility_candidate": None}

    def std(values: list[float]) -> float:
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return variance ** 0.5

    weekly = std(returns[-5:]) * sqrt(5)
    monthly = std(returns[-20:]) * sqrt(20) if len(returns) >= 20 else None
    return {
        "weekly_volatility_candidate": round(weekly, 6),
        "monthly_volatility_candidate": round(monthly, 6) if monthly is not None else None,
    }


def get_volatility_signal(closes: list[float]) -> dict:
    candidates = calculate_volatility_candidates(closes)
    weekly = candidates["weekly_volatility_candidate"]
    if weekly is None:
        return {
            "status": "no_data",
            "signal": "unknown",
            "summary": "波动数据样本不足",
            "sources": [],
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            **candidates,
        }
    summary = "周波动率因子已预留，阈值 15%，具体计算方式待交易员确认。"
    return {
        "status": "connected",
        "signal": "positive" if weekly >= 0.15 else "neutral",
        "summary": summary,
        "sources": [],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        **candidates,
    }
