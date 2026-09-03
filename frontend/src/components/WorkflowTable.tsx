import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import type { RecoveryWorkflow } from "../types/recovery";
import { StatusBadge } from "./StatusBadge";
import { RiskBadge } from "./RiskBadge";
import { ActionBadge } from "./ActionBadge";
import { EmptyState } from "./EmptyState";
import { displayId, FAILURE_LABELS, label } from "../utils/labels";

interface WorkflowTableProps {
  workflows: RecoveryWorkflow[];
  compact?: boolean;
}

export function WorkflowTable({ workflows, compact = false }: WorkflowTableProps) {
  if (workflows.length === 0) {
    return (
      <EmptyState
        title="No cases to display"
        description="Adjust your filters or analyze a failed payment to create a recovery case."
      />
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-surface-border bg-surface-raised shadow-card">
      <table className="min-w-full">
        <thead>
          <tr className="border-b border-surface-border bg-surface-overlay">
            <th className="px-5 py-3 text-left text-[10px] font-semibold text-text-subtle uppercase tracking-widest">Case</th>
            <th className="px-5 py-3 text-left text-[10px] font-semibold text-text-subtle uppercase tracking-widest">Payment</th>
            <th className="px-5 py-3 text-left text-[10px] font-semibold text-text-subtle uppercase tracking-widest">Recovery</th>
            {!compact && (
              <th className="px-5 py-3 text-left text-[10px] font-semibold text-text-subtle uppercase tracking-widest">
                Risk &amp; Action
              </th>
            )}
            <th className="px-5 py-3 text-left text-[10px] font-semibold text-text-subtle uppercase tracking-widest">Status</th>
            <th className="px-5 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-border">
          {workflows.map((wf) => (
            <tr
              key={wf.recovery_id}
              className="hover:bg-surface-hover transition-colors group"
            >
              {/* Case ID */}
              <td className="px-5 py-4 whitespace-nowrap">
                <div className="flex flex-col">
                  <span className="text-sm font-semibold text-text-primary font-mono">
                    {displayId(wf.recovery_id)}
                  </span>
                  <span className="text-[10px] text-text-subtle mt-0.5">
                    {new Date(wf.created_at).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "short",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
              </td>

              {/* Payment details */}
              <td className="px-5 py-4 whitespace-nowrap">
                <div className="flex flex-col">
                  <span className="text-sm font-semibold text-text-primary">
                    ₹{wf.amount.toLocaleString("en-IN")}
                  </span>
                  <span className="text-[11px] text-text-muted mt-0.5">
                    {label(FAILURE_LABELS, wf.failure_code)}
                  </span>
                </div>
              </td>

              {/* Recovery score */}
              <td className="px-5 py-4 whitespace-nowrap">
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-bold text-accent">
                    {Math.round(wf.recovery_probability * 100)}%
                  </span>
                  <span className="text-[10px] text-text-muted">
                    ₹{wf.expected_recovery_value.toLocaleString("en-IN", { maximumFractionDigits: 0 })} expected
                  </span>
                </div>
              </td>

              {/* Risk & Action */}
              {!compact && (
                <td className="px-5 py-4 whitespace-nowrap">
                  <div className="flex flex-col items-start gap-1.5">
                    <RiskBadge tier={wf.risk_tier} />
                    <ActionBadge action={wf.recommended_action} />
                  </div>
                </td>
              )}

              {/* Status */}
              <td className="px-5 py-4 whitespace-nowrap">
                <div className="flex flex-col items-start gap-1">
                  <StatusBadge status={wf.status} />
                  <span className="text-[10px] text-text-subtle">
                    {wf.attempt_count}/{wf.max_attempts} attempts
                  </span>
                </div>
              </td>

              {/* Action */}
              <td className="px-5 py-4 whitespace-nowrap text-right">
                <Link
                  to={`/recovery/${wf.recovery_id}`}
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-accent border border-accent-border bg-accent-light opacity-0 group-hover:opacity-100 focus:opacity-100 hover:bg-blue-100 transition-all"
                  aria-label={`Open case ${displayId(wf.recovery_id)}`}
                >
                  View
                  <ArrowUpRight className="w-3 h-3" />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
