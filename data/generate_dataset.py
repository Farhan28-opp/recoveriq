
"""
RecoverIQ synthetic payment dataset generator.

Generates a fully synthetic, offline, deterministic dataset of customers,
merchants, transactions, and payment-health observations and (optionally)
loads it into PostgreSQL using the existing SQLAlchemy infrastructure.

This module ONLY generates source data. It does not train models, call
AI/ML systems, create recovery actions, or expose any API.

Usage:
    python data/generate_dataset.py
    python data/generate_dataset.py --reset
    python data/generate_dataset.py --skip-insert
"""

import argparse
import os
import random
import sys
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import delete, insert

# Allow running as `python data/generate_dataset.py` from the project root
# without requiring PYTHONPATH to be set manually.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.database import Base, SessionLocal, engine
from backend.models import Customer, Merchant, PaymentHealth, Transaction

# ==================================================
# CONFIGURATION
# ==================================================

SEED = 42

CUSTOMER_COUNT = 3000
MERCHANT_COUNT = 100
TRANSACTION_COUNT = 55000

HISTORY_DAYS = 30
DB_INSERT_BATCH_SIZE = 5000

PAYMENT_METHODS = ["UPI", "CARD", "NETBANKING", "WALLET"]
PAYMENT_METHOD_WEIGHTS = [0.50, 0.30, 0.10, 0.10]

BANKS = ["HDFC", "ICICI", "SBI", "AXIS", "KOTAK", "YES", "INDUSIND"]
BANK_WEIGHTS = [0.22, 0.20, 0.18, 0.14, 0.12, 0.08, 0.06]

DEVICE_TYPES = ["MOBILE", "DESKTOP", "TABLET"]
DEVICE_WEIGHTS = [0.60, 0.30, 0.10]

MERCHANT_CATEGORIES = [
    "E_COMMERCE", "FOOD", "TRAVEL", "EDUCATION", "SUBSCRIPTION",
    "HEALTHCARE", "ENTERTAINMENT", "UTILITIES", "RETAIL", "SERVICES",
]

FAILURE_CODES = [
    "BANK_DECLINED", "INSUFFICIENT_FUNDS", "TIMEOUT", "NETWORK_ERROR",
    "LIMIT_EXCEEDED", "FRAUD_CHECK", "TECHNICAL_ERROR", "METHOD_UNAVAILABLE",
]
FAILURE_CODE_BASE_WEIGHTS = {
    "BANK_DECLINED": 0.25,
    "INSUFFICIENT_FUNDS": 0.20,
    "TIMEOUT": 0.15,
    "NETWORK_ERROR": 0.12,
    "LIMIT_EXCEEDED": 0.08,
    "FRAUD_CHECK": 0.07,
    "TECHNICAL_ERROR": 0.08,
    "METHOD_UNAVAILABLE": 0.05,
}
FAILURE_REASON_TEXT = {
    "BANK_DECLINED": "The issuing bank declined the transaction.",
    "INSUFFICIENT_FUNDS": "The customer had insufficient funds at the time of payment.",
    "TIMEOUT": "The payment request timed out before completion.",
    "NETWORK_ERROR": "A network error interrupted the payment attempt.",
    "LIMIT_EXCEEDED": "The transaction exceeded the customer's payment limit.",
    "FRAUD_CHECK": "The transaction was held by an automated fraud check.",
    "TECHNICAL_ERROR": "A technical error occurred at the payment gateway.",
    "METHOD_UNAVAILABLE": "The selected payment method was temporarily unavailable.",
}
# Failure codes considered more "recoverable" via retry/reminder get a bonus.
FAILURE_CODE_RECOVERY_BONUS = {
    "TIMEOUT": 0.35,
    "NETWORK_ERROR": 0.30,
    "TECHNICAL_ERROR": 0.25,
    "METHOD_UNAVAILABLE": 0.20,
    "BANK_DECLINED": 0.10,
    "INSUFFICIENT_FUNDS": 0.05,
    "LIMIT_EXCEEDED": 0.05,
    "FRAUD_CHECK": 0.02,
}

