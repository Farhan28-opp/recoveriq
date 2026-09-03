import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.services.transaction_import_service import TransactionImportService

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
    "/recovery/import/csv",
    summary="Import business transactions from CSV",
    response_model=Dict[str, Any],
    responses={
        400: {"description": "Invalid CSV schema or contents"},
        500: {"description": "Internal error during import"},
    },
)
async def import_transactions_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Import business transactions and generate ML recovery workflows for failures."""
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
        
    try:
        content = await file.read()
        file_content = content.decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")
        
    service = TransactionImportService(db)
    try:
        result = service.process_import(file_content)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Import processing failed.")
        raise HTTPException(status_code=500, detail="Internal server error during import.")

@router.delete(
    "/recovery/import/{batch_id}",
    summary="Safely delete an imported dataset and its generated workflows",
    response_model=Dict[str, Any],
)
def delete_imported_batch(batch_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    from backend.models import Transaction, RecoveryWorkflow
    
    # Check if any exist
    tx_count = db.query(Transaction).filter(Transaction.import_batch_id == batch_id).count()
    if tx_count == 0:
        raise HTTPException(status_code=404, detail="Import batch not found.")
        
    try:
        # Must delete workflows first to satisfy foreign key safely
        workflows_deleted = db.query(RecoveryWorkflow).filter(RecoveryWorkflow.import_batch_id == batch_id).delete(synchronize_session=False)
        txs_deleted = db.query(Transaction).filter(Transaction.import_batch_id == batch_id).delete(synchronize_session=False)
        db.commit()
        return {
            "deleted_transactions": txs_deleted,
            "deleted_workflows": workflows_deleted,
            "message": "Dataset successfully removed."
        }
    except Exception as e:
        db.rollback()
        logger.exception("Failed to delete imported batch.")
        raise HTTPException(status_code=500, detail="Failed to delete imported batch safely.")
