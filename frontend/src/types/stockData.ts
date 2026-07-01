export type ADataStatus = "OK" | "PARTIAL" | "EMPTY" | "ERROR";
export type ADataMode = "live" | "fixture";
export type ADataNetworkStatus = "READY" | "NETWORK_WARN" | "PROXY_CONFIGURED";

export interface ADataHealth {
  status: string;
  mode: ADataMode;
  timeoutSeconds: number;
  networkStatus: ADataNetworkStatus;
  fixturesEnabled: boolean;
  proxy: Record<string, string>;
}

export interface ADataStockSearchItem {
  symbol: string;
  name: string | null;
  market: string;
  exchange: string;
  industry?: string | null;
  source: string;
  updateTime: string | null;
  dataStatus: ADataStatus;
  missingFields: string[];
  errorMessage?: string | null;
  mode?: ADataMode;
  networkStatus?: ADataNetworkStatus;
}

export interface ADataStockQuote {
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
  dataStatus: ADataStatus;
  missingFields: string[];
  errorMessage?: string | null;
  mode?: ADataMode;
  networkStatus?: ADataNetworkStatus;
}

export interface ADataKlineBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
  turnoverRate?: number | null;
}

export interface ADataStockKline {
  symbol: string;
  period: string;
  items: ADataKlineBar[];
  source: string;
  updateTime: string | null;
  dataStatus: ADataStatus;
  missingFields: string[];
  errorMessage?: string | null;
  mode?: ADataMode;
  networkStatus?: ADataNetworkStatus;
}

export interface ADataFinancialMetric {
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
  dataStatus: ADataStatus;
  missingFields: string[];
  errorMessage?: string | null;
}

export interface ADataSourceSummary {
  quoteSource: string;
  klineSource: string;
  financialsSource: string;
  searchSource: string;
}

export interface ADataStockBundle {
  symbol: string;
  searchItem?: ADataStockSearchItem | null;
  quote?: ADataStockQuote | null;
  kline?: ADataStockKline | null;
  financials: ADataFinancialMetric[];
  sourceSummary: ADataSourceSummary;
  updateTime: string | null;
  dataStatus: ADataStatus;
  missingFields: string[];
  errorMessage?: string | null;
  mode?: ADataMode;
  networkStatus?: ADataNetworkStatus;
}