CUSTOMER_PROFILES = ["reliable", "average", "failure_prone", "high_value", "low_value"]
CUSTOMER_PROFILE_WEIGHTS = [0.20, 0.45, 0.15, 0.10, 0.10]
PROFILE_BASE_FAIL = {
    "reliable": 0.03,
    "average": 0.08,
    "failure_prone": 0.22,
    "high_value": 0.06,
    "low_value": 0.10,
}
PROFILE_VALUE_SCALE = {
    "reliable": 1.0,
    "average": 1.0,
    "failure_prone": 0.9,
    "high_value": 3.0,
    "low_value": 0.4,
}

BANK_BASE_FAIL = {
    "HDFC": 0.05,
    "ICICI": 0.06,
    "SBI": 0.09,
    "AXIS": 0.07,
    "KOTAK": 0.06,
    "YES": 0.11,
    "INDUSIND": 0.08,
}
METHOD_BASE_FAIL = {
    "UPI": 0.05,
    "CARD": 0.09,
    "NETBANKING": 0.10,
    "WALLET": 0.06,
}
METHOD_BASE_LATENCY_MS = {
    "UPI": 700,
    "CARD": 1500,
    "NETBANKING": 2600,
    "WALLET": 650,
}

# Rolling-rate defaults used before enough history has accumulated.
MIN_HISTORY_FOR_ROLLING_RATE = 20
DEFAULT_CUSTOMER_SUCCESS_RATE = 0.90

NUM_DEGRADATION_EVENTS = 8


# ==================================================
# SEEDING
# ==================================================

def set_seed(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)


# ==================================================
# MERCHANTS
# ==================================================

def generate_merchants(count: int = MERCHANT_COUNT):
    merchants = []
    for i in range(1, count + 1):
        merchant_id = f"MERCH_{i:04d}"
        category = random.choice(MERCHANT_CATEGORIES)
        avg_txn_value = round(float(np.random.lognormal(mean=6.8, sigma=0.7)), 2)
        avg_txn_value = min(max(avg_txn_value, 50.0), 100000.0)
        monthly_volume = int(np.random.lognormal(mean=7.5, sigma=1.0))
        monthly_volume = min(max(monthly_volume, 10), 200000)

        merchants.append({
            "merchant_id": merchant_id,
            "merchant_category": category,
            "average_transaction_value": avg_txn_value,
            "monthly_transaction_volume": monthly_volume,
        })
    return merchants


# ==================================================
# CUSTOMERS (profile generation; aggregates filled in later)
# ==================================================

def generate_customers(count: int = CUSTOMER_COUNT):
    customers = []
    for i in range(1, count + 1):
        customer_id = f"CUST_{i:06d}"
        profile = random.choices(CUSTOMER_PROFILES, weights=CUSTOMER_PROFILE_WEIGHTS, k=1)[0]
        preferred_payment_method = random.choices(
            PAYMENT_METHODS, weights=PAYMENT_METHOD_WEIGHTS, k=1
        )[0]
        preferred_bank = random.choices(BANKS, weights=BANK_WEIGHTS, k=1)[0]

        # Synthetic customer trait; not derivable from the current transaction
        # schema (no "abandoned" status exists), so it is generated per-profile.
        base_abandonment = {
            "reliable": 0.03,
            "average": 0.08,
            "failure_prone": 0.20,
            "high_value": 0.05,
            "low_value": 0.12,
        }[profile]
        abandonment_rate = round(
            min(max(np.random.normal(base_abandonment, 0.03), 0.0), 1.0), 4
        )

        customers.append({
            "customer_id": customer_id,
            "profile": profile,
            "preferred_payment_method": preferred_payment_method,
            "preferred_bank": preferred_bank,
            "abandonment_rate": abandonment_rate,
            # Aggregates below are computed after transaction generation.
            "total_transactions": 0,
            "successful_transactions": 0,
            "failed_transactions": 0,
            "customer_success_rate": 0.0,
            "lifetime_value": 0.0,
            "average_transaction_value": 0.0,
            "previous_recoveries": 0,
        })
    return customers


