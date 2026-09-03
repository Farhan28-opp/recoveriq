import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, TrendingUp, AlertCircle, CheckCircle2, Clock } from "lucide-react";
import { Layout } from "../components/Layout";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { WorkflowTable } from "../components/WorkflowTable";
import { ImportModal } from "../components/ImportModal";
import { api } from "../services/api";
import type { RecoveryStats, RecoveryWorkflow } from "../types/recovery";

export function Home() {
  const [stats, setStats] = useState<RecoveryStats | null>(null);
  const [allWorkflows, setAllWorkflows] = useState<RecoveryWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);

  const fetchData = () => {
    setLoading(true);
    Promise.all([api.getRecoveryStats(), api.getRecoveryWorkflows()])
      .then(([s, w]) => {
        setStats(s);
        setAllWorkflows(w);
      })
      .catch((err) => setError(err.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) return <Layout><LoadingState message="Loading..." /></Layout>;
  if (error) return <Layout><ErrorState message={error} onRetry={() => window.location.reload()} /></Layout>;
  if (!stats) return <Layout><ErrorState message="No data available" /></Layout>;

  // Top pending opportunities sorted by expected recovery value
  const topOpportunities = allWorkflows
    .filter((w) => w.status === "PENDING")
    .sort((a, b) => b.expected_recovery_value - a.expected_recovery_value)
    .slice(0, 5);

  const recoveryRate = stats.total_cases > 0
    ? Math.round((stats.completed_count / stats.total_cases) * 100)
    : 0;

  return (
    <Layout>
      <ImportModal 
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        onSuccess={fetchData}
      />
      <div className="animate-slide-up">
        {/* Page title */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-text-primary tracking-tight">Revenue Recovery</h1>
          <p className="text-sm text-text-muted mt-1">
            Monitor, prioritize, and act on failed-payment recovery opportunities.
          </p>
        </div>

        {/* Primary KPIs — asymmetric hero block */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
          {/* Large hero card — revenue at risk */}
          <div className="md:col-span-3 bg-white border border-surface-border rounded-xl p-6 shadow-card">
            <div className="flex items-start justify-between mb-4">
              <div>
                <p className="text-xs font-medium text-text-muted uppercase tracking-wide mb-1">
                  Revenue at risk
                </p>
                <p className="text-4xl font-bold text-text-primary tracking-tight">
                  ₹{stats.total_amount_at_risk.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                </p>
              </div>
              <div className="p-2.5 bg-red-50 rounded-lg">
                <AlertCircle className="w-5 h-5 text-red-500" />
              </div>
            </div>
            <p className="text-sm text-text-muted">
              {stats.total_cases} failed payment{stats.total_cases !== 1 ? "s" : ""} in the recovery pipeline
            </p>
          </div>

          {/* Expected recovery */}
          <div className="md:col-span-2 bg-accent-light border border-accent-border rounded-xl p-6 shadow-card">
            <div className="flex items-start justify-between mb-4">
              <div>
                <p className="text-xs font-medium text-accent uppercase tracking-wide mb-1">
                  Expected recovery
                </p>
                <p className="text-4xl font-bold text-accent tracking-tight">
                  ₹{stats.total_expected_recovery.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                </p>
              </div>
              <div className="p-2.5 bg-white/60 rounded-lg">
                <TrendingUp className="w-5 h-5 text-accent" />
              </div>
            </div>
            <p className="text-sm text-accent/80">
              {Math.round(stats.average_recovery_probability * 100)}% average probability
            </p>
          </div>
        </div>

        {/* Status strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
          {[
            {
              label: "Pending",
              value: stats.pending_count,
              icon: <Clock className="w-3.5 h-3.5" />,
              color: "text-blue-600 bg-blue-50 border-blue-200",
            },
            {
              label: "Completed",
              value: stats.completed_count,
              icon: <CheckCircle2 className="w-3.5 h-3.5" />,
              color: "text-emerald-600 bg-emerald-50 border-emerald-200",
            },
            {
              label: "Blocked",
              value: stats.blocked_count,
              icon: <AlertCircle className="w-3.5 h-3.5" />,
              color: "text-orange-600 bg-orange-50 border-orange-200",
            },
            {
              label: "Review required",
              value: stats.escalated_count,
              icon: <AlertCircle className="w-3.5 h-3.5" />,
              color: "text-red-600 bg-red-50 border-red-200",
            },
          ].map((s) => (
            <div key={s.label} className={`flex items-center gap-3 p-3.5 rounded-xl border ${s.color}`}>
              <div className="opacity-60">{s.icon}</div>
              <div>
                <p className="text-xs font-medium opacity-75">{s.label}</p>
                <p className="text-lg font-bold">{s.value}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Main content: opportunities (dominant) + quick actions */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Recovery Opportunities — dominant left panel */}
          <div className="xl:col-span-2">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-base font-semibold text-text-primary">Recovery opportunities</h2>
                <p className="text-xs text-text-muted mt-0.5">
                  {topOpportunities.length} pending case{topOpportunities.length !== 1 ? "s" : ""} ready for action
                </p>
              </div>
              <Link
                to="/discover"
                className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:text-accent-hover transition-colors"
              >
                View all <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {topOpportunities.length === 0 ? (
              <div className="bg-white border border-surface-border rounded-xl p-8 text-center shadow-card">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                <p className="text-sm font-medium text-text-secondary">No pending opportunities</p>
                <p className="text-xs text-text-muted mt-1 mb-4">
                  All cases have been processed. Analyze a failed payment to create a new recovery case.
                </p>
                <Link
                  to="/recover"
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-accent text-white text-xs font-medium rounded-lg hover:bg-accent-hover transition-colors"
                >
                  Analyze a payment
                </Link>
              </div>
            ) : (
              <WorkflowTable workflows={topOpportunities} compact />
            )}
          </div>

          {/* Quick actions sidebar */}
          <div className="space-y-3">
            <h2 className="text-base font-semibold text-text-primary mb-4">Quick actions</h2>

            {/* Import Data Entry Point */}
            <div className="p-4 bg-accent-light border border-accent-border rounded-xl shadow-card flex flex-col gap-3">
              <div>
                <p className="text-sm font-semibold text-accent mb-0.5">Import transactions</p>
                <p className="text-xs text-accent/80">Upload your business payment data to discover recovery opportunities.</p>
              </div>
              <button 
                onClick={() => setIsImportModalOpen(true)}
                className="w-full py-2 bg-accent text-white text-xs font-semibold rounded-lg shadow-sm hover:bg-accent-hover transition-colors"
              >
                Import data
              </button>
            </div>

            <Link
              to="/recover"
              className="flex items-center gap-3 p-4 bg-white border border-surface-border rounded-xl shadow-card hover:shadow-card-hover hover:border-accent-border transition-all group"
            >
              <div className="w-8 h-8 rounded-lg bg-accent-light flex items-center justify-center flex-shrink-0 group-hover:bg-blue-100 transition-colors">
                <span className="text-accent text-sm font-bold">↗</span>
              </div>
              <div>
                <p className="text-sm font-semibold text-text-primary">Analyze a payment</p>
                <p className="text-xs text-text-muted">Run recovery prediction</p>
              </div>
            </Link>

            <Link
              to="/discover"
              className="flex items-center gap-3 p-4 bg-white border border-surface-border rounded-xl shadow-card hover:shadow-card-hover hover:border-accent-border transition-all group"
            >
              <div className="w-8 h-8 rounded-lg bg-surface-overlay flex items-center justify-center flex-shrink-0">
                <span className="text-text-muted text-sm font-bold">⊙</span>
              </div>
              <div>
                <p className="text-sm font-semibold text-text-primary">Find opportunities</p>
                <p className="text-xs text-text-muted">Prioritized recovery list</p>
              </div>
            </Link>

            <Link
              to="/understand"
              className="flex items-center gap-3 p-4 bg-white border border-surface-border rounded-xl shadow-card hover:shadow-card-hover hover:border-accent-border transition-all group"
            >
              <div className="w-8 h-8 rounded-lg bg-surface-overlay flex items-center justify-center flex-shrink-0">
                <span className="text-text-muted text-sm font-bold">≡</span>
              </div>
              <div>
                <p className="text-sm font-semibold text-text-primary">Understand failures</p>
                <p className="text-xs text-text-muted">Patterns and distributions</p>
              </div>
            </Link>

            <Link
              to="/manage"
              className="flex items-center gap-3 p-4 bg-white border border-surface-border rounded-xl shadow-card hover:shadow-card-hover hover:border-accent-border transition-all group"
            >
              <div className="w-8 h-8 rounded-lg bg-surface-overlay flex items-center justify-center flex-shrink-0">
                <span className="text-text-muted text-sm font-bold">☰</span>
              </div>
              <div>
                <p className="text-sm font-semibold text-text-primary">Manage recovery</p>
                <p className="text-xs text-text-muted">All workflows and status</p>
              </div>
            </Link>

            {/* Recovery rate summary */}
            {stats.total_cases > 0 && (
              <div className="mt-4 p-4 bg-surface-raised border border-surface-border rounded-xl shadow-card">
                <p className="text-xs font-medium text-text-muted mb-2">Recovery rate</p>
                <div className="flex items-end gap-2 mb-2">
                  <span className="text-2xl font-bold text-text-primary">{recoveryRate}%</span>
                  <span className="text-xs text-text-muted mb-0.5">of cases completed</span>
                </div>
                <div className="w-full bg-surface-overlay rounded-full h-1.5 border border-surface-border">
                  <div
                    className="h-1.5 rounded-full bg-emerald-500 transition-all duration-700"
                    style={{ width: `${recoveryRate}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}
