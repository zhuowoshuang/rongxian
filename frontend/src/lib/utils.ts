import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** 格式化百分比 */
export function formatPercent(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return "N/A";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}

/** 格式化金额（亿） */
export function formatAmount(value: number | null | undefined, t?: (key: string) => string): string {
  if (value === null || value === undefined) return "N/A";
  const billion = t ? t("unit.billion") : "亿";
  const million = t ? t("unit.million") : "万";
  if (value >= 1e8) return `${(value / 1e8).toFixed(2)}${billion}`;
  if (value >= 1e4) return `${(value / 1e4).toFixed(2)}${million}`;
  return value.toFixed(2);
}

/** 格式化数字（千分位） */
export function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return "--";
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** 格式化市值 */
export function formatMarketCap(value: number | null | undefined, t?: (key: string) => string): string {
  if (value === null || value === undefined) return "--";
  const trillion = t ? t("unit.trillion") : "万亿";
  const billion = t ? t("unit.billion") : "亿";
  const million = t ? t("unit.million") : "万";
  if (value >= 1e12) return `${(value / 1e12).toFixed(1)}${trillion}`;
  if (value >= 1e8) return `${(value / 1e8).toFixed(0)}${billion}`;
  if (value >= 1e4) return `${(value / 1e4).toFixed(0)}${million}`;
  return value.toFixed(0);
}

/** 获取风险等级颜色 */
export function getRiskColor(level: string): string {
  const map: Record<string, string> = {
    low: "text-emerald-400",
    medium: "text-amber-400",
    high: "text-orange-400",
    critical: "text-red-400",
  };
  return map[level] || "text-dark-muted";
}

/** 信号类型映射 */
export function signalTypeLabel(type: string, t?: (key: string) => string): string {
  if (t) {
    const key = `signal.${type.toLowerCase()}`;
    const translated = t(key);
    if (translated !== key) return translated;
  }
  const map: Record<string, string> = {
    BUY: "买入",
    ADD: "加仓",
    WATCH: "观察",
    REDUCE: "减仓",
    SELL: "卖出",
  };
  return map[type] || type;
}

/** 信号类型样式类 */
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

/** 评级样式类 */
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

/** 生成星级 */
export function renderStars(count: number, max = 5): string {
  return "★".repeat(count) + "☆".repeat(max - count);
}

/** 获取涨跌颜色 - 深色主题 */
export function getChangeColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return "text-dark-muted";
  return value >= 0 ? "text-emerald-400" : "text-red-400";
}

/** 市场标签 */
export function marketLabel(market: string, t?: (key: string) => string): string {
  if (t) {
    const key = market === "A_SHARE" ? "market.aShare" : "market.hk";
    const translated = t(key);
    if (translated !== key) return translated;
  }
  return market === "A_SHARE" ? "A股" : "港股";
}
