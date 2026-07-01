import Link from "next/link";

export default function NotFoundPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f4f8fb] p-6 text-slate-900">
      <section className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-8 text-center shadow-sm">
        <p className="text-sm font-semibold text-cyan-700">未找到页面</p>
        <h1 className="mt-2 text-2xl font-bold">该页面不存在或已移动</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">请返回投研驾驶舱继续使用系统。</p>
        <Link href="/dashboard" className="mt-6 inline-flex rounded-lg bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-800">
          返回首页
        </Link>
      </section>
    </main>
  );
}
