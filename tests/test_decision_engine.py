"""
Tests for the RecoverIQ Decision Engine (Day 4).

These tests exercise the pure business-logic DecisionEngine class
independently of FastAPI, the ML model, and the database.

Run with:
    pytest tests/test_decision_engine.py -v
"""

import pytest

from backend.services.decision_engine import (
    HIGH_TIER_THRESHOLD,
    MAX_AUTOMATED_RETRIES,
    MEDIUM_TIER_THRESHOLD,
    DecisionEngine,
    RecoveryAction,
    RecoveryDecision,
    RiskTier,
)


@pytest.fixture
def engine():
    """Default decision engine with standard thresholds."""
    return DecisionEngine()


# ====================================================================
# 1. TIER CLASSIFICATION
# ====================================================================

class TestTierClassification:
    """Verify probability → tier mapping at boundaries."""

    @pytest.mark.parametrize("probability,expected_tier", [
        (0.00, RiskTier.LOW),
        (0.10, RiskTier.LOW),
        (0.39, RiskTier.LOW),
        (0.40, RiskTier.MEDIUM),
        (0.50, RiskTier.MEDIUM),
        (0.69, RiskTier.MEDIUM),
        (0.70, RiskTier.HIGH),
        (0.85, RiskTier.HIGH),
        (0.95, RiskTier.HIGH),
        (1.00, RiskTier.HIGH),
    ])
    def test_tier_boundaries(self, engine, probability, expected_tier):
        decision = engine.decide(
            recovery_probability=probability,
            amount=1000.0,
            failure_code="TIMEOUT",
            retry_count=0,
            model_version="test-v1",
        )
        assert decision.risk_tier == expected_tier

    def test_thresholds_match_constants(self):
        """Verify the engine uses the centralized constants."""
        assert HIGH_TIER_THRESHOLD == 0.70
        assert MEDIUM_TIER_THRESHOLD == 0.40


# ====================================================================
# 2. EXPECTED RECOVERY VALUE
# ====================================================================

class TestExpectedRecoveryValue:
    """Verify expected_recovery_value = probability × amount."""

    @pytest.mark.parametrize("probability,amount,expected_value", [
        (0.80, 5000.0, 4000.0),
        (0.55, 10000.0, 5500.0),
        (0.00, 1000.0, 0.0),
        (1.00, 1000.0, 1000.0),
        (0.33, 3000.0, 990.0),
    ])
    def test_expected_recovery_value(
        self, engine, probability, amount, expected_value,
    ):
        decision = engine.decide(
            recovery_probability=probability,
            amount=amount,
            failure_code="TIMEOUT",
            retry_count=0,
        )
        assert decision.expected_recovery_value == expected_value


# ====================================================================
# 3. FAILURE-CODE SPECIFIC ACTIONS
# ====================================================================

