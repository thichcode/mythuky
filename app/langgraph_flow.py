"""Production-oriented LangGraph orchestration skeleton.

This file is intentionally adapter-first: replace placeholders with concrete
clients for Teams/Telegram, Zabbix, ELK/Loki, GitLab, LlamaIndex, Trivy,
and Gitleaks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, TypedDict


Decision = Literal["respond", "propose_action", "execute_action"]
FeedbackType = Literal["approve", "edit", "reject"]


class GraphState(TypedDict, total=False):
    request_id: str
    user_id: str
    channel: str
    thread_id: str
    text: str
    intent: str
    entity: str
    environment: str
    short_memory: Dict[str, Any]
    long_memory: Dict[str, Any]
    tool_outputs: Dict[str, Dict[str, Any]]
    synthesis: Dict[str, Any]
    policy_result: Dict[str, Any]
    decision: Decision
    action_plan: Dict[str, Any]
    response: str


@dataclass(slots=True)
class ToolContext:
    request_id: str
    service: str
    environment: str
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Orchestrator:
    """Minimal orchestrator API designed for LangGraph-style node wiring."""

    def route(self, state: GraphState) -> GraphState:
        # Replace with robust NLU/classifier + entity extraction.
        text = state["text"].lower()
        state["intent"] = "incident_deploy_decision" if "rollback" in text else "incident_triage"
        state["entity"] = "auth-prod" if "auth" in text else "unknown"
        state["environment"] = "prod" if "prod" in text else "non-prod"
        return state

    def load_memory(self, state: GraphState) -> GraphState:
        # Replace with DB-backed memory repository.
        state["short_memory"] = {
            "previous_queries": ["check logs", "check pipeline"],
            "evidence": [],
        }
        state["long_memory"] = {
            "team_preference": "no_auto_rollback",
            "rollback_policy": "requires_approval",
        }
        return state

    def collect_evidence(self, state: GraphState) -> GraphState:
        # Replace with parallel fan-out to real adapters.
        state["tool_outputs"] = {
            "zabbix": {
                "alert": "High error rate",
                "started_at": "12:14",
                "severity": "high",
            },
            "logs": {
                "top_errors": ["token timeout", "redis latency"],
                "trend": "increasing",
            },
            "gitlab": {
                "deploy_time": "12:10",
                "status": "success",
                "commit": "abc123",
            },
            "rag": {
                "runbook": "check redis before rollback",
                "postmortem": "pool exhaustion pattern",
            },
            "security": {"critical_vuln": False},
        }
        return state

    def synthesize(self, state: GraphState) -> GraphState:
        tools = state["tool_outputs"]
        state["synthesis"] = {
            "facts": [
                f"Deploy at {tools['gitlab']['deploy_time']}",
                f"Errors started at {tools['zabbix']['started_at']}",
                "Primary errors: redis latency / token timeout",
            ],
            "inference": "Likely runtime/config issue correlated with deploy",
            "risk": "Immediate full rollback may not fix infra-driven root cause",
            "recommendation": [
                "Check Redis saturation and connection pool first",
                "If errors persist, trigger rollback with approval",
            ],
            "confidence": 0.73,
        }
        return state

    def apply_policy(self, state: GraphState) -> GraphState:
        env = state.get("environment", "non-prod")
        requires_approval = env == "prod"
        state["policy_result"] = {
            "requires_approval": requires_approval,
            "reason": "prod rollback gate" if requires_approval else "low-risk env",
        }
        state["decision"] = "propose_action" if requires_approval else "execute_action"
        state["action_plan"] = {
            "type": "rollback",
            "scope": "canary_first",
            "service": state.get("entity", "unknown"),
        }
        return state

    def format_response(self, state: GraphState) -> GraphState:
        recommendation = state["synthesis"]["recommendation"]
        state["response"] = (
            "Chưa nên rollback full ngay. "
            f"Đề xuất: (1) {recommendation[0]}; (2) {recommendation[1]}."
        )
        return state


def run_once(message: str, user_id: str = "unknown") -> GraphState:
    """Local smoke-run for development."""
    engine = Orchestrator()
    state: GraphState = {
        "request_id": "demo-001",
        "text": message,
        "user_id": user_id,
        "channel": "teams",
        "thread_id": "thread-001",
    }

    for step in (
        engine.route,
        engine.load_memory,
        engine.collect_evidence,
        engine.synthesize,
        engine.apply_policy,
        engine.format_response,
    ):
        state = step(state)

    return state


if __name__ == "__main__":
    result = run_once("auth-prod lỗi tăng, có cần rollback không?")
    print(result["response"])
    print(result["policy_result"])
