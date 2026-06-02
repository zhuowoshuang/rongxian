"use client";

import { cn } from "@/lib/utils";

interface Tab {
  key: string;
  label: string;
  count?: number;
}

interface Props {
  tabs: Tab[];
  active: string;
  onChange: (key: string) => void;
  className?: string;
}

export default function TabSwitch({ tabs, active, onChange, className }: Props) {
  return (
    <div className={cn("flex gap-1 p-1 rounded-xl bg-white/[0.03] border border-white/[0.06]", className)}>
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={cn(
            "flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all",
            active === tab.key
              ? "bg-primary-500/20 text-primary-400 border border-primary-500/30"
              : "text-dark-muted hover:text-dark-text hover:bg-white/[0.05]"
          )}
        >
          {tab.label}
          {tab.count !== undefined && (
            <span className={cn(
              "ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full",
              active === tab.key ? "bg-primary-500/20 text-primary-400" : "bg-white/5 text-dark-muted"
            )}>
              {tab.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
