import logging
from typing import Any, Dict, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, and_, desc

from backend.database import SessionLocal
from backend.models import Transaction, RecoveryWorkflow
from pydantic import BaseModel, Field
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class TransactionResponse(BaseModel):
    transaction_id: str
    customer_id: str
    merchant_id: str
    amount: float
    currency: str
    timestamp: datetime
    status: str
    payment_method: Optional[str] = None
    bank: Optional[str] = None
    device_type: Optional[str] = None
    failure_code: Optional[str] = None
    failure_reason: Optional[str] = None
    import_batch_id: Optional[str] = None
    recovery_id: Optional[str] = None

class PaginatedTransactionResponse(BaseModel):
    items: List[TransactionResponse]
    total: int
    page: int
    size: int

class TransactionUpdateRequest(BaseModel):
    amount: Optional[float] = None
    timestamp: Optional[datetime] = None
    status: Optional[str] = None
    payment_method: Optional[str] = None
    bank: Optional[str] = None
    device_type: Optional[str] = None
    failure_code: Optional[str] = None
    failure_reason: Optional[str] = None

class BulkDeleteRequest(BaseModel):
    transaction_ids: List[str] = Field(..., min_items=1)

@router.get(
    "/transactions",
    response_model=PaginatedTransactionResponse,
    summary="Search transactions",
)
def search_transactions(
    search: Optional[str] = None,
    status: Optional[str] = None,
    import_batch_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Search and paginate transactions."""
    query = select(Transaction, RecoveryWorkflow.recovery_id).outerjoin(
        RecoveryWorkflow, RecoveryWorkflow.transaction_id == Transaction.transaction_id
    )

    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Transaction.transaction_id.ilike(search_term),
                Transaction.customer_id.ilike(search_term),
                Transaction.merchant_id.ilike(search_term),
            )
        )

    if status:
        query = query.where(Transaction.status == status.upper())
        
    if import_batch_id:
        query = query.where(Transaction.import_batch_id == import_batch_id)

    # Order by timestamp descending
    query = query.order_by(desc(Transaction.timestamp))

    from sqlalchemy import func
    
    # Calculate total
    total = db.scalar(select(func.count()).select_from(query.with_only_columns(Transaction.transaction_id).subquery()))

    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)

    results = db.execute(query).all()

    items = []
    for tx, rec_id in results:
        items.append(
            TransactionResponse(
                transaction_id=tx.transaction_id,
                customer_id=tx.customer_id,
                merchant_id=tx.merchant_id,
                amount=tx.amount,
                currency=tx.currency,
                timestamp=tx.timestamp,
                status=tx.status,
                payment_method=tx.payment_method,
                bank=tx.bank,
                device_type=tx.device_type,
                failure_code=tx.failure_code,
                failure_reason=tx.failure_reason,
                import_batch_id=tx.import_batch_id,
                recovery_id=rec_id,
            )
        )

    return PaginatedTransactionResponse(
        items=items,
        total=total or 0,
        page=page,
        size=size
    )

@router.patch(
    "/transactions/{transaction_id}",
    response_model=TransactionResponse,
    summary="Update transaction safe fields",
)
def update_transaction(
    transaction_id: str,
    update_data: TransactionUpdateRequest,
    db: Session = Depends(get_db)
):
    """Update safe fields on a transaction. Does not automatically re-run recovery analysis."""
    tx = db.query(Transaction).filter_by(transaction_id=transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    update_dict = update_data.dict(exclude_unset=True)
    if not update_dict:
        raise HTTPException(status_code=400, detail="No fields provided for update.")

    for field, value in update_dict.items():
        if field == "status" and value:
            setattr(tx, field, value.upper())
        else:
            setattr(tx, field, value)

    try:
        db.commit()
        db.refresh(tx)
    except Exception as e:
        db.rollback()
        logger.exception("Failed to update transaction.")
        raise HTTPException(status_code=500, detail="Failed to update transaction.")

    # Check for existing recovery workflow
    rec_id = None
    workflow = db.query(RecoveryWorkflow).filter_by(transaction_id=tx.transaction_id).first()
    if workflow:
        rec_id = workflow.recovery_id

    return TransactionResponse(
        transaction_id=tx.transaction_id,
        customer_id=tx.customer_id,
        merchant_id=tx.merchant_id,
        amount=tx.amount,
        currency=tx.currency,
        timestamp=tx.timestamp,
        status=tx.status,
        payment_method=tx.payment_method,
        bank=tx.bank,
        device_type=tx.device_type,
        failure_code=tx.failure_code,
        failure_reason=tx.failure_reason,
        import_batch_id=tx.import_batch_id,
        recovery_id=rec_id,
    )

@router.delete(
    "/transactions",
    summary="Bulk delete transactions",
)
def bulk_delete_transactions(
    request: BulkDeleteRequest,
    db: Session = Depends(get_db)
):
    """Safely delete multiple transactions, automatically handling related RecoveryWorkflows."""
    try:
        # Step 1: Verify transactions exist
        txs = db.query(Transaction.transaction_id).filter(
            Transaction.transaction_id.in_(request.transaction_ids)
        ).all()
        found_ids = {tx.transaction_id for tx in txs}

        if not found_ids:
            raise HTTPException(status_code=404, detail="No matching transactions found.")

        # Step 2: Delete associated recovery workflows first (to satisfy FK safely)
        workflows_deleted = db.query(RecoveryWorkflow).filter(
            RecoveryWorkflow.transaction_id.in_(found_ids)
        ).delete(synchronize_session=False)

        # Step 3: Delete transactions
        txs_deleted = db.query(Transaction).filter(
            Transaction.transaction_id.in_(found_ids)
        ).delete(synchronize_session=False)

        db.commit()

        return {
            "deleted_transactions": txs_deleted,
            "deleted_workflows": workflows_deleted,
            "message": f"Successfully deleted {txs_deleted} transactions."
        }
    except Exception as e:
        db.rollback()
        logger.exception("Failed to bulk delete transactions.")
        raise HTTPException(status_code=500, detail="Failed to delete transactions safely.")
