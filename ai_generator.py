import asyncio
import ast
import html
import json
import os
import re
import math
import subprocess
import time
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Callable, Awaitable
from urllib.parse import quote

import aiohttp
import pytz

from db import (
    DB_WRITE_LOCK,
    get_conn,
    copy_daily_tests_bank_rows_to_arena_questions,
    _is_postgres_enabled,
    ensure_vocab_seed_pool_schema,
    upsert_vocab_seed_pool_items,
    pull_seed_candidates,
)
from logging_config import get_logger
from vocabulary import vocab_language_for_subject



def get_gemini_model():
    return "gemini-2.5-flash"   # Bu yerni o‘zgartirib turasiz

GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{get_gemini_model()}:generateContent"

# --- xAI / Grok provider (replace Gemini at runtime) ---
def get_grok_model_candidates() -> list[str]:
    """
    Resolve xAI model candidates in priority order.
    Keeps behavior configurable via env while providing safe fallbacks when a model is retired.
    """
    raw_primary = str(os.getenv("XAI_MODEL") or "").strip()
    raw_fallbacks = str(os.getenv("XAI_MODEL_FALLBACKS") or "").strip()
    defaults = [
        "grok-4-1-fast-reasoning",
        "grok-4-1-fast-reasoning-latest",
        "grok-4-1-fast",
        "grok-4.3",
        "grok-4-fast-reasoning",
        "grok-4-fast-reasoning-latest",
        "grok-4",
        "grok-4-latest",
        "grok-3",
        "grok-3-latest",
        "grok-3-mini",
        "grok-3-mini-latest",
        "grok-beta",
        "grok-2-latest",
    ]
    ordered: list[str] = []
    if raw_primary:
        ordered.append(raw_primary)
    if raw_fallbacks:
        ordered.extend([part.strip() for part in raw_fallbacks.split(",") if part.strip()])
    ordered.extend(defaults)
    # Deduplicate while preserving order.
    out: list[str] = []
    seen: set[str] = set()
    for model in ordered:
        if model in seen:
            continue
        seen.add(model)
        out.append(model)
    return out

XAI_ENDPOINT = "https://api.x.ai/v1/chat/completions"
X_GROK_CONV_ID = "diamond-education-ai-generator-v1"

logger = get_logger(__name__)

XAI_TRANSIENT_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504, 529}


def _xai_reasoning_effort() -> str:
    raw = str(os.getenv("XAI_REASONING_EFFORT") or "low").strip().lower()
    if raw in {"none", "low", "medium", "high"}:
        return raw
    return "low"


def _xai_model_supports_reasoning_effort(model: str) -> bool:
    normalized = str(model or "").lower()
    return any(
        marker in normalized
        for marker in (
            "grok-4.3",
            "grok-4-1-fast",
            "grok-4-fast-reasoning",
            "grok-4.20",
        )
    )


def _xai_image_detail() -> str:
    raw = str(os.getenv("XAI_IMAGE_DETAIL") or "low").strip().lower()
    if raw in {"low", "high", "auto"}:
        return raw
    return "low"


def _xai_apply_payload_tuning(payload: dict[str, Any], *, model: str, stream: bool) -> dict[str, Any]:
    if _xai_model_supports_reasoning_effort(model):
        payload["reasoning_effort"] = _xai_reasoning_effort()
    if stream:
        payload["stream_options"] = {"include_usage": True}
    return payload


def _xai_usage_value(usage: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = usage.get(key)
        if value is not None:
            return value
    for detail_key in ("prompt_tokens_details", "input_tokens_details", "completion_tokens_details", "output_tokens_details"):
        details = usage.get(detail_key)
        if isinstance(details, dict):
            for key in keys:
                value = details.get(key)
                if value is not None:
                    return value
    return None


def _xai_log_usage(usage: Any, *, model: str, stream: bool, conv_id: str = X_GROK_CONV_ID) -> None:
    try:
        if not isinstance(usage, dict) or not usage:
            return
        prompt_tokens = _xai_usage_value(usage, "prompt_tokens", "input_tokens")
        completion_tokens = _xai_usage_value(usage, "completion_tokens", "output_tokens")
        cached_tokens = _xai_usage_value(usage, "cached_tokens")
        image_tokens = _xai_usage_value(usage, "image_tokens")
        reasoning_tokens = _xai_usage_value(usage, "reasoning_tokens")
        cached_pct = None
        if isinstance(prompt_tokens, int) and prompt_tokens > 0 and isinstance(cached_tokens, int) and cached_tokens >= 0:
            cached_pct = round((cached_tokens * 100.0) / prompt_tokens, 2)
        logger.info(
            "xai usage model=%s stream=%s prompt_tokens=%s completion_tokens=%s cached_tokens=%s image_tokens=%s reasoning_tokens=%s cached_pct=%s conv_id=%s",
            model,
            int(bool(stream)),
            prompt_tokens,
            completion_tokens,
            cached_tokens,
            image_tokens,
            reasoning_tokens,
            cached_pct,
            conv_id,
        )
    except Exception:
        pass


def _xai_retry_attempts() -> int:
    try:
        return max(1, min(8, int(os.getenv("XAI_TRANSIENT_RETRY_ATTEMPTS") or "5")))
    except Exception:
        return 5


def _xai_retry_delays() -> list[float]:
    raw = str(os.getenv("XAI_TRANSIENT_RETRY_DELAYS") or "").strip()
    if raw:
        values: list[float] = []
        for part in raw.split(","):
            try:
                value = float(part.strip())
            except Exception:
                continue
            if value >= 0:
                values.append(min(value, 30.0))
        if values:
            return values
    return [2.0, 5.0, 10.0, 18.0]


def _is_xai_model_missing_error(error_text: str) -> bool:
    normalized = error_text.lower()
    return ("model not found" in normalized) or ("invalid argument" in normalized and "model" in normalized)


def _is_xai_transient_error(status: int, error_text: str) -> bool:
    normalized = error_text.lower()
    if status in XAI_TRANSIENT_STATUS_CODES:
        return True
    return any(
        marker in normalized
        for marker in (
            "capacity",
            "resource has been exhausted",
            "rate limit",
            "too many requests",
            "temporarily unavailable",
            "try again",
            "overloaded",
        )
    )


def _xai_transient_user_message() -> str:
    return "Grok API vaqtincha band. Bir necha daqiqadan keyin qayta urinib ko'ring."


def _xai_log_preview(value: Any, *, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


_ADULT_TOKEN_RE = re.compile(
    r"\b("
    r"sex|sexy|sexual|porn|porno|nude|nudity|xxx|erotic|fetish|"
    r"masturbat|orgasm|genital|penis|vagina|boobs?|breast|"
    r"jinsiy|yalang|yalangoch|pornograf|"
    r"секс|сексуал|порно|эротик|обнажен|голый|мастурб|пенис|вагин"
    r")\b",
    re.I,
)

_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def _normalize_text_for_safety(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def _contains_adult_content(parts: list[Any]) -> bool:
    for p in parts:
        txt = _normalize_text_for_safety(p)
        if not txt:
            continue
        if _ADULT_TOKEN_RE.search(txt):
            return True
    return False


def _has_cyrillic_text(value: Any) -> bool:
    return bool(_CYRILLIC_RE.search(str(value or "")))


def _has_latin_text(value: Any) -> bool:
    return bool(_LATIN_RE.search(str(value or "")))


def _is_russian_text_valid(value: Any, *, allow_empty: bool = False) -> bool:
    txt = str(value or "").strip()
    if not txt:
        return bool(allow_empty)
    # Russian fields must be native Cyrillic (no transliteration).
    if not _has_cyrillic_text(txt):
        return False
    if _has_latin_text(txt):
        return False
    return True


def _is_valid_russian_vocab_item(item: dict[str, Any]) -> bool:
    return (
        _is_russian_text_valid(item.get("word"))
        and _is_russian_text_valid(item.get("definition"))
        and _is_russian_text_valid(item.get("example"))
        and _is_russian_text_valid(item.get("translation_ru"), allow_empty=True)
    )


def _get_xai_api_key() -> str:
    key = os.getenv("XAI_API_KEY") or ""
    if not key:
        raise RuntimeError("XAI_API_KEY .env faylda topilmadi! Iltimos qo'shing.")
    return key


async def _call_xai(
    *,
    prompt: str,
    session: aiohttp.ClientSession,
    system_content: str,
    temperature: float,
    max_tokens: int,
) -> str:
    api_key = _get_xai_api_key()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        # Keep a stable conversation id to improve prompt caching hits.
        "x-grok-conv-id": X_GROK_CONV_ID,
    }

    last_error: RuntimeError | None = None
    last_transient_error: RuntimeError | None = None
    data: dict[str, Any] | None = None
    used_model = ""
    model_candidates = get_grok_model_candidates()
    retry_attempts = _xai_retry_attempts()
    retry_delays = _xai_retry_delays()
    transient_fallback_limit = max(1, min(3, len(model_candidates)))
    call_started = time.monotonic()
    logger.info(
        "xai request queued stream=0 prompt_chars=%s system_chars=%s max_tokens=%s temperature=%s candidates=%s attempts=%s conv_id=%s",
        len(prompt or ""),
        len(system_content or ""),
        int(max_tokens),
        float(temperature),
        len(model_candidates),
        retry_attempts,
        X_GROK_CONV_ID,
    )
    for attempt in range(1, retry_attempts + 1):
        transient_seen = False
        for model_index, model in enumerate(model_candidates):
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_content,
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": float(temperature),
                "max_tokens": int(max_tokens),
            }
            _xai_apply_payload_tuning(payload, model=model, stream=False)
            attempt_started = time.monotonic()
            logger.info(
                "xai request attempt stream=0 model=%s attempt=%s/%s fallback_index=%s max_tokens=%s temperature=%s",
                model,
                attempt,
                retry_attempts,
                model_index,
                int(max_tokens),
                float(temperature),
            )
            async with session.post(
                XAI_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=150),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    used_model = model
                    logger.info(
                        "xai request http_ok stream=0 model=%s attempt=%s/%s fallback_index=%s elapsed_ms=%s",
                        model,
                        attempt,
                        retry_attempts,
                        model_index,
                        int((time.monotonic() - attempt_started) * 1000),
                    )
                    break
                error_text = await resp.text()
                error_sample = _xai_log_preview(error_text)
                if _is_xai_model_missing_error(error_text):
                    logger.warning(
                        "xai model unavailable stream=0 model=%s status=%s switching_fallback=1 error_sample=%s",
                        model,
                        resp.status,
                        error_sample,
                    )
                    last_error = RuntimeError(f"Grok API error {resp.status}: {error_text[:300]}")
                    continue
                if _is_xai_transient_error(resp.status, error_text):
                    transient_seen = True
                    last_transient_error = RuntimeError(f"Grok API error {resp.status}: {error_text[:300]}")
                    logger.warning(
                        "xai transient error stream=0 model=%s status=%s attempt=%s/%s fallback_index=%s error_sample=%s",
                        model,
                        resp.status,
                        attempt,
                        retry_attempts,
                        model_index,
                        error_sample,
                    )
                    if model_index + 1 < transient_fallback_limit:
                        continue
                    break
                logger.error(
                    "xai request failed stream=0 model=%s status=%s attempt=%s/%s fallback_index=%s error_sample=%s",
                    model,
                    resp.status,
                    attempt,
                    retry_attempts,
                    model_index,
                    error_sample,
                )
                raise RuntimeError(f"Grok API error {resp.status}: {error_text[:300]}")
        if data is not None:
            break
        if transient_seen and attempt < retry_attempts:
            await asyncio.sleep(retry_delays[min(attempt - 1, len(retry_delays) - 1)])
            continue
        if not transient_seen:
            break
    if data is None:
        if last_transient_error:
            logger.error("xai transient retries exhausted: %s", last_transient_error)
            raise RuntimeError(_xai_transient_user_message())
        if last_error:
            raise last_error
        raise RuntimeError("Grok API error: no model candidate succeeded")

    _xai_log_usage(data.get("usage") if isinstance(data, dict) else {}, model=used_model, stream=False)

    # Typical xAI/OpenAI-compatible shape:
    # { "choices": [ { "message": { "content": "..." } } ] }
    try:
        content = str(data["choices"][0]["message"]["content"]).strip()
        logger.info(
            "xai request completed stream=0 model=%s elapsed_ms=%s response_chars=%s conv_id=%s",
            used_model,
            int((time.monotonic() - call_started) * 1000),
            len(content),
            X_GROK_CONV_ID,
        )
        return content
    except Exception:
        # Keep error readable for logs.
        raise RuntimeError(f"Grok API xatosi: response shape unexpected: {type(data)} | {data}")


async def _xai_generate(prompt: str, *, session: aiohttp.ClientSession) -> str:
    """
    JSON-only xAI generation for banked question/vocabulary pipelines.
    """
    return await _call_xai(
        prompt=prompt,
        session=session,
        system_content=(
            "You are a strict JSON-only generator. "
            "Return ONLY a valid JSON array. "
            "No explanations, no markdown, no ```json, no extra text."
        ),
        temperature=0.3,
        max_tokens=16000,
    )


async def _xai_generate_text(prompt: str, *, session: aiohttp.ClientSession, temperature: float = 0.65, system_content: str = None) -> str:
    """
    Plain-text xAI generation for Diamondvoy chat/classifier flows.
    """
    return await _call_xai(
        prompt=prompt,
        session=session,
        system_content=system_content or (
            "You are a helpful assistant. "
            "Follow user language instructions strictly and return plain text only."
        ),
        temperature=temperature,
        max_tokens=16000,
    )


async def _call_xai_stream(
    *,
    prompt: str,
    session: aiohttp.ClientSession,
    system_content: str,
    temperature: float,
    max_tokens: int,
):
    api_key = _get_xai_api_key()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "x-grok-conv-id": X_GROK_CONV_ID,
    }

    last_error: RuntimeError | None = None
    last_transient_error: RuntimeError | None = None
    model_candidates = get_grok_model_candidates()
    retry_attempts = _xai_retry_attempts()
    retry_delays = _xai_retry_delays()
    transient_fallback_limit = max(1, min(3, len(model_candidates)))
    for attempt in range(1, retry_attempts + 1):
        transient_seen = False
        for model_index, model in enumerate(model_candidates):
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_content,
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": float(temperature),
                "max_tokens": int(max_tokens),
                "stream": True,
            }
            _xai_apply_payload_tuning(payload, model=model, stream=True)
            async with session.post(
                XAI_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=150),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    if _is_xai_model_missing_error(error_text):
                        logger.warning("xai stream model unavailable model=%s status=%s switching_fallback=1", model, resp.status)
                        last_error = RuntimeError(f"Grok API error {resp.status}: {error_text[:300]}")
                        continue
                    if _is_xai_transient_error(resp.status, error_text):
                        transient_seen = True
                        last_transient_error = RuntimeError(f"Grok API error {resp.status}: {error_text[:300]}")
                        logger.warning(
                            "xai stream transient error model=%s status=%s attempt=%s/%s fallback_index=%s",
                            model,
                            resp.status,
                            attempt,
                            retry_attempts,
                            model_index,
                        )
                        if model_index + 1 < transient_fallback_limit:
                            continue
                        break
                    raise RuntimeError(f"Grok API error {resp.status}: {error_text[:300]}")
                logger.info("xai stream using model=%s conv_id=%s", model, X_GROK_CONV_ID)
                usage_seen: dict[str, Any] | None = None
                async for line in resp.content:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith(b"data: "):
                        data_str = line[6:].decode("utf-8", errors="ignore")
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            usage = data.get("usage")
                            if isinstance(usage, dict) and usage:
                                usage_seen = usage
                            delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if delta:
                                yield delta
                        except Exception:
                            pass
                if usage_seen:
                    _xai_log_usage(usage_seen, model=model, stream=True)
                return
        if transient_seen and attempt < retry_attempts:
            await asyncio.sleep(retry_delays[min(attempt - 1, len(retry_delays) - 1)])
            continue
        if not transient_seen:
            break
    if last_transient_error:
        logger.error("xai stream transient retries exhausted: %s", last_transient_error)
        raise RuntimeError(_xai_transient_user_message())
    if last_error:
        raise last_error
    raise RuntimeError("Grok API stream error: no model candidate succeeded")


