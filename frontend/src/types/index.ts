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
  report_id?: number | null;
  source_type?: string | null;
  source_name?: string | null;
  source_url?: string | null;
  updated_at?: string | null;
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
  dashboard_sections?: {
    data_coverage: Record<string, number>;
    core_ready_samples: Array<{
      symbol: string;
      name: string;
      market: string;
      exchange: string;
      readiness: string;
      price_count: number;
      financial_count: number;
      technical_count: number;
      score: number;
      signal_label: string;
      detail_url: string;
    }>;
    risk_observation_samples: Array<{
      symbol: string;
      name: string;
      market: string;
      score: number;
      signal_type_label: string;
      primary_low_score_reason: string;
    }>;
    valuation_gap: {
      pe_non_null: number;
      pb_non_null: number;
      real_score_count: number;
      valuation_gap_reason: string;
      next_action: string;
    };
    recent_reports: Array<{
      id: number;
      title: string;
      report_type: string;
      created_at: string;
    }>;
    backtest_entry: {
      sample_count: number;
      trade_day_count: number;
      price_count: number;
      date_range: string;
    };
    demo_entry: {
      demo_score_count: number;
      enabled: boolean;
      label: string;
    };
  };
  meta?: {
    signal_date?: string;
    generated_at?: string;
    cache_mode?: string;
    cache_ttl_seconds?: number;
    is_cached?: boolean;
    available_dates?: string[];
    view_date?: string;
    data_mode?: string;
    data_mode_label?: string;
    warning?: string | null;
    real_score_count?: number;
    demo_score_count?: number;
    real_signal_count?: number;
    demo_signal_count?: number;
    demo_contaminated?: boolean;
    formal_real_count?: number;
    real_observation_count?: number;
    data_quality_limited_count?: number;
    data_insufficient_count?: number;
    core_total?: number;
    core_ready_full_count?: number;
    latest_real_score_date?: string | null;
    avg_total_score?: number | null;
    avg_quality_score?: number | null;
    avg_valuation_score?: number | null;
    avg_growth_score?: number | null;
    avg_trend_score?: number | null;
    avg_risk_score?: number | null;
    low_score_reasons?: Array<{ reason: string; count: number }>;
    launch_data_status?: string;
    data_quality_warning?: string | null;
    cache?: {
      enabled: boolean;
      hit: boolean;
      generated_at: string;
      ttl_seconds: number;
      stale: boolean;
      fallback_used: boolean;
    };
    cache_warning?: string | null;
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
  source?: string;
  updateTime?: string | null;
  dataStatus?: "OK" | "PARTIAL" | "EMPTY" | "ERROR";
  missingFields?: string[];
  errorMessage?: string | null;
  mode?: "live" | "fixture";
  networkStatus?: "READY" | "NETWORK_WARN" | "PROXY_CONFIGURED";
}

export interface AvailableBacktestStock {
  stock_code: string;
  stock_name: string;
  market: string;
  industry?: string | null;
  available_start_date: string | null;
  available_end_date: string | null;
  price_count: number;
  supports_backtest: boolean;
  support_level: "full" | "basic" | "preview" | "insufficient" | "no_price";
  reason?: string | null;
  missing_reason?: string | null;
  supports_report: boolean;
  supports_watchlist: boolean;
  has_financial_snapshot?: boolean;
  has_technical_snapshot?: boolean;
  basic_available?: boolean;
  factor_available?: boolean;
  recommended_mode?: "basic" | "factor" | "unavailable";
  support?: {
    basic_available?: boolean;
    factor_available?: boolean;
    financial_before_start?: boolean;
    technical_before_start?: boolean;
    price_count?: number;
    recommended_mode?: "basic" | "factor" | "unavailable";
    factor_reason?: string | null;
    basic_reason?: string | null;
  };
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
  signal_source?: string | null;
  report_id?: number | null;
  source_type?: string | null;
  source_name?: string | null;
  source_url?: string | null;
  updated_at?: string | null;
}

export interface SignalListResponse {
  total: number;
  page: number;
  page_size: number;
  items: SignalItem[];
  message?: string | null;
  risk_observation_count?: number;
  risk_observation_summary?: {
    risk_rising_count?: number;
    avoid_observation_count?: number;
  };
  risk_observation_items?: Array<{
    symbol: string;
    name: string;
    signal_type?: string | null;
    signal_label?: string | null;
    score?: number | null;
    score_source?: string | null;
    primary_low_score_reason?: string | null;
    display_tier?: string | null;
  }>;
  data_quality_limited_items?: Array<{
    symbol: string;
    name: string;
    signal_type?: string | null;
    signal_label?: string | null;
    score?: number | null;
    score_source?: string | null;
    primary_low_score_reason?: string | null;
    display_tier?: string | null;
    blocking_reasons?: string[];
  }>;
  meta?: {
    include_demo?: boolean;
    real_signal_count?: number;
    demo_signal_count?: number;
    data_mode?: string;
    warning?: string | null;
    demo_isolated?: boolean;
    message?: string | null;
    summary?: {
      real_signal_count?: number;
      formal_signal_count?: number;
      demo_signal_count?: number;
      risk_rising_count?: number;
      avoid_observation_count?: number;
      data_quality_limited_count?: number;
    };
  };
  diagnostics?: {
    real_score_count?: number;
    formal_real_count?: number;
    real_observation_count?: number;
    risk_observation_count?: number;
    risk_rising_count?: number;
    avoid_observation_count?: number;
    data_quality_limited_count?: number;
    top_reasons?: Array<{ reason: string; count: number }>;
    launch_data_status?: string;
  };
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
  score_source?: string | null;
  score_label?: string | null;
  risk_flags?: string[];
  coverage_level?: string | null;
  readiness_label?: string | null;
  display_tier?: string;
  display_tier_label?: string;
  primary_low_score_reason?: string | null;
  blocking_reasons?: string[];
}

