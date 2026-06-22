/**
 * API 请求封装
 * 所有后端接口集中管理，方便后续维护
 */
import type {
  DashboardData,
  StockSearchResult,
  StockDetail,
  SignalListResponse,
  ResearchReportItem,
  BacktestResult,
  SimulateHolding,
  SimulateResult,
  PoolResponse,
  ReportListResponse,
  ReportItem,
  AdminStats,
  AdminTableInfo,
  AdminTableData,
  StockCount,
  ApiMessage,
  ApiConfigItem,
  UserQuotaItem,
  ApiLogResponse,
  ApiStatsResponse,
  AdminStockResponse,
  AdminScoreResponse,
  AdminSignalResponse,
  AdminUserItem,
  FetchStockResult,
  AdminTableDataResponse,
} from "@/types";

const API_BASE = "/api";

async function fetchAPI<T>(path: string, options?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const { timeoutMs, ...fetchOptions } = options || {};
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchOptions.headers as Record<string, string> || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs || 15000);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...fetchOptions,
      headers,
      signal: controller.signal,
    });
    if (!res.ok) {
      if (res.status === 401 && typeof window !== "undefined") {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        // 通知 auth context 清除状态
        window.dispatchEvent(new Event("auth:logout"));
        window.location.href = "/";
      }
      // 尝试解析后端返回的错误详情
      let detail = "";
      try { const body = await res.json(); detail = body.detail || ""; } catch {}
      throw new Error(detail || `API Error: ${res.status} ${res.statusText}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("请求超时，报告生成耗时较长，请稍后再试");
    throw e;
  } finally {
    clearTimeout(timeout);
  }
}

// ==================== 仪表盘 ====================

export const getDashboard = () => fetchAPI<DashboardData>("/dashboard");

// ==================== 股票 ====================

export const searchStocks = (keyword: string, market?: string) =>
  fetchAPI<StockSearchResult[]>(`/stocks/search?keyword=${encodeURIComponent(keyword)}${market ? `&market=${market}` : ""}`);

export const syncStocks = (market: string = "ALL") =>
  fetchAPI<{ status: string; message: string; added: number; updated: number; total: number }>(`/stocks/sync?market=${market}`, {
    method: "POST",
  });

export const getStockCount = () =>
  fetchAPI<StockCount>("/stocks/count");

export const getStockDetail = (symbol: string) =>
  fetchAPI<StockDetail>(`/stocks/${symbol}`);

// ==================== 信号 ====================

export const getSignals = (params: {
  market?: string;
  signal_type?: string;
  min_score?: number;
  signal_date?: string;
  page?: number;
  page_size?: number;
} = {}) => {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined && val !== null) searchParams.set(key, String(val));
  });
  return fetchAPI<SignalListResponse>(`/signals?${searchParams.toString()}`);
};

// ==================== 股票池 ====================

export const getStockPool = (type: string) =>
  fetchAPI<PoolResponse>(`/pools?type=${type}`);

// ==================== 报告 ====================

export const getReports = (params: { report_type?: string; page?: number; page_size?: number } = {}) => {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined && val !== null) searchParams.set(key, String(val));
  });
  return fetchAPI<ReportListResponse>(`/reports?${searchParams.toString()}`);
};

export const getReport = (id: number) => fetchAPI<ReportItem & { content_markdown: string; content_json: string }>(`/reports/${id}`);

export const getResearchReports = (params: { symbol?: string; page?: number; page_size?: number; refresh?: boolean } = {}) => {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined && val !== null) searchParams.set(key, String(val));
  });
  return fetchAPI<{ total: number; reports: ResearchReportItem[] }>(`/reports/research?${searchParams.toString()}`);
};

export const generateReport = (params: { report_type: string; stock_symbol?: string; style?: string }) =>
  fetchAPI<ApiMessage>(`/reports/generate?report_type=${params.report_type}${params.stock_symbol ? `&stock_symbol=${params.stock_symbol}` : ""}${params.style ? `&style=${params.style}` : ""}`, {
    method: "POST",
    timeoutMs: 120000,
  });

export const generateStyleReport = (style: string) =>
  fetchAPI<ApiMessage>(`/reports/generate-style?style=${style}`, {
    method: "POST",
    timeoutMs: 120000,
  });

export const downloadReportPdf = async (reportId: number, filename: string) => {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60000);
  try {
    const res = await fetch(`/api/reports/${reportId}/pdf`, { headers, signal: controller.signal });
    if (!res.ok) throw new Error("PDF下载失败");

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (e: any) {
    if (e.name === "AbortError") throw new Error("PDF生成超时，请稍后重试");
    throw e;
  } finally {
    clearTimeout(timeout);
  }
};

// ==================== 回测 ====================

export const runBacktest = (params: {
  strategy?: string;
  market?: string;
  start_date?: string;
  end_date?: string;
  rebalance?: string;
  initial_capital?: number;
}) =>
  fetchAPI<BacktestResult>("/backtest/run", {
    method: "POST",
    body: JSON.stringify(params),
  });

export const simulatePortfolio = (holdings: SimulateHolding[]) =>
  fetchAPI<SimulateResult>("/backtest/simulate", {
    method: "POST",
    body: JSON.stringify({ holdings }),
  });

// ==================== 设置 ====================

export const getSettings = () => fetchAPI<Record<string, { value: string; description: string }>>("/settings");

export const getNotificationConfig = () => fetchAPI<Record<string, string>>("/settings/notification");

export const updateNotificationConfig = (config: {
  email_smtp_host?: string;
  email_smtp_port?: string;
  email_sender?: string;
  email_password?: string;
  email_recipient?: string;
  feishu_webhook?: string;
  feishu_enabled?: string;
}) =>
  fetchAPI<{ status: string; message: string }>("/settings/notification", {
    method: "POST",
    body: JSON.stringify(config),
  });

export const testNotification = (type: "email" | "feishu") =>
  fetchAPI<{ status: string; message: string }>(`/settings/test-notification?type=${type}`, {
    method: "POST",
  });

export const saveSetting = (key: string, value: string) =>
  fetchAPI<{ status: string }>("/settings/save", {
    method: "POST",
    body: JSON.stringify({ key, value }),
  });

// ==================== 管理 ====================

export const getAdminStats = () =>
  fetchAPI<AdminStats>("/admin/stats");

export const getAdminUsers = () =>
  fetchAPI<AdminUserItem[]>("/admin/users");

export const updateAdminUser = (id: number, data: { role?: string; is_active?: boolean }) =>
  fetchAPI<{ status: string; message: string }>(`/admin/users/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const disableAdminUser = (id: number) =>
  fetchAPI<{ status: string; message: string }>(`/admin/users/${id}`, {
    method: "DELETE",
  });

export const getAdminTables = () =>
  fetchAPI<AdminTableInfo[]>("/admin/tables");

export const getAdminTableData = (tableName: string, page: number = 1, pageSize: number = 50) =>
  fetchAPI<AdminTableData>(`/admin/tables/${tableName}?page=${page}&page_size=${pageSize}`);

// ==================== API管理 ====================

export const getApiConfigs = () =>
  fetchAPI<ApiConfigItem[]>("/admin/api-configs");

export const saveApiConfig = (config: Partial<ApiConfigItem>) =>
  fetchAPI<{ status: string; message: string; id: number }>("/admin/api-configs", { method: "POST", body: JSON.stringify(config) });

export const deleteApiConfig = (id: number) =>
  fetchAPI<{ status: string; message: string }>(`/admin/api-configs/${id}`, { method: "DELETE" });

export const testApiConfig = (id: number) =>
  fetchAPI<{ status: string; message: string }>(`/admin/api-configs/${id}/test`, { method: "POST" });

export const getUserQuotas = () =>
  fetchAPI<UserQuotaItem[]>("/admin/user-quotas");

export const updateUserQuota = (userId: number, quota: Partial<UserQuotaItem>) =>
  fetchAPI<{ status: string; message: string }>(`/admin/user-quotas/${userId}`, { method: "PUT", body: JSON.stringify(quota) });

export const getApiLogs = (params: { page?: number; page_size?: number; user_id?: number; provider?: string } = {}) => {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined && val !== null) searchParams.set(key, String(val));
  });
  return fetchAPI<ApiLogResponse>(`/admin/api-logs?${searchParams.toString()}`);
};

