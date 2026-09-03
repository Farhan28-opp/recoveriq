# RecoverIQ — ML Feature Dictionary (Day 2)

This documents the feature-engineering pipeline in `ml/` (`ml/config.py`,
`ml/features.py`, `ml/dataset.py`). It complements `docs/data_dictionary.md`,
which documents the raw database schema; this file documents what the
ML pipeline does with that schema.

**No model has been trained yet.** This document describes the feature
matrix (`X`) and target (`y`) that a Day 3 model will train on, and the
train/validation split strategy. There is no `/predict` endpoint,
trained model artifact, or recovery-decision logic in the repository
today.

## Population and target

- **Population**: only `transactions` rows where `status = 'FAILED'`.
  Recovery prediction only makes sense for payments that have already
  failed; `SUCCESS` transactions are never in scope.
- **Target column**: `transactions.recovered` (boolean) — whether that
  failed transaction was (synthetically) recovered.

## Leakage rule — outcome fields (never used as features)

These fields are only known **after** a recovery attempt has
concluded and must never be used as model input features:

| Column | Table |
|---|---|
| `recovered` | `transactions` (this is the target itself) |
| `recovery_delay_minutes` | `transactions` |
| `recovered_amount` | `transactions` |

Enforced in code by `ml.config.LEAKAGE_COLUMNS` and dropped in
`ml.features.split_features_and_target`.

## Leakage rule — customer full-history aggregates (found during Day 2 audit)

`backend/models.py` defines `Customer.total_transactions`,
`.successful_transactions`, `.failed_transactions`,
`.customer_success_rate`, `.lifetime_value`, `.average_transaction_value`,
and `.previous_recoveries`. `data/generate_dataset.py:finalize_customer_aggregates()`
computes these from a customer's **entire 30-day transaction history**,
not causally up to any single transaction. For any transaction that
isn't a customer's chronologically-last one, these columns encode
information from transactions that happen **after** the transaction
being predicted — a real temporal leakage source, distinct from the
outcome fields above.

**Important name collision**: `transactions.customer_success_rate` and
`transactions.customer_lifetime_value` are *different, safe* columns —
rolling snapshots computed strictly from transactions processed
*before* the current one (`data/generate_dataset.py` processes
transactions "strictly in chronological order to avoid leakage" and
updates its rolling counters *after* computing each transaction's
features). The `customers` table columns with similar names are the
leaky, full-history versions. The feature pipeline only ever selects
the `transactions`-table (safe) versions — see
`ml.config.CUSTOMER_FULL_HISTORY_LEAKAGE_COLUMNS` for the excluded
`customers`-table columns.

## Leakage rule — `payment_health` (found during Day 2 audit, excluded)

`generate_payment_health()` aggregates all transactions into
`(bank, payment_method, hour)` buckets, and each bucket **includes the
outcome of the very transaction being predicted**, plus any later
transactions in the same hour. Joining `payment_health` by exact
`(bank, method, hour)` as currently structured would leak the target.
`payment_health` is **excluded from the Day 2 feature set entirely**.
A causally-safe version (aggregating only prior-hour buckets) is
future work.

## Final feature list

### From `transactions` (available at failure time)

| Feature | Type | Notes |
|---|---|---|
| `amount` | numeric | transaction amount |
| `retry_count` | numeric | retries so far |
| `payment_method` | categorical (one-hot) | UPI / CARD / NETBANKING / WALLET |
| `bank` | categorical (one-hot) | issuing bank |
| `device_type` | categorical (one-hot) | MOBILE / DESKTOP / TABLET |
| `failure_code` | categorical (one-hot) | reason the payment failed; known at failure time, before any recovery attempt |
| `customer_success_rate` | numeric | rolling snapshot, causally safe (see collision note above) |
| `customer_lifetime_value` | numeric | rolling snapshot, causally safe |
| `recent_bank_failure_rate` | numeric | rolling snapshot at this bank, causally safe |
| `recent_method_failure_rate` | numeric | rolling snapshot at this method, causally safe |
| `hour_of_day` | numeric (derived) | from `timestamp`; cyclical, generalizes across dates |
| `day_of_week` | numeric (derived) | from `timestamp` |

`transaction_id`, `customer_id`, `merchant_id`, and the raw `timestamp`
are kept as **metadata** (`ml.features.METADATA_COLUMNS`) for
traceability and the time-aware split, but are not fed to the model as
raw features — an absolute timestamp/ID doesn't generalize to future
data. `failure_reason` (free-text, 1:1 redundant with `failure_code`)
and `currency` (constant `"INR"` for every row in this dataset, zero
predictive variance) are excluded.

