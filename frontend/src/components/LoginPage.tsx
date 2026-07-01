"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Lock, Phone, UserRound } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { clearAuthNotice, getAuthNotice } from "@/lib/api";

const MAINLAND_PHONE_RE = /^(?:\+?86)?1\d{10}$/;

function validatePhone(value: string): string | null {
  const normalized = value.replace(/\s+/g, "").trim();
  if (!normalized) return "手机号不能为空";
  if (!MAINLAND_PHONE_RE.test(normalized)) return "手机号格式不正确，请输入 11 位手机号";
  return null;
}

function validateUserId(value: string): string | null {
  const normalized = value.trim();
  if (!normalized) return "用户ID不能为空";
  if (normalized.length < 2 || normalized.length > 32) return "用户ID长度需在 2-32 个字符之间";
  if (/[<>{}'";\\]/.test(normalized)) return "用户ID仅支持中文、英文、数字、下划线和中划线";
  return null;
}

function validatePassword(value: string): string | null {
  if (!value) return "密码不能为空";
  if (value.length < 8) return "密码长度至少 8 位";
  return null;
}

export default function LoginPage() {
  const router = useRouter();
  const { user, loading: authLoading, login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [identifier, setIdentifier] = useState("");
  const [phone, setPhone] = useState("");
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [redirectTo, setRedirectTo] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setRedirectTo(new URLSearchParams(window.location.search).get("redirect"));
  }, []);

  useEffect(() => {
    if (!authLoading && user) {
      const target = redirectTo && redirectTo.startsWith("/") ? redirectTo : "/dashboard";
      router.replace(target);
    }
  }, [authLoading, redirectTo, router, user]);

  useEffect(() => {
    const savedNotice = getAuthNotice();
    if (savedNotice === "expired") {
      setNotice("登录已过期，请重新登录后查看真实数据。");
    } else if (savedNotice === "logged_out") {
      setNotice("你已退出登录，如需继续查看真实数据请重新登录。");
    } else if (savedNotice === "unauthorized") {
      setNotice("当前账号无权访问该页面，请使用有权限的账号重新登录。");
    }
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (loading) return;

    setError("");
    setNotice("");
    clearAuthNotice();
    setLoading(true);

    try {
      if (mode === "login") {
        const normalizedIdentifier = identifier.trim();
        if (!normalizedIdentifier) {
          setError("请输入手机号或用户ID");
          return;
        }
        const passwordError = validatePassword(password);
        if (passwordError) {
          setError(passwordError);
          return;
        }
        await login(normalizedIdentifier, password, redirectTo);
        return;
      }

      const phoneError = validatePhone(phone);
      if (phoneError) {
        setError(phoneError);
        return;
      }

      const userIdError = validateUserId(userId);
      if (userIdError) {
        setError(userIdError);
        return;
      }

      const passwordError = validatePassword(password);
      if (passwordError) {
        setError(passwordError);
        return;
      }

      if (!confirmPassword) {
        setError("确认密码不能为空");
        return;
      }

      if (password !== confirmPassword) {
        setError("两次输入的密码不一致");
        return;
      }

      await register(phone.trim(), userId.trim(), password, redirectTo);
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#f4f8fb] text-slate-900">
      <div className="mx-auto grid min-h-screen w-full max-w-7xl grid-cols-1 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="flex flex-col justify-between px-6 py-8 sm:px-10 lg:px-14">
          <div className="w-full max-w-xl">
            <div className="relative h-24 w-72 sm:h-32 sm:w-96">
              <Image src="/brand/qingshu-full-logo.png" alt="清数智算" fill priority className="object-contain object-left" />
            </div>
            <div className="mt-10 space-y-5">
              <p className="text-sm font-semibold text-cyan-700">真实用户体系 · 报告追踪 · 回测复用</p>
              <h1 className="text-4xl font-bold leading-tight tracking-normal text-slate-950 sm:text-5xl">
                清数智算投研工作台
              </h1>
              <p className="max-w-lg text-base leading-7 text-slate-600">
                面向研究与辅助分析场景，沉淀用户 API 配置、个股研究报告、下载记录和策略回测历史。
              </p>
            </div>
            <div className="mt-10 grid gap-3 sm:grid-cols-3">
              {["联合数据", "评分信号", "研究与回测"].map((item) => (
                <div key={item} className="rounded-lg border border-cyan-100 bg-white/80 px-4 py-4 shadow-sm">
                  <div className="text-sm font-semibold text-slate-900">{item}</div>
                  <div className="mt-2 h-1 w-10 rounded-full bg-cyan-500" />
                </div>
              ))}
            </div>
          </div>
          <p className="mt-10 text-xs text-slate-500">仅用于研究与辅助分析，不构成投资建议</p>
        </section>

        <section className="flex items-center px-6 py-8 sm:px-10 lg:px-14">
          <div className="w-full rounded-lg border border-slate-200 bg-white p-6 shadow-xl shadow-slate-200/60 sm:p-8">
            <div className="mb-7 flex rounded-lg bg-slate-100 p-1">
              <button
                type="button"
                onClick={() => {
                  setMode("login");
                  setError("");
                  setNotice("");
                  clearAuthNotice();
                }}
                className={`h-11 flex-1 rounded-md text-sm font-semibold ${mode === "login" ? "bg-white text-cyan-700 shadow-sm" : "text-slate-500"}`}
              >
                登录
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode("register");
                  setError("");
                  setNotice("");
                  clearAuthNotice();
                }}
                className={`h-11 flex-1 rounded-md text-sm font-semibold ${mode === "register" ? "bg-white text-cyan-700 shadow-sm" : "text-slate-500"}`}
              >
                注册
              </button>
            </div>

            <form onSubmit={submit} className="space-y-4">
              {mode === "login" ? (
                <Field
                  icon={<UserRound className="h-4 w-4" />}
                  label="手机号或用户ID"
                  value={identifier}
                  onChange={setIdentifier}
                  placeholder="输入手机号或用户ID"
                />
              ) : (
                <>
                  <Field
                    icon={<Phone className="h-4 w-4" />}
                    label="手机号"
                    value={phone}
                    onChange={setPhone}
                    placeholder="输入 11 位手机号"
                  />
                  <Field
                    icon={<UserRound className="h-4 w-4" />}
                    label="用户ID"
                    value={userId}
                    onChange={setUserId}
                    placeholder="支持中文、英文、数字、_、-"
                  />
                </>
              )}

              <PasswordField
                label="密码"
                value={password}
                onChange={setPassword}
                show={showPassword}
                onToggle={() => setShowPassword((value) => !value)}
              />

              {mode === "register" ? (
                <PasswordField
                  label="确认密码"
                  value={confirmPassword}
                  onChange={setConfirmPassword}
                  show={showPassword}
                  onToggle={() => setShowPassword((value) => !value)}
                />
              ) : null}

              {error ? <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div> : null}
              {!error && notice ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">{notice}</div>
              ) : null}

              <button
                disabled={loading}
                className="h-12 w-full rounded-lg bg-cyan-700 text-sm font-semibold text-white shadow-sm transition hover:bg-cyan-800 disabled:opacity-60"
              >
                {loading ? "处理中..." : mode === "login" ? "登录工作台" : "创建账户"}
              </button>
            </form>
          </div>
        </section>
      </div>
    </main>
  );
}

function Field({
  icon,
  label,
  value,
  onChange,
  placeholder,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-slate-600">{label}</span>
      <span className="mt-1 flex h-11 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 focus-within:border-cyan-500">
        <span className="text-slate-400">{icon}</span>
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          required
          className="h-full min-w-0 flex-1 border-0 bg-transparent p-0 text-sm outline-none"
        />
      </span>
    </label>
  );
}

function PasswordField({
  label,
  value,
  onChange,
  show,
  onToggle,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  show: boolean;
  onToggle: () => void;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-slate-600">{label}</span>
      <span className="mt-1 flex h-11 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 focus-within:border-cyan-500">
        <Lock className="h-4 w-4 text-slate-400" />
        <input
          type={show ? "text" : "password"}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="至少 8 位，建议包含大小写和数字"
          required
          className="h-full min-w-0 flex-1 border-0 bg-transparent p-0 text-sm outline-none"
        />
        <button type="button" onClick={onToggle} className="text-slate-400 hover:text-slate-700">
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </span>
    </label>
  );
}
