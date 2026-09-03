import { Inbox } from "lucide-react";
import type { ReactNode } from "react";

interface EmptyStateProps {
  title?: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({
  title = "No records found",
  description = "Nothing to display here yet.",
  action,
}: EmptyStateProps) {
  return (
    <div className="text-center py-16 px-4 border border-dashed border-surface-border rounded-xl bg-surface-raised">
      <Inbox className="mx-auto h-8 w-8 text-text-subtle mb-3" />
      <p className="text-sm font-medium text-text-secondary">{title}</p>
      <p className="mt-1 text-xs text-text-muted">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