export const getApiStats = () =>
  fetchAPI<ApiStatsResponse>("/admin/api-stats");

// ==================== 管理-股票管理 ====================

export const getAdminStocks = (params: { keyword?: string; market?: string; status?: string; page?: number; page_size?: number } = {}) => {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") sp.set(k, String(v)); });
  return fetchAPI<AdminStockResponse>(`/admin/stocks?${sp.toString()}`);
};

export const updateAdminStock = (id: number, data: { name?: string; industry?: string; sector?: string; status?: string }) =>
  fetchAPI<{ status: string; message: string }>(`/admin/stocks/${id}`, { method: "PUT", body: JSON.stringify(data) });

export const deleteAdminStock = (id: number) =>
  fetchAPI<{ status: string; message: string }>(`/admin/stocks/${id}`, { method: "DELETE" });

export const adminSyncStocks = (market: string = "ALL") =>
  fetchAPI<{ status: string; message: string; added: number; updated: number; total: number }>(`/admin/stocks/sync?market=${market}`, { method: "POST" });

export const adminFetchStock = (symbol: string) =>
  fetchAPI<FetchStockResult>(`/admin/stocks/fetch?symbol=${encodeURIComponent(symbol)}`, { method: "POST" });

// ==================== 管理-评分管理 ====================