async def _xai_generate_text_stream(prompt: str, *, session: aiohttp.ClientSession, temperature: float = 0.65, system_content: str = None):
    """
    Streaming xAI text generation, matching _xai_generate_text defaults.
    """
    async for chunk in _call_xai_stream(
        prompt=prompt,
        session=session,
        system_content=system_content or (
            "You are a helpful assistant. "
            "Follow user language instructions strictly and return plain text only."
        ),
        temperature=temperature,
        max_tokens=16000,
    ):
        yield chunk


async def _xai_generate_text_stream_with_images(
    prompt: str,
    image_urls: list[str],
    *,
    session: aiohttp.ClientSession,
):
    """
    OpenAI-compatible vision streaming for xAI/Grok.
    Falls back through configured Grok model candidates like text streaming.
    """
    api_key = _get_xai_api_key()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "x-grok-conv-id": X_GROK_CONV_ID,
    }
    content: list[dict[str, Any]] = [{"type": "text", "text": str(prompt or "")}]
    image_detail = _xai_image_detail()
    for url in (image_urls or [])[:3]:
        clean_url = str(url or "").strip()
        if clean_url:
            content.append({"type": "image_url", "image_url": {"url": clean_url, "detail": image_detail}})

    system_content = (
        "You are Diamondvoy, a school tutoring assistant. "
        "Analyze attached images only when they are educational materials "
        "(tests, grammar, reading, math problems, homework, books, notebooks, or study material). "
        "If an image is not educational, refuse briefly. Return plain text only."
    )

    last_error: RuntimeError | None = None
    last_transient_error: RuntimeError | None = None
    model_candidates = get_grok_model_candidates()
    retry_attempts = _xai_retry_attempts()
    retry_delays = _xai_retry_delays()
    transient_fallback_limit = max(1, min(3, len(model_candidates)))
    for attempt in range(1, retry_attempts + 1):
        transient_seen = False
        for model_index, model in enumerate(model_candidates):
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": content},
                ],
                "temperature": 0.55,
                "max_tokens": 12000,
                "stream": True,
            }
            _xai_apply_payload_tuning(payload, model=model, stream=True)
            async with session.post(
                XAI_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=150),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    if _is_xai_model_missing_error(error_text):
                        last_error = RuntimeError(f"Grok API error {resp.status}: {error_text[:300]}")
                        continue
                    if _is_xai_transient_error(resp.status, error_text):
                        transient_seen = True
                        last_transient_error = RuntimeError(f"Grok API error {resp.status}: {error_text[:300]}")
                        if model_index + 1 < transient_fallback_limit:
                            continue
                        break
                    raise RuntimeError(f"Grok API error {resp.status}: {error_text[:300]}")
                logger.info("xai vision stream using model=%s image_detail=%s conv_id=%s", model, image_detail, X_GROK_CONV_ID)
                usage_seen: dict[str, Any] | None = None
                async for line in resp.content:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith(b"data: "):
                        data_str = line[6:].decode("utf-8", errors="ignore")
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            usage = data.get("usage")
                            if isinstance(usage, dict) and usage:
                                usage_seen = usage
                            delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if delta:
                                yield delta
                        except Exception:
                            pass
                if usage_seen:
                    _xai_log_usage(usage_seen, model=model, stream=True)
                return
        if transient_seen and attempt < retry_attempts:
            await asyncio.sleep(retry_delays[min(attempt - 1, len(retry_delays) - 1)])
            continue
        if not transient_seen:
            break
    if last_transient_error:
        raise RuntimeError(_xai_transient_user_message())
    if last_error:
        raise last_error
    raise RuntimeError("Grok vision stream error: no model candidate succeeded")



@dataclass(frozen=True)
class GenerationResult:
    requested: int
    generated: int
    inserted: int
    skipped: int = 0
    attempts: int = 0
    skipped_existing: int = 0
    skipped_invalid: int = 0
    inserted_from_seed: int = 0
    inserted_from_ai: int = 0
    raw_parse_warnings: tuple[str, ...] = ()
    completed: bool = True
    note: str = ""


_ai_generation_locks: dict[tuple[str, str], asyncio.Lock] = {}


def _get_gemini_api_key() -> str:
    # Support a few common env var names.
    return (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GOOGLE_GENAI_API_KEY")
        or ""
    )


def _balanced_json_slice(s: str, start: int, open_char: str, close_char: str) -> str | None:
    """`start` indeksidagi ochuvchi belgidan boshlab to'g'ri yopiladigan JSON bo'lagini qaytaradi."""
    depth = 0
    in_str = False
    esc = False
    quote: str | None = None
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
                quote = None
            continue
        if ch in "\"'":
            in_str = True
            quote = ch
            continue
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


def _balanced_json_array_slice(s: str, start: int) -> str | None:
    """`start` — '[' indeksi; qator ichidagi qavslar va string escape larni hisobga oladi."""
    return _balanced_json_slice(s, start, "[", "]")


def _balanced_json_object_slice(s: str, start: int) -> str | None:
    """`start` — '{' indeksi; qator ichidagi qavslar va string escape larni hisobga oladi."""
    return _balanced_json_slice(s, start, "{", "}")


def _sanitize_json_like_text(text: str) -> str:
    # LLM responses sometimes include BOM or typographic quotes that break strict JSON parsing.
    return (
        (text or "")
        .strip()
        .lstrip("\ufeff")
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )


def _extract_list_from_payload(payload: Any, *, _depth: int = 0) -> list[Any] | None:
    if _depth > 8:
        return None

    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        # Common wrapper keys returned by some models.
        priority_keys = (
            "items",
            "questions",
            "daily_tests",
            "tests",
            "data",
            "result",
            "results",
        )
        for key in priority_keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
        for value in payload.values():
            found = _extract_list_from_payload(value, _depth=_depth + 1)
            if found is not None:
                return found
        return None

    if isinstance(payload, str):
        return _parse_json_like_to_list(payload, _depth=_depth + 1)

    return None


def _parse_json_like_to_list(raw_text: str, *, _depth: int = 0) -> list[Any] | None:
    if _depth > 8:
        return None
    raw = _sanitize_json_like_text(raw_text)
    if not raw:
        return None

    candidates = [raw]
    # Common malformed JSON from LLMs: trailing commas before ] or }.
    trailing_commas_fixed = re.sub(r",\s*([}\]])", r"\1", raw)
    if trailing_commas_fixed != raw:
        candidates.append(trailing_commas_fixed)

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        found = _extract_list_from_payload(parsed, _depth=_depth + 1)
        if found is not None:
            return found

    # Fallback for Python-like literals (single quotes, True/False/None).
    for candidate in candidates:
        try:
            parsed = ast.literal_eval(candidate)
        except Exception:
            # Try converting JSON tokens to Python tokens for literal_eval.
            py_candidate = re.sub(r"\bnull\b", "None", candidate)
            py_candidate = re.sub(r"\btrue\b", "True", py_candidate, flags=re.IGNORECASE)
            py_candidate = re.sub(r"\bfalse\b", "False", py_candidate, flags=re.IGNORECASE)
            try:
                parsed = ast.literal_eval(py_candidate)
            except Exception:
                continue
        found = _extract_list_from_payload(parsed, _depth=_depth + 1)
        if found is not None:
            return found

    return None


def _extract_json_array(text: str) -> list[Any]:
    """Gemini javobidan JSON array ni ishonchli ajratadi (markdown, prose, code block)."""
    if not text:
        return []

    raw = _sanitize_json_like_text(text)
    if not raw:
        return []

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, re.IGNORECASE)
    fence_inner = _sanitize_json_like_text(fence.group(1)) if fence else ""

    candidate_texts = []
    if fence_inner:
        candidate_texts.append(fence_inner)
    if raw:
        candidate_texts.append(raw)

    for candidate in candidate_texts:
        parsed = _parse_json_like_to_list(candidate)
        if parsed is not None:
            return parsed

    # If there's prose around JSON, scan every balanced array/object segment.
    for candidate in candidate_texts:
        for m in re.finditer(r"\[", candidate):
            arr_slice = _balanced_json_array_slice(candidate, m.start())
            if not arr_slice:
                continue
            parsed = _parse_json_like_to_list(arr_slice)
            if parsed is not None:
                return parsed
        for m in re.finditer(r"\{", candidate):
            obj_slice = _balanced_json_object_slice(candidate, m.start())
            if not obj_slice:
                continue
            parsed = _parse_json_like_to_list(obj_slice)
            if parsed is not None:
                return parsed

    raise ValueError("Could not find valid JSON array in Gemini response.")


_JSON_ONLY_PREFIX = """You are a JSON-only generator.
Return **ONLY** a valid JSON array. No explanations, no markdown, no ```json.

"""


def _wrap_json_only_prompt(rules: str) -> str:
    return _JSON_ONLY_PREFIX + rules.strip()


def levels_for_ai_generation(subject: str) -> list[str]:
    """Inline keyboard levels for admin/teacher AI Generator (no MIXED button)."""
    return ["Beginner", "Elementary", "Pre-Intermediate", "Intermediate", "Upper-Intermediate", "Advanced"]


def allowed_levels_for_ai_pipeline(subject: str) -> set[str]:
    """Superset for generate_* and arena: UI levels plus MIXED for internal mixed-difficulty runs."""
    return {lvl.upper() for lvl in levels_for_ai_generation(subject)} | {"MIXED"}


def _normalize_level(level: str) -> str:
    return (level or "").strip().upper()


def _normalize_generated_level(level: str) -> str:
    lv = _normalize_level(level)
    return lv if lv in {"BEGINNER", "ELEMENTARY", "PRE-INTERMEDIATE", "INTERMEDIATE", "UPPER-INTERMEDIATE", "ADVANCED"} else "BEGINNER"


def _normalize_russian_bank_level(model_level: str | None, selected: str) -> str:
    """Store Russian rows with the same CEFR tiers as English."""
    sel = _normalize_level(selected)
    gl = _normalize_level(str(model_level or ""))
    valid_levels = ("BEGINNER", "ELEMENTARY", "PRE-INTERMEDIATE", "INTERMEDIATE", "UPPER-INTERMEDIATE", "ADVANCED")
    if sel == "MIXED":
        return gl if gl in valid_levels else "INTERMEDIATE"
    if gl in valid_levels:
        return gl
    if sel in valid_levels:
        return sel
    return "BEGINNER"


def _subject_to_vocab_language(subject: str) -> str:
    # In this codebase:
    # - English subject => words.language == 'en'
    # - Russian subject => words.language == 'ru'
    subj = (subject or "").strip().lower()
    if "russian" in subj:
        return "ru"
    return "en"


async def _gemini_generate(prompt: str, *, session: aiohttp.ClientSession) -> str:
    """
    Backwards-compatible wrapper.

    Historically this project used Gemini; now we route the same prompt flow
    through xAI (Grok) so the rest of the generation logic stays unchanged.
    """
    return await _xai_generate(prompt, session=session)


def _partition_list(items: list[Any], size: int) -> list[list[Any]]:
    if size <= 0:
        size = len(items) or 1
    return [items[i : i + size] for i in range(0, len(items), size)]


