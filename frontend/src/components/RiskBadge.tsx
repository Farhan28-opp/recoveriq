import { RISK_LABELS, label } from "../utils/labels";

const tierStyles: Record<string, string> = {
  HIGH:   "text-emerald-700 bg-emerald-50 border-emerald-200",
  MEDIUM: "text-amber-700 bg-amber-50 border-amber-200",
  LOW:    "text-red-700 bg-red-50 border-red-200",
};

export function RiskBadge({ tier }: { tier: string }) {
  const style = tierStyles[tier] ?? "text-gray-600 bg-gray-50 border-gray-200";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border ${style}`}>
      {label(RISK_LABELS, tier)} risk
    </span>
  );
}
