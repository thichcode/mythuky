from __future__ import annotations

from typing import Any, Dict

from fastapi.testclient import TestClient

import app.main as main
import app.security as security


class FakeRepo:
    def __init__(self) -> None:
        self.actions: dict[str, Dict[str, Any]] = {}
        self.event_to_request: dict[str, str] = {}

    def apply_migrations(self) -> None:
        return None

    def ensure_session(self, thread_id: str, channel: str) -> int:
        return 1

    def register_webhook_event(self, external_event_id: str, channel: str, thread_id: str, request_id: str) -> bool:
        if external_event_id in self.event_to_request:
            return False
        self.event_to_request[external_event_id] = request_id
        return True

    def get_request_id_by_external_event(self, external_event_id: str) -> str | None:
        return self.event_to_request.get(external_event_id)

    def insert_evidence(self, request_id: str, tool_name: str, payload: Dict[str, Any]) -> None:
        return None

    def log_policy_decision(self, **kwargs: Any) -> None:
        return None

    def upsert_action(
        self,
        request_id: str,
        action_type: str,
        target: str,
        idempotency_key: str,
        status: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        row = {
            "request_id": request_id,
            "action_type": action_type,
            "target": target,
            "idempotency_key": idempotency_key,
            "status": status,
            "metadata_json": metadata,
        }
        self.actions[request_id] = row
        return row

    def get_action_by_request(self, request_id: str) -> Dict[str, Any] | None:
        return self.actions.get(request_id)

    def transition_action_status(self, idempotency_key: str, next_status: str) -> Dict[str, Any] | None:
        for row in self.actions.values():
            if row["idempotency_key"] == idempotency_key:
                row["status"] = next_status
                return row
        return None

    def transition_action_to_executed(self, idempotency_key: str) -> Dict[str, Any] | None:
        return self.transition_action_status(idempotency_key, "executed")

    def log_feedback(self, **kwargs: Any) -> None:
        return None


class FakeProm:
    def query_error_rate(self, service: str, env: str) -> Dict[str, Any]:
        return {"error_rate": 0.2}


class FakeLoki:
    def query_redis_latency(self, service: str) -> Dict[str, Any]:
        return {"redis_latency_ms_estimate": 100.0}


class FakeLLM:
    def suggest(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "provider": "openai",
            "model": "fake",
            "confidence": 0.9,
            "recommendation": "rollback with caution",
        }


def make_client() -> TestClient:
    main.repo = FakeRepo()
    main.prom = FakeProm()
    main.loki = FakeLoki()
    main.llm_advisor = FakeLLM()
    main.settings.auth_enabled = False
    security.settings.auth_enabled = False
    return TestClient(main.app)


def test_webhook_then_approve_flow() -> None:
    client = make_client()
    payload = {
        "user_id": "u1",
        "channel": "teams",
        "thread_id": "t1",
        "text": "auth-prod lỗi tăng",
        "service": "auth-prod",
        "env": "prod",
        "external_event_id": "evt-1",
    }

    r1 = client.post("/webhook/teams", json=payload)
    assert r1.status_code == 200
    body = r1.json()
    assert body["approval_required"] is True
    request_id = body["request_id"]

    r2 = client.post(
        f"/approvals/{request_id}",
        json={"approver_id": "oncall", "decision": "approve", "rationale": "ok"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "executed"


def test_webhook_duplicate_external_event() -> None:
    client = make_client()
    payload = {
        "user_id": "u1",
        "channel": "teams",
        "thread_id": "t1",
        "text": "auth-prod lỗi tăng",
        "service": "auth-prod",
        "env": "prod",
        "external_event_id": "evt-dup",
    }

    first = client.post("/webhook/teams", json=payload)
    second = client.post("/webhook/teams", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["request_id"] == first.json()["request_id"]
