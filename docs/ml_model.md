# RecoverIQ — ML Model Documentation (Day 3)

## 1. Problem Definition

RecoverIQ predicts whether a **failed payment** can be recovered.
Not every failure is the same: transient failures (timeouts, network
errors) are more likely to succeed on retry than fundamental ones
(insufficient funds, fraud holds). The model estimates the probability
that a specific failed transaction will be recovered, enabling a future
recovery agent to prioritise its actions.

**Current scope**: the model produces a recovery probability for each
failed transaction. It does **not** make a recovery decision, select
an action, or trigger a retry — those are future work (Day 4+).

## 2. Target

- **Column**: `transactions.recovered` (boolean)
- **Population**: only `transactions` rows where `status = 'FAILED'`
- `True` = the failed transaction was (synthetically) recovered
- `False` = the failed transaction was not recovered

## 3. Feature Pipeline

The model reuses the Day 2 feature pipeline (`ml/features.py`,
`ml/dataset.py`) without duplicating any feature-engineering logic.

```
PostgreSQL
    ↓
ml.features.load_raw_frame()     — FAILED transactions + safe Customer/Merchant columns
    ↓
ml.features._add_time_features() — hour_of_day, day_of_week
    ↓
ml.features._coerce_numeric_dtypes() — Decimal → float64
    ↓
ml.features._encode_categoricals()   — one-hot with fixed vocabulary
    ↓
ml.features._handle_missing_numeric() — median fill (robustness)
    ↓
ml.dataset.build_ml_dataset()     — time-aware 80/20 split → X_train/y_train/X_val/y_val
    ↓
ml.training.train.train_model()   — LogisticRegression
```

### Feature sources

| Source | Features |
|---|---|
| `transactions` (at failure time) | `amount`, `retry_count`, `payment_method`, `bank`, `device_type`, `failure_code`, `customer_success_rate`, `customer_lifetime_value`, `recent_bank_failure_rate`, `recent_method_failure_rate` |
| `transactions` (derived) | `hour_of_day`, `day_of_week` |
| `customers` (static traits) | `preferred_payment_method`, `preferred_bank`, `abandonment_rate` |
| `merchants` (static traits) | `merchant_category`, `average_transaction_value`, `monthly_transaction_volume` |

Categorical features are one-hot encoded against a **fixed vocabulary**
sourced from the dataset generator's own constants
(`ml.config.CATEGORICAL_VOCAB`), guaranteeing identical columns across
train/validation/inference regardless of which categories appear.

## 4. Leakage Prevention

Three categories of leakage are prevented:

### Outcome fields (never used as features)
| Column | Reason |
|---|---|
| `recovered` | is the target itself |
| `recovery_delay_minutes` | only known after recovery concludes |
| `recovered_amount` | only known after recovery concludes |

### Customer full-history aggregates (excluded from feature set)
`Customer.total_transactions`, `.successful_transactions`,
`.failed_transactions`, `.customer_success_rate`, `.lifetime_value`,
`.average_transaction_value`, `.previous_recoveries` are computed from
a customer's **entire** 30-day history, leaking future transaction
outcomes for any non-last transaction.

**Safe alternatives used**: `Transaction.customer_success_rate` and
`Transaction.customer_lifetime_value` are rolling snapshots computed
strictly from transactions processed *before* the current one.

### Payment health (excluded entirely)
`payment_health` buckets include the current transaction's own outcome
and later same-hour transactions. A causally-safe version (prior-hour
only) is future work.

## 5. Train/Validation Strategy

- **Method**: time-aware split by `timestamp`, not random
- **Split fraction**: 80% earliest / 20% latest of FAILED transactions
- **Rationale**: a random split would let the model train on
  transactions chronologically *after* some validation transactions,
  which is impossible in production
- The cutoff is computed dynamically from the data each time, not a
  hardcoded date

## 6. Model Choice

**LogisticRegression** (scikit-learn):
- Reliable, well-understood baseline
- Produces calibrated probabilities natively
- Fast to train (~6K rows)
- Deterministic (`random_state=42`)
- Easy to persist and reload (joblib)
- Easy to explain to buildathon judges
- Already available via `scikit-learn==1.5.2` in `requirements.txt`

Configuration: `solver='lbfgs'`, `max_iter=1000`, `random_state=42`

## 7. Metrics

All metrics are computed from actual model predictions on the
time-based validation set. Nothing is hardcoded.

| Metric | Description |
|---|---|
| Accuracy | Overall correct classification rate |
| Precision | Of predicted-recovered, how many were actually recovered |
| Recall | Of actually-recovered, how many did the model identify |
| F1 | Harmonic mean of precision and recall |
| ROC-AUC | Area under the ROC curve (discrimination quality) |
| PR-AUC | Area under the precision-recall curve (important for imbalanced data) |
| Brier Score | Calibration quality of probability estimates (lower is better) |
| Confusion Matrix | TN/FP/FN/TP breakdown |

Actual metric values are recorded in `models/model_metadata.json` after
each training run.

## 8. Model Artifact

| File | Contents |
|---|---|
| `models/recovery_model.joblib` | Serialized LogisticRegression model |
| `models/model_metadata.json` | Model type, features, metrics, timestamps, class distribution |

The metadata JSON stores `feature_names` — the exact ordered list of
features the model expects at inference time.

## 9. Inference Flow

```python
from ml.inference.predictor import RecoveryPredictor

predictor = RecoveryPredictor()  # loads from models/

# X is a DataFrame with the same features used during training
probabilities = predictor.predict_proba(X)
# → numpy array of P(recovered=True) for each row, in [0.0, 1.0]
```

The predictor:
1. Loads the persisted model and metadata
2. Validates all expected features are present
3. Rejects leakage columns (`recovered`, `recovery_delay_minutes`,
   `recovered_amount`)
4. Reorders columns to match the exact training order
5. Warns about and drops unexpected extra columns
6. Returns P(recovered=True) for each row

## 10. Known Limitations

1. **Synthetic data only** — the model is trained and validated on
   generated data, not real payment transactions
2. **LogisticRegression** — a linear model that may underfit if the
   true decision boundary is nonlinear; a tree-based model may
   perform better
3. **No hyperparameter tuning** — default settings are used; a grid
   search or cross-validation study could improve performance
4. **No class weighting** — the dataset has a ~30/70 recovered/
   unrecovered imbalance; explicit class weighting or resampling could
   help
5. **No probability calibration** — LogisticRegression probabilities
   are natively calibrated, but isotonic/Platt calibration could
   improve Brier score
6. **Payment health excluded** — the current `payment_health` table
   has leakage; a causally-safe version could add predictive power
7. **Static customer/merchant features** — the safe Customer/Merchant
   columns are static traits, not dynamic signals
8. **This is NOT a production model** — it is a buildathon prototype

## 11. Next Steps (Day 4+)

1. **Prediction API endpoint** — expose `/predict` via FastAPI
2. **Recovery decision engine** — map probability → risk tier → action
3. **Recovery action selection** — choose between retry, reminder,
   escalation based on probability + failure code
4. **Payment retry workflow** — integrate with Razorpay API for
   actual recovery actions
5. **Dashboard** — visualise recovery performance, model metrics,
   action outcomes
6. **Tree-based model comparison** — try RandomForest or GBM
7. **Hyperparameter tuning** — grid search with time-series CV
8. **Production deployment** — Docker, CI/CD, monitoring