# ==================================================
# DEGRADATION EVENTS (used by both transactions and payment_health)
# ==================================================

def generate_degradation_events(window_start: datetime, window_end: datetime,
                                 count: int = NUM_DEGRADATION_EVENTS):
    events = []
    total_seconds = int((window_end - window_start).total_seconds())
    for _ in range(count):
        bank = random.choice(BANKS)
        # Some events are bank-wide outages (method=None), others are
        # specific to one payment method at that bank.
        method = random.choice(PAYMENT_METHODS + [None])
        start_offset = random.randint(0, max(total_seconds - 3600, 1))
        start = window_start + timedelta(seconds=start_offset)
        duration_hours = random.randint(1, 6)
        end = start + timedelta(hours=duration_hours)
        severity = round(random.uniform(0.15, 0.45), 3)
        events.append({"bank": bank, "method": method, "start": start, "end": end, "severity": severity})
    return events


def degradation_bonus(bank: str, method: str, ts: datetime, events) -> float:
    bonus = 0.0
    for ev in events:
        if ev["bank"] == bank and (ev["method"] is None or ev["method"] == method):
            if ev["start"] <= ts <= ev["end"]:
                bonus += ev["severity"]
    return bonus


# ==================================================
# TRANSACTIONS
# ==================================================

HOUR_WEIGHTS = np.array([
    0.010, 0.006, 0.004, 0.003, 0.003, 0.005,   # 00-05
    0.015, 0.030, 0.050, 0.065, 0.070, 0.072,   # 06-11
    0.075, 0.070, 0.065, 0.062, 0.060, 0.058,   # 12-17
    0.060, 0.058, 0.050, 0.040, 0.025, 0.014,   # 18-23
])
HOUR_WEIGHTS = HOUR_WEIGHTS / HOUR_WEIGHTS.sum()


def _random_timestamp(window_start: datetime) -> datetime:
    day_offset = random.randint(0, HISTORY_DAYS - 1)
    hour = int(np.random.choice(np.arange(24), p=HOUR_WEIGHTS))
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return window_start + timedelta(days=day_offset, hours=hour, minutes=minute, seconds=second)


