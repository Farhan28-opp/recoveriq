"""
Pydantic request and response schemas for the RecoverIQ orchestration API (Day 5).
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# Use existing enum states
class WorkflowStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"


class RecoveryWorkflowResponse(BaseModel):
    """Current state of a recovery workflow."""
    recovery_id: str = Field(..., description="Unique UUID for this workflow.")
    
    # Context
    failure_code: str = Field(..., description="The failure code that triggered this.")
    amount: float = Field(..., description="The original transaction amount in INR.")
    
    # Decision
    recovery_probability: float = Field(..., description="Probability of recovery.")
    risk_tier: str = Field(..., description="HIGH, MEDIUM, or LOW.")
    recommended_action: str = Field(..., description="The action recommended by the engine.")
    expected_recovery_value: float = Field(..., description="Probability * Amount.")
    reason: str = Field(..., description="Human-readable decision explanation.")
    model_version: str = Field(..., description="Model version used for prediction.")
    
    # State
    status: WorkflowStatus = Field(..., description="Current workflow state.")
    attempt_count: int = Field(..., description="Number of execution attempts.")
    max_attempts: int = Field(..., description="Maximum allowed automated attempts.")
    
    # Result
    execution_result: Optional[dict[str, Any]] = Field(None, description="Last execution result if any.")
    
    # Timestamps
    created_at: datetime = Field(..., description="Workflow creation time.")
    updated_at: datetime = Field(..., description="Workflow last update time.")


class ExecutionResponse(BaseModel):
    """Result of an execution request."""
    recovery_id: str = Field(..., description="Workflow ID.")
    status: WorkflowStatus = Field(..., description="New status after execution attempt.")
    success: bool = Field(..., description="Whether the simulated execution succeeded.")
    message: str = Field(..., description="Outcome message or safety reason.")
    simulated: bool = Field(True, description="Always true for Day 5 prototype.")
    executed_at: datetime = Field(default_factory=datetime.utcnow, description="Time of execution.")


class RecoveryStats(BaseModel):
    """Aggregate dashboard metrics."""
    total_cases: int
    total_amount_at_risk: float
    total_expected_recovery: float
    average_recovery_probability: float
    pending_count: int
    executing_count: int
    completed_count: int
    failed_count: int
    blocked_count: int
    escalated_count: int
