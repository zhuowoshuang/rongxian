/**
 * API 请求封装
 * 所有后端接口集中管理，方便后续维护
 */
import type {
  DashboardData,
  DashboardAvailableDates,
  StockSearchResult,
  StockDetail,
  SignalListResponse,
  StockLibraryResponse,
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
  RuntimeInfo,
  BacktestMeta,
  OperationLogItem,
  AvailableBacktestStockResponse,
  ScoreDiagnosticsResponse,
} from "@/types";
import { safeGetItem, safeRemoveItem, safeSetItem } from "@/lib/safeStorage";

const API_BASE = "/api";
const DIRECT_API_BASE =   `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"}/api`;
export const AUTH_NOTICE_KEY = "auth-notice";

export type ApiErrorCode = "AUTH_EXPIRED" | "FORBIDDEN" | "NETWORK" | "TIMEOUT" | "HTTP_ERROR";

export class ApiRequestError extends Error {
  status?: number;
  code: ApiErrorCode;

  constructor(message: string, options: { status?: number; code: ApiErrorCode }) {
    super(message);
    this.name = "ApiRequestError";
    this.status = options.status;
    this.code = options.code;
  }
}

export function setAuthNotice(notice: "expired" | "logged_out" | "unauthorized") {
  if (typeof window === "undefined") return;
  safeSetItem(window.sessionStorage, AUTH_NOTICE_KEY, notice);
}

export function getAuthNotice() {
  if (typeof window === "undefined") return null;
  return safeGetItem(window.sessionStorage, AUTH_NOTICE_KEY);
}

export function clearAuthNotice() {
  if (typeof window === "undefined") return;
  safeRemoveItem(window.sessionStorage, AUTH_NOTICE_KEY);
}

export function clearClientSession(notice: "expired" | "logged_out" | "unauthorized" = "expired") {
  if (typeof window === "undefined") return;
  safeRemoveItem(window.localStorage, "token");
  safeRemoveItem(window.localStorage, "user");
  safeRemoveItem(window.sessionStorage, "token");
  safeRemoveItem(window.sessionStorage, "user");
  setAuthNotice(notice);
  window.dispatchEvent(new Event("auth:logout"));
}

export function isApiRequestError(error: unknown): error is ApiRequestError {
  return error instanceof ApiRequestError;
}

export function isAuthExpiredError(error: unknown) {
  return isApiRequestError(error) && error.code === "AUTH_EXPIRED";
}

export function isForbiddenError(error: unknown) {
  return isApiRequestError(error) && error.code === "FORBIDDEN";
}

export function isNetworkError(error: unknown) {
  return isApiRequestError(error) && error.code === "NETWORK";
}

export function isTimeoutError(error: unknown) {
  return isApiRequestError(error) && error.code === "TIMEOUT";
}

function mapApiError(status: number, statusText: string, detail: string): string {
  if (detail) return detail;
  if (status === 400) return "请求参数无效，请检查后重试。";
  if (status === 401) return "登录已过期，请重新登录后查看真实数据。";
  if (status === 403) return "当前账号无权访问此页面。";
  if (status === 404) return "请求的内容不存在或尚未接通。";
  if (status === 408) return "请求超时，请稍后重试。";
  if (status === 429) return "请求过于频繁，请稍后再试。";
  if (status >= 500) return "后端服务暂不可用，请确认本地后端已启动。";
  return `接口请求失败（${status} ${statusText}）`;
}

function normalizeErrorDetail(body: any): string {
  const detail = body?.detail ?? body?.message ?? "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item?.message || JSON.stringify(item)).join("；");
  }
  if (detail && typeof detail === "object") return detail.msg || detail.message || JSON.stringify(detail);
  return "";
}

type FetchApiOptions = RequestInit & {
  timeoutMs?: number;
  timeoutErrorMessage?: string;
  useDirectBase?: boolean;
};

function buildApiUrl(path: string, useDirectBase?: boolean): string {
  const base = useDirectBase ? DIRECT_API_BASE : API_BASE;
  return `${base}${path}`;
}

