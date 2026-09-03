import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { ChevronDown, ChevronUp, ArrowRight, Info } from "lucide-react";
import { Layout } from "../components/Layout";
import { ProbabilityGauge } from "../components/ProbabilityGauge";
import { api } from "../services/api";
import type { PredictionRequest, ModelInfo } from "../types/recovery";
import { ACTION_LABELS, RISK_LABELS, label } from "../utils/labels";

const DEFAULT_FORM: PredictionRequest = {
  amount: 2500.0,
  retry_count: 1,
  customer_success_rate: 0.85,
  customer_lifetime_value: 15000.0,
  recent_bank_failure_rate: 0.04,
  recent_method_failure_rate: 0.02,
  abandonment_rate: 0.12,
  average_transaction_value: 1200.0,
  monthly_transaction_volume: 45,
  hour_of_day: 14,
  day_of_week: 3,
  payment_method: "UPI",
  bank: "HDFC",
  device_type: "MOBILE",
  failure_code: "INSUFFICIENT_FUNDS",
  preferred_payment_method: "UPI",
  preferred_bank: "HDFC",
  merchant_category: "E_COMMERCE",
};

function SectionToggle({ title, defaultOpen = true, children }: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-white border border-surface-border rounded-xl shadow-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-surface-hover transition-colors"
      >
        <span className="text-sm font-semibold text-text-primary">{title}</span>
        {open ? <ChevronUp className="w-4 h-4 text-text-muted" /> : <ChevronDown className="w-4 h-4 text-text-muted" />}
      </button>
      {open && <div className="px-5 pb-5 pt-1">{children}</div>}
    </div>
  );
}

const inputClass = "w-full bg-surface-overlay border border-surface-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent transition-shadow";
const labelClass = "block text-xs font-medium text-text-muted mb-1";

