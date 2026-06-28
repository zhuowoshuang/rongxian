"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Loader2, Play, Plus, Search, Trash2 } from "lucide-react";

import PageShell from "@/components/layout/PageShell";
import ChartTooltip from "@/components/ui/ChartTooltip";
import EmptyState from "@/components/ui/EmptyState";
import SimulatedDataNotice from "@/components/ui/SimulatedDataNotice";
import { showToast } from "@/components/ui/Toast";
import { getBacktestMeta, getRuntimeInfo, runBacktest, searchStocks, simulatePortfolio } from "@/lib/api";
import {
  formatNumber,
  formatPercent,
  getChangeColor,
  marketLabel,
  sanitizeDisplayText,
} from "@/lib/utils";
import type { BacktestMeta, BacktestResult, RuntimeInfo, SimulateHolding, SimulateResult, StockSearchResult } from "@/types";

type TabKey = "backtest" | "simulate";

const MARKET_OPTIONS = [
  { value: "A_SHARE", label: "A股" },
  { value: "HK", label: "港股" },
];

const REBALANCE_OPTIONS = [
  { value: "monthly", label: "月度" },
  { value: "quarterly", label: "季度" },
];

function ResultCard({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "positive" | "negative" }) {
  const className =
    tone === "positive" ? "text-emerald-600" : tone === "negative" ? "text-red-600" : "text-[var(--text-primary)]";
  return (
    <div className="card text-center">
      <p className="text-xs font-medium text-[var(--text-secondary)]">{label}</p>
      <p className={`mt-2 text-2xl font-bold ${className}`}>{value}</p>
    </div>
  );
}

