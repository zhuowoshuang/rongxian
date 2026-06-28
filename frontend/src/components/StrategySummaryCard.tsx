"use client";

import type { StrategySummary } from "@/types";
import { useTranslation } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";
import { TrendingUp, TrendingDown, Minus, AlertTriangle } from "lucide-react";

interface Props {
  summary: StrategySummary;
}

export default function StrategySummaryCard({ summary }: Props) {
  const { t } = useTranslation();

  const statusConfig: Record<string, { color: string; bg: string; border: string; icon: React.ReactNode; labelKey: string }> = {
    bullish: { color: "text-[var(--color-success)]", bg: "bg-[var(--color-success-bg)]", border: "border-[#A7F3D0]", icon: <TrendingUp className="w-6 h-6" />, labelKey: "strategy.bullish" },
    mildly_bullish: { color: "text-blue-700", bg: "bg-blue-50", border: "border-blue-200", icon: <TrendingUp className="w-6 h-6" />, labelKey: "strategy.mildlyBullish" },
    neutral: { color: "text-[var(--color-warning)]", bg: "bg-[var(--color-warning-bg)]", border: "border-[#FDE68A]", icon: <Minus className="w-6 h-6" />, labelKey: "strategy.neutral" },
    mildly_bearish: { color: "text-orange-700", bg: "bg-orange-50", border: "border-orange-200", icon: <TrendingDown className="w-6 h-6" />, labelKey: "strategy.mildlyBearish" },
    bearish: { color: "text-[var(--color-danger)]", bg: "bg-[var(--color-danger-bg)]", border: "border-[#FECACA]", icon: <TrendingDown className="w-6 h-6" />, labelKey: "strategy.bearish" },
  };

  const config = statusConfig[summary.market_status] || statusConfig.neutral;

  return (
    <GlassCard title={t("dashboard.strategy")} className="h-full flex flex-col">
      <div className={`p-4 rounded-xl border mb-5 ${config.bg} ${config.border}`}>
        <div className="flex items-center justify-between">
          <span className="text-caption">{t("strategy.marketStatus")}</span>
          <span className={config.color}>{config.icon}</span>
        </div>
        <p className={`text-2xl font-bold mt-1 ${config.color}`}>{t(config.labelKey)}</p>
      </div>

      <div className="mb-5">
        <span className="text-caption">{t("strategy.suggestedPosition")}</span>
        <p className="text-3xl font-bold text-primary-600 mt-1 font-mono">{summary.suggested_position}</p>
      </div>

      <div className="mb-5 flex-1">
        <span className="text-caption">{t("strategy.coreStrategy")}</span>
        <p className="text-body mt-1 leading-relaxed">{summary.core_strategy}</p>
      </div>

      <div className="card-warning">
        <span className="text-xs font-semibold flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5" /> {t("strategy.riskWarning")}
        </span>
        <p className="text-xs mt-1 opacity-80">{summary.risk_warning}</p>
      </div>
    </GlassCard>
  );
}
