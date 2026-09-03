import { useEffect, useState } from "react";
import { Layout } from "../components/Layout";
import { PageHeader } from "../components/PageHeader";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { api } from "../services/api";
import type { RecoveryWorkflow, RecoveryStats } from "../types/recovery";
import { FAILURE_LABELS, ACTION_LABELS, label } from "../utils/labels";

type Tab = "overview" | "failures" | "actions" | "recovery";

export function Understand() {
  const [workflows, setWorkflows] = useState<RecoveryWorkflow[]>([]);
  const [stats, setStats] = useState<RecoveryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");

  useEffect(() => {
    Promise.all([api.getRecoveryWorkflows(), api.getRecoveryStats()])
      .then(([wf, s]) => { setWorkflows(wf); setStats(s); })
      .catch((err) => setError(err.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  // Computed distributions
  const failureCounts = workflows.reduce<Record<string, number>>((acc, wf) => {
    acc[wf.failure_code] = (acc[wf.failure_code] ?? 0) + 1;
    return acc;
  }, {});

  const actionCounts = workflows.reduce<Record<string, number>>((acc, wf) => {
    acc[wf.recommended_action] = (acc[wf.recommended_action] ?? 0) + 1;
    return acc;
  }, {});

  const riskCounts = workflows.reduce<Record<string, number>>((acc, wf) => {
    acc[wf.risk_tier] = (acc[wf.risk_tier] ?? 0) + 1;
    return acc;
  }, {});

  const avgProb = workflows.length > 0
    ? workflows.reduce((s, w) => s + w.recovery_probability, 0) / workflows.length
    : 0;

  const totalExpected = workflows.reduce((s, w) => s + w.expected_recovery_value, 0);

  function Bar({ value, total, color = "bg-accent" }: { value: number; total: number; color?: string }) {
    const pct = total > 0 ? (value / total) * 100 : 0;
    return (
      <div className="w-full bg-surface-overlay rounded-full h-2 border border-surface-border overflow-hidden">
        <div className={`${color} h-2 rounded-full transition-all duration-700`} style={{ width: `${pct}%` }} />
      </div>
    );
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "failures", label: "Failure patterns" },
    { key: "actions", label: "Recovery actions" },
    { key: "recovery", label: "Recovery score" },
  ];

  return (
    <Layout>
      <PageHeader
        title="Payment intelligence"
        description="Understand failure patterns and recovery performance across all cases."
      />

      {loading ? (
        <LoadingState message="Analyzing data..." />
      ) : error ? (
        <ErrorState message={error} onRetry={() => window.location.reload()} />
      ) : (
        <div className="space-y-6 animate-fade-in">
          {/* Tab bar */}
          <div className="flex gap-1 border-b border-surface-border">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  tab === t.key
                    ? "border-accent text-accent"
                    : "border-transparent text-text-muted hover:text-text-secondary"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Overview */}
          {tab === "overview" && stats && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {[
                { label: "Total cases", value: stats.total_cases, sub: "in pipeline" },
                { label: "Revenue at risk", value: `₹${stats.total_amount_at_risk.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`, sub: "failed payments" },
                { label: "Expected recovery", value: `₹${totalExpected.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`, sub: "model forecast" },
                { label: "Average probability", value: `${Math.round(avgProb * 100)}%`, sub: "recovery likelihood" },
                { label: "Completed", value: stats.completed_count, sub: `${stats.total_cases > 0 ? Math.round((stats.completed_count / stats.total_cases) * 100) : 0}% recovery rate` },
                { label: "Review required", value: stats.escalated_count + stats.blocked_count, sub: "escalated or blocked" },
              ].map((item) => (
                <div key={item.label} className="bg-white border border-surface-border rounded-xl p-5 shadow-card">
                  <p className="text-xs font-medium text-text-muted mb-2">{item.label}</p>
                  <p className="text-2xl font-bold text-text-primary">{item.value}</p>
                  <p className="text-[11px] text-text-subtle mt-1">{item.sub}</p>
                </div>
              ))}

              {/* Status breakdown */}
              <div className="bg-white border border-surface-border rounded-xl p-5 shadow-card sm:col-span-2 lg:col-span-3">
                <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-4">Workflow status breakdown</p>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
                  {[
                    { s: "Pending", v: stats.pending_count, c: "bg-blue-500" },
                    { s: "Executing", v: stats.executing_count, c: "bg-amber-500" },
                    { s: "Completed", v: stats.completed_count, c: "bg-emerald-500" },
                    { s: "Failed", v: stats.failed_count, c: "bg-red-500" },
                    { s: "Blocked", v: stats.blocked_count, c: "bg-orange-500" },
                    { s: "Escalated", v: stats.escalated_count, c: "bg-orange-700" },
                  ].map((item) => (
                    <div key={item.s} className="text-center">
                      <div className={`text-xl font-bold text-text-primary`}>{item.v}</div>
                      <div className="text-[11px] text-text-muted mt-0.5">{item.s}</div>
                      <div className="mt-2 h-1 rounded-full bg-surface-overlay border border-surface-border overflow-hidden">
                        <div className={`${item.c} h-full rounded-full`} style={{ width: `${stats.total_cases > 0 ? (item.v / stats.total_cases) * 100 : 0}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Failure patterns */}
          {tab === "failures" && (
            <div className="bg-white border border-surface-border rounded-xl p-6 shadow-card">
              <h3 className="text-sm font-semibold text-text-primary mb-5">Failure code distribution</h3>
              <div className="space-y-4">
                {Object.entries(failureCounts)
                  .sort(([, a], [, b]) => b - a)
                  .map(([code, count]) => (
                    <div key={code}>
                      <div className="flex justify-between text-xs mb-1.5">
                        <span className="font-medium text-text-secondary">{label(FAILURE_LABELS, code)}</span>
                        <span className="text-text-muted">{count} case{count !== 1 ? "s" : ""} · {Math.round((count / workflows.length) * 100)}%</span>
                      </div>
                      <Bar value={count} total={workflows.length} />
                    </div>
                  ))}
              </div>

              <div className="mt-6 pt-5 border-t border-surface-border">
                <h4 className="text-sm font-semibold text-text-primary mb-4">Risk tier distribution</h4>
                <div className="grid grid-cols-3 gap-4">
                  {(["HIGH", "MEDIUM", "LOW"] as const).map((tier) => {
                    const count = riskCounts[tier] ?? 0;
                    const colors: Record<string, string> = { HIGH: "text-emerald-600", MEDIUM: "text-amber-600", LOW: "text-red-500" };
                    const barColors: Record<string, string> = { HIGH: "bg-emerald-500", MEDIUM: "bg-amber-500", LOW: "bg-red-400" };
                    return (
                      <div key={tier} className="p-4 bg-surface-overlay border border-surface-border rounded-xl text-center">
                        <p className={`text-2xl font-bold ${colors[tier]}`}>{count}</p>
                        <p className="text-xs text-text-muted mt-1">{tier.charAt(0)}{tier.slice(1).toLowerCase()} risk</p>
                        <div className="mt-2">
                          <Bar value={count} total={workflows.length} color={barColors[tier]} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Recovery actions */}
          {tab === "actions" && (
            <div className="bg-white border border-surface-border rounded-xl p-6 shadow-card">
              <h3 className="text-sm font-semibold text-text-primary mb-5">Recommended action distribution</h3>
              <div className="space-y-4">
                {Object.entries(actionCounts)
                  .sort(([, a], [, b]) => b - a)
                  .map(([action, count]) => (
                    <div key={action}>
                      <div className="flex justify-between text-xs mb-1.5">
                        <span className="font-medium text-text-secondary">{label(ACTION_LABELS, action)}</span>
                        <span className="text-text-muted">{count} case{count !== 1 ? "s" : ""} · {Math.round((count / workflows.length) * 100)}%</span>
                      </div>
                      <Bar value={count} total={workflows.length} color={action === "ESCALATE_MANUAL_REVIEW" ? "bg-orange-400" : "bg-accent"} />
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Recovery score */}
          {tab === "recovery" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="bg-white border border-surface-border rounded-xl p-6 shadow-card">
                <h3 className="text-sm font-semibold text-text-primary mb-5">Probability buckets</h3>
                {(() => {
                  const buckets = [
                    { label: "High (70–100%)", min: 0.7, max: 1.0 },
                    { label: "Medium (45–70%)", min: 0.45, max: 0.7 },
                    { label: "Low (0–45%)", min: 0, max: 0.45 },
                  ];
                  const colors = ["bg-emerald-500", "bg-blue-500", "bg-red-400"];
                  return buckets.map(({ label: blabel, min, max }, i) => {
                    const count = workflows.filter((w) => w.recovery_probability >= min && w.recovery_probability < max).length;
                    return (
                      <div key={blabel} className="mb-4">
                        <div className="flex justify-between text-xs mb-1.5">
                          <span className="font-medium text-text-secondary">{blabel}</span>
                          <span className="text-text-muted">{count} cases</span>
                        </div>
                        <Bar value={count} total={workflows.length} color={colors[i]} />
                      </div>
                    );
                  });
                })()}
              </div>
              <div className="bg-white border border-surface-border rounded-xl p-6 shadow-card">
                <h3 className="text-sm font-semibold text-text-primary mb-5">Expected value breakdown</h3>
                <div className="space-y-4">
                  <div>
                    <p className="text-xs text-text-muted mb-1">Total pipeline value</p>
                    <p className="text-3xl font-bold text-text-primary">
                      ₹{stats?.total_amount_at_risk.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                    </p>
                  </div>
                  <div className="h-px bg-surface-border" />
                  <div>
                    <p className="text-xs text-text-muted mb-1">Projected recovery</p>
                    <p className="text-3xl font-bold text-accent">
                      ₹{totalExpected.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                    </p>
                  </div>
                  <div className="h-px bg-surface-border" />
                  <div>
                    <p className="text-xs text-text-muted mb-1">Recovery efficiency</p>
                    <p className="text-2xl font-bold text-text-primary">
                      {stats && stats.total_amount_at_risk > 0
                        ? `${Math.round((totalExpected / stats.total_amount_at_risk) * 100)}%`
                        : "—"}
                    </p>
                    <p className="text-[10px] text-text-subtle mt-1">of at-risk revenue expected to be recovered</p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </Layout>
  );
}
