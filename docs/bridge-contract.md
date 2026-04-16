# Bridge Contract: Teams Ingress + Telegram Approval

This document defines the minimal JSON contracts between channel bridges and the ChatOps AI service.

## 1) Teams ingress -> ChatOps AI

**Endpoint**: `POST /webhook/teams`

### Required JSON

```json
{
  "user_id": "teams:aad:<aad_object_id>",
  "channel": "teams",
  "thread_id": "teams:<tenant_id>:<team_id>:<channel_id>:<conversation_id>",
  "text": "auth-prod lỗi tăng, có cần rollback không?",
  "service": "auth-prod",
  "env": "prod",
  "external_event_id": "teams:<tenant_id>:<team_id>:<channel_id>:<activity_id>"
}
```

### Notes

- `external_event_id` MUST be globally unique and namespaced by source.
- `thread_id` should remain stable for all replies in the same conversation thread.
- `user_id` should be stable (AAD object id preferred).

## 2) Telegram approval callback -> ChatOps AI

**Endpoint**: `POST /approvals/{request_id}`

### Required JSON

```json
{
  "approver_id": "telegram:<chat_id_or_user_id>",
  "decision": "approve",
  "edited_scope": null,
  "rationale": "SRE confirmed Redis pool saturation fixed"
}
```

### Decision values

- `approve`
- `edit`
- `reject`

If `decision = edit`, set `edited_scope` (example: `canary-only`).

## 3) Suggested identity mapping rules

- Teams identity key: `teams:aad:<aad_object_id>`
- Telegram identity key: `telegram:<user_or_chat_id>`
- Internal identity key: `internal:<employee_or_oncall_id>`

Bridge should resolve both channel identities to one internal user before writing approvals.

## 4) Error handling contract (bridge side)

- Retry on `5xx` with exponential backoff.
- Do not retry on `4xx` except `429`.
- Include request correlation id in bridge logs.

