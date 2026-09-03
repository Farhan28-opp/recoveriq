"""
Recovery API routes for RecoverIQ (Day 5).

Provides:
    POST /recovery              — Create a recovery workflow
    GET  /recovery/{id}         — Get workflow status
    POST /recovery/{id}/execute — Execute recommended action
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.routes.predict import _get_decision_engine, _get_predictor, transform_request_to_dataframe
from backend.schemas.prediction import ErrorResponse, PredictionRequest
from backend.schemas.recovery import ExecutionResponse, RecoveryStats, RecoveryWorkflowResponse
from backend.services.recovery_workflow_service import RecoveryWorkflowService

logger = logging.getLogger(__name__)

router = APIRouter()


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post(
    "/recovery",
    response_model=RecoveryWorkflowResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal error"},
    },
    summary="Create a recovery workflow",
)
def create_recovery(
    request: PredictionRequest, db: Session = Depends(get_db)
) -> RecoveryWorkflowResponse:
    """Create a new recovery workflow from a failed payment payload."""
    
    # 1. Run the Prediction & Decision pipeline (reuse Day 4 logic)
    try:
        predictor = _get_predictor()
        df = transform_request_to_dataframe(request, predictor.feature_names)
        probability = float(predictor.predict_proba(df)[0])
        probability = max(0.0, min(1.0, probability))
        
        engine = _get_decision_engine()
        model_version = predictor.metadata.get("version", "unknown")
        decision = engine.decide(
            recovery_probability=probability,
            amount=request.amount,
            failure_code=request.failure_code,
            retry_count=request.retry_count,
            model_version=model_version,
        )
    except Exception as exc:
        logger.error("Failed to generate prediction/decision: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to analyze recovery opportunity.")

    # 2. Delegate to Workflow Service
    service = RecoveryWorkflowService(db)
    return service.create_workflow(request, probability, decision)


@router.get(
    "/recovery",
    response_model=list[RecoveryWorkflowResponse],
    summary="List all recovery workflows",
)
def list_recoveries(db: Session = Depends(get_db)) -> list[RecoveryWorkflowResponse]:
    """Fetch all recovery workflows ordered by creation date."""
    service = RecoveryWorkflowService(db)
    return service.list_workflows()


@router.get(
    "/recovery/stats",
    response_model=RecoveryStats,
    summary="Get recovery dashboard stats",
)
def get_recovery_stats(db: Session = Depends(get_db)) -> RecoveryStats:
    """Fetch aggregate dashboard statistics."""
    service = RecoveryWorkflowService(db)
    return service.get_stats()


@router.get(
    "/recovery/{recovery_id}",
    response_model=RecoveryWorkflowResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Workflow not found"},
    },
    summary="Get recovery workflow status",
)
def get_recovery(recovery_id: str, db: Session = Depends(get_db)) -> RecoveryWorkflowResponse:
    """Fetch the current state of a recovery workflow."""
    service = RecoveryWorkflowService(db)
    workflow = service.get_workflow(recovery_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Recovery workflow not found.")
    return workflow


@router.post(
    "/recovery/{recovery_id}/execute",
    response_model=ExecutionResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Workflow not found"},
    },
    summary="Execute recommended recovery action",
)
def execute_recovery(recovery_id: str, db: Session = Depends(get_db)) -> ExecutionResponse:
    """Attempt to execute the recommended action for the workflow."""
    service = RecoveryWorkflowService(db)
    try:
        return service.execute_workflow(recovery_id)
    except ValueError as e:
        if str(e) == "Workflow not found.":
            raise HTTPException(status_code=404, detail="Recovery workflow not found.")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during execution.")
