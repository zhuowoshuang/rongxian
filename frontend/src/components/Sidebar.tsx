"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import { useTheme } from "@/lib/theme";
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
  Sun,
  Moon,
  Menu,
  X,
} from "lucide-react";

export function useSidebarCollapsed() {
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    const saved = localStorage.getItem("sidebar-collapsed");
    if (saved) setCollapsed(saved === "true");
    // H-04: 监听自定义事件同步折叠状态
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
  const { theme, toggleTheme } = useTheme();
  const { collapsed, toggle } = useSidebarCollapsed();
  const [mobileOpen, setMobileOpen] = useState(false);
  const isDark = theme === "dark";

  // 移动端路由切换时自动关闭侧边栏
  useEffect(() => { setMobileOpen(false); }, [pathname]);

  const role = user?.role || "guest";
  const navItems = [
    { href: "/dashboard", label: t("nav.dashboard"), icon: BarChart3 },
    { href: "/signals", label: t("nav.signals"), icon: Radio },
    { href: "/stocks", label: t("nav.stocks"), icon: TrendingUp },
    { href: "/pools", label: t("nav.pools"), icon: Target },
    ...(role !== "guest" ? [{ href: "/reports", label: t("nav.reports"), icon: FileText }] : []),
    ...(role === "admin" || role === "analyst" ? [{ href: "/backtest", label: t("nav.backtest"), icon: FlaskConical }] : []),
    ...(role === "admin" ? [{ href: "/settings", label: t("nav.settings"), icon: Settings }] : []),
    ...(role === "admin" ? [{ href: "/admin", label: t("nav.admin"), icon: Shield }] : []),
  ];

  return (
    <>
      {/* H-12: 移动端汉堡菜单按钮 */}
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="fixed top-4 left-4 z-[60] p-2 rounded-lg bg-dark-card/90 border border-white/[0.08] text-dark-text lg:hidden backdrop-blur"
        aria-label="Toggle menu"
      >
        {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      {/* 移动端遮罩 */}
      {mobileOpen && <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={() => setMobileOpen(false)} />}

    <aside
      className={`fixed left-0 top-0 h-screen gradient-bg flex flex-col z-50 transition-all duration-300 ${
        collapsed ? "w-16" : "w-60"
      } ${isDark ? "text-white" : "text-slate-800"} max-lg:-translate-x-full ${mobileOpen ? "max-lg:translate-x-0" : ""}`}
    >
      {/* Logo */}
      <div className={`px-4 py-4 border-b flex items-center justify-between ${isDark ? "border-white/[0.06]" : "border-slate-200"}`}>
        {!collapsed && (
          <div>
            <h1 className="text-lg font-bold tracking-tight">{t("app.name")}</h1>
            <p className={`text-[10px] mt-0.5 ${isDark ? "text-white/40" : "text-slate-400"}`}>{t("app.subtitle")}</p>
          </div>
        )}
        {collapsed && (
          <div className="w-8 h-8 rounded-lg bg-primary-500/20 flex items-center justify-center mx-auto">
            <Shield className="w-4 h-4 text-primary-400" />
          </div>
        )}
        <button
          onClick={toggle}
          className={`p-1.5 rounded-lg transition-colors ${isDark ? "hover:bg-white/10 text-white/40 hover:text-white" : "hover:bg-slate-100 text-slate-400 hover:text-slate-700"}`}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = pathname === item.href || pathname?.startsWith(item.href + "/");
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              title={collapsed ? item.label : undefined}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                isActive
                  ? isDark
                    ? "bg-white/10 text-white shadow-sm backdrop-blur"
                    : "bg-primary-500/10 text-primary-600 shadow-sm"
                  : isDark
                    ? "text-white/50 hover:bg-white/[0.06] hover:text-white/80"
                    : "text-slate-500 hover:bg-slate-100 hover:text-slate-700"
              } ${collapsed ? "justify-center" : ""}`}
            >
              <Icon className="w-[18px] h-[18px] flex-shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Language & Theme toggles */}
      <div className={`px-3 py-2 border-t flex ${collapsed ? "flex-col items-center" : "items-center justify-between"} gap-1 ${isDark ? "border-white/[0.06]" : "border-slate-200"}`}>
        <button
          onClick={() => setLanguage(language === "zh" ? "en" : "zh")}
          title={language === "zh" ? "Switch to English" : "切换到中文"}
          className={`p-2 rounded-lg transition-colors ${isDark ? "hover:bg-white/10 text-white/40 hover:text-white" : "hover:bg-slate-100 text-slate-400 hover:text-slate-700"}`}
        >
          <Languages className="w-4 h-4" />
        </button>
        {!collapsed && (
          <button
            onClick={() => setLanguage(language === "zh" ? "en" : "zh")}
            className={`text-xs font-medium transition-colors ${isDark ? "text-white/40 hover:text-white" : "text-slate-400 hover:text-slate-700"}`}
          >
            {language === "zh" ? "EN" : "中"}
          </button>
        )}
        <button
          onClick={toggleTheme}
          title={isDark ? t("sidebar.switchToLight") : t("sidebar.switchToDark")}
          className={`p-2 rounded-lg transition-colors ${isDark ? "hover:bg-white/10 text-white/40 hover:text-white" : "hover:bg-slate-100 text-slate-400 hover:text-slate-700"}`}
        >
          {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
      </div>

      {/* User Info */}
      <div className={`px-3 py-3 border-t ${isDark ? "border-white/[0.06]" : "border-slate-200"}`}>
        {!collapsed ? (
          <>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-8 h-8 rounded-full bg-primary-500/20 flex items-center justify-center text-sm font-bold text-primary-400">
                {(user?.display_name || user?.username || "U")[0]}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{user?.display_name || user?.username}</p>
                <p className={`text-[10px] ${isDark ? "text-white/30" : "text-slate-400"}`}>{t(`role.${user?.role || "guest"}`)}</p>
              </div>
            </div>
            <button
              onClick={logout}
              className={`w-full py-2 text-xs rounded-lg transition-all flex items-center justify-center gap-1.5 ${isDark ? "text-white/40 hover:text-white hover:bg-white/10" : "text-slate-400 hover:text-slate-700 hover:bg-slate-100"}`}
            >
              <LogOut className="w-3.5 h-3.5" />
              {t("sidebar.logout")}
            </button>
          </>
        ) : (
          <button
            onClick={logout}
            title={t("sidebar.logout")}
            className={`w-full py-2 flex items-center justify-center rounded-lg transition-all ${isDark ? "text-white/40 hover:text-white hover:bg-white/10" : "text-slate-400 hover:text-slate-700 hover:bg-slate-100"}`}
          >
            <LogOut className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Footer */}
      {!collapsed && (
        <div className={`px-4 py-2 border-t ${isDark ? "border-white/[0.06]" : "border-slate-200"}`}>
          <p className={`text-[9px] leading-relaxed ${isDark ? "text-white/25" : "text-slate-400"}`}>
            {t("app.disclaimer")}
          </p>
        </div>
      )}
    </aside>
    </>
  );
}
