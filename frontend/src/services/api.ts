import type { ExecutionResponse, ModelInfo, PredictionRequest, PredictionResponse, RecoveryStats, RecoveryWorkflow } from "../types/recovery";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = {
  async getRecoveryStats(): Promise<RecoveryStats> {
    const res = await fetch(`${API_BASE_URL}/recovery/stats`);
    if (!res.ok) throw new Error("Failed to fetch recovery stats");
    return res.json();
  },

  async getRecoveryWorkflows(): Promise<RecoveryWorkflow[]> {
    const res = await fetch(`${API_BASE_URL}/recovery`);
    if (!res.ok) throw new Error("Failed to fetch recovery workflows");
    return res.json();
  },

  async getRecoveryWorkflow(id: string): Promise<RecoveryWorkflow> {
    const res = await fetch(`${API_BASE_URL}/recovery/${id}`);
    if (!res.ok) throw new Error("Failed to fetch recovery workflow details");
    return res.json();
  },

  async executeRecovery(id: string): Promise<ExecutionResponse> {
    const res = await fetch(`${API_BASE_URL}/recovery/${id}/execute`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Execution failed");
    return res.json();
  },

  async createPrediction(data: PredictionRequest): Promise<PredictionResponse> {
    const res = await fetch(`${API_BASE_URL}/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Prediction failed" }));
      throw new Error(err.detail || "Prediction failed");
    }
    return res.json();
  },

  async createRecovery(data: PredictionRequest): Promise<RecoveryWorkflow> {
    const res = await fetch(`${API_BASE_URL}/recovery`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Failed to create recovery" }));
      throw new Error(err.detail || "Failed to create recovery");
    }
    return res.json();
  },

  async getModelInfo(): Promise<ModelInfo> {
    const res = await fetch(`${API_BASE_URL}/model/info`);
    if (!res.ok) throw new Error("Failed to fetch model info");
    return res.json();
  },

  async importTransactionsCSV(file: File): Promise<{ batch_id?: string; imported: number; skipped: number; workflows_created: number }> {
    const formData = new FormData();
    formData.append("file", file);
    
    const res = await fetch(`${API_BASE_URL}/recovery/import/csv`, {
      method: "POST",
      body: formData,
    });
    
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Import failed" }));
      throw new Error(err.detail || "Import failed");
    }
    
    return res.json();
  },

  async getTransactions(page: number = 1, size: number = 50, search?: string, status?: string, import_batch_id?: string) {
    const params = new URLSearchParams({
      page: page.toString(),
      size: size.toString(),
    });
    if (search) params.append('search', search);
    if (status) params.append('status', status);
    if (import_batch_id) params.append('import_batch_id', import_batch_id);

    const res = await fetch(`${API_BASE_URL}/transactions?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch transactions');
    return res.json();
  },

  async deleteImportBatch(batchId: string) {
    const res = await fetch(`${API_BASE_URL}/recovery/import/${batchId}`, {
      method: 'DELETE'
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || 'Failed to delete imported dataset');
    }
    return res.json();
  },

  async updateTransaction(id: string, data: any) {
    const res = await fetch(`${API_BASE_URL}/transactions/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Failed to update transaction" }));
      throw new Error(err.detail || "Failed to update transaction");
    }
    return res.json();
  },

  async deleteTransactions(ids: string[]) {
    const res = await fetch(`${API_BASE_URL}/transactions`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transaction_ids: ids }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Failed to delete transactions" }));
      throw new Error(err.detail || "Failed to delete transactions");
    }
    return res.json();
  }
};
