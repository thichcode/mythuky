from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import psycopg
from psycopg.rows import dict_row


class PostgresRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def init_schema(self) -> None:
        schema_path = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
        sql = schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
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
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into action_execution_log
                    (request_id, action_type, target, idempotency_key, status, metadata_json)
                    values (%s, %s, %s, %s, %s, %s::jsonb)
                    on conflict (idempotency_key) do update
                    set status = excluded.status,
                        metadata_json = action_execution_log.metadata_json || excluded.metadata_json
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

    def transition_action_to_executed(self, idempotency_key: str) -> Dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update action_execution_log
                    set status = 'executed'
                    where idempotency_key = %s
                      and status in ('pending_approval', 'approved')
                    returning *
                    """,
                    (idempotency_key,),
                )
                updated = cur.fetchone()

                if updated is None:
                    cur.execute(
                        """
                        select * from action_execution_log
                        where idempotency_key = %s
                        """,
                        (idempotency_key,),
                    )
                    updated = cur.fetchone()
            conn.commit()
        return updated

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
