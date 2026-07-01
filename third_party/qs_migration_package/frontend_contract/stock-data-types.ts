/**
 * 清数智算 — 股票数据类型契约
 *
 * 本文件定义前端 TypeScript 类型，与 qs_backend_bridge/api_models.py 完全一致。
 * 复制到清数智算前端项目即可直接使用，不依赖具体框架。
 */

// ==================== 状态枚举 ====================

export type DataStatus = 'OK' | 'PARTIAL' | 'EMPTY' | 'ERROR';

// ==================== 个股搜索 ====================

export interface StockSearchItem {
  symbol: string;
  name: string | null;
  market: string;
  exchange: string;
  industry?: string | null;
  status?: string;
  source: string;
  updateTime: string | null;
  dataStatus: DataStatus;
  missingFields: string[];
  errorMessage?: string | null;
}

// ==================== 实时行情 ====================

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

// ==================== K 线 ====================

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

// ==================== 财务指标 ====================

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

// ==================== 综合数据包 ====================

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
