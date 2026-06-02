import { signalTypeLabel, signalTypeClass } from "@/lib/utils";

interface Props {
  type: string;
  size?: "sm" | "md";
}

export default function SignalBadge({ type, size = "md" }: Props) {
  const glowColors: Record<string, string> = {
    BUY: "shadow-[0_0_8px_rgba(16,185,129,0.3)]",
    ADD: "shadow-[0_0_8px_rgba(59,130,246,0.3)]",
    WATCH: "shadow-[0_0_8px_rgba(245,158,11,0.3)]",
    REDUCE: "shadow-[0_0_8px_rgba(249,115,22,0.3)]",
    SELL: "shadow-[0_0_8px_rgba(239,68,68,0.3)]",
  };

  return (
    <span className={`${signalTypeClass(type)} ${glowColors[type] || ""} ${size === "sm" ? "!text-[10px] !px-1.5 !py-0.5" : ""}`}>
      {signalTypeLabel(type)}
    </span>
  );
}
