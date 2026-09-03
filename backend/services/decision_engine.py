"""
Recovery Decision Engine for RecoverIQ.

Pure business-logic component that converts a recovery probability and
payment context into a structured recovery decision.  This module has
no dependency on FastAPI, the ML model, or the database — it receives
a probability (from RecoveryPredictor) and contextual fields, and
returns a deterministic RecoveryDecision.

Architecture:
    RecoveryPredictor → probability
                            ↓
                    DecisionEngine.decide()
                            ↓
                    RecoveryDecision (tier + action + reason)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ====================================================================
# CENTRALIZED POLICY CONSTANTS
# ====================================================================

# Risk tier probability thresholds.
# These are initial business-policy thresholds, not mathematically
# optimized cutoffs.  They should be reviewed as the model improves.
HIGH_TIER_THRESHOLD: float = 0.70
MEDIUM_TIER_THRESHOLD: float = 0.40

# Maximum number of automated retries allowed before the system stops
# recommending retry-type actions.  This is a hard safety constraint
# that cannot be bypassed by a high probability.
MAX_AUTOMATED_RETRIES: int = 3


# ====================================================================
# ENUMS
# ====================================================================

class RiskTier(str, Enum):
    """Recovery opportunity classification."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RecoveryAction(str, Enum):
    """Recommended next recovery action."""
    RETRY_PAYMENT = "RETRY_PAYMENT"
    DELAYED_RETRY = "DELAYED_RETRY"
    SEND_PAYMENT_REMINDER = "SEND_PAYMENT_REMINDER"
    SUGGEST_ALTERNATIVE_METHOD = "SUGGEST_ALTERNATIVE_METHOD"
    ESCALATE_MANUAL_REVIEW = "ESCALATE_MANUAL_REVIEW"
    NO_ACTION = "NO_ACTION"


# ====================================================================
# FAILURE CODE CLASSIFICATION
# ====================================================================

# Temporary/transient failures — an automated retry may resolve them.
_TEMPORARY_FAILURES = frozenset({
    "TIMEOUT",
    "NETWORK_ERROR",
    "TECHNICAL_ERROR",
})

# Fund/limit-related failures — retry is unlikely to help; a payment
# reminder giving the customer time to arrange funds is more appropriate.
_FUND_FAILURES = frozenset({
    "INSUFFICIENT_FUNDS",
    "LIMIT_EXCEEDED",
})

# Fraud/authentication failures — always escalate to manual review.
_FRAUD_FAILURES = frozenset({
    "FRAUD_CHECK",
})

# Method-unavailable failures — suggest an alternative payment method.
_METHOD_FAILURES = frozenset({
    "METHOD_UNAVAILABLE",
})

# Bank-declined — context-dependent; may suggest alternative method or
# escalation depending on probability tier.
_BANK_FAILURES = frozenset({
    "BANK_DECLINED",
})


# ====================================================================
# DECISION OUTPUT
# ====================================================================

@dataclass(frozen=True)
class RecoveryDecision:
    """Immutable structured recovery decision."""
    recovery_probability: float
    risk_tier: RiskTier
    recommended_action: RecoveryAction
    expected_recovery_value: float
    reason: str
    model_version: str


# ====================================================================
# DECISION ENGINE
# ====================================================================

