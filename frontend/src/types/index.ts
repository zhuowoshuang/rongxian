export interface MarketIndex {
  name: string;
  code: string;
  current: number;
  change: number;
  change_pct: number;
}

export interface StrategySummary {
  market_status: string;
  market_status_label?: string;
  suggested_position: string;
  core_strategy: string;
  judgement_basis?: string[];
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
  meta?: {
    signal_date?: string;
    generated_at?: string;
    cache_mode?: string;
    cache_ttl_seconds?: number;
    is_cached?: boolean;
    available_dates?: string[];
    view_date?: string;
  };
}

export interface DashboardAvailableDates {
  available_dates: string[];
  latest_date: string | null;
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

export interface StockLibraryItem {
  stock_id: number;
  symbol: string;
  name: string;
  market: string;
  exchange: string;
  industry?: string | null;
  rating: string | null;
  rating_label?: string | null;
  signal_type?: string | null;
  signal_label?: string | null;
  signal_strength?: number | null;
  total_score: number | null;
  quality_score: number | null;
  valuation_score: number | null;
  growth_score: number | null;
  trend_score: number | null;
  risk_score: number | null;
  latest_close: number | null;
  change_pct: number | null;
  updated_at: string | null;
  score_date?: string | null;
  signal_date?: string | null;
  reason_summary?: string | null;
  risk_flags?: string[];
}

export interface StockLibraryResponse {
  total: number;
  page: number;
  page_size: number;
  items: StockLibraryItem[];
  summary: {
    rated_stocks: number;
    a_share: number;
    hk: number;
    highest_score: number;
    risk_elevated: number;
  };
}

export interface ReportItem {
  id: number;
  report_date: string;
  report_type: string;
  style?: string | null;
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
  operating_cashflow?: number | null;
  free_cashflow?: number | null;
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
  rating_label?: string;
  reason: string;
  date: string;
  trace?: Record<string, unknown>;
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
  data_source?: Record<string, string>;
  latest_updates?: {
    price?: string | null;
    financial?: string | null;
    technical?: string | null;
    score?: string | null;
    signal?: string | null;
  };
  missing_fields?: string[];
  score: ScoreDetail | null;
  signal: {
    type: string;
    type_label?: string;
    strength: number;
    position: number;
    entry_price: number | null;
    target_price: number | null;
    stop_loss: number | null;
    holding_period: string;
    logic: Record<string, any> | null;
    risk: Record<string, any> | null;
    date: string;
    source?: string;
    market?: string;
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
  sell_date?: string;  // 可选卖出日期，不填则持有至今
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

// ==================== 股票池 ====================

export interface PoolItem {
  symbol: string;
  name: string;
  market: string;
  industry?: string;
  total_score: number;
  quality_score: number;
  valuation_score: number;
  growth_score: number;
  trend_score: number;
  risk_score: number;
  rating: string;
  reason?: string;
  latest_close?: number;
  pe?: number;
  pb?: number;
  volatility?: number;
  price_change?: number;
  risk_flags?: string[];
  explanation?: {
    entry_reason: string;
    advantages: string[];
    risks: string[];
    observation: string;
    flags: string[];
    incomplete: boolean;
  };
}

export interface PoolResponse {
  type: string;
  count: number;
  date: string;
  items: PoolItem[];
  has_more?: boolean;
  meta?: {
    name: string;
    positioning: string;
    rules: string[];
    scenario: string;
    risks: string[];
    data_updated_at: string | null;
    research_only: boolean;
  };
}

// ==================== 报告列表 ====================

export interface ReportListResponse {
  items: ReportItem[];
  total: number;
}

export interface ResearchReportListResponse {
  reports: ResearchReportItem[];
  total: number;
}

// ==================== 管理后台 ====================

export interface AdminStats {
  total_stocks: number;
  total_signals: number;
  total_users: number;
  total_reports: number;
  db_size: string;
  total_research_reports: number;
}

export interface AdminTableInfo {
  name: string;
  row_count: number;
}

export interface AdminTableData {
  columns: string[];
  rows: Array<Record<string, any>>;
  total: number;
  page: number;
  page_size: number;
}

export interface StockCount {
  total: number;
  a_share: number;
  hk: number;
}

export interface NotificationConfig {
  email_smtp_host: string;
  email_smtp_port: string;
  email_sender: string;
  email_password: string;
  email_recipient: string;
  feishu_webhook: string;
  feishu_enabled: string;
}

export interface ApiMessage {
  message: string;
  id?: number;
  title?: string;
  type?: string;
  style?: string | null;
}

export interface RuntimeInfo {
  status: string;
  database: string;
  redis: string;
  provider_mode: "live" | "mock";
  db_size: string;
  api_configured: {
    enabled: number;
    total: number;
  };
  latest_updates: {
    prices: string | null;
    scores: string | null;
    signals: string | null;
    reports: string | null;
    research_reports: string | null;
    settings: string | null;
    api_logs: string | null;
  };
  counts: {
    stocks: number;
    prices: number;
    scores: number;
    signals: number;
    reports: number;
    research_reports: number;
  };
  notes: string[];
  data_mode?: string;
  provider?: string;
  cache_mode?: string;
  app_env?: string;
  db_path?: string;
  security?: {
    default_password_warning?: boolean;
  };
  latest_error?: {
    endpoint: string | null;
    status_code: number | null;
    error_msg: string | null;
    called_at: string | null;
  };
}

export interface BacktestMeta {
  market: string;
  earliest_date: string | null;
  latest_date: string | null;
  trade_day_count: number;
  sample_count: number;
  price_count: number;
  fees: {
    commission_rate: number;
    stamp_duty_rate: number;
    transfer_fee_rate: number;
    min_commission: number;
    slippage_rate: number;
  };
  assumptions: {
    has_slippage: boolean;
    has_commission: boolean;
    handles_limit_lock: boolean;
    handles_suspension: boolean;
    benchmark: string;
  };
}

export interface OperationLogItem {
  time: string | null;
  type: string;
  status: string;
  actor: string;
  duration_ms: number;
  summary: string;
  error: string | null;
  status_code: number;
}

// ==================== 管理后台 - API 配置 ====================

export interface ApiConfigItem {
  id: number;
  provider: string;
  display_name: string;
  api_key: string;
  api_secret: string;
  base_url: string | null;
  is_enabled: boolean;
  daily_limit: number;
  rate_limit: number;
  config_json: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface UserQuotaItem {
  user_id: number;
  username: string;
  display_name: string;
  role: string;
  is_active: boolean;
  daily_report_limit: number;
  daily_backtest_limit: number;
  daily_search_limit: number;
  daily_pdf_limit: number;
  can_download_pdf: boolean;
  can_use_style_report: boolean;
  can_use_simulation: boolean;
  today_calls: number;
  today_reports: number;
  today_backtests: number;
}

export interface ApiLogItem {
  id: number;
  user_id: number;
  username: string;
  provider: string;
  endpoint: string;
  method: string;
  status_code: number;
  response_time: number;
  error_msg: string | null;
  called_at: string | null;
}

export interface ApiLogResponse {
  total: number;
  page: number;
  page_size: number;
  items: ApiLogItem[];
}

export interface ApiStatsResponse {
  today_total: number;
  today_errors: number;
  avg_response_time: number;
  by_provider: Record<string, number>;
  by_user: Record<string, number>;
}

export interface AdminStockItem {
  id: number;
  symbol: string;
  name: string;
  market: string;
  exchange: string;
  industry: string | null;
  sector: string | null;
  status: string;
  currency: string;
  created_at: string | null;
}

export interface AdminStockResponse {
  total: number;
  page: number;
  page_size: number;
  items: AdminStockItem[];
}

export interface AdminScoreItem {
  id: number;
  stock_id: number;
  symbol: string;
  name: string;
  total_score: number;
  quality_score: number;
  valuation_score: number;
  growth_score: number;
  trend_score: number;
  risk_score: number;
  rating: string;
  reason_summary: string | null;
  score_date: string;
}

export interface AdminScoreResponse {
  total: number;
  page: number;
  page_size: number;
  items: AdminScoreItem[];
}

export interface AdminSignalItem {
  id: number;
  stock_id: number;
  symbol: string;
  name: string;
  signal_type: string;
  signal_strength: number;
  suggested_position: number;
  entry_price: number | null;
  target_price: number | null;
  stop_loss_price: number | null;
  holding_period: string;
  status: string;
  signal_date: string;
}

export interface AdminSignalResponse {
  total: number;
  page: number;
  page_size: number;
  items: AdminSignalItem[];
}

export interface AdminUserItem {
  id: number;
  username: string;
  display_name: string;
  email: string | null;
  role: string;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface FetchStockResult {
  symbol: string;
  steps: string[];
  status: string;
  stock_id: number;
  stock_name: string;
}

export interface AdminTableDataResponse {
  columns: string[];
  total: number;
  page: number;
  page_size: number;
  data: Array<Record<string, unknown>>;
}
