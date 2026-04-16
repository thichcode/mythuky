# ChatOps AI Incident Copilot (Production-Ready Starter)

This repository now contains a runnable hybrid API service for incident triage + controlled rollback flow:

- FastAPI webhook service for Teams/Telegram input
- Real adapters for metrics/logs (Prometheus + Loki HTTP APIs)
- PostgreSQL persistence (schema + runtime logging)
- Hybrid decisioning: deterministic rules + optional LLM recommendation layer
- Approval flow (`approve/edit/reject`) for production rollback
- Idempotent action execution via deterministic idempotency key
- LLM fallback to rule-based recommendation if LLM is unavailable/fails

## Repository layout

- `app/main.py`: FastAPI service and orchestration entrypoints.
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
- If LLM fails (provider unavailable, bad response, missing key), service falls back to rule-based recommendation and still returns incident output.
