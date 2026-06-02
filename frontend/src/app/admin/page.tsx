"use client";

import { useEffect, useState } from "react";
import {
  getAdminStats, getAdminUsers, updateAdminUser, disableAdminUser,
  getAdminTables, getAdminTableData,
  getApiConfigs, saveApiConfig, deleteApiConfig, testApiConfig,
  getUserQuotas, updateUserQuota,
  getApiLogs, getApiStats,
} from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";
import TabSwitch from "@/components/ui/TabSwitch";
import { SkeletonCard } from "@/components/ui/Skeleton";
import EmptyState from "@/components/ui/EmptyState";
import { Shield, Users, Database, BarChart3, AlertCircle, CheckCircle, Key, Activity, Settings } from "lucide-react";

export default function AdminPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState("overview");
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const showMsg = (type: "ok" | "err", text: string) => {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 3000);
  };

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
      <h1 className="text-xl font-bold text-white flex items-center gap-2">
        <span className="w-1 h-6 bg-primary-500 rounded-full" />
        {t("admin.title")}
      </h1>

      {msg && (
        <div className={`px-4 py-3 rounded-xl text-sm flex items-center gap-2 ${
          msg.type === "ok" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"
        }`}>
          {msg.type === "ok" ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
          {msg.text}
        </div>
      )}

      <TabSwitch
        tabs={[
          { key: "overview", label: "📊 系统概览" },
          { key: "users", label: "👥 用户管理" },
          { key: "api-config", label: "🔑 API配置" },
          { key: "quotas", label: "📋 用户配额" },
          { key: "api-logs", label: "📈 调用日志" },
          { key: "database", label: "🗄️ 数据库" },
        ]}
        active={activeTab}
        onChange={setActiveTab}
      />

      {activeTab === "overview" && <OverviewTab />}
      {activeTab === "users" && <UsersTab showMsg={showMsg} />}
      {activeTab === "api-config" && <ApiConfigTab showMsg={showMsg} />}
      {activeTab === "quotas" && <QuotasTab showMsg={showMsg} />}
      {activeTab === "api-logs" && <ApiLogsTab />}
      {activeTab === "database" && <DatabaseTab />}

      <div className="disclaimer">{t("app.disclaimer")}</div>
    </div>
  );
}

// ==================== 系统概览 ====================

function OverviewTab() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<any>(null);
  const [apiStats, setApiStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getAdminStats().then(setStats).catch(() => {}),
      getApiStats().then(setApiStats).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  if (loading) return <SkeletonCard />;

  return (
    <>
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {[
            { label: "股票总数", value: stats.total_stocks, icon: <BarChart3 className="w-5 h-5" />, color: "text-primary-400" },
            { label: "信号总数", value: stats.total_signals, icon: <BarChart3 className="w-5 h-5" />, color: "text-emerald-400" },
            { label: "用户总数", value: stats.total_users, icon: <Users className="w-5 h-5" />, color: "text-blue-400" },
            { label: "报告总数", value: stats.total_reports, icon: <BarChart3 className="w-5 h-5" />, color: "text-amber-400" },
            { label: "数据库大小", value: stats.db_size, icon: <Database className="w-5 h-5" />, color: "text-purple-400" },
            { label: "券商研报", value: stats.total_research_reports, icon: <BarChart3 className="w-5 h-5" />, color: "text-cyan-400" },
          ].map((m) => (
            <GlassCard key={m.label} className="text-center">
              <div className={`${m.color} mb-2 flex justify-center`}>{m.icon}</div>
              <p className="text-2xl font-bold text-white font-mono">{typeof m.value === 'number' ? m.value.toLocaleString() : m.value}</p>
              <p className="text-xs text-dark-muted mt-1">{m.label}</p>
            </GlassCard>
          ))}
        </div>
      )}

      {apiStats && (
        <GlassCard title="今日API调用统计">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <p className="text-3xl font-bold text-white font-mono">{apiStats.today_total}</p>
              <p className="text-xs text-dark-muted">总调用次数</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-red-400 font-mono">{apiStats.today_errors}</p>
              <p className="text-xs text-dark-muted">错误次数</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-emerald-400 font-mono">{apiStats.avg_response_time}ms</p>
              <p className="text-xs text-dark-muted">平均响应</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-blue-400 font-mono">{Object.keys(apiStats.by_user || {}).length}</p>
              <p className="text-xs text-dark-muted">活跃用户</p>
            </div>
          </div>
          {apiStats.by_provider && Object.keys(apiStats.by_provider).length > 0 && (
            <div className="mt-4 pt-4 border-t border-white/[0.06]">
              <p className="text-xs text-dark-muted mb-2">按供应商:</p>
              <div className="flex gap-4 flex-wrap">
                {Object.entries(apiStats.by_provider).map(([k, v]) => (
                  <span key={k} className="text-sm text-dark-text">{k}: <strong className="text-white">{String(v)}</strong></span>
                ))}
              </div>
            </div>
          )}
        </GlassCard>
      )}
    </>
  );
}