def generate_transactions(customers, merchants):
    window_end = datetime(2026, 8, 25, 12, 0, 0)
    window_start = window_end - timedelta(days=HISTORY_DAYS)

    degradation_events = generate_degradation_events(window_start, window_end)

    # --- Step 1: generate raw (unordered) transaction skeletons ---
    raw = []
    for _ in range(TRANSACTION_COUNT):
        customer = random.choice(customers)
        merchant = random.choice(merchants)

        ts = _random_timestamp(window_start)

        if random.random() < 0.65:
            payment_method = customer["preferred_payment_method"]
        else:
            payment_method = random.choices(PAYMENT_METHODS, weights=PAYMENT_METHOD_WEIGHTS, k=1)[0]

        if random.random() < 0.65:
            bank = customer["preferred_bank"]
        else:
            bank = random.choices(BANKS, weights=BANK_WEIGHTS, k=1)[0]

        device_type = random.choices(DEVICE_TYPES, weights=DEVICE_WEIGHTS, k=1)[0]

        value_scale = PROFILE_VALUE_SCALE[customer["profile"]]
        base_amount = merchant["average_transaction_value"] * value_scale
        noise = float(np.random.lognormal(mean=0.0, sigma=0.6))
        amount = round(min(max(base_amount * noise, 10.0), 200000.0), 2)

        raw.append({
            "customer_id": customer["customer_id"],
            "customer_profile": customer["profile"],
            "merchant_id": merchant["merchant_id"],
            "timestamp": ts,
            "payment_method": payment_method,
            "bank": bank,
            "device_type": device_type,
            "amount": amount,
            "currency": "INR",
        })

    # --- Step 2: process strictly in chronological order to avoid leakage ---
    raw.sort(key=lambda r: r["timestamp"])

    bank_stats = {b: {"attempts": 0, "failures": 0} for b in BANKS}
    method_stats = {m: {"attempts": 0, "failures": 0} for m in PAYMENT_METHODS}
    customer_stats = {
        c["customer_id"]: {
            "attempts": 0, "successes": 0, "amount_sum": 0.0,
            "success_amount_sum": 0.0, "recoveries": 0,
        }
        for c in customers
    }

    transactions = []
    for idx, row in enumerate(raw, start=1):
        bank = row["bank"]
        method = row["payment_method"]
        cid = row["customer_id"]
        ts = row["timestamp"]
        amount = row["amount"]

        b_stats = bank_stats[bank]
        m_stats = method_stats[method]
        c_stats = customer_stats[cid]

        recent_bank_failure_rate = (
            b_stats["failures"] / b_stats["attempts"]
            if b_stats["attempts"] >= MIN_HISTORY_FOR_ROLLING_RATE
            else BANK_BASE_FAIL[bank]
        )
        recent_method_failure_rate = (
            m_stats["failures"] / m_stats["attempts"]
            if m_stats["attempts"] >= MIN_HISTORY_FOR_ROLLING_RATE
            else METHOD_BASE_FAIL[method]
        )
        customer_success_rate_snapshot = (
            c_stats["successes"] / c_stats["attempts"]
            if c_stats["attempts"] >= 5
            else DEFAULT_CUSTOMER_SUCCESS_RATE
        )
        customer_lifetime_value_snapshot = round(c_stats["success_amount_sum"], 2)

        deg_bonus = degradation_bonus(bank, method, ts, degradation_events)
        amount_effect = min(0.05, (amount / 100000.0) * 0.03)
        time_effect = 0.03 if (ts.hour < 6 or ts.hour >= 23) else 0.0
        recent_bank_effect = (recent_bank_failure_rate - BANK_BASE_FAIL[bank]) * 0.5
        recent_method_effect = (recent_method_failure_rate - METHOD_BASE_FAIL[method]) * 0.5

        p_fail = (
            PROFILE_BASE_FAIL[row["customer_profile"]] * 0.35
            + BANK_BASE_FAIL[bank] * 0.20
            + METHOD_BASE_FAIL[method] * 0.20
            + deg_bonus
            + amount_effect
            + time_effect
            + recent_bank_effect
            + recent_method_effect
            + float(np.random.normal(0, 0.01))
        )
        p_fail = min(max(p_fail, 0.01), 0.85)

        status = "FAILED" if random.random() < p_fail else "SUCCESS"

        if status == "FAILED":
            retry_count = min(int(np.random.poisson(1.2)), 5)
        else:
            retry_count = min(int(np.random.poisson(0.15)), 2)

        failure_code = None
        failure_reason = None
        recovered = False
        recovery_delay_minutes = None
        recovered_amount = None

        if status == "FAILED":
            code_weights = dict(FAILURE_CODE_BASE_WEIGHTS)
            if amount > 50000:
                code_weights["LIMIT_EXCEEDED"] *= 3
                code_weights["FRAUD_CHECK"] *= 3
            if deg_bonus > 0:
                code_weights["TIMEOUT"] *= 3
                code_weights["NETWORK_ERROR"] *= 3
            codes = list(code_weights.keys())
            weights = np.array([code_weights[c] for c in codes], dtype=float)
            weights = weights / weights.sum()
            failure_code = str(np.random.choice(codes, p=weights))
            failure_reason = FAILURE_REASON_TEXT[failure_code]

            base_recovery = 0.15
            amount_effect_r = max(-0.15, -(amount / 100000.0) * 0.10)
            customer_effect_r = (customer_success_rate_snapshot - 0.90) * 0.30
            bank_effect_r = -(recent_bank_failure_rate - 0.08) * 0.60
            method_effect_r = -(recent_method_failure_rate - 0.08) * 0.60
            retry_effect_r = min(0.15, retry_count * 0.05)
            noise_r = float(np.random.normal(0, 0.05))

            p_recover = (
                base_recovery
                + FAILURE_CODE_RECOVERY_BONUS[failure_code]
                + amount_effect_r
                + customer_effect_r
                + bank_effect_r
                + method_effect_r
                + retry_effect_r
                + noise_r
            )
            p_recover = min(max(p_recover, 0.02), 0.95)
            recovered = random.random() < p_recover

            if recovered:
                delay_params = {
                    "TIMEOUT": (2.0, 15.0),
                    "NETWORK_ERROR": (2.0, 15.0),
                    "TECHNICAL_ERROR": (2.0, 30.0),
                    "METHOD_UNAVAILABLE": (2.0, 30.0),
                    "BANK_DECLINED": (2.0, 90.0),
                    "INSUFFICIENT_FUNDS": (2.0, 90.0),
                    "LIMIT_EXCEEDED": (2.0, 180.0),
                    "FRAUD_CHECK": (2.0, 180.0),
                }[failure_code]
                delay = float(np.random.gamma(shape=delay_params[0], scale=delay_params[1]))
                recovery_delay_minutes = max(1, int(round(delay)))
                recovered_amount = amount

        transaction_id = f"TXN_{idx:07d}"
        transactions.append({
            "transaction_id": transaction_id,
            "customer_id": cid,
            "merchant_id": row["merchant_id"],
            "amount": amount,
            "currency": row["currency"],
            "timestamp": ts,
            "payment_method": method,
            "bank": bank,
            "device_type": row["device_type"],
            "status": status,
            "failure_code": failure_code,
            "failure_reason": failure_reason,
            "retry_count": retry_count,
            "customer_success_rate": round(customer_success_rate_snapshot, 4),
            "customer_lifetime_value": customer_lifetime_value_snapshot,
            "recent_bank_failure_rate": round(recent_bank_failure_rate, 4),
            "recent_method_failure_rate": round(recent_method_failure_rate, 4),
            "recovered": recovered,
            "recovery_delay_minutes": recovery_delay_minutes,
            "recovered_amount": recovered_amount,
        })

        # Update rolling counters AFTER computing this transaction's features.
        b_stats["attempts"] += 1
        if status == "FAILED":
            b_stats["failures"] += 1

        m_stats["attempts"] += 1
        if status == "FAILED":
            m_stats["failures"] += 1

        c_stats["attempts"] += 1
        c_stats["amount_sum"] += amount
        if status == "SUCCESS":
            c_stats["successes"] += 1
            c_stats["success_amount_sum"] += amount
        if recovered:
            c_stats["recoveries"] += 1

    return transactions, customer_stats, degradation_events, window_start, window_end


