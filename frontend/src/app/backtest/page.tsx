"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, Play, Search } from "lucide-react";

import PageShell from "@/components/layout/PageShell";
import EmptyState from "@/components/ui/EmptyState";
import SimulatedDataNotice from "@/components/ui/SimulatedDataNotice";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { showToast } from "@/components/ui/Toast";
import {
  getAvailableBacktestStocks,
  getBacktestMeta,
  getBacktestStrategies,
  getRuntimeInfo,
  runBacktest,
  searchStocks,
} from "@/lib/api";
import { formatNumber, formatPercent, marketLabel, sanitizeDisplayText } from "@/lib/utils";
import type {
  AvailableBacktestStock,
  AvailableBacktestStockResponse,
  BacktestMeta,
  BacktestResult,
  RuntimeInfo,
  StockSearchResult,
} from "@/types";

type SupportMode = "factor" | "basic" | "unavailable";

const MARKET_OPTIONS = [
  { value: "A_SHARE", label: "A股" },
  { value: "HK", label: "港股" },
];

const REBALANCE_OPTIONS = [
  { value: "monthly", label: "月度" },
  { value: "quarterly", label: "季度" },
];

const RECOMMENDED_SYMBOLS = ["002415", "600519"];

function supportModeFromStock(item?: AvailableBacktestStock | null): SupportMode {
  if (!item) return "unavailable";
  if (item.support?.factor_available || item.recommended_mode === "factor" || item.support_level === "full") return "factor";
  if (item.support?.basic_available || item.recommended_mode === "basic" || ["basic", "preview"].includes(item.support_level)) return "basic";
  return "unavailable";
}

function supportReason(item?: AvailableBacktestStock | null, mode: SupportMode = "basic") {
  if (!item) return "请先从样本池或搜索结果中选择股票。";
  if (mode === "factor") {
    return item.support?.factor_reason || item.missing_reason || item.reason || "当前样本暂不支持完整因子回测。";
  }
  return item.support?.basic_reason || item.reason || "当前样本暂不支持基础行情回测。";
}

