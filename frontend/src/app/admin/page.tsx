"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useAuth } from "@/lib/auth";
import {
  getAdminStats, getAdminUsers, updateAdminUser, disableAdminUser,
  getAdminTables, getAdminTableData,
  getApiConfigs, saveApiConfig, deleteApiConfig, testApiConfig,
  getUserQuotas, updateUserQuota,
  getApiLogs, getApiStats,
  getAdminSystemStatus,
  getAdminScoreDiagnostics,
  getOperationLogSummary,
  getAdminUsageRankings,
  getAuditLogs,
  exportAuditLogsExcel,
  exportAdminUsersExcel,
  resetAdminUserPassword,
  getAdminWatchlistStats,
  getAdminStocks, updateAdminStock, deleteAdminStock, adminSyncStocks, adminFetchStock,
  getAdminScores, updateAdminScore,
  getAdminSignals, updateAdminSignal, deleteAdminSignal,
} from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import type {
  AdminStats, AdminStockItem, AdminStockResponse,
  AdminScoreItem, AdminScoreResponse,
  AdminSignalItem, AdminSignalResponse,
  AdminUserItem, ApiConfigItem, AdminTableInfo, AdminTableDataResponse,
  RuntimeInfo,
  ScoreDiagnosticsResponse,
} from "@/types";
import GlassCard from "@/components/ui/GlassCard";
import TabSwitch from "@/components/ui/TabSwitch";
import { SkeletonCard } from "@/components/ui/Skeleton";
import EmptyState from "@/components/ui/EmptyState";
import DataStatusBadge from "@/components/ui/DataStatusBadge";
import { Shield, Users, Database, BarChart3, AlertCircle, CheckCircle, Key, Activity, Settings, Search, Plus, RefreshCw, Trash2, Edit3, Save, X, Download, Zap } from "lucide-react";
import { displayTierLabel, displayTierTone, sanitizeDisplayText, signalTypeLabel } from "@/lib/utils";

export default function AdminPage() {
  const { t } = useTranslation();
  const { user } = useAuth();

  if (user && user.role !== "admin") {
    return (
      <div className="mx-auto max-w-[960px] p-6" style={{ background: "var(--bg-page)" }}>
        <EmptyState
          message="权限不足"
          description="当前账号可以使用研究功能，但无权访问管理员运行驾驶舱。请使用管理员账号登录后再查看。"
        />
      </div>
    );
  }

  const [activeTab, setActiveTab] = useState("overview");
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    const tab = new URLSearchParams(window.location.search).get("tab");
    if (tab) setActiveTab(tab);
  }, []);

  const showMsg = (type: "ok" | "err", text: string) => {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 3000);
  };

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto" style={{ background: "var(--bg-page)" }}>
      <h1 className="text-h1 flex items-center gap-2">
        <span className="w-1 h-6 bg-primary-500 rounded-full" />
        {t("admin.title")}
      </h1>

      {msg && (
        <div className={`px-4 py-3 rounded-xl text-sm font-medium flex items-center gap-2 ${
          msg.type === "ok" ? "card-success" : "card-danger"
        }`}>
          {msg.type === "ok" ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
          {msg.text}
        </div>
      )}

      <div className="flex gap-2 flex-wrap bg-white rounded-xl p-1 border border-[var(--border-default)] shadow-sm">
        {[
          { key: "overview", label: t("admin.tabOverview") },
          { key: "stocks", label: t("admin.tabStocks") },
          { key: "scores", label: t("admin.tabScores") },
          { key: "signals", label: t("admin.tabSignals") },
          { key: "users", label: t("admin.tabUsers") },
          { key: "database", label: t("admin.tabDatabase") },
          { key: "api-config", label: t("admin.tabApiConfig") },
          { key: "exports", label: "导出管理" },
          { key: "audit", label: "审计日志" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab.key
                ? "bg-primary-50 text-primary-700 shadow-sm font-semibold"
                : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface)]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "overview" && <OverviewTab />}
      {activeTab === "stocks" && <StocksTab showMsg={showMsg} />}
      {activeTab === "scores" && <ScoresTab showMsg={showMsg} />}
      {activeTab === "signals" && <SignalsTab showMsg={showMsg} />}
      {activeTab === "users" && <UsersTab showMsg={showMsg} />}
      {activeTab === "database" && <DatabaseTab />}
      {activeTab === "api-config" && <ApiConfigTab showMsg={showMsg} />}
      {activeTab === "audit" && <AuditTab showMsg={showMsg} />}
      {activeTab === "exports" && <ExportsTab showMsg={showMsg} />}

      <div className="disclaimer">{t("app.disclaimer")}</div>
    </div>
  );
}

// ─── 工具函数 ───
const ratingColors: Record<string, string> = {
  BUY: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  ADD: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  WATCH: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  REDUCE: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  SELL: "bg-red-500/15 text-red-400 border-red-500/30",
};

const signalColors: Record<string, string> = {
  BUY: "bg-emerald-500/15 text-emerald-400",
  ADD: "bg-blue-500/15 text-blue-400",
  WATCH: "bg-amber-500/15 text-amber-400",
  REDUCE: "bg-orange-500/15 text-orange-400",
  SELL: "bg-red-500/15 text-red-400",
};

function Badge({ text, className }: { text: string; className?: string }) {
  return <span className={`text-xs px-2 py-0.5 rounded-full border ${className || "bg-white/5 text-dark-muted border-white/10"}`}>{text}</span>;
}

