"""
Tests for the RecoverIQ Day 3 inference / prediction component
(ml/inference/predictor.py).

These tests query the existing database (via the application's existing
SQLAlchemy session factory) and are skipped automatically if no
synthetic dataset has been generated yet.  They also require a trained
model artifact at ``models/recovery_model.joblib``.

Run with:
    pytest tests/test_prediction.py -v
"""

import json
import tempfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sqlalchemy import func, select

from backend.database import SessionLocal
from backend.models import Customer
from ml.config import LEAKAGE_COLUMNS
from ml.dataset import build_ml_dataset
from ml.inference.predictor import RecoveryPredictor
from ml.training.train import MODEL_PATH, METADATA_PATH, train_model


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


@pytest.fixture(scope="module")
def ml_dataset(db_session):
    return build_ml_dataset(db_session)


@pytest.fixture(scope="module")
def predictor_artifacts(ml_dataset):
    """Train a model and save artifacts to a temp directory for tests."""
    tmpdir = tempfile.mkdtemp()
    model_path = Path(tmpdir) / "recovery_model.joblib"
    metadata_path = Path(tmpdir) / "model_metadata.json"

    model = train_model(ml_dataset.X_train, ml_dataset.y_train)
    joblib.dump(model, model_path)

    feature_names = list(ml_dataset.X_train.columns)
    metadata = {
        "model_type": "LogisticRegression",
        "target_name": "recovered",
        "feature_count": len(feature_names),
        "feature_names": feature_names,
        "random_state": 42,
    }
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return model_path, metadata_path, model


@pytest.fixture(scope="module")
def predictor(predictor_artifacts):
    model_path, metadata_path, _ = predictor_artifacts
    return RecoveryPredictor(model_path=model_path, metadata_path=metadata_path)


# ==================================================
# 1. PREDICTOR LOADS SUCCESSFULLY
# ==================================================

def test_predictor_loads_successfully(predictor):
    assert predictor.model is not None
    assert predictor.feature_names is not None
    assert len(predictor.feature_names) > 0


# ==================================================
# 2. PREDICTOR PRODUCES PROBABILITIES BETWEEN 0 AND 1
# ==================================================

def test_predictor_produces_valid_probabilities(predictor, ml_dataset):
    probas = predictor.predict_proba(ml_dataset.X_val)
    assert len(probas) == len(ml_dataset.X_val)
    assert all(0.0 <= p <= 1.0 for p in probas), (
        "Some probabilities are outside [0, 1]"
    )


# ==================================================
# 3. PREDICTOR PRODUCES BINARY PREDICTIONS
# ==================================================

def test_predictor_produces_binary_predictions(predictor, ml_dataset):
    preds = predictor.predict(ml_dataset.X_val)
    assert len(preds) == len(ml_dataset.X_val)


# ==================================================
# 4. MISSING FEATURES RAISE CLEAR ERROR
# ==================================================

def test_missing_features_raise_error(predictor, ml_dataset):
    # Drop a required feature
    X_broken = ml_dataset.X_val.drop(columns=[ml_dataset.X_val.columns[0]])
    with pytest.raises(ValueError, match="Missing.*required feature"):
        predictor.predict_proba(X_broken)


# ==================================================
# 5. LEAKAGE COLUMNS RAISE CLEAR ERROR
# ==================================================

def test_leakage_columns_rejected(predictor, ml_dataset):
    for col in LEAKAGE_COLUMNS:
        X_with_leakage = ml_dataset.X_val.copy()
        X_with_leakage[col] = 0
        with pytest.raises(ValueError, match="Leakage columns"):
            predictor.predict_proba(X_with_leakage)


# ==================================================
# 6. EXTRA COLUMNS ARE HANDLED (dropped with warning)
# ==================================================

def test_extra_columns_handled(predictor, ml_dataset):
    X_extra = ml_dataset.X_val.copy()
    X_extra["totally_bogus_column"] = 999

    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        probas = predictor.predict_proba(X_extra)
        assert len(probas) == len(ml_dataset.X_val)
        assert any("unexpected column" in str(warning.message).lower()
                    for warning in w)


# ==================================================
# 7. FEATURE ORDER MATCHES TRAINING
# ==================================================

def test_feature_order_matches_training(predictor, ml_dataset):
    assert predictor.feature_names == list(ml_dataset.X_train.columns)


# ==================================================
# 8. PREDICTOR MATCHES DIRECT MODEL PREDICTIONS
# ==================================================

def test_predictor_matches_direct_model(predictor, predictor_artifacts, ml_dataset):
    _, _, direct_model = predictor_artifacts
    predictor_probas = predictor.predict_proba(ml_dataset.X_val)
    direct_probas = direct_model.predict_proba(ml_dataset.X_val)[:, 1]
    np.testing.assert_array_equal(predictor_probas, direct_probas)


# ==================================================
# 9. FILE NOT FOUND RAISES CLEAR ERROR
# ==================================================

def test_missing_model_file_raises_error():
    with pytest.raises(FileNotFoundError, match="Model artifact not found"):
        RecoveryPredictor(
            model_path="/nonexistent/path/model.joblib",
            metadata_path="/nonexistent/path/metadata.json",
        )


# ==================================================
# 10. SHUFFLED COLUMN ORDER STILL WORKS
# ==================================================

def test_shuffled_column_order_produces_same_results(predictor, ml_dataset):
    """The predictor must reorder columns to match training, not rely on
    accidental DataFrame column ordering."""
    import random

    X_shuffled = ml_dataset.X_val.copy()
    cols = list(X_shuffled.columns)
    # Deterministic shuffle
    rng = random.Random(123)
    rng.shuffle(cols)
    X_shuffled = X_shuffled[cols]

    probas_original = predictor.predict_proba(ml_dataset.X_val)
    probas_shuffled = predictor.predict_proba(X_shuffled)
    np.testing.assert_array_equal(probas_original, probas_shuffled)
