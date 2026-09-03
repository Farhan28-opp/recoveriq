"""
Model evaluation for the RecoverIQ recovery-prediction pipeline.

Computes classification metrics on a held-out validation set.  Every
metric is computed from the actual model predictions — nothing is
hardcoded or fabricated.
"""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def evaluate_model(
    model,
    X_val: pd.DataFrame,
    y_val: pd.Series,
) -> dict[str, Any]:
    """Evaluate a fitted binary classifier on the validation set.

    Parameters
    ----------
    model : fitted sklearn estimator
        Must support ``predict`` and ``predict_proba``.
    X_val : pd.DataFrame
        Validation feature matrix (same columns as training).
    y_val : pd.Series
        Validation target (boolean).

    Returns
    -------
    dict
        All evaluation metrics in a JSON-serializable structure.
    """
    y_pred = model.predict(X_val)
    y_proba = model.predict_proba(X_val)[:, 1]  # P(recovered=True)

    cm = confusion_matrix(y_val, y_pred)

    metrics: dict[str, Any] = {
        "accuracy": float(accuracy_score(y_val, y_pred)),
        "precision": float(precision_score(y_val, y_pred, zero_division=0)),
        "recall": float(recall_score(y_val, y_pred, zero_division=0)),
        "f1": float(f1_score(y_val, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_val, y_proba)),
        "pr_auc": float(average_precision_score(y_val, y_proba)),
        "brier_score": float(brier_score_loss(y_val, y_proba)),
        "confusion_matrix": cm.tolist(),
    }
    return metrics


def compute_class_distribution(
    y_train: pd.Series,
    y_val: pd.Series,
) -> dict[str, int]:
    """Compute recovered/unrecovered counts for train and validation."""
    return {
        "train_recovered": int(y_train.sum()),
        "train_unrecovered": int((~y_train).sum()),
        "train_total": int(len(y_train)),
        "val_recovered": int(y_val.sum()),
        "val_unrecovered": int((~y_val).sum()),
        "val_total": int(len(y_val)),
    }
