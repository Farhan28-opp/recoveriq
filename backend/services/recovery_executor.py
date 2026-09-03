"""
Simulated execution layer for recovery actions (Day 5).
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from backend.models import RecoveryWorkflow

logger = logging.getLogger(__name__)


class RecoveryExecutor(ABC):
    """Abstract interface for executing recovery actions."""
    
    @abstractmethod
    def execute(self, workflow: RecoveryWorkflow) -> dict[str, Any]:
        """Execute the recommended action and return a structured result."""
        pass


class SimulatedRecoveryExecutor(RecoveryExecutor):
    """
    A simulated executor for the prototype.
    
    Does NOT actually charge money, send real SMS, or make external API calls.
    Returns deterministic, structured results to progress the workflow state.
    """
    
    def __init__(self, forced_success: bool | None = None):
        """
        Args:
            forced_success: If set, forces the outcome (useful for testing).
                            If None, defaults to success.
        """
        self.forced_success = forced_success

    def execute(self, workflow: RecoveryWorkflow) -> dict[str, Any]:
        """Simulate the execution of the workflow's recommended action."""
        
        logger.info(f"Simulating execution of {workflow.recommended_action} for {workflow.recovery_id}")
        
        # Determine success outcome
        success = True if self.forced_success is None else self.forced_success
        
        # Generate simulation details based on the action
        action = workflow.recommended_action
        
        if success:
            status = "SUCCESS"
            message = f"Simulated success for {action}."
        else:
            status = "FAILURE"
            message = f"Simulated failure for {action}."
            
        return {
            "action": action,
            "success": success,
            "status": status,
            "message": message,
            "simulated": True,
            "executed_at": datetime.utcnow().isoformat()
        }
