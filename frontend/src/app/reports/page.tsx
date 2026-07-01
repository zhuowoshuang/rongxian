"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Download, Eye, FileText, ImageDown, Loader2, Search } from "lucide-react";

import EmptyState from "@/components/ui/EmptyState";
import SimulatedDataNotice from "@/components/ui/SimulatedDataNotice";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { showToast } from "@/components/ui/Toast";
import {
  downloadReportPdf,
  downloadReportPng,
  generateReport,
  getReports,
  getResearchReports,
  getRuntimeInfo,
  searchStocks,
} from "@/lib/api";
import { marketLabel, reportTypeLabel, sanitizeDisplayText } from "@/lib/utils";
import type { ReportItem, ResearchReportItem, RuntimeInfo, StockSearchResult } from "@/types";

type TabKey = "system" | "broker";
type Step = 1 | 2 | 3;

const REPORT_STYLES = [
  { key: "basic", label: "基础解读版", desc: "围绕核心财务、评分与业务质量做基础研究解读。" },
  { key: "risk", label: "风险排查版", desc: "优先梳理估值、波动、财务和信号层面的潜在风险。" },
  { key: "valuation", label: "估值观察版", desc: "从估值分位、盈利质量和同类比较角度观察。 " },
  { key: "growth", label: "成长质量版", desc: "聚焦成长持续性、ROE、现金流与质量指标。" },
  { key: "technical", label: "技术趋势版", desc: "从价格趋势、波动和技术指标节奏辅助观察。" },
];

function reportStyleLabel(style?: string | null) {
  return REPORT_STYLES.find((item) => item.key === style)?.label || style || "通用研究";
}

function reportStatusLabel(status?: string | null) {
  if (status === "real_backed") return "真实研究报告";
  if (status === "real_observation") return "研究观察报告";
  if (status === "data_quality_limited") return "数据质量受限报告";
  if (status === "demo_backed") return "演示评分报告";
  if (status === "data_insufficient") return "数据不足报告";
  return "正式研究口径";
}