export default function BacktestPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("backtest");
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [meta, setMeta] = useState<BacktestMeta | null>(null);
  const [metaLoading, setMetaLoading] = useState(true);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [simResult, setSimResult] = useState<SimulateResult | null>(null);
  const [runLoading, setRunLoading] = useState(false);
  const [simLoading, setSimLoading] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [simError, setSimError] = useState<string | null>(null);
  const [searchKeyword, setSearchKeyword] = useState("");
  const [searchResults, setSearchResults] = useState<StockSearchResult[]>([]);
  const [showSearchResults, setShowSearchResults] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  const [params, setParams] = useState({
    strategy: "fundamental_medium_long",
    market: "A_SHARE",
    start_date: "",
    end_date: "",
    rebalance: "monthly",
    initial_capital: 1000000,
  });

  const [newHolding, setNewHolding] = useState<SimulateHolding>({
    symbol: "",
    buy_date: "",
    shares: 100,
  });
  const [holdings, setHoldings] = useState<SimulateHolding[]>([]);

  useEffect(() => {
    getRuntimeInfo().then(setRuntime).catch(() => null);
  }, []);

  useEffect(() => {
    const loadMeta = async () => {
      setMetaLoading(true);
      setMetaError(null);
      try {
        const nextMeta = await getBacktestMeta(params.market);
        setMeta(nextMeta);
        setParams((current) => ({
          ...current,
          start_date: current.start_date || nextMeta.earliest_date || "",
          end_date: current.end_date || nextMeta.latest_date || "",
        }));
        setNewHolding((current) => ({
          ...current,
          buy_date: current.buy_date || nextMeta.latest_date || "",
        }));
      } catch (err: unknown) {
        const message =
          err instanceof Error && err.message.trim() ? err.message : "回测日期范围加载失败，请稍后重试。";
        setMetaError(message);
        setMeta(null);
      } finally {
        setMetaLoading(false);
      }
    };

    void loadMeta();
  }, [params.market]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setShowSearchResults(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (!searchKeyword.trim()) {
      setSearchResults([]);
      return;
    }

    const timer = window.setTimeout(() => {
      searchStocks(searchKeyword)
        .then((items) => {
          setSearchResults(items || []);
          setShowSearchResults(true);
        })
        .catch(() => {
          setSearchResults([]);
          setShowSearchResults(false);
        });
    }, 250);

    return () => window.clearTimeout(timer);
  }, [searchKeyword]);

  const rangeHint = useMemo(() => {
    if (!meta?.earliest_date || !meta?.latest_date) return "当前数据库尚未返回可用日期范围。";
    return `日期范围：${meta.earliest_date} 至 ${meta.latest_date}`;
  }, [meta]);

  const validateBacktest = () => {
    if (!meta) return "当前无法读取回测日期范围。";
    if (!params.start_date || !params.end_date) return "请先选择完整的开始日期和结束日期。";
    if (meta.earliest_date && params.start_date < meta.earliest_date) {
      return `回测开始日期越界，当前最早仅支持 ${meta.earliest_date}。`;
    }
    if (meta.latest_date && params.end_date > meta.latest_date) {
      return `回测结束日期越界，当前最晚仅支持 ${meta.latest_date}。`;
    }
    if (params.start_date >= params.end_date) {
      return "开始日期必须早于结束日期。";
    }
    return null;
  };

  const canRunMessage = validateBacktest();

  const handleRunBacktest = async () => {
    if (canRunMessage) {
      setRunError(canRunMessage);
      showToast("error", canRunMessage);
      return;
    }
    setRunLoading(true);
    setRunError(null);
    try {
      const nextResult = await runBacktest(params);
      setResult(nextResult);
      showToast("success", "回测已完成，可查看历史研究测算结果。");
    } catch (err: unknown) {
      const message = err instanceof Error && err.message.trim() ? err.message : "回测执行失败，请稍后重试。";
      setRunError(message);
      setResult(null);
      showToast("error", message);
    } finally {
      setRunLoading(false);
    }
  };

  const addHoldingError = () => {
    if (!newHolding.symbol) return "请先选择一只股票后再添加持仓。";
    if (!newHolding.buy_date) return "请先选择买入日期。";
    if (!newHolding.shares || newHolding.shares <= 0) return "股数必须大于 0。";
    if (meta?.earliest_date && newHolding.buy_date < meta.earliest_date) {
      return `买入日期越界，当前最早仅支持 ${meta.earliest_date}。`;
    }
    if (meta?.latest_date && newHolding.buy_date > meta.latest_date) {
      return `买入日期越界，当前最晚仅支持 ${meta.latest_date}。`;
    }
    return null;
  };

  const handleAddHolding = () => {
    const message = addHoldingError();
    if (message) {
      setSimError(message);
      showToast("error", message);
      return;
    }
    setHoldings((current) => [...current, { ...newHolding }]);
    setNewHolding({
      symbol: "",
      buy_date: meta?.latest_date || "",
      shares: 100,
    });
    setSearchKeyword("");
    setShowSearchResults(false);
    setSimError(null);
    showToast("success", "持仓已加入模拟列表。");
  };

  const handleRunSimulation = async () => {
    if (!holdings.length) {
      const message = "请先添加至少一条持仓，再开始组合模拟。";
      setSimError(message);
      showToast("error", message);
      return;
    }

    setSimLoading(true);
    setSimError(null);
    try {
      const nextResult = await simulatePortfolio(holdings);
      setSimResult(nextResult);
      showToast("success", "组合研究测算已完成。");
    } catch (err: unknown) {
      const message = err instanceof Error && err.message.trim() ? err.message : "组合模拟失败，请稍后重试。";
      setSimError(message);
      showToast("error", message);
    } finally {
      setSimLoading(false);
    }
  };

  return (
    <PageShell title="回测中心" subtitle={activeTab === "backtest" ? "历史研究测算" : "组合研究测算"}>
      <div className="flex flex-wrap gap-2">
        {[
          { key: "backtest", label: "策略回测" },
          { key: "simulate", label: "组合模拟" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as TabKey)}
            className={`rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.key ? "bg-primary-500 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <SimulatedDataNotice
        title="回测研究边界"
        badges={[
          { label: `数据截至 ${meta?.latest_date || runtime?.latest_updates?.prices || "待更新"}`, tone: "database" },
          { label: `样本数 ${meta?.sample_count || 0}`, tone: "database" },
          { label: "历史研究测算 / 非实盘收益", tone: "simulated" },
        ]}
        lines={[
          "回测结果基于历史行情、费用和滑点假设，不代表未来收益，也不代表实际可成交价格。",
          "研究组合模拟同样属于研究视图，不代表真实账户表现。",
        ]}
      />

      {activeTab === "backtest" ? (
        <>
          <div className="card space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-6">
              <div>
                <label className="text-xs font-medium text-[var(--text-secondary)]">策略</label>
                <select
                  value={params.strategy}
                  onChange={(event) => setParams((current) => ({ ...current, strategy: event.target.value }))}
                  className="mt-1 w-full rounded-xl border border-[var(--border-default)] bg-white px-3 py-2 text-sm text-[var(--text-primary)]"
                >
                  <option value="fundamental_medium_long">基本面中期策略</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-[var(--text-secondary)]">市场</label>
                <select
                  value={params.market}
                  onChange={(event) => setParams((current) => ({ ...current, market: event.target.value }))}
                  className="mt-1 w-full rounded-xl border border-[var(--border-default)] bg-white px-3 py-2 text-sm text-[var(--text-primary)]"
                >
                  {MARKET_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-[var(--text-secondary)]">开始日期</label>
                <input
                  type="date"
                  value={params.start_date}
                  min={meta?.earliest_date || undefined}
                  max={meta?.latest_date || undefined}
                  onChange={(event) => setParams((current) => ({ ...current, start_date: event.target.value }))}
                  className="mt-1 w-full rounded-xl border border-[var(--border-default)] bg-white px-3 py-2 text-sm text-[var(--text-primary)]"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-[var(--text-secondary)]">结束日期</label>
                <input
                  type="date"
                  value={params.end_date}
                  min={meta?.earliest_date || undefined}
                  max={meta?.latest_date || undefined}
                  onChange={(event) => setParams((current) => ({ ...current, end_date: event.target.value }))}
                  className="mt-1 w-full rounded-xl border border-[var(--border-default)] bg-white px-3 py-2 text-sm text-[var(--text-primary)]"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-[var(--text-secondary)]">调仓频率</label>
                <select
                  value={params.rebalance}
                  onChange={(event) => setParams((current) => ({ ...current, rebalance: event.target.value }))}
                  className="mt-1 w-full rounded-xl border border-[var(--border-default)] bg-white px-3 py-2 text-sm text-[var(--text-primary)]"
                >
                  {REBALANCE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-end">
                <button
                  onClick={() => void handleRunBacktest()}
                  disabled={runLoading || metaLoading}
                  className="btn-primary flex w-full items-center justify-center gap-2 px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                  title={canRunMessage || "开始回测"}
                >
                  {runLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                  {runLoading ? "计算中，预计约 30 秒" : "开始回测"}
                </button>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-xl border border-[var(--border-default)] bg-slate-50 px-4 py-3 text-sm text-[var(--text-body)]">
                {metaLoading ? "正在读取可用日期范围..." : rangeHint}
              </div>
              <div className="rounded-xl border border-[var(--border-default)] bg-slate-50 px-4 py-3 text-sm text-[var(--text-body)]">
                手续费：佣金 {((meta?.fees.commission_rate || 0) * 100).toFixed(3)}% + 印花税{" "}
                {((meta?.fees.stamp_duty_rate || 0) * 100).toFixed(3)}%
              </div>
              <div className="rounded-xl border border-[var(--border-default)] bg-slate-50 px-4 py-3 text-sm text-[var(--text-body)]">
                滑点：{((meta?.fees.slippage_rate || 0) * 100).toFixed(2)}% · 基准：{meta?.assumptions.benchmark || "待核验"}
              </div>
              <div className="rounded-xl border border-[var(--border-default)] bg-slate-50 px-4 py-3 text-sm text-[var(--text-body)]">
                边界：{meta?.assumptions.handles_limit_lock ? "已考虑涨跌停锁定" : "未建模涨跌停"}；
                {meta?.assumptions.handles_suspension ? "已考虑停牌" : "未显式建模停牌恢复"}
              </div>
            </div>

            {metaError ? (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                回测元数据加载失败：{metaError}
              </div>
            ) : null}
            {runError ? (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{runError}</div>
            ) : null}
          </div>

          {result ? (
            <>
              <div className="grid grid-cols-2 gap-4 xl:grid-cols-6">
                <ResultCard label="总收益" value={formatPercent(result.total_return)} tone={result.total_return >= 0 ? "positive" : "negative"} />
                <ResultCard label="年化收益" value={formatPercent(result.annual_return)} tone={result.annual_return >= 0 ? "positive" : "negative"} />
                <ResultCard label="基准收益" value={formatPercent(result.benchmark_return)} tone={result.benchmark_return >= 0 ? "positive" : "negative"} />
                <ResultCard label="超额收益" value={formatPercent(result.excess_return)} tone={result.excess_return >= 0 ? "positive" : "negative"} />
                <ResultCard label="最大回撤" value={formatPercent(result.max_drawdown)} tone="negative" />
                <ResultCard label="夏普比率" value={formatNumber(result.sharpe_ratio)} />
              </div>

              <div className="grid gap-4 xl:grid-cols-2">
                <div className="card">
                  <div className="mb-3">
                    <h2 className="text-base font-semibold text-[var(--text-primary)]">权益曲线</h2>
                    <p className="mt-1 text-xs text-[var(--text-secondary)]">历史研究测算，不代表未来收益。</p>
                  </div>
                  <div className="h-[340px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={result.equity_curve}>
                        <CartesianGrid stroke="#E2E8F0" />
                        <XAxis dataKey="date" tick={{ fill: "#64748B", fontSize: 11 }} />
                        <YAxis tick={{ fill: "#64748B", fontSize: 11 }} />
                        <Tooltip content={<ChartTooltip />} />
                        <Line type="monotone" dataKey="equity" stroke="#2563EB" dot={false} strokeWidth={2} />
                        <Line type="monotone" dataKey="benchmark" stroke="#94A3B8" dot={false} strokeWidth={2} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="card">
                  <div className="mb-3">
                    <h2 className="text-base font-semibold text-[var(--text-primary)]">月度超额收益</h2>
                    <p className="mt-1 text-xs text-[var(--text-secondary)]">用于观察策略相对基准的阶段性表现。</p>
                  </div>
                  <div className="h-[340px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={result.monthly_returns.slice(-24)}>
                        <CartesianGrid stroke="#E2E8F0" />
                        <XAxis dataKey="month" tick={{ fill: "#64748B", fontSize: 11 }} />
                        <YAxis tick={{ fill: "#64748B", fontSize: 11 }} />
                        <Tooltip content={<ChartTooltip />} />
                        <Bar dataKey="excess_return" fill="#14B8A6" radius={[6, 6, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            </>
          ) : null}
        </>
      ) : (
        <div className="space-y-4">
          <div className="card space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div className="relative" ref={searchRef}>
                <label className="text-xs font-medium text-[var(--text-secondary)]">股票代码或名称</label>
                <div className="relative mt-1">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
                  <input
                    value={newHolding.symbol || searchKeyword}
                    onChange={(event) => {
                      setSearchKeyword(event.target.value);
                      setNewHolding((current) => ({ ...current, symbol: "" }));
                      setShowSearchResults(true);
                    }}
                    placeholder="搜索股票代码或名称"
                    className="w-full rounded-xl border border-[var(--border-default)] bg-white py-2 pl-9 pr-3 text-sm text-[var(--text-primary)]"
                  />
                </div>
                {showSearchResults && searchResults.length > 0 ? (
                  <div className="absolute left-0 right-0 top-full z-20 mt-1 max-h-56 overflow-y-auto rounded-xl border border-[var(--border-default)] bg-white shadow-lg">
                    {searchResults.map((stock) => (
                      <button
                        key={stock.symbol}
                        onClick={() => {
                          setNewHolding((current) => ({ ...current, symbol: stock.symbol }));
                          setSearchKeyword("");
                          setShowSearchResults(false);
                        }}
                        className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm text-[var(--text-primary)] hover:bg-slate-50"
                      >
                        <span className="font-mono text-primary-600">{stock.symbol}</span>
                        <span>{sanitizeDisplayText(stock.name, stock.symbol)}</span>
                        <span className="ml-auto text-xs text-[var(--text-secondary)]">{marketLabel(stock.market)}</span>
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>

              <div>
                <label className="text-xs font-medium text-[var(--text-secondary)]">买入日期</label>
                <input
                  type="date"
                  value={newHolding.buy_date}
                  min={meta?.earliest_date || undefined}
                  max={meta?.latest_date || undefined}
                  onChange={(event) => setNewHolding((current) => ({ ...current, buy_date: event.target.value }))}
                  className="mt-1 w-full rounded-xl border border-[var(--border-default)] bg-white px-3 py-2 text-sm text-[var(--text-primary)]"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-[var(--text-secondary)]">股数</label>
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={newHolding.shares}
                  onChange={(event) => setNewHolding((current) => ({ ...current, shares: Number(event.target.value) || 0 }))}
                  className="mt-1 w-full rounded-xl border border-[var(--border-default)] bg-white px-3 py-2 text-sm text-[var(--text-primary)]"
                />
              </div>

              <div className="flex items-end gap-2">
                <button onClick={handleAddHolding} className="btn-secondary flex items-center gap-2 px-4 py-2 text-sm">
                  <Plus className="h-4 w-4" />
                  添加持仓
                </button>
                <button
                  onClick={() => void handleRunSimulation()}
                  disabled={simLoading || holdings.length === 0}
                  className="btn-primary flex flex-1 items-center justify-center gap-2 px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {simLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                  {simLoading ? "计算中" : "开始模拟"}
                </button>
              </div>
            </div>

            <div className="rounded-xl border border-[var(--border-default)] bg-slate-50 px-4 py-3 text-sm text-[var(--text-body)]">
              组合模拟流程：输入股票、日期和股数后先点击“添加持仓”，待列表中出现持仓记录后，再点击“开始模拟”。
            </div>

            {simError ? (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{simError}</div>
            ) : null}
          </div>

          <div className="card">
            {holdings.length === 0 ? (
              <EmptyState
                message="当前还没有加入模拟持仓。"
                description="请先添加至少一条持仓记录，再开始组合研究测算。"
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--border-default)]">
                      {["股票", "买入日期", "股数", "操作"].map((header) => (
                        <th key={header} className="px-3 py-3 text-left text-xs font-semibold text-[var(--text-secondary)]">
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {holdings.map((holding, index) => (
                      <tr key={`${holding.symbol}-${holding.buy_date}-${index}`} className="border-b border-[var(--border-light)]">
                        <td className="px-3 py-3 font-mono text-[var(--text-primary)]">{holding.symbol}</td>
                        <td className="px-3 py-3 text-[var(--text-body)]">{holding.buy_date}</td>
                        <td className="px-3 py-3 text-[var(--text-body)]">{holding.shares}</td>
                        <td className="px-3 py-3">
                          <button
                            onClick={() => setHoldings((current) => current.filter((_, currentIndex) => currentIndex !== index))}
                            className="inline-flex items-center gap-1 text-xs font-semibold text-red-600 hover:text-red-700"
                          >
                            <Trash2 className="h-4 w-4" />
                            删除
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {simResult ? (
            <>
              <div className="grid grid-cols-2 gap-4 xl:grid-cols-5">
                <ResultCard label="总投入" value={formatNumber(simResult.total_invested, 0)} />
                <ResultCard label="当前市值" value={formatNumber(simResult.current_value, 0)} />
                <ResultCard label="总收益" value={formatPercent(simResult.total_return)} tone={simResult.total_return >= 0 ? "positive" : "negative"} />
                <ResultCard label="基准收益" value={formatPercent(simResult.benchmark_return)} tone={simResult.benchmark_return >= 0 ? "positive" : "negative"} />
                <ResultCard label="超额收益" value={formatPercent(simResult.excess_return)} tone={simResult.excess_return >= 0 ? "positive" : "negative"} />
              </div>

              <div className="card">
                <div className="mb-3">
                  <h2 className="text-base font-semibold text-[var(--text-primary)]">持仓结果</h2>
                  <p className="mt-1 text-xs text-[var(--text-secondary)]">以下结果属于研究视图 / 非实盘 / 不代表未来收益。</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[900px] text-sm">
                    <thead>
                      <tr className="border-b border-[var(--border-default)]">
                        {["股票", "买入日期", "买入价", "当前价", "股数", "成本", "当前市值", "盈亏", "收益率"].map((header) => (
                          <th key={header} className="px-3 py-3 text-left text-xs font-semibold text-[var(--text-secondary)]">
                            {header}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {simResult.holdings.map((holding) => (
                        <tr key={`${holding.symbol}-${holding.buy_date}`} className="border-b border-[var(--border-light)]">
                          <td className="px-3 py-3 font-mono text-[var(--text-primary)]">{holding.symbol}</td>
                          <td className="px-3 py-3 text-[var(--text-body)]">{holding.buy_date}</td>
                          <td className="px-3 py-3 font-mono text-[var(--text-primary)]">{formatNumber(holding.buy_price)}</td>
                          <td className="px-3 py-3 font-mono text-[var(--text-primary)]">{formatNumber(holding.current_price)}</td>
                          <td className="px-3 py-3 text-[var(--text-body)]">{holding.shares}</td>
                          <td className="px-3 py-3 font-mono text-[var(--text-primary)]">{formatNumber(holding.cost, 0)}</td>
                          <td className="px-3 py-3 font-mono text-[var(--text-primary)]">{formatNumber(holding.current_value, 0)}</td>
                          <td className={`px-3 py-3 font-mono ${getChangeColor(holding.pnl)}`}>{formatNumber(holding.pnl, 0)}</td>
                          <td className={`px-3 py-3 font-mono ${getChangeColor(holding.pnl_pct)}`}>{formatPercent(holding.pnl_pct)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : null}
        </div>
      )}

      <div className="disclaimer">本系统仅用于研究和辅助分析，不构成任何投资建议。</div>
    </PageShell>
  );
}
