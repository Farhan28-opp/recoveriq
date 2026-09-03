import pytest
from fastapi.testclient import TestClient
import io
import datetime
import random
import uuid

from backend.main import app

client = TestClient(app)

def generate_csv(num_rows: int):
    lines = ["Transaction ID,Timestamp,Sender Name,Sender UPI ID,Receiver Name,Receiver UPI ID,Amount (INR),Status"]
    for i in range(num_rows):
        tx_id = str(uuid.uuid4())
        ts = (datetime.datetime.now() - datetime.timedelta(minutes=i)).isoformat() + "Z"
        status = random.choice(["SUCCESS", "FAILED"])
        amount = round(random.uniform(10, 5000), 2)
        lines.append(f"{tx_id},{ts},User{i},user{i}@upi,Merchant{i%5},merchant{i%5}@upi,{amount},{status}")
    return "\n".join(lines)

def test_sizes():
    for count in [10, 100, 500, 1000]:
        csv_content = generate_csv(count)
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
        res = client.post("/recovery/import/csv", files=files)
        assert res.status_code == 200, res.text
        data = res.json()
        print(f"Tested {count} rows: Imported {data['imported']}, Skipped {data['skipped']}, Workflows {data['workflows_created']}")

if __name__ == "__main__":
    test_sizes()