class TestFailureCodeActions:
    """Verify failure-code-aware action selection."""

    def test_fraud_always_escalates(self, engine):
        """FRAUD_CHECK → ESCALATE_MANUAL_REVIEW regardless of tier."""
        for prob in [0.10, 0.50, 0.95]:
            decision = engine.decide(
                recovery_probability=prob,
                amount=1000.0,
                failure_code="FRAUD_CHECK",
                retry_count=0,
            )
            assert decision.recommended_action == RecoveryAction.ESCALATE_MANUAL_REVIEW

    def test_temporary_failure_high_tier_retries(self, engine):
        """Temporary failure + HIGH tier → RETRY_PAYMENT."""
        for code in ["TIMEOUT", "NETWORK_ERROR", "TECHNICAL_ERROR"]:
            decision = engine.decide(
                recovery_probability=0.80,
                amount=1000.0,
                failure_code=code,
                retry_count=0,
            )
            assert decision.recommended_action == RecoveryAction.RETRY_PAYMENT

    def test_temporary_failure_medium_tier_delayed_retry(self, engine):
        """Temporary failure + MEDIUM tier → DELAYED_RETRY."""
        decision = engine.decide(
            recovery_probability=0.50,
            amount=1000.0,
            failure_code="TIMEOUT",
            retry_count=0,
        )
        assert decision.recommended_action == RecoveryAction.DELAYED_RETRY

    def test_temporary_failure_low_tier_no_action(self, engine):
        """Temporary failure + LOW tier → NO_ACTION."""
        decision = engine.decide(
            recovery_probability=0.10,
            amount=1000.0,
            failure_code="TIMEOUT",
            retry_count=0,
        )
        assert decision.recommended_action == RecoveryAction.NO_ACTION

    def test_insufficient_funds_sends_reminder(self, engine):
        """INSUFFICIENT_FUNDS → SEND_PAYMENT_REMINDER (HIGH/MEDIUM)."""
        for prob in [0.50, 0.80]:
            decision = engine.decide(
                recovery_probability=prob,
                amount=1000.0,
                failure_code="INSUFFICIENT_FUNDS",
                retry_count=0,
            )
            assert decision.recommended_action == RecoveryAction.SEND_PAYMENT_REMINDER

    def test_limit_exceeded_sends_reminder(self, engine):
        """LIMIT_EXCEEDED → SEND_PAYMENT_REMINDER (HIGH/MEDIUM)."""
        decision = engine.decide(
            recovery_probability=0.80,
            amount=1000.0,
            failure_code="LIMIT_EXCEEDED",
            retry_count=0,
        )
        assert decision.recommended_action == RecoveryAction.SEND_PAYMENT_REMINDER

    def test_method_unavailable_suggests_alternative(self, engine):
        """METHOD_UNAVAILABLE → SUGGEST_ALTERNATIVE_METHOD (non-LOW)."""
        decision = engine.decide(
            recovery_probability=0.50,
            amount=1000.0,
            failure_code="METHOD_UNAVAILABLE",
            retry_count=0,
        )
        assert decision.recommended_action == RecoveryAction.SUGGEST_ALTERNATIVE_METHOD

    def test_bank_declined_high_delayed_retry(self, engine):
        """BANK_DECLINED + HIGH → DELAYED_RETRY."""
        decision = engine.decide(
            recovery_probability=0.80,
            amount=1000.0,
            failure_code="BANK_DECLINED",
            retry_count=0,
        )
        assert decision.recommended_action == RecoveryAction.DELAYED_RETRY

    def test_bank_declined_medium_suggest_alternative(self, engine):
        """BANK_DECLINED + MEDIUM → SUGGEST_ALTERNATIVE_METHOD."""
        decision = engine.decide(
            recovery_probability=0.50,
            amount=1000.0,
            failure_code="BANK_DECLINED",
            retry_count=0,
        )
        assert decision.recommended_action == RecoveryAction.SUGGEST_ALTERNATIVE_METHOD

    def test_bank_declined_low_escalates(self, engine):
        """BANK_DECLINED + LOW → ESCALATE_MANUAL_REVIEW."""
        decision = engine.decide(
            recovery_probability=0.10,
            amount=1000.0,
            failure_code="BANK_DECLINED",
            retry_count=0,
        )
        assert decision.recommended_action == RecoveryAction.ESCALATE_MANUAL_REVIEW

    def test_unknown_failure_code_uses_default(self, engine):
        """UNKNOWN failure code → default tier-based action."""
        decision = engine.decide(
            recovery_probability=0.80,
            amount=1000.0,
            failure_code="UNKNOWN",
            retry_count=0,
        )
        assert decision.recommended_action == RecoveryAction.RETRY_PAYMENT


# ====================================================================
# 4. RETRY SAFETY
# ====================================================================

