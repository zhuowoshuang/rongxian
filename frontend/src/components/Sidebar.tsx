"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import { useState, useEffect } from "react";
import {
  BarChart3,
  Radio,
  TrendingUp,
  Target,
  FileText,
  FlaskConical,
  Settings,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Shield,
  Languages,
  Menu,
  X,
} from "lucide-react";

export function useSidebarCollapsed() {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("sidebar-collapsed");
    if (saved) setCollapsed(saved === "true");
    const handler = (e: Event) => setCollapsed((e as CustomEvent).detail);
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

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const role = user?.role || "guest";
  const navItems = [
    { href: "/dashboard", label: t("nav.dashboard"), icon: BarChart3 },
    { href: "/signals", label: t("nav.signals"), icon: Radio },
    { href: "/stocks", label: t("nav.stocks"), icon: TrendingUp },
    { href: "/pools", label: t("nav.pools"), icon: Target },
    { href: "/reports", label: t("nav.reports"), icon: FileText },
    ...(role === "admin" || role === "analyst" ? [{ href: "/backtest", label: t("nav.backtest"), icon: FlaskConical }] : []),
    ...(role === "admin" ? [{ href: "/settings", label: t("nav.settings"), icon: Settings }] : []),
    ...(role === "admin" ? [{ href: "/admin", label: t("nav.admin"), icon: Shield }] : []),
  ];

  return (
    <>
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="fixed top-4 left-4 z-[60] p-2 rounded-lg bg-white border border-[var(--border-default)] text-[var(--text-primary)] lg:hidden shadow-sm"
        aria-label="切换侧边栏菜单"
      >
        {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      {mobileOpen && <div className="fixed inset-0 bg-black/30 z-40 lg:hidden" onClick={() => setMobileOpen(false)} />}

      <aside
        className={`fixed left-0 top-0 h-screen gradient-bg flex flex-col z-50 transition-all duration-300 ${
          collapsed ? "w-16" : "w-60"
        } max-lg:-translate-x-full ${mobileOpen ? "max-lg:translate-x-0" : ""}`}
      >
        {/* Logo */}
        <div className="px-4 py-3 border-b border-[var(--border-default)] flex items-center justify-between" style={{ minHeight: "72px" }}>
          {!collapsed ? (
            <div className="flex items-center gap-3">
              <img
                src="/brand/qingshu-icon-logo.png"
                alt="清数智算"
                width={40}
                height={40}
                className="rounded-lg flex-shrink-0"
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
              />
              <div>
                <h1 className="text-base font-bold tracking-tight text-[var(--text-heading)]">{t("app.name")}</h1>
                <p className="text-[11px] mt-0.5 text-[var(--text-muted)]">{t("app.subtitle")}</p>
              </div>
            </div>
          ) : (
            <img
              src="/brand/qingshu-icon-logo.png"
              alt="清数智算"
              width={32}
              height={32}
              className="rounded-lg mx-auto flex-shrink-0"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          )}
          <button
            onClick={toggle}
            className="p-1.5 rounded-lg hover:bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
            title={collapsed ? "展开侧边栏" : "收起侧边栏"}
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* 导航 */}
        <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
          {navItems.map((item) => {
            const isActive = pathname === item.href || pathname?.startsWith(item.href + "/");
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                title={collapsed ? item.label : undefined}
                aria-label={item.label}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? "bg-primary-50 text-primary-700 shadow-sm font-semibold"
                    : "text-[var(--text-secondary)] hover:bg-[var(--bg-surface)] hover:text-[var(--text-primary)]"
                } ${collapsed ? "justify-center" : ""}`}
              >
                <Icon className="w-[18px] h-[18px] flex-shrink-0" />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* 语言切换 */}
        <div className={`px-3 py-2 border-t border-[var(--border-default)] flex ${collapsed ? "flex-col items-center" : "items-center justify-between"} gap-1`}>
          <button
            onClick={() => setLanguage(language === "zh" ? "en" : "zh")}
            title={language === "zh" ? "切换到英文界面" : "切换到中文界面"}
            className="p-2 rounded-lg hover:bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
          >
            <Languages className="w-4 h-4" />
          </button>
          {!collapsed && (
            <button
              onClick={() => setLanguage(language === "zh" ? "en" : "zh")}
              className="text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
            >
              {language === "zh" ? "切换到英文" : "切换到中文"}
            </button>
          )}
        </div>

        {/* 用户信息 */}
        <div className="px-3 py-3 border-t border-[var(--border-default)]">
          {!collapsed ? (
            <>
              <div className="flex items-center gap-3 mb-2">
                <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center text-sm font-bold text-primary-700">
                  {(user?.display_name || user?.username || "U")[0]}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate text-[var(--text-primary)]">{user?.display_name || user?.username}</p>
                  <p className="text-[11px] text-[var(--text-muted)]">{t(`role.${user?.role || "guest"}`)}</p>
                </div>
              </div>
              <button
                onClick={logout}
                className="w-full py-2 text-xs rounded-lg transition-all flex items-center justify-center gap-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface)]"
              >
                <LogOut className="w-3.5 h-3.5" />
                {t("sidebar.logout")}
              </button>
            </>
          ) : (
            <button
              onClick={logout}
              title={t("sidebar.logout")}
              className="w-full py-2 flex items-center justify-center rounded-lg transition-all text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface)]"
            >
              <LogOut className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* 免责声明 */}
        {!collapsed && (
          <div className="px-4 py-2 border-t border-[var(--border-default)]">
            <p className="text-[10px] leading-relaxed text-[var(--text-muted)]">
              {t("app.disclaimer")}
            </p>
          </div>
        )}
      </aside>
    </>
  );
}
