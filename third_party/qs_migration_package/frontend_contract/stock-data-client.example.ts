/**
 * 清数智算 — 股票数据 API 客户端（示例）
 *
 * 本文件展示前端如何调用后端 API。
 * 请求路径假设清数智算 backend 已配置如下路由：
 *   GET  /api/adata/stocks/search?keyword=
 *   GET  /api/adata/stocks/:symbol/quote
 *   GET  /api/adata/stocks/:symbol/kline?period=daily
 *   GET  /api/adata/stocks/:symbol/financials
 *   GET  /api/adata/stocks/:symbol/bundle
 *
 * 复制到清数智算前端后，只需替换 BASE_URL。
 */

import type {
  StockSearchItem,
  StockQuote,
  StockKline,
  FinancialMetric,
  StockDataBundle,
} from './stock-data-types';

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE || '/api/adata';

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    throw new Error(`API ${path} 返回 ${res.status}`);
  }
  return res.json();
}

// ==================== 核心 API ====================

/** 搜索股票（代码或名称） */
export async function searchStocks(keyword: string): Promise<StockSearchItem[]> {
  return apiGet<StockSearchItem[]>(
    `/stocks/search?keyword=${encodeURIComponent(keyword)}`
  );
}

/** 获取个股行情（含延迟 fallback） */
export async function getStockQuote(symbol: string): Promise<StockQuote> {
  return apiGet<StockQuote>(`/stocks/${symbol}/quote`);
}

/** 获取 K 线（daily / weekly / monthly） */
export async function getStockKline(
  symbol: string,
  period: string = 'daily'
): Promise<StockKline> {
  return apiGet<StockKline>(`/stocks/${symbol}/kline?period=${period}`);
}

/** 获取财务指标 */
export async function getStockFinancials(
  symbol: string
): Promise<FinancialMetric[]> {
  return apiGet<FinancialMetric[]>(`/stocks/${symbol}/financials`);
}

/** 获取综合数据包（一次请求拿到所有） */
export async function getStockDataBundle(
  symbol: string,
  period: string = 'daily'
): Promise<StockDataBundle> {
  return apiGet<StockDataBundle>(
    `/stocks/${symbol}/bundle?period=${period}`
  );
}