class TestRetrySafety:
    """Verify the retry safety limit cannot be bypassed."""

    def test_retry_limit_suppresses_retry_high_prob(self, engine):
        """Even with HIGH probability, retry is suppressed at the limit."""
        decision = engine.decide(
            recovery_probability=0.95,
            amount=10000.0,
            failure_code="TIMEOUT",
            retry_count=MAX_AUTOMATED_RETRIES,
        )
        assert decision.recommended_action != RecoveryAction.RETRY_PAYMENT
        assert decision.recommended_action != RecoveryAction.DELAYED_RETRY

    def test_retry_limit_exact_boundary(self, engine):
        """retry_count == MAX_AUTOMATED_RETRIES → no retry."""
        decision = engine.decide(
            recovery_probability=0.80,
            amount=1000.0,
            failure_code="TIMEOUT",
            retry_count=3,
        )
        assert decision.recommended_action not in {
            RecoveryAction.RETRY_PAYMENT,
            RecoveryAction.DELAYED_RETRY,
        }

    def test_retry_below_limit_allows_retry(self, engine):
        """retry_count < MAX_AUTOMATED_RETRIES → retry allowed."""
        decision = engine.decide(
            recovery_probability=0.80,
            amount=1000.0,
            failure_code="TIMEOUT",
            retry_count=2,
        )
        assert decision.recommended_action == RecoveryAction.RETRY_PAYMENT

    def test_retry_exhausted_method_failure_suggests_alternative(self, engine):
        """Retries exhausted + METHOD_UNAVAILABLE → SUGGEST_ALTERNATIVE."""
        decision = engine.decide(
            recovery_probability=0.80,
            amount=1000.0,
            failure_code="METHOD_UNAVAILABLE",
            retry_count=MAX_AUTOMATED_RETRIES,
        )
        assert decision.recommended_action == RecoveryAction.SUGGEST_ALTERNATIVE_METHOD

    def test_retry_exhausted_low_tier_no_action(self, engine):
        """Retries exhausted + LOW tier → NO_ACTION."""
        decision = engine.decide(
            recovery_probability=0.10,
            amount=1000.0,
            failure_code="TIMEOUT",
            retry_count=MAX_AUTOMATED_RETRIES,
        )
        assert decision.recommended_action == RecoveryAction.NO_ACTION

    def test_retry_exhausted_reason_mentions_limit(self, engine):
        """Reason should mention retry limit when exhausted."""
        decision = engine.decide(
            recovery_probability=0.80,
            amount=1000.0,
            failure_code="TIMEOUT",
            retry_count=MAX_AUTOMATED_RETRIES,
        )
        assert "retry safety limit" in decision.reason.lower()

    def test_max_retries_constant(self):
        """Verify the centralized constant value."""
        assert MAX_AUTOMATED_RETRIES == 3


# ====================================================================
# 5. DETERMINISM
# ====================================================================

class TestDeterminism:
    """Same input must always produce the same output."""

    def test_deterministic_decision(self, engine):
        """Two identical calls produce identical decisions."""
        kwargs = dict(
            recovery_probability=0.65,
            amount=2500.0,
            failure_code="NETWORK_ERROR",
            retry_count=1,
            model_version="test-v1",
        )
        d1 = engine.decide(**kwargs)
        d2 = engine.decide(**kwargs)
        assert d1 == d2


# ====================================================================
# 6. REASON GENERATION
# ====================================================================

class TestReasonGeneration:
    """Verify every decision includes a non-empty reason."""

    def test_reason_is_nonempty(self, engine):
        decision = engine.decide(
            recovery_probability=0.50,
            amount=1000.0,
            failure_code="TIMEOUT",
            retry_count=0,
        )
        assert isinstance(decision.reason, str)
        assert len(decision.reason) > 0

    def test_reason_mentions_tier(self, engine):
        decision = engine.decide(
            recovery_probability=0.80,
            amount=1000.0,
            failure_code="TIMEOUT",
            retry_count=0,
        )
        assert "HIGH" in decision.reason

    def test_reason_mentions_expected_value(self, engine):
        decision = engine.decide(
            recovery_probability=0.80,
            amount=1000.0,
            failure_code="TIMEOUT",
            retry_count=0,
        )
        assert "800.00" in decision.reason


# ====================================================================
# 7. INPUT VALIDATION
# ====================================================================

