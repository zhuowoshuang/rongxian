"use client";

interface TooltipPayloadItem {
  name: string;
  value: number | string;
  color: string;
}

interface ChartTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
}

export default function ChartTooltip({ active, payload, label }: ChartTooltipProps) {
  if (active && payload?.length) {
    return (
      <div className="bg-dark-card border border-white/10 rounded-lg px-3 py-2 shadow-xl backdrop-blur-xl">
        <p className="text-xs text-dark-muted mb-1">{label}</p>
        {payload.map((p, i) => (
          <p key={i} className="text-sm" style={{ color: p.color }}>
            {p.name}: <span className="font-mono font-bold">{typeof p.value === "number" ? p.value.toFixed(2) : p.value}</span>
          </p>
        ))}
      </div>
    );
  }
  return null;
}
