import requests

base_url = "http://localhost:8000"

payloads = [
    {
        "amount": 12400.0,
        "retry_count": 0,
        "customer_success_rate": 0.85,
        "customer_lifetime_value": 50000.0,
        "recent_bank_failure_rate": 0.05,
        "recent_method_failure_rate": 0.02,
        "abandonment_rate": 0.1,
        "average_transaction_value": 1500.0,
        "monthly_transaction_volume": 10,
        "hour_of_day": 14,
        "day_of_week": 3,
        "payment_method": "UPI",
        "bank": "HDFC",
        "device_type": "MOBILE",
        "failure_code": "INSUFFICIENT_FUNDS",
        "preferred_payment_method": "UPI",
        "preferred_bank": "HDFC",
        "merchant_category": "E_COMMERCE"
    },
    {
        "amount": 8200.0,
        "retry_count": 1,
        "customer_success_rate": 0.60,
        "customer_lifetime_value": 20000.0,
        "recent_bank_failure_rate": 0.15,
        "recent_method_failure_rate": 0.1,
        "abandonment_rate": 0.2,
        "average_transaction_value": 800.0,
        "monthly_transaction_volume": 5,
        "hour_of_day": 10,
        "day_of_week": 1,
        "payment_method": "CARD",
        "bank": "ICICI",
        "device_type": "DESKTOP",
        "failure_code": "BANK_DECLINED",
        "preferred_payment_method": "CARD",
        "preferred_bank": "ICICI",
        "merchant_category": "TRAVEL"
    },
    {
        "amount": 4500.0,
        "retry_count": 0,
        "customer_success_rate": 0.90,
        "customer_lifetime_value": 10000.0,
        "recent_bank_failure_rate": 0.02,
        "recent_method_failure_rate": 0.01,
        "abandonment_rate": 0.05,
        "average_transaction_value": 4500.0,
        "monthly_transaction_volume": 2,
        "hour_of_day": 20,
        "day_of_week": 5,
        "payment_method": "NETBANKING",
        "bank": "SBI",
        "device_type": "MOBILE",
        "failure_code": "NETWORK_ERROR",
        "preferred_payment_method": "UPI",
        "preferred_bank": "SBI",
        "merchant_category": "FOOD"
    },
    {
        "amount": 25000.0,
        "retry_count": 0,
        "customer_success_rate": 0.95,
        "customer_lifetime_value": 150000.0,
        "recent_bank_failure_rate": 0.01,
        "recent_method_failure_rate": 0.01,
        "abandonment_rate": 0.01,
        "average_transaction_value": 10000.0,
        "monthly_transaction_volume": 15,
        "hour_of_day": 9,
        "day_of_week": 2,
        "payment_method": "CARD",
        "bank": "AXIS",
        "device_type": "DESKTOP",
        "failure_code": "LIMIT_EXCEEDED",
        "preferred_payment_method": "CARD",
        "preferred_bank": "AXIS",
        "merchant_category": "EDUCATION"
    },
    {
        "amount": 350.0,
        "retry_count": 2,
        "customer_success_rate": 0.40,
        "customer_lifetime_value": 500.0,
        "recent_bank_failure_rate": 0.20,
        "recent_method_failure_rate": 0.15,
        "abandonment_rate": 0.3,
        "average_transaction_value": 200.0,
        "monthly_transaction_volume": 3,
        "hour_of_day": 23,
        "day_of_week": 6,
        "payment_method": "WALLET",
        "bank": "UNKNOWN",
        "device_type": "MOBILE",
        "failure_code": "TIMEOUT",
        "preferred_payment_method": "WALLET",
        "preferred_bank": "UNKNOWN",
        "merchant_category": "ENTERTAINMENT"
    }
]

for p in payloads:
    r = requests.post(f"{base_url}/recovery", json=p)
    if r.status_code == 200:
        print(f"Created recovery for {p['amount']}")
    else:
        print(f"Failed: {r.text}")
