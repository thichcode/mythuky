from __future__ import annotations

import json
from typing import Any, Dict

import httpx
from openai import OpenAI

from app.config import Settings


class LLMUnavailableError(RuntimeError):
    pass


class LLMAdvisor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def suggest(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.settings.llm_enabled:
            raise LLMUnavailableError("llm is disabled")

        provider = self.settings.llm_provider.lower()
        if provider == "openai":
            return self._suggest_openai(context)
        if provider == "ollama":
            return self._suggest_ollama(context)

        raise LLMUnavailableError(f"unsupported llm provider: {self.settings.llm_provider}")

    def _suggest_openai(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.settings.openai_api_key:
            raise LLMUnavailableError("OPENAI_API_KEY is missing")

        client = OpenAI(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
            timeout=self.settings.llm_timeout_seconds,
        )

        system_prompt = (
            "You are an SRE incident assistant. Return compact JSON with keys: "
            "summary, recommendation, risk, confidence (0-1)."
        )

        completion = client.chat.completions.create(
            model=self.settings.llm_model,
            temperature=self.settings.llm_temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ],
        )

        content = completion.choices[0].message.content or "{}"
        payload = json.loads(content)
        payload["provider"] = "openai"
        payload["model"] = self.settings.llm_model
        return payload

    def _suggest_ollama(self, context: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "model": self.settings.llm_model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an SRE incident assistant. Return compact JSON with keys: "
                        "summary, recommendation, risk, confidence (0-1)."
                    ),
                },
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ],
            "options": {"temperature": self.settings.llm_temperature},
        }

        with httpx.Client(timeout=self.settings.llm_timeout_seconds) as client:
            response = client.post(f"{self.settings.ollama_base_url.rstrip('/')}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

        content = data.get("message", {}).get("content", "{}")
        parsed = json.loads(content)
        parsed["provider"] = "ollama"
        parsed["model"] = self.settings.llm_model
        return parsed
