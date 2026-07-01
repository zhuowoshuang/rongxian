"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, CalendarDays } from "lucide-react";

import PageShell from "@/components/layout/PageShell";
import MarketOverviewCard from "@/components/MarketOverviewCard";
import PortfolioChart from "@/components/PortfolioChart";
import RiskAlertCard from "@/components/RiskAlertCard";
import SignalDistributionChart from "@/components/SignalDistributionChart";
import SignalTable from "@/components/SignalTable";
import StockPoolCard from "@/components/StockPoolCard";
import StrategySummaryCard from "@/components/StrategySummaryCard";
import GlassCard from "@/components/ui/GlassCard";
import EmptyState from "@/components/ui/EmptyState";
import DataStatusBadge from "@/components/ui/DataStatusBadge";
import SimulatedDataNotice from "@/components/ui/SimulatedDataNotice";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { getDashboard, getDashboardAvailableDates, getRuntimeInfo, getScoreDiagnostics } from "@/lib/api";
import { dataModeLabel, displayTierLabel, displayTierTone, readinessLabel, runtimeStatusLabel, sanitizeDisplayText } from "@/lib/utils";
import { safeGetItem, safeSetItem } from "@/lib/safeStorage";
import type { DashboardData, RuntimeInfo, ScoreDiagnosticsResponse } from "@/types";

const DASHBOARD_CACHE_KEY = "dashboard-last-success";

type CachedDashboard = {
  selectedDate: string | null;
  savedAt: string;
  payload: DashboardData;
};

