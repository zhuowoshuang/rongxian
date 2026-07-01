import type { ADataFinancialMetric, ADataHealth, ADataStockBundle, ADataStockSearchItem } from "@/types/stockData";

const API_BASE = "/api/adata";

async function adataGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`AData API ${path} failed with ${response.status}`);
  }
  return response.json();
}

export function searchADataStocks(keyword: string) {
  return adataGet<ADataStockSearchItem[]>(`/stocks/search?keyword=${encodeURIComponent(keyword)}`);
}

export function getADataHealth() {
  return adataGet<ADataHealth>("/health");
}

export function getADataStockFinancials(symbol: string) {
  return adataGet<ADataFinancialMetric[]>(`/stocks/${symbol}/financials`);
}

export function getADataStockBundle(symbol: string, period: string = "daily") {
  return adataGet<ADataStockBundle>(`/stocks/${symbol}/bundle?period=${encodeURIComponent(period)}`);
}
