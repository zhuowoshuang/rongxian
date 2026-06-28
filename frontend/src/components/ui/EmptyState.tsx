import { InboxIcon } from "lucide-react";

interface Props {
  message?: string;
  description?: string;
}

export default function EmptyState({ message = "暂无数据", description }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-16 h-16 rounded-2xl bg-[var(--bg-surface)] flex items-center justify-center mb-4">
        <InboxIcon className="w-8 h-8 text-[var(--text-muted)]" />
      </div>
      <p className="text-sm text-[var(--text-secondary)]">{message}</p>
      {description && <p className="text-xs text-[var(--text-muted)] mt-1">{description}</p>}
    </div>
  );
}
