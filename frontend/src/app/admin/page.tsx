"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  getAdminStats, getAdminUsers, updateAdminUser, disableAdminUser,
  getAdminTables, getAdminTableData,
  getApiConfigs, saveApiConfig, deleteApiConfig, testApiConfig,
  getUserQuotas, updateUserQuota,
  getApiLogs, getApiStats,
  // 新增
  getAdminStocks, updateAdminStock, deleteAdminStock, adminSyncStocks, adminFetchStock,
  getAdminScores, updateAdminScore,
  getAdminSignals, updateAdminSignal, deleteAdminSignal,
} from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";
import TabSwitch from "@/components/ui/TabSwitch";
import { SkeletonCard } from "@/components/ui/Skeleton";
import EmptyState from "@/components/ui/EmptyState";
import { Shield, Users, Database, BarChart3, AlertCircle, CheckCircle, Key, Activity, Settings, Search, Plus, RefreshCw, Trash2, Edit3, Save, X, Download, Zap } from "lucide-react";

export default function AdminPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (user && user.role !== "admin") {
      router.replace("/");
    }
  }, [user, router]);

  if (user && user.role !== "admin") return null;

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
          { key: "stocks", label: "📈 股票管理" },
          { key: "scores", label: "⭐ 评分管理" },
          { key: "signals", label: "📡 信号管理" },
          { key: "users", label: "👥 用户管理" },
          { key: "database", label: "🗄️ 数据库" },
          { key: "api-config", label: "🔑 API配置" },
        ]}
        active={activeTab}
        onChange={setActiveTab}
      />

      {activeTab === "overview" && <OverviewTab />}
      {activeTab === "stocks" && <StocksTab showMsg={showMsg} />}
      {activeTab === "scores" && <ScoresTab showMsg={showMsg} />}
      {activeTab === "signals" && <SignalsTab showMsg={showMsg} />}
      {activeTab === "users" && <UsersTab showMsg={showMsg} />}
      {activeTab === "database" && <DatabaseTab />}
      {activeTab === "api-config" && <ApiConfigTab showMsg={showMsg} />}

      <div className="disclaimer">{t("app.disclaimer")}</div>
    </div>
  );
}

// ─── 工具函数 ───
const ratingColors: Record<string, string> = {
  BUY: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  ADD: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  WATCH: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  REDUCE: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  SELL: "bg-red-500/15 text-red-400 border-red-500/30",
};

const signalColors: Record<string, string> = {
  BUY: "bg-emerald-500/15 text-emerald-400",
  ADD: "bg-blue-500/15 text-blue-400",
  WATCH: "bg-amber-500/15 text-amber-400",
  REDUCE: "bg-orange-500/15 text-orange-400",
  SELL: "bg-red-500/15 text-red-400",
};

function Badge({ text, className }: { text: string; className?: string }) {
  return <span className={`text-xs px-2 py-0.5 rounded-full border ${className || "bg-white/5 text-dark-muted border-white/10"}`}>{text}</span>;
}

