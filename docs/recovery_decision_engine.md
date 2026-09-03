# Recovery Decision Engine

RecoverIQ Day 4 documentation — Prediction API and Recovery Decision Engine.

## 1. Purpose

The Recovery Decision Engine converts a machine-learning recovery
probability into a structured, actionable recovery decision.  It is the
component that transforms RecoverIQ from "a model that predicts
recovery probability" into "a system that recommends what to do about a
failed payment."

The engine is a pure business-logic component with no dependency on
FastAPI, the ML model, or the database.

## 2. Architecture

```
POST /predict (JSON payload)
     │
     ▼
PredictionRequest (Pydantic validation)
     │
     ▼
transform_request_to_dataframe()
  - Accepts raw categorical values (e.g. "UPI")
  - One-hot encodes using CATEGORICAL_VOCAB from ml.config
  - Produces 61-column DataFrame matching model training schema
     │
     ▼
RecoveryPredictor.predict_proba()
  - Existing Day 3 ML inference component
  - Validates features, rejects leakage, reorders columns
  - Returns P(recovered=True)
     │
     ▼
DecisionEngine.decide()
  - Pure business logic
  - Applies safety constraints → failure context → tier → action
     │
     ▼
RecoveryDecision
  - probability, tier, action, expected_recovery_value, reason
     │
     ▼
PredictionResponse (JSON)
```

### Dependency Direction

```
API Route → Decision Engine
API Route → ML Predictor
Decision Engine ← (does NOT import) ML Predictor
Decision Engine ← (does NOT import) FastAPI
```

### File Locations

| Component | Location |
|---|---|
| Prediction route | `backend/routes/predict.py` |
| Feature transformation | `backend/routes/predict.py:transform_request_to_dataframe()` |
| Pydantic schemas | `backend/schemas/prediction.py` |
| Decision engine | `backend/services/decision_engine.py` |
| ML predictor | `ml/inference/predictor.py` (unchanged from Day 3) |
| Model artifacts | `models/recovery_model.joblib`, `models/model_metadata.json` |

## 3. Prediction Flow

1. **Request validation** — Pydantic validates all fields (numeric
   ranges, categorical values from fixed vocabulary)
2. **Feature transformation** — Raw categorical values are one-hot
   encoded to produce the 61-column DataFrame expected by the model
3. **ML prediction** — `RecoveryPredictor.predict_proba()` returns
   P(recovered=True) in [0.0, 1.0]
4. **Expected recovery value** — `probability × amount`
5. **Decision engine** — Applies decision hierarchy:
   1. Validate inputs
   2. Apply safety constraints (retry limit)
   3. Consider failure-code context
   4. Consider recovery probability (tier)
   5. Select action
   6. Generate explanation
6. **Response** — Structured JSON with probability, tier, action,
   expected recovery value, reason, and model version

## 4. Risk Tiers

| Tier | Probability Range | Description |
|---|---|---|
| **HIGH** | ≥ 0.70 | Strong recovery signal — automated action may be appropriate |
| **MEDIUM** | 0.40 – 0.69 | Moderate recovery signal — context-dependent action |
| **LOW** | < 0.40 | Weak recovery signal — limited automated action |

These are initial business-policy thresholds, not mathematically
optimized cutoffs.  They should be reviewed as the model improves and
real recovery outcome data becomes available.

## 5. Thresholds

Thresholds are centralized as module-level constants in
`backend/services/decision_engine.py`:

```python
HIGH_TIER_THRESHOLD = 0.70
MEDIUM_TIER_THRESHOLD = 0.40
MAX_AUTOMATED_RETRIES = 3
```

The `DecisionEngine` constructor accepts custom thresholds for
testing or future configuration.

## 6. Expected Recovery Value

```
expected_recovery_value = recovery_probability × transaction_amount
```

Example:

| Amount | Probability | Expected Recovery Value |
|---|---|---|
| ₹5,000 | 0.80 | ₹4,000 |
| ₹10,000 | 0.55 | ₹5,500 |
| ₹100 | 0.95 | ₹95 |

**Important**: This is a probabilistic estimate, not actual recovered
revenue.  No money has been recovered at prediction time.

## 7. Failure-Code Handling

The decision engine classifies failure codes into categories and adjusts
the recommended action accordingly:

### Temporary Failures
`TIMEOUT`, `NETWORK_ERROR`, `TECHNICAL_ERROR`

Potentially appropriate for automated retry (if retry limit allows).
- HIGH tier → `RETRY_PAYMENT`
- MEDIUM tier → `DELAYED_RETRY`
- LOW tier → `NO_ACTION`

### Fund/Limit Failures
`INSUFFICIENT_FUNDS`, `LIMIT_EXCEEDED`

Retry is unlikely to help; customer action is needed.
- HIGH/MEDIUM tier → `SEND_PAYMENT_REMINDER`
- LOW tier → `NO_ACTION`

### Fraud/Authentication
`FRAUD_CHECK`

Always escalated regardless of probability.
- All tiers → `ESCALATE_MANUAL_REVIEW`

### Method Unavailable
`METHOD_UNAVAILABLE`

Suggesting an alternative method is more appropriate.
- HIGH/MEDIUM tier → `SUGGEST_ALTERNATIVE_METHOD`
- LOW tier → `NO_ACTION`