export default function DashboardPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [data, setData] = useState<DashboardData | null>(null);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [diagnostics, setDiagnostics] = useState<ScoreDiagnosticsResponse | null>(null);
  const [availableDates, setAvailableDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [includeDemo, setIncludeDemoState] = useState(searchParams.get("include_demo") !== "false");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [slowLoading, setSlowLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usingFallbackCache, setUsingFallbackCache] = useState(false);

  const setIncludeDemo = (next: boolean) => {
    setIncludeDemoState(next);
    const params = new URLSearchParams(searchParams.toString());
    if (next) params.set("include_demo", "true");
    else params.delete("include_demo");
    router.replace(`/dashboard${params.toString() ? `?${params.toString()}` : ""}`, { scroll: false });
  };

  useEffect(() => {
    setIncludeDemoState(searchParams.get("include_demo") === "true");
  }, [searchParams]);

  const persistDashboard = (payload: DashboardData, date: string | null) => {
    if (typeof window === "undefined") return;
    const cached: CachedDashboard = {
      selectedDate: date,
      savedAt: new Date().toISOString(),
      payload,
    };
    safeSetItem(window.sessionStorage, DASHBOARD_CACHE_KEY, JSON.stringify(cached));
  };

  const restoreDashboard = (): CachedDashboard | null => {
    if (typeof window === "undefined") return null;
    try {
      const raw = safeGetItem(window.sessionStorage, DASHBOARD_CACHE_KEY);
      return raw ? (JSON.parse(raw) as CachedDashboard) : null;
    } catch {
      return null;
    }
  };

  const fetchData = async (mode: "initial" | "refresh" = "initial", dateOverride?: string | null) => {
    if (mode === "initial") setLoading(true);
    if (mode === "refresh") setRefreshing(true);
    setError(null);
    setSlowLoading(false);
    setUsingFallbackCache(false);
    const slowTimer =
      typeof window !== "undefined"
        ? window.setTimeout(() => setSlowLoading(true), 5000)
        : null;

    try {
      const [runtimeValue, dateMeta] = await Promise.all([
        getRuntimeInfo().catch(() => null),
        getDashboardAvailableDates(includeDemo),
      ]);

      if (runtimeValue) setRuntime(runtimeValue);
      const dates = dateMeta?.available_dates || [];
      setAvailableDates(dates);

      const effectiveDate = dateOverride ?? selectedDate ?? dateMeta?.latest_date ?? dates[0] ?? null;
      setSelectedDate(effectiveDate);

      const [dashboardValue, diagnosticsValue] = await Promise.all([
        getDashboard(effectiveDate || undefined, includeDemo, mode === "refresh"),
        getScoreDiagnostics().catch(() => null),
      ]);
      setData(dashboardValue);
      setDiagnostics(diagnosticsValue);
      persistDashboard(dashboardValue, effectiveDate);
    } catch (err: unknown) {
      const fallback = restoreDashboard();
      if (fallback?.payload) {
        setData(fallback.payload);
        setSelectedDate(fallback.selectedDate);
        setUsingFallbackCache(true);
      }
      const message =
        err instanceof Error && err.message.trim()
          ? err.message
          : "投研驾驶舱加载失败，请稍后重试。";
      setError(message);
      try {
        const runtimeValue = await getRuntimeInfo();
        setRuntime(runtimeValue);
      } catch {
        // ignore secondary failure
      }
    } finally {
      if (slowTimer) window.clearTimeout(slowTimer);
      setLoading(false);
      setRefreshing(false);
      setSlowLoading(false);
    }
  };

  useEffect(() => {
    void fetchData("initial");
  }, [includeDemo]);

  const totalSignals = useMemo(() => {
    if (!data?.signal_distribution) return 0;
    return Object.values(data.signal_distribution).reduce((sum, count) => sum + count, 0);
  }, [data]);

  if (loading && !data) {
    return (
      <PageShell title="今日投研驾驶舱" subtitle="正在加载投研驾驶舱数据">
        <div className="card-info">
          <p className="text-sm font-medium">正在加载真实研究摘要，请稍候...</p>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">首次聚合可能需要约 30 秒，系统会优先返回最近一次成功结果。</p>
          {slowLoading ? (
            <p className="mt-2 text-xs text-[var(--text-secondary)]">
              数据聚合较慢，正在继续加载。你也可以先查看个股评分库或报告中心。
            </p>
          ) : null}
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </PageShell>
    );
  }

  if (!data) {
    return (
      <PageShell
        title="今日投研驾驶舱"
        subtitle="投研驾驶舱暂时不可用"
        onRefresh={() => void fetchData("refresh", selectedDate)}
        refreshing={refreshing}
      >
        <div className="card py-12 text-center">
          <EmptyState
            message="投研驾驶舱暂时不可用"
            description="请检查登录状态、后端服务和数据源状态后重试。"
          />
          {error ? <p className="mt-4 text-sm text-[var(--color-danger)]">{error}</p> : null}
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <button onClick={() => void fetchData("refresh", selectedDate)} className="btn-primary px-6 py-2 text-sm">
              重新加载
            </button>
            <button onClick={() => (window.location.href = "/stocks")} className="btn-secondary px-6 py-2 text-sm">
              查看个股评分库
            </button>
            <button onClick={() => (window.location.href = "/reports")} className="btn-secondary px-6 py-2 text-sm">
              查看报告中心
            </button>
          </div>
        </div>
      </PageShell>
    );
  }

  const viewDate = data.meta?.view_date || selectedDate || data.meta?.signal_date || "待确认";
  const signalDate = data.meta?.signal_date || "待确认";
  const generatedAt = data.meta?.generated_at || "待确认";
  const cacheMeta = data.meta?.cache;
  const showServerCacheNotice = Boolean(cacheMeta?.hit || cacheMeta?.fallback_used || cacheMeta?.stale);

  return (
    <PageShell
      title="今日投研驾驶舱"
      subtitle={
        data.meta?.formal_real_count === 0
          ? "样本观察中 / 暂不形成正式区间"
          : data.strategy_summary.market_status_label || runtimeStatusLabel(data.strategy_summary.market_status)
      }
      onRefresh={() => void fetchData("refresh", selectedDate)}
      refreshing={refreshing}
    >
      {(error || usingFallbackCache) && (
        <div className="card-warning">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold">
                {usingFallbackCache ? "当前展示的是最近一次成功加载的驾驶舱结果。" : "本次加载发生异常，页面已进入可控降级状态。"}
              </p>
              <p className="mt-1 text-xs opacity-80">{error || "服务恢复后可点击“重新加载”获取最新结果。"}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button onClick={() => void fetchData("refresh", selectedDate)} className="btn-primary px-4 py-2 text-xs">
                  重新加载
                </button>
                <button onClick={() => (window.location.href = "/stocks")} className="btn-secondary px-4 py-2 text-xs">
                  查看个股评分库
                </button>
                <button onClick={() => (window.location.href = "/reports")} className="btn-secondary px-4 py-2 text-xs">
                  查看报告中心
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showServerCacheNotice ? (
        <div className="card-info">
          <p className="text-sm font-medium">
            {cacheMeta?.fallback_used
              ? `当前显示最近一次成功聚合结果，生成时间：${cacheMeta.generated_at}`
              : `当前显示缓存聚合结果，生成时间：${cacheMeta?.generated_at || generatedAt}`}
          </p>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            该结果属于演示缓存 / 非实时视图，用于降低聚合等待时间，不代表逐秒刷新。
          </p>
        </div>
      ) : null}

      <div className="card flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-primary-500">智能投研工作台 / 研究辅助系统</p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-[var(--text-secondary)]">
            <span className="inline-flex items-center gap-1">
              <CalendarDays className="h-4 w-4" />
              当前查看日期：{viewDate}
            </span>
            <span>数据截至：{signalDate}</span>
            <span>聚合时间：{generatedAt}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setIncludeDemo(false)}
            className={`rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
              includeDemo ? "bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:bg-primary-50" : "bg-primary-500 text-white"
            }`}
          >
            仅看正式研究
          </button>
          <button
            onClick={() => setIncludeDemo(true)}
            className={`rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
              includeDemo ? "bg-primary-500 text-white" : "bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:bg-primary-50"
            }`}
          >
            包含演示样本
          </button>
          {availableDates.map((date) => (
            <button
              key={date}
              onClick={() => void fetchData("initial", date)}
              className={`rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
                date === viewDate ? "bg-primary-500 text-white" : "bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:bg-primary-50"
              }`}
            >
              {date}
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">投资人演示路径</h3>
        <div className="flex flex-wrap gap-2">
          <Link href="/stocks/002415" className="rounded-lg border border-[var(--border-default)] bg-white px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:border-primary-300 hover:text-primary-600 transition-colors">
            海康威视 (002415)
          </Link>
          <Link href="/stocks/600519" className="rounded-lg border border-[var(--border-default)] bg-white px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:border-primary-300 hover:text-primary-600 transition-colors">
            贵州茅台 (600519)
          </Link>
          <Link href="/reports" className="rounded-lg border border-[var(--border-default)] bg-white px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:border-primary-300 hover:text-primary-600 transition-colors">
            报告中心
          </Link>
          <Link href="/backtest" className="rounded-lg border border-[var(--border-default)] bg-white px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:border-primary-300 hover:text-primary-600 transition-colors">
            策略回测
          </Link>
        </div>
      </div>

      <SimulatedDataNotice
        title="研究口径说明"
        badges={[
          { label: `数据模式：${dataModeLabel(runtime?.data_mode || runtime?.provider_mode)}`, tone: runtime?.provider_mode === "mock" ? "simulated" : "live" },
          { label: `信号总数：${totalSignals}`, tone: "database" },
          { label: includeDemo ? "当前含演示样本" : "当前仅正式研究视图", tone: includeDemo ? "simulated" : "live" },
          { label: data.meta?.is_cached ? "演示缓存 / 非实时" : "实时聚合视图", tone: data.meta?.is_cached ? "simulated" : "database" },
        ]}
        lines={[
          "本页聚合数据库评分、信号、市场概览和研究组合结果，用于研究辅助，不构成投资建议。",
          "研究组合表现属于研究视图 / 非实盘 / 不代表未来收益。",
          data.meta?.warning || "若暂无真实评分，页面会自动降级为空状态，不会把演示评分当作正式研究结果展示。",
        ]}
      />

      {data.dashboard_sections && data.top_signals.length === 0 ? (
        <>
          <div className="card-info">
            <p className="text-sm font-medium">样本观察中 / 暂不形成正式区间 / 研究辅助非投资建议</p>
          </div>

          <GlassCard title="真实数据覆盖">
            <div className="flex flex-wrap gap-3 text-sm">
              {Object.entries(data.dashboard_sections.data_coverage).map(([key, value]) => (
                <span key={key} className="rounded-full border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-1.5">
                  <span className="font-medium">{key}</span>{" "}
                  <span className="font-mono font-bold text-[var(--text-primary)]">{typeof value === "number" ? value.toLocaleString() : String(value)}</span>
                </span>
              ))}
            </div>
          </GlassCard>

          {data.dashboard_sections.core_ready_samples.length > 0 ? (
            <GlassCard title="完整链路样本">
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {data.dashboard_sections.core_ready_samples.slice(0, 6).map((sample) => (
                  <Link
                    key={sample.symbol}
                    href={sample.detail_url || `/stocks/${sample.symbol}`}
                    className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4 transition-colors hover:border-primary-300"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-semibold text-[var(--text-primary)]">{sample.symbol}</span>
                      <DataStatusBadge label={readinessLabel(sample.readiness || "ready_full")} tone="live" />
                    </div>
                    <p className="mt-1 text-sm text-[var(--text-primary)]">{sample.name}</p>
                    <div className="mt-2 flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                      <span>评分 {sample.score}</span>
                      <span className="text-[var(--text-muted)]">|</span>
                      <span>{sample.signal_label || "观察中"}</span>
                    </div>
                  </Link>
                ))}
              </div>
            </GlassCard>
          ) : null}

          {data.dashboard_sections.risk_observation_samples.length > 0 ? (
            <GlassCard
              title="风险观察样本"
              action={
                <button
                  onClick={() => (window.location.href = "/signals?include_demo=false")}
                  className="rounded-lg border border-[var(--border-default)] bg-white px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:bg-slate-50"
                >
                  查看全部风险观察
                </button>
              }
            >
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {data.dashboard_sections.risk_observation_samples.slice(0, 6).map((sample) => (
                  <Link
                    key={sample.symbol}
                    href={`/stocks/${sample.symbol}`}
                    className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4 transition-colors hover:border-amber-200"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-semibold text-[var(--text-primary)]">{sample.symbol}</span>
                      <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700">
                        {sample.signal_type_label || "风险观察"}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-[var(--text-primary)]">{sample.name}</p>
                    <div className="mt-2 text-xs text-[var(--text-secondary)]">
                      <span>评分 {sample.score}</span>
                      {sample.primary_low_score_reason ? (
                        <>
                          <span className="text-[var(--text-muted)]"> | </span>
                          <span>{sample.primary_low_score_reason}</span>
                        </>
                      ) : null}
                    </div>
                  </Link>
                ))}
              </div>
            </GlassCard>
          ) : null}

          <GlassCard title="估值字段覆盖进度">
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm">
                  <span className="font-medium">PE 非空</span>
                  <span className="font-mono font-bold text-[var(--text-primary)]">
                    {data.dashboard_sections.valuation_gap.pe_non_null} / {data.dashboard_sections.valuation_gap.real_score_count}
                  </span>
                </div>
                <div className="mt-1.5 h-2 rounded-full bg-slate-200">
                  <div
                    className="h-2 rounded-full bg-primary-500 transition-all"
                    style={{
                      width: `${data.dashboard_sections.valuation_gap.real_score_count > 0 ? (data.dashboard_sections.valuation_gap.pe_non_null / data.dashboard_sections.valuation_gap.real_score_count) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm">
                  <span className="font-medium">PB 非空</span>
                  <span className="font-mono font-bold text-[var(--text-primary)]">
                    {data.dashboard_sections.valuation_gap.pb_non_null} / {data.dashboard_sections.valuation_gap.real_score_count}
                  </span>
                </div>
                <div className="mt-1.5 h-2 rounded-full bg-slate-200">
                  <div
                    className="h-2 rounded-full bg-primary-500 transition-all"
                    style={{
                      width: `${data.dashboard_sections.valuation_gap.real_score_count > 0 ? (data.dashboard_sections.valuation_gap.pb_non_null / data.dashboard_sections.valuation_gap.real_score_count) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm">
                  <span className="font-medium">真实评分</span>
                  <span className="font-mono font-bold text-[var(--text-primary)]">
                    {data.dashboard_sections.valuation_gap.real_score_count} / {data.dashboard_sections.valuation_gap.real_score_count}
                  </span>
                </div>
                <div className="mt-1.5 h-2 rounded-full bg-emerald-200">
                  <div className="h-2 w-full rounded-full bg-emerald-500" />
                </div>
              </div>
              <p className="text-xs text-[var(--text-secondary)]">{data.dashboard_sections.valuation_gap.valuation_gap_reason || "PE/PB 覆盖正在回填中。"}</p>
            </div>
          </GlassCard>

          <GlassCard title="报告与回测入口">
            <div className="flex flex-wrap items-center gap-3">
              {data.dashboard_sections.recent_reports.length > 0 ? (
                <div className="flex-1 min-w-[200px]">
                  <p className="mb-2 text-xs font-medium text-[var(--text-secondary)]">最近报告</p>
                  {data.dashboard_sections.recent_reports.slice(0, 3).map((r) => (
                    <Link key={r.id} href={`/reports/${r.id}`} className="block py-1 text-sm text-primary-600 hover:text-primary-700">
                      {r.title}
                    </Link>
                  ))}
                </div>
              ) : null}
              <button
                onClick={() => (window.location.href = "/reports")}
                className="rounded-lg border border-[var(--border-default)] bg-white px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-slate-50"
              >
                查看报告
              </button>
              <button
                onClick={() => (window.location.href = "/backtest")}
                className="rounded-lg border border-[var(--border-default)] bg-white px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-slate-50"
              >
                进入回测
              </button>
            </div>
            {data.dashboard_sections.backtest_entry ? (
              <p className="mt-3 text-xs text-[var(--text-secondary)]">
                回测样本 {data.dashboard_sections.backtest_entry.sample_count} 只 |{" "}
                交易日 {data.dashboard_sections.backtest_entry.trade_day_count} |{" "}
                行情 {data.dashboard_sections.backtest_entry.price_count} 条 |{" "}
                日期范围 {data.dashboard_sections.backtest_entry.date_range}
              </p>
            ) : null}
          </GlassCard>

          {data.dashboard_sections.demo_entry?.enabled ? (
            <div className="card-info">
              <p className="text-sm">{data.dashboard_sections.demo_entry.label || "演示数据已隔离，不影响正式研究视图。"}</p>
              <button
                onClick={() => setIncludeDemo(true)}
                className="mt-2 inline-flex rounded-lg border border-[var(--border-default)] bg-white px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-slate-50"
              >
                查看演示数据
              </button>
            </div>
          ) : null}
        </>
      ) : null}

      {diagnostics ? (
        <div className="card space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">真实评分观察说明</h2>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                {sanitizeDisplayText(diagnostics.summary.message, "当前首页结论来自真实评分与信号聚合，但整体以研究观察和风险识别为主。")}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <DataStatusBadge label={`真实样本 ${diagnostics.summary.real_count}`} tone="live" />
              <DataStatusBadge label={`演示样本 ${diagnostics.summary.demo_count}`} tone="simulated" />
              <DataStatusBadge label={`评分日期 ${diagnostics.summary.score_date || "待核验"}`} tone="database" />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(diagnostics.display_tier_distribution || {}).map(([key, value]) => (
              <DataStatusBadge key={key} label={`${displayTierLabel(key)} ${value}`} tone={displayTierTone(key)} />
            ))}
          </div>
          {(diagnostics.low_score_reasons || []).length > 0 ? (
            <div className="grid gap-3 md:grid-cols-3">
              {diagnostics.low_score_reasons.slice(0, 3).map((item) => (
                <div key={item.reason} className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4">
                  <p className="text-sm font-semibold text-[var(--text-primary)]">{sanitizeDisplayText(item.reason, "待核验")}</p>
                  <p className="mt-2 text-xs text-[var(--text-secondary)]">当前真实样本命中次数</p>
                  <p className="mt-1 font-mono text-xl font-bold text-[var(--text-primary)]">{item.count}</p>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {data.meta?.warning ? (
        <div className="card-warning">
          <p className="text-sm font-medium">{data.meta.warning}</p>
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-1">
          {data.meta?.formal_real_count === 0 ? (
            <GlassCard title="当前研究状态">
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                <p className="text-sm font-semibold text-amber-800">真实投研链路已接通，正式研究信号仍在数据质量爬坡中</p>
                <p className="mt-2 text-xs text-amber-700">
                  当前已有 {data.meta?.real_score_count || 0} 个真实评分样本和 {data.meta?.real_signal_count || 0} 条真实信号。由于估值、市值、财务覆盖仍在补齐，系统暂不把这些样本包装成正式重点信号，而是归入风险观察或数据质量受限状态。
                </p>
              </div>
              <div className="mt-4 space-y-2 text-sm text-[var(--text-secondary)]">
                <div className="flex justify-between">
                  <span>真实评分样本</span>
                  <span className="font-mono font-bold text-[var(--text-primary)]">{data.meta?.real_score_count || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span>正式研究样本</span>
                  <span className="font-mono font-bold text-[var(--text-primary)]">{data.meta?.formal_real_count || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span>风险观察样本</span>
                  <span className="font-mono font-bold text-[var(--text-primary)]">{data.meta?.real_observation_count || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span>数据质量受限</span>
                  <span className="font-mono font-bold text-[var(--text-primary)]">{data.meta?.data_quality_limited_count || 0}</span>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <button onClick={() => (window.location.href = "/signals")} className="btn-secondary px-3 py-1.5 text-xs">查看风险观察样本</button>
                <button onClick={() => (window.location.href = "/stocks/002415")} className="btn-secondary px-3 py-1.5 text-xs">海康威视</button>
                <button onClick={() => (window.location.href = "/stocks/600519")} className="btn-secondary px-3 py-1.5 text-xs">贵州茅台</button>
                <button onClick={() => setIncludeDemo(true)} className="btn-secondary px-3 py-1.5 text-xs">查看演示数据</button>
              </div>
            </GlassCard>
          ) : (
            <StrategySummaryCard summary={data.strategy_summary} />
          )}
        </div>
        <div className="lg:col-span-2 space-y-4">
          <MarketOverviewCard markets={data.market_summary} />
          {data.meta?.formal_real_count === 0 ? (
            <div className="card !p-4">
              <p className="text-caption mb-2 font-semibold">研究状态说明</p>
              <p className="text-sm text-[var(--text-body)]">
                当前真实评分样本均处于风险观察阶段，暂不形成正式研究区间。系统持续跟踪观察中，待数据覆盖度提升后自动进入正式研究流程。
              </p>
              <p className="mt-2 text-xs text-[var(--text-secondary)]">风险提示：本系统仅用于研究和辅助分析，不构成任何投资建议。</p>
            </div>
          ) : (
            <div className="card !p-4">
              <p className="text-caption mb-2 font-semibold">判断依据</p>
              <div className="space-y-1 text-sm text-[var(--text-body)]">
                {(data.strategy_summary.judgement_basis || []).slice(0, 3).map((item) => (
                  <p key={item}>- {item}</p>
                ))}
              </div>
              <p className="mt-3 text-caption">风险提示：{data.strategy_summary.risk_warning}</p>
            </div>
          )}
        </div>
      </div>

      <div id="signals">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-h2 flex items-center gap-2">
            <span className="h-5 w-1 rounded-full bg-primary-500" />
            今日重点信号
          </h2>
          <span className="text-caption">{totalSignals} 条</span>
        </div>
        <SignalTable signals={data.top_signals} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <SignalDistributionChart distribution={data.signal_distribution} />
          <p className="mt-1 text-caption">信号分布反映当前研究优先级结构，不代表自动交易指令。</p>
        </div>
        <div id="portfolio">
          <PortfolioChart portfolio={data.portfolio_summary} />
          <p className="mt-1 text-caption">研究组合表现属于研究视图 / 非实盘 / 不代表未来收益。</p>
        </div>
      </div>

      <div id="pools">
        <h2 className="text-h2 mb-3 flex items-center gap-2">
          <span className="h-5 w-1 rounded-full bg-primary-500" />
          策略股票池
        </h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
          <StockPoolCard title="优质基本面池" type="quality" items={data.stock_pools?.quality || []} />
          <StockPoolCard title="低估值池" type="undervalued" items={data.stock_pools?.undervalued || []} />
          <StockPoolCard title="趋势确认池" type="trend" items={data.stock_pools?.trend || []} />
          <StockPoolCard title="风险预警池" type="risk" items={data.stock_pools?.risk || []} />
        </div>
      </div>

      {data.risk_alerts?.length > 0 ? <RiskAlertCard alerts={data.risk_alerts} /> : null}

      <div className="disclaimer">本系统仅用于研究和辅助分析，不构成任何投资建议。</div>
    </PageShell>
  );
}
