"""
Model training for the RecoverIQ recovery-prediction pipeline.

Connects to the existing database via ``backend.database.SessionLocal``,
reuses the Day 2 feature pipeline (``ml.dataset.build_ml_dataset``),
trains a LogisticRegression baseline, evaluates on the time-based
validation set, and persists the model + metadata.

Usage:
    python -m ml.training.train
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Allow running as ``python -m ml.training.train`` from the project root.
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.database import SessionLocal
from ml.config import LEAKAGE_COLUMNS, TARGET_COLUMN
from ml.dataset import build_ml_dataset
from ml.training.evaluate import compute_class_distribution, evaluate_model

# --------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------

MODELS_DIR = Path(_PROJECT_ROOT) / "models"
MODEL_PATH = MODELS_DIR / "recovery_model.joblib"
METADATA_PATH = MODELS_DIR / "model_metadata.json"

# --------------------------------------------------------------------
# Training
# --------------------------------------------------------------------

RANDOM_STATE = 42


def train_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
):
    """Train a StandardScaler + LogisticRegression pipeline.

    LogisticRegression with lbfgs requires scaled features for reliable
    convergence.  Wrapping in a Pipeline keeps the scaler and model
    together as a single serializable artifact.

    Parameters
    ----------
    X_train : pd.DataFrame
        Feature matrix (output of ``build_ml_dataset``).
    y_train : pd.Series
        Boolean target series.

    Returns
    -------
    sklearn.pipeline.Pipeline
        Fitted pipeline (scaler → logistic regression).
    """
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(
            max_iter=1000,
            random_state=RANDOM_STATE,
            solver="lbfgs",
        )),
    ])
    pipeline.fit(X_train, y_train)
    return pipeline


# --------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------


def save_model(
    model,
    feature_names: list[str],
    metrics: dict[str, Any],
    class_distribution: dict[str, int],
    split_timestamp: pd.Timestamp,
) -> None:
    """Save model artifact and metadata to ``models/``."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Model artifact
    joblib.dump(model, MODEL_PATH)

    # Metadata (JSON-serializable)
    metadata = {
        "model_type": "Pipeline(StandardScaler + LogisticRegression)",
        "target_name": TARGET_COLUMN,
        "random_state": RANDOM_STATE,
        "solver": "lbfgs",
        "max_iter": 1000,
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "split_timestamp": str(split_timestamp),
        "feature_count": len(feature_names),
        "feature_names": feature_names,
        "class_distribution": class_distribution,
        "metrics": metrics,
    }
    with open(METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)


# --------------------------------------------------------------------
# End-to-end pipeline
# --------------------------------------------------------------------


def run_training_pipeline() -> dict[str, Any]:
    """Full training pipeline: DB → features → train → evaluate → save.

    Returns
    -------
    dict
        Summary including metrics, paths, and class distribution.
    """
    print("=" * 60)
    print("RecoverIQ — Day 3 Model Training")
    print("=" * 60)

    # 1. Build dataset (reuses Day 2 pipeline exactly)
    print("\n[1/5] Building ML dataset from database...")
    session = SessionLocal()
    try:
        dataset = build_ml_dataset(session)
    finally:
        session.close()

    X_train = dataset.X_train
    y_train = dataset.y_train
    X_val = dataset.X_val
    y_val = dataset.y_val

    feature_names = list(X_train.columns)

    # Safety: verify no leakage columns slipped through
    for col in LEAKAGE_COLUMNS:
        assert col not in feature_names, (
            f"LEAKAGE DETECTED: '{col}' found in training features"
        )

    print(f"    Training samples:   {len(X_train)}")
    print(f"    Validation samples: {len(X_val)}")
    print(f"    Features:           {len(feature_names)}")
    print(f"    Split timestamp:    {dataset.split_timestamp}")

    # 2. Class distribution
    print("\n[2/5] Computing class distribution...")
    class_dist = compute_class_distribution(y_train, y_val)
    print(f"    Train — recovered: {class_dist['train_recovered']}, "
          f"unrecovered: {class_dist['train_unrecovered']}")
    print(f"    Val   — recovered: {class_dist['val_recovered']}, "
          f"unrecovered: {class_dist['val_unrecovered']}")

    # 3. Train
    print("\n[3/5] Training LogisticRegression...")
    model = train_model(X_train, y_train)
    print("    Training complete.")

    # 4. Evaluate
    print("\n[4/5] Evaluating on validation set...")
    metrics = evaluate_model(model, X_val, y_val)

    print(f"    Accuracy:      {metrics['accuracy']:.4f}")
    print(f"    Precision:     {metrics['precision']:.4f}")
    print(f"    Recall:        {metrics['recall']:.4f}")
    print(f"    F1:            {metrics['f1']:.4f}")
    print(f"    ROC-AUC:       {metrics['roc_auc']:.4f}")
    print(f"    PR-AUC:        {metrics['pr_auc']:.4f}")
    print(f"    Brier Score:   {metrics['brier_score']:.4f}")
    print(f"    Confusion Matrix:")
    cm = metrics["confusion_matrix"]
    print(f"        TN={cm[0][0]}  FP={cm[0][1]}")
    print(f"        FN={cm[1][0]}  TP={cm[1][1]}")

    # 5. Save
    print("\n[5/5] Saving model and metadata...")
    save_model(model, feature_names, metrics, class_dist,
               dataset.split_timestamp)
    print(f"    Model:    {MODEL_PATH}")
    print(f"    Metadata: {METADATA_PATH}")

    # Verify round-trip
    loaded = joblib.load(MODEL_PATH)
    sample_proba = loaded.predict_proba(X_val.iloc[:5])[:, 1]
    assert all(0.0 <= p <= 1.0 for p in sample_proba), (
        "Round-trip verification failed: probabilities out of range"
    )
    print("    Round-trip verification: PASSED")

    print("\n" + "=" * 60)
    print("Day 3 training pipeline complete.")
    print("=" * 60)

    return {
        "model_path": str(MODEL_PATH),
        "metadata_path": str(METADATA_PATH),
        "metrics": metrics,
        "class_distribution": class_dist,
        "feature_count": len(feature_names),
    }


if __name__ == "__main__":
    run_training_pipeline()
