# -*- coding: utf-8 -*-
"""
清数智算股票数据适配器

封装 AData 原生 API，输出统一 StockSearchItem / StockQuote /
StockKline / FinancialMetric / StockDataBundle 结构。

所有对外函数遵循：
  - 不抛异常，通过 dataStatus + errorMessage 报告错误
  - 缺失数据返回 EMPTY 或 PARTIAL
  - 不编造任何数值
"""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any

from qs_adapter.types import (
    DataStatus,
    StockSearchItem,
    StockQuote,
    KlineBar,
    StockKline,
    FinancialMetric,
    StockDataBundle,
)
from qs_adapter.normalize import (
    normalize_symbol,
    detect_exchange,
    detect_market,
    map_kline_row,
    map_quote_row,
    map_finance_row,
    collect_missing_fields,
    safe_float,
    safe_int,
    normalize_date,
)
from qs_adapter.errors import QSAdapterError


# ==================== 内部：调用 AData 原生 API ====================

def _now_iso() -> str:
    return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')


def _safe_call_adata(fn, *args, **kwargs) -> Dict[str, Any]:
    """
    安全调用 AData 函数，统一异常捕获。
    返回 {"ok": True, "data": ...} 或 {"ok": False, "error": str}
    """
    try:
        result = fn(*args, **kwargs)
        return {"ok": True, "data": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ==================== 1. search_stocks ====================

def search_stocks(keyword: str) -> List[StockSearchItem]:
    """
    根据关键词搜索股票（代码或名称）。
    底层调用 adata.stock.info.all_code() 获取全量列表后本地过滤。
    """
    result: List[StockSearchItem] = []
    try:
        import adata  # noqa: F401
    except Exception as e:
        return [StockSearchItem(
            symbol=keyword, name="", market="A", exchange="UNKNOWN",
            data_status=DataStatus.ERROR, error_message=f"导入 adata 失败: {e}"
        )]

    r = _safe_call_adata(adata.stock.info.all_code)
    if not r["ok"]:
        # all_code() 失败 → 用代码直接构造搜索项作为 fallback
        try:
            sym = normalize_symbol(keyword)
        except Exception:
            sym = keyword
        return [StockSearchItem(
            symbol=sym,
            name=keyword if not keyword.isdigit() else "",
            market="A",
            exchange=detect_exchange(sym),
            data_status=DataStatus.PARTIAL,
            missing_fields=["name", "industry"],
            error_message=f"all_code() 失败: {r['error']}；使用代码直接构造",
        )]

    df = r["data"]
    if df is None or df.empty:
        # 空 DataFrame → 用代码构造
        try:
            sym = normalize_symbol(keyword)
        except Exception:
            sym = keyword
        return [StockSearchItem(
            symbol=sym,
            name=keyword if not keyword.isdigit() else "",
            market="A",
            exchange=detect_exchange(sym),
            data_status=DataStatus.PARTIAL,
            missing_fields=["name", "industry"],
            error_message="all_code() 返回空 DataFrame",
        )]

    # 过滤匹配项
    kw = str(keyword).strip().lower()
    for _, row in df.iterrows():
        code = str(row['stock_code']).zfill(6)
        name = str(row.get('short_name', ''))
        if kw in code or kw in name.lower() or kw in name:
            try:
                sym = normalize_symbol(code)
            except Exception:
                sym = code
            result.append(StockSearchItem(
                symbol=sym,
                name=name,
                market=detect_market(sym),
                exchange=detect_exchange(sym),
                update_time=_now_iso(),
            ))

    if not result:
        # 如果本地列表没找到，直接用代码尝试
        return [StockSearchItem(
            symbol=normalize_symbol(keyword),
            name=keyword if not keyword.isdigit() else "",
            market="A",
            exchange=detect_exchange(keyword),
            data_status=DataStatus.PARTIAL,
            missing_fields=["name", "industry"],
            error_message="全量代码列表中未匹配，使用输入作为 symbol",
        )]

    return result


# ==================== 2. get_stock_quote ====================

def get_stock_quote(symbol: str) -> StockQuote:
    """
    获取个股最新行情。
    底层调用 adata.stock.market.list_market_current([symbol])。
    """
    sym = normalize_symbol(symbol)
    exchange = detect_exchange(sym)
    market = detect_market(sym)

    try:
        import adata
    except Exception as e:
        return StockQuote(
            symbol=sym, market=market, exchange=exchange,
            data_status=DataStatus.ERROR, error_message=f"导入 adata 失败: {e}"
        )

    r = _safe_call_adata(adata.stock.market.list_market_current, code_list=[sym])
    if not r["ok"]:
        return StockQuote(
            symbol=sym, market=market, exchange=exchange,
            data_status=DataStatus.ERROR,
            error_message=f"list_market_current 失败: {r['error']}"
        )

    df = r["data"]
    if df is None or df.empty:
        return StockQuote(
            symbol=sym, market=market, exchange=exchange,
            data_status=DataStatus.EMPTY,
            missing_fields=["price", "change", "change_pct", "open", "high", "low",
                            "pre_close", "volume", "amount", "turnover_rate", "name"],
            error_message="list_market_current 返回空 DataFrame（可能非交易时段或无此代码）"
        )

    raw = df.iloc[0].to_dict()
    mapped = map_quote_row(raw)

    missing = collect_missing_fields(mapped, [
        'price', 'change', 'change_pct', 'open', 'high', 'low',
        'pre_close', 'volume', 'amount', 'name'
    ])
    status = DataStatus.PARTIAL if missing else DataStatus.OK

    return StockQuote(
        symbol=sym,
        name=mapped.get('name'),
        market=market,
        exchange=exchange,
        trade_date=mapped.get('trade_date'),
        price=mapped.get('price'),
        change=mapped.get('change'),
        change_pct=mapped.get('change_pct'),
        open=mapped.get('open'),
        high=mapped.get('high'),
        low=mapped.get('low'),
        pre_close=mapped.get('pre_close'),
        volume=mapped.get('volume'),
        amount=mapped.get('amount'),
        turnover_rate=mapped.get('turnover_rate'),
        source='adata',
        is_realtime=True,
        update_time=_now_iso(),
        data_status=status,
        missing_fields=missing,
        error_message=None if status == DataStatus.OK else f"缺失字段: {missing}",
    )


# ==================== 3. get_stock_kline ====================

# period 映射
PERIOD_MAP = {
    'daily': 1,
    'weekly': 2,
    'monthly': 3,
    '1': 1, '2': 2, '3': 3,
}


def get_stock_kline(symbol: str, period: str = "daily") -> StockKline:
    """
    获取个股 K 线数据。
    底层调用 adata.stock.market.get_market(symbol, k_type=..., start_date='2000-01-01')。
    """
    sym = normalize_symbol(symbol)
    k_type = PERIOD_MAP.get(period, 1)

    try:
        import adata
    except Exception as e:
        return StockKline(
            symbol=sym, period=period,
            data_status=DataStatus.ERROR, error_message=f"导入 adata 失败: {e}"
        )

    r = _safe_call_adata(
        adata.stock.market.get_market,
        stock_code=sym, k_type=k_type, start_date='2000-01-01'
    )
    if not r["ok"]:
        return StockKline(
            symbol=sym, period=period,
            data_status=DataStatus.ERROR,
            error_message=f"get_market 失败: {r['error']}"
        )

    df = r["data"]
    if df is None or df.empty:
        return StockKline(
            symbol=sym, period=period,
            data_status=DataStatus.EMPTY,
            error_message="get_market 返回空 DataFrame"
        )

    bars: List[KlineBar] = []
    missing_fields = set()
    for _, row in df.iterrows():
        m = map_kline_row(row.to_dict())
        missing_fields.update(collect_missing_fields(m, [
            'date', 'open', 'high', 'low', 'close', 'volume', 'amount'
        ]))
        bars.append(KlineBar(
            date=m['date'],
            open=m['open'],
            high=m['high'],
            low=m['low'],
            close=m['close'],
            volume=m['volume'],
            amount=m['amount'],
            turnover_rate=m.get('turnover_rate'),
        ))

    missing = sorted(list(missing_fields))
    status = DataStatus.PARTIAL if missing else DataStatus.OK

    return StockKline(
        symbol=sym,
        period=period,
        items=bars,
        source='adata',
        update_time=_now_iso(),
        data_status=status,
        missing_fields=missing,
        error_message=None if status == DataStatus.OK else f"部分 K 线记录缺失字段: {missing}",
    )


# ==================== 4. get_stock_financials ====================

def get_stock_financials(symbol: str) -> List[FinancialMetric]:
    """
    获取个股财务指标。
    底层调用 adata.stock.finance.get_core_index(symbol)。

    AData 当前仅提供核心财务指标（东方财富来源），
    如原始接口返回空则整个 financials 列表为空。
    """
    sym = normalize_symbol(symbol)

    try:
        import adata
    except Exception as e:
        return [FinancialMetric(
            period="",
            data_status=DataStatus.ERROR,
            error_message=f"导入 adata 失败: {e}"
        )]

    r = _safe_call_adata(adata.stock.finance.get_core_index, stock_code=sym)
    if not r["ok"]:
        return [FinancialMetric(
            period="",
            data_status=DataStatus.ERROR,
            error_message=f"get_core_index 失败: {r['error']}"
        )]

    df = r["data"]
    if df is None or df.empty:
        return []  # 无财务数据，返回空列表（由上层标记 dataStatus）

    result: List[FinancialMetric] = []
    for _, row in df.iterrows():
        m = map_finance_row(row.to_dict())
        missing = collect_missing_fields(m, [
            'period', 'revenue', 'net_profit', 'eps'
        ])
        status = DataStatus.PARTIAL if missing else DataStatus.OK
        result.append(FinancialMetric(
            period=m['period'] or '',
            revenue=m['revenue'],
            revenue_yoy=m['revenue_yoy'],
            net_profit=m['net_profit'],
            profit_yoy=m['profit_yoy'],
            gross_margin=m['gross_margin'],
            net_margin=m['net_margin'],
            roe=m['roe'],
            debt_ratio=m['debt_ratio'],
            eps=m['eps'],
            source='adata',
            update_time=_now_iso(),
            data_status=status,
            missing_fields=missing,
            error_message=None if status == DataStatus.OK else f"缺失: {missing}",
        ))

    return result


# ==================== 5. get_stock_data_bundle ====================

def get_stock_data_bundle(symbol: str, period: str = "daily") -> StockDataBundle:
    """
    获取个股综合数据包，包含搜索项、行情、K 线、财务指标。
    此函数一次性返回清数智算前端所需的所有数据。
    """
    sym = normalize_symbol(symbol)
    missing: List[str] = []
    error_msgs: List[str] = []
    sources: List[str] = []

    # --- 搜索项 ---
    search_items = search_stocks(sym)
    search_item = None
    if search_items:
        search_item = search_items[0]
        if search_item.data_status != DataStatus.OK:
            missing.append('searchItem')
            if search_item.error_message:
                error_msgs.append(search_item.error_message)
        sources.append(search_item.source)
    else:
        search_item = StockSearchItem(
            symbol=sym, name=sym, market='A', exchange=detect_exchange(sym),
            data_status=DataStatus.EMPTY,
            error_message=f"未找到 {sym} 的搜索结果"
        )
        missing.append('searchItem')

    # --- 行情 ---
    quote = get_stock_quote(sym)
    if quote.data_status != DataStatus.OK:
        missing.append('quote')
        if quote.error_message:
            error_msgs.append(quote.error_message)
    if quote.source not in sources:
        sources.append(quote.source)

    # --- K线 ---
    kline = get_stock_kline(sym, period)
    if kline.data_status != DataStatus.OK:
        missing.append('kline')
        if kline.error_message:
            error_msgs.append(kline.error_message)
    if kline.source not in sources:
        sources.append(kline.source)

    # --- 财务 ---
    financials = get_stock_financials(sym)
    if len(financials) == 0:
        missing.append('financials')
        error_msgs.append("AData 当前未找到该股票财务指标接口或返回为空")
    elif any(f.data_status != DataStatus.OK for f in financials):
        missing.append('financials')
        error_msgs.append("部分财务指标缺失")

    # --- 汇总状态 ---
    if not missing:
        status = DataStatus.OK
    elif len(missing) == 4:
        status = DataStatus.ERROR
    else:
        status = DataStatus.PARTIAL

    return StockDataBundle(
        symbol=sym,
        search_item=search_item,
        quote=quote,
        kline=kline,
        financials=financials,
        source_summary=' + '.join(sources),
        update_time=_now_iso(),
        data_status=status,
        missing_fields=missing,
        error_message='; '.join(error_msgs) if error_msgs else None,
    )
