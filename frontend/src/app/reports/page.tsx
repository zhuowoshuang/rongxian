"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { getReports, getReport, generateReport, generateStyleReport, downloadReportPdf, searchStocks, getResearchReports } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import { showToast } from "@/components/ui/Toast";
import type { ReportItem, ResearchReportItem, StockSearchResult } from "@/types";

// ==================== Markdown → 纯 HTML 渲染 ====================

function mdToHtml(md: string): string {
  if (!md) return "";
  let html = md;

  // 代码块
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:8px;padding:16px;overflow-x:auto;font-family:'JetBrains Mono',monospace;font-size:13px;color:#334155;margin:16px 0;line-height:1.6"><code>${code.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</code></pre>`
  );

  // 标题
  html = html.replace(/^### (.+)$/gm, '<h3 style="font-size:16px;font-weight:700;color:#1e293b;margin:24px 0 8px;padding-bottom:6px;border-bottom:1px solid #e2e8f0">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 style="font-size:20px;font-weight:700;color:#0f172a;margin:28px 0 10px;padding-bottom:8px;border-bottom:2px solid #6366f1">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1 style="font-size:24px;font-weight:800;color:#0f172a;margin:32px 0 12px;padding-bottom:10px;border-bottom:3px solid #6366f1">$1</h1>');

  // 引用块
  html = html.replace(/^> (.+)$/gm, '<blockquote style="border-left:4px solid #6366f1;background:#f8fafc;padding:12px 16px;margin:12px 0;border-radius:0 8px 8px 0;color:#475569;font-size:14px">$1</blockquote>');

  // 水平线
  html = html.replace(/^---$/gm, '<hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0">');

  // 表格
  html = html.replace(/\n(\|.+\|)\n(\|[-| :]+\|)\n((?:\|.+\|\n?)+)/g, (_, header, sep, body) => {
    const ths = header.split("|").filter((c: string) => c.trim()).map((c: string) =>
      `<th style="padding:10px 14px;text-align:left;font-weight:600;color:#475569;border-bottom:2px solid #e2e8f0;background:#f8fafc;font-size:13px">${c.trim()}</th>`
    ).join("");
    const rows = body.trim().split("\n").map((row: string) => {
      const tds = row.split("|").filter((c: string) => c.trim()).map((c: string) =>
        `<td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;font-size:13px;color:#334155">${c.trim()}</td>`
      ).join("");
      return `<tr>${tds}</tr>`;
    }).join("");
    return `<div style="overflow-x:auto;margin:16px 0;border-radius:8px;border:1px solid #e2e8f0"><table style="width:100%;border-collapse:collapse"><thead><tr>${ths}</tr></thead><tbody>${rows}</tbody></table></div>`;
  });

  // 无序列表
  html = html.replace(/^- (.+)$/gm, '<div style="display:flex;gap:8px;margin:4px 0;padding-left:8px"><span style="color:#6366f1;font-weight:bold;flex-shrink:0">•</span><span style="color:#334155;font-size:14px;line-height:1.6">$1</span></div>');

  // 有序列表
  html = html.replace(/^(\d+)\. (.+)$/gm, '<div style="display:flex;gap:8px;margin:4px 0;padding-left:8px"><span style="color:#6366f1;font-weight:600;flex-shrink:0;min-width:20px">$1.</span><span style="color:#334155;font-size:14px;line-height:1.6">$2</span></div>');

  // 加粗和行内代码
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong style="font-weight:600;color:#1e293b">$1</strong>');
  html = html.replace(/`([^`]+)`/g, '<code style="background:#f1f5f9;color:#6366f1;padding:2px 6px;border-radius:4px;font-family:JetBrains Mono,monospace;font-size:12px">$1</code>');

  // 段落（双换行）
  html = html.replace(/\n\n/g, '</p><p style="margin:8px 0;color:#475569;font-size:14px;line-height:1.8">');
  // 单换行
  html = html.replace(/\n/g, "<br>");

  // 包裹
  html = `<p style="margin:8px 0;color:#475569;font-size:14px;line-height:1.8">${html}</p>`;

  return html;
}

// ==================== 报告 HTML 模板（浅色 UI）====================

function buildReportHtml(title: string, date: string, type: string, content: string): string {
  return `
