# ChatOps AI Incident Copilot (Production-Ready Starter)

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

