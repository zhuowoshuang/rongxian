/**
 * 清数智算前端 — AData 股票 API 客户端
 *
 * 复制到 frontend/src/services/adataStockApi.ts
 * 只请求清数智算后端 /api/adata/...，不直接调 AData。
 */

// ==================== 类型定义（需与 frontend/src/types/stockData.ts 一致） ====================

export type DataStatus = 'OK' | 'PARTIAL' | 'EMPTY' | 'ERROR';

export interface StockSearchItem {
  symbol: string;
  name: string | null;
  market: string;
  exchange: string;
  industry?: string | null;
  source: string;
  updateTime: string | null;
  dataStatus: DataStatus;
  missingFields: string[];
  errorMessage?: string | null;
}

export interface StockQuote {
  symbol: string;
  name: string | null;
  market: string;
  exchange: string;
  tradeDate: string | null;
  price: number | null;
  change: number | null;
  changePct: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  preClose: number | null;
  volume: number | null;
  amount: number | null;
  turnoverRate: number | null;
  source: string;
  isRealtime: boolean;
  quoteStatusReason?: string | null;
  updateTime: string | null;
  dataStatus: DataStatus;
  missingFields: string[];
  errorMessage?: string | null;
}

export interface KlineBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
  turnoverRate?: number | null;
}

export interface StockKline {
  symbol: string;
  period: string;
  items: KlineBar[];
  source: string;
  updateTime: string | null;
  dataStatus: DataStatus;
  missingFields: string[];
  errorMessage?: string | null;
}

export interface FinancialMetric {
  period: string;
  revenue?: number | null;
  revenueYoy?: number | null;
  netProfit?: number | null;
  profitYoy?: number | null;
  grossMargin?: number | null;
  netMargin?: number | null;
  roe?: number | null;
  debtRatio?: number | null;
  eps?: number | null;
  source: string;
  updateTime: string | null;
  dataStatus: DataStatus;
  missingFields: string[];
  errorMessage?: string | null;
}

export interface SourceSummary {
  quoteSource: string;
  klineSource: string;
  financialsSource: string;
  searchSource: string;
}

export interface StockDataBundle {
  symbol: string;
  searchItem?: StockSearchItem | null;
  quote?: StockQuote | null;
  kline?: StockKline | null;
  financials: FinancialMetric[];
  sourceSummary: SourceSummary;
  updateTime: string | null;
  dataStatus: DataStatus;
  missingFields: string[];
  errorMessage?: string | null;
}

// ==================== API 客户端 ====================

const BASE_URL = '/api/adata';

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`AData API ${path}: ${res.status} ${text}`);
  }
  return res.json();
}

export function searchStocks(keyword: string): Promise<StockSearchItem[]> {
  return apiGet(`/stocks/search?keyword=${encodeURIComponent(keyword)}`);
}

export function getStockQuote(symbol: string): Promise<StockQuote> {
  return apiGet(`/stocks/${symbol}/quote`);
}

export function getStockKline(
  symbol: string,
  period: string = 'daily'
): Promise<StockKline> {
  return apiGet(`/stocks/${symbol}/kline?period=${period}`);
}

export function getStockFinancials(symbol: string): Promise<FinancialMetric[]> {
  return apiGet(`/stocks/${symbol}/financials`);
}

export function getStockDataBundle(
  symbol: string,
  period: string = 'daily'
): Promise<StockDataBundle> {
  return apiGet(`/stocks/${symbol}/bundle?period=${period}`);
}