// ==================== 用户管理 ====================

function UsersTab({ showMsg }: { showMsg: (type: "ok" | "err", text: string) => void }) {
  const { t } = useTranslation();
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAdminUsers().then(setUsers).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const handleRoleToggle = async (user: any) => {
    const newRole = user.role === "admin" ? "user" : "admin";
    try {
      await updateAdminUser(user.id, { role: newRole });
      setUsers((prev) => prev.map((u) => u.id === user.id ? { ...u, role: newRole } : u));
      showMsg("ok", `${user.username} → ${newRole}`);
    } catch (e: any) { showMsg("err", e.message || "操作失败"); }
  };

  const handleActiveToggle = async (user: any) => {
    try {
      if (user.is_active) {
        await disableAdminUser(user.id);
        setUsers((prev) => prev.map((u) => u.id === user.id ? { ...u, is_active: false } : u));
      } else {
        await updateAdminUser(user.id, { is_active: true });
        setUsers((prev) => prev.map((u) => u.id === user.id ? { ...u, is_active: true } : u));
      }
      showMsg("ok", `${user.username} ${user.is_active ? "已禁用" : "已启用"}`);
    } catch (e: any) { showMsg("err", e.message || "操作失败"); }
  };

  if (loading) return <SkeletonCard />;

  return (
    <GlassCard title={t("admin.userManagement")}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/[0.06]">
              {["ID", "用户名", "显示名", "角色", "状态", "注册时间", "操作"].map((h) => (
                <th key={h} className="text-left py-3 px-3 text-dark-muted font-medium text-xs">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-white/[0.03] hover:bg-white/[0.03]">
                <td className="py-3 px-3 font-mono text-xs text-dark-text">{u.id}</td>
                <td className="py-3 px-3 font-medium text-dark-text">{u.username}</td>
                <td className="py-3 px-3 text-dark-text">{u.display_name}</td>
                <td className="py-3 px-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${u.role === "admin" ? "bg-purple-500/10 text-purple-400" : "bg-blue-500/10 text-blue-400"}`}>
                    {u.role}
                  </span>
                </td>
                <td className="py-3 px-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${u.is_active ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"}`}>
                    {u.is_active ? "正常" : "禁用"}
                  </span>
                </td>
                <td className="py-3 px-3 text-xs text-dark-muted">{u.created_at?.slice(0, 19)}</td>
                <td className="py-3 px-3">
                  <div className="flex gap-2">
                    <button onClick={() => handleRoleToggle(u)} className="text-xs px-2 py-1 rounded bg-white/[0.05] hover:bg-white/[0.1] text-dark-muted hover:text-white transition-colors">
                      {u.role === "admin" ? "设为用户" : "设为管理员"}
                    </button>
                    <button onClick={() => handleActiveToggle(u)} className={`text-xs px-2 py-1 rounded transition-colors ${u.is_active ? "bg-red-500/10 text-red-400 hover:bg-red-500/20" : "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"}`}>
                      {u.is_active ? "禁用" : "启用"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassCard>
  );
}

// ==================== API配置 ====================

function ApiConfigTab({ showMsg }: { showMsg: (type: "ok" | "err", text: string) => void }) {
  const [configs, setConfigs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<any>(null);
  const [testing, setTesting] = useState<number | null>(null);

  const defaultProviders = [
    { provider: "eastmoney", display_name: "东方财富", base_url: "https://push2.eastmoney.com" },
    { provider: "yahoo", display_name: "Yahoo Finance", base_url: "https://query1.finance.yahoo.com" },
    { provider: "akshare", display_name: "AkShare", base_url: "" },
    { provider: "llm", display_name: "LLM API", base_url: "" },
  ];

  const fetchConfigs = () => {
    setLoading(true);
    getApiConfigs().then(setConfigs).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => { fetchConfigs(); }, []);

  const handleSave = async (config: any) => {
    try {
      await saveApiConfig(config);
      showMsg("ok", `${config.provider} 配置已保存`);
      fetchConfigs();
      setEditing(null);
    } catch (e: any) { showMsg("err", e.message || "保存失败"); }
  };

  const handleDelete = async (id: number, provider: string) => {
    if (!confirm(`确认删除 ${provider} 配置？`)) return;
    try {
      await deleteApiConfig(id);
      showMsg("ok", "已删除");
      fetchConfigs();
    } catch (e: any) { showMsg("err", e.message || "删除失败"); }
  };

  const handleTest = async (id: number) => {
    setTesting(id);
    try {
      const result = await testApiConfig(id);
      showMsg(result.status === "ok" ? "ok" : "err", result.message);
    } catch (e: any) { showMsg("err", e.message || "测试失败"); }
    setTesting(null);
  };

  if (loading) return <SkeletonCard />;

  return (
    <div className="space-y-4">
      <GlassCard title="API供应商配置">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.06]">
                {["供应商", "显示名称", "API密钥", "基础URL", "状态", "每日限额", "频率/分钟", "操作"].map((h) => (
                  <th key={h} className="text-left py-3 px-3 text-dark-muted font-medium text-xs">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {configs.map((c) => (
                <tr key={c.id} className="border-b border-white/[0.03] hover:bg-white/[0.03]">
                  <td className="py-3 px-3 font-mono text-xs text-primary-400">{c.provider}</td>
                  <td className="py-3 px-3 text-dark-text">{c.display_name}</td>
                  <td className="py-3 px-3 font-mono text-xs text-dark-muted">{c.api_key || "未配置"}</td>
                  <td className="py-3 px-3 text-xs text-dark-muted max-w-[150px] truncate">{c.base_url || "-"}</td>
                  <td className="py-3 px-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${c.is_enabled ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"}`}>
                      {c.is_enabled ? "启用" : "禁用"}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-right font-mono text-dark-text">{c.daily_limit}</td>
                  <td className="py-3 px-3 text-right font-mono text-dark-text">{c.rate_limit}</td>
                  <td className="py-3 px-3">
                    <div className="flex gap-1">
                      <button onClick={() => setEditing(c)} className="text-xs px-2 py-1 rounded bg-white/[0.05] hover:bg-white/[0.1] text-dark-muted">编辑</button>
                      <button onClick={() => handleTest(c.id)} disabled={testing === c.id} className="text-xs px-2 py-1 rounded bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 disabled:opacity-50">
                        {testing === c.id ? "测试中..." : "测试"}
                      </button>
                      <button onClick={() => handleDelete(c.id, c.provider)} className="text-xs px-2 py-1 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20">删除</button>
                    </div>
                  </td>
                </tr>
              ))}
              {configs.length === 0 && (
                <tr><td colSpan={8} className="py-8 text-center text-dark-muted">暂无配置，点击下方添加</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </GlassCard>

      {/* 添加新配置 */}
      <GlassCard title="添加/编辑 API 配置">
        <ApiConfigForm
          initial={editing}
          onSave={handleSave}
          onCancel={() => setEditing(null)}
        />
      </GlassCard>
    </div>
  );
}

