"use client";

type Tone = "live" | "database" | "third-party" | "simulated" | "pending" | "warning";

const toneClass: Record<Tone, string> = {
  live: "bg-emerald-50 text-emerald-700 border-emerald-200",
  database: "bg-blue-50 text-blue-700 border-blue-200",
  "third-party": "bg-cyan-50 text-cyan-700 border-cyan-200",
  simulated: "bg-amber-50 text-amber-700 border-amber-200",
  pending: "bg-gray-100 text-gray-600 border-gray-200",
  warning: "bg-red-50 text-red-700 border-red-200",
};

export default function DataStatusBadge({ label, tone = "database" }: { label: string; tone?: Tone }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${toneClass[tone]}`}>
      {label}
    </span>
  );
}
