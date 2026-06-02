"use client";

import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer, Tooltip } from "recharts";
import { useTranslation } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";

interface Props {
  score: {
    total: number;
    quality: number;
    valuation: number;
    growth: number;
    trend: number;
    risk: number;
    rating: string;
    reason: string;
    date: string;
  };
}

export default function ScoreBreakdown({ score }: Props) {
  const { t } = useTranslation();

  const radarData = [
    { subject: t("score.quality"), value: score.quality, fullMark: 30 },
    { subject: t("score.valuation"), value: score.valuation, fullMark: 20 },
    { subject: t("score.growth"), value: score.growth, fullMark: 20 },
    { subject: t("score.trend"), value: score.trend, fullMark: 20 },
    { subject: t("score.risk"), value: score.risk, fullMark: 10 },
  ];

  const categories = [
    { label: t("score.qualityLabel"), key: "quality", max: 30, color: "bg-emerald-500" },
    { label: t("score.valuationLabel"), key: "valuation", max: 20, color: "bg-blue-500" },
    { label: t("score.growthLabel"), key: "growth", max: 20, color: "bg-purple-500" },
    { label: t("score.trendLabel"), key: "trend", max: 20, color: "bg-amber-500" },
    { label: t("score.riskLabel"), key: "risk", max: 10, color: "bg-red-500" },
  ];

  return (
    <GlassCard title={t("score.total", { score: score.total?.toFixed(0) || "0" })}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData}>
              <PolarGrid stroke="#1E293B" />
              <PolarAngleAxis dataKey="subject" tick={{ fontSize: 12, fill: "#94A3B8" }} />
              <PolarRadiusAxis angle={30} domain={[0, 30]} tick={{ fontSize: 10, fill: "#94A3B8" }} />
              <Radar name={t("stock.score")} dataKey="value" stroke="#6366f1" fill="#6366f1" fillOpacity={0.3} />
              <Tooltip
                contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "0.75rem", color: "#E2E8F0" }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div className="space-y-4">
          {categories.map((cat) => {
            const val = score[cat.key as keyof typeof score] as number;
            const pct = (val / cat.max) * 100;
            return (
              <div key={cat.key}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-dark-text">{cat.label}</span>
                  <span className="text-sm font-bold text-white font-mono">{val?.toFixed(1)}/{cat.max}</span>
                </div>
                <div className="w-full bg-white/[0.06] rounded-full h-2.5">
                  <div
                    className={`h-2.5 rounded-full transition-all ${cat.color}`}
                    style={{ width: `${Math.min(pct, 100)}%` }}
                  />
                </div>
              </div>
            );
          })}

          {score.reason && (
            <div className="mt-4 p-3 bg-white/[0.03] rounded-xl border border-white/[0.06]">
              <p className="text-xs text-dark-muted mb-1">{t("score.reason")}</p>
              <p className="text-sm text-dark-text">{score.reason}</p>
            </div>
          )}
        </div>
      </div>
    </GlassCard>
  );
}
