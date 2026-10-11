"""Pure request-to-record rules for the Speaking media-admin API."""
from __future__ import annotations

from typing import Any
import re

TOPIC_STATUS_BADGES = frozenset({"COMMON", "PREDICTED", "HIGH FREQUENCY"})
PREDICTED_STATUS_LABEL = "PREDICTED TILL THE END OF 2026"
MAX_BATCH_TOPIC_COUNT = 5
MAX_QUESTION_GENERATION_COUNT = 10


def normalize_topic_status(value: Any) -> str:
    """Return the canonical status badge accepted for a Speaking topic."""
    status = str(value or "").strip().upper()
    if status not in TOPIC_STATUS_BADGES:
        raise ValueError("status_badge must be COMMON, PREDICTED, or HIGH FREQUENCY")
    return status


def display_topic_status(value: Any) -> str:
    """Return the user-facing label while keeping stored values canonical."""
    try:
        status = normalize_topic_status(value)
    except ValueError:
        status = "PREDICTED"
    return PREDICTED_STATUS_LABEL if status == "PREDICTED" else status


def normalize_batch_topic_count(value: Any) -> int:
    """Validate the number of topics generated or saved in one batch."""
    if isinstance(value, bool):
        raise ValueError(f"topic_count must be between 1 and {MAX_BATCH_TOPIC_COUNT}")
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"topic_count must be between 1 and {MAX_BATCH_TOPIC_COUNT}") from exc
    if not 1 <= count <= MAX_BATCH_TOPIC_COUNT:
        raise ValueError(f"topic_count must be between 1 and {MAX_BATCH_TOPIC_COUNT}")
    return count


def individual_ai_topic_generation_count(value: Any) -> int:
    """Return the number of standalone AI calls required for a topic batch.

    A single large response with several topics, long model answers, and
    vocabulary can be truncated by an AI provider. Generating each topic as a
    normal one-topic response keeps every response within its output budget.
    """
    count = normalize_batch_topic_count(value)
    return count if count > 1 else 0


def normalize_question_generation_count(value: Any) -> int:
    """Validate the number of questions requested from the Speaking AI."""
    if isinstance(value, bool):
        raise ValueError(
            f"question_count must be between 1 and {MAX_QUESTION_GENERATION_COUNT}"
        )
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"question_count must be between 1 and {MAX_QUESTION_GENERATION_COUNT}"
        ) from exc
    if not 1 <= count <= MAX_QUESTION_GENERATION_COUNT:
        raise ValueError(
            f"question_count must be between 1 and {MAX_QUESTION_GENERATION_COUNT}"
        )
    return count


def part_two_cue_card_fallback(question_text: Any) -> list[str]:
    """Build four cue-card prompts that still reflect the actual question.

    The AI normally supplies these prompts.  This fallback prevents a malformed
    provider response from making every Part 2 card show the same generic
    ``You should say`` text.
    """
    text = " ".join(str(question_text or "").split()).strip(" ?.")
    subject = re.sub(r"^(?:describe|talk about|tell me about)\s+", "", text, flags=re.IGNORECASE)
    subject = subject[:160].strip(" ?.") or "the experience or thing in the cue card"
    return [
        f"The key details of {subject}",
        f"When, where and how {subject} was part of your experience",
        f"The people, actions or events connected with {subject}",
        f"And explain why {subject} was meaningful to you",
    ]


def public_sample_answer(value: Any, subject: Any) -> str:
    """Return an answer only for subjects that are allowed to expose one."""
    if str(subject or "english").strip().lower() in {"russian", "ru"}:
        return ""
    return str(value or "")


def question_insert_values_for_topic(payload: Any, topic: dict[str, Any]) -> dict[str, Any]:
    """Build a question record from its parent topic, not client-provided filters.

    The media UI can be left open while its filter changes. Using the topic as
    the source of truth prevents cross-part/cross-language question records and
    removes a common request-format failure on save.
    """
    part = int(topic.get("part") or 1)
    subject = str(topic.get("subject") or "english").strip().lower()
    bullets = [str(item).strip() for item in (payload.cue_card_bullet_points or []) if str(item).strip()]
    if subject == "russian" or part != 2:
        bullets = []
    answer = "" if subject == "russian" else (str(payload.sample_answer or "").strip() or "Sample answer to be reviewed.")
    return {
        "part": part,
        "subject": subject,
        "question_text": str(payload.question_text).strip(),
        "cue_card_bullet_points": bullets,
        "sample_answer": answer,
        "examiner_tip": payload.examiner_tip.strip() if payload.examiner_tip else None,
        "vocabulary": payload.vocabulary or [],
        "sort_order": payload.sort_order,
    }
