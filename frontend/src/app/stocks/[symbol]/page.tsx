"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import ScoreBreakdown from "@/components/ScoreBreakdown";
import TopSearch from "@/components/TopSearch";
import GlassCard from "@/components/ui/GlassCard";
import DataStatusBadge from "@/components/ui/DataStatusBadge";
import SimulatedDataNotice from "@/components/ui/SimulatedDataNotice";
import { SkeletonCard } from "@/components/ui/Skeleton";
import TabSwitch from "@/components/ui/TabSwitch";
import ChartTooltip from "@/components/ui/ChartTooltip";
import { getStockDetail } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import { formatPercent, getChangeColor, marketLabel, sanitizeDisplayText, sanitizeSignalNarrative, signalTypeClass, signalTypeLabel } from "@/lib/utils";
import type { FinancialMetricItem, PriceHistory, ResearchReportItem, StockDetail } from "@/types";

type TraceCard = {
  key: string;
  label: string;
  score: number;
  max: number;
  weight: string;
  updatedAt: string | null | undefined;
  summary: string;
  indicators: Array<{ label: string; value: string }>;
};

function textOrMissing(value: string | number | null | undefined, suffix = "") {
  if (value === null || value === undefined || value === "") {
    return "缺失";
  }
  return `${value}${suffix}`;
}

function buildTrace(data: StockDetail): TraceCard[] {
  const latestFinancial = data.financial_metrics?.[0];
  const prevFinancial = data.financial_metrics?.[1];
  const latestPrice = data.latest_price;
  const tech = data.technical_indicators || {};
  const signalRiskCount = Array.isArray(data.signal?.risk?.items) ? data.signal?.risk?.items?.length || 0 : 0;
  const hasSpecialRisk =
    data.stock.name.includes("ST") ||
    data.stock.name.includes("退") ||
    (data.missing_fields || []).some((field) => /risk|status|warning/i.test(field));

  return [
    {
      key: "quality",
      label: "质量",
      score: data.score?.quality ?? 0,
      max: 30,
      weight: "30%",
      updatedAt: data.latest_updates?.financial || data.score?.date,
      summary: "质量维度关注盈利能力、现金流与负债结构，用于判断经营韧性。",
      indicators: [
        { label: "ROE", value: latestFinancial?.roe != null ? `${latestFinancial.roe.toFixed(1)}%` : "缺失" },
        { label: "毛利率", value: latestFinancial?.gross_margin != null ? `${latestFinancial.gross_margin.toFixed(1)}%` : "缺失" },
        { label: "经营现金流", value: latestFinancial?.operating_cashflow != null ? latestFinancial.operating_cashflow.toFixed(1) : "缺失" },
        { label: "负债率", value: latestFinancial?.debt_ratio != null ? `${latestFinancial.debt_ratio.toFixed(1)}%` : "缺失" },
      ],
    },
    {
      key: "valuation",
      label: "估值",
      score: data.score?.valuation ?? 0,
      max: 20,
      weight: "20%",
      updatedAt: data.latest_updates?.price || data.score?.date,
      summary: "估值维度用于比较当前价格与历史区间，不代表真实交易定价建议。",
      indicators: [
        { label: "PE", value: latestPrice?.pe != null ? latestPrice.pe.toFixed(1) : "缺失" },
        { label: "PB", value: latestPrice?.pb != null ? latestPrice.pb.toFixed(1) : "缺失" },
        { label: "股息率", value: latestPrice?.dividend_yield != null ? `${latestPrice.dividend_yield.toFixed(2)}%` : "缺失" },
        { label: "每股净资产", value: latestFinancial?.book_value_per_share != null ? latestFinancial.book_value_per_share.toFixed(2) : "缺失" },
      ],
    },
    {
      key: "growth",
      label: "成长",
      score: data.score?.growth ?? 0,
      max: 20,
      weight: "20%",
      updatedAt: data.latest_updates?.financial || data.score?.date,
      summary: "成长维度关注收入、利润与每股收益变化，用于判断扩张持续性。",
      indicators: [
        { label: "营收同比", value: latestFinancial?.revenue_yoy != null ? formatPercent(latestFinancial.revenue_yoy) : "缺失" },
        { label: "利润同比", value: latestFinancial?.net_profit_yoy != null ? formatPercent(latestFinancial.net_profit_yoy) : "缺失" },
        { label: "EPS", value: latestFinancial?.eps != null ? latestFinancial.eps.toFixed(2) : "缺失" },
        { label: "上一期 ROE", value: prevFinancial?.roe != null ? `${prevFinancial.roe.toFixed(1)}%` : "缺失" },
      ],
    },
    {
      key: "trend",
      label: "趋势",
      score: data.score?.trend ?? 0,
      max: 20,
      weight: "20%",
      updatedAt: data.latest_updates?.technical || data.score?.date,
      summary: "趋势维度来自价格与技术指标，只能反映历史走势特征，不代表未来收益。",
      indicators: [
        { label: "MA20", value: tech.ma20 != null ? tech.ma20.toFixed(2) : "缺失" },
        { label: "MA60", value: tech.ma60 != null ? tech.ma60.toFixed(2) : "缺失" },
        { label: "MACD", value: tech.macd != null ? tech.macd.toFixed(3) : "缺失" },
        { label: "RSI14", value: tech.rsi14 != null ? tech.rsi14.toFixed(1) : "缺失" },
      ],
    },
    {
      key: "risk",
      label: "风险",
      score: data.score?.risk ?? 0,
      max: 10,
      weight: "10%",
      updatedAt: data.latest_updates?.signal || data.score?.date,
      summary: "风险维度用于识别高波动、异常状态和关键字段缺失，不构成卖出指令。",
      indicators: [
        { label: "风险评分", value: data.score?.risk != null ? data.score.risk.toFixed(1) : "缺失" },
        { label: "特殊状态", value: hasSpecialRisk ? "存在风险提示" : "未见显著标记" },
        { label: "信号风险项", value: String(signalRiskCount) },
        { label: "高估值风险", value: latestPrice?.pe != null && latestPrice.pe >= 60 ? "偏高" : "未见显著高估" },
      ],
    },
  ];
}

