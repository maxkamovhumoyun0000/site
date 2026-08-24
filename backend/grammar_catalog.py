from __future__ import annotations

import hashlib
import json
import threading
from functools import lru_cache
from types import SimpleNamespace
from typing import Any

from grammar_content import ALL_GRAMMAR_TOPICS, get_topic as _legacy_get_topic
from db import get_conn


SUPPORTED_LEVELS = ("A1", "A2", "B1", "B2", "C1")
_ORDER_STEP = 1000
_ADMIN_SCHEMA_LOCK = threading.Lock()
_ADMIN_SCHEMA_READY = False


def _legacy_order_seed_rows() -> list[tuple[str, str, int]]:
    """Return a deterministic, per-subject initial order for code topics."""
    counters: dict[str, int] = {}
    seen: set[str] = set()
    rows: list[tuple[str, str, int]] = []
    for topic in list(ALL_GRAMMAR_TOPICS or []):
        topic_id = str(getattr(topic, "topic_id", "") or "").strip()
        if not topic_id or topic_id in seen:
            continue
        seen.add(topic_id)
        subject = _normalize_subject(str(getattr(topic, "subject", "English"))) or "English"
        counters[subject] = counters.get(subject, 0) + _ORDER_STEP
        rows.append((topic_id, subject, counters[subject]))
    return rows


