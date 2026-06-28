"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import PageShell from "@/components/layout/PageShell";
import GlassCard from "@/components/ui/GlassCard";
import SimulatedDataNotice from "@/components/ui/SimulatedDataNotice";
import { SkeletonTable } from "@/components/ui/Skeleton";
import TabSwitch from "@/components/ui/TabSwitch";
import { showToast } from "@/components/ui/Toast";
import { getSignals, getRuntimeInfo } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import { getChangeColor, marketLabel, renderStars, sanitizeDisplayText, sanitizeSignalNarrative, signalTypeClass, signalTypeLabel } from "@/lib/utils";
import type { RuntimeInfo, SignalListResponse } from "@/types";

export default function SignalsPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const [data, setData] = useState<SignalListResponse | null>(null);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [market, setMarket] = useState("");
  const [signalType, setSignalType] = useState("");
  const [page, setPage] = useState(1);

  const load = () => {
    setLoading(true);
    setError(false);
    getRuntimeInfo().then(setRuntime).catch(() => {});
    getSignals({ market: market || undefined, signal_type: signalType || undefined, page, page_size: 20 })
      .then(setData)
      .catch(() => {
        setError(true);
        showToast("error", t("common.loadFailed"));
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [market, page, signalType]);

  return (
    <PageShell title={t("signals.title")} subtitle="筛选和研究交易信号">

      <div className="flex flex-wrap gap-4">
        <TabSwitch
          tabs={[
            { key: "", label: t("common.all") },
            { key: "A_SHARE", label: t("market.aShare") },
            { key: "HK", label: t("market.hk") },
          ]}
          active={market}
          onChange={(key) => {
            setMarket(key);
            setPage(1);
          }}
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
          onChange={(key) => {
            setSignalType(key);
            setPage(1);
          }}
          className="w-fit"
        />
      </div>

      <SimulatedDataNotice
        title="信号研究口径"
        badges={[
          { label: `信号日期 ${runtime?.latest_updates?.signals || "待核验"}`, tone: "database" },
          { label: runtime?.provider_mode === "mock" ? "含模拟或种子数据" : "数据库生成信号", tone: runtime?.provider_mode === "mock" ? "simulated" : "live" },
        ]}
        lines={[
          "高关注、增强关注、观察、风险升高、回避观察代表模型研究优先级，不代表买卖指令。",
          "研究仓位、模型观察价和风险警戒价来自评分规则推导，仅用于研究辅助，不代表实盘建议。",
        ]}
      />

      {loading ? (
        <SkeletonTable />
      ) : error ? (
        <GlassCard>
          <div className="py-10 text-center">
            <p className="text-sm text-dark-text">{t("common.loadingError")}</p>
            <button onClick={load} className="btn-primary mt-4 px-4 py-2 text-sm">
              {t("common.retry")}
            </button>
          </div>
        </GlassCard>
      ) : (
        <>
          <GlassCard>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    {[
                      t("signals.code"),
                      t("signals.name"),
                      t("signals.market"),
                      t("signals.signal"),
                      t("signals.strength"),
                      "生成时间",
                      "研究依据",
                      t("signals.position"),
                      t("signals.targetPrice"),
                      t("signals.stopLoss"),
                      t("signals.holdingPeriod"),
                      t("signals.latestPrice"),
                      t("signals.action"),
                    ].map((header) => (
                      <th key={header} className="px-3 py-3 text-left text-xs font-medium text-dark-muted">
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data?.items?.map((item) => (
                    <tr key={item.id} className="border-b border-white/[0.03] transition-colors hover:bg-white/[0.03]">
                      <td className="px-3 py-3 font-mono text-xs text-dark-text">{item.symbol}</td>
                      <td className="px-3 py-3 font-medium text-dark-text">{item.name}</td>
                      <td className="px-3 py-3">
                        <span className={`rounded px-2 py-0.5 text-xs ${item.market === "A_SHARE" ? "bg-blue-500/10 text-blue-400" : "bg-purple-500/10 text-purple-400"}`}>
                          {marketLabel(item.market)}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <span className={signalTypeClass(item.signal_type)}>{signalTypeLabel(item.signal_type)}</span>
                      </td>
                      <td className="star px-3 py-3 text-sm">{renderStars(item.signal_strength)}</td>
                      <td className="px-3 py-3 text-xs text-dark-muted">{item.signal_date || "-"}</td>
                      <td className="max-w-[260px] px-3 py-3 text-xs leading-5 text-dark-muted">
                        <div>
                          {sanitizeSignalNarrative(item.logic?.display_label || item.logic?.reason || "模型研究标签")
                            .replace("建议研究关注", "研究关注")
                            .replace("可适当增强关注", "增强关注")}
                        </div>
                        <div className="mt-1 text-[11px] text-dark-muted/70">
                          数据来源: {sanitizeDisplayText(item.logic?.data_source || "数据库信号表（trade_signals）")}
                        </div>
                      </td>
                      <td className="px-3 py-3 font-mono text-dark-text">{item.suggested_position > 0 ? `${item.suggested_position}%` : "-"}</td>
                      <td className="px-3 py-3 font-mono text-emerald-400">{item.target_price?.toFixed(2) || "-"}</td>
                      <td className="px-3 py-3 font-mono text-red-400">{item.stop_loss_price?.toFixed(2) || "-"}</td>
                      <td className="px-3 py-3 text-xs text-dark-muted">{sanitizeDisplayText(item.holding_period || "-")}</td>
                      <td className={`px-3 py-3 font-mono font-medium ${getChangeColor(item.change_pct)}`}>{item.latest_close?.toFixed(2) || "-"}</td>
                      <td className="px-3 py-3">
                        <button onClick={() => router.push(`/stocks/${item.symbol}`)} className="text-xs font-medium text-primary-400 transition-colors hover:text-primary-300">
                          {t("common.detail")}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>

          {data && data.total === 0 && (
            <GlassCard>
              <div className="py-10 text-center text-sm text-dark-muted">当前筛选条件下暂无研究信号。</div>
            </GlassCard>
          )}

          {data && data.total > data.page_size && (
            <div className="flex justify-center gap-2">
              <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1} className="btn-secondary px-4 py-2 text-sm disabled:opacity-50">
                {t("common.prevPage")}
              </button>
              <span className="px-4 py-2 text-sm text-dark-muted">
                {t("common.page", { page: String(page), total: String(Math.ceil(data.total / data.page_size)) })}
              </span>
              <button onClick={() => setPage(page + 1)} disabled={page >= Math.ceil(data.total / data.page_size)} className="btn-secondary px-4 py-2 text-sm disabled:opacity-50">
                {t("common.nextPage")}
              </button>
            </div>
          )}
        </>
      )}

      <div className="disclaimer">{t("app.disclaimer")}</div>
    </PageShell>
  );
}
