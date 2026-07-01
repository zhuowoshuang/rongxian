# -*- coding: utf-8 -*-
"""
清数智算统一数据服务 v1.1 — 契约冻结版

在 qs_adapter 之上增加：
  - 非交易时段 quote fallback（K 线末条构造延迟行情）
  - 股票名称补齐（search → quote → code.csv）
  - 精细 missingFields（不用整个模块名，用具体字段）
  - 无效 / 不存在代码 → EMPTY 或 ERROR（不滥用 PARTIAL）

DataStatus 语义：
  OK       — 核心数据正常，无缺失
  PARTIAL  — 数据可用但部分字段缺失 / fallback / 非实时
  EMPTY    — 代码合法但查无此股 / 该模块确实无数据
  ERROR    — 参数非法 / 接口异常 / 网络异常
"""

import os
import sys
from datetime import datetime
from typing import List, Optional, Dict, Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_ADAPTER = os.path.join(_HERE, '..', 'qs_adapter')
if _ADAPTER not in sys.path:
    sys.path.insert(0, os.path.abspath(_ADAPTER))

from qs_adapter.normalize import normalize_symbol  # noqa: E402
from qs_adapter.stock_adapter import (  # noqa: E402
    search_stocks as _adapter_search,
    get_stock_quote as _adapter_quote,
    get_stock_kline as _adapter_kline,
    get_stock_financials as _adapter_financials,
)
from qs_adapter.types import DataStatus  # noqa: E402

from .data_status import DataStatus as BridgeDataStatus
from .quote_fallback import build_fallback_quote
from .stock_name_resolver import resolve_stock_name
from .api_models import (
    StockSearchItemResponse,
    StockQuoteResponse,
    KlineBarResponse,
    StockKlineResponse,
    FinancialMetricResponse,
    StockDataBundleResponse,
    SourceSummaryResponse,
)


def _now_iso() -> str:
    return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')


# ==================== 符号校验 ====================

def _validate_symbol(raw: str) -> tuple:
    """
    校验股票代码合法性。
    Returns: (normalized: str, valid: bool, error_msg: str)
    """
    if not raw or not str(raw).strip():
        return ("", False, "symbol 为空")
    s = str(raw).strip()
    # 纯字母 → 非法
    if s.isalpha():
        return (s, False, f"非法股票代码: {s}（必须为6位数字）")
    # 尝试归一化
    try:
        sym = normalize_symbol(s)
        return (sym, True, "")
    except Exception as e:
        return (s, False, f"symbol 格式非法: {e}")


# ==================== 1. search_stocks ====================

def search_stocks(keyword: str) -> List[StockSearchItemResponse]:
    sym, valid, err = _validate_symbol(keyword)
    if not valid:
        return [StockSearchItemResponse(
            symbol=keyword, name=None, market="A", exchange="UNKNOWN",
            dataStatus="ERROR", errorMessage=err,
            missingFields=["symbol"],
        )]

    items = _adapter_search(sym)
    if not items:
        return [StockSearchItemResponse(
            symbol=sym, name=None, market="A", exchange="UNKNOWN",
            dataStatus="EMPTY", errorMessage=f"未找到股票 {sym}",
            missingFields=["name", "industry"],
        )]

    return [_search_item_to_response(i) for i in items]


def _search_item_to_response(item) -> StockSearchItemResponse:
    name, name_src, name_status, name_missing, name_err = resolve_stock_name(
        symbol=item.symbol, from_search=item.name if item.name else None,
    )
    missing = []
    if not name: missing.append("name")
    if not item.industry: missing.append("industry")
    if item.data_status.value == "ERROR":
        return StockSearchItemResponse(
            symbol=item.symbol, name=name, market=item.market, exchange=item.exchange,
            source=name_src if name else item.source,
            updateTime=item.update_time or _now_iso(),
            dataStatus="ERROR", missingFields=missing,
            errorMessage=item.error_message or "搜索接口异常",
        )

    status = "OK" if not missing else "PARTIAL"
    return StockSearchItemResponse(
        symbol=item.symbol, name=name, market=item.market, exchange=item.exchange,
        industry=item.industry,
        source=name_src if name else item.source,
        updateTime=item.update_time or _now_iso(),
        dataStatus=status, missingFields=missing,
        errorMessage=name_err if name_err else item.error_message,
    )


# ==================== 2. get_stock_quote ====================