function modeTitle(mode: SupportMode) {
  if (mode === "factor") return "完整因子回测";
  if (mode === "basic") return "基础行情回测";
  return "暂不可回测";
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[var(--border-default)] bg-white p-4">
      <p className="text-xs font-medium text-[var(--text-secondary)]">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

export default function BacktestPage() {
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [meta, setMeta] = useState<BacktestMeta | null>(null);
  const [strategies, setStrategies] = useState<Array<{ key: string; name?: string }>>([]);
  const [availableData, setAvailableData] = useState<AvailableBacktestStockResponse | null>(null);
  const [selectedStock, setSelectedStock] = useState<StockSearchResult | null>(null);
  const [selectedSupport, setSelectedSupport] = useState<AvailableBacktestStock | null>(null);
  const [keyword, setKeyword] = useState("");
  const [searchResults, setSearchResults] = useState<StockSearchResult[]>([]);
  const [searchNotice, setSearchNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [params, setParams] = useState({
    strategy: "qingshu_1_short",
    market: "A_SHARE",
    start_date: "",
    end_date: "",
    rebalance: "monthly",
    initial_capital: 1000000,
  });

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [runtimeValue, metaValue, availableValue, strategyValue] = await Promise.all([
          getRuntimeInfo().catch(() => null),
          getBacktestMeta(params.market),
          getAvailableBacktestStocks(params.market, 24),
          getBacktestStrategies().catch(() => ({ items: [] })),
        ]);
        setRuntime(runtimeValue);
        setMeta(metaValue);
        setAvailableData(availableValue);
        setStrategies(strategyValue.items || []);
        setParams((current) => ({
          ...current,
          start_date: current.start_date || metaValue.earliest_date || "",
          end_date: current.end_date || metaValue.latest_date || "",
        }));
      } catch (err) {
        setError(err instanceof Error ? err.message : "回测数据加载失败，请稍后重试。");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [params.market]);

  useEffect(() => {
    if (!keyword.trim()) {
      setSearchResults([]);
      setSearchNotice(null);
      return;
    }
    const timer = window.setTimeout(() => {
      searchStocks(keyword.trim(), params.market)
        .then((items) => {
          setSearchResults(items || []);
          setSearchNotice((items || []).length ? null : "未找到匹配股票");
        })
        .catch((err) => {
          setSearchResults([]);
          setSearchNotice(err instanceof Error ? err.message : "股票搜索暂时不可用。");
        });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [keyword, params.market]);

  const stockSupportMap = useMemo(() => {
    const map = new Map<string, AvailableBacktestStock>();
    for (const item of availableData?.items || []) map.set(item.stock_code, item);
    for (const item of availableData?.unavailable_examples || []) {
      if (!map.has(item.stock_code)) map.set(item.stock_code, item);
    }
    return map;
  }, [availableData]);

  const recommendedItems = useMemo(() => {
    const items = availableData?.items || [];
    const bySymbol = new Map(items.map((item) => [item.stock_code, item]));
    return RECOMMENDED_SYMBOLS.map((symbol) => bySymbol.get(symbol)).filter(Boolean) as AvailableBacktestStock[];
  }, [availableData]);

  const chosenMode = supportModeFromStock(selectedSupport);
  const basicAvailable = chosenMode === "factor" || chosenMode === "basic";
  const factorAvailable = chosenMode === "factor";

  const pickStock = (stock: StockSearchResult) => {
    setSelectedStock(stock);
    setSelectedSupport(stockSupportMap.get(stock.symbol) || null);
    setKeyword("");
    setSearchResults([]);
    setSearchNotice(null);
    setResult(null);
    setError(null);
  };

  const runSelectedBacktest = async () => {
    if (!selectedStock) {
      setError("请先选择股票。");
      return;
    }
    if (!basicAvailable) {
      setError(supportReason(selectedSupport, "basic"));
      return;
    }
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const data = await runBacktest({
        strategy: params.strategy,
        market: params.market,
        stock_symbol: selectedStock.symbol,
        stock_name: selectedStock.name,
        start_date: params.start_date,
        end_date: params.end_date,
        rebalance: params.rebalance,
        initial_capital: params.initial_capital,
      });
      setResult(data);
      showToast("success", data.mode === "basic" ? "已完成基础行情回测" : "已完成完整因子回测");
    } catch (err) {
      const message = err instanceof Error ? err.message : "回测执行失败，请稍后重试。";
      setError(message);
      showToast("error", message);
    } finally {
      setRunning(false);
    }
  };

  const displayedMode = result?.mode || (factorAvailable ? "factor" : basicAvailable ? "basic" : "unavailable");

  return (
    <PageShell
      title="回测中心"
      subtitle="区分基础行情回测与完整因子回测，数据不足时说明真实原因，不伪装成行情异常。"
    >
      <SimulatedDataNotice
        title="研究测算说明"
        badges={[
          { label: `市场范围：${marketLabel(params.market)}`, tone: "database" },
          { label: `样本池：${availableData?.supported_count || 0} 只`, tone: "live" },
          { label: `日期覆盖：${meta?.trade_day_count || 0} 个交易日`, tone: "database" },
        ]}
        lines={[
          "基础行情回测只要求所选日期范围内有足够价格样本。",
          "完整因子回测还需要财务、技术指标与评分链路支撑。",
          runtime?.warning || "本页结果属于研究测算 / 非实盘 / 不代表未来收益。",
        ]}
      />

      <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <section className="rounded-2xl border border-[var(--border-default)] bg-white p-5">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2">
              <span className="text-sm font-medium text-[var(--text-primary)]">市场</span>
              <select
                value={params.market}
                onChange={(event) => setParams((current) => ({ ...current, market: event.target.value }))}
                className="input"
              >
                {MARKET_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-[var(--text-primary)]">研究策略</span>
              <select
                value={params.strategy}
                onChange={(event) => setParams((current) => ({ ...current, strategy: event.target.value }))}
                className="input"
              >
                {strategies.map((item) => (
                  <option key={item.key} value={item.key}>
                    {item.name || item.key}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-[var(--text-primary)]">开始日期</span>
              <input
                type="date"
                value={params.start_date}
                onChange={(event) => setParams((current) => ({ ...current, start_date: event.target.value }))}
                className="input"
              />
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-[var(--text-primary)]">结束日期</span>
              <input
                type="date"
                value={params.end_date}
                onChange={(event) => setParams((current) => ({ ...current, end_date: event.target.value }))}
                className="input"
              />
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-[var(--text-primary)]">调仓频率</span>
              <select
                value={params.rebalance}
                onChange={(event) => setParams((current) => ({ ...current, rebalance: event.target.value }))}
                className="input"
              >
                {REBALANCE_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-[var(--text-primary)]">初始资金</span>
              <input
                type="number"
                min={10000}
                step={10000}
                value={params.initial_capital}
                onChange={(event) =>
                  setParams((current) => ({ ...current, initial_capital: Number(event.target.value) || 0 }))
                }
                className="input"
              />
            </label>
          </div>

          <div className="mt-5 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4">
            <div className="flex items-center gap-2">
              <Search className="h-4 w-4 text-[var(--text-secondary)]" />
              <p className="text-sm font-medium text-[var(--text-primary)]">搜索或选择可回测样本</p>
            </div>
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="输入股票代码或中文名称"
              className="mt-3 input"
            />
            {searchNotice ? <p className="mt-2 text-xs text-[var(--color-warning)]">{searchNotice}</p> : null}

            {searchResults.length ? (
              <div className="mt-3 space-y-2">
                {searchResults.slice(0, 6).map((item) => (
                  <button
                    key={item.symbol}
                    onClick={() => pickStock(item)}
                    className="flex w-full items-center justify-between rounded-xl border border-[var(--border-default)] bg-white px-4 py-3 text-left hover:border-primary-300"
                  >
                    <div>
                      <p className="font-medium text-[var(--text-primary)]">
                        {item.name} <span className="font-mono text-[var(--text-secondary)]">{item.symbol}</span>
                      </p>
                      <p className="text-xs text-[var(--text-secondary)]">{marketLabel(item.market)} {item.industry ? `· ${item.industry}` : ""}</p>
                    </div>
                    <span className="text-xs text-primary-600">选择</span>
                  </button>
                ))}
              </div>
            ) : null}

            <div className="mt-4">
              <p className="text-xs font-medium text-[var(--text-secondary)]">推荐可回测样本</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {recommendedItems.map((item) => (
                  <button
                    key={item.stock_code}
                    onClick={() =>
                      pickStock({
                        id: 0,
                        symbol: item.stock_code,
                        name: item.stock_name,
                        market: item.market,
                        exchange: item.market === "HK" ? "HK" : item.stock_code.startsWith("6") ? "SH" : "SZ",
                        industry: item.industry || "",
                      })
                    }
                    className="rounded-xl border border-[var(--border-default)] bg-white px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:border-primary-300"
                  >
                    {item.stock_name} ({item.stock_code})
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-[var(--border-default)] bg-white p-5">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">当前样本可用性</h2>
          {selectedStock ? (
            <>
              <div className="mt-3 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4">
                <p className="text-lg font-semibold text-[var(--text-primary)]">
                  {selectedStock.name} <span className="font-mono text-base text-[var(--text-secondary)]">{selectedStock.symbol}</span>
                </p>
                <p className="mt-1 text-sm text-[var(--text-secondary)]">
                  {marketLabel(selectedStock.market)}{selectedStock.industry ? ` · ${selectedStock.industry}` : ""}
                </p>
              </div>

              <div className="mt-4 grid gap-3">
                <div className={`rounded-2xl border p-4 ${basicAvailable ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-slate-50"}`}>
                  <p className="text-sm font-semibold text-[var(--text-primary)]">基础行情回测</p>
                  <p className="mt-2 text-sm">{basicAvailable ? "可用" : "不可用"}</p>
                  <p className="mt-2 text-xs text-[var(--text-secondary)]">
                    {basicAvailable
                      ? "只依赖价格样本，可先验证基础走势与区间表现。"
                      : supportReason(selectedSupport, "basic")}
                  </p>
                </div>

                <div className={`rounded-2xl border p-4 ${factorAvailable ? "border-blue-200 bg-blue-50" : "border-slate-200 bg-slate-50"}`}>
                  <p className="text-sm font-semibold text-[var(--text-primary)]">完整因子回测</p>
                  <p className="mt-2 text-sm">{factorAvailable ? "可用" : "暂不可用"}</p>
                  <p className="mt-2 text-xs text-[var(--text-secondary)]">
                    {factorAvailable
                      ? "已具备财务、技术指标与评分支撑，可运行完整研究回测。"
                      : supportReason(selectedSupport, "factor")}
                  </p>
                </div>
              </div>

              <button
                onClick={() => void runSelectedBacktest()}
                disabled={running || !basicAvailable}
                className="btn-primary mt-5 inline-flex w-full items-center justify-center gap-2 px-4 py-3 text-sm disabled:opacity-60"
              >
                {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                {running ? "正在执行回测..." : `运行${modeTitle(chosenMode === "factor" ? "factor" : basicAvailable ? "basic" : "unavailable")}`}
              </button>

              {!factorAvailable && basicAvailable ? (
                <p className="mt-3 text-xs text-[var(--text-secondary)]">
                  当前将运行基础行情回测。缺少财务或评分时，不会再误报为“行情样本不足”。
                </p>
              ) : null}
            </>
          ) : (
            <div className="mt-4">
              <EmptyState
                message="请先选择股票"
                description="优先从推荐样本或搜索结果中选择股票，再查看当前支持的回测模式。"
              />
            </div>
          )}
        </section>
      </div>

      {loading ? (
        <div className="grid gap-4 lg:grid-cols-4">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-4">
          <StatCard label="样本池股票" value={String(availableData?.supported_count || 0)} />
          <StatCard label="交易日覆盖" value={String(meta?.trade_day_count || 0)} />
          <StatCard label="价格样本" value={String(meta?.price_count || 0)} />
          <StatCard label="默认执行模式" value={modeTitle(displayedMode)} />
        </div>
      )}

      {result ? (
        <section className="rounded-2xl border border-[var(--border-default)] bg-white p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                {result.stock_name || selectedStock?.name} {result.stock_code ? `(${result.stock_code})` : ""}
              </h2>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                {sanitizeDisplayText(result.user_visible_message, "研究测算 / 非实盘 / 不代表未来收益。")}
              </p>
            </div>
            <span className="rounded-full border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-1 text-xs font-medium text-[var(--text-primary)]">
              {modeTitle(result.mode || "basic")}
            </span>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-3 lg:grid-cols-6">
            <StatCard label="总收益率" value={formatPercent(result.total_return / 100)} />
            <StatCard label="年化收益率" value={formatPercent(result.annual_return / 100)} />
            <StatCard label="基准收益率" value={formatPercent(result.benchmark_return / 100)} />
            <StatCard label="超额收益" value={formatPercent(result.excess_return / 100)} />
            <StatCard label="最大回撤" value={formatPercent(result.max_drawdown / 100)} />
            <StatCard label="交易次数" value={String(result.total_trades)} />
          </div>

          {result.support ? (
            <div className="mt-5 grid gap-3 md:grid-cols-2">
              <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4">
                <p className="text-sm font-semibold text-[var(--text-primary)]">基础行情回测状态</p>
                <p className="mt-2 text-sm">{result.support.basic_available ? "已满足" : "未满足"}</p>
                <p className="mt-2 text-xs text-[var(--text-secondary)]">
                  {result.support.basic_reason || "当前日期范围内价格样本可用。"}
                </p>
              </div>
              <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4">
                <p className="text-sm font-semibold text-[var(--text-primary)]">完整因子回测状态</p>
                <p className="mt-2 text-sm">{result.support.factor_available ? "已满足" : "未满足"}</p>
                <p className="mt-2 text-xs text-[var(--text-secondary)]">
                  {result.support.factor_reason || "已具备财务、技术指标与评分支撑。"}
                </p>
              </div>
            </div>
          ) : null}

          {result.trade_log?.length ? (
            <div className="mt-5 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4">
              <p className="text-sm font-semibold text-[var(--text-primary)]">交易记录摘要</p>
              <div className="mt-3 space-y-2">
                {result.trade_log.slice(0, 6).map((item, index) => (
                  <div key={`${item.date || index}-${item.action || index}`} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--border-default)] bg-white px-4 py-3 text-sm">
                    <span>{item.date || "--"}</span>
                    <span>{item.name || item.symbol || "--"}</span>
                    <span>{item.action === "BUY_AND_HOLD" ? "买入并持有测算" : item.action || "--"}</span>
                    <span>{typeof item.price === "number" ? formatNumber(item.price, 2) : "--"}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </section>
      ) : null}
    </PageShell>
  );
}
