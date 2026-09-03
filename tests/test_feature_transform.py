"""
Tests for the RecoverIQ feature transformation layer (Day 4).

Verifies that ``transform_request_to_dataframe`` produces a DataFrame
that exactly matches the 61-column one-hot schema expected by
``RecoveryPredictor``, with correct column names, ordering, and
values.  This is the critical bridge between raw API input and the
ML model.

These tests use the real model metadata (``models/model_metadata.json``)
to validate against the trained model's exact feature contract.

Run with:
    pytest tests/test_feature_transform.py -v
"""

from pathlib import Path

import pytest

from backend.routes.predict import transform_request_to_dataframe
from backend.schemas.prediction import PredictionRequest
from ml.config import CATEGORICAL_VOCAB, LEAKAGE_COLUMNS

# Check if model artifacts exist.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MODEL_EXISTS = (
    (_PROJECT_ROOT / "models" / "recovery_model.joblib").exists()
    and (_PROJECT_ROOT / "models" / "model_metadata.json").exists()
)

requires_model = pytest.mark.skipif(
    not _MODEL_EXISTS,
    reason="Model artifacts not found. Run `python -m ml.training.train` first.",
)


# ====================================================================
# FIXTURES
# ====================================================================

@pytest.fixture
def predictor():
    """Load the real predictor to get authoritative feature_names."""
    from ml.inference.predictor import RecoveryPredictor
    return RecoveryPredictor()


@pytest.fixture
def sample_request() -> PredictionRequest:
    """A valid prediction request with realistic values."""
    return PredictionRequest(
        amount=1500.00,
        retry_count=1,
        customer_success_rate=0.85,
        customer_lifetime_value=25000.00,
        recent_bank_failure_rate=0.05,
        recent_method_failure_rate=0.03,
        abandonment_rate=0.10,
        average_transaction_value=2000.00,
        monthly_transaction_volume=150,
        hour_of_day=14,
        day_of_week=2,
        payment_method="UPI",
        bank="HDFC",
        device_type="MOBILE",
        failure_code="TIMEOUT",
        preferred_payment_method="UPI",
        preferred_bank="HDFC",
        merchant_category="E_COMMERCE",
    )


@pytest.fixture
def unknown_request() -> PredictionRequest:
    """A request with all categorical values set to UNKNOWN."""
    return PredictionRequest(
        amount=500.00,
        retry_count=0,
        customer_success_rate=0.50,
        customer_lifetime_value=5000.00,
        recent_bank_failure_rate=0.10,
        recent_method_failure_rate=0.10,
        abandonment_rate=0.20,
        average_transaction_value=1000.00,
        monthly_transaction_volume=50,
        hour_of_day=9,
        day_of_week=0,
        payment_method="UNKNOWN",
        bank="UNKNOWN",
        device_type="UNKNOWN",
        failure_code="UNKNOWN",
        preferred_payment_method="UNKNOWN",
        preferred_bank="UNKNOWN",
        merchant_category="UNKNOWN",
    )


# ====================================================================
# 1. COLUMN COUNT
# ====================================================================

class TestColumnCount:
    """Verify the transformed DataFrame has exactly 61 columns."""

    @requires_model
    def test_exactly_61_columns(self, predictor, sample_request):
        df = transform_request_to_dataframe(
            sample_request, predictor.feature_names,
        )
        assert df.shape[1] == 61

    @requires_model
    def test_matches_model_feature_count(self, predictor, sample_request):
        df = transform_request_to_dataframe(
            sample_request, predictor.feature_names,
        )
        assert df.shape[1] == predictor.metadata["feature_count"]


# ====================================================================
# 2. EXACT COLUMN NAMES
# ====================================================================

class TestColumnNames:
    """Verify column names match the model metadata exactly."""

    @requires_model
    def test_column_names_match_model(self, predictor, sample_request):
        df = transform_request_to_dataframe(
            sample_request, predictor.feature_names,
        )
        assert list(df.columns) == predictor.feature_names

    @requires_model
    def test_no_missing_model_features(self, predictor, sample_request):
        df = transform_request_to_dataframe(
            sample_request, predictor.feature_names,
        )
        missing = [c for c in predictor.feature_names if c not in df.columns]
        assert missing == [], f"Missing model features: {missing}"

    @requires_model
    def test_no_unexpected_features(self, predictor, sample_request):
        df = transform_request_to_dataframe(
            sample_request, predictor.feature_names,
        )
        extra = [c for c in df.columns if c not in predictor.feature_names]
        assert extra == [], f"Unexpected features: {extra}"


# ====================================================================
# 3. EXACT COLUMN ORDERING
# ====================================================================