<div style="max-width:900px;margin:0 auto;background:#ffffff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;color:#334155">
  <!-- 顶部装饰条 -->
  <div style="height:4px;background:linear-gradient(90deg,#6366f1,#8b5cf6,#a78bfa);border-radius:4px 4px 0 0"></div>

  <!-- 报告头部 -->
  <div style="padding:32px 40px 24px;background:linear-gradient(135deg,#f8fafc,#eef2ff);border-bottom:1px solid #e2e8f0">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
      <div style="width:36px;height:36px;background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:10px;display:flex;align-items:center;justify-content:center;color:white;font-size:18px;font-weight:800">融</div>
      <div>
        <div style="font-size:22px;font-weight:800;color:#0f172a;letter-spacing:-0.5px">${title}</div>
        <div style="font-size:13px;color:#64748b;margin-top:2px">清数智算量化分析系统 · ${date} · ${type}</div>
      </div>
    </div>
  </div>

  <!-- 报告正文 -->
  <div style="padding:24px 40px 40px;min-height:400px">${content}</div>

  <!-- 底部 -->
  <div style="padding:16px 40px;background:#f8fafc;border-top:1px solid #e2e8f0;text-align:center">
    <div style="font-size:11px;color:#94a3b8">本报告由清数智算量化分析系统自动生成，仅供研究参考，不构成投资建议</div>
    <div style="font-size:11px;color:#cbd5e1;margin-top:4px">RongXian Quantitative Analysis System</div>
  </div>
</div>`;
}

// ==================== PNG 下载 =====================

function downloadAsPng(elementId: string, filename: string) {
  const el = document.getElementById(elementId);
  if (!el) return;

  // 使用 Canvas API 将 HTML 转为图片
  import("html2canvas").then(({ default: html2canvas }) => {
    html2canvas(el, {
      scale: 2,
      backgroundColor: "#ffffff",
      useCORS: true,
      logging: false,
    }).then((canvas: HTMLCanvasElement) => {
      const link = document.createElement("a");
      link.download = `${filename}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
    });
  }).catch(() => {
    // html2canvas 不可用时，降级为打印
    showToast("error", "PNG 下载组件加载失败，请使用浏览器打印功能 (Ctrl+P)");
  });
}

// ==================== 主页面 ====================

