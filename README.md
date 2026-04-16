# ChatOps AI Incident Copilot (Production-Ready Starter)

This repository contains a runnable hybrid API service for incident triage + controlled rollback flow:

This repository now contains a runnable hybrid API service for incident triage + controlled rollback flow:


- FastAPI webhook service for Teams/Telegram input
- Real adapters for metrics/logs (Prometheus + Loki HTTP APIs)
- PostgreSQL persistence (schema + runtime logging)
- Hybrid decisioning: deterministic rules + optional LLM recommendation layer
- Approval flow (`approve/edit/reject`) for production rollback
- Idempotent action execution via deterministic idempotency key
- LLM fallback to rule-based recommendation if LLM is unavailable/fails
- Hardening: API key auth, adapter retries, and structured JSON logging
- Approval flow (`approve/edit/reject`) for production rollback
- Idempotent action execution via deterministic idempotency key

## Repository layout

- `app/main.py`: FastAPI service and orchestration entrypoints.
- `app/adapters.py`: Prometheus/Loki adapters with retry.
- `app/llm.py`: OpenAI/Ollama LLM advisor client.
- `app/security.py`: API key verification dependency.
- `app/logging_utils.py`: JSON structured logging formatter/configuration.
- `app/db.py`: PostgreSQL repository and persistence logic.
- `app/config.py`: environment-driven settings and request schemas.
- `tests/`: pytest tests for utilities/auth/LLM fallback behavior.
- `.env.example`: configuration template.
- `docs/bridge-contract.md`: Teams ingress + Telegram approval JSON contracts and identity mapping guidance.
- `app/adapters.py`: Prometheus/Loki adapters.
- `app/llm.py`: OpenAI/Ollama LLM advisor client.
- `app/db.py`: PostgreSQL repository and persistence logic.
- `app/config.py`: environment-driven settings and request schemas.
- `db/schema.sql`: database schema.
- `policy/policy_rules.yaml`: policy reference rules.
- `docs/production-ready-system-flow.md`: architecture overview.
- `.env.example`: configuration template.

## Prerequisites

- Python 3.10+
- PostgreSQL 14+
- Prometheus and Loki endpoints (or stubs/mocks)
- Optional: OpenAI API key or Ollama local runtime

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env as needed
uvicorn app.main:app --reload --port 8000
```

## Security & hardening config

```env
AUTH_ENABLED=true
API_KEY=change-me
HTTP_MAX_RETRIES=2
HTTP_RETRY_BACKOFF_SECONDS=0.3
LOG_LEVEL=INFO
```

Call protected endpoints with:

```bash
-H 'X-API-Key: change-me'
```

## LLM provider config

### OpenAI

```env
LLM_ENABLED=true
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=sk-...
# OPENAI_BASE_URL optional
```

### Ollama

```env
LLM_ENABLED=true
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:14b-instruct
OLLAMA_BASE_URL=http://localhost:11434
```

### Disable LLM (rule-only)

```env
LLM_ENABLED=false
```

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
  -H 'X-API-Key: change-me' \
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
  -H 'X-API-Key: change-me' \
  -d '{
    "approver_id":"oncall-1",
    "decision":"approve",
    "rationale":"error rate keeps increasing"
  }' | jq
```

## Migrations

- SQL migrations are applied on startup from `db/migrations/*.sql` and tracked in `schema_migration`.

## Tests

```bash
pytest -q
```

Integration-like API tests are in `tests/test_api_integration.py` (webhook -> approval flow and webhook dedupe).

## Notes

- Identity links can be stored in `user_identity_map` for Teams/Telegram/internal user correlation.
- In `prod`, rollback is persisted as `pending_approval` first.
- Execution is idempotent by `idempotency_key` (`sha256(request_id:action:target)`).
- If LLM fails (provider unavailable, bad response, missing key), service falls back to rule-based recommendation and still returns incident output.
- In `prod`, rollback is persisted as `pending_approval` first.
- Execution is idempotent by `idempotency_key` (`sha256(request_id:action:target)`).
- If LLM fails (provider unavailable, bad response, missing key), service falls back to rule-based recommendation and still returns incident output.
- Approving the same request repeatedly returns stable executed state rather than creating duplicate action rows.
- 
This repository contains a production-minded starter design for a ChatOps AI system that:

- Receives incidents from Teams/Telegram
- Orchestrates investigation with LangGraph
- Retrieves runbooks with RAG (LlamaIndex)
- Queries ops/security tools (Zabbix, ELK/Loki, GitLab, Trivy, Gitleaks)
- Applies policy/approval gates before risky actions
- Captures human feedback and continuously improves behavior

## Repository layout

- `docs/production-ready-system-flow.md`: End-to-end architecture and runtime flow.
- `app/langgraph_flow.py`: Executable-oriented skeleton for LangGraph orchestration.
- `db/schema.sql`: Memory + feedback + audit schema.
- `policy/policy_rules.yaml`: Deterministic policy gates for production actions.

## Quick start

1. Read `docs/production-ready-system-flow.md`.
2. Implement concrete adapters in `app/langgraph_flow.py` for your stack.
3. Apply `db/schema.sql` to PostgreSQL.
4. Wire `policy/policy_rules.yaml` into your policy engine and CI checks.


