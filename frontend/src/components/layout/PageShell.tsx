"use client";

import { ReactNode } from "react";
import TopSearch from "@/components/TopSearch";
import { RefreshCw } from "lucide-react";

interface PageShellProps {
  title: string;
  subtitle?: string;
  badges?: ReactNode;
  actions?: ReactNode;
  onRefresh?: () => void;
  refreshing?: boolean;
  children: ReactNode;
}

/**
 * 统一页面容器
 * - 固定 max-width 1500px
 * - 统一 padding py-5 px-6
 * - 顶部：标题 + 搜索 + 操作按钮
 * - 下方：页面内容
 */
export default function PageShell({
  title,
  subtitle,
  badges,
  actions,
  onRefresh,
  refreshing,
  children,
}: PageShellProps) {
  return (
    <div className="py-5 px-6 max-w-[1500px] mx-auto space-y-5" style={{ background: "var(--bg-page)" }}>
      {/* 顶部栏：标题 + 搜索 + 操作 */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-1 h-6 bg-primary-500 rounded-full flex-shrink-0" />
          <div className="min-w-0">
            <h1 className="text-h1 leading-tight">{title}</h1>
            {subtitle && <p className="text-caption mt-0.5">{subtitle}</p>}
          </div>
          {badges && <div className="flex-shrink-0">{badges}</div>}
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <TopSearch />
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="btn-secondary !p-2.5"
              title="刷新"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
            </button>
          )}
          {actions}
        </div>
      </div>

      {/* 页面内容 */}
      {children}
    </div>
  );
}
