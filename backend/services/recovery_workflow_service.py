"""
Recovery Workflow Orchestration Service (Day 5).
"""

import json
import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from backend.models import RecoveryWorkflow
from backend.schemas.prediction import PredictionRequest
from backend.schemas.recovery import ExecutionResponse, RecoveryWorkflowResponse, WorkflowStatus
from backend.services.decision_engine import DecisionEngine, MAX_AUTOMATED_RETRIES
from backend.services.recovery_executor import RecoveryExecutor, SimulatedRecoveryExecutor
from backend.services.recovery_policy import check_execution_safety

logger = logging.getLogger(__name__)


class RecoveryWorkflowService:
    """Service to manage the lifecycle of Recovery Workflows."""

    def __init__(self, db: Session, executor: Optional[RecoveryExecutor] = None):
        self.db = db
        # Injectable executor (defaults to Simulated for Day 5)
        self.executor = executor or SimulatedRecoveryExecutor()

    def create_workflow(
        self, request: PredictionRequest, probability: float, decision: "RecoveryDecision",
        import_batch_id: Optional[str] = None, transaction_id: Optional[str] = None
    ) -> RecoveryWorkflowResponse:
        """Create a new recovery workflow from a prediction decision."""
        
        workflow_id = str(uuid.uuid4())
        
        workflow = RecoveryWorkflow(
            recovery_id=workflow_id,
            failure_code=request.failure_code,
            amount=request.amount,
            recovery_probability=probability,
            risk_tier=decision.risk_tier.value,
            recommended_action=decision.recommended_action.value,
            expected_recovery_value=decision.expected_recovery_value,
            reason=decision.reason,
            model_version=decision.model_version,
            status=WorkflowStatus.PENDING.value,
            attempt_count=0,
            max_attempts=MAX_AUTOMATED_RETRIES,
            import_batch_id=import_batch_id,
            transaction_id=transaction_id,
        )
        
        self.db.add(workflow)
        self.db.commit()
        self.db.refresh(workflow)
        
        return self._to_response(workflow)

    def get_workflow(self, recovery_id: str) -> Optional[RecoveryWorkflowResponse]:
        """Retrieve a workflow by ID."""
        workflow = self._get_model(recovery_id)
        if not workflow:
            return None
        return self._to_response(workflow)

    def execute_workflow(self, recovery_id: str) -> ExecutionResponse:
        """Attempt to execute the recommended action for a workflow."""
        workflow = self._get_model(recovery_id)
        if not workflow:
            raise ValueError("Workflow not found.")

        # 1. Idempotency Check
        if workflow.status == WorkflowStatus.COMPLETED.value:
            # Already completed, just return the existing success result
            result = json.loads(workflow.execution_result or "{}")
            return ExecutionResponse(
                recovery_id=workflow.recovery_id,
                status=WorkflowStatus.COMPLETED,
                success=result.get("success", True),
                message=result.get("message", "Already completed."),
                simulated=result.get("simulated", True),
            )

        # 2. Safety Policy Check
        is_allowed, next_status, message = check_execution_safety(workflow)
        
        if not is_allowed:
            # Transition to terminal failure/blocked state
            workflow.status = next_status.value
            workflow.execution_result = json.dumps({"message": message})
            self.db.commit()
            return ExecutionResponse(
                recovery_id=workflow.recovery_id,
                status=next_status,
                success=False,
                message=message,
                simulated=True,
            )

        # 3. Transition to EXECUTING
        workflow.status = WorkflowStatus.EXECUTING.value
        self.db.commit()

        # 4. Execute (Simulated)
        workflow.attempt_count += 1
        result_dict = self.executor.execute(workflow)
        
        # 5. Transition to final state based on result
        success = result_dict.get("success", False)
        if success:
            workflow.status = WorkflowStatus.COMPLETED.value
        else:
            workflow.status = WorkflowStatus.FAILED.value
            
        workflow.execution_result = json.dumps(result_dict)
        self.db.commit()
        
        return ExecutionResponse(
            recovery_id=workflow.recovery_id,
            status=WorkflowStatus(workflow.status),
            success=success,
            message=result_dict.get("message", "Execution complete"),
            simulated=result_dict.get("simulated", True),
        )

    # --- Helpers ---
    
    def list_workflows(self) -> list[RecoveryWorkflowResponse]:
        """List all workflows ordered by creation date descending."""
        workflows = self.db.query(RecoveryWorkflow).order_by(RecoveryWorkflow.created_at.desc()).all()
        return [self._to_response(wf) for wf in workflows]

    def get_stats(self) -> "RecoveryStats":
        """Calculate aggregate statistics across all workflows."""
        from backend.schemas.recovery import RecoveryStats
        workflows = self.db.query(RecoveryWorkflow).all()
        
        total_cases = len(workflows)
        total_amount_at_risk = sum(wf.amount for wf in workflows)
        total_expected_recovery = sum(wf.expected_recovery_value for wf in workflows)
        avg_prob = sum(wf.recovery_probability for wf in workflows) / total_cases if total_cases > 0 else 0.0
        
        counts = {s.value: 0 for s in WorkflowStatus}
        for wf in workflows:
            if wf.status in counts:
                counts[wf.status] += 1
                
        return RecoveryStats(
            total_cases=total_cases,
            total_amount_at_risk=total_amount_at_risk,
            total_expected_recovery=total_expected_recovery,
            average_recovery_probability=avg_prob,
            pending_count=counts[WorkflowStatus.PENDING.value],
            executing_count=counts[WorkflowStatus.EXECUTING.value],
            completed_count=counts[WorkflowStatus.COMPLETED.value],
            failed_count=counts[WorkflowStatus.FAILED.value],
            blocked_count=counts[WorkflowStatus.BLOCKED.value],
            escalated_count=counts[WorkflowStatus.ESCALATED.value],
        )

    def _get_model(self, recovery_id: str) -> Optional[RecoveryWorkflow]:
        return self.db.query(RecoveryWorkflow).filter(RecoveryWorkflow.recovery_id == recovery_id).first()

    def _to_response(self, workflow: RecoveryWorkflow) -> RecoveryWorkflowResponse:
        result = None
        if workflow.execution_result:
            try:
                result = json.loads(workflow.execution_result)
            except json.JSONDecodeError:
                result = {"raw": workflow.execution_result}
                
        return RecoveryWorkflowResponse(
            recovery_id=workflow.recovery_id,
            failure_code=workflow.failure_code,
            amount=workflow.amount,
            recovery_probability=workflow.recovery_probability,
            risk_tier=workflow.risk_tier,
            recommended_action=workflow.recommended_action,
            expected_recovery_value=workflow.expected_recovery_value,
            reason=workflow.reason,
            model_version=workflow.model_version,
            status=WorkflowStatus(workflow.status),
            attempt_count=workflow.attempt_count,
            max_attempts=workflow.max_attempts,
            execution_result=result,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
        )
