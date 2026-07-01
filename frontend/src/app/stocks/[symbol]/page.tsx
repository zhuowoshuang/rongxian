"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import TopSearch from "@/components/TopSearch";
import ScoreBreakdown from "@/components/ScoreBreakdown";
import CandlestickChart from "@/components/charts/CandlestickChart";
import GlassCard from "@/components/ui/GlassCard";
import DataStatusBadge from "@/components/ui/DataStatusBadge";
import SimulatedDataNotice from "@/components/ui/SimulatedDataNotice";
import { SkeletonCard } from "@/components/ui/Skeleton";
import TabSwitch from "@/components/ui/TabSwitch";
import ChartTooltip from "@/components/ui/ChartTooltip";
import { getStockDetail } from "@/lib/api";
import {
  displayTierLabel,
  displayTierTone,
  formatPercent,
  marketLabel,
  readinessLabel,
  sanitizeDisplayText,
  signalTypeClass,
  signalTypeLabel,
} from "@/lib/utils";
import type { StockDetail } from "@/types";

type TabKey = "overview" | "financial" | "score" | "signal" | "reports";

function statusRows(data: StockDetail) {
  return [
    { label: "行情数据", value: data.latest_price ? "有" : "暂无" },
    { label: "财务数据", value: data.financial_metrics?.length ? `${data.financial_metrics.length} 期` : "暂无" },
    { label: "技术指标", value: data.technical_indicators ? "有" : "暂无" },
    { label: "真实评分", value: data.score ? "有" : "暂无" },
    { label: "报告摘要", value: data.reports?.length ? "有" : "无" },
  ];
}

