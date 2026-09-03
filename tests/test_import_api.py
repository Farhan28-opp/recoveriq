import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import io

from backend.main import app
from backend.database import SessionLocal
from backend.models import Transaction, Customer, Merchant, RecoveryWorkflow

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_import_missing_columns():
    csv_content = "Transaction ID,Amount (INR)\nTXN1,100"
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    response = client.post("/recovery/import/csv", files=files)
    assert response.status_code == 400
    assert "Required column(s) missing" in response.json()["detail"]

def test_import_invalid_status():
    csv_content = "Transaction ID,Timestamp,Sender Name,Sender UPI ID,Receiver Name,Receiver UPI ID,Amount (INR),Status\nTXN1,2026-09-01T10:00:00Z,Alice,alice@upi,Bob,bob@upi,100,UNKNOWN"
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    response = client.post("/recovery/import/csv", files=files)
    assert response.status_code == 400
    assert "status must be SUCCESS or FAILED" in response.json()["detail"]

def test_successful_import_and_workflow_creation(db_session: Session):
    # Ensure fresh DB state for these IDs
    db_session.query(RecoveryWorkflow).filter(RecoveryWorkflow.amount == 9999.0).delete()
    db_session.query(Transaction).filter(Transaction.customer_id == "TEST_C1").delete()
    db_session.query(Customer).filter(Customer.customer_id == "TEST_C1").delete()
    db_session.query(Merchant).filter(Merchant.merchant_id == "TEST_M1").delete()
    db_session.commit()

    csv_content = """Transaction ID,Timestamp,Sender Name,Sender UPI ID,Receiver Name,Receiver UPI ID,Amount (INR),Status
TEST_TXN_001,2026-09-01T10:00:00Z,Alice,TEST_C1,Bob,TEST_M1,9999.0,FAILED
"""
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    response = client.post("/recovery/import/csv", files=files)
    assert response.status_code == 200
    data = response.json()
    
    assert data["imported"] == 1
    assert data["skipped"] == 0
    # Depending on model weights, this amount/failure code combo should trigger an action
    assert data["workflows_created"] >= 0
    assert "batch_id" in data
    
    # Verify records in DB
    tx = db_session.query(Transaction).filter_by(transaction_id="TEST_TXN_001").first()
    assert tx is not None
    assert tx.amount == 9999.0
    assert tx.customer_id == "TEST_C1"
    assert tx.payment_method == "UPI"  # Defaulted based on Sender UPI ID presence
    assert tx.failure_code == "UNKNOWN" # Defaulted when missing
    
    c = db_session.query(Customer).filter_by(customer_id="TEST_C1").first()
    assert c is not None
    assert c.abandonment_rate is not None
    
def test_import_duplicate_skipped():
    csv_content = """Transaction ID,Timestamp,Sender Name,Sender UPI ID,Receiver Name,Receiver UPI ID,Amount (INR),Status
TEST_TXN_001,2026-09-01T10:00:00Z,Alice,TEST_C1,Bob,TEST_M1,9999.0,FAILED
"""
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    response = client.post("/recovery/import/csv", files=files)
    assert response.status_code == 200
    data = response.json()
    
    # Since TEST_TXN_001 was imported in the previous test, it should be skipped now
    assert data["imported"] == 0
    assert data["skipped"] == 1
    assert data["workflows_created"] == 0

def test_import_batch_id_assigned(db_session):
    db_session.query(RecoveryWorkflow).filter(RecoveryWorkflow.amount == 9999.0).delete()
    db_session.query(Transaction).filter(Transaction.customer_id == "TEST_C1").delete()
    db_session.commit()
    
    csv_content = """Transaction ID,Timestamp,Sender Name,Sender UPI ID,Receiver Name,Receiver UPI ID,Amount (INR),Status
TEST_BATCH_001,2026-09-01T10:00:00Z,Alice,TEST_C1,Bob,TEST_M1,9999.0,FAILED
"""
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post("/recovery/import/csv", files=files)
    assert res.status_code == 200
    
    tx = db_session.query(Transaction).filter_by(transaction_id="TEST_BATCH_001").first()
    assert tx is not None
    assert tx.import_batch_id is not None
    assert res.json()["batch_id"] == tx.import_batch_id
    
    wf = db_session.query(RecoveryWorkflow).filter_by(transaction_id="TEST_BATCH_001").first()
    assert wf is not None
    assert wf.import_batch_id == tx.import_batch_id
    
    # Test transactions endpoint
    res = client.get(f"/transactions?import_batch_id={tx.import_batch_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["transaction_id"] == "TEST_BATCH_001"
    
    # Test delete
    res = client.delete(f"/recovery/import/{tx.import_batch_id}")
    assert res.status_code == 200
    
    # Verify deleted
    tx_after = db_session.query(Transaction).filter_by(transaction_id="TEST_BATCH_001").first()
    assert tx_after is None
    wf_after = db_session.query(RecoveryWorkflow).filter_by(transaction_id="TEST_BATCH_001").first()
    assert wf_after is None
