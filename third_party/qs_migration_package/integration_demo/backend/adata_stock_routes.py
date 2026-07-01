"""
清数智算后端 — AData 股票数据 API 路由（FastAPI）

复制到 backend/app/api/ 或 backend/app/routers/ 后在 main.py 中注册：

  from .routers.adata_stock_routes import router as adata_router
  app.include_router(adata_router, prefix="/api/adata")

依赖：
  backend/app/integrations/adata/qs_backend_bridge/

安装：
  pip install -r backend/app/integrations/adata/requirements-adata.txt
"""

import sys
import os
from typing import List
from fastapi import APIRouter, Query, HTTPException

# === 按清数智算实际路径调整 import ===
# 方案A: vendored 路径（推荐）
_HERE = os.path.dirname(os.path.abspath(__file__))
_INTEGRATIONS = os.path.join(_HERE, '..', '..', 'integrations', 'adata')
if os.path.exists(_INTEGRATIONS):
    if _INTEGRATIONS not in sys.path:
        sys.path.insert(0, _INTEGRATIONS)

from qs_backend_bridge.stock_data_service import (  # noqa: E402
    search_stocks,
    get_stock_quote,
    get_stock_kline,
    get_stock_financials,
    get_stock_data_bundle,
)

router = APIRouter(prefix="/stocks", tags=["AData 股票数据"])


# ==================== 1. 搜索 ====================
@router.get("/search")
async def api_search_stocks(keyword: str = Query(..., description="股票代码或名称")):
    """搜索股票。GET /api/adata/stocks/search?keyword=300866"""
    results = search_stocks(keyword)
    return results


# ==================== 2. 行情 ====================
@router.get("/{symbol}/quote")
async def api_stock_quote(symbol: str):
    """
    个股行情（含 K 线 fallback）。
    GET /api/adata/stocks/300866/quote

    返回 StockQuote:
      - isRealtime=true  → 实时行情
      - isRealtime=false → 延迟行情（AData-Kline-Fallback）
      - dataStatus=PARTIAL → 部分字段缺失
      - dataStatus=EMPTY  → 查无此股
      - dataStatus=ERROR  → 参数非法
    """
    result = get_stock_quote(symbol)
    if result.dataStatus == "ERROR":
        raise HTTPException(status_code=400, detail=result.errorMessage)
    return result


# ==================== 3. K线 ====================
@router.get("/{symbol}/kline")
async def api_stock_kline(
    symbol: str,
    period: str = Query("daily", description="K线周期: daily/weekly/monthly"),
):
    """个股K线。GET /api/adata/stocks/300866/kline?period=daily"""
    result = get_stock_kline(symbol, period)
    return result


# ==================== 4. 财务 ====================
@router.get("/{symbol}/financials")
async def api_stock_financials(symbol: str):
    """个股财务指标。GET /api/adata/stocks/300866/financials"""
    result = get_stock_financials(symbol)
    return result


# ==================== 5. 综合数据包 ====================
@router.get("/{symbol}/bundle")
async def api_stock_bundle(
    symbol: str,
    period: str = Query("daily"),
):
    """
    个股综合数据包（search + quote + kline + financials）。
    GET /api/adata/stocks/300866/bundle?period=daily

    返回 StockDataBundle:
      - dataStatus=OK → 所有模块正常
      - dataStatus=PARTIAL → 部分字段缺失
      - dataStatus=EMPTY → 查无此股（quote+kline均不可用）
      - dataStatus=ERROR → 参数非法
    """
    result = get_stock_data_bundle(symbol, period)
    if result.dataStatus == "ERROR":
        raise HTTPException(status_code=400, detail=result.errorMessage)
    return result
