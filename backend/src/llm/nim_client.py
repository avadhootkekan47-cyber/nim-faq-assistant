"""
src/llm/nim_client.py
─────────────────────
Generic async client for NVIDIA NIM chat completions endpoint.
Endpoint assumption: POST {NIM_BASE_URL}/chat/completions
(OpenAI-compatible — adjust NIM_BASE_URL in .env if your NIM deployment
uses a different path prefix, e.g. /v1 is appended automatically by the
client if the URL does not already end with /v1.)
"""

import logging
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.config import settings

logger = logging.getLogger(__name__)

Message = dict[str, str]   # {"role": "user"|"system"|"assistant", "content": "..."}


def _should_retry(exc: BaseException) -> bool:
    """Retry on network errors, 429, and 5xx responses."""
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, NIMError) and exc.status_code in {429, 500, 502, 503, 504}:
        return True
    return False


class NIMError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(f"NIM API error {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class NIMClient:
    """
    Thin async wrapper around the NIM /chat/completions endpoint.
    One shared httpx.AsyncClient is reused across requests (connection pooling).
    Call .aclose() on app shutdown.
    """

    def __init__(self):
        base = settings.nim_base_url.rstrip("/")
        # Ensure the path ends with /v1 (OpenAI-compatible NIM convention)
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        self._base = base
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {settings.nim_api_key}",
                "Content-Type": "application/json",
            },
            timeout=settings.llm_timeout,
        )

    async def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """
        Send a chat completion request and return the assistant reply as a string.
        Falls back to settings defaults for any unset params.
        """
        payload: dict[str, Any] = {
            "model": model or settings.nim_model,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.llm_temperature,
            "max_tokens": max_tokens if max_tokens is not None else settings.llm_max_tokens,
            "top_p": top_p if top_p is not None else settings.llm_top_p,
        }
        if extra:
            payload.update(extra)

        url = f"{self._base}/chat/completions"
        logger.debug("NIM request → model=%s messages=%d", payload["model"], len(messages))

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(settings.llm_max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=16),
            retry=retry_if_exception(_should_retry),
            reraise=True,
        ):
            with attempt:
                response = await self._client.post(url, json=payload)

        if response.status_code != 200:
            raise NIMError(response.status_code, response.text[:500])

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise NIMError(200, f"Unexpected response shape: {e} — {data}") from e

        logger.debug("NIM response ← %d chars", len(content))
        return content.strip()

    async def aclose(self) -> None:
        await self._client.aclose()


# ── Module-level singleton ─────────────────────────────────────────────────────
nim_client = NIMClient()
