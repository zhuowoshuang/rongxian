"use client";

import type { MarketIndex } from "@/types";
import { formatPercent, getChangeColor } from "@/lib/utils";
import { useTranslation } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";

interface Props {
  markets: MarketIndex[];
}

export default function MarketOverviewCard({ markets }: Props) {
  const { t } = useTranslation();
  const aShare = markets.filter((m) => m.code.includes(".SH") || m.code.includes(".SZ") || m.code === "000001.SH");
  const hk = markets.filter((m) => m.code === "HSI" || m.code === "HSTECH" || (!m.code.includes(".SH") && !m.code.includes(".SZ")));

  const IndexCard = ({ m }: { m: MarketIndex }) => (
    <div className="p-3 bg-white/[0.03] rounded-xl border border-white/[0.06] hover:bg-white/[0.05] transition-colors">
      <p className="text-xs text-dark-muted">{m.name}</p>
      <p className="text-base font-bold text-white mt-1 font-mono">{m.current.toLocaleString()}</p>
      <div className="flex items-center gap-1 mt-1">
        <span className={`text-xs font-medium font-mono ${getChangeColor(m.change_pct)}`}>
          {m.change >= 0 ? "+" : ""}{m.change.toFixed(2)}
        </span>
        <span className={`text-xs font-medium font-mono ${getChangeColor(m.change_pct)}`}>
          ({formatPercent(m.change_pct)})
        </span>
      </div>
    </div>
  );

  return (
    <GlassCard title={t("dashboard.marketOverview")} className="h-full">
      {aShare.length > 0 && (
        <div className="mb-4">
          <span className="text-[10px] text-dark-muted font-medium uppercase tracking-wider">{t("market.aShare")}</span>
          <div className="grid grid-cols-3 gap-3 mt-2">
            {aShare.map((m) => <IndexCard key={m.code} m={m} />)}
          </div>
        </div>
      )}
      {hk.length > 0 && (
        <div>
          <span className="text-[10px] text-dark-muted font-medium uppercase tracking-wider">{t("market.hk")}</span>
          <div className="grid grid-cols-2 gap-3 mt-2">
            {hk.map((m) => <IndexCard key={m.code} m={m} />)}
          </div>
        </div>
      )}
    </GlassCard>
  );
}