export function Recover() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<PredictionRequest>(DEFAULT_FORM);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [prediction, setPrediction] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getModelInfo().then(setModelInfo).catch(() => {});
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    setFormData((prev) => ({ ...prev, [name]: type === "number" ? Number(value) : value }));
  };

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setAnalyzing(true);
    setError(null);
    setPrediction(null);
    try {
      const res = await api.createPrediction(formData);
      setPrediction(res);
    } catch (err: any) {
      setError(err.message ?? "Analysis failed. Check backend connection.");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleCreateWorkflow = async () => {
    setCreating(true);
    setError(null);
    try {
      const wf = await api.createRecovery(formData);
      navigate(`/recovery/${wf.recovery_id}`);
    } catch (err: any) {
      setError(err.message ?? "Failed to create workflow.");
      setCreating(false);
    }
  };

  const isFraudCase = formData.failure_code === "FRAUD_CHECK";

  return (
    <Layout>
      <div className="mb-8">
        <h1 className="text-xl font-semibold text-text-primary">Analyze a failed payment</h1>
        <p className="text-sm text-text-muted mt-0.5">
          Enter payment details to receive a recovery recommendation and expected value.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Form */}
        <div>
          <div className="flex items-start gap-2.5 p-3.5 bg-blue-50 border border-blue-200 rounded-xl mb-4">
            <Info className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-blue-700">
              Review the payment details and analyze recovery potential.
            </p>
          </div>

          <form onSubmit={handleAnalyze} className="space-y-4">
            <SectionToggle title="Payment details">
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2 sm:col-span-1">
                  <label className={labelClass}>Amount (₹)</label>
                  <input type="number" name="amount" value={formData.amount} onChange={handleChange} required min={1}
                    className={inputClass} />
                </div>
                <div className="col-span-2 sm:col-span-1">
                  <label className={labelClass}>Failure reason</label>
                  <select name="failure_code" value={formData.failure_code} onChange={handleChange} className={inputClass}>
                    <option value="INSUFFICIENT_FUNDS">Insufficient funds</option>
                    <option value="BANK_DECLINED">Bank declined</option>
                    <option value="TIMEOUT">Timeout</option>
                    <option value="NETWORK_ERROR">Network error</option>
                    <option value="LIMIT_EXCEEDED">Limit exceeded</option>
                    <option value="FRAUD_CHECK">Fraud check</option>
                    <option value="TECHNICAL_ERROR">Technical error</option>
                    <option value="METHOD_UNAVAILABLE">Method unavailable</option>
                  </select>
                </div>
                <div>
                  <label className={labelClass}>Payment method</label>
                  <select name="payment_method" value={formData.payment_method} onChange={handleChange} className={inputClass}>
                    <option value="UPI">UPI</option>
                    <option value="CARD">Card</option>
                    <option value="NETBANKING">Net banking</option>
                  </select>
                </div>
                <div>
                  <label className={labelClass}>Bank</label>
                  <select name="bank" value={formData.bank} onChange={handleChange} className={inputClass}>
                    <option value="HDFC">HDFC</option>
                    <option value="ICICI">ICICI</option>
                    <option value="SBI">SBI</option>
                    <option value="AXIS">Axis</option>
                  </select>
                </div>
                <div>
                  <label className={labelClass}>Device</label>
                  <select name="device_type" value={formData.device_type} onChange={handleChange} className={inputClass}>
                    <option value="MOBILE">Mobile</option>
                    <option value="DESKTOP">Desktop</option>
                    <option value="TABLET">Tablet</option>
                  </select>
                </div>
                <div>
                  <label className={labelClass}>Merchant category</label>
                  <select name="merchant_category" value={formData.merchant_category} onChange={handleChange} className={inputClass}>
                    <option value="E_COMMERCE">E-commerce</option>
                    <option value="FOOD_DELIVERY">Food delivery</option>
                    <option value="TRAVEL">Travel</option>
                    <option value="UTILITIES">Utilities</option>
                    <option value="EDUCATION">Education</option>
                  </select>
                </div>
              </div>
            </SectionToggle>

            <SectionToggle title="Customer context" defaultOpen={false}>
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2 sm:col-span-1">
                  <label className={labelClass}>Payment success rate</label>
                  <input type="number" name="customer_success_rate" value={formData.customer_success_rate}
                    onChange={handleChange} min={0} max={1} step={0.01} className={inputClass} />
                  <p className="text-[10px] text-text-subtle mt-1">0.0 – 1.0</p>
                </div>
                <div className="col-span-2 sm:col-span-1">
                  <label className={labelClass}>Customer lifetime value (₹)</label>
                  <input type="number" name="customer_lifetime_value" value={formData.customer_lifetime_value}
                    onChange={handleChange} min={0} className={inputClass} />
                </div>
                <div className="col-span-2 sm:col-span-1">
                  <label className={labelClass}>Prior retry count</label>
                  <input type="number" name="retry_count" value={formData.retry_count}
                    onChange={handleChange} min={0} className={inputClass} />
                </div>
              </div>
            </SectionToggle>

            <SectionToggle title="Transaction context" defaultOpen={false}>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={labelClass}>Average transaction value (₹)</label>
                  <input type="number" name="average_transaction_value" value={formData.average_transaction_value}
                    onChange={handleChange} min={0} className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Monthly volume</label>
                  <input type="number" name="monthly_transaction_volume" value={formData.monthly_transaction_volume}
                    onChange={handleChange} min={0} className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Recent bank failure rate</label>
                  <input type="number" name="recent_bank_failure_rate" value={formData.recent_bank_failure_rate}
                    onChange={handleChange} min={0} max={1} step={0.01} className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Recent method failure rate</label>
                  <input type="number" name="recent_method_failure_rate" value={formData.recent_method_failure_rate}
                    onChange={handleChange} min={0} max={1} step={0.01} className={inputClass} />
                </div>
              </div>
            </SectionToggle>

            <SectionToggle title="Timing" defaultOpen={false}>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={labelClass}>Hour of day (0–23)</label>
                  <input type="number" name="hour_of_day" value={formData.hour_of_day}
                    onChange={handleChange} min={0} max={23} className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Day of week (0=Mon, 6=Sun)</label>
                  <input type="number" name="day_of_week" value={formData.day_of_week}
                    onChange={handleChange} min={0} max={6} className={inputClass} />
                </div>
              </div>
            </SectionToggle>

            {error && (
              <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={analyzing}
              className="w-full py-2.5 bg-accent text-white text-sm font-semibold rounded-xl hover:bg-accent-hover disabled:opacity-60 disabled:cursor-not-allowed transition-colors shadow-btn"
            >
              {analyzing ? "Analyzing..." : "Analyze payment"}
            </button>

            {modelInfo && (
              <p className="text-[10px] text-text-subtle text-center">
                Model: {modelInfo.version} · {modelInfo.feature_count} features
              </p>
            )}
          </form>
        </div>

        {/* Right: Result */}
        <div>
          {!prediction ? (
            <div className="bg-white border border-surface-border rounded-xl shadow-card p-8 text-center">
              <div className="w-12 h-12 rounded-full bg-accent-light flex items-center justify-center mx-auto mb-3">
                <ArrowRight className="w-5 h-5 text-accent" />
              </div>
              <p className="text-sm font-medium text-text-secondary">Recovery analysis</p>
              <p className="text-xs text-text-muted mt-1">
                Fill in the payment details and click "Analyze payment" to get a recovery recommendation.
              </p>
            </div>
          ) : (
            <div className="bg-white border border-surface-border rounded-xl shadow-card animate-slide-up overflow-hidden">
              {/* Result header */}
              <div className="px-6 py-5 border-b border-surface-border">
                <h3 className="text-sm font-semibold text-text-primary">Recovery analysis</h3>
              </div>

              <div className="p-6 space-y-6">
                {/* Probability gauge */}
                <ProbabilityGauge probability={prediction.recovery_probability} />

                {/* Key metrics */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-surface-overlay rounded-xl border border-surface-border">
                    <p className="text-xs text-text-muted mb-1">Expected recovery</p>
                    <p className="text-xl font-bold text-text-primary">
                      ₹{prediction.expected_recovery_value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                    </p>
                  </div>
                  <div className="p-4 bg-surface-overlay rounded-xl border border-surface-border">
                    <p className="text-xs text-text-muted mb-1">Risk level</p>
                    <p className="text-lg font-bold text-text-primary">
                      {label(RISK_LABELS, prediction.risk_tier)}
                    </p>
                  </div>
                </div>

                {/* Recommended action */}
                <div className="p-4 bg-accent-light border border-accent-border rounded-xl">
                  <p className="text-xs font-medium text-accent mb-1">Recommended action</p>
                  <p className="text-base font-semibold text-accent">
                    {label(ACTION_LABELS, prediction.recommended_action)}
                  </p>
                </div>

                {/* Reasoning */}
                <div>
                  <p className="text-xs font-medium text-text-muted mb-2">Analysis</p>
                  <p className="text-sm text-text-secondary leading-relaxed bg-surface-overlay border border-surface-border rounded-xl p-4">
                    {prediction.reason}
                  </p>
                </div>

                {/* CTA */}
                {isFraudCase ? (
                  <div className="p-4 bg-orange-50 border border-orange-200 rounded-xl">
                    <p className="text-sm font-semibold text-orange-700 mb-1">Manual review required</p>
                    <p className="text-xs text-orange-600">
                      Fraud-related failures cannot be automatically recovered. This case requires manual escalation.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <button
                      onClick={handleCreateWorkflow}
                      disabled={creating}
                      className="w-full py-2.5 bg-accent text-white text-sm font-semibold rounded-xl hover:bg-accent-hover disabled:opacity-60 transition-colors shadow-btn"
                    >
                      {creating ? "Creating..." : "Create recovery workflow"}
                    </button>
                    <p className="text-[10px] text-text-subtle text-center">
                      Creates a tracked recovery workflow. Opens the case detail page.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Navigation shortcuts */}
          <div className="mt-4 p-4 bg-white border border-surface-border rounded-xl shadow-card">
            <p className="text-xs font-semibold text-text-muted mb-2">Navigation</p>
            <div className="space-y-1.5">
              <Link
                to="/discover"
                className="flex items-center justify-between text-xs text-text-secondary hover:text-accent py-1 transition-colors"
              >
                <span>View recovery opportunities</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
              <Link
                to="/manage"
                className="flex items-center justify-between text-xs text-text-secondary hover:text-accent py-1 transition-colors"
              >
                <span>Open recovery center</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
