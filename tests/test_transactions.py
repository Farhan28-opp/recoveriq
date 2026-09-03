import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.main import app
from backend.database import SessionLocal
from backend.models import Transaction, RecoveryWorkflow, Customer, Merchant

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_search_transactions(db_session: Session):
    # Setup some transactions
    tx_id = "TEST_SEARCH_001"
    db_session.query(Transaction).filter_by(transaction_id=tx_id).delete()
    db_session.merge(Customer(customer_id="TEST_CUST_1"))
    db_session.merge(Merchant(merchant_id="TEST_MERCH_1"))
    db_session.commit()
    
    tx = Transaction(
        transaction_id=tx_id,
        customer_id="TEST_CUST_1",
        merchant_id="TEST_MERCH_1",
        amount=500.0,
        currency="INR",
        timestamp=datetime.now(timezone.utc),
        status="FAILED",
        import_batch_id="BATCH_X"
    )
    db_session.add(tx)
    db_session.commit()

    # Search by tx id
    res = client.get(f"/transactions?search={tx_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any(item["transaction_id"] == tx_id for item in data["items"])

    # Search by batch id
    res = client.get("/transactions?import_batch_id=BATCH_X")
    assert res.status_code == 200
    data = res.json()
    assert any(item["transaction_id"] == tx_id for item in data["items"])

    # Cleanup
    db_session.query(Transaction).filter_by(transaction_id=tx_id).delete()
    db_session.commit()

def test_edit_transaction_success(db_session: Session):
    tx_id = "TEST_EDIT_001"
    db_session.query(Transaction).filter_by(transaction_id=tx_id).delete()
    db_session.merge(Customer(customer_id="TEST_CUST_2"))
    db_session.merge(Merchant(merchant_id="TEST_MERCH_2"))
    db_session.commit()
    
    tx = Transaction(
        transaction_id=tx_id,
        customer_id="TEST_CUST_2",
        merchant_id="TEST_MERCH_2",
        amount=100.0,
        currency="INR",
        timestamp=datetime.now(timezone.utc),
        status="FAILED",
        failure_reason="Old Reason"
    )
    db_session.add(tx)
    db_session.commit()

    res = client.patch(f"/transactions/{tx_id}", json={
        "amount": 250.0,
        "failure_reason": "New Reason",
        "status": "SUCCESS"
    })
    
    assert res.status_code == 200, f"Status: {res.status_code}, Body: {res.text}"
    data = res.json()
    print("RESPONSE DATA:", data)
    assert "amount" in data, f"Data missing amount: {data}"
    assert data["amount"] == 250.0
    assert data["failure_reason"] == "New Reason"
    assert data["status"] == "SUCCESS"
    
    # Verify in DB
    updated_tx = db_session.query(Transaction).filter_by(transaction_id=tx_id).first()
    assert updated_tx.amount == 250.0
    assert updated_tx.failure_reason == "New Reason"

    # Cleanup
    db_session.query(Transaction).filter_by(transaction_id=tx_id).delete()
    db_session.commit()

def test_bulk_delete_transactions_with_workflows(db_session: Session):
    tx_id_1 = "TEST_DEL_001"
    tx_id_2 = "TEST_DEL_002"
    
    db_session.query(RecoveryWorkflow).filter(RecoveryWorkflow.transaction_id.in_([tx_id_1, tx_id_2])).delete()
    db_session.query(Transaction).filter(Transaction.transaction_id.in_([tx_id_1, tx_id_2])).delete()
    db_session.merge(Customer(customer_id="C1"))
    db_session.merge(Customer(customer_id="C2"))
    db_session.merge(Merchant(merchant_id="M1"))
    db_session.merge(Merchant(merchant_id="M2"))
    db_session.commit()
    
    tx1 = Transaction(
        transaction_id=tx_id_1,
        customer_id="C1",
        merchant_id="M1",
        amount=100.0,
        currency="INR",
        timestamp=datetime.now(timezone.utc),
        status="FAILED"
    )
    tx2 = Transaction(
        transaction_id=tx_id_2,
        customer_id="C2",
        merchant_id="M2",
        amount=200.0,
        currency="INR",
        timestamp=datetime.now(timezone.utc),
        status="FAILED"
    )
    db_session.add(tx1)
    db_session.add(tx2)
    db_session.commit()
    
    wf1 = RecoveryWorkflow(
        recovery_id="REC_TEST_001",
        transaction_id=tx_id_1,
        amount=100.0,
        recovery_probability=0.5,
        risk_tier="HIGH",
        recommended_action="SEND_SMS",
        failure_code="INSUFFICIENT_FUNDS",
        expected_recovery_value=50.0,
        reason="Test reason",
        model_version="1.0"
    )
    db_session.add(wf1)
    db_session.commit()
    
    res = client.request("DELETE", "/transactions", json={
        "transaction_ids": [tx_id_1, tx_id_2]
    })
    
    assert res.status_code == 200
    data = res.json()
    assert data["deleted_transactions"] == 2
    assert data["deleted_workflows"] == 1
    
    # Verify removed
    assert db_session.query(Transaction).filter_by(transaction_id=tx_id_1).first() is None
    assert db_session.query(Transaction).filter_by(transaction_id=tx_id_2).first() is None
    assert db_session.query(RecoveryWorkflow).filter_by(recovery_id="REC_TEST_001").first() is None
