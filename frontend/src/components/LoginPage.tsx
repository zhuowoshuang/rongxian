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
    if (loading) return; // 防止重复提交（H-11 竞态条件修复）
    setError("");
    setLoading(true);
    try {
      if (mode === "login") {
        await login(username, password);
      } else {
        await register(username, password, displayName);
      }
    } catch (err: any) {
      setError(err.message || t("auth.error"));
    }
    setLoading(false);
  };

  const fillAccount = (u: string, p: string) => {
    setUsername(u);
    setPassword(p);
    setError("");
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden" style={{ background: "var(--background)" }}>
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-500/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-md px-4 relative z-10">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-gradient-to-br from-primary-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-primary-500/20">
            <Shield className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">{t("app.name")}</h1>
          <p className="text-dark-muted mt-2 text-sm">{t("app.description")}</p>
        </div>

        <div className="card p-8">
          <div className="flex mb-6 bg-white/[0.03] rounded-xl p-1 border border-white/[0.06]">
            <button
              onClick={() => { setMode("login"); setError(""); }}
              className={`flex-1 py-2.5 text-sm font-medium rounded-lg transition-all ${
                mode === "login" ? "bg-primary-500/20 text-primary-400 border border-primary-500/30" : "text-dark-muted"
              }`}
            >
              {t("auth.login")}
            </button>
            <button
              onClick={() => { setMode("register"); setError(""); }}
              className={`flex-1 py-2.5 text-sm font-medium rounded-lg transition-all ${
                mode === "register" ? "bg-primary-500/20 text-primary-400 border border-primary-500/30" : "text-dark-muted"
              }`}
            >
              {t("auth.register")}
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs text-dark-muted font-medium">{t("auth.username")}</label>
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
                <label className="text-xs text-dark-muted font-medium">{t("auth.displayName")}</label>
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
              <label className="text-xs text-dark-muted font-medium">{t("auth.password")}</label>
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
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-muted hover:text-dark-text"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center gap-2">
                <span className="text-red-500 font-bold">!</span>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary py-3 disabled:opacity-50"
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

          <div className="mt-6 pt-5 border-t border-white/[0.06]">
            <p className="text-xs text-dark-muted text-center mb-3">{t("auth.quickLogin")}</p>
            <div className="grid grid-cols-2 gap-2">
              {[
                { u: "admin", p: "admin123", r: t("auth.admin"), color: "text-purple-400 bg-purple-500/10" },
                { u: "demo", p: "demo123", r: t("auth.demo"), color: "text-blue-400 bg-blue-500/10" },
                { u: "analyst", p: "analyst123", r: t("auth.analyst"), color: "text-emerald-400 bg-emerald-500/10" },
                { u: "guest", p: "guest123", r: t("auth.guest"), color: "text-gray-400 bg-gray-500/10" },
              ].map((acc) => (
                <button
                  key={acc.u}
                  type="button"
                  onClick={() => fillAccount(acc.u, acc.p)}
                  className="p-2.5 rounded-xl transition-all text-left border border-white/[0.06] hover:bg-white/[0.05] hover:border-white/[0.1]"
                >
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${acc.color}`}>{acc.r}</span>
                  </div>
                  <p className="text-xs font-medium text-dark-text mt-1">{acc.u}</p>
                  <p className="text-[10px] text-dark-muted">{acc.p}</p>
                </button>
              ))}
            </div>
          </div>
        </div>

        <p className="text-center text-xs text-white/20 mt-6">
          {t("app.disclaimer")}
        </p>
      </div>
    </div>
  );
}
