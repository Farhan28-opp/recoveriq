"""
Prediction API routes for RecoverIQ (Day 4).

Provides:
    POST /predict     — predict recovery probability + decision
    GET  /model/info  — safe model metadata

The route layer is deliberately thin: it validates the request,
transforms raw categorical values to the one-hot format expected by
RecoveryPredictor, delegates to the predictor and decision engine,
and returns the structured response.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

from backend.schemas.prediction import (
    ErrorResponse,
    ModelInfoResponse,
    PredictionRequest,
    PredictionResponse,
)
from backend.services.decision_engine import DecisionEngine

# Import-chain note:
#   Importing CATEGORICAL_VOCAB from ml.config triggers the chain:
#       ml.config → data.generate_dataset → backend.database
#   which eagerly creates the SQLAlchemy engine.  However,
#   RecoveryPredictor (imported below) already triggers this exact
#   chain via ml.config.LEAKAGE_COLUMNS, so importing CATEGORICAL_VOCAB
#   adds zero additional side effects.
#
#   CATEGORICAL_VOCAB is the single source of truth for the categorical
#   values used during training (Day 2/3).  Duplicating these lists here
#   would risk divergence if the vocabulary ever changes.
from ml.config import CATEGORICAL_VOCAB
from ml.inference.predictor import RecoveryPredictor

logger = logging.getLogger(__name__)

router = APIRouter()

# ====================================================================
# Singleton instances — loaded once at startup
# ====================================================================

_predictor: RecoveryPredictor | None = None
_decision_engine: DecisionEngine | None = None


def _get_predictor() -> RecoveryPredictor:
    """Lazy-load the predictor singleton."""
    global _predictor
    if _predictor is None:
        logger.info("Loading RecoveryPredictor model artifacts...")
        _predictor = RecoveryPredictor()
        logger.info(
            "RecoveryPredictor loaded: %d features, model_type=%s",
            len(_predictor.feature_names),
            _predictor.model_type,
        )
    return _predictor


def _get_decision_engine() -> DecisionEngine:
    """Lazy-load the decision engine singleton."""
    global _decision_engine
    if _decision_engine is None:
        _decision_engine = DecisionEngine()
    return _decision_engine


# ====================================================================
# Feature transformation: raw API input → 61-column one-hot DataFrame
# ====================================================================

# Categorical columns and their vocabularies, matching the encoding
# in ml/features.py:_encode_categoricals.  The UNKNOWN category is
# appended to each group exactly as the training pipeline does.
_CATEGORICAL_COLUMNS = [
    "payment_method",
    "bank",
    "device_type",
    "failure_code",
    "preferred_payment_method",
    "preferred_bank",
    "merchant_category",
]

_NUMERIC_COLUMNS = [
    "amount",
    "retry_count",
    "customer_success_rate",
    "customer_lifetime_value",
    "recent_bank_failure_rate",
    "recent_method_failure_rate",
    "abandonment_rate",
    "average_transaction_value",
    "monthly_transaction_volume",
    "hour_of_day",
    "day_of_week",
]


def transform_request_to_dataframe(
    request: PredictionRequest,
    feature_names: list[str],
) -> pd.DataFrame:
    """Convert a validated PredictionRequest to a 61-column DataFrame.

    This mirrors the one-hot encoding logic in
    ``ml.features._encode_categoricals`` but operates on a single API
    row rather than a database query result.  It reuses
    ``ml.config.CATEGORICAL_VOCAB`` as the source of truth for
    category values.

    Parameters
    ----------
    request : PredictionRequest
        Validated API request.
    feature_names : list[str]
        Exact ordered list of feature column names from the model
        metadata (``predictor.feature_names``).

    Returns
    -------
    pd.DataFrame
        Single-row DataFrame with 61 one-hot encoded columns, ordered
        to match the model's training schema.
    """
    # Start with numeric features
    row: dict[str, Any] = {}
    for col in _NUMERIC_COLUMNS:
        row[col] = float(getattr(request, col))

    # One-hot encode each categorical group
    for col in _CATEGORICAL_COLUMNS:
        raw_value = getattr(request, col)
        # Build the full vocabulary with UNKNOWN, matching
        # ml/features.py:_encode_categoricals (lines 159-161).
        vocab = list(CATEGORICAL_VOCAB.get(col, []))
        if "UNKNOWN" not in vocab:
            vocab = vocab + ["UNKNOWN"]

        for category in vocab:
            one_hot_col = f"{col}_{category}"
            row[one_hot_col] = 1.0 if raw_value == category else 0.0

    df = pd.DataFrame([row])

    # Reorder to exact model column order.  The predictor's
    # _validate_features would also do this, but being explicit here
    # makes the transformation self-contained and testable.
    df = df[feature_names]

    return df


# ====================================================================
# POST /predict
# ====================================================================

@router.post(
    "/predict",
    response_model=PredictionResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal error"},
    },
    summary="Predict recovery probability and recommend action",
    description=(
        "Accepts a failed payment's features and returns a structured "
        "recovery decision including probability, risk tier, recommended "
        "action, expected recovery value, and a human-readable explanation."
    ),
)
def predict(request: PredictionRequest) -> PredictionResponse:
    """Prediction endpoint: request → transform → predict → decide → respond."""
    logger.info("Prediction request received for amount=%.2f", request.amount)

    try:
        predictor = _get_predictor()
    except FileNotFoundError as exc:
        logger.error("Model artifacts not found: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "Model artifacts are not available. "
                "Ensure the model has been trained with "
                "`python -m ml.training.train`."
            ),
        )

    try:
        # Transform raw request → one-hot DataFrame
        df = transform_request_to_dataframe(request, predictor.feature_names)

        # ML prediction
        probabilities = predictor.predict_proba(df)
        probability = float(probabilities[0])

        # Ensure probability is in valid range (defensive)
        probability = float(np.clip(probability, 0.0, 1.0))

    except ValueError as exc:
        logger.warning("Feature validation failed: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("Prediction failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred during prediction.",
        )

    try:
        # Decision engine
        engine = _get_decision_engine()
        model_version = predictor.metadata.get("version", "unknown")
        decision = engine.decide(
            recovery_probability=probability,
            amount=request.amount,
            failure_code=request.failure_code,
            retry_count=request.retry_count,
            model_version=model_version,
        )

        logger.info(
            "Decision generated: tier=%s action=%s probability=%.4f",
            decision.risk_tier.value,
            decision.recommended_action.value,
            probability,
        )

    except Exception as exc:
        logger.error("Decision engine failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred during decision generation.",
        )

    return PredictionResponse(
        recovery_probability=round(probability, 6),
        risk_tier=decision.risk_tier.value,
        recommended_action=decision.recommended_action.value,
        expected_recovery_value=decision.expected_recovery_value,
        reason=decision.reason,
        model_version=decision.model_version,
    )


# ====================================================================
# GET /model/info
# ====================================================================

@router.get(
    "/model/info",
    response_model=ModelInfoResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Model not available"},
    },
    summary="Get model metadata",
    description="Returns safe metadata about the currently loaded model.",
)
def model_info() -> ModelInfoResponse:
    """Return safe model metadata."""
    try:
        predictor = _get_predictor()
    except FileNotFoundError as exc:
        logger.error("Model artifacts not found: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Model artifacts are not available.",
        )

    metadata = predictor.metadata

    return ModelInfoResponse(
        version=metadata.get("version", "unknown"),
        model_type=metadata.get("model_type", "unknown"),
        feature_count=metadata.get("feature_count", len(predictor.feature_names)),
        training_timestamp=metadata.get("training_timestamp"),
        metrics=metadata.get("metrics"),
    )
