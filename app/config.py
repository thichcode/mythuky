from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "chatops-ai-service"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/chatops"

    prometheus_base_url: str = "http://localhost:9090"
    loki_base_url: str = "http://localhost:3100"

    rollback_error_rate_threshold: float = 0.05
    redis_latency_threshold_ms: float = 80.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


class IncidentMessage(BaseModel):
    user_id: str
    channel: str
    thread_id: str
    text: str
    service: str
    env: str


class ApprovalRequest(BaseModel):
    approver_id: str
    decision: str  # approve | edit | reject
    edited_scope: str | None = None
    rationale: str | None = None
