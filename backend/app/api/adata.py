from __future__ import annotations

from fastapi import APIRouter, Query

from app.integrations.adata import service as adata_service


router = APIRouter(prefix="/api/adata", tags=["AData"])


@router.get("/health")
async def adata_health():
    return adata_service.health()


@router.get("/stocks/search")
async def adata_search(keyword: str = Query(..., min_length=1)):
    return adata_service.search_stocks(keyword)


@router.get("/stocks/{symbol}/quote")
async def adata_quote(symbol: str):
    return adata_service.get_stock_quote(symbol)


@router.get("/stocks/{symbol}/kline")
async def adata_kline(symbol: str, period: str = Query("daily")):
    return adata_service.get_stock_kline(symbol, period)


@router.get("/stocks/{symbol}/financials")
async def adata_financials(symbol: str):
    return adata_service.get_stock_financials(symbol)


@router.get("/stocks/{symbol}/bundle")
async def adata_bundle(symbol: str, period: str = Query("daily")):
    return adata_service.get_stock_data_bundle(symbol, period)
