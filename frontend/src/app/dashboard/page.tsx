"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CalendarDays } from "lucide-react";

import PageShell from "@/components/layout/PageShell";
import MarketOverviewCard from "@/components/MarketOverviewCard";
import PortfolioChart from "@/components/PortfolioChart";
import RiskAlertCard from "@/components/RiskAlertCard";
import SignalDistributionChart from "@/components/SignalDistributionChart";
import SignalTable from "@/components/SignalTable";
import StockPoolCard from "@/components/StockPoolCard";
import StrategySummaryCard from "@/components/StrategySummaryCard";
import EmptyState from "@/components/ui/EmptyState";
import SimulatedDataNotice from "@/components/ui/SimulatedDataNotice";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { getDashboard, getDashboardAvailableDates, getRuntimeInfo } from "@/lib/api";
import { dataModeLabel, runtimeStatusLabel } from "@/lib/utils";
import type { DashboardData, RuntimeInfo } from "@/types";

const DASHBOARD_CACHE_KEY = "dashboard-last-success";

type CachedDashboard = {
  selectedDate: string | null;
  savedAt: string;
  payload: DashboardData;
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [availableDates, setAvailableDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usingFallbackCache, setUsingFallbackCache] = useState(false);

  const persistDashboard = (payload: DashboardData, date: string | null) => {
    if (typeof window === "undefined") return;
    const cached: CachedDashboard = {
      selectedDate: date,
      savedAt: new Date().toISOString(),
      payload,
    };
    window.sessionStorage.setItem(DASHBOARD_CACHE_KEY, JSON.stringify(cached));
  };

  const restoreDashboard = (): CachedDashboard | null => {
    if (typeof window === "undefined") return null;
    try {
      const raw = window.sessionStorage.getItem(DASHBOARD_CACHE_KEY);
      return raw ? (JSON.parse(raw) as CachedDashboard) : null;
    } catch {
      return null;
    }
  };

  const fetchData = async (mode: "initial" | "refresh" = "initial", dateOverride?: string | null) => {
    if (mode === "initial") setLoading(true);
    if (mode === "refresh") setRefreshing(true);
    setError(null);
    setUsingFallbackCache(false);

    try {
      const [runtimeValue, dateMeta] = await Promise.all([
        getRuntimeInfo().catch(() => null),
        getDashboardAvailableDates(),
      ]);

      if (runtimeValue) setRuntime(runtimeValue);
      const dates = dateMeta?.available_dates || [];
      setAvailableDates(dates);

      const effectiveDate = dateOverride ?? selectedDate ?? dateMeta?.latest_date ?? dates[0] ?? null;
      setSelectedDate(effectiveDate);

      const dashboardValue = await getDashboard(effectiveDate || undefined);
      setData(dashboardValue);
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
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void fetchData("initial");
  }, []);

  const totalSignals = useMemo(() => {
    if (!data?.signal_distribution) return 0;
    return Object.values(data.signal_distribution).reduce((sum, count) => sum + count, 0);
  }, [data]);

  if (loading && !data) {
    return (
      <PageShell title="今日投研驾驶舱" subtitle="正在加载投研驾驶舱数据">
        <div className="card-info">
          <p className="text-sm font-medium">正在加载投研驾驶舱数据，首次聚合可能需要约 30 秒。</p>
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
          <button onClick={() => void fetchData("refresh", selectedDate)} className="btn-primary mt-4 px-6 py-2 text-sm">
            重新加载
          </button>
        </div>
      </PageShell>
    );
  }

  const viewDate = data.meta?.view_date || selectedDate || data.meta?.signal_date || "待确认";
  const signalDate = data.meta?.signal_date || "待确认";
  const generatedAt = data.meta?.generated_at || "待确认";

  return (
    <PageShell
      title="今日投研驾驶舱"
      subtitle={data.strategy_summary.market_status_label || runtimeStatusLabel(data.strategy_summary.market_status)}
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
            </div>
          </div>
        </div>
      )}

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

      <SimulatedDataNotice
        title="研究口径说明"
        badges={[
          { label: `数据模式：${dataModeLabel(runtime?.data_mode || runtime?.provider_mode)}`, tone: runtime?.provider_mode === "mock" ? "simulated" : "live" },
          { label: `信号总数：${totalSignals}`, tone: "database" },
          { label: data.meta?.is_cached ? "演示缓存 / 非实时" : "实时聚合视图", tone: data.meta?.is_cached ? "simulated" : "database" },
        ]}
        lines={[
          "本页聚合数据库评分、信号、市场概览和研究组合结果，用于研究辅助，不构成投资建议。",
          "研究组合表现属于研究视图 / 非实盘 / 不代表未来收益。",
        ]}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <StrategySummaryCard summary={data.strategy_summary} />
        </div>
        <div className="lg:col-span-2 space-y-4">
          <MarketOverviewCard markets={data.market_summary} />
          <div className="card !p-4">
            <p className="text-caption mb-2 font-semibold">判断依据</p>
            <div className="space-y-1 text-sm text-[var(--text-body)]">
              {(data.strategy_summary.judgement_basis || []).slice(0, 3).map((item) => (
                <p key={item}>- {item}</p>
              ))}
            </div>
            <p className="mt-3 text-caption">风险提示：{data.strategy_summary.risk_warning}</p>
          </div>
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
