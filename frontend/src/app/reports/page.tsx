"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import EmptyState from "@/components/ui/EmptyState";
import SimulatedDataNotice from "@/components/ui/SimulatedDataNotice";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { showToast } from "@/components/ui/Toast";
import {
  downloadReportPdf,
  generateReport,
  generateStyleReport,
  getReport,
  getReports,
  getResearchReports,
  getRuntimeInfo,
  searchStocks,
} from "@/lib/api";
import { sanitizeDisplayText } from "@/lib/utils";
import type { ReportItem, ResearchReportItem, RuntimeInfo, StockSearchResult } from "@/types";

function markdownToHtml(markdown: string) {
  const safe = sanitizeDisplayText(
    markdown,
    "原始文本存在编码异常，已隐藏原文，请以结构化评分、研究说明和 PDF 报告为准。"
  )
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  return safe
    .replace(/^### (.+)$/gm, "<h3 class='mt-6 mb-2 text-lg font-semibold text-slate-900'>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2 class='mt-8 mb-3 text-xl font-bold text-slate-900'>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1 class='mt-8 mb-4 text-2xl font-bold text-slate-950'>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code class='rounded bg-slate-100 px-1.5 py-0.5 text-xs'>$1</code>")
    .replace(/(?:^|\n)- (.+)/g, "\n<li>$1</li>")
    .replace(/(<li>[\s\S]*<\/li>)/g, "<ul class='list-disc space-y-1 pl-5'>$1</ul>")
    .replace(/\n{2,}/g, "</p><p>")
    .replace(/\n/g, "<br/>")
    .replace(/^/, "<p>")
    .concat("</p>");
}

function reportDisplayText(text: string | null | undefined, fallback: string) {
  return sanitizeDisplayText(text, fallback)
    .replaceAll("投资策略", "研究策略")
    .replaceAll("投资建议", "研究结论")
    .replaceAll("策略报告", "研究报告")
    .replaceAll("研究研究报告", "研究报告")
    .replaceAll("观望", "观察");
}

function reportTypeLabel(report: ReportItem) {
  if (report.report_type === "DAILY") return "系统研究报告";
  if (report.report_type === "STOCK") return "个股研究报告";
  if (report.report_type === "STYLE") {
    const labelMap: Record<string, string> = {
      steady: "稳健型",
      aggressive: "进取型",
      conservative: "保守型",
    };
    return `${labelMap[report.style || ""] || "风格"}研究报告`;
  }
  return "系统研究报告";
}

type SystemTab = "system" | "broker";

export default function ReportsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<SystemTab>("system");
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [researchReports, setResearchReports] = useState<ResearchReportItem[]>([]);
  const [selectedReport, setSelectedReport] = useState<(ReportItem & { content_markdown: string }) | null>(null);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState<number | null>(null);
  const [stockKeyword, setStockKeyword] = useState("");
  const [stockResults, setStockResults] = useState<StockSearchResult[]>([]);
  const [selectedStock, setSelectedStock] = useState<StockSearchResult | null>(null);
  const [showSearch, setShowSearch] = useState(false);
  const [selectedStyle, setSelectedStyle] = useState<string>("");
  const [selectedStockStyle, setSelectedStockStyle] = useState<string>("steady");
  const [reportType, setReportType] = useState<string>("");
  const searchRef = useRef<HTMLDivElement>(null);

  const styles = [
    { key: "steady", label: "稳健型" },
    { key: "aggressive", label: "进取型" },
    { key: "conservative", label: "保守型" },
  ];

  const fetchReports = async () => {
    setLoading(true);
    setError(null);
    try {
      const [runtimeInfo, reportData, researchData] = await Promise.all([
        getRuntimeInfo().catch(() => null),
        getReports({ report_type: reportType || undefined, page_size: 50 }),
        getResearchReports({ page_size: 20 }),
      ]);
      setRuntime(runtimeInfo);
      setReports(reportData.items || []);
      setResearchReports(researchData.reports || []);
    } catch (e: any) {
      setError(e.message || "报告列表加载失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchReports();
  }, [reportType]);

  useEffect(() => {
    const handler = (event: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setShowSearch(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    if (!stockKeyword.trim()) {
      setStockResults([]);
      return;
    }
    const timer = setTimeout(() => {
      searchStocks(stockKeyword)
        .then((data) => {
          setStockResults(data || []);
          setShowSearch(true);
        })
        .catch(() => {
          setStockResults([]);
        });
    }, 250);
    return () => clearTimeout(timer);
  }, [stockKeyword]);

  const handleGenerateDaily = async () => {
    setGenerating(true);
    setError(null);
    try {
      const result = await generateReport({ report_type: "DAILY", style: selectedStyle || undefined });
      showToast("success", "系统研究报告已生成。");
      await fetchReports();
      if (result?.id) {
        router.push(`/reports/${result.id}`);
      }
    } catch (e: any) {
      const message = e.message || "系统研究报告生成失败。";
      setError(message);
      showToast("error", message);
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateStock = async () => {
    if (!selectedStock) return;
    setGenerating(true);
    setError(null);
    try {
      const result = await generateReport({
        report_type: "STOCK",
        stock_symbol: selectedStock.symbol,
        style: selectedStockStyle || undefined,
      });
      showToast("success", `个股研究报告已生成：${selectedStock.symbol} ${selectedStock.name}`);
      await fetchReports();
      // 自动跳转到新生成的报告
      if (result?.id) {
        router.push(`/reports/${result.id}`);
      }
    } catch (e: any) {
      const message = e.message || "个股研究报告生成失败。";
      setError(message);
      showToast("error", message);
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateStyle = async (style: string) => {
    setGenerating(true);
    setError(null);
    try {
      const result = await generateStyleReport(style);
      showToast("success", `${styles.find((item) => item.key === style)?.label || style}研究报告已生成。`);
      await fetchReports();
      if (result?.id) {
        router.push(`/reports/${result.id}`);
      }
    } catch (e: any) {
      const message = e.message || "风格研究报告生成失败。";
      setError(message);
      showToast("error", message);
    } finally {
      setGenerating(false);
    }
  };

  const handleView = async (id: number) => {
    setError(null);
    try {
      const report = await getReport(id);
      setSelectedReport(report);
    } catch (e: any) {
      setError(e.message || "HTML 报告加载失败。");
    }
  };

  const handleDownloadPdf = async (report: ReportItem) => {
    setDownloadingPdf(report.id);
    setError(null);
    try {
      await downloadReportPdf(report.id, `${report.title}.pdf`);
      showToast("success", "PDF 报告下载已开始。");
    } catch (e: any) {
      const message = e.message || "PDF 报告下载失败。";
      setError(message);
      showToast("error", message);
    } finally {
      setDownloadingPdf(null);
    }
  };

  const previewHtml = useMemo(
    () => markdownToHtml(selectedReport?.content_markdown || ""),
    [selectedReport]
  );

  return (
    <div className="min-h-screen p-6" style={{ background: "var(--bg-page)" }}>
      <div className="mx-auto max-w-[1400px] space-y-6">
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-indigo-500/80">投研成果中心</p>
          <h1 className="mt-2 text-3xl font-bold text-slate-900">报告中心</h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">
            系统研究报告、个股研究报告与券商研报资料索引在此分开展示。系统报告来自当前后端规则生成并真实入库，
            券商研报仅作为外部资料索引，不代表平台自身观点。
          </p>
        </section>

        <SimulatedDataNotice
          title="报告口径说明"
          badges={[
            { label: `系统报告更新：${runtime?.latest_updates?.reports || "待更新"}`, tone: "database" },
            { label: `券商研报更新：${runtime?.latest_updates?.research_reports || "待更新"}`, tone: "third-party" },
            { label: `数据源模式：${runtime?.data_mode || runtime?.provider || "待核验"}`, tone: "pending" },
            { label: "不含实盘交易数据", tone: "simulated" },
          ]}
          lines={[
            "系统研究报告基于当前数据库与模型规则生成，并写入真实报告表。",
            "券商研报属于第三方资料索引，请与平台研究输出区分理解。",
            "所有内容仅供研究参考，不构成投资建议。",
          ]}
        />

        {error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span>{error}</span>
              <button
                onClick={() => void fetchReports()}
                className="rounded-lg border border-red-200 bg-white px-3 py-1.5 text-xs font-medium text-red-700"
              >
                重新加载
              </button>
            </div>
          </div>
        )}

        <div className="flex w-fit gap-2 rounded-2xl border border-slate-200 bg-white p-1 shadow-sm">
          {[
            { key: "system", label: "系统研究报告" },
            { key: "broker", label: "券商研报索引" },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as SystemTab)}
              className={`rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === tab.key ? "bg-indigo-500 text-white" : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "system" ? (
          <div className="grid gap-6 lg:grid-cols-[1.05fr_1.95fr]">
            <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div>
                <h2 className="text-base font-semibold text-slate-900">生成新的研究成果</h2>
                <p className="mt-1 text-xs text-slate-500">所有生成动作均调用真实后端接口，结果写入数据库。</p>
              </div>

              <div className="space-y-3">
                <p className="text-xs font-medium text-slate-500">系统研究报告</p>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => setSelectedStyle("")}
                    className={`rounded-xl px-4 py-2 text-sm ${
                      selectedStyle === "" ? "bg-indigo-50 text-indigo-700" : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    通用版
                  </button>
                  {styles.map((style) => (
                    <button
                      key={style.key}
                      onClick={() => setSelectedStyle(style.key)}
                      className={`rounded-xl px-4 py-2 text-sm ${
                        selectedStyle === style.key ? "bg-indigo-500 text-white" : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {style.label}
                    </button>
                  ))}
                </div>
                <button onClick={handleGenerateDaily} disabled={generating} className="btn-primary w-full px-5 py-2.5 text-sm">
                  {generating ? "正在生成..." : "生成系统研究报告"}
                </button>
              </div>

              <div className="space-y-3 border-t border-slate-100 pt-4">
                <p className="text-xs font-medium text-slate-500">个股研究报告</p>
                <div className="relative" ref={searchRef}>
                  <input
                    type="text"
                    value={selectedStock ? `${selectedStock.symbol} ${selectedStock.name}` : stockKeyword}
                    onChange={(event) => {
                      setStockKeyword(event.target.value);
                      setSelectedStock(null);
                    }}
                    placeholder="搜索股票代码或名称"
                    className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm text-slate-800 outline-none focus:border-indigo-400"
                  />
                  {showSearch && (
                    <div className="absolute left-0 right-0 top-full z-20 mt-1 max-h-56 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-lg">
                      {stockResults.length > 0 ? (
                        stockResults.map((stock) => (
                          <button
                            key={stock.symbol}
                            onClick={() => {
                              setSelectedStock(stock);
                              setStockKeyword("");
                              setShowSearch(false);
                            }}
                            className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm text-slate-700 hover:bg-slate-50"
                          >
                            <span className="font-mono text-indigo-600">{stock.symbol}</span>
                            <span>{stock.name}</span>
                          </button>
                        ))
                      ) : (
                        <div className="px-4 py-3 text-xs text-slate-500">未找到匹配股票。</div>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {styles.map((style) => (
                    <button
                      key={`stock-style-${style.key}`}
                      onClick={() => setSelectedStockStyle(style.key)}
                      className={`rounded-xl px-4 py-2 text-sm ${
                        selectedStockStyle === style.key ? "bg-indigo-500 text-white" : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {style.label}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-slate-500">
                  请先选择股票，再选择报告风格，系统会按返回的 report_id 打开对应报告。
                </p>
                <button
                  onClick={handleGenerateStock}
                  disabled={generating || !selectedStock}
                  className="btn-primary w-full px-5 py-2.5 text-sm"
                >
                  {generating ? "正在生成..." : "生成个股研究报告"}
                </button>
              </div>

              <div className="space-y-3 border-t border-slate-100 pt-4">
                <p className="text-xs font-medium text-slate-500">风格研究报告</p>
                <div className="grid gap-2">
                  {styles.map((style) => (
                    <button
                      key={style.key}
                      onClick={() => handleGenerateStyle(style.key)}
                      disabled={generating}
                      className="btn-secondary px-4 py-2.5 text-sm"
                    >
                      生成{style.label}研究报告
                    </button>
                  ))}
                </div>
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-base font-semibold text-slate-900">已生成的系统成果</h2>
                  <p className="mt-1 text-xs text-slate-500">下方列表来自真实报告表，支持 HTML 查看与 PDF 下载。</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {[
                    { value: "", label: "全部" },
                    { value: "DAILY", label: "系统" },
                    { value: "STYLE", label: "风格" },
                    { value: "STOCK", label: "个股" },
                  ].map((option) => (
                    <button
                      key={option.value || "all"}
                      onClick={() => setReportType(option.value)}
                      className={`rounded-xl px-3 py-2 text-sm ${
                        reportType === option.value ? "bg-indigo-50 text-indigo-700" : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>

              {loading ? (
                <div className="grid gap-4 lg:grid-cols-[1fr_1.15fr]">
                  <div className="space-y-3">
                    <SkeletonCard />
                    <SkeletonCard />
                    <SkeletonCard />
                  </div>
                  <SkeletonCard className="min-h-[420px]" />
                </div>
              ) : reports.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 py-10">
                  <EmptyState
                    message="当前筛选条件下暂无报告"
                    description="请先生成研究报告，或切换筛选条件后再查看。"
                  />
                </div>
              ) : (
                <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
                  <div className="max-h-[720px] space-y-3 overflow-y-auto pr-1">
                    {reports.map((report) => (
                      <button
                        key={report.id}
                        onClick={() => void handleView(report.id)}
                        className={`w-full rounded-2xl border p-4 text-left transition-colors ${
                          selectedReport?.id === report.id
                            ? "border-indigo-300 bg-indigo-50"
                            : "border-slate-200 hover:bg-slate-50"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-2">
                            <p className="text-sm font-semibold text-slate-900">
                              {reportDisplayText(report.title, "未命名研究报告")}
                            </p>
                            <p className="text-xs text-slate-500">{reportTypeLabel(report)}</p>
                            <p className="text-xs text-slate-500">
                              生成时间：{report.created_at || report.report_date || "待核验"}
                            </p>
                            <p className="text-xs leading-5 text-slate-600">
                              {reportDisplayText(report.summary, "当前暂无摘要说明。")}
                            </p>
                          </div>
                          <div className="flex flex-col gap-2 text-[11px]">
                            <span className="rounded-full bg-blue-50 px-2.5 py-1 text-blue-700">研究口径</span>
                            <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">支持 PDF</span>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    {selectedReport ? (
                      <div className="space-y-4">
                        <div className="flex flex-wrap items-center justify-between gap-4">
                          <div>
                            <h3 className="text-lg font-semibold text-slate-900">
                              {reportDisplayText(selectedReport.title, "未命名研究报告")}
                            </h3>
                            <p className="mt-1 text-xs text-slate-500">
                              {reportTypeLabel(selectedReport)} · 数据截至 {selectedReport.report_date || "待核验"}
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <span className="rounded-full bg-blue-50 px-3 py-1 text-xs text-blue-700">研究口径</span>
                            <span className="rounded-full bg-amber-50 px-3 py-1 text-xs text-amber-700">非实盘数据</span>
                          </div>
                        </div>

                        <div className="flex flex-wrap gap-3">
                          <a
                            href={`/reports/${selectedReport.id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn-secondary px-4 py-2 text-sm"
                          >
                            查看 HTML 报告
                          </a>
                          <button
                            onClick={() => router.push(`/reports/${selectedReport.id}`)}
                            className="btn-secondary px-4 py-2 text-sm"
                          >
                            📷 查看并下载 PNG
                          </button>
                          <button
                            onClick={() => void handleDownloadPdf(selectedReport)}
                            disabled={downloadingPdf === selectedReport.id}
                            className="btn-primary px-4 py-2 text-sm"
                          >
                            {downloadingPdf === selectedReport.id ? "正在导出 PDF..." : "📄 下载 PDF 报告"}
                          </button>
                        </div>

                        <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
                          点击"查看并下载 PNG"进入报告详情页，可下载报告长图。
                        </div>

                        <div className="rounded-2xl border border-slate-200 bg-white p-5">
                          <div
                            className="prose prose-sm max-w-none prose-headings:scroll-mt-24"
                            dangerouslySetInnerHTML={{ __html: previewHtml }}
                          />
                        </div>
                      </div>
                    ) : (
                      <div className="flex min-h-[420px] items-center justify-center text-center">
                        <div>
                          <p className="text-sm text-slate-700">请选择一份已生成报告，查看真实入库后的正文内容。</p>
                          <p className="mt-2 text-xs text-slate-500">
                            如果原始文本存在编码异常，预览区会自动启用展示保护。
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </section>
          </div>
        ) : (
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4">
              <h2 className="text-base font-semibold text-slate-900">券商研报资料索引</h2>
              <p className="mt-1 text-xs text-slate-500">
                下方记录均为第三方研究资料索引，仅供参考输入，不代表平台自有研究结论。
              </p>
            </div>

            {loading ? (
              <div className="space-y-3">
                <SkeletonCard />
                <SkeletonCard />
              </div>
            ) : researchReports.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 py-10">
                <EmptyState
                  message="当前暂无可展示的券商研报记录"
                  description="这通常表示外部资料源尚未完成同步。"
                />
              </div>
            ) : (
              <div className="space-y-3">
                {researchReports.map((report) => (
                  <div key={`${report.info_code}-${report.publish_date}`} className="rounded-2xl border border-slate-200 p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="space-y-2">
                        <a
                          href={report.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-semibold text-slate-900 hover:text-indigo-600"
                        >
                          {reportDisplayText(report.title, "外部研报标题暂不可用")}
                        </a>
                        <p className="text-xs text-slate-500">
                          {report.org_name || "机构待标注"} · {report.publish_date || "发布日期待核验"} ·{" "}
                          {report.stock_code || "全市场"}
                        </p>
                        <p className="text-xs text-slate-600">
                          原始评级：{reportDisplayText(report.rating, "原始评级存在编码异常，已隐藏")}
                        </p>
                      </div>
                      <span className="rounded-full bg-cyan-50 px-3 py-1 text-xs text-cyan-700">第三方资料</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
