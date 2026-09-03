from fastapi.testclient import TestClient
from backend.main import app
from backend.models import Transaction, RecoveryWorkflow
from backend.database import SessionLocal
import io

client = TestClient(app)

def main():
    # 1. 500 row test
    with open("demo_500.csv", "rb") as f:
        resp = client.post("/recovery/import/csv", files={"file": ("demo_500.csv", f, "text/csv")})
    
    print("500-row test status:", resp.status_code)
    print("500-row test response:", resp.json())
    assert resp.status_code == 200, "500-row upload failed"

    # 2. Rollback test
    # Submit invalid CSV that fails during DB insertion (e.g., amount is invalid for DB schema but parsed as string initially... wait, parse_csv validates amount as float. We can simulate DB failure by using a string that is too long for a column, e.g. transaction_id > 255 chars)
    invalid_tx_id = "X" * 300
    csv_content = f"""transaction_id,customer_id,merchant_id,amount,timestamp,status,payment_method,bank,device_type,failure_code
{invalid_tx_id},C1,M1,100,2026-09-01T10:00:00Z,FAILED,UPI,HDFC,MOBILE,TIMEOUT
"""
    db = SessionLocal()
    initial_tx_count = db.query(Transaction).count()
    initial_wf_count = db.query(RecoveryWorkflow).count()
    
    resp_bad = client.post("/recovery/import/csv", files={"file": ("bad.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")})
    
    print("Rollback test status:", resp_bad.status_code)
    
    final_tx_count = db.query(Transaction).count()
    final_wf_count = db.query(RecoveryWorkflow).count()
    print(f"Transactions: {initial_tx_count} -> {final_tx_count}")
    print(f"Workflows: {initial_wf_count} -> {final_wf_count}")
    assert initial_tx_count == final_tx_count, "Rollback failed: Transactions inserted"
    assert initial_wf_count == final_wf_count, "Rollback failed: Workflows inserted"

if __name__ == "__main__":
    main()
