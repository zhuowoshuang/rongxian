"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronUp, Search } from "lucide-react";
import { useRouter } from "next/navigation";

import PageShell from "@/components/layout/PageShell";
import DataStatusBadge from "@/components/ui/DataStatusBadge";
import EmptyState from "@/components/ui/EmptyState";
import SimulatedDataNotice from "@/components/ui/SimulatedDataNotice";
import { SkeletonTable } from "@/components/ui/Skeleton";
import { showToast } from "@/components/ui/Toast";
import { getRuntimeInfo, getScoreDiagnostics, getStockLibrary } from "@/lib/api";
import {
  dataStatusLabel,
  displayTierLabel,
  displayTierTone,
  formatNumber,
  formatPercent,
  marketLabel,
  readinessLabel,
  sanitizeDisplayText,
  scoreSourceLabel,
  signalTypeLabel,
} from "@/lib/utils";
import type { RuntimeInfo, ScoreDiagnosticsResponse, StockLibraryItem, StockLibraryResponse } from "@/types";

const PAGE_SIZE = 50;

const RATING_OPTIONS = [
  { value: "", label: "全部评级" },
  { value: "BUY", label: "高关注" },
  { value: "ADD", label: "增强关注" },
  { value: "WATCH", label: "观察" },
  { value: "REDUCE", label: "风险升高" },
  { value: "SELL", label: "回避观察" },
];

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="card">
      <p className="text-xs font-medium text-[var(--text-secondary)]">{label}</p>
      <p className="mt-2 text-2xl font-bold text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

function statusTone(item: StockLibraryItem) {
  if (item.score_source && item.score_source !== "real_calculated") return "simulated" as const;
  return displayTierTone(item.display_tier || item.coverage_level || item.readiness_label);
}

function statusText(item: StockLibraryItem) {
  if (item.score_source && item.score_source !== "real_calculated") return "演示评分";
  if (item.display_tier_label) return sanitizeDisplayText(item.display_tier_label, "待核验");
  if (item.readiness_label) return sanitizeDisplayText(item.readiness_label, readinessLabel(item.coverage_level));
  return readinessLabel(item.display_tier || item.coverage_level);
}

function scoreBrief(item: StockLibraryItem) {
  if (item.total_score == null) return "暂无";
  if (item.total_score >= 70) return `${item.total_score.toFixed(0)} / 较强`;
  if (item.total_score >= 55) return `${item.total_score.toFixed(0)} / 观察`;
  return `${item.total_score.toFixed(0)} / 谨慎`;
}

