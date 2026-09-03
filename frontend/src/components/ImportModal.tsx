import React, { useState, useRef } from 'react';
import Papa from 'papaparse';
import { Upload, X, AlertCircle, CheckCircle2, Loader2, FileSpreadsheet } from 'lucide-react';
import { api } from '../services/api';

interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function ImportModal({ isOpen, onClose, onSuccess }: ImportModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [allRows, setAllRows] = useState<any[]>([]);
  const [headers, setHeaders] = useState<string[]>([]);
  const [currentPage, setCurrentPage] = useState(0);
  const [parseErrors, setParseErrors] = useState<any[]>([]);
  const [isImporting, setIsImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const reset = () => {
    setFile(null);
    setAllRows([]);
    setHeaders([]);
    setParseErrors([]);
    setCurrentPage(0);
    setError(null);
    setSuccess(null);
    setBatchId(null);
    setIsImporting(false);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;
    
    if (selected.type !== 'text/csv' && !selected.name.endsWith('.csv')) {
      setError("Please select a valid CSV file.");
      return;
    }
    
    setFile(selected);
    setError(null);
    
    // Parse preview
    Papa.parse(selected, {
      header: true,
      preview: 0, // Parse the whole file
      skipEmptyLines: true,
      complete: (results) => {
        setAllRows(results.data);
        setHeaders(results.meta.fields || []);
        setParseErrors(results.errors);
      },
      error: (err) => {
        setError(`Failed to read CSV: ${err.message}`);
      }
    });
  };

  const handleImport = async () => {
    if (!file) return;
    setIsImporting(true);
    setError(null);
    
    try {
      const res = await api.importTransactionsCSV(file);
      setSuccess(`Successfully imported ${res.imported} transactions. Skipped ${res.skipped} duplicates. Created ${res.workflows_created} recovery workflows.`);
      if (res.batch_id) {
        setBatchId(res.batch_id);
      } else {
        setTimeout(() => {
          onSuccess();
          handleClose();
        }, 2500);
      }
    } catch (err: any) {
      setError(err.message || "Failed to import transactions.");
      setIsImporting(false);
    }
  };

  const copyBatchId = () => {
    if (batchId) {
      navigator.clipboard.writeText(batchId);
    }
  };

  const handleDeleteImport = async () => {
    if (!batchId) return;
    if (!window.confirm("Are you sure you want to delete this imported batch?")) return;
    setIsDeleting(true);
    try {
      await api.deleteImportBatch(batchId);
      onSuccess();
      handleClose();
    } catch (err: any) {
      setError(err.message || "Failed to delete imported batch.");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border-light">
          <h2 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <FileSpreadsheet className="w-5 h-5 text-accent" />
            Import data
          </h2>
          <button 
            onClick={handleClose}
            className="text-text-muted hover:text-text-primary transition-colors"
            disabled={(isImporting || isDeleting) && !success}
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="p-6 overflow-y-auto flex-1">
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-100 rounded-lg flex items-start gap-3 text-red-700">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <p className="text-sm">{error}</p>
            </div>
          )}
          
          {success && (
            <div className="mb-6 p-6 bg-green-50 border border-green-100 rounded-xl flex flex-col gap-4 text-green-800">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="w-6 h-6 text-green-600" />
                <h3 className="text-lg font-bold">Import completed</h3>
              </div>
              <p className="text-sm font-medium">{success}</p>
              
              {batchId && (
                <div className="mt-2 bg-white/60 p-4 rounded-lg border border-green-200">
                  <p className="text-xs font-semibold uppercase text-green-700 mb-1">Batch ID</p>
                  <p className="font-mono text-sm mb-4">{batchId}</p>
                  
                  <div className="flex flex-wrap items-center gap-3">
                    <button 
                      onClick={copyBatchId}
                      className="px-3 py-1.5 bg-white border border-green-200 text-green-700 hover:bg-green-50 rounded-lg text-sm font-medium transition-colors"
                    >
                      Copy Batch ID
                    </button>
                    <a 
                      href={`/transactions?batch_id=${batchId}`}
                      className="px-3 py-1.5 bg-green-600 text-white hover:bg-green-700 rounded-lg text-sm font-medium transition-colors"
                      onClick={() => {
                        onSuccess();
                        onClose();
                      }}
                    >
                      View imported transactions
                    </a>
                    <button
                      onClick={handleDeleteImport}
                      disabled={isDeleting}
                      className="px-3 py-1.5 bg-white border border-red-200 text-red-600 hover:bg-red-50 rounded-lg text-sm font-medium transition-colors"
                    >
                      {isDeleting ? "Deleting..." : "Delete import"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {!file ? (
            <div 
              className="border-2 border-dashed border-border-light rounded-xl p-12 flex flex-col items-center justify-center text-center hover:border-accent/50 hover:bg-accent/5 transition-colors cursor-pointer group"
              onClick={() => fileInputRef.current?.click()}
            >
              <div className="w-16 h-16 rounded-full bg-accent/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Upload className="w-8 h-8 text-accent" />
              </div>
              <h3 className="text-lg font-semibold text-text-primary mb-2">Upload CSV File</h3>
              <p className="text-sm text-text-muted max-w-sm mb-6">
                Drag and drop your transaction records, or click to browse. Must contain transaction_id, customer_id, merchant_id, amount, and timestamp.
              </p>
              <button className="px-4 py-2 bg-accent text-white font-medium rounded-lg shadow-sm hover:bg-accent-hover transition-colors">
                Select File
              </button>
              <input 
                type="file" 
                ref={fileInputRef}
                className="hidden" 
                accept=".csv,text/csv"
                onChange={handleFileChange}
              />
            </div>
          ) : (
            <div className="space-y-6">
              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-border-light">
                <div className="flex items-center gap-3 overflow-hidden">
                  <div className="w-10 h-10 rounded bg-accent/10 flex items-center justify-center flex-shrink-0">
                    <FileSpreadsheet className="w-5 h-5 text-accent" />
                  </div>
                  <div className="truncate">
                    <p className="text-sm font-semibold text-text-primary truncate">{file.name}</p>
                    <p className="text-xs text-text-muted">{(file.size / 1024).toFixed(1)} KB</p>
                  </div>
                </div>
                {!isImporting && !success && (
                  <button 
                    onClick={reset}
                    className="text-sm text-accent font-medium hover:underline"
                  >
                    Change file
                  </button>
                )}
              </div>
              
              {allRows.length > 0 && !success && (
                <div className="border border-border-light rounded-lg overflow-hidden flex flex-col">
                  {/* Summary Header */}
                  <div className="bg-gray-50 px-4 py-3 border-b border-border-light flex items-center justify-between">
                    <div className="flex items-center gap-4 text-xs font-semibold">
                      <span className="text-text-primary">Total rows: {allRows.length}</span>
                      {parseErrors.length > 0 && (
                        <span className="text-amber-600 flex items-center gap-1">
                          <AlertCircle className="w-3.5 h-3.5" />
                          {parseErrors.length} warnings
                        </span>
                      )}
                    </div>
                  </div>
                  
                  {/* Table View */}
                  <div className="overflow-x-auto max-h-[300px]">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-white border-b border-border-light text-xs text-text-muted sticky top-0 shadow-sm z-10">
                        <tr>
                          <th className="px-4 py-2 font-medium whitespace-nowrap bg-gray-50">#</th>
                          {headers.map((key) => (
                            <th key={key} className="px-4 py-2 font-medium whitespace-nowrap bg-gray-50">{key}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border-light bg-white">
                        {allRows.slice(currentPage * 10, (currentPage + 1) * 10).map((row, i) => (
                          <tr key={currentPage * 10 + i} className="hover:bg-gray-50">
                            <td className="px-4 py-2 whitespace-nowrap text-text-muted text-xs bg-gray-50/50">
                              {currentPage * 10 + i + 1}
                            </td>
                            {headers.map((key, j) => (
                              <td key={j} className="px-4 py-2 whitespace-nowrap truncate max-w-[150px] text-text-secondary">
                                {row[key] !== undefined ? row[key] : ""}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination Controls */}
                  {allRows.length > 10 && (
                    <div className="bg-white px-4 py-2 border-t border-border-light flex items-center justify-between text-xs">
                      <span className="text-text-muted">
                        Showing {currentPage * 10 + 1}–{Math.min((currentPage + 1) * 10, allRows.length)} of {allRows.length}
                      </span>
                      <div className="flex items-center gap-2">
                        <button 
                          disabled={currentPage === 0}
                          onClick={() => setCurrentPage(c => c - 1)}
                          className="px-2.5 py-1 bg-gray-100 hover:bg-gray-200 text-text-primary rounded disabled:opacity-50 transition-colors"
                        >
                          Previous
                        </button>
                        <button 
                          disabled={(currentPage + 1) * 10 >= allRows.length}
                          onClick={() => setCurrentPage(c => c + 1)}
                          className="px-2.5 py-1 bg-gray-100 hover:bg-gray-200 text-text-primary rounded disabled:opacity-50 transition-colors"
                        >
                          Next
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
        
        {file && !success && (
          <div className="px-6 py-4 border-t border-border-light bg-gray-50 flex items-center justify-end gap-3">
            <button 
              onClick={handleClose}
              disabled={isImporting}
              className="px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-primary disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button 
              onClick={handleImport}
              disabled={isImporting}
              className="px-6 py-2 bg-accent text-white text-sm font-medium rounded-lg shadow-sm hover:bg-accent-hover disabled:opacity-70 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              {isImporting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Importing...
                </>
              ) : (
                "Import data"
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