def _env_int(name: str, default: int, *, min_value: int = 1, max_value: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        val = int(str(raw).strip())
    except Exception:
        return default
    if val < min_value:
        return min_value
    if max_value is not None and val > max_value:
        return max_value
    return val


AI_VOCAB_INSERT_BATCH_SIZE = _env_int("AI_VOCAB_INSERT_BATCH_SIZE", 50, min_value=1, max_value=5000)
AI_VOCAB_OVERSAMPLE_FACTOR = _env_int("AI_VOCAB_OVERSAMPLE_FACTOR", 3, min_value=1, max_value=20)
AI_VOCAB_MAX_ATTEMPTS = _env_int("AI_VOCAB_MAX_ATTEMPTS", 20, min_value=1, max_value=10000)
AI_VOCAB_MAX_BATCH_SIZE = _env_int("AI_VOCAB_MAX_BATCH_SIZE", 50, min_value=10, max_value=1000)
AI_VOCAB_NO_PROGRESS_LIMIT = _env_int("AI_VOCAB_NO_PROGRESS_LIMIT", 5, min_value=1, max_value=20)
AI_VOCAB_SEED_REFRESH_FETCH_LIMIT = _env_int("AI_VOCAB_SEED_REFRESH_FETCH_LIMIT", 2500, min_value=100, max_value=10000)
AI_VOCAB_SEED_HTTP_TIMEOUT_SEC = _env_int("AI_VOCAB_SEED_HTTP_TIMEOUT_SEC", 20, min_value=5, max_value=120)
AI_VOCAB_EXISTING_CACHE_TTL_SEC = _env_int("AI_VOCAB_EXISTING_CACHE_TTL_SEC", 180, min_value=10, max_value=3600)
AI_VOCAB_PROMPT_EXISTING_SAMPLE_LIMIT = _env_int("AI_VOCAB_PROMPT_EXISTING_SAMPLE_LIMIT", 1500, min_value=100, max_value=60000)
AI_VOCAB_RUSSIAN_OFFICIAL_CHECK_LIMIT = _env_int("AI_VOCAB_RUSSIAN_OFFICIAL_CHECK_LIMIT", 40, min_value=0, max_value=1000)
AI_VOCAB_RUSSIAN_OFFICIAL_CONCURRENCY = _env_int("AI_VOCAB_RUSSIAN_OFFICIAL_CONCURRENCY", 1, min_value=1, max_value=30)

_existing_vocab_keys_cache: dict[tuple[str, str], tuple[float, set[str]]] = {}


def _normalize_word_key(word: Any) -> str:
    return str(word or "").strip().lower()


_REQUIRED_VOCAB_FIELDS: tuple[str, ...] = (
    "translation_uz",
    "translation_ru",
    "definition",
    "example",
)


_VOCAB_GENERATION_CACHE_BLOCK = """
[CACHE_BLOCK:VOCAB_GENERATION_V2]
You are a professional vocabulary expert for CEFR-based educational content.
Output format rules:
- Return ONLY a valid JSON array.
- No markdown, no comments, no prose.
- Each item must be an object with EXACT keys:
  word, translation_uz, translation_ru, definition, example
- Never leave any key empty.
- Never use placeholders like "-", "N/A", or "TBD".
Quality rules:
- word: real usable vocabulary item for the requested subject and level.
- translation_uz: natural Uzbek translation.
- translation_ru: natural Russian translation.
- definition: clear educational definition in 1-2 full sentences.
- example: exactly one natural sentence that uses the word.
- Keep language grammar correct and classroom-safe.
[/CACHE_BLOCK]
"""


_VOCAB_SEED_ENRICH_CACHE_BLOCK = """
[CACHE_BLOCK:VOCAB_SEED_ENRICH_V2]
You receive a fixed list of words.
Your job is enrichment only:
- Do not add new words.
- Do not remove words.
- Do not rewrite words.
Return EXACTLY one JSON object per input word, preserving order.
Use these keys in every object:
- word
- translation_uz
- translation_ru
- definition
- example
All keys must be non-empty and meaningful.
Output must be ONLY a JSON array.
[/CACHE_BLOCK]
"""


_DEFINITION_BAD_SNIPPETS: tuple[str, ...] = (
    "a common cefr",
    "word of level",
    "слово уровня",
    "darajadagi muhim so‘z",
)

_EXAMPLE_BAD_SNIPPETS: tuple[str, ...] = (
    "this sentence uses the word",
    "i use the word",
    "я использую слово",
    "oddiy gapda ishlataman",
)


def _word_count(text: Any) -> int:
    return len(re.findall(r"[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳ'-]+", str(text or "")))


def _mentions_target_word(example: str, word: str) -> bool:
    ex = str(example or "").strip().lower()
    w = str(word or "").strip().lower()
    if not ex or not w:
        return False
    if w in ex:
        return True
    # For phrases / inflections, allow token-level overlap.
    tokens = [t for t in re.findall(r"[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳ'-]+", w) if len(t) >= 4]
    return any(t in ex for t in tokens)


def _is_definition_quality_ok(subject: str, definition: Any) -> bool:
    txt = str(definition or "").strip()
    if not txt:
        return False
    lower_txt = txt.lower()
    if any(sn in lower_txt for sn in _DEFINITION_BAD_SNIPPETS):
        return False
    if len(txt) < 24 or _word_count(txt) < 5:
        return False
    if subject == "Russian":
        return _is_russian_text_valid(txt)
    # English subject: definition must be in English (no Cyrillic noise).
    return _has_latin_text(txt) and not _has_cyrillic_text(txt)


def _is_example_quality_ok(subject: str, word: Any, example: Any) -> bool:
    txt = str(example or "").strip()
    if not txt:
        return False
    lower_txt = txt.lower()
    if any(sn in lower_txt for sn in _EXAMPLE_BAD_SNIPPETS):
        return False
    if len(txt) < 18 or _word_count(txt) < 4:
        return False
    if not _mentions_target_word(txt, str(word or "")):
        return False
    if subject == "Russian":
        if not _is_russian_text_valid(txt):
            return False
    else:
        if not (_has_latin_text(txt) and not _has_cyrillic_text(txt)):
            return False
    # Keep one-sentence examples only.
    if len(re.findall(r"[.!?]", txt)) > 1:
        return False
    return True


def _needs_vocab_quality_repair(item: dict[str, Any], subject: str) -> bool:
    if not _has_all_required_vocab_fields(item):
        return True
    if not _is_definition_quality_ok(subject, item.get("definition")):
        return True
    if not _is_example_quality_ok(subject, item.get("word"), item.get("example")):
        return True
    if subject == "Russian" and not _is_valid_russian_vocab_item(item):
        return True
    return False


def _prompt_language_hint(subject: str) -> str:
    if subject == "Russian":
        return "definition_language=Russian(Cyrillic only)\nexample_language=Russian(Cyrillic only)\n"
    return "definition_language=English\nexample_language=English\n"


def _capitalize_russian_word(word: Any) -> str:
    w = str(word or "").strip()
    if not w:
        return "Слово"
    return f"{w[:1].upper()}{w[1:]}"


def _russian_seed_definition(word: Any) -> str:
    w = _capitalize_russian_word(word)
    return f"{w} — русское слово, которое помогает точно выразить мысль в учебной речи."


def _russian_seed_example(word: Any) -> str:
    w = _capitalize_russian_word(word)
    return f"{w} часто встречается в учебном тексте и помогает понять основную мысль."


def _fallback_vocab_fields(subject: str, level: str, word: str) -> dict[str, str]:
    w = str(word or "").strip() or "word"
    lv = _normalize_level(level) or "BEGINNER"
    if subject == "Russian":
        return {
            "translation_uz": f"{w} so'zi",
            "translation_ru": w,
            "definition": _russian_seed_definition(w),
            "example": _russian_seed_example(w),
        }
    return {
        "translation_uz": f"{w} (o‘zbekcha tarjimasi)",
        "translation_ru": f"{w} (ruscha tarjimasi)",
        "definition": f"A common CEFR {lv} English word: {w}. It is useful in daily communication.",
        "example": f"I use the word {w} in a natural sentence.",
    }


def _has_all_required_vocab_fields(item: dict[str, Any]) -> bool:
    for field in _REQUIRED_VOCAB_FIELDS:
        if not str(item.get(field) or "").strip():
            return False
    return True


def _ensure_required_vocab_fields(item: dict[str, Any], *, subject: str, level: str) -> dict[str, Any]:
    out = dict(item or {})
    normalized_word = _normalize_seed_word(subject, out.get("word"))
    if normalized_word:
        out["word"] = normalized_word
    fallback = _fallback_vocab_fields(subject, level, out.get("word") or "")
    for field in _REQUIRED_VOCAB_FIELDS:
        val = str(out.get(field) or "").strip()
        out[field] = val if val else fallback[field]
    return out


def _apply_russian_vocab_defaults(item: dict[str, Any], *, level: str) -> dict[str, Any]:
    out = dict(item or {})
    word = _normalize_seed_word("Russian", out.get("word"))
    if not word:
        return out
    out["word"] = word
    fallback = _fallback_vocab_fields("Russian", level, word)
    if not str(out.get("translation_uz") or "").strip():
        out["translation_uz"] = fallback["translation_uz"]
    if not _is_russian_text_valid(out.get("translation_ru"), allow_empty=True):
        out["translation_ru"] = fallback["translation_ru"]
    if not _is_definition_quality_ok("Russian", out.get("definition")):
        out["definition"] = fallback["definition"]
    if not _is_example_quality_ok("Russian", word, out.get("example")):
        out["example"] = fallback["example"]
    return out


def _build_seed_enrichment_prompt(subject: str, level: str, words: list[str]) -> str:
    clean_words = [str(w or "").strip() for w in words if str(w or "").strip()]
    target = len(clean_words)
    task = (
        "TASK:\n"
        f"subject={subject}\n"
        f"level={_normalize_level(level)}\n"
        f"target_count={target}\n"
        f"{_prompt_language_hint(subject)}"
        f"words_json={json.dumps(clean_words, ensure_ascii=False)}\n"
    )
    if (subject or "").strip().title() == "Russian":
        task += (
            "For Russian, enrich only real Cyrillic dictionary words and keep all definition/example text in Russian.\n"
        )
    return _wrap_json_only_prompt(_VOCAB_SEED_ENRICH_CACHE_BLOCK + task)


async def _enrich_and_repair_vocab_items(
    subject: str,
    level: str,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not items:
        return []

    prepared: list[dict[str, Any]] = []
    repair_words: list[str] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        it = dict(raw)
        word = _normalize_seed_word(subject, it.get("word"))
        if not word:
            continue
        it["word"] = word
        if subject == "Russian":
            it = _apply_russian_vocab_defaults(it, level=level)
        if _needs_vocab_quality_repair(it, subject):
            repair_words.append(word)
        prepared.append(it)

    if not prepared:
        return []

    ai_by_word: dict[str, dict[str, Any]] = {}
    repaired_candidates = 0
    if repair_words:
        deduped_pending = _dedupe_words_preserve_order(repair_words)
        repaired_candidates = len(deduped_pending)
        async with aiohttp.ClientSession() as session:
            for chunk in _partition_list(deduped_pending, 35):
                if not chunk:
                    continue
                prompt = _build_seed_enrichment_prompt(subject, level, chunk)
                try:
                    text = await _gemini_generate(prompt, session=session)
                    parsed = parse_vocabulary_json(text, subject, level)
                except Exception as e:
                    logger.warning(
                        "seed enrichment failed subject=%s level=%s chunk_size=%s err=%s",
                        subject,
                        level,
                        len(chunk),
                        e,
                    )
                    continue
                for p in parsed:
                    key = _normalize_word_key(p.get("word"))
                    if key and key not in ai_by_word:
                        ai_by_word[key] = p

    enriched: list[dict[str, Any]] = []
    for it in prepared:
        key = _normalize_word_key(it.get("word"))
        ai_item = ai_by_word.get(key, {})
        merged = dict(it)
        if _needs_vocab_quality_repair(merged, subject) and ai_item:
            for field in _REQUIRED_VOCAB_FIELDS:
                candidate = str(ai_item.get(field) or "").strip()
                if candidate:
                    merged[field] = candidate
        if subject == "Russian":
            merged = _apply_russian_vocab_defaults(merged, level=level)
        merged = _ensure_required_vocab_fields(merged, subject=subject, level=level)
        enriched.append(merged)
    if repaired_candidates > 0:
        logger.info(
            "vocab quality repair subject=%s level=%s candidates=%s ai_resolved=%s total=%s",
            subject,
            level,
            repaired_candidates,
            len(ai_by_word),
            len(prepared),
        )
    return enriched


def _existing_vocab_cache_key(subject: str, language: str) -> tuple[str, str]:
    return (str(subject or "").strip().title(), str(language or "").strip().lower())


def _load_existing_word_keys(subject: str, language: str, *, force: bool = False) -> set[str]:
    cache_key = _existing_vocab_cache_key(subject, language)
    now = time.monotonic()
    cached = _existing_vocab_keys_cache.get(cache_key)
    if not force and cached:
        cached_at, cached_keys = cached
        if now - cached_at <= AI_VOCAB_EXISTING_CACHE_TTL_SEC:
            return set(cached_keys)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT LOWER(TRIM(word)) AS lw
            FROM words
            WHERE subject = ?
              AND language = ?
            """,
            (subject, language),
        )
        out: set[str] = set()
        for r in cur.fetchall():
            lw = (r.get("lw") if isinstance(r, dict) else r[0])  # type: ignore[index]
            if lw:
                out.add(str(lw))
        _existing_vocab_keys_cache[cache_key] = (now, set(out))
        return out
    finally:
        conn.close()


def _remember_existing_word_keys(subject: str, language: str, keys: set[str]) -> None:
    if not keys:
        return
    cache_key = _existing_vocab_cache_key(subject, language)
    cached_at, cached_keys = _existing_vocab_keys_cache.get(cache_key, (time.monotonic(), set()))
    updated = set(cached_keys)
    updated.update({_normalize_word_key(key) for key in keys if _normalize_word_key(key)})
    _existing_vocab_keys_cache[cache_key] = (cached_at, updated)


def _is_reasonable_word(word: str, subject: str) -> bool:
    del subject  # reserved for subject-specific heuristics if needed later
    w = str(word or "").strip().lower()
    if len(w) < 2 or len(w) > 40:
        return False
    if len(w) == 1:
        return False
    return True

_ENGLISH_OXFORD_3000_URL = (
    "https://raw.githubusercontent.com/Kolia951/The_Oxford_3000_CEFR/main/package.txt"
)
_ENGLISH_FREQ_20K_URL = (
    "https://raw.githubusercontent.com/first20hours/google-10000-english/master/20k.txt"
)
_RUSSIAN_FREQ_10K_URL = (
    "https://raw.githubusercontent.com/hingston/russian/master/10000-russian-words-cyrillic-only.txt"
)
_RUSSIAN_GRAMOTA_SEARCH_URL = "https://gramota.ru/poisk?query={query}"
_GRAMOTA_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/147.0.0.0 Safari/537.36"
)
_GRAMOTA_BROWSER_HEADERS = {
    "User-Agent": _GRAMOTA_BROWSER_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.6,en;q=0.5",
    "Referer": "https://gramota.ru/",
}


def _seed_levels_for_request(subject: str, level: str) -> list[str]:
    lvl = _normalize_level(level)
    if lvl != "MIXED":
        return [lvl]
    return ["BEGINNER", "ELEMENTARY", "PRE-INTERMEDIATE", "INTERMEDIATE", "UPPER-INTERMEDIATE", "ADVANCED"]


def _slice_window_by_level(subject: str, level: str) -> tuple[int, int]:
    lvl = _normalize_level(level)
    if subject == "Russian":
        mapping = {
            "BEGINNER": (0, 700),
            "ELEMENTARY": (700, 1700),
            "PRE-INTERMEDIATE": (1700, 3500),
            "INTERMEDIATE": (3500, 5200),
            "UPPER-INTERMEDIATE": (5200, 7600),
            "ADVANCED": (7600, 10000),
        }
    else:
        mapping = {
            "BEGINNER": (0, 1200),
            "ELEMENTARY": (1200, 2600),
            "PRE-INTERMEDIATE": (2600, 5200),
            "INTERMEDIATE": (5200, 9000),
            "UPPER-INTERMEDIATE": (9000, 15000),
            "ADVANCED": (15000, 20000),
        }
    return mapping.get(lvl, (0, 1200))


def _normalize_seed_word(subject: str, raw_word: Any) -> str:
    w = str(raw_word or "").strip()
    if not w:
        return ""

    # Normalize repeated spaces, but keep phrase shape.
    w = re.sub(r"\s+", " ", w).strip()
    if (subject or "").strip().title() == "Russian":
        w = re.sub(r"[\u0301`´]", "", w).strip().lower()
        if not _has_cyrillic_text(w) or _has_latin_text(w):
            return ""
        if not re.fullmatch(r"[а-яё]+(?:[- ][а-яё]+){0,2}", w, re.IGNORECASE):
            return ""

    if not _is_reasonable_word(w, subject):
        return ""

    # Reject one-character vowel-only noise.
    if len(w) == 1 and w.lower() in "aiouy":
        return ""

    # Soft mixed-script guard: reject only strongly mixed words.
    has_cyr = bool(re.search(r"[а-яё]", w, re.IGNORECASE))
    has_lat = bool(re.search(r"[a-z]", w, re.IGNORECASE))
    if has_cyr and has_lat:
        cyr_count = len(re.findall(r"[а-яё]", w, re.IGNORECASE))
        lat_count = len(re.findall(r"[a-z]", w, re.IGNORECASE))
        if cyr_count > 3 and lat_count > 3:
            return ""
    return w


def _build_seed_vocab_item(subject: str, level: str, word: str, source: str) -> dict[str, Any]:
    if subject == "Russian":
        fallback = _fallback_vocab_fields(subject, level, word)
        return {
            "subject": subject,
            "level": level,
            "language": "ru",
            "word": word,
            "translation_uz": fallback["translation_uz"],
            "translation_ru": fallback["translation_ru"],
            "definition": fallback["definition"],
            "example": fallback["example"],
            "source": source,
        }
    return {
        "subject": subject,
        "level": level,
        "language": "en",
        "word": word,
        "translation_uz": "",
        "translation_ru": "",
        "definition": f"A common CEFR {level} English word: {word}.",
        "example": f"This sentence uses the word {word}.",
        "source": source,
    }


def _extract_json_object(raw: str) -> dict[str, Any]:
    txt = _sanitize_json_like_text(raw)
    if not txt:
        return {}
    try:
        obj = json.loads(txt)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass
    try:
        obj = ast.literal_eval(txt)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


async def _download_text(url: str, *, session: aiohttp.ClientSession) -> str:
    if "gramota.ru/" in str(url or "").lower():
        return await _download_gramota_text(url)
    async with session.get(
        url,
        timeout=aiohttp.ClientTimeout(total=AI_VOCAB_SEED_HTTP_TIMEOUT_SEC),
    ) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        return await resp.text()


async def _download_gramota_text(url: str) -> str:
    """
    Gramota.ru currently rejects aiohttp clients on the production server even
    with browser headers, while curl with the same browser identity is accepted.
    Keep this narrow fallback scoped to the official Russian dictionary lookup.
    """
    timeout_sec = str(max(5, min(30, AI_VOCAB_SEED_HTTP_TIMEOUT_SEC)))
    last_error = ""
    for attempt in range(3):
        proc = await asyncio.to_thread(
            subprocess.run,
            [
                "curl",
                "-fsSL",
                "--compressed",
                "--max-time",
                timeout_sec,
                "-A",
                _GRAMOTA_BROWSER_USER_AGENT,
                "-H",
                f"Accept: {_GRAMOTA_BROWSER_HEADERS['Accept']}",
                "-H",
                f"Accept-Language: {_GRAMOTA_BROWSER_HEADERS['Accept-Language']}",
                "-H",
                f"Referer: {_GRAMOTA_BROWSER_HEADERS['Referer']}",
                url,
            ],
            check=False,
            capture_output=True,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout.decode("utf-8", errors="replace")
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        last_error = err or str(proc.returncode)
        if attempt < 2:
            await asyncio.sleep(0.8 + (attempt * 0.8))
    raise RuntimeError(f"Gramota.ru curl fetch failed: {last_error}")


def _russian_compare_key(value: Any) -> str:
    txt = html.unescape(str(value or ""))
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"[\u0301`´]", "", txt)
    txt = re.sub(r"\s+", " ", txt).strip().lower()
    return txt.replace("ё", "е")


def _extract_gramota_dictionary_titles(raw_html: str) -> set[str]:
    if not raw_html:
        return set()
    titles: set[str] = set()
    for match in re.findall(r"class=[\"'][^\"']*\btitle\b[^\"']*[\"'][^>]*>(.*?)</(?:a|span|p|div)>", raw_html, re.IGNORECASE | re.DOTALL):
        cleaned = _russian_compare_key(match)
        if cleaned and re.fullmatch(r"[а-яе]+(?:[- ][а-яе]+){0,2}", cleaned):
            titles.add(cleaned)
    return titles


async def _gramota_has_dictionary_word(word: str, *, session: aiohttp.ClientSession) -> bool:
    normalized = _normalize_seed_word("Russian", word)
    if not normalized:
        return False
    url = _RUSSIAN_GRAMOTA_SEARCH_URL.format(query=quote(normalized))
    raw = await _download_text(url, session=session)
    target = _russian_compare_key(normalized)
    return target in _extract_gramota_dictionary_titles(raw)


async def _filter_russian_words_from_official_sources(
    words: list[str],
    *,
    session: aiohttp.ClientSession,
    max_items: int,
) -> list[str]:
    if not words or max_items <= 0 or AI_VOCAB_RUSSIAN_OFFICIAL_CHECK_LIMIT <= 0:
        return []
    candidates = _dedupe_words_preserve_order(words)[: min(len(words), AI_VOCAB_RUSSIAN_OFFICIAL_CHECK_LIMIT)]
    found: list[str] = []
    for idx, candidate in enumerate(candidates):
        try:
            if await _gramota_has_dictionary_word(candidate, session=session):
                found.append(candidate)
                if len(found) >= max_items:
                    return found
        except Exception as exc:
            logger.debug("Gramota.ru seed check failed word=%s err=%r", candidate, exc)
        if idx + 1 < len(candidates):
            await asyncio.sleep(0.35)
    return found


def _dedupe_words_preserve_order(words: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for w in words:
        key = _normalize_word_key(w)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(w)
    return out


async def _fetch_seed_words_for_level(
    subject: str,
    level: str,
    *,
    session: aiohttp.ClientSession,
    max_items: int,
) -> list[dict[str, Any]]:
    subject = (subject or "").strip().title()
    level = _normalize_level(level)
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _accept(word: str, source: str) -> None:
        normalized = _normalize_seed_word(subject, word)
        if not normalized:
            return
        if normalized in seen:
            return
        seen.add(normalized)
        collected.append(_build_seed_vocab_item(subject, level, normalized, source))

    if subject == "English":
        # Primary CEFR source for A1..B2.
        try:
            oxford_raw = await _download_text(_ENGLISH_OXFORD_3000_URL, session=session)
            oxford = _extract_json_object(oxford_raw)
            lvl_words = oxford.get(level) if isinstance(oxford, dict) else None
            if isinstance(lvl_words, list):
                for w in _dedupe_words_preserve_order([str(x or "").strip() for x in lvl_words]):
                    _accept(w, "oxford3000_cefr")
                    if len(collected) >= max_items:
                        return collected
        except Exception as e:
            logger.warning("Seed source oxford3000 fetch failed level=%s err=%s", level, e)

        # Frequency-ranked fallback source for any missing capacity (and C1).
        try:
            freq_raw = await _download_text(_ENGLISH_FREQ_20K_URL, session=session)
            all_words = [
                str(line or "").strip().lower()
                for line in freq_raw.splitlines()
                if str(line or "").strip()
            ]
            start, end = _slice_window_by_level("English", level)
            for w in all_words[start:end]:
                _accept(w, "english_frequency_rank")
                if len(collected) >= max_items:
                    break
        except Exception as e:
            logger.warning("Seed source english_frequency fetch failed level=%s err=%s", level, e)
    else:
        try:
            freq_raw = await _download_text(_RUSSIAN_FREQ_10K_URL, session=session)
            all_words = [
                str(line or "").strip().lower()
                for line in freq_raw.splitlines()
                if str(line or "").strip()
            ]
            start, end = _slice_window_by_level("Russian", level)
            level_words = _dedupe_words_preserve_order(all_words[start:end])
            official_words = await _filter_russian_words_from_official_sources(
                level_words,
                session=session,
                max_items=max_items,
            )
            for w in official_words:
                _accept(w, "gramota_ru_dictionary")
                if len(collected) >= max_items:
                    return collected
            for w in level_words:
                _accept(w, "russian_frequency_rank")
                if len(collected) >= max_items:
                    break
        except Exception as e:
            logger.warning("Seed source russian_frequency fetch failed level=%s err=%s", level, e)

    return collected


async def refresh_vocab_seed_pool(subject: str, level: str) -> dict[str, int]:
    """
    Lazy internet refresh for vocab_seed_pool.
    Returns stats with fetched/upserted counts.
    """
    ensure_vocab_seed_pool_schema()
    subject = (subject or "").strip().title()
    level = _normalize_level(level)
    if subject not in ("English", "Russian"):
        raise ValueError("subject must be 'English' or 'Russian'")
    if level not in allowed_levels_for_ai_pipeline(subject):
        raise ValueError(f"level must be one of {sorted(allowed_levels_for_ai_pipeline(subject))}")

    levels = _seed_levels_for_request(subject, level)
    all_rows: list[dict[str, Any]] = []
    async with aiohttp.ClientSession() as session:
        for lvl in levels:
            rows = await _fetch_seed_words_for_level(
                subject,
                lvl,
                session=session,
                max_items=AI_VOCAB_SEED_REFRESH_FETCH_LIMIT,
            )
            all_rows.extend(rows)

    result = upsert_vocab_seed_pool_items(all_rows)
    return {
        "fetched": len(all_rows),
        "inserted": int(result.get("inserted") or 0),
        "updated": int(result.get("updated") or 0),
        "skipped_invalid": int(result.get("skipped_invalid") or 0),
    }


def _pull_seed_candidates_for_request(
    subject: str,
    level: str,
    need_count: int,
    exclude_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    subject = (subject or "").strip().title()
    level = _normalize_level(level)
    remaining = max(0, int(need_count))
    if remaining <= 0:
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set(_normalize_word_key(x) for x in (exclude_keys or set()))
    for lvl in _seed_levels_for_request(subject, level):
        if remaining <= 0:
            break
        part = pull_seed_candidates(subject, lvl, remaining, exclude_keys=seen)
        for row in part:
            w = _normalize_word_key(row.get("word"))
            if not w or w in seen:
                continue
            seen.add(w)
            out.append(row)
            remaining -= 1
            if remaining <= 0:
                break
    return out


def _insert_vocab_items_into_words(
    *,
    subject: str,
    level: str,
    items: list[dict[str, Any]],
    added_by: Optional[int],
    max_insert: Optional[int] = None,
    external_seen: set[str] | None = None,
) -> tuple[int, int, int]:
    words_to_insert: list[dict[str, Any]] = []
    seen_in_response: set[str] = set()
    skipped_invalid = 0
    skipped_existing = 0
    language = _subject_to_vocab_language(subject)
    for it in items:
        if not isinstance(it, dict):
            skipped_invalid += 1
            continue
        w = (it.get("word") or "").strip()
        if not w:
            skipped_invalid += 1
            continue
        key = _normalize_word_key(w)
        if not key:
            skipped_invalid += 1
            continue
        if key in seen_in_response:
            skipped_existing += 1
            continue
        if external_seen is not None and key in external_seen:
            skipped_existing += 1
            continue
        seen_in_response.add(key)
        words_to_insert.append(it)

    conn = get_conn()
    cur = conn.cursor()
    existing_lw: set[str] = set()
    generated_lw = [_normalize_word_key(it.get("word")) for it in words_to_insert]
    for part in _partition_list(generated_lw, 400):
        if not part:
            continue
        placeholders = ",".join(["?"] * len(part))
        sql = (
            f"SELECT LOWER(TRIM(word)) as lw FROM words "
            f"WHERE subject=? "
            f"AND language=? "
            f"AND LOWER(TRIM(word)) IN ({placeholders})"
        )
        cur.execute(sql, tuple([subject, language] + part))
        for r in cur.fetchall():
            lw = (r.get("lw") if isinstance(r, dict) else r[0])  # type: ignore[index]
            if lw:
                existing_lw.add(str(lw).lower())
    if external_seen:
        existing_lw.update(external_seen)
    conn.close()

    inserted = 0
    inserted_keys: set[str] = set()
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        for it in words_to_insert:
            if max_insert is not None and inserted >= int(max_insert):
                break
            w = (it.get("word") or "").strip()
            key = _normalize_word_key(w)
            if not key:
                skipped_invalid += 1
                continue
            if _contains_adult_content(
                [
                    it.get("word"),
                    it.get("translation_uz"),
                    it.get("translation_ru"),
                    it.get("definition"),
                    it.get("example"),
                ]
            ):
                skipped_invalid += 1
                logger.warning("Skipped vocab item due to 18+ content subject=%s level=%s word=%s", subject, level, w)
                continue
            if key in existing_lw:
                skipped_existing += 1
                continue

            prepared_item = _ensure_required_vocab_fields(it, subject=subject, level=level)
            translation_uz = (prepared_item.get("translation_uz") or "").strip()
            translation_ru = (prepared_item.get("translation_ru") or "").strip()
            definition = (prepared_item.get("definition") or "").strip()
            example = (prepared_item.get("example") or "").strip()

            if subject == "Russian":
                raw_lv = prepared_item.get("level")
                word_level = _normalize_russian_bank_level(
                    str(raw_lv) if raw_lv is not None else "",
                    level,
                )
            else:
                word_level = _normalize_generated_level(prepared_item.get("level") if level == "MIXED" else level)
            cur.execute(
                """
                INSERT INTO words
                (word, subject, language, level, translation_uz, translation_ru, definition, example, added_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    w,
                    subject,
                    language,
                    word_level,
                    translation_uz,
                    translation_ru,
                    definition,
                    example,
                    added_by,
                ),
            )
            inserted += 1
            existing_lw.add(key)
            inserted_keys.add(key)
            if external_seen is not None:
                external_seen.add(key)

        conn.commit()
        conn.close()
    _remember_existing_word_keys(subject, language, inserted_keys)
    return inserted, skipped_existing, skipped_invalid


def parse_vocabulary_json(raw_text: str, subject: str, level: str) -> list[dict]:
    items = _parse_json_like_to_list(raw_text)
    if not items:
        return []

    parsed = []
    for it in items:
        if not isinstance(it, dict):
            continue

        word = str(it.get("word") or "").strip()
        if not word:
            continue

        normalized_word = _normalize_seed_word(subject, word)
        if not normalized_word:
            continue

        entry = _ensure_required_vocab_fields({
            "subject": subject,
            "level": level,
            "language": vocab_language_for_subject(subject),
            "word": normalized_word,
            "translation_uz": str(it.get("translation_uz") or "").strip(),
            "translation_ru": str(it.get("translation_ru") or "").strip(),
            "definition": str(it.get("definition") or "").strip(),
            "example": str(it.get("example") or "").strip(),
            "source": "ai_generator",
        }, subject=subject, level=level)
        parsed.append(entry)

    return parsed


def _build_vocab_generation_prompt(subject: str, level: str, count: int) -> str:
    return _build_vocab_generation_prompt_exact(subject, level, int(count))


def _vocab_existing_prompt_sample(existing_list: list[str]) -> list[str]:
    if len(existing_list) <= AI_VOCAB_PROMPT_EXISTING_SAMPLE_LIMIT:
        return existing_list
    limit = AI_VOCAB_PROMPT_EXISTING_SAMPLE_LIMIT
    head_count = max(50, limit // 5)
    tail_count = max(50, limit // 5)
    middle_limit = max(0, limit - head_count - tail_count)
    middle = existing_list[head_count : max(head_count, len(existing_list) - tail_count)]
    step = max(1, len(middle) // max(1, middle_limit)) if middle_limit else 1
    sample = existing_list[:head_count]
    if middle_limit:
        sample.extend(middle[::step][:middle_limit])
    sample.extend(existing_list[-tail_count:])
    out: list[str] = []
    seen: set[str] = set()
    for word in sample:
        key = _normalize_word_key(word)
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out[:limit]


def _build_vocab_generation_prompt_exact(
    subject: str,
    level: str,
    target_count: int,
    initial_existing_words: set[str] | list[str] | tuple[str, ...] | None = None,
    recently_generated_words: set[str] | list[str] | tuple[str, ...] | None = None,
) -> str:
    target_count = int(target_count)
    initial_list = sorted({_normalize_word_key(w) for w in (initial_existing_words or []) if _normalize_word_key(w)})
    recent_list = sorted({_normalize_word_key(w) for w in (recently_generated_words or []) if _normalize_word_key(w)})
    
    existing_sample = _vocab_existing_prompt_sample(initial_list)
    
    static_prefix = (
        _VOCAB_GENERATION_CACHE_BLOCK +
        "TASK DEFINITION:\n"
        f"subject={subject}\n"
        f"level={_normalize_level(level)}\n"
        f"{_prompt_language_hint(subject)}"
        f"db_reference_words={json.dumps(existing_sample, ensure_ascii=False)}\n"
    )
    if (subject or "").strip().title() == "Russian":
        static_prefix += (
            "Russian source rule: choose only real Cyrillic Russian dictionary words that can be checked in "
            "authoritative Russian references such as Gramota.ru or academic dictionaries. "
            "Do not invent words and do not use transliteration.\n"
        )
        
    dynamic_suffix = (
        f"target_count={target_count}\n"
        f"total_db_words_count={len(initial_list) + len(recent_list)}\n"
        "Do not generate any word from db_reference_words.\n"
    )
    if recent_list:
        dynamic_suffix += f"Also DO NOT generate any of these words (already generated in this session): {json.dumps(recent_list, ensure_ascii=False)}\n"
        
    dynamic_suffix += (
        f"To ensure variety, random seed: {random.randint(100000, 999999)}\n"
        "Avoid repeating any word already generated earlier in this same JSON response.\n"
    )

    return _wrap_json_only_prompt(static_prefix + dynamic_suffix)


def _daily_instruction_for_type(question_type: str, subject: str) -> str:
    qt = str(question_type or "").strip().lower()
    is_ru = str(subject or "").strip().lower() == "russian"
    if is_ru:
        return {
            "grammar_rules": "Выберите правильное грамматическое правило.",
            "grammar_sentence": "Выберите правильный вариант для завершения предложения.",
            "find_mistake": "Найдите ошибку и выберите правильный вариант.",
            "error_spotting": "Определите, в какой части предложения есть ошибка.",
        }.get(qt, "Выберите правильный ответ.")
    return {
        "grammar_rules": "Choose the correct grammar rule.",
        "grammar_sentence": "Choose the correct option to complete the sentence.",
        "find_mistake": "Find the mistake and choose the correct version.",
        "error_spotting": "Identify which part of the sentence has the error.",
    }.get(qt, "Choose the correct answer.")


def _daily_question_with_instruction(question: str, question_type: str, subject: str) -> str:
    q = str(question or "").strip()
    instruction = _daily_instruction_for_type(question_type, subject)
    if not q:
        return instruction
    q_low = q.lower()
    instruction_low = instruction.lower()
    if q_low.startswith(instruction_low[: max(12, min(len(instruction_low), 28))]):
        return q
    generic_markers = (
        "choose ",
        "select ",
        "find ",
        "complete ",
        "identify ",
        "выберите ",
        "найдите ",
        "определите ",
        "завершите ",
    )
    if q_low.startswith(generic_markers):
        return q
    return f"{instruction} {q}"


DAILY_RICH_QUESTION_TYPES = (
    "grammar_rules",
    "grammar_sentence",
    "find_mistake",
    "error_spotting",
)


def _daily_type_counts(count: int) -> dict[str, int]:
    total = max(1, int(count or 1))
    weights = {
        "grammar_rules": 0.25,
        "grammar_sentence": 0.35,
        "find_mistake": 0.20,
        "error_spotting": 0.20,
    }
    counts = {k: int(round(total * v)) for k, v in weights.items()}
    diff = total - sum(counts.values())
    order = list(DAILY_RICH_QUESTION_TYPES)
    idx = 0
    while diff != 0 and order:
        key = order[idx % len(order)]
        if diff > 0:
            counts[key] += 1
            diff -= 1
        elif counts[key] > 0:
            counts[key] -= 1
            diff += 1
        idx += 1
        if idx > 1000:
            break
    return counts


def _clean_options(values: Any, limit: int | None = None) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if limit and len(out) >= limit:
            break
    return out


def _normalize_rich_daily_item(item: dict[str, Any], *, subject: str, level: str) -> dict[str, Any] | None:
    qt = str(item.get("question_type") or "").strip().lower()
    if qt not in DAILY_RICH_QUESTION_TYPES:
        qt = "grammar_sentence"
    instruction = _daily_instruction_for_type(qt, subject)
    question = str(item.get("question") or item.get("prompt") or "").strip()
    if not question:
        question = instruction
    options = _clean_options(item.get("options"), 4)
    if len(options) != 4:
        return None
    try:
        coi = int(item.get("correct_option_index") or 1)
    except Exception:
        coi = 1
    coi = max(1, min(4, coi))
    payload = {
        "question_type": qt,
        "instruction": instruction,
        "question": _daily_question_with_instruction(question, qt, subject),
        "prompt": _daily_question_with_instruction(question, qt, subject),
        "options": options,
        "correct_option_index": coi,
        "explanation": str(item.get("explanation") or "").strip(),
    }

    if subject == "Russian":
        row_level = _normalize_russian_bank_level(str(item.get("level") or ""), level)
    else:
        row_level = _normalize_generated_level(item.get("level") if level == "MIXED" else level)
    payload["level"] = str(row_level or "").upper()
    return payload


async def _generate_vocabulary_and_insert_once(
    *,
    subject: str,
    level: str,
    count: int,
    added_by: Optional[int],
    max_insert: Optional[int] = None,
    external_seen: set[str] | None = None,
    prompt_override: Optional[str] = None,
) -> GenerationResult:
    language = _subject_to_vocab_language(subject)
    prompt = prompt_override or _build_vocab_generation_prompt_exact(
        subject,
        level,
        count,
        _load_existing_word_keys(subject, language),
    )

    warnings: list[str] = []
    async with aiohttp.ClientSession() as session:
        text = await _gemini_generate(prompt, session=session)

    try:
        items = parse_vocabulary_json(text, subject, level)
    except Exception as e:
        raise RuntimeError(f"Failed to parse vocabulary JSON from Gemini: {e}")
    items = await _enrich_and_repair_vocab_items(subject, level, items)

    generated = len(items)
    if generated == 0:
        return GenerationResult(
            requested=count,
            generated=0,
            inserted=0,
            skipped=count,
            attempts=1,
            skipped_existing=0,
            skipped_invalid=count,
            raw_parse_warnings=tuple(warnings),
        )

    inserted, skipped_existing, skipped_invalid = _insert_vocab_items_into_words(
        subject=subject,
        level=level,
        items=items,
        added_by=added_by,
        max_insert=max_insert,
        external_seen=external_seen,
    )

    return GenerationResult(
        requested=count,
        generated=generated,
        inserted=inserted,
        skipped=(skipped_existing + skipped_invalid),
        attempts=1,
        skipped_existing=skipped_existing,
        skipped_invalid=skipped_invalid,
        inserted_from_ai=inserted,
        raw_parse_warnings=tuple(warnings),
    )


async def generate_vocabulary_and_insert(
    *,
    subject: str,
    level: str,
    count: int,
    added_by: Optional[int] = None,
) -> GenerationResult:
    """Best-effort single pass vocabulary generation + insert."""
    subject = (subject or "").strip().title()
    level = _normalize_level(level)

    if subject not in ("English", "Russian"):
        raise ValueError("subject must be 'English' or 'Russian'")
    allowed_vocab = allowed_levels_for_ai_pipeline(subject)
    if level not in allowed_vocab:
        raise ValueError(f"level must be one of {sorted(allowed_vocab)}")
    count = int(count)
    if count <= 0:
        raise ValueError("count must be > 0")

    # Prevent concurrent generation for the same (subject,level) within one process.
    lock_key = (f"vocab:{subject}", level)
    lock = _ai_generation_locks.setdefault(lock_key, asyncio.Lock())
    async with lock:
        return await _generate_vocabulary_and_insert_once(
            subject=subject,
            level=level,
            count=count,
            added_by=added_by,
            max_insert=None,
        )


async def generate_vocabulary_and_insert_exact(
    *,
    subject: str,
    level: str,
    target_count: int,
    added_by: Optional[int] = None,
    progress_cb: Optional[Callable[[int, int, int], Awaitable[None] | None]] = None,
    check_cancel: Optional[Callable[[], bool]] = None,
    max_attempts: Optional[int] = None,
    allow_partial: bool = False,
) -> GenerationResult:
    """
    Insert exactly target_count words with cache-first internet seeds and capped AI retries.
    """
    subject = (subject or "").strip().title()
    level = _normalize_level(level)
    target_count = int(target_count)
    if target_count <= 0:
        raise ValueError("target_count must be > 0")
    if subject not in ("English", "Russian"):
        raise ValueError("subject must be 'English' or 'Russian'")
    allowed_vocab = allowed_levels_for_ai_pipeline(subject)
    if level not in allowed_vocab:
        raise ValueError(f"level must be one of {sorted(allowed_vocab)}")
    if max_attempts is None:
        # Large requests (e.g. 5000) need proportionally more attempts.
        scaled_attempts = int(math.ceil(target_count / max(10, AI_VOCAB_MAX_BATCH_SIZE)) * 4)
        max_attempts = max(AI_VOCAB_MAX_ATTEMPTS, scaled_attempts)
    max_attempts = max(1, int(max_attempts))
    language = _subject_to_vocab_language(subject)

    lock_key = (f"vocab:{subject}", level)
    lock = _ai_generation_locks.setdefault(lock_key, asyncio.Lock())
    async with lock:
        ensure_vocab_seed_pool_schema()
        global_seen = _load_existing_word_keys(subject, language)
        initial_seen = set(global_seen)
        attempts = 0
        total_generated = 0
        inserted_total = 0
        inserted_from_seed_total = 0
        inserted_from_ai_total = 0
        skipped_existing_total = 0
        skipped_invalid_total = 0
        warnings_all: list[str] = []
        last_error: str = ""
        no_progress_streak = 0
        no_progress_limit = max(AI_VOCAB_NO_PROGRESS_LIMIT, min(40, max(6, max_attempts // 4)))

        # 1) Cache-first: use existing seed pool first.
        seed_candidates = _pull_seed_candidates_for_request(
            subject,
            level,
            target_count - inserted_total,
            exclude_keys=global_seen,
        )

        # 2) Lazy internet refresh only if local seed pool is not enough.
        if len(seed_candidates) < (target_count - inserted_total):
            try:
                refresh_stats = await refresh_vocab_seed_pool(subject, level)
                logger.info(
                    "vocab seed refresh subject=%s level=%s fetched=%s inserted=%s updated=%s skipped_invalid=%s",
                    subject,
                    level,
                    refresh_stats.get("fetched"),
                    refresh_stats.get("inserted"),
                    refresh_stats.get("updated"),
                    refresh_stats.get("skipped_invalid"),
                )
            except Exception as e:
                logger.warning("vocab seed refresh failed subject=%s level=%s err=%s", subject, level, e)
            seed_candidates = _pull_seed_candidates_for_request(
                subject,
                level,
                target_count - inserted_total,
                exclude_keys=global_seen,
            )

        if seed_candidates:
            seed_candidates = await _enrich_and_repair_vocab_items(subject, level, seed_candidates)
            seed_inserted, seed_skipped_existing, seed_skipped_invalid = _insert_vocab_items_into_words(
                subject=subject,
                level=level,
                items=seed_candidates,
                added_by=added_by,
                max_insert=(target_count - inserted_total),
                external_seen=global_seen,
            )
            total_generated += int(len(seed_candidates))
            inserted_total += int(seed_inserted)
            inserted_from_seed_total += int(seed_inserted)
            skipped_existing_total += int(seed_skipped_existing)
            skipped_invalid_total += int(seed_skipped_invalid)
            logger.info(
                "vocab exact seed stage subject=%s level=%s generated=%s inserted=%s remaining=%s",
                subject,
                level,
                len(seed_candidates),
                seed_inserted,
                max(0, target_count - inserted_total),
            )
            if progress_cb is not None:
                current = int(inserted_total)
                pct = int((current * 100) / max(1, target_count))
                r = progress_cb(pct, current, target_count)
                if asyncio.iscoroutine(r):
                    await r

        while inserted_total < target_count and attempts < max_attempts:
            if check_cancel and check_cancel():
                last_error = "Cancelled by user"
                break
            attempts += 1
            remaining = target_count - inserted_total
            req = max(AI_VOCAB_INSERT_BATCH_SIZE, remaining * AI_VOCAB_OVERSAMPLE_FACTOR)
            req = min(req, AI_VOCAB_MAX_BATCH_SIZE)
            try:
                rep = await _generate_vocabulary_and_insert_once(
                    subject=subject,
                    level=level,
                    count=req,
                    added_by=added_by,
                    max_insert=remaining,
                    external_seen=global_seen,
                    prompt_override=_build_vocab_generation_prompt_exact(
                        subject,
                        level,
                        req,
                        initial_existing_words=initial_seen,
                        recently_generated_words=(global_seen - initial_seen),
                    ),
                )
            except Exception as e:
                last_error = str(e)
                no_progress_streak += 1
                logger.warning(
                    "vocab exact ai attempt failed subject=%s level=%s attempt=%s/%s no_progress_streak=%s err=%s",
                    subject,
                    level,
                    attempts,
                    max_attempts,
                    no_progress_streak,
                    e,
                )
                if no_progress_streak >= no_progress_limit:
                    break
                continue
            total_generated += int(rep.generated or 0)
            inserted_total += int(rep.inserted or 0)
            inserted_from_ai_total += int(rep.inserted or 0)
            skipped_existing_total += int(rep.skipped_existing or 0)
            skipped_invalid_total += int(rep.skipped_invalid or 0)
            if rep.raw_parse_warnings:
                warnings_all.extend(rep.raw_parse_warnings)
            inserted_this_attempt = int(rep.inserted or 0)
            if inserted_this_attempt <= 0:
                no_progress_streak += 1
            else:
                no_progress_streak = 0
            logger.info(
                "vocab exact ai attempt subject=%s level=%s attempt=%s/%s req=%s inserted_this=%s remaining=%s no_progress_streak=%s",
                subject,
                level,
                attempts,
                max_attempts,
                req,
                inserted_this_attempt,
                max(0, target_count - inserted_total),
                no_progress_streak,
            )
            if no_progress_streak >= no_progress_limit:
                last_error = (
                    "no-progress-guard reached "
                    f"(limit={no_progress_limit})"
                )
                break

            if progress_cb is not None:
                current = int(inserted_total)
                base_pct = (current * 100) / max(1, target_count)
                attempt_bonus = (attempts / max(1, max_attempts)) * (100 - base_pct) * 0.8 if max_attempts > 0 else 0
                pct = int(base_pct + attempt_bonus)
                r = progress_cb(pct, current, target_count)
                if asyncio.iscoroutine(r):
                    await r

        completed = inserted_total == target_count
        incomplete_note = (
            "Exact vocabulary generation incomplete after capped retries: "
            f"target={target_count}, inserted={inserted_total}, attempts={attempts}, "
            f"generated={total_generated}, inserted_from_seed={inserted_from_seed_total}, "
            f"inserted_from_ai={inserted_from_ai_total}, skipped_existing={skipped_existing_total}, "
            f"skipped_invalid={skipped_invalid_total}, no_progress_streak={no_progress_streak}, "
            f"last_error={last_error}"
        )
        if not completed and not allow_partial:
            raise RuntimeError(incomplete_note)

        return GenerationResult(
            requested=target_count,
            generated=total_generated,
            inserted=inserted_total,
            skipped=(skipped_existing_total + skipped_invalid_total),
            attempts=attempts,
            skipped_existing=skipped_existing_total,
            skipped_invalid=skipped_invalid_total,
            inserted_from_seed=inserted_from_seed_total,
            inserted_from_ai=inserted_from_ai_total,
            raw_parse_warnings=tuple(warnings_all),
            completed=completed,
            note="" if completed else incomplete_note,
        )


async def _generate_daily_test_questions(
    *,
    subject: str,
    level: str,
    count: int,
    created_by: Optional[int] = None,
    exclude_questions: list[str] | None = None,
    check_cancel: Optional[Callable[[], bool]] = None,
) -> GenerationResult:
    """Generate daily test rows into `daily_tests_bank` (caller holds per-subject/level lock)."""
    type_counts = _daily_type_counts(count)
    type_lines = "\n".join(f"- {key}: {value}" for key, value in type_counts.items() if int(value) > 0)
    allowed_type_text = ", ".join(DAILY_RICH_QUESTION_TYPES)

    exclude_block = ""
    if exclude_questions:
        recent_excludes = exclude_questions[:50]
        exclude_block = "\nDo NOT generate any of the following questions (or very similar ones):\n" + "\n".join(f"- {q}" for q in recent_excludes) + "\n"

    if subject == "English":
        rules = f"""
Generate exactly {count} English educational test questions (CEFR {"BEGINNER..ADVANCED mixed" if level == "MIXED" else level}).

Each element must be an object with:
  - level (BEGINNER/ELEMENTARY/PRE-INTERMEDIATE/INTERMEDIATE/UPPER-INTERMEDIATE/ADVANCED)
  - question_type (one of: {allowed_type_text})
  - instruction (clear student instruction)
  - question (prompt shown to student)
  - explanation (short)

Generate with the following EXACT type counts:
{type_lines}

Type-specific required fields:
- grammar_rules, grammar_sentence, find_mistake, error_spotting: options array of exactly 4 distinct strings and correct_option_index 1..4.

Rules:
- Keep everything educational and age-appropriate.
- Keep language appropriate for CEFR {level}.
{exclude_block}
""".strip()
        prompt = _wrap_json_only_prompt(rules)
    else:
        if level == "MIXED":
            ru_daily_scope = "mixed difficulty across CEFR PRE-INTERMEDIATE and INTERMEDIATE (vary the `level` field between PRE-INTERMEDIATE and INTERMEDIATE)"
            ru_daily_level_key = "PRE-INTERMEDIATE or INTERMEDIATE"
        elif level == "BEGINNER":
            ru_daily_scope = "Начальный уровень (BEGINNER): очень простая грамматика и короткие предложения"
            ru_daily_level_key = "repeat: BEGINNER"
        elif level == "ELEMENTARY":
            ru_daily_scope = "Элементарный уровень (ELEMENTARY): базовые конструкции, чуть сложнее чем BEGINNER"
            ru_daily_level_key = "repeat: ELEMENTARY"
        else:
            ru_daily_scope = "Базовый уровень (PRE-INTERMEDIATE/INTERMEDIATE): уверенное повседневное общение"
            ru_daily_level_key = "repeat: PRE-INTERMEDIATE or INTERMEDIATE"
        rules = f"""
Generate exactly {count} Russian language educational test questions ({ru_daily_scope}).

Each element must be an object with:
  - level ({ru_daily_level_key})
  - question_type (one of: {allowed_type_text})
  - instruction
  - question
  - explanation

Generate with the following EXACT type counts:
{type_lines}

Type-specific required fields:
- grammar_rules, grammar_sentence, find_mistake, error_spotting: options array of exactly 4 distinct strings and correct_option_index 1..4.

Rules:
- Keep difficulty appropriate for the stated tier.
- All instructions, prompts, options and explanations must be in Russian.
{exclude_block}
""".strip()
        prompt = _wrap_json_only_prompt(rules)

    async with aiohttp.ClientSession() as session:
        text = await _gemini_generate(prompt, session=session)

    try:
        parsed = _extract_json_array(text)
    except Exception as e:
        raise RuntimeError(f"Failed to parse daily test JSON from Gemini: {e}")

    if not isinstance(parsed, list):
        raise RuntimeError("Gemini daily test response is not a JSON array.")

    items: list[dict[str, Any]] = [x for x in parsed if isinstance(x, dict)]
    generated = len(items)
    if generated == 0:
        return GenerationResult(
            requested=count,
            generated=0,
            inserted=0,
            skipped=count,
        )

    normalized: list[dict[str, Any]] = []
    exclude_set = {str(q).strip().lower() for q in (exclude_questions or []) if str(q).strip()}
    for it in items:
        if check_cancel and check_cancel():
            break
        payload = _normalize_rich_daily_item(it, subject=subject, level=level)
        if payload:
            q_text = str(payload.get("question") or payload.get("prompt") or "").strip().lower()
            if q_text in exclude_set:
                logger.info("generate_daily_test_questions: skipping duplicate question from AI: %s", q_text)
                continue
            normalized.append(payload)

    inserted = 0
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        for payload in normalized:
            qt = str(payload.get("question_type") or "grammar_sentence").strip().lower()
            opts = _clean_options(payload.get("options"), None)
            if len(opts) < 4:
                continue
            opts2 = (opts + ["-", "-", "-", "-"])[:4]
            try:
                coi_int = int(payload.get("correct_option_index") or 1)
            except Exception:
                coi_int = 1
            coi_int = max(1, min(4, coi_int))
            q = str(payload.get("question") or payload.get("prompt") or "").strip()
            if level == "MIXED":
                row_level = _normalize_generated_level(str(payload.get("level") or ""))
            else:
                row_level = level.upper()
            payload_json = json.dumps(payload, ensure_ascii=False)
            cur.execute(
                """
                INSERT INTO daily_tests_bank
                (created_by, subject, level, question, option_a, option_b, option_c, option_d, correct_option_index, question_type, payload_json, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    created_by,
                    subject,
                    row_level,
                    q,
                    opts2[0],
                    opts2[1],
                    opts2[2],
                    opts2[3],
                    coi_int,
                    qt,
                    payload_json,
                ),
            )
            inserted += 1
        conn.commit()
        conn.close()
    skipped = max(0, int(count) - int(inserted))

    return GenerationResult(
        requested=count,
        generated=generated,
        inserted=inserted,
        skipped=skipped,
    )


def _assign_daily_test_set_sync(
    subject: str,
    level: str,
    test_date: str,
    created_by: Optional[int],
) -> None:
    """Pick 20 random active bank rows and store in daily_test_day_question_sets (PostgreSQL)."""
    del created_by  # reserved for future filtering
    if not _is_postgres_enabled():
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1 FROM daily_test_day_question_sets
            WHERE test_date=? AND subject=? AND level=?
            """,
            (test_date, subject, level),
        )
        if cur.fetchone():
            return

        cur.execute(
            """
            SELECT id FROM daily_tests_bank
            WHERE subject=? AND level=? AND active=1
            ORDER BY RANDOM() LIMIT 20
            """,
            (subject, level),
        )
        rows = cur.fetchall()
        if len(rows) < 20:
            logger.warning(
                "Only %s questions available for daily set %s %s on %s",
                len(rows),
                subject,
                level,
                test_date,
            )
        qids = [int(r["id"]) for r in rows]
        if not qids:
            return
        total_q = len(qids)
        payload = json.dumps(qids, ensure_ascii=False)
        cur.execute(
            """
            INSERT INTO daily_test_day_question_sets
                (test_date, subject, level, total_questions, bank_ids_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (test_date, subject, level) DO NOTHING
            """,
            (test_date, subject, level, total_q, payload),
        )
        conn.commit()
    finally:
        conn.close()


async def _assign_daily_test_set(
    subject: str,
    level: str,
    test_date: str,
    created_by: Optional[int],
) -> None:
    await asyncio.to_thread(_assign_daily_test_set_sync, subject, level, test_date, created_by)


async def generate_daily_tests_and_insert(
    *,
    subject: str,
    level: str,
    count: int = 20,
    created_by: Optional[int] = None,
    assign_today_set: bool = False,
    exclude_questions: list[str] | None = None,
) -> GenerationResult:
    """
    Generate new daily test items via Gemini and insert into `daily_tests_bank`.

    When ``assign_today_set`` is True (daily stock replenishment), each batch is
    exactly 20 questions and today's row in ``daily_test_day_question_sets`` is
    updated after a successful insert (PostgreSQL). Otherwise ``count`` is used
    as-is (arena/admin bulk generation) and no day-set assignment runs.
    """
    subject = (subject or "").strip().title()
    level = _normalize_level(level)

    if assign_today_set:
        count = 20
    else:
        count = int(count)
        if count <= 0:
            raise ValueError("count must be > 0")

    if subject not in ("English", "Russian"):
        raise ValueError("subject must be 'English' or 'Russian'")
    allowed_daily = allowed_levels_for_ai_pipeline(subject)
    if level not in allowed_daily:
        raise ValueError(f"level must be one of {sorted(allowed_daily)}")

    lock_key = (f"daily:{subject}", level)
    lock = _ai_generation_locks.setdefault(lock_key, asyncio.Lock())
    async with lock:
        result = await _generate_daily_test_questions(
            subject=subject,
            level=level,
            count=count,
            created_by=created_by,
            exclude_questions=exclude_questions,
        )
        if result.inserted == 0 or not assign_today_set:
            return result

        today = datetime.now(pytz.timezone("Asia/Tashkent")).date().isoformat()
        await _assign_daily_test_set(subject, level, today, created_by)
        return result


async def _generate_reading_questions_with_passage(
    *,
    subject: str,
    level: str,
    count: int = 2,
) -> list[dict[str, Any]]:
    """Generate `count` reading MCQs, each with a short passage (5–7 sentences).

    Returns question dicts compatible with competition format:
    keys: question, subject, option_a..d, correct_option_index, question_type, payload_json.
    payload_json includes: passage, time_limit_sec (60–120 s based on word count).
    """
    count = max(1, min(3, int(count)))
    is_russian = str(subject or "").strip().lower() == "russian"
    lang = "Russian" if is_russian else "English"

    if is_russian:
        lang_rule = "Все тексты, вопросы и варианты ответов — только на русском языке."
        passage_hint = (
            "Каждый текст: 5–7 предложений на тему повседневной жизни, учёбы, "
            "науки или природы. Предложения не должны быть слишком длинными. "
            "Уровень сложности: CEFR " + level + "."
        )
        instruction_text = "Прочитайте текст и выберите правильный ответ."
        skill_labels = [
            "главная мысль текста",
            "конкретная деталь из текста",
            "логический вывод из текста",
            "значение слова в контексте",
        ]
    else:
        lang_rule = "All passages, questions, and options must be in English."
        passage_hint = (
            "Each passage: 5–7 sentences about everyday life, study, science, or nature. "
            "Sentences should not be overly long. Appropriate for CEFR " + level + " learners."
        )
        instruction_text = "Read the passage and choose the correct answer."
        skill_labels = [
            "main idea of the passage",
            "specific detail from the passage",
            "logical inference from the passage",
            "meaning of a word in context",
        ]

    import random as _rnd
    skills = (_rnd.sample(skill_labels, min(count, len(skill_labels))) + skill_labels * 2)[:count]
    skill_lines = "\n".join(f"  - Question {i + 1}: test the «{s}»" for i, s in enumerate(skills))

    rules = f"""Generate EXACTLY {count} reading comprehension MCQ(s) for {lang} level {level}.

{lang_rule}

Each element must be a JSON object with these EXACT keys:
  - "passage": string — a short reading text of EXACTLY 5 to 7 sentences. {passage_hint}
  - "question": string — one comprehension question about the passage.
  - "options": array of EXACTLY 4 distinct strings (plausible distractors; only 1 correct).
  - "correct_option_index": integer 1..4 (1-indexed, must match the correct option).
  - "question_type": always the string "reading".

Comprehension skill targets:
{skill_lines}

IMPORTANT rules:
- passage MUST be 5–7 sentences — not shorter, not longer.
- All 4 options must be plausible; wrong options should NOT be obviously wrong.
- correct_option_index MUST point to the one correct answer in "options".
- Do NOT include the passage answer verbatim in the question text.
- Topics must be varied across questions (no two passages on the same topic).

Return ONLY a valid JSON array. No markdown, no explanation.""".strip()

    prompt = _wrap_json_only_prompt(rules)

    async with aiohttp.ClientSession() as sess:
        raw_text = await _gemini_generate(prompt, session=sess)

    try:
        parsed = _extract_json_array(raw_text)
    except Exception as exc:
        logger.warning("_generate_reading_questions_with_passage: JSON parse failed: %s", exc)
        return []

    if not isinstance(parsed, list):
        return []

    results: list[dict[str, Any]] = []
    for it in parsed:
        if not isinstance(it, dict):
            continue
        passage = str(it.get("passage") or "").strip()
        question = str(it.get("question") or "").strip()
        if not passage or not question:
            continue
        opts_raw = it.get("options") or []
        if not isinstance(opts_raw, list):
            continue
        opts = [str(o).strip() for o in opts_raw if str(o).strip()]
        if len(opts) < 4:
            continue
        opts = opts[:4]

        # Validate / trim passage length (5-7 sentences)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", passage) if s.strip()]
        if len(sentences) < 3:
            continue  # too short — skip
        if len(sentences) > 7:
            passage = " ".join(sentences[:7])
            if not passage.endswith((".", "!", "?")):
                passage += "."

        try:
            coi = max(1, min(4, int(it.get("correct_option_index") or 1)))
        except Exception:
            coi = 1

        # time_limit_sec: 60–120 s based on total word count
        all_text = " ".join([passage, question] + opts)
        word_count = len(all_text.split())
        time_sec = min(120, max(60, 30 + int(word_count * 0.85)))

        payload: dict[str, Any] = {
            "question_type": "reading",
            "instruction": instruction_text,
            "passage": passage,
            "question": question,
            "prompt": question,
            "options": opts,
            "correct_option_index": coi,
            "subject": subject,
            "level": level,
            "time_limit_sec": time_sec,
        }
        results.append({
            "question": question,
            "subject": subject,
            "level": level,
            "option_a": opts[0],
            "option_b": opts[1],
            "option_c": opts[2],
            "option_d": opts[3],
            "correct_option_index": coi,
            "question_type": "reading",
            "payload_json": json.dumps(payload, ensure_ascii=False),
        })
        if len(results) >= count:
            break

    logger.info(
        "_generate_reading_questions_with_passage: subject=%s level=%s requested=%s got=%s",
        subject, level, count, len(results),
    )
    return results


async def _generate_gamified_vocab(*, subject: str, level: str, count: int = 16, session_nonce: str | None = None) -> list[dict[str, str]]:
    """Fresh AI vocab batch for a gamified test — each item is
    {word, tr (Uzbek translation), ex (short example sentence containing the
    word verbatim)}, matching the shape the gamified builders expect. The
    verbatim-word requirement is enforced so the fill-gap / word-order
    builders can locate the target token. Best-effort: returns whatever
    validated items it got (possibly empty) so the caller can fall back."""
    count = max(6, min(24, int(count)))
    is_russian = str(subject or "").strip().lower() == "russian"
    if is_russian:
        lang_rule = (
            "\"word\" — русское слово; \"tr\" — его перевод на узбекский язык; "
            "\"ex\" — короткое предложение (4–7 слов) на русском, содержащее слово \"word\" в точности."
        )
    else:
        lang_rule = (
            "\"word\" is an English word; \"tr\" is its Uzbek translation; "
            "\"ex\" is a short 4–7 word English sentence that contains \"word\" verbatim."
        )
    rules = f"""Generate EXACTLY {count} vocabulary items for {subject} at CEFR level {level}.

Each element must be a JSON object with these EXACT keys:
  - "word": string
  - "tr": string
  - "ex": string

Field rules:
- {lang_rule}
- The example "ex" MUST contain "word" exactly as written (same spelling).
- Keep "ex" short and simple (4–7 words), no punctuation except a final period is optional.
- Vary the words; do not repeat. Keep everything age-appropriate and educational.
- Freshness nonce for this one attempt: {session_nonce or "none"}. Use it only to vary topic/word choices; do not include it in the JSON.

Return ONLY a valid JSON array. No markdown, no explanation.""".strip()
    prompt = _wrap_json_only_prompt(rules)

    async with aiohttp.ClientSession() as sess:
        raw_text = await _gemini_generate(prompt, session=sess)
    try:
        parsed = _extract_json_array(raw_text)
    except Exception as exc:
        logger.warning("_generate_gamified_vocab: JSON parse failed: %s", exc)
        return []
    if not isinstance(parsed, list):
        return []

    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for it in parsed:
        if not isinstance(it, dict):
            continue
        word = str(it.get("word") or "").strip()
        tr = str(it.get("tr") or it.get("translation_uz") or "").strip()
        ex = str(it.get("ex") or it.get("example") or "").strip()
        if not word or not tr or not ex:
            continue
        key = word.lower()
        if key in seen:
            continue
        # The builders locate the target token in the example — require it.
        if word.lower() not in ex.lower():
            continue
        seen.add(key)
        out.append({"word": word, "tr": tr, "ex": ex})
    logger.info("_generate_gamified_vocab: subject=%s level=%s requested=%s got=%s", subject, level, count, len(out))
    return out


async def generate_gamified_material(*, subject: str, level: str, vocab_count: int = 16, reading_count: int = 3, session_nonce: str | None = None) -> dict[str, Any]:
    """Fresh, per-attempt raw material for a gamified test: an AI vocab batch
    plus AI reading passages. Returns {"vocab": [...], "readings": [...]}
    where readings are {passage, question, options, answer_index}. Fully
    best-effort — any failure yields an empty list for that part so the
    caller (gamified_tests.build_questions) falls back to the static bank."""
    result: dict[str, Any] = {"vocab": [], "readings": []}
    try:
        result["vocab"] = await _generate_gamified_vocab(subject=subject, level=level, count=vocab_count, session_nonce=session_nonce)
    except Exception:
        logger.exception("generate_gamified_material: vocab generation failed")
    try:
        raw_readings = await _generate_reading_questions_with_passage(subject=subject, level=level, count=reading_count)
        readings: list[dict[str, Any]] = []
        for r in raw_readings:
            try:
                payload = json.loads(r.get("payload_json") or "{}")
            except Exception:
                payload = {}
            opts = payload.get("options") or []
            coi = int(payload.get("correct_option_index") or 0) - 1  # 1-indexed -> 0-indexed
            if len(opts) >= 4 and 0 <= coi < len(opts):
                readings.append({
                    "passage": payload.get("passage", ""),
                    "question": payload.get("question", ""),
                    "options": opts[:4],
                    "answer_index": coi,
                })
        result["readings"] = readings
    except Exception:
        logger.exception("generate_gamified_material: reading generation failed")
    return result


async def ensure_vocabulary_stock_for_student_level(
    *,
    subject: str,
    level: str,
    min_words: int,
    added_by: Optional[int] = None,
) -> GenerationResult:
    """
    If we have less than `min_words` words for (subject, level), generate the missing amount.
    """
    subject = (subject or "").strip().title()
    level = _normalize_level(level)
    min_words = int(min_words)
    if min_words <= 0:
        return GenerationResult(requested=0, generated=0, inserted=0, skipped=0)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) as c FROM words WHERE subject=? AND level=?",
        (subject, level),
    )
    row = cur.fetchone()
    conn.close()
    have = int(row["c"] or 0) if row else 0
    if have >= min_words:
        return GenerationResult(
            requested=0,
            generated=0,
            inserted=0,
            skipped=0,
        )
    need = min_words - have
    return await generate_vocabulary_and_insert_exact(
        subject=subject,
        level=level,
        target_count=need,
        added_by=added_by,
    )


async def ensure_daily_tests_stock_for_student_level(
    *,
    subject: str,
    level: str,
    min_questions: int,
    created_by: Optional[int] = None,
) -> GenerationResult:
    """
    If daily test stock (unused items) is less than `min_questions`,
    generate the missing number of daily test items.
    """
    from db import count_available_daily_tests

    subject = (subject or "").strip().title()
    level = _normalize_level(level)
    min_questions = int(min_questions)
    if min_questions <= 0:
        return GenerationResult(requested=0, generated=0, inserted=0, skipped=0)

    have = count_available_daily_tests(subject=subject, level=level)
    if have >= min_questions:
        return GenerationResult(
            requested=0,
            generated=0,
            inserted=0,
            skipped=0,
        )

    total_requested = total_generated = total_inserted = total_skipped = 0
    max_iters = 50
    for _ in range(max_iters):
        have = count_available_daily_tests(subject=subject, level=level)
        if have >= min_questions:
            break
        r = await generate_daily_tests_and_insert(
            subject=subject,
            level=level,
            created_by=created_by,
            assign_today_set=True,
        )
        total_requested += r.requested
        total_generated += r.generated
        total_inserted += r.inserted
        total_skipped += r.skipped
        if r.inserted == 0:
            break

    return GenerationResult(
        requested=total_requested,
        generated=total_generated,
        inserted=total_inserted,
        skipped=total_skipped,
    )


async def generate_arena_questions_and_insert(
    *,
    subject: str,
    level: str,
    count: int,
    created_by: Optional[int],
) -> GenerationResult:
    """
    Arena question generator (best-effort).

    Current implementation reuses the existing daily generator to ensure:
    - poll-ready multiple-choice options (4 distinct options)
    - correct_option_index is consistent (1..4)

    Then it copies the freshly generated rows into `arena_questions_bank`.
    """
    if created_by is None:
        raise ValueError("created_by must be provided to seed arena questions.")

    subject = (subject or "").strip().title()
    level = (level or "").strip().upper()
    count = int(count)

    if count <= 0:
        return GenerationResult(requested=0, generated=0, inserted=0)

    start_ts = datetime.utcnow()

    # Generate into `daily_tests_bank`.
    await generate_daily_tests_and_insert(
        subject=subject,
        level=level,
        count=count,
        created_by=created_by,
    )

    # Select generated daily rows created in this window.
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            SELECT id
            FROM daily_tests_bank
            WHERE created_by=? AND subject=? AND level=?
              AND active=1 AND created_at >= ?
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            ''',
            (int(created_by), subject, level, start_ts, count),
        )
        rows = cur.fetchall() or []
        bank_ids = [
            int(r["id"]) if isinstance(r, dict) or hasattr(r, "get") else int(r[0])
            for r in rows
        ]
    finally:
        conn.close()

    if not bank_ids:
        return GenerationResult(
            requested=count,
            generated=count,
            inserted=0,
            skipped=0,
            raw_parse_warnings=(),
        )

    arena_ids = copy_daily_tests_bank_rows_to_arena_questions(
        bank_ids=bank_ids,
        created_by=int(created_by),
    )

    return GenerationResult(
        requested=count,
        generated=len(bank_ids),
        inserted=len(arena_ids),
        skipped=max(0, len(bank_ids) - len(arena_ids)),
        raw_parse_warnings=(),
    )


async def populate_daily_arena_run_questions(
    *,
    run_id: int,
    subject: str,
    level: str = "B1",
    created_by: int = 0,
) -> bool:
    """
    Insert 5 stages x 10 MCQ into arena_run_questions (stages 1..5).
    Reuses generate_daily_tests_and_insert then copies last batch into arena payload JSON.
    """
    import json

    from db import insert_arena_run_question, ensure_arena_run_questions_user_id_column

    ensure_arena_run_questions_user_id_column()
    subject = (subject or "").strip().title()
    level = _normalize_level(level)

    for stage in range(1, 6):
        await generate_daily_tests_and_insert(
            subject=subject,
            level=level,
            count=10,
            created_by=created_by,
        )
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT question, option_a, option_b, option_c, option_d, correct_option_index
            FROM daily_tests_bank
            WHERE created_by=? AND subject=? AND active=1
            ORDER BY id DESC
            LIMIT 10
            """,
            (int(created_by), subject),
        )
        rows = list(reversed(cur.fetchall() or []))
        conn.close()
        for i, r in enumerate(rows, start=1):
            row = dict(r)
            payload = {
                "question": str(row.get("question") or ""),
                "option_a": str(row.get("option_a") or ""),
                "option_b": str(row.get("option_b") or ""),
                "option_c": str(row.get("option_c") or ""),
                "option_d": str(row.get("option_d") or ""),
                "correct_option_index": int(row.get("correct_option_index") or 1),
            }
            insert_arena_run_question(run_id, stage, i, json.dumps(payload), None)
    return True


async def generate_daily_arena_stage_questions_and_insert(
    *,
    run_id: int,
    stage: int,
    subject: str,
    progress_cb: Optional[Callable[[int, int, int], Awaitable[None] | None]] = None,
    created_by: int = 0,
) -> int:
    """
    Generate exactly 10 Daily Arena MCQs for a given `stage` and insert into `arena_run_questions`.

    Payload JSON format (stored in `arena_run_questions.payload_json`):
      - question: string
      - option_a..option_d: strings (4 options)
      - correct_option_index: integer 1..4
      - question_type: one of:
          reading, grammar, sentence_error, true_false, synonym, antonym, gap_fill, vocab_definition

    If `progress_cb` is provided, it is called after each inserted question:
      progress_cb(pct, current, total)
    """
    import aiohttp

    from db import fetch_arena_run_questions, insert_arena_run_question, ensure_arena_run_questions_user_id_column

    subject = (subject or "").strip().title()
    stage = int(stage)
    run_id = int(run_id)
    created_by = int(created_by or 0)

    if subject not in ("English", "Russian"):
        raise ValueError("subject must be 'English' or 'Russian'")
    if stage not in (1, 2, 3, 4, 5):
        raise ValueError("stage must be in [1..5]")

    total = 10

    # Stage difficulty / CEFR hints (used mainly for prompt shaping + payload metadata).
    if subject == "English":
        level = {1: "B2", 2: "B2", 3: "B2", 4: "C1", 5: "C1"}.get(stage, "B2")
    else:
        # Russian: ramp from B1 to B2.
        level = {1: "B1", 2: "B1", 3: "B2", 4: "B2", 5: "B2"}.get(stage, "B2")

    allowed_types = [
        "reading",
        "grammar",
        "sentence_error",
        "true_false",
        "synonym",
        "antonym",
        "gap_fill",
        "vocab_definition",
    ]

    # Simple, explicit distribution by stage (sums to 10 each).
    if stage == 1:
        type_counts = {
            "grammar": 4,
            "sentence_error": 2,
            "true_false": 1,
            "gap_fill": 1,
            "vocab_definition": 1,
            "synonym": 1,
            "antonym": 0,
            "reading": 0,
        }
    elif stage == 2:
        type_counts = {
            "grammar": 1,
            "sentence_error": 1,
            "true_false": 1,
            "synonym": 2,
            "antonym": 2,
            "gap_fill": 2,
            "vocab_definition": 1,
            "reading": 0,
        }
    elif stage == 3:
        type_counts = {
            "grammar": 0,
            "sentence_error": 1,
            "true_false": 1,
            "synonym": 3,
            "antonym": 2,
            "gap_fill": 2,
            "vocab_definition": 1,
            "reading": 0,
        }
    elif stage == 4:
        type_counts = {
            "grammar": 1,
            "sentence_error": 1,
            "true_false": 1,
            "synonym": 2,
            "antonym": 1,
            "gap_fill": 1,
            "vocab_definition": 2,
            "reading": 1,
        }
    else:  # stage == 5 (hardest)
        type_counts = {
            "reading": 2,
            "grammar": 0,
            "sentence_error": 1,
            "true_false": 1,
            "synonym": 2,
            "antonym": 1,
            "gap_fill": 1,
            "vocab_definition": 2,
        }

    # Lock to avoid parallel generation for the same run/stage in-process.
    lock_key = (f"daily_arena_stage:{run_id}:{stage}", subject)
    lock = _ai_generation_locks.setdefault(lock_key, asyncio.Lock())

    async with lock:
        existing = fetch_arena_run_questions(run_id, stage, None)
        if len(existing) >= total:
            return len(existing)

        # Replace stage content (avoid duplicates if stage got partially filled).
        conn = get_conn()
        cur = conn.cursor()
        try:
            # Daily arena inserts with `user_id IS NULL`.
            cur.execute(
                """
                DELETE FROM arena_run_questions
                WHERE run_id=? AND stage=? AND user_id IS NULL
                """,
                (run_id, stage),
            )
            conn.commit()
        finally:
            conn.close()

        # Build strict JSON prompt.
        type_lines = "\n".join([f"- {k}: {int(v)}" for k, v in type_counts.items() if int(v) > 0])
        if not type_lines:
            raise RuntimeError("Daily arena stage question type distribution is empty.")

        difficulty_note = {
            1: "easy",
            2: "medium",
            3: "medium-hard",
            4: "hard",
            5: "max-hard",
        }.get(stage, "medium")
        lang_hint = "English" if subject == "English" else "Russian"

        rules = f"""
Generate EXACTLY {total} Daily Arena MCQs ({lang_hint}) for stage {stage} (difficulty: {difficulty_note}).

Each element must be an object with EXACT keys:
  - question (string)
  - options (array of 4 strings, all distinct)
  - correct_option_index (integer 1..4, 1-indexed)
  - question_type (one of: {", ".join(allowed_types)})

Rules:
- Make distractors plausible and non-trivial (especially for stage 5).
- Keep everything in {lang_hint}.
- `question_type` must match how the question is constructed:
    reading -> reading comprehension / context + choose best answer
    grammar -> grammar rule / correct form selection
    sentence_error -> pick the sentence with an error or correct it
    true_false -> statement + choose correct True/False-related option
    synonym -> choose the synonym of a given word
    antonym -> choose the antonym of a given word
    gap_fill -> sentence with a blank; choose the best word/phrase
    vocab_definition -> match a word to its best definition
- correct_option_index must match the correct option in `options`.

Generate with the following EXACT type counts:
{type_lines}
""".strip()

        prompt = _wrap_json_only_prompt(rules)

        async with aiohttp.ClientSession() as session:
            text = await _gemini_generate(prompt, session=session)

        parsed = _extract_json_array(text)
        if not isinstance(parsed, list):
            raise RuntimeError("Daily arena stage generator did not return JSON array.")

        items: list[dict[str, Any]] = [x for x in parsed if isinstance(x, dict)]
        if not items:
            return 0

        # Insert stage questions in order.
        inserted = 0
        current = 0

        for it in items:
            if inserted >= total:
                break

            q = str(it.get("question") or "").strip()
            opts = it.get("options") or []
            if not q or not isinstance(opts, list) or len(opts) != 4:
                continue

            opts2 = [str(o).strip() for o in opts]

            coi = it.get("correct_option_index")
            try:
                coi_int = int(coi)
            except Exception:
                coi_int = 1
            coi_int = max(1, min(4, coi_int))

            qt = str(it.get("question_type") or "").strip()
            if qt not in allowed_types:
                qt = "grammar"

            current += 1
            payload = {
                "question": q,
                "option_a": opts2[0],
                "option_b": opts2[1],
                "option_c": opts2[2],
                "option_d": opts2[3],
                "correct_option_index": coi_int,
                "question_type": qt,
                "level": level,
                "created_by": created_by,
            }

            insert_arena_run_question(
                run_id=run_id,
                stage=stage,
                q_index=inserted + 1,
                payload_json=json.dumps(payload, ensure_ascii=True),
                user_id=None,
            )
            inserted += 1

            if progress_cb is not None:
                pct = int(round((inserted / total) * 100))
                r = progress_cb(pct, inserted, total)
                if asyncio.iscoroutine(r):
                    await r

        return inserted


async def populate_boss_arena_run_questions(
    *,
    run_id: int,
    subject: str,
    level: str = "B1",
    pool_size: int = 15,
    created_by: int = 0,
) -> bool:
    """
    Boss pool: stage=0, sequential q_index, user_id NULL until assigned per participant.
    """
    import json

    from db import insert_arena_run_question, ensure_arena_run_questions_user_id_column

    ensure_arena_run_questions_user_id_column()
    subject = (subject or "").strip().title()
    level = _normalize_level(level)
    pool_size = max(3, int(pool_size))

    await generate_daily_tests_and_insert(
        subject=subject,
        level=level,
        count=pool_size,
        created_by=created_by,
    )
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT question, option_a, option_b, option_c, option_d, correct_option_index
        FROM daily_tests_bank
        WHERE created_by=? AND subject=? AND active=1
        ORDER BY id DESC
        LIMIT ?
        """,
        (int(created_by), subject, pool_size),
    )
    rows = list(reversed(cur.fetchall() or []))
    conn.close()
    for i, r in enumerate(rows, start=1):
        row = dict(r)
        payload = {
            "question": str(row.get("question") or ""),
            "option_a": str(row.get("option_a") or ""),
            "option_b": str(row.get("option_b") or ""),
            "option_c": str(row.get("option_c") or ""),
            "option_d": str(row.get("option_d") or ""),
            "correct_option_index": int(row.get("correct_option_index") or 1),
        }
        insert_arena_run_question(run_id, 0, i, json.dumps(payload), None)
    return True