function SearchBar({ value, onChange, placeholder, onSearch }: { value: string; onChange: (v: string) => void; placeholder?: string; onSearch?: () => void }) {
  return (
    <div className="flex gap-2">
      <div className="relative flex-1">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-muted" />
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSearch?.()}
          placeholder={placeholder || "搜索..."}
          className="w-full pl-9 pr-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-dark-text placeholder:text-dark-muted focus:outline-none focus:border-primary-500/40"
        />
      </div>
      {onSearch && (
        <button onClick={onSearch} className="px-4 py-2 bg-primary-500/15 text-primary-400 border border-primary-500/30 rounded-lg text-sm hover:bg-primary-500/25 transition-colors">
          <Search className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}

function Pagination({ page, total, pageSize, onChange }: { page: number; total: number; pageSize: number; onChange: (p: number) => void }) {
  const pages = Math.ceil(total / pageSize);
  if (pages <= 1) return null;
  return (
    <div className="flex items-center justify-between mt-4 pt-4 border-t border-white/[0.06]">
      <span className="text-xs text-dark-muted">共 {total} 条</span>
      <div className="flex items-center gap-2">
        <button onClick={() => onChange(page - 1)} disabled={page <= 1} className="px-3 py-1.5 text-xs rounded-lg bg-white/[0.05] text-dark-muted hover:bg-white/[0.1] disabled:opacity-30 transition-colors">上一页</button>
        <span className="text-xs text-dark-muted px-2">{page} / {pages}</span>
        <button onClick={() => onChange(page + 1)} disabled={page >= pages} className="px-3 py-1.5 text-xs rounded-lg bg-white/[0.05] text-dark-muted hover:bg-white/[0.1] disabled:opacity-30 transition-colors">下一页</button>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════
// 系统概览
// ══════════════════════════════════════════════════════════

function OverviewTab() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAdminStats().then(setStats).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <SkeletonCard />;

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {stats && [
        { label: "股票总数", value: stats.total_stocks, icon: <BarChart3 className="w-5 h-5" />, color: "text-primary-400" },
        { label: "信号总数", value: stats.total_signals, icon: <Zap className="w-5 h-5" />, color: "text-emerald-400" },
        { label: "用户总数", value: stats.total_users, icon: <Users className="w-5 h-5" />, color: "text-blue-400" },
        { label: "报告总数", value: stats.total_reports, icon: <Activity className="w-5 h-5" />, color: "text-amber-400" },
        { label: "数据库大小", value: stats.db_size, icon: <Database className="w-5 h-5" />, color: "text-purple-400" },
        { label: "券商研报", value: stats.total_research_reports, icon: <Key className="w-5 h-5" />, color: "text-cyan-400" },
      ].map((m) => (
        <GlassCard key={m.label} className="text-center">
          <div className={`${m.color} mb-2 flex justify-center`}>{m.icon}</div>
          <p className="text-2xl font-bold text-white font-mono">{typeof m.value === "number" ? m.value.toLocaleString() : m.value}</p>
          <p className="text-xs text-dark-muted mt-1">{m.label}</p>
        </GlassCard>
      ))}
    </div>
  );
}

// ══════════════════════════════════════════════════════════
// 股票管理
// ══════════════════════════════════════════════════════════

function StocksTab({ showMsg }: { showMsg: (type: "ok" | "err", text: string) => void }) {
  const [stocks, setStocks] = useState<any>({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(1);
  const [market, setMarket] = useState("");
  const [editing, setEditing] = useState<any>(null);
  const [addingSymbol, setAddingSymbol] = useState("");
  const [adding, setAdding] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const fetchStocks = useCallback(() => {
    setLoading(true);
    getAdminStocks({ keyword, market, page, page_size: 50 }).then(setStocks).catch(() => {}).finally(() => setLoading(false));
  }, [keyword, market, page]);

  useEffect(() => { fetchStocks(); }, [fetchStocks]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const result = await adminSyncStocks(market || "ALL");
      showMsg("ok", result.message);
      fetchStocks();
    } catch (e: any) { showMsg("err", e.message || "同步失败"); }
    setSyncing(false);
  };

  const handleAdd = async () => {
    if (!addingSymbol.trim()) return;
    setAdding(true);
    try {
      const result = await adminFetchStock(addingSymbol.trim());
      showMsg("ok", `已添加 ${addingSymbol}: ${result.steps?.join(", ")}`);
      setAddingSymbol("");
      fetchStocks();
    } catch (e: any) { showMsg("err", e.message || "添加失败"); }
    setAdding(false);
  };

  const handleSave = async (stock: any) => {
    try {
      await updateAdminStock(stock.id, { name: stock.name, industry: stock.industry, status: stock.status });
      showMsg("ok", `${stock.symbol} 已更新`);
      setEditing(null);
      fetchStocks();
    } catch (e: any) { showMsg("err", e.message || "更新失败"); }
  };

  const handleDelete = async (stock: any) => {
    if (!confirm(`确认删除 ${stock.symbol} ${stock.name}？\n将同时删除关联的行情、财务、评分、信号数据。`)) return;
    try {
      await deleteAdminStock(stock.id);
      showMsg("ok", `${stock.symbol} 已删除`);
      fetchStocks();
    } catch (e: any) { showMsg("err", e.message || "删除失败"); }
  };

  return (
    <div className="space-y-4">
      {/* 操作栏 */}
      <GlassCard>
        <div className="flex flex-wrap gap-3 items-center">
          <div className="flex-1 min-w-[200px]">
            <SearchBar value={keyword} onChange={setKeyword} placeholder="搜索股票代码或名称..." onSearch={() => { setPage(1); fetchStocks(); }} />
          </div>
          <select value={market} onChange={(e) => { setMarket(e.target.value); setPage(1); }} className="px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-dark-text">
            <option value="">全部市场</option>
            <option value="A_SHARE">A股</option>
            <option value="HK">港股</option>
          </select>
          <button onClick={handleSync} disabled={syncing} className="flex items-center gap-1.5 px-4 py-2 bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 rounded-lg text-sm hover:bg-emerald-500/25 disabled:opacity-50 transition-colors">
            <Download className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
            {syncing ? "同步中..." : "同步全部"}
          </button>
        </div>
        <div className="flex gap-2 mt-3">
          <input value={addingSymbol} onChange={(e) => setAddingSymbol(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleAdd()} placeholder="输入股票代码，如 600519" className="flex-1 max-w-xs px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-dark-text placeholder:text-dark-muted" />
          <button onClick={handleAdd} disabled={adding || !addingSymbol.trim()} className="flex items-center gap-1.5 px-4 py-2 bg-primary-500/15 text-primary-400 border border-primary-500/30 rounded-lg text-sm hover:bg-primary-500/25 disabled:opacity-50 transition-colors">
            <Plus className="w-4 h-4" />
            {adding ? "获取中..." : "添加+获取数据"}
          </button>
        </div>
      </GlassCard>

      {/* 股票列表 */}
      <GlassCard>
        {loading ? <SkeletonCard /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  {["代码", "名称", "市场", "行业", "状态", "操作"].map((h) => (
                    <th key={h} className="text-left py-3 px-3 text-dark-muted font-medium text-xs">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {stocks.items?.map((s: any) => (
                  <tr key={s.id} className="border-b border-white/[0.03] hover:bg-white/[0.03]">
                    <td className="py-2.5 px-3 font-mono text-xs text-primary-400">{s.symbol}</td>
                    <td className="py-2.5 px-3">
                      {editing?.id === s.id ? (
                        <input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} className="w-full px-2 py-1 bg-white/[0.06] border border-primary-500/30 rounded text-xs text-dark-text" />
                      ) : (
                        <span className="text-dark-text">{s.name}</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3"><Badge text={s.market === "A_SHARE" ? "A股" : "港股"} /></td>
                    <td className="py-2.5 px-3 text-xs text-dark-muted">{s.industry || "-"}</td>
                    <td className="py-2.5 px-3">
                      {editing?.id === s.id ? (
                        <select value={editing.status} onChange={(e) => setEditing({ ...editing, status: e.target.value })} className="px-2 py-1 bg-white/[0.06] border border-primary-500/30 rounded text-xs text-dark-text">
                          <option value="ACTIVE">ACTIVE</option>
                          <option value="DELISTED">DELISTED</option>
                          <option value="SUSPENDED">SUSPENDED</option>
                        </select>
                      ) : (
                        <Badge text={s.status} className={s.status === "ACTIVE" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-red-500/10 text-red-400 border-red-500/20"} />
                      )}
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="flex gap-1">
                        {editing?.id === s.id ? (
                          <>
                            <button onClick={() => handleSave(editing)} className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"><Save className="w-3.5 h-3.5" /></button>
                            <button onClick={() => setEditing(null)} className="p-1.5 rounded-lg bg-white/[0.05] text-dark-muted hover:bg-white/[0.1] transition-colors"><X className="w-3.5 h-3.5" /></button>
                          </>
                        ) : (
                          <>
                            <button onClick={() => setEditing({ ...s })} className="p-1.5 rounded-lg bg-white/[0.05] text-dark-muted hover:bg-white/[0.1] transition-colors" title="编辑"><Edit3 className="w-3.5 h-3.5" /></button>
                            <button onClick={() => handleDelete(s)} className="p-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors" title="删除"><Trash2 className="w-3.5 h-3.5" /></button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {(!stocks.items || stocks.items.length === 0) && (
                  <tr><td colSpan={6} className="py-12 text-center"><EmptyState message="暂无股票数据，点击「同步全部」或「添加」开始" /></td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
        <Pagination page={page} total={stocks.total} pageSize={50} onChange={setPage} />
      </GlassCard>
    </div>
  );
}

// ══════════════════════════════════════════════════════════
// 评分管理
// ══════════════════════════════════════════════════════════

function ScoresTab({ showMsg }: { showMsg: (type: "ok" | "err", text: string) => void }) {
  const [scores, setScores] = useState<any>({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState("");
  const [rating, setRating] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<any>(null);

  const fetchScores = useCallback(() => {
    setLoading(true);
    getAdminScores({ keyword, rating, page, page_size: 50 }).then(setScores).catch(() => {}).finally(() => setLoading(false));
  }, [keyword, rating, page]);

  useEffect(() => { fetchScores(); }, [fetchScores]);

  const handleSave = async () => {
    if (!editing) return;
    try {
      const result = await updateAdminScore(editing.id, {
        quality_score: editing.quality_score,
        valuation_score: editing.valuation_score,
        growth_score: editing.growth_score,
        trend_score: editing.trend_score,
        risk_score: editing.risk_score,
        rating: editing.rating,
      });
      showMsg("ok", `评分已更新，总分: ${result.total_score}`);
      setEditing(null);
      fetchScores();
    } catch (e: any) { showMsg("err", e.message || "更新失败"); }
  };

  return (
    <div className="space-y-4">
      <GlassCard>
        <div className="flex flex-wrap gap-3 items-center">
          <div className="flex-1 min-w-[200px]">
            <SearchBar value={keyword} onChange={setKeyword} placeholder="搜索股票代码或名称..." onSearch={() => { setPage(1); fetchScores(); }} />
          </div>
          <select value={rating} onChange={(e) => { setRating(e.target.value); setPage(1); }} className="px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-dark-text">
            <option value="">全部评级</option>
            {["BUY", "ADD", "WATCH", "REDUCE", "SELL"].map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
      </GlassCard>

      <GlassCard>
        {loading ? <SkeletonCard /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  {["代码", "名称", "总分", "质量", "估值", "成长", "趋势", "风险", "评级", "日期", "操作"].map((h) => (
                    <th key={h} className="text-left py-3 px-2 text-dark-muted font-medium text-xs whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {scores.items?.map((s: any) => {
                  const isEditing = editing?.id === s.id;
                  return (
                    <tr key={s.id} className={`border-b border-white/[0.03] ${isEditing ? "bg-primary-500/[0.05]" : "hover:bg-white/[0.03]"}`}>
                      <td className="py-2.5 px-2 font-mono text-xs text-primary-400">{s.symbol}</td>
                      <td className="py-2.5 px-2 text-dark-text text-xs">{s.name}</td>
                      <td className="py-2.5 px-2 font-mono font-bold text-white">{isEditing ? "—" : s.total_score}</td>
                      {["quality_score", "valuation_score", "growth_score", "trend_score", "risk_score"].map((field) => (
                        <td key={field} className="py-2.5 px-2 font-mono text-xs">
                          {isEditing ? (
                            <input type="number" step="0.1" value={editing[field]} onChange={(e) => setEditing({ ...editing, [field]: parseFloat(e.target.value) || 0 })} className="w-16 px-1.5 py-1 bg-white/[0.06] border border-primary-500/30 rounded text-xs text-dark-text font-mono" />
                          ) : (
                            <span className="text-dark-text">{s[field]}</span>
                          )}
                        </td>
                      ))}
                      <td className="py-2.5 px-2">
                        {isEditing ? (
                          <select value={editing.rating} onChange={(e) => setEditing({ ...editing, rating: e.target.value })} className="px-1.5 py-1 bg-white/[0.06] border border-primary-500/30 rounded text-xs">
                            {["BUY", "ADD", "WATCH", "REDUCE", "SELL"].map((r) => <option key={r} value={r}>{r}</option>)}
                          </select>
                        ) : (
                          <Badge text={s.rating} className={ratingColors[s.rating]} />
                        )}
                      </td>
                      <td className="py-2.5 px-2 text-xs text-dark-muted">{s.score_date}</td>
                      <td className="py-2.5 px-2">
                        <div className="flex gap-1">
                          {isEditing ? (
                            <>
                              <button onClick={handleSave} className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"><Save className="w-3.5 h-3.5" /></button>
                              <button onClick={() => setEditing(null)} className="p-1.5 rounded-lg bg-white/[0.05] text-dark-muted hover:bg-white/[0.1] transition-colors"><X className="w-3.5 h-3.5" /></button>
                            </>
                          ) : (
                            <button onClick={() => setEditing({ ...s })} className="p-1.5 rounded-lg bg-white/[0.05] text-dark-muted hover:bg-white/[0.1] transition-colors" title="编辑评分"><Edit3 className="w-3.5 h-3.5" /></button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <Pagination page={page} total={scores.total} pageSize={50} onChange={setPage} />
      </GlassCard>
    </div>
  );
}

// ══════════════════════════════════════════════════════════
// 信号管理
// ══════════════════════════════════════════════════════════

function SignalsTab({ showMsg }: { showMsg: (type: "ok" | "err", text: string) => void }) {
  const [signals, setSignals] = useState<any>({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState("");
  const [sigType, setSigType] = useState("");
  const [sigStatus, setSigStatus] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<any>(null);

  const fetchSignals = useCallback(() => {
    setLoading(true);
    getAdminSignals({ keyword, signal_type: sigType, status: sigStatus, page, page_size: 50 }).then(setSignals).catch(() => {}).finally(() => setLoading(false));
  }, [keyword, sigType, sigStatus, page]);

  useEffect(() => { fetchSignals(); }, [fetchSignals]);

  const handleSave = async () => {
    if (!editing) return;
    try {
      await updateAdminSignal(editing.id, {
        signal_type: editing.signal_type,
        entry_price: editing.entry_price,
        target_price: editing.target_price,
        stop_loss_price: editing.stop_loss_price,
        status: editing.status,
      });
      showMsg("ok", "信号已更新");
      setEditing(null);
      fetchSignals();
    } catch (e: any) { showMsg("err", e.message || "更新失败"); }
  };

  const handleExpire = async (sig: any) => {
    try {
      await updateAdminSignal(sig.id, { status: "EXPIRED" });
      showMsg("ok", `${sig.signal_type} 信号已作废`);
      fetchSignals();
    } catch (e: any) { showMsg("err", e.message || "操作失败"); }
  };

  const handleDelete = async (sig: any) => {
    if (!confirm(`确认删除 ${sig.symbol} 的 ${sig.signal_type} 信号？`)) return;
    try {
      await deleteAdminSignal(sig.id);
      showMsg("ok", "信号已删除");
      fetchSignals();
    } catch (e: any) { showMsg("err", e.message || "删除失败"); }
  };

  return (
    <div className="space-y-4">
      <GlassCard>
        <div className="flex flex-wrap gap-3 items-center">
          <div className="flex-1 min-w-[200px]">
            <SearchBar value={keyword} onChange={setKeyword} placeholder="搜索股票代码或名称..." onSearch={() => { setPage(1); fetchSignals(); }} />
          </div>
          <select value={sigType} onChange={(e) => { setSigType(e.target.value); setPage(1); }} className="px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-dark-text">
            <option value="">全部类型</option>
            {["BUY", "ADD", "WATCH", "REDUCE", "SELL"].map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <select value={sigStatus} onChange={(e) => { setSigStatus(e.target.value); setPage(1); }} className="px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-dark-text">
            <option value="">全部状态</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="EXPIRED">EXPIRED</option>
            <option value="EXECUTED">EXECUTED</option>
          </select>
        </div>
      </GlassCard>

      <GlassCard>
        {loading ? <SkeletonCard /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  {["代码", "名称", "信号", "入场价", "目标价", "止损价", "状态", "日期", "操作"].map((h) => (
                    <th key={h} className="text-left py-3 px-2 text-dark-muted font-medium text-xs whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {signals.items?.map((s: any) => {
                  const isEditing = editing?.id === s.id;
                  return (
                    <tr key={s.id} className={`border-b border-white/[0.03] ${isEditing ? "bg-primary-500/[0.05]" : "hover:bg-white/[0.03]"}`}>
                      <td className="py-2.5 px-2 font-mono text-xs text-primary-400">{s.symbol}</td>
                      <td className="py-2.5 px-2 text-dark-text text-xs">{s.name}</td>
                      <td className="py-2.5 px-2">
                        {isEditing ? (
                          <select value={editing.signal_type} onChange={(e) => setEditing({ ...editing, signal_type: e.target.value })} className="px-1.5 py-1 bg-white/[0.06] border border-primary-500/30 rounded text-xs">
                            {["BUY", "ADD", "WATCH", "REDUCE", "SELL"].map((r) => <option key={r} value={r}>{r}</option>)}
                          </select>
                        ) : (
                          <Badge text={s.signal_type} className={signalColors[s.signal_type]} />
                        )}
                      </td>
                      {["entry_price", "target_price", "stop_loss_price"].map((field) => (
                        <td key={field} className="py-2.5 px-2 font-mono text-xs">
                          {isEditing ? (
                            <input type="number" step="0.01" value={editing[field] || ""} onChange={(e) => setEditing({ ...editing, [field]: parseFloat(e.target.value) || 0 })} className="w-20 px-1.5 py-1 bg-white/[0.06] border border-primary-500/30 rounded text-xs text-dark-text font-mono" />
                          ) : (
                            <span className="text-dark-text">{s[field] || "-"}</span>
                          )}
                        </td>
                      ))}
                      <td className="py-2.5 px-2">
                        {isEditing ? (
                          <select value={editing.status} onChange={(e) => setEditing({ ...editing, status: e.target.value })} className="px-1.5 py-1 bg-white/[0.06] border border-primary-500/30 rounded text-xs">
                            {["ACTIVE", "EXPIRED", "EXECUTED"].map((r) => <option key={r} value={r}>{r}</option>)}
                          </select>
                        ) : (
                          <Badge text={s.status} className={s.status === "ACTIVE" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-dark-muted/10 text-dark-muted border-white/10"} />
                        )}
                      </td>
                      <td className="py-2.5 px-2 text-xs text-dark-muted">{s.signal_date}</td>
                      <td className="py-2.5 px-2">
                        <div className="flex gap-1">
                          {isEditing ? (
                            <>
                              <button onClick={handleSave} className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"><Save className="w-3.5 h-3.5" /></button>
                              <button onClick={() => setEditing(null)} className="p-1.5 rounded-lg bg-white/[0.05] text-dark-muted hover:bg-white/[0.1] transition-colors"><X className="w-3.5 h-3.5" /></button>
                            </>
                          ) : (
                            <>
                              <button onClick={() => setEditing({ ...s })} className="p-1.5 rounded-lg bg-white/[0.05] text-dark-muted hover:bg-white/[0.1] transition-colors" title="编辑"><Edit3 className="w-3.5 h-3.5" /></button>
                              {s.status === "ACTIVE" && <button onClick={() => handleExpire(s)} className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition-colors" title="作废"><RefreshCw className="w-3.5 h-3.5" /></button>}
                              <button onClick={() => handleDelete(s)} className="p-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors" title="删除"><Trash2 className="w-3.5 h-3.5" /></button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <Pagination page={page} total={signals.total} pageSize={50} onChange={setPage} />
      </GlassCard>
    </div>
  );
}

// ══════════════════════════════════════════════════════════
// 用户管理
// ══════════════════════════════════════════════════════════

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
                  <Badge text={u.role} className={u.role === "admin" ? "bg-purple-500/10 text-purple-400 border-purple-500/20" : "bg-blue-500/10 text-blue-400 border-blue-500/20"} />
                </td>
                <td className="py-3 px-3">
                  <Badge text={u.is_active ? "正常" : "禁用"} className={u.is_active ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-red-500/10 text-red-400 border-red-500/20"} />
                </td>
                <td className="py-3 px-3 text-xs text-dark-muted">{u.created_at?.slice(0, 19)}</td>
                <td className="py-3 px-3">
                  <div className="flex gap-1">
                    <button onClick={() => handleRoleToggle(u)} className="text-xs px-2 py-1 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-dark-muted hover:text-white transition-colors">
                      {u.role === "admin" ? "设为用户" : "设为管理员"}
                    </button>
                    <button onClick={() => handleActiveToggle(u)} className={`text-xs px-2 py-1 rounded-lg transition-colors ${u.is_active ? "bg-red-500/10 text-red-400 hover:bg-red-500/20" : "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"}`}>
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

// ══════════════════════════════════════════════════════════
// 数据库浏览
// ══════════════════════════════════════════════════════════

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
              <Pagination page={tablePage} total={tableData.total} pageSize={50} onChange={handleTablePage} />
            </div>
          ) : null}
        </div>
      </div>
    </GlassCard>
  );
}

// ══════════════════════════════════════════════════════════
// API配置
// ══════════════════════════════════════════════════════════

function ApiConfigTab({ showMsg }: { showMsg: (type: "ok" | "err", text: string) => void }) {
  const [configs, setConfigs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<any>(null);
  const [testing, setTesting] = useState<number | null>(null);

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
                {["供应商", "显示名称", "API密钥", "状态", "每日限额", "操作"].map((h) => (
                  <th key={h} className="text-left py-3 px-3 text-dark-muted font-medium text-xs">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {configs.map((c) => (
                <tr key={c.id} className="border-b border-white/[0.03] hover:bg-white/[0.03]">
                  <td className="py-2.5 px-3 font-mono text-xs text-primary-400">{c.provider}</td>
                  <td className="py-2.5 px-3 text-dark-text">{c.display_name}</td>
                  <td className="py-2.5 px-3 font-mono text-xs text-dark-muted">{c.api_key || "未配置"}</td>
                  <td className="py-2.5 px-3">
                    <Badge text={c.is_enabled ? "启用" : "禁用"} className={c.is_enabled ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-red-500/10 text-red-400 border-red-500/20"} />
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono text-dark-text">{c.daily_limit}</td>
                  <td className="py-2.5 px-3">
                    <div className="flex gap-1">
                      <button onClick={() => setEditing(c)} className="text-xs px-2 py-1 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-dark-muted">编辑</button>
                      <button onClick={() => handleTest(c.id)} disabled={testing === c.id} className="text-xs px-2 py-1 rounded-lg bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 disabled:opacity-50">
                        {testing === c.id ? "..." : "测试"}
                      </button>
                      <button onClick={() => handleDelete(c.id, c.provider)} className="text-xs px-2 py-1 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20">删除</button>
                    </div>
                  </td>
                </tr>
              ))}
              {configs.length === 0 && <tr><td colSpan={6} className="py-8 text-center text-dark-muted">暂无配置</td></tr>}
            </tbody>
          </table>
        </div>
      </GlassCard>

      <GlassCard title={editing ? `编辑 ${editing.provider}` : "添加 API 配置"}>
        <ApiConfigForm initial={editing} onSave={handleSave} onCancel={() => setEditing(null)} />
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
        <label className="text-xs text-dark-muted">基础URL</label>
        <input value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://api.example.com" className="w-full mt-1" />
      </div>
      <div>
        <label className="text-xs text-dark-muted">每日限额</label>
        <input type="number" value={form.daily_limit} onChange={(e) => setForm({ ...form, daily_limit: parseInt(e.target.value) || 0 })} className="w-full mt-1" />
      </div>
      <div className="flex items-end gap-3 col-span-2">
        <label className="flex items-center gap-2 text-sm text-dark-text">
          <input type="checkbox" checked={form.is_enabled} onChange={(e) => setForm({ ...form, is_enabled: e.target.checked })} />
          启用
        </label>
        <button onClick={() => onSave(form)} className="px-4 py-2 bg-primary-500/15 text-primary-400 border border-primary-500/30 rounded-lg text-sm hover:bg-primary-500/25 transition-colors">保存</button>
        {onCancel && <button onClick={onCancel} className="px-4 py-2 bg-white/[0.05] text-dark-muted border border-white/[0.08] rounded-lg text-sm hover:bg-white/[0.1] transition-colors">取消</button>}
      </div>
    </div>
  );
}