function ApiConfigForm({ initial, onSave, onCancel }: { initial?: any; onSave: (c: any) => void; onCancel: () => void }) {
  const [form, setForm] = useState({
    provider: initial?.provider || "",
    display_name: initial?.display_name || "",
    api_key: initial?.api_key || "",
    api_secret: initial?.api_secret || "",
    base_url: initial?.base_url || "",
    is_enabled: initial?.is_enabled ?? true,
    daily_limit: initial?.daily_limit ?? 1000,
    rate_limit: initial?.rate_limit ?? 10,
  });

  useEffect(() => {
    if (initial) {
      setForm({
        provider: initial.provider || "",
        display_name: initial.display_name || "",
        api_key: initial.api_key || "",
        api_secret: initial.api_secret || "",
        base_url: initial.base_url || "",
        is_enabled: initial.is_enabled ?? true,
        daily_limit: initial.daily_limit ?? 1000,
        rate_limit: initial.rate_limit ?? 10,
      });
    }
  }, [initial]);

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div>
        <label className="text-xs text-dark-muted">供应商标识</label>
        <input value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })} placeholder="eastmoney" className="w-full mt-1" />
      </div>
      <div>
        <label className="text-xs text-dark-muted">显示名称</label>
        <input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} placeholder="东方财富" className="w-full mt-1" />
      </div>
      <div>
        <label className="text-xs text-dark-muted">API密钥</label>
        <input type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder="留空则不更新" className="w-full mt-1" />
      </div>
      <div>
        <label className="text-xs text-dark-muted">API Secret</label>
        <input type="password" value={form.api_secret} onChange={(e) => setForm({ ...form, api_secret: e.target.value })} placeholder="留空则不更新" className="w-full mt-1" />
      </div>
      <div className="col-span-2">
        <label className="text-xs text-dark-muted">基础URL</label>
        <input value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://api.example.com" className="w-full mt-1" />
      </div>
      <div>
        <label className="text-xs text-dark-muted">每日限额</label>
        <input type="number" value={form.daily_limit} onChange={(e) => setForm({ ...form, daily_limit: parseInt(e.target.value) || 0 })} className="w-full mt-1" />
      </div>
      <div>
        <label className="text-xs text-dark-muted">频率/分钟</label>
        <input type="number" value={form.rate_limit} onChange={(e) => setForm({ ...form, rate_limit: parseInt(e.target.value) || 0 })} className="w-full mt-1" />
      </div>
      <div className="flex items-end gap-2 col-span-2">
        <label className="flex items-center gap-2 text-sm text-dark-text">
          <input type="checkbox" checked={form.is_enabled} onChange={(e) => setForm({ ...form, is_enabled: e.target.checked })} />
          启用
        </label>
        <button onClick={() => onSave(form)} className="btn-primary px-4 py-2 text-sm">保存</button>
        {onCancel && <button onClick={onCancel} className="btn-secondary px-4 py-2 text-sm">取消</button>}
      </div>
    </div>
  );
}

