# Recovery Orchestration

The Recovery Orchestration layer (implemented in Day 5) manages the execution lifecycle of recommended recovery actions.

## Architecture

1. **API Layer (`backend/routes/recovery.py`)**
   - Exposes REST endpoints to create, monitor, and execute recovery workflows.
2. **Service Layer (`backend/services/recovery_workflow_service.py`)**
   - Coordinates state transitions (PENDING -> EXECUTING -> COMPLETED/FAILED).
3. **Policy Layer (`backend/services/recovery_policy.py`)**
   - Enforces safety checks (fraud prevention, retry limits, idempotency).
4. **Execution Layer (`backend/services/recovery_executor.py`)**
   - Simulates the actual recovery actions (e.g., retries, reminders).

## Workflows

A `RecoveryWorkflow` object represents a single payment failure's recovery lifecycle. 

- Created via `POST /recovery`.
- Executed via `POST /recovery/{recovery_id}/execute`.
- Guarded by maximum retry limits and terminal state protections.
