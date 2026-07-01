"use client";

import { useEffect, useState } from "react";
import {
  createMyApiConfig,
  deleteMyApiConfig,
  deleteMyWatchlistItem,
  getMyApiConfigs,
  getMyBacktests,
  getMyReports,
  getMyUsage,
  getMyWatchlist,
  getProfile,
  refreshMyWatchlistItem,
  testMyApiConfig,
  updateMyApiConfig,
} from "@/lib/api";
import { Edit3, Loader2, LogOut, PlugZap, RefreshCw, Save, Star, Trash2 } from "lucide-react";
import { useAuth } from "@/lib/auth";

const tabs = ["账户信息", "我的 API 配置", "我的报告", "我的回测", "我的关注"] as const;

function testStatusLabel(status: string) {
  if (status === "ok") return "测试通过";
  if (status === "format_valid") return "格式有效";
  if (status === "unsupported") return "暂未支持自动测试";
  return "测试失败";
}

function roleLabel(role: string): string {
  if (role === "admin") return "管理员";
  if (role === "analyst") return "分析师";
  return "普通用户";
}

export default function ProfilePage() {
  const { user, logout } = useAuth();
  const [active, setActive] = useState<(typeof tabs)[number]>("账户信息");
  const [profile, setProfile] = useState<any>(null);
  const [usage, setUsage] = useState<any>(null);
  const [configs, setConfigs] = useState<any[]>([]);
  const [reports, setReports] = useState<any[]>([]);
  const [backtests, setBacktests] = useState<any[]>([]);
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [watchRefreshingId, setWatchRefreshingId] = useState<number | null>(null);
  const [form, setForm] = useState({ name: "", provider: "", base_url: "", api_key: "", model_name: "", note: "", is_default: false });

  const show = (type: "ok" | "err", text: string) => setMsg({ type, text });

  const load = async () => {
    const [p, u, c, r, b, w] = await Promise.all([
      getProfile(),
      getMyUsage(),
      getMyApiConfigs(),
      getMyReports(),
      getMyBacktests(),
      getMyWatchlist(),
    ]);
    setProfile(p);
    setUsage(u);
    setConfigs(c);
    setReports(r);
    setBacktests(b);
    setWatchlist(w);
  };

  useEffect(() => {
    load().catch((e) => show("err", e.message));
  }, []);

  const resetForm = () => {
    setForm({ name: "", provider: "", base_url: "", api_key: "", model_name: "", note: "", is_default: false });
    setEditingId(null);
  };

  const saveConfig = async () => {
    setSaving(true);
    try {
      if (!form.name.trim() || !form.provider.trim()) throw new Error("配置名称和供应商不能为空。");
      if (editingId) await updateMyApiConfig(editingId, form);
      else await createMyApiConfig(form);
      resetForm();
      await load();
      show("ok", editingId ? "API 配置已更新。" : "API 配置已保存。");
    } catch (e: any) {
      show("err", e.message || "API 配置保存失败。");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (config: any) => {
    setEditingId(config.id);
    setForm({
      name: config.name || "",
      provider: config.provider || "",
      base_url: config.base_url || "",
      api_key: "",
      model_name: config.model_name || "",
      note: config.note || "",
      is_default: Boolean(config.is_default),
    });
    setActive("我的 API 配置");
  };

  const handleTest = async (config: any) => {
    setTestingId(config.id);
    try {
      const result = await testMyApiConfig(config.id);
      show(result.status === "failed" ? "err" : "ok", `${testStatusLabel(result.status)}：${result.message}`);
    } catch (e: any) {
      show("err", e.message || "测试连接失败。");
    } finally {
      setTestingId(null);
    }
  };

  const handleDelete = async (config: any) => {
    if (!confirm(`确认删除「${config.name}」？`)) return;
    try {
      await deleteMyApiConfig(config.id);
      await load();
      show("ok", "配置已删除。");
    } catch (e: any) {
      show("err", e.message || "删除失败。");
    }
  };

  const makeDefault = async (config: any) => {
    try {
      await updateMyApiConfig(config.id, { ...config, api_key: "", is_default: true });
      await load();
      show("ok", "默认 API 配置已更新。");
    } catch (e: any) {
      show("err", e.message || "设置默认失败。");
    }
  };

  const refreshWatch = async (item: any) => {
    setWatchRefreshingId(item.id);
    try {
      await refreshMyWatchlistItem(item.id);
      await load();
      show("ok", `${item.stock_code} 关注快照已刷新。`);
    } catch (e: any) {
      show("err", e.message || "关注快照刷新失败。");
    } finally {
      setWatchRefreshingId(null);
    }
  };

  const removeWatch = async (item: any) => {
    if (!confirm(`确认取消关注 ${item.stock_code} ${item.stock_name || ""}？`)) return;
    try {
      await deleteMyWatchlistItem(item.id);
      await load();
      show("ok", "已取消关注。");
    } catch (e: any) {
      show("err", e.message || "取消关注失败。");
    }
  };

  const usageItems = usage?.items || {};

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-heading)]">个人中心</h1>
        <p className="mt-1 text-sm text-[var(--text-muted)]">查看账号、用量、API 配置、报告、回测和关注股票。</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActive(tab)}
            className={`rounded-lg px-4 py-2 text-sm font-medium ${active === tab ? "bg-cyan-700 text-white" : "border border-slate-200 bg-white text-slate-600"}`}
          >
            {tab}
          </button>
        ))}
      </div>

      {msg && <div className={`rounded-lg border px-4 py-3 text-sm ${msg.type === "ok" ? "border-cyan-100 bg-cyan-50 text-cyan-800" : "border-red-100 bg-red-50 text-red-700"}`}>{msg.text}</div>}

      {active === "账户信息" && (
        <div className="grid gap-5 xl:grid-cols-[1fr_1.2fr]">
          <Panel title="账户信息">
            <Info label="用户名" value={user?.username || profile?.user_id || profile?.username || "-"} />
            <Info label="手机号" value={profile?.phone || "-"} />
            <Info label="用户 ID" value={profile?.user_id || profile?.username || "-"} />
            <Info label="角色" value={roleLabel(profile?.role || user?.role || "user")} />
            <Info label="登录状态" value={user ? "已登录" : "未登录"} />
            <Info label="注册时间" value={profile?.created_at || "-"} />
            <Info label="最近登录" value={profile?.last_login_at || "暂无记录"} />
            <button
              onClick={logout}
              className="mt-2 inline-flex items-center justify-center gap-2 rounded-lg border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
            >
              <LogOut className="h-4 w-4" />
              退出登录
            </button>
            <p className="mt-3 text-xs leading-5 text-slate-400">
              本系统仅用于研究和辅助分析，不构成投资建议。
            </p>
          </Panel>
          <Panel title="今日用量与剩余额度">
            <div className="grid gap-3 sm:grid-cols-2">
              {Object.entries(usageItems).map(([key, item]: any) => (
                <div key={key} className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                  <div className="text-sm text-slate-500">{item.label}</div>
                  <div className="mt-1 text-lg font-semibold text-slate-900">
                    {item.used} / {item.unlimited ? "不限" : item.limit}
                  </div>
                  <div className="mt-1 text-xs text-slate-500">{item.unlimited ? "管理员不受该额度限制" : `剩余 ${item.remaining}`}</div>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}

      {active === "我的 API 配置" && (
        <div className="grid gap-5 lg:grid-cols-[360px_1fr]">
          <Panel title={editingId ? "编辑配置" : "新增配置"}>
            {(["name", "provider", "base_url", "api_key", "model_name", "note"] as const).map((key) => (
              <input
                key={key}
                value={(form as any)[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                placeholder={{
                  name: "配置名称",
                  provider: "供应商，如 openai / deepseek / custom",
                  base_url: "Base URL",
                  api_key: editingId ? "留空则不更新 Key" : "API Key",
                  model_name: "模型名称",
                  note: "备注",
                }[key]}
                className="h-10 rounded-lg border border-slate-200 px-3 text-sm"
                type={key === "api_key" ? "password" : "text"}
              />
            ))}
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input type="checkbox" checked={form.is_default} onChange={(e) => setForm({ ...form, is_default: e.target.checked })} />
              设为默认
            </label>
            <button onClick={saveConfig} disabled={saving} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-cyan-700 px-4 text-sm font-semibold text-white disabled:opacity-60">
              <Save className="h-4 w-4" />
              {saving ? "保存中..." : editingId ? "更新配置" : "保存配置"}
            </button>
            {editingId && (
              <button onClick={resetForm} className="h-10 rounded-lg border border-slate-200 px-4 text-sm text-slate-600">
                取消编辑
              </button>
            )}
          </Panel>

          <Panel title="已保存配置">
            <div className="overflow-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-500">
                    {["名称", "供应商", "Base URL", "Key", "模型", "默认", "操作"].map((h) => (
                      <th key={h} className="border-b p-2">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {configs.map((c) => (
                    <tr key={c.id} className="border-b last:border-0">
                      <td className="p-2">{c.name}</td>
                      <td className="p-2">{c.provider}</td>
                      <td className="p-2">{c.base_url || "-"}</td>
                      <td className="p-2 font-mono">{c.api_key || "-"}</td>
                      <td className="p-2">{c.model_name || "-"}</td>
                      <td className="p-2">
                        {c.is_default ? "是" : <button className="text-xs text-cyan-700" onClick={() => makeDefault(c)}>设为默认</button>}
                      </td>
                      <td className="p-2">
                        <button title="测试连接" disabled={testingId === c.id} onClick={() => handleTest(c)} className="mr-2 text-cyan-700 disabled:opacity-50">
                          <PlugZap className="h-4 w-4" />
                        </button>
                        <button title="编辑" onClick={() => startEdit(c)} className="mr-2 text-slate-600">
                          <Edit3 className="h-4 w-4" />
                        </button>
                        <button title="删除" onClick={() => handleDelete(c)} className="text-red-600">
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {configs.length === 0 && <tr><td colSpan={7} className="p-6 text-center text-sm text-slate-500">暂无配置</td></tr>}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      )}

      {active === "我的报告" && (
        <Panel title="我的报告">
          {reports.length
            ? reports.map((r) => <Info key={r.id} label={`${r.stock_code || "系统"} ${r.stock_name || r.title}`} value={`${r.report_type || "-"} / ${r.style || "通用"} / 下载 ${r.download_count || 0} 次 / ${r.created_at || ""}`} />)
            : <Empty />}
        </Panel>
      )}

      {active === "我的回测" && (
        <Panel title="我的回测">
          {backtests.length
            ? backtests.map((b) => <Info key={b.id} label={`${b.stock_code || "-"} ${b.stock_name || ""} / ${b.strategy_name || b.strategy || "-"}`} value={`${b.status === "success" ? "成功" : "失败"} / ${b.start_date} 至 ${b.end_date} / ${b.created_at || ""}`} />)
            : <Empty />}
        </Panel>
      )}

      {active === "我的关注" && (
        <Panel title="我的关注">
          {watchlist.length ? (
            <div className="grid gap-4">
              {watchlist.map((item) => (
                <div key={item.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <Star className="h-4 w-4 text-amber-500" />
                        <span className="font-semibold text-slate-900">{item.stock_code} {item.stock_name || ""}</span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{item.market || "-"} / {item.industry || "行业待补充"} / 快照 {item.snapshot?.snapshot_date || "暂无"}</p>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => refreshWatch(item)} disabled={watchRefreshingId === item.id} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 disabled:opacity-60">
                        {watchRefreshingId === item.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                        刷新快照
                      </button>
                      <button onClick={() => removeWatch(item)} className="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-white px-3 py-2 text-xs text-red-600">
                        <Trash2 className="h-3.5 w-3.5" />
                        取消关注
                      </button>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    <WatchMetric label="最新价格" value={item.snapshot?.price || "-"} />
                    <WatchMetric label="综合评分" value={item.snapshot?.total_score || "-"} />
                    <WatchMetric label="研究评级" value={item.snapshot?.rating || "-"} />
                    <WatchMetric label="信号状态" value={item.snapshot?.signal_type || "暂无"} />
                  </div>

                  <div className="mt-4 grid gap-3 xl:grid-cols-2">
                    <SnapshotPanel title="研究快照" lines={[
                      `公司新闻：${item.snapshot?.news_summary?.summary || "暂无数据"}`,
                      `行业状态：${item.snapshot?.industry_support?.summary || "暂无数据"}`,
                      `股东结构：${item.snapshot?.shareholder_signal?.summary || "暂无数据"}`,
                      `业绩趋势：${item.snapshot?.earnings_signal?.summary || "暂无数据"}`,
                    ]} />
                    <SnapshotPanel title="风险与波动" lines={[
                      `波动率：${item.snapshot?.volatility_signal?.summary || "暂无数据"}`,
                      `风险提示：${(item.snapshot?.risk_flags || []).join("、") || "暂无显著风险提示"}`,
                      `PE / PB：${item.snapshot?.key_metrics?.pe ?? "-"} / ${item.snapshot?.key_metrics?.pb ?? "-"}`,
                      `ROE / 净利同比：${item.snapshot?.key_metrics?.roe ?? "-"} / ${item.snapshot?.key_metrics?.net_profit_yoy ?? "-"}`,
                    ]} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <Empty text="暂无关注股票。可在个股详情页点击“加入关注”建立研究快照。" />
          )}
        </Panel>
      )}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-4 text-base font-semibold text-slate-900">{title}</h2>
      <div className="grid gap-3">{children}</div>
    </section>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 rounded-lg border border-slate-100 bg-slate-50 p-3 sm:grid-cols-[160px_1fr]">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="text-sm font-medium text-slate-900">{value}</div>
    </div>
  );
}

function WatchMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-white p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 text-base font-semibold text-slate-900">{value}</div>
    </div>
  );
}

function SnapshotPanel({ title, lines }: { title: string; lines: string[] }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-white p-3">
      <div className="text-sm font-semibold text-slate-900">{title}</div>
      <div className="mt-2 space-y-2 text-xs leading-5 text-slate-600">
        {lines.map((line) => <div key={line}>{line}</div>)}
      </div>
    </div>
  );
}

function Empty({ text = "暂无记录" }: { text?: string }) {
  return <div className="rounded-lg border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500">{text}</div>;
}
