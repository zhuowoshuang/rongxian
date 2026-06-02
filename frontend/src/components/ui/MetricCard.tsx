import { cn, getChangeColor } from "@/lib/utils";

interface Props {
  label: string;
  value: string | number;
  change?: number | null;
  suffix?: string;
  className?: string;
}

export default function MetricCard({ label, value, change, suffix, className }: Props) {
  return (
    <div className={cn("card-inner", className)}>
      <p className="text-[11px] text-dark-muted mb-1">{label}</p>
      <div className="flex items-baseline gap-1">
        <span className="text-lg font-bold font-mono text-dark-text">{value}</span>
        {suffix && <span className="text-xs text-dark-muted">{suffix}</span>}
      </div>
      {change !== null && change !== undefined && (
        <p className={`text-xs font-mono mt-1 ${getChangeColor(change)}`}>
          {change > 0 ? "+" : ""}{change.toFixed(2)}%
        </p>
      )}
    </div>
  );
}