export interface StockLibraryResponse {
  total: number;
  page: number;
  page_size: number;
  items: StockLibraryItem[];
  summary: {
    rated_stocks: number;
    rated_records_total?: number;
    current_result_count?: number;
    current_page_count?: number;
    current_page_items_count?: number;
    a_share: number;
    hk: number;
    highest_score: number;
    risk_elevated: number;
    real_score_count?: number;
    demo_score_count?: number;
    formal_real_count?: number;
    real_observation_count?: number;
    data_quality_limited_count?: number;
    data_insufficient_count?: number;
    real_highest_score?: number;
    include_demo?: boolean;
  };
}

export interface ScoreDiagnosticItem {
  stock_code: string;
  stock_name: string;
  market: string;
  industry?: string | null;
  score_date?: string | null;
  signal_date?: string | null;
  signal_type?: string | null;
  signal_strength?: number | null;
  signal_source?: string | null;
  score_source?: string | null;
  total_score?: number | null;
  quality_score?: number | null;
  valuation_score?: number | null;
  growth_score?: number | null;
  trend_score?: number | null;
  risk_score?: number | null;
  latest_close?: number | null;
  latest_trade_date?: string | null;
  market_cap?: number | null;
  pe?: number | null;
  pb?: number | null;
  dividend_yield?: number | null;
  turnover_rate?: number | null;
  report_period?: string | null;
  report_date?: string | null;
  revenue_yoy?: number | null;
  net_profit_yoy?: number | null;
  roe?: number | null;
  gross_margin?: number | null;
  debt_ratio?: number | null;
  operating_cashflow?: number | null;
  free_cashflow?: number | null;
  eps?: number | null;
  book_value_per_share?: number | null;
  previous_roe?: number | null;
  ma5?: number | null;
  ma10?: number | null;
  ma20?: number | null;
  ma60?: number | null;
  ma120?: number | null;
  macd?: number | null;
  macd_signal?: number | null;
  macd_hist?: number | null;
  rsi14?: number | null;
  volume_ratio_5_20?: number | null;
  weekly_volatility?: number | null;
  monthly_volatility?: number | null;
  coverage_level?: string | null;
  readiness_label?: string | null;
  display_tier?: string;
  display_tier_label?: string;
  data_quality_level?: string;
  primary_low_score_reason?: string;
  blocking_reasons?: string[];
}

export interface ScoreDiagnosticsResponse {
  summary: {
    score_date?: string | null;
    included_count: number;
    real_count: number;
    demo_count: number;
    message?: string;
    averages?: {
      total_score?: number | null;
      quality_score?: number | null;
      valuation_score?: number | null;
      growth_score?: number | null;
      trend_score?: number | null;
      risk_score?: number | null;
    };
  };
  display_tier_distribution: Record<string, number>;
  signal_distribution: Record<string, number>;
  low_score_reasons: Array<{ reason: string; count: number }>;
  items: ScoreDiagnosticItem[];
}

export interface ReportItem {
  id: number;
  report_id?: number;
  report_date: string;
  report_type: string;
  style?: string | null;
  stock_code?: string | null;
  stock_name?: string | null;
  market?: string | null;
  title: string;
  summary: string;
  download_count?: number;
  html_views?: number;
  png_downloads?: number;
  pdf_downloads?: number;
  created_at: string;
  report_data_status?: string;
  score_source_used?: string | null;
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
  trend_v2?: number;
  risk: number;
  rating: string;
  rating_label?: string;
  reason: string;
  date: string;
  score_source?: string;
  score_label?: string;
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
    reports?: string | null;
  };
  missing_fields?: string[];
  data_readiness?: {
    has_price: boolean;
    has_financial: boolean;
    has_technical: boolean;
    has_score: boolean;
    score_is_real: boolean;
    readiness_level: string;
  };
  diagnostics?: ScoreDiagnosticItem | null;
  analysis_status?: {
    company_news?: Record<string, any>;
    industry_support?: Record<string, any>;
    shareholder_signal?: Record<string, any>;
    earnings_signal?: Record<string, any>;
    volatility_signal?: Record<string, any>;
  };
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
    signal_source?: string;
    market?: string;
  } | null;
  price_data_quality?: {
    can_render_kline: boolean;
    data_points?: number;
    message?: string | null;
  };
  reports: ResearchReportItem[];
}

