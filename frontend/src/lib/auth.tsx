"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { clearAuthNotice, clearClientSession } from "@/lib/api";
import { safeGetItem, safeRemoveItem, safeSetItem } from "@/lib/safeStorage";

interface User {
  username: string;
  phone?: string;
  user_id?: string;
  display_name: string;
  role: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (identifier: string, password: string, redirectTo?: string | null) => Promise<void>;
  register: (phone: string, userId: string, password: string, redirectTo?: string | null) => Promise<void>;
  logout: () => void;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function mapValidationMessage(field: string, message: string): string {
  if (field === "phone") {
    if (/required/i.test(message)) return "手机号不能为空";
    return "手机号格式不正确，请输入 11 位手机号";
  }
  if (field === "user_id" || field === "userId") {
    if (/required/i.test(message)) return "用户ID不能为空";
    return "用户ID格式不正确，请检查后重试";
  }
  if (field === "password") {
    if (/required/i.test(message)) return "密码不能为空";
    return "密码格式不正确，请检查后重试";
  }
  if (field === "confirm_password") return "确认密码不能为空";
  return "";
}

export function normalizeApiError(body: unknown, fallback: string): string {
  if (!body) return fallback;
  if (typeof body === "string") return body || fallback;
  if (typeof body !== "object") return fallback;

  const payload = body as Record<string, unknown>;

  if (typeof payload.detail === "string" && payload.detail.trim()) return payload.detail;
  if (typeof payload.message === "string" && payload.message.trim()) return payload.message;

  if (Array.isArray(payload.detail)) {
    const messages = payload.detail
      .map((item) => {
        if (!item || typeof item !== "object") return "";
        const entry = item as Record<string, unknown>;
        const msg = typeof entry.msg === "string" ? entry.msg : "";
        const loc = Array.isArray(entry.loc) ? entry.loc : [];
        const field = typeof loc[loc.length - 1] === "string" ? String(loc[loc.length - 1]) : "";
        return mapValidationMessage(field, msg) || msg;
      })
      .filter(Boolean);

    if (messages.length > 0) return messages.join("；");
    return fallback;
  }

  if (payload.detail && typeof payload.detail === "object") {
    const detail = payload.detail as Record<string, unknown>;
    if (typeof detail.message === "string" && detail.message.trim()) return detail.message;
    if (typeof detail.msg === "string" && detail.msg.trim()) return detail.msg;
  }

  return fallback;
}

async function readJsonSafe(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function persistAuth(data: { access_token: string; username: string; phone?: string; user_id?: string; display_name: string; role: string }) {
  const userData = {
    username: data.username,
    phone: data.phone,
    user_id: data.user_id,
    display_name: data.display_name,
    role: data.role,
  };
  safeSetItem(typeof window !== "undefined" ? window.localStorage : undefined, "token", data.access_token);
  safeSetItem(typeof window !== "undefined" ? window.localStorage : undefined, "user", JSON.stringify(userData));
  return userData;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const handleLogout = () => {
      setToken(null);
      setUser(null);
    };
    window.addEventListener("auth:logout", handleLogout);
    return () => window.removeEventListener("auth:logout", handleLogout);
  }, []);

  useEffect(() => {
    const savedToken = safeGetItem(window.localStorage, "token");
    const savedUser = safeGetItem(window.localStorage, "user");
    if (!savedToken || !savedUser) {
      setLoading(false);
      return;
    }

    let parsedUser: User | null = null;
    try {
      parsedUser = JSON.parse(savedUser) as User;
    } catch {
      safeRemoveItem(window.localStorage, "token");
      safeRemoveItem(window.localStorage, "user");
      setLoading(false);
      return;
    }

    if (!parsedUser?.username || !parsedUser?.role) {
      safeRemoveItem(window.localStorage, "token");
      safeRemoveItem(window.localStorage, "user");
      setLoading(false);
      return;
    }

    setToken(savedToken);
    setUser(parsedUser);

    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 8000);

    fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${savedToken}` },
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) {
          clearClientSession("expired");
          setToken(null);
          setUser(null);
        }
      })
      .catch(() => undefined)
      .finally(() => {
        window.clearTimeout(timeout);
        setLoading(false);
      });
  }, []);

  const login = async (identifier: string, password: string, redirectTo?: string | null) => {
    let response: Response;
    try {
      response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, password }),
      });
    } catch {
      throw new Error("无法连接服务器，请检查后端服务是否启动");
    }

    if (!response.ok) {
      const errorBody = await readJsonSafe(response);
      throw new Error(normalizeApiError(errorBody, "手机号、用户ID或密码错误，请检查后重试"));
    }

    const data = await response.json();
    clearAuthNotice();
    const userData = persistAuth(data);
    setToken(data.access_token);
    setUser(userData);
    const target = redirectTo && redirectTo.startsWith("/") ? redirectTo : data.role === "admin" ? "/admin" : "/dashboard";
    window.location.href = target;
  };

  const register = async (phone: string, userId: string, password: string, redirectTo?: string | null) => {
    let response: Response;
    try {
      response = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, user_id: userId, password }),
      });
    } catch {
      throw new Error("无法连接服务器，请检查后端服务是否启动");
    }

    if (!response.ok) {
      const errorBody = await readJsonSafe(response);
      throw new Error(normalizeApiError(errorBody, "注册失败，请检查填写信息后重试"));
    }

    const data = await response.json();
    clearAuthNotice();
    const userData = persistAuth(data);
    setToken(data.access_token);
    setUser(userData);
    const target = redirectTo && redirectTo.startsWith("/") ? redirectTo : data.role === "admin" ? "/admin" : "/dashboard";
    window.location.href = target;
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    if (typeof window !== "undefined") {
      clearClientSession("logged_out");
      window.location.replace("/login");
    }
  };

  return <AuthContext.Provider value={{ user, token, login, register, logout, loading }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
