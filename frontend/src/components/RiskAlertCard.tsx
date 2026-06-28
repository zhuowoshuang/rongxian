"use client";

import type { RiskAlert } from "@/types";
import { marketLabel } from "@/lib/utils";
import { useTranslation } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";
import { AlertTriangle } from "lucide-react";

interface Props {
  alerts: RiskAlert[];
}

export default function RiskAlertCard({ alerts }: Props) {
  const { t } = useTranslation();
  if (!alerts || alerts.length === 0) return null;

  return (
    <GlassCard className="border-l-4 border-l-amber-500">
      <h3 className="text-sm font-semibold text-[var(--text-muted)] mb-4 flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 text-amber-500" /> {t("risk.title")}
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {alerts.slice(0, 15).map((alert, i) => (
          <div key={i} className="flex items-start gap-3 p-3 bg-amber-50 rounded-xl border border-amber-200">
            <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${alert.level === "high" ? "bg-red-500" : "bg-amber-500"}`} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium text-sm text-[var(--text-primary)]">{alert.name}</span>
                <span className="text-xs text-[var(--text-muted)] font-mono">{alert.symbol}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                  alert.market === "A_SHARE" ? "bg-blue-50 text-blue-700" : "bg-purple-50 text-purple-700"
                }`}>
                  {marketLabel(alert.market)}
                </span>
              </div>
              <p className="text-xs text-amber-700 mt-1">{alert.message}</p>
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}
