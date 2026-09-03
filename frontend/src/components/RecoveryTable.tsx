
import { Link } from "react-router-dom";
import type { RecoveryWorkflow } from "../types/recovery";
import { StatusBadge } from "./StatusBadge";
import { RiskBadge } from "./RiskBadge";
import { ActionBadge } from "./ActionBadge";
import { EmptyState } from "./EmptyState";

export function RecoveryTable({ workflows }: { workflows: RecoveryWorkflow[] }) {
  if (workflows.length === 0) return <EmptyState />;

  return (
    <div className="overflow-x-auto border border-surface-border rounded-lg">
      <table className="min-w-full">
        <thead>
          <tr className="border-b border-surface-border">
            <th className="px-5 py-3 text-left text-[11px] font-medium text-gray-500 uppercase tracking-wider">Recovery ID</th>
            <th className="px-5 py-3 text-left text-[11px] font-medium text-gray-500 uppercase tracking-wider">Amount</th>
            <th className="px-5 py-3 text-left text-[11px] font-medium text-gray-500 uppercase tracking-wider">Prob.</th>
            <th className="px-5 py-3 text-left text-[11px] font-medium text-gray-500 uppercase tracking-wider">Tier</th>
            <th className="px-5 py-3 text-left text-[11px] font-medium text-gray-500 uppercase tracking-wider">Action</th>
            <th className="px-5 py-3 text-left text-[11px] font-medium text-gray-500 uppercase tracking-wider">Status</th>
            <th className="px-5 py-3 text-center text-[11px] font-medium text-gray-500 uppercase tracking-wider">Attempts</th>
          </tr>
        </thead>
        <tbody>
          {workflows.map((wf) => (
            <tr key={wf.recovery_id} className="border-b border-surface-border last:border-b-0 hover:bg-white/[0.02] transition-colors">
              <td className="px-5 py-3.5 whitespace-nowrap text-sm font-medium">
                <Link to={`/recovery/${wf.recovery_id}`} className="text-accent hover:text-accent/80 transition-colors">
                  {wf.recovery_id.split("-")[0]}...
                </Link>
              </td>
              <td className="px-5 py-3.5 whitespace-nowrap text-sm text-gray-200">
                ₹{wf.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                <div className="text-[11px] text-gray-500 mt-0.5 font-mono">{wf.failure_code}</div>
              </td>
              <td className="px-5 py-3.5 whitespace-nowrap text-sm text-accent font-medium">
                {Math.round(wf.recovery_probability * 100)}%
              </td>
              <td className="px-5 py-3.5 whitespace-nowrap text-sm">
                <RiskBadge tier={wf.risk_tier} />
              </td>
              <td className="px-5 py-3.5 whitespace-nowrap text-sm">
                <ActionBadge action={wf.recommended_action} />
              </td>
              <td className="px-5 py-3.5 whitespace-nowrap text-sm">
                <StatusBadge status={wf.status} />
              </td>
              <td className="px-5 py-3.5 whitespace-nowrap text-sm text-gray-500 text-center">
                {wf.attempt_count} / {wf.max_attempts}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
