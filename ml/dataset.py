"""
Reproducible dataset construction for the RecoverIQ recovery-prediction
pipeline: DB -> features -> time-aware train/validation split -> X/y.

Model training itself is out of Day 2 scope — this module stops at
producing a ready-to-train (X_train, y_train, X_val, y_val).
"""

from dataclasses import dataclass

import pandas as pd
from sqlalchemy.orm import Session

from ml.config import TRAIN_FRACTION
from ml.features import build_features, split_features_and_target


@dataclass
class MLDataset:
    X_train: pd.DataFrame
    y_train: pd.Series
    X_val: pd.DataFrame
    y_val: pd.Series
    meta_train: pd.DataFrame
    meta_val: pd.DataFrame
    split_timestamp: pd.Timestamp


def time_aware_split(df: pd.DataFrame, train_fraction: float = TRAIN_FRACTION):
    """
    Split a frame into train/validation by TIMESTAMP, not randomly.

    Why: this is payment/recovery data. A random split would let the
    model train on transactions that happened AFTER some of the
    transactions it's validated on, which a real production system
    could never do (it only ever sees the past). Splitting by
    timestamp keeps validation honest: every validation transaction
    happens strictly after every training transaction.

    `train_fraction` (default from ml.config.TRAIN_FRACTION, currently
    0.8) is applied to the actual timestamp-sorted distribution of the
    eligible (FAILED) transactions in `df` — the cutoff is computed
    from the real data each time, not a hardcoded date.
    """
    ordered = df.sort_values("timestamp").reset_index(drop=True)
    cutoff_idx = int(len(ordered) * train_fraction)
    split_timestamp = ordered["timestamp"].iloc[cutoff_idx]

    train_df = ordered[ordered["timestamp"] < split_timestamp]
    val_df = ordered[ordered["timestamp"] >= split_timestamp]
    return train_df, val_df, split_timestamp


def build_ml_dataset(session: Session, train_fraction: float = TRAIN_FRACTION) -> MLDataset:
    """End-to-end, reproducible pipeline: DB -> features -> split -> X/y."""
    full_df = build_features(session)
    train_df, val_df, split_ts = time_aware_split(full_df, train_fraction)

    X_train, y_train, meta_train = split_features_and_target(train_df)
    X_val, y_val, meta_val = split_features_and_target(val_df)

    # Safety net: fixed categorical vocab (ml.config) already guarantees
    # identical columns on both sides, but align() protects against any
    # future non-categorical column drift instead of failing silently
    # at model-fit time.
    X_train, X_val = X_train.align(X_val, join="outer", axis=1, fill_value=0)

    return MLDataset(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        meta_train=meta_train,
        meta_val=meta_val,
        split_timestamp=split_ts,
    )