class DecisionEngine:
    """Deterministic recovery decision engine.

    Applies the following decision hierarchy:

        1. Validate inputs
        2. Classify risk tier from probability
        3. Calculate expected recovery value
        4. Apply safety constraints (retry limit)
        5. Consider failure-code context
        6. Select action based on tier + context
        7. Generate human-readable explanation

    Safety constraints (e.g. retry limit) take priority over
    probability.  A high probability does NOT override the retry
    safety limit.
    """

    def __init__(
        self,
        high_threshold: float = HIGH_TIER_THRESHOLD,
        medium_threshold: float = MEDIUM_TIER_THRESHOLD,
        max_retries: int = MAX_AUTOMATED_RETRIES,
    ) -> None:
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold
        self.max_retries = max_retries

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def decide(
        self,
        recovery_probability: float,
        amount: float,
        failure_code: str,
        retry_count: int,
        model_version: str = "unknown",
    ) -> RecoveryDecision:
        """Produce a recovery decision from probability and context.

        Parameters
        ----------
        recovery_probability : float
            P(recovered=True) from RecoveryPredictor, in [0.0, 1.0].
        amount : float
            Transaction amount (used for expected recovery value).
        failure_code : str
            The payment failure code (e.g. "TIMEOUT", "FRAUD_CHECK").
        retry_count : int
            Number of retries already attempted for this payment.
        model_version : str
            Model version string for traceability.

        Returns
        -------
        RecoveryDecision
            Immutable decision containing tier, action, reason, and
            expected recovery value.

        Raises
        ------
        ValueError
            If recovery_probability is outside [0, 1] or amount < 0.
        """
        # 1. Validate
        self._validate_inputs(recovery_probability, amount, retry_count)

        # 2. Classify tier
        tier = self._classify_tier(recovery_probability)

        # 3. Expected recovery value
        expected_value = round(recovery_probability * amount, 2)

        # 4–6. Select action (safety + failure context + tier)
        retry_exhausted = retry_count >= self.max_retries
        action = self._select_action(tier, failure_code, retry_exhausted)

        # 7. Generate reason
        reason = self._generate_reason(
            tier, action, failure_code, retry_exhausted,
            recovery_probability, expected_value,
        )

        return RecoveryDecision(
            recovery_probability=recovery_probability,
            risk_tier=tier,
            recommended_action=action,
            expected_recovery_value=expected_value,
            reason=reason,
            model_version=model_version,
        )

    # ----------------------------------------------------------------
    # Tier classification
    # ----------------------------------------------------------------

    def _classify_tier(self, probability: float) -> RiskTier:
        """Map probability to risk tier."""
        if probability >= self.high_threshold:
            return RiskTier.HIGH
        elif probability >= self.medium_threshold:
            return RiskTier.MEDIUM
        else:
            return RiskTier.LOW

    # ----------------------------------------------------------------
    # Action selection — decision hierarchy
    # ----------------------------------------------------------------

    def _select_action(
        self,
        tier: RiskTier,
        failure_code: str,
        retry_exhausted: bool,
    ) -> RecoveryAction:
        """Select the recommended action.

        Priority order:
            1. Fraud → always escalate
            2. Retry safety limit → suppress retries
            3. Failure-code context → adjust action
            4. Probability tier → default action
        """
        # --- Priority 1: Fraud always escalates ---
        if failure_code in _FRAUD_FAILURES:
            return RecoveryAction.ESCALATE_MANUAL_REVIEW

        # --- Priority 2: Retry safety ---
        # If retries are exhausted, never recommend retry-type actions.
        if retry_exhausted:
            return self._select_non_retry_action(tier, failure_code)

        # --- Priority 3 & 4: Failure context + tier ---
        if failure_code in _TEMPORARY_FAILURES:
            return self._action_for_temporary_failure(tier)

        if failure_code in _FUND_FAILURES:
            return self._action_for_fund_failure(tier)

        if failure_code in _METHOD_FAILURES:
            return self._action_for_method_failure(tier)

        if failure_code in _BANK_FAILURES:
            return self._action_for_bank_failure(tier)

        # Unknown or unclassified failure codes — fall back to tier.
        return self._default_action_for_tier(tier)

    def _select_non_retry_action(
        self, tier: RiskTier, failure_code: str,
    ) -> RecoveryAction:
        """Select an action when retry limit has been reached."""
        if failure_code in _METHOD_FAILURES:
            return RecoveryAction.SUGGEST_ALTERNATIVE_METHOD
        if tier == RiskTier.LOW:
            return RecoveryAction.NO_ACTION
        if tier == RiskTier.MEDIUM:
            return RecoveryAction.SEND_PAYMENT_REMINDER
        # HIGH tier but retries exhausted
        return RecoveryAction.ESCALATE_MANUAL_REVIEW

    def _action_for_temporary_failure(self, tier: RiskTier) -> RecoveryAction:
        """Temporary failures are good candidates for retry."""
        if tier == RiskTier.HIGH:
            return RecoveryAction.RETRY_PAYMENT
        elif tier == RiskTier.MEDIUM:
            return RecoveryAction.DELAYED_RETRY
        else:
            return RecoveryAction.NO_ACTION

    def _action_for_fund_failure(self, tier: RiskTier) -> RecoveryAction:
        """Fund/limit failures — retry is unlikely to help."""
        if tier == RiskTier.HIGH:
            return RecoveryAction.SEND_PAYMENT_REMINDER
        elif tier == RiskTier.MEDIUM:
            return RecoveryAction.SEND_PAYMENT_REMINDER
        else:
            return RecoveryAction.NO_ACTION

    def _action_for_method_failure(self, tier: RiskTier) -> RecoveryAction:
        """Method-unavailable — suggest an alternative."""
        if tier == RiskTier.LOW:
            return RecoveryAction.NO_ACTION
        return RecoveryAction.SUGGEST_ALTERNATIVE_METHOD

    def _action_for_bank_failure(self, tier: RiskTier) -> RecoveryAction:
        """Bank-declined — depends on tier."""
        if tier == RiskTier.HIGH:
            return RecoveryAction.DELAYED_RETRY
        elif tier == RiskTier.MEDIUM:
            return RecoveryAction.SUGGEST_ALTERNATIVE_METHOD
        else:
            return RecoveryAction.ESCALATE_MANUAL_REVIEW

    def _default_action_for_tier(self, tier: RiskTier) -> RecoveryAction:
        """Fallback when failure code is unknown or unclassified."""
        if tier == RiskTier.HIGH:
            return RecoveryAction.RETRY_PAYMENT
        elif tier == RiskTier.MEDIUM:
            return RecoveryAction.SEND_PAYMENT_REMINDER
        else:
            return RecoveryAction.NO_ACTION

    # ----------------------------------------------------------------
    # Reason generation
    # ----------------------------------------------------------------

    def _generate_reason(
        self,
        tier: RiskTier,
        action: RecoveryAction,
        failure_code: str,
        retry_exhausted: bool,
        probability: float,
        expected_value: float,
    ) -> str:
        """Generate a human-readable explanation for the decision."""
        parts: list[str] = []

        # Probability context
        prob_pct = f"{probability:.0%}"
        parts.append(
            f"Recovery probability is {prob_pct} ({tier.value} tier)."
        )

        # Expected value context
        parts.append(
            f"Expected recovery value is ₹{expected_value:,.2f}."
        )

        # Safety constraint
        if retry_exhausted:
            parts.append(
                f"Automated retry is suppressed because the retry safety "
                f"limit ({self.max_retries}) has been reached."
            )

        # Failure context
        if failure_code in _FRAUD_FAILURES:
            parts.append(
                "The failure is flagged as a fraud check; manual review "
                "is required regardless of recovery probability."
            )
        elif failure_code in _TEMPORARY_FAILURES:
            parts.append(
                "The failure appears temporary (e.g. timeout or network "
                "error), which may resolve on retry."
            )
        elif failure_code in _FUND_FAILURES:
            parts.append(
                "The failure context suggests customer action may be "
                "required (e.g. insufficient funds or limit exceeded); "
                "a payment reminder is more appropriate than an "
                "automated retry."
            )
        elif failure_code in _METHOD_FAILURES:
            parts.append(
                "The selected payment method was unavailable; suggesting "
                "an alternative method may help."
            )
        elif failure_code in _BANK_FAILURES:
            parts.append(
                "The issuing bank declined the transaction; the "
                "recommended action accounts for this context."
            )

        # Action summary
        action_descriptions = {
            RecoveryAction.RETRY_PAYMENT: "An automated retry is recommended.",
            RecoveryAction.DELAYED_RETRY: "A delayed retry is recommended.",
            RecoveryAction.SEND_PAYMENT_REMINDER: "Sending a payment reminder is recommended.",
            RecoveryAction.SUGGEST_ALTERNATIVE_METHOD: "Suggesting an alternative payment method is recommended.",
            RecoveryAction.ESCALATE_MANUAL_REVIEW: "Escalation to manual review is recommended.",
            RecoveryAction.NO_ACTION: "No automated recovery action is recommended at this time.",
        }
        parts.append(action_descriptions.get(action, ""))

        return " ".join(parts)

    # ----------------------------------------------------------------
    # Validation
    # ----------------------------------------------------------------

    @staticmethod
    def _validate_inputs(
        probability: float, amount: float, retry_count: int,
    ) -> None:
        """Validate decision engine inputs."""
        if not (0.0 <= probability <= 1.0):
            raise ValueError(
                f"recovery_probability must be between 0 and 1, "
                f"got {probability}"
            )
        if amount < 0:
            raise ValueError(
                f"amount must be non-negative, got {amount}"
            )
        if retry_count < 0:
            raise ValueError(
                f"retry_count must be non-negative, got {retry_count}"
            )
