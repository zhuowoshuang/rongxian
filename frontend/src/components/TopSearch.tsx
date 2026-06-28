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
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)] pointer-events-none" />
        <input
          type="text"
          value={keyword}
          onChange={(e) => handleSearch(e.target.value)}
          onFocus={() => { if (results.length > 0) setShowDropdown(true); }}
          placeholder={t("common.searchPlaceholder")}
          className="w-full search-input"
        />
        {keyword && (
          <button onClick={handleClear} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {showDropdown && (
        <div className="absolute top-full left-0 right-0 mt-1.5 card shadow-lg z-50 max-h-80 overflow-y-auto !p-0">
          {searching ? (
            <div className="flex items-center justify-center gap-2 px-4 py-6 text-[var(--text-muted)] text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              {t("reports.searching")}
            </div>
          ) : results.length > 0 ? (
            results.map((r) => (
              <button
                key={r.id}
                onMouseDown={(e) => { e.preventDefault(); handleSelect(r.symbol); }}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-[var(--bg-surface)] transition-colors text-left border-b border-[var(--border-light)] last:border-0"
              >
                <div className="flex items-center gap-2.5">
                  <span className="font-mono text-xs text-primary-600 bg-primary-50 px-1.5 py-0.5 rounded font-semibold">{r.symbol}</span>
                  <span className="font-medium text-sm text-[var(--text-primary)]">{r.name}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                    r.market === "A_SHARE" ? "bg-blue-50 text-blue-700" : "bg-purple-50 text-purple-700"
                  }`}>
                    {r.market === "A_SHARE" ? t("market.aShare") : t("market.hk")}
                  </span>
                </div>
                {r.industry && <span className="text-xs text-[var(--text-muted)]">{r.industry}</span>}
              </button>
            ))
          ) : (
            <div className="px-4 py-6 text-center text-[var(--text-muted)] text-sm">{t("reports.noMatch")}</div>
          )}
        </div>
      )}
    </div>
  );
}
