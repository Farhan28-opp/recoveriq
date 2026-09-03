import csv
from datetime import datetime, timedelta

def main():
    headers = ["transaction_id", "customer_id", "merchant_id", "amount", "timestamp", "status", "payment_method", "bank", "device_type", "failure_code", "failure_reason"]
    rows = [
        ["DEMO_TXN_001", "DEMO_CUST_1", "DEMO_MERCH_1", "1500.0", (datetime.utcnow() - timedelta(minutes=50)).isoformat(), "FAILED", "UPI", "HDFC", "MOBILE", "TIMEOUT", "Gateway timeout"],
        ["DEMO_TXN_002", "DEMO_CUST_1", "DEMO_MERCH_1", "1500.0", (datetime.utcnow() - timedelta(minutes=40)).isoformat(), "SUCCESS", "UPI", "HDFC", "MOBILE", "", ""],
        ["DEMO_TXN_003", "DEMO_CUST_2", "DEMO_MERCH_2", "8500.0", (datetime.utcnow() - timedelta(minutes=30)).isoformat(), "FAILED", "CARD", "ICICI", "DESKTOP", "BANK_DECLINED", "Bank declined"],
        ["DEMO_TXN_004", "DEMO_CUST_3", "DEMO_MERCH_1", "250.0", (datetime.utcnow() - timedelta(minutes=20)).isoformat(), "FAILED", "WALLET", "UNKNOWN", "MOBILE", "INSUFFICIENT_FUNDS", "Low balance"],
        ["DEMO_TXN_005", "DEMO_CUST_4", "DEMO_MERCH_3", "45000.0", (datetime.utcnow() - timedelta(minutes=10)).isoformat(), "FAILED", "NETBANKING", "SBI", "DESKTOP", "LIMIT_EXCEEDED", "Daily limit"],
    ]
    with open("demo_transactions.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print("demo_transactions.csv created.")

if __name__ == "__main__":
    main()
