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
    { label: t("portfolio.totalAssets"), value: `¥${(portfolio.total_assets / 10000).toFixed(1)}万`, color: "text-white" },
    { label: t("portfolio.cashRatio"), value: `${portfolio.cash_ratio.toFixed(1)}%`, color: "text-dark-text" },
  ];

  return (
    <GlassCard title={t("dashboard.portfolio")}>
      <div className="grid grid-cols-2 gap-4">
        {metrics.map((m) => (
          <div key={m.label} className="p-3 bg-white/[0.03] rounded-xl border border-white/[0.06]">
            <p className="text-xs text-dark-muted">{m.label}</p>
            <p className={`text-lg font-bold mt-1 font-mono ${m.color}`}>{m.value}</p>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}
