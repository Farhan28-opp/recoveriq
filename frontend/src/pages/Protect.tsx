import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ShieldAlert, Lock, AlertTriangle, ArrowUpRight } from "lucide-react";
import { Layout } from "../components/Layout";
import { PageHeader } from "../components/PageHeader";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";
import { api } from "../services/api";
import type { RecoveryWorkflow } from "../types/recovery";
import { displayId, FAILURE_LABELS, label } from "../utils/labels";

export function Protect() {
  const [workflows, setWorkflows] = useState<RecoveryWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getRecoveryWorkflows()
      .then((data) => {
        const protected_ = data
          .filter(
            (w) =>
              w.status === "ESCALATED" ||
              w.status === "BLOCKED" ||
              w.failure_code === "FRAUD_CHECK" ||
              w.recommended_action === "ESCALATE_MANUAL_REVIEW"
          )
          .sort((a, b) => {
            // Escalated first, then blocked
            const priority: Record<string, number> = { ESCALATED: 0, BLOCKED: 1, COMPLETED: 2, FAILED: 3 };
            return (priority[a.status] ?? 9) - (priority[b.status] ?? 9);
          });
        setWorkflows(protected_);
      })
      .catch((err) => setError(err.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  const escalated = workflows.filter((w) => w.status === "ESCALATED");
  const blocked = workflows.filter((w) => w.status === "BLOCKED");
  const fraud = workflows.filter((w) => w.failure_code === "FRAUD_CHECK");

  return (
    <Layout>
      <PageHeader
        title="Risk control"
        description="Cases requiring manual attention. Recovery intelligence does not override safety."
      />

      {loading ? (
        <LoadingState message="Loading safety controls..." />
      ) : error ? (
        <ErrorState message={error} onRetry={() => window.location.reload()} />
      ) : (
        <div className="space-y-6 animate-fade-in">
          {/* Safety policy notice */}
          <div className="flex items-start gap-3.5 p-4 bg-orange-50 border border-orange-200 rounded-xl">
            <ShieldAlert className="w-5 h-5 text-orange-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-orange-800">Safety-first policy</p>
              <p className="text-xs text-orange-700 mt-0.5">
                Recovery intelligence does not override risk controls. Cases involving fraud signals,
                maximum retry limits, or manual escalation cannot be automatically executed.
              </p>
            </div>
          </div>

          {/* Summary stats */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-4 bg-white border border-orange-200 rounded-xl shadow-card">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="w-4 h-4 text-orange-500" />
                <p className="text-xs font-semibold text-orange-700">Escalated</p>
              </div>
              <p className="text-2xl font-bold text-text-primary">{escalated.length}</p>
              <p className="text-[11px] text-text-muted mt-0.5">Pending manual review</p>
            </div>
            <div className="p-4 bg-white border border-surface-border rounded-xl shadow-card">
              <div className="flex items-center gap-2 mb-2">
                <Lock className="w-4 h-4 text-text-muted" />
                <p className="text-xs font-semibold text-text-muted">Blocked</p>
              </div>
              <p className="text-2xl font-bold text-text-primary">{blocked.length}</p>
              <p className="text-[11px] text-text-muted mt-0.5">Retry limit reached</p>
            </div>
            <div className="p-4 bg-white border border-red-200 rounded-xl shadow-card">
              <div className="flex items-center gap-2 mb-2">
                <ShieldAlert className="w-4 h-4 text-red-500" />
                <p className="text-xs font-semibold text-red-700">Fraud signals</p>
              </div>
              <p className="text-2xl font-bold text-text-primary">{fraud.length}</p>
              <p className="text-[11px] text-text-muted mt-0.5">Fraud check failures</p>
            </div>
          </div>

          {/* Case list */}
          {workflows.length === 0 ? (
            <div className="bg-white border border-surface-border rounded-xl p-8 text-center shadow-card">
              <ShieldAlert className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
              <p className="text-sm font-medium text-text-secondary">No cases requiring attention</p>
              <p className="text-xs text-text-muted mt-1">All safety controls are clear.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {workflows.map((wf) => {
                const isFraud = wf.failure_code === "FRAUD_CHECK";
                const isBlocked = wf.status === "BLOCKED";
                return (
                  <div
                    key={wf.recovery_id}
                    className={`bg-white border rounded-xl shadow-card p-5 ${
                      isFraud ? "border-red-200" : isBlocked ? "border-orange-200" : "border-surface-border"
                    }`}
                  >
                    <div className="flex flex-wrap justify-between items-start gap-4">
                      <div>
                        <div className="flex items-center gap-2.5 mb-1.5">
                          <span className="text-sm font-semibold text-text-primary font-mono">
                            {displayId(wf.recovery_id)}
                          </span>
                          <StatusBadge status={wf.status} />
                        </div>
                        <p className="text-xs text-text-muted">
                          {label(FAILURE_LABELS, wf.failure_code)} · ₹{wf.amount.toLocaleString("en-IN")}
                          · {wf.attempt_count}/{wf.max_attempts} attempts
                        </p>
                      </div>
                      <Link
                        to={`/recovery/${wf.recovery_id}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-text-muted border border-surface-border rounded-lg hover:text-accent hover:border-accent-border hover:bg-accent-light transition-all"
                      >
                        View <ArrowUpRight className="w-3 h-3" />
                      </Link>
                    </div>

                    {/* Reason for protection */}
                    <div className={`mt-3 pt-3 border-t border-surface-border text-xs rounded-lg`}>
                      {isFraud && (
                        <p className="text-red-600">
                          <span className="font-semibold">Fraud signal detected.</span>{" "}
                          Automatic execution is blocked. Manual investigation required before any recovery action.
                        </p>
                      )}
                      {isBlocked && !isFraud && (
                        <p className="text-orange-700">
                          <span className="font-semibold">Maximum retry limit reached.</span>{" "}
                          This case has exhausted automated retries. Manual intervention may be required.
                        </p>
                      )}
                      {wf.status === "ESCALATED" && !isFraud && (
                        <p className="text-orange-700">
                          <span className="font-semibold">Escalated for manual review.</span>{" "}
                          Recovery intelligence flagged this case for human decision.
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </Layout>
  );
}