# ==================================================
# CUSTOMER AGGREGATES (finalized from full transaction history)
# ==================================================

def finalize_customer_aggregates(customers, customer_stats):
    for c in customers:
        stats = customer_stats[c["customer_id"]]
        total = stats["attempts"]
        successes = stats["successes"]
        failures = total - successes

        c["total_transactions"] = total
        c["successful_transactions"] = successes
        c["failed_transactions"] = failures
        c["customer_success_rate"] = round(successes / total, 4) if total > 0 else 0.0
        c["lifetime_value"] = round(stats["success_amount_sum"], 2)
        c["average_transaction_value"] = round(stats["amount_sum"] / total, 2) if total > 0 else 0.0
        c["previous_recoveries"] = stats["recoveries"]
        # "profile" was only used for generation; not a column on the model.
        c.pop("profile", None)
    return customers


# ==================================================
# PAYMENT HEALTH (aggregated directly from generated transactions)
# ==================================================

def generate_payment_health(transactions, degradation_events):
    buckets = {}
    for t in transactions:
        hour_bucket = t["timestamp"].replace(minute=0, second=0, microsecond=0)
        key = (t["bank"], t["payment_method"], hour_bucket)
        if key not in buckets:
            buckets[key] = {"total": 0, "success": 0, "failed": 0}
        buckets[key]["total"] += 1
        if t["status"] == "SUCCESS":
            buckets[key]["success"] += 1
        else:
            buckets[key]["failed"] += 1

    records = []
    for (bank, method, hour_bucket), stats in sorted(buckets.items(), key=lambda kv: (kv[0][2], kv[0][0], kv[0][1])):
        total = stats["total"]
        success = stats["success"]
        failed = stats["failed"]
        success_rate = round(success / total, 4) if total > 0 else 0.0

        deg = degradation_bonus(bank, method, hour_bucket, degradation_events)
        base_latency = METHOD_BASE_LATENCY_MS[method]
        latency = base_latency + deg * 6000 + float(np.random.normal(0, 60))
        latency = max(latency, 50.0)

        records.append({
            "timestamp": hour_bucket,
            "payment_method": method,
            "bank": bank,
            "total_attempts": total,
            "successful_attempts": success,
            "failed_attempts": failed,
            "success_rate": success_rate,
            "average_response_time_ms": round(latency, 2),
        })
    return records


