"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import { Shield, Eye, EyeOff } from "lucide-react";

export default function LoginPage() {
  const { login, register } = useAuth();
  const { t } = useTranslation();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;
    setError("");
    setLoading(true);
    try {
      if (mode === "login") {
        await login(username, password);
      } else {
        await register(username, password, displayName);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("auth.error"));
    }
    setLoading(false);
  };

  const fillAccount = (u: string) => {
    setUsername(u);
    setError("");
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden" style={{ background: "var(--bg-page)" }}>
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-200/30 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-primary-300/20 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-md px-4 relative z-10">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-gradient-to-br from-primary-500 to-primary-700 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg">
            <Shield className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-[var(--text-heading)] tracking-tight">{t("app.name")}</h1>
          <p className="text-[var(--text-muted)] mt-2 text-sm">{t("app.description")}</p>
        </div>

        <div className="card p-8">
          <div className="flex mb-6 bg-[var(--bg-surface)] rounded-xl p-1 border border-[var(--border-default)]">
            <button
              onClick={() => { setMode("login"); setError(""); }}
              className={`flex-1 py-2.5 text-sm font-medium rounded-lg transition-all ${
                mode === "login" ? "bg-white text-primary-700 shadow-sm font-semibold" : "text-[var(--text-muted)]"
              }`}
            >
              {t("auth.login")}
            </button>
            <button
              onClick={() => { setMode("register"); setError(""); }}
              className={`flex-1 py-2.5 text-sm font-medium rounded-lg transition-all ${
                mode === "register" ? "bg-white text-primary-700 shadow-sm font-semibold" : "text-[var(--text-muted)]"
              }`}
            >
              {t("auth.register")}
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs text-[var(--text-secondary)] font-medium">{t("auth.username")}</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={t("auth.username.placeholder")}
                required
                className="w-full mt-1"
              />
            </div>

            {mode === "register" && (
              <div>
                <label className="text-xs text-[var(--text-secondary)] font-medium">{t("auth.displayName")}</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder={t("auth.displayName.placeholder")}
                  className="w-full mt-1"
                />
              </div>
            )}

            <div>
              <label className="text-xs text-[var(--text-secondary)] font-medium">{t("auth.password")}</label>
              <div className="relative mt-1">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={t("auth.password.placeholder")}
                  required
                  className="w-full pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="p-3 rounded-xl text-sm flex items-center gap-2 card-danger">
                <span className="font-bold">!</span>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary py-3"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  {t("auth.processing")}
                </span>
              ) : (
                mode === "login" ? t("auth.login") : t("auth.register")
              )}
            </button>
          </form>

          {process.env.NODE_ENV === "development" && (
            <div className="mt-6 pt-5 border-t border-[var(--border-default)]">
              <p className="text-xs text-[var(--text-muted)] text-center mb-2">{t("auth.quickLogin")}</p>
              <p className="text-[11px] text-[var(--color-warning)] text-center mb-3">仅开发环境显示用户名快捷填充</p>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { u: "admin", r: t("auth.admin"), color: "text-primary-700 bg-primary-50" },
                  { u: "demo", r: t("auth.demo"), color: "text-blue-700 bg-blue-50" },
                  { u: "analyst", r: t("auth.analyst"), color: "text-emerald-700 bg-emerald-50" },
                  { u: "guest", r: t("auth.guest"), color: "text-gray-600 bg-gray-100" },
                ].map((acc) => (
                  <button
                    key={acc.u}
                    type="button"
                    onClick={() => fillAccount(acc.u)}
                    className="p-2.5 rounded-xl transition-all text-left border border-[var(--border-default)] hover:bg-[var(--bg-surface)] hover:border-primary-300"
                  >
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${acc.color}`}>{acc.r}</span>
                    </div>
                    <p className="text-xs font-medium text-[var(--text-primary)] mt-1">{acc.u}</p>
                    <p className="text-[10px] text-[var(--text-muted)]">点击填充账号名</p>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <p className="text-center text-xs text-[var(--text-muted)] mt-6">
          {t("app.disclaimer")}
        </p>
      </div>
    </div>
  );
}
