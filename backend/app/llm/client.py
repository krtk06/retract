"""LLM client abstraction and OpenAI-compatible implementation.

The adapter is endpoint-agnostic (works against OpenAI, Azure OpenAI, Ollama,
vLLM, LM Studio, or any OpenAI-compatible gateway). It returns structured JSON
validated by the caller; token usage is returned for the per-analysis cost
ledger. Logprobs are captured when the endpoint supports them and are used as a
raw confidence signal (calibrated in Phase 5).
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    logprob_confidence: float | None = None
    provider: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    name: str
    model: str

    def complete(
        self,
        system: str,
        user: str,
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "response",
    ) -> LLMResponse: ...


class OpenAICompatibleClient:
    """Chat Completions client with JSON-schema structured output + logprobs."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 120.0,
        max_retries: int = 2,
        temperature: float = 0.0,
        request_logprobs: bool = True,
        max_output_tokens: int = 4000,
    ) -> None:
        self.name = "openai"
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries
        self._temperature = temperature
        self._request_logprobs = request_logprobs
        self._max_output_tokens = max_output_tokens

    def complete(
        self,
        system: str,
        user: str,
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "response",
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_output_tokens,
        }
        if json_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": False, "schema": json_schema},
            }
        if self._request_logprobs:
            payload["logprobs"] = True
            payload["top_logprobs"] = 3

        response = self._post("/chat/completions", payload)
        choices = response.get("choices") or []
        if not choices:
            raise LLMError("LLM returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        usage = response.get("usage") or {}
        return LLMResponse(
            content=content,
            model=response.get("model", self.model),
            tokens_in=int(usage.get("prompt_tokens", 0)),
            tokens_out=int(usage.get("completion_tokens", 0)),
            logprob_confidence=_mean_logprob_confidence(choices[0]),
            provider=self.name,
            raw={"id": response.get("id"), "finish_reason": choices[0].get("finish_reason")},
        )

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(
                        f"{self._base_url}{path}",
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                if response.status_code >= 400:
                    body = response.text[:500]
                    # Some endpoints reject json_schema / logprobs: retry without them.
                    if response.status_code in (400, 404, 422) and "response_format" in payload:
                        logger.warning(
                            "endpoint rejected response_format, retrying as text: %s", body
                        )
                        payload = {k: v for k, v in payload.items() if k != "response_format"}
                        continue
                    if response.status_code in (400, 404, 422) and "logprobs" in payload:
                        logger.warning("endpoint rejected logprobs, retrying without: %s", body)
                        payload = {k: v for k, v in payload.items() if k != "logprobs"}
                        payload.pop("top_logprobs", None)
                        continue
                    raise LLMError(f"LLM HTTP {response.status_code}: {body}")
                return response.json()
            except (httpx.HTTPError, ValueError, LLMError) as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                logger.warning("LLM request failed (attempt %s): %s", attempt + 1, exc)
        raise LLMError(f"LLM request failed after retries: {last_error}")


def _mean_logprob_confidence(choice: dict[str, Any]) -> float | None:
    """Average token probability as a raw confidence signal (0-1)."""
    content = (choice.get("logprobs") or {}).get("content") or []
    probabilities = [item.get("probability") for item in content if item.get("probability")]
    if not probabilities:
        return None
    return sum(probabilities) / len(probabilities)


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def set_llm_client(client: LLMClient | None) -> None:
    """Test helper: inject a client (e.g. a scripted mock)."""
    global _client
    _client = client


def _build_client() -> LLMClient:
    from app.llm.mock import HeuristicMockLLM

    settings = get_settings()
    provider = settings.llm_provider.lower()
    if provider == "mock":
        logger.warning("LLM provider is 'mock' — deterministic offline harness, NOT real analysis")
        return HeuristicMockLLM()
    if provider == "openai":
        if not settings.llm_api_key:
            raise LLMError(
                "AI_INTEL_LLM_API_KEY is required for the openai provider "
                "(set AI_INTEL_LLM_PROVIDER=mock for the offline harness)"
            )
        return OpenAICompatibleClient(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            temperature=settings.llm_temperature,
            request_logprobs=settings.llm_request_logprobs,
            max_output_tokens=settings.agent_max_output_tokens,
        )
    raise LLMError(f"Unknown AI_INTEL_LLM_PROVIDER: {settings.llm_provider}")


def parse_json_object(content: str) -> dict[str, Any]:
    """Extract a JSON object from a model response (tolerates code fences/prose)."""
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise LLMError("Response is not valid JSON") from None
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise LLMError("Response JSON is not an object")
    return data