function fileSafeName(report: ReportItem, ext: "png" | "pdf") {
  const name = `${report.stock_code || report.report_type}_${report.stock_name || "研究报告"}_${ext === "png" ? "报告摘要" : "研究报告"}_${report.report_date || ""}.${ext}`;
  return name.replace(/[<>:"/\\|?*]/g, "_");
}

export default function ReportsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabKey>("system");
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [researchReports, setResearchReports] = useState<ResearchReportItem[]>([]);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [step, setStep] = useState<Step>(1);
  const [keyword, setKeyword] = useState("");
  const [stockResults, setStockResults] = useState<StockSearchResult[]>([]);
  const [searchNotice, setSearchNotice] = useState<string | null>(null);
  const [selectedStock, setSelectedStock] = useState<StockSearchResult | null>(null);
  const [style, setStyle] = useState(REPORT_STYLES[0].key);
  const [generating, setGenerating] = useState(false);
  const [busy, setBusy] = useState<{ id: number; action: "html" | "png" | "pdf" } | null>(null);
  const [freshReportId, setFreshReportId] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [runtimeInfo, reportData, researchData] = await Promise.all([
        getRuntimeInfo().catch(() => null),
        getReports({ page_size: 80 }),
        getResearchReports({ page_size: 20 }),
      ]);
      setRuntime(runtimeInfo);
      setReports(reportData.items || []);
      setResearchReports(researchData.reports || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "报告列表加载失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  useEffect(() => {
    if (!keyword.trim()) {
      setStockResults([]);
      setSearchNotice(null);
      return;
    }
    const timer = window.setTimeout(() => {
      searchStocks(keyword.trim())
        .then((items) => {
          const result = items || [];
          const warningItem = result.find((item) => item.networkStatus === "NETWORK_WARN" || item.errorMessage);
          setStockResults(result);
          setSearchNotice(
            warningItem?.errorMessage ||
              (result.length === 0 ? "未找到匹配的股票，请尝试输入代码或中文名称。" : null),
          );
          const exact = result.filter((item) => item.symbol === keyword.trim());
          if (exact.length === 1) {
            setSelectedStock(exact[0]);
            setStep(2);
          }
        })
        .catch((err) => {
          setStockResults([]);
          setSearchNotice(null);
          setError(err instanceof Error ? `股票搜索失败：${err.message}` : "股票搜索失败，请重试。");
        });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [keyword]);

  const selectedStyle = useMemo(() => REPORT_STYLES.find((item) => item.key === style) || REPORT_STYLES[0], [style]);

  const handleGenerate = async () => {
    if (!selectedStock) {
      setError("请先选择股票后再生成报告。");
      setStep(1);
      return;
    }
    setGenerating(true);
    setError("");
    try {
      const result = await generateReport({ report_type: "STOCK", stock_symbol: selectedStock.symbol, style });
      const id = result.report_id || result.id;
      if (!id) throw new Error("后端未返回 report_id，无法打开正确报告。");
      setFreshReportId(id);
      showToast("success", `已生成 ${selectedStock.symbol} ${selectedStock.name} ${selectedStyle.label}`);
      await load();
      router.push(`/reports/${id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "报告生成失败，请稍后重试。";
      setError(`报告生成失败：${message}`);
      showToast("error", `报告生成失败：${message}`);
    } finally {
      setGenerating(false);
    }
  };

  const openHtml = async (report: ReportItem) => {
    setBusy({ id: report.id, action: "html" });
    try {
      router.push(`/reports/${report.id}`);
    } catch {
      setError("HTML 报告打开失败，请稍后重试。");
    } finally {
      setBusy(null);
    }
  };

  const downloadPng = async (report: ReportItem) => {
    setBusy({ id: report.id, action: "png" });
    try {
      await downloadReportPng(report.id, fileSafeName(report, "png"));
      showToast("success", "PNG 摘要图下载已开始。");
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : "PNG 摘要图生成失败，请稍后重试。";
      setError(`PNG 摘要图生成失败：${message}`);
      showToast("error", `PNG 摘要图生成失败：${message}`);
    } finally {
      setBusy(null);
    }
  };

  const downloadPdf = async (report: ReportItem) => {
    setBusy({ id: report.id, action: "pdf" });
    try {
      await downloadReportPdf(report.id, fileSafeName(report, "pdf"));
      showToast("success", "PDF 报告下载已开始。");
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : "PDF 报告下载失败，请稍后重试。";
      setError(`PDF 报告下载失败：${message}`);
      showToast("error", `PDF 报告下载失败：${message}`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="min-h-screen p-6" style={{ background: "var(--bg-page)" }}>
      <div className="mx-auto max-w-[1400px] space-y-6">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-700">报告中心</p>
          <h1 className="mt-2 text-3xl font-bold text-slate-950">个股研究报告与系统报告</h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">
            个股报告按“选股票 → 选研究视角 → 确认生成”执行，生成后使用后端返回的 report_id 打开，避免指向错误。
          </p>
        </section>

        <SimulatedDataNotice
          title="报告口径说明"
          badges={[
            { label: `系统报告更新：${runtime?.latest_updates?.reports || "待更新"}`, tone: "database" },
            { label: `券商研报更新：${runtime?.latest_updates?.research_reports || "待更新"}`, tone: "third-party" },
            { label: "PNG 为摘要图，PDF 为归档下载", tone: "database" },
          ]}
          lines={["所有内容仅供研究参考，不构成投资建议。", "PNG/PDF 均调用真实后端接口，失败会显示明确错误。", runtime?.warning || "若底层评分为演示评分或待生成，报告会明确标注为演示/数据不足口径。"]}
        />

        {error && (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <span>{error}</span>
            <button onClick={() => void load()} className="rounded-md border border-red-200 bg-white px-3 py-1.5 text-xs">重试</button>
          </div>
        )}

        <div className="flex w-fit gap-2 rounded-lg border border-slate-200 bg-white p-1">
          {[{ key: "system", label: "系统/个股报告" }, { key: "broker", label: "券商研报索引" }].map((tab) => (
            <button key={tab.key} onClick={() => setActiveTab(tab.key as TabKey)} className={`rounded-md px-4 py-2 text-sm font-medium ${activeTab === tab.key ? "bg-cyan-700 text-white" : "text-slate-600 hover:bg-slate-50"}`}>
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "system" ? (
          <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-5 flex items-center gap-2 text-sm font-semibold text-slate-900">
                {[1, 2, 3].map((item) => <span key={item} className={`flex h-7 w-7 items-center justify-center rounded-full ${step === item ? "bg-cyan-700 text-white" : "bg-slate-100 text-slate-500"}`}>{item}</span>)}
              </div>

              <div className="space-y-5">
                <div>
                  <h2 className="text-base font-semibold text-slate-950">第一步：搜索并选择股票</h2>
                  <div className="relative mt-3">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <input value={keyword} onChange={(e) => { setKeyword(e.target.value); setSelectedStock(null); setStep(1); }} placeholder="输入股票代码或名称" className="h-11 w-full rounded-lg border border-slate-200 pl-9 pr-3 text-sm outline-none focus:border-cyan-600" />
                  </div>
                  {searchNotice ? <p className="mt-2 text-xs text-amber-700">{searchNotice}</p> : null}
                  <div className="mt-3 max-h-56 overflow-auto rounded-lg border border-slate-100">
                    {stockResults.length ? stockResults.map((stock) => (
                      <button key={stock.symbol} onClick={() => { setSelectedStock(stock); setStep(2); }} className={`grid w-full grid-cols-[90px_1fr_70px] gap-2 border-b border-slate-100 px-3 py-2 text-left text-sm last:border-0 hover:bg-cyan-50 ${selectedStock?.symbol === stock.symbol ? "bg-cyan-50" : ""}`}>
                        <span className="font-mono font-semibold text-cyan-700">{stock.symbol}</span>
                        <span className="truncate text-slate-900">{stock.name}</span>
                        <span className="text-xs text-slate-500">{marketLabel(stock.market)}</span>
                        <span className="col-span-3 text-xs text-slate-500">{stock.industry || "行业待补充"}</span>
                      </button>
                    )) : <div className="px-3 py-4 text-sm text-slate-500">请输入代码或名称搜索真实股票。</div>}
                  </div>
                </div>

                <div className={step < 2 ? "opacity-50" : ""}>
                  <h2 className="text-base font-semibold text-slate-950">第二步：选择报告风格</h2>
                  <div className="mt-3 grid gap-2">
                    {REPORT_STYLES.map((item) => (
                      <button key={item.key} disabled={!selectedStock} onClick={() => { setStyle(item.key); setStep(3); }} className={`rounded-lg border p-3 text-left ${style === item.key ? "border-cyan-600 bg-cyan-50" : "border-slate-200 bg-white"} disabled:cursor-not-allowed`}>
                        <div className="text-sm font-semibold text-slate-900">{item.label}</div>
                        <div className="mt-1 text-xs leading-5 text-slate-500">{item.desc} 这是研究视角，不是投资建议。</div>
                      </button>
                    ))}
                  </div>
                </div>

                <div className={step < 3 ? "opacity-50" : ""}>
                  <h2 className="text-base font-semibold text-slate-950">第三步：确认生成</h2>
                  <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
                    {selectedStock ? <>将为 <b>{selectedStock.symbol} {selectedStock.name}</b> 生成【{selectedStyle.label}】个股研究报告</> : "请先选择股票。"}
                  </div>
                  <button onClick={handleGenerate} disabled={!selectedStock || generating} className="mt-3 inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-cyan-700 text-sm font-semibold text-white disabled:opacity-60">
                    {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
                    {generating ? "正在生成..." : "确认生成并打开报告"}
                  </button>
                </div>
              </div>
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="text-base font-semibold text-slate-950">报告列表</h2>
                  <p className="mt-1 text-xs text-slate-500">所有卡片来自真实报告接口，下载次数来自事件统计。</p>
                </div>
                <button onClick={() => void load()} className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600">刷新</button>
              </div>

              {loading ? <SkeletonCard /> : reports.length === 0 ? (
                <EmptyState message="暂无报告" description="生成一份个股研究报告后会显示在这里。" />
              ) : (
                <div className="grid gap-3">
                  {reports.map((report) => (
                    <article key={report.id} className={`rounded-lg border p-4 ${freshReportId === report.id ? "border-cyan-400 bg-cyan-50/70" : "border-slate-200 bg-white"}`}>
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-sm font-semibold text-slate-950">{sanitizeDisplayText(report.title, "未命名研究报告")}</h3>
                            {freshReportId === report.id && <span className="rounded-full bg-cyan-700 px-2 py-0.5 text-xs text-white">刚刚生成</span>}
                            <span className={`rounded-full px-2 py-0.5 text-xs ${report.report_data_status === "real_backed" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
                              {reportStatusLabel(report.report_data_status)}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-slate-500">
                            {report.stock_code || "系统"} {report.stock_name || ""} · {reportTypeLabel(report.report_type)} · {reportStyleLabel(report.style)} · {report.created_at || report.report_date}
                          </p>
                          <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-600">{sanitizeDisplayText(report.summary, "暂无摘要。")}</p>
                          <p className="mt-2 text-xs text-slate-500">HTML {report.html_views || 0} 次 · PNG {report.png_downloads || 0} 次 · PDF {report.pdf_downloads || 0} 次</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <ActionButton busy={busy?.id === report.id && busy.action === "html"} icon={<Eye className="h-4 w-4" />} label="查看 HTML 报告" onClick={() => void openHtml(report)} />
                          <ActionButton busy={busy?.id === report.id && busy.action === "png"} icon={<ImageDown className="h-4 w-4" />} label="下载 PNG 摘要图" onClick={() => void downloadPng(report)} />
                          <ActionButton primary busy={busy?.id === report.id && busy.action === "pdf"} icon={<Download className="h-4 w-4" />} label="下载 PDF 报告" onClick={() => void downloadPdf(report)} />
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>
          </div>
        ) : (
          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-base font-semibold text-slate-950">券商研报资料索引</h2>
            <p className="mt-1 text-xs text-slate-500">第三方资料索引，不代表平台自有研究结论。</p>
            <div className="mt-4 grid gap-3">
              {researchReports.map((report) => (
                <a key={`${report.info_code}-${report.publish_date}`} href={report.url} target="_blank" rel="noreferrer" className="rounded-lg border border-slate-200 p-4 hover:bg-slate-50">
                  <div className="text-sm font-semibold text-slate-900">{sanitizeDisplayText(report.title, "外部研报标题暂不可用")}</div>
                  <div className="mt-1 text-xs text-slate-500">{report.stock_code} {report.stock_name} · {report.org_name || "机构待标注"} · {report.publish_date || "日期待核验"}</div>
                </a>
              ))}
              {!researchReports.length && <EmptyState message="暂无券商研报索引" />}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

function ActionButton({ label, icon, busy, primary, onClick }: { label: string; icon: React.ReactNode; busy?: boolean; primary?: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} disabled={busy} className={`inline-flex h-9 items-center gap-2 rounded-lg px-3 text-xs font-semibold disabled:opacity-60 ${primary ? "bg-cyan-700 text-white" : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}>
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {busy ? "处理中..." : label}
    </button>
  );
}
