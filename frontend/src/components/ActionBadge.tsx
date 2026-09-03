import { ACTION_LABELS, label } from "../utils/labels";

export function ActionBadge({ action }: { action: string }) {
  const isEscalation = action === "ESCALATE_MANUAL_REVIEW";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium border ${
      isEscalation
        ? "text-orange-700 bg-orange-50 border-orange-200"
        : "text-text-secondary bg-surface-overlay border-surface-border"
    }`}>
      {label(ACTION_LABELS, action)}
    </span>
  );
}
