import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { LanguageProvider } from "@/lib/i18n";
import { ThemeProvider } from "@/lib/theme";
import AuthGuard from "@/components/AuthGuard";
import ErrorBoundary from "@/components/ErrorBoundary";
import ToastContainer from "@/components/ui/Toast";

export const metadata: Metadata = {
  title: "清数智算 - 智能投研工作台",
  description: "面向 A 股与港股研究场景的智能投研工作台",
  icons: {
    icon: "/favicon.png",
    shortcut: "/favicon.png",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className="antialiased">
        <ErrorBoundary>
          <ThemeProvider>
            <LanguageProvider>
              <AuthProvider>
                <AuthGuard>
                  {children}
                </AuthGuard>
                <ToastContainer />
              </AuthProvider>
            </LanguageProvider>
          </ThemeProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
