"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import { downloadReportPng, getReport } from "@/lib/api";
import { showToast } from "@/components/ui/Toast";
import { useTranslation } from "@/lib/i18n";
import { normalizeResearchText } from "@/lib/utils";
import type { ReportItem } from "@/types";

const REPORT_TYPE_LABELS: Record<string, string> = {
  DAILY: "系统研究报告",
  STYLE: "风格研究报告",
  STOCK: "个股研究报告",
};

// 数据清洗：None/BUY/WATCH/旧投顾表述 → 中文研究口径
function cleanText(text: string): string {
  if (!text) return "暂无数据";
  let clean = normalizeResearchText(text);
  const ratingMap: Record<string, string> = {
    BUY: "高关注", ADD: "增强关注", WATCH: "观察", REDUCE: "风险升高", SELL: "回避观察",
  };
  for (const [eng, chn] of Object.entries(ratingMap)) {
    clean = clean.replace(new RegExp(`\\b${eng}\\b`, "g"), chn);
  }
  Object.entries(REPORT_TYPE_LABELS).forEach(([source, label]) => {
    clean = clean.replace(new RegExp(`报告类型:\\s*${source}\\b`, "g"), `报告类型: ${label}`);
  });
  clean = clean.replace(/\bNone\b/g, "暂无数据");
  clean = clean.replace(/\bnull\b/g, "暂无数据");
  clean = clean.replace(/\bundefined\b/g, "暂无数据");
  clean = clean.replace(/\bN\/A\b/g, "暂缺");
  clean = clean.replace(/投资价值判断/g, "研究价值分析");
  clean = clean.replace(/投资风格/g, "研究风格");
  clean = clean.replace(/if\s+\w+\s+else/g, "暂无数据");
  return clean;
}

