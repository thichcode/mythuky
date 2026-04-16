from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException

from app.adapters import LokiAdapter, PrometheusAdapter
from app.config import ApprovalRequest, IncidentMessage, Settings
from app.db import PostgresRepository
from app.llm import LLMAdvisor, LLMUnavailableError
from app.logging_utils import configure_logging, get_logger
from app.security import verify_api_key

settings = Settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

app = FastAPI(title=settings.app_name)
repo = PostgresRepository(settings.database_url)
prom = PrometheusAdapter(
    settings.prometheus_base_url,
    max_retries=settings.http_max_retries,
    retry_backoff_seconds=settings.http_retry_backoff_seconds,
)
loki = LokiAdapter(
    settings.loki_base_url,
    max_retries=settings.http_max_retries,
    retry_backoff_seconds=settings.http_retry_backoff_seconds,
)
llm_advisor = LLMAdvisor(settings)


def build_idempotency_key(request_id: str, action_type: str, target: str) -> str:
    seed = f"{request_id}:{action_type}:{target}".encode("utf-8")
    return hashlib.sha256(seed).hexdigest()


def run_action_executor(action_row: Dict[str, Any]) -> Dict[str, Any]:
    idempotency_key = action_row["idempotency_key"]
    return repo.transition_action_to_executed(idempotency_key)


def process_incident(payload: IncidentMessage) -> Dict[str, Any]:
    if payload.external_event_id:
        existing_request_id = repo.get_request_id_by_external_event(payload.external_event_id)
        if existing_request_id:
            existing_action = repo.get_action_by_request(existing_request_id)
            logger.info(
                "incident_duplicate_event",
                extra={
                    "external_event_id": payload.external_event_id,
                    "request_id": existing_request_id,
                },
            )
            return {
                "request_id": existing_request_id,
                "duplicate": True,
                "action_status": existing_action["status"] if existing_action else "none",
            }

    request_id = str(uuid.uuid4())
    session_id = repo.ensure_session(payload.thread_id, payload.channel)

    if payload.external_event_id:
        repo.register_webhook_event(payload.external_event_id, payload.channel, payload.thread_id, request_id)

    logger.info(
        "incident_received",
        extra={
            "request_id": request_id,
            "service": payload.service,
            "env": payload.env,
            "thread_id": payload.thread_id,
        },
    )

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
    llm_info: Dict[str, Any] = {"used": False, "fallback_reason": None}

    llm_context = {
        "request_id": request_id,
        "service": payload.service,
        "env": payload.env,
        "user_text": payload.text,
        "signals": {
            "error_rate": error_rate,
            "redis_latency_ms_estimate": redis_latency,
            "thresholds": {
                "rollback_error_rate_threshold": settings.rollback_error_rate_threshold,
                "redis_latency_threshold_ms": settings.redis_latency_threshold_ms,
            },
        },
        "rule_based_action": "rollback" if should_rollback else "observe",
    }

    try:
        llm_result = llm_advisor.suggest(llm_context)
        llm_info = {
            "used": True,
            "provider": llm_result.get("provider"),
            "model": llm_result.get("model"),
            "confidence": llm_result.get("confidence"),
            "fallback_reason": None,
        }
        recommendation = llm_result.get("recommendation") or recommendation
    except (LLMUnavailableError, json.JSONDecodeError, KeyError, ValueError) as exc:
        llm_info["fallback_reason"] = f"llm_fallback: {exc}"
        logger.warning(
            "llm_fallback",
            extra={"request_id": request_id, "reason": llm_info["fallback_reason"]},
        )

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
            metadata={
                "session_id": session_id,
                "env": payload.env,
                "llm": llm_info,
            },
        )
        if not requires_approval:
            action = run_action_executor(action)

    logger.info(
        "incident_decided",
        extra={
            "request_id": request_id,
            "service": payload.service,
            "proposed_action": action_type,
            "approval_required": requires_approval,
        },
    )

    return {
        "request_id": request_id,
        "service": payload.service,
        "env": payload.env,
        "metrics": {
            "error_rate": error_rate,
            "redis_latency_ms_estimate": redis_latency,
        },
        "recommendation": recommendation,
        "llm": llm_info,
        "proposed_action": action_type,
        "approval_required": requires_approval,
        "action_status": action["status"] if action else "none",
    }


@app.on_event("startup")
def startup() -> None:
    repo.apply_migrations()


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/teams", dependencies=[Depends(verify_api_key)])
def teams_webhook(payload: IncidentMessage) -> Dict[str, Any]:
    return process_incident(payload)


@app.post("/webhook/telegram", dependencies=[Depends(verify_api_key)])
def telegram_webhook(payload: IncidentMessage) -> Dict[str, Any]:
    return process_incident(payload)


@app.post("/approvals/{request_id}", dependencies=[Depends(verify_api_key)])
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
        action = repo.transition_action_status(action["idempotency_key"], "rejected")
        logger.info("approval_rejected", extra={"request_id": request_id})
        return {"request_id": request_id, "status": action["status"] if action else "rejected"}

    if decision == "edit":
        merged_meta = dict(action["metadata_json"])
        merged_meta["edited_scope"] = payload.edited_scope
        repo.upsert_action(
            request_id=action["request_id"],
            action_type=action["action_type"],
            target=action["target"],
            idempotency_key=action["idempotency_key"],
            status=action["status"],
            metadata=merged_meta,
        )

    repo.transition_action_status(action["idempotency_key"], "approved")
    executed = run_action_executor(action)
    if not executed:
        raise HTTPException(status_code=409, detail="action execution conflict")

    logger.info(
        "approval_executed",
        extra={"request_id": request_id, "status": executed["status"]},
    )
    return {
        "request_id": request_id,
        "status": executed["status"],
        "idempotency_key": executed["idempotency_key"],
        "action": executed["action_type"],
    }


@app.get("/requests/{request_id}", dependencies=[Depends(verify_api_key)])
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
