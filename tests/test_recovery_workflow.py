"""
Tests for the RecoverIQ Recovery Workflow Orchestration (Day 5).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.database import SessionLocal, engine, Base
from backend.main import app
from backend.models import RecoveryWorkflow
from backend.schemas.recovery import WorkflowStatus
from backend.services.decision_engine import MAX_AUTOMATED_RETRIES

# Ensure tables exist for tests
Base.metadata.create_all(bind=engine)

client = TestClient(app)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MODEL_EXISTS = (
    (_PROJECT_ROOT / "models" / "recovery_model.joblib").exists()
    and (_PROJECT_ROOT / "models" / "model_metadata.json").exists()
)

requires_model = pytest.mark.skipif(
    not _MODEL_EXISTS,
    reason="Model artifacts not found. Run `python -m ml.training.train` first.",
)


@pytest.fixture
def db_session():
    """Provides a database session for direct inspection."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _valid_request(failure_code="TIMEOUT"):
    return {
        "amount": 1500.00,
        "retry_count": 0,
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
        "failure_code": failure_code,
        "preferred_payment_method": "UPI",
        "preferred_bank": "HDFC",
        "merchant_category": "E_COMMERCE",
    }


class TestRecoveryWorkflowAPI:

    @requires_model
    def test_create_recovery_workflow(self, db_session: Session):
        """Test POST /recovery creates a PENDING workflow."""
        response = client.post("/recovery", json=_valid_request())
        assert response.status_code == 200
        data = response.json()
        
        assert "recovery_id" in data
        assert data["status"] == WorkflowStatus.PENDING.value
        assert data["attempt_count"] == 0
        assert data["max_attempts"] == MAX_AUTOMATED_RETRIES
        assert data["recommended_action"] != "NO_ACTION"
        
        # Verify DB
        workflow = db_session.query(RecoveryWorkflow).filter_by(recovery_id=data["recovery_id"]).first()
        assert workflow is not None
        assert workflow.status == WorkflowStatus.PENDING.value

    @requires_model
    def test_get_recovery_workflow(self):
        """Test GET /recovery/{id}."""
        create_resp = client.post("/recovery", json=_valid_request())
        recovery_id = create_resp.json()["recovery_id"]
        
        get_resp = client.get(f"/recovery/{recovery_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["recovery_id"] == recovery_id

    @requires_model
    def test_execute_workflow_success(self):
        """Test executing a valid PENDING workflow transitions to COMPLETED."""
        create_resp = client.post("/recovery", json=_valid_request("TIMEOUT"))
        recovery_id = create_resp.json()["recovery_id"]
        
        exec_resp = client.post(f"/recovery/{recovery_id}/execute")
        assert exec_resp.status_code == 200
        data = exec_resp.json()
        
        assert data["status"] == WorkflowStatus.COMPLETED.value
        assert data["success"] is True
        assert data["simulated"] is True
        
        # Verify updated state
        get_resp = client.get(f"/recovery/{recovery_id}")
        assert get_resp.json()["status"] == WorkflowStatus.COMPLETED.value
        assert get_resp.json()["attempt_count"] == 1

    @requires_model
    def test_fraud_escalation_safety(self):
        """Test FRAUD_CHECK correctly transitions to ESCALATED and is not executed."""
        create_resp = client.post("/recovery", json=_valid_request("FRAUD_CHECK"))
        recovery_id = create_resp.json()["recovery_id"]
        
        # Fraud check triggers manual review recommendation
        assert create_resp.json()["recommended_action"] == "ESCALATE_MANUAL_REVIEW"
        
        exec_resp = client.post(f"/recovery/{recovery_id}/execute")
        assert exec_resp.status_code == 200
        data = exec_resp.json()
        
        assert data["status"] == WorkflowStatus.ESCALATED.value
        assert data["success"] is False
        assert "escalated" in data["message"].lower() or "manual review" in data["message"].lower()

    @requires_model
    def test_idempotency_completed_workflow(self):
        """Test that executing a COMPLETED workflow is idempotent."""
        create_resp = client.post("/recovery", json=_valid_request("TIMEOUT"))
        recovery_id = create_resp.json()["recovery_id"]
        
        # First execution
        exec_1 = client.post(f"/recovery/{recovery_id}/execute")
        assert exec_1.json()["status"] == WorkflowStatus.COMPLETED.value
        
        # Second execution should return COMPLETED without bumping attempt count
        exec_2 = client.post(f"/recovery/{recovery_id}/execute")
        assert exec_2.status_code == 200
        assert exec_2.json()["status"] == WorkflowStatus.COMPLETED.value
        
        get_resp = client.get(f"/recovery/{recovery_id}")
        assert get_resp.json()["attempt_count"] == 1  # Still 1

    @requires_model
    def test_retry_limit_protection(self, db_session: Session):
        """Test that reaching max attempts blocks further execution."""
        create_resp = client.post("/recovery", json=_valid_request("TIMEOUT"))
        recovery_id = create_resp.json()["recovery_id"]
        
        # Manually force the DB state to simulate exhausted retries
        workflow = db_session.query(RecoveryWorkflow).filter_by(recovery_id=recovery_id).first()
        workflow.attempt_count = MAX_AUTOMATED_RETRIES
        db_session.commit()
        
        exec_resp = client.post(f"/recovery/{recovery_id}/execute")
        data = exec_resp.json()
        
        assert data["status"] == WorkflowStatus.BLOCKED.value
        assert data["success"] is False
        assert "limit" in data["message"].lower()

    @requires_model
    def test_invalid_recovery_id(self):
        exec_resp = client.post("/recovery/nonexistent-id-123/execute")
        assert exec_resp.status_code == 404
        
        get_resp = client.get("/recovery/nonexistent-id-123")
        assert get_resp.status_code == 404

    @requires_model
    def test_list_workflows(self):
        """Test GET /recovery returns a list of workflows."""
        # Create a new workflow to ensure list is not empty
        client.post("/recovery", json=_valid_request())
        
        resp = client.get("/recovery")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "recovery_id" in data[0]
        
    @requires_model
    def test_get_stats(self):
        """Test GET /recovery/stats returns expected aggregates."""
        resp = client.get("/recovery/stats")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "total_cases" in data
        assert "total_amount_at_risk" in data
        assert "total_expected_recovery" in data
        assert "average_recovery_probability" in data
        assert "pending_count" in data
        assert "executing_count" in data
        assert "completed_count" in data
        
        assert data["total_cases"] >= 1
        assert data["total_amount_at_risk"] >= 1500.00
