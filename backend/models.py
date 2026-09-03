from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String, primary_key=True)

    total_transactions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_transactions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_transactions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    customer_success_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=True)

    lifetime_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    average_transaction_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)

    preferred_payment_method: Mapped[str] = mapped_column(String, nullable=True)
    preferred_bank: Mapped[str] = mapped_column(String, nullable=True)

    previous_recoveries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    abandonment_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=True)

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="customer",
    )

    __table_args__ = (
        CheckConstraint("total_transactions >= 0", name="ck_customers_total_transactions_nonneg"),
        CheckConstraint("successful_transactions >= 0", name="ck_customers_successful_transactions_nonneg"),
        CheckConstraint("failed_transactions >= 0", name="ck_customers_failed_transactions_nonneg"),
        CheckConstraint("previous_recoveries >= 0", name="ck_customers_previous_recoveries_nonneg"),
    )


class Merchant(Base):
    __tablename__ = "merchants"

    merchant_id: Mapped[str] = mapped_column(String, primary_key=True)

    merchant_category: Mapped[str] = mapped_column(String, nullable=True)
    average_transaction_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    monthly_transaction_volume: Mapped[int] = mapped_column(Integer, nullable=True)

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="merchant",
    )

    __table_args__ = (
        CheckConstraint(
            "monthly_transaction_volume >= 0",
            name="ck_merchants_monthly_transaction_volume_nonneg",
        ),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id: Mapped[str] = mapped_column(String, primary_key=True)

    customer_id: Mapped[str] = mapped_column(
        String, ForeignKey("customers.customer_id"), nullable=False
    )
    merchant_id: Mapped[str] = mapped_column(
        String, ForeignKey("merchants.merchant_id"), nullable=False
    )

    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")

    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    payment_method: Mapped[str] = mapped_column(String, nullable=True)
    bank: Mapped[str] = mapped_column(String, nullable=True)
    device_type: Mapped[str] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, nullable=False)

    failure_code: Mapped[str] = mapped_column(String, nullable=True)
    failure_reason: Mapped[str] = mapped_column(String, nullable=True)

    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    customer_success_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=True)
    customer_lifetime_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    recent_bank_failure_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=True)
    recent_method_failure_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=True)

    import_batch_id: Mapped[str] = mapped_column(String, nullable=True)

    # Ground-truth outcome fields (used later as ML prediction targets).
    # Must remain in the schema; feature-selection concerns are handled
    # separately at the ML layer, not by omitting these columns.
    recovered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recovery_delay_minutes: Mapped[int] = mapped_column(Integer, nullable=True)
    recovered_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="transactions")
    merchant: Mapped["Merchant"] = relationship(back_populates="transactions")
    recovery_actions: Mapped[list["RecoveryAction"]] = relationship(
        back_populates="transaction",
    )

    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_transactions_amount_nonneg"),
        CheckConstraint("retry_count >= 0", name="ck_transactions_retry_count_nonneg"),
        CheckConstraint(
            "recovered_amount >= 0",
            name="ck_transactions_recovered_amount_nonneg",
        ),
        CheckConstraint(
            "recovery_delay_minutes >= 0",
            name="ck_transactions_recovery_delay_minutes_nonneg",
        ),
    )


class PaymentHealth(Base):
    __tablename__ = "payment_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    payment_method: Mapped[str] = mapped_column(String, nullable=False)
    bank: Mapped[str] = mapped_column(String, nullable=True)

    total_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    success_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=True)
    average_response_time_ms: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)

    __table_args__ = (
        CheckConstraint("total_attempts >= 0", name="ck_payment_health_total_attempts_nonneg"),
        CheckConstraint(
            "successful_attempts >= 0", name="ck_payment_health_successful_attempts_nonneg"
        ),
        CheckConstraint("failed_attempts >= 0", name="ck_payment_health_failed_attempts_nonneg"),
    )


class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    action_id: Mapped[str] = mapped_column(String, primary_key=True)

    transaction_id: Mapped[str] = mapped_column(
        String, ForeignKey("transactions.transaction_id"), nullable=False
    )

    action_type: Mapped[str] = mapped_column(String, nullable=False)
    action_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    expected_recovery_probability: Mapped[float] = mapped_column(Numeric(5, 4), nullable=True)
    expected_recovered_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)

    action_status: Mapped[str] = mapped_column(String, nullable=True)
    actual_result: Mapped[str] = mapped_column(String, nullable=True)

    transaction: Mapped["Transaction"] = relationship(back_populates="recovery_actions")

    __table_args__ = (
        CheckConstraint(
            "expected_recovery_probability >= 0 AND expected_recovery_probability <= 1",
            name="ck_recovery_actions_probability_range",
        ),
        CheckConstraint(
            "expected_recovered_amount >= 0",
            name="ck_recovery_actions_expected_recovered_amount_nonneg",
        ),
    )


class RecoveryWorkflow(Base):
    __tablename__ = "recovery_workflows"

    recovery_id: Mapped[str] = mapped_column(String, primary_key=True)

    failure_code: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    recovery_probability: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    risk_tier: Mapped[str] = mapped_column(String, nullable=False)
    recommended_action: Mapped[str] = mapped_column(String, nullable=False)
    expected_recovery_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)

    status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    
    execution_result: Mapped[str] = mapped_column(String, nullable=True)

    import_batch_id: Mapped[str] = mapped_column(String, nullable=True)
    transaction_id: Mapped[str] = mapped_column(String, ForeignKey("transactions.transaction_id", ondelete="CASCADE"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_recovery_workflows_amount_nonneg"),
        CheckConstraint("attempt_count >= 0", name="ck_recovery_workflows_attempt_count_nonneg"),
        CheckConstraint(
            "recovery_probability >= 0 AND recovery_probability <= 1",
            name="ck_recovery_workflows_probability_range",
        ),
    )
