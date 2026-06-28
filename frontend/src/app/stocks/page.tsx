"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";

import PageShell from "@/components/layout/PageShell";
import EmptyState from "@/components/ui/EmptyState";
import SimulatedDataNotice from "@/components/ui/SimulatedDataNotice";
import { SkeletonTable } from "@/components/ui/Skeleton";
import { showToast } from "@/components/ui/Toast";
import { getRuntimeInfo, getStockLibrary } from "@/lib/api";
import {
  formatNumber,
  formatPercent,
  getChangeColor,
  humanizeReasonSummary,
  marketLabel,
  ratingClass,
  sanitizeDisplayText,
  signalTypeLabel,
} from "@/lib/utils";
import type { RuntimeInfo, StockLibraryItem, StockLibraryResponse } from "@/types";

const PAGE_SIZE = 50;
const RATING_OPTIONS = [
  { value: "", label: "全部研究评级" },
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

function RiskBadge({ label }: { label: string }) {
  const tone = label.includes("ST") || label.includes("退市") || label.includes("风险") ? "warning" : "neutral";
  const className =
    tone === "warning"
      ? "bg-red-50 text-red-700 border-red-200"
      : "bg-slate-100 text-slate-700 border-slate-200";
  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${className}`}>{label}</span>;
}

export default function StocksPage() {
  const [response, setResponse] = useState<StockLibraryResponse | null>(null);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [market, setMarket] = useState("");
  const [rating, setRating] = useState("");
  const [keywordInput, setKeywordInput] = useState("");
  const [keyword, setKeyword] = useState("");

  const fetchStocks = async () => {
    setLoading(true);
    setError(null);
    try {
      const [runtimeInfo, stockLibrary] = await Promise.all([
        getRuntimeInfo().catch(() => null),
        getStockLibrary({
          market: market || undefined,
          rating: rating || undefined,
          keyword: keyword || undefined,
          page: 1,
          page_size: PAGE_SIZE,
        }),
      ]);
      setRuntime(runtimeInfo);
      setResponse(stockLibrary);
    } catch (err: unknown) {
      const message =
        err instanceof Error && err.message.trim()
          ? err.message
          : "股票分析数据加载失败，请稍后重试。";
      setError(message);
      setResponse(null);
      showToast("error", message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchStocks();
  }, [market, rating, keyword]);

  const items = response?.items || [];
  const summary = response?.summary;
  const latestUpdate = useMemo(() => {
    return items.find((item) => item.updated_at)?.updated_at || runtime?.latest_updates?.scores || "待更新";
  }, [items, runtime]);

  const handleSearch = () => {
    setKeyword(keywordInput.trim());
  };

  return (
    <PageShell title="个股评分库" subtitle="基于五维评分模型的研究样本库，点击股票查看详情。">
      <SimulatedDataNotice
        title="研究口径说明"
        badges={[
          { label: `数据模式：${runtime?.data_mode || "待核验"}`, tone: runtime?.provider_mode === "mock" ? "simulated" : "database" },
          { label: `评分更新时间：${latestUpdate}`, tone: "database" },
          { label: "非投资建议", tone: "simulated" },
        ]}
        lines={[
          "页面列表来自真实股票、评分、信号与最新行情接口聚合结果，不使用前端写死样例。",
          "高关注、增强关注、观察、风险升高、回避观察仅代表研究优先级，不代表买卖指令。",
        ]}
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatCard label="有评分股票" value={summary ? summary.rated_stocks.toLocaleString() : "--"} />
        <StatCard label="A 股样本" value={summary ? summary.a_share.toLocaleString() : "--"} />
        <StatCard label="港股样本" value={summary ? summary.hk.toLocaleString() : "--"} />
        <StatCard label="最高综合评分" value={summary ? formatNumber(summary.highest_score, 0) : "--"} />
        <StatCard label="风险升高/回避观察" value={summary ? summary.risk_elevated.toLocaleString() : "--"} />
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
                placeholder="输入股票代码或名称"
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
          <EmptyState message="股票分析数据加载失败，请稍后重试。" description={error} />
          <button onClick={() => void fetchStocks()} className="btn-primary mt-4 px-5 py-2 text-sm">
            重新加载
          </button>
        </div>
      ) : !response || items.length === 0 ? (
        <div className="card py-12">
          <EmptyState
            message="当前筛选条件下暂无评分样本。"
            description="可以切换市场、研究评级，或清空关键词后重新查看。"
          />
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[1280px] text-sm">
            <thead>
              <tr className="border-b border-[var(--border-default)]">
                {["代码", "名称", "市场", "研究评级", "综合评分", "质量", "估值", "成长", "趋势", "风险", "最新价", "涨跌", "更新时间", "风险标签", "操作"].map((header) => (
                  <th key={header} className="px-3 py-3 text-left text-xs font-semibold text-[var(--text-secondary)]">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item: StockLibraryItem) => {
                const detailHref = `/stocks/${item.symbol}`;
                return (
                  <tr key={`${item.symbol}-${item.updated_at || "latest"}`} className="border-b border-[var(--border-light)] align-top hover:bg-slate-50">
                    <td className="px-3 py-3 font-mono text-[13px] font-semibold text-[var(--text-primary)]">
                      <Link href={detailHref} className="hover:text-primary-600">
                        {item.symbol}
                      </Link>
                    </td>
                    <td className="px-3 py-3">
                      <Link href={detailHref} className="font-semibold text-[var(--text-primary)] hover:text-primary-600">
                        {sanitizeDisplayText(item.name, item.symbol)}
                      </Link>
                    </td>
                    <td className="px-3 py-3 text-[var(--text-body)]">{marketLabel(item.market)}</td>
                    <td className="px-3 py-3">
                      <span className={item.rating ? ratingClass(item.rating) : "rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-500"}>
                        {item.rating_label || "暂缺"}
                      </span>
                    </td>
                    <td className="px-3 py-3 font-semibold text-[var(--text-primary)]">{item.total_score ?? "暂缺"}</td>
                    <td className="px-3 py-3 text-[var(--text-body)]">{item.quality_score ?? "暂缺"}</td>
                    <td className="px-3 py-3 text-[var(--text-body)]">{item.valuation_score ?? "暂缺"}</td>
                    <td className="px-3 py-3 text-[var(--text-body)]">{item.growth_score ?? "暂缺"}</td>
                    <td className="px-3 py-3 text-[var(--text-body)]">{item.trend_score ?? "暂缺"}</td>
                    <td className="px-3 py-3 text-[var(--text-body)]">{item.risk_score ?? "暂缺"}</td>
                    <td className="px-3 py-3 font-mono text-[var(--text-primary)]">
                      {item.latest_close !== null && item.latest_close !== undefined ? formatNumber(item.latest_close) : "暂缺"}
                    </td>
                    <td className={`px-3 py-3 font-mono ${getChangeColor(item.change_pct)}`}>{formatPercent(item.change_pct)}</td>
                    <td className="px-3 py-3 text-[var(--text-body)]">{item.updated_at || "暂缺"}</td>
                    <td className="px-3 py-3">
                      <div className="flex max-w-[220px] flex-wrap gap-1">
                        {(item.risk_flags && item.risk_flags.length > 0 ? item.risk_flags : ["暂无显著标签"]).slice(0, 3).map((flag) => (
                          <RiskBadge key={`${item.symbol}-${flag}`} label={sanitizeDisplayText(flag, "风险提示")} />
                        ))}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <div className="space-y-1">
                        <Link href={detailHref} className="inline-flex text-xs font-semibold text-primary-600 hover:text-primary-700">
                          查看详情
                        </Link>
                        <p className="max-w-[200px] text-xs leading-5 text-[var(--text-secondary)]">
                          {humanizeReasonSummary(
                            item.reason_summary,
                            `${signalTypeLabel(item.signal_type || item.rating || "")}，详情页可查看评分追溯。`
                          )}
                        </p>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="disclaimer">本系统仅用于研究和辅助分析，不构成任何投资建议。</div>
    </PageShell>
  );
}
