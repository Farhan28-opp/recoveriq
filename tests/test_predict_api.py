"""
Tests for the RecoverIQ Prediction API (Day 4).

These tests exercise the ``POST /predict`` and ``GET /model/info``
endpoints via FastAPI's TestClient.  They use the real persisted model
artifacts (``models/recovery_model.joblib`` and
``models/model_metadata.json``) to verify end-to-end integration.

Tests that do NOT require a model artifact are unconditional.
Tests that DO require model artifacts are skipped if the model has
not been trained.

Run with:
    pytest tests/test_predict_api.py -v
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

# Check if model artifacts exist (some tests need the real model).
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
# SAMPLE REQUEST FIXTURES
# ====================================================================

def _valid_request() -> dict:
    """A valid prediction request with realistic values."""
    return {
        "amount": 1500.00,
        "retry_count": 1,
        "customer_success_rate": 0.85,
        "customer_lifetime_value": 25000.00,
        "recent_bank_failure_rate": 0.05,
        "recent_method_failure_rate": 0.03,
        "abandonment_rate": 0.10,
        "average_transaction_value": 2000.00,
        "monthly_transaction_volume": 150,
        "hour_of_day": 14,
        "day_of_week": 2,
        "payment_method": "UPI",
        "bank": "HDFC",
        "device_type": "MOBILE",
        "failure_code": "TIMEOUT",
        "preferred_payment_method": "UPI",
        "preferred_bank": "HDFC",
        "merchant_category": "E_COMMERCE",
    }


# ====================================================================
# 1. EXISTING ENDPOINTS STILL WORK
# ====================================================================

class TestExistingEndpoints:
    """Verify Day 1 endpoints are not broken."""

    def test_root_endpoint(self):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["service"] == "RecoverIQ"

    def test_health_endpoint(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ====================================================================
# 2. VALID PREDICTION REQUEST
# ====================================================================

class TestValidPrediction:
    """Verify POST /predict with valid input."""

    @requires_model
    def test_valid_request_returns_200(self):
        response = client.post("/predict", json=_valid_request())
        assert response.status_code == 200

    @requires_model
    def test_response_has_required_fields(self):
        response = client.post("/predict", json=_valid_request())
        data = response.json()
        assert "recovery_probability" in data
        assert "risk_tier" in data
        assert "recommended_action" in data
        assert "expected_recovery_value" in data
        assert "reason" in data
        assert "model_version" in data

    @requires_model
    def test_probability_in_valid_range(self):
        response = client.post("/predict", json=_valid_request())
        prob = response.json()["recovery_probability"]
        assert 0.0 <= prob <= 1.0

    @requires_model
    def test_risk_tier_is_valid(self):
        response = client.post("/predict", json=_valid_request())
        tier = response.json()["risk_tier"]
        assert tier in {"HIGH", "MEDIUM", "LOW"}

    @requires_model
    def test_action_is_valid(self):
        response = client.post("/predict", json=_valid_request())
        action = response.json()["recommended_action"]
        valid_actions = {
            "RETRY_PAYMENT", "DELAYED_RETRY", "SEND_PAYMENT_REMINDER",
            "SUGGEST_ALTERNATIVE_METHOD", "ESCALATE_MANUAL_REVIEW",
            "NO_ACTION",
        }
        assert action in valid_actions

    @requires_model
    def test_expected_recovery_value_is_positive(self):
        response = client.post("/predict", json=_valid_request())
        erv = response.json()["expected_recovery_value"]
        assert erv >= 0.0

    @requires_model
    def test_expected_recovery_value_calculation(self):
        """ERV should equal probability × amount."""
        response = client.post("/predict", json=_valid_request())
        data = response.json()
        prob = data["recovery_probability"]
        amount = _valid_request()["amount"]
        expected = round(prob * amount, 2)
        assert data["expected_recovery_value"] == expected

    @requires_model
    def test_reason_is_nonempty_string(self):
        response = client.post("/predict", json=_valid_request())
        reason = response.json()["reason"]
        assert isinstance(reason, str)
        assert len(reason) > 0

    @requires_model
    def test_model_version_is_present(self):
        response = client.post("/predict", json=_valid_request())
        version = response.json()["model_version"]
        assert isinstance(version, str)
        assert len(version) > 0


# ====================================================================
# 3. REQUEST VALIDATION — MISSING FIELDS
# ====================================================================

class TestMissingFields:
    """Verify missing required fields produce 422."""

    def test_empty_body(self):
        response = client.post("/predict", json={})
        assert response.status_code == 422

    def test_missing_amount(self):
        req = _valid_request()
        del req["amount"]
        response = client.post("/predict", json=req)
        assert response.status_code == 422

    def test_missing_payment_method(self):
        req = _valid_request()
        del req["payment_method"]
        response = client.post("/predict", json=req)
        assert response.status_code == 422

    def test_missing_failure_code(self):
        req = _valid_request()
        del req["failure_code"]
        response = client.post("/predict", json=req)
        assert response.status_code == 422


# ====================================================================
# 4. REQUEST VALIDATION — INVALID NUMERIC VALUES
# ====================================================================

class TestInvalidNumericValues:
    """Verify invalid numeric values produce 422."""

    def test_negative_amount(self):
        req = _valid_request()
        req["amount"] = -100.0
        response = client.post("/predict", json=req)
        assert response.status_code == 422

    def test_zero_amount(self):
        req = _valid_request()
        req["amount"] = 0.0
        response = client.post("/predict", json=req)
        assert response.status_code == 422

    def test_negative_retry_count(self):
        req = _valid_request()
        req["retry_count"] = -1
        response = client.post("/predict", json=req)
        assert response.status_code == 422

    def test_success_rate_above_one(self):
        req = _valid_request()
        req["customer_success_rate"] = 1.5
        response = client.post("/predict", json=req)
        assert response.status_code == 422

    def test_success_rate_below_zero(self):
        req = _valid_request()
        req["customer_success_rate"] = -0.1
        response = client.post("/predict", json=req)
        assert response.status_code == 422

    def test_hour_out_of_range(self):
        req = _valid_request()
        req["hour_of_day"] = 25
        response = client.post("/predict", json=req)
        assert response.status_code == 422

    def test_day_out_of_range(self):
        req = _valid_request()
        req["day_of_week"] = 7
        response = client.post("/predict", json=req)
        assert response.status_code == 422


# ====================================================================
# 5. REQUEST VALIDATION — INVALID CATEGORICAL VALUES
# ====================================================================

class TestInvalidCategoricalValues:
    """Verify invalid categorical values produce 422."""

    def test_invalid_payment_method(self):
        req = _valid_request()
        req["payment_method"] = "BITCOIN"
        response = client.post("/predict", json=req)
        assert response.status_code == 422

    def test_invalid_bank(self):
        req = _valid_request()
        req["bank"] = "BANK_OF_MARS"
        response = client.post("/predict", json=req)
        assert response.status_code == 422

    def test_invalid_failure_code(self):
        req = _valid_request()
        req["failure_code"] = "ALIEN_INTERFERENCE"
        response = client.post("/predict", json=req)
        assert response.status_code == 422

    def test_invalid_merchant_category(self):
        req = _valid_request()
        req["merchant_category"] = "MOON_BASE"
        response = client.post("/predict", json=req)
        assert response.status_code == 422


# ====================================================================
# 6. MODEL INFO ENDPOINT
# ====================================================================

class TestModelInfo:
    """Verify GET /model/info."""

    @requires_model
    def test_model_info_returns_200(self):
        response = client.get("/model/info")
        assert response.status_code == 200

    @requires_model
    def test_model_info_has_required_fields(self):
        response = client.get("/model/info")
        data = response.json()
        assert "version" in data
        assert "model_type" in data
        assert "feature_count" in data

    @requires_model
    def test_model_info_feature_count(self):
        response = client.get("/model/info")
        assert response.json()["feature_count"] == 61

    @requires_model
    def test_model_info_does_not_expose_paths(self):
        """Model info must not expose filesystem paths."""
        response = client.get("/model/info")
        text = str(response.json())
        # Should not contain absolute paths
        assert "/Users/" not in text
        assert "/home/" not in text
        assert "\\Users\\" not in text


# ====================================================================
# 7. DIFFERENT FAILURE CODES PRODUCE VALID DECISIONS
# ====================================================================

class TestDifferentFailureCodes:
    """Verify all supported failure codes produce valid responses."""

    @requires_model
    @pytest.mark.parametrize("failure_code", [
        "BANK_DECLINED",
        "INSUFFICIENT_FUNDS",
        "TIMEOUT",
        "NETWORK_ERROR",
        "LIMIT_EXCEEDED",
        "FRAUD_CHECK",
        "TECHNICAL_ERROR",
        "METHOD_UNAVAILABLE",
        "UNKNOWN",
    ])
    def test_each_failure_code_produces_valid_response(self, failure_code):
        req = _valid_request()
        req["failure_code"] = failure_code
        response = client.post("/predict", json=req)
        assert response.status_code == 200
        data = response.json()
        assert data["risk_tier"] in {"HIGH", "MEDIUM", "LOW"}


# ====================================================================
# 8. DETERMINISM
# ====================================================================

class TestAPIDeterminism:
    """Verify the API produces deterministic results."""

    @requires_model
    def test_same_request_same_response(self):
        req = _valid_request()
        r1 = client.post("/predict", json=req).json()
        r2 = client.post("/predict", json=req).json()
        assert r1 == r2
