# RecoverIQ Intelligence Dashboard (Day 6)

## Overview
The Intelligence Dashboard is a lightweight, frontend interface built with Vite, React, TypeScript, and TailwindCSS. It provides a visual layer over the robust RecoverIQ prediction and orchestration engine, answering the core question: **"How can an operator clearly see, understand, and interact with the entire recovery system?"**

## Architecture
The frontend is strictly a presentation layer. It does **not** duplicate the ML logic, decision engine thresholds, or recovery policies.

```
                    ┌─────────────────────┐
                    │   React Frontend    │
                    │ Dashboard / Cases   │
                    └──────────┬──────────┘
                               │
                               │ HTTP (REST)
                               ▼
                    ┌─────────────────────┐
                    │     FastAPI API     │
                    └──────────┬──────────┘
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
        ML Predictor     Decision Engine    Workflow Service
```

## Component Structure
- `Dashboard.tsx`: Primary overview rendering aggregated KPIs (`/recovery/stats`) and recent recovery workflows (`/recovery`).
- `RecoveryCase.tsx`: Detailed view for a specific workflow ID, mapping probabilities to visual gauges, displaying risk tiers, and exposing the execution action.
- **Shared Components**: 
  - `ProbabilityGauge`: Visualizes the prediction probability using a colored progress bar matching backend thresholds.
  - `RiskBadge`, `StatusBadge`, `ActionBadge`: Type-safe visual indicators for system states.

## API Integration
The dashboard communicates with the backend via `src/services/api.ts`, which supports the following endpoints:
1. `GET /recovery/stats`: Retrieves system-wide aggregates like Total Cases, Amount At Risk, and Average Recovery Probability.
2. `GET /recovery`: Fetches all existing workflow instances.
3. `GET /recovery/{id}`: Gets details of a specific workflow case.
4. `POST /recovery/{id}/execute`: Triggers the simulated execution of a workflow case.

## Execution and Safety
The frontend strictly respects backend safety mechanisms:
1. **Simulation**: Execution is completely simulated (`SimulatedRecoveryExecutor`). No real payment gateways are called.
2. **Fraud Guard UX**: If a case is triggered by `FRAUD_CHECK`, the frontend automatically hides the execution action and highlights the `ESCALATED` manual review status.
3. **Idempotency & Limits**: Workflows in terminal states (`COMPLETED`, `FAILED`, `BLOCKED`) prevent execution attempts at the UI layer.

## Development Setup
To run the dashboard locally:
```bash
cd frontend
npm install
npm run dev
```
Make sure the backend is running at the same time:
```bash
uvicorn backend.main:app --reload
```
The frontend API URL defaults to `http://localhost:8000`. You can configure it by creating a `.env` file from the provided `.env.example`.
