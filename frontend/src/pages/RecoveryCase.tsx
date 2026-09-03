import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Clock,
  PlayCircle,
  Lock,
} from "lucide-react";
import { Layout } from "../components/Layout";
import { StatusBadge } from "../components/StatusBadge";
import { RiskBadge } from "../components/RiskBadge";
import { ActionBadge } from "../components/ActionBadge";
import { ProbabilityGauge } from "../components/ProbabilityGauge";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import type { RecoveryWorkflow } from "../types/recovery";
import { WorkflowStatusEnum } from "../types/recovery";
import { api } from "../services/api";
import { displayId, FAILURE_LABELS, ACTION_LABELS, label } from "../utils/labels";

export function RecoveryCase() {
  const { id } = useParams<{ id: string }>();
  const [workflow, setWorkflow] = useState<RecoveryWorkflow | null>(null);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [execMessage, setExecMessage] = useState<{ success: boolean; text: string } | null>(null);

  useEffect(() => {
    if (!id) return;
    api
      .getRecoveryWorkflow(id)
      .then(setWorkflow)
      .catch((err) => setError(err.message ?? "Failed to load case"))
      .finally(() => setLoading(false));
  }, [id]);

  const handleExecute = async () => {
    if (!workflow || !id) return;
    setExecuting(true);
    setExecMessage(null);
    try {
      const res = await api.executeRecovery(id);
      setExecMessage({ success: res.success, text: res.message });
      const updated = await api.getRecoveryWorkflow(id);
      setWorkflow(updated);
    } catch (err: any) {
      setExecMessage({ success: false, text: err.message ?? "Execution failed." });
    } finally {
      setExecuting(false);
    }
  };

  if (loading) return <Layout><LoadingState message="Loading case details..." /></Layout>;

  if (error || !workflow) {
    return (
      <Layout>
        <ErrorState message={error ?? "Case not found"} />
        <div className="text-center mt-4">
          <Link to="/" className="text-sm text-accent hover:underline">Return to home</Link>
        </div>
      </Layout>
    );
  }

  const isFraud = workflow.failure_code === "FRAUD_CHECK";
  const isEscalated = workflow.status === "ESCALATED";
  const isBlocked = workflow.status === "BLOCKED";
  const canExecute =
    [WorkflowStatusEnum.PENDING, WorkflowStatusEnum.EXECUTING].includes(workflow.status as any) &&
    workflow.attempt_count < workflow.max_attempts &&
    !isFraud;

  const attemptPercent = Math.min(100, (workflow.attempt_count / workflow.max_attempts) * 100);

  return (
    <Layout>
      {/* Breadcrumb / back nav */}
      <div className="mb-6 animate-fade-in">
        <Link
          to={-1 as any}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-text-muted hover:text-accent transition-colors mb-4"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back
        </Link>

        <div className="flex flex-wrap justify-between items-start gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold text-text-primary tracking-tight">
                {displayId(workflow.recovery_id)}
              </h1>
              <StatusBadge status={workflow.status} />
            </div>
            <p className="text-sm text-text-muted mt-1">
              Created {new Date(workflow.created_at).toLocaleString("en-IN")}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 animate-slide-up">
        {/* Left: Details */}
        <div className="lg:col-span-2 space-y-5">
          {/* Payment details */}
          <div className="bg-white border border-surface-border rounded-xl p-6 shadow-card">
            <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-5">Payment details</h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              <div>
                <p className="text-xs text-text-muted mb-1">Original amount</p>
                <p className="text-2xl font-bold text-text-primary">
                  ₹{workflow.amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </p>
              </div>
              <div>
                <p className="text-xs text-text-muted mb-1">Expected recovery</p>
                <p className="text-2xl font-bold text-accent">
                  ₹{workflow.expected_recovery_value.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </p>
              </div>
              <div>
                <p className="text-xs text-text-muted mb-1">Failure reason</p>
                <p className="text-sm font-semibold text-text-secondary mt-1.5">
                  {label(FAILURE_LABELS, workflow.failure_code)}
                </p>
                <p className="text-[10px] text-text-subtle font-mono">{workflow.failure_code}</p>
              </div>
            </div>
          </div>

          {/* Recovery assessment */}
          <div className="bg-white border border-surface-border rounded-xl p-6 shadow-card">
            <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-5">Recovery assessment</h2>
            <div className="space-y-6">
              <ProbabilityGauge probability={workflow.recovery_probability} />

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div>
                  <p className="text-xs text-text-muted mb-2">Risk level</p>
                  <RiskBadge tier={workflow.risk_tier} />
                </div>
                <div>
                  <p className="text-xs text-text-muted mb-2">Recommended action</p>
                  <ActionBadge action={workflow.recommended_action} />
                </div>
              </div>

              <div>
                <p className="text-xs font-medium text-text-muted mb-2">Analysis</p>
                <div className="bg-surface-overlay border border-surface-border rounded-xl p-4">
                  <p className="text-sm text-text-secondary leading-relaxed">{workflow.reason}</p>
                </div>
              </div>

              <p className="text-[10px] text-text-subtle font-mono">
                Model: {workflow.model_version}
              </p>
            </div>
          </div>
        </div>

        {/* Right: Execution */}
        <div className="space-y-5">
          <div className="bg-white border border-surface-border rounded-xl p-5 shadow-card">
            <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-5">Execution</h2>

            {/* Attempt progress */}
            <div className="mb-5">
              <div className="flex justify-between items-center mb-1.5">
                <span className="text-xs text-text-muted">Attempts used</span>
                <span className="text-xs font-semibold text-text-primary bg-surface-overlay border border-surface-border px-2 py-0.5 rounded">
                  {workflow.attempt_count} / {workflow.max_attempts}
                </span>
              </div>
              <div className="w-full bg-surface-overlay rounded-full h-1.5 border border-surface-border overflow-hidden">
                <div
                  className={`h-1.5 rounded-full transition-all duration-500 ${
                    attemptPercent >= 100 ? "bg-red-400" : "bg-accent"
                  }`}
                  style={{ width: `${attemptPercent}%` }}
                />
              </div>
            </div>

            {/* Execution area */}
            {isFraud || isEscalated ? (
              <div className="p-4 bg-orange-50 border border-orange-200 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <ShieldAlert className="w-4 h-4 text-orange-500 flex-shrink-0" />
                  <span className="text-sm font-semibold text-orange-800">Manual review required</span>
                </div>
                <p className="text-xs text-orange-700 leading-relaxed">
                  {isFraud
                    ? "Fraud-related failures cannot be automatically recovered. This case requires escalation to the risk team."
                    : "This case has been escalated for human review before any recovery action can proceed."}
                </p>
              </div>
            ) : isBlocked ? (
              <div className="p-4 bg-surface-overlay border border-surface-border rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <Lock className="w-4 h-4 text-text-muted flex-shrink-0" />
                  <span className="text-sm font-semibold text-text-secondary">Retry limit reached</span>
                </div>
                <p className="text-xs text-text-muted">
                  This case has exhausted its maximum automated retries ({workflow.max_attempts}). Manual intervention may be required.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {/* Recommended action summary */}
                <div className="p-4 bg-accent-light border border-accent-border rounded-xl">
                  <p className="text-[10px] font-semibold text-accent uppercase tracking-wide mb-1">Recommended action</p>
                  <p className="text-sm font-bold text-accent">{label(ACTION_LABELS, workflow.recommended_action) ?? workflow.recommended_action}</p>
                  <p className="text-xs text-accent/80 mt-1">Expected: ₹{workflow.expected_recovery_value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}</p>
                </div>

                {canExecute ? (
                  <button
                    onClick={handleExecute}
                    disabled={executing}
                    className={`w-full py-3 px-4 rounded-xl text-sm font-semibold transition-all flex items-center justify-center gap-2 ${
                      executing
                        ? "bg-accent/50 text-white cursor-not-allowed"
                        : "bg-accent text-white hover:bg-accent-hover shadow-btn"
                    }`}
                  >
                    {executing ? (
                      <>
                        <div className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Executing...
                      </>
                    ) : (
                      <>
                        <PlayCircle className="w-4 h-4" />
                        Execute recovery
                      </>
                    )}
                  </button>
                ) : (
                  <div className="flex items-center justify-center gap-2 py-3 px-4 bg-surface-overlay border border-surface-border rounded-xl text-sm text-text-muted">
                    {workflow.status === "COMPLETED" ? (
                      <><CheckCircle2 className="w-4 h-4 text-emerald-500" /> Recovery completed</>
                    ) : workflow.status === "FAILED" ? (
                      <><XCircle className="w-4 h-4 text-red-500" /> Recovery failed</>
                    ) : (
                      <><Clock className="w-4 h-4" /> Execution unavailable</>
                    )}
                  </div>
                )}

                <div className="text-center pt-1">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-700 text-[10px] font-semibold">
                    Simulation mode · no real payment processed
                  </span>
                </div>
              </div>
            )}

            {/* Execution result message */}
            {execMessage && (
              <div className={`mt-4 p-4 rounded-xl text-sm font-medium border animate-fade-in ${
                execMessage.success
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : "bg-red-50 text-red-700 border-red-200"
              }`}>
                {execMessage.success ? (
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                    {execMessage.text}
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <XCircle className="w-4 h-4 flex-shrink-0" />
                    {execMessage.text}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Execution log */}
          {workflow.execution_result && (
            <div className="bg-white border border-surface-border rounded-xl shadow-card overflow-hidden">
              <div className="px-5 py-3.5 border-b border-surface-border">
                <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wide">Execution log</h2>
              </div>
              <div className="p-4 overflow-auto">
                <pre className="text-[11px] font-mono text-text-secondary whitespace-pre-wrap leading-relaxed">
                  {JSON.stringify(workflow.execution_result, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
