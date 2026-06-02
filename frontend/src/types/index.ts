export interface MarketIndex {
  name: string;
  code: string;
  current: number;
  change: number;
  change_pct: number;
}

export interface StrategySummary {
  market_status: string;
  suggested_position: string;
  core_strategy: string;
  risk_warning: string;
}

export interface TopSignal {
  symbol: string;
  name: string;
  market: string;
  signal_type: string;
  signal_strength: number;
  suggested_position: number;
  logic: string;
  risk: string[];
  latest_close: number | null;
  change_pct: number | null;
}

export interface SignalDistribution {
  BUY: number;
  ADD: number;
  WATCH: number;
  REDUCE: number;
  SELL: number;
}

export interface PortfolioSummary {
  monthly_return: number;
  benchmark_return: number;
  excess_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  total_assets: number;
  cash_ratio: number;
  position_count?: number;
  name?: string;
}

export interface StockPoolItem {
  symbol: string;
  name: string;
  market: string;
  score: number;
  rating: string;
  latest_close?: number;
  change_pct?: number;
}

export interface RiskAlert {
  symbol: string;
  name: string;
  market: string;
  level: string;
  message: string;
}

export interface DashboardData {
  market_summary: MarketIndex[];
  strategy_summary: StrategySummary;
  top_signals: TopSignal[];
  signal_distribution: SignalDistribution;
  portfolio_summary: PortfolioSummary;
  stock_pools: Record<string, StockPoolItem[]>;
  risk_alerts: RiskAlert[];
}

export interface StockSearchResult {
  id: number;
  symbol: string;
  name: string;
  market: string;
  exchange: string;
  industry: string;
}

export interface SignalItem {
  id: number;
  stock_id: number;
  symbol: string;
  name: string;
  market: string;
  signal_type: string;
  signal_strength: number;
  suggested_position: number;
  entry_price: number | null;
  target_price: number | null;
  stop_loss_price: number | null;
  holding_period: string;
  logic: Record<string, any> | null;
  risk: Record<string, any> | null;
  status: string;
  signal_date: string;
  latest_close: number | null;
  change_pct: number | null;
}

export interface SignalListResponse {
  total: number;
  page: number;
  page_size: number;
  items: SignalItem[];
}

export interface ReportItem {
  id: number;
  report_date: string;
  report_type: string;
  title: string;
  summary: string;
  created_at: string;
}

export interface ResearchReportItem {
  info_code: string;
  title: string;
  stock_code: string;
  stock_name: string;
  org_name: string;
  publish_date: string;
  rating: string;
  industry: string;
  researcher: string;
  predict_this_year_eps: number | null;
  predict_this_year_pe: number | null;
  predict_next_year_eps: number | null;
  predict_next_year_pe: number | null;
  predict_next_two_year_eps: number | null;
  predict_next_two_year_pe: number | null;
  url: string;
}

export interface PriceHistory {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface FinancialMetricItem {
  period: string;
  revenue: number | null;
  revenue_yoy: number | null;
  net_profit: number | null;
  net_profit_yoy: number | null;
  gross_margin: number | null;
  net_margin: number | null;
  roe: number | null;
  roa: number | null;
  debt_ratio: number | null;
  eps: number | null;
  book_value_per_share: number | null;
}

export interface ScoreDetail {
  total: number;
  quality: number;
  valuation: number;
  growth: number;
  trend: number;
  risk: number;
  rating: string;
  reason: string;
  date: string;
}

export interface StockDetail {
  stock: {
    id: number;
    symbol: string;
    name: string;
    market: string;
    exchange: string;
    industry: string;
    sector: string;
  };
  latest_price: {
    trade_date: string;
    close: number;
    open: number;
    high: number;
    low: number;
    volume: number;
    turnover: number;
    pe: number | null;
    pb: number | null;
    market_cap: number | null;
    dividend_yield: number | null;
  } | null;
  price_history: PriceHistory[];
  financial_metrics: FinancialMetricItem[];
  technical_indicators: Record<string, any> | null;
  score: ScoreDetail | null;
  signal: {
    type: string;
    strength: number;
    position: number;
    entry_price: number | null;
    target_price: number | null;
    stop_loss: number | null;
    holding_period: string;
    logic: Record<string, any> | null;
    risk: Record<string, any> | null;
    date: string;
  } | null;
  reports: ResearchReportItem[];
}

export interface BacktestResult {
  total_return: number;
  annual_return: number;
  benchmark_return: number;
  excess_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  win_rate: number;
  total_trades: number;
  equity_curve: Array<{ date: string; equity: number; benchmark: number }>;
  monthly_returns: Array<{ month: string; strategy_return: number; benchmark_return: number; excess_return: number }>;
  trade_log: Array<Record<string, any>>;
}

export interface SimulateHolding {
  symbol: string;
  buy_date: string;
  shares: number;
}

export interface SimulateResult {
  total_invested: number;
  current_value: number;
  total_return: number;
  total_pnl: number;
  benchmark_return: number;
  excess_return: number;
  holdings: Array<{
    symbol: string;
    name: string;
    buy_date: string;
    buy_price: number;
    shares: number;
    cost: number;
    current_price: number;
    current_value: number;
    pnl: number;
    pnl_pct: number;
  }>;
  equity_curve: Array<{ date: string; equity: number; benchmark: number }>;
  monthly_returns: Array<{ month: string; strategy_return: number; benchmark_return: number; excess_return: number }>;
}