async function fetchAPI<T>(path: string, options?: FetchApiOptions): Promise<T> {
  const token = typeof window !== "undefined" ? safeGetItem(window.localStorage, "token") : null;
  const { timeoutMs, timeoutErrorMessage, useDirectBase, ...fetchOptions } = options || {};
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((fetchOptions.headers as Record<string, string>) || {}),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs || 15000);
  try {
    const res = await fetch(buildApiUrl(path, useDirectBase), {
      ...fetchOptions,
      headers,
      signal: controller.signal,
    });
    if (!res.ok) {
      let detail = "";
      try {
        const body = await res.json();
        detail = normalizeErrorDetail(body);
      } catch {
        detail = "";
      }
      const message = mapApiError(res.status, res.statusText, detail);
      if (res.status === 401) {
        clearClientSession("expired");
        throw new ApiRequestError(message, { status: 401, code: "AUTH_EXPIRED" });
      }
      if (res.status === 403) {
        throw new ApiRequestError(message, { status: 403, code: "FORBIDDEN" });
      }
      throw new ApiRequestError(message, { status: res.status, code: "HTTP_ERROR" });
    }
    return res.json();
  } catch (error: any) {
    if (error?.name === "AbortError") {
      throw new ApiRequestError(timeoutErrorMessage || "请求超时，请检查后端服务状态。", {
        code: "TIMEOUT",
      });
    }
    if (error instanceof ApiRequestError) throw error;
    if (error instanceof TypeError) {
      throw new ApiRequestError("后端服务暂不可用，请确认本地后端已启动。", {
        code: "NETWORK",
      });
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

async function readDownloadError(res: Response, fallback: string): Promise<string> {
  const contentType = res.headers.get("content-type") || "";
  try {
    if (contentType.includes("application/json")) {
      const body = await res.json();
      const detail = normalizeErrorDetail(body);
      return detail || fallback;
    }
    const text = await res.text();
    return text || fallback;
  } catch {
    return fallback;
  }
}

export const getDashboard = (date?: string, includeDemo?: boolean, refresh?: boolean) => {
  const searchParams = new URLSearchParams();
  if (date) searchParams.set("date", date);
  if (includeDemo) searchParams.set("include_demo", "true");
  if (refresh) searchParams.set("refresh", "true");
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return fetchAPI<DashboardData>(`/dashboard${suffix}`, { timeoutMs: 60000 });
};

export const getDashboardAvailableDates = (includeDemo?: boolean) =>
  fetchAPI<DashboardAvailableDates>(`/dashboard/available-dates${includeDemo ? "?include_demo=true" : ""}`);

// ==================== 股票 ====================

export const searchStocks = async (keyword: string, market?: string) => {
  const searchParams = new URLSearchParams();
  searchParams.set("keyword", keyword);
  if (market) searchParams.set("market", market);
  const items = await fetchAPI<StockSearchResult[]>(`/stocks/search?${searchParams.toString()}`);
  return items.map((item) => ({
    ...item,
    source: item.source || "database",
    dataStatus: item.dataStatus || "OK",
    networkStatus: item.networkStatus || "READY",
    mode: item.mode || "live",
    missingFields: item.missingFields || [],
    errorMessage: item.errorMessage || null,
  }));
};

export const syncStocks = (market: string = "ALL") =>
  fetchAPI<{ status: string; message: string; added: number; updated: number; total: number }>(`/stocks/sync?market=${market}`, {
    method: "POST",
  });

export const getStockCount = () =>
  fetchAPI<StockCount>("/stocks/count");

export const getStockDetail = (symbol: string) =>
  fetchAPI<StockDetail>(`/stocks/${symbol}`);

export const getAvailableBacktestStocks = (market: string = "A_SHARE", limit: number = 12) =>
  fetchAPI<AvailableBacktestStockResponse>(`/stocks/available-for-backtest?market=${encodeURIComponent(market)}&limit=${limit}`);

export const getStockLibrary = (params: {
  market?: string;
  rating?: string;
  keyword?: string;
  include_demo?: boolean;
  page?: number;
  page_size?: number;
} = {}) => {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined && val !== null && val !== "") searchParams.set(key, String(val));
  });
  return fetchAPI<StockLibraryResponse>(`/stocks?${searchParams.toString()}`);
};

export const getScoreDiagnostics = (scoreDate?: string) =>
  fetchAPI<ScoreDiagnosticsResponse>(`/stocks/diagnostics${scoreDate ? `?score_date=${encodeURIComponent(scoreDate)}` : ""}`);

// ==================== 信号 ====================

