import { useEffect, useState } from "react";
import { Trash2, Search, ArrowRight, ExternalLink, Edit2, AlertCircle, Upload } from "lucide-react";
import { Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { PageHeader } from "../components/PageHeader";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { ImportModal } from "../components/ImportModal";
import { api } from "../services/api";
import type { Transaction, PaginatedTransactionResponse } from "../types/recovery";

export function Transactions() {
  const [data, setData] = useState<PaginatedTransactionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [importBatchId, setImportBatchId] = useState("");

  const [selectedTx, setSelectedTx] = useState<Transaction | null>(null);
  const [editTx, setEditTx] = useState<Transaction | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  
  // Batch deletion based on selection
  const [targetBatchId, setTargetBatchId] = useState("");

  // Row selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isDeleteSelectedModalOpen, setIsDeleteSelectedModalOpen] = useState(false);
  
  // Edit Form State
  const [editForm, setEditForm] = useState<Partial<Transaction>>({});
  const [isSaving, setIsSaving] = useState(false);

  const fetchTransactions = () => {
    setLoading(true);
    api
      .getTransactions(page, 50, search, status, importBatchId)
      .then(setData)
      .catch((err) => setError(err.message ?? "Failed to load transactions"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchTransactions();
  }, [page, status, importBatchId]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchTransactions();
  };

  const handleDeleteBatch = async () => {
    const batchIdToDelete = targetBatchId || importBatchId;
    if (!batchIdToDelete) return;
    setIsDeleting(true);
    try {
      await api.deleteImportBatch(batchIdToDelete);
      setIsDeleteModalOpen(false);
      setTargetBatchId("");
      if (batchIdToDelete === importBatchId) {
        setImportBatchId(""); // Reset filter
      }
      setSelectedIds(new Set());
      setPage(1);
      fetchTransactions();
    } catch (err: any) {
      alert(err.message || "Failed to delete");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return;
    setIsDeleting(true);
    try {
      await api.deleteTransactions(Array.from(selectedIds));
      setIsDeleteSelectedModalOpen(false);
      setSelectedIds(new Set());
      fetchTransactions();
    } catch (err: any) {
      alert(err.message || "Failed to delete selected");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleEditSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editTx) return;
    setIsSaving(true);
    try {
      await api.updateTransaction(editTx.transaction_id, editForm);
      setEditTx(null);
      fetchTransactions();
    } catch (err: any) {
      alert(err.message || "Failed to save transaction");
    } finally {
      setIsSaving(false);
    }
  };

  const openEditModal = () => {
    if (selectedIds.size !== 1) return;
    const tx = data?.items.find(t => t.transaction_id === Array.from(selectedIds)[0]);
    if (tx) {
      setEditTx(tx);
      setEditForm({
        amount: tx.amount,
        timestamp: tx.timestamp,
        status: tx.status,
        payment_method: tx.payment_method,
        bank: tx.bank,
        device_type: tx.device_type,
        failure_code: tx.failure_code,
        failure_reason: tx.failure_reason,
      });
    }
  };

  const toggleSelectAll = () => {
    if (!data) return;
    if (selectedIds.size === data.items.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(data.items.map(t => t.transaction_id)));
    }
  };

  const toggleSelect = (id: string) => {
    const newSet = new Set(selectedIds);
    if (newSet.has(id)) newSet.delete(id);
    else newSet.add(id);
    setSelectedIds(newSet);
  };

  const formatCurrency = (amount: number, currency: string) =>
    new Intl.NumberFormat("en-IN", { style: "currency", currency }).format(amount);

  // Compute common batch id for selected items
  const selectedTransactions = data?.items.filter(t => selectedIds.has(t.transaction_id)) || [];
  const commonBatchId = selectedTransactions.length > 0 
    ? selectedTransactions.every(t => t.import_batch_id === selectedTransactions[0].import_batch_id)
      ? selectedTransactions[0].import_batch_id 
      : null
    : null;

  return (
    <Layout>
      <div className="mb-6 border-b border-surface-border flex gap-6">
        <Link to="/manage" className="px-1 py-3 border-b-2 border-transparent text-text-muted hover:text-text-primary hover:border-surface-border text-sm font-semibold transition-colors">
          Recovery Center
        </Link>
        <Link to="/transactions" className="px-1 py-3 border-b-2 border-accent text-accent text-sm font-semibold">
          Transactions
        </Link>
      </div>

      <div className="flex items-center justify-between">
        <PageHeader
          title="Transaction Explorer"
          description="Search and view imported transactions and their recovery workflows."
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
        onSuccess={fetchTransactions}
      />

      <div className="mb-6 bg-white p-4 rounded-xl border border-surface-border shadow-sm flex flex-col sm:flex-row gap-4 items-end mt-4">
        <form onSubmit={handleSearch} className="flex-1 w-full">
          <label className="block text-xs font-semibold text-text-subtle uppercase mb-1">Search</label>
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by transaction ID, customer, merchant..."
              className="w-full pl-9 pr-4 py-2 bg-surface-base border border-surface-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>
        </form>
        <div className="w-full sm:w-48">
          <label className="block text-xs font-semibold text-text-subtle uppercase mb-1">Status</label>
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
            className="w-full px-3 py-2 bg-surface-base border border-surface-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          >
            <option value="">All Statuses</option>
            <option value="SUCCESS">Success</option>
            <option value="FAILED">Failed</option>
          </select>
        </div>
        <div className="w-full sm:w-48">
          <label className="block text-xs font-semibold text-text-subtle uppercase mb-1">Batch ID</label>
          <input
            type="text"
            value={importBatchId}
            onChange={(e) => { setImportBatchId(e.target.value); setPage(1); }}
            placeholder="Paste Batch ID..."
            className="w-full px-3 py-2 bg-surface-base border border-surface-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          />
        </div>
        <button
          onClick={handleSearch}
          className="px-4 py-2 bg-surface-overlay border border-surface-border text-text-primary text-sm font-medium rounded-lg shadow-sm hover:bg-surface-raised transition-colors"
        >
          Apply Filters
        </button>
      </div>

      {loading ? (
        <LoadingState message="Loading transactions..." />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchTransactions} />
      ) : data ? (
        <div className="space-y-4 animate-fade-in">
          <div className="bg-white rounded-xl border border-surface-border shadow-sm overflow-hidden">
            {selectedIds.size > 0 && (
              <div className="bg-accent-light/30 border-b border-accent/20 px-5 py-3 flex items-center justify-between">
                <span className="text-sm font-medium text-accent-dark">
                  {selectedIds.size} transaction{selectedIds.size > 1 ? 's' : ''} selected
                </span>
                <div className="flex items-center gap-3">
                  {commonBatchId && (
                    <button
                      onClick={() => { setTargetBatchId(commonBatchId); setIsDeleteModalOpen(true); }}
                      className="px-3 py-1.5 bg-red-50 text-red-600 text-sm font-medium rounded shadow-sm border border-red-200 hover:bg-red-100 flex items-center gap-1.5 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      Delete import batch
                    </button>
                  )}
                  {selectedIds.size === 1 && (
                    <button
                      onClick={openEditModal}
                      className="px-3 py-1.5 bg-accent text-white text-sm font-medium rounded shadow-sm hover:bg-accent-hover flex items-center gap-1.5 transition-colors"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                      Edit selected
                    </button>
                  )}
                  <button
                    onClick={() => setIsDeleteSelectedModalOpen(true)}
                    className="px-3 py-1.5 bg-red-600 text-white text-sm font-medium rounded shadow-sm hover:bg-red-700 flex items-center gap-1.5 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Delete selected
                  </button>
                </div>
              </div>
            )}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="bg-surface-raised border-b border-surface-border text-xs uppercase text-text-subtle font-semibold">
                  <tr>
                    <th className="px-5 py-3 w-10">
                      <input 
                        type="checkbox" 
                        className="w-4 h-4 rounded border-gray-300 text-accent focus:ring-accent cursor-pointer"
                        checked={data.items.length > 0 && selectedIds.size === data.items.length}
                        onChange={toggleSelectAll}
                      />
                    </th>
                    <th className="px-5 py-3">Transaction ID</th>
                    <th className="px-5 py-3">Customer</th>
                    <th className="px-5 py-3">Amount</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3">Date</th>
                    <th className="px-5 py-3">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border">
                  {data.items.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-5 py-8 text-center text-text-muted">
                        No transactions found.
                      </td>
                    </tr>
                  )}
                  {data.items.map((tx) => (
                    <tr key={tx.transaction_id} className={`transition-colors ${selectedIds.has(tx.transaction_id) ? 'bg-accent-light/10' : 'hover:bg-surface-raised/50'}`}>
                      <td className="px-5 py-3">
                        <input 
                          type="checkbox" 
                          className="w-4 h-4 rounded border-gray-300 text-accent focus:ring-accent cursor-pointer"
                          checked={selectedIds.has(tx.transaction_id)}
                          onChange={() => toggleSelect(tx.transaction_id)}
                        />
                      </td>
                      <td className="px-5 py-3 font-mono text-xs">{tx.transaction_id.slice(0, 8)}...</td>
                      <td className="px-5 py-3">{tx.customer_id}</td>
                      <td className="px-5 py-3 font-medium text-text-primary">
                        {formatCurrency(tx.amount, tx.currency)}
                      </td>
                      <td className="px-5 py-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                          tx.status === 'SUCCESS' ? 'bg-status-success/10 text-status-success' : 
                          tx.status === 'FAILED' ? 'bg-status-danger/10 text-status-danger' : 
                          'bg-surface-overlay text-text-muted'
                        }`}>
                          {tx.status}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-text-muted">
                        {new Date(tx.timestamp).toLocaleString()}
                      </td>
                      <td className="px-5 py-3">
                        <button
                          onClick={() => setSelectedTx(tx)}
                          className="text-accent hover:text-accent-hover font-medium flex items-center gap-1"
                        >
                          Details <ArrowRight className="w-3 h-3" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            <div className="px-5 py-3 border-t border-surface-border bg-surface-raised flex items-center justify-between">
              <span className="text-sm text-text-muted">
                Showing {(page - 1) * 50 + 1} to {Math.min(page * 50, data.total)} of {data.total}
              </span>
              <div className="flex gap-2">
                <button
                  disabled={page === 1}
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  className="px-3 py-1.5 bg-white border border-surface-border rounded shadow-sm text-sm disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  disabled={page * 50 >= data.total}
                  onClick={() => setPage(p => p + 1)}
                  className="px-3 py-1.5 bg-white border border-surface-border rounded shadow-sm text-sm disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {selectedTx && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col">
            <div className="p-5 border-b border-surface-border flex items-center justify-between bg-surface-raised">
              <h2 className="text-lg font-bold text-text-primary tracking-tight">Transaction Details</h2>
              <button
                onClick={() => setSelectedTx(null)}
                className="p-1.5 text-text-muted hover:text-text-primary bg-surface-base hover:bg-surface-overlay rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="block text-text-subtle font-semibold mb-1 uppercase text-xs">Transaction ID</span>
                  <span className="font-mono">{selectedTx.transaction_id}</span>
                </div>
                <div>
                  <span className="block text-text-subtle font-semibold mb-1 uppercase text-xs">Date</span>
                  <span>{new Date(selectedTx.timestamp).toLocaleString()}</span>
                </div>
                <div>
                  <span className="block text-text-subtle font-semibold mb-1 uppercase text-xs">Amount</span>
                  <span className="font-medium text-text-primary">{formatCurrency(selectedTx.amount, selectedTx.currency)}</span>
                </div>
                <div>
                  <span className="block text-text-subtle font-semibold mb-1 uppercase text-xs">Status</span>
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                    selectedTx.status === 'SUCCESS' ? 'bg-status-success/10 text-status-success' : 
                    selectedTx.status === 'FAILED' ? 'bg-status-danger/10 text-status-danger' : 
                    'bg-surface-overlay text-text-muted'
                  }`}>
                    {selectedTx.status}
                  </span>
                </div>
                <div>
                  <span className="block text-text-subtle font-semibold mb-1 uppercase text-xs">Customer</span>
                  <span>{selectedTx.customer_id}</span>
                </div>
                <div>
                  <span className="block text-text-subtle font-semibold mb-1 uppercase text-xs">Merchant</span>
                  <span>{selectedTx.merchant_id}</span>
                </div>
                <div>
                  <span className="block text-text-subtle font-semibold mb-1 uppercase text-xs">Payment Method</span>
                  <span>{selectedTx.payment_method || 'N/A'}</span>
                </div>
                <div>
                  <span className="block text-text-subtle font-semibold mb-1 uppercase text-xs">Failure Code</span>
                  <span>{selectedTx.failure_code || 'N/A'}</span>
                </div>
                {selectedTx.import_batch_id && (
                  <div className="col-span-2">
                    <span className="block text-text-subtle font-semibold mb-1 uppercase text-xs">Import Batch ID</span>
                    <span className="font-mono text-xs">{selectedTx.import_batch_id}</span>
                  </div>
                )}
              </div>
              
              {selectedTx.recovery_id && (
                <div className="mt-6 p-4 bg-accent-light/50 border border-accent/20 rounded-xl">
                  <h3 className="font-semibold text-accent mb-2">Recovery Case Available</h3>
                  <p className="text-sm text-text-muted mb-3">A recovery workflow was generated for this failed transaction.</p>
                  <Link
                    to={`/recovery/${selectedTx.recovery_id}`}
                    className="inline-flex items-center gap-1.5 px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg shadow-sm hover:bg-accent-hover transition-colors"
                  >
                    View recovery case <ExternalLink className="w-4 h-4" />
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {isDeleteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl w-full max-w-sm shadow-2xl overflow-hidden p-6 text-center">
            <div className="w-12 h-12 rounded-full bg-status-danger/10 text-status-danger flex items-center justify-center mx-auto mb-4">
              <Trash2 className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-bold text-text-primary tracking-tight mb-2">Delete imported dataset?</h2>
            <p className="text-sm text-text-muted mb-6">
              This will safely remove all imported transactions and recovery workflows matching batch ID <strong>{(targetBatchId || importBatchId).slice(0,8)}...</strong>
              <br/><br/>This action cannot be undone.
            </p>
            <div className="flex gap-3 justify-center">
              <button
                onClick={() => setIsDeleteModalOpen(false)}
                className="px-4 py-2 bg-surface-overlay text-text-primary text-sm font-medium rounded-lg hover:bg-surface-raised transition-colors"
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteBatch}
                className="px-4 py-2 bg-status-danger text-white text-sm font-medium rounded-lg hover:bg-status-danger/90 transition-colors"
                disabled={isDeleting}
              >
                {isDeleting ? "Deleting..." : "Delete imported data"}
              </button>
            </div>
          </div>
        </div>
      )}

      {isDeleteSelectedModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl w-full max-w-sm shadow-2xl overflow-hidden p-6 text-center">
            <div className="w-12 h-12 rounded-full bg-status-danger/10 text-status-danger flex items-center justify-center mx-auto mb-4">
              <Trash2 className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-bold text-text-primary tracking-tight mb-2">Delete {selectedIds.size} transaction{selectedIds.size > 1 ? 's' : ''}?</h2>
            <p className="text-sm text-text-muted mb-6">
              This may also remove recovery workflows linked to these transactions.
              <br/><br/>This action cannot be undone.
            </p>
            <div className="flex gap-3 justify-center">
              <button
                onClick={() => setIsDeleteSelectedModalOpen(false)}
                className="px-4 py-2 bg-surface-overlay text-text-primary text-sm font-medium rounded-lg hover:bg-surface-raised transition-colors"
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteSelected}
                className="px-4 py-2 bg-status-danger text-white text-sm font-medium rounded-lg hover:bg-status-danger/90 transition-colors"
                disabled={isDeleting}
              >
                {isDeleting ? "Deleting..." : "Delete transactions"}
              </button>
            </div>
          </div>
        </div>
      )}

      {editTx && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            <div className="p-5 border-b border-surface-border flex items-center justify-between bg-surface-raised">
              <h2 className="text-lg font-bold text-text-primary tracking-tight">Edit Transaction</h2>
              <button
                onClick={() => setEditTx(null)}
                className="p-1.5 text-text-muted hover:text-text-primary bg-surface-base hover:bg-surface-overlay rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
            <div className="p-6 overflow-y-auto space-y-6">
              {editTx.recovery_id && (
                <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-3 text-amber-800">
                  <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5 text-amber-600" />
                  <div>
                    <h4 className="font-semibold text-amber-900">Transaction data changed. Re-analysis may be required.</h4>
                    <p className="text-sm mt-1">This transaction has an existing recovery workflow. Modifying these fields will not automatically overwrite the historical recovery decision.</p>
                  </div>
                </div>
              )}
              
              <form id="editTxForm" onSubmit={handleEditSave} className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-text-subtle uppercase mb-1">Transaction ID</label>
                  <input type="text" value={editTx.transaction_id} disabled className="w-full px-3 py-2 bg-surface-overlay border border-surface-border rounded-lg text-sm text-text-muted cursor-not-allowed" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-text-subtle uppercase mb-1">Date/Time</label>
                  <input 
                    type="text" 
                    value={editForm.timestamp ? new Date(editForm.timestamp).toISOString() : ''} 
                    onChange={e => setEditForm({...editForm, timestamp: e.target.value})}
                    className="w-full px-3 py-2 bg-surface-base border border-surface-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent" 
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-text-subtle uppercase mb-1">Amount</label>
                  <input 
                    type="number" 
                    step="0.01"
                    value={editForm.amount || ''} 
                    onChange={e => setEditForm({...editForm, amount: parseFloat(e.target.value)})}
                    className="w-full px-3 py-2 bg-surface-base border border-surface-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent" 
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-text-subtle uppercase mb-1">Status</label>
                  <select 
                    value={editForm.status || ''} 
                    onChange={e => setEditForm({...editForm, status: e.target.value})}
                    className="w-full px-3 py-2 bg-surface-base border border-surface-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                  >
                    <option value="SUCCESS">Success</option>
                    <option value="FAILED">Failed</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-text-subtle uppercase mb-1">Customer ID</label>
                  <input type="text" value={editTx.customer_id} disabled className="w-full px-3 py-2 bg-surface-overlay border border-surface-border rounded-lg text-sm text-text-muted cursor-not-allowed" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-text-subtle uppercase mb-1">Merchant ID</label>
                  <input type="text" value={editTx.merchant_id} disabled className="w-full px-3 py-2 bg-surface-overlay border border-surface-border rounded-lg text-sm text-text-muted cursor-not-allowed" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-text-subtle uppercase mb-1">Payment Method</label>
                  <input 
                    type="text" 
                    value={editForm.payment_method || ''} 
                    onChange={e => setEditForm({...editForm, payment_method: e.target.value})}
                    className="w-full px-3 py-2 bg-surface-base border border-surface-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent" 
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-text-subtle uppercase mb-1">Bank</label>
                  <input 
                    type="text" 
                    value={editForm.bank || ''} 
                    onChange={e => setEditForm({...editForm, bank: e.target.value})}
                    className="w-full px-3 py-2 bg-surface-base border border-surface-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent" 
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-text-subtle uppercase mb-1">Device Type</label>
                  <input 
                    type="text" 
                    value={editForm.device_type || ''} 
                    onChange={e => setEditForm({...editForm, device_type: e.target.value})}
                    className="w-full px-3 py-2 bg-surface-base border border-surface-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent" 
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-text-subtle uppercase mb-1">Failure Code</label>
                  <input 
                    type="text" 
                    value={editForm.failure_code || ''} 
                    onChange={e => setEditForm({...editForm, failure_code: e.target.value})}
                    className="w-full px-3 py-2 bg-surface-base border border-surface-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent" 
                  />
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-semibold text-text-subtle uppercase mb-1">Failure Reason</label>
                  <textarea 
                    value={editForm.failure_reason || ''} 
                    onChange={e => setEditForm({...editForm, failure_reason: e.target.value})}
                    className="w-full px-3 py-2 bg-surface-base border border-surface-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                    rows={2}
                  />
                </div>
              </form>
            </div>
            <div className="p-5 border-t border-surface-border bg-surface-raised flex items-center justify-end gap-3">
              <button
                onClick={() => setEditTx(null)}
                className="px-4 py-2 bg-surface-overlay text-text-primary text-sm font-medium rounded-lg hover:bg-surface-raised transition-colors"
                disabled={isSaving}
              >
                Cancel
              </button>
              <button
                type="submit"
                form="editTxForm"
                className="px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent-hover transition-colors shadow-sm"
                disabled={isSaving}
              >
                {isSaving ? "Saving..." : "Save changes"}
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
