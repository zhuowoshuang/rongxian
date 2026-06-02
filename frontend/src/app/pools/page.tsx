"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getStockPool } from "@/lib/api";
import { ratingClass, marketLabel } from "@/lib/utils";
import { useTranslation } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonTable } from "@/components/ui/Skeleton";

export default function PoolsPage() {
  const { t } = useTranslation();
  const [activeType, setActiveType] = useState("quality");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const poolTypes = [
    { key: "quality", label: t("pool.quality"), color: "bg-emerald-500" },
    { key: "undervalued", label: t("pool.undervalued"), color: "bg-blue-500" },
    { key: "trend", label: t("pool.trend"), color: "bg-purple-500" },
    { key: "risk", label: t("pool.risk"), color: "bg-red-500" },
    { key: "steady", label: "🛡️ 稳健优选", color: "bg-blue-400" },
    { key: "aggressive", label: "🚀 进取优选", color: "bg-purple-400" },
    { key: "conservative", label: "🏦 保守优选", color: "bg-green-400" },
    { key: "volatile", label: "⚡ 周波动>2%", color: "bg-orange-400" },
  ];

  useEffect(() => {
    setLoading(true);
    getStockPool(activeType)
      .then(setData)
      .finally(() => setLoading(false));
  }, [activeType]);

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
      <h1 className="text-xl font-bold text-white flex items-center gap-2">
        <span className="w-1 h-6 bg-primary-500 rounded-full" />
        {t("pools.title")}
      </h1>

      <div className="flex gap-2">
        {poolTypes.map((pt) => (
          <button
            key={pt.key}
            onClick={() => setActiveType(pt.key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all border ${
              activeType === pt.key
                ? "bg-white/[0.08] border-white/[0.15] text-white"
                : "bg-white/[0.03] border-white/[0.06] text-dark-muted hover:bg-white/[0.05]"
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${pt.color}`} />
            {pt.label}
          </button>
        ))}
      </div>

      {loading ? (
        <SkeletonTable />
      ) : (
        <GlassCard>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-dark-muted">
              {poolTypes.find(pt => pt.key === activeType)?.label} ({t("common.items", { count: String(data?.count || 0) })})
            </h3>
            {data?.date && <span className="text-xs text-dark-muted">{t("pools.scoreDate")} {data.date}</span>}
          </div>
          {data?.items?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    {[t("pools.title").includes("Pool") ? "Code" : "代码", t("stocks.name"), t("stocks.market"), t("pools.industry"), t("pools.totalScore"), t("pools.quality"), t("pools.valuation"), t("pools.growth"), t("pools.trend"), t("pools.risk"), t("pools.rating"), t("pools.reason"), t("pools.action")].map((h) => (
                      <th key={h} className="text-left py-3 px-3 text-dark-muted text-xs">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((item: any) => (
                    <tr key={item.symbol} className="border-b border-white/[0.03] hover:bg-white/[0.03] cursor-pointer" onClick={() => router.push(`/stocks/${item.symbol}`)}>
                      <td className="py-3 px-3 font-mono text-xs text-dark-text">{item.symbol}</td>
                      <td className="py-3 px-3 font-medium text-dark-text">{item.name}</td>
                      <td className="py-3 px-3">
                        <span className={`text-xs px-2 py-0.5 rounded ${item.market === "A_SHARE" ? "bg-blue-500/10 text-blue-400" : "bg-purple-500/10 text-purple-400"}`}>
                          {marketLabel(item.market)}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-dark-muted">{item.industry}</td>
                      <td className="py-3 px-3 text-right font-bold text-primary-400 font-mono">{item.total_score?.toFixed(0)}</td>
                      <td className="py-3 px-3 text-right font-mono text-dark-text">{item.quality_score?.toFixed(0)}</td>
                      <td className="py-3 px-3 text-right font-mono text-dark-text">{item.valuation_score?.toFixed(0)}</td>
                      <td className="py-3 px-3 text-right font-mono text-dark-text">{item.growth_score?.toFixed(0)}</td>
                      <td className="py-3 px-3 text-right font-mono text-dark-text">{item.trend_score?.toFixed(0)}</td>
                      <td className="py-3 px-3 text-right font-mono text-dark-text">{item.risk_score?.toFixed(0)}</td>
                      <td className="py-3 px-3"><span className={`${ratingClass(item.rating)} !px-2 !py-0 !text-[10px]`}>{item.rating}</span></td>
                      <td className="py-3 px-3 text-xs text-dark-muted max-w-[200px] truncate">{item.reason}</td>
                      <td className="py-3 px-3">
                        <button onClick={(e) => { e.stopPropagation(); router.push(`/stocks/${item.symbol}`); }} className="text-primary-400 hover:text-primary-300 text-xs font-medium transition-colors">{t("common.detail")}</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState message={t("common.noData.seed")} />
          )}
        </GlassCard>
      )}

      <div className="disclaimer">{t("app.disclaimer")}</div>
    </div>
  );
}
