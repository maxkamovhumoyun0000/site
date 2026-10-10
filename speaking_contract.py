"""Pure request-to-record rules for the Speaking media-admin API."""
from __future__ import annotations

from typing import Any


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
    answer = str(payload.sample_answer or "").strip() or "Sample answer to be reviewed."
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
