"""
Pydantic request and response schemas for the RecoverIQ prediction API.

The request schema accepts human-friendly raw categorical values
(e.g. ``"payment_method": "UPI"``) rather than requiring callers to
manually one-hot encode.  The route layer transforms these into the
61-column one-hot DataFrame expected by RecoveryPredictor.

Categorical value validation uses ``Literal`` types derived from the
existing project vocabularies in ``data.generate_dataset``.
"""

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ====================================================================
# Categorical value types — sourced from data.generate_dataset constants
# ====================================================================

# These Literal types mirror the exact values in
# data.generate_dataset.PAYMENT_METHODS / BANKS / etc.
# UNKNOWN is accepted as a fallback for missing/unavailable values.

PaymentMethodType = Literal[
    "UPI", "CARD", "NETBANKING", "WALLET", "UNKNOWN",
]
BankType = Literal[
    "HDFC", "ICICI", "SBI", "AXIS", "KOTAK", "YES", "INDUSIND", "UNKNOWN",
]
DeviceTypeType = Literal[
    "MOBILE", "DESKTOP", "TABLET", "UNKNOWN",
]
FailureCodeType = Literal[
    "BANK_DECLINED", "INSUFFICIENT_FUNDS", "TIMEOUT", "NETWORK_ERROR",
    "LIMIT_EXCEEDED", "FRAUD_CHECK", "TECHNICAL_ERROR",
    "METHOD_UNAVAILABLE", "UNKNOWN",
]
MerchantCategoryType = Literal[
    "E_COMMERCE", "FOOD", "TRAVEL", "EDUCATION", "SUBSCRIPTION",
    "HEALTHCARE", "ENTERTAINMENT", "UTILITIES", "RETAIL", "SERVICES",
    "UNKNOWN",
]


# ====================================================================
# Request schema
# ====================================================================

class PredictionRequest(BaseModel):
    """Input payload for ``POST /predict``.

    Accepts the raw feature values that would be known at the time of
    a failed payment.  Categorical fields use human-readable values
    (e.g. ``"UPI"``) — the API transforms these to the one-hot
    representation expected by the ML model.
    """

    # --- Numeric features ---
    amount: float = Field(
        ..., gt=0, description="Transaction amount in INR (must be > 0).",
        json_schema_extra={"example": 1500.00},
    )
    retry_count: int = Field(
        ..., ge=0, description="Number of retries already attempted.",
        json_schema_extra={"example": 1},
    )
    customer_success_rate: float = Field(
        ..., ge=0.0, le=1.0,
        description="Rolling customer success rate at the time of this transaction (0–1).",
        json_schema_extra={"example": 0.85},
    )
    customer_lifetime_value: float = Field(
        ..., ge=0.0,
        description="Customer lifetime value in INR at the time of this transaction.",
        json_schema_extra={"example": 25000.00},
    )
    recent_bank_failure_rate: float = Field(
        ..., ge=0.0, le=1.0,
        description="Recent failure rate for this bank (0–1).",
        json_schema_extra={"example": 0.05},
    )
    recent_method_failure_rate: float = Field(
        ..., ge=0.0, le=1.0,
        description="Recent failure rate for this payment method (0–1).",
        json_schema_extra={"example": 0.03},
    )
    abandonment_rate: float = Field(
        ..., ge=0.0, le=1.0,
        description="Customer abandonment rate (0–1).",
        json_schema_extra={"example": 0.10},
    )
    average_transaction_value: float = Field(
        ..., ge=0.0,
        description="Merchant average transaction value in INR.",
        json_schema_extra={"example": 2000.00},
    )
    monthly_transaction_volume: int = Field(
        ..., ge=0,
        description="Merchant monthly transaction volume.",
        json_schema_extra={"example": 150},
    )
    hour_of_day: int = Field(
        ..., ge=0, le=23,
        description="Hour of transaction (0–23).",
        json_schema_extra={"example": 14},
    )
    day_of_week: int = Field(
        ..., ge=0, le=6,
        description="Day of week (0=Monday, 6=Sunday).",
        json_schema_extra={"example": 2},
    )

    # --- Categorical features (raw values, not one-hot) ---
    payment_method: PaymentMethodType = Field(
        ..., description="Payment method used.",
        json_schema_extra={"example": "UPI"},
    )
    bank: BankType = Field(
        ..., description="Issuing bank.",
        json_schema_extra={"example": "HDFC"},
    )
    device_type: DeviceTypeType = Field(
        ..., description="Device type used for the transaction.",
        json_schema_extra={"example": "MOBILE"},
    )
    failure_code: FailureCodeType = Field(
        ..., description="Payment failure code.",
        json_schema_extra={"example": "TIMEOUT"},
    )
    preferred_payment_method: PaymentMethodType = Field(
        ..., description="Customer's preferred payment method.",
        json_schema_extra={"example": "UPI"},
    )
    preferred_bank: BankType = Field(
        ..., description="Customer's preferred bank.",
        json_schema_extra={"example": "HDFC"},
    )
    merchant_category: MerchantCategoryType = Field(
        ..., description="Merchant category.",
        json_schema_extra={"example": "E_COMMERCE"},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "amount": 1500.00,
                    "retry_count": 1,
                    "customer_success_rate": 0.85,
                    "customer_lifetime_value": 25000.00,
                    "recent_bank_failure_rate": 0.05,
                    "recent_method_failure_rate": 0.03,
                    "abandonment_rate": 0.10,
                    "average_transaction_value": 2000.00,
                    "monthly_transaction_volume": 150,
                    "hour_of_day": 14,
                    "day_of_week": 2,
                    "payment_method": "UPI",
                    "bank": "HDFC",
                    "device_type": "MOBILE",
                    "failure_code": "TIMEOUT",
                    "preferred_payment_method": "UPI",
                    "preferred_bank": "HDFC",
                    "merchant_category": "E_COMMERCE",
                }
            ]
        }
    }


# ====================================================================
# Response schemas
# ====================================================================

class PredictionResponse(BaseModel):
    """Structured recovery decision response from ``POST /predict``."""
    recovery_probability: float = Field(
        ..., ge=0.0, le=1.0,
        description="Predicted probability of recovery (0–1).",
    )
    risk_tier: str = Field(
        ..., description="Recovery opportunity tier: HIGH, MEDIUM, or LOW.",
    )
    recommended_action: str = Field(
        ..., description="Recommended next recovery action.",
    )
    expected_recovery_value: float = Field(
        ..., ge=0.0,
        description="Expected recovery value = probability × amount (INR).",
    )
    reason: str = Field(
        ..., description="Human-readable explanation of the decision.",
    )
    model_version: str = Field(
        ..., description="Model version used for this prediction.",
    )


class ModelInfoResponse(BaseModel):
    """Safe subset of model metadata returned by ``GET /model/info``."""
    version: str = Field(..., description="Model version identifier.")
    model_type: str = Field(..., description="Model type / pipeline description.")
    feature_count: int = Field(..., description="Number of features used by the model.")
    training_timestamp: Optional[str] = Field(
        None, description="ISO 8601 timestamp of model training.",
    )
    metrics: Optional[dict] = Field(
        None, description="Model evaluation metrics on validation set.",
    )


class ErrorResponse(BaseModel):
    """Structured error response."""
    detail: str = Field(..., description="Human-readable error description.")
