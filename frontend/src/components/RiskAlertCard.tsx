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
      <h3 className="text-sm font-semibold text-dark-muted mb-4 flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 text-amber-400" /> {t("risk.title")}
      </h3>
      <div className="space-y-3">
        {alerts.map((alert, i) => (
          <div key={i} className="flex items-start gap-3 p-3 bg-amber-500/5 rounded-xl border border-amber-500/10">
            <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${alert.level === "high" ? "bg-red-400" : "bg-amber-400"}`} />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm text-dark-text">{alert.name}</span>
                <span className="text-xs text-dark-muted font-mono">{alert.symbol}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                  alert.market === "A_SHARE" ? "bg-blue-500/10 text-blue-400" : "bg-purple-500/10 text-purple-400"
                }`}>
                  {marketLabel(alert.market)}
                </span>
              </div>
              <p className="text-xs text-amber-400 mt-1">{alert.message}</p>
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}
