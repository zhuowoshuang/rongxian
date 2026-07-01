import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

const GARBLE_MARKERS = ["姘", "蹇", "鑾", "鑼", "鐚", "閿", "闁", "鑴"];

const DISPLAY_REPLACEMENTS: Array<[string, string]> = [
  ["建议买入", "研究关注"],
  ["建议加仓", "增强关注"],
  ["建议减仓", "降低关注"],
  ["建议卖出", "回避观察"],
  ["建议观望", "继续观察"],
  ["建议研究关注", "研究关注"],
  ["可适当增强关注", "增强关注"],
  ["强烈推荐", "高优先级研究样本"],
  ["强烈买入", "高关注"],
  ["买入", "高关注"],
  ["加仓", "增强关注"],
  ["减仓", "风险升高"],
  ["卖出", "回避观察"],
  ["目标价", "模型观察价"],
  ["止损价", "风险警戒价"],
  ["建议仓位", "研究仓位"],
  ["组合表现", "研究组合表现"],
  ["投资建议", "研究结论"],
  ["收益保证", "历史研究测算结果"],
  ["收益承诺", "历史研究测算结果"],
  ["跑赢市场", "相对基准表现更强"],
  ["跑赢指数", "相对基准表现更强"],
  ["投资策略", "研究策略"],
  ["观望等待", "继续观察"],
];

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPercent(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}

export function formatAmount(value: number | null | undefined, t?: (key: string) => string): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  const billion = t ? t("unit.billion") : "亿";
  const million = t ? t("unit.million") : "万";
  if (value >= 1e8) return `${(value / 1e8).toFixed(2)}${billion}`;
  if (value >= 1e4) return `${(value / 1e4).toFixed(2)}${million}`;
  return value.toFixed(2);
}

export function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatMarketCap(value: number | null | undefined, t?: (key: string) => string): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  const trillion = t ? t("unit.trillion") : "万亿";
  const billion = t ? t("unit.billion") : "亿";
  const million = t ? t("unit.million") : "万";
  if (value >= 1e12) return `${(value / 1e12).toFixed(1)}${trillion}`;
  if (value >= 1e8) return `${(value / 1e8).toFixed(0)}${billion}`;
  if (value >= 1e4) return `${(value / 1e4).toFixed(0)}${million}`;
  return value.toFixed(0);
}

export function getRiskColor(level: string): string {
  const map: Record<string, string> = {
    low: "text-emerald-400",
    medium: "text-amber-400",
    high: "text-orange-400",
    critical: "text-red-400",
  };
  return map[level] || "text-dark-muted";
}

export function isLikelyGarbledText(text: string | null | undefined): boolean {
  if (!text) return false;
  const markerHits = GARBLE_MARKERS.reduce((sum, marker) => sum + text.split(marker).length - 1, 0);
  const questionHits = (text.match(/\?/g) || []).length;
  return markerHits >= 2 || questionHits >= Math.max(4, Math.floor(text.length / 6));
}

function tryRepairGarbledText(text: string): string {
  try {
    const repaired = decodeURIComponent(escape(text));
    return isLikelyGarbledText(repaired) ? text : repaired;
  } catch {
    return text;
  }
}

export function normalizeResearchText(text: string | null | undefined): string {
  if (!text) return "";
  let result = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
  if (isLikelyGarbledText(result)) {
    result = tryRepairGarbledText(result);
  }
  for (const [source, target] of DISPLAY_REPLACEMENTS) {
    result = result.replaceAll(source, target);
  }
  return result.replace(/\n{3,}/g, "\n\n").trim();
}

export function sanitizeDisplayText(text: string | null | undefined, fallback = ""): string {
  const normalized = normalizeResearchText(text);
  if (!normalized) return fallback;
  if (isLikelyGarbledText(normalized)) {
    return fallback || "原始文本存在编码异常，已隐藏原文，请以结构化评分和数据为准。";
  }
  return normalized;
}

export function signalTypeLabel(type: string, t?: (key: string) => string): string {
  if (t) {
    const key = `signal.${type.toLowerCase()}`;
    const translated = t(key);
    if (translated !== key) return translated;
  }
  const map: Record<string, string> = {
    BUY: "高关注",
    ADD: "增强关注",
    WATCH: "观察",
    REDUCE: "风险升高",
    SELL: "回避观察",
    DATA_INSUFFICIENT: "数据质量受限",
  };
  return map[type] || type;
}

export function signalFieldLabel(field: "position" | "entry" | "target" | "stop"): string {
  const map = {
    position: "研究仓位",
    entry: "参考价",
    target: "模型观察价",
    stop: "风险警戒价",
  };
  return map[field];
}

export function sanitizeSignalNarrative(text: string | null | undefined): string {
  return sanitizeDisplayText(text, "原始文本存在编码异常，已隐藏原文，请以结构化评分和数据为准。");
}

export function humanizeReasonSummary(
  text: string | null | undefined,
  fallback = "当前条目已纳入研究样本库，详情页可继续查看评分追溯。"
): string {
  const normalized = sanitizeDisplayText(text, fallback);
  if (!normalized) return fallback;
  if (!normalized.includes("优势:") && !normalized.includes("风险:")) {
    return normalized;
  }
  const advantageMatch = normalized.match(/优势:\s*([^|]+)/);
  const riskMatch = normalized.match(/风险:\s*(.+)$/);
  const advantages = advantageMatch?.[1]?.trim();
  const risks = riskMatch?.[1]?.trim();
  const parts = [];
  if (advantages) parts.push(`当前进入样本库的主要支撑因素包括 ${advantages}。`);
  if (risks) parts.push(`仍需重点关注 ${risks}。`);
  parts.push("该结论仅基于现有评分与指标，不构成投资建议。");
  return parts.join("");
}

