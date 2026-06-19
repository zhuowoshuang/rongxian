"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSignals } from "@/lib/api";
import type { SignalListResponse } from "@/types";
import { signalTypeLabel, signalTypeClass, renderStars, marketLabel, getChangeColor } from "@/lib/utils";
import { useTranslation } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";
import TabSwitch from "@/components/ui/TabSwitch";
import { SkeletonTable } from "@/components/ui/Skeleton";
import { showToast } from "@/components/ui/Toast";

export default function SignalsPage() {
  const { t } = useTranslation();
  const [data, setData] = useState<SignalListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [market, setMarket] = useState<string>("");
  const [signalType, setSignalType] = useState<string>("");
  const [page, setPage] = useState(1);
  const router = useRouter();

  useEffect(() => {
    setLoading(true);
    setError(false);
    getSignals({ market: market || undefined, signal_type: signalType || undefined, page, page_size: 20 })
      .then(setData)
      .catch(() => { setError(true); showToast("error", t("common.loadFailed")); })
      .finally(() => setLoading(false));
  }, [market, signalType, page]);

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
      <h1 className="text-xl font-bold text-white flex items-center gap-2">
        <span className="w-1 h-6 bg-primary-500 rounded-full" />
        {t("signals.title")}
      </h1>

      <div className="flex gap-4 flex-wrap">
        <TabSwitch
          tabs={[
            { key: "", label: t("common.all") },
            { key: "A_SHARE", label: t("market.aShare") },
            { key: "HK", label: t("market.hk") },
          ]}
          active={market}
          onChange={(k) => { setMarket(k); setPage(1); }}
          className="w-fit"
        />
        <TabSwitch
          tabs={[
            { key: "", label: t("common.all") },
            { key: "BUY", label: t("signal.BUY") },
            { key: "ADD", label: t("signal.ADD") },
            { key: "WATCH", label: t("signal.WATCH") },
            { key: "REDUCE", label: t("signal.REDUCE") },
            { key: "SELL", label: t("signal.SELL") },
          ]}
          active={signalType}
          onChange={(k) => { setSignalType(k); setPage(1); }}
          className="w-fit"
        />
      </div>

      {loading ? (
        <SkeletonTable />
      ) : error ? (
        <GlassCard>
          <div className="text-center py-8 text-dark-muted">
            <p className="mb-3">{t("common.loadingError")}</p>
            <button onClick={() => { setLoading(true); setError(false); getSignals({ market: market || undefined, signal_type: signalType || undefined, page, page_size: 20 }).then(setData).catch(() => setError(true)).finally(() => setLoading(false)); }} className="btn-primary px-4 py-2 text-sm">{t("common.retry")}</button>
          </div>
        </GlassCard>
      ) : (
        <>
          <GlassCard>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    {[t("signals.code"), t("signals.name"), t("signals.market"), t("signals.signal"), t("signals.strength"), t("signals.position"), t("signals.entryPrice"), t("signals.targetPrice"), t("signals.stopLoss"), t("signals.holdingPeriod"), t("signals.latestPrice"), t("signals.action")].map((h) => (
                      <th key={h} className="text-left py-3 px-3 text-dark-muted font-medium text-xs">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data?.items?.map((s: any) => (
                    <tr key={s.id} className="border-b border-white/[0.03] hover:bg-white/[0.03] transition-colors">
                      <td className="py-3 px-3 font-mono text-xs text-dark-text">{s.symbol}</td>
                      <td className="py-3 px-3 font-medium text-dark-text">{s.name}</td>
                      <td className="py-3 px-3">
                        <span className={`text-xs px-2 py-0.5 rounded ${s.market === "A_SHARE" ? "bg-blue-500/10 text-blue-400" : "bg-purple-500/10 text-purple-400"}`}>
                          {marketLabel(s.market)}
                        </span>
                      </td>
                      <td className="py-3 px-3"><span className={signalTypeClass(s.signal_type)}>{signalTypeLabel(s.signal_type)}</span></td>
                      <td className="py-3 px-3 star text-sm">{renderStars(s.signal_strength)}</td>
                      <td className="py-3 px-3 font-mono text-dark-text">{s.suggested_position > 0 ? `${s.suggested_position}%` : "-"}</td>
                      <td className="py-3 px-3 font-mono text-dark-text">{s.entry_price?.toFixed(2) || "-"}</td>
                      <td className="py-3 px-3 font-mono text-emerald-400">{s.target_price?.toFixed(2) || "-"}</td>
                      <td className="py-3 px-3 font-mono text-red-400">{s.stop_loss_price?.toFixed(2) || "-"}</td>
                      <td className="py-3 px-3 text-xs text-dark-muted">{s.holding_period}</td>
                      <td className={`py-3 px-3 font-medium font-mono ${getChangeColor(s.change_pct)}`}>{s.latest_close?.toFixed(2) || "-"}</td>
                      <td className="py-3 px-3">
                        <button onClick={() => router.push(`/stocks/${s.symbol}`)} className="text-primary-400 hover:text-primary-300 text-xs font-medium transition-colors">{t("common.detail")}</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>

          {data && data.total > data.page_size && (
            <div className="flex justify-center gap-2">
              <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1} className="btn-secondary px-4 py-2 text-sm disabled:opacity-50">{t("common.prevPage")}</button>
              <span className="px-4 py-2 text-sm text-dark-muted">{t("common.page", { page: String(page), total: String(Math.ceil(data.total / data.page_size)) })}</span>
              <button onClick={() => setPage(page + 1)} disabled={page >= Math.ceil(data.total / data.page_size)} className="btn-secondary px-4 py-2 text-sm disabled:opacity-50">{t("common.nextPage")}</button>
            </div>
          )}
        </>
      )}

      <div className="disclaimer">{t("app.disclaimer")}</div>
    </div>
  );
}