export interface BacktestResult {
  stock_code?: string;
  stock_name?: string;
  market?: string;
  strategy_id?: string;
  strategy_name?: string;
  rebalance_frequency?: string;
  user_visible_message?: string;
  total_return: number;
  annual_return: number;
  benchmark_return: number;
  excess_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  win_rate: number;
  total_trades: number;
  metrics?: Record<string, number>;
  equity_curve: Array<{ date: string; equity: number; benchmark: number }>;
  benchmark_curve?: Array<{ date: string; value: number }>;
  monthly_returns: Array<{ month: string; strategy_return: number; benchmark_return: number; excess_return: number }>;
  trade_log: Array<Record<string, any>>;
  strategy_snapshot?: Array<Record<string, any>>;
  strategy_config?: Record<string, any>;
  mode?: "basic" | "factor";
  support?: {
    basic_available?: boolean;
    factor_available?: boolean;
    financial_before_start?: boolean;
    technical_before_start?: boolean;
    price_count?: number;
    recommended_mode?: "basic" | "factor" | "unavailable";
    factor_reason?: string | null;
    basic_reason?: string | null;
  };
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
  message?: string;
  meta?: {
    name: string;
    positioning: string;
    rules: string[];
    scenario: string;
    risks: string[];
    data_updated_at: string | null;
    research_only: boolean;
    display_limit?: number;
    warning?: string | null;
    data_mode?: string;
  };
  diagnostics?: {
    real_score_count?: number;
    demo_score_count?: number;
    formal_real_count?: number;
    real_observation_count?: number;
    risk_observation_count?: number;
    data_quality_limited_count?: number;
    reason_code?: string;
    top_reasons?: Array<{ reason: string; count: number }>;
    launch_data_status?: string;
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
  report_id?: number;
  title?: string;
  type?: string;
  style?: string | null;
  stock_code?: string;
  stock_name?: string;
  market?: string;
  html_url?: string;
  pdf_url?: string;
  png_url?: string;
  png_supported?: boolean;
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
  data_mode_label?: string;
  provider?: string;
  cache_mode?: string;
  app_env?: string;
  db_path?: string;
  real_score_count?: number;
  demo_score_count?: number;
  real_signal_count?: number;
  demo_signal_count?: number;
  financial_metrics_count?: number;
  technical_indicators_count?: number;
  real_pipeline_status?: string;
  real_pipeline_label?: string;
  coverage_message?: string;
  data_coverage?: {
    stocks_total?: number;
    daily_prices_total?: number;
    daily_prices_stocks?: number;
    latest_price_date?: string | null;
    financial_metrics_total?: number;
    financial_metrics_stocks?: number;
    latest_financial_period?: string | null;
    technical_indicators_total?: number;
    technical_indicators_stocks?: number;
    latest_technical_date?: string | null;
    real_calculated_scores?: number;
    quick_seed_demo_scores?: number;
    real_calculated_signals?: number;
    quick_seed_demo_signals?: number;
    latest_real_score_date?: string | null;
    latest_real_signal_date?: string | null;
    scoreable_stock_count?: number;
    not_scoreable_reason_distribution?: Record<string, number>;
  };
  recent_refresh_jobs?: Array<{
    id: number;
    status: string;
    sample_size?: number | null;
    financial_attempted?: number;
    financial_success?: number;
    technical_attempted?: number;
    technical_success?: number;
    scores_attempted?: number;
    scores_success?: number;
    signals_attempted?: number;
    signals_success?: number;
    trigger_source?: string;
  }>;
  warning?: string | null;
  security?: {
    default_password_warning?: boolean;
    default_password_accounts?: string[];
    default_password_risk_level?: string;
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

export interface AvailableBacktestStockResponse {
  market?: string;
  total_price_stocks?: number;
  supported_count?: number;
  full_count?: number;
  basic_count?: number;
  preview_count?: number;
  partial_count?: number;
  unsupported_count?: number;
  requirements?: {
    full_backtest_min_price_count: number;
    basic_backtest_min_price_count: number;
    preview_min_price_count: number;
    min_date_range_days?: number;
  };
  items: AvailableBacktestStock[];
  unavailable_examples?: AvailableBacktestStock[];
  summary: {
    market: string;
    supported_count: number;
    full_count?: number;
    basic_count?: number;
    preview_count?: number;
    unsupported_count: number;
    price_stock_count?: number;
    financial_coverage_count?: number;
    technical_coverage_count?: number;
    diagnosis?: string;
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
  phone?: string | null;
  user_id?: string | null;
  display_name: string;
  email: string | null;
  role: string;
  status?: string;
  is_active: boolean;
  report_count?: number;
  api_config_count?: number;
  pdf_downloads?: number;
  png_downloads?: number;
  html_views?: number;
  last_report_at?: string;
  last_login_at?: string | null;
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