function SearchBar({ value, onChange, placeholder, onSearch }: { value: string; onChange: (v: string) => void; placeholder?: string; onSearch?: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="flex gap-2">
      <div className="relative flex-1">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)] pointer-events-none" />
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSearch?.()}
          placeholder={placeholder || t("admin.search")}
          className="w-full pl-9 pr-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-dark-text placeholder:text-dark-muted focus:outline-none focus:border-primary-500/40"
        />
      </div>
      {onSearch && (
        <button onClick={onSearch} className="px-4 py-2 bg-primary-500/15 text-primary-400 border border-primary-500/30 rounded-lg text-sm hover:bg-primary-500/25 transition-colors">
          <Search className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}

function Pagination({ page, total, pageSize, onChange }: { page: number; total: number; pageSize: number; onChange: (p: number) => void }) {
  const { t } = useTranslation();
  const pages = Math.ceil(total / pageSize);
  if (pages <= 1) return null;
  return (
    <div className="flex items-center justify-between mt-4 pt-4 border-t border-white/[0.06]">
      <span className="text-xs text-dark-muted">{t("admin.totalItems", { total: String(total) })}</span>
      <div className="flex items-center gap-2">
        <button onClick={() => onChange(page - 1)} disabled={page <= 1} className="px-3 py-1.5 text-xs rounded-lg bg-white/[0.05] text-dark-muted hover:bg-white/[0.1] disabled:opacity-30 transition-colors">{t("admin.prevPage")}</button>
        <span className="text-xs text-dark-muted px-2">{page} / {pages}</span>
        <button onClick={() => onChange(page + 1)} disabled={page >= pages} className="px-3 py-1.5 text-xs rounded-lg bg-white/[0.05] text-dark-muted hover:bg-white/[0.1] disabled:opacity-30 transition-colors">{t("admin.nextPage")}</button>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════
// 系统概览
// ══════════════════════════════════════════════════════════

function OverviewTab() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<RuntimeInfo | null>(null);
  const [scoreDiagnostics, setScoreDiagnostics] = useState<ScoreDiagnosticsResponse | null>(null);
  const [logSummary, setLogSummary] = useState<Record<string, any> | null>(null);
  const [watchStats, setWatchStats] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getAdminSystemStatus(), getAdminScoreDiagnostics().catch(() => null), getOperationLogSummary().catch(() => null), getAdminWatchlistStats().catch(() => null)])
      .then(([systemStatus, diagnosticsValue, summary, watchlist]) => {
        setStatus(systemStatus);
        setScoreDiagnostics(diagnosticsValue);
        setLogSummary(summary);
        setWatchStats(watchlist);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <SkeletonCard />;

  const counts = (status?.counts || {}) as Record<string, number>;
  const updates = (status?.latest_updates || {}) as Record<string, string | null>;
  const security = (status?.security || {}) as {
    default_password_warning?: boolean;
    default_password_accounts?: string[];
    default_password_risk_level?: string;
  };
  const apiCfg = (status?.api_configured || {}) as Record<string, number>;

  return (
    <div className="space-y-6">
      {/* 核心指标卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {[
          { label: t("admin.stockCount"), value: counts.stocks ?? 0, icon: <BarChart3 className="w-5 h-5" />, color: "text-primary-400" },
          { label: t("admin.signalCount"), value: counts.signals ?? 0, icon: <Zap className="w-5 h-5" />, color: "text-emerald-400" },
          { label: t("admin.scoreCount"), value: counts.scores ?? 0, icon: <Activity className="w-5 h-5" />, color: "text-blue-400" },
          { label: t("admin.reportCount"), value: counts.reports ?? 0, icon: <Activity className="w-5 h-5" />, color: "text-amber-400" },
          { label: t("admin.dbSizeLabel"), value: status?.db_size || "N/A", icon: <Database className="w-5 h-5" />, color: "text-purple-400" },
          { label: t("admin.researchReports"), value: counts.research_reports ?? 0, icon: <Key className="w-5 h-5" />, color: "text-cyan-400" },
        ].map((m) => (
          <GlassCard key={m.label} className="text-center">
            <div className={`${m.color} mb-2 flex justify-center`}>{m.icon}</div>
            <p className="text-2xl font-bold text-[var(--text-primary)] font-mono">{typeof m.value === "number" ? m.value.toLocaleString() : m.value}</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{m.label}</p>
          </GlassCard>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {[
          { label: "真实评分数量", value: status?.real_score_count ?? 0 },
          { label: "演示评分数量", value: status?.demo_score_count ?? 0 },
          { label: "真实信号数量", value: status?.real_signal_count ?? 0 },
          { label: "演示信号数量", value: status?.demo_signal_count ?? 0 },
          { label: "财务数据数量", value: status?.financial_metrics_count ?? 0 },
          { label: "技术指标数量", value: status?.technical_indicators_count ?? 0 },
        ].map((item) => (
          <GlassCard key={item.label} className="text-center">
            <p className="text-2xl font-bold text-[var(--text-primary)] font-mono">{item.value.toLocaleString()}</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{item.label}</p>
          </GlassCard>
        ))}
      </div>

      <GlassCard title="真实数据覆盖中心">
        <div className="space-y-4">
          <div className={`rounded-lg border p-3 text-sm ${(status?.real_score_count ?? 0) === 0 ? "border-red-200 bg-red-50 text-red-800" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`}>
            {status?.coverage_message || ((status?.real_score_count ?? 0) === 0
              ? "真实评分尚未生成，C 端只展示行情和数据状态。"
              : `真实评分已小样本跑通，覆盖 ${status?.real_score_count ?? 0} 条评分记录。`)}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            {[
              { label: "行情覆盖股票", value: status?.data_coverage?.daily_prices_stocks ?? counts.prices ?? 0 },
              { label: "财务覆盖股票", value: status?.data_coverage?.financial_metrics_stocks ?? 0 },
              { label: "技术指标覆盖", value: status?.data_coverage?.technical_indicators_stocks ?? 0 },
              { label: "可评分股票", value: status?.data_coverage?.scoreable_stock_count ?? 0 },
            ].map((item) => (
              <div key={item.label} className="rounded-lg border border-[var(--border-subtle)] p-3">
                <p className="text-caption">{item.label}</p>
                <p className="text-lg font-mono font-semibold">{Number(item.value).toLocaleString()}</p>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
            {[
              { label: "最新行情", value: updates.prices },
              { label: "最新财务期", value: status?.data_coverage?.latest_financial_period },
              { label: "最新技术指标", value: updates.technicals || status?.data_coverage?.latest_technical_date },
              { label: "最新真实评分", value: updates.latest_real_score_date },
              { label: "最新真实信号", value: updates.latest_real_signal_date },
            ].map((item) => (
              <div key={item.label} className="flex justify-between gap-3">
                <span className="text-caption">{item.label}</span>
                <span className="font-mono">{item.value || "暂无"}</span>
              </div>
            ))}
          </div>
          {(status?.recent_refresh_jobs?.length ?? 0) > 0 && (
            <div>
              <p className="text-caption mb-2">最近刷新任务（最多10条）</p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-[var(--text-muted)]">
                      <th className="py-1 pr-2">ID</th>
                      <th className="py-1 pr-2">状态</th>
                      <th className="py-1 pr-2">样本</th>
                      <th className="py-1 pr-2">财务</th>
                      <th className="py-1 pr-2">技术</th>
                      <th className="py-1 pr-2">评分</th>
                      <th className="py-1 pr-2">信号</th>
                      <th className="py-1">触发</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(status?.recent_refresh_jobs || []).slice(0, 10).map((job) => (
                      <tr key={job.id} className="border-t border-[var(--border-subtle)]">
                        <td className="py-1 pr-2 font-mono">{job.id}</td>
                        <td className="py-1 pr-2">{job.status}</td>
                        <td className="py-1 pr-2">{job.sample_size ?? "-"}</td>
                        <td className="py-1 pr-2">{job.financial_success}/{job.financial_attempted}</td>
                        <td className="py-1 pr-2">{job.technical_success}/{job.technical_attempted}</td>
                        <td className="py-1 pr-2">{job.scores_success}/{job.scores_attempted}</td>
                        <td className="py-1 pr-2">{job.signals_success}/{job.signals_attempted}</td>
                        <td className="py-1">{job.trigger_source}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </GlassCard>

      {scoreDiagnostics && (
        <GlassCard title="真实评分诊断">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <DataStatusBadge label={`真实样本 ${scoreDiagnostics.summary.real_count}`} tone="live" />
              <DataStatusBadge label={`演示样本 ${scoreDiagnostics.summary.demo_count}`} tone="simulated" />
              <DataStatusBadge label={`评分日期 ${scoreDiagnostics.summary.score_date || "待核验"}`} tone="database" />
            </div>
            <p className="text-sm text-[var(--text-secondary)]">
              {sanitizeDisplayText(scoreDiagnostics.summary.message, "用于解释当前真实评分结果结构，不对模型分数做人工修饰。")}
            </p>
            <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
              {[
                { label: "平均总分", value: scoreDiagnostics.summary.averages?.total_score },
                { label: "质量均分", value: scoreDiagnostics.summary.averages?.quality_score },
                { label: "估值均分", value: scoreDiagnostics.summary.averages?.valuation_score },
                { label: "成长均分", value: scoreDiagnostics.summary.averages?.growth_score },
                { label: "趋势均分", value: scoreDiagnostics.summary.averages?.trend_score },
                { label: "风险均分", value: scoreDiagnostics.summary.averages?.risk_score },
              ].map((item) => (
                <div key={item.label} className="rounded-lg border border-[var(--border-subtle)] p-3">
                  <p className="text-caption">{item.label}</p>
                  <p className="text-lg font-mono font-semibold text-[var(--text-primary)]">{item.value ?? "--"}</p>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(scoreDiagnostics.display_tier_distribution || {}).map(([key, value]) => (
                <DataStatusBadge key={key} label={`${displayTierLabel(key)} ${value}`} tone={displayTierTone(key)} />
              ))}
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              <div className="rounded-lg border border-[var(--border-subtle)] p-3">
                <p className="text-caption mb-2">低分主因</p>
                <div className="space-y-2 text-sm text-[var(--text-secondary)]">
                  {(scoreDiagnostics.low_score_reasons || []).slice(0, 5).map((item) => (
                    <div key={item.reason} className="flex items-center justify-between gap-3">
                      <span>{sanitizeDisplayText(item.reason, "待核验")}</span>
                      <span className="font-mono text-[var(--text-primary)]">{item.count}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="rounded-lg border border-[var(--border-subtle)] p-3">
                <p className="text-caption mb-2">真实信号结构</p>
                <div className="space-y-2 text-sm text-[var(--text-secondary)]">
                  {Object.entries(scoreDiagnostics.signal_distribution || {}).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between gap-3">
                      <span>{signalTypeLabel(key)}</span>
                      <span className="font-mono text-[var(--text-primary)]">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </GlassCard>
      )}

      {/* 系统状态 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <GlassCard title="系统状态">
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-caption">数据库状态</span>
              <DataStatusBadge label={status?.database === "ok" ? "正常" : "异常"} tone={status?.database === "ok" ? "live" : "warning"} />
            </div>
            <div className="flex justify-between items-center">
              <span className="text-caption">Redis 状态</span>
              <DataStatusBadge label={status?.redis === "ok" ? "正常" : "不可用"} tone={status?.redis === "ok" ? "live" : "simulated"} />
            </div>
            {status?.redis !== "ok" && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800">
                缓存服务：内存模式运行中（本地演示环境无需 Redis）
              </div>
            )}
            <div className="flex justify-between items-center">
              <span className="text-caption">数据源模式</span>
              <DataStatusBadge label={status?.data_mode_label || status?.data_mode || "待核验"} tone={status?.provider_mode === "mock" ? "simulated" : "live"} />
            </div>
            {status?.provider_mode !== "mock" && (status?.real_signal_count ?? 0) === 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800">
                数据源：真实行情已接入，正式信号待评分扩展
              </div>
            )}
            <div className="flex justify-between items-center">
              <span className="text-caption">真实评分链路</span>
              <DataStatusBadge
                label={
                  status?.real_pipeline_status === "ready"
                    ? "小样本真实闭环已打通"
                    : status?.real_pipeline_status === "partial_ready"
                      ? "部分真实评分已生成"
                      : status?.real_pipeline_status === "financial_missing"
                        ? "财务数据待刷新"
                        : status?.real_pipeline_status === "financial_ready_only"
                          ? "财务已接入，待补技术指标"
                          : status?.real_pipeline_status === "technical_ready_only"
                            ? "技术指标已就绪"
                            : status?.real_pipeline_status === "provider_failed"
                              ? "财务 Provider 失败"
                              : "仅有真实行情"
                }
                tone={status?.real_pipeline_status === "ready" ? "live" : "warning"}
              />
            </div>
            <div className="flex justify-between items-center">
              <span className="text-caption">API 配置</span>
              <span className="text-body text-sm">{apiCfg.enabled || 0} / {apiCfg.total || 0} 已启用</span>
            </div>
            {security.default_password_warning && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-caption">默认密码风险</span>
                  <DataStatusBadge
                    label={security.default_password_risk_level === "critical" ? "生产高风险" : "开发验收账号存在"}
                    tone="warning"
                  />
                </div>
                <p className="mt-2">
                  系统检测到默认开发账号仍在使用，生产部署前必须修改。
                </p>
              </div>
            )}
            {status?.warning && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800">
                {status.warning}
              </div>
            )}
          </div>
        </GlassCard>

        <GlassCard title="数据新鲜度">
          <div className="space-y-3">
            {[
              { label: "最新行情", value: updates.prices },
              { label: "最新评分", value: updates.scores },
              { label: "最新信号", value: updates.signals },
              { label: "最新报告", value: updates.reports },
              { label: "券商研报", value: updates.research_reports },
            ].map((item) => (
              <div key={item.label} className="flex justify-between items-center">
                <span className="text-caption">{item.label}</span>
                <span className="text-body text-sm font-mono">{item.value || "暂无记录"}</span>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      <GlassCard title="关注股票统计">
        <div className="grid gap-4 xl:grid-cols-[320px_1fr]">
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "总关注数", value: watchStats?.summary?.total_items ?? 0 },
              { label: "今日新增关注", value: watchStats?.summary?.today_added ?? 0 },
              { label: "关注用户数", value: watchStats?.summary?.total_users ?? 0 },
              { label: "快照已就绪", value: watchStats?.summary?.snapshots_ready ?? 0 },
              { label: "高波动关注数", value: watchStats?.summary?.high_volatility_watch_count ?? 0 },
              { label: "关注后回测", value: watchStats?.summary?.backtests_after_watch ?? 0 },
              { label: "关注后报告", value: watchStats?.summary?.reports_after_watch ?? 0 },
            ].map((item) => (
              <div key={item.label} className="rounded-xl border border-[var(--border-default)] bg-slate-50 p-3">
                <p className="text-xs text-[var(--text-secondary)]">{item.label}</p>
                <p className="mt-2 text-xl font-bold text-[var(--text-primary)] font-mono">{item.value}</p>
              </div>
            ))}
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-[var(--border-default)] bg-white p-4">
              <p className="text-sm font-semibold text-[var(--text-primary)]">TOP 关注股票</p>
              <div className="mt-3 space-y-2">
                {(watchStats?.top_watched || []).slice(0, 8).map((item: any) => (
                  <div key={item.stock_code} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                    <div>
                      <div className="font-mono text-slate-900">{item.stock_code}</div>
                      <div className="text-xs text-slate-500">{item.stock_name || "未命名"} · {item.industry || "未分类"}</div>
                    </div>
                    <div className="font-mono text-slate-900">{item.watch_count}</div>
                  </div>
                ))}
                {(!watchStats?.top_watched || watchStats.top_watched.length === 0) && <div className="text-xs text-slate-500">暂无关注数据</div>}
              </div>
            </div>
            <div className="rounded-xl border border-[var(--border-default)] bg-white p-4">
              <p className="text-sm font-semibold text-[var(--text-primary)]">行业分布</p>
              <div className="mt-3 space-y-2">
                {(watchStats?.industry_distribution || []).slice(0, 8).map((item: any) => (
                  <div key={item.industry} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                    <span className="text-slate-700">{item.industry || "未分类"}</span>
                    <span className="font-mono text-slate-900">{item.watch_count}</span>
                  </div>
                ))}
                {(!watchStats?.industry_distribution || watchStats.industry_distribution.length === 0) && <div className="text-xs text-slate-500">暂无关注数据</div>}
              </div>
            </div>
          </div>
        </div>
      </GlassCard>

      {/* 研究口径说明 */}
      <GlassCard title="运行与操作摘要">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {[
            { label: "最近报告生成", item: logSummary?.latest_report_generate },
            { label: "最近 HTML 查看", item: logSummary?.latest_html_view },
            { label: "最近 PNG 导出", item: logSummary?.latest_png_export },
            { label: "最近 PDF 导出", item: logSummary?.latest_pdf_export },
            { label: "最近回测 / 模拟", item: logSummary?.latest_backtest },
            { label: "最近 API 配置 / 管理操作", item: logSummary?.latest_admin_action },
            { label: "最近错误", item: logSummary?.latest_error },
            { label: "最近股票同步", item: logSummary?.latest_stock_sync },
          ].map(({ label, item }) => (
            <div key={label} className="rounded-xl border border-[var(--border-default)] bg-slate-50 p-3">
              <p className="text-xs font-medium text-[var(--text-secondary)]">{label}</p>
              <p className="mt-2 text-sm font-semibold text-[var(--text-primary)]">{item?.time || "暂无记录"}</p>
              <p className="mt-1 text-xs text-[var(--text-secondary)]">{item?.summary || "未接入或近期无记录"}</p>
              <p className="mt-1 text-xs text-[var(--text-muted)]">
                {item ? `状态：${item.status === "ok" ? "正常" : "失败"} / 触发者：${item.actor || "system"}` : "当前没有可展示的最近记录"}
              </p>
            </div>
          ))}
        </div>
      </GlassCard>

      <div className="card-info">
        <p className="text-caption font-semibold mb-1">研究口径说明</p>
        {status?.notes?.map((note: string) => (
          <p key={note} className="text-body text-sm">• {note}</p>
        ))}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════
// 股票管理
// ══════════════════════════════════════════════════════════

function StocksTab({ showMsg }: { showMsg: (type: "ok" | "err", text: string) => void }) {
  const { t } = useTranslation();
  const [stocks, setStocks] = useState<AdminStockResponse>({ items: [], total: 0, page: 1, page_size: 50 });
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(1);
  const [market, setMarket] = useState("");
  const [editing, setEditing] = useState<AdminStockItem | null>(null);
  const [addingSymbol, setAddingSymbol] = useState("");
  const [adding, setAdding] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const fetchStocks = useCallback(() => {
    setLoading(true);
    getAdminStocks({ keyword, market, page, page_size: 50 }).then(setStocks).catch(() => {}).finally(() => setLoading(false));
  }, [keyword, market, page]);

  useEffect(() => { fetchStocks(); }, [fetchStocks]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const result = await adminSyncStocks(market || "ALL");
      showMsg("ok", result.message);
      fetchStocks();
    } catch (e: any) { showMsg("err", e.message || t("admin.syncFailed")); }
    setSyncing(false);
  };

  const handleAdd = async () => {
    if (!addingSymbol.trim()) return;
    setAdding(true);
    try {
      const result = await adminFetchStock(addingSymbol.trim());
      showMsg("ok", `${t("admin.added")} ${addingSymbol}: ${result.steps?.join(", ")}`);
      setAddingSymbol("");
      fetchStocks();
    } catch (e: any) { showMsg("err", e.message || t("admin.addFailed")); }
    setAdding(false);
  };

  const handleSave = async (stock: AdminStockItem) => {
    try {
      await updateAdminStock(stock.id, { name: stock.name, industry: stock.industry ?? undefined, status: stock.status });
      showMsg("ok", `${stock.symbol} ${t("admin.updated")}`);
      setEditing(null);
      fetchStocks();
    } catch (e: any) { showMsg("err", e.message || t("admin.updateFailed")); }
  };

  const handleDelete = async (stock: AdminStockItem) => {
    if (!confirm(t("admin.confirmDeleteStock", { symbol: stock.symbol, name: stock.name }))) return;
    try {
      await deleteAdminStock(stock.id);
      showMsg("ok", t("admin.deletedSymbol", { symbol: stock.symbol }));
      fetchStocks();
    } catch (e: any) { showMsg("err", e.message || t("admin.deleteFailed")); }
  };

  return (
    <div className="space-y-4">
      {/* 操作栏 */}
      <GlassCard>
        <div className="flex flex-wrap gap-3 items-center">
          <div className="flex-1 min-w-[200px]">
            <SearchBar value={keyword} onChange={setKeyword} placeholder={t("admin.stockSearch")} onSearch={() => { setPage(1); fetchStocks(); }} />
          </div>
          <select value={market} onChange={(e) => { setMarket(e.target.value); setPage(1); }} className="px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-dark-text">
            <option value="">{t("common.all")}</option>
            <option value="A_SHARE">{t("admin.aShare")}</option>
            <option value="HK">{t("admin.hk")}</option>
          </select>
          <button onClick={handleSync} disabled={syncing} className="flex items-center gap-1.5 px-4 py-2 bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 rounded-lg text-sm hover:bg-emerald-500/25 disabled:opacity-50 transition-colors">
            <Download className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
            {syncing ? t("admin.syncing") : t("admin.syncAll")}
          </button>
        </div>
        <div className="flex gap-2 mt-3">
          <input value={addingSymbol} onChange={(e) => setAddingSymbol(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleAdd()} placeholder={t("admin.stockPlaceholder")} className="flex-1 max-w-xs px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-dark-text placeholder:text-dark-muted" />
          <button onClick={handleAdd} disabled={adding || !addingSymbol.trim()} className="flex items-center gap-1.5 px-4 py-2 bg-primary-500/15 text-primary-400 border border-primary-500/30 rounded-lg text-sm hover:bg-primary-500/25 disabled:opacity-50 transition-colors">
            <Plus className="w-4 h-4" />
            {adding ? t("admin.fetching") : t("admin.addFetch")}
          </button>
        </div>
      </GlassCard>

      {/* 股票列表 */}
      <GlassCard>
        {loading ? <SkeletonCard /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  {[t("admin.stockCode"), t("admin.stockName"), t("admin.stockMarket"), t("admin.stockIndustry"), t("admin.stockStatus"), t("admin.stockActions")].map((h) => (
                    <th key={h} className="text-left py-3 px-3 text-dark-muted font-medium text-xs">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {stocks.items?.map((s: AdminStockItem) => (
                  <tr key={s.id} className="border-b border-white/[0.03] hover:bg-white/[0.03]">
                    <td className="py-2.5 px-3 font-mono text-xs text-primary-400">{s.symbol}</td>
                    <td className="py-2.5 px-3">
                      {editing?.id === s.id ? (
                        <input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} className="w-full px-2 py-1 bg-white/[0.06] border border-primary-500/30 rounded text-xs text-dark-text" />
                      ) : (
                        <span className="text-dark-text">{s.name}</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3"><Badge text={s.market === "A_SHARE" ? t("admin.aShare") : t("admin.hk")} /></td>
                    <td className="py-2.5 px-3 text-xs text-dark-muted">{s.industry || "-"}</td>
                    <td className="py-2.5 px-3">
                      {editing?.id === s.id ? (
                        <select value={editing.status} onChange={(e) => setEditing({ ...editing, status: e.target.value })} className="px-2 py-1 bg-white/[0.06] border border-primary-500/30 rounded text-xs text-dark-text">
                          <option value="ACTIVE">ACTIVE</option>
                          <option value="DELISTED">DELISTED</option>
                          <option value="SUSPENDED">SUSPENDED</option>
                        </select>
                      ) : (
                        <Badge text={s.status} className={s.status === "ACTIVE" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-red-500/10 text-red-400 border-red-500/20"} />
                      )}
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="flex gap-1">
                        {editing?.id === s.id ? (
                          <>
                            <button onClick={() => handleSave(editing)} className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"><Save className="w-3.5 h-3.5" /></button>
                            <button onClick={() => setEditing(null)} className="p-1.5 rounded-lg bg-white/[0.05] text-dark-muted hover:bg-white/[0.1] transition-colors"><X className="w-3.5 h-3.5" /></button>
                          </>
                        ) : (
                          <>
                            <button onClick={() => setEditing({ ...s })} className="p-1.5 rounded-lg bg-white/[0.05] text-dark-muted hover:bg-white/[0.1] transition-colors" title={t("admin.edit")}><Edit3 className="w-3.5 h-3.5" /></button>
                            <button onClick={() => handleDelete(s)} className="p-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors" title={t("admin.delete")}><Trash2 className="w-3.5 h-3.5" /></button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {(!stocks.items || stocks.items.length === 0) && (
                  <tr><td colSpan={6} className="py-12 text-center"><EmptyState message={t("admin.noStocks")} /></td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
        <Pagination page={page} total={stocks.total} pageSize={50} onChange={setPage} />
      </GlassCard>
    </div>
  );
}

// ══════════════════════════════════════════════════════════
// 评分管理
// ══════════════════════════════════════════════════════════

function ScoresTab({ showMsg }: { showMsg: (type: "ok" | "err", text: string) => void }) {
  const { t } = useTranslation();
  const [scores, setScores] = useState<AdminScoreResponse>({ items: [], total: 0, page: 1, page_size: 50 });
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState("");
  const [rating, setRating] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<AdminScoreItem | null>(null);

  const fetchScores = useCallback(() => {
    setLoading(true);
    getAdminScores({ keyword, rating, page, page_size: 50 }).then(setScores).catch(() => {}).finally(() => setLoading(false));
  }, [keyword, rating, page]);

  useEffect(() => { fetchScores(); }, [fetchScores]);

  const handleSave = async () => {
    if (!editing) return;
    try {
      const result = await updateAdminScore(editing.id, {
        quality_score: editing.quality_score,
        valuation_score: editing.valuation_score,
        growth_score: editing.growth_score,
        trend_score: editing.trend_score,
        risk_score: editing.risk_score,
        rating: editing.rating,
      });
      showMsg("ok", t("admin.scoreUpdated", { score: result.total_score }));
      setEditing(null);
      fetchScores();
    } catch (e: any) { showMsg("err", e.message || t("admin.updateFailed")); }
  };

  return (
    <div className="space-y-4">
      <GlassCard>
        <div className="flex flex-wrap gap-3 items-center">
          <div className="flex-1 min-w-[200px]">
            <SearchBar value={keyword} onChange={setKeyword} placeholder={t("admin.scoreSearch")} onSearch={() => { setPage(1); fetchScores(); }} />
          </div>
          <select value={rating} onChange={(e) => { setRating(e.target.value); setPage(1); }} className="px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-dark-text">
            <option value="">{t("admin.allRatings")}</option>
            {["BUY", "ADD", "WATCH", "REDUCE", "SELL"].map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
      </GlassCard>

      <GlassCard>
        {loading ? <SkeletonCard /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  {[t("admin.code"), t("admin.name"), t("admin.totalScore"), t("admin.quality"), t("admin.valuation"), t("admin.growth"), t("admin.trend"), t("admin.risk"), t("admin.rating"), t("admin.date"), t("admin.actions")].map((h) => (
                    <th key={h} className="text-left py-3 px-2 text-dark-muted font-medium text-xs whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {scores.items?.map((s: AdminScoreItem) => {
                  const isEditing = editing?.id === s.id;
                  return (
                    <tr key={s.id} className={`border-b border-white/[0.03] ${isEditing ? "bg-primary-500/[0.05]" : "hover:bg-white/[0.03]"}`}>
                      <td className="py-2.5 px-2 font-mono text-xs text-primary-400">{s.symbol}</td>
                      <td className="py-2.5 px-2 text-dark-text text-xs">{s.name}</td>
                      <td className="py-2.5 px-2 font-mono font-bold text-white">{isEditing ? "—" : s.total_score}</td>
                      {(["quality_score", "valuation_score", "growth_score", "trend_score", "risk_score"] as const).map((field) => (
                        <td key={field} className="py-2.5 px-2 font-mono text-xs">
                          {isEditing ? (
                            <input type="number" step="0.1" value={editing[field]} onChange={(e) => setEditing({ ...editing, [field]: parseFloat(e.target.value) || 0 })} className="w-16 px-1.5 py-1 bg-white/[0.06] border border-primary-500/30 rounded text-xs text-dark-text font-mono" />
                          ) : (
                            <span className="text-dark-text">{s[field]}</span>
                          )}
                        </td>
                      ))}
                      <td className="py-2.5 px-2">
                        {isEditing ? (
                          <select value={editing.rating} onChange={(e) => setEditing({ ...editing, rating: e.target.value })} className="px-1.5 py-1 bg-white/[0.06] border border-primary-500/30 rounded text-xs">
                            {["BUY", "ADD", "WATCH", "REDUCE", "SELL"].map((r) => <option key={r} value={r}>{r}</option>)}
                          </select>
                        ) : (
                          <Badge text={s.rating} className={ratingColors[s.rating]} />
                        )}
                      </td>
                      <td className="py-2.5 px-2 text-xs text-dark-muted">{s.score_date}</td>
                      <td className="py-2.5 px-2">
                        <div className="flex gap-1">
                          {isEditing ? (
                            <>
                              <button onClick={handleSave} className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"><Save className="w-3.5 h-3.5" /></button>
                              <button onClick={() => setEditing(null)} className="p-1.5 rounded-lg bg-white/[0.05] text-dark-muted hover:bg-white/[0.1] transition-colors"><X className="w-3.5 h-3.5" /></button>
                            </>
                          ) : (
                            <button onClick={() => setEditing({ ...s })} className="p-1.5 rounded-lg bg-white/[0.05] text-dark-muted hover:bg-white/[0.1] transition-colors" title={t("admin.editScore")}><Edit3 className="w-3.5 h-3.5" /></button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <Pagination page={page} total={scores.total} pageSize={50} onChange={setPage} />
      </GlassCard>
    </div>
  );
}

// ══════════════════════════════════════════════════════════
// 信号管理
// ══════════════════════════════════════════════════════════

function SignalsTab({ showMsg }: { showMsg: (type: "ok" | "err", text: string) => void }) {
  const { t } = useTranslation();
  const [signals, setSignals] = useState<AdminSignalResponse>({ items: [], total: 0, page: 1, page_size: 50 });
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState("");
  const [sigType, setSigType] = useState("");
  const [sigStatus, setSigStatus] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<AdminSignalItem | null>(null);

  const fetchSignals = useCallback(() => {
    setLoading(true);
    getAdminSignals({ keyword, signal_type: sigType, status: sigStatus, page, page_size: 50 }).then(setSignals).catch(() => {}).finally(() => setLoading(false));
  }, [keyword, sigType, sigStatus, page]);

  useEffect(() => { fetchSignals(); }, [fetchSignals]);

  const handleSave = async () => {
    if (!editing) return;
    try {
      await updateAdminSignal(editing.id, {
        signal_type: editing.signal_type,
        entry_price: editing.entry_price ?? undefined,
        target_price: editing.target_price ?? undefined,
        stop_loss_price: editing.stop_loss_price ?? undefined,
        status: editing.status,
      });
      showMsg("ok", t("admin.signalUpdated"));
      setEditing(null);
      fetchSignals();
    } catch (e: any) { showMsg("err", e.message || t("admin.updateFailed")); }
  };

  const handleExpire = async (sig: AdminSignalItem) => {
    try {
      await updateAdminSignal(sig.id, { status: "EXPIRED" });
      showMsg("ok", t("admin.signalVoided", { type: sig.signal_type }));
      fetchSignals();
    } catch (e: any) { showMsg("err", e.message || t("admin.operationFailed")); }
  };

  const handleDelete = async (sig: AdminSignalItem) => {
    if (!confirm(t("admin.confirmDeleteSignal", { symbol: sig.symbol, type: sig.signal_type }))) return;
    try {
      await deleteAdminSignal(sig.id);
      showMsg("ok", t("admin.signalDeleted"));
      fetchSignals();
    } catch (e: any) { showMsg("err", e.message || t("admin.deleteFailed")); }
  };

  return (
    <div className="space-y-4">
      <GlassCard>
        <div className="flex flex-wrap gap-3 items-center">
          <div className="flex-1 min-w-[200px]">
            <SearchBar value={keyword} onChange={setKeyword} placeholder={t("admin.signalSearch")} onSearch={() => { setPage(1); fetchSignals(); }} />
          </div>
          <select value={sigType} onChange={(e) => { setSigType(e.target.value); setPage(1); }} className="px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-dark-text">
            <option value="">{t("admin.allTypes")}</option>
            {["BUY", "ADD", "WATCH", "REDUCE", "SELL"].map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <select value={sigStatus} onChange={(e) => { setSigStatus(e.target.value); setPage(1); }} className="px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-dark-text">
            <option value="">{t("admin.allStatus")}</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="EXPIRED">EXPIRED</option>
            <option value="EXECUTED">EXECUTED</option>
          </select>
        </div>
      </GlassCard>

      <GlassCard>
        {loading ? <SkeletonCard /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  {[t("admin.code"), t("admin.name"), t("admin.signal"), t("admin.entryPrice"), t("admin.targetPrice"), t("admin.stopLoss"), t("admin.status"), t("admin.date"), t("admin.actions")].map((h) => (
                    <th key={h} className="text-left py-3 px-2 text-dark-muted font-medium text-xs whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {signals.items?.map((s: AdminSignalItem) => {
                  const isEditing = editing?.id === s.id;
                  return (
                    <tr key={s.id} className={`border-b border-white/[0.03] ${isEditing ? "bg-primary-500/[0.05]" : "hover:bg-white/[0.03]"}`}>
                      <td className="py-2.5 px-2 font-mono text-xs text-primary-400">{s.symbol}</td>
                      <td className="py-2.5 px-2 text-dark-text text-xs">{s.name}</td>
                      <td className="py-2.5 px-2">
                        {isEditing ? (
                          <select value={editing.signal_type} onChange={(e) => setEditing({ ...editing, signal_type: e.target.value })} className="px-1.5 py-1 bg-white/[0.06] border border-primary-500/30 rounded text-xs">
                            {["BUY", "ADD", "WATCH", "REDUCE", "SELL"].map((r) => <option key={r} value={r}>{r}</option>)}
                          </select>
                        ) : (
                          <Badge text={s.signal_type} className={signalColors[s.signal_type]} />
                        )}
                      </td>
                      {(["entry_price", "target_price", "stop_loss_price"] as const).map((field) => (
                        <td key={field} className="py-2.5 px-2 font-mono text-xs">
                          {isEditing ? (
                            <input type="number" step="0.01" value={editing[field] || ""} onChange={(e) => setEditing({ ...editing, [field]: parseFloat(e.target.value) || 0 })} className="w-20 px-1.5 py-1 bg-white/[0.06] border border-primary-500/30 rounded text-xs text-dark-text font-mono" />
                          ) : (
                            <span className="text-dark-text">{s[field] || "-"}</span>
                          )}
                        </td>
                      ))}
                      <td className="py-2.5 px-2">
                        {isEditing ? (
                          <select value={editing.status} onChange={(e) => setEditing({ ...editing, status: e.target.value })} className="px-1.5 py-1 bg-white/[0.06] border border-primary-500/30 rounded text-xs">
                            {["ACTIVE", "EXPIRED", "EXECUTED"].map((r) => <option key={r} value={r}>{r}</option>)}
                          </select>
                        ) : (
                          <Badge text={s.status} className={s.status === "ACTIVE" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-dark-muted/10 text-dark-muted border-white/10"} />
                        )}
                      </td>
                      <td className="py-2.5 px-2 text-xs text-dark-muted">{s.signal_date}</td>
                      <td className="py-2.5 px-2">
                        <div className="flex gap-1">
                          {isEditing ? (
                            <>
                              <button onClick={handleSave} className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"><Save className="w-3.5 h-3.5" /></button>
                              <button onClick={() => setEditing(null)} className="p-1.5 rounded-lg bg-white/[0.05] text-dark-muted hover:bg-white/[0.1] transition-colors"><X className="w-3.5 h-3.5" /></button>
                            </>
                          ) : (
                            <>
                              <button onClick={() => setEditing({ ...s })} className="p-1.5 rounded-lg bg-white/[0.05] text-dark-muted hover:bg-white/[0.1] transition-colors" title={t("admin.edit")}><Edit3 className="w-3.5 h-3.5" /></button>
                              {s.status === "ACTIVE" && <button onClick={() => handleExpire(s)} className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition-colors" title={t("admin.void")}><RefreshCw className="w-3.5 h-3.5" /></button>}
                              <button onClick={() => handleDelete(s)} className="p-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors" title={t("admin.delete")}><Trash2 className="w-3.5 h-3.5" /></button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <Pagination page={page} total={signals.total} pageSize={50} onChange={setPage} />
      </GlassCard>
    </div>
  );
}

// ══════════════════════════════════════════════════════════
// 用户管理
// ══════════════════════════════════════════════════════════

function UsersTab({ showMsg }: { showMsg: (type: "ok" | "err", text: string) => void }) {
  const { t } = useTranslation();
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState<"all" | "7" | "30" | "custom">("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [sortBy, setSortBy] = useState<"report_count" | "downloads" | "last_login_at">("report_count");
  const [rankings, setRankings] = useState<Record<string, any[]>>({});

  const fetchUsers = () => {
    setLoading(true);
    getAdminUsers().then(setUsers).catch((e: any) => showMsg("err", e.message || "用户运营统计加载失败")).finally(() => setLoading(false));
  };

  useEffect(() => { fetchUsers(); }, []);

  const filteredUsers = useMemo(() => {
    const now = Date.now();
    const lower = range === "7" ? now - 7 * 86400000 : range === "30" ? now - 30 * 86400000 : null;
    return [...users].filter((u) => {
      const t = u.created_at ? new Date(u.created_at).getTime() : 0;
      if (lower && t < lower) return false;
      if (range === "custom") {
        if (startDate && t < new Date(startDate).getTime()) return false;
        if (endDate && t > new Date(`${endDate}T23:59:59`).getTime()) return false;
      }
      return true;
    }).sort((a, b) => {
      if (sortBy === "downloads") return ((b.pdf_downloads || 0) + (b.png_downloads || 0)) - ((a.pdf_downloads || 0) + (a.png_downloads || 0));
      if (sortBy === "last_login_at") return new Date(b.last_login_at || 0).getTime() - new Date(a.last_login_at || 0).getTime();
      return (b.report_count || 0) - (a.report_count || 0);
    });
  }, [users, range, startDate, endDate, sortBy]);

  const handleRoleToggle = async (user: AdminUserItem) => {
    const newRole = user.role === "admin" ? "user" : "admin";
    if (!confirm(`${user.user_id || user.username}: ${user.role} → ${newRole}?`)) return;
    try {
      await updateAdminUser(user.id, { role: newRole });
      setUsers((prev) => prev.map((u) => u.id === user.id ? { ...u, role: newRole } : u));
      showMsg("ok", `${user.user_id || user.username} → ${newRole}`);
    } catch (e: any) { showMsg("err", e.message || t("admin.operationFailed")); }
  };

  const handleActiveToggle = async (user: AdminUserItem) => {
    try {
      if (user.is_active) {
        await disableAdminUser(user.id);
        setUsers((prev) => prev.map((u) => u.id === user.id ? { ...u, is_active: false } : u));
      } else {
        await updateAdminUser(user.id, { is_active: true });
        setUsers((prev) => prev.map((u) => u.id === user.id ? { ...u, is_active: true } : u));
      }
      showMsg("ok", `${user.username} ${user.is_active ? t("admin.userDisabled") : t("admin.userActive")}`);
    } catch (e: any) { showMsg("err", e.message || t("admin.operationFailed")); }
  };

  const handleResetPassword = async (user: AdminUserItem) => {
    const password = window.prompt(`为 ${user.user_id || user.username} 设置新密码（至少 8 位，不会在页面展示）`);
    if (!password) return;
    if (!confirm("确认重置该用户密码？该操作不会显示明文密码。")) return;
    try {
      await resetAdminUserPassword(user.id, password);
      showMsg("ok", "密码已重置");
    } catch (e: any) { showMsg("err", e.message || "重置密码失败"); }
  };

  const handleExport = async () => {
    try {
      await exportAdminUsersExcel();
      showMsg("ok", "Excel 导出已开始");
    } catch (e: any) { showMsg("err", e.message || "Excel 导出失败"); }
  };

  if (loading) return <SkeletonCard />;

  return (
    <GlassCard title="用户运营统计">
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="flex flex-wrap gap-2">
          {[["all", "全部"], ["7", "最近7天"], ["30", "最近30天"], ["custom", "自定义"]].map(([key, label]) => (
            <button key={key} onClick={() => setRange(key as any)} className={`rounded-lg px-3 py-2 text-xs ${range === key ? "bg-primary-500/15 text-primary-400 border border-primary-500/30" : "bg-white/[0.05] text-dark-muted"}`}>{label}</button>
          ))}
        </div>
        {range === "custom" && (
          <>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-2 text-xs text-dark-text" />
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-2 text-xs text-dark-text" />
          </>
        )}
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value as any)} className="rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-2 text-xs text-dark-text">
          <option value="report_count">按报告总数</option>
          <option value="downloads">按下载次数</option>
          <option value="last_login_at">按最近活跃</option>
        </select>
        <button onClick={handleExport} className="rounded-lg bg-emerald-500/15 px-3 py-2 text-xs font-medium text-emerald-400 border border-emerald-500/30">导出 Excel</button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1180px] text-sm">
          <thead>
            <tr className="border-b border-white/[0.06]">
              {["手机号", "用户ID", "角色", "状态", "注册时间", "最近登录", "报告总数", "报告类型分布", "HTML查看", "PNG下载", "PDF下载", "最近报告", "API配置", "操作"].map((h) => (
                <th key={h} className="text-left py-3 px-3 text-dark-muted font-medium text-xs">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredUsers.map((u) => (
              <tr key={u.id} className="border-b border-white/[0.03] hover:bg-white/[0.03]">
                <td className="py-3 px-3 font-mono text-xs text-dark-text">{u.phone || "-"}</td>
                <td className="py-3 px-3 font-medium text-dark-text">{u.user_id || u.username}</td>
                <td className="py-3 px-3">
                  <Badge text={u.role} className={u.role === "admin" ? "bg-purple-500/10 text-purple-400 border-purple-500/20" : "bg-blue-500/10 text-blue-400 border-blue-500/20"} />
                </td>
                <td className="py-3 px-3">
                  <Badge text={u.is_active ? t("admin.userActive") : t("admin.userDisabled")} className={u.is_active ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-red-500/10 text-red-400 border-red-500/20"} />
                </td>
                <td className="py-3 px-3 text-xs text-dark-muted">{u.created_at?.slice(0, 19)}</td>
                <td className="py-3 px-3 text-xs text-dark-muted">{u.last_login_at?.slice(0, 19) || "暂无记录"}</td>
                <td className="py-3 px-3 font-mono text-dark-text">{u.report_count || 0}</td>
                <td className="py-3 px-3 text-xs text-dark-muted">系统/个股统计待细分</td>
                <td className="py-3 px-3 font-mono text-dark-text">{u.html_views || 0}</td>
                <td className="py-3 px-3 font-mono text-dark-text">{u.png_downloads || 0}</td>
                <td className="py-3 px-3 font-mono text-dark-text">{u.pdf_downloads || 0}</td>
                <td className="py-3 px-3 text-xs text-dark-muted">{u.last_report_at || "暂无记录"}</td>
                <td className="py-3 px-3 font-mono text-dark-text">{u.api_config_count || 0}</td>
                <td className="py-3 px-3">
                  <div className="flex gap-1">
                    <button onClick={() => handleRoleToggle(u)} className="text-xs px-2 py-1 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-dark-muted hover:text-white transition-colors">
                      {u.role === "admin" ? t("admin.setAsUser") : t("admin.setAsAdmin")}
                    </button>
                    <button onClick={() => handleActiveToggle(u)} className={`text-xs px-2 py-1 rounded-lg transition-colors ${u.is_active ? "bg-red-500/10 text-red-400 hover:bg-red-500/20" : "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"}`}>
                      {u.is_active ? t("admin.userDisable") : t("admin.userEnable")}
                    </button>
                    <button onClick={() => handleResetPassword(u)} className="text-xs px-2 py-1 rounded-lg bg-amber-500/10 text-amber-400 hover:bg-amber-500/20">
                      重置密码
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassCard>
  );
}

// ══════════════════════════════════════════════════════════
// 数据库浏览
// ══════════════════════════════════════════════════════════

function DatabaseTab() {
  const { t } = useTranslation();
  const [tables, setTables] = useState<AdminTableInfo[]>([]);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [tableData, setTableData] = useState<AdminTableDataResponse | null>(null);
  const [tablePage, setTablePage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [tableLoading, setTableLoading] = useState(false);

  useEffect(() => {
    getAdminTables().then(setTables).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const handleSelectTable = async (tableName: string) => {
    setSelectedTable(tableName);
    setTablePage(1);
    setTableLoading(true);
    try { setTableData(await getAdminTableData(tableName, 1, 50)); } catch {}
    setTableLoading(false);
  };

  const handleTablePage = async (page: number) => {
    if (!selectedTable) return;
    setTablePage(page);
    setTableLoading(true);
    try { setTableData(await getAdminTableData(selectedTable, page, 50)); } catch {}
    setTableLoading(false);
  };

  if (loading) return <SkeletonCard />;

  return (
    <GlassCard title={t("admin.dbBrowser")}>
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-1 space-y-1 max-h-[500px] overflow-y-auto">
          {tables.map((tbl) => (
            <button key={tbl.name} onClick={() => handleSelectTable(tbl.name)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all flex items-center justify-between ${selectedTable === tbl.name ? "bg-primary-500/10 text-primary-400 border border-primary-500/20" : "text-dark-muted hover:bg-white/[0.05]"}`}>
              <span className="font-mono text-xs">{tbl.name}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.05]">{tbl.row_count}</span>
            </button>
          ))}
        </div>
        <div className="lg:col-span-3">
          {!selectedTable ? (
            <div className="flex items-center justify-center h-64"><EmptyState message={t("admin.selectTable")} /></div>
          ) : tableLoading ? <SkeletonCard /> : tableData ? (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-white font-mono">{selectedTable}</h3>
                <span className="text-xs text-dark-muted">{t("admin.totalItems", { total: tableData.total })}</span>
              </div>
              <div className="overflow-x-auto max-h-[400px]">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-white/[0.06] sticky top-0 bg-dark-card">
                      {tableData.columns.map((col: string) => (
                        <th key={col} className="text-left py-2 px-2 text-dark-muted font-medium whitespace-nowrap">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tableData.data.map((row: Record<string, unknown>, i: number) => (
                      <tr key={i} className="border-b border-white/[0.03] hover:bg-white/[0.03]">
                        {tableData.columns.map((col: string) => (
                          <td key={col} className="py-2 px-2 text-dark-text font-mono whitespace-nowrap max-w-[200px] truncate" title={String(row[col] ?? "")}>
                            {row[col] === null ? <span className="text-dark-muted italic">null</span> : String(row[col])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={tablePage} total={tableData.total} pageSize={50} onChange={handleTablePage} />
            </div>
          ) : null}
        </div>
      </div>
    </GlassCard>
  );
}

// ══════════════════════════════════════════════════════════
// API配置
// ══════════════════════════════════════════════════════════

function AuditTab({ showMsg }: { showMsg: (type: "ok" | "err", text: string) => void }) {
  const [logs, setLogs] = useState<any[]>([]);
  const [rankings, setRankings] = useState<Record<string, any[]>>({});
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ range: "all", user_keyword: "", action: "", status: "", start_date: "", end_date: "" });

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([getAuditLogs({ ...filters, page_size: 80 }), getAdminUsageRankings()])
      .then(([logData, rankData]) => {
        setLogs(logData.items || []);
        setRankings(rankData || {});
      })
      .catch((e: any) => showMsg("err", e.message || "审计日志加载失败"))
      .finally(() => setLoading(false));
  }, [filters, showMsg]);

  useEffect(() => { load(); }, [load]);

  const exportLogs = async () => {
    try {
      await exportAuditLogsExcel(filters);
      showMsg("ok", "审计日志 Excel 导出已开始");
    } catch (e: any) {
      showMsg("err", e.message || "审计日志导出失败");
    }
  };

  const rankGroups = [
    ["报告生成最多", rankings.top_reports || [], "report_total"],
    ["下载最多", rankings.top_downloads || [], "download_total"],
    ["回测最多", rankings.top_backtests || [], "backtest_total"],
    ["最近活跃", rankings.recent_active || [], "last_active_at"],
  ] as const;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {rankGroups.map(([title, rows, field]) => (
          <GlassCard key={title} title={title}>
            <div className="space-y-2">
              {rows.slice(0, 5).map((row: any) => (
                <div key={`${title}-${row.user_id}`} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-xs">
                  <span className="text-slate-700">{row.phone || row.username || row.user_id}</span>
                  <span className="font-mono text-slate-900">{row[field] || 0}</span>
                </div>
              ))}
              {rows.length === 0 && <div className="text-xs text-slate-500">暂无记录</div>}
            </div>
          </GlassCard>
        ))}
      </div>

      <GlassCard title="审计日志">
        <div className="mb-4 flex flex-wrap items-end gap-2">
          <select value={filters.range} onChange={(e) => setFilters({ ...filters, range: e.target.value })} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700">
            <option value="all">全部时间</option>
            <option value="7">最近7天</option>
            <option value="30">最近30天</option>
            <option value="custom">自定义</option>
          </select>
          {filters.range === "custom" && (
            <>
              <input type="date" value={filters.start_date} onChange={(e) => setFilters({ ...filters, start_date: e.target.value })} className="rounded-lg border border-slate-200 px-3 py-2 text-xs" />
              <input type="date" value={filters.end_date} onChange={(e) => setFilters({ ...filters, end_date: e.target.value })} className="rounded-lg border border-slate-200 px-3 py-2 text-xs" />
            </>
          )}
          <input value={filters.user_keyword} onChange={(e) => setFilters({ ...filters, user_keyword: e.target.value })} placeholder="用户ID/手机号" className="rounded-lg border border-slate-200 px-3 py-2 text-xs" />
          <select value={filters.action} onChange={(e) => setFilters({ ...filters, action: e.target.value })} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700">
            <option value="">全部操作</option>
            <option value="login_success">登录成功</option>
            <option value="login_failed">登录失败</option>
            <option value="report_generate">生成报告</option>
            <option value="report_png_download">下载PNG</option>
            <option value="report_pdf_download">下载PDF</option>
            <option value="backtest_run">运行回测</option>
            <option value="api_config_test">测试API配置</option>
            <option value="admin_reset_password">重置密码</option>
          </select>
          <select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700">
            <option value="">全部状态</option>
            <option value="success">成功</option>
            <option value="failed">失败</option>
          </select>
          <button onClick={load} className="rounded-lg bg-primary-500/15 px-3 py-2 text-xs font-medium text-primary-700">筛选</button>
          <button onClick={exportLogs} className="rounded-lg bg-emerald-500/15 px-3 py-2 text-xs font-medium text-emerald-700">导出 Excel</button>
        </div>
        {loading ? <SkeletonCard /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] text-sm">
              <thead><tr className="border-b border-slate-200">{["时间", "用户", "角色", "操作", "对象", "状态", "摘要"].map((h) => <th key={h} className="px-3 py-2 text-left text-xs font-medium text-slate-500">{h}</th>)}</tr></thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="border-b border-slate-100">
                    <td className="px-3 py-2 text-xs text-slate-500">{log.created_at || "-"}</td>
                    <td className="px-3 py-2 text-slate-800">{log.actor || "-"}</td>
                    <td className="px-3 py-2 text-slate-600">{log.role || "-"}</td>
                    <td className="px-3 py-2 text-slate-800">{log.action_label || log.action}</td>
                    <td className="px-3 py-2 text-xs text-slate-500">{log.target_type}:{log.target_id || "-"}</td>
                    <td className="px-3 py-2"><Badge text={log.status_label || (log.status === "failed" ? "失败" : "成功")} className={log.status === "failed" ? "bg-red-500/10 text-red-600 border-red-500/20" : "bg-emerald-500/10 text-emerald-600 border-emerald-500/20"} /></td>
                    <td className="px-3 py-2 text-xs text-slate-500">{log.message || "-"}</td>
                  </tr>
                ))}
                {logs.length === 0 && <tr><td colSpan={7} className="py-8 text-center text-sm text-slate-500">暂无记录</td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>
    </div>
  );
}

function ExportsTab({ showMsg }: { showMsg: (type: "ok" | "err", text: string) => void }) {
  const [exporting, setExporting] = useState<string | null>(null);

  const runExport = async (kind: "users" | "audit") => {
    setExporting(kind);
    try {
      if (kind === "users") {
        await exportAdminUsersExcel();
        showMsg("ok", "用户运营统计 Excel 已开始下载");
      } else {
        await exportAuditLogsExcel({});
        showMsg("ok", "审计日志 Excel 已开始下载");
      }
    } catch (e: any) {
      showMsg("err", e.message || "导出失败，请稍后重试");
    } finally {
      setExporting(null);
    }
  };

  return (
    <GlassCard title="导出管理">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm font-semibold text-slate-900">用户运营统计</p>
          <p className="mt-2 text-xs leading-5 text-slate-600">导出用户、报告、HTML 查看、PNG/PDF 下载、API 配置等运营字段。</p>
          <button onClick={() => runExport("users")} disabled={exporting === "users"} className="mt-4 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {exporting === "users" ? "导出中..." : "导出 Excel"}
          </button>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm font-semibold text-slate-900">审计日志</p>
          <p className="mt-2 text-xs leading-5 text-slate-600">导出操作时间、用户、角色、操作、对象、状态和摘要。</p>
          <button onClick={() => runExport("audit")} disabled={exporting === "audit"} className="mt-4 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {exporting === "audit" ? "导出中..." : "导出 Excel"}
          </button>
        </div>
      </div>
    </GlassCard>
  );
}

function ApiConfigTab({ showMsg }: { showMsg: (type: "ok" | "err", text: string) => void }) {
  const { t } = useTranslation();
  const [configs, setConfigs] = useState<ApiConfigItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<ApiConfigItem | null>(null);
  const [testing, setTesting] = useState<number | null>(null);

  const fetchConfigs = () => {
    setLoading(true);
    getApiConfigs().then(setConfigs).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => { fetchConfigs(); }, []);

  const handleSave = async (config: Partial<ApiConfigItem>) => {
    try {
      await saveApiConfig(config);
      showMsg("ok", t("admin.configSaved", { provider: config.provider || "未命名" }));
      fetchConfigs();
      setEditing(null);
    } catch (e: any) { showMsg("err", e.message || t("admin.saveFailed")); }
  };

  const handleDelete = async (id: number, provider: string) => {
    if (!confirm(t("admin.confirmDeleteConfig", { provider }))) return;
    try {
      await deleteApiConfig(id);
      showMsg("ok", t("admin.deleted"));
      fetchConfigs();
    } catch (e: any) { showMsg("err", e.message || t("admin.deleteFailed")); }
  };

  const handleTest = async (id: number) => {
    setTesting(id);
    try {
      const result = await testApiConfig(id);
      const prefix = result.status === "ok" ? "测试通过" : result.status === "format_valid" ? "格式有效" : result.status === "unsupported" ? "暂未支持自动测试" : "测试失败";
      showMsg(result.status === "failed" ? "err" : "ok", `${prefix}：${result.message}`);
    } catch (e: any) { showMsg("err", e.message || t("admin.testFailed")); }
    setTesting(null);
  };

  if (loading) return <SkeletonCard />;

  return (
    <div className="space-y-4">
      <div className="card-info">
        <p className="text-sm font-semibold">API 供应商配置</p>
        <p className="text-xs mt-1 opacity-80">管理员可在此维护数据源和模型服务供应商配置。密钥仅用于后端调用，前端始终脱敏展示。本系统不接券商交易接口，不提供自动下单能力。</p>
      </div>

      <GlassCard title={t("admin.apiProviderConfig")}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.06]">
                {[t("admin.provider"), t("admin.displayNameLabel"), t("admin.apiKey"), t("admin.status"), t("admin.dailyQuota"), t("admin.actions")].map((h) => (
                  <th key={h} className="text-left py-3 px-3 text-dark-muted font-medium text-xs">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {configs.map((c) => (
                <tr key={c.id} className="border-b border-white/[0.03] hover:bg-white/[0.03]">
                  <td className="py-2.5 px-3 font-mono text-xs text-primary-400">{c.provider}</td>
                  <td className="py-2.5 px-3 text-dark-text">{c.display_name}</td>
                  <td className="py-2.5 px-3 font-mono text-xs text-dark-muted">{c.api_key || t("admin.notConfigured")}</td>
                  <td className="py-2.5 px-3">
                    <Badge text={c.is_enabled ? t("admin.enable") : t("admin.disable")} className={c.is_enabled ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-red-500/10 text-red-400 border-red-500/20"} />
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono text-dark-text">{c.daily_limit}</td>
                  <td className="py-2.5 px-3">
                    <div className="flex gap-1">
                      <button onClick={() => setEditing(c)} className="text-xs px-2 py-1 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-dark-muted">{t("admin.edit")}</button>
                      <button onClick={() => handleTest(c.id)} disabled={testing === c.id} className="text-xs px-2 py-1 rounded-lg bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 disabled:opacity-50">
                        {testing === c.id ? "..." : t("admin.test")}
                      </button>
                      <button onClick={() => handleDelete(c.id, c.provider)} className="text-xs px-2 py-1 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20">{t("admin.delete")}</button>
                    </div>
                  </td>
                </tr>
              ))}
              {configs.length === 0 && <tr><td colSpan={6} className="py-8 text-center text-dark-muted">{t("admin.noData")}</td></tr>}
            </tbody>
          </table>
        </div>
      </GlassCard>

      <GlassCard title={editing ? `${t("admin.edit")} ${editing.provider}` : t("admin.addApiConfig")}>
        <ApiConfigForm initial={editing || undefined} onSave={handleSave} onCancel={() => setEditing(null)} />
      </GlassCard>
    </div>
  );
}

function ApiConfigForm({ initial, onSave, onCancel }: { initial?: ApiConfigItem; onSave: (c: Partial<ApiConfigItem>) => void; onCancel: () => void }) {
  const { t } = useTranslation();
  const [form, setForm] = useState({
    provider: initial?.provider || "",
    display_name: initial?.display_name || "",
    api_key: initial?.api_key || "",
    api_secret: initial?.api_secret || "",
    base_url: initial?.base_url || "",
    is_enabled: initial?.is_enabled ?? true,
    daily_limit: initial?.daily_limit ?? 1000,
    rate_limit: initial?.rate_limit ?? 10,
  });

  useEffect(() => {
    if (initial) {
      setForm({
        provider: initial.provider || "",
        display_name: initial.display_name || "",
        api_key: initial.api_key || "",
        api_secret: initial.api_secret || "",
        base_url: initial.base_url || "",
        is_enabled: initial.is_enabled ?? true,
        daily_limit: initial.daily_limit ?? 1000,
        rate_limit: initial.rate_limit ?? 10,
      });
    }
  }, [initial]);

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div>
        <label className="text-xs text-dark-muted">{t("admin.provider")}</label>
        <input value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })} placeholder="eastmoney" className="w-full mt-1" />
      </div>
      <div>
        <label className="text-xs text-dark-muted">{t("admin.displayNameLabel")}</label>
        <input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} placeholder={t("admin.eastmoney")} className="w-full mt-1" />
      </div>
      <div>
        <label className="text-xs text-dark-muted">{t("admin.apiKey")}</label>
        <input type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder={t("admin.leaveEmpty")} className="w-full mt-1" />
      </div>
      <div>
        <label className="text-xs text-dark-muted">{t("admin.baseUrl")}</label>
        <input value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://api.example.com" className="w-full mt-1" />
      </div>
      <div>
        <label className="text-xs text-dark-muted">{t("admin.dailyQuota")}</label>
        <input type="number" value={form.daily_limit} onChange={(e) => setForm({ ...form, daily_limit: parseInt(e.target.value) || 0 })} className="w-full mt-1" />
      </div>
      <div className="flex items-end gap-3 col-span-2">
        <label className="flex items-center gap-2 text-sm text-dark-text">
          <input type="checkbox" checked={form.is_enabled} onChange={(e) => setForm({ ...form, is_enabled: e.target.checked })} />
          {t("admin.enable")}
        </label>
        <button onClick={() => onSave(form)} className="px-4 py-2 bg-primary-500/15 text-primary-400 border border-primary-500/30 rounded-lg text-sm hover:bg-primary-500/25 transition-colors">{t("admin.save")}</button>
        {onCancel && <button onClick={onCancel} className="px-4 py-2 bg-white/[0.05] text-dark-muted border border-white/[0.08] rounded-lg text-sm hover:bg-white/[0.1] transition-colors">{t("admin.cancel")}</button>}
      </div>
    </div>
  );
}
