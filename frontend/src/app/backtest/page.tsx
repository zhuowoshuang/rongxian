"use client";

import { useState, useEffect } from "react";
import { runBacktest, simulatePortfolio, searchStocks } from "@/lib/api";
import type { BacktestResult, SimulateResult, SimulateHolding } from "@/types";
import { formatPercent, getChangeColor } from "@/lib/utils";
import { useTranslation } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";
import TabSwitch from "@/components/ui/TabSwitch";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Legend } from "recharts";

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload?.length) {
    return (
      <div className="bg-dark-card border border-white/10 rounded-lg px-3 py-2 shadow-xl backdrop-blur-xl">
        <p className="text-xs text-dark-muted mb-1">{label}</p>
        {payload.map((p: any, i: number) => (
          <p key={i} className="text-sm" style={{ color: p.color }}>{p.name}: <span className="font-mono font-bold">{typeof p.value === "number" ? p.value.toFixed(2) : p.value}</span></p>
        ))}
      </div>
    );
  }
  return null;
};

export default function BacktestPage() {
  const { t } = useTranslation();
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [params, setParams] = useState({
    strategy: "fundamental_medium_long",
    market: "A_SHARE",
    start_date: "2020-01-01",
    end_date: "2025-12-31",
    rebalance: "monthly",
    initial_capital: 1000000,
  });

  // 模拟买入状态
  const [activeTab, setActiveTab] = useState("backtest");
  const [simResult, setSimResult] = useState<SimulateResult | null>(null);
  const [simLoading, setSimLoading] = useState(false);
  const [holdings, setHoldings] = useState<SimulateHolding[]>([]);
  const [simStockKeyword, setSimStockKeyword] = useState("");
  const [simStockResults, setSimStockResults] = useState<any[]>([]);
  const [showSimStockSearch, setShowSimStockSearch] = useState(false);
  const [newHolding, setNewHolding] = useState<SimulateHolding>({ symbol: "", buy_date: "2024-01-15", shares: 100 });

  useEffect(() => {
    if (simStockKeyword.length < 1) { setSimStockResults([]); return; }
    const timer = setTimeout(() => { searchStocks(simStockKeyword).then((data) => setSimStockResults(data || [])).catch(() => {}); }, 300);
    return () => clearTimeout(timer);
  }, [simStockKeyword]);

  const addHolding = () => {
    if (!newHolding.symbol || !newHolding.buy_date || newHolding.shares <= 0) return;
    setHoldings([...holdings, { ...newHolding }]);
    setNewHolding({ symbol: "", buy_date: "2024-01-15", shares: 100 });
    setSimStockKeyword("");
  };

  const removeHolding = (idx: number) => {
    setHoldings(holdings.filter((_, i) => i !== idx));
  };

  const handleSimulate = async () => {
    if (holdings.length === 0) return;
    setSimLoading(true);
    try {
      const data = await simulatePortfolio(holdings);
      setSimResult(data);
    } catch (e) { console.error(e); }
    setSimLoading(false);
  };

  const handleRun = async () => {
    setLoading(true);
    try { const data = await runBacktest(params); setResult(data); } catch (e) { console.error(e); }
    setLoading(false);
  };

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
      <h1 className="text-xl font-bold text-white flex items-center gap-2">
        <span className="w-1 h-6 bg-primary-500 rounded-full" />
        {t("backtest.title")}
      </h1>

      <TabSwitch
        tabs={[
          { key: "backtest", label: "📊 策略回测" },
          { key: "simulate", label: "🎯 模拟买入" },
        ]}
        active={activeTab}
        onChange={setActiveTab}
        className="w-fit"
      />

      {activeTab === "backtest" && (
        <GlassCard title={t("backtest.strategy")}>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <div>
              <label className="text-xs text-dark-muted">{t("backtest.strategy")}</label>
              <select value={params.strategy} onChange={(e) => setParams({ ...params, strategy: e.target.value })} className="w-full mt-1">
                <option value="fundamental_medium_long">{t("backtest.fundamental")}</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-dark-muted">{t("backtest.market")}</label>
              <select value={params.market} onChange={(e) => setParams({ ...params, market: e.target.value })} className="w-full mt-1">
                <option value="A_SHARE">{t("market.aShare")}</option>
                <option value="HK">{t("market.hk")}</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-dark-muted">{t("backtest.startDate")}</label>
              <input type="date" value={params.start_date} onChange={(e) => setParams({ ...params, start_date: e.target.value })} className="w-full mt-1" />
            </div>
            <div>
              <label className="text-xs text-dark-muted">{t("backtest.endDate")}</label>
              <input type="date" value={params.end_date} onChange={(e) => setParams({ ...params, end_date: e.target.value })} className="w-full mt-1" />
            </div>
            <div>
              <label className="text-xs text-dark-muted">{t("backtest.rebalance")}</label>
              <select value={params.rebalance} onChange={(e) => setParams({ ...params, rebalance: e.target.value })} className="w-full mt-1">
                <option value="monthly">{t("backtest.monthly")}</option>
                <option value="quarterly">{t("backtest.quarterly")}</option>
              </select>
            </div>
            <div className="flex items-end">
              <button onClick={handleRun} disabled={loading} className="w-full btn-primary px-4 py-2 text-sm disabled:opacity-50">
                {loading ? t("backtest.running") : t("backtest.run")}
              </button>
            </div>
          </div>
        </GlassCard>
      )}

      {activeTab === "simulate" && (
        <GlassCard title="模拟买入回测">
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
              <div className="relative">
                <label className="text-xs text-dark-muted">股票代码</label>
                <input
                  type="text"
                  value={newHolding.symbol ? newHolding.symbol : simStockKeyword}
                  onChange={(e) => { setSimStockKeyword(e.target.value); setNewHolding({ ...newHolding, symbol: "" }); setShowSimStockSearch(true); }}
                  onFocus={() => setShowSimStockSearch(true)}
                  placeholder="搜索股票..."
                  className="w-full mt-1"
                />
                {showSimStockSearch && simStockResults.length > 0 && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-dark-card border border-white/[0.08] rounded-lg shadow-lg z-10 max-h-48 overflow-y-auto">
                    {simStockResults.map((s) => (
                      <button key={s.symbol} onClick={() => { setNewHolding({ ...newHolding, symbol: s.symbol }); setSimStockKeyword(""); setShowSimStockSearch(false); setSimStockResults([]); }}
                        className="w-full text-left px-3 py-2 hover:bg-white/[0.05] text-sm flex items-center gap-2 text-dark-text">
                        <span className="font-mono text-primary-400">{s.symbol}</span><span>{s.name}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <label className="text-xs text-dark-muted">买入日期</label>
                <input type="date" value={newHolding.buy_date} onChange={(e) => setNewHolding({ ...newHolding, buy_date: e.target.value })} className="w-full mt-1" />
              </div>
              <div>
                <label className="text-xs text-dark-muted">买入股数</label>
                <input type="number" value={newHolding.shares} onChange={(e) => setNewHolding({ ...newHolding, shares: parseInt(e.target.value) || 0 })} className="w-full mt-1" min={100} step={100} />
              </div>
              <div className="flex gap-2">
                <button onClick={addHolding} disabled={!newHolding.symbol} className="btn-secondary px-4 py-2 text-sm disabled:opacity-50">添加</button>
                <button onClick={handleSimulate} disabled={simLoading || holdings.length === 0} className="btn-primary px-4 py-2 text-sm disabled:opacity-50 flex-1">
                  {simLoading ? "计算中..." : "开始模拟"}
                </button>
              </div>
            </div>

            {holdings.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06]">
                      <th className="text-left py-2 px-3 text-dark-muted text-xs">股票代码</th>
                      <th className="text-left py-2 px-3 text-dark-muted text-xs">买入日期</th>
                      <th className="text-right py-2 px-3 text-dark-muted text-xs">股数</th>
                      <th className="text-right py-2 px-3 text-dark-muted text-xs">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {holdings.map((h, idx) => (
                      <tr key={idx} className="border-b border-white/[0.03]">
                        <td className="py-2 px-3 font-mono text-primary-400">{h.symbol}</td>
                        <td className="py-2 px-3 text-dark-text">{h.buy_date}</td>
                        <td className="py-2 px-3 text-right text-dark-text">{h.shares}</td>
                        <td className="py-2 px-3 text-right">
                          <button onClick={() => removeHolding(idx)} className="text-red-400 hover:text-red-300 text-xs">移除</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </GlassCard>
      )}

      {activeTab === "backtest" && result && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: t("backtest.totalReturn"), value: formatPercent(result.total_return), color: getChangeColor(result.total_return) },
              { label: t("backtest.annualReturn"), value: formatPercent(result.annual_return), color: getChangeColor(result.annual_return) },
              { label: t("backtest.excessReturn"), value: formatPercent(result.excess_return), color: getChangeColor(result.excess_return) },
              { label: t("backtest.maxDrawdown"), value: formatPercent(result.max_drawdown), color: "text-red-400" },
              { label: t("backtest.sharpeRatio"), value: result.sharpe_ratio.toFixed(2), color: result.sharpe_ratio >= 1 ? "text-emerald-400" : "text-amber-400" },
              { label: t("backtest.winRate"), value: `${result.win_rate.toFixed(1)}%`, color: "text-white" },
              { label: t("backtest.totalTrades"), value: String(result.total_trades), color: "text-white" },
              { label: t("backtest.benchmark"), value: formatPercent(result.benchmark_return), color: getChangeColor(result.benchmark_return) },
            ].map((m) => (
              <GlassCard key={m.label} className="text-center">
                <p className="text-xs text-dark-muted">{m.label}</p>
                <p className={`text-2xl font-bold mt-1 font-mono ${m.color}`}>{m.value}</p>
              </GlassCard>
            ))}
          </div>

          <GlassCard title={t("backtest.equityCurve")}>
            <div className="h-[400px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={result.equity_curve}>
                  <CartesianGrid stroke="#1E293B" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94A3B8" }} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ color: "#94A3B8" }} />
                  <Line type="monotone" dataKey="equity" stroke="#6366f1" strokeWidth={2} dot={false} name={t("backtest.strategyEquity")} />
                  <Line type="monotone" dataKey="benchmark" stroke="#94A3B8" strokeWidth={1} dot={false} name={t("backtest.benchmark")} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>

          <GlassCard title={t("backtest.monthlyExcess")}>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={result.monthly_returns.slice(-24)}>
                  <CartesianGrid stroke="#1E293B" />
                  <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#94A3B8" }} />
                  <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="excess_return" fill="#6366f1" name={t("backtest.excessReturnPct")} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>
        </>
      )}

      {/* 模拟买入结果 */}
      {activeTab === "simulate" && simResult && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "总投入", value: `¥${simResult.total_invested.toLocaleString()}`, color: "text-white" },
              { label: "当前市值", value: `¥${simResult.current_value.toLocaleString()}`, color: "text-white" },
              { label: "总收益率", value: formatPercent(simResult.total_return), color: getChangeColor(simResult.total_return) },
              { label: "总盈亏", value: `¥${simResult.total_pnl.toLocaleString()}`, color: getChangeColor(simResult.total_pnl) },
              { label: "基准收益", value: formatPercent(simResult.benchmark_return), color: getChangeColor(simResult.benchmark_return) },
              { label: "超额收益", value: formatPercent(simResult.excess_return), color: getChangeColor(simResult.excess_return) },
            ].map((m) => (
              <GlassCard key={m.label} className="text-center">
                <p className="text-xs text-dark-muted">{m.label}</p>
                <p className={`text-xl font-bold mt-1 font-mono ${m.color}`}>{m.value}</p>
              </GlassCard>
            ))}
          </div>

          {/* 持仓明细 */}
          <GlassCard title="持仓明细">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    {["代码", "名称", "买入日期", "买入价", "股数", "成本", "现价", "市值", "盈亏", "收益率"].map((h) => (
                      <th key={h} className="text-left py-2 px-3 text-dark-muted text-xs">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {simResult.holdings.map((h, idx) => (
                    <tr key={idx} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                      <td className="py-2 px-3 font-mono text-primary-400">{h.symbol}</td>
                      <td className="py-2 px-3 text-dark-text">{h.name}</td>
                      <td className="py-2 px-3 text-dark-muted">{h.buy_date}</td>
                      <td className="py-2 px-3 text-right font-mono text-dark-text">{h.buy_price.toFixed(2)}</td>
                      <td className="py-2 px-3 text-right text-dark-text">{h.shares}</td>
                      <td className="py-2 px-3 text-right font-mono text-dark-text">{h.cost.toLocaleString()}</td>
                      <td className="py-2 px-3 text-right font-mono text-dark-text">{h.current_price.toFixed(2)}</td>
                      <td className="py-2 px-3 text-right font-mono text-dark-text">{h.current_value.toLocaleString()}</td>
                      <td className={`py-2 px-3 text-right font-mono font-bold ${getChangeColor(h.pnl)}`}>{h.pnl >= 0 ? "+" : ""}{h.pnl.toLocaleString()}</td>
                      <td className={`py-2 px-3 text-right font-mono font-bold ${getChangeColor(h.pnl_pct)}`}>{formatPercent(h.pnl_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>

          {/* 模拟权益曲线 */}
          {simResult.equity_curve.length > 0 && (
            <GlassCard title="模拟权益曲线">
              <div className="h-[400px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={simResult.equity_curve}>
                    <CartesianGrid stroke="#1E293B" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94A3B8" }} interval="preserveStartEnd" />
                    <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend wrapperStyle={{ color: "#94A3B8" }} />
                    <Line type="monotone" dataKey="equity" stroke="#6366f1" strokeWidth={2} dot={false} name="组合市值" />
                    <Line type="monotone" dataKey="benchmark" stroke="#94A3B8" strokeWidth={1} dot={false} name="基准" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </GlassCard>
          )}

          {/* 模拟月度超额收益 */}
          {simResult.monthly_returns.length > 0 && (
            <GlassCard title="月度超额收益">
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={simResult.monthly_returns.slice(-24)}>
                    <CartesianGrid stroke="#1E293B" />
                    <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#94A3B8" }} />
                    <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="strategy_return" fill="#6366f1" name="组合收益%" radius={[2, 2, 0, 0]} />
                    <Bar dataKey="benchmark_return" fill="#94A3B8" name="基准收益%" radius={[2, 2, 0, 0]} />
                    <Bar dataKey="excess_return" fill="#10b981" name="超额收益%" radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </GlassCard>
          )}
        </>
      )}

      <div className="disclaimer">{t("app.disclaimer")}</div>
    </div>
  );
}
