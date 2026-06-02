"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { searchStocks } from "@/lib/api";
import type { StockSearchResult } from "@/types";
import { useTranslation } from "@/lib/i18n";
import { Search } from "lucide-react";

export default function TopSearch() {
  const { t } = useTranslation();
  const [keyword, setKeyword] = useState("");
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const router = useRouter();

  const handleSearch = useCallback(async (value: string) => {
    setKeyword(value);
    if (value.length < 1) {
      setResults([]);
      setShowDropdown(false);
      return;
    }
    try {
      const data = await searchStocks(value);
      setResults(data);
      setShowDropdown(true);
    } catch {
      setResults([]);
    }
  }, []);

  const handleSelect = (symbol: string) => {
    setShowDropdown(false);
    setKeyword("");
    router.push(`/stocks/${symbol}`);
  };

  return (
    <div className="relative">
      <div className="relative">
        <input
          type="text"
          value={keyword}
          onChange={(e) => handleSearch(e.target.value)}
          onFocus={() => results.length > 0 && setShowDropdown(true)}
          onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
          placeholder={t("reports.stockSearch") + "（A股+港股）..."}
          className="w-full pl-10 pr-4 py-2.5 bg-white/[0.05] border border-white/[0.08] rounded-xl text-sm text-dark-text placeholder:text-dark-muted/50 focus:outline-none focus:ring-2 focus:ring-primary-500/40 focus:border-primary-500/30 backdrop-blur-xl"
        />
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-muted" />

        {showDropdown && results.length > 0 && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-dark-card rounded-xl shadow-2xl border border-white/[0.08] overflow-hidden z-50 max-h-80 overflow-y-auto backdrop-blur-xl">
            {results.map((r) => (
              <button
                key={r.id}
                onClick={() => handleSelect(r.symbol)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/[0.05] transition-colors text-left border-b border-white/[0.03] last:border-0"
              >
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm text-dark-text">{r.name}</span>
                  <span className="text-xs font-mono text-dark-muted">{r.symbol}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                    r.market === "A_SHARE" ? "bg-blue-500/10 text-blue-400" : "bg-purple-500/10 text-purple-400"
                  }`}>
                    {r.market === "A_SHARE" ? t("market.aShare") : t("market.hk")}
                  </span>
                </div>
                <span className="text-xs text-dark-muted">{r.industry}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
