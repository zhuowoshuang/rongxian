"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from "recharts";
import type { SignalDistribution } from "@/types";
import { useTranslation } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";

interface Props {
  distribution: SignalDistribution;
}

const COLORS = {
  BUY: "#10B981",
  ADD: "#3B82F6",
  WATCH: "#F59E0B",
  REDUCE: "#F97316",
  SELL: "#EF4444",
};

export default function SignalDistributionChart({ distribution }: Props) {
  const { t } = useTranslation();

  const LABELS: Record<string, string> = {
    BUY: t("signal.BUY"),
    ADD: t("signal.ADD"),
    WATCH: t("signal.WATCH"),
    REDUCE: t("signal.REDUCE"),
    SELL: t("signal.SELL"),
  };

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload?.length) {
      return (
        <div className="bg-dark-card border border-white/10 rounded-lg px-3 py-2 shadow-xl backdrop-blur-xl">
          <p className="text-sm text-white">{payload[0].name}: <span className="font-bold">{payload[0].value}</span></p>
        </div>
      );
    }
    return null;
  };

  const data = Object.entries(distribution)
    .filter(([_, count]) => count > 0)
    .map(([key, count]) => ({
      name: LABELS[key] || key,
      value: count,
      color: COLORS[key as keyof typeof COLORS] || "#94A3B8",
    }));

  const total = Object.values(distribution).reduce((a, b) => a + b, 0);

  return (
    <GlassCard title={t("dashboard.signalDistribution")}>
      {total === 0 ? (
        <div className="flex items-center justify-center h-48 text-dark-muted">{t("common.noSignal")}</div>
      ) : (
        <div className="flex items-center gap-6">
          <div className="w-48 h-48">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={75}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {data.map((entry, index) => (
                    <Cell key={index} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex-1 space-y-3">
            {Object.entries(distribution).map(([key, count]) => (
              <div key={key} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[key as keyof typeof COLORS] }} />
                  <span className="text-sm text-dark-muted">{LABELS[key]}</span>
                </div>
                <span className="font-bold text-sm text-white font-mono">{count}</span>
              </div>
            ))}
            <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between">
              <span className="text-sm text-dark-muted">{t("common.total")}</span>
              <span className="font-bold text-white font-mono">{total}</span>
            </div>
          </div>
        </div>
      )}
    </GlassCard>
  );
}
