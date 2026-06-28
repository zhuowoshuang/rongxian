"use client";

import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle, Database, Mail, MessageSquare } from "lucide-react";

import GlassCard from "@/components/ui/GlassCard";
import DataStatusBadge from "@/components/ui/DataStatusBadge";
import SimulatedDataNotice from "@/components/ui/SimulatedDataNotice";
import { getNotificationConfig, getRuntimeInfo, getStockCount, syncStocks, testNotification, updateNotificationConfig } from "@/lib/api";
import { dataModeLabel, runtimeStatusLabel } from "@/lib/utils";
import type { RuntimeInfo } from "@/types";

export default function SettingsPage() {
  const [config, setConfig] = useState({
    email_smtp_host: "",
    email_smtp_port: "465",
    email_sender: "",
    email_password: "",
    email_recipient: "",
    feishu_webhook: "",
    feishu_enabled: "false",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [stockCount, setStockCount] = useState<{ total: number; a_share: number; hk: number } | null>(null);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);

  const loadRuntime = () => {
    getStockCount().then(setStockCount).catch(() => {});
    getRuntimeInfo().then(setRuntime).catch(() => {});
  };

  useEffect(() => {
    getNotificationConfig()
      .then((data) => setConfig((prev) => ({ ...prev, ...data })))
      .catch(() => setMsg({ type: "err", text: "系统设置加载失败，请检查后端服务。" }))
      .finally(() => setLoading(false));
    loadRuntime();
  }, []);

  const handleChange = (key: string, value: string) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
    setMsg(null);
  };

  const handleSave = async () => {
    if (config.email_sender && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(config.email_sender)) {
      setMsg({ type: "err", text: "发件邮箱格式不正确。" });
      return;
    }
    if (config.email_recipient && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(config.email_recipient)) {
      setMsg({ type: "err", text: "收件邮箱格式不正确。" });
      return;
    }
    if (config.email_smtp_port && !/^\d+$/.test(config.email_smtp_port)) {
      setMsg({ type: "err", text: "SMTP 端口必须为数字。" });
      return;
    }

    setSaving(true);
    setMsg(null);
    try {
      const response = await updateNotificationConfig(config);
      setMsg({ type: "ok", text: response.message || "设置已保存。" });
      loadRuntime();
    } catch (error: any) {
      setMsg({ type: "err", text: error.message || "保存失败，请稍后重试。" });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async (type: "email" | "feishu") => {
    setTesting(type);
    setMsg(null);
    try {
      const response = await testNotification(type);
      setMsg({ type: "ok", text: response.message || "测试发送成功。" });
    } catch (error: any) {
      setMsg({ type: "err", text: error.message || "测试发送失败，请检查配置。" });
    } finally {
      setTesting(null);
    }
  };

  const handleSyncStocks = async (market: string) => {
    setSyncing(true);
    setMsg(null);
    try {
      const response = await syncStocks(market);
      setMsg({ type: "ok", text: response.message });
      loadRuntime();
    } catch (error: any) {
      setMsg({ type: "err", text: error.message || "股票同步失败。" });
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center p-6">
        <div className="text-sm text-dark-muted">正在加载系统设置...</div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[960px] space-y-6 p-6" style={{ background: "var(--bg-page)" }}>
      <h1 className="flex items-center gap-2 text-h1">
        <span className="h-6 w-1 rounded-full bg-primary-500" />
        系统设置
      </h1>

      {msg && (
        <div
          className={`flex items-center gap-2 rounded-xl border px-4 py-3 text-sm ${
            msg.type === "ok" ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-400" : "border-red-500/20 bg-red-500/10 text-red-400"
          }`}
        >
          {msg.type === "ok" ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
          {msg.text}
        </div>
      )}

      <GlassCard title="系统健康与数据口径" className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <DataStatusBadge label={`数据库：${runtimeStatusLabel(runtime?.database)}`} tone={runtime?.database === "ok" ? "live" : "warning"} />
          <DataStatusBadge label={`Redis 状态：${runtimeStatusLabel(runtime?.redis)}`} tone={runtime?.redis === "ok" ? "live" : "warning"} />
          <DataStatusBadge label={`数据模式：${dataModeLabel(runtime?.data_mode || runtime?.provider_mode)}`} tone={runtime?.provider_mode === "mock" ? "simulated" : "database"} />
          <DataStatusBadge label={`数据源选择方式：${runtimeStatusLabel(runtime?.provider)}`} tone="database" />
          <DataStatusBadge label={`驾驶舱缓存：${runtimeStatusLabel(runtime?.cache_mode)}`} tone={runtime?.cache_mode === "memory" ? "simulated" : "database"} />
          <DataStatusBadge label={`API 配置状态：${runtime ? `${runtime.api_configured.enabled}/${runtime.api_configured.total}` : "待核验"}`} tone="database" />
          {runtime?.security?.default_password_warning ? <DataStatusBadge label="默认密码风险" tone="warning" /> : <DataStatusBadge label="默认密码未告警" tone="live" />}
        </div>

        <div className="grid gap-3 text-sm text-dark-text md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">SQLite 数据库大小：{runtime?.db_size || "待核验"}</div>
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">运行环境：{runtimeStatusLabel(runtime?.app_env)}</div>
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">股票数量：{runtime?.counts?.stocks ?? 0}</div>
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">信号数量：{runtime?.counts?.signals ?? 0}</div>
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">报告数量：{runtime?.counts?.reports ?? 0}</div>
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">研报数量：{runtime?.counts?.research_reports ?? 0}</div>
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">最新行情：{runtime?.latest_updates?.prices || "待核验"}</div>
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">最新评分：{runtime?.latest_updates?.scores || "待核验"}</div>
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">最新信号：{runtime?.latest_updates?.signals || "待核验"}</div>
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">最新报告：{runtime?.latest_updates?.reports || "待核验"}</div>
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">最新研报：{runtime?.latest_updates?.research_reports || "待核验"}</div>
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">最近错误：{runtime?.latest_error?.called_at || "暂无记录"}</div>
        </div>

        <SimulatedDataNotice
          title="设置页说明"
          badges={[
            { label: `数据模式：${dataModeLabel(runtime?.data_mode || runtime?.provider_mode)}`, tone: runtime?.provider_mode === "mock" ? "simulated" : "live" },
            { label: `数据库路径：${runtime?.db_path || "已隐藏或待核验"}`, tone: "pending" },
          ]}
          lines={[
            "此页面展示的是当前运行实例的真实配置状态，不展示 API Key 和密码原文。",
            "当 Redis 不可用时，Dashboard 会退回进程内演示缓存，属于非实时聚合结果。",
          ]}
        />
      </GlassCard>

      <GlassCard title="股票数据管理" className="space-y-5">
        <p className="text-xs text-dark-muted">可从真实数据源同步股票基础信息，用于搜索、评分、信号和报告链路。</p>
        {stockCount && (
          <div className="grid grid-cols-3 gap-4">
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4 text-center">
              <div className="font-mono text-2xl font-bold text-primary-400">{stockCount.a_share.toLocaleString()}</div>
              <div className="mt-1 text-xs text-dark-muted">A股</div>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4 text-center">
              <div className="font-mono text-2xl font-bold text-emerald-400">{stockCount.hk.toLocaleString()}</div>
              <div className="mt-1 text-xs text-dark-muted">港股</div>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4 text-center">
              <div className="font-mono text-2xl font-bold text-white">{stockCount.total.toLocaleString()}</div>
              <div className="mt-1 text-xs text-dark-muted">总计</div>
            </div>
          </div>
        )}
        <div className="flex flex-wrap gap-3">
          <button onClick={() => handleSyncStocks("ALL")} disabled={syncing} className="btn-primary px-5 py-2.5 text-sm disabled:opacity-50">
            <Database className="mr-1.5 inline h-4 w-4" />
            {syncing ? "同步中..." : "同步全部"}
          </button>
          <button onClick={() => handleSyncStocks("A_SHARE")} disabled={syncing} className="btn-secondary px-4 py-2.5 text-sm disabled:opacity-50">
            仅同步 A股
          </button>
          <button onClick={() => handleSyncStocks("HK")} disabled={syncing} className="btn-secondary px-4 py-2.5 text-sm disabled:opacity-50">
            仅同步 港股
          </button>
        </div>
        <p className="text-xs text-dark-muted">同步通常需要 10-30 秒，期间不会删除已有真实数据。</p>
      </GlassCard>

      <GlassCard className="space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
              <Mail className="h-4 w-4 text-primary-400" /> 邮件通知
            </h3>
            <p className="mt-1 text-xs text-dark-muted">配置邮件通道，用于向内部研究人员发送日报或提醒。</p>
          </div>
          <button onClick={() => handleTest("email")} disabled={testing === "email"} className="btn-secondary px-4 py-1.5 text-xs disabled:opacity-50">
            {testing === "email" ? "发送中..." : "发送测试邮件"}
          </button>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-medium text-dark-muted">SMTP 服务器</label>
            <input type="text" value={config.email_smtp_host} onChange={(e) => handleChange("email_smtp_host", e.target.value)} className="mt-1 w-full" />
          </div>
          <div>
            <label className="text-xs font-medium text-dark-muted">SMTP 端口</label>
            <input type="text" value={config.email_smtp_port} onChange={(e) => handleChange("email_smtp_port", e.target.value)} className="mt-1 w-full" />
          </div>
        </div>
        <div>
          <label className="text-xs font-medium text-dark-muted">发件邮箱</label>
          <input type="email" value={config.email_sender} onChange={(e) => handleChange("email_sender", e.target.value)} placeholder="your@qq.com" className="mt-1 w-full" />
        </div>
        <div>
          <label className="text-xs font-medium text-dark-muted">邮箱授权码</label>
          <input type="password" value={config.email_password} onChange={(e) => handleChange("email_password", e.target.value)} placeholder="填写邮箱授权码，而非登录密码" className="mt-1 w-full" />
          <p className="mt-1 text-xs text-dark-muted">例如 QQ 邮箱可在设置 - 账户 - POP3/SMTP 服务中生成授权码。</p>
        </div>
        <div>
          <label className="text-xs font-medium text-dark-muted">收件邮箱</label>
          <input type="email" value={config.email_recipient} onChange={(e) => handleChange("email_recipient", e.target.value)} placeholder="收件邮箱地址" className="mt-1 w-full" />
        </div>
      </GlassCard>

      <GlassCard className="space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
              <MessageSquare className="h-4 w-4 text-primary-400" /> 飞书 Webhook 通知
            </h3>
            <p className="mt-1 text-xs text-dark-muted">用于向内部群组发送研究提醒，不涉及交易执行。</p>
          </div>
          <button onClick={() => handleTest("feishu")} disabled={testing === "feishu"} className="btn-secondary px-4 py-1.5 text-xs disabled:opacity-50">
            {testing === "feishu" ? "发送中..." : "发送测试消息"}
          </button>
        </div>
        <div>
          <label className="text-xs font-medium text-dark-muted">Webhook URL</label>
          <input
            type="text"
            value={config.feishu_webhook}
            onChange={(e) => handleChange("feishu_webhook", e.target.value)}
            placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
            className="mt-1 w-full"
          />
        </div>
        <div className="flex items-center gap-3">
          <label className="text-xs font-medium text-dark-muted">启用飞书通知</label>
          <button
            onClick={() => handleChange("feishu_enabled", config.feishu_enabled === "true" ? "false" : "true")}
            className={`relative h-6 w-11 rounded-full transition-colors ${config.feishu_enabled === "true" ? "bg-primary-500" : "bg-white/10"}`}
          >
            <span className={`absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${config.feishu_enabled === "true" ? "translate-x-5" : ""}`} />
          </button>
        </div>
      </GlassCard>

      <button onClick={handleSave} disabled={saving} className="btn-primary w-full py-2.5 text-sm disabled:opacity-50">
        {saving ? "保存中..." : "保存设置"}
      </button>

      <GlassCard title="推送说明" className="space-y-3">
        <div className="space-y-2 text-xs text-dark-muted">
          <p>- 推送能力用于研究结果通知和内部协作，不代表实盘交易能力。</p>
          <p>- 修改设置后需要点击“保存设置”，再使用测试按钮验证通道是否连通。</p>
          <p>- 页面不会展示 API Key、邮箱密码或飞书密钥原文。</p>
        </div>
      </GlassCard>

      <div className="disclaimer">本系统仅用于研究和辅助分析，不构成任何投资建议。</div>
    </div>
  );
}
