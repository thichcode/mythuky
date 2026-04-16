from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import psycopg
from psycopg.rows import dict_row


VALID_ACTION_STATUSES = {"pending_approval", "approved", "executed", "rejected", "failed"}

ALLOWED_TRANSITIONS = {
    "pending_approval": {"approved", "rejected", "failed", "executed"},
    "approved": {"executed", "failed"},
    "executed": set(),
    "rejected": set(),
    "failed": set(),
}


class PostgresRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def apply_migrations(self) -> None:
        migration_dir = Path(__file__).resolve().parent.parent / "db" / "migrations"
        migration_files = sorted(migration_dir.glob("*.sql"))

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    create table if not exists schema_migration (
                      version text primary key,
                      applied_at timestamptz not null default now()
                    )
                    """
                )
                for file in migration_files:
                    version = file.name
                    cur.execute("select 1 from schema_migration where version = %s", (version,))
                    exists = cur.fetchone()
                    if exists:
                        continue

                    sql = file.read_text(encoding="utf-8")
                    cur.execute(sql)
                    cur.execute("insert into schema_migration (version) values (%s)", (version,))
            conn.commit()

    def ensure_session(self, thread_id: str, channel: str) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into chat_session (thread_id, channel)
                    values (%s, %s)
                    returning id
                    """,
                    (thread_id, channel),
                )
                row = cur.fetchone()
            conn.commit()
        return int(row["id"])

    def register_webhook_event(
        self,
        external_event_id: str,
        channel: str,
        thread_id: str,
        request_id: str,
    ) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into webhook_event (external_event_id, channel, thread_id, request_id)
                    values (%s, %s, %s, %s)
                    on conflict (external_event_id) do nothing
                    returning id
                    """,
                    (external_event_id, channel, thread_id, request_id),
                )
                row = cur.fetchone()
            conn.commit()
        return row is not None

    def get_request_id_by_external_event(self, external_event_id: str) -> str | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select request_id from webhook_event
                    where external_event_id = %s
                    """,
                    (external_event_id,),
                )
                row = cur.fetchone()
        return row["request_id"] if row else None

    def insert_evidence(self, request_id: str, tool_name: str, payload: Dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into evidence_snapshot (request_id, tool_name, payload_json)
                    values (%s, %s, %s::jsonb)
                    """,
                    (request_id, tool_name, json.dumps(payload)),
                )
            conn.commit()

    def log_policy_decision(
        self,
        request_id: str,
        action_type: str,
        env: str,
        allowed: bool,
        requires_approval: bool,
        reason: str,
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into policy_decision_log
                    (request_id, action_type, env, allowed, requires_approval, reason)
                    values (%s, %s, %s, %s, %s, %s)
                    """,
                    (request_id, action_type, env, allowed, requires_approval, reason),
                )
            conn.commit()

    def upsert_action(
        self,
        request_id: str,
        action_type: str,
        target: str,
        idempotency_key: str,
        status: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        if status not in VALID_ACTION_STATUSES:
            raise ValueError(f"invalid action status: {status}")

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into action_execution_log
                    (request_id, action_type, target, idempotency_key, status, metadata_json)
                    values (%s, %s, %s, %s, %s, %s::jsonb)
                    on conflict (idempotency_key) do update
                    set metadata_json = action_execution_log.metadata_json || excluded.metadata_json
                    returning *
                    """,
                    (
                        request_id,
                        action_type,
                        target,
                        idempotency_key,
                        status,
                        json.dumps(metadata),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        return row

    def get_action_by_request(self, request_id: str) -> Dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select * from action_execution_log
                    where request_id = %s
                    order by id desc
                    limit 1
                    """,
                    (request_id,),
                )
                row = cur.fetchone()
        return row

    def transition_action_status(self, idempotency_key: str, next_status: str) -> Dict[str, Any] | None:
        if next_status not in VALID_ACTION_STATUSES:
            raise ValueError(f"invalid action status: {next_status}")

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select * from action_execution_log
                    where idempotency_key = %s
                    for update
                    """,
                    (idempotency_key,),
                )
                row = cur.fetchone()
                if row is None:
                    conn.commit()
                    return None

                current_status = row["status"]
                if next_status == current_status:
                    conn.commit()
                    return row

                allowed = ALLOWED_TRANSITIONS.get(current_status, set())
                if next_status not in allowed:
                    raise ValueError(f"invalid transition {current_status} -> {next_status}")

                cur.execute(
                    """
                    update action_execution_log
                    set status = %s
                    where idempotency_key = %s
                    returning *
                    """,
                    (next_status, idempotency_key),
                )
                updated = cur.fetchone()
            conn.commit()
        return updated

    def transition_action_to_executed(self, idempotency_key: str) -> Dict[str, Any] | None:
        return self.transition_action_status(idempotency_key, "executed")

    def log_feedback(
        self,
        request_id: str,
        user_id: str,
        feedback_type: str,
        rationale: str | None,
        edited_plan_json: Dict[str, Any] | None,
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into feedback_event
                    (request_id, user_id, feedback_type, rationale, edited_plan_json)
                    values (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        request_id,
                        user_id,
                        feedback_type,
                        rationale,
                        json.dumps(edited_plan_json) if edited_plan_json else None,
                    ),
                )
            conn.commit()
