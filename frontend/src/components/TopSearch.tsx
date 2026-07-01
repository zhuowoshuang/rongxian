"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Search, X } from "lucide-react";

import { searchStocks } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import { searchADataStocks } from "@/services/adataStockApi";
import type { StockSearchResult } from "@/types";

function containsChinese(value: string) {
  return /[\u4e00-\u9fff]/.test(value);
}

function isSixDigitCode(value: string) {
  return /^\d{6}$/.test(value);
}

function normalizeADataResult(item: any): StockSearchResult {
  return {
    id: Number(item.id || 0),
    symbol: String(item.symbol || item.code || ""),
    name: String(item.name || item.symbol || ""),
    market: item.market === "A" ? "A_SHARE" : item.market || "A_SHARE",
    exchange: item.exchange || (String(item.symbol || "").startsWith("6") ? "SH" : "SZ"),
    industry: item.industry || "",
    source: "adata",
    dataStatus: item.dataStatus || "OK",
    networkStatus: item.networkStatus || "NETWORK_WARN",
    mode: item.mode || "live",
    missingFields: item.missingFields || [],
    errorMessage: item.errorMessage || null,
  };
}

export default function TopSearch() {
  const { t } = useTranslation();
  const router = useRouter();
  const [keyword, setKeyword] = useState("");
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [searching, setSearching] = useState(false);
  const [notice, setNotice] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const performSearch = useCallback(async (value: string) => {
    const trimmed = value.trim();
    setKeyword(value);

    if (!trimmed) {
      setResults([]);
      setNotice("");
      setShowDropdown(false);
      setSearching(false);
      return;
    }

    setSearching(true);
    setNotice("");

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const dbResults = await searchStocks(trimmed);
        if (dbResults.length > 0) {
          setResults(dbResults);
          setShowDropdown(true);
          setSearching(false);
          return;
        }

        if (containsChinese(trimmed)) {
          setResults([]);
          setNotice("未找到匹配股票");
          setShowDropdown(true);
          setSearching(false);
          return;
        }

        if (!isSixDigitCode(trimmed)) {
          setResults([]);
          setNotice("未找到匹配股票");
          setShowDropdown(true);
          setSearching(false);
          return;
        }

        try {
          const adataResults = await searchADataStocks(trimmed);
          const normalized = (adataResults || [])
            .filter((item) => item?.symbol)
            .map(normalizeADataResult);

          setResults(normalized);
          setNotice(normalized.length > 0 ? "补充数据源结果，仅用于辅助定位股票。" : "未找到匹配股票");
        } catch {
          setResults([]);
          setNotice("补充数据源暂不可用，不影响本地股票库搜索。");
        }
      } catch {
        setResults([]);
        setNotice("搜索暂时不可用，请稍后重试。");
      } finally {
        setSearching(false);
        setShowDropdown(true);
      }
    }, 250);
  }, []);

  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
  }, []);

  const handleSelect = (symbol: string) => {
    setShowDropdown(false);
    setKeyword("");
    setResults([]);
    setNotice("");
    router.push(`/stocks/${symbol}`);
  };

  const handleClear = () => {
    setKeyword("");
    setResults([]);
    setNotice("");
    setShowDropdown(false);
    setSearching(false);
  };

  return (
    <div ref={wrapperRef} className="relative w-full max-w-xl">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
        <input
          type="text"
          value={keyword}
          onChange={(event) => void performSearch(event.target.value)}
          onFocus={() => {
            if (results.length > 0 || notice) setShowDropdown(true);
          }}
          placeholder={t("common.searchPlaceholder")}
          className="w-full search-input"
        />
        {keyword ? (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] transition-colors hover:text-[var(--text-primary)]"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>

      {showDropdown ? (
        <div className="card absolute left-0 right-0 top-full z-50 mt-1.5 max-h-80 overflow-y-auto !p-0 shadow-lg">
          {searching ? (
            <div className="flex items-center justify-center gap-2 px-4 py-6 text-sm text-[var(--text-muted)]">
              <Loader2 className="h-4 w-4 animate-spin" />
              正在搜索股票…
            </div>
          ) : results.length > 0 ? (
            <>
              {notice ? <div className="border-b border-[var(--border-light)] px-4 py-2 text-xs text-amber-700">{notice}</div> : null}
              {results.map((result) => (
                <button
                  key={`${result.symbol}-${result.exchange}`}
                  onMouseDown={(event) => {
                    event.preventDefault();
                    handleSelect(result.symbol);
                  }}
                  className="flex w-full items-center justify-between border-b border-[var(--border-light)] px-4 py-3 text-left transition-colors last:border-0 hover:bg-[var(--bg-surface)]"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="rounded bg-primary-50 px-1.5 py-0.5 font-mono text-xs font-semibold text-primary-600">{result.symbol}</span>
                    <span className="text-sm font-medium text-[var(--text-primary)]">{result.name || result.symbol}</span>
                    <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${result.market === "A_SHARE" ? "bg-blue-50 text-blue-700" : "bg-purple-50 text-purple-700"}`}>
                      {result.market === "A_SHARE" ? t("market.aShare") : t("market.hk")}
                    </span>
                  </div>
                  {result.industry ? <span className="text-xs text-[var(--text-muted)]">{result.industry}</span> : null}
                </button>
              ))}
            </>
          ) : (
            <div className="px-4 py-6 text-center text-sm text-[var(--text-muted)]">{notice || "未找到匹配股票"}</div>
          )}
        </div>
      ) : null}
    </div>
  );
}