export const getSignals = (params: {
  market?: string;
  signal_type?: string;
  min_score?: number;
  signal_date?: string;
  include_demo?: boolean;
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

export const getStockPool = (type: string, includeDemo?: boolean) =>
  fetchAPI<PoolResponse>(`/pools?type=${encodeURIComponent(type)}${includeDemo ? "&include_demo=true" : ""}`);

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
    timeoutErrorMessage: "报告生成超时，请检查后端服务状态后重试。",
  });

export const generateStyleReport = (style: string) =>
  fetchAPI<ApiMessage>(`/reports/generate-style?style=${style}`, {
    method: "POST",
    timeoutMs: 120000,
    timeoutErrorMessage: "风格研究报告生成超时，请稍后重试。",
  });

export const downloadReportPdf = async (reportId: number, filename: string) => {
  const token = typeof window !== "undefined" ? safeGetItem(window.localStorage, "token") : null;
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120000);  // 2 分钟超时
  try {
    const res = await fetch(`/api/reports/${reportId}/pdf`, { headers, signal: controller.signal });
    if (!res.ok) {
      if (res.status === 401) {
        clearClientSession("expired");
        throw new ApiRequestError("登录已过期，请重新登录后下载 PDF 报告。", { status: 401, code: "AUTH_EXPIRED" });
      }
      throw new Error(await readDownloadError(res, `PDF 下载失败（HTTP ${res.status}），请稍后重试`));
    }

    const blob = await res.blob();
    if (blob.size < 100) {
      throw new Error("PDF 内容为空");
    }
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

export const downloadReportPng = async (reportId: number, filename: string) => {
  const token = typeof window !== "undefined" ? safeGetItem(window.localStorage, "token") : null;
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`/api/reports/${reportId}/png`, { headers });
  if (!res.ok) {
    if (res.status === 401) {
      clearClientSession("expired");
      throw new ApiRequestError("登录已过期，请重新登录后下载 PNG 摘要图。", { status: 401, code: "AUTH_EXPIRED" });
    }
    throw new Error(await readDownloadError(res, "PNG 摘要图生成失败，请稍后重试"));
  }
  const blob = await res.blob();
  if (blob.size < 100) throw new Error("PNG 摘要图内容为空");
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
};

// ==================== 回测 ====================

export const runBacktest = (params: {
  strategy?: string;
  strategy_id?: string;
  stock_symbol?: string;
  stock_code?: string;
  stock_name?: string;
  market?: string;
  start_date?: string;
  end_date?: string;
  rebalance?: string;
  rebalance_frequency?: string;
  initial_capital?: number;
}) =>
  fetchAPI<BacktestResult>("/backtest/run", {
    method: "POST",
    body: JSON.stringify(params),
    timeoutMs: 120000,
    timeoutErrorMessage: "回测请求超时，请检查后端服务状态后重试。",
  });

export const simulatePortfolio = (holdings: SimulateHolding[]) =>
  fetchAPI<SimulateResult>("/backtest/simulate", {
    method: "POST",
    body: JSON.stringify({ holdings }),
    timeoutMs: 120000,
    timeoutErrorMessage: "组合模拟请求超时，请检查后端服务状态后重试。",
  });

export const getBacktestMeta = (market: string = "A_SHARE") =>
  fetchAPI<BacktestMeta>(`/backtest/meta?market=${market}`, {
    timeoutMs: 10000,
  });

// ==================== 设置 ====================

export const getSettings = () => fetchAPI<Record<string, { value: string; description: string }>>("/settings");

export const getNotificationConfig = () => fetchAPI<Record<string, string>>("/settings/notification");

export const getRuntimeInfo = () => fetchAPI<RuntimeInfo>("/settings/runtime-info");

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

export const getAdminSystemStatus = () =>
  fetchAPI<RuntimeInfo>("/admin/system-status");

export const getAdminScoreDiagnostics = (scoreDate?: string) =>
  fetchAPI<ScoreDiagnosticsResponse>(`/admin/score-diagnostics${scoreDate ? `?score_date=${encodeURIComponent(scoreDate)}` : ""}`);

export const getAdminUsers = () =>
  fetchAPI<AdminUserItem[]>("/admin/users");

export const exportAdminUsersExcel = async () => {
  const token = typeof window !== "undefined" ? safeGetItem(window.localStorage, "token") : null;
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch("/api/admin/users/export", { headers });
  if (!res.ok) throw new Error("Excel 导出失败，请稍后重试。");
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "用户运营统计.xlsx";
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
};

