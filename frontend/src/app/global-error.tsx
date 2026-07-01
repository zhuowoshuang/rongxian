"use client";

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="zh-CN">
      <body>
        <main className="flex min-h-screen items-center justify-center bg-[#f4f8fb] p-6 text-slate-900">
          <section className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-8 text-center shadow-sm">
            <p className="text-sm font-semibold text-cyan-700">系统遇到异常</p>
            <h1 className="mt-2 text-2xl font-bold">请重新加载页面</h1>
            <p className="mt-3 text-sm leading-6 text-slate-600">错误详情已被隐藏，避免暴露内部信息。</p>
            <button onClick={reset} className="mt-6 rounded-lg bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-800">
              重新加载
            </button>
          </section>
        </main>
      </body>
    </html>
  );
}
