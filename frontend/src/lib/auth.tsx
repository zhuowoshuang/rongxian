"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { useTranslation } from "@/lib/i18n";

interface User {
  username: string;
  display_name: string;
  role: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, displayName: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // 监听 401 强制登出事件
  useEffect(() => {
    const handleLogout = () => { setToken(null); setUser(null); };
    window.addEventListener("auth:logout", handleLogout);
    return () => window.removeEventListener("auth:logout", handleLogout);
  }, []);

  useEffect(() => {
    const savedToken = localStorage.getItem("token");
    const savedUser = localStorage.getItem("user");
    if (savedToken && savedUser) {
      let parsedUser: User | null = null;
      try {
        parsedUser = JSON.parse(savedUser) as User;
      } catch {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        setLoading(false);
        return;
      }
      if (!parsedUser?.username || !parsedUser?.role) {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        setLoading(false);
        return;
      }
      setToken(savedToken);
      setUser(parsedUser);
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 8000);
      fetch("/api/auth/me", {
        headers: { Authorization: `Bearer ${savedToken}` },
        signal: controller.signal,
      })
        .then((r) => {
          if (!r.ok) {
            localStorage.removeItem("token");
            localStorage.removeItem("user");
            setToken(null);
            setUser(null);
          }
        })
        .catch(() => {})
        .finally(() => { clearTimeout(timeout); setLoading(false); });
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (username: string, password: string) => {
    let res: Response;
    try {
      res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
    } catch {
      throw new Error(t("auth.serverError"));
    }
    if (!res.ok) {
      let msg = t("auth.loginFailed");
      try {
        const err = await res.json();
        msg = err.detail || msg;
      } catch {}
      throw new Error(msg);
    }
    const data = await res.json();
    const userData = { username: data.username, display_name: data.display_name, role: data.role };
    setToken(data.access_token);
    setUser(userData);
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("user", JSON.stringify(userData));
  };

  const register = async (username: string, password: string, displayName: string) => {
    let res: Response;
    try {
      res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, display_name: displayName }),
      });
    } catch {
      throw new Error(t("auth.serverError"));
    }
    if (!res.ok) {
      let msg = t("auth.registerFailed");
      try {
        const err = await res.json();
        msg = err.detail || msg;
      } catch {}
      throw new Error(msg);
    }
    const data = await res.json();
    const userData = { username: data.username, display_name: data.display_name, role: data.role };
    setToken(data.access_token);
    setUser(userData);
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("user", JSON.stringify(userData));
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  };

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
