"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getStockDetail } from "@/lib/api";
import type { StockDetail } from "@/types";
import { useTranslation } from "@/lib/i18n";
import TopSearch from "@/components/TopSearch";
import ScoreBreakdown from "@/components/ScoreBreakdown";
import GlassCard from "@/components/ui/GlassCard";
import TabSwitch from "@/components/ui/TabSwitch";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { signalTypeLabel, signalTypeClass, renderStars, formatPercent, getChangeColor, marketLabel } from "@/lib/utils";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload?.length) {
    return (
      <div className="bg-dark-card border border-white/10 rounded-lg px-3 py-2 shadow-xl backdrop-blur-xl">
        <p className="text-xs text-dark-muted mb-1">{label}</p>
        {payload.map((p: any, i: number) => (
          <p key={i} className="text-sm" style={{ color: p.color }}>{p.name}: <span className="font-mono font-bold">{p.value?.toFixed(2)}</span></p>
        ))}
      </div>
    );
  }
  return null;
};

export default function StockDetailPage() {
  const { t } = useTranslation();
  const params = useParams();
  const symbol = params.symbol as string;
  const [data, setData] = useState<StockDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");

  const fetchData = () => {
    setLoading(true);
    setError(false);
    getStockDetail(symbol)
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, [symbol]);

  if (loading) {
    return (
      <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
        <SkeletonCard /><SkeletonCard />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <p className="text-dark-muted">{t("common.loadingError")}</p>
        <button onClick={fetchData} className="btn-primary px-4 py-2 text-sm">{t("common.retry")}</button>
      </div>
    );
  }

  if (!data) {
    return <div className="flex items-center justify-center min-h-screen text-dark-muted">{t("stock.notFound")}</div>;
  }

  const { stock, latest_price, price_history, financial_metrics, technical_indicators, score, signal, reports } = data;

  const tabs = [
    { key: "overview", label: t("stock.overview") },
    { key: "financial", label: t("stock.financial") },
    { key: "score", label: t("stock.score") },
    { key: "signal", label: t("stock.signal") },
    { key: "reports", label: t("stock.reports") },
  ];

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
      <TopSearch />

      <GlassCard>
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-white">{stock.name}</h1>
              <span className="text-sm text-dark-muted font-mono">{stock.symbol}</span>
              <span className={`text-xs px-2 py-0.5 rounded ${stock.market === "A_SHARE" ? "bg-blue-500/10 text-blue-400" : "bg-purple-500/10 text-purple-400"}`}>
                {marketLabel(stock.market)}
              </span>
              <span className="text-xs text-dark-muted">{stock.industry}</span>
            </div>
            {latest_price && (
              <div className="flex items-end gap-4 mt-3">
                <span className="text-3xl font-bold text-white font-mono">{latest_price.close?.toFixed(2)}</span>
                {latest_price.pe && <span className="text-sm text-dark-muted font-mono">PE {latest_price.pe.toFixed(1)}</span>}
                {latest_price.pb && <span className="text-sm text-dark-muted font-mono">PB {latest_price.pb.toFixed(1)}</span>}
                {latest_price.market_cap && <span className="text-sm text-dark-muted font-mono">{t("stock.marketCap")} {(latest_price.market_cap / 1e8).toFixed(0)}亿</span>}
              </div>
            )}
          </div>
          {score && (
            <div className="text-right">
              <div className="text-4xl font-bold text-primary-400 font-mono">{score.total?.toFixed(0)}</div>
              <span className={`inline-block mt-1 px-3 py-1 rounded-full text-sm font-bold text-white ${
                score.rating === "BUY" ? "bg-emerald-500" :
                score.rating === "ADD" ? "bg-blue-500" :
                score.rating === "WATCH" ? "bg-amber-500" :
                score.rating === "REDUCE" ? "bg-orange-500" : "bg-red-500"
              }`}>
                {score.rating}
              </span>
            </div>
          )}
        </div>
      </GlassCard>

      <TabSwitch tabs={tabs} active={activeTab} onChange={setActiveTab} />

      {activeTab === "overview" && price_history && (
        <GlassCard title={t("stock.priceChart")}>
          <div className="h-[400px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={price_history.map((p: any, i: number, arr: any[]) => {
                if (i >= 19) {
                  const slice = arr.slice(i - 19, i + 1);
                  const ma20 = slice.reduce((s: number, v: any) => s + v.close, 0) / slice.length;
                  return { ...p, ma20: Math.round(ma20 * 100) / 100 };
                }
                return { ...p, ma20: null };
              })}>
                <CartesianGrid stroke="#1E293B" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94A3B8" }} interval="preserveStartEnd" />
                <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10, fill: "#94A3B8" }} />
                <Tooltip content={<CustomTooltip />} />
                <Line type="monotone" dataKey="close" stroke="#6366f1" strokeWidth={2} dot={false} name={t("stock.closePrice")} />
                <Line type="monotone" dataKey="ma20" stroke="#10B981" strokeWidth={1} dot={false} name="MA20" connectNulls={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>
      )}

      {activeTab === "financial" && financial_metrics && (
        <GlassCard title={t("stock.financial")}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  {[t("financial.period"), t("financial.revenue"), t("financial.revenueGrowth"), t("financial.netProfit"), t("financial.profitGrowth"), t("financial.grossMargin"), t("financial.roe"), t("financial.debtRatio"), "EPS"].map((h) => (
                    <th key={h} className="text-left py-2 px-3 text-dark-muted text-xs">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {financial_metrics.map((f: any, i: number) => (
                  <tr key={i} className="border-b border-white/[0.03]">
                    <td className="py-2 px-3 font-medium text-dark-text">{f.period}</td>
                    <td className="py-2 px-3 text-right font-mono text-dark-text">{f.revenue?.toFixed(1)}</td>
                    <td className={`py-2 px-3 text-right font-medium font-mono ${getChangeColor(f.revenue_yoy)}`}>{formatPercent(f.revenue_yoy)}</td>
                    <td className="py-2 px-3 text-right font-mono text-dark-text">{f.net_profit?.toFixed(1)}</td>
                    <td className={`py-2 px-3 text-right font-medium font-mono ${getChangeColor(f.net_profit_yoy)}`}>{formatPercent(f.net_profit_yoy)}</td>
                    <td className="py-2 px-3 text-right font-mono text-dark-text">{f.gross_margin?.toFixed(1)}%</td>
                    <td className="py-2 px-3 text-right font-mono text-dark-text">{f.roe?.toFixed(1)}%</td>
                    <td className="py-2 px-3 text-right font-mono text-dark-text">{f.debt_ratio?.toFixed(1)}%</td>
                    <td className="py-2 px-3 text-right font-mono text-dark-text">{f.eps?.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}

      {activeTab === "score" && score && <ScoreBreakdown score={score} />}

      {activeTab === "signal" && signal && (
        <GlassCard title={t("stock.signal")}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="p-3 bg-white/[0.03] rounded-xl border border-white/[0.06]">
              <p className="text-xs text-dark-muted">{t("stock.signalType")}</p>
              <span className={signalTypeClass(signal.type) + " mt-1 inline-block"}>{signalTypeLabel(signal.type)}</span>
            </div>
            <div className="p-3 bg-white/[0.03] rounded-xl border border-white/[0.06]">
              <p className="text-xs text-dark-muted">{t("stock.signalStrength")}</p>
              <p className="star text-lg mt-1">{renderStars(signal.strength)}</p>
            </div>
            <div className="p-3 bg-white/[0.03] rounded-xl border border-white/[0.06]">
              <p className="text-xs text-dark-muted">{t("stock.suggestedPosition")}</p>
              <p className="text-lg font-bold text-white mt-1 font-mono">{signal.position > 0 ? `${signal.position}%` : "-"}</p>
            </div>
            <div className="p-3 bg-white/[0.03] rounded-xl border border-white/[0.06]">
              <p className="text-xs text-dark-muted">{t("stock.holdingPeriod")}</p>
              <p className="text-lg font-bold text-white mt-1">{signal.holding_period}</p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="p-3 bg-emerald-500/10 rounded-xl border border-emerald-500/20 text-center">
              <p className="text-xs text-dark-muted">{t("stock.entryPrice")}</p>
              <p className="text-lg font-bold text-emerald-400 font-mono">{signal.entry_price?.toFixed(2) || "-"}</p>
            </div>
            <div className="p-3 bg-blue-500/10 rounded-xl border border-blue-500/20 text-center">
              <p className="text-xs text-dark-muted">{t("stock.targetPrice")}</p>
              <p className="text-lg font-bold text-blue-400 font-mono">{signal.target_price?.toFixed(2) || "-"}</p>
            </div>
            <div className="p-3 bg-red-500/10 rounded-xl border border-red-500/20 text-center">
              <p className="text-xs text-dark-muted">{t("stock.stopLoss")}</p>
              <p className="text-lg font-bold text-red-400 font-mono">{signal.stop_loss?.toFixed(2) || "-"}</p>
            </div>
          </div>
          {signal.logic && (
            <div className="p-4 bg-white/[0.03] rounded-xl border border-white/[0.06]">
              <p className="text-xs text-dark-muted mb-2">{t("stock.signalLogic")}</p>
              <p className="text-sm text-dark-text">{signal.logic.reason}</p>
            </div>
          )}
          {signal.risk && (
            <div className="p-4 bg-amber-500/10 rounded-xl border border-amber-500/20 mt-4">
              <p className="text-xs text-amber-400 mb-2">{t("stock.riskWarning")}</p>
              <ul className="text-sm text-amber-400/80 space-y-1">
                {signal.risk.items?.map((r: string, i: number) => <li key={i}>- {r}</li>)}
              </ul>
            </div>
          )}
        </GlassCard>
      )}

      {activeTab === "reports" && (
        <GlassCard title={t("stock.brokerReports")}>
          {reports && reports.length > 0 ? (
            <div className="space-y-3">
              {reports.map((r: any, i: number) => (
                <div key={i} className="p-4 bg-white/[0.03] rounded-xl border border-white/[0.06]">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        {r.rating && (
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            r.rating.includes("买入") || r.rating.includes("强推") ? "bg-red-500/10 text-red-400"
                              : r.rating.includes("增持") || r.rating.includes("推荐") ? "bg-orange-500/10 text-orange-400"
                              : "bg-white/5 text-dark-muted"
                          }`}>{r.rating}</span>
                        )}
                        <span className="text-xs text-dark-muted">{r.org_name}</span>
                        {r.researcher && <span className="text-xs text-dark-muted">{t("reports.researcher")} {r.researcher}</span>}
                      </div>
                      <a href={r.url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-dark-text hover:text-primary-400 transition-colors">{r.title}</a>
                      <p className="text-xs text-dark-muted mt-1">{r.publish_date}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-dark-muted text-sm">{t("common.noResearch")}</div>
          )}
        </GlassCard>
      )}

      <div className="disclaimer">{t("app.disclaimer")}</div>
    </div>
  );
}