def _ensure_admin_topics_schema() -> None:
    """Small DB overlay for the otherwise code-backed grammar catalogue.

    It lets admins correct existing topics and add their own without editing
    Python files on production.  A disabled overlay hides a legacy topic.
    """
    global _ADMIN_SCHEMA_READY
    if _ADMIN_SCHEMA_READY:
        return
    with _ADMIN_SCHEMA_LOCK:
        if _ADMIN_SCHEMA_READY:
            return
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS grammar_topic_overrides (
                    topic_id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    level TEXT NOT NULL,
                    title TEXT NOT NULL,
                    rule TEXT DEFAULT '',
                    questions_json TEXT NOT NULL DEFAULT '[]',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    updated_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Keep ordering separate from overrides.  A legacy topic can be
            # rearranged without duplicating its full rule and question data.
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS grammar_topic_order (
                    topic_id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    sort_order BIGINT NOT NULL,
                    updated_by BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_grammar_topic_order_subject_position
                ON grammar_topic_order(subject, sort_order, topic_id)
                """
            )
            # Existing grammar comes from grammar_content.py.  Seed it once
            # in its stable source order so a newly deployed schema never
            # changes the catalogue order unexpectedly.
            for topic_id, subject, sort_order in _legacy_order_seed_rows():
                cur.execute(
                    """
                    INSERT INTO grammar_topic_order(topic_id, subject, sort_order)
                    VALUES (?, ?, ?)
                    ON CONFLICT(topic_id) DO NOTHING
                    """,
                    (topic_id, subject, sort_order),
                )
            conn.commit()
            _ADMIN_SCHEMA_READY = True
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()


def _row_data(row: Any) -> dict[str, Any]:
    try:
        return dict(row)
    except Exception:
        return {}


def _topic_order_rows() -> dict[str, tuple[str, int]]:
    _ensure_admin_topics_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT topic_id, subject, sort_order FROM grammar_topic_order")
        rows = cur.fetchall() or []
    finally:
        conn.close()
    result: dict[str, tuple[str, int]] = {}
    for row in rows:
        data = _row_data(row)
        topic_id = str(data.get("topic_id") or "").strip()
        if not topic_id:
            continue
        try:
            sort_order = int(data.get("sort_order") or 0)
        except (TypeError, ValueError):
            sort_order = 0
        result[topic_id] = (_normalize_subject(str(data.get("subject") or "")) or "English", sort_order)
    return result


def _next_sort_order(cur: Any, subject: str) -> int:
    cur.execute(
        "SELECT COALESCE(MAX(sort_order), 0) AS max_sort_order FROM grammar_topic_order WHERE subject=?",
        (subject,),
    )
    data = _row_data(cur.fetchone())
    try:
        current = int(data.get("max_sort_order") or 0)
    except (TypeError, ValueError):
        current = 0
    return max(_ORDER_STEP, current + _ORDER_STEP)


def _admin_overrides() -> dict[str, Any]:
    _ensure_admin_topics_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM grammar_topic_overrides")
        rows = cur.fetchall() or []
    finally:
        conn.close()
    result: dict[str, Any] = {}
    for row in rows:
        data = dict(row)
        try:
            questions = json.loads(str(data.get("questions_json") or "[]"))
        except Exception:
            questions = []
        normalized_questions = []
        for item in questions if isinstance(questions, list) else []:
            if not isinstance(item, dict):
                continue
            options = [str(value or "").strip() for value in (item.get("options") or [])]
            if len([value for value in options if value]) < 2:
                continue
            normalized_questions.append(SimpleNamespace(
                prompt=str(item.get("prompt") or item.get("question") or "Savol").strip(),
                options=options,
                correct_index=int(item.get("correct_index", item.get("correct_option_index", 0)) or 0),
            ))
        result[str(data.get("topic_id") or "").strip()] = SimpleNamespace(
            topic_id=str(data.get("topic_id") or "").strip(),
            subject=str(data.get("subject") or "English").strip(),
            level=str(data.get("level") or "A1").strip().upper(),
            title=str(data.get("title") or "Grammar").strip(),
            rule=str(data.get("rule") or "").strip(),
            questions=normalized_questions,
            is_active=bool(data.get("is_active")),
        )
    return result


def clear_catalog_cache() -> None:
    _catalog_signature.cache_clear()
    _topics_by_level_cached.cache_clear()
    _topic_lookup_cached.cache_clear()


def admin_topic_rows(subject: str | None = None) -> list[dict[str, Any]]:
    selected = _normalize_subject(subject)
    rows: list[dict[str, Any]] = []
    for index, topic in enumerate(_all_topics(), start=1):
        item_subject = _normalize_subject(str(getattr(topic, "subject", "English"))) or "English"
        if selected and item_subject != selected:
            continue
        # Russian grammar is intentionally not split into CEFR levels.  The
        # catalogue keeps a technical level internally for backwards
        # compatible topic lookup, but never exposes one to the admin UI.
        display_level = str(getattr(topic, "level", "A1") or "A1").upper() if item_subject == "English" else ""
        payload = {
            "topic_id": str(getattr(topic, "topic_id", "") or "").strip(),
            "title": _clean_text(getattr(topic, "title", "")) or "Grammar",
            "rule": _clean_text(getattr(topic, "rule", "")),
            "questions": [item for item in (normalize_question_payload(question) for question in list(getattr(topic, "questions", []) or [])) if item],
            "question_count": len(list(getattr(topic, "questions", []) or [])),
            "subject": item_subject,
            "level": display_level,
            "is_active": True,
            "sort_order": index,
        }
        rows.append(payload)
    return rows


def save_admin_topic(payload: dict[str, Any], updated_by: int | None = None) -> dict[str, Any]:
    topic_id = _clean_text(payload.get("topic_id"))
    if not topic_id:
        raise ValueError("topic_id is required")
    subject = _normalize_subject(_clean_text(payload.get("subject")))
    supplied_level = _clean_text(payload.get("level")).upper()
    title = _clean_text(payload.get("title"))
    if subject not in {"English", "Russian"} or not title:
        raise ValueError("Invalid grammar topic")
    # Keep a stable stored value for Russian so existing quiz/detail lookup
    # stays backwards-compatible, but do not require or expose a level.
    level = "A1" if subject == "Russian" else supplied_level
    if level not in SUPPORTED_LEVELS:
        raise ValueError("Invalid grammar topic")
    questions = []
    for raw in payload.get("questions") or []:
        if not isinstance(raw, dict):
            continue
        options = [_clean_text(value) for value in raw.get("options") or []]
        options = [value for value in options if value]
        if len(options) < 2:
            continue
        correct = int(raw.get("correct_index", raw.get("correct_option_index", 0)) or 0)
        questions.append({"prompt": _clean_text(raw.get("prompt") or raw.get("question")) or "Savol", "options": options, "correct_index": max(0, min(correct, len(options) - 1))})
    rule = _clean_text(payload.get("rule"))
    if not questions and not rule:
        raise ValueError("Add a grammar rule or at least one valid question")
    _ensure_admin_topics_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT subject FROM grammar_topic_order WHERE topic_id=? LIMIT 1",
            (topic_id,),
        )
        old_order = _row_data(cur.fetchone())
        old_subject = _normalize_subject(str(old_order.get("subject") or ""))
        cur.execute(
            """INSERT INTO grammar_topic_overrides(topic_id, subject, level, title, rule, questions_json, is_active, updated_by, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(topic_id) DO UPDATE SET subject=EXCLUDED.subject, level=EXCLUDED.level, title=EXCLUDED.title,
               rule=EXCLUDED.rule, questions_json=EXCLUDED.questions_json, is_active=1, updated_by=EXCLUDED.updated_by, updated_at=CURRENT_TIMESTAMP""",
            (topic_id, subject, level, title, rule, json.dumps(questions, ensure_ascii=False), updated_by),
        )
        # New topics start at the end of their subject. Existing order is
        # preserved on normal edits; moving a topic to another subject puts
        # it at the end of that subject until an admin drags it into place.
        if not old_order or (old_subject and old_subject != subject):
            sort_order = _next_sort_order(cur, subject)
            cur.execute(
                """
                INSERT INTO grammar_topic_order(topic_id, subject, sort_order, updated_by, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(topic_id) DO UPDATE SET
                    subject=EXCLUDED.subject,
                    sort_order=EXCLUDED.sort_order,
                    updated_by=EXCLUDED.updated_by,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (topic_id, subject, sort_order, updated_by),
            )
        conn.commit()
    finally:
        conn.close()
    clear_catalog_cache()
    return {
        "topic_id": topic_id,
        "subject": subject,
        "level": level if subject == "English" else "",
        "title": title,
        "rule": rule,
        "questions": questions,
        "question_count": len(questions),
        "is_active": True,
    }


def deactivate_admin_topic(topic_id: str, updated_by: int | None = None) -> bool:
    key = _clean_text(topic_id)
    if not key:
        return False
    existing = next((topic for topic in list(ALL_GRAMMAR_TOPICS or []) if str(getattr(topic, "topic_id", "")) == key), None)
    if existing is None:
        _ensure_admin_topics_schema()
        conn = get_conn(); cur = conn.cursor()
        try:
            cur.execute("DELETE FROM grammar_topic_overrides WHERE topic_id=?", (key,))
            override_changed = int(getattr(cur, "rowcount", 0) or 0) > 0
            cur.execute("DELETE FROM grammar_topic_order WHERE topic_id=?", (key,))
            changed = override_changed or int(getattr(cur, "rowcount", 0) or 0) > 0
            conn.commit()
        finally:
            conn.close()
    else:
        save_payload = {"topic_id": key, "subject": getattr(existing, "subject", "English"), "level": getattr(existing, "level", "A1"), "title": getattr(existing, "title", "Grammar"), "rule": getattr(existing, "rule", ""), "questions": [{"prompt": getattr(q, "prompt", ""), "options": list(getattr(q, "options", []) or []), "correct_index": getattr(q, "correct_index", 0)} for q in list(getattr(existing, "questions", []) or [])]}
        save_admin_topic(save_payload, updated_by)
        conn = get_conn(); cur = conn.cursor()
        try:
            cur.execute("UPDATE grammar_topic_overrides SET is_active=0, updated_by=?, updated_at=CURRENT_TIMESTAMP WHERE topic_id=?", (updated_by, key))
            changed = int(getattr(cur, "rowcount", 0) or 0) > 0
            conn.commit()
        finally:
            conn.close()
    clear_catalog_cache()
    return changed


def _normalize_subject(subject: str | None) -> str | None:
    value = str(subject or "").strip()
    return value.title() if value else None


@lru_cache(maxsize=1)
def _catalog_signature() -> str:
    compact: list[dict[str, Any]] = []
    for topic in _all_topics():
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
    rows = [topic for topic in _all_topics() if str(getattr(topic, "level", "")).upper() == level]
    if subject:
        rows = [topic for topic in rows if _normalize_subject(str(getattr(topic, "subject", ""))) == subject]
    return tuple(rows)


def get_topics_for_subject(subject: str | None = None) -> list[Any]:
    """All active topics in the persisted admin order for one subject."""
    normalized_subject = _normalize_subject(subject)
    rows = _all_topics()
    if normalized_subject:
        rows = [topic for topic in rows if _normalize_subject(str(getattr(topic, "subject", ""))) == normalized_subject]
    return rows


def _all_topics() -> list[Any]:
    overrides = _admin_overrides()
    rows: list[Any] = []
    seen: set[str] = set()
    for original in list(ALL_GRAMMAR_TOPICS or []):
        topic_id = str(getattr(original, "topic_id", "") or "").strip()
        override = overrides.get(topic_id)
        seen.add(topic_id)
        if override is not None:
            if bool(getattr(override, "is_active", False)):
                rows.append(override)
        else:
            rows.append(original)
    for topic_id, override in overrides.items():
        if topic_id not in seen and bool(getattr(override, "is_active", False)):
            rows.append(override)
    positions = _topic_order_rows()
    # The database is seeded from the existing source order.  This fallback
    # protects rows created during an interrupted first migration as well.
    fallback_order = {
        topic_id: index
        for index, (topic_id, _subject, _position) in enumerate(_legacy_order_seed_rows())
    }
    return sorted(
        rows,
        key=lambda topic: (
            {"English": 0, "Russian": 1}.get(
                _normalize_subject(str(getattr(topic, "subject", ""))) or "", 99
            ),
            positions.get(str(getattr(topic, "topic_id", "") or ""), ("", 10**12))[1],
            fallback_order.get(str(getattr(topic, "topic_id", "") or ""), 10**12),
            str(getattr(topic, "topic_id", "") or ""),
        ),
    )


def reorder_admin_topics(subject: str, topic_ids: list[str], updated_by: int | None = None) -> list[dict[str, Any]]:
    """Atomically persist a full subject order from the admin drag UI."""
    selected_subject = _normalize_subject(subject)
    if selected_subject not in {"English", "Russian"}:
        raise ValueError("Unsupported grammar subject")
    requested = [str(item or "").strip() for item in topic_ids]
    if not requested or any(not item for item in requested) or len(set(requested)) != len(requested):
        raise ValueError("Topic order contains invalid or repeated IDs")
    available = [
        str(getattr(topic, "topic_id", "") or "").strip()
        for topic in get_topics_for_subject(selected_subject)
    ]
    if set(requested) != set(available):
        raise ValueError("Topic order must include every active topic for this subject")
    _ensure_admin_topics_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        for index, topic_id in enumerate(requested, start=1):
            cur.execute(
                """
                INSERT INTO grammar_topic_order(topic_id, subject, sort_order, updated_by, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(topic_id) DO UPDATE SET
                    subject=EXCLUDED.subject,
                    sort_order=EXCLUDED.sort_order,
                    updated_by=EXCLUDED.updated_by,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (topic_id, selected_subject, index * _ORDER_STEP, updated_by),
            )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()
    clear_catalog_cache()
    return admin_topic_rows(selected_subject)


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
