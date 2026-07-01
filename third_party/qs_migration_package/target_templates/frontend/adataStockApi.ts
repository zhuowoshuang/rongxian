/**
 * 清数智算前端 — AData 股票 API 客户端
 *
 * 只调用 /api/adata/...，不直接调用 AData。
 */

import type {
  StockSearchItem,
  StockQuote,
  StockKline,
  FinancialMetric,
  StockDataBundle,
} from './stockData';

const BASE = '/api/adata';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${path}: ${res.status}`);
  return res.json();
}

export function searchStocks(keyword: string): Promise<StockSearchItem[]> {
  return get(`/stocks/search?keyword=${encodeURIComponent(keyword)}`);
}

export function getStockQuote(symbol: string): Promise<StockQuote> {
  return get(`/stocks/${symbol}/quote`);
}

export function getStockKline(
  symbol: string,
  period: string = 'daily'
): Promise<StockKline> {
  return get(`/stocks/${symbol}/kline?period=${period}`);
}

export function getStockFinancials(symbol: string): Promise<FinancialMetric[]> {
  return get(`/stocks/${symbol}/financials`);
}

export function getStockDataBundle(
  symbol: string,
  period: string = 'daily'
): Promise<StockDataBundle> {
  return get(`/stocks/${symbol}/bundle?period=${period}`);
}