### From `customers` (static traits, independent of transaction outcomes)

| Feature | Type | Notes |
|---|---|---|
| `preferred_payment_method` | categorical (one-hot) | assigned at customer-generation time |
| `preferred_bank` | categorical (one-hot) | assigned at customer-generation time |
| `abandonment_rate` | numeric | synthetic per-profile trait, not derived from observed transactions |

### From `merchants` (static traits)

| Feature | Type | Notes |
|---|---|---|
| `merchant_category` | categorical (one-hot) | fixed at merchant-generation time |
| `average_transaction_value` | numeric | fixed at merchant-generation time — **not** the same column as the excluded `customers.average_transaction_value` |
| `monthly_transaction_volume` | numeric | fixed at merchant-generation time |

### Explicitly excluded (leakage)

| Column | Table | Reason |
|---|---|---|
| `recovered` | `transactions` | is the target |
| `recovery_delay_minutes` | `transactions` | post-outcome |
| `recovered_amount` | `transactions` | post-outcome |
| `total_transactions` | `customers` | full-history aggregate |
| `successful_transactions` | `customers` | full-history aggregate |
| `failed_transactions` | `customers` | full-history aggregate |
| `customer_success_rate` | `customers` | full-history aggregate (name collision, see above) |
| `lifetime_value` | `customers` | full-history aggregate |
| `average_transaction_value` | `customers` | full-history aggregate (name collision with the safe `merchants` column) |
| `previous_recoveries` | `customers` | full-history aggregate |
| all `payment_health` columns | `payment_health` | own-bucket/future-bucket leakage, see above |

### Excluded for other reasons (not leakage, just not useful)

| Column | Table | Reason |
|---|---|---|
| `failure_reason` | `transactions` | free-text, redundant with `failure_code` |
| `currency` | `transactions` | constant `"INR"` in this dataset; zero variance |

## Encoding and missing-value handling

- Categorical columns are one-hot encoded against a **fixed vocabulary**
  sourced from `data/generate_dataset.py`'s own constants
  (`ml.config.CATEGORICAL_VOCAB`), not the values observed in any one
  split. This guarantees `X_train` and `X_val` always have identical
  columns even if a rare category is absent from one side, and an
  `UNKNOWN` bucket is added for any unseen/null category.
- Numeric columns returned by SQLAlchemy as `decimal.Decimal` (any DB
  `Numeric` column, e.g. `amount`, `customer_success_rate`) are cast to
  `float64` — without this, pandas silently treats them as
  non-numeric `object` columns and scikit-learn cannot fit on them.
- Missing numeric values are filled with the column median (none are
  currently null for `FAILED` transactions in the generated dataset,
  verified against the live data — this is a robustness measure for
  future generator changes, not a currently-active code path).

## Train/validation split

- **Method**: time-aware split by `timestamp`, not random. Verified
  against the actual dataset with `HISTORY_DAYS = 30`.
- **Split fraction**: 80% earliest / 20% latest of the eligible
  (`FAILED`) transactions, by timestamp (`ml.config.TRAIN_FRACTION`).
  The cutoff is computed from the real data's timestamp distribution
  each time the pipeline runs (`ml.dataset.time_aware_split`), not a
  hardcoded date.
- **Measured on the current dataset** (`python data/generate_dataset.py`,
  seed 42): 7,529 FAILED transactions spanning 2026-07-26 12:48:10 to
  2026-08-25 11:52:39.
  - Train: 6,023 rows, timestamps < 2026-08-19 20:04:09 — 1,826 recovered / 4,197 unrecovered.
  - Validation: 1,506 rows, timestamps ≥ 2026-08-19 20:04:09 — 416 recovered / 1,090 unrecovered.
- **Why time-based, not random**: this is payment/recovery data. A
  random split would let the model train on transactions that happened
  chronologically *after* some of the transactions it's validated on —
  something a real production system could never do, since it only
  ever sees the past. A time-based split keeps validation honest.
- Both classes (`recovered` True/False) are present on both sides of
  the split — verified above and enforced by
  `tests/test_ml_pipeline.py::test_target_contains_both_classes`.

## Reuse for inference (Day 3)

`ml.config.CATEGORICAL_VOCAB` is the single source of truth for
one-hot column names; a future inference path should reuse it directly
(rather than re-deriving categories from whatever data is available at
inference time) so a saved model's expected input columns stay stable.
