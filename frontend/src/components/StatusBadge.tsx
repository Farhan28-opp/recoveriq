import { STATUS_LABELS, label } from "../utils/labels";

const statusStyles: Record<string, string> = {
  PENDING:   "text-blue-700 bg-blue-50 border-blue-200",
  EXECUTING: "text-amber-700 bg-amber-50 border-amber-200",
  COMPLETED: "text-emerald-700 bg-emerald-50 border-emerald-200",
  FAILED:    "text-red-700 bg-red-50 border-red-200",
  BLOCKED:   "text-orange-700 bg-orange-50 border-orange-200",
  ESCALATED: "text-orange-800 bg-orange-50 border-orange-300",
};

export function StatusBadge({ status }: { status: string }) {
  const style = statusStyles[status] ?? "text-gray-600 bg-gray-50 border-gray-200";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border ${style}`}>
      {label(STATUS_LABELS, status)}
    </span>
  );
}
