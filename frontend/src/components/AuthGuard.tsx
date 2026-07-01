"use client";

import Link from "next/link";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import LoginPage from "@/components/LoginPage";
import Sidebar, { useSidebarCollapsed } from "@/components/Sidebar";
import LoadingScreen from "@/components/ui/LoadingScreen";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const { collapsed } = useSidebarCollapsed();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user && pathname === "/login") {
      const redirectTo = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("redirect") : null;
      router.replace(redirectTo && redirectTo.startsWith("/") ? redirectTo : "/dashboard");
    }
    if (!loading && !user && pathname === "/") {
      router.replace("/login");
    }
  }, [loading, pathname, router, user]);

  if (loading) {
    return <LoadingScreen />;
  }

  if (!user) {
    return <LoginPage />;
  }

  if (pathname === "/login") {
    return <LoadingScreen />;
  }

  if (pathname?.startsWith("/admin") && user.role !== "admin") {
    return (
      <div className="flex min-h-screen" style={{ background: "var(--bg-page)" }}>
        <Sidebar />
        <main className={`flex-1 transition-all duration-300 ${collapsed ? "ml-16" : "ml-60"}`}>
          <div className="mx-auto flex min-h-screen max-w-2xl items-center justify-center p-6">
            <div className="card w-full p-8 text-center">
              <p className="text-sm font-semibold text-primary-600">权限不足</p>
              <h1 className="mt-2 text-2xl font-bold text-[var(--text-primary)]">当前账号不能访问管理员后台</h1>
              <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
                管理中心、审计日志、系统状态和平台 API 配置只对管理员开放。普通用户可以继续使用投研驾驶舱、报告中心、回测中心和个人中心。
              </p>
              <Link href="/dashboard" className="btn-primary mt-6 inline-flex px-5 py-2 text-sm">
                返回投研驾驶舱
              </Link>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg-page)" }}>
      <Sidebar />
      <main className={`flex-1 transition-all duration-300 ${collapsed ? "ml-16" : "ml-60"}`}>
        {children}
      </main>
    </div>
  );
}