def get_stock_quote(symbol: str) -> StockQuoteResponse:
    sym, valid, err = _validate_symbol(symbol)
    if not valid:
        return StockQuoteResponse(
            symbol=symbol, name=None, market="A", exchange="UNKNOWN",
            dataStatus="ERROR", errorMessage=err,
            missingFields=["symbol"],
        )

    quote = _adapter_quote(sym)

    # EMPTY / ERROR → K 线 fallback
    if quote.data_status.value in ("EMPTY", "ERROR"):
        kline = _adapter_kline(sym, "daily")
        if kline.items:
            resolved_name, _, _, _, _ = resolve_stock_name(sym, from_quote=quote.name)
            k_dicts = [_bar_to_dict(b) for b in kline.items]
            fb = build_fallback_quote(k_dicts, symbol=sym, name=resolved_name or quote.name)
            return StockQuoteResponse(
                symbol=sym,
                name=fb.get("name") or resolved_name or quote.name,
                market="A", exchange=fb.get("exchange", ""),
                tradeDate=fb.get("trade_date"),
                price=fb.get("price"), change=fb.get("change"),
                changePct=fb.get("changePct"), open=fb.get("open"),
                high=fb.get("high"), low=fb.get("low"),
                preClose=fb.get("preClose"), volume=fb.get("volume"),
                amount=fb.get("amount"), turnoverRate=fb.get("turnoverRate"),
                source="AData-Kline-Fallback", isRealtime=False,
                updateTime=_now_iso(),
                dataStatus="PARTIAL",
                missingFields=["realtimeQuote"],
                quoteStatusReason="实时行情为空，使用最新K线构造延迟行情",
            )
        # K 线也为空 → 查无此股
        return StockQuoteResponse(
            symbol=sym, name=None, market="A", exchange="UNKNOWN",
            dataStatus="EMPTY", errorMessage=f"未找到 {sym} 行情数据（实时+K线均为空）",
            missingFields=["price", "change", "changePct", "open", "high", "low",
                          "preClose", "volume", "amount", "realtimeQuote"],
        )

    # quote 正常 → 补齐名称
    name, _, _, _, _ = resolve_stock_name(sym, from_quote=quote.name)
    missing = []
    if not name: missing.append("name")
    if quote.price is None: missing.append("price")
    if quote.change_pct is None: missing.append("changePct")

    status = "OK" if not missing else "PARTIAL"
    return StockQuoteResponse(
        symbol=sym, name=name or quote.name,
        market=quote.market, exchange=quote.exchange,
        tradeDate=quote.trade_date,
        price=quote.price, change=quote.change,
        changePct=quote.change_pct, open=quote.open,
        high=quote.high, low=quote.low, preClose=quote.pre_close,
        volume=quote.volume, amount=quote.amount,
        turnoverRate=quote.turnover_rate,
        source="adata-realtime", isRealtime=quote.is_realtime,
        updateTime=quote.update_time or _now_iso(),
        dataStatus=status, missingFields=missing,
        errorMessage=quote.error_message,
        quoteStatusReason="实时行情" if quote.is_realtime else None,
    )


# ==================== 3. get_stock_kline ====================

def get_stock_kline(symbol: str, period: str = "daily") -> StockKlineResponse:
    sym, valid, err = _validate_symbol(symbol)
    if not valid:
        return StockKlineResponse(
            symbol=symbol, period=period,
            dataStatus="ERROR", errorMessage=err,
            missingFields=["symbol"],
        )

    kline = _adapter_kline(sym, period)
    if not kline.items:
        return StockKlineResponse(
            symbol=sym, period=period,
            dataStatus="EMPTY",
            errorMessage=kline.error_message or f"未找到 {sym} K线数据",
            missingFields=["klineData"],
        )

    return StockKlineResponse(
        symbol=sym, period=period,
        items=[_bar_to_response(b) for b in kline.items],
        source=kline.source, updateTime=kline.update_time or _now_iso(),
        dataStatus=kline.data_status.value,
        missingFields=kline.missing_fields,
        errorMessage=kline.error_message,
    )


# ==================== 4. get_stock_financials ====================

def get_stock_financials(symbol: str) -> List[FinancialMetricResponse]:
    sym, valid, err = _validate_symbol(symbol)
    if not valid:
        return [FinancialMetricResponse(
            period="", source="none",
            dataStatus="ERROR", errorMessage=err,
            missingFields=["symbol"],
        )]

    fins = _adapter_financials(sym)
    if not fins:
        return []  # 空列表，由 bundle 标记 EMPTY
    return [_fin_to_response(f) for f in fins]


