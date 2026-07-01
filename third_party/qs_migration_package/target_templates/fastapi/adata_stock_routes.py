"""
清数智算 Backend — AData 股票数据 FastAPI 路由模板

复制此文件到清数智算 backend，调整 import 路径后即可使用。
路由路径与 OpenAPI 契约完全一致。

用法：
  from fastapi import FastAPI
  from .adata_stock_routes import router as adata_router
  app = FastAPI()
  app.include_router(adata_router, prefix="/api/adata")
"""

from typing import List, Optional
from fastapi import APIRouter, Query

# 按清数智算实际路径调整
# from qs_backend_bridge.stock_data_service import (
#     search_stocks,
#     get_stock_quote,
#     get_stock_kline,
#     get_stock_financials,
#     get_stock_data_bundle,
# )

router = APIRouter(tags=["AData 股票数据"])


@router.get("/stocks/search")
async def api_search_stocks(
    keyword: str = Query(..., description="股票代码或名称"),
):
    """
    搜索股票（代码或名称）。
    返回 StockSearchItem[]。

    示例：
      GET /api/adata/stocks/search?keyword=300866
      GET /api/adata/stocks/search?keyword=安克创新
    """
    from qs_backend_bridge.stock_data_service import search_stocks
    return search_stocks(keyword)


@router.get("/stocks/{symbol}/quote")
async def api_stock_quote(symbol: str):
    """
    个股行情（可能为实时或 K线 fallback 延迟行情）。

    返回 StockQuote：
      - isRealtime=true  → 实时行情
      - isRealtime=false → 延迟行情（非交易时段 K线 fallback）
      - dataStatus=PATIAL → 部分字段缺失
      - dataStatus=EMPTY  → 查无此股
      - dataStatus=ERROR  → 参数非法

    示例：
      GET /api/adata/stocks/300866/quote
    """
    from qs_backend_bridge.stock_data_service import get_stock_quote
    return get_stock_quote(symbol)


@router.get("/stocks/{symbol}/kline")
async def api_stock_kline(
    symbol: str,
    period: str = Query("daily", description="K线周期: daily/weekly/monthly"),
):
    """
    个股K线数据。

    示例：
      GET /api/adata/stocks/300866/kline?period=daily
    """
    from qs_backend_bridge.stock_data_service import get_stock_kline
    return get_stock_kline(symbol, period)


@router.get("/stocks/{symbol}/financials")
async def api_stock_financials(symbol: str):
    """
    个股财务指标列表。

    示例：
      GET /api/adata/stocks/300866/financials
    """
    from qs_backend_bridge.stock_data_service import get_stock_financials
    return get_stock_financials(symbol)


@router.get("/stocks/{symbol}/bundle")
async def api_stock_bundle(
    symbol: str,
    period: str = Query("daily"),
):
    """
    个股综合数据包（一次返回 search + quote + kline + financials）。

    示例：
      GET /api/adata/stocks/300866/bundle
    """
    from qs_backend_bridge.stock_data_service import get_stock_data_bundle
    return get_stock_data_bundle(symbol, period)
