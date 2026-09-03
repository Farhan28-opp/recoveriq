import csv
import logging
import uuid
from collections import defaultdict
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Customer, Merchant, Transaction
from backend.schemas.prediction import PredictionRequest
from backend.routes.predict import _get_decision_engine, _get_predictor, transform_request_to_dataframe
from backend.services.recovery_workflow_service import RecoveryWorkflowService

logger = logging.getLogger(__name__)

# Constants identical to data/generate_dataset.py
BANK_BASE_FAIL = {
    "HDFC": 0.05,
    "ICICI": 0.06,
    "SBI": 0.09,
    "AXIS": 0.07,
    "KOTAK": 0.06,
    "YES": 0.11,
    "INDUSIND": 0.08,
}
METHOD_BASE_FAIL = {
    "UPI": 0.05,
    "CARD": 0.09,
    "NETBANKING": 0.10,
    "WALLET": 0.06,
}
MIN_HISTORY_FOR_ROLLING_RATE = 20
DEFAULT_CUSTOMER_SUCCESS_RATE = 0.90
DEFAULT_ABANDONMENT_RATE = 0.08

class TransactionImportService:
    def __init__(self, db: Session):
        self.db = db

    def parse_csv(self, file_content: str) -> List[Dict[str, Any]]:
        """Parse raw CSV string into a list of dictionaries with header normalization."""
        reader = csv.reader(StringIO(file_content))
        
        # Read the raw headers
        raw_headers = next(reader, None)
        if not raw_headers:
            raise ValueError("CSV is empty.")
            
        # Normalization mapping
        # Supports the internal schema as well as the newly approved "real-world" schema.
        header_mapping = {
            "transaction_id": "transaction_id",
            "transaction id": "transaction_id",
            "customer_id": "customer_id",
            "sender upi id": "customer_id",
            "merchant_id": "merchant_id",
            "receiver upi id": "merchant_id",
            "amount": "amount",
            "amount (inr)": "amount",
            "timestamp": "timestamp",
            "status": "status",
            "payment_method": "payment_method",
            "failure_code": "failure_code",
            "bank": "bank",
            "device_type": "device_type",
        }
        
        normalized_headers = []
        for h in raw_headers:
            clean_h = h.strip().lower()
            normalized_headers.append(header_mapping.get(clean_h, clean_h))
            
        # Check required normalized fields
        required_internal = ["transaction_id", "customer_id", "merchant_id", "amount", "timestamp"]
        missing_internal = [req for req in required_internal if req not in normalized_headers]
        
        if missing_internal:
            # For a better user experience, translate the internal requirements back to standard human names 
            # if the user uploaded something completely different.
            human_reqs = {
                "transaction_id": "Transaction ID",
                "customer_id": "Customer ID (or Sender UPI ID)",
                "merchant_id": "Merchant ID (or Receiver UPI ID)",
                "amount": "Amount",
                "timestamp": "Timestamp"
            }
            missing_human = [human_reqs[req] for req in missing_internal]
            raise ValueError(f"Required column(s) missing: {', '.join(missing_human)}")
            
        # Determine if we used the UPI-based mapping for this specific format
        derived_payment_method = "UPI" if "sender upi id" in [h.strip().lower() for h in raw_headers] else "UNKNOWN"

        rows = []
        for i, row in enumerate(reader):
            if not row or len(row) == 0:
                continue
                
            row_dict = dict(zip(normalized_headers, row))
            
            # Additional safety: check if the row has empty values for required fields
            if not row_dict.get("transaction_id") or not row_dict.get("customer_id") or not row_dict.get("merchant_id") or not row_dict.get("amount") or not row_dict.get("timestamp"):
                raise ValueError(f"Row {i+2}: Missing required values.")
            
            try:
                dt = datetime.fromisoformat(row_dict["timestamp"].replace('Z', '+00:00'))
            except ValueError:
                raise ValueError(f"Row {i+2}: Invalid ISO 8601 timestamp format.")
                
            status = row_dict.get("status", "").upper()
            if status not in ("SUCCESS", "FAILED"):
                raise ValueError(f"Row {i+2}: status must be SUCCESS or FAILED.")

            rows.append({
                "transaction_id": row_dict["transaction_id"].strip(),
                "customer_id": row_dict["customer_id"].strip(),
                "merchant_id": row_dict["merchant_id"].strip(),
                "amount": float(row_dict["amount"]),
                "currency": row_dict.get("currency", "INR").strip(),
                "timestamp": dt,
                "status": status,
                "payment_method": row_dict.get("payment_method", derived_payment_method).strip().upper() if row_dict.get("payment_method") else derived_payment_method,
                "bank": row_dict.get("bank", "UNKNOWN").strip().upper() if row_dict.get("bank") else "UNKNOWN",
                "device_type": row_dict.get("device_type", "UNKNOWN").strip().upper() if row_dict.get("device_type") else "UNKNOWN",
                "failure_code": row_dict.get("failure_code", "UNKNOWN").strip().upper() if status == "FAILED" and row_dict.get("failure_code") else ("UNKNOWN" if status == "FAILED" else None),
                "failure_reason": row_dict.get("failure_reason", "").strip() if status == "FAILED" else None,
            })
            
        # Deduplicate inside CSV (keep first occurrence)
        seen = set()
        deduped = []
        for row in rows:
            if row["transaction_id"] not in seen:
                seen.add(row["transaction_id"])
                deduped.append(row)
        return deduped

    def process_import(self, file_content: str) -> Dict[str, Any]:
        """Main entrypoint for processing the CSV inside a transaction."""
        parsed_rows = self.parse_csv(file_content)
        if not parsed_rows:
            return {"imported": 0, "skipped": 0, "workflows_created": 0}

        try:
            batch_id = str(uuid.uuid4())
            # 1. Deduplicate against existing DB transactions
            csv_tx_ids = [r["transaction_id"] for r in parsed_rows]
            existing_tx_ids = set(
                self.db.scalars(
                    select(Transaction.transaction_id).where(Transaction.transaction_id.in_(csv_tx_ids))
                ).all()
            )
            
            valid_rows = [r for r in parsed_rows if r["transaction_id"] not in existing_tx_ids]
            
            if not valid_rows:
                return {"imported": 0, "skipped": len(parsed_rows), "workflows_created": 0}
                
            # Sort chronologically for causal ML feature derivation
            valid_rows.sort(key=lambda r: r["timestamp"])
            
            # 2. Insert missing Customers and Merchants
            self._ensure_customers_and_merchants(valid_rows)
            
            # 3. Derive ML features chronologically and insert Transactions
            new_transactions = self._derive_and_insert_transactions(valid_rows, batch_id)
            
            # 4. Orchestrate ML workflows for eligible failed transactions
            workflows_created = self._orchestrate_workflows(new_transactions, batch_id)
            
            self.db.commit()
            
            return {
                "batch_id": batch_id,
                "imported": len(valid_rows),
                "skipped": len(parsed_rows) - len(valid_rows),
                "workflows_created": workflows_created
            }
            
        except Exception as e:
            self.db.rollback()
            logger.exception("Import failed, rolled back transaction.")
            raise ValueError(f"Import failed: {str(e)}")

    def _ensure_customers_and_merchants(self, rows: List[Dict[str, Any]]):
        customer_ids = {r["customer_id"] for r in rows}
        merchant_ids = {r["merchant_id"] for r in rows}
        
        existing_customers = set(self.db.scalars(select(Customer.customer_id).where(Customer.customer_id.in_(customer_ids))).all())
        existing_merchants = set(self.db.scalars(select(Merchant.merchant_id).where(Merchant.merchant_id.in_(merchant_ids))).all())
        
        new_customers = customer_ids - existing_customers
        for cid in new_customers:
            self.db.add(Customer(
                customer_id=cid,
                total_transactions=0,
                successful_transactions=0,
                failed_transactions=0,
                abandonment_rate=DEFAULT_ABANDONMENT_RATE,
                previous_recoveries=0
            ))
            
        new_merchants = merchant_ids - existing_merchants
        for mid in new_merchants:
            first_amount = next(r["amount"] for r in rows if r["merchant_id"] == mid)
            self.db.add(Merchant(
                merchant_id=mid,
                merchant_category="UNKNOWN",
                average_transaction_value=first_amount,
                monthly_transaction_volume=1
            ))
            
        self.db.flush()

    def _derive_and_insert_transactions(self, rows: List[Dict[str, Any]], batch_id: str) -> List[Transaction]:
        oldest_ts = rows[0]["timestamp"]
        customer_ids = {r["customer_id"] for r in rows}
        
        c_stats = defaultdict(lambda: {"attempts": 0, "successes": 0, "success_amount_sum": 0.0})
        
        existing_txs = self.db.execute(
            select(Transaction.customer_id, Transaction.status, Transaction.amount)
            .where(Transaction.customer_id.in_(customer_ids))
            .where(Transaction.timestamp < oldest_ts)
        ).all()
        
        for tx in existing_txs:
            c_stats[tx.customer_id]["attempts"] += 1
            if tx.status == "SUCCESS":
                c_stats[tx.customer_id]["successes"] += 1
                c_stats[tx.customer_id]["success_amount_sum"] += float(tx.amount)
                
        banks_in_csv = {r["bank"] for r in rows}
        methods_in_csv = {r["payment_method"] for r in rows}
        
        b_stats = defaultdict(lambda: {"attempts": 0, "failures": 0})
        m_stats = defaultdict(lambda: {"attempts": 0, "failures": 0})
        
        existing_b_txs = self.db.execute(
            select(Transaction.bank, Transaction.status)
            .where(Transaction.bank.in_(banks_in_csv))
            .where(Transaction.timestamp < oldest_ts)
        ).all()
        for tx in existing_b_txs:
            b_stats[tx.bank]["attempts"] += 1
            if tx.status == "FAILED":
                b_stats[tx.bank]["failures"] += 1
                
        existing_m_txs = self.db.execute(
            select(Transaction.payment_method, Transaction.status)
            .where(Transaction.payment_method.in_(methods_in_csv))
            .where(Transaction.timestamp < oldest_ts)
        ).all()
        for tx in existing_m_txs:
            m_stats[tx.payment_method]["attempts"] += 1
            if tx.status == "FAILED":
                m_stats[tx.payment_method]["failures"] += 1

        inserted_transactions = []
        for row in rows:
            cid = row["customer_id"]
            bank = row["bank"]
            method = row["payment_method"]
            status = row["status"]
            amount = row["amount"]
            ts = row["timestamp"]
            
            b_att = b_stats[bank]["attempts"]
            b_fail = b_stats[bank]["failures"]
            recent_bank_failure_rate = (b_fail / b_att) if b_att >= MIN_HISTORY_FOR_ROLLING_RATE else BANK_BASE_FAIL.get(bank, 0.07)
            
            m_att = m_stats[method]["attempts"]
            m_fail = m_stats[method]["failures"]
            recent_method_failure_rate = (m_fail / m_att) if m_att >= MIN_HISTORY_FOR_ROLLING_RATE else METHOD_BASE_FAIL.get(method, 0.07)
            
            c_att = c_stats[cid]["attempts"]
            c_succ = c_stats[cid]["successes"]
            c_sum = c_stats[cid]["success_amount_sum"]
            customer_success_rate = (c_succ / c_att) if c_att >= 5 else DEFAULT_CUSTOMER_SUCCESS_RATE
            customer_lifetime_value = c_sum
            
            tx = Transaction(
                transaction_id=row["transaction_id"],
                customer_id=cid,
                merchant_id=row["merchant_id"],
                amount=amount,
                currency=row["currency"],
                timestamp=ts,
                payment_method=method,
                bank=bank,
                device_type=row["device_type"],
                status=status,
                failure_code=row["failure_code"],
                failure_reason=row["failure_reason"],
                retry_count=0,
                customer_success_rate=customer_success_rate,
                customer_lifetime_value=customer_lifetime_value,
                recent_bank_failure_rate=recent_bank_failure_rate,
                recent_method_failure_rate=recent_method_failure_rate,
                import_batch_id=batch_id,
            )
            self.db.add(tx)
            inserted_transactions.append(tx)
            
            c_stats[cid]["attempts"] += 1
            if status == "SUCCESS":
                c_stats[cid]["successes"] += 1
                c_stats[cid]["success_amount_sum"] += amount
            
            b_stats[bank]["attempts"] += 1
            m_stats[method]["attempts"] += 1
            if status == "FAILED":
                b_stats[bank]["failures"] += 1
                m_stats[method]["failures"] += 1
                
        self.db.flush()
        return inserted_transactions

    def _orchestrate_workflows(self, transactions: List[Transaction], batch_id: str) -> int:
        workflows_created = 0
        workflow_service = RecoveryWorkflowService(self.db)
        
        customer_ids = {t.customer_id for t in transactions if t.status == "FAILED"}
        merchant_ids = {t.merchant_id for t in transactions if t.status == "FAILED"}
        
        if not customer_ids:
            return 0
            
        customers = {c.customer_id: c for c in self.db.scalars(select(Customer).where(Customer.customer_id.in_(customer_ids))).all()}
        merchants = {m.merchant_id: m for m in self.db.scalars(select(Merchant).where(Merchant.merchant_id.in_(merchant_ids))).all()}
        
        predictor = _get_predictor()
        engine = _get_decision_engine()
        
        for tx in transactions:
            if tx.status != "FAILED":
                continue
                
            cust = customers[tx.customer_id]
            merch = merchants[tx.merchant_id]
            
            request_data = {
                "amount": float(tx.amount),
                "retry_count": int(tx.retry_count),
                "customer_success_rate": float(tx.customer_success_rate),
                "customer_lifetime_value": float(tx.customer_lifetime_value),
                "recent_bank_failure_rate": float(tx.recent_bank_failure_rate),
                "recent_method_failure_rate": float(tx.recent_method_failure_rate),
                "abandonment_rate": float(cust.abandonment_rate or DEFAULT_ABANDONMENT_RATE),
                "average_transaction_value": float(merch.average_transaction_value or tx.amount),
                "monthly_transaction_volume": int(merch.monthly_transaction_volume or 1),
                "hour_of_day": tx.timestamp.hour,
                "day_of_week": tx.timestamp.weekday(),
                "payment_method": tx.payment_method or "UNKNOWN",
                "bank": tx.bank or "UNKNOWN",
                "device_type": tx.device_type or "UNKNOWN",
                "failure_code": tx.failure_code or "UNKNOWN",
                "preferred_payment_method": cust.preferred_payment_method or "UNKNOWN",
                "preferred_bank": cust.preferred_bank or "UNKNOWN",
                "merchant_category": merch.merchant_category or "UNKNOWN",
            }
            
            try:
                pred_req = PredictionRequest(**request_data)
            except Exception as e:
                logger.error(f"Validation error generating PredictionRequest for {tx.transaction_id}: {e}")
                raise ValueError(f"Failed to create prediction request for {tx.transaction_id}: {e}")
                
            df = transform_request_to_dataframe(pred_req, predictor.feature_names)
            probability = float(predictor.predict_proba(df)[0])
            probability = max(0.0, min(1.0, probability))
            
            decision = engine.decide(
                recovery_probability=probability,
                amount=pred_req.amount,
                failure_code=pred_req.failure_code,
                retry_count=pred_req.retry_count,
                model_version=predictor.metadata.get("version", "unknown")
            )
            
            # The prompt requested: Do not automatically create records for every failed transaction unless it matches existing behavior.
            # In the current implementation, we create a workflow if it is actioned by the decision engine. Wait, does existing POST /recovery ALWAYS create a workflow?
            # Yes, RecoveryWorkflowService.create_workflow is always called in POST /recovery.
            # But the prompt: "unless that matches the existing RecoverIQ recovery-analysis behavior. Verify eligibility first."
            # We'll create it for all failed transactions as that matches `/recovery`. Actually, it's safer to just create for all FAILED since they are all failures.
            workflow_service.create_workflow(pred_req, probability, decision, import_batch_id=batch_id, transaction_id=tx.transaction_id)
            workflows_created += 1
                
        return workflows_created
