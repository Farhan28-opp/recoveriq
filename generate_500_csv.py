import csv
from datetime import datetime, timedelta
import random

def main():
    headers = ["transaction_id", "customer_id", "merchant_id", "amount", "timestamp", "status", "payment_method", "bank", "device_type", "failure_code", "failure_reason"]
    rows = []
    base_time = datetime.utcnow() - timedelta(days=10)
    for i in range(500):
        tx_id = f"TXN500_{i:04d}"
        cid = f"CUST_{random.randint(1, 50)}"
        mid = f"MERCH_{random.randint(1, 10)}"
        amt = round(random.uniform(10, 50000), 2)
        ts = (base_time + timedelta(minutes=i*15)).isoformat() + "Z"
        status = "FAILED" if random.random() < 0.2 else "SUCCESS"
        method = random.choice(["UPI", "CARD", "NETBANKING", "WALLET"])
        bank = random.choice(["HDFC", "ICICI", "SBI", "AXIS"])
        device = random.choice(["MOBILE", "DESKTOP"])
        fcode = "TIMEOUT" if status == "FAILED" else ""
        freason = "Timeout" if status == "FAILED" else ""
        rows.append([tx_id, cid, mid, amt, ts, status, method, bank, device, fcode, freason])

    with open("demo_500.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print("demo_500.csv created.")

if __name__ == "__main__":
    main()
