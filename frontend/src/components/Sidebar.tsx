"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  Database,
  Download,
  FileText,
  FlaskConical,
  Key,
  Languages,
  LogOut,
  Menu,
  Radio,
  Shield,
  Target,
  TrendingUp,
  UserRound,
  Users,
  X,
} from "lucide-react";

import { useAuth } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";

export function useSidebarCollapsed() {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("sidebar-collapsed");
    if (saved) setCollapsed(saved === "true");
    const handler = (event: Event) => setCollapsed((event as CustomEvent).detail);
    window.addEventListener("sidebar-toggle", handler);
    return () => window.removeEventListener("sidebar-toggle", handler);
  }, []);

  const toggle = () => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem("sidebar-collapsed", String(next));
      window.dispatchEvent(new CustomEvent("sidebar-toggle", { detail: next }));
      return next;
    });
  };

  return { collapsed, toggle };
}

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { t, language, setLanguage } = useTranslation();
  const { collapsed, toggle } = useSidebarCollapsed();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => setMobileOpen(false), [pathname]);

  const role = user?.role || "guest";
  const isAdmin = role === "admin";
  const navItems = useMemo(() => {
    const cItems = [
      { href: "/dashboard", label: "投研驾驶舱", icon: BarChart3 },
      { href: "/signals", label: "研究信号", icon: Radio },
      { href: "/stocks", label: "个股评分库", icon: TrendingUp },
      { href: "/pools", label: "策略股票池", icon: Target },
      { href: "/reports", label: "报告中心", icon: FileText },
      { href: "/backtest", label: "回测中心", icon: FlaskConical },
      { href: "/profile", label: "个人中心", icon: UserRound },
    ];
    const adminItems = [
      { href: "/admin", label: "管理中心", icon: Shield },
      { href: "/admin?tab=users", label: "用户管理", icon: Users },
      { href: "/admin?tab=audit", label: "审计日志", icon: Activity },
      { href: "/admin?tab=overview", label: "系统状态", icon: Database },
      { href: "/admin?tab=api-config", label: "平台 API 配置", icon: Key },
      { href: "/admin?tab=exports", label: "导出管理", icon: Download },
    ];
    return isAdmin ? adminItems : cItems;
  }, [isAdmin]);

  return (
    <>
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="fixed left-4 top-4 z-[60] rounded-lg border border-[var(--border-default)] bg-white p-2 text-[var(--text-primary)] shadow-sm lg:hidden"
        aria-label="切换侧边栏菜单"
      >
        {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      {mobileOpen && <div className="fixed inset-0 z-40 bg-black/30 lg:hidden" onClick={() => setMobileOpen(false)} />}

      <aside
        className={`gradient-bg fixed left-0 top-0 z-50 flex h-screen flex-col transition-all duration-300 ${
          collapsed ? "w-16" : "w-60"
        } max-lg:-translate-x-full ${mobileOpen ? "max-lg:translate-x-0" : ""}`}
      >
        <div className="flex items-center justify-between border-b border-[var(--border-default)] px-4 py-3" style={{ minHeight: 72 }}>
          {!collapsed ? (
            <div className="flex items-center gap-3">
              <img src="/brand/qingshu-icon-logo.png" alt="清数智算" width={40} height={40} className="shrink-0 rounded-lg" onError={(e) => ((e.target as HTMLImageElement).style.display = "none")} />
              <div>
                <h1 className="text-base font-bold tracking-normal text-[var(--text-heading)]">{t("app.name")}</h1>
                <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">{isAdmin ? "管理员运营后台" : t("app.subtitle")}</p>
              </div>
            </div>
          ) : (
            <img src="/brand/qingshu-icon-logo.png" alt="清数智算" width={32} height={32} className="mx-auto shrink-0 rounded-lg" onError={(e) => ((e.target as HTMLImageElement).style.display = "none")} />
          )}
          <button onClick={toggle} className="rounded-lg p-1.5 text-[var(--text-muted)] transition-colors hover:bg-[var(--bg-surface)] hover:text-[var(--text-primary)]" title={collapsed ? "展开侧边栏" : "收起侧边栏"}>
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 py-3">
          {navItems.map((item) => {
            const pathOnly = item.href.split("?")[0];
            const isActive = pathname === pathOnly || pathname?.startsWith(`${pathOnly}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                title={collapsed ? item.label : undefined}
                aria-label={item.label}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all ${
                  isActive ? "bg-primary-50 font-semibold text-primary-700 shadow-sm" : "text-[var(--text-secondary)] hover:bg-[var(--bg-surface)] hover:text-[var(--text-primary)]"
                } ${collapsed ? "justify-center" : ""}`}
              >
                <Icon className="h-[18px] w-[18px] shrink-0" />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        <div className={`flex gap-1 border-t border-[var(--border-default)] px-3 py-2 ${collapsed ? "flex-col items-center" : "items-center justify-between"}`}>
          <button
            onClick={() => setLanguage(language === "zh" ? "en" : "zh")}
            title={language === "zh" ? "切换到英文界面" : "切换到中文界面"}
            className="rounded-lg p-2 text-[var(--text-muted)] transition-colors hover:bg-[var(--bg-surface)] hover:text-[var(--text-primary)]"
          >
            <Languages className="h-4 w-4" />
          </button>
          {!collapsed && (
            <button onClick={() => setLanguage(language === "zh" ? "en" : "zh")} className="text-xs font-medium text-[var(--text-muted)] transition-colors hover:text-[var(--text-primary)]">
              {language === "zh" ? "切换到英文" : "切换到中文"}
            </button>
          )}
        </div>

        <div className="border-t border-[var(--border-default)] px-3 py-3">
          {!collapsed ? (
            <>
              <Link href="/profile" className="mb-2 flex items-center gap-3 rounded-lg p-1 hover:bg-[var(--bg-surface)]">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-100 text-sm font-bold text-primary-700">
                  {(user?.display_name || user?.username || "U")[0]}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-[var(--text-primary)]">{user?.display_name || user?.username}</p>
                  <p className="text-[11px] text-[var(--text-muted)]">{t(`role.${user?.role || "guest"}`)}</p>
                </div>
              </Link>
              <button
                type="button"
                onMouseDown={(event) => {
                  event.preventDefault();
                  logout();
                }}
                onClick={logout}
                className="flex w-full items-center justify-center gap-1.5 rounded-lg py-2 text-xs text-[var(--text-muted)] transition-all hover:bg-[var(--bg-surface)] hover:text-[var(--text-primary)]"
              >
                <LogOut className="h-3.5 w-3.5" />
                {t("sidebar.logout")}
              </button>
            </>
          ) : (
            <button
              type="button"
              onMouseDown={(event) => {
                event.preventDefault();
                logout();
              }}
              onClick={logout}
              title={t("sidebar.logout")}
              className="flex w-full items-center justify-center rounded-lg py-2 text-[var(--text-muted)] transition-all hover:bg-[var(--bg-surface)] hover:text-[var(--text-primary)]"
            >
              <LogOut className="h-4 w-4" />
            </button>
          )}
        </div>

        {!collapsed && (
          <div className="border-t border-[var(--border-default)] px-4 py-2">
            <p className="text-[10px] leading-relaxed text-[var(--text-muted)]">本系统仅用于研究和辅助分析，不构成任何投资建议。</p>
          </div>
        )}
      </aside>
    </>
  );
}
