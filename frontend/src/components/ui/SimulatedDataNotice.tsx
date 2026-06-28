"use client";

import DataStatusBadge from "@/components/ui/DataStatusBadge";

export default function SimulatedDataNotice({
  title,
  lines,
  badges = [],
}: {
  title: string;
  lines: string[];
  badges?: Array<{ label: string; tone?: "live" | "database" | "third-party" | "simulated" | "pending" | "warning" }>;
}) {
  return (
    <div className="card-info">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <DataStatusBadge label={title} tone="simulated" />
        {badges.map((badge) => (
          <DataStatusBadge key={badge.label} label={badge.label} tone={badge.tone} />
        ))}
      </div>
      <div className="space-y-1 text-xs leading-5 opacity-80">
        {lines.map((line) => (
          <p key={line}>{line}</p>
        ))}
      </div>
    </div>
  );
}
