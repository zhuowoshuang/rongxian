"use client";

import Link from "next/link";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f4f8fb] p-6 text-slate-900">
      <section className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-8 text-center shadow-sm">
        <p className="text-sm font-semibold text-cyan-700">页面暂时不可用</p>
        <h1 className="mt-2 text-2xl font-bold">请重试或返回首页</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          {error?.message || "页面加载时遇到异常，系统已拦截原始错误信息。"}
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <button onClick={reset} className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-800">
            重新加载
          </button>
          <Link href="/dashboard" className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
            返回首页
          </Link>
        </div>
      </section>
    </main>
  );
}
