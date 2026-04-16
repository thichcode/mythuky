from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Dict

from fastapi import FastAPI, HTTPException

from app.adapters import LokiAdapter, PrometheusAdapter
from app.config import ApprovalRequest, IncidentMessage, Settings
from app.db import PostgresRepository

settings = Settings()
app = FastAPI(title=settings.app_name)
repo = PostgresRepository(settings.database_url)
prom = PrometheusAdapter(settings.prometheus_base_url)
loki = LokiAdapter(settings.loki_base_url)


def build_idempotency_key(request_id: str, action_type: str, target: str) -> str:
    seed = f"{request_id}:{action_type}:{target}".encode("utf-8")
    return hashlib.sha256(seed).hexdigest()


def run_action_executor(action_row: Dict[str, Any]) -> Dict[str, Any]:
    idempotency_key = action_row["idempotency_key"]
    return repo.transition_action_to_executed(idempotency_key)


def process_incident(payload: IncidentMessage) -> Dict[str, Any]:
    request_id = str(uuid.uuid4())
    session_id = repo.ensure_session(payload.thread_id, payload.channel)

    metrics = prom.query_error_rate(payload.service, payload.env)
    logs = loki.query_redis_latency(payload.service)

    repo.insert_evidence(request_id, "prometheus", metrics)
    repo.insert_evidence(request_id, "loki", logs)

    error_rate = float(metrics["error_rate"])
    redis_latency = float(logs["redis_latency_ms_estimate"])

    should_rollback = (
        error_rate >= settings.rollback_error_rate_threshold
        or redis_latency >= settings.redis_latency_threshold_ms
    )

    recommendation = "check redis + pool before rollback"
    action_type = "rollback" if should_rollback else "observe"

    requires_approval = payload.env == "prod" and action_type == "rollback"
    repo.log_policy_decision(
        request_id=request_id,
        action_type=action_type,
        env=payload.env,
        allowed=True,
        requires_approval=requires_approval,
        reason="prod rollback gate" if requires_approval else "no approval needed",
    )

    action = None
    if action_type == "rollback":
        idempotency_key = build_idempotency_key(request_id, action_type, payload.service)
        status = "pending_approval" if requires_approval else "approved"
        action = repo.upsert_action(
            request_id=request_id,
            action_type=action_type,
            target=payload.service,
            idempotency_key=idempotency_key,
            status=status,
            metadata={"session_id": session_id, "env": payload.env},
        )
        if not requires_approval:
            action = run_action_executor(action)

    return {
        "request_id": request_id,
        "service": payload.service,
        "env": payload.env,
        "metrics": {"error_rate": error_rate, "redis_latency_ms_estimate": redis_latency},
        "recommendation": recommendation,
        "proposed_action": action_type,
        "approval_required": requires_approval,
        "action_status": action["status"] if action else "none",
    }


@app.on_event("startup")
def startup() -> None:
    repo.init_schema()


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/teams")
def teams_webhook(payload: IncidentMessage) -> Dict[str, Any]:
    return process_incident(payload)


@app.post("/webhook/telegram")
def telegram_webhook(payload: IncidentMessage) -> Dict[str, Any]:
    return process_incident(payload)


@app.post("/approvals/{request_id}")
def approval_webhook(request_id: str, payload: ApprovalRequest) -> Dict[str, Any]:
    action = repo.get_action_by_request(request_id)
    if not action:
        raise HTTPException(status_code=404, detail="request_id not found")

    decision = payload.decision.strip().lower()
    if decision not in {"approve", "edit", "reject"}:
        raise HTTPException(status_code=400, detail="decision must be approve|edit|reject")

    edited_plan = {"scope": payload.edited_scope} if payload.edited_scope else None
    repo.log_feedback(
        request_id=request_id,
        user_id=payload.approver_id,
        feedback_type=decision,
        rationale=payload.rationale,
        edited_plan_json=edited_plan,
    )

    if decision == "reject":
        repo.upsert_action(
            request_id=action["request_id"],
            action_type=action["action_type"],
            target=action["target"],
            idempotency_key=action["idempotency_key"],
            status="rejected",
            metadata={"rationale": payload.rationale or ""},
        )
        return {"request_id": request_id, "status": "rejected"}

    if decision == "edit":
        merged_meta = dict(action["metadata_json"])
        merged_meta["edited_scope"] = payload.edited_scope
        repo.upsert_action(
            request_id=action["request_id"],
            action_type=action["action_type"],
            target=action["target"],
            idempotency_key=action["idempotency_key"],
            status="approved",
            metadata=merged_meta,
        )

    executed = run_action_executor(action)
    if not executed:
        raise HTTPException(status_code=409, detail="action execution conflict")

    return {
        "request_id": request_id,
        "status": executed["status"],
        "idempotency_key": executed["idempotency_key"],
        "action": executed["action_type"],
    }


@app.get("/requests/{request_id}")
def get_request(request_id: str) -> Dict[str, Any]:
    action = repo.get_action_by_request(request_id)
    if not action:
        raise HTTPException(status_code=404, detail="request_id not found")

    metadata = action["metadata_json"]
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    return {
        "request_id": request_id,
        "action_type": action["action_type"],
        "target": action["target"],
        "status": action["status"],
        "metadata": metadata,
        "idempotency_key": action["idempotency_key"],
    }
