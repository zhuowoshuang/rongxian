"use client";

import type { PortfolioSummary } from "@/types";
import { formatPercent, getChangeColor } from "@/lib/utils";
import { useTranslation } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";

interface Props {
  portfolio: PortfolioSummary;
}

export default function PortfolioChart({ portfolio }: Props) {
  const { t } = useTranslation();

  const metrics = [
    { label: t("portfolio.monthlyReturn"), value: formatPercent(portfolio.monthly_return), color: getChangeColor(portfolio.monthly_return) },
    { label: t("portfolio.excessReturn"), value: formatPercent(portfolio.excess_return), color: getChangeColor(portfolio.excess_return) },
    { label: t("portfolio.maxDrawdown"), value: formatPercent(portfolio.max_drawdown), color: "text-red-400" },
    { label: t("portfolio.sharpeRatio"), value: portfolio.sharpe_ratio.toFixed(2), color: portfolio.sharpe_ratio >= 1 ? "text-emerald-400" : "text-amber-400" },
    { label: t("portfolio.totalAssets"), value: `${(portfolio.total_assets / 10000).toFixed(1)} 万`, color: "text-white" },
    { label: t("portfolio.cashRatio"), value: `${portfolio.cash_ratio.toFixed(1)}%`, color: "text-dark-text" },
  ];

  return (
    <GlassCard title={`${t("dashboard.portfolio")}（研究视图）`}>
      <div className="grid grid-cols-2 gap-4">
        {metrics.map((metric) => (
          <div key={metric.label} className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-3">
            <p className="text-xs text-dark-muted">{metric.label}</p>
            <p className={`mt-1 font-mono text-lg font-bold ${metric.color}`}>{metric.value}</p>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}