export default function ReportsPage() {
  const { t } = useTranslation();
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [reportType, setReportType] = useState<string>("");
  const [selectedReport, setSelectedReport] = useState<(ReportItem & { content_markdown: string }) | null>(null);
  const [generating, setGenerating] = useState(false);
  const [selectedStyle, setSelectedStyle] = useState<string>("");
  const [downloadingPdf, setDownloadingPdf] = useState<number | null>(null);
  const [downloadingPng, setDownloadingPng] = useState(false);

  const styleOptions = [
    { key: "steady", label: t("style.steady"), icon: "🛡️", desc: t("style.steady.desc"), color: "#3b82f6" },
    { key: "aggressive", label: t("style.aggressive"), icon: "🚀", desc: t("style.aggressive.desc"), color: "#8b5cf6" },
    { key: "conservative", label: t("style.conservative"), icon: "🏦", desc: t("style.conservative.desc"), color: "#10b981" },
  ];

  const [researchReports, setResearchReports] = useState<ResearchReportItem[]>([]);
  const [researchTotal, setResearchTotal] = useState(0);
  const [researchLoading, setResearchLoading] = useState(false);
  const [researchPage, setResearchPage] = useState(1);
  const [researchStock, setResearchStock] = useState<StockSearchResult | null>(null);

  const [activeTab, setActiveTab] = useState("self");

  const [stockKeyword, setStockKeyword] = useState("");
  const [stockResults, setStockResults] = useState<StockSearchResult[]>([]);
  const [selectedStock, setSelectedStock] = useState<StockSearchResult | null>(null);
  const [showStockSearch, setShowStockSearch] = useState(false);
  const [stockSearching, setStockSearching] = useState(false);
  const stockSearchRef = useRef<HTMLDivElement>(null);

  const [rStockKeyword, setRStockKeyword] = useState("");
  const [rStockResults, setRStockResults] = useState<StockSearchResult[]>([]);
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

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (stockSearchRef.current && !stockSearchRef.current.contains(e.target as Node)) setShowStockSearch(false);
      if (rStockSearchRef.current && !rStockSearchRef.current.contains(e.target as Node)) setShowRStockSearch(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (stockKeyword.length < 1) { setStockResults([]); return; }
    setStockSearching(true);
    const timer = setTimeout(() => {
      searchStocks(stockKeyword)
        .then((data) => { setStockResults(data || []); setShowStockSearch(true); })
        .catch(() => { setStockResults([]); })
        .finally(() => setStockSearching(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [stockKeyword]);

  useEffect(() => {
    if (rStockKeyword.length < 1) { setRStockResults([]); return; }
    setRStockSearching(true);
    const timer = setTimeout(() => {
      searchStocks(rStockKeyword)
        .then((data) => { setRStockResults(data || []); setShowRStockSearch(true); })
        .catch(() => { setRStockResults([]); })
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

  const handleDownloadPng = () => {
    if (!selectedReport) return;
    setDownloadingPng(true);
    downloadAsPng("report-printable", selectedReport.title);
    setTimeout(() => setDownloadingPng(false), 2000);
  };

  // 浅色 UI 样式常量
  const cardStyle = "bg-white rounded-2xl border border-gray-200 shadow-sm";
  const cardPadded = `${cardStyle} p-6`;
  const inputStyle = "w-full px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-gray-800 text-sm focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 transition-all placeholder:text-gray-400";
  const btnPrimary = "px-5 py-2.5 rounded-xl text-sm font-medium text-white bg-indigo-500 hover:bg-indigo-600 active:bg-indigo-700 transition-all shadow-sm shadow-indigo-200 disabled:opacity-50 disabled:cursor-not-allowed";
  const btnSecondary = "px-4 py-2.5 rounded-xl text-sm font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 border border-gray-200 transition-all disabled:opacity-40";
  const tabBase = "px-4 py-2 rounded-lg text-sm font-medium transition-all cursor-pointer";

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-[1400px] mx-auto space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center gap-3">
          <div className="w-1 h-7 bg-indigo-500 rounded-full" />
          <h1 className="text-xl font-bold text-gray-900">{t("reports.title")}</h1>
        </div>

        {/* Tab 切换 */}
        <div className="flex gap-2 bg-white rounded-xl p-1 border border-gray-200 w-fit shadow-sm">
          {[{ key: "self", label: t("reports.system") }, { key: "research", label: t("reports.broker") }].map((tab) => (
            <button key={tab.key} onClick={() => setActiveTab(tab.key)}
              className={`${tabBase} ${activeTab === tab.key ? "bg-indigo-500 text-white shadow-sm" : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"}`}>
              {tab.label}
            </button>
          ))}
        </div>

        {/* ========== 系统报告 Tab ========== */}
        {activeTab === "self" && (
          <>
            {/* 生成面板 */}
            <div className={cardPadded}>
              <h3 className="text-sm font-semibold text-gray-700 mb-4">{t("reports.generate")}</h3>
              <div className="space-y-4">
                {/* 风格选择 */}
                <div>
                  <label className="text-xs text-gray-400 mb-2 block">{t("reports.styleHint")}</label>
                  <div className="flex gap-3">
                    <button onClick={() => setSelectedStyle("")}
                      className={`flex-1 px-3 py-2.5 rounded-xl text-sm font-medium transition-all border ${selectedStyle === "" ? "bg-indigo-50 border-indigo-300 text-indigo-700" : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50"}`}>
                      {t("reports.general")}
                    </button>
                    {styleOptions.map((s) => (
                      <button key={s.key} onClick={() => setSelectedStyle(s.key)}
                        className={`flex-1 px-3 py-2.5 rounded-xl text-sm font-medium transition-all border ${selectedStyle === s.key ? "text-white shadow-sm" : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50"}`}
                        style={selectedStyle === s.key ? { background: s.color, borderColor: s.color } : {}}>
                        {s.icon} {s.label}
                        <span className="block text-[10px] opacity-70 mt-0.5">{s.desc}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* 生成按钮 */}
                <div className="flex gap-4 items-end flex-wrap">
                  <button onClick={() => handleGenerate("DAILY")} disabled={generating} className={btnPrimary}>
                    {generating ? t("reports.generating") : t("reports.generateDaily")}
                  </button>
                  <div className="text-gray-200">|</div>
                  <div className="flex-1 relative min-w-[250px]">
                    <label className="text-xs text-gray-400 mb-1 block">{t("reports.stockAnalysis")}</label>
                    <div className="flex gap-2">
                      <div className="flex-1 relative" ref={stockSearchRef}>
                        <input type="text" value={selectedStock ? `${selectedStock.symbol} ${selectedStock.name}` : stockKeyword}
                          onChange={(e) => { setStockKeyword(e.target.value); setSelectedStock(null); }}
                          onFocus={() => { if (stockResults.length > 0) setShowStockSearch(true); }}
                          placeholder={t("reports.stockSearch")} className={inputStyle} />
                        {showStockSearch && stockKeyword.length > 0 && (
                          <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-lg z-50 max-h-48 overflow-y-auto">
                            {stockSearching ? (
                              <div className="px-3 py-2 text-xs text-gray-400">{t("reports.searching")}</div>
                            ) : stockResults.length > 0 ? (
                              stockResults.map((s) => (
                                <button key={s.symbol} onClick={() => { setSelectedStock(s); setStockKeyword(""); setShowStockSearch(false); setStockResults([]); }}
                                  className="w-full text-left px-3 py-2 hover:bg-indigo-50 text-sm flex items-center gap-2 text-gray-700 transition-colors">
                                  <span className="font-mono text-indigo-500">{s.symbol}</span><span>{s.name}</span>
                                  <span className="text-xs text-gray-400 ml-auto">{s.market === "HK" ? t("market.hk") : t("market.aShare")}</span>
                                </button>
                              ))
                            ) : (
                              <div className="px-3 py-2 text-xs text-gray-400">{t("reports.noMatch")}</div>
                            )}
                          </div>
                        )}
                      </div>
                      <button onClick={() => handleGenerate("STOCK")} disabled={generating || !selectedStock} className={`${btnPrimary} whitespace-nowrap`}>{t("reports.generateStock")}</button>
                    </div>
                  </div>
                </div>

                {/* 风格报告 */}
                <div className="border-t border-gray-100 pt-4">
                  <label className="text-xs text-gray-400 mb-2 block">{t("reports.generateStyleHint")}</label>
                  <div className="flex gap-3">
                    {styleOptions.map((s) => (
                      <button key={s.key} onClick={() => handleGenerateStyle(s.key)} disabled={generating}
                        className="flex-1 px-4 py-3 rounded-xl text-sm font-medium transition-all border text-white shadow-sm disabled:opacity-50 hover:brightness-110"
                        style={{ background: s.color, borderColor: s.color }}>
                        {s.icon} {t("reports.generateStyleReport", { style: s.label })}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* 类型筛选 */}
            <div className="flex gap-2 bg-white rounded-xl p-1 border border-gray-200 w-fit shadow-sm">
              {[{ key: "", label: t("common.all") }, { key: "DAILY", label: t("reports.strategyReport") }, { key: "STYLE", label: t("reports.styleReport") }, { key: "STOCK", label: t("reports.stockReport") }].map((tab) => (
                <button key={tab.key} onClick={() => setReportType(tab.key)}
                  className={`${tabBase} ${reportType === tab.key ? "bg-indigo-50 text-indigo-700" : "text-gray-400 hover:text-gray-600 hover:bg-gray-50"}`}>
                  {tab.label}
                </button>
              ))}
            </div>

            {/* 报告列表 + 内容 */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* 左侧列表 */}
              <div className="lg:col-span-1 space-y-3 max-h-[calc(100vh-380px)] overflow-y-auto">
                {loading ? (
                  <div className={`${cardPadded} animate-pulse`}><div className="h-4 bg-gray-100 rounded w-3/4 mb-3"></div><div className="h-3 bg-gray-100 rounded w-full mb-2"></div><div className="h-3 bg-gray-100 rounded w-2/3"></div></div>
                ) : reports.length === 0 ? (
                  <div className={`${cardPadded} text-center text-gray-400 text-sm`}>{t("common.noReport")}</div>
                ) : reports.map((r) => (
                  <button key={r.id} onClick={() => handleView(r.id)}
                    className={`w-full text-left ${cardPadded} cursor-pointer transition-all hover:shadow-md ${selectedReport?.id === r.id ? "!border-indigo-400 !bg-indigo-50/50 shadow-md" : ""}`}>
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${r.report_type === "DAILY" ? "bg-blue-50 text-blue-600" : r.report_type === "STYLE" ? "bg-amber-50 text-amber-600" : "bg-emerald-50 text-emerald-600"}`}>
                        {r.report_type === "DAILY" ? t("reports.strategyReport") : r.report_type === "STYLE" ? t("reports.styleReport") : t("reports.stockReport")}
                      </span>
                      {r.style && (
                        <span className={`text-[10px] px-2 py-0.5 rounded-full ${r.style === "steady" ? "bg-blue-50 text-blue-500" : r.style === "aggressive" ? "bg-purple-50 text-purple-500" : "bg-green-50 text-green-500"}`}>
                          {r.style === "steady" ? "🛡️" + t("style.steady") : r.style === "aggressive" ? "🚀" + t("style.aggressive") : "🏦" + t("style.conservative")}
                        </span>
                      )}
                      <span className="text-xs text-gray-400 ml-auto">{r.report_date}</span>
                    </div>
                    <p className="font-medium text-sm text-gray-800">{r.title}</p>
                    <p className="text-xs text-gray-400 mt-1 line-clamp-2">{r.summary}</p>
                  </button>
                ))}
              </div>

              {/* 右侧内容 */}
              <div className="lg:col-span-2">
                {selectedReport ? (
                  <div className="space-y-4">
                    {/* 操作栏 */}
                    <div className={`${cardPadded} flex items-center justify-between`}>
                      <div>
                        <h2 className="text-lg font-bold text-gray-900">{selectedReport.title}</h2>
                        <p className="text-xs text-gray-400 mt-1">{selectedReport.report_date} · {selectedReport.report_type === "DAILY" ? t("reports.strategyReport") : selectedReport.report_type === "STYLE" ? t("reports.styleReport") : t("reports.stockReport")}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={handleDownloadPng} disabled={downloadingPng}
                          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-500 text-white hover:bg-emerald-600 transition-colors text-xs shadow-sm shadow-emerald-200 disabled:opacity-50">
                          📷 {downloadingPng ? "生成中..." : "下载 PNG"}
                        </button>
                        <button onClick={() => handleDownloadPdf(selectedReport.id, selectedReport.title)} disabled={downloadingPdf === selectedReport.id}
                          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-500 text-white hover:bg-indigo-600 transition-colors text-xs shadow-sm shadow-indigo-200 disabled:opacity-50">
                          📄 {downloadingPdf === selectedReport.id ? t("reports.downloading") : t("reports.downloadPdf")}
                        </button>
                      </div>
                    </div>

                    {/* 报告正文（浅色渲染） */}
                    <div id="report-printable" className={cardStyle} style={{ overflow: "hidden" }}
                      dangerouslySetInnerHTML={{ __html: buildReportHtml(
                        selectedReport.title,
                        selectedReport.report_date,
                        selectedReport.report_type === "DAILY" ? t("reports.strategyReport") : selectedReport.report_type === "STYLE" ? t("reports.styleReport") : t("reports.stockReport"),
                        mdToHtml(selectedReport.content_markdown || "")
                      )}} />
                  </div>
                ) : (
                  <div className={`${cardPadded} flex items-center justify-center h-64 text-gray-400 text-sm`}>
                    {t("common.selectReport")}
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {/* ========== 券商研报 Tab ========== */}
        {activeTab === "research" && (
          <>
            <div className={cardPadded}>
              <div className="flex gap-3 items-end flex-wrap">
                <div className="flex-1 relative min-w-[200px]" ref={rStockSearchRef}>
                  <label className="text-xs text-gray-400 mb-1 block">{t("reports.brokerFilter")}</label>
                  <input type="text" value={researchStock ? `${researchStock.symbol} ${researchStock.name}` : rStockKeyword}
                    onChange={(e) => { setRStockKeyword(e.target.value); setResearchStock(null); }}
                    onFocus={() => { if (rStockResults.length > 0) setShowRStockSearch(true); }}
                    placeholder={t("reports.brokerSearch")} className={inputStyle} />
                  {showRStockSearch && rStockKeyword.length > 0 && (
                    <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-lg z-50 max-h-48 overflow-y-auto">
                      {rStockSearching ? (
                        <div className="px-3 py-2 text-xs text-gray-400">{t("reports.searching")}</div>
                      ) : rStockResults.length > 0 ? (
                        rStockResults.map((s) => (
                          <button key={s.symbol} onClick={() => { setResearchStock(s); setRStockKeyword(""); setShowRStockSearch(false); setRStockResults([]); }}
                            className="w-full text-left px-3 py-2 hover:bg-indigo-50 text-sm flex items-center gap-2 text-gray-700 transition-colors">
                            <span className="font-mono text-indigo-500">{s.symbol}</span><span>{s.name}</span>
                          </button>
                        ))
                      ) : (
                        <div className="px-3 py-2 text-xs text-gray-400">{t("reports.noMatch")}</div>
                      )}
                    </div>
                  )}
                </div>
                <button onClick={() => fetchResearchReports(1, researchStock?.symbol || (rStockKeyword.length > 0 ? rStockKeyword : undefined))} disabled={researchLoading} className={btnPrimary}>
                  {researchLoading ? t("reports.loading") : t("reports.searchReport")}
                </button>
                {(researchStock || rStockKeyword) && (
                  <button onClick={() => { setResearchStock(null); setRStockKeyword(""); fetchResearchReports(1); }} className={btnSecondary}>{t("reports.clearFilter")}</button>
                )}
              </div>
              <p className="text-xs text-gray-400 mt-2">{t("reports.dataSource", { total: String(researchTotal) })}</p>
            </div>

            {researchLoading ? (
              <div className={`${cardPadded} animate-pulse`}><div className="h-4 bg-gray-100 rounded w-3/4 mb-3"></div><div className="h-3 bg-gray-100 rounded w-full"></div></div>
            ) : researchReports.length === 0 ? (
              <div className={`${cardPadded} text-center text-gray-400 text-sm`}>{t("common.noResearch")}</div>
            ) : (
              <div className="space-y-3">
                {researchReports.map((r, idx) => (
                  <div key={idx} className={cardPadded}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                          {r.stock_code && <span className="text-xs font-mono px-2 py-0.5 bg-gray-100 text-gray-500 rounded">{r.stock_code}</span>}
                          {r.stock_name && <span className="text-xs font-medium text-gray-700">{r.stock_name}</span>}
                          {r.rating && (
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                              r.rating.includes("买入") || r.rating.includes("强推") ? "bg-red-50 text-red-500"
                                : r.rating.includes("增持") || r.rating.includes("推荐") ? "bg-orange-50 text-orange-500"
                                : r.rating.includes("中性") || r.rating.includes("持有") ? "bg-gray-100 text-gray-500"
                                : "bg-blue-50 text-blue-500"
                            }`}>{r.rating}</span>
                          )}
                          {r.industry && <span className="text-xs text-gray-400">{r.industry}</span>}
                        </div>
                        <a href={r.url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-gray-800 hover:text-indigo-500 transition-colors line-clamp-2">{r.title}</a>
                        <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                          <span>{r.org_name}</span>
                          {r.researcher && <span>{t("reports.researcher")} {r.researcher}</span>}
                          <span>{r.publish_date}</span>
                        </div>
                      </div>
                      {(r.predict_this_year_eps || r.predict_this_year_pe) && (
                        <div className="flex-shrink-0 bg-gray-50 rounded-lg p-3 text-xs space-y-1 min-w-[180px] border border-gray-100">
                          <div className="font-medium text-gray-400 mb-1">{t("reports.earningsForecast")}</div>
                          <div className="grid grid-cols-3 gap-2 text-center">
                            {[[t("reports.thisYear"), r.predict_this_year_eps, r.predict_this_year_pe], [t("reports.nextYear"), r.predict_next_year_eps, r.predict_next_year_pe], [t("reports.yearAfter"), r.predict_next_two_year_eps, r.predict_next_two_year_pe]].map(([label, eps, pe]) => (
                              <div key={label as string}>
                                <div className="text-gray-400">{label}</div>
                                {eps && <div className="font-mono text-gray-700">EPS {(eps as number).toFixed(2)}</div>}
                                {pe && <div className="font-mono text-gray-400">PE {(pe as number).toFixed(1)}</div>}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {researchTotal > 20 && (
                  <div className="flex justify-center gap-2 pt-4">
                    <button onClick={() => fetchResearchReports(researchPage - 1, researchStock?.symbol)} disabled={researchPage <= 1} className={btnSecondary}>{t("common.prevPage")}</button>
                    <span className="px-4 py-2 text-sm text-gray-400">{t("common.page", { page: String(researchPage), total: String(Math.ceil(researchTotal / 20)) })}</span>
                    <button onClick={() => fetchResearchReports(researchPage + 1, researchStock?.symbol)} disabled={researchPage >= Math.ceil(researchTotal / 20)} className={btnSecondary}>{t("common.nextPage")}</button>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* 底部免责声明 */}
        <div className="text-center text-xs text-gray-300 py-4">
          {t("app.disclaimer")} {t("app.disclaimer.broker")}
        </div>
      </div>
    </div>
  );
}