export const resetAdminUserPassword = (id: number, password: string) =>
  fetchAPI<{ status: string; message: string }>(`/admin/users/${id}/reset-password`, {
    method: "POST",
    body: JSON.stringify({ password }),
  });

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
  fetchAPI<AdminTableDataResponse>(`/admin/tables/${tableName}?page=${page}&page_size=${pageSize}`);

// ==================== API管理 ====================

export const getApiConfigs = () =>
  fetchAPI<ApiConfigItem[]>("/admin/api-configs");

export const saveApiConfig = (config: Partial<ApiConfigItem>) =>
  fetchAPI<{ status: string; message: string; id: number }>("/admin/api-configs", { method: "POST", body: JSON.stringify(config) });

export const deleteApiConfig = (id: number) =>
  fetchAPI<{ status: string; message: string }>(`/admin/api-configs/${id}`, { method: "DELETE" });

export const testApiConfig = (id: number) =>
  fetchAPI<{ status: string; message: string }>(`/admin/api-configs/${id}/check`, { method: "POST" });

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

export const getOperationLogs = (limit: number = 30) =>
  fetchAPI<{ items: OperationLogItem[] }>(`/admin/operation-logs?limit=${limit}`);

export const getOperationLogSummary = () =>
  fetchAPI<Record<string, any>>("/admin/operation-logs/summary");

export const getAdminUsageRankings = () =>
  fetchAPI<Record<string, any[]>>("/admin/usage-rankings");

export const getAuditLogs = (params: { range?: string; user_keyword?: string; action?: string; status?: string; start_date?: string; end_date?: string; page?: number; page_size?: number } = {}) => {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([key, val]) => { if (val !== undefined && val !== null && val !== "") sp.set(key, String(val)); });
  return fetchAPI<{ total: number; page: number; page_size: number; items: any[] }>(`/admin/audit-logs?${sp.toString()}`);
};

export const exportAuditLogsExcel = async (params: { range?: string; user_keyword?: string; action?: string; status?: string; start_date?: string; end_date?: string } = {}) => {
  const token = typeof window !== "undefined" ? safeGetItem(window.localStorage, "token") : null;
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([key, val]) => { if (val !== undefined && val !== null && val !== "") sp.set(key, String(val)); });
  const res = await fetch(`/api/admin/audit-logs/export?${sp.toString()}`, { headers });
  if (!res.ok) throw new Error("审计日志 Excel 导出失败，请稍后重试。");
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "审计日志.xlsx";
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
};

export const getProfile = () => fetchAPI<Record<string, any>>("/profile");
export const getMyUsage = () => fetchAPI<Record<string, any>>("/profile/usage");
export const getMyApiConfigs = () => fetchAPI<any[]>("/profile/api-configs");
export const createMyApiConfig = (data: Record<string, any>) => fetchAPI<any>("/profile/api-configs", { method: "POST", body: JSON.stringify(data) });
export const updateMyApiConfig = (id: number, data: Record<string, any>) => fetchAPI<any>(`/profile/api-configs/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteMyApiConfig = (id: number) => fetchAPI<{ status: string }>(`/profile/api-configs/${id}`, { method: "DELETE" });
export const testMyApiConfig = (id: number) => fetchAPI<{ status: string; message: string }>(`/profile/api-configs/${id}/test`, { method: "POST" });
export const getMyReports = () => fetchAPI<any[]>("/profile/reports");
export const getMyBacktests = () => fetchAPI<any[]>("/profile/backtests");
export const getMyWatchlist = () => fetchAPI<any[]>("/profile/watchlist");
export const createMyWatchlistItem = (data: Record<string, any>) => fetchAPI<any>("/profile/watchlist", { method: "POST", body: JSON.stringify(data) });
export const refreshMyWatchlistItem = (id: number) => fetchAPI<any>(`/profile/watchlist/${id}/refresh`, { method: "POST" });
export const getMyWatchlistSnapshot = (id: number) => fetchAPI<any>(`/profile/watchlist/${id}/snapshot`);
export const deleteMyWatchlistItem = (id: number) => fetchAPI<{ status: string; message: string }>(`/profile/watchlist/${id}`, { method: "DELETE" });
export const getBacktestStrategies = () => fetchAPI<{ items: any[] }>("/backtest/strategies");
export const getAdminWatchlistStats = () => fetchAPI<Record<string, any>>("/admin/watchlist-stats");

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
