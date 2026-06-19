"use client";

import { useState, useEffect } from "react";
import { getNotificationConfig, updateNotificationConfig, testNotification, syncStocks, getStockCount } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";
import { Settings, Mail, MessageSquare, Database, AlertCircle, CheckCircle } from "lucide-react";

export default function SettingsPage() {
  const { t } = useTranslation();
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
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const [stockCount, setStockCount] = useState<{ total: number; a_share: number; hk: number } | null>(null);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    getNotificationConfig().then((data) => setConfig((prev) => ({ ...prev, ...data }))).catch(() => {}).finally(() => setLoading(false));
    getStockCount().then(setStockCount).catch(() => {});
  }, []);

  const handleChange = (key: string, value: string) => { setConfig((prev) => ({ ...prev, [key]: value })); setMsg(null); };

  const handleSave = async () => {
    // H-09: 表单校验
    if (config.email_sender && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(config.email_sender)) {
      setMsg({ type: "err", text: "发件邮箱格式不正确" }); return;
    }
    if (config.email_recipient && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(config.email_recipient)) {
      setMsg({ type: "err", text: "收件邮箱格式不正确" }); return;
    }
    if (config.email_smtp_port && !/^\d+$/.test(config.email_smtp_port)) {
      setMsg({ type: "err", text: "SMTP 端口必须为数字" }); return;
    }
    setSaving(true); setMsg(null);
    try { const res = await updateNotificationConfig(config); setMsg({ type: "ok", text: res.message || t("settings.saveSuccess") }); }
    catch (e: any) { setMsg({ type: "err", text: e.message || t("settings.saveFailed") }); }
    finally { setSaving(false); }
  };

  const handleTest = async (type: "email" | "feishu") => {
    setTesting(type); setMsg(null);
    try { const res = await testNotification(type); setMsg({ type: "ok", text: res.message || t("settings.testSuccess") }); }
    catch (e: any) { setMsg({ type: "err", text: e.message || t("settings.testFailed") }); }
    finally { setTesting(null); }
  };

  const handleSyncStocks = async (market: string) => {
    setSyncing(true); setMsg(null);
    try { const res = await syncStocks(market); setMsg({ type: "ok", text: res.message }); const counts = await getStockCount(); setStockCount(counts); }
    catch (e: any) { setMsg({ type: "err", text: e.message || "同步失败" }); }
    finally { setSyncing(false); }
  };

  if (loading) {
    return <div className="p-6 flex items-center justify-center h-64"><div className="text-dark-muted text-sm">{t("common.loading")}</div></div>;
  }

  return (
    <div className="p-6 space-y-6 max-w-[800px] mx-auto">
      <h1 className="text-xl font-bold text-white flex items-center gap-2">
        <span className="w-1 h-6 bg-primary-500 rounded-full" />
        {t("settings.title")}
      </h1>

      {msg && (
        <div className={`px-4 py-3 rounded-xl text-sm flex items-center gap-2 ${
          msg.type === "ok" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"
        }`}>
          {msg.type === "ok" ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
          {msg.text}
        </div>
      )}

      <GlassCard title={t("settings.stockData")} className="space-y-5">
        <p className="text-xs text-dark-muted">{t("settings.stockDataDesc")}</p>
        {stockCount && (
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white/[0.03] rounded-xl p-4 text-center border border-white/[0.06]">
              <div className="text-2xl font-bold text-primary-400 font-mono">{stockCount.a_share.toLocaleString()}</div>
              <div className="text-xs text-dark-muted mt-1">{t("market.aShare")}</div>
            </div>
            <div className="bg-white/[0.03] rounded-xl p-4 text-center border border-white/[0.06]">
              <div className="text-2xl font-bold text-emerald-400 font-mono">{stockCount.hk.toLocaleString()}</div>
              <div className="text-xs text-dark-muted mt-1">{t("market.hk")}</div>
            </div>
            <div className="bg-white/[0.03] rounded-xl p-4 text-center border border-white/[0.06]">
              <div className="text-2xl font-bold text-white font-mono">{stockCount.total.toLocaleString()}</div>
              <div className="text-xs text-dark-muted mt-1">{t("common.total")}</div>
            </div>
          </div>
        )}
        <div className="flex gap-3">
          <button onClick={() => handleSyncStocks("ALL")} disabled={syncing} className="btn-primary px-5 py-2.5 text-sm disabled:opacity-50">
            <Database className="w-4 h-4 inline mr-1.5" />{syncing ? t("settings.syncing") : t("settings.syncAll")}
          </button>
          <button onClick={() => handleSyncStocks("A_SHARE")} disabled={syncing} className="btn-secondary px-4 py-2.5 text-sm disabled:opacity-50">{t("settings.syncAShare")}</button>
          <button onClick={() => handleSyncStocks("HK")} disabled={syncing} className="btn-secondary px-4 py-2.5 text-sm disabled:opacity-50">{t("settings.syncHK")}</button>
        </div>
        <p className="text-xs text-dark-muted">{t("settings.syncDesc")}</p>
      </GlassCard>

      <GlassCard className="space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2"><Mail className="w-4 h-4 text-primary-400" /> {t("settings.emailTitle")}</h3>
            <p className="text-xs text-dark-muted mt-1">{t("settings.emailDesc")}</p>
          </div>
          <button onClick={() => handleTest("email")} disabled={testing === "email"} className="btn-secondary px-4 py-1.5 text-xs disabled:opacity-50">
            {testing === "email" ? t("settings.sending") : t("settings.sendTest")}
          </button>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div><label className="text-xs text-dark-muted font-medium">{t("settings.smtpHost")}</label><input type="text" value={config.email_smtp_host} onChange={(e) => handleChange("email_smtp_host", e.target.value)} className="w-full mt-1" /></div>
          <div><label className="text-xs text-dark-muted font-medium">{t("settings.smtpPort")}</label><input type="text" value={config.email_smtp_port} onChange={(e) => handleChange("email_smtp_port", e.target.value)} className="w-full mt-1" /></div>
        </div>
        <div><label className="text-xs text-dark-muted font-medium">{t("settings.sender")}</label><input type="email" value={config.email_sender} onChange={(e) => handleChange("email_sender", e.target.value)} placeholder="your@qq.com" className="w-full mt-1" /></div>
        <div>
          <label className="text-xs text-dark-muted font-medium">{t("settings.authCode")}</label>
          <input type="password" value={config.email_password} onChange={(e) => handleChange("email_password", e.target.value)} placeholder={t("settings.authCodeDesc")} className="w-full mt-1" />
          <p className="text-xs text-dark-muted mt-1">{t("settings.authCodeHelp")}</p>
        </div>
        <div><label className="text-xs text-dark-muted font-medium">{t("settings.recipient")}</label><input type="email" value={config.email_recipient} onChange={(e) => handleChange("email_recipient", e.target.value)} placeholder={t("settings.recipient")} className="w-full mt-1" /></div>
      </GlassCard>

      <GlassCard className="space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2"><MessageSquare className="w-4 h-4 text-primary-400" /> {t("settings.feishuTitle")}</h3>
            <p className="text-xs text-dark-muted mt-1">{t("settings.feishuDesc")}</p>
          </div>
          <button onClick={() => handleTest("feishu")} disabled={testing === "feishu"} className="btn-secondary px-4 py-1.5 text-xs disabled:opacity-50">
            {testing === "feishu" ? t("settings.sending") : t("settings.sendTestMsg")}
          </button>
        </div>
        <div>
          <label className="text-xs text-dark-muted font-medium">{t("settings.webhookUrl")}</label>
          <input type="text" value={config.feishu_webhook} onChange={(e) => handleChange("feishu_webhook", e.target.value)} placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx" className="w-full mt-1" />
        </div>
        <div className="flex items-center gap-3">
          <label className="text-xs text-dark-muted font-medium">{t("settings.feishuEnable")}</label>
          <button onClick={() => handleChange("feishu_enabled", config.feishu_enabled === "true" ? "false" : "true")}
            className={`relative w-11 h-6 rounded-full transition-colors ${config.feishu_enabled === "true" ? "bg-primary-500" : "bg-white/10"}`}>
            <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${config.feishu_enabled === "true" ? "translate-x-5" : ""}`} />
          </button>
        </div>
      </GlassCard>

      <button onClick={handleSave} disabled={saving} className="w-full btn-primary py-2.5 text-sm disabled:opacity-50">
        {saving ? t("settings.saving") : t("settings.saveBtn")}
      </button>

      <GlassCard title={t("settings.pushDesc")} className="space-y-3">
        <div className="text-xs text-dark-muted space-y-2">
          <p>- {t("settings.pushNote1")}</p>
          <p>- {t("settings.pushNote2")}</p>
          <p>- {t("settings.pushNote3")}</p>
          <p>- {t("settings.pushNote4")}</p>
        </div>
      </GlassCard>

      <div className="disclaimer">{t("app.disclaimer")}</div>
    </div>
  );
}