# ==================== 5. get_stock_data_bundle ====================

def get_stock_data_bundle(symbol: str, period: str = "daily") -> StockDataBundleResponse:
    sym, valid, err = _validate_symbol(symbol)
    if not valid:
        return StockDataBundleResponse(
            symbol=symbol,
            dataStatus="ERROR",
            errorMessage=err,
            missingFields=["symbol"],
            sourceSummary=SourceSummaryResponse(),
            updateTime=_now_iso(),
        )

    search_items = search_stocks(sym)
    quote = get_stock_quote(sym)
    kline = get_stock_kline(sym, period)
    financials = get_stock_financials(sym)

    # 判断是否查无此股：quote 和 kline 都不可用 → EMPTY
    # （search 可能通过 fallback 构造了条目，但不能仅凭 search 判定股票存在）
    quote_ok = quote.dataStatus in ("OK", "PARTIAL")
    kline_ok = kline.dataStatus in ("OK", "PARTIAL")

    if not quote_ok and not kline_ok:
        # 核心行情数据完全不可用 → 查无此股
        return StockDataBundleResponse(
            symbol=sym,
            searchItem=search_items[0] if search_items else None,
            quote=quote, kline=kline, financials=[],
            sourceSummary=SourceSummaryResponse(),
            updateTime=_now_iso(),
            dataStatus="EMPTY",
            missingFields=_collect_all_missing(search_items, quote, kline, []),
            errorMessage=f"未找到股票 {sym} 的有效数据",
        )

    # 收集具体缺失字段（不用模块名）
    all_missing = _collect_all_missing(search_items, quote, kline, financials)

    # 判断状态
    has_fallback = quote.source == "AData-Kline-Fallback"
    has_partial = bool(all_missing)
    fins_missing = len(financials) == 0

    if fins_missing and "financials" not in all_missing:
        all_missing.append("financials")

    if not all_missing:
        status = "OK"
    else:
        status = "PARTIAL"

    return StockDataBundleResponse(
        symbol=sym,
        searchItem=search_items[0] if search_items else None,
        quote=quote, kline=kline, financials=financials,
        sourceSummary=SourceSummaryResponse(
            quoteSource=quote.source,
            klineSource=kline.source,
            financialsSource="adata-eastmoney" if financials else "none",
            searchSource=search_items[0].source if search_items else "none",
        ),
        updateTime=_now_iso(),
        dataStatus=status,
        missingFields=all_missing,
        errorMessage=None if status == "OK" else (
            f"部分数据缺失或降级: {all_missing}" + ("（已触发K线fallback）" if has_fallback else "")
        ),
    )


def _collect_all_missing(search_items, quote, kline, financials) -> List[str]:
    """收集所有具体缺失字段（不用模块名）"""
    missing = set()
    if search_items:
        missing.update(search_items[0].missingFields or [])
    if quote:
        missing.update(quote.missingFields or [])
    if kline:
        missing.update(kline.missingFields or [])
    if not financials:
        missing.add("financials")
    else:
        for f in financials:
            missing.update(f.missingFields or [])
    # 剔除模块级别的粗粒度标记
    coarse = {"searchItem", "quote", "kline"}
    missing = {m for m in missing if m not in coarse}
    return sorted(list(missing))


# ==================== 内部转换 ====================

def _bar_to_dict(b) -> Dict[str, Any]:
    return {
        'date': b.date, 'open': b.open, 'high': b.high,
        'low': b.low, 'close': b.close,
        'volume': b.volume, 'amount': b.amount,
        'turnover_rate': b.turnover_rate,
    }


def _bar_to_response(b) -> KlineBarResponse:
    return KlineBarResponse(
        date=b.date, open=b.open, high=b.high, low=b.low, close=b.close,
        volume=b.volume, amount=b.amount, turnoverRate=b.turnover_rate,
    )


def _fin_to_response(f) -> FinancialMetricResponse:
    return FinancialMetricResponse(
        period=f.period, revenue=f.revenue, revenueYoy=f.revenue_yoy,
        netProfit=f.net_profit, profitYoy=f.profit_yoy,
        grossMargin=f.gross_margin, netMargin=f.net_margin,
        roe=f.roe, debtRatio=f.debt_ratio, eps=f.eps,
        source=f.source, updateTime=f.update_time,
        dataStatus=f.data_status.value if f.data_status else "OK",
        missingFields=f.missing_fields, errorMessage=f.error_message,
    )
