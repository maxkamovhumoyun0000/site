from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Any

from grammar_content import ALL_GRAMMAR_TOPICS, get_topic as _legacy_get_topic, get_topics_by_level as _legacy_get_topics_by_level


SUPPORTED_LEVELS = ("A1", "A2", "B1", "B2", "C1")


def _normalize_subject(subject: str | None) -> str | None:
    value = str(subject or "").strip()
    return value.title() if value else None


@lru_cache(maxsize=1)
def _catalog_signature() -> str:
    compact: list[dict[str, Any]] = []
    for topic in list(ALL_GRAMMAR_TOPICS or []):
        compact.append(
            {
                "topic_id": str(getattr(topic, "topic_id", "") or ""),
                "level": str(getattr(topic, "level", "") or ""),
                "subject": str(getattr(topic, "subject", "English") or "English"),
                "title": str(getattr(topic, "title", "") or ""),
                "question_count": len(list(getattr(topic, "questions", []) or [])),
            }
        )
    payload = json.dumps(compact, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def catalog_meta() -> dict[str, str]:
    return {
        "grammar_source": "backend/grammar_catalog.py->grammar_content.py",
        "grammar_catalog_version": _catalog_signature(),
    }


def _clean_text(value: Any) -> str:
    text = str(value or "")
    for _ in range(3):
        next_text = (
            text.replace("\\r\\n", "\n")
            .replace("\\n", "\n")
            .replace("\\r", "\n")
            .replace("\\t", " ")
        )
        if next_text == text:
            break
        text = next_text
    return text.strip()


def get_topics_by_level(level: str, subject: str | None = None) -> list[Any]:
    normalized_level = str(level or "").strip().upper()
    if normalized_level not in SUPPORTED_LEVELS:
        return []
    normalized_subject = _normalize_subject(subject)
    return list(_topics_by_level_cached(normalized_level, normalized_subject))


@lru_cache(maxsize=32)
def _topics_by_level_cached(level: str, subject: str | None) -> tuple[Any, ...]:
    return tuple(_legacy_get_topics_by_level(level, subject=subject) or [])


def get_topic(level: str, topic_id: str, subject: str | None = None) -> Any | None:
    normalized_level = str(level or "").strip().upper()
    if normalized_level not in SUPPORTED_LEVELS:
        return None
    topic_key = str(topic_id or "").strip()
    if not topic_key:
        return None
    normalized_subject = _normalize_subject(subject)
    cached = _topic_lookup_cached(normalized_level, topic_key, normalized_subject)
    if cached:
        return cached
    return _legacy_get_topic(normalized_level, topic_key, subject=normalized_subject)


@lru_cache(maxsize=1024)
def _topic_lookup_cached(level: str, topic_id: str, subject: str | None) -> Any | None:
    for item in _topics_by_level_cached(level, subject):
        if str(getattr(item, "topic_id", "")).strip() == topic_id:
            return item
    return None


def resolve_topic_with_fallback(subject: str, preferred_level: str, topic_id: str) -> tuple[Any | None, str]:
    normalized_subject = _normalize_subject(subject) or "English"
    norm_preferred = str(preferred_level or "A1").strip().upper()
    if norm_preferred not in SUPPORTED_LEVELS:
        norm_preferred = "A1"
    ordered = [norm_preferred, *[lvl for lvl in SUPPORTED_LEVELS if lvl != norm_preferred]]

    for level_ref in ordered:
        topic = get_topic(level_ref, topic_id, subject=normalized_subject)
        if topic:
            return topic, level_ref

    topic_key = str(topic_id or "").strip()
    for level_ref in ordered:
        rows = get_topics_by_level(level_ref, subject=normalized_subject)
        for row in rows:
            if str(getattr(row, "topic_id", "")).strip() == topic_key:
                return row, level_ref
    return None, norm_preferred


def normalize_question_payload(question: Any) -> dict[str, Any] | None:
    prompt = _clean_text(getattr(question, "prompt", ""))
    raw_options = list(getattr(question, "options", []) or [])
    try:
        original_correct_index = int(getattr(question, "correct_index", 0))
    except Exception:
        original_correct_index = 0

    # Build filtered options while tracking original→new index mapping
    # so that if blank options are removed, correct_index stays valid.
    options: list[str] = []
    index_remap: dict[int, int] = {}  # original_idx -> new_idx
    for orig_idx, opt in enumerate(raw_options):
        cleaned = _clean_text(opt)
        if cleaned:
            index_remap[orig_idx] = len(options)
            options.append(cleaned)

    if len(options) < 2:
        return None

    # Re-map correct_index using the remap table; fall back to 0 if not found
    correct_index = index_remap.get(original_correct_index, 0)
    # Safety clamp
    if correct_index < 0 or correct_index >= len(options):
        correct_index = 0

    return {
        "prompt": prompt or "Savol",
        "options": options,
        "correct_index": correct_index,
    }


def serialize_topic_payload(topic: Any, *, preview_limit: int | None = 5) -> dict[str, Any]:
    topic_id = str(getattr(topic, "topic_id", "") or "").strip()
    if not topic_id:
        raise ValueError("Grammar topic has no topic_id")

    title = _clean_text(getattr(topic, "title", "") or "Grammar") or "Grammar"
    rule = _clean_text(getattr(topic, "rule", ""))
    raw_questions = list(getattr(topic, "questions", []) or [])
    if preview_limit is None or int(preview_limit or 0) <= 0:
        questions_for_payload = raw_questions
    else:
        questions_for_payload = raw_questions[: int(preview_limit)]

    normalized_questions: list[dict[str, Any]] = []
    for question in questions_for_payload:
        payload = normalize_question_payload(question)
        if payload:
            normalized_questions.append(payload)

    out = {
        "topic_id": topic_id,
        "title": title,
        "rule": rule,
        "question_count": len(raw_questions),
        "questions": normalized_questions,
    }
    out.update(catalog_meta())
    return out
