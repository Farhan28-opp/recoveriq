/**
 * Central human-readable label mappings.
 * Use these everywhere the UI needs to display backend enum values.
 * The raw backend values (e.g. DELAYED_RETRY) are preserved for API calls —
 * only the display representation changes.
 */

export const ACTION_LABELS: Record<string, string> = {
  DELAYED_RETRY: "Delayed retry",
  IMMEDIATE_RETRY: "Immediate retry",
  ALTERNATE_METHOD: "Try alternate method",
  CONTACT_BANK: "Contact bank",
  MANUAL_REVIEW: "Manual review",
  ESCALATE_MANUAL_REVIEW: "Manual review required",
  BLACKLIST: "Blacklist",
  IGNORE: "No action",
  UNKNOWN: "Unknown",
};

export const FAILURE_LABELS: Record<string, string> = {
  INSUFFICIENT_FUNDS: "Insufficient funds",
  BANK_DECLINED: "Bank declined",
  TIMEOUT: "Timeout",
  NETWORK_ERROR: "Network error",
  LIMIT_EXCEEDED: "Limit exceeded",
  FRAUD_CHECK: "Fraud check",
  TECHNICAL_ERROR: "Technical error",
  METHOD_UNAVAILABLE: "Method unavailable",
  UNKNOWN: "Unknown failure",
};

export const STATUS_LABELS: Record<string, string> = {
  PENDING: "Pending",
  EXECUTING: "Executing",
  COMPLETED: "Completed",
  FAILED: "Failed",
  BLOCKED: "Blocked",
  ESCALATED: "Escalated",
};

export const RISK_LABELS: Record<string, string> = {
  HIGH: "High",
  MEDIUM: "Medium",
  LOW: "Low",
};

export const METHOD_LABELS: Record<string, string> = {
  UPI: "UPI",
  CARD: "Card",
  NETBANKING: "Net banking",
  WALLET: "Wallet",
  UNKNOWN: "Unknown",
};

/** Returns a human-readable label or falls back to the raw value. */
export function label(map: Record<string, string>, key: string): string {
  return map[key] ?? key;
}

/**
 * Display ID: produce a short stable identifier from a UUID.
 * Uses the last 6 hex chars (from the UUID's 4th segment) — stable
 * across page reloads, no counter needed, no backend change required.
 * The full UUID is preserved for all API calls.
 *
 * Example: "f665e8c7-ea32-4e1c-a31a-2158229983e7" → "REC-983E7"
 */
export function displayId(recoveryId: string): string {
  const parts = recoveryId.split("-");
  // Use last segment (most unique part of the UUID)
  const last = parts[parts.length - 1] ?? recoveryId;
  return `REC-${last.slice(-5).toUpperCase()}`;
}
