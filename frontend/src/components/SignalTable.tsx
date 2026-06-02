"use client";

import { useRouter } from "next/navigation";
import type { TopSignal } from "@/types";
import { signalTypeLabel, signalTypeClass, renderStars, formatPercent, getChangeColor, marketLabel } from "@/lib/utils";
import { useTranslation } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";
import EmptyState from "@/components/ui/EmptyState";

interface Props {
  signals: TopSignal[];
}

export default function SignalTable({ signals }: Props) {
  const router = useRouter();
  const { t } = useTranslation();

  if (!signals || signals.length === 0) {
    return (
      <GlassCard>
        <EmptyState message={t("common.noSignal")} />
      </GlassCard>
    );
  }

  return (
    <GlassCard>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/[0.06]">
              {[t("signals.code"), t("signals.name"), t("signals.market"), t("signals.signal"), t("signals.strength"), t("signals.position"), t("stock.signalLogic"), t("stock.riskWarning"), t("signals.latestPrice"), t("stocks.change"), t("common.viewReport")].map((h) => (
                <th key={h} className="text-left py-3 px-2 text-dark-muted font-medium text-xs">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {signals.map((s, i) => (
              <tr key={i} className="border-b border-white/[0.03] hover:bg-white/[0.03] transition-colors">
                <td className="py-3 px-2 font-mono text-xs text-dark-text">{s.symbol}</td>
                <td className="py-3 px-2 font-medium text-dark-text">{s.name}</td>
                <td className="py-3 px-2">
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    s.market === "A_SHARE" ? "bg-blue-500/10 text-blue-400" : "bg-purple-500/10 text-purple-400"
                  }`}>
                    {marketLabel(s.market)}
                  </span>
                </td>
                <td className="py-3 px-2">
                  <span className={signalTypeClass(s.signal_type)}>{signalTypeLabel(s.signal_type)}</span>
                </td>
                <td className="py-3 px-2 star text-sm">{renderStars(s.signal_strength)}</td>
                <td className="py-3 px-2 font-mono text-dark-text">{s.suggested_position > 0 ? `${s.suggested_position}%` : "-"}</td>
                <td className="py-3 px-2 text-xs text-dark-muted max-w-[200px] truncate">{s.logic}</td>
                <td className="py-3 px-2 text-xs text-amber-400 max-w-[150px] truncate">{s.risk?.join(", ")}</td>
                <td className="py-3 px-2 font-mono text-dark-text">{s.latest_close?.toFixed(2) || "-"}</td>
                <td className={`py-3 px-2 font-medium font-mono ${getChangeColor(s.change_pct)}`}>
                  {formatPercent(s.change_pct)}
                </td>
                <td className="py-3 px-2">
                  <button
                    onClick={() => router.push(`/stocks/${s.symbol}`)}
                    className="text-primary-400 hover:text-primary-300 text-xs font-medium transition-colors"
                  >
                    {t("common.viewReport")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassCard>
  );
}
