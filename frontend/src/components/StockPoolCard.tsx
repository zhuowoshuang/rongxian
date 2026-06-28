"use client";

import { useRouter } from "next/navigation";
import type { StockPoolItem } from "@/types";
import { ratingClass, signalTypeLabel } from "@/lib/utils";
import { useTranslation } from "@/lib/i18n";
import GlassCard from "@/components/ui/GlassCard";

interface Props {
  title: string;
  type: string;
  items: StockPoolItem[];
}

export default function StockPoolCard({ title, type, items }: Props) {
  const router = useRouter();
  const { t } = useTranslation();

  const typeColors: Record<string, string> = {
    quality: "border-l-emerald-500",
    undervalued: "border-l-blue-500",
    trend: "border-l-purple-500",
    risk: "border-l-red-500",
  };

  return (
    <GlassCard className={`border-l-4 ${typeColors[type] || "border-l-gray-500"}`}>
      <h4 className="text-sm font-semibold text-white mb-3">{title}</h4>
      {items.length === 0 ? (
        <p className="text-xs text-dark-muted">{t("pool.noData")}</p>
      ) : (
        <div className="space-y-2">
          {items.slice(0, 5).map((item) => (
            <button
              key={item.symbol}
              onClick={() => router.push(`/stocks/${item.symbol}`)}
              className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-white/[0.05] transition-colors text-left"
            >
              <div>
                <span className="text-sm font-medium text-dark-text">{item.name}</span>
                <span className="ml-1 text-[10px] text-dark-muted font-mono">{item.symbol}</span>
              </div>
              <div className="flex items-center gap-2">
                {item.score && (
                  <span className="text-xs font-bold text-primary-400 font-mono">{item.score.toFixed(0)}</span>
                )}
                {item.rating && (
                  <span className={`${ratingClass(item.rating)} !px-2 !py-0 !text-[10px]`}>{signalTypeLabel(item.rating)}</span>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </GlassCard>
  );
}