// ==================== 用户配额 ====================

function QuotasTab({ showMsg }: { showMsg: (type: "ok" | "err", text: string) => void }) {
  const [quotas, setQuotas] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingUser, setEditingUser] = useState<number | null>(null);

  const fetchQuotas = () => {
    setLoading(true);
    getUserQuotas().then(setQuotas).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => { fetchQuotas(); }, []);

  const handleSave = async (userId: number, quota: any) => {
    try {
      await updateUserQuota(userId, quota);
      showMsg("ok", "配额已更新");
      fetchQuotas();
      setEditingUser(null);
    } catch (e: any) { showMsg("err", e.message || "更新失败"); }
  };

  if (loading) return <SkeletonCard />;

  return (
    <GlassCard title="用户API配额管理">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/[0.06]">
              {["用户", "角色", "报告/日", "回测/日", "搜索/日", "PDF/日", "PDF", "风格报告", "模拟买入", "今日调用", "操作"].map((h) => (
                <th key={h} className="text-left py-3 px-2 text-dark-muted font-medium text-xs whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {quotas.map((q) => (
              <tr key={q.user_id} className="border-b border-white/[0.03] hover:bg-white/[0.03]">
                <td className="py-3 px-2 font-medium text-dark-text">{q.username}</td>
                <td className="py-3 px-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${q.role === "admin" ? "bg-purple-500/10 text-purple-400" : "bg-blue-500/10 text-blue-400"}`}>{q.role}</span>
                </td>
                <td className="py-3 px-2 text-right font-mono text-dark-text">{q.role === "admin" ? "∞" : q.daily_report_limit}</td>
                <td className="py-3 px-2 text-right font-mono text-dark-text">{q.role === "admin" ? "∞" : q.daily_backtest_limit}</td>
                <td className="py-3 px-2 text-right font-mono text-dark-text">{q.role === "admin" ? "∞" : q.daily_search_limit}</td>
                <td className="py-3 px-2 text-right font-mono text-dark-text">{q.role === "admin" ? "∞" : q.daily_pdf_limit}</td>
                <td className="py-3 px-2 text-center">{q.can_download_pdf ? "✅" : "❌"}</td>
                <td className="py-3 px-2 text-center">{q.can_use_style_report ? "✅" : "❌"}</td>
                <td className="py-3 px-2 text-center">{q.can_use_simulation ? "✅" : "❌"}</td>
                <td className="py-3 px-2 text-right font-mono text-primary-400">{q.today_calls}</td>
                <td className="py-3 px-2">
                  {q.role !== "admin" && (
                    <button onClick={() => setEditingUser(editingUser === q.user_id ? null : q.user_id)} className="text-xs px-2 py-1 rounded bg-white/[0.05] hover:bg-white/[0.1] text-dark-muted">
                      {editingUser === q.user_id ? "收起" : "编辑"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 编辑配额弹出 */}
      {editingUser && quotas.filter(q => q.user_id === editingUser).map(q => (
        <QuotaEditForm key={q.user_id} quota={q} onSave={(data) => handleSave(q.user_id, data)} onCancel={() => setEditingUser(null)} />
      ))}
    </GlassCard>
  );
}

function QuotaEditForm({ quota, onSave, onCancel }: { quota: any; onSave: (d: any) => void; onCancel: () => void }) {
  const [form, setForm] = useState({
    daily_report_limit: quota.daily_report_limit,
    daily_backtest_limit: quota.daily_backtest_limit,
    daily_search_limit: quota.daily_search_limit,
    daily_pdf_limit: quota.daily_pdf_limit,
    can_download_pdf: quota.can_download_pdf,
    can_use_style_report: quota.can_use_style_report,
    can_use_simulation: quota.can_use_simulation,
  });

  return (
    <div className="mt-4 p-4 rounded-xl bg-white/[0.03] border border-white/[0.08]">
      <h4 className="text-sm font-medium text-white mb-3">编辑 {quota.username} 的配额</h4>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
          <label className="text-xs text-dark-muted">每日报告上限</label>
          <input type="number" value={form.daily_report_limit} onChange={(e) => setForm({ ...form, daily_report_limit: parseInt(e.target.value) || 0 })} className="w-full mt-1" />
        </div>
        <div>
          <label className="text-xs text-dark-muted">每日期回测上限</label>
          <input type="number" value={form.daily_backtest_limit} onChange={(e) => setForm({ ...form, daily_backtest_limit: parseInt(e.target.value) || 0 })} className="w-full mt-1" />
        </div>
        <div>
          <label className="text-xs text-dark-muted">每日搜索上限</label>
          <input type="number" value={form.daily_search_limit} onChange={(e) => setForm({ ...form, daily_search_limit: parseInt(e.target.value) || 0 })} className="w-full mt-1" />
        </div>
        <div>
          <label className="text-xs text-dark-muted">每日PDF上限</label>
          <input type="number" value={form.daily_pdf_limit} onChange={(e) => setForm({ ...form, daily_pdf_limit: parseInt(e.target.value) || 0 })} className="w-full mt-1" />
        </div>
        <div className="flex items-center gap-4 col-span-3">
          <label className="flex items-center gap-2 text-sm text-dark-text">
            <input type="checkbox" checked={form.can_download_pdf} onChange={(e) => setForm({ ...form, can_download_pdf: e.target.checked })} /> PDF下载
          </label>
          <label className="flex items-center gap-2 text-sm text-dark-text">
            <input type="checkbox" checked={form.can_use_style_report} onChange={(e) => setForm({ ...form, can_use_style_report: e.target.checked })} /> 风格报告
          </label>
          <label className="flex items-center gap-2 text-sm text-dark-text">
            <input type="checkbox" checked={form.can_use_simulation} onChange={(e) => setForm({ ...form, can_use_simulation: e.target.checked })} /> 模拟买入
          </label>
        </div>
        <div className="flex items-end gap-2">
          <button onClick={() => onSave(form)} className="btn-primary px-4 py-2 text-sm">保存</button>
          <button onClick={onCancel} className="btn-secondary px-4 py-2 text-sm">取消</button>
        </div>
      </div>
    </div>
  );
}

// ==================== 调用日志 ====================

function ApiLogsTab() {
  const [logs, setLogs] = useState<any>({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setLoading(true);
    getApiLogs({ page, page_size: 50 }).then(setLogs).catch(() => {}).finally(() => setLoading(false));
  }, [page]);

  if (loading) return <SkeletonCard />;

  return (
    <GlassCard title="API调用日志">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/[0.06]">
              {["时间", "用户", "供应商", "接口", "方法", "状态", "耗时", "错误"].map((h) => (
                <th key={h} className="text-left py-3 px-2 text-dark-muted font-medium text-xs whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {logs.items?.map((l: any) => (
              <tr key={l.id} className="border-b border-white/[0.03] hover:bg-white/[0.03]">
                <td className="py-2 px-2 text-xs text-dark-muted font-mono">{l.called_at?.slice(0, 19)}</td>
                <td className="py-2 px-2 text-xs text-dark-text">{l.username}</td>
                <td className="py-2 px-2 text-xs text-dark-muted">{l.provider}</td>
                <td className="py-2 px-2 text-xs font-mono text-dark-text max-w-[200px] truncate">{l.endpoint}</td>
                <td className="py-2 px-2 text-xs text-dark-muted">{l.method}</td>
                <td className="py-2 px-2">
                  <span className={`text-xs px-1.5 py-0.5 rounded ${l.status_code < 400 ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"}`}>
                    {l.status_code}
                  </span>
                </td>
                <td className="py-2 px-2 text-xs font-mono text-dark-muted">{l.response_time}ms</td>
                <td className="py-2 px-2 text-xs text-red-400 max-w-[150px] truncate">{l.error_msg || "-"}</td>
              </tr>
            ))}
            {(!logs.items || logs.items.length === 0) && (
              <tr><td colSpan={8} className="py-8 text-center text-dark-muted">暂无调用记录</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {logs.total > 50 && (
        <div className="flex justify-center gap-2 mt-4">
          <button onClick={() => setPage(page - 1)} disabled={page <= 1} className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-40">上一页</button>
          <span className="px-3 py-1.5 text-xs text-dark-muted">{page} / {Math.ceil(logs.total / 50)}</span>
          <button onClick={() => setPage(page + 1)} disabled={page >= Math.ceil(logs.total / 50)} className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-40">下一页</button>
        </div>
      )}
    </GlassCard>
  );
}

// ==================== 数据库浏览 ====================

function DatabaseTab() {
  const { t } = useTranslation();
  const [tables, setTables] = useState<any[]>([]);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [tableData, setTableData] = useState<any>(null);
  const [tablePage, setTablePage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [tableLoading, setTableLoading] = useState(false);

  useEffect(() => {
    getAdminTables().then(setTables).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const handleSelectTable = async (tableName: string) => {
    setSelectedTable(tableName);
    setTablePage(1);
    setTableLoading(true);
    try { setTableData(await getAdminTableData(tableName, 1, 50)); } catch {}
    setTableLoading(false);
  };

  const handleTablePage = async (page: number) => {
    if (!selectedTable) return;
    setTablePage(page);
    setTableLoading(true);
    try { setTableData(await getAdminTableData(selectedTable, page, 50)); } catch {}
    setTableLoading(false);
  };

  if (loading) return <SkeletonCard />;

  return (
    <GlassCard title={t("admin.dbBrowser")}>
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-1 space-y-1 max-h-[500px] overflow-y-auto">
          {tables.map((tbl) => (
            <button key={tbl.name} onClick={() => handleSelectTable(tbl.name)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all flex items-center justify-between ${selectedTable === tbl.name ? "bg-primary-500/10 text-primary-400 border border-primary-500/20" : "text-dark-muted hover:bg-white/[0.05]"}`}>
              <span className="font-mono text-xs">{tbl.name}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.05]">{tbl.row_count}</span>
            </button>
          ))}
        </div>
        <div className="lg:col-span-3">
          {!selectedTable ? (
            <div className="flex items-center justify-center h-64"><EmptyState message={t("admin.selectTable")} /></div>
          ) : tableLoading ? <SkeletonCard /> : tableData ? (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-white font-mono">{selectedTable}</h3>
                <span className="text-xs text-dark-muted">共 {tableData.total} 条</span>
              </div>
              <div className="overflow-x-auto max-h-[400px]">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-white/[0.06] sticky top-0 bg-dark-card">
                      {tableData.columns.map((col: string) => (
                        <th key={col} className="text-left py-2 px-2 text-dark-muted font-medium whitespace-nowrap">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tableData.data.map((row: any, i: number) => (
                      <tr key={i} className="border-b border-white/[0.03] hover:bg-white/[0.03]">
                        {tableData.columns.map((col: string) => (
                          <td key={col} className="py-2 px-2 text-dark-text font-mono whitespace-nowrap max-w-[200px] truncate" title={String(row[col] ?? "")}>
                            {row[col] === null ? <span className="text-dark-muted italic">null</span> : String(row[col])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {tableData.total > tableData.page_size && (
                <div className="flex justify-center gap-2 mt-4">
                  <button onClick={() => handleTablePage(tablePage - 1)} disabled={tablePage <= 1} className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-40">上一页</button>
                  <span className="px-3 py-1.5 text-xs text-dark-muted">{tablePage} / {Math.ceil(tableData.total / tableData.page_size)}</span>
                  <button onClick={() => handleTablePage(tablePage + 1)} disabled={tablePage >= Math.ceil(tableData.total / tableData.page_size)} className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-40">下一页</button>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </GlassCard>
  );
}
