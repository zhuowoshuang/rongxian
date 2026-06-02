"use client";

import { useEffect, useState } from "react";
import { getDashboard } from "@/lib/api";
import type { DashboardData } from "@/types";
import { useTranslation } from "@/lib/i18n";
import TopSearch from "@/components/TopSearch";
import StrategySummaryCard from "@/components/StrategySummaryCard";
import MarketOverviewCard from "@/components/MarketOverviewCard";
import SignalTable from "@/components/SignalTable";
import SignalDistributionChart from "@/components/SignalDistributionChart";
import PortfolioChart from "@/components/PortfolioChart";
import StockPoolCard from "@/components/StockPoolCard";
import RiskAlertCard from "@/components/RiskAlertCard";
import { SkeletonCard } from "@/components/ui/Skeleton";
import EmptyState from "@/components/ui/EmptyState";

export default function DashboardPage() {
  const { t } = useTranslation();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDashboard()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen p-6 space-y-6">
        <div className="max-w-[1400px] mx-auto">
          <div className="h-12 bg-white/[0.03] rounded-xl animate-pulse" />
        </div>
        <div className="max-w-[1400px] mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
          <SkeletonCard />
          <div className="lg:col-span-2"><SkeletonCard /></div>
        </div>
        <div className="max-w-[1400px] mx-auto grid grid-cols-2 lg:grid-cols-4 gap-4">
          <SkeletonCard /><SkeletonCard /><SkeletonCard /><SkeletonCard />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center max-w-md">
          <EmptyState message={error || t("common.error")} />
          <div className="mt-4 p-4 card text-xs text-dark-muted text-left space-y-1">
            <p>{t("common.startSteps")}</p>
            <p>1. cd backend</p>
            <p>2. python -m app.seed</p>
            <p>3. uvicorn app.main:app --reload --port 8000</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 space-y-6">
      <div className="max-w-[1400px] mx-auto">
        <TopSearch />
      </div>

      <div className="max-w-[1400px] mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <StrategySummaryCard summary={data.strategy_summary} />
        </div>
        <div className="lg:col-span-2">
          <MarketOverviewCard markets={data.market_summary} />
        </div>
      </div>

      <div className="max-w-[1400px] mx-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <span className="w-1 h-5 bg-primary-500 rounded-full" />
            {t("dashboard.todaySignals")}
          </h2>
          <span className="text-xs text-dark-muted">
            {t("dashboard.signalCount", { count: Object.values(data.signal_distribution).reduce((a, b) => a + b, 0) })}
          </span>
        </div>
        <SignalTable signals={data.top_signals} />
      </div>

      <div className="max-w-[1400px] mx-auto grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SignalDistributionChart distribution={data.signal_distribution} />
        <PortfolioChart portfolio={data.portfolio_summary} />
      </div>

      <div className="max-w-[1400px] mx-auto">
        <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
          <span className="w-1 h-5 bg-primary-500 rounded-full" />
          {t("dashboard.stockPool")}
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StockPoolCard title={t("pool.quality")} type="quality" items={data.stock_pools?.quality || []} />
          <StockPoolCard title={t("pool.undervalued")} type="undervalued" items={data.stock_pools?.undervalued || []} />
          <StockPoolCard title={t("pool.trend")} type="trend" items={data.stock_pools?.trend || []} />
          <StockPoolCard title={t("pool.risk")} type="risk" items={data.stock_pools?.risk || []} />
        </div>
      </div>

      {data.risk_alerts && data.risk_alerts.length > 0 && (
        <div className="max-w-[1400px] mx-auto">
          <RiskAlertCard alerts={data.risk_alerts} />
        </div>
      )}

      <div className="disclaimer max-w-[1400px] mx-auto">
        {t("app.disclaimer")}
      </div>
    </div>
  );
}