class TestInputValidation:
    """Verify invalid inputs are rejected."""

    def test_probability_below_zero(self, engine):
        with pytest.raises(ValueError, match="between 0 and 1"):
            engine.decide(
                recovery_probability=-0.1,
                amount=1000.0,
                failure_code="TIMEOUT",
                retry_count=0,
            )

    def test_probability_above_one(self, engine):
        with pytest.raises(ValueError, match="between 0 and 1"):
            engine.decide(
                recovery_probability=1.1,
                amount=1000.0,
                failure_code="TIMEOUT",
                retry_count=0,
            )

    def test_negative_amount(self, engine):
        with pytest.raises(ValueError, match="non-negative"):
            engine.decide(
                recovery_probability=0.50,
                amount=-100.0,
                failure_code="TIMEOUT",
                retry_count=0,
            )

    def test_negative_retry_count(self, engine):
        with pytest.raises(ValueError, match="non-negative"):
            engine.decide(
                recovery_probability=0.50,
                amount=1000.0,
                failure_code="TIMEOUT",
                retry_count=-1,
            )


# ====================================================================
# 8. DECISION OUTPUT STRUCTURE
# ====================================================================

class TestDecisionStructure:
    """Verify decision output is well-formed."""

    def test_decision_is_dataclass(self, engine):
        decision = engine.decide(
            recovery_probability=0.50,
            amount=1000.0,
            failure_code="TIMEOUT",
            retry_count=0,
            model_version="test-v1",
        )
        assert isinstance(decision, RecoveryDecision)

    def test_decision_has_all_fields(self, engine):
        decision = engine.decide(
            recovery_probability=0.50,
            amount=1000.0,
            failure_code="TIMEOUT",
            retry_count=0,
            model_version="test-v1",
        )
        assert isinstance(decision.recovery_probability, float)
        assert isinstance(decision.risk_tier, RiskTier)
        assert isinstance(decision.recommended_action, RecoveryAction)
        assert isinstance(decision.expected_recovery_value, float)
        assert isinstance(decision.reason, str)
        assert isinstance(decision.model_version, str)

    def test_model_version_passthrough(self, engine):
        decision = engine.decide(
            recovery_probability=0.50,
            amount=1000.0,
            failure_code="TIMEOUT",
            retry_count=0,
            model_version="recovery-model-v1",
        )
        assert decision.model_version == "recovery-model-v1"

    def test_all_actions_are_valid_enum_values(self, engine):
        """Every possible action from the engine is a valid RecoveryAction."""
        test_cases = [
            (0.80, "TIMEOUT", 0),
            (0.50, "TIMEOUT", 0),
            (0.10, "TIMEOUT", 0),
            (0.80, "FRAUD_CHECK", 0),
            (0.80, "INSUFFICIENT_FUNDS", 0),
            (0.80, "METHOD_UNAVAILABLE", 0),
            (0.80, "BANK_DECLINED", 0),
            (0.80, "UNKNOWN", 0),
            (0.80, "TIMEOUT", MAX_AUTOMATED_RETRIES),
            (0.10, "TIMEOUT", MAX_AUTOMATED_RETRIES),
        ]
        for prob, code, retries in test_cases:
            decision = engine.decide(
                recovery_probability=prob,
                amount=1000.0,
                failure_code=code,
                retry_count=retries,
            )
            assert decision.recommended_action in RecoveryAction


# ====================================================================
# 9. CUSTOM THRESHOLDS
# ====================================================================

class TestCustomThresholds:
    """Verify the engine respects custom threshold configuration."""

    def test_custom_high_threshold(self):
        engine = DecisionEngine(high_threshold=0.90)
        decision = engine.decide(
            recovery_probability=0.85,
            amount=1000.0,
            failure_code="TIMEOUT",
            retry_count=0,
        )
        # 0.85 < 0.90 custom threshold → MEDIUM, not HIGH
        assert decision.risk_tier == RiskTier.MEDIUM

    def test_custom_max_retries(self):
        engine = DecisionEngine(max_retries=1)
        decision = engine.decide(
            recovery_probability=0.80,
            amount=1000.0,
            failure_code="TIMEOUT",
            retry_count=1,
        )
        # retry_count == max_retries(1) → no retry
        assert decision.recommended_action not in {
            RecoveryAction.RETRY_PAYMENT,
            RecoveryAction.DELAYED_RETRY,
        }
