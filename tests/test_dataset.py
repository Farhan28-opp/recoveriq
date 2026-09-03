"""
Tests validating the synthetic RecoverIQ dataset produced by
data/generate_dataset.py.

These tests do NOT generate data themselves. They query the existing
database (via the application's existing SQLAlchemy session factory)
and assert that the currently loaded dataset is internally consistent
and suitable for future ML training.

Run with:
    pytest tests/test_dataset.py -v
"""

import pytest
from sqlalchemy import func, select

from backend.database import SessionLocal
from backend.models import Customer, Merchant, PaymentHealth, Transaction


@pytest.fixture(scope="module")
def db_session():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module", autouse=True)
def ensure_dataset_present(db_session):
    """Skip all tests in this module if no synthetic dataset has been loaded."""
    count = db_session.execute(select(func.count()).select_from(Customer)).scalar()
    if not count:
        pytest.skip(
            "No synthetic dataset found in the database. "
            "Run `python data/generate_dataset.py` first."
        )


# ==================================================
# 1. CUSTOMER DATA VALIDITY
# ==================================================

def test_customer_data_validity(db_session):
    total_customers = db_session.execute(
        select(func.count()).select_from(Customer)
    ).scalar()
    assert total_customers > 0, "customers table contains no records"

    invalid_customers = db_session.execute(
        select(func.count()).select_from(Customer).where(
            (Customer.customer_id.is_(None))
            | (Customer.total_transactions < 0)
            | (Customer.successful_transactions < 0)
            | (Customer.failed_transactions < 0)
            | (Customer.previous_recoveries < 0)
        )
    ).scalar()
    assert invalid_customers == 0, (
        f"{invalid_customers} customers have missing customer_id or negative counters"
    )

    inconsistent_customers = db_session.execute(
        select(func.count()).select_from(Customer).where(
            Customer.successful_transactions + Customer.failed_transactions
            != Customer.total_transactions
        )
    ).scalar()
    assert inconsistent_customers == 0, (
        f"{inconsistent_customers} customers have "
        "successful_transactions + failed_transactions != total_transactions"
    )


# ==================================================
# 2. MERCHANT DATA VALIDITY
# ==================================================

def test_merchant_data_validity(db_session):
    total_merchants = db_session.execute(
        select(func.count()).select_from(Merchant)
    ).scalar()
    assert total_merchants > 0, "merchants table contains no records"

    invalid_merchants = db_session.execute(
        select(func.count()).select_from(Merchant).where(
            (Merchant.merchant_id.is_(None))
            | (Merchant.monthly_transaction_volume < 0)
            | (Merchant.average_transaction_value < 0)
        )
    ).scalar()
    assert invalid_merchants == 0, (
        f"{invalid_merchants} merchants have missing merchant_id or negative values"
    )


# ==================================================
# 3. TRANSACTION AMOUNT VALIDITY
# ==================================================

def test_transaction_amounts_are_valid(db_session):
    invalid_transactions = db_session.execute(
        select(func.count()).select_from(Transaction).where(
            (Transaction.amount < 0) | (Transaction.retry_count < 0)
        )
    ).scalar()
    assert invalid_transactions == 0, (
        f"{invalid_transactions} transactions have a negative amount or retry_count"
    )


# ==================================================
# 4. TRANSACTION FOREIGN KEYS
# ==================================================

def test_transaction_foreign_keys_reference_existing_records(db_session):
    orphan_customer_refs = db_session.execute(
        select(func.count()).select_from(Transaction).where(
            ~Transaction.customer_id.in_(select(Customer.customer_id))
        )
    ).scalar()
    assert orphan_customer_refs == 0, (
        f"{orphan_customer_refs} transactions reference a non-existent customer_id"
    )

    orphan_merchant_refs = db_session.execute(
        select(func.count()).select_from(Transaction).where(
            ~Transaction.merchant_id.in_(select(Merchant.merchant_id))
        )
    ).scalar()
    assert orphan_merchant_refs == 0, (
        f"{orphan_merchant_refs} transactions reference a non-existent merchant_id"
    )


# ==================================================
# 5. SUCCESS TRANSACTION RULES
# ==================================================

def test_success_transactions_have_no_failure_or_recovery_data(db_session):
    invalid_success = db_session.execute(
        select(func.count()).select_from(Transaction).where(
            Transaction.status == "SUCCESS",
            (Transaction.failure_code.is_not(None))
            | (Transaction.failure_reason.is_not(None))
            | (Transaction.recovered.is_(True)),
        )
    ).scalar()
    assert invalid_success == 0, (
        f"{invalid_success} SUCCESS transactions have a failure_code, "
        "failure_reason, or are marked recovered"
    )


# ==================================================
# 6. FAILED TRANSACTION RULES
# ==================================================

