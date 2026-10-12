"""Optional language-model adapter.

Deterministic extraction is the default and the fallback. An external model
may only propose a JSON interpretation. It cannot supply schedule math, and
its output is checked before anything is stored.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Protocol
from urllib import error, request

logger = logging.getLogger("projectverse.llm")

ALLOWED_TYPES = {
    "construction",
    "software",
    "manufacturing",
    "infrastructure",
    "urban",
    "logistics",
    "research",
    "event",
    "custom",
}


class RequirementModel(Protocol):
    def interpret(self, prompt: str) -> dict | None: ...


@dataclass
class LLMSettings:
    provider: str = "deterministic"
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    timeout_seconds: float = 20.0
    max_retries: int = 2


class DeterministicModel:
    def interpret(self, prompt: str) -> dict | None:
        return None


class OpenAICompatibleModel:
    def __init__(self, settings: LLMSettings):
        self.settings = settings

    def interpret(self, prompt: str) -> dict | None:
        if not self.settings.api_key or not self.settings.base_url:
            raise RuntimeError("LLM provider is not configured.")
        payload = {
            "model": self.settings.model or "gpt-4o-mini",
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract project facts as JSON with keys project_type, floors, basements, "
                        "gfa_sqm, budget_amount, currency, duration_months, team_size, location, name. "
                        "Use null when unknown. Do not invent quantities. Return JSON only."
                    ),
                },
                {"role": "user", "content": prompt[:20000]},
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        url = self.settings.base_url.rstrip("/") + "/chat/completions"
        last_error: Exception | None = None
        attempts = max(1, self.settings.max_retries + 1)
        for _ in range(attempts):
            req = request.Request(
                url,
                data=body,
                headers={
                    "Authorization": f"Bearer {self.settings.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=self.settings.timeout_seconds) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                content = raw["choices"][0]["message"]["content"]
                return _parse_model_json(content)
            except (error.URLError, TimeoutError, KeyError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                logger.warning("LLM attempt failed: %s", exc.__class__.__name__)
        raise RuntimeError("LLM request failed") from last_error


def _parse_model_json(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("LLM output was not an object.")
    cleaned: dict = {}
    project_type = parsed.get("project_type")
    if isinstance(project_type, str) and project_type in ALLOWED_TYPES:
        cleaned["project_type"] = project_type
    for key in ("floors", "basements", "team_size"):
        if isinstance(parsed.get(key), int) and not isinstance(parsed.get(key), bool):
            cleaned[key] = parsed[key]
    for key in ("gfa_sqm", "budget_amount", "duration_months"):
        if isinstance(parsed.get(key), (int, float)) and not isinstance(parsed.get(key), bool):
            cleaned[key] = float(parsed[key])
    for key in ("currency", "location", "name"):
        if isinstance(parsed.get(key), str) and parsed[key].strip():
            cleaned[key] = parsed[key].strip()[:200]
    return cleaned


def merge_model_hints(structured: dict, hints: dict | None) -> dict:
    """User-supplied structured fields win. Model hints fill only empty keys."""

    merged = dict(structured)
    if not hints:
        return merged
    for key, value in hints.items():
        if merged.get(key) in (None, ""):
            merged[key] = value
    return merged