export default function StockDetailPage() {
  const { t } = useTranslation();
  const params = useParams();
  const router = useRouter();
  const symbol = params.symbol as string;

  const [data, setData] = useState<StockDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("overview");

  const fetchData = () => {
    setLoading(true);
    setError("");
    return getStockDetail(symbol)
      .then(setData)
      .catch((err: Error) => setError(err.message || t("common.loadFailed")))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    void fetchData();
  }, [symbol, t]);

  const trace = useMemo(() => (data ? buildTrace(data) : []), [data]);

  if (loading) {
    return (
      <div className="mx-auto max-w-[1400px] space-y-6 p-6">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-[900px] p-6" style={{ background: "var(--bg-page)" }}>
        <TopSearch />
        <div className="card mt-6 py-12 text-center">
          <p className="text-h3 mb-2">未找到该股票的详情数据</p>
          <p className="text-caption">{error || "请检查股票代码、登录状态或后端服务状态。"}</p>
          <div className="flex gap-3 justify-center mt-4">
            <button onClick={fetchData} className="btn-primary px-4 py-2 text-sm">重新加载</button>
            <button onClick={() => router.push("/pools")} className="btn-secondary px-4 py-2 text-sm">返回股票池</button>
          </div>
        </div>
      </div>
    );
  }

  const { stock, latest_price, price_history, financial_metrics, score, signal, reports, latest_updates, missing_fields } = data;
  const tabs = [
    { key: "overview", label: t("stock.overview") },
    { key: "financial", label: t("stock.financial") },
    { key: "score", label: "评分追溯" },
    { key: "signal", label: t("stock.signal") },
    { key: "reports", label: t("stock.reports") },
  ];
  const specialRisk = stock.name.includes("ST") || stock.name.includes("退");

  return (
    <div className="mx-auto max-w-[1440px] space-y-6 p-6" style={{ background: "var(--bg-page)" }}>
      <TopSearch />

      <GlassCard>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-bold text-[var(--text-heading)]">{stock.name}</h1>
              <span className="font-mono text-sm font-semibold text-[var(--text-secondary)]">{stock.symbol}</span>
              <span className={`rounded px-2 py-0.5 text-xs font-medium ${stock.market === "A_SHARE" ? "bg-blue-50 text-blue-700" : "bg-purple-50 text-purple-700"}`}>
                {marketLabel(stock.market)}
              </span>
              <span className="text-xs text-[var(--text-muted)]">{sanitizeDisplayText(stock.industry || "行业待补充")}</span>
              {specialRisk && <DataStatusBadge label="特殊风险标的" tone="warning" />}
            </div>
            <div className="flex flex-wrap gap-2">
              <DataStatusBadge label={`行情 ${latest_updates?.price || "待核验"}`} tone="database" />
              <DataStatusBadge label={`财务 ${latest_updates?.financial || "待核验"}`} tone="database" />
              <DataStatusBadge label={`评分 ${latest_updates?.score || "待核验"}`} tone="database" />
              <DataStatusBadge label="研究口径 / 非投资建议" tone="simulated" />
            </div>
          </div>
          {score && (
            <div className="text-right">
              <p className="font-mono text-4xl font-bold text-primary-400">{score.total?.toFixed(0)}</p>
              <p className="mt-1 text-sm text-dark-muted">{sanitizeDisplayText(score.rating_label || signalTypeLabel(score.rating))}</p>
            </div>
          )}
        </div>

        <SimulatedDataNotice
          title="个股研究口径"
          badges={[
            { label: `价格更新 ${latest_updates?.price || "待核验"}`, tone: "database" },
            { label: `财务更新 ${latest_updates?.financial || "待核验"}`, tone: "database" },
            { label: missing_fields?.length ? `缺失字段 ${missing_fields.length}` : "关键字段完整度正常", tone: missing_fields?.length ? "warning" : "live" },
          ]}
          lines={[
            "本页评分、信号和解释来自数据库中的价格、财务与技术指标，属于研究辅助结果，不构成投资建议。",
            "如存在字段缺失、异常状态或高波动风险，页面会直接标记，不会用静态文案补齐结论。",
          ]}
        />
      </GlassCard>

      <TabSwitch tabs={tabs} active={activeTab} onChange={setActiveTab} />

      {activeTab === "overview" && (
        <>
          <GlassCard title={t("stock.priceChart")}>
            <div className="h-[360px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={price_history.map((item: PriceHistory, index: number, arr: PriceHistory[]) => {
                    if (index >= 19) {
                      const slice = arr.slice(index - 19, index + 1);
                      const ma20 = slice.reduce((sum, value) => sum + value.close, 0) / slice.length;
                      return { ...item, ma20: Math.round(ma20 * 100) / 100 };
                    }
                    return { ...item, ma20: null };
                  })}
                >
                  <CartesianGrid stroke="#1E293B" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94A3B8" }} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} />
                  <Tooltip content={<ChartTooltip />} />
                  <Line type="monotone" dataKey="close" stroke="#6366f1" strokeWidth={2} dot={false} name="Close" />
                  <Line type="monotone" dataKey="ma20" stroke="#10B981" strokeWidth={1} dot={false} name="MA20" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>

          <GlassCard title="数据来源与缺失提示">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-4">
                <p className="mb-2 text-xs text-dark-muted">数据来源</p>
                <div className="space-y-2 text-sm text-dark-text">
                  <p>价格: {sanitizeDisplayText(data.data_source?.prices || "待核验")}</p>
                  <p>财务: {sanitizeDisplayText(data.data_source?.financials || "待核验")}</p>
                  <p>评分: {sanitizeDisplayText(data.data_source?.scores || "待核验")}</p>
                  <p>信号: {sanitizeDisplayText(data.data_source?.signals || "待核验")}</p>
                </div>
              </div>
              <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-4">
                <p className="mb-2 text-xs text-dark-muted">缺失指标</p>
                {missing_fields?.length ? (
                  <div className="flex flex-wrap gap-2">
                    {missing_fields.map((field) => (
                      <DataStatusBadge key={field} label={sanitizeDisplayText(field)} tone="warning" />
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-dark-text">当前关键指标未见显著缺失。</p>
                )}
              </div>
            </div>
          </GlassCard>

          <GlassCard title="关键价格与状态">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <div className="card-inner">
                <p className="text-caption">最新收盘价</p>
                <p className="mt-1 font-mono text-lg font-bold text-[var(--text-primary)]">{latest_price?.close?.toFixed(2) || "-"}</p>
              </div>
              <div className="card-inner">
                <p className="text-caption">PE / PB</p>
                <p className="mt-1 font-mono text-lg font-bold text-[var(--text-primary)]">{textOrMissing(latest_price?.pe?.toFixed(1))} / {textOrMissing(latest_price?.pb?.toFixed(1))}</p>
              </div>
              <div className="card-inner">
                <p className="text-caption">研究评级</p>
                <p className="mt-1 text-lg font-bold text-[var(--text-primary)]">{signal ? signalTypeLabel(signal.type) : "-"}</p>
              </div>
              <div className="card-inner">
                <p className="text-caption">研究仓位</p>
                <p className="mt-1 font-mono text-lg font-bold text-[var(--text-primary)]">{signal?.position ? `${signal.position}%` : "-"}</p>
              </div>
            </div>
          </GlassCard>
        </>
      )}

      {activeTab === "financial" && (
        <GlassCard title={t("stock.financial")}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  {["期间", "营收", "营收同比", "净利润", "利润同比", "毛利率", "ROE", "负债率", "EPS"].map((header) => (
                    <th key={header} className="px-3 py-2 text-left text-xs text-dark-muted">
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {financial_metrics.map((item: FinancialMetricItem, index: number) => (
                  <tr key={index} className="border-b border-white/[0.03]">
                    <td className="px-3 py-2 text-dark-text">{item.period}</td>
                    <td className="px-3 py-2 text-right font-mono text-dark-text">{item.revenue?.toFixed(1) ?? "-"}</td>
                    <td className={`px-3 py-2 text-right font-mono ${getChangeColor(item.revenue_yoy ?? 0)}`}>{item.revenue_yoy != null ? formatPercent(item.revenue_yoy) : "-"}</td>
                    <td className="px-3 py-2 text-right font-mono text-dark-text">{item.net_profit?.toFixed(1) ?? "-"}</td>
                    <td className={`px-3 py-2 text-right font-mono ${getChangeColor(item.net_profit_yoy ?? 0)}`}>{item.net_profit_yoy != null ? formatPercent(item.net_profit_yoy) : "-"}</td>
                    <td className="px-3 py-2 text-right font-mono text-dark-text">{item.gross_margin != null ? `${item.gross_margin.toFixed(1)}%` : "-"}</td>
                    <td className="px-3 py-2 text-right font-mono text-dark-text">{item.roe != null ? `${item.roe.toFixed(1)}%` : "-"}</td>
                    <td className="px-3 py-2 text-right font-mono text-dark-text">{item.debt_ratio != null ? `${item.debt_ratio.toFixed(1)}%` : "-"}</td>
                    <td className="px-3 py-2 text-right font-mono text-dark-text">{item.eps?.toFixed(2) ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}

      {activeTab === "score" && (
        <div className="space-y-6">
          {score && <ScoreBreakdown score={{ ...score, reason: sanitizeDisplayText(score.reason || "") }} />}
          <GlassCard title="五维评分拆解 / 模型追溯">
            <div className="space-y-4">
              {trace.map((dimension) => (
                <div key={dimension.key} className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
                  <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="text-base font-semibold text-white">{dimension.label}</h3>
                      <p className="mt-1 text-xs text-dark-muted">{dimension.summary}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-mono text-lg text-primary-300">{dimension.score.toFixed(1)} / {dimension.max}</p>
                      <p className="text-xs text-dark-muted">权重 {dimension.weight} · 更新 {dimension.updatedAt || "待核验"}</p>
                    </div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                    {dimension.indicators.map((indicator) => (
                      <div key={indicator.label} className="rounded-xl border border-white/[0.06] bg-black/10 p-3">
                        <p className="text-xs text-dark-muted">{indicator.label}</p>
                        <p className="mt-1 text-sm font-mono text-dark-text">{indicator.value}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>
        </div>
      )}

      {activeTab === "signal" && (
        <GlassCard title={t("stock.signal")}>
          {signal ? (
            <div className="space-y-4">
              {/* 四个关键指标卡 */}
              <div className="grid gap-4 md:grid-cols-4">
                <div className="card-inner">
                  <p className="text-caption">研究评级</p>
                  <span className={`${signalTypeClass(signal.type)} mt-2 inline-block`}>{sanitizeDisplayText(signal.type_label || signalTypeLabel(signal.type))}</span>
                </div>
                <div className="card-inner">
                  <p className="text-caption">生成时间</p>
                  <p className="mt-2 text-sm font-semibold text-[var(--text-primary)]">{sanitizeDisplayText(signal.date)}</p>
                </div>
                <div className="card-inner">
                  <p className="text-caption">研究仓位</p>
                  <p className="mt-2 text-sm font-semibold text-[var(--text-primary)]">{signal.position ? `${signal.position}%` : "-"}</p>
                </div>
                <div className="card-inner">
                  <p className="text-caption">研究周期</p>
                  <p className="mt-2 text-sm font-semibold text-[var(--text-primary)]">{sanitizeDisplayText(signal.holding_period || "-")}</p>
                </div>
              </div>

              {/* 三张价格卡 */}
              <div className="grid gap-4 md:grid-cols-3">
                <div className="card-success">
                  <p className="text-xs font-semibold opacity-80">研究参考价</p>
                  <p className="mt-1 text-lg font-mono font-bold">{signal.entry_price?.toFixed(2) || "-"}</p>
                </div>
                <div className="card-info">
                  <p className="text-xs font-semibold opacity-80">模型观察价</p>
                  <p className="mt-1 text-lg font-mono font-bold">{signal.target_price?.toFixed(2) || "-"}</p>
                </div>
                <div className="card-danger">
                  <p className="text-xs font-semibold opacity-80">风险警戒价</p>
                  <p className="mt-1 text-lg font-mono font-bold">{signal.stop_loss?.toFixed(2) || "-"}</p>
                </div>
              </div>

              {/* 信号触发依据 */}
              <div className="card-inner">
                <p className="text-caption font-semibold mb-2">信号触发依据</p>
                <p className="text-body leading-6">{sanitizeSignalNarrative(signal.logic?.reason || signal.logic?.display_label || "")}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <DataStatusBadge label={`质量 ${score?.quality?.toFixed(0) || "-"}`} tone="database" />
                  <DataStatusBadge label={`估值 ${score?.valuation?.toFixed(0) || "-"}`} tone="database" />
                  <DataStatusBadge label={`成长 ${score?.growth?.toFixed(0) || "-"}`} tone="database" />
                  <DataStatusBadge label={`趋势 ${score?.trend?.toFixed(0) || "-"}`} tone="database" />
                  <DataStatusBadge label={`风险 ${score?.risk?.toFixed(0) || "-"}`} tone="warning" />
                </div>
              </div>

              {/* 主要风险 */}
              {Array.isArray(signal.risk?.items) && signal.risk.items.length > 0 && (
                <div className="card-warning">
                  <p className="text-xs font-semibold mb-2">主要风险</p>
                  <div className="space-y-2 text-sm">
                    {signal.risk.items.map((item: string) => (
                      <p key={item}>{sanitizeDisplayText(item)}</p>
                    ))}
                  </div>
                </div>
              )}

              <p className="text-caption">数据来源: 价格、财务、技术指标与数据库信号记录。前端只展示研究评级，不展示买卖指令。</p>
            </div>
          ) : (
            <div className="py-12 text-center text-dark-muted">当前没有可展示的研究信号。</div>
          )}
        </GlassCard>
      )}

      {activeTab === "reports" && (
        <GlassCard title={t("stock.brokerReports")}>
          {reports?.length ? (
            <div className="space-y-3">
              {reports.map((report: ResearchReportItem, index: number) => (
                <div key={`${report.title}-${index}`} className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <a href={report.url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-dark-text hover:text-primary-400">
                        {sanitizeDisplayText(report.title)}
                      </a>
                      <p className="text-xs text-dark-muted">{sanitizeDisplayText(report.org_name)} · {sanitizeDisplayText(report.publish_date || "日期缺失")}</p>
                    </div>
                    {report.rating && <DataStatusBadge label={sanitizeSignalNarrative(report.rating)} tone="third-party" />}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-12 text-center text-dark-muted">当前没有已同步的研报数据。</div>
          )}
        </GlassCard>
      )}

      <div className="disclaimer">{t("app.disclaimer")}</div>
    </div>
  );
}