export default function StocksPage() {
  const router = useRouter();
  const [response, setResponse] = useState<StockLibraryResponse | null>(null);
  const [diagnostics, setDiagnostics] = useState<ScoreDiagnosticsResponse | null>(null);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [market, setMarket] = useState("");
  const [rating, setRating] = useState("");
  const [includeDemo, setIncludeDemo] = useState(true);
  const [keywordInput, setKeywordInput] = useState("");
  const [keyword, setKeyword] = useState("");
  const [expandedSymbol, setExpandedSymbol] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setIncludeDemo(new URLSearchParams(window.location.search).get("include_demo") === "true");
  }, []);

  const fetchStocks = async () => {
    setLoading(true);
    setError(null);
    try {
      const [runtimeInfo, diagnosticsValue, stockLibrary] = await Promise.all([
        getRuntimeInfo().catch(() => null),
        getScoreDiagnostics().catch(() => null),
        getStockLibrary({
          market: market || undefined,
          rating: rating || undefined,
          keyword: keyword || undefined,
          include_demo: includeDemo || undefined,
          page: 1,
          page_size: PAGE_SIZE,
        }),
      ]);
      setRuntime(runtimeInfo);
      setDiagnostics(diagnosticsValue);
      setResponse(stockLibrary);
    } catch (err: unknown) {
      const message = err instanceof Error && err.message.trim() ? err.message : "个股评分库加载失败，请稍后重试。";
      setError(message);
      setResponse(null);
      showToast("error", message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchStocks();
  }, [includeDemo, market, rating, keyword]);

  const items = response?.items || [];
  const summary = response?.summary;
  const latestUpdate = useMemo(() => {
    return items.find((item) => item.updated_at)?.updated_at || runtime?.latest_updates?.scores || "待更新";
  }, [items, runtime]);

  const handleSearch = () => setKeyword(keywordInput.trim());

  const updateIncludeDemo = (next: boolean) => {
    setIncludeDemo(next);
    const params = new URLSearchParams(typeof window !== "undefined" ? window.location.search : "");
    if (next) params.set("include_demo", "true");
    else params.delete("include_demo");
    router.replace(`/stocks${params.toString() ? `?${params.toString()}` : ""}`);
  };

  return (
    <PageShell title="个股评分库" subtitle="真实评分样本优先展示，演示评分仅在主动切换后查看。">
      <SimulatedDataNotice
        title="研究口径说明"
        badges={[
          { label: `数据模式：${runtime?.data_mode_label || runtime?.data_mode || "待核验"}`, tone: runtime?.provider_mode === "mock" ? "simulated" : "database" },
          { label: `评分更新时间：${latestUpdate}`, tone: "database" },
          { label: "研究辅助系统 / 非投资建议", tone: "simulated" },
        ]}
        lines={[
          "真实评分样本表示已经由真实链路生成评分的股票；当前筛选结果表示当前条件下可展示的样本；演示评分默认隔离。",
          "研究评级仅表示研究优先级，不代表买卖指令。",
          runtime?.warning || "当数据不足时，页面会明确展示“数据质量受限”或“暂无数据”，不会用演示结果冒充正式结论。",
        ]}
      />

      {diagnostics ? (
        <div className="card space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">真实评分诊断摘要</h2>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                {sanitizeDisplayText(diagnostics.summary.message, "用于解释当前真实评分结构，不调整评分算法。")}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <DataStatusBadge label={`真实样本 ${diagnostics.summary.real_count}`} tone="live" />
              <DataStatusBadge label={`演示样本 ${diagnostics.summary.demo_count}`} tone="simulated" />
              <DataStatusBadge label={`评分日期 ${diagnostics.summary.score_date || "待核验"}`} tone="database" />
            </div>
          </div>
        </div>
      ) : null}

      {includeDemo ? (
        <div className="card-warning">
          <p className="text-sm font-medium">当前视图包含演示评分，仅用于功能体验，不代表正式研究结果。</p>
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatCard label="真实评分样本" value={summary ? String(summary.real_score_count || 0) : "--"} />
        <StatCard label="当前筛选结果" value={summary ? String(summary.current_result_count || 0) : "--"} />
        <StatCard label="当前页展示" value={summary ? String(summary.current_page_items_count ?? summary.current_page_count ?? 0) : "--"} />
        <StatCard label="正式研究样本" value={summary ? String(summary.formal_real_count || 0) : "--"} />
        <StatCard label="数据质量受限" value={summary ? String(summary.data_quality_limited_count || 0) : "--"} />
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatCard label="演示评分样本" value={summary ? String(summary.demo_score_count || 0) : "--"} />
        <StatCard label="最高真实评分" value={summary ? formatNumber(summary.real_highest_score ?? summary.highest_score, 0) : "--"} />
        <StatCard label="风险观察样本" value={summary ? String(summary.risk_elevated || 0) : "--"} />
        <StatCard label="A股样本" value={summary ? String(summary.a_share || 0) : "--"} />
        <StatCard label="港股样本" value={summary ? String(summary.hk || 0) : "--"} />
      </div>

      <div className="card flex flex-col gap-4 lg:flex-row lg:items-end">
        <div className="flex flex-wrap gap-2">
          {[
            { value: "", label: "全部" },
            { value: "A_SHARE", label: "A股" },
            { value: "HK", label: "港股" },
          ].map((option) => (
            <button
              key={option.value || "all"}
              onClick={() => setMarket(option.value)}
              className={`rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
                market === option.value ? "bg-primary-500 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap gap-2">
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
            查看演示评分
          </button>
        </div>

        <div className="min-w-[180px]">
          <label className="text-xs font-medium text-[var(--text-secondary)]">研究评级</label>
          <select
            value={rating}
            onChange={(event) => setRating(event.target.value)}
            className="mt-1 w-full rounded-xl border border-[var(--border-default)] bg-white px-3 py-2 text-sm text-[var(--text-primary)]"
          >
            {RATING_OPTIONS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1">
          <label className="text-xs font-medium text-[var(--text-secondary)]">搜索代码或名称</label>
          <div className="mt-1 flex gap-2">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
              <input
                value={keywordInput}
                onChange={(event) => setKeywordInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") handleSearch();
                }}
                placeholder="输入股票代码或中文名称"
                className="w-full rounded-xl border border-[var(--border-default)] bg-white py-2 pl-9 pr-3 text-sm text-[var(--text-primary)]"
              />
            </div>
            <button onClick={handleSearch} className="btn-primary px-4 py-2 text-sm">
              查询
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <SkeletonTable />
      ) : error ? (
        <div className="card py-12 text-center">
          <EmptyState message="个股评分库加载失败，请稍后重试。" description={error} />
          <button onClick={() => void fetchStocks()} className="btn-primary mt-4 px-5 py-2 text-sm">
            重新加载
          </button>
        </div>
      ) : !response || items.length === 0 ? (
        <div className="card py-12">
          <EmptyState message="当前筛选条件下暂无评分样本。" description="可以切换市场、研究评级或清空关键词后重新查看。" />
        </div>
      ) : (
        <>
          <div className="space-y-3 md:hidden">
            {items.map((item) => {
              const expanded = expandedSymbol === item.symbol;
              return (
                <div key={item.symbol} className="card space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <Link href={`/stocks/${item.symbol}`} className="font-semibold text-[var(--text-primary)] hover:text-primary-600">
                        {item.name}
                      </Link>
                      <p className="mt-1 font-mono text-xs text-[var(--text-secondary)]">{item.symbol}</p>
                    </div>
                    <DataStatusBadge label={statusText(item)} tone={statusTone(item)} />
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="text-xs text-[var(--text-secondary)]">市场</p>
                      <p className="mt-1">{marketLabel(item.market)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[var(--text-secondary)]">研究评级</p>
                      <p className="mt-1">{sanitizeDisplayText(item.rating_label || signalTypeLabel(item.rating || ""))}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[var(--text-secondary)]">综合评分</p>
                      <p className="mt-1">{scoreBrief(item)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[var(--text-secondary)]">最新价</p>
                      <p className="mt-1">{item.latest_close != null ? item.latest_close.toFixed(2) : "暂无"}</p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Link href={`/stocks/${item.symbol}`} className="btn-primary flex-1 px-4 py-2 text-center text-sm">
                      查看详情
                    </Link>
                    <button onClick={() => setExpandedSymbol(expanded ? null : item.symbol)} className="btn-secondary flex-1 px-4 py-2 text-sm">
                      {expanded ? "收起" : "展开"}
                    </button>
                  </div>
                  {expanded ? (
                    <div className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4 text-sm">
                      <div className="grid grid-cols-2 gap-3">
                        <div>质量：{item.quality_score ?? "暂无"}</div>
                        <div>估值：{item.valuation_score ?? "暂无"}</div>
                        <div>成长：{item.growth_score ?? "暂无"}</div>
                        <div>趋势：{item.trend_score ?? "暂无"}</div>
                        <div>风险：{item.risk_score ?? "暂无"}</div>
                        <div>来源：{scoreSourceLabel(item.score_source)}</div>
                      </div>
                      <p className="mt-3 text-xs text-[var(--text-secondary)]">{sanitizeDisplayText(item.primary_low_score_reason, "暂无补充说明。")}</p>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>

          <div className="card hidden overflow-x-auto md:block">
            <table className="w-full min-w-[980px] text-sm">
              <thead>
                <tr className="border-b border-[var(--border-default)]">
                  {["代码", "名称", "市场", "研究评级", "综合评分", "最新价", "数据状态", "操作"].map((header) => (
                    <th key={header} className="px-3 py-3 text-left text-xs font-semibold text-[var(--text-secondary)]">
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const expanded = expandedSymbol === item.symbol;
                  return (
                    <>
                      <tr key={item.symbol} className="border-b border-[var(--border-light)] align-top hover:bg-slate-50">
                        <td className="px-3 py-3 font-mono text-[13px] font-semibold text-[var(--text-primary)]">
                          <Link href={`/stocks/${item.symbol}`} className="hover:text-primary-600">
                            {item.symbol}
                          </Link>
                        </td>
                        <td className="px-3 py-3">
                          <Link href={`/stocks/${item.symbol}`} className="font-semibold text-[var(--text-primary)] hover:text-primary-600">
                            {item.name}
                          </Link>
                        </td>
                        <td className="px-3 py-3">{marketLabel(item.market)}</td>
                        <td className="px-3 py-3">{sanitizeDisplayText(item.rating_label || signalTypeLabel(item.rating || ""))}</td>
                        <td className="px-3 py-3 font-medium text-[var(--text-primary)]">{scoreBrief(item)}</td>
                        <td className="px-3 py-3">{item.latest_close != null ? item.latest_close.toFixed(2) : "暂无"}</td>
                        <td className="px-3 py-3">
                          <DataStatusBadge label={statusText(item)} tone={statusTone(item)} />
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-2">
                            <Link href={`/stocks/${item.symbol}`} className="text-sm font-medium text-primary-600 hover:text-primary-700">
                              查看详情
                            </Link>
                            <button
                              onClick={() => setExpandedSymbol(expanded ? null : item.symbol)}
                              className="inline-flex items-center gap-1 text-sm font-medium text-slate-600 hover:text-slate-900"
                            >
                              {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                              {expanded ? "收起" : "展开"}
                            </button>
                          </div>
                        </td>
                      </tr>
                      {expanded ? (
                        <tr className="border-b border-[var(--border-light)] bg-[var(--bg-surface)]">
                          <td colSpan={8} className="px-4 py-4">
                            <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
                              <div className="space-y-3">
                                <div className="grid grid-cols-2 gap-3 xl:grid-cols-5">
                                  <div className="rounded-xl border border-[var(--border-default)] bg-white p-3">质量：{item.quality_score ?? "暂无"}</div>
                                  <div className="rounded-xl border border-[var(--border-default)] bg-white p-3">估值：{item.valuation_score ?? "暂无"}</div>
                                  <div className="rounded-xl border border-[var(--border-default)] bg-white p-3">成长：{item.growth_score ?? "暂无"}</div>
                                  <div className="rounded-xl border border-[var(--border-default)] bg-white p-3">趋势：{item.trend_score ?? "暂无"}</div>
                                  <div className="rounded-xl border border-[var(--border-default)] bg-white p-3">风险：{item.risk_score ?? "暂无"}</div>
                                </div>
                                <div className="rounded-xl border border-[var(--border-default)] bg-white p-3">
                                  <p className="text-xs font-medium text-[var(--text-secondary)]">主要原因</p>
                                  <p className="mt-2 text-sm text-[var(--text-primary)]">
                                    {sanitizeDisplayText(item.primary_low_score_reason || item.reason_summary, "暂无补充说明。")}
                                  </p>
                                </div>
                              </div>
                              <div className="space-y-3">
                                <div className="rounded-xl border border-[var(--border-default)] bg-white p-3">
                                  <p className="text-xs font-medium text-[var(--text-secondary)]">补充信息</p>
                                  <div className="mt-2 space-y-2 text-sm text-[var(--text-primary)]">
                                    <p>数据状态：{statusText(item)}</p>
                                    <p>数据来源：{scoreSourceLabel(item.score_source)}</p>
                                    <p>更新时间：{item.updated_at || "暂无"}</p>
                                    <p>缺失字段：{item.blocking_reasons?.length ? item.blocking_reasons.join("、") : "暂无明显缺口"}</p>
                                  </div>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                  {(item.risk_flags || []).map((flag) => (
                                    <DataStatusBadge key={flag} label={sanitizeDisplayText(flag, dataStatusLabel(flag))} tone="warning" />
                                  ))}
                                  {item.display_tier ? (
                                    <DataStatusBadge label={displayTierLabel(item.display_tier)} tone={displayTierTone(item.display_tier)} />
                                  ) : null}
                                </div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </PageShell>
  );
}
