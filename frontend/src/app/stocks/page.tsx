"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSignals } from "@/lib/api";
import TopSearch from "@/components/TopSearch";
import GlassCard from "@/components/ui/GlassCard";
import TabSwitch from "@/components/ui/TabSwitch";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonTable } from "@/components/ui/Skeleton";
import { showToast } from "@/components/ui/Toast";
import { useTranslation } from "@/lib/i18n";
import { signalTypeLabel, signalTypeClass, renderStars, marketLabel, getChangeColor, formatPercent } from "@/lib/utils";

export default function StocksPage() {
  const { t } = useTranslation();
  const [stocks, setStocks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [market, setMarket] = useState<string>("");
  const router = useRouter();

  useEffect(() => {
    setLoading(true);
    setError(false);
    getSignals({ market: market || undefined, page_size: 50 })
      .then((data) => setStocks(data.items || []))
      .catch(() => { setError(true); showToast("error", t("common.loadFailed")); })
      .finally(() => setLoading(false));
  }, [market]);

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
      <TopSearch />

      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <span className="w-1 h-6 bg-primary-500 rounded-full" />
          {t("stocks.title")}
        </h1>
        <TabSwitch
          tabs={[
            { key: "", label: t("common.all") },
            { key: "A_SHARE", label: t("market.aShare") },
            { key: "HK", label: t("market.hk") },
          ]}
          active={market}
          onChange={setMarket}
          className="w-fit"
        />
      </div>

      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-dark-muted">{t("stocks.signalList")}</h2>
        <span className="text-xs text-dark-muted">{t("common.count", { count: String(stocks.length) })}</span>
      </div>

      {loading ? (
        <SkeletonTable />
      ) : error ? (
        <GlassCard>
          <div className="text-center py-8 text-dark-muted">
            <p className="mb-3">{t("common.loadingError")}</p>
            <button onClick={() => { setLoading(true); setError(false); getSignals({ market: market || undefined, page_size: 50 }).then((data) => setStocks(data.items || [])).catch(() => setError(true)).finally(() => setLoading(false)); }} className="btn-primary px-4 py-2 text-sm">{t("common.retry")}</button>
          </div>
        </GlassCard>
      ) : stocks.length === 0 ? (
        <GlassCard>
          <EmptyState message={t("common.noSignal.sync")} />
        </GlassCard>
      ) : (
        <GlassCard>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  {[t("stocks.code"), t("stocks.name"), t("stocks.market"), t("stocks.signal"), t("stocks.strength"), t("stocks.score"), t("stocks.latestPrice"), t("stocks.change"), t("stocks.position"), t("stocks.action")].map((h) => (
                    <th key={h} className="text-left py-3 px-3 text-dark-muted font-medium text-xs">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {stocks.map((s) => (
                  <tr key={s.id} className="border-b border-white/[0.03] hover:bg-white/[0.03] transition-colors cursor-pointer" onClick={() => router.push(`/stocks/${s.symbol}`)}>
                    <td className="py-3 px-3 font-mono text-xs text-dark-text">{s.symbol}</td>
                    <td className="py-3 px-3 font-medium text-dark-text">{s.name}</td>
                    <td className="py-3 px-3">
                      <span className={`text-xs px-2 py-0.5 rounded ${s.market === "A_SHARE" ? "bg-blue-500/10 text-blue-400" : "bg-purple-500/10 text-purple-400"}`}>
                        {marketLabel(s.market)}
                      </span>
                    </td>
                    <td className="py-3 px-3"><span className={signalTypeClass(s.signal_type)}>{signalTypeLabel(s.signal_type)}</span></td>
                    <td className="py-3 px-3 star text-sm">{renderStars(s.signal_strength)}</td>
                    <td className="py-3 px-3">
                      {s.logic?.total_score ? <span className="font-bold text-primary-400 font-mono">{s.logic.total_score.toFixed(0)}</span> : "-"}
                    </td>
                    <td className="py-3 px-3 font-mono text-dark-text">{s.latest_close?.toFixed(2) || "-"}</td>
                    <td className={`py-3 px-3 font-medium font-mono ${getChangeColor(s.change_pct)}`}>{formatPercent(s.change_pct)}</td>
                    <td className="py-3 px-3 font-mono text-dark-text">{s.suggested_position > 0 ? `${s.suggested_position}%` : "-"}</td>
                    <td className="py-3 px-3">
                      <button onClick={(e) => { e.stopPropagation(); router.push(`/stocks/${s.symbol}`); }} className="text-primary-400 hover:text-primary-300 text-xs font-medium transition-colors">{t("common.detail")}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}

      <div className="disclaimer">{t("app.disclaimer")}</div>
    </div>
  );
}
