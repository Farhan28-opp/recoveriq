"""
Safety and retry policy for recovery execution (Day 5).
"""

import logging

from backend.models import RecoveryWorkflow
from backend.schemas.recovery import WorkflowStatus
from backend.services.decision_engine import MAX_AUTOMATED_RETRIES, RecoveryAction

logger = logging.getLogger(__name__)


def check_execution_safety(workflow: RecoveryWorkflow) -> tuple[bool, WorkflowStatus, str]:
    """
    Apply centralized safety policies before allowing an execution.
    
    Returns:
        (is_allowed, next_status, message)
        
        If is_allowed is False, next_status dictates the new terminal state 
        (e.g., BLOCKED or ESCALATED).
    """
    
    # 1. State Guard: terminal states cannot be re-executed
    if workflow.status in {
        WorkflowStatus.COMPLETED.value, 
        WorkflowStatus.FAILED.value, 
        WorkflowStatus.BLOCKED.value, 
        WorkflowStatus.ESCALATED.value
    }:
        return False, WorkflowStatus(workflow.status), f"Workflow is already in terminal state: {workflow.status}"
        
    # 2. In-Progress Guard
    if workflow.status == WorkflowStatus.EXECUTING.value:
        return False, WorkflowStatus.EXECUTING, "Workflow is currently executing."

    # 3. Fraud Guard (Extra layer of safety beyond DecisionEngine)
    if workflow.failure_code == "FRAUD_CHECK":
        return False, WorkflowStatus.ESCALATED, "Fraud checks must be escalated and cannot be auto-executed."

    # 4. Retry Limit Guard
    if workflow.attempt_count >= workflow.max_attempts:
        return False, WorkflowStatus.BLOCKED, f"Maximum automated retry limit ({workflow.max_attempts}) reached."
        
    # 5. Non-executable actions
    action = workflow.recommended_action
    if action == RecoveryAction.ESCALATE_MANUAL_REVIEW.value:
        return False, WorkflowStatus.ESCALATED, "Action requires manual review."
    
    if action == RecoveryAction.NO_ACTION.value:
        return False, WorkflowStatus.BLOCKED, "No action recommended for this recovery."

    # Passes all safety checks
    return True, WorkflowStatus.EXECUTING, "Safety checks passed."