export const getAdminScores = (params: { keyword?: string; rating?: string; page?: number; page_size?: number } = {}) => {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") sp.set(k, String(v)); });
  return fetchAPI<AdminScoreResponse>(`/admin/scores?${sp.toString()}`);
};

export const updateAdminScore = (id: number, data: { quality_score?: number; valuation_score?: number; growth_score?: number; trend_score?: number; risk_score?: number; rating?: string; reason_summary?: string }) =>
  fetchAPI<{ status: string; message: string; total_score: number }>(`/admin/scores/${id}`, { method: "PUT", body: JSON.stringify(data) });

// ==================== 管理-信号管理 ====================

export const getAdminSignals = (params: { keyword?: string; signal_type?: string; status?: string; page?: number; page_size?: number } = {}) => {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") sp.set(k, String(v)); });
  return fetchAPI<AdminSignalResponse>(`/admin/signals?${sp.toString()}`);
};

export const updateAdminSignal = (id: number, data: { signal_type?: string; signal_strength?: number; suggested_position?: number; entry_price?: number; target_price?: number; stop_loss_price?: number; holding_period?: string; status?: string }) =>
  fetchAPI<{ status: string; message: string }>(`/admin/signals/${id}`, { method: "PUT", body: JSON.stringify(data) });

export const deleteAdminSignal = (id: number) =>
  fetchAPI<{ status: string; message: string }>(`/admin/signals/${id}`, { method: "DELETE" });

// ==================== 管理-通用表操作 ====================

export const addTableRow = (tableName: string, data: Record<string, unknown>) =>
  fetchAPI<{ status: string; id: number }>(`/admin/tables/${tableName}`, { method: "POST", body: JSON.stringify(data) });

export const updateTableRow = (tableName: string, rowId: number, data: Record<string, unknown>) =>
  fetchAPI<{ status: string }>(`/admin/tables/${tableName}/${rowId}`, { method: "PUT", body: JSON.stringify(data) });

export const deleteTableRow = (tableName: string, rowId: number) =>
  fetchAPI<{ status: string }>(`/admin/tables/${tableName}/${rowId}`, { method: "DELETE" });
