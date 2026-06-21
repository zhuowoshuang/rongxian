"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { getReports, getReport, generateReport, generateStyleReport, downloadReportPdf, searchStocks, getResearchReports } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";
import TabSwitch from "@/components/ui/TabSwitch";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { FileText, Download, Search } from "lucide-react";
import { showToast } from "@/components/ui/Toast";

export default function ReportsPage() {
  const { t } = useTranslation();
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [reportType, setReportType] = useState<string>("");
  const [selectedReport, setSelectedReport] = useState<any>(null);
  const [generating, setGenerating] = useState(false);
  const [selectedStyle, setSelectedStyle] = useState<string>("");
  const [downloadingPdf, setDownloadingPdf] = useState<number | null>(null);

  const styleOptions = [
    { key: "steady", label: t("style.steady"), icon: "🛡️", desc: t("style.steady.desc"), color: "from-blue-500/20 to-blue-600/10 border-blue-500/30 text-blue-300" },
    { key: "aggressive", label: t("style.aggressive"), icon: "🚀", desc: t("style.aggressive.desc"), color: "from-purple-500/20 to-purple-600/10 border-purple-500/30 text-purple-300" },
    { key: "conservative", label: t("style.conservative"), icon: "🏦", desc: t("style.conservative.desc"), color: "from-green-500/20 to-green-600/10 border-green-500/30 text-green-300" },
  ];

  const [researchReports, setResearchReports] = useState<any[]>([]);
  const [researchTotal, setResearchTotal] = useState(0);
  const [researchLoading, setResearchLoading] = useState(false);
  const [researchPage, setResearchPage] = useState(1);
  const [researchStock, setResearchStock] = useState<any>(null);

  const [activeTab, setActiveTab] = useState("self");

  const [stockKeyword, setStockKeyword] = useState("");
  const [stockResults, setStockResults] = useState<any[]>([]);
  const [selectedStock, setSelectedStock] = useState<any>(null);
  const [showStockSearch, setShowStockSearch] = useState(false);
  const [stockSearching, setStockSearching] = useState(false);
  const stockSearchRef = useRef<HTMLDivElement>(null);

  const [rStockKeyword, setRStockKeyword] = useState("");
  const [rStockResults, setRStockResults] = useState<any[]>([]);
  const [showRStockSearch, setShowRStockSearch] = useState(false);
  const [rStockSearching, setRStockSearching] = useState(false);
  const rStockSearchRef = useRef<HTMLDivElement>(null);

  const fetchReports = () => {
    setLoading(true);
    getReports({ report_type: reportType || undefined, page_size: 50 })
      .then((data) => setReports(data.items || []))
      .catch(() => { setReports([]); showToast("error", t("common.loadFailed")); })
      .finally(() => setLoading(false));
  };

  const fetchResearchReports = (page = 1, symbol?: string) => {
    setResearchLoading(true);
    getResearchReports({ symbol, page, page_size: 20 })
      .then((data) => { setResearchReports(data.reports || []); setResearchTotal(data.total || 0); setResearchPage(page); })
      .catch(() => { setResearchReports([]); setResearchTotal(0); })
      .finally(() => setResearchLoading(false));
  };

  useEffect(() => { fetchReports(); }, [reportType]);
  useEffect(() => { if (activeTab === "research") fetchResearchReports(1, researchStock?.symbol); }, [activeTab]);

  // 点击外部关闭下拉
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (stockSearchRef.current && !stockSearchRef.current.contains(e.target as Node)) setShowStockSearch(false);
      if (rStockSearchRef.current && !rStockSearchRef.current.contains(e.target as Node)) setShowRStockSearch(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // 系统报告 - 股票搜索
  useEffect(() => {
    if (stockKeyword.length < 1) { setStockResults([]); return; }
    setStockSearching(true);
    const timer = setTimeout(() => {
      searchStocks(stockKeyword)
        .then((data) => { setStockResults(data || []); setShowStockSearch(true); })
        .catch((err) => { console.error("Stock search failed:", err); setStockResults([]); })
        .finally(() => setStockSearching(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [stockKeyword]);

  // 券商研报 - 股票搜索
  useEffect(() => {
    if (rStockKeyword.length < 1) { setRStockResults([]); return; }
    setRStockSearching(true);
    const timer = setTimeout(() => {
      searchStocks(rStockKeyword)
        .then((data) => { setRStockResults(data || []); setShowRStockSearch(true); })
        .catch((err) => { console.error("Research stock search failed:", err); setRStockResults([]); })
        .finally(() => setRStockSearching(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [rStockKeyword]);

  const handleGenerate = async (type: string) => {
    setGenerating(true);
    try {
      if (type === "STOCK" && selectedStock) await generateReport({ report_type: "STOCK", stock_symbol: selectedStock.symbol });
      else if (type === "DAILY") await generateReport({ report_type: "DAILY", style: selectedStyle || undefined });
      showToast("success", t("reports.generateSuccess"));
      fetchReports();
    } catch (e: any) {
      console.error(e);
      showToast("error", e.message || t("reports.generateError"));
    }
    setGenerating(false);
  };

  const handleGenerateStyle = async (style: string) => {
    setGenerating(true);
    try {
      await generateStyleReport(style);
      showToast("success", t("reports.styleGenerateSuccess"));
      fetchReports();
    } catch (e: any) {
      console.error(e);
      showToast("error", e.message || t("reports.styleGenerateError"));
    }
    setGenerating(false);
  };

  const handleDownloadPdf = async (id: number, title: string) => {
    setDownloadingPdf(id);
    try {
      await downloadReportPdf(id, `${title}.pdf`);
      showToast("success", t("reports.pdfStarted"));
    } catch (e: any) {
      console.error(e);
      showToast("error", e.message || t("reports.pdfError"));
    }
    setDownloadingPdf(null);
  };

  const handleView = async (id: number) => {
    try {
      const report = await getReport(id);
      setSelectedReport(report);
    } catch (e: any) {
      showToast("error", e.message || t("common.loadFailed"));
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
      <h1 className="text-xl font-bold text-white flex items-center gap-2">
        <span className="w-1 h-6 bg-primary-500 rounded-full" />
        {t("reports.title")}
      </h1>

      <TabSwitch
        tabs={[
          { key: "self", label: t("reports.system") },
          { key: "research", label: t("reports.broker") },
        ]}
        active={activeTab}
        onChange={setActiveTab}
        className="w-fit"
      />

      {activeTab === "self" && (
        <>
          <GlassCard title={t("reports.generate")}>
            <div className="space-y-4">
              {/* 风格选择器 */}
              <div>
                <label className="text-xs text-dark-muted mb-2 block">{t("reports.styleHint")}</label>
                <div className="flex gap-3">
                  <button
                    onClick={() => setSelectedStyle("")}
                    className={`flex-1 px-3 py-2.5 rounded-xl text-sm font-medium transition-all border ${
                      selectedStyle === "" ? "bg-white/[0.08] border-white/[0.15] text-white" : "bg-white/[0.03] border-white/[0.06] text-dark-muted hover:bg-white/[0.05]"
                    }`}
                  >
                    {t("reports.general")}
                  </button>
                  {styleOptions.map((s) => (
                    <button
                      key={s.key}
                      onClick={() => setSelectedStyle(s.key)}
                      className={`flex-1 px-3 py-2.5 rounded-xl text-sm font-medium transition-all border bg-gradient-to-br ${
                        selectedStyle === s.key ? s.color : "bg-white/[0.03] border-white/[0.06] text-dark-muted hover:bg-white/[0.05]"
                      }`}
                    >
                      {s.icon} {s.label}
                      <span className="block text-[10px] opacity-70 mt-0.5">{s.desc}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* 生成按钮行 */}
              <div className="flex gap-4 items-end flex-wrap">
                <button onClick={() => handleGenerate("DAILY")} disabled={generating} className="btn-primary px-5 py-2.5 text-sm disabled:opacity-50">
                  {generating ? t("reports.generating") : t("reports.generateDaily")}
                </button>
                <div className="text-white/20">|</div>
                <div className="flex-1 relative min-w-[250px]">
                  <label className="text-xs text-dark-muted mb-1 block">{t("reports.stockAnalysis")}</label>
                  <div className="flex gap-2">
                    <div className="flex-1 relative" ref={stockSearchRef}>
                      <input
                        type="text"
                        value={selectedStock ? `${selectedStock.symbol} ${selectedStock.name}` : stockKeyword}
                        onChange={(e) => { setStockKeyword(e.target.value); setSelectedStock(null); }}
                        onFocus={() => { if (stockResults.length > 0) setShowStockSearch(true); }}
                        placeholder={t("reports.stockSearch")}
                        className="w-full"
                      />
                      {showStockSearch && stockKeyword.length > 0 && (
                        <div className="absolute top-full left-0 right-0 mt-1 bg-dark-card border border-white/[0.08] rounded-lg shadow-xl z-50 max-h-48 overflow-y-auto">
                          {stockSearching ? (
                            <div className="px-3 py-2 text-xs text-dark-muted">{t("reports.searching")}</div>
                          ) : stockResults.length > 0 ? (
                            stockResults.map((s) => (
                              <button key={s.symbol} onClick={() => { setSelectedStock(s); setStockKeyword(""); setShowStockSearch(false); setStockResults([]); }}
                                className="w-full text-left px-3 py-2 hover:bg-white/[0.05] text-sm flex items-center gap-2 text-dark-text">
                                <span className="font-mono text-primary-400">{s.symbol}</span><span>{s.name}</span>
                                <span className="text-xs text-dark-muted ml-auto">{s.market === "HK" ? t("market.hk") : t("market.aShare")}</span>
                              </button>
                            ))
                          ) : (
                            <div className="px-3 py-2 text-xs text-dark-muted">{t("reports.noMatch")}</div>
                          )}
                        </div>
                      )}
                    </div>
                    <button onClick={() => handleGenerate("STOCK")} disabled={generating || !selectedStock} className="btn-primary px-4 py-2 text-sm disabled:opacity-50 whitespace-nowrap">{t("reports.generateStock")}</button>
                  </div>
                </div>
              </div>

              {/* 风格专属报告生成 */}
              <div className="border-t border-white/[0.06] pt-4">
                <label className="text-xs text-dark-muted mb-2 block">{t("reports.generateStyleHint")}</label>
                <div className="flex gap-3">
                  {styleOptions.map((s) => (
                    <button
                      key={s.key}
                      onClick={() => handleGenerateStyle(s.key)}
                      disabled={generating}
                      className={`flex-1 px-4 py-3 rounded-xl text-sm font-medium transition-all border bg-gradient-to-br ${s.color} disabled:opacity-50 hover:brightness-110`}
                    >
                      {s.icon} {t("reports.generateStyleReport", { style: s.label })}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </GlassCard>

          <TabSwitch
            tabs={[{ key: "", label: t("common.all") }, { key: "DAILY", label: t("reports.strategyReport") }, { key: "STYLE", label: t("reports.styleReport") }, { key: "STOCK", label: t("reports.stockReport") }]}
            active={reportType}
            onChange={setReportType}
            className="w-fit"
          />

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1 space-y-3 max-h-[calc(100vh-320px)] overflow-y-auto">
              {loading ? <SkeletonCard /> : reports.length === 0 ? (
                <GlassCard><EmptyState message={t("common.noReport")} /></GlassCard>
              ) : reports.map((r) => (
                <button key={r.id} onClick={() => handleView(r.id)}
                  className={`w-full text-left card ${selectedReport?.id === r.id ? "!border-primary-500/40 !bg-primary-500/10" : ""}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${r.report_type === "DAILY" ? "bg-blue-500/10 text-blue-400" : r.report_type === "STYLE" ? "bg-amber-500/10 text-amber-400" : "bg-emerald-500/10 text-emerald-400"}`}>
                      {r.report_type === "DAILY" ? t("reports.strategyReport") : r.report_type === "STYLE" ? t("reports.styleReport") : t("reports.stockReport")}
                    </span>
                    {r.style && (
                      <span className={`text-[10px] px-2 py-0.5 rounded-full ${r.style === "steady" ? "bg-blue-500/10 text-blue-300" : r.style === "aggressive" ? "bg-purple-500/10 text-purple-300" : "bg-green-500/10 text-green-300"}`}>
                        {r.style === "steady" ? "🛡️" + t("style.steady") : r.style === "aggressive" ? "🚀" + t("style.aggressive") : "🏦" + t("style.conservative")}
                      </span>
                    )}
                    <span className="text-xs text-dark-muted">{r.report_date}</span>
                  </div>
                  <p className="font-medium text-sm text-dark-text">{r.title}</p>
                  <p className="text-xs text-dark-muted mt-1 line-clamp-2">{r.summary}</p>
                </button>
              ))}
            </div>

            <div className="lg:col-span-2">
              {selectedReport ? (
                <GlassCard className="max-h-[calc(100vh-320px)] overflow-y-auto">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h2 className="text-lg font-bold text-white">{selectedReport.title}</h2>
                      <p className="text-xs text-dark-muted mt-1">{selectedReport.report_date} - {selectedReport.report_type === "DAILY" ? t("reports.strategyReport") : selectedReport.report_type === "STYLE" ? t("reports.styleReport") : t("reports.stockReport")}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-3 py-1 rounded-full ${selectedReport.report_type === "DAILY" ? "bg-blue-500/10 text-blue-400" : selectedReport.report_type === "STYLE" ? "bg-amber-500/10 text-amber-400" : "bg-emerald-500/10 text-emerald-400"}`}>
                        {selectedReport.report_type === "DAILY" ? t("reports.strategyReport") : selectedReport.report_type === "STYLE" ? t("reports.styleReport") : t("reports.stockReport")}
                      </span>
                      <button
                        onClick={() => handleDownloadPdf(selectedReport.id, selectedReport.title)}
                        disabled={downloadingPdf === selectedReport.id}
                        className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 transition-colors text-xs disabled:opacity-50"
                      >
                        <Download size={14} />
                        {downloadingPdf === selectedReport.id ? t("reports.downloading") : t("reports.downloadPdf")}
                      </button>
                    </div>
                  </div>
                  <div className="prose prose-sm max-w-none report-content">
                    <MarkdownRenderer content={selectedReport.content_markdown || ""} />
                  </div>
                </GlassCard>
              ) : (
                <GlassCard className="flex items-center justify-center h-64">
                  <EmptyState message={t("common.selectReport")} />
                </GlassCard>
              )}
            </div>
          </div>
        </>
      )}

      {activeTab === "research" && (
        <>
          <GlassCard>
            <div className="flex gap-3 items-end flex-wrap">
              <div className="flex-1 relative min-w-[200px]" ref={rStockSearchRef}>
                <label className="text-xs text-dark-muted mb-1 block">{t("reports.brokerFilter")}</label>
                <input
                  type="text"
                  value={researchStock ? `${researchStock.symbol} ${researchStock.name}` : rStockKeyword}
                  onChange={(e) => { setRStockKeyword(e.target.value); setResearchStock(null); }}
                  onFocus={() => { if (rStockResults.length > 0) setShowRStockSearch(true); }}
                  placeholder={t("reports.brokerSearch")}
                  className="w-full"
                />
                {showRStockSearch && rStockKeyword.length > 0 && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-dark-card border border-white/[0.08] rounded-lg shadow-xl z-50 max-h-48 overflow-y-auto">
                    {rStockSearching ? (
                      <div className="px-3 py-2 text-xs text-dark-muted">{t("reports.searching")}</div>
                    ) : rStockResults.length > 0 ? (
                      rStockResults.map((s) => (
                        <button key={s.symbol} onClick={() => { setResearchStock(s); setRStockKeyword(""); setShowRStockSearch(false); setRStockResults([]); }}
                          className="w-full text-left px-3 py-2 hover:bg-white/[0.05] text-sm flex items-center gap-2 text-dark-text">
                          <span className="font-mono text-primary-400">{s.symbol}</span><span>{s.name}</span>
                        </button>
                      ))
                    ) : (
                      <div className="px-3 py-2 text-xs text-dark-muted">{t("reports.noMatch")}</div>
                    )}
                  </div>
                )}
              </div>
              <button onClick={() => fetchResearchReports(1, researchStock?.symbol || (rStockKeyword.length > 0 ? rStockKeyword : undefined))} disabled={researchLoading} className="btn-primary px-5 py-2.5 text-sm disabled:opacity-50">
                {researchLoading ? t("reports.loading") : t("reports.searchReport")}
              </button>
              {(researchStock || rStockKeyword) && (
                <button onClick={() => { setResearchStock(null); setRStockKeyword(""); fetchResearchReports(1); }} className="btn-secondary px-4 py-2.5 text-sm">{t("reports.clearFilter")}</button>
              )}
            </div>
            <p className="text-xs text-dark-muted mt-2">{t("reports.dataSource", { total: String(researchTotal) })}</p>
          </GlassCard>

          {researchLoading ? <SkeletonCard /> : researchReports.length === 0 ? (
            <GlassCard><EmptyState message={t("common.noResearch")} /></GlassCard>
          ) : (
            <div className="space-y-3">
              {researchReports.map((r, idx) => (
                <GlassCard key={idx}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                        {r.stock_code && <span className="text-xs font-mono px-2 py-0.5 bg-white/5 text-dark-muted rounded">{r.stock_code}</span>}
                        {r.stock_name && <span className="text-xs font-medium text-dark-text">{r.stock_name}</span>}
                        {r.rating && (
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            r.rating.includes("买入") || r.rating.includes("强推") ? "bg-red-500/10 text-red-400"
                              : r.rating.includes("增持") || r.rating.includes("推荐") ? "bg-orange-500/10 text-orange-400"
                              : r.rating.includes("中性") || r.rating.includes("持有") ? "bg-white/5 text-dark-muted"
                              : "bg-blue-500/10 text-blue-400"
                          }`}>{r.rating}</span>
                        )}
                        {r.industry && <span className="text-xs text-dark-muted">{r.industry}</span>}
                      </div>
                      <a href={r.url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-dark-text hover:text-primary-400 transition-colors line-clamp-2">{r.title}</a>
                      <div className="flex items-center gap-3 mt-2 text-xs text-dark-muted">
                        <span>{r.org_name}</span>
                        {r.researcher && <span>{t("reports.researcher")} {r.researcher}</span>}
                        <span>{r.publish_date}</span>
                      </div>
                    </div>
                    {(r.predict_this_year_eps || r.predict_this_year_pe) && (
                      <div className="flex-shrink-0 bg-white/[0.03] rounded-lg p-3 text-xs space-y-1 min-w-[180px] border border-white/[0.06]">
                        <div className="font-medium text-dark-muted mb-1">{t("reports.earningsForecast")}</div>
                        <div className="grid grid-cols-3 gap-2 text-center">
                          {[[t("reports.thisYear"), r.predict_this_year_eps, r.predict_this_year_pe], [t("reports.nextYear"), r.predict_next_year_eps, r.predict_next_year_pe], [t("reports.yearAfter"), r.predict_next_two_year_eps, r.predict_next_two_year_pe]].map(([label, eps, pe]) => (
                            <div key={label as string}>
                              <div className="text-dark-muted">{label}</div>
                              {eps && <div className="font-mono text-dark-text">EPS {(eps as number).toFixed(2)}</div>}
                              {pe && <div className="font-mono text-dark-muted">PE {(pe as number).toFixed(1)}</div>}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </GlassCard>
              ))}

              {researchTotal > 20 && (
                <div className="flex justify-center gap-2 pt-4">
                  <button onClick={() => fetchResearchReports(researchPage - 1, researchStock?.symbol)} disabled={researchPage <= 1} className="btn-secondary px-4 py-2 text-sm disabled:opacity-40">{t("common.prevPage")}</button>
                  <span className="px-4 py-2 text-sm text-dark-muted">{t("common.page", { page: String(researchPage), total: String(Math.ceil(researchTotal / 20)) })}</span>
                  <button onClick={() => fetchResearchReports(researchPage + 1, researchStock?.symbol)} disabled={researchPage >= Math.ceil(researchTotal / 20)} className="btn-secondary px-4 py-2 text-sm disabled:opacity-40">{t("common.nextPage")}</button>
                </div>
              )}
            </div>
          )}
        </>
      )}

      <div className="disclaimer">{t("app.disclaimer")} {t("app.disclaimer.broker")}</div>
    </div>
  );
}

// ==================== Markdown Renderer ====================

function MarkdownRenderer({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: JSX.Element[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (line.trim() === "") { elements.push(<div key={key++} className="h-2" />); i++; continue; }

    if (line.trim().startsWith("```")) {
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) { codeLines.push(lines[i]); i++; }
      i++;
      elements.push(<pre key={key++} className="bg-black/30 text-emerald-400 text-xs p-4 rounded-lg overflow-x-auto my-3 font-mono border border-white/[0.06]"><code>{codeLines.join("\n")}</code></pre>);
      continue;
    }

    if (line.startsWith("# ")) { elements.push(<h1 key={key++} className="text-xl font-bold mt-6 mb-3 text-white border-b border-white/[0.06] pb-2">{renderInline(line.slice(2))}</h1>); i++; continue; }
    if (line.startsWith("## ")) { elements.push(<h2 key={key++} className="text-lg font-bold mt-5 mb-2 text-dark-text">{renderInline(line.slice(3))}</h2>); i++; continue; }
    if (line.startsWith("### ")) { elements.push(<h3 key={key++} className="text-base font-semibold mt-4 mb-2 text-dark-text">{renderInline(line.slice(4))}</h3>); i++; continue; }

    if (line.startsWith("> ")) {
      const quoteLines: string[] = [line.slice(2)];
      while (i + 1 < lines.length && lines[i + 1].startsWith("> ")) { i++; quoteLines.push(lines[i].slice(2)); }
      elements.push(<blockquote key={key++} className="border-l-4 border-primary-500/40 pl-4 py-2 my-3 bg-primary-500/5 text-sm text-dark-text rounded-r-lg">{quoteLines.map((ql, qi) => <p key={qi}>{renderInline(ql)}</p>)}</blockquote>);
      i++; continue;
    }

    if (line.startsWith("|") && i + 1 < lines.length && lines[i + 1].startsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].startsWith("|")) { tableLines.push(lines[i]); i++; }
      const headerCells = tableLines[0].split("|").filter(Boolean).map((c) => c.trim());
      const dataRows = tableLines.slice(2);
      elements.push(
        <div key={key++} className="overflow-x-auto my-3">
          <table className="w-full text-sm border-collapse">
            <thead><tr className="bg-white/[0.03]">{headerCells.map((h, hi) => <th key={hi} className="px-3 py-2 text-left font-semibold text-dark-text border-b border-white/[0.06]">{renderInline(h)}</th>)}</tr></thead>
            <tbody>{dataRows.map((row, ri) => {
              const cells = row.split("|").filter(Boolean).map((c) => c.trim());
              return <tr key={ri} className={ri % 2 === 0 ? "" : "bg-white/[0.02]"}>{cells.map((c, ci) => <td key={ci} className="px-3 py-2 border-b border-white/[0.03] text-dark-text">{renderInline(c)}</td>)}</tr>;
            })}</tbody>
          </table>
        </div>
      );
      continue;
    }

    if (line.trim().startsWith("---")) { elements.push(<hr key={key++} className="my-4 border-white/[0.06]" />); i++; continue; }

    if (line.match(/^\d+\.\s/)) {
      const text = line.replace(/^\d+\.\s/, "");
      elements.push(<div key={key++} className="flex gap-2 ml-4 my-1 text-sm"><span className="text-primary-400 font-medium">{line.match(/^\d+/)?.[0]}.</span><span className="text-dark-text">{renderInline(text)}</span></div>);
      i++; continue;
    }
    if (line.startsWith("- ")) { elements.push(<div key={key++} className="flex gap-2 ml-4 my-1 text-sm"><span className="text-primary-400">-</span><span className="text-dark-text">{renderInline(line.slice(2))}</span></div>); i++; continue; }

    elements.push(<p key={key++} className="text-sm my-2 leading-relaxed text-dark-text">{renderInline(line)}</p>);
    i++;
  }
  return <>{elements}</>;
}

function renderInline(text: string): JSX.Element {
  const parts: (string | JSX.Element)[] = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
    const codeMatch = remaining.match(/`([^`]+)`/);
    let firstMatch: { type: string; index: number; full: string; content: string } | null = null;
    if (boldMatch && boldMatch.index !== undefined) firstMatch = { type: "bold", index: boldMatch.index, full: boldMatch[0], content: boldMatch[1] };
    if (codeMatch && codeMatch.index !== undefined) { if (!firstMatch || codeMatch.index < firstMatch.index) firstMatch = { type: "code", index: codeMatch.index, full: codeMatch[0], content: codeMatch[1] }; }
    if (!firstMatch) { parts.push(remaining); break; }
    if (firstMatch.index > 0) parts.push(remaining.slice(0, firstMatch.index));
    if (firstMatch.type === "bold") parts.push(<strong key={key++} className="font-semibold text-white">{firstMatch.content}</strong>);
    else if (firstMatch.type === "code") parts.push(<code key={key++} className="bg-white/5 text-primary-400 px-1 py-0.5 rounded text-xs font-mono">{firstMatch.content}</code>);
    remaining = remaining.slice(firstMatch.index + firstMatch.full.length);
  }
  return <>{parts.map((p, i) => <span key={i}>{p}</span>)}</>;
}