def test_failed_transactions_have_failure_details(db_session):
    invalid_failed = db_session.execute(
        select(func.count()).select_from(Transaction).where(
            Transaction.status == "FAILED",
            (Transaction.failure_code.is_(None))
            | (Transaction.failure_reason.is_(None)),
        )
    ).scalar()
    assert invalid_failed == 0, (
        f"{invalid_failed} FAILED transactions are missing failure_code or failure_reason"
    )


# ==================================================
# 7. RECOVERY CONSISTENCY
# ==================================================

def test_recovered_transactions_have_valid_recovery_fields(db_session):
    invalid_recovered = db_session.execute(
        select(func.count()).select_from(Transaction).where(
            Transaction.recovered.is_(True),
            (Transaction.recovered_amount.is_(None))
            | (Transaction.recovered_amount < 0)
            | (Transaction.recovery_delay_minutes.is_(None))
            | (Transaction.recovery_delay_minutes < 0),
        )
    ).scalar()
    assert invalid_recovered == 0, (
        f"{invalid_recovered} recovered transactions have missing/negative "
        "recovered_amount or recovery_delay_minutes"
    )


def test_unrecovered_transactions_have_no_recovery_fields(db_session):
    invalid_unrecovered = db_session.execute(
        select(func.count()).select_from(Transaction).where(
            Transaction.recovered.is_(False),
            (Transaction.recovered_amount.is_not(None))
            | (Transaction.recovery_delay_minutes.is_not(None)),
        )
    ).scalar()
    assert invalid_unrecovered == 0, (
        f"{invalid_unrecovered} unrecovered transactions have "
        "recovered_amount or recovery_delay_minutes set"
    )


# ==================================================
# 8. PAYMENT HEALTH VALIDITY
# ==================================================

def test_payment_health_data_validity(db_session):
    total_payment_health = db_session.execute(
        select(func.count()).select_from(PaymentHealth)
    ).scalar()
    assert total_payment_health > 0, "payment_health table contains no records"

    invalid_payment_health = db_session.execute(
        select(func.count()).select_from(PaymentHealth).where(
            (PaymentHealth.total_attempts < 0)
            | (PaymentHealth.successful_attempts < 0)
            | (PaymentHealth.failed_attempts < 0)
            | (PaymentHealth.success_rate < 0)
            | (PaymentHealth.success_rate > 1)
        )
    ).scalar()
    assert invalid_payment_health == 0, (
        f"{invalid_payment_health} payment_health records have negative "
        "attempt counts or an out-of-range success_rate"
    )


# ==================================================
# 9. DATASET HAS BOTH CLASSES (useful for ML)
# ==================================================

def test_dataset_contains_both_success_and_failed_transactions(db_session):
    success_count = db_session.execute(
        select(func.count()).select_from(Transaction).where(Transaction.status == "SUCCESS")
    ).scalar()
    failed_count = db_session.execute(
        select(func.count()).select_from(Transaction).where(Transaction.status == "FAILED")
    ).scalar()

    assert success_count > 0, "dataset contains no SUCCESS transactions"
    assert failed_count > 0, "dataset contains no FAILED transactions"


def test_dataset_contains_recovered_and_unrecovered_failed_transactions(db_session):
    recovered_count = db_session.execute(
        select(func.count()).select_from(Transaction).where(
            Transaction.status == "FAILED", Transaction.recovered.is_(True)
        )
    ).scalar()
    unrecovered_count = db_session.execute(
        select(func.count()).select_from(Transaction).where(
            Transaction.status == "FAILED", Transaction.recovered.is_(False)
        )
    ).scalar()

    assert recovered_count > 0, "dataset contains no recovered FAILED transactions"
    assert unrecovered_count > 0, "dataset contains no unrecovered FAILED transactions"


# ==================================================
# 10. NO NULL REQUIRED FIELDS
# ==================================================

def test_required_fields_are_not_null(db_session):
    null_customer_ids = db_session.execute(
        select(func.count()).select_from(Customer).where(Customer.customer_id.is_(None))
    ).scalar()
    assert null_customer_ids == 0, "customers.customer_id contains NULL values"

    null_merchant_ids = db_session.execute(
        select(func.count()).select_from(Merchant).where(Merchant.merchant_id.is_(None))
    ).scalar()
    assert null_merchant_ids == 0, "merchants.merchant_id contains NULL values"

    invalid_transactions = db_session.execute(
        select(func.count()).select_from(Transaction).where(
            (Transaction.transaction_id.is_(None))
            | (Transaction.customer_id.is_(None))
            | (Transaction.merchant_id.is_(None))
            | (Transaction.status.is_(None))
        )
    ).scalar()
    assert invalid_transactions == 0, (
        f"{invalid_transactions} transactions have a NULL transaction_id, "
        "customer_id, merchant_id, or status"
    )
