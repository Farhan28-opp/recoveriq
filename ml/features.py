"""
Feature engineering for the RecoverIQ recovery-prediction pipeline.

Builds a feature+target+metadata frame from the existing `transactions`,
`customers`, and `merchants` tables via the project's existing
SQLAlchemy session (backend.database.SessionLocal). Only FAILED
transactions are in scope, since recovery prediction is only meaningful
for payments that have already failed.

Every column pulled in here is deliberately chosen because it is
available BEFORE a recovery decision would be made. See ml/config.py
for the columns that were excluded and why.
"""

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Customer, Merchant, Transaction
from ml.config import (
    CATEGORICAL_VOCAB,
    ELIGIBLE_STATUS,
    LEAKAGE_COLUMNS,
    TARGET_COLUMN,
)

# Transaction columns: amount/method/bank/device/failure_code are known
# at failure time. customer_success_rate, customer_lifetime_value,
# recent_bank_failure_rate, recent_method_failure_rate are rolling
# snapshots computed strictly from transactions processed BEFORE this
# one (see data/generate_dataset.py: "process strictly in chronological
# order to avoid leakage") — safe despite the name overlap with the
# (excluded) Customer-table aggregate columns.
_TRANSACTION_FEATURE_COLUMNS = [
    "amount",
    "retry_count",
    "payment_method",
    "bank",
    "device_type",
    "failure_code",
    "customer_success_rate",
    "customer_lifetime_value",
    "recent_bank_failure_rate",
    "recent_method_failure_rate",
]

# Customer columns that are static per-customer traits assigned at
# customer-generation time, independent of transaction history/outcomes
# (see data/generate_dataset.py: generate_customers). Safe.
_CUSTOMER_FEATURE_COLUMNS = [
    "preferred_payment_method",
    "preferred_bank",
    "abandonment_rate",
]

# Merchant columns: static per-merchant traits, not derived from
# observed transactions (see data/generate_dataset.py: generate_merchants).
_MERCHANT_FEATURE_COLUMNS = [
    "merchant_category",
    "average_transaction_value",
    "monthly_transaction_volume",
]

_CATEGORICAL_COLUMNS = [
    "payment_method",
    "bank",
    "device_type",
    "failure_code",
    "preferred_payment_method",
    "preferred_bank",
    "merchant_category",
]

_NUMERIC_COLUMNS = [
    "amount",
    "retry_count",
    "customer_success_rate",
    "customer_lifetime_value",
    "recent_bank_failure_rate",
    "recent_method_failure_rate",
    "abandonment_rate",
    "average_transaction_value",
    "monthly_transaction_volume",
    "hour_of_day",
    "day_of_week",
]

# Kept for traceability/splitting; never fed to the model as raw features.
METADATA_COLUMNS = ["transaction_id", "customer_id", "merchant_id", "timestamp"]


def load_raw_frame(session: Session) -> pd.DataFrame:
    """
    Query FAILED transactions joined with the safe Customer/Merchant
    columns above. One row per FAILED transaction, ordered by timestamp.
    Does not derive features or encode categoricals — see
    `build_features` for that.
    """
    stmt = (
        select(
            Transaction.transaction_id,
            Transaction.customer_id,
            Transaction.merchant_id,
            Transaction.timestamp,
            Transaction.amount,
            Transaction.retry_count,
            Transaction.payment_method,
            Transaction.bank,
            Transaction.device_type,
            Transaction.failure_code,
            Transaction.customer_success_rate,
            Transaction.customer_lifetime_value,
            Transaction.recent_bank_failure_rate,
            Transaction.recent_method_failure_rate,
            Customer.preferred_payment_method,
            Customer.preferred_bank,
            Customer.abandonment_rate,
            Merchant.merchant_category,
            Merchant.average_transaction_value,
            Merchant.monthly_transaction_volume,
            Transaction.recovered,
            Transaction.recovery_delay_minutes,
            Transaction.recovered_amount,
        )
        .join(Customer, Transaction.customer_id == Customer.customer_id)
        .join(Merchant, Transaction.merchant_id == Merchant.merchant_id)
        .where(Transaction.status == ELIGIBLE_STATUS)
        .order_by(Transaction.timestamp.asc())
    )
    rows = session.execute(stmt).all()
    columns = list(stmt.selected_columns.keys())
    return pd.DataFrame(rows, columns=columns)


