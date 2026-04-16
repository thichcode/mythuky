from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "chatops-ai-service"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/chatops"

    prometheus_base_url: str = "http://localhost:9090"
    loki_base_url: str = "http://localhost:3100"

    rollback_error_rate_threshold: float = 0.05
    redis_latency_threshold_ms: float = 80.0

    llm_enabled: bool = True
    llm_provider: str = "openai"  # openai | ollama
    llm_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: float = 12.0
    llm_temperature: float = 0.1

    openai_api_key: str = ""
    openai_base_url: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    auth_enabled: bool = True
    api_key: str = "change-me"

    http_max_retries: int = 2
    http_retry_backoff_seconds: float = 0.3

    log_level: str = "INFO"

    ollama_base_url: str = "http://localhost:11434"

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
