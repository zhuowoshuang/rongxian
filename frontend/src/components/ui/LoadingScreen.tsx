"use client";

import { useTranslation } from "@/lib/i18n";

export default function LoadingScreen() {
  const { t } = useTranslation();

  return (
    <div className="fixed inset-0 bg-dark-bg flex items-center justify-center z-50">
      <div className="flex flex-col items-center gap-4">
        <div className="relative">
          <div className="w-12 h-12 border-2 border-primary-500/20 rounded-full" />
          <div className="absolute inset-0 w-12 h-12 border-2 border-transparent border-t-primary-500 rounded-full animate-spin" />
        </div>
        <span className="text-sm text-dark-muted">{t("common.loading")}</span>
        <button
          onClick={() => { localStorage.clear(); location.reload(); }}
          className="mt-4 px-4 py-2 text-xs text-dark-muted border border-white/10 rounded-lg hover:bg-white/5"
        >
          {t("common.clearCache")}
        </button>
      </div>
    </div>
  );
}
