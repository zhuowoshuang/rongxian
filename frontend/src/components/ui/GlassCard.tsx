"use client";

import { cn } from "@/lib/utils";

interface Props {
  children: React.ReactNode;
  className?: string;
  title?: string;
  action?: React.ReactNode;
  glow?: boolean;
}

export default function GlassCard({ children, className, title, action, glow }: Props) {
  return (
    <div className={cn(glow ? "card-glow" : "card", className)}>
      {(title || action) && (
        <div className="flex items-center justify-between mb-4">
          {title && (
            <h3 className="text-sm font-semibold text-dark-muted dark:text-dark-muted flex items-center gap-2">
              <span className="w-1 h-4 bg-primary-500 rounded-full" />
              {title}
            </h3>
          )}
          {action}
        </div>
      )}
      {children}
    </div>
  );
}
