from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import httpx

from app.logging_utils import get_logger


logger = get_logger(__name__)


class PrometheusAdapter:
    def __init__(self, base_url: str, max_retries: int = 2, retry_backoff_seconds: float = 0.3) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    def _get_with_retry(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=5.0) as client:
                    response = client.get(f"{self.base_url}{path}", params=params)
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning(
                    "prometheus_request_failed",
                    extra={"attempt": attempt, "path": path, "error": str(exc)},
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))

        raise RuntimeError(f"prometheus request failed after retries: {last_exc}")

class PrometheusAdapter:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def query_error_rate(self, service: str, env: str) -> Dict[str, Any]:
        query = (
            'sum(rate(http_requests_total{service="%s",env="%s",status=~"5.."}[5m])) '
            '/ sum(rate(http_requests_total{service="%s",env="%s"}[5m]))'
        ) % (service, env, service, env)
        data = self._get_with_retry("/api/v1/query", {"query": query})
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{self.base_url}/api/v1/query", params={"query": query})
            response.raise_for_status()
            data = response.json()
        result = data.get("data", {}).get("result", [])
        value = float(result[0]["value"][1]) if result else 0.0
        return {"error_rate": value, "raw": data}


class LokiAdapter:
    def __init__(self, base_url: str, max_retries: int = 2, retry_backoff_seconds: float = 0.3) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    def _get_with_retry(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=5.0) as client:
                    response = client.get(f"{self.base_url}{path}", params=params)
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning(
                    "loki_request_failed",
                    extra={"attempt": attempt, "path": path, "error": str(exc)},
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))

        raise RuntimeError(f"loki request failed after retries: {last_exc}")
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def query_redis_latency(self, service: str, window_minutes: int = 30) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        start = now - timedelta(minutes=window_minutes)
        query = f'{{service="{service}"}} |= "redis latency"'
        params = {
            "query": query,
            "start": str(int(start.timestamp() * 1_000_000_000)),
            "end": str(int(now.timestamp() * 1_000_000_000)),
            "limit": "200",
            "direction": "backward",
        }
        data = self._get_with_retry("/loki/api/v1/query_range", params)
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{self.base_url}/loki/api/v1/query_range", params=params)
            response.raise_for_status()
            data = response.json()

        streams = data.get("data", {}).get("result", [])
        matched_lines = sum(len(stream.get("values", [])) for stream in streams)
        estimated_latency_ms = 120.0 if matched_lines > 0 else 10.0
        return {
            "redis_latency_ms_estimate": estimated_latency_ms,
            "matched_log_lines": matched_lines,
            "raw": data,
        }