# ==================================================
# VALIDATION
# ==================================================

def validate_dataset(customers, merchants, transactions, payment_health):
    customer_ids = {c["customer_id"] for c in customers}
    merchant_ids = {m["merchant_id"] for m in merchants}

    if len(customer_ids) != len(customers):
        raise ValueError("Duplicate customer_id values detected.")
    if len(merchant_ids) != len(merchants):
        raise ValueError("Duplicate merchant_id values detected.")

    seen_txn_ids = set()
    total_recovered_failed = 0
    total_failed = 0
    total_success = 0

    for t in transactions:
        if t["transaction_id"] in seen_txn_ids:
            raise ValueError(f"Duplicate transaction_id: {t['transaction_id']}")
        seen_txn_ids.add(t["transaction_id"])

        if t["amount"] < 0:
            raise ValueError(f"Negative amount on {t['transaction_id']}")
        if t["retry_count"] < 0:
            raise ValueError(f"Negative retry_count on {t['transaction_id']}")
        if t["customer_id"] not in customer_ids:
            raise ValueError(f"Transaction {t['transaction_id']} references unknown customer_id")
        if t["merchant_id"] not in merchant_ids:
            raise ValueError(f"Transaction {t['transaction_id']} references unknown merchant_id")

        if t["status"] == "SUCCESS":
            total_success += 1
            if t["failure_code"] is not None:
                raise ValueError(f"SUCCESS transaction {t['transaction_id']} has a failure_code")
            if t["recovered"] is not False:
                raise ValueError(f"SUCCESS transaction {t['transaction_id']} is marked recovered")
            if t["recovery_delay_minutes"] is not None or t["recovered_amount"] is not None:
                raise ValueError(f"SUCCESS transaction {t['transaction_id']} has recovery fields set")
        elif t["status"] == "FAILED":
            total_failed += 1
            if t["failure_code"] is None:
                raise ValueError(f"FAILED transaction {t['transaction_id']} is missing a failure_code")
            if t["recovered"]:
                total_recovered_failed += 1
                if t["recovered_amount"] is None:
                    raise ValueError(f"Recovered transaction {t['transaction_id']} missing recovered_amount")
                if t["recovery_delay_minutes"] is None:
                    raise ValueError(f"Recovered transaction {t['transaction_id']} missing recovery_delay_minutes")
            else:
                if t["recovered_amount"] is not None or t["recovery_delay_minutes"] is not None:
                    raise ValueError(f"Unrecovered transaction {t['transaction_id']} has recovery fields set")
        else:
            raise ValueError(f"Unknown status '{t['status']}' on {t['transaction_id']}")

    for c in customers:
        if c["total_transactions"] < 0 or c["successful_transactions"] < 0 or c["failed_transactions"] < 0:
            raise ValueError(f"Negative transaction counts for {c['customer_id']}")
        if c["previous_recoveries"] < 0:
            raise ValueError(f"Negative previous_recoveries for {c['customer_id']}")
        if c["successful_transactions"] + c["failed_transactions"] != c["total_transactions"]:
            raise ValueError(f"Inconsistent transaction counts for {c['customer_id']}")

    for ph in payment_health:
        if ph["successful_attempts"] + ph["failed_attempts"] > ph["total_attempts"]:
            raise ValueError("payment_health attempts inconsistent (success + failed > total)")
        if not (0.0 <= ph["success_rate"] <= 1.0):
            raise ValueError("payment_health success_rate out of range")

    return {
        "total_success": total_success,
        "total_failed": total_failed,
        "total_recovered_failed": total_recovered_failed,
    }


