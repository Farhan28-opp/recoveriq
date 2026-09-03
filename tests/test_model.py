"""
Tests for the RecoverIQ Day 3 model training pipeline
(ml/training/train.py, ml/training/evaluate.py).

These tests query the existing database (via the application's existing
SQLAlchemy session factory) and are skipped automatically if no
synthetic dataset has been generated yet.

Run with:
    pytest tests/test_model.py -v
"""

import json
import tempfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sqlalchemy import func, select

from backend.database import SessionLocal
from backend.models import Customer
from ml.config import LEAKAGE_COLUMNS, TARGET_COLUMN
from ml.dataset import build_ml_dataset
from ml.training.evaluate import compute_class_distribution, evaluate_model
from ml.training.train import RANDOM_STATE, save_model, train_model


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
def trained_model(ml_dataset):
    return train_model(ml_dataset.X_train, ml_dataset.y_train)


# ==================================================
# 1. MODEL TRAINING SUCCEEDS
# ==================================================

def test_model_training_succeeds(trained_model):
    assert isinstance(trained_model, Pipeline)


# ==================================================
# 2. MODEL PRODUCES PREDICTIONS
# ==================================================

def test_model_produces_predictions(trained_model, ml_dataset):
    preds = trained_model.predict(ml_dataset.X_val)
    assert len(preds) == len(ml_dataset.X_val)


# ==================================================
# 3. MODEL PRODUCES PROBABILITIES BETWEEN 0 AND 1
# ==================================================

def test_model_produces_valid_probabilities(trained_model, ml_dataset):
    probas = trained_model.predict_proba(ml_dataset.X_val)[:, 1]
    assert len(probas) == len(ml_dataset.X_val)
    assert all(0.0 <= p <= 1.0 for p in probas), (
        "Some probabilities are outside [0, 1]"
    )


# ==================================================
# 4. EXPECTED NUMBER OF PREDICTIONS
# ==================================================

def test_expected_prediction_count(trained_model, ml_dataset):
    preds = trained_model.predict(ml_dataset.X_val)
    probas = trained_model.predict_proba(ml_dataset.X_val)[:, 1]
    assert len(preds) == len(ml_dataset.y_val)
    assert len(probas) == len(ml_dataset.y_val)


# ==================================================
# 5 & 6. MODEL CAN BE SAVED AND LOADED, PRODUCES SAME PREDICTIONS
# ==================================================

def test_model_save_and_load_round_trip(trained_model, ml_dataset):
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = Path(tmpdir) / "test_model.joblib"
        joblib.dump(trained_model, model_path)

        # Verify file was created
        assert model_path.exists()

        # Load and compare predictions
        loaded = joblib.load(model_path)
        original_probas = trained_model.predict_proba(ml_dataset.X_val)[:, 1]
        loaded_probas = loaded.predict_proba(ml_dataset.X_val)[:, 1]
        np.testing.assert_array_equal(original_probas, loaded_probas)


# ==================================================
# 7. FEATURE ORDERING IS PRESERVED
# ==================================================

def test_feature_ordering_preserved(trained_model, ml_dataset):
    """The model's expected features match the training columns exactly."""
    feature_names = list(ml_dataset.X_train.columns)
    assert len(feature_names) == trained_model.n_features_in_
    # sklearn Pipeline stores feature_names_in_ on the first step
    if hasattr(trained_model, "feature_names_in_"):
        np.testing.assert_array_equal(
            trained_model.feature_names_in_, feature_names
        )


# ==================================================
# 8. LEAKAGE COLUMNS ARE NEVER ACCEPTED
# ==================================================

def test_leakage_columns_not_in_training_features(ml_dataset):
    for col in LEAKAGE_COLUMNS:
        assert col not in ml_dataset.X_train.columns, (
            f"Leakage column '{col}' found in X_train"
        )
        assert col not in ml_dataset.X_val.columns, (
            f"Leakage column '{col}' found in X_val"
        )


# ==================================================
# 9. EVALUATION METRICS ARE VALID
# ==================================================

def test_evaluation_metrics_are_valid(trained_model, ml_dataset):
    metrics = evaluate_model(trained_model, ml_dataset.X_val, ml_dataset.y_val)

    assert 0.0 <= metrics["accuracy"] <= 1.0
    assert 0.0 <= metrics["precision"] <= 1.0
    assert 0.0 <= metrics["recall"] <= 1.0
    assert 0.0 <= metrics["f1"] <= 1.0
    assert 0.0 <= metrics["roc_auc"] <= 1.0
    assert 0.0 <= metrics["pr_auc"] <= 1.0
    assert 0.0 <= metrics["brier_score"] <= 1.0
    assert len(metrics["confusion_matrix"]) == 2
    assert len(metrics["confusion_matrix"][0]) == 2


# ==================================================
# 10. CLASS DISTRIBUTION IS CORRECT
# ==================================================

def test_class_distribution(ml_dataset):
    dist = compute_class_distribution(ml_dataset.y_train, ml_dataset.y_val)
    assert dist["train_recovered"] + dist["train_unrecovered"] == dist["train_total"]
    assert dist["val_recovered"] + dist["val_unrecovered"] == dist["val_total"]
    assert dist["train_total"] == len(ml_dataset.y_train)
    assert dist["val_total"] == len(ml_dataset.y_val)


# ==================================================
# 11. SAVE_MODEL WRITES VALID METADATA
# ==================================================

def test_save_model_writes_valid_metadata(trained_model, ml_dataset):
    with tempfile.TemporaryDirectory() as tmpdir:
        import ml.training.train as train_mod
        # Temporarily override paths
        orig_models_dir = train_mod.MODELS_DIR
        orig_model_path = train_mod.MODEL_PATH
        orig_metadata_path = train_mod.METADATA_PATH

        train_mod.MODELS_DIR = Path(tmpdir)
        train_mod.MODEL_PATH = Path(tmpdir) / "test_model.joblib"
        train_mod.METADATA_PATH = Path(tmpdir) / "test_metadata.json"

        try:
            metrics = evaluate_model(trained_model, ml_dataset.X_val, ml_dataset.y_val)
            class_dist = compute_class_distribution(ml_dataset.y_train, ml_dataset.y_val)
            feature_names = list(ml_dataset.X_train.columns)

            save_model(trained_model, feature_names, metrics, class_dist,
                       ml_dataset.split_timestamp)

            assert train_mod.MODEL_PATH.exists()
            assert train_mod.METADATA_PATH.exists()

            with open(train_mod.METADATA_PATH) as f:
                meta = json.load(f)

            assert meta["model_type"] == "Pipeline(StandardScaler + LogisticRegression)"
            assert meta["target_name"] == TARGET_COLUMN
            assert meta["feature_count"] == len(feature_names)
            assert meta["feature_names"] == feature_names
            assert meta["random_state"] == RANDOM_STATE
            assert "metrics" in meta
            assert "class_distribution" in meta
        finally:
            train_mod.MODELS_DIR = orig_models_dir
            train_mod.MODEL_PATH = orig_model_path
            train_mod.METADATA_PATH = orig_metadata_path


# ==================================================
# 12. DETERMINISTIC TRAINING
# ==================================================

def test_deterministic_training(ml_dataset):
    model_a = train_model(ml_dataset.X_train, ml_dataset.y_train)
    model_b = train_model(ml_dataset.X_train, ml_dataset.y_train)
    probas_a = model_a.predict_proba(ml_dataset.X_val)[:, 1]
    probas_b = model_b.predict_proba(ml_dataset.X_val)[:, 1]
    np.testing.assert_array_equal(probas_a, probas_b)
