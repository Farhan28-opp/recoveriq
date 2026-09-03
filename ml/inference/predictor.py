"""
Reusable inference component for the RecoverIQ recovery-prediction model.

Loads a persisted model artifact and its metadata, validates incoming
feature DataFrames, and returns recovery probabilities.  Designed to be
imported by future API endpoints or batch pipelines without duplicating
any feature-engineering or model-loading logic.
"""

import json
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

from ml.config import LEAKAGE_COLUMNS


# Default artifact paths (relative to project root).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_MODEL_PATH = _PROJECT_ROOT / "models" / "recovery_model.joblib"
DEFAULT_METADATA_PATH = _PROJECT_ROOT / "models" / "model_metadata.json"


class RecoveryPredictor:
    """Load a persisted recovery model and produce predictions.

    Parameters
    ----------
    model_path : Path or str, optional
        Path to the joblib model file.
    metadata_path : Path or str, optional
        Path to the JSON metadata file.

    Raises
    ------
    FileNotFoundError
        If model or metadata files do not exist.
    """

    def __init__(
        self,
        model_path: Optional[Path | str] = None,
        metadata_path: Optional[Path | str] = None,
    ) -> None:
        model_path = Path(model_path or DEFAULT_MODEL_PATH)
        metadata_path = Path(metadata_path or DEFAULT_METADATA_PATH)

        if not model_path.exists():
            raise FileNotFoundError(
                f"Model artifact not found: {model_path}. "
                "Run `python -m ml.training.train` first."
            )
        if not metadata_path.exists():
            raise FileNotFoundError(
                f"Model metadata not found: {metadata_path}. "
                "Run `python -m ml.training.train` first."
            )

        self.model = joblib.load(model_path)

        with open(metadata_path) as f:
            self.metadata: dict = json.load(f)

        self.feature_names: list[str] = self.metadata["feature_names"]
        self.model_type: str = self.metadata["model_type"]
        self.target_name: str = self.metadata["target_name"]

    # ----------------------------------------------------------------
    # Validation
    # ----------------------------------------------------------------

    def _validate_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """Validate and align input features to the training schema.

        1. Rejects leakage columns.
        2. Checks all expected features are present.
        3. Reorders columns to exactly match training order.
        4. Drops unexpected extra columns with a warning.

        Returns the validated, reordered DataFrame.
        """
        # Reject leakage columns
        present_leakage = [c for c in LEAKAGE_COLUMNS if c in X.columns]
        if present_leakage:
            raise ValueError(
                f"Leakage columns must not be passed to the predictor: "
                f"{present_leakage}. These are post-outcome fields that "
                f"would not be available at prediction time."
            )

        # Check for missing features
        missing = [c for c in self.feature_names if c not in X.columns]
        if missing:
            raise ValueError(
                f"Missing {len(missing)} required feature(s): {missing}"
            )

        # Warn about extra columns (silently drop them)
        extra = [c for c in X.columns if c not in self.feature_names]
        if extra:
            import warnings
            warnings.warn(
                f"Dropping {len(extra)} unexpected column(s) not used by "
                f"the model: {extra[:10]}"
                + (" ..." if len(extra) > 10 else ""),
                stacklevel=2,
            )

        # Reorder to exact training column order
        return X[self.feature_names]

    # ----------------------------------------------------------------
    # Prediction
    # ----------------------------------------------------------------

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return recovery probabilities for each row.

        Parameters
        ----------
        X : pd.DataFrame
            Feature matrix.  Must contain all columns the model was
            trained on (available from ``self.feature_names``).

        Returns
        -------
        np.ndarray
            1-D array of P(recovered=True) for each row, values in
            [0.0, 1.0].
        """
        X_aligned = self._validate_features(X)
        probas = self.model.predict_proba(X_aligned)[:, 1]
        return probas

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return binary class predictions (True/False).

        Parameters
        ----------
        X : pd.DataFrame
            Feature matrix.

        Returns
        -------
        np.ndarray
            1-D boolean array.
        """
        X_aligned = self._validate_features(X)
        return self.model.predict(X_aligned)
