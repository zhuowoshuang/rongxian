# -*- coding: utf-8 -*-
"""
非交易时段 Quote Fallback

当实时行情（list_market_current）返回 EMPTY 时：
  用最新一根 K 线构造"延迟行情"，并明确标注 isRealtime=false。

规则：
  - price    = latest.close
  - open     = latest.open
  - high     = latest.high
  - low      = latest.low
  - preClose = 上一根 K 线的 close（如果只有 1 根则用自身 close）
  - change   = price - preClose
  - changePct = change / preClose * 100
  - volume / amount / turnoverRate 从 K 线中取（K 线有则有，无则 None）
  - 不编造任何数值
"""

from typing import Optional, Dict, Any, List

from .data_status import DataStatus


def build_fallback_quote(
    kline_items: List[Dict[str, Any]],
    symbol: str,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    用最新 K 线构造延迟行情。

    Args:
        kline_items: K 线数据列表（至少包含 date/open/high/low/close）
        symbol: 股票代码
        name: 股票名称（可选）

    Returns:
        标准化的 quote dict，dataStatus=PARTIAL, isRealtime=false
    """
    if not kline_items:
        return {
            "symbol": symbol,
            "name": name,
            "market": "A",
            "exchange": _detect_exchange(symbol),
            "trade_date": None,
            "price": None,
            "change": None,
            "changePct": None,
            "open": None,
            "high": None,
            "low": None,
            "preClose": None,
            "volume": None,
            "amount": None,
            "turnoverRate": None,
            "source": "AData-Kline-Fallback",
            "isRealtime": False,
            "updateTime": None,
            "dataStatus": DataStatus.EMPTY.value,
            "missingFields": ["price", "change", "changePct", "open", "high", "low",
                              "preClose", "volume", "amount", "turnoverRate", "realtimeQuote"],
            "errorMessage": "K 线为空，无法构造 fallback 行情",
        }

    latest = kline_items[-1]
    prev = kline_items[-2] if len(kline_items) >= 2 else latest

    price = _safe_float(latest.get("close"))
    pre_close = _safe_float(prev.get("close"))
    open_p = _safe_float(latest.get("open"))
    high = _safe_float(latest.get("high"))
    low = _safe_float(latest.get("low"))

    change = None
    change_pct = None
    if price is not None and pre_close is not None and pre_close != 0:
        change = round(price - pre_close, 2)
        change_pct = round(change / pre_close * 100, 2)

    missing = ["realtimeQuote"]
    if price is None: missing.append("price")
    if open_p is None: missing.append("open")
    if high is None: missing.append("high")
    if low is None: missing.append("low")
    if pre_close is None: missing.append("preClose")

    return {
        "symbol": symbol,
        "name": name,
        "market": "A",
        "exchange": _detect_exchange(symbol),
        "trade_date": latest.get("date"),
        "price": price,
        "change": change,
        "changePct": change_pct,
        "open": open_p,
        "high": high,
        "low": low,
        "preClose": pre_close,
        "volume": _safe_int(latest.get("volume")),
        "amount": _safe_float(latest.get("amount")),
        "turnoverRate": _safe_float(latest.get("turnover_rate")),
        "source": "AData-Kline-Fallback",
        "isRealtime": False,
        "updateTime": None,
        "dataStatus": DataStatus.PARTIAL.value,
        "missingFields": missing,
        "errorMessage": f"非交易时段，使用最新K线({latest.get('date')})构造延迟行情",
    }


def _safe_float(v) -> Optional[float]:
    if v is None: return None
    try: return float(v)
    except (ValueError, TypeError): return None


def _safe_int(v) -> Optional[int]:
    f = _safe_float(v)
    return int(f) if f is not None else None


def _detect_exchange(symbol: str) -> str:
    s = str(symbol).zfill(6)
    if s.startswith('6'): return 'SH'
    if s.startswith(('0', '3')): return 'SZ'
    if s.startswith(('8', '4')): return 'BJ'
    return 'UNKNOWN'
