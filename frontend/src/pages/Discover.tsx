import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, SlidersHorizontal } from "lucide-react";
import { Layout } from "../components/Layout";
import { PageHeader } from "../components/PageHeader";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";
import { RiskBadge } from "../components/RiskBadge";
import { ActionBadge } from "../components/ActionBadge";
import { EmptyState } from "../components/EmptyState";
import { api } from "../services/api";
import type { RecoveryWorkflow } from "../types/recovery";
import { displayId, FAILURE_LABELS, label } from "../utils/labels";

type SortKey = "expected_recovery_value" | "recovery_probability" | "amount";
type RiskFilter = "ALL" | "HIGH" | "MEDIUM" | "LOW";

export function Discover() {
  const [all, setAll] = useState<RecoveryWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortKey>("expected_recovery_value");
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("ALL");
  const [search, setSearch] = useState("");

  useEffect(() => {
    api
      .getRecoveryWorkflows()
      .then((data) => {
        // Discover = actionable pending cases only
        const pending = data.filter((w) => w.status === "PENDING");
        setAll(pending);
      })
      .catch((err) => setError(err.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  const filtered = all
    .filter((w) => riskFilter === "ALL" || w.risk_tier === riskFilter)
    .filter((w) => {
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return (
        w.failure_code.toLowerCase().includes(q) ||
        w.recommended_action.toLowerCase().includes(q) ||
        displayId(w.recovery_id).toLowerCase().includes(q)
      );
    })
    .sort((a, b) => b[sortBy] - a[sortBy]);

  const totalValue = filtered.reduce((s, w) => s + w.expected_recovery_value, 0);

  return (
    <Layout>
      <PageHeader
        title="Recovery opportunities"
        description="Pending cases ranked by expected recovery value. Click a case to review and execute."
      />

      {loading ? (
        <LoadingState message="Loading opportunities..." />
      ) : error ? (
        <ErrorState message={error} onRetry={() => window.location.reload()} />
      ) : (
        <div className="space-y-5 animate-fade-in">
          {/* Summary bar */}
          <div className="bg-white border border-surface-border rounded-xl p-5 shadow-card flex flex-wrap gap-6 items-center">
            <div>
              <p className="text-xs text-text-muted font-medium mb-0.5">Showing</p>
              <p className="text-2xl font-bold text-text-primary">{filtered.length} cases</p>
            </div>
            <div className="h-10 w-px bg-surface-border hidden sm:block" />
            <div>
              <p className="text-xs text-accent font-medium mb-0.5">Potential recovery</p>
              <p className="text-2xl font-bold text-accent">
                ₹{totalValue.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
              </p>
            </div>
          </div>

          {/* Filters & search */}
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1">
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by case ID, failure type, or action..."
                className="w-full bg-white border border-surface-border rounded-xl px-4 py-2.5 text-sm text-text-primary placeholder:text-text-subtle focus:outline-none focus:ring-2 focus:ring-accent shadow-card"
              />
            </div>
            <div className="flex gap-2 items-center flex-wrap">
              <SlidersHorizontal className="w-4 h-4 text-text-muted flex-shrink-0" />
              {(["ALL", "HIGH", "MEDIUM", "LOW"] as RiskFilter[]).map((r) => (
                <button
                  key={r}
                  onClick={() => setRiskFilter(r)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    riskFilter === r
                      ? "bg-accent text-white"
                      : "bg-white border border-surface-border text-text-muted hover:text-text-primary"
                  }`}
                >
                  {r === "ALL" ? "All risk" : `${r.charAt(0)}${r.slice(1).toLowerCase()} risk`}
                </button>
              ))}
              <span className="text-text-subtle text-xs px-1">Sort:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortKey)}
                className="bg-white border border-surface-border rounded-lg px-2.5 py-1.5 text-xs text-text-secondary focus:outline-none focus:ring-1 focus:ring-accent"
              >
                <option value="expected_recovery_value">Expected recovery</option>
                <option value="recovery_probability">Probability</option>
                <option value="amount">Amount</option>
              </select>
            </div>
          </div>

          {/* Opportunity cards */}
          {filtered.length === 0 ? (
            <EmptyState
              title="No matching opportunities"
              description={all.length === 0 ? "All cases have been processed or no recovery workflows exist yet." : "Try adjusting your search or filters."}
            />
          ) : (
            <div className="space-y-3">
              {filtered.map((wf, idx) => {
                const pct = Math.round(wf.recovery_probability * 100);
                return (
                  <div
                    key={wf.recovery_id}
                    className="bg-white border border-surface-border rounded-xl shadow-card hover:shadow-card-hover hover:border-accent-border transition-all group"
                  >
                    <div className="p-5">
                      <div className="flex flex-wrap justify-between items-start gap-4">
                        {/* Left */}
                        <div className="flex items-start gap-4">
                          {/* Rank */}
                          <div className="w-8 h-8 rounded-full bg-surface-overlay border border-surface-border flex items-center justify-center flex-shrink-0 text-xs font-bold text-text-muted">
                            {idx + 1}
                          </div>
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-sm font-semibold text-text-primary font-mono">
                                {displayId(wf.recovery_id)}
                              </span>
                              <RiskBadge tier={wf.risk_tier} />
                            </div>
                            <p className="text-xs text-text-muted">
                              {label(FAILURE_LABELS, wf.failure_code)} · ₹{wf.amount.toLocaleString("en-IN")} original amount
                            </p>
                          </div>
                        </div>

                        {/* Right — key metrics */}
                        <div className="flex items-center gap-6 text-right">
                          <div>
                            <p className="text-[10px] text-text-subtle font-medium">Recovery probability</p>
                            <p className={`text-xl font-bold ${
                              pct >= 70 ? "text-emerald-600" : pct >= 45 ? "text-blue-600" : "text-red-500"
                            }`}>
                              {pct}%
                            </p>
                          </div>
                          <div>
                            <p className="text-[10px] text-text-subtle font-medium">Expected recovery</p>
                            <p className="text-xl font-bold text-text-primary">
                              ₹{wf.expected_recovery_value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                            </p>
                          </div>
                          <Link
                            to={`/recovery/${wf.recovery_id}`}
                            className="inline-flex items-center gap-1.5 px-3 py-2 bg-accent-light border border-accent-border text-accent text-xs font-semibold rounded-lg hover:bg-blue-100 transition-colors"
                          >
                            Review
                            <ArrowUpRight className="w-3.5 h-3.5" />
                          </Link>
                        </div>
                      </div>

                      {/* Action */}
                      <div className="mt-3 pt-3 border-t border-surface-border flex items-center gap-3">
                        <ActionBadge action={wf.recommended_action} />
                        <StatusBadge status={wf.status} />
                        <span className="text-[10px] text-text-subtle ml-auto">
                          Created {new Date(wf.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                        </span>
                      </div>
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
