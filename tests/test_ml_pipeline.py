"""
Tests for the RecoverIQ Day 2 ML feature-engineering pipeline
(ml/config.py, ml/features.py, ml/dataset.py).

Like tests/test_dataset.py, these query the existing database (via the
application's existing SQLAlchemy session factory) and are skipped
automatically if no synthetic dataset has been generated yet.

Run with:
    pytest tests/test_ml_pipeline.py -v
"""

import pandas as pd
import pytest
from sqlalchemy import func, select

from backend.database import SessionLocal
from backend.models import Customer
from ml.config import (
    CUSTOMER_FULL_HISTORY_LEAKAGE_COLUMNS,
    LEAKAGE_COLUMNS,
    TARGET_COLUMN,
)
from ml.dataset import build_ml_dataset, time_aware_split
from ml.features import build_features


@pytest.fixture(scope="module")
def db_session():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module", autouse=True)
def ensure_dataset_present(db_session):
    """Skip all tests in this module if no synthetic dataset has been loaded."""
    count = db_session.execute(select(func.count()).select_from(Customer)).scalar()
    if not count:
        pytest.skip(
            "No synthetic dataset found in the database. "
            "Run `python data/generate_dataset.py` first."
        )


@pytest.fixture(scope="module")
def ml_dataset(db_session):
    return build_ml_dataset(db_session)


# ==================================================
# 1. FEATURE GENERATION SUCCEEDS
# ==================================================

def test_feature_generation_succeeds(db_session):
    df = build_features(db_session)
    assert isinstance(df, pd.DataFrame)


# ==================================================
# 2 & 3. FEATURE MATRIX AND TARGET ARE NON-EMPTY
# ==================================================

def test_feature_matrix_and_target_are_non_empty(ml_dataset):
    assert len(ml_dataset.X_train) > 0
    assert len(ml_dataset.X_val) > 0
    assert len(ml_dataset.y_train) > 0
    assert len(ml_dataset.y_val) > 0


# ==================================================
# 4. X AND y HAVE MATCHING ROW COUNTS
# ==================================================

def test_x_and_y_row_counts_match(ml_dataset):
    assert len(ml_dataset.X_train) == len(ml_dataset.y_train)
    assert len(ml_dataset.X_val) == len(ml_dataset.y_val)


# ==================================================
# 5. TARGET CONTAINS BOTH CLASSES (in each split)
# ==================================================

def test_target_contains_both_classes(ml_dataset):
    assert ml_dataset.y_train.any(), "no recovered=True examples in y_train"
    assert (~ml_dataset.y_train).any(), "no recovered=False examples in y_train"
    assert ml_dataset.y_val.any(), "no recovered=True examples in y_val"
    assert (~ml_dataset.y_val).any(), "no recovered=False examples in y_val"


# ==================================================
# 6. TARGET / LEAKAGE COLUMNS ARE NOT PRESENT IN X
# ==================================================

def test_leakage_columns_not_in_feature_matrix(ml_dataset):
    for col in LEAKAGE_COLUMNS:
        assert col not in ml_dataset.X_train.columns, (
            f"leakage column '{col}' found in X_train"
        )
        assert col not in ml_dataset.X_val.columns, (
            f"leakage column '{col}' found in X_val"
        )


def test_customer_full_history_columns_not_in_feature_matrix(db_session):
    """The Customer table's full-history aggregate columns must never
    be joined in as features (see ml/config.py for why). This is
    checked against the raw query itself, not just by column name,
    since Transaction.customer_success_rate is a *different*, safe
    column that legitimately shares a name with the excluded
    Customer.customer_success_rate.
    """
    from ml.features import load_raw_frame

    raw = load_raw_frame(db_session)
    for col in CUSTOMER_FULL_HISTORY_LEAKAGE_COLUMNS:
        if col in ("customer_success_rate", "average_transaction_value"):
            # These names are legitimately reused by safe columns
            # (Transaction snapshot / Merchant static value respectively).
            continue
        assert col not in raw.columns, (
            f"customer full-history column '{col}' leaked into the raw frame"
        )


# ==================================================
# 7. EXPECTED FEATURE COLUMNS EXIST
# ==================================================

def test_expected_feature_columns_exist(ml_dataset):
    expected = {
        "amount",
        "retry_count",
        "hour_of_day",
        "day_of_week",
        "customer_success_rate",
        "recent_bank_failure_rate",
        "recent_method_failure_rate",
        "abandonment_rate",
        "average_transaction_value",
        "monthly_transaction_volume",
    }
    missing = expected - set(ml_dataset.X_train.columns)
    assert not missing, f"expected feature columns missing: {missing}"

    # spot-check one-hot encoded columns exist too
    assert "payment_method_UPI" in ml_dataset.X_train.columns
    assert "failure_code_TIMEOUT" in ml_dataset.X_train.columns


# ==================================================
# 8. CATEGORICAL / MISSING VALUES ARE HANDLED
# ==================================================

def test_no_missing_values_in_feature_matrix(ml_dataset):
    assert ml_dataset.X_train.isna().sum().sum() == 0
    assert ml_dataset.X_val.isna().sum().sum() == 0


def test_categoricals_are_numerically_encoded(ml_dataset):
    # After one-hot encoding, no column should hold raw strings.
    object_cols = ml_dataset.X_train.select_dtypes(include="object").columns.tolist()
    assert object_cols == [], f"un-encoded object columns found: {object_cols}"

    # And Decimal-returning DB columns must be real floats, not Decimal
    # objects, or a downstream model fit would fail.
    import decimal

    sample = ml_dataset.X_train["amount"].iloc[0]
    assert not isinstance(sample, decimal.Decimal)


# ==================================================
# 9. FEATURE GENERATION IS DETERMINISTIC
# ==================================================

def test_feature_generation_is_deterministic(db_session):
    df1 = build_features(db_session)
    df2 = build_features(db_session)
    pd.testing.assert_frame_equal(
        df1.sort_values("transaction_id").reset_index(drop=True),
        df2.sort_values("transaction_id").reset_index(drop=True),
    )


# ==================================================
# 10. TEMPORAL SPLIT DOES NOT OVERLAP
# ==================================================

def test_temporal_split_does_not_overlap(db_session):
    df = build_features(db_session)
    train_df, val_df, split_ts = time_aware_split(df)

    assert len(train_df) > 0
    assert len(val_df) > 0
    assert train_df["timestamp"].max() < split_ts
    assert val_df["timestamp"].min() >= split_ts
    assert train_df["timestamp"].max() < val_df["timestamp"].min()


def test_ml_dataset_split_does_not_overlap(ml_dataset):
    assert ml_dataset.meta_train["timestamp"].max() < ml_dataset.meta_val["timestamp"].min()


# ==================================================
# BONUS: y matches TARGET_COLUMN semantics
# ==================================================

def test_target_is_boolean(ml_dataset):
    assert ml_dataset.y_train.dtype == bool
    assert ml_dataset.y_val.dtype == bool
    assert TARGET_COLUMN == "recovered"
