"use client";

import type { MarketIndex } from "@/types";
import { formatPercent, getChangeColor } from "@/lib/utils";
import { useTranslation } from "@/lib/i18n";

interface Props {
  markets: MarketIndex[];
}

export default function MarketOverviewCard({ markets }: Props) {
  const { t } = useTranslation();

  if (!markets || markets.length === 0) {
    return (
      <div className="card">
        <h3 className="text-h3 mb-3">{t("dashboard.marketOverview")}</h3>
        <p className="text-caption">暂无市场数据</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h3 className="text-h3 mb-3">{t("dashboard.marketOverview")}</h3>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {markets.map((m) => (
          <div key={m.code} className="card-inner hover:shadow-sm transition-shadow">
            <p className="text-caption mb-1">{m.name}</p>
            <p className="text-lg font-bold text-[var(--text-primary)] font-mono">
              {m.current.toLocaleString()}
            </p>
            <div className="flex items-center gap-1.5 mt-1">
              <span className={`text-xs font-semibold font-mono ${getChangeColor(m.change_pct)}`}>
                {m.change >= 0 ? "+" : ""}{m.change.toFixed(2)}
              </span>
              <span className={`text-xs font-semibold font-mono ${getChangeColor(m.change_pct)}`}>
                ({formatPercent(m.change_pct)})
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
