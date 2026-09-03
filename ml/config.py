"""
Target definition and leakage rules for the RecoverIQ recovery-prediction
ML pipeline.

This module is the single source of truth for what the target is and
which columns must never be used as model input features. Every other
module in `ml/` imports from here rather than redefining these rules.

Categorical vocabularies are imported from `data.generate_dataset`
(the actual dataset generator) rather than redefined, so the feature
pipeline always reflects this repository's real semantics instead of
an assumed or invented vocabulary.
"""

from data.generate_dataset import (
    BANKS,
    DEVICE_TYPES,
    FAILURE_CODES,
    MERCHANT_CATEGORIES,
    PAYMENT_METHODS,
)

# --------------------------------------------------------------------
# Population and target
# --------------------------------------------------------------------

# Recovery prediction is only meaningful for payments that already
# failed. SUCCESS transactions are never in scope for this model.
ELIGIBLE_STATUS = "FAILED"

# The prediction target: whether a failed transaction was recovered.
TARGET_COLUMN = "recovered"

# --------------------------------------------------------------------
# Leakage rule #1 — explicit outcome fields (per Day 2 instructions)
# --------------------------------------------------------------------

# These are only known AFTER a recovery attempt has concluded. They
# must never be used as model input features.
LEAKAGE_COLUMNS = [
    "recovered",
    "recovery_delay_minutes",
    "recovered_amount",
]

# --------------------------------------------------------------------
# Leakage rule #2 — customer full-history aggregates (found during audit)
# --------------------------------------------------------------------

# backend/models.py: Customer.total_transactions, .successful_transactions,
# .failed_transactions, .customer_success_rate, .lifetime_value,
# .average_transaction_value, and .previous_recoveries are finalized by
# data/generate_dataset.py:finalize_customer_aggregates() from that
# customer's ENTIRE 30-day transaction history, not causally up to any
# one transaction. For any transaction that isn't a customer's last one,
# these columns encode information from transactions that happen
# chronologically AFTER the transaction being predicted.
#
# IMPORTANT NAME COLLISIONS: Transaction.customer_success_rate and
# Transaction.customer_lifetime_value ARE safe per-transaction causal
# snapshots (see generate_transactions(): rolling counters are updated
# strictly AFTER computing each transaction's features, in chronological
# order). Customer.customer_success_rate / Customer.lifetime_value /
# Customer.average_transaction_value are DIFFERENT columns on a
# different table with the same/similar names but full-history
# semantics. Do not join these Customer columns in as features.
CUSTOMER_FULL_HISTORY_LEAKAGE_COLUMNS = [
    "total_transactions",
    "successful_transactions",
    "failed_transactions",
    "customer_success_rate",
    "lifetime_value",
    "average_transaction_value",
    "previous_recoveries",
]

# --------------------------------------------------------------------
# Leakage rule #3 — payment_health hourly buckets (found during audit)
# --------------------------------------------------------------------

# data/generate_dataset.py:generate_payment_health() aggregates ALL
# transactions in a given (bank, payment_method, hour) bucket, including
# the transaction being predicted itself and any later transactions in
# the same hour. Joining payment_health by exact (bank, method, hour)
# would leak the current transaction's own outcome into its own
# features. A causally-safe version (only prior-hour buckets) is future
# work; payment_health is excluded from Day 2 features entirely.
PAYMENT_HEALTH_EXCLUDED = True
PAYMENT_HEALTH_EXCLUSION_REASON = (
    "payment_health buckets are aggregated per (bank, payment_method, hour) "
    "and include the current transaction's own outcome plus any later "
    "same-hour transactions. Using it as-is would leak the target. "
    "Excluded from Day 2 scope; a prior-hour-only join is future work."
)

# --------------------------------------------------------------------
# Categorical vocabulary (fixed, sourced from the generator's own
# constants so train/validation splits always produce identical
# one-hot columns regardless of which categories appear in which split)
# --------------------------------------------------------------------

CATEGORICAL_VOCAB = {
    "payment_method": list(PAYMENT_METHODS),
    "bank": list(BANKS),
    "device_type": list(DEVICE_TYPES),
    "failure_code": list(FAILURE_CODES),
    "preferred_payment_method": list(PAYMENT_METHODS),
    "preferred_bank": list(BANKS),
    "merchant_category": list(MERCHANT_CATEGORIES),
}

# --------------------------------------------------------------------
# Split
# --------------------------------------------------------------------

# Fraction of (timestamp-sorted) eligible transactions used for training.
# See ml/dataset.py:time_aware_split for how this is applied.
TRAIN_FRACTION = 0.8