export function humanizePoolReason(
  text: string | null | undefined,
  fallback = "当前标的进入该策略池，原因将结合评分和已有指标持续更新。"
): string {
  const normalized = sanitizeDisplayText(text, fallback);
  if (!normalized) return fallback;
  if (normalized.includes("优势:") || normalized.includes("风险:")) {
    return humanizeReasonSummary(normalized, fallback);
  }
  if (normalized.includes("进入")) {
    return `${normalized} 当前展示仅用于研究观察与样本排序，不构成投资建议。`;
  }
  return normalized;
}

export function signalTypeClass(type: string): string {
  const map: Record<string, string> = {
    BUY: "signal-buy",
    ADD: "signal-add",
    WATCH: "signal-watch",
    REDUCE: "signal-reduce",
    SELL: "signal-sell",
  };
  return map[type] || "";
}

export function ratingClass(rating: string): string {
  const map: Record<string, string> = {
    BUY: "rating-buy",
    ADD: "rating-add",
    WATCH: "rating-watch",
    REDUCE: "rating-reduce",
    SELL: "rating-sell",
  };
  return map[rating] || "";
}

export function renderStars(count: number, max = 5): string {
  return "★".repeat(count) + "☆".repeat(Math.max(0, max - count));
}

export function getChangeColor(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "text-dark-muted";
  return value >= 0 ? "text-emerald-400" : "text-red-400";
}

export function normalizeMarketCode(market: string | null | undefined): string {
  const normalized = (market || "").trim().toUpperCase();
  if (normalized === "A_SHARE" || normalized === "A" || normalized === "SH" || normalized === "SZ") return "A_SHARE";
  if (normalized === "HK" || normalized === "H_SHARE") return "HK";
  return normalized || "UNKNOWN";
}

export function marketLabel(market: string, t?: (key: string) => string): string {
  const normalized = normalizeMarketCode(market);
  if (t) {
    const key = normalized === "A_SHARE" ? "market.aShare" : normalized === "HK" ? "market.hk" : "";
    const translated = key ? t(key) : "";
    if (translated !== key) return translated;
  }
  if (normalized === "A_SHARE") return "A股";
  if (normalized === "HK") return "港股";
  return "待核验";
}

export function runtimeStatusLabel(value: string | null | undefined): string {
  const normalized = (value || "").toLowerCase();
  const map: Record<string, string> = {
    ok: "正常",
    healthy: "正常",
    degraded: "降级",
    unavailable: "不可用",
    unknown: "未知",
    pending: "待执行",
    error: "失败",
    success: "成功",
    running: "运行中",
    completed: "已完成",
    live: "真实数据",
    mock: "模拟数据",
    hybrid: "混合数据",
    auto: "自动选择",
    memory: "演示缓存",
    redis: "Redis 缓存",
    system: "系统",
    admin: "管理员",
    development: "开发环境",
    production: "生产环境",
  };
  return map[normalized] || value || "未知";
}

export function dataModeLabel(value: string | null | undefined): string {
  if (!value) return "未知";
  if (value.includes("真实")) return "真实/混合数据";
  if (value.includes("模拟")) return "模拟数据";
  return runtimeStatusLabel(value);
}

export function displayTierLabel(value: string | null | undefined): string {
  const map: Record<string, string> = {
    formal_real: "正式研究",
    real_observation: "风险观察",
    data_quality_limited: "数据质量受限",
    data_insufficient: "数据不足",
    demo_only: "演示数据",
  };
  return map[value || ""] || "待核验";
}

export function displayTierTone(value: string | null | undefined): "live" | "database" | "warning" | "simulated" | "pending" {
  const map: Record<string, "live" | "database" | "warning" | "simulated" | "pending"> = {
    formal_real: "live",
    real_observation: "database",
    data_quality_limited: "warning",
    data_insufficient: "pending",
    demo_only: "simulated",
  };
  return map[value || ""] || "pending";
}

export function readinessLabel(value: string | null | undefined): string {
  const map: Record<string, string> = {
    ready_full: "完整链路",
    no_data: "暂无数据",
    data_quality_limited: "数据质量受限",
    risk_observation: "风险观察",
    formal_real: "正式研究样本",
  };
  return map[value || ""] || displayTierLabel(value);
}

export function scoreSourceLabel(value: string | null | undefined): string {
  const map: Record<string, string> = {
    real_calculated: "真实评分",
    quick_seed_demo: "演示评分",
    "Fixture-Only": "固定样例",
    NETWORK_WARN: "网络受限",
    EMPTY: "暂无数据",
    ERROR: "数据异常",
  };
  return map[value || ""] || "待核验";
}

export function reportTypeLabel(value: string | null | undefined): string {
  const map: Record<string, string> = {
    STOCK: "股票",
    REPORT: "报告",
    DAILY: "日报",
  };
  return map[value || ""] || "报告";
}

export function dataStatusLabel(value: string | null | undefined): string {
  const map: Record<string, string> = {
    OK: "数据可用",
    PARTIAL: "部分可用",
    EMPTY: "暂无数据",
    ERROR: "数据异常",
    DATA_INSUFFICIENT: "数据质量受限",
  };
  return map[value || ""] || "待核验";
}
