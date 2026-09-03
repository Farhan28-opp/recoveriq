export type WorkflowStatus = 
  | "PENDING"
  | "EXECUTING"
  | "COMPLETED"
  | "FAILED"
  | "BLOCKED"
  | "ESCALATED";

export const WorkflowStatusEnum = {
  PENDING: "PENDING" as WorkflowStatus,
  EXECUTING: "EXECUTING" as WorkflowStatus,
  COMPLETED: "COMPLETED" as WorkflowStatus,
  FAILED: "FAILED" as WorkflowStatus,
  BLOCKED: "BLOCKED" as WorkflowStatus,
  ESCALATED: "ESCALATED" as WorkflowStatus,
};

export interface RecoveryWorkflow {
  recovery_id: string;
  failure_code: string;
  amount: number;
  recovery_probability: number;
  risk_tier: string;
  recommended_action: string;
  expected_recovery_value: number;
  reason: string;
  model_version: string;
  status: WorkflowStatus;
  attempt_count: number;
  max_attempts: number;
  execution_result: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface RecoveryStats {
  total_cases: number;
  total_amount_at_risk: number;
  total_expected_recovery: number;
  average_recovery_probability: number;
  pending_count: number;
  executing_count: number;
  completed_count: number;
  failed_count: number;
  blocked_count: number;
  escalated_count: number;
}

export interface ExecutionResponse {
  recovery_id: string;
  status: WorkflowStatus;
  success: boolean;
  message: string;
  simulated: boolean;
  executed_at: string;
}

// --- Prediction types (matching backend PredictionRequest / PredictionResponse) ---

export type PaymentMethod = "UPI" | "CARD" | "NETBANKING" | "WALLET" | "UNKNOWN";
export type BankType = "HDFC" | "ICICI" | "SBI" | "AXIS" | "KOTAK" | "YES" | "INDUSIND" | "UNKNOWN";
export type DeviceType = "MOBILE" | "DESKTOP" | "TABLET" | "UNKNOWN";
export type FailureCode = "BANK_DECLINED" | "INSUFFICIENT_FUNDS" | "TIMEOUT" | "NETWORK_ERROR" | "LIMIT_EXCEEDED" | "FRAUD_CHECK" | "TECHNICAL_ERROR" | "METHOD_UNAVAILABLE" | "UNKNOWN";
export type MerchantCategory = "E_COMMERCE" | "FOOD" | "TRAVEL" | "EDUCATION" | "SUBSCRIPTION" | "HEALTHCARE" | "ENTERTAINMENT" | "UTILITIES" | "RETAIL" | "SERVICES" | "UNKNOWN";

export interface PredictionRequest {
  amount: number;
  retry_count: number;
  customer_success_rate: number;
  customer_lifetime_value: number;
  recent_bank_failure_rate: number;
  recent_method_failure_rate: number;
  abandonment_rate: number;
  average_transaction_value: number;
  monthly_transaction_volume: number;
  hour_of_day: number;
  day_of_week: number;
  payment_method: PaymentMethod;
  bank: BankType;
  device_type: DeviceType;
  failure_code: FailureCode;
  preferred_payment_method: PaymentMethod;
  preferred_bank: BankType;
  merchant_category: MerchantCategory;
}

export interface PredictionResponse {
  recovery_probability: number;
  risk_tier: string;
  recommended_action: string;
  expected_recovery_value: number;
  reason: string;
  model_version: string;
}

export interface ModelInfo {
  version: string;
  model_type: string;
  feature_count: number;
  training_timestamp: string | null;
  metrics: Record<string, unknown> | null;
}

export interface Transaction {
  transaction_id: string;
  customer_id: string;
  merchant_id: string;
  amount: number;
  currency: string;
  timestamp: string;
  status: string;
  payment_method?: string;
  bank?: string;
  device_type?: string;
  failure_code?: string;
  failure_reason?: string;
  import_batch_id?: string;
  recovery_id?: string;
}

export interface PaginatedTransactionResponse {
  items: Transaction[];
  total: number;
  page: number;
  size: number;
}
