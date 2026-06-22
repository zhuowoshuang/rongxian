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

  const statusConfig: Record<string, { color: string; bg: string; icon: React.ReactNode; labelKey: string }> = {
    bullish: { color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20", icon: <TrendingUp className="w-6 h-6" />, labelKey: "strategy.bullish" },
    mildly_bullish: { color: "text-blue-400", bg: "bg-blue-500/10 border-blue-500/20", icon: <TrendingUp className="w-6 h-6" />, labelKey: "strategy.mildlyBullish" },
    neutral: { color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/20", icon: <Minus className="w-6 h-6" />, labelKey: "strategy.neutral" },
    mildly_bearish: { color: "text-orange-400", bg: "bg-orange-500/10 border-orange-500/20", icon: <TrendingDown className="w-6 h-6" />, labelKey: "strategy.mildlyBearish" },
    bearish: { color: "text-red-400", bg: "bg-red-500/10 border-red-500/20", icon: <TrendingDown className="w-6 h-6" />, labelKey: "strategy.bearish" },
  };

  const config = statusConfig[summary.market_status] || statusConfig.neutral;

  return (
    <GlassCard title={t("dashboard.strategy")} className="h-full flex flex-col">
      <div className={`p-4 rounded-xl border mb-5 ${config.bg}`}>
        <div className="flex items-center justify-between">
          <span className="text-xs text-dark-muted">{t("strategy.marketStatus")}</span>
          <span className={config.color}>{config.icon}</span>
        </div>
        <p className={`text-2xl font-bold mt-1 ${config.color}`}>{t(config.labelKey)}</p>
      </div>

      <div className="mb-5">
        <span className="text-xs text-dark-muted">{t("strategy.suggestedPosition")}</span>
        <p className="text-3xl font-bold text-primary-400 mt-1 font-mono">{summary.suggested_position}</p>
      </div>

      <div className="mb-5 flex-1">
        <span className="text-xs text-dark-muted">{t("strategy.coreStrategy")}</span>
        <p className="text-sm text-dark-text mt-1 leading-relaxed">{summary.core_strategy}</p>
      </div>

      <div className="p-3 bg-amber-500/10 rounded-xl border border-amber-500/20">
        <span className="text-xs text-amber-400 font-medium flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5" /> {t("strategy.riskWarning")}
        </span>
        <p className="text-xs text-amber-400/80 mt-1">{summary.risk_warning}</p>
      </div>
    </GlassCard>
  );
}
