"use client";

import { cn, getChangeColor } from "@/lib/utils";

interface Props {
  value: number | null | undefined;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  showSign?: boolean;
  className?: string;
  size?: "sm" | "md" | "lg" | "xl";
}

export default function NumberDisplay({
  value,
  decimals = 2,
  prefix,
  suffix,
  showSign = false,
  className,
  size = "md",
}: Props) {
  if (value === null || value === undefined) {
    return <span className={cn("text-dark-muted font-mono", className)}>--</span>;
  }

  const formatted = value.toFixed(decimals);
  const sign = showSign && value > 0 ? "+" : "";
  const colorClass = showSign ? getChangeColor(value) : "";

  const sizeClasses = {
    sm: "text-xs",
    md: "text-sm",
    lg: "text-lg",
    xl: "text-2xl",
  };

  return (
    <span className={cn("font-mono tabular-nums", sizeClasses[size], colorClass, className)}>
      {prefix}{sign}{formatted}{suffix}
    </span>
  );
}
