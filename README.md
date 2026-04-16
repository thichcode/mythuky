# ChatOps AI Incident Copilot (Production-Ready Starter)

This repository now contains a runnable API service for incident triage + controlled rollback flow:

- FastAPI webhook service for Teams/Telegram input
- Real adapters for metrics/logs (Prometheus + Loki HTTP APIs)
- PostgreSQL persistence (schema + runtime logging)
- Approval flow (`approve/edit/reject`) for production rollback
- Idempotent action execution via deterministic idempotency key

## Repository layout

- `app/main.py`: FastAPI service and orchestration entrypoints.
- `app/adapters.py`: Prometheus/Loki adapters.
- `app/db.py`: PostgreSQL repository and persistence logic.
- `app/config.py`: environment-driven settings and request schemas.
- `db/schema.sql`: database schema.
- `policy/policy_rules.yaml`: policy reference rules.
- `docs/production-ready-system-flow.md`: architecture overview.

## Prerequisites

- Python 3.10+
- PostgreSQL 14+
- Prometheus and Loki endpoints (or stubs/mocks)

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='postgresql://postgres:postgres@localhost:5432/chatops'
export PROMETHEUS_BASE_URL='http://localhost:9090'
export LOKI_BASE_URL='http://localhost:3100'
uvicorn app.main:app --reload --port 8000
```

## API examples

### 1) Incident via Teams webhook

```bash
curl -s http://localhost:8000/webhook/teams \
  -H 'content-type: application/json' \
  -d '{
    "user_id":"u1",
    "channel":"teams",
    "thread_id":"t-001",
    "text":"auth-prod lỗi tăng, có cần rollback không?",
    "service":"auth-prod",
    "env":"prod"
  }' | jq
```

### 2) Approval action

```bash
curl -s http://localhost:8000/approvals/<request_id> \
  -H 'content-type: application/json' \
  -d '{
    "approver_id":"oncall-1",
    "decision":"approve",
    "rationale":"error rate keeps increasing"
  }' | jq
```

## Notes

- In `prod`, rollback is persisted as `pending_approval` first.
- Execution is idempotent by `idempotency_key` (`sha256(request_id:action:target)`).
- Approving the same request repeatedly returns stable executed state rather than creating duplicate action rows.
