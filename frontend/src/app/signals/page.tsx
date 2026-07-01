"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import PageShell from "@/components/layout/PageShell";
import GlassCard from "@/components/ui/GlassCard";
import SimulatedDataNotice from "@/components/ui/SimulatedDataNotice";
import { SkeletonTable } from "@/components/ui/Skeleton";
import TabSwitch from "@/components/ui/TabSwitch";
import { showToast } from "@/components/ui/Toast";
import { getSignals, getRuntimeInfo, isForbiddenError } from "@/lib/api";
import {
  displayTierLabel,
  displayTierTone,
  marketLabel,
  sanitizeDisplayText,
  signalTypeClass,
  signalTypeLabel,
} from "@/lib/utils";
import type { RuntimeInfo, SignalListResponse } from "@/types";

type SignalSection = "formal" | "risk" | "limited" | "demo";

function CountBadge({ label, value, tone }: { label: string; value: number; tone: string }) {
  return <span className={`rounded-full border px-3 py-1 text-xs ${tone}`}>{label} {value}</span>;
}

export default function SignalsPage() {
  const router = useRouter();
  const [data, setData] = useState<SignalListResponse | null>(null);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [market, setMarket] = useState("");
  const [includeDemo, setIncludeDemo] = useState(true);
  const [section, setSection] = useState<SignalSection>("formal");

  useEffect(() => {
    if (typeof window === "undefined") return;
    setIncludeDemo(new URLSearchParams(window.location.search).get("include_demo") === "true");
  }, []);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [runtimeInfo, signalData] = await Promise.all([
        getRuntimeInfo().catch(() => null),
        getSignals({
          market: market || undefined,
          include_demo: includeDemo || undefined,
          page: 1,
          page_size: 20,
        }),
      ]);
      setRuntime(runtimeInfo);
      setData(signalData);
    } catch (err) {
      const message = err instanceof Error ? err.message : "信号列表加载失败，请稍后重试。";
      setError(message);
      if (!isForbiddenError(err)) showToast("error", message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [includeDemo, market]);

  const updateIncludeDemo = (next: boolean) => {
    setIncludeDemo(next);
    setSection(next ? "demo" : "formal");
    const params = new URLSearchParams(typeof window !== "undefined" ? window.location.search : "");
    if (next) params.set("include_demo", "true");
    else params.delete("include_demo");
    router.replace(`/signals${params.toString() ? `?${params.toString()}` : ""}`);
  };

  const formalCount = data?.meta?.summary?.formal_signal_count || data?.items.length || 0;
  const riskCount = data?.risk_observation_count || data?.diagnostics?.risk_observation_count || 0;
  const limitedCount = data?.diagnostics?.data_quality_limited_count || data?.meta?.summary?.data_quality_limited_count || 0;
  const demoCount = data?.meta?.demo_signal_count || 0;
  const riskItems = data?.risk_observation_items || [];
  const limitedItems = data?.data_quality_limited_items || [];

  const sectionItems = useMemo(() => {
    if (!data) return [];
    if (section === "formal") return data.items;
    if (section === "risk") return riskItems;
    if (section === "limited") return limitedItems;
    return includeDemo ? data.items : [];
  }, [data, includeDemo, limitedItems, riskItems, section]);

  return (
    <PageShell title="研究信号" subtitle="正式研究信号、风险观察样本与数据质量受限样本分开展示。">
      <div className="flex flex-wrap gap-4">
        <TabSwitch
          tabs={[
            { key: "", label: "全部市场" },
            { key: "A_SHARE", label: "A股" },
            { key: "HK", label: "港股" },
          ]}
          active={market}
          onChange={setMarket}
          className="w-fit"
        />
        <div className="flex gap-2">
          <button
            onClick={() => updateIncludeDemo(false)}
            className={`rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
              includeDemo ? "bg-slate-100 text-slate-700 hover:bg-slate-200" : "bg-primary-500 text-white"
            }`}
          >
            返回正式视图
          </button>
          <button
            onClick={() => updateIncludeDemo(true)}
            className={`rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
              includeDemo ? "bg-primary-500 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
            }`}
          >
            查看演示信号
          </button>
        </div>
      </div>

      {includeDemo ? (
        <div className="card-warning">
          <p className="text-sm font-medium">当前展示包含演示信号，仅用于功能体验，不代表正式研究结果。</p>
        </div>
      ) : null}

      <SimulatedDataNotice
        title="信号形成解释"
        badges={[
          { label: `信号日期 ${runtime?.latest_updates?.signals || "待更新"}`, tone: "database" },
          { label: includeDemo ? "当前含演示信号" : "当前仅正式研究视图", tone: includeDemo ? "simulated" : "live" },
        ]}
        lines={[
          `当前真实样本中：正式研究信号 ${formalCount} 条、风险观察样本 ${riskCount} 条、数据质量受限 ${limitedCount} 条。`,
          "风险观察不等于正式推荐，数据质量受限也不等于看空。",
          "演示信号默认隔离，只有主动切换后才会进入当前视图。",
        ]}
      />

      <GlassCard>
        <div className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-dark-text">当前信号结构</h2>
              <p className="mt-1 text-sm text-dark-muted">
                {formalCount === 1
                  ? "当前只有 1 条正式研究信号，说明系统在真实数据覆盖不足阶段保持保守，不将低置信度样本包装成正式结论。"
                  : sanitizeDisplayText(data?.message || data?.meta?.message, "正式研究信号仅展示满足当前阈值且覆盖较完整的样本。")}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <CountBadge label="正式研究信号" value={formalCount} tone="border-emerald-200 bg-emerald-50 text-emerald-700" />
              <CountBadge label="风险观察样本" value={riskCount} tone="border-blue-200 bg-blue-50 text-blue-700" />
              <CountBadge label="数据质量受限" value={limitedCount} tone="border-amber-200 bg-amber-50 text-amber-700" />
              <CountBadge label="演示信号" value={demoCount} tone="border-slate-200 bg-slate-50 text-slate-700" />
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {[
              { key: "formal" as const, label: `正式研究信号 (${formalCount})` },
              { key: "risk" as const, label: `风险观察样本 (${riskCount})` },
              { key: "limited" as const, label: `数据质量受限 (${limitedCount})` },
              { key: "demo" as const, label: `演示信号 (${demoCount})` },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => {
                  if (tab.key === "demo") {
                    updateIncludeDemo(true);
                  } else if (includeDemo) {
                    updateIncludeDemo(false);
                    setSection(tab.key);
                  } else {
                    setSection(tab.key);
                  }
                }}
                className={`rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
                  section === tab.key ? "bg-primary-500 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </GlassCard>

      {loading ? (
        <SkeletonTable />
      ) : error ? (
        <GlassCard>
          <div className="py-10 text-center">
            <p className="text-sm text-dark-text">{error}</p>
            <button onClick={() => void load()} className="btn-primary mt-4 px-4 py-2 text-sm">
              重新加载
            </button>
          </div>
        </GlassCard>
      ) : sectionItems.length === 0 ? (
        <GlassCard>
          <div className="py-10 text-center text-sm text-dark-muted">
            {section === "formal"
              ? "当前暂无正式研究信号。"
              : section === "risk"
              ? "当前暂无可展示的风险观察样本。"
              : section === "limited"
              ? "当前暂无可展示的数据质量受限样本。"
              : "当前暂无演示信号。"}
          </div>
        </GlassCard>
      ) : (
        <GlassCard>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  {["代码", "名称", "市场", "标签", "评分", "主要原因", "数据状态", "详情"].map((header) => (
                    <th key={header} className="px-3 py-3 text-left text-xs font-medium text-dark-muted">
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sectionItems.map((item: any) => (
                  <tr key={`${item.symbol}-${item.signal_type || item.display_tier || "row"}`} className="border-b border-white/[0.03] transition-colors hover:bg-white/[0.03]">
                    <td className="px-3 py-3 font-mono text-xs text-dark-text">{item.symbol}</td>
                    <td className="px-3 py-3 font-medium text-dark-text">{item.name}</td>
                    <td className="px-3 py-3 text-dark-muted">{marketLabel(item.market || market || "A_SHARE")}</td>
                    <td className="px-3 py-3">
                      <span className={signalTypeClass(item.signal_type || "WATCH")}>
                        {sanitizeDisplayText(item.signal_label || signalTypeLabel(item.signal_type || "WATCH"))}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-dark-text">{item.score != null ? item.score : item.total_score != null ? item.total_score : "暂无"}</td>
                    <td className="max-w-[320px] px-3 py-3 text-xs leading-5 text-dark-muted">
                      {sanitizeDisplayText(item.primary_low_score_reason || item.reason_summary, "暂无补充说明。")}
                    </td>
                    <td className="px-3 py-3">
                      <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs ${displayTierTone(item.display_tier || "data_quality_limited") === "warning" ? "border-amber-200 bg-amber-50 text-amber-700" : "border-slate-200 bg-slate-50 text-slate-700"}`}>
                        {displayTierLabel(item.display_tier || (section === "risk" ? "real_observation" : "data_quality_limited"))}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <Link href={`/stocks/${item.symbol}`} className="text-xs font-medium text-primary-400 transition-colors hover:text-primary-300">
                        查看详情
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}
    </PageShell>
  );
}