# ==================================================
# DATABASE RESET (idempotency)
# ==================================================

def reset_synthetic_data(session):
    """
    Deletes previously generated synthetic rows in FK-safe order:
    transactions -> payment_health -> customers -> merchants.

    recovery_actions is intentionally NOT touched here, since this
    generator does not own recovery-agent history. If transactions
    cannot be deleted because recovery_actions rows still reference
    them, the developer must clear backend.models.RecoveryAction rows
    first (e.g. via a separate script or `DELETE FROM recovery_actions;`)
    before re-running this generator with --reset.
    """
    try:
        session.execute(delete(Transaction))
        session.execute(delete(PaymentHealth))
        session.execute(delete(Customer))
        session.execute(delete(Merchant))
        session.commit()
    except Exception as exc:
        session.rollback()
        print(
            "Reset failed. This is often caused by recovery_actions rows "
            "still referencing transactions. Clear recovery_actions first, "
            "then re-run with --reset.\n"
            f"Underlying error: {exc}"
        )
        raise


# ==================================================
# DATABASE INSERTION
# ==================================================

def insert_dataset(session, merchants, customers, transactions, payment_health):
    session.execute(insert(Merchant), merchants)
    session.execute(insert(Customer), customers)

    for start in range(0, len(transactions), DB_INSERT_BATCH_SIZE):
        batch = transactions[start:start + DB_INSERT_BATCH_SIZE]
        session.execute(insert(Transaction), batch)

    if payment_health:
        session.execute(insert(PaymentHealth), payment_health)

    session.commit()


# ==================================================
# MAIN
# ==================================================

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic RecoverIQ payment data.")
    parser.add_argument("--reset", action="store_true", help="Delete existing synthetic data before generating.")
    parser.add_argument("--skip-insert", action="store_true", help="Generate and validate only; skip PostgreSQL insertion.")
    args = parser.parse_args()

    set_seed(SEED)

    print("Generating merchants...")
    merchants = generate_merchants()

    print("Generating customers...")
    customers = generate_customers()

    print("Generating transactions...")
    transactions, customer_stats, degradation_events, window_start, window_end = generate_transactions(
        customers, merchants
    )
    finalize_customer_aggregates(customers, customer_stats)

    print("Generating payment health...")
    payment_health = generate_payment_health(transactions, degradation_events)

    print("Validating dataset...")
    counts = validate_dataset(customers, merchants, transactions, payment_health)

    if args.skip_insert:
        print("Skipping PostgreSQL insertion (--skip-insert).")
    else:
        print("Ensuring database tables exist...")
        Base.metadata.create_all(bind=engine)

        session = SessionLocal()
        try:
            if args.reset:
                print("Resetting existing synthetic data...")
                reset_synthetic_data(session)

            print("Inserting into PostgreSQL...")
            insert_dataset(session, merchants, customers, transactions, payment_health)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    print("Generation complete.")
    print(f"Customers: {len(customers)}")
    print(f"Merchants: {len(merchants)}")
    print(f"Transactions: {len(transactions)}")
    print(f"Payment health records: {len(payment_health)}")
    print(f"Successful transactions: {counts['total_success']}")
    print(f"Failed transactions: {counts['total_failed']}")
    print(f"Recovered failed transactions: {counts['total_recovered_failed']}")


if __name__ == "__main__":
    main()