export default function StockDetailPage() {
  const params = useParams();
  const router = useRouter();
  const symbol = String(params.symbol || "");
  const [data, setData] = useState<StockDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [chartMode, setChartMode] = useState<"kline" | "line">("kline");

  const canRenderKline = data?.price_data_quality?.can_render_kline === true;

  useEffect(() => {
    if (!data) return;
    setChartMode(data.price_data_quality?.can_render_kline ? "kline" : "line");
  }, [data]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const nextData = await getStockDetail(symbol);
        setData(nextData);
      } catch (err) {
        setData(null);
        setError(err instanceof Error ? err.message : "个股详情加载失败");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [symbol]);

  const hasNoData = Boolean(
    data &&
      !data.latest_price &&
      (!data.price_history || data.price_history.length === 0) &&
      !data.score
  );

  const isNotFound = /未找到|not found|404/i.test(error);
  const isTimeout = /超时|timeout|network|服务/i.test(error);
  const latestClose = data?.latest_price?.close;
  const previousClose = data?.price_history?.length && data.price_history.length > 1 ? data.price_history[data.price_history.length - 2]?.close : null;
  const changePct = useMemo(() => {
    if (typeof latestClose === "number" && typeof previousClose === "number" && previousClose !== 0) {
      return ((latestClose - previousClose) / previousClose) * 100;
    }
    return null;
  }, [latestClose, previousClose]);

  const tabs = [
    { key: "overview", label: "概览" },
    { key: "financial", label: "财务" },
    { key: "score", label: "评分" },
    { key: "signal", label: "信号" },
    { key: "reports", label: "报告" },
  ] as const;

  if (loading) {
    return (
      <div className="mx-auto max-w-[1280px] space-y-6 p-6">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-[900px] p-6" style={{ background: "var(--bg-page)" }}>
        <TopSearch />
        <div className="card mt-6 py-12 text-center">
          <p className="mb-2 text-h3">{isNotFound ? "未找到该股票" : isTimeout ? "请求超时，请检查后端服务状态。" : "该股票详情暂时不可用"}</p>
          <p className="text-caption">{error || "请检查股票代码、登录状态或后端服务状态。"}</p>
          <div className="mt-4 flex justify-center gap-3">
            <button onClick={() => router.push("/stocks")} className="btn-secondary px-4 py-2 text-sm">返回股票库</button>
            <button onClick={() => router.push("/stocks/002415")} className="btn-secondary px-4 py-2 text-sm">查看海康威视</button>
            <button onClick={() => router.push("/stocks/600519")} className="btn-secondary px-4 py-2 text-sm">查看贵州茅台</button>
          </div>
        </div>
      </div>
    );
  }

  if (hasNoData) {
    return (
      <div className="mx-auto max-w-[980px] p-6" style={{ background: "var(--bg-page)" }}>
        <TopSearch />
        <div className="card mt-6 space-y-6 py-10">
          <div className="text-center">
            <p className="mb-2 text-h3">该股票暂无可展示的行情与评分数据</p>
            <p className="text-caption mt-2">
              {sanitizeDisplayText(data.stock.name)}（{data.stock.symbol}）已在股票基础库中，但当前暂无行情、财务、技术指标或真实评分数据。
              这不代表系统错误，而是该股票尚未进入当前真实数据覆盖范围。
            </p>
            {data.reports?.length ? <p className="mt-3 text-sm text-[var(--text-secondary)]">该股票已有数据状态报告，但个股详情链路尚未补齐。</p> : null}
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            {statusRows(data).map((item) => (
              <div key={item.label} className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4 text-center text-sm">
                {item.label}：{item.value}
              </div>
            ))}
          </div>

          <div className="flex flex-wrap justify-center gap-2">
            <button onClick={() => router.push("/stocks")} className="btn-secondary px-4 py-2 text-sm">返回股票库</button>
            <button onClick={() => router.push("/stocks/002415")} className="btn-secondary px-4 py-2 text-sm">查看海康威视</button>
            <button onClick={() => router.push("/stocks/600519")} className="btn-secondary px-4 py-2 text-sm">查看贵州茅台</button>
            <button onClick={() => router.push("/reports")} className="btn-secondary px-4 py-2 text-sm">查看已有报告</button>
            <button onClick={() => router.push("/stocks?include_demo=true")} className="btn-primary px-4 py-2 text-sm">查看演示数据</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1320px] space-y-6 p-6" style={{ background: "var(--bg-page)" }}>
      <TopSearch />

      <GlassCard>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-bold text-[var(--text-heading)]">{sanitizeDisplayText(data.stock.name)}</h1>
              <span className="font-mono text-sm font-semibold text-[var(--text-secondary)]">{data.stock.symbol}</span>
              <DataStatusBadge label={marketLabel(data.stock.market)} tone="database" />
              <DataStatusBadge label={readinessLabel(data.data_readiness?.readiness_level)} tone={displayTierTone(data.data_readiness?.readiness_level)} />
              {data.score?.score_source ? <DataStatusBadge label={sanitizeDisplayText(data.score.score_label, "待核验")} tone={data.score.score_source === "real_calculated" ? "live" : "simulated"} /> : null}
            </div>
            <p className="text-sm text-[var(--text-secondary)]">
              {sanitizeDisplayText(data.stock.industry || "暂无行业标签")}
              {data.stock.exchange ? ` · ${data.stock.exchange}` : ""}
            </p>
          </div>

          <div className="text-right">
            <p className="font-mono text-4xl font-bold text-primary-500">{latestClose != null ? latestClose.toFixed(2) : "暂无"}</p>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">{changePct != null ? formatPercent(changePct) : "暂无涨跌幅"}</p>
          </div>
        </div>

        <div className="mt-4">
          <SimulatedDataNotice
            title="数据状态说明"
            badges={[
              { label: `行情更新 ${data.latest_updates?.price || "暂无"}`, tone: "database" },
              { label: `财务更新 ${data.latest_updates?.financial || "暂无"}`, tone: "database" },
              { label: "研究辅助系统 / 非投资建议", tone: "simulated" },
            ]}
            lines={[
              data.diagnostics?.blocking_reasons?.length ? `当前仍需补齐：${data.diagnostics.blocking_reasons.join("、")}。` : "当前详情以数据库真实链路结果为准。",
              "无评分或无价格时会直接显示数据不足，不再误报成请求超时。",
              data.reports?.length ? "该股票已有可查看报告摘要。" : "当前暂无关联报告摘要。",
            ]}
          />
        </div>
      </GlassCard>

      <TabSwitch tabs={tabs as unknown as Array<{ key: string; label: string }>} active={activeTab} onChange={(key) => setActiveTab(key as TabKey)} />

      {activeTab === "overview" ? (
        <>
          <GlassCard
            title="行情走势"
            action={
              canRenderKline ? (
                <div className="flex rounded-lg border border-[var(--border-default)] overflow-hidden text-xs">
                  <button
                    onClick={() => setChartMode("kline")}
                    className={`px-3 py-1.5 font-medium transition-colors ${
                      chartMode === "kline"
                        ? "bg-primary-500 text-white"
                        : "bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    K线
                  </button>
                  <button
                    onClick={() => setChartMode("line")}
                    className={`px-3 py-1.5 font-medium transition-colors ${
                      chartMode === "line"
                        ? "bg-primary-500 text-white"
                        : "bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    收盘价
                  </button>
                </div>
              ) : undefined
            }
          >
            {data.price_history?.length ? (
              canRenderKline && chartMode === "kline" ? (
                <CandlestickChart data={data.price_history} />
              ) : (
                <div className="h-[340px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data.price_history}>
                      <CartesianGrid stroke="#E2E8F0" />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748B" }} interval="preserveStartEnd" />
                      <YAxis tick={{ fontSize: 10, fill: "#64748B" }} />
                      <Tooltip content={<ChartTooltip />} />
                      <Line type="monotone" dataKey="close" stroke="#0F766E" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )
            ) : (
              <div className="py-12 text-center text-[var(--text-secondary)]">当前没有可展示的价格走势数据。</div>
            )}
          </GlassCard>

          <GlassCard title="关键状态">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              {statusRows(data).map((item) => (
                <div key={item.label} className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4 text-center text-sm">
                  <p className="text-xs text-[var(--text-secondary)]">{item.label}</p>
                  <p className="mt-2 font-semibold text-[var(--text-primary)]">{item.value}</p>
                </div>
              ))}
            </div>
          </GlassCard>
        </>
      ) : null}

      {activeTab === "financial" ? (
        <GlassCard title="财务概览">
          {data.financial_metrics?.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border-default)]">
                    {["期间", "营收", "营收同比", "净利润", "净利润同比", "毛利率", "ROE", "负债率"].map((header) => (
                      <th key={header} className="px-3 py-3 text-left text-xs text-[var(--text-secondary)]">{header}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.financial_metrics.map((item) => (
                    <tr key={item.period} className="border-b border-[var(--border-light)]">
                      <td className="px-3 py-3">{item.period}</td>
                      <td className="px-3 py-3">{item.revenue ?? "暂无"}</td>
                      <td className="px-3 py-3">{item.revenue_yoy != null ? formatPercent(item.revenue_yoy) : "暂无"}</td>
                      <td className="px-3 py-3">{item.net_profit ?? "暂无"}</td>
                      <td className="px-3 py-3">{item.net_profit_yoy != null ? formatPercent(item.net_profit_yoy) : "暂无"}</td>
                      <td className="px-3 py-3">{item.gross_margin != null ? formatPercent(item.gross_margin) : "暂无"}</td>
                      <td className="px-3 py-3">{item.roe != null ? formatPercent(item.roe) : "暂无"}</td>
                      <td className="px-3 py-3">{item.debt_ratio != null ? formatPercent(item.debt_ratio) : "暂无"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-10 text-center text-[var(--text-secondary)]">当前暂无财务数据。</div>
          )}
        </GlassCard>
      ) : null}

      {activeTab === "score" ? (
        <GlassCard title="评分拆解">
          {data.score ? (
            <ScoreBreakdown
              score={{
                total: data.score.total,
                quality: data.score.quality,
                valuation: data.score.valuation,
                growth: data.score.growth,
                trend: data.score.trend,
                risk: data.score.risk,
                rating: data.score.rating,
                reason: data.score.reason,
                date: data.score.date || "",
              }}
            />
          ) : (
            <div className="space-y-3 py-8 text-center">
              <p className="text-lg font-semibold text-[var(--text-primary)]">当前暂无真实评分</p>
              <p className="text-sm text-[var(--text-secondary)]">
                当前缺少可用于评分的完整数据链路，系统不会用演示评分伪装成正式研究结论。
              </p>
            </div>
          )}
        </GlassCard>
      ) : null}

      {activeTab === "signal" ? (
        <GlassCard title="研究信号">
          {data.signal ? (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <span className={signalTypeClass(data.signal.type)}>{sanitizeDisplayText(data.signal.type_label || signalTypeLabel(data.signal.type))}</span>
                {data.data_readiness?.readiness_level ? (
                  <DataStatusBadge label={displayTierLabel(data.data_readiness.readiness_level)} tone={displayTierTone(data.data_readiness.readiness_level)} />
                ) : null}
              </div>
              <p className="text-sm text-[var(--text-secondary)]">
                {sanitizeDisplayText(data.signal.logic?.display_label || data.signal.logic?.reason, "当前暂无结构化信号说明。")}
              </p>
            </div>
          ) : (
            <div className="py-10 text-center text-[var(--text-secondary)]">当前暂无研究信号。</div>
          )}
        </GlassCard>
      ) : null}

      {activeTab === "reports" ? (
        <GlassCard title="关联报告">
          {data.reports?.length ? (
            <div className="space-y-3">
              {data.reports.map((report) => (
                <div key={`${report.info_code}-${report.publish_date}`} className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4">
                  <p className="font-semibold text-[var(--text-primary)]">{sanitizeDisplayText(report.title, "未命名报告")}</p>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">{report.publish_date || "暂无日期"} · {sanitizeDisplayText(report.org_name, "研究机构")}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-10 text-center text-[var(--text-secondary)]">当前暂无关联报告。</div>
          )}
        </GlassCard>
      ) : null}
    </div>
  );
}
