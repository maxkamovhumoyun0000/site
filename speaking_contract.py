"""Pure request-to-record rules for the Speaking media-admin API."""
from __future__ import annotations

from typing import Any
import hashlib
import re

TOPIC_STATUS_BADGES = frozenset({"COMMON", "PREDICTED", "HIGH FREQUENCY"})
PREDICTED_STATUS_LABEL = "PREDICTED TILL THE END OF 2026"
MAX_BATCH_TOPIC_COUNT = 5
MAX_QUESTION_GENERATION_COUNT = 10
MIN_BATCH_QUESTIONS_PER_TOPIC = 4
# Catalogue fills run as durable background jobs, so they can safely accept a
# fuller plan than the regular one-request AI generator.
MAX_CATALOG_TOPIC_COUNT = 30
MAX_CATALOG_QUESTION_TARGET = 30


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


def normalize_catalog_topic_titles(value: Any) -> tuple[str, ...]:
    """Clean a manually supplied catalogue list without creating duplicates."""
    if not isinstance(value, list):
        raise ValueError("topics must be a list")
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        title = " ".join(str(item or "").split()).strip()
        if not title:
            continue
        if len(title) > 180:
            raise ValueError("each topic title must be at most 180 characters")
        key = title.casefold()
        if key not in seen:
            cleaned.append(title)
            seen.add(key)
    if len(cleaned) > MAX_CATALOG_TOPIC_COUNT:
        raise ValueError(f"at most {MAX_CATALOG_TOPIC_COUNT} topics can be filled at once")
    return tuple(cleaned)


def normalize_catalog_question_target(
    mode: Any,
    *,
    exact_count: Any = None,
    minimum_count: Any = None,
    maximum_count: Any = None,
) -> tuple[int, int]:
    """Validate a fixed or varied final question total for every topic."""
    normalized_mode = str(mode or "").strip().lower()

    def normalize(value: Any, label: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{label} must be between 1 and {MAX_CATALOG_QUESTION_TARGET}")
        try:
            count = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{label} must be between 1 and {MAX_CATALOG_QUESTION_TARGET}"
            ) from exc
        if not 1 <= count <= MAX_CATALOG_QUESTION_TARGET:
            raise ValueError(f"{label} must be between 1 and {MAX_CATALOG_QUESTION_TARGET}")
        return count

    if normalized_mode == "exact":
        exact = normalize(exact_count, "exact_question_count")
        return exact, exact
    if normalized_mode == "range":
        minimum = normalize(minimum_count, "minimum_question_count")
        maximum = normalize(maximum_count, "maximum_question_count")
        if minimum > maximum:
            raise ValueError("minimum_question_count cannot exceed maximum_question_count")
        return minimum, maximum
    raise ValueError("question_target_mode must be exact or range")


def minimum_questions_for_requested_limit(value: Any) -> int:
    """Return the minimum useful batch size without forcing the selected cap.

    The media admin's value is a maximum.  A request for ten should not fail
    merely because the provider supplied four strong questions, while requests
    below four retain their exact requested count.
    """
    return min(normalize_question_generation_count(value), MIN_BATCH_QUESTIONS_PER_TOPIC)


def variable_batch_question_targets(value: Any, topic_count: Any, seed: Any) -> list[int]:
    """Plan varied per-topic counts within the requested maximum.

    A digest-derived rotation is intentionally stable for the same batch input,
    but distributes topic counts across the allowed range rather than making
    every saved topic have the same minimum count.
    """
    maximum = normalize_question_generation_count(value)
    topics = normalize_batch_topic_count(topic_count)
    minimum = minimum_questions_for_requested_limit(maximum)
    span = maximum - minimum + 1
    if span == 1:
        return [minimum] * topics
    digest = hashlib.sha256(str(seed or "speaking-batch").encode("utf-8")).digest()
    start = int.from_bytes(digest[:4], "big") % span
    return [minimum + ((start + index) % span) for index in range(topics)]


def part_two_cue_card_fallback(question_text: Any) -> list[str]:
    """Build four cue-card prompts that still reflect the actual question.

    The AI normally supplies these prompts.  This fallback prevents a malformed
    provider response from making every Part 2 card show the same generic
    ``You should say`` text.
    """
    text = " ".join(str(question_text or "").split()).strip(" ?.")
    subject = re.sub(r"^(?:describe|talk about|tell me about)\s+", "", text, flags=re.IGNORECASE)
    # A cue card must help the learner plan *their own* answer. If a legacy
    # question itself contains a name, place or year, do not carry that fact
    # into the fallback guidance as though it were part of a model response.
    subject = re.sub(
        r"\b(?:named|called|with|from|in|at)\s+[A-Z][A-Za-z'’-]{1,}\b",
        "",
        subject,
    )
    subject = re.sub(r"\b(?:19|20)\d{2}\b", "", subject)
    subject = re.sub(r"\s{2,}", " ", subject).strip(" ,;:-")
    subject = subject[:160].strip(" ?.") or "the experience or thing in the cue card"
    return [
        f"The key details of {subject}",
        f"When, where and how {subject} was part of your experience",
        f"The people, actions or events connected with {subject}",
        f"And explain why {subject} was meaningful to you",
    ]


def cue_card_bullets_are_open_ended(points: Any) -> bool:
    """Reject cue-card bullets that prescribe a model answer's private facts.

    Names, dates and exact locations belong in a learner's answer, never in
    ``You should say`` planning prompts. The provider still has flexibility to
    tailor prompts to a question; this guard only falls back when it starts
    inventing a story for the learner.
    """
    if not isinstance(points, list) or len(points) < 4:
        return False
    cleaned = [" ".join(str(point or "").split()) for point in points[:4]]
    if any(not point for point in cleaned):
        return False
    combined = " ".join(cleaned)
    if re.search(r"\b(?:19|20)\d{2}\b", combined):
        return False
    # These constructions expose an invented proper noun in context, while
    # allowing normal bullet openings such as "Describe the person...".
    if re.search(
        r"\b(?:named|called|with|from|in|at|to|visited)\s+[A-Z][A-Za-z'’-]{1,}\b",
        combined,
    ):
        return False
    return True


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
