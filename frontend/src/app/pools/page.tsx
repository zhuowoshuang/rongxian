"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Search } from "lucide-react";

import PageShell from "@/components/layout/PageShell";
import DataStatusBadge from "@/components/ui/DataStatusBadge";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonTable } from "@/components/ui/Skeleton";
import { showToast } from "@/components/ui/Toast";
import { getStockPool } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import { humanizePoolReason, marketLabel, signalTypeLabel } from "@/lib/utils";
import type { PoolItem, PoolResponse } from "@/types";

const poolTypeConfig = [
  { key: "quality", color: "bg-emerald-500", label: "优质基本面池" },
  { key: "undervalued", color: "bg-blue-500", label: "低估值池" },
  { key: "trend", color: "bg-purple-500", label: "趋势确认池" },
  { key: "risk", color: "bg-red-500", label: "风险预警池" },
  { key: "steady", color: "bg-cyan-500", label: "稳健优选" },
  { key: "aggressive", color: "bg-fuchsia-500", label: "进取优选" },
  { key: "conservative", color: "bg-lime-500", label: "保守优选" },
  { key: "volatile", color: "bg-orange-500", label: "周波动 > 2%" },
];

export default function PoolsPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [activeType, setActiveType] = useState("quality");
  const [includeDemo, setIncludeDemoState] = useState(searchParams.get("include_demo") !== "false");
  const [data, setData] = useState<PoolResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterText, setFilterText] = useState("");

  const setIncludeDemo = (next: boolean) => {
    setIncludeDemoState(next);
    const params = new URLSearchParams(searchParams.toString());
    if (next) params.set("include_demo", "true");
    else params.delete("include_demo");
    router.replace(`/pools${params.toString() ? `?${params.toString()}` : ""}`, { scroll: false });
  };

  useEffect(() => {
    setIncludeDemoState(searchParams.get("include_demo") === "true");
  }, [searchParams]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getStockPool(activeType, includeDemo);
      setData(result);
    } catch (error) {
      const message = error instanceof Error ? error.message : "股票池加载失败，请稍后重试。";
      setError(message);
      showToast("error", message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchData();
  }, [activeType, includeDemo]);

  const filteredItems = useMemo(() => {
    if (!data?.items) return [];
    if (!filterText.trim()) return data.items;
    const query = filterText.toLowerCase();
    return data.items.filter(
      (item: PoolItem) =>
        item.symbol.toLowerCase().includes(query) ||
        item.name.toLowerCase().includes(query) ||
        (item.industry || "").toLowerCase().includes(query),
    );
  }, [data?.items, filterText]);

  const poolLabel = poolTypeConfig.find((item) => item.key === activeType)?.label || activeType;

  return (
    <PageShell title="策略股票池" subtitle="基于真实筛选规则的研究样本池，空池会明确解释原因，不再伪装成无数据。">
      <div className="flex flex-wrap gap-2">
        {poolTypeConfig.map((item) => (
          <button
            key={item.key}
            onClick={() => {
              setActiveType(item.key);
              setFilterText("");
            }}
            className={`flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-medium transition-all ${
              activeType === item.key
                ? "border-primary-300 bg-primary-50 font-semibold text-primary-700 shadow-sm"
                : "border-[var(--border-default)] bg-white text-[var(--text-secondary)] hover:border-primary-200 hover:bg-[var(--bg-surface)]"
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${item.color}`} />
            {item.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setIncludeDemo(false)}
          className={`rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
            includeDemo ? "bg-slate-100 text-slate-700 hover:bg-slate-200" : "bg-primary-500 text-white"
          }`}
        >
          仅看正式股票池
        </button>
        <button
          onClick={() => setIncludeDemo(true)}
          className={`rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
            includeDemo ? "bg-primary-500 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          包含演示样本
        </button>
      </div>

      <div className="card-info flex flex-wrap items-center gap-3">
        <span className="text-sm font-semibold">{poolLabel}</span>
        <DataStatusBadge label={`评分日期：${data?.date || "待更新"}`} tone="database" />
        <DataStatusBadge label="基于研究评分规则" tone="database" />
        <DataStatusBadge label={includeDemo ? "演示口径 / 非正式研究结果" : "研究口径 / 非投资建议"} tone={includeDemo ? "simulated" : "database"} />
        <span className="text-caption">当前展示前 {data?.meta?.display_limit || data?.count || 30} 个研究样本</span>
      </div>

      {data?.meta?.warning ? (
        <div className="card-warning">
          <p className="text-sm">{data.meta.warning}</p>
        </div>
      ) : null}

      {data?.diagnostics ? (
        <div className="card">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-[var(--text-primary)]">当前股票池形成状态</h2>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                {data.message || "当前页面只展示达到正式研究池门槛的样本；如果为空，通常表示真实样本仍在风险观察或数据质量受限阶段。"}
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              <DataStatusBadge label={`真实评分样本 ${data.diagnostics.real_score_count || 0}`} tone="live" />
              <DataStatusBadge label={`正式研究样本 ${data.diagnostics.formal_real_count || 0}`} tone="live" />
              <DataStatusBadge label={`风险观察样本 ${data.diagnostics.real_observation_count || 0}`} tone="warning" />
              <DataStatusBadge label={`演示评分样本 ${data.diagnostics.demo_score_count || 0}`} tone="simulated" />
            </div>
          </div>
        </div>
      ) : null}

      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
        <input
          type="text"
          value={filterText}
          onChange={(event) => setFilterText(event.target.value)}
          placeholder="按代码、名称或行业搜索当前池"
          className="w-full search-input"
        />
      </div>

      {loading ? (
        <SkeletonTable rows={8} cols={8} />
      ) : error ? (
        <div className="card p-8 text-center">
          <p className="text-body">{error}</p>
          <p className="mt-2 text-caption">股票池数据暂时加载失败，请确认后端服务可用后重试。</p>
          <button onClick={() => void fetchData()} className="btn-primary mt-4 px-4 py-2 text-sm">
            重新加载
          </button>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="card">
          <EmptyState
            message={filterText ? "没有匹配的股票" : "当前股票池暂无可正式展示的样本"}
            description={
              filterText
                ? "请尝试其他关键词。"
                : data?.message || "真实评分样本已接入，但当前样本多处于风险观察或数据质量受限状态，尚未达到该股票池门槛。"
            }
          />
          {!filterText ? (
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              <button onClick={() => router.push("/stocks")} className="btn-secondary px-4 py-2 text-sm">
                查看真实评分库
              </button>
              <button onClick={() => router.push("/signals")} className="btn-secondary px-4 py-2 text-sm">
                查看风险观察样本
              </button>
              <button
                onClick={() => setIncludeDemo(true)}
                className="btn-primary px-4 py-2 text-sm"
              >
                查看演示股票池
              </button>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="card !p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th>代码</th>
                  <th>名称</th>
                  <th className="w-[76px]">市场</th>
                  <th>行业</th>
                  <th className="text-right">综合评分</th>
                  <th className="w-[104px]">研究评级</th>
                  <th className="text-right">质量</th>
                  <th className="text-right">估值</th>
                  <th className="text-right">成长</th>
                  <th className="text-right">趋势</th>
                  <th className="text-right">风险</th>
                  <th className="text-right">最新价</th>
                  <th>入池原因</th>
                  <th className="w-[180px]">风险标签</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item) => {
                  const highRisk = item.risk_flags?.some((flag: string) => /ST|退市|高波动|风险/i.test(flag));
                  return (
                    <tr
                      key={item.symbol}
                      className={`cursor-pointer transition-colors ${highRisk ? "bg-red-50/50" : ""}`}
                      onClick={() => router.push(`/stocks/${item.symbol}`)}
                    >
                      <td>
                        <span className="font-mono font-semibold text-primary-600 hover:underline">{item.symbol}</span>
                      </td>
                      <td>
                        <span className="font-semibold text-[var(--text-primary)] hover:text-primary-600 hover:underline">{item.name}</span>
                      </td>
                      <td className="w-[76px]">
                        <span className={`rounded px-2 py-0.5 text-xs font-medium ${item.market === "A_SHARE" ? "bg-blue-50 text-blue-700" : "bg-purple-50 text-purple-700"}`}>
                          {marketLabel(item.market)}
                        </span>
                      </td>
                      <td className="text-[var(--text-secondary)]">{item.industry || "-"}</td>
                      <td className="text-right font-mono font-bold text-[var(--text-primary)]">{item.total_score?.toFixed(0)}</td>
                      <td className="w-[104px]">
                        <span className={`signal-${item.rating?.toLowerCase() || "watch"}`}>{signalTypeLabel(item.rating)}</span>
                      </td>
                      <td className="text-right font-mono text-[var(--text-body)]">{item.quality_score?.toFixed(0)}</td>
                      <td className="text-right font-mono text-[var(--text-body)]">{item.valuation_score?.toFixed(0)}</td>
                      <td className="text-right font-mono text-[var(--text-body)]">{item.growth_score?.toFixed(0)}</td>
                      <td className="text-right font-mono text-[var(--text-body)]">{item.trend_score?.toFixed(0)}</td>
                      <td className="text-right font-mono text-[var(--text-body)]">{item.risk_score?.toFixed(0)}</td>
                      <td className="text-right font-mono text-[var(--text-body)]">{item.latest_close?.toFixed(2) || "-"}</td>
                      <td className="max-w-[220px]">
                        <span className="line-clamp-2 text-caption" title={item.reason || ""}>
                          {humanizePoolReason(item.reason, "当前标的进入该股票池，详情页可继续查看评分与风险追溯。")}
                        </span>
                      </td>
                      <td className="w-[180px]">
                        <div className="flex max-w-[180px] flex-wrap gap-1">
                          {(item.risk_flags || []).slice(0, 3).map((flag: string) => (
                            <DataStatusBadge key={flag} label={flag} tone={/ST|退市|高波动|风险/i.test(flag) ? "warning" : "database"} />
                          ))}
                          {(item.risk_flags || []).length > 3 ? (
                            <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-500">+{(item.risk_flags || []).length - 3}</span>
                          ) : null}
                        </div>
                      </td>
                      <td>
                        <button
                          onClick={(event) => {
                            event.stopPropagation();
                            router.push(`/stocks/${item.symbol}`);
                          }}
                          className="btn-ghost !px-3 !py-1.5 text-xs"
                        >
                          详情
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data?.meta ? (
        <div className="card">
          <h3 className="mb-4 text-h3">入池规则与风险说明</h3>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="card-inner">
              <p className="mb-2 text-caption font-semibold">池子定位</p>
              <p className="text-sm text-body">{data.meta.positioning || "暂无说明"}</p>
              <p className="mb-2 mt-4 text-caption font-semibold">主要筛选条件</p>
              <div className="space-y-2">
                {data.meta.rules?.map((rule: string) => (
                  <p key={rule} className="text-sm text-body">- {rule}</p>
                ))}
              </div>
            </div>
            <div className="card-inner">
              <p className="mb-2 text-caption font-semibold">适合研究场景</p>
              <p className="text-sm text-body">{data.meta.scenario || "暂无说明"}</p>
              <p className="mb-2 mt-4 text-caption font-semibold text-[var(--color-warning)]">主要风险</p>
              <div className="space-y-1">
                {data.meta.risks?.map((risk: string) => (
                  <p key={risk} className="text-sm text-[var(--color-warning)]">- {risk}</p>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-4 border-t border-[var(--border-light)] pt-4">
            <p className="text-caption">数据截至 {data.meta.data_updated_at || "待更新"}，基于研究评分规则生成，不构成投资建议。</p>
          </div>
        </div>
      ) : null}

      <div className="disclaimer">{t("app.disclaimer")}</div>
    </PageShell>
  );
}