def _add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive cyclical/calendar features from the transaction timestamp.

    The raw absolute timestamp is kept only as metadata (for the
    time-aware split), not as a raw model feature, since an absolute
    timestamp doesn't generalize to future dates.
    """
    df = df.copy()
    df["hour_of_day"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    return df


def _encode_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    """
    One-hot encode categorical columns using the FIXED vocabulary from
    ml.config.CATEGORICAL_VOCAB (sourced from the generator's own
    constants), not the values observed in this particular frame. This
    guarantees train and validation splits produce identical columns
    even if a rare category is absent from one side.
    """
    df = df.copy()
    for col in _CATEGORICAL_COLUMNS:
        df[col] = df[col].fillna("UNKNOWN")
        categories = list(CATEGORICAL_VOCAB.get(col, sorted(df[col].unique())))
        if "UNKNOWN" not in categories:
            categories = categories + ["UNKNOWN"]
        df[col] = pd.Categorical(df[col], categories=categories)
    dummies = pd.get_dummies(df[_CATEGORICAL_COLUMNS], prefix=_CATEGORICAL_COLUMNS)
    return pd.concat([df.drop(columns=_CATEGORICAL_COLUMNS), dummies], axis=1)


def _coerce_numeric_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Cast DB Numeric columns (returned as python Decimal by psycopg2)
    to float64.

    Without this, columns like `amount` and `customer_success_rate`
    come back as object-dtype Series of decimal.Decimal, which pandas
    silently excludes from numeric aggregation and which scikit-learn
    cannot fit on directly. This must run before `_handle_missing_numeric`
    so median-fill operates on real floats.
    """
    df = df.copy()
    for col in _NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype(float)
    return df


def _handle_missing_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Fill any missing numeric values with the column median.

    None of the columns pulled in here are expected to be NULL for
    FAILED transactions today (verified against the current dataset),
    but this makes the pipeline robust to future generator changes
    instead of silently propagating NaNs into the feature matrix.
    """
    df = df.copy()
    for col in _NUMERIC_COLUMNS:
        if col in df.columns and df[col].isna().any():
            df[col] = df[col].fillna(df[col].median())
    return df


def build_features(session: Session) -> pd.DataFrame:
    """
    Build the full feature+target+metadata frame for FAILED transactions.

    The returned frame still contains LEAKAGE_COLUMNS and
    METADATA_COLUMNS; use `split_features_and_target` to get a clean
    (X, y, metadata) split.
    """
    df = load_raw_frame(session)
    df = _add_time_features(df)
    df = _coerce_numeric_dtypes(df)
    df = _encode_categoricals(df)
    df = _handle_missing_numeric(df)
    return df


def split_features_and_target(df: pd.DataFrame):
    """
    Split a frame produced by `build_features` into (X, y, metadata).

    X: feature matrix. Never contains LEAKAGE_COLUMNS or
       METADATA_COLUMNS.
    y: target Series (bool), from TARGET_COLUMN.
    metadata: transaction_id/customer_id/merchant_id/timestamp, kept for
       traceability and time-aware splitting, not fed to the model.
    """
    y = df[TARGET_COLUMN].astype(bool)
    metadata = df[METADATA_COLUMNS].copy()
    drop_cols = set(LEAKAGE_COLUMNS) | set(METADATA_COLUMNS)
    X = df.drop(columns=[c for c in drop_cols if c in df.columns])
    return X, y, metadata
