import { useEffect, useState } from "react";
import { Upload } from "lucide-react";
import { Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { PageHeader } from "../components/PageHeader";
import { WorkflowTable } from "../components/WorkflowTable";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { ImportModal } from "../components/ImportModal";
import { api } from "../services/api";
import type { RecoveryWorkflow } from "../types/recovery";

const FILTER_OPTIONS = ["All", "Pending", "Executing", "Completed", "Failed", "Blocked", "Escalated"];

export function Manage() {
  const [workflows, setWorkflows] = useState<RecoveryWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);

  const fetchWorkflows = () => {
    setLoading(true);
    api
      .getRecoveryWorkflows()
      .then((data) => setWorkflows(data.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())))
      .catch((err) => setError(err.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchWorkflows();
  }, []);

  const filterUpper = filter.toUpperCase();
  const filtered = workflows
    .filter((w) => filter === "All" || w.status === filterUpper)
    .filter((w) => {
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return (
        w.failure_code.toLowerCase().includes(q) ||
        w.status.toLowerCase().includes(q) ||
        w.recommended_action.toLowerCase().includes(q) ||
        w.recovery_id.toLowerCase().includes(q)
      );
    });

  const countFor = (s: string) =>
    s === "All" ? workflows.length : workflows.filter((w) => w.status === s.toUpperCase()).length;

  return (
    <Layout>
      <div className="mb-6 border-b border-surface-border flex gap-6">
        <Link to="/manage" className="px-1 py-3 border-b-2 border-accent text-accent text-sm font-semibold">
          Recovery Center
        </Link>
        <Link to="/transactions" className="px-1 py-3 border-b-2 border-transparent text-text-muted hover:text-text-primary hover:border-surface-border text-sm font-semibold transition-colors">
          Transactions
        </Link>
      </div>

      <div className="flex items-center justify-between">
        <PageHeader
          title="Recovery center"
          description="All recovery workflows — filter by status, search, and open individual cases."
        />
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsImportModalOpen(true)}
            className="px-4 py-2 bg-accent text-white text-sm font-medium rounded-xl shadow-btn hover:bg-accent-hover transition-colors flex items-center gap-2"
          >
            <Upload className="w-4 h-4" />
            Import data
          </button>
        </div>
      </div>

      <ImportModal 
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        onSuccess={fetchWorkflows}
      />

      {loading ? (
        <LoadingState message="Loading workflows..." />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchWorkflows} />
      ) : (
        <div className="space-y-5 animate-fade-in">
          {/* Search */}
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by case ID, failure type, status, or action..."
            className="w-full bg-white border border-surface-border rounded-xl px-4 py-2.5 text-sm text-text-primary placeholder:text-text-subtle focus:outline-none focus:ring-2 focus:ring-accent shadow-card"
          />

          {/* Status filter chips */}
          <div className="flex overflow-x-auto hide-scrollbar gap-2 pb-1">
            {FILTER_OPTIONS.map((opt) => (
              <button
                key={opt}
                onClick={() => setFilter(opt)}
                className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-colors ${
                  filter === opt
                    ? "bg-accent text-white"
                    : "bg-white border border-surface-border text-text-muted hover:text-text-primary shadow-sm"
                }`}
              >
                {opt}
                <span className={`text-[10px] ${filter === opt ? "text-white/70" : "text-text-subtle"}`}>
                  {countFor(opt)}
                </span>
              </button>
            ))}
          </div>

          {/* Results info */}
          <p className="text-xs text-text-muted">
            Showing {filtered.length} of {workflows.length} workflows
          </p>

          <WorkflowTable workflows={filtered} />
        </div>
      )}
    </Layout>
  );
}