### Bank Declined
`BANK_DECLINED`

Context-dependent response.
- HIGH tier → `DELAYED_RETRY`
- MEDIUM tier → `SUGGEST_ALTERNATIVE_METHOD`
- LOW tier → `ESCALATE_MANUAL_REVIEW`

### Unknown
`UNKNOWN` or any unrecognized failure code falls back to the
tier-based default action.

## 8. Retry Safety

The decision engine enforces a hard retry safety limit
(`MAX_AUTOMATED_RETRIES = 3`).  If `retry_count >= MAX_AUTOMATED_RETRIES`,
the engine **never** recommends `RETRY_PAYMENT` or `DELAYED_RETRY`,
regardless of how high the recovery probability is.

This prevents infinite retry loops.

When the retry limit is reached:
- `METHOD_UNAVAILABLE` → `SUGGEST_ALTERNATIVE_METHOD`
- HIGH tier → `ESCALATE_MANUAL_REVIEW`
- MEDIUM tier → `SEND_PAYMENT_REMINDER`
- LOW tier → `NO_ACTION`

## 9. Action Selection

| Action | Description |
|---|---|
| `RETRY_PAYMENT` | Recommend an immediate automated retry |
| `DELAYED_RETRY` | Recommend a retry after a delay |
| `SEND_PAYMENT_REMINDER` | Send the customer a payment reminder |
| `SUGGEST_ALTERNATIVE_METHOD` | Suggest an alternative payment method |
| `ESCALATE_MANUAL_REVIEW` | Escalate to human review |
| `NO_ACTION` | No automated recovery action is recommended |

## 10. Example Decisions

### Example 1: High probability, temporary failure
```json
{
  "recovery_probability": 0.82,
  "risk_tier": "HIGH",
  "recommended_action": "RETRY_PAYMENT",
  "expected_recovery_value": 1230.0,
  "reason": "Recovery probability is 82% (HIGH tier). Expected recovery value is ₹1,230.00. The failure appears temporary (e.g. timeout or network error), which may resolve on retry. An automated retry is recommended.",
  "model_version": "recovery-model-v1"
}
```

### Example 2: Medium probability, insufficient funds
```json
{
  "recovery_probability": 0.55,
  "risk_tier": "MEDIUM",
  "recommended_action": "SEND_PAYMENT_REMINDER",
  "expected_recovery_value": 2750.0,
  "reason": "Recovery probability is 55% (MEDIUM tier). Expected recovery value is ₹2,750.00. The failure context suggests customer action may be required (e.g. insufficient funds or limit exceeded); a payment reminder is more appropriate than an automated retry. Sending a payment reminder is recommended.",
  "model_version": "recovery-model-v1"
}
```

### Example 3: High probability, fraud check
```json
{
  "recovery_probability": 0.90,
  "risk_tier": "HIGH",
  "recommended_action": "ESCALATE_MANUAL_REVIEW",
  "expected_recovery_value": 9000.0,
  "reason": "Recovery probability is 90% (HIGH tier). Expected recovery value is ₹9,000.00. The failure is flagged as a fraud check; manual review is required regardless of recovery probability. Escalation to manual review is recommended.",
  "model_version": "recovery-model-v1"
}
```

### Example 4: High probability, retry limit reached
```json
{
  "recovery_probability": 0.85,
  "risk_tier": "HIGH",
  "recommended_action": "ESCALATE_MANUAL_REVIEW",
  "expected_recovery_value": 4250.0,
  "reason": "Recovery probability is 85% (HIGH tier). Expected recovery value is ₹4,250.00. Automated retry is suppressed because the retry safety limit (3) has been reached. The failure appears temporary (e.g. timeout or network error), which may resolve on retry. Escalation to manual review is recommended.",
  "model_version": "recovery-model-v1"
}
```

## 11. Limitations

1. **Synthetic data**: The underlying ML model was trained on synthetic
   data.  Predictions do not reflect real-world payment recovery rates.

2. **Baseline model**: The model (ROC-AUC ≈ 0.69) is a LogisticRegression
   baseline.  It is not optimized or production-validated.

3. **No causal claims**: The model identifies correlations, not
   causation.  The reason text uses careful language ("prediction is
   influenced by…") rather than causal statements.

4. **Static thresholds**: Risk tier thresholds are initial policy values,
   not data-driven cutoffs.

5. **No recovery outcome tracking**: Actions are recommended but not
   executed or tracked.  There is no feedback loop yet.

6. **No real-time signals**: The model uses feature snapshots, not
   live payment-health signals.

7. **Single-model system**: Only one model version is supported at a
   time.

## 12. Future Improvements

- **Recovery workflow orchestration** — Execute recommended actions
  (retry scheduling, reminder dispatch)
- **Outcome tracking** — Record whether recommended actions led to
  actual recovery
- **Feedback loop** — Use recovery outcomes to improve the model
- **A/B testing** — Experiment with different thresholds and actions
- **Dynamic thresholds** — Data-driven threshold optimization
- **Real-time payment health** — Incorporate live bank/method success
  rates
- **Model monitoring** — Track prediction distribution drift
- **Multi-model support** — Run multiple model versions simultaneously
- **Analytics dashboard** — Visualize recovery decisions and outcomes