class TestColumnOrdering:
    """Verify columns are in the exact order expected by the model."""

    @requires_model
    def test_column_order_matches_model(self, predictor, sample_request):
        df = transform_request_to_dataframe(
            sample_request, predictor.feature_names,
        )
        for i, (actual, expected) in enumerate(
            zip(df.columns, predictor.feature_names)
        ):
            assert actual == expected, (
                f"Column {i}: expected '{expected}', got '{actual}'"
            )


# ====================================================================
# 4. NO LEAKAGE COLUMNS
# ====================================================================

class TestNoLeakage:
    """Verify the transformed DataFrame never contains leakage columns."""

    @requires_model
    def test_no_leakage_columns(self, predictor, sample_request):
        df = transform_request_to_dataframe(
            sample_request, predictor.feature_names,
        )
        leakage = [c for c in LEAKAGE_COLUMNS if c in df.columns]
        assert leakage == [], f"Leakage columns found: {leakage}"


# ====================================================================
# 5. ONE-HOT ENCODING CORRECTNESS
# ====================================================================

class TestOneHotEncoding:
    """Verify one-hot encoding produces correct values."""

    @requires_model
    def test_exactly_one_hot_per_group(self, predictor, sample_request):
        """Each categorical group should have exactly one 1.0."""
        df = transform_request_to_dataframe(
            sample_request, predictor.feature_names,
        )
        for col_name in CATEGORICAL_VOCAB:
            group_cols = [
                c for c in df.columns if c.startswith(f"{col_name}_")
            ]
            group_values = [df[c].iloc[0] for c in group_cols]
            assert sum(group_values) == 1.0, (
                f"Group '{col_name}': expected exactly one 1.0, "
                f"got sum={sum(group_values)}"
            )

    @requires_model
    def test_correct_value_is_hot(self, predictor, sample_request):
        """Verify the correct category has value 1.0."""
        df = transform_request_to_dataframe(
            sample_request, predictor.feature_names,
        )
        # sample_request has payment_method="UPI"
        assert df["payment_method_UPI"].iloc[0] == 1.0
        assert df["payment_method_CARD"].iloc[0] == 0.0
        # sample_request has bank="HDFC"
        assert df["bank_HDFC"].iloc[0] == 1.0
        assert df["bank_ICICI"].iloc[0] == 0.0
        # sample_request has failure_code="TIMEOUT"
        assert df["failure_code_TIMEOUT"].iloc[0] == 1.0
        assert df["failure_code_BANK_DECLINED"].iloc[0] == 0.0

    @requires_model
    def test_unknown_is_hot_when_specified(self, predictor, unknown_request):
        """UNKNOWN values should set the UNKNOWN column to 1.0."""
        df = transform_request_to_dataframe(
            unknown_request, predictor.feature_names,
        )
        for col_name in CATEGORICAL_VOCAB:
            unknown_col = f"{col_name}_UNKNOWN"
            assert unknown_col in df.columns, (
                f"Missing UNKNOWN column: {unknown_col}"
            )
            assert df[unknown_col].iloc[0] == 1.0, (
                f"{unknown_col} should be 1.0 for UNKNOWN input"
            )


# ====================================================================
# 6. NUMERIC VALUES PASSTHROUGH
# ====================================================================

class TestNumericValues:
    """Verify numeric values are passed through unchanged."""

    @requires_model
    def test_numeric_values_passthrough(self, predictor, sample_request):
        df = transform_request_to_dataframe(
            sample_request, predictor.feature_names,
        )
        assert df["amount"].iloc[0] == 1500.0
        assert df["retry_count"].iloc[0] == 1.0
        assert df["customer_success_rate"].iloc[0] == 0.85
        assert df["customer_lifetime_value"].iloc[0] == 25000.0
        assert df["recent_bank_failure_rate"].iloc[0] == 0.05
        assert df["recent_method_failure_rate"].iloc[0] == 0.03
        assert df["abandonment_rate"].iloc[0] == 0.10
        assert df["average_transaction_value"].iloc[0] == 2000.0
        assert df["monthly_transaction_volume"].iloc[0] == 150.0
        assert df["hour_of_day"].iloc[0] == 14.0
        assert df["day_of_week"].iloc[0] == 2.0


# ====================================================================
# 7. SINGLE ROW OUTPUT
# ====================================================================

class TestSingleRow:
    """Verify the output is always a single-row DataFrame."""

    @requires_model
    def test_single_row(self, predictor, sample_request):
        df = transform_request_to_dataframe(
            sample_request, predictor.feature_names,
        )
        assert df.shape[0] == 1


