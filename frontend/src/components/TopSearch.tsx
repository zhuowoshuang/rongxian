"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { searchStocks } from "@/lib/api";
import type { StockSearchResult } from "@/types";
import { useTranslation } from "@/lib/i18n";
import { Search, X, Loader2 } from "lucide-react";

export default function TopSearch() {
  const { t } = useTranslation();
  const [keyword, setKeyword] = useState("");
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [searching, setSearching] = useState(false);
  const router = useRouter();
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // 点击外部关闭下拉
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const handleSearch = useCallback(async (value: string) => {
    setKeyword(value);
    if (value.trim().length < 1) {
      setResults([]);
      setShowDropdown(false);
      setSearching(false);
      return;
    }
    setSearching(true);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const data = await searchStocks(value.trim());
        setResults(data);
        setShowDropdown(true);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
  }, []);

  useEffect(() => () => { if (debounceRef.current) clearTimeout(debounceRef.current); }, []);

  const handleSelect = (symbol: string) => {
    setShowDropdown(false);
    setKeyword("");
    setResults([]);
    router.push(`/stocks/${symbol}`);
  };

  const handleClear = () => {
    setKeyword("");
    setResults([]);
    setShowDropdown(false);
    setSearching(false);
  };

  return (
    <div ref={wrapperRef} className="relative w-full max-w-xl">
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-muted pointer-events-none" />
        <input
          type="text"
          value={keyword}
          onChange={(e) => handleSearch(e.target.value)}
          onFocus={() => { if (results.length > 0) setShowDropdown(true); }}
          placeholder={t("common.searchPlaceholder")}
          className="w-full pl-10 pr-9 py-2.5 bg-white/[0.05] border border-white/[0.08] rounded-xl text-sm text-dark-text placeholder:text-dark-muted/50 focus:outline-none focus:ring-2 focus:ring-primary-500/40 focus:border-primary-500/30 backdrop-blur-xl transition-all"
        />
        {keyword && (
          <button onClick={handleClear} className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-muted hover:text-dark-text transition-colors">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {showDropdown && (
        <div className="absolute top-full left-0 right-0 mt-1.5 bg-dark-card rounded-xl shadow-2xl border border-white/[0.08] overflow-hidden z-50 max-h-80 overflow-y-auto backdrop-blur-xl">
          {searching ? (
            <div className="flex items-center justify-center gap-2 px-4 py-6 text-dark-muted text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              {t("reports.searching")}
            </div>
          ) : results.length > 0 ? (
            results.map((r) => (
              <button
                key={r.id}
                onMouseDown={(e) => { e.preventDefault(); handleSelect(r.symbol); }}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/[0.05] transition-colors text-left border-b border-white/[0.03] last:border-0"
              >
                <div className="flex items-center gap-2.5">
                  <span className="font-mono text-xs text-primary-400 bg-primary-500/10 px-1.5 py-0.5 rounded">{r.symbol}</span>
                  <span className="font-medium text-sm text-dark-text">{r.name}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                    r.market === "A_SHARE" ? "bg-blue-500/10 text-blue-400" : "bg-purple-500/10 text-purple-400"
                  }`}>
                    {r.market === "A_SHARE" ? t("market.aShare") : t("market.hk")}
                  </span>
                </div>
                {r.industry && <span className="text-xs text-dark-muted">{r.industry}</span>}
              </button>
            ))
          ) : (
            <div className="px-4 py-6 text-center text-dark-muted text-sm">{t("reports.noMatch")}</div>
          )}
        </div>
      )}
    </div>
  );
}
