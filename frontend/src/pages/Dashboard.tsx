import { useEffect, useState } from "react";
import { Layout } from "../components/Layout";
import { KpiCard } from "../components/KpiCard";
import { RecoveryTable } from "../components/RecoveryTable";
import { api } from "../services/api";
import type { RecoveryStats, RecoveryWorkflow } from "../types/recovery";

export function Dashboard() {
  const [stats, setStats] = useState<RecoveryStats | null>(null);
  const [workflows, setWorkflows] = useState<RecoveryWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const [statsData, workflowsData] = await Promise.all([
          api.getRecoveryStats(),
          api.getRecoveryWorkflows(),
        ]);
        setStats(statsData);
        setWorkflows(workflowsData);
      } catch (err: any) {
        setError(err.message || "Failed to load dashboard data. Check backend connection.");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <Layout>
        <div className="flex justify-center items-center h-64 gap-3">
          <div className="h-5 w-5 border-2 border-accent/30 border-t-accent rounded-full animate-spin"></div>
          <span className="text-sm text-gray-500">Loading...</span>
        </div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout>
        <div className="bg-red-400/10 border border-red-400/20 text-red-400 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white">Recovery Overview</h1>
      </div>

      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
          <KpiCard
            title="Amount at Risk"
            value={`₹${stats.total_amount_at_risk.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
          />
          <KpiCard
            title="Expected Recovery"
            value={`₹${stats.total_expected_recovery.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
            subtitle="Based on model probabilities"
          />
          <KpiCard
            title="Recovery Probability"
            value={`${Math.round(stats.average_recovery_probability * 100)}%`}
            subtitle="Average across cases"
          />
          <KpiCard
            title="Active Cases"
            value={stats.total_cases.toLocaleString()}
            subtitle={`${stats.pending_count + stats.executing_count} pending`}
          />
        </div>
      )}

      <div>
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">Recovery Cases</h2>
        <RecoveryTable workflows={workflows} />
      </div>
    </Layout>
  );
}
