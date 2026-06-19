"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { CheckCircle, AlertCircle, Info, X } from "lucide-react";

type ToastType = "success" | "error" | "info";

interface ToastItem {
  id: number;
  type: ToastType;
  message: string;
}

let _nextId = 0;
let _listener: ((items: ToastItem[]) => void) | null = null;
let _toasts: ToastItem[] = [];

function _emit() {
  _listener?.([..._toasts]);
}

function _addToast(type: ToastType, message: string) {
  // L-02: 去重 - 相同类型+消息的 toast 不重复显示
  if (_toasts.some((t) => t.type === type && t.message === message)) return;
  const id = _nextId++;
  _toasts = [..._toasts, { id, type, message }];
  _emit();
  setTimeout(() => {
    _toasts = _toasts.filter((t) => t.id !== id);
    _emit();
  }, 3500);
}

function _removeToast(id: number) {
  _toasts = _toasts.filter((t) => t.id !== id);
  _emit();
}

/** 显示一条 Toast 通知 */
export function showToast(type: ToastType, message: string) {
  if (typeof window === "undefined") return;
  _addToast(type, message);
}

const ICON_MAP = {
  success: CheckCircle,
  error: AlertCircle,
  info: Info,
};

const COLOR_MAP = {
  success: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400",
  error: "bg-red-500/10 border-red-500/30 text-red-400",
  info: "bg-blue-500/10 border-blue-500/30 text-blue-400",
};

const ICON_COLOR = {
  success: "text-emerald-400",
  error: "text-red-400",
  info: "text-blue-400",
};

export default function ToastContainer() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    _listener = setToasts;
    setToasts([..._toasts]);
    return () => { _listener = null; };
  }, []);

  if (!mounted || toasts.length === 0) return null;

  return createPortal(
    <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none" style={{ maxWidth: 380 }}>
      {toasts.map((t) => {
        const Icon = ICON_MAP[t.type];
        return (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl border backdrop-blur-md shadow-lg animate-[slideIn_0.25s_ease-out] ${COLOR_MAP[t.type]}`}
          >
            <Icon size={18} className={`flex-shrink-0 mt-0.5 ${ICON_COLOR[t.type]}`} />
            <span className="text-sm flex-1 leading-relaxed">{t.message}</span>
            <button
              onClick={() => _removeToast(t.id)}
              className="flex-shrink-0 opacity-50 hover:opacity-100 transition-opacity"
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
      <style>{`
        @keyframes slideIn {
          from { opacity: 0; transform: translateX(20px); }
          to { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </div>,
    document.body
  );
}
