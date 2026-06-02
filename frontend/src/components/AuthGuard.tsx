"use client";

import { useAuth } from "@/lib/auth";
import LoginPage from "@/components/LoginPage";
import Sidebar, { useSidebarCollapsed } from "@/components/Sidebar";
import LoadingScreen from "@/components/ui/LoadingScreen";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const { collapsed } = useSidebarCollapsed();

  if (loading) {
    return <LoadingScreen />;
  }

  if (!user) {
    return <LoginPage />;
  }

  return (
    <div className="flex min-h-screen bg-dark-bg">
      <Sidebar />
      <main className={`flex-1 transition-all duration-300 ${collapsed ? "ml-16" : "ml-60"}`}>
        {children}
      </main>
    </div>
  );
}
