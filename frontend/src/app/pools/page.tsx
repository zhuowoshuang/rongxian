"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";

import PageShell from "@/components/layout/PageShell";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonTable } from "@/components/ui/Skeleton";
import DataStatusBadge from "@/components/ui/DataStatusBadge";
import { showToast } from "@/components/ui/Toast";
import { getStockPool } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import { humanizePoolReason, marketLabel, signalTypeLabel } from "@/lib/utils";
import type { PoolResponse, PoolItem } from "@/types";

const poolTypeConfig = [
  { key: "quality", color: "bg-emerald-500", label: "优质基本面池" },
  { key: "undervalued", color: "bg-blue-500", label: "低估值池" },
  { key: "trend", color: "bg-purple-500", label: "趋势确认池" },
  { key: "risk", color: "bg-red-500", label: "风险预警池" },
  { key: "steady", color: "bg-cyan-500", label: "稳健优选" },
  { key: "aggressive", color: "bg-fuchsia-500", label: "进取优选" },
  { key: "conservative", color: "bg-lime-500", label: "保守优选" },
  { key: "volatile", color: "bg-orange-500", label: "周波动>2%" },
];

export default function PoolsPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const [activeType, setActiveType] = useState("quality");
  const [data, setData] = useState<PoolResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filterText, setFilterText] = useState("");

  const fetchData = () => {
    setLoading(true);
    setError("");
    getStockPool(activeType)
      .then(setData)
      .catch((err: Error) => {
        setError(err.message || t("common.loadFailed"));
        showToast("error", err.message || t("common.loadFailed"));
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, [activeType]);

  // 前端过滤（在已返回的 70 条内搜索）
  const filteredItems = useMemo(() => {
    if (!data?.items) return [];
    if (!filterText.trim()) return data.items;
    const q = filterText.toLowerCase();
    return data.items.filter(
      (item: PoolItem) =>
        item.symbol.toLowerCase().includes(q) ||
        item.name.toLowerCase().includes(q) ||
        (item.industry || "").toLowerCase().includes(q)
    );
  }, [data?.items, filterText]);

  const poolLabel = poolTypeConfig.find((p) => p.key === activeType)?.label || activeType;

  return (
    <PageShell
      title="策略股票池"
      subtitle="各股票池来自后端真实筛选规则与数据库评分结果，用于研究分层与观察排序"
    >
      {/* 池子切换按钮 */}
      <div className="flex gap-2 flex-wrap">
        {poolTypeConfig.map((item) => (
          <button
            key={item.key}
            onClick={() => { setActiveType(item.key); setFilterText(""); }}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all border ${
              activeType === item.key
                ? "bg-primary-50 border-primary-300 text-primary-700 font-semibold shadow-sm"
                : "bg-white border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--bg-surface)] hover:border-primary-200"
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${item.color}`} />
            {item.label}
          </button>
        ))}
      </div>

      {/* 当前池子说明条 */}
      <div className="card-info flex flex-wrap items-center gap-3">
        <span className="text-sm font-semibold">{poolLabel}</span>
        <DataStatusBadge label={`评分日期：${data?.date || "待更新"}`} tone="database" />
        <DataStatusBadge label="基于研究评分规则" tone="database" />
        <DataStatusBadge label="非投资建议" tone="simulated" />
        {data?.has_more && (
          <span className="text-caption">当前仅展示该策略池前 {data.count} 个研究样本</span>
        )}
      </div>

      {/* 搜索框 */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)] pointer-events-none" />
        <input
          type="text"
          value={filterText}
          onChange={(e) => setFilterText(e.target.value)}
          placeholder="按代码、名称、行业搜索当前池子..."
          className="w-full search-input"
        />
      </div>

      {/* 股票表格 */}
      {loading ? (
        <SkeletonTable rows={8} cols={8} />
      ) : error ? (
        <div className="card p-8 text-center">
          <p className="text-body">{error}</p>
          <p className="text-caption mt-2">股票池数据暂时加载失败，请确认后端服务可用后重试。</p>
          <button onClick={fetchData} className="btn-primary px-4 py-2 mt-4 text-sm">重新加载</button>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="card">
          <EmptyState
            message={filterText ? "没有匹配的股票" : "当前股票池暂无可展示样本"}
            description={filterText ? "请尝试其他关键词" : "这通常表示现有规则下暂无匹配记录，或评分数据尚未完成刷新。"}
          />
        </div>
      ) : (
        <div className="card !p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th>代码</th>
                  <th>名称</th>
                  <th>市场</th>
                  <th>行业</th>
                  <th className="text-right">综合评分</th>
                  <th>研究评级</th>
                  <th className="text-right">质量</th>
                  <th className="text-right">估值</th>
                  <th className="text-right">成长</th>
                  <th className="text-right">趋势</th>
                  <th className="text-right">风险</th>
                  <th className="text-right">最新价</th>
                  <th>入池原因</th>
                  <th>风险标签</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item) => {
                  const highRisk = item.risk_flags?.some((flag: string) => /ST|delist|退市|高波动/i.test(flag));
                  return (
                    <tr
                      key={item.symbol}
                      className={`cursor-pointer transition-colors ${highRisk ? "bg-red-50/50" : ""}`}
                      onClick={() => router.push(`/stocks/${item.symbol}`)}
                    >
                      <td>
                        <span className="font-mono text-primary-600 font-semibold hover:underline">
                          {item.symbol}
                        </span>
                      </td>
                      <td>
                        <span className="font-semibold text-[var(--text-primary)] hover:text-primary-600 hover:underline">
                          {item.name}
                        </span>
                      </td>
                      <td>
                        <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                          item.market === "A_SHARE" ? "bg-blue-50 text-blue-700" : "bg-purple-50 text-purple-700"
                        }`}>
                          {marketLabel(item.market)}
                        </span>
                      </td>
                      <td className="text-[var(--text-secondary)]">{item.industry || "-"}</td>
                      <td className="text-right">
                        <span className="font-mono font-bold text-[var(--text-primary)]">
                          {item.total_score?.toFixed(0)}
                        </span>
                      </td>
                      <td>
                        <span className={`signal-${item.rating?.toLowerCase() || "watch"}`}>
                          {signalTypeLabel(item.rating)}
                        </span>
                      </td>
                      <td className="text-right font-mono text-[var(--text-body)]">{item.quality_score?.toFixed(0)}</td>
                      <td className="text-right font-mono text-[var(--text-body)]">{item.valuation_score?.toFixed(0)}</td>
                      <td className="text-right font-mono text-[var(--text-body)]">{item.growth_score?.toFixed(0)}</td>
                      <td className="text-right font-mono text-[var(--text-body)]">{item.trend_score?.toFixed(0)}</td>
                      <td className="text-right font-mono text-[var(--text-body)]">{item.risk_score?.toFixed(0)}</td>
                      <td className="text-right font-mono text-[var(--text-body)]">{item.latest_close?.toFixed(2) || "-"}</td>
                      <td className="max-w-[200px]">
                        <span className="text-caption line-clamp-2" title={item.reason || ""}>
                          {humanizePoolReason(item.reason, "当前标的进入该策略池，详情页可继续查看评分与风险追溯。")}
                        </span>
                      </td>
                      <td>
                        <div className="flex flex-wrap gap-1">
                          {(item.risk_flags || []).map((flag: string) => (
                            <DataStatusBadge
                              key={flag}
                              label={flag}
                              tone={/ST|delist|退市|高波动/i.test(flag) ? "warning" : "database"}
                            />
                          ))}
                        </div>
                      </td>
                      <td>
                        <button
                          onClick={(e) => { e.stopPropagation(); router.push(`/stocks/${item.symbol}`); }}
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

      {/* 入池规则解释（表格下方） */}
      {!loading && data?.meta && (
        <div className="card">
          <h3 className="text-h3 mb-4">入池规则与风险说明</h3>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="card-inner">
              <p className="text-caption font-semibold mb-2">入池规则</p>
              <div className="space-y-2">
                {data.meta.rules?.map((rule: string) => (
                  <p key={rule} className="text-body text-sm">• {rule}</p>
                ))}
              </div>
            </div>
            <div className="card-inner">
              <p className="text-caption font-semibold mb-2">适合研究场景</p>
              <p className="text-body text-sm">{data.meta.scenario || "暂无说明"}</p>
              <p className="text-caption font-semibold mt-3 mb-2 text-[var(--color-warning)]">主要风险</p>
              <div className="space-y-1">
                {data.meta.risks?.map((risk: string) => (
                  <p key={risk} className="text-sm text-[var(--color-warning)]">• {risk}</p>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-[var(--border-light)]">
            <p className="text-caption">
              数据截至 {data.meta.data_updated_at || "待更新"} · 基于研究评分规则 · 非投资建议输出
            </p>
          </div>
        </div>
      )}

      <div className="disclaimer">{t("app.disclaimer")}</div>
    </PageShell>
  );
}
