import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, XCircle, Clock, Lock, AlertTriangle, ArrowUpRight } from "lucide-react";
import { Layout } from "../components/Layout";
import { PageHeader } from "../components/PageHeader";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { api } from "../services/api";
import type { RecoveryWorkflow } from "../types/recovery";
import { displayId, ACTION_LABELS, FAILURE_LABELS, label } from "../utils/labels";

function getStatusIcon(status: string): React.JSX.Element {
  switch (status) {
    case "COMPLETED": return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />;
    case "FAILED": return <XCircle className="w-3.5 h-3.5 text-red-500" />;
    case "BLOCKED": return <Lock className="w-3.5 h-3.5 text-orange-500" />;
    case "ESCALATED": return <AlertTriangle className="w-3.5 h-3.5 text-orange-600" />;
    default: return <Clock className="w-3.5 h-3.5 text-text-muted" />;
  }
}

function getStatusBg(status: string): string {
  switch (status) {
    case "COMPLETED": return "bg-emerald-50 border-emerald-200";
    case "FAILED": return "bg-red-50 border-red-200";
    case "BLOCKED": return "bg-orange-50 border-orange-200";
    case "ESCALATED": return "bg-orange-50 border-orange-300";
    default: return "bg-surface-overlay border-surface-border";
  }
}

function TimelineEvent({
  icon,
  label: eventLabel,
  time,
  color = "bg-surface-overlay border-surface-border",
  iconColor = "text-text-muted",
}: {
  icon: React.JSX.Element;
  label: string;
  time?: string;
  color?: string;
  iconColor?: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className={`flex-shrink-0 w-7 h-7 rounded-full border flex items-center justify-center ${color}`}>
        <span className={`w-3.5 h-3.5 ${iconColor}`}>{icon}</span>
      </div>
      <div className="pt-0.5 pb-4">
        <p className="text-xs font-medium text-text-secondary">{eventLabel}</p>
        {time && <p className="text-[10px] text-text-subtle mt-0.5">{time}</p>}
      </div>
    </div>
  );
}

export function Track() {
  const [workflows, setWorkflows] = useState<RecoveryWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getRecoveryWorkflows()
      .then((data) => {
        const acted = data
          .filter((w) => w.status !== "PENDING" || w.attempt_count > 0)
          .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
        setWorkflows(acted);
      })
      .catch((err) => setError(err.message ?? "Failed to load history"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Layout>
      <PageHeader
        title="Recovery history"
        description="Audit trail of recovery executions, outcomes, and workflow events."
      />

      {loading ? (
        <LoadingState message="Loading history..." />
      ) : error ? (
        <ErrorState message={error} onRetry={() => window.location.reload()} />
      ) : workflows.length === 0 ? (
        <div className="text-center py-16 px-4 border border-dashed border-surface-border rounded-xl bg-white">
          <Clock className="w-8 h-8 text-text-subtle mx-auto mb-3" />
          <p className="text-sm font-medium text-text-secondary">No execution history yet</p>
          <p className="text-xs text-text-muted mt-1">
            Executed or processed recovery cases will appear here.
          </p>
        </div>
      ) : (
        <div className="space-y-4 animate-fade-in">
          {workflows.map((wf) => {
            const iconEl = getStatusIcon(wf.status);
            const bgCls = getStatusBg(wf.status);
            const executedAt =
              wf.execution_result &&
              typeof wf.execution_result === "object" &&
              "executed_at" in wf.execution_result &&
              typeof (wf.execution_result as Record<string, unknown>)["executed_at"] === "string"
                ? new Date(String((wf.execution_result as Record<string, unknown>)["executed_at"])).toLocaleString("en-IN")
                : undefined;

            const isSimulated =
              wf.execution_result &&
              typeof wf.execution_result === "object" &&
              "simulated" in wf.execution_result &&
              (wf.execution_result as Record<string, unknown>)["simulated"] === true;

            return (
              <div
                key={wf.recovery_id}
                className="bg-white border border-surface-border rounded-xl shadow-card overflow-hidden"
              >
                {/* Header */}
                <div className="flex flex-wrap justify-between items-center gap-3 px-5 py-4 border-b border-surface-border">
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-full border flex items-center justify-center ${bgCls}`}>
                      {iconEl}
                    </div>
                    <div>
                      <span className="text-sm font-semibold text-text-primary font-mono">
                        {displayId(wf.recovery_id)}
                      </span>
                      <p className="text-[10px] text-text-muted">
                        ₹{wf.amount.toLocaleString("en-IN")} · {label(FAILURE_LABELS, wf.failure_code)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border ${
                      wf.status === "COMPLETED" ? "text-emerald-700 bg-emerald-50 border-emerald-200" :
                      wf.status === "FAILED" ? "text-red-700 bg-red-50 border-red-200" :
                      wf.status === "BLOCKED" ? "text-orange-700 bg-orange-50 border-orange-200" :
                      wf.status === "ESCALATED" ? "text-orange-800 bg-orange-50 border-orange-300" :
                      "text-gray-600 bg-gray-50 border-gray-200"
                    }`}>
                      {wf.status.charAt(0) + wf.status.slice(1).toLowerCase()}
                    </span>
                    <Link
                      to={`/recovery/${wf.recovery_id}`}
                      className="inline-flex items-center gap-1 text-[11px] font-medium text-text-muted hover:text-accent transition-colors"
                    >
                      View <ArrowUpRight className="w-3 h-3" />
                    </Link>
                  </div>
                </div>

                {/* Timeline */}
                <div className="px-5 pt-4 pb-2 relative">
                  <div className="absolute left-[2.1rem] top-6 bottom-6 w-px bg-surface-border" />

                  <TimelineEvent
                    icon={<Clock />}
                    label="Payment failed — recovery workflow created"
                    time={new Date(wf.created_at).toLocaleString("en-IN")}
                    color="bg-blue-50 border-blue-200"
                    iconColor="text-blue-500"
                  />

                  <TimelineEvent
                    icon={<CheckCircle2 />}
                    label={`Recovery predicted: ${Math.round(wf.recovery_probability * 100)}% probability · ${label(ACTION_LABELS, wf.recommended_action)}`}
                    time={new Date(wf.created_at).toLocaleString("en-IN")}
                    color="bg-accent-light border-accent-border"
                    iconColor="text-accent"
                  />

                  {wf.attempt_count > 0 && (
                    <TimelineEvent
                      icon={<CheckCircle2 />}
                      label={`Execution attempted (${wf.attempt_count}/${wf.max_attempts} attempts)`}
                      time={executedAt}
                      color={wf.status === "COMPLETED" ? "bg-emerald-50 border-emerald-200" : "bg-surface-overlay border-surface-border"}
                      iconColor={wf.status === "COMPLETED" ? "text-emerald-500" : "text-text-muted"}
                    />
                  )}

                  <TimelineEvent
                    icon={iconEl}
                    label={
                      wf.status === "COMPLETED" ? "Recovery completed successfully" :
                      wf.status === "FAILED" ? "Recovery failed" :
                      wf.status === "BLOCKED" ? "Blocked — retry limit reached" :
                      wf.status === "ESCALATED" ? "Escalated for manual review" :
                      `Status: ${wf.status.toLowerCase()}`
                    }
                    time={new Date(wf.updated_at).toLocaleString("en-IN")}
                    color={bgCls}
                  />

                  {isSimulated && (
                    <div className="ml-10 mb-3">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium text-amber-700 bg-amber-50 border border-amber-200">
                        Simulation mode · no real payment processed
                      </span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Layout>
  );
}