// 简单 Markdown → HTML
function mdToHtml(md: string): string {
  if (!md) return "<p>暂无内容</p>";
  let html = cleanText(md);

  // 代码块
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:8px;padding:12px;overflow-x:auto;font-size:12px;color:#334155;margin:12px 0;line-height:1.6"><code>${code.replace(/</g, "&lt;")}</code></pre>`
  );

  // 标题
  html = html.replace(/^### (.+)$/gm, '<h3 style="font-size:16px;font-weight:700;color:#0f172a;margin:20px 0 8px;padding-bottom:6px;border-bottom:1px solid #e2e8f0">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 style="font-size:20px;font-weight:700;color:#0f172a;margin:24px 0 10px;padding-bottom:8px;border-bottom:2px solid #7c3aed">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1 style="font-size:24px;font-weight:800;color:#0f172a;margin:28px 0 12px">$1</h1>');

  // 引用
  html = html.replace(/^> (.+)$/gm, '<blockquote style="border-left:4px solid #7c3aed;background:#f5f3ff;padding:10px 14px;margin:10px 0;border-radius:0 6px 6px 0;color:#475569;font-size:13px">$1</blockquote>');

  // 水平线
  html = html.replace(/^---$/gm, '<hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0">');

  // 表格
  html = html.replace(/\n(\|.+\|)\n(\|[-| :]+\|)\n((?:\|.+\|\n?)+)/g, (_, header, sep, body) => {
    const ths = header.split("|").filter((c: string) => c.trim()).map((c: string) =>
      `<th style="padding:8px 12px;text-align:left;font-weight:600;color:#1e293b;border-bottom:2px solid #d8dee9;background:#f8fafc;font-size:12px">${c.trim()}</th>`
    ).join("");
    const rows = body.trim().split("\n").map((row: string) => {
      const tds = row.split("|").filter((c: string) => c.trim()).map((c: string) =>
        `<td style="padding:8px 12px;border-bottom:1px solid #e8ecf1;font-size:12px;color:#334155">${c.trim()}</td>`
      ).join("");
      return `<tr>${tds}</tr>`;
    }).join("");
    return `<div style="overflow-x:auto;margin:12px 0;border-radius:8px;border:1px solid #d8dee9"><table style="width:100%;border-collapse:collapse"><thead><tr>${ths}</tr></thead><tbody>${rows}</tbody></table></div>`;
  });

  // 列表
  html = html.replace(/^- (.+)$/gm, '<div style="display:flex;gap:6px;margin:3px 0;padding-left:8px"><span style="color:#7c3aed;font-weight:bold">•</span><span style="color:#334155;font-size:13px">$1</span></div>');
  html = html.replace(/^(\d+)\. (.+)$/gm, '<div style="display:flex;gap:6px;margin:3px 0;padding-left:8px"><span style="color:#7c3aed;font-weight:600;min-width:18px">$1.</span><span style="color:#334155;font-size:13px">$2</span></div>');

  // 内联
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong style="font-weight:600;color:#0f172a">$1</strong>');
  html = html.replace(/`([^`]+)`/g, '<code style="background:#f1f5f9;color:#7c3aed;padding:1px 4px;border-radius:3px;font-size:12px">$1</code>');

  // 段落
  html = html.replace(/\n\n/g, '</p><p style="margin:6px 0;color:#334155;font-size:13px;line-height:1.7">');
  html = html.replace(/\n/g, "<br>");
  html = `<p style="margin:6px 0;color:#334155;font-size:13px;line-height:1.7">${html}</p>`;

  return html;
}

type ReportData = ReportItem & { content_markdown: string };

export default function ReportDetailPage() {
  const { t } = useTranslation();
  const params = useParams();
  const reportId = params.id as string;
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState<"png" | "pdf" | null>(null);
  const reportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!reportId) return;
    setLoading(true);
    getReport(Number(reportId))
      .then(setReport)
      .catch((err: Error) => setError(err.message || "加载失败"))
      .finally(() => setLoading(false));
  }, [reportId]);

  const handleDownloadPng = async () => {
    if (!report) return;
    setDownloading("png");
    try {
      const filename = `${report.stock_code || report.report_type}_${report.stock_name || "研究报告"}_报告摘要_${report.report_date}.png`.replace(/[<>:"/\\|?*]/g, "_");
      await downloadReportPng(report.id, filename);
      showToast("success", "PNG 摘要图下载已开始。");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "PNG 摘要图生成失败";
      showToast("error", `PNG 摘要图生成失败: ${msg}`);
    } finally {
      setDownloading(null);
    }
  };

  const handleDownloadPdf = async () => {
    if (!report) return;
    setDownloading("pdf");
    try {
      const { downloadReportPdf } = await import("@/lib/api");
      await downloadReportPdf(report.id, `${report.title || "report"}.pdf`);
      showToast("success", "PDF 报告下载已开始。");
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "PDF 导出失败";
      showToast("error", message);
    } finally {
      setDownloading(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-page)" }}>
        <div className="text-center">
          <div className="w-12 h-12 border-2 border-primary-200 rounded-full mx-auto mb-4">
            <div className="w-12 h-12 border-2 border-transparent border-t-primary-500 rounded-full animate-spin" />
          </div>
          <p className="text-[var(--text-muted)]">加载报告中...</p>
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-page)" }}>
        <div className="text-center">
          <p className="text-h3 mb-2">报告加载失败</p>
          <p className="text-caption">{error || "未找到该报告"}</p>
        </div>
      </div>
    );
  }

  const reportTypeLabel = REPORT_TYPE_LABELS[report.report_type] || "研究报告";
  const reportStatus = report.report_data_status;

  return (
    <div className="min-h-screen p-4 md:p-8" style={{ background: "var(--bg-page)" }}>
        {/* 操作栏（不打印） */}
        <div className="no-print max-w-[900px] mx-auto mb-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => window.history.back()} className="btn-secondary !px-3 !py-2 text-xs">← 返回</button>
            <span className="text-caption">报告详情</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleDownloadPng}
              disabled={downloading === "png"}
              className="btn-secondary !px-4 !py-2 text-xs"
            >
              📷 {downloading === "png" ? "生成中..." : "下载 PNG 摘要图"}
            </button>
            <button
              onClick={handleDownloadPdf}
              disabled={downloading === "pdf"}
              className="btn-primary !px-4 !py-2 text-xs"
            >
              📄 {downloading === "pdf" ? "导出中..." : "下载 PDF 报告"}
            </button>
          </div>
        </div>

        {reportStatus && reportStatus !== "real_backed" && (
          <div className="no-print max-w-[900px] mx-auto mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            本报告基于演示评分或数据不足状态生成，仅用于研究辅助，不代表真实评分结论。
          </div>
        )}

        {/* 报告正文（不使用 overflow-hidden 以确保 html2canvas 能捕获完整内容） */}
        <div ref={reportRef} className="report-container max-w-[900px] mx-auto bg-white rounded-2xl shadow-sm border border-[var(--border-default)]">
          {/* 顶部装饰条 */}
          <div style={{ height: "4px", background: "linear-gradient(90deg, #7c3aed, #a78bfa, #c4b5fd)" }} />

          {/* 报告头部 */}
          <div style={{ padding: "32px 40px 24px", background: "linear-gradient(135deg, #f8fafc, #f5f3ff)", borderBottom: "1px solid #e2e8f0" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "8px" }}>
              <img
                src="/brand/qingshu-icon-logo.png"
                alt="清数智算"
                width={36}
                height={36}
                style={{ borderRadius: "8px" }}
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
              />
              <div>
                <div style={{ fontSize: "22px", fontWeight: 800, color: "#0f172a", letterSpacing: "-0.5px" }}>
                  {cleanText(report.title)}
                </div>
                <div style={{ fontSize: "13px", color: "#64748b", marginTop: "2px" }}>
                  清数智算智能投研工作台 · {report.report_date} · {reportTypeLabel}
                </div>
              </div>
            </div>
            {report.summary && (
              <p style={{ fontSize: "13px", color: "#475569", marginTop: "8px", lineHeight: 1.6 }}>
                {cleanText(report.summary)}
              </p>
            )}
          </div>

          {/* 报告正文 */}
          <div
            style={{ padding: "24px 40px 40px", minHeight: "400px" }}
            dangerouslySetInnerHTML={{ __html: mdToHtml(report.content_markdown || "") }}
          />

          {/* 页脚 */}
          <div style={{ padding: "16px 40px", background: "#f8fafc", borderTop: "1px solid #e2e8f0", textAlign: "center" }}>
            <div style={{ fontSize: "11px", color: "#94a3b8" }}>
              本报告由系统基于公开数据、数据库评分和规则模型生成，仅用于研究辅助，不构成投资建议。
            </div>
            <div style={{ fontSize: "11px", color: "#cbd5e1", marginTop: "4px" }}>
              清数智算 · 智能投研工作台 · {report.report_date}
            </div>
          </div>
        </div>
    </div>
  );
}