# ====================================================================
# 8. VOCABULARY SOURCE OF TRUTH
# ====================================================================

class TestVocabularySourceOfTruth:
    """Verify the transformation uses the same vocabulary as training."""

    def test_categorical_vocab_has_all_groups(self):
        """CATEGORICAL_VOCAB must cover all 7 categorical columns."""
        expected_groups = {
            "payment_method",
            "bank",
            "device_type",
            "failure_code",
            "preferred_payment_method",
            "preferred_bank",
            "merchant_category",
        }
        assert set(CATEGORICAL_VOCAB.keys()) == expected_groups

    @requires_model
    def test_one_hot_columns_match_vocab_plus_unknown(self, predictor):
        """Each categorical group in model feature_names should have
        exactly len(vocab) + 1 columns (vocab values + UNKNOWN)."""
        for col_name, vocab in CATEGORICAL_VOCAB.items():
            group_cols = [
                c for c in predictor.feature_names
                if c.startswith(f"{col_name}_")
            ]
            expected_count = len(vocab) + 1  # vocab + UNKNOWN
            assert len(group_cols) == expected_count, (
                f"Group '{col_name}': expected {expected_count} one-hot "
                f"columns, got {len(group_cols)}: {group_cols}"
            )


# ====================================================================
# 9. ALL CATEGORICAL VALUES ACCEPTED
# ====================================================================

class TestAllCategoricalValues:
    """Verify every valid categorical value produces valid output."""

    @requires_model
    @pytest.mark.parametrize("payment_method", [
        "UPI", "CARD", "NETBANKING", "WALLET", "UNKNOWN",
    ])
    def test_all_payment_methods(self, predictor, payment_method):
        req = PredictionRequest(
            amount=1000.0, retry_count=0, customer_success_rate=0.5,
            customer_lifetime_value=5000.0, recent_bank_failure_rate=0.1,
            recent_method_failure_rate=0.1, abandonment_rate=0.1,
            average_transaction_value=1000.0, monthly_transaction_volume=50,
            hour_of_day=12, day_of_week=3,
            payment_method=payment_method, bank="HDFC",
            device_type="MOBILE", failure_code="TIMEOUT",
            preferred_payment_method="UPI", preferred_bank="HDFC",
            merchant_category="E_COMMERCE",
        )
        df = transform_request_to_dataframe(req, predictor.feature_names)
        assert df.shape == (1, 61)
        assert list(df.columns) == predictor.feature_names
        assert df[f"payment_method_{payment_method}"].iloc[0] == 1.0

    @requires_model
    @pytest.mark.parametrize("failure_code", [
        "BANK_DECLINED", "INSUFFICIENT_FUNDS", "TIMEOUT", "NETWORK_ERROR",
        "LIMIT_EXCEEDED", "FRAUD_CHECK", "TECHNICAL_ERROR",
        "METHOD_UNAVAILABLE", "UNKNOWN",
    ])
    def test_all_failure_codes(self, predictor, failure_code):
        req = PredictionRequest(
            amount=1000.0, retry_count=0, customer_success_rate=0.5,
            customer_lifetime_value=5000.0, recent_bank_failure_rate=0.1,
            recent_method_failure_rate=0.1, abandonment_rate=0.1,
            average_transaction_value=1000.0, monthly_transaction_volume=50,
            hour_of_day=12, day_of_week=3,
            payment_method="UPI", bank="HDFC",
            device_type="MOBILE", failure_code=failure_code,
            preferred_payment_method="UPI", preferred_bank="HDFC",
            merchant_category="E_COMMERCE",
        )
        df = transform_request_to_dataframe(req, predictor.feature_names)
        assert df.shape == (1, 61)
        assert df[f"failure_code_{failure_code}"].iloc[0] == 1.0


# ====================================================================
# 10. PREDICTOR ACCEPTS TRANSFORMED OUTPUT
# ====================================================================

class TestPredictorAcceptsOutput:
    """End-to-end: predictor successfully predicts on transformed data."""

    @requires_model
    def test_predictor_accepts_transformed_dataframe(
        self, predictor, sample_request,
    ):
        df = transform_request_to_dataframe(
            sample_request, predictor.feature_names,
        )
        probas = predictor.predict_proba(df)
        assert len(probas) == 1
        assert 0.0 <= probas[0] <= 1.0

    @requires_model
    def test_predictor_accepts_unknown_dataframe(
        self, predictor, unknown_request,
    ):
        df = transform_request_to_dataframe(
            unknown_request, predictor.feature_names,
        )
        probas = predictor.predict_proba(df)
        assert len(probas) == 1
        assert 0.0 <= probas[0] <= 1.0
