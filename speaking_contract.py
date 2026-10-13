"""Pure request-to-record rules for the Speaking media-admin API."""
from __future__ import annotations

from typing import Any
from datetime import datetime, timezone
import hashlib
import os
import re
import unicodedata

TOPIC_STATUS_BADGES = frozenset({"COMMON", "PREDICTED", "HIGH FREQUENCY"})
PREDICTED_STATUS_LABEL = "PREDICTED TILL THE END OF 2026"
MAX_BATCH_TOPIC_COUNT = 5
MAX_QUESTION_GENERATION_COUNT = 10
MIN_BATCH_QUESTIONS_PER_TOPIC = 4
# Catalogue fills run as durable background jobs, so they can safely accept a
# fuller plan than the regular one-request AI generator.
MAX_CATALOG_TOPIC_COUNT = 30
MAX_CATALOG_QUESTION_TARGET = 30
SPEAKING_APP_LOGIN_TYPE = 7


def is_speaking_verification_expired(value: Any, *, now: datetime | None = None) -> bool:
    """Compare verification expiry values as instants, not database strings.

    SQLite returns the stored ISO string while PostgreSQL returns ``datetime``.
    Lexicographic comparison makes a PostgreSQL value such as
    ``2026-10-13 10:10:00+00:00`` appear older than an ISO value containing
    ``T``.  Parsing both forms keeps a fresh email code valid on either DB.
    """
    if isinstance(value, datetime):
        expires_at = value
    else:
        try:
            expires_at = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        except ValueError:
            return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return expires_at <= current


def is_speaking_app_account(value: Any) -> bool:
    """Interpret the dedicated Speaking-app account marker conservatively."""
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def session_replacements_for_login(
    active_sessions: list[dict[str, Any]],
    *,
    limit: int,
    device_id: Any,
    requested_session_ids: Any,
) -> tuple[str, ...]:
    """Choose sessions that must end before a new authenticated device starts.

    A known device replaces only its own older session automatically.  A new
    device must explicitly name an existing session when the learner has
    reached the three-session student limit.  IDs are intersected with the
    authenticated user's active sessions here so a client cannot revoke a
    different account's session by guessing an identifier.
    """
    if limit <= 0:
        return ()
    rows = [row for row in active_sessions if str(row.get("session_id") or "").strip()]
    required = max(0, len(rows) + 1 - int(limit))
    if required == 0:
        return ()
    current_device = str(device_id or "").strip()
    valid_ids = {str(row.get("session_id") or "").strip() for row in rows}
    selected: list[str] = []
    if current_device:
        selected.extend(
            str(row.get("session_id") or "").strip()
            for row in rows
            if str(row.get("device_id") or "").strip() == current_device
        )
    if isinstance(requested_session_ids, (list, tuple, set)):
        for item in requested_session_ids:
            session_id = str(item or "").strip()
            if session_id and session_id in valid_ids and session_id not in selected:
                selected.append(session_id)
    if len(selected) < required:
        raise ValueError("session_limit_selection_required")
    return tuple(selected[:required])


def normalize_speaking_link_code(value: Any) -> str:
    """Validate a short, user-visible Student-to-Speaking approval code."""
    code = str(value or "").strip().upper().replace(" ", "")
    if re.fullmatch(r"SPEAK-[A-Z0-9]{8}", code):
        return code
    raise ValueError("invalid_speaking_link_code")


def normalize_speaking_email(value: Any) -> str:
    """Normalize a deliverable email without accepting display-name syntax."""
    email = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+", email):
        raise ValueError("invalid_speaking_email")
    if len(email) > 254:
        raise ValueError("invalid_speaking_email")
    return email


def speaking_account_state_label(deleted_at: Any) -> str:
    """The only public state labels for the dedicated admin list."""
    return "inactive" if str(deleted_at or "").strip() else "active"

# Public Speaking vocabulary lookup is intentionally family-safe. This is a
# narrow search filter, not a judgement on a learner: it prevents adult terms
# from being shown or sent to the paid AI fallback. Deployment owners may add
# locally relevant terms without publishing a new mobile build.
_SPEAKING_VOCABULARY_18_PLUS_TERMS = frozenset(
    {
        "porn",
        "pornography",
        "xxx",
        "onlyfans",
        "nude",
        "nudity",
        "sex",
        "sexual",
        "erotic",
        "порно",
        "порнография",
        "секс",
        "сексуальный",
        "эротика",
        "jinsiy",
        "porno",
        "yalangoch",
        "yalang'och",
        "yalang‘och",
    }
)


def normalize_speaking_voice_guest_name(value: Any) -> str:
    """Return a safe, short display name for an unauthenticated speaker.

    Voice-room guest labels are displayed to everyone in a live room, so
    control characters are stripped rather than echoed into WebSocket frames.
    This is deliberately a display label only; it never becomes an account.
    """
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    normalized = "".join(
        character
        for character in normalized
        if unicodedata.category(character)[0] != "C"
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized[:32].strip() or "Speaking learner"


def speaking_voice_guest_identity(value: Any) -> str | None:
    """Create a non-reversible room identity from a random app installation id."""
    raw = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", raw):
        return None
    return "guest-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def is_safe_speaking_vocabulary_query(value: Any) -> bool:
    """Whether a public vocabulary query may be searched or sent to AI.

    The normalizer removes zero-width characters and folds case first, so a
    simple visual spelling variation cannot bypass the family-safety filter.
    """
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    text = "".join(char for char in text if unicodedata.category(char) != "Cf")
    text = re.sub(r"\s+", " ", text)
    if len(text) < 2 or len(text) > 80:
        return False
    terms = set(_SPEAKING_VOCABULARY_18_PLUS_TERMS)
    terms.update(
        term.strip().casefold()
        for term in str(os.environ.get("SPEAKING_VOCAB_BLOCKED_TERMS") or "").split("|")
        if term.strip()
    )
    return not any(
        re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text)
        for term in terms
    )


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
