"""Teacher library (nested folders) + AI-checked test runtime + weekly review.

Bu modul uchta katta blokni beradi:

1. `/teacher/library/*` — cheksiz chuqurlikdagi papka daraxti. Har bir tugun
   `folder`, `file` yoki `test` bo'lishi mumkin. Tugunlar boshqa o'qituvchilarga
   `view` / `assign` / `edit` huquqi bilan share qilinadi (huquq subtree'ga meros).

2. `/teacher/library/ai/import-screenshot` — kitob sahifasining skrinshotini
   Grok vision bilan o'qib, matn + mashqlarni tayyor test savollariga aylantiradi.
   O'qituvchi tahrirlab saqlaydi.

3. `/student/ai-tests/*` — yangi test turlari runtime'i. Taymer yo'q, har bir
   javob darhol tekshiriladi, xato bo'lsa shu savol tugatilmaguncha keyingisiga
   o'tilmaydi, testdan chiqib ketilsa attempt bekor bo'ladi (boshqatdan).
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

import db as dbm

router = APIRouter()
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Test turlari registri — sayt va ikkala ilova shu ro'yxatdan foydalanadi
# ═══════════════════════════════════════════════════════════════════════════

#: `check` — javob qanday tekshiriladi: "auto" (server solishtiradi) yoki "ai".
#: `input` — student nima yuboradi: "text" | "audio" | "audio_or_text" | "choice" | "order" | "pairs"
#: `needs_audio_asset` — o'qituvchi mashqqa audio fayl yuklashi shart.
AI_TEST_TYPES: dict[str, dict[str, Any]] = {
    # ── Foydalanuvchi so'ragan asosiy turlar ────────────────────────────────
    "speak_sentence": {
        "label_uz": "So'z bilan gap tuzib gapirish",
        "label_ru": "Составить предложение и произнести",
        "label_en": "Speak a sentence",
        "check": "ai", "input": "audio", "needs_audio_asset": False,
        "retry_until_correct": True,
    },
    "write_sentence": {
        "label_uz": "So'z bilan gap tuzib yozish",
        "label_ru": "Составить предложение письменно",
        "label_en": "Write a sentence",
        "check": "ai", "input": "text", "needs_audio_asset": False,
        "retry_until_correct": True,
    },
    "guided_writing": {
        "label_uz": "Mavzu bo'yicha yozma mashq",
        "label_ru": "Письменное задание по теме",
        "label_en": "Guided writing",
        "check": "ai", "input": "text", "needs_audio_asset": False,
        "retry_until_correct": True,
    },
    # ── Kitob mashqlarida uchraydigan qo'shimcha turlar (AI tekshiradi) ─────
    "translation": {
        "label_uz": "Tarjima qilish",
        "label_ru": "Перевод",
        "label_en": "Translation",
        "check": "ai", "input": "text", "needs_audio_asset": False,
        "retry_until_correct": True,
    },
    "reading_open": {
        "label_uz": "Matn bo'yicha ochiq savol",
        "label_ru": "Открытый вопрос по тексту",
        "label_en": "Reading comprehension (open)",
        "check": "ai", "input": "text", "needs_audio_asset": False,
        "retry_until_correct": True,
    },
    "read_aloud": {
        "label_uz": "Matnni ovoz chiqarib o'qish",
        "label_ru": "Чтение вслух",
        "label_en": "Read aloud",
        "check": "ai", "input": "audio", "needs_audio_asset": False,
        "retry_until_correct": True,
    },
    "paraphrase": {
        "label_uz": "Gapni boshqacha aytish",
        "label_ru": "Перефразировать",
        "label_en": "Paraphrase",
        "check": "ai", "input": "text", "needs_audio_asset": False,
        "retry_until_correct": True,
    },
    "dialogue_completion": {
        "label_uz": "Dialogni to'ldirish",
        "label_ru": "Дополнить диалог",
        "label_en": "Dialogue completion",
        "check": "ai", "input": "audio_or_text", "needs_audio_asset": False,
        "retry_until_correct": True,
    },
    "picture_description": {
        "label_uz": "Rasmni tasvirlash",
        "label_ru": "Описать картинку",
        "label_en": "Picture description",
        "check": "ai", "input": "audio_or_text", "needs_audio_asset": False,
        "retry_until_correct": True,
    },
    # ── Avtomatik tekshiriladigan turlar (AI chaqirilmaydi, tez ishlaydi) ───
    "listening": {
        "label_uz": "Tinglab tushunish",
        "label_ru": "Аудирование",
        "label_en": "Listening",
        "check": "auto", "input": "choice", "needs_audio_asset": True,
        "retry_until_correct": False,
    },
    "dictation": {
        "label_uz": "Diktant (tinglab yozish)",
        "label_ru": "Диктант",
        "label_en": "Dictation",
        "check": "auto", "input": "text", "needs_audio_asset": True,
        "retry_until_correct": True,
    },
    "spelling": {
        "label_uz": "So'zni to'g'ri yozish",
        "label_ru": "Правописание",
        "label_en": "Spelling",
        "check": "auto", "input": "text", "needs_audio_asset": False,
        "retry_until_correct": True,
    },
    "matching": {
        "label_uz": "Juftlab moslashtirish",
        "label_ru": "Соотнести пары",
        "label_en": "Matching",
        "check": "auto", "input": "pairs", "needs_audio_asset": False,
        "retry_until_correct": False,
    },
    "scrambled_sentence": {
        "label_uz": "So'zlarni tartibga solish",
        "label_ru": "Составить предложение из слов",
        "label_en": "Scrambled sentence",
        "check": "auto", "input": "order", "needs_audio_asset": False,
        "retry_until_correct": True,
    },
    "gap_fill": {
        "label_uz": "Bo'sh joyni to'ldirish",
        "label_ru": "Заполнить пропуск",
        "label_en": "Gap fill",
        "check": "auto", "input": "text", "needs_audio_asset": False,
        "retry_until_correct": True,
    },
    # ── Polimorf: bitta so'z. Studentga tushganda random test turiga aylanadi ──
    "word_practice": {
        "label_uz": "So'z mashqi (random tur)",
        "label_ru": "Практика слова (случайный тип)",
        "label_en": "Word practice (random type)",
        "check": "ai", "input": "text", "needs_audio_asset": False,
        "retry_until_correct": True,
        "polymorphic": True,
    },
}

AI_CHECKED_KINDS = {k for k, v in AI_TEST_TYPES.items() if v["check"] == "ai"}
AUTO_CHECKED_KINDS = {k for k, v in AI_TEST_TYPES.items() if v["check"] == "auto"}
AUDIO_ASSET_KINDS = {k for k, v in AI_TEST_TYPES.items() if v["needs_audio_asset"]}
POLYMORPHIC_KINDS = {k for k, v in AI_TEST_TYPES.items() if v.get("polymorphic")}

#: word_practice studentga tushganda shu turlardan biriga random aylanadi.
WORD_PRACTICE_VARIANTS = ["speak_sentence", "write_sentence", "spelling", "translation"]

MAX_RETRIES_PER_QUESTION = 6


@router.get("/test-types")
async def list_test_types(x_language: str | None = Header(default=None, alias="X-Language")):
    """Sayt va ilovalar test turlari ro'yxatini shu yerdan oladi (bir manba)."""
    lang = str(x_language or "uz").strip().lower()[:2]
    key = f"label_{lang}" if f"label_{lang}" in next(iter(AI_TEST_TYPES.values())) else "label_uz"
    return {
        "items": [
            {
                "kind": kind,
                "label": meta.get(key) or meta.get("label_uz"),
                "check": meta["check"],
                "input": meta["input"],
                "needs_audio_asset": meta["needs_audio_asset"],
                "retry_until_correct": meta["retry_until_correct"],
            }
            for kind, meta in AI_TEST_TYPES.items()
        ]
    }


# ═══════════════════════════════════════════════════════════════════════════
# Auth yordamchilari (backend.main bilan tsiklik importdan qochish uchun lazy)
# ═══════════════════════════════════════════════════════════════════════════

def _auth(authorization: str | None, roles: set[str]) -> dict:
    from backend.main import _require_role, _user_row_from_bearer

    user = _user_row_from_bearer(authorization)
    _require_role(user, roles)
    return user


TEACHER_ROLES = {"teacher", "support", "admin", "superadmin"}
STUDENT_ROLES = {"student"}


def _settings() -> dict[str, float]:
    from backend.main import _get_runtime_settings

    try:
        return _get_runtime_settings() or {}
    except Exception:
        logger.exception("dpoint settings read failed")
        return {}


def _setting(key: str, default: float) -> float:
    try:
        return float(_settings().get(key, default))
    except Exception:
        return float(default)


def _safe(fn, fallback=None):
    try:
        return fn()
    except HTTPException:
        raise
    except Exception:
        logger.exception("library_ai safe call failed")
        return fallback


# ═══════════════════════════════════════════════════════════════════════════
# 1. KUTUBXONA DARAXTI
# ═══════════════════════════════════════════════════════════════════════════

class LibraryNodeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    kind: str = "folder"
    parent_id: int | None = None
    description: str | None = None
    subject: str | None = None
    level: str | None = None
    file_url: str | None = None
    payload: dict | None = None
    is_public: bool = False


class LibraryNodeUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    subject: str | None = None
    level: str | None = None
    file_url: str | None = None
    payload: dict | None = None
    is_public: bool | None = None
    parent_id: int | None = None
    sort_order: int | None = None


class LibraryShareRequest(BaseModel):
    teacher_id: int
    permission: str = "view"


class LibraryAssignRequest(BaseModel):
    student_ids: list[int] | None = None
    group_id: int | None = None
    title: str | None = None
    description: str | None = None
    due_at: str | None = None


def _node_or_404(node_id: int) -> dict:
    node = _safe(lambda: dbm.get_library_node(int(node_id)))
    if not node:
        raise HTTPException(status_code=404, detail="Kutubxona elementi topilmadi")
    return node


def _require_node_permission(user: dict, node: dict, need: str) -> str:
    """need: 'view' | 'assign' | 'edit'. Admin hamma narsani ko'radi/tahrirlaydi."""
    from backend.main import _role_from_login_type

    role = _role_from_login_type(int(user.get("login_type") or 1), str(user.get("login_id") or ""))
    if role in {"admin", "superadmin"}:
        return "owner"
    perm = _safe(lambda: dbm.library_permission_for(None, int(user.get("id") or 0), node))
    if perm is None and node.get("is_public") and need == "view":
        perm = "view"
    if perm is None:
        raise HTTPException(status_code=403, detail="Bu elementga ruxsatingiz yo'q")
    rank = {"view": 1, "assign": 2, "edit": 3, "owner": 4}
    if rank.get(perm, 0) < rank.get(need, 99):
        raise HTTPException(status_code=403, detail="Bu amal uchun huquq yetarli emas")
    return perm


@router.get("/teacher/library")
async def library_list(authorization: str | None = Header(default=None)):
    """O'ziniki + public + share qilingan barcha tugunlar (flat, frontend daraxt qiladi)."""
    user = _auth(authorization, TEACHER_ROLES)
    data = _safe(lambda: dbm.list_library_nodes(int(user.get("id") or 0)), {"nodes": [], "shares": []}) or {}
    nodes = []
    for node in data.get("nodes") or []:
        item = dict(node)
        item["payload"] = _json_obj(item.pop("payload_json", None))
        nodes.append(item)
    return {
        "nodes": nodes,
        "shares": data.get("shares") or [],
        "my_id": int(user.get("id") or 0),
        "total": len(nodes),
    }


@router.get("/teacher/library/{node_id}")
async def library_get(node_id: int, authorization: str | None = Header(default=None)):
    user = _auth(authorization, TEACHER_ROLES)
    node = _node_or_404(node_id)
    perm = _require_node_permission(user, node, "view")
    out = dict(node)
    out["payload"] = _json_obj(out.pop("payload_json", None))
    out["permission"] = perm
    return {"item": out}


@router.post("/teacher/library")
async def library_create(payload: LibraryNodeCreate, authorization: str | None = Header(default=None)):
    user = _auth(authorization, TEACHER_ROLES)
    kind = str(payload.kind or "folder").strip().lower()
    if kind not in dbm.LIBRARY_KINDS:
        raise HTTPException(status_code=400, detail="Yaroqsiz element turi")
    if payload.parent_id:
        parent = _node_or_404(int(payload.parent_id))
        if str(parent.get("kind") or "") != "folder":
            raise HTTPException(status_code=400, detail="Faqat papka ichiga element qo'shiladi")
        _require_node_permission(user, parent, "edit")
    if kind == "test":
        questions = _normalize_questions((payload.payload or {}).get("questions"))
        if not questions:
            raise HTTPException(status_code=400, detail="Test uchun kamida bitta savol kerak")
        payload.payload = {**(payload.payload or {}), "questions": questions}
    try:
        node = dbm.create_library_node(
            int(user.get("id") or 0),
            payload.title,
            kind,
            parent_id=payload.parent_id,
            description=payload.description,
            subject=payload.subject,
            level=payload.level,
            file_url=payload.file_url,
            payload=payload.payload,
            is_public=bool(payload.is_public),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    out = dict(node)
    out["payload"] = _json_obj(out.pop("payload_json", None))
    return {"message": "Element yaratildi", "item": out}


@router.patch("/teacher/library/{node_id}")
async def library_update(node_id: int, payload: LibraryNodeUpdate, authorization: str | None = Header(default=None)):
    user = _auth(authorization, TEACHER_ROLES)
    node = _node_or_404(node_id)
    _require_node_permission(user, node, "edit")
    new_payload = payload.payload
    if new_payload is not None and str(node.get("kind") or "") == "test":
        questions = _normalize_questions(new_payload.get("questions"))
        if not questions:
            raise HTTPException(status_code=400, detail="Test uchun kamida bitta savol kerak")
        new_payload = {**new_payload, "questions": questions}
    if payload.parent_id is not None and int(payload.parent_id or 0) > 0:
        target = _node_or_404(int(payload.parent_id))
        if str(target.get("kind") or "") != "folder":
            raise HTTPException(status_code=400, detail="Faqat papka ichiga ko'chiriladi")
        _require_node_permission(user, target, "edit")
    try:
        updated = dbm.update_library_node(
            int(node_id),
            title=payload.title,
            description=payload.description,
            subject=payload.subject,
            level=payload.level,
            file_url=payload.file_url,
            payload=new_payload,
            is_public=payload.is_public,
            parent_id=payload.parent_id,
            sort_order=payload.sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="Element topilmadi")
    out = dict(updated)
    out["payload"] = _json_obj(out.pop("payload_json", None))
    return {"message": "Saqlandi", "item": out}


@router.delete("/teacher/library/{node_id}")
async def library_delete(node_id: int, authorization: str | None = Header(default=None)):
    user = _auth(authorization, TEACHER_ROLES)
    node = _node_or_404(node_id)
    from backend.main import _role_from_login_type

    role = _role_from_login_type(int(user.get("login_type") or 1), str(user.get("login_id") or ""))
    if int(node.get("owner_id") or 0) != int(user.get("id") or 0) and role not in {"admin", "superadmin"}:
        raise HTTPException(status_code=403, detail="Faqat egasi o'chira oladi")
    ok = _safe(lambda: dbm.delete_library_node(int(node_id)), False)
    if not ok:
        raise HTTPException(status_code=404, detail="Element topilmadi")
    return {"message": "O'chirildi"}


@router.get("/teacher/library/{node_id}/shares")
async def library_shares(node_id: int, authorization: str | None = Header(default=None)):
    user = _auth(authorization, TEACHER_ROLES)
    node = _node_or_404(node_id)
    _require_node_permission(user, node, "view")
    data = _safe(lambda: dbm.list_library_share_targets(int(node_id)), {"shares": [], "teachers": []}) or {}
    return data


@router.post("/teacher/library/{node_id}/share")
async def library_share(node_id: int, payload: LibraryShareRequest, authorization: str | None = Header(default=None)):
    user = _auth(authorization, TEACHER_ROLES)
    node = _node_or_404(node_id)
    from backend.main import _role_from_login_type

    role = _role_from_login_type(int(user.get("login_type") or 1), str(user.get("login_id") or ""))
    if int(node.get("owner_id") or 0) != int(user.get("id") or 0) and role not in {"admin", "superadmin"}:
        raise HTTPException(status_code=403, detail="Faqat egasi share qila oladi")
    if int(payload.teacher_id or 0) == int(node.get("owner_id") or 0):
        raise HTTPException(status_code=400, detail="Egasiga share qilish shart emas")
    try:
        result = dbm.share_library_node(
            int(node_id), int(payload.teacher_id), payload.permission, shared_by=int(user.get("id") or 0)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"message": "Ulashildi", "share": result}


@router.delete("/teacher/library/{node_id}/share/{teacher_id}")
async def library_unshare(node_id: int, teacher_id: int, authorization: str | None = Header(default=None)):
    user = _auth(authorization, TEACHER_ROLES)
    node = _node_or_404(node_id)
    from backend.main import _role_from_login_type

    role = _role_from_login_type(int(user.get("login_type") or 1), str(user.get("login_id") or ""))
    if int(node.get("owner_id") or 0) != int(user.get("id") or 0) and role not in {"admin", "superadmin"}:
        raise HTTPException(status_code=403, detail="Faqat egasi bekor qila oladi")
    dbm.unshare_library_node(int(node_id), int(teacher_id))
    return {"message": "Ulashish bekor qilindi"}


@router.post("/teacher/library/upload")
async def library_upload(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    """Kutubxona uchun umumiy fayl yuklash (PDF, rasm, listening audio)."""
    user = _auth(authorization, TEACHER_ROLES)
    from backend.main import HOMEWORK_UPLOAD_DIR, _upload_web_file

    filename, _ = await _upload_web_file(
        file, HOMEWORK_UPLOAD_DIR, f"library_{int(user.get('id') or 0)}", max_size_mb=25
    )
    return {"url": f"/homework/files/{filename}", "filename": filename}


@router.post("/teacher/library/{node_id}/assign")
async def library_assign(node_id: int, payload: LibraryAssignRequest, authorization: str | None = Header(default=None)):
    """Kutubxonadagi test/faylni studentlarga homework qilib beradi."""
    user = _auth(authorization, TEACHER_ROLES)
    node = _node_or_404(node_id)
    _require_node_permission(user, node, "assign")
    kind = str(node.get("kind") or "")
    if kind == "folder":
        raise HTTPException(status_code=400, detail="Papkani homework qilib berib bo'lmaydi")
    node_payload = _json_obj(node.get("payload_json"))
    questions = _normalize_questions(node_payload.get("questions")) if kind == "test" else []
    if kind == "test" and not questions:
        raise HTTPException(status_code=400, detail="Bu testda savol yo'q")

    student_ids = [int(s) for s in (payload.student_ids or []) if int(s or 0) > 0]
    group_id = int(payload.group_id or 0) or None
    if not student_ids and not group_id:
        raise HTTPException(status_code=400, detail="Student yoki guruh tanlanmadi")

    title = str(payload.title or node.get("title") or "Kutubxona vazifasi").strip()
    description = str(payload.description or node.get("description") or "").strip() or None
    created: list[dict] = []
    targets: list[int | None] = student_ids or [None]
    for student_id in targets:
        homework = _safe(
            lambda sid=student_id: dbm.create_homework(
                int(user.get("id") or 0),
                sid,
                title,
                description=description,
                due_at=payload.due_at,
                group_id=group_id if sid is None else None,
                homework_kind="test" if kind == "test" else "list",
            )
        )
        if not homework:
            continue
        homework_id = int(homework.get("id") or 0)
        if kind == "test" and homework_id > 0:
            _safe(
                lambda hid=homework_id: dbm.save_content_test(
                    "homework",
                    hid,
                    json.dumps(questions, ensure_ascii=False),
                    int(user.get("id") or 0),
                    title=title,
                    raw_questions=True,
                )
            )
        created.append(homework)
    if not created:
        raise HTTPException(status_code=500, detail="Vazifa yaratilmadi")
    return {"message": f"{len(created)} ta vazifa berildi", "items": created}


def _json_obj(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _normalize_questions(raw: Any) -> list[dict]:
    """Yangi test turlari uchun savollarni normallashtiradi va validatsiya qiladi."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = []
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or item.get("question_type") or "").strip().lower()
        if kind not in AI_TEST_TYPES:
            # Eski MCQ savollari ham kutubxonada yashashi mumkin
            if item.get("options"):
                kind = "listening" if item.get("audio_url") else "gap_fill"
            else:
                continue
        meta = AI_TEST_TYPES[kind]
        question: dict[str, Any] = {
            "kind": kind,
            "prompt": str(item.get("prompt") or item.get("question") or "").strip(),
            "instruction": str(item.get("instruction") or "").strip() or None,
            "word": str(item.get("word") or "").strip() or None,
            "passage": str(item.get("passage") or "").strip() or None,
            "image_url": str(item.get("image_url") or "").strip() or None,
            "audio_url": str(item.get("audio_url") or "").strip() or None,
            "level": str(item.get("level") or "").strip() or None,
            "topic": str(item.get("topic") or "").strip() or None,
        }
        if not question["prompt"] and not question["word"]:
            continue
        if meta["needs_audio_asset"] and not question["audio_url"]:
            # Audio yuklanmagan listening/diktant savoli studentga ko'rsatilmaydi
            question["needs_audio_upload"] = True
        if meta["check"] == "auto":
            if kind == "matching":
                pairs = item.get("pairs")
                clean_pairs = []
                if isinstance(pairs, list):
                    for pair in pairs:
                        if isinstance(pair, dict):
                            left = str(pair.get("left") or "").strip()
                            right = str(pair.get("right") or "").strip()
                            if left and right:
                                clean_pairs.append({"left": left, "right": right})
                if len(clean_pairs) < 2:
                    continue
                question["pairs"] = clean_pairs
            elif kind in {"scrambled_sentence"}:
                answer = str(item.get("answer") or "").strip()
                if not answer:
                    continue
                question["answer"] = answer
                tokens = item.get("tokens")
                question["tokens"] = (
                    [str(t).strip() for t in tokens if str(t).strip()]
                    if isinstance(tokens, list) and tokens
                    else answer.replace(".", "").split()
                )
            elif kind == "listening":
                options = [str(o).strip() for o in (item.get("options") or []) if str(o).strip()]
                if len(options) < 2:
                    continue
                question["options"] = options[:4]
                try:
                    question["correct_index"] = max(0, min(len(question["options"]) - 1, int(item.get("correct_index") or item.get("correct_option_index") or 0)))
                except Exception:
                    question["correct_index"] = 0
            else:  # dictation, spelling, gap_fill
                answer = str(item.get("answer") or "").strip()
                if not answer:
                    continue
                question["answer"] = answer
                accepted = item.get("accepted_answers")
                question["accepted_answers"] = (
                    [str(a).strip() for a in accepted if str(a).strip()] if isinstance(accepted, list) else []
                )
        else:
            question["reference_answer"] = str(item.get("reference_answer") or item.get("answer") or "").strip() or None
            question["target_level"] = str(item.get("target_level") or item.get("level") or "").strip() or None
            if kind == "word_practice":
                # So'z mashqi: studentga tushganda random turga aylanadi.
                word = question.get("word") or question.get("prompt")
                if not word:
                    continue
                question["word"] = word
                question["translation"] = str(item.get("translation") or "").strip() or None
                question["meaning"] = str(item.get("meaning") or "").strip() or None
        out.append(question)
    return out


def _materialize_word_practice(q: dict) -> dict:
    """word_practice ni random konkret test turiga aylantiradi (har attemptda boshqacha)."""
    import random

    word = str(q.get("word") or q.get("prompt") or "").strip()
    translation = str(q.get("translation") or "").strip()
    instruction = q.get("instruction")
    level = q.get("level")
    variants = list(WORD_PRACTICE_VARIANTS)
    if not translation and "translation" in variants:
        variants.remove("translation")
    kind = random.choice(variants) if variants else "write_sentence"
    base: dict[str, Any] = {"kind": kind, "word": word, "level": level, "instruction": instruction}
    if kind == "speak_sentence":
        base["prompt"] = q.get("prompt") or f"'{word}' so'zi bilan gap tuzib gapiring"
    elif kind == "write_sentence":
        base["prompt"] = q.get("prompt") or f"'{word}' so'zidan foydalanib gap yozing"
        base["reference_answer"] = None
    elif kind == "spelling":
        base["prompt"] = q.get("prompt") or "Eshitgan/ko'rgan so'zingizni to'g'ri yozing"
        base["answer"] = word
        base["accepted_answers"] = []
    else:  # translation
        base["prompt"] = f"Tarjima qiling: {word}"
        base["answer"] = translation
        base["accepted_answers"] = [translation]
    return base


def _expand_polymorphic_questions(questions: list[dict]) -> list[dict]:
    """Attempt boshlanishidan oldin polimorf savollarni konkret turga ochadi."""
    out: list[dict] = []
    for q in questions or []:
        if str(q.get("kind") or "") in POLYMORPHIC_KINDS:
            out.append(_materialize_word_practice(q))
        else:
            out.append(q)
    return out


def _question_for_student(question: dict) -> dict:
    """Javobni yashirib, studentga ko'rsatiladigan shaklga keltiradi."""
    kind = str(question.get("kind") or "")
    meta = AI_TEST_TYPES.get(kind, {})
    out = {
        "kind": kind,
        "check": meta.get("check", "ai"),
        "input": meta.get("input", "text"),
        "retry_until_correct": bool(meta.get("retry_until_correct", True)),
        "prompt": question.get("prompt"),
        "instruction": question.get("instruction"),
        "word": question.get("word"),
        "passage": question.get("passage"),
        "image_url": question.get("image_url"),
        "audio_url": question.get("audio_url"),
        "level": question.get("level"),
    }
    if kind == "listening":
        out["options"] = question.get("options") or []
    elif kind == "matching":
        pairs = question.get("pairs") or []
        out["left_items"] = [p.get("left") for p in pairs]
        out["right_items"] = sorted([p.get("right") for p in pairs])
    elif kind == "scrambled_sentence":
        tokens = list(question.get("tokens") or [])
        out["tokens"] = sorted(tokens, key=lambda t: (len(t), t.lower()))
    return out


# ═══════════════════════════════════════════════════════════════════════════
# 2. AI SKRINSHOT IMPORT — kitob sahifasidan matn + mashqlar
# ═══════════════════════════════════════════════════════════════════════════

class ScreenshotImportRequest(BaseModel):
    # Har qanday fayl turi: rasm (png/jpg/webp…), PDF, DOC/DOCX, TXT/RTF.
    # `image_urls` — eski mijozlar bilan moslik uchun; `file_urls` — yangi nom.
    image_urls: list[str] = Field(default_factory=list, max_length=10)
    file_urls: list[str] = Field(default_factory=list, max_length=10)
    subject: str = "English"
    level: str | None = None
    node_id: int | None = None
    instruction: str | None = None
    #: bo'sh bo'lsa AI rasmda ko'rgan mashq turlarining o'zini tanlaydi
    wanted_kinds: list[str] | None = None

    @property
    def all_urls(self) -> list[str]:
        seen: list[str] = []
        for url in [*(self.file_urls or []), *(self.image_urls or [])]:
            clean = str(url or "").strip()
            if clean and clean not in seen:
                seen.append(clean)
        return seen


def _import_system_prompt(subject: str, level: str | None, wanted: list[str], instruction_language: str) -> str:
    kinds_help = "\n".join(
        f'- "{kind}": {meta["label_en"]}'
        + (" (teacher must upload the audio file afterwards)" if meta["needs_audio_asset"] else "")
        + (" — polymorphic: for a single vocabulary word; the app randomly turns it into a "
           "speaking/writing/spelling/translation task when the student reaches it" if meta.get("polymorphic") else "")
        for kind, meta in AI_TEST_TYPES.items()
        if kind in wanted
    )
    return (
        "You are an expert curriculum digitizer for a language school.\n"
        "You receive one or more coursebook pages — as page images and/or as extracted "
        "text from a PDF/DOC/DOCX. Convert EVERYTHING teachable in the material into practice "
        "questions: not only the printed exercises, but also vocabulary words, grammar rules, "
        "reading texts and dialogues. Nothing teachable should be left out.\n\n"
        "STRICT RULES:\n"
        "1. Cover ALL the learning content in the material. If there is a vocabulary list, turn "
        "each word into a \"word_practice\" item (with its translation/meaning if shown). If there "
        "is a reading text, add reading_open questions. If there is a grammar rule, add gap_fill / "
        "scrambled_sentence / write_sentence practice for it.\n"
        "2. MIX the question kinds and vary them across the set (do not make them all the same type). "
        "Choose the kinds that best fit each piece of content.\n"
        "3. Keep the target-language content (the English/Russian words and sentences being taught) "
        "exactly as written. Do not translate the study content unless the exercise itself is a translation task.\n"
        "4. For every auto-checked type you MUST provide the exact expected answer.\n"
        "5. If the material has a listening exercise, still produce the question but leave audio_url empty — "
        "the teacher uploads the audio separately.\n"
        f"6. LANGUAGE OF INSTRUCTIONS: every instruction/prompt wording that the STUDENT reads "
        f"(the \"instruction\" and the non-content part of \"prompt\") MUST be written in {instruction_language}. "
        "Auto-detect if unsure: a Russian course → Russian instructions; otherwise Uzbek. Never write "
        "instructions in English unless the course language itself is English.\n"
        "7. If the material is not educational, return {\"error\":\"not_educational\"}.\n\n"
        f"Subject: {subject}. Level: {level or 'infer from the material'}. "
        f"Student instruction language: {instruction_language}.\n\n"
        f"Allowed question kinds:\n{kinds_help}\n\n"
        "Return ONLY valid JSON, no markdown fences, with this shape:\n"
        "{\n"
        '  "title": "short title of the page/unit",\n'
        '  "level": "A1|A2|B1|B2|C1|C2 or empty",\n'
        '  "reading_text": "the main text of the page, empty string if none",\n'
        '  "notes": "grammar rule / explanation found on the page, empty if none",\n'
        '  "questions": [\n'
        '    {"kind":"word_practice","word":"decide","translation":"qaror qilmoq","meaning":"to make a choice"},\n'
        '    {"kind":"gap_fill","prompt":"She ___ to school every day.","answer":"goes",'
        '"accepted_answers":["goes"],"instruction":"Bo\'sh joyni to\'ldiring."},\n'
        '    {"kind":"matching","prompt":"So\'zlarni ta\'riflarga moslang.",'
        '"pairs":[{"left":"brave","right":"not afraid"}]},\n'
        '    {"kind":"scrambled_sentence","prompt":"So\'zlardan gap tuzing.",'
        '"answer":"I have never been to Paris.","tokens":["I","have","never","been","to","Paris."]},\n'
        '    {"kind":"listening","prompt":"Notiq nima buyurtma qiladi?",'
        '"options":["Tea","Coffee","Juice","Water"],"correct_index":1},\n'
        '    {"kind":"write_sentence","word":"although","prompt":"\'although\' so\'zi bilan gap yozing.",'
        '"reference_answer":"Although it was raining, we went out."},\n'
        '    {"kind":"reading_open","passage":"...","prompt":"Tom nega erta ketdi?",'
        '"reference_answer":"Because he had a train to catch."}\n'
        "  ]\n"
        "}\n"
        "Produce as many questions as the material contains (typically 6–40), covering every teachable item."
    )


def _instruction_language_name(code: str | None, subject: str) -> str:
    c = str(code or "").strip().lower()[:2]
    if c == "ru":
        return "Russian"
    if c == "uz":
        return "Uzbek"
    # Fan rus tili bo'lsa — rus, aks holda o'zbek (default).
    subj = str(subject or "").lower()
    if any(t in subj for t in ("rus", "рус", "russian")):
        return "Russian"
    return "Uzbek"


@router.post("/teacher/library/ai/import-screenshot")
async def library_ai_import_screenshot(
    payload: ScreenshotImportRequest,
    authorization: str | None = Header(default=None),
    x_language: str | None = Header(default=None, alias="X-Language"),
):
    """Har qanday fayldan (rasm/PDF/DOC/DOCX/TXT) fayldagi BARCHA o'quv materialini
    har xil, random test turlariga aylantiradi. Ko'rsatmalar o'quv tilida (rus/o'zbek)
    avtomatik yoziladi."""
    user = _auth(authorization, TEACHER_ROLES)
    if payload.node_id:
        node = _node_or_404(int(payload.node_id))
        _require_node_permission(user, node, "edit")

    urls = payload.all_urls
    if not urls:
        raise HTTPException(status_code=400, detail="Fayl yuborilmadi")

    wanted = [k for k in (payload.wanted_kinds or []) if k in AI_TEST_TYPES] or list(AI_TEST_TYPES.keys())
    instruction_language = _instruction_language_name(x_language, payload.subject)
    vision_urls, text_blocks, unsupported = _prepare_import_sources(urls, owner_id=int(user.get("id") or 0))
    if not vision_urls and not text_blocks:
        detail = "Fayldan matn yoki rasm o'qib bo'lmadi"
        if unsupported:
            detail += f" ({', '.join(unsupported)} qo'llab-quvvatlanmaydi)"
        raise HTTPException(status_code=422, detail=detail)

    from ai_generator import _xai_generate_text, _xai_generate_text_stream_with_images
    import aiohttp

    user_prompt = str(payload.instruction or "").strip() or (
        "Digitize this coursebook material: extract its text and convert every exercise into structured questions."
    )
    system_prompt = _import_system_prompt(payload.subject, payload.level, wanted, instruction_language)
    extracted = "\n\n".join(text_blocks).strip()
    if extracted:
        # 60k belgidan oshsa kesamiz (juda katta hujjatlarni AI baribir hazm qilmaydi).
        extracted = extracted[:60000]

    raw = ""
    try:
        async with aiohttp.ClientSession() as session:
            if vision_urls:
                task = system_prompt + "\n\nTASK: " + user_prompt
                if extracted:
                    task += "\n\nAdditional extracted text from the same material:\n" + extracted
                chunks: list[str] = []
                async for chunk in _xai_generate_text_stream_with_images(task, vision_urls, session=session):
                    chunks.append(str(chunk or ""))
                raw = "".join(chunks).strip()
            else:
                # Faqat matn (DOCX/DOC/TXT) — vision shart emas.
                task = (
                    system_prompt
                    + "\n\nTASK: " + user_prompt
                    + "\n\nMATERIAL TEXT:\n" + extracted
                )
                raw = await _xai_generate_text(
                    task,
                    session=session,
                    system_content="You are an educational content digitizer. Output only valid JSON.",
                )
    except Exception as exc:
        logger.exception("library ai import failed teacher=%s: %s", user.get("id"), exc)
        raise HTTPException(status_code=503, detail="AI hozir javob bermadi, qayta urinib ko'ring")

    data = _extract_json_object(str(raw or "").strip())
    if not data:
        raise HTTPException(status_code=502, detail="AI natijasini o'qib bo'lmadi, qayta urinib ko'ring")
    if str(data.get("error") or "") == "not_educational":
        raise HTTPException(status_code=422, detail="Fayl o'quv materiali emas")

    questions = _normalize_questions(data.get("questions"))
    if not questions:
        raise HTTPException(status_code=422, detail="Fayldan mashq topilmadi. Aniqroq material yuboring.")
    needs_audio = [
        {"index": i, "kind": q["kind"], "prompt": q.get("prompt")}
        for i, q in enumerate(questions)
        if q.get("needs_audio_upload")
    ]
    return {
        "message": f"{len(questions)} ta mashq tayyorlandi",
        "title": str(data.get("title") or "").strip() or "Yangi mavzu",
        "level": str(data.get("level") or payload.level or "").strip() or None,
        "reading_text": str(data.get("reading_text") or "").strip(),
        "notes": str(data.get("notes") or "").strip(),
        "questions": questions,
        "needs_audio_upload": needs_audio,
        "kinds_used": sorted({q["kind"] for q in questions}),
        "unsupported": unsupported,
    }


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".avif"}
_PDF_EXTS = {".pdf"}
_DOC_EXTS = {".docx", ".doc"}
_TEXT_EXTS = {".txt", ".rtf", ".md"}
_MAX_VISION_IMAGES = 3
_MAX_PDF_PAGES = 3


def _resolve_local_path(url: str):
    """Yuklangan fayl serverdagi haqiqiy yo'lini topadi (bir nechta upload papka)."""
    from backend.main import HOMEWORK_UPLOAD_DIR

    name = Path(urlparse(str(url or "")).path).name
    if not name:
        return None
    candidates = [
        HOMEWORK_UPLOAD_DIR / name,
        HOMEWORK_UPLOAD_DIR.parent / "homework_uploads" / name,
    ]
    for cand in candidates:
        try:
            if cand.is_file():
                return cand
        except Exception:
            continue
    return None


def _abs_url(url: str) -> str:
    base = str(os.getenv("BACKEND_BASE_URL") or "https://diamond-education.uz/api").rstrip("/")
    clean = str(url or "").strip()
    return base + clean if clean.startswith("/") else clean


def _prepare_import_sources(urls: list[str], owner_id: int) -> tuple[list[str], list[str], list[str]]:
    """Har xil fayllarni AI uchun tayyorlaydi.

    Qaytaradi: (vision uchun rasm URL lari, ajratilgan matn bloklari, qo'llab-
    quvvatlanmaydigan kengaytmalar ro'yxati). PDF sahifalari PNG ga render
    qilinib vision ro'yxatiga qo'shiladi; DOC/DOCX/TXT matn sifatida o'qiladi.
    """
    vision_urls: list[str] = []
    text_blocks: list[str] = []
    unsupported: list[str] = []

    for url in urls:
        ext = Path(urlparse(str(url or "")).path).suffix.lower()
        if ext in _IMAGE_EXTS:
            if len(vision_urls) < _MAX_VISION_IMAGES:
                vision_urls.append(_abs_url(url))
            continue
        local = _resolve_local_path(url)
        if ext in _PDF_EXTS:
            rendered = _render_pdf_to_images(local, owner_id) if local else []
            if rendered:
                for served in rendered:
                    if len(vision_urls) < _MAX_VISION_IMAGES:
                        vision_urls.append(_abs_url(served))
            else:
                text = _extract_pdf_text(local) if local else ""
                if text.strip():
                    text_blocks.append(text)
                else:
                    unsupported.append(ext)
            continue
        if ext in _DOC_EXTS:
            text = _extract_docx_text(local) if local else ""
            if text.strip():
                text_blocks.append(text)
            else:
                unsupported.append(ext)
            continue
        if ext in _TEXT_EXTS:
            text = _read_text_file(local) if local else ""
            if text.strip():
                text_blocks.append(text)
            else:
                unsupported.append(ext)
            continue
        unsupported.append(ext or "noma'lum")
    return vision_urls, text_blocks, unsupported


def _render_pdf_to_images(path, owner_id: int) -> list[str]:
    """PDF sahifalarini PNG ga aylantiradi va servisdan yuklanadigan URL qaytaradi."""
    try:
        import fitz  # PyMuPDF
    except Exception:
        logger.info("PyMuPDF yo'q — PDF matn sifatida o'qiladi")
        return []
    from backend.main import HOMEWORK_UPLOAD_DIR

    served: list[str] = []
    try:
        doc = fitz.open(str(path))
        try:
            page_count = min(_MAX_PDF_PAGES, doc.page_count)
            for i in range(page_count):
                page = doc.load_page(i)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # ~144 DPI
                filename = f"library_pdf_{owner_id}_{int(__import__('time').time()*1000)}_{i}.png"
                out_path = HOMEWORK_UPLOAD_DIR / filename
                pix.save(str(out_path))
                served.append(f"/homework/files/{filename}")
        finally:
            doc.close()
    except Exception:
        logger.exception("PDF render failed path=%s", path)
        return []
    return served


def _extract_pdf_text(path) -> str:
    try:
        import fitz

        doc = fitz.open(str(path))
        try:
            parts = [doc.load_page(i).get_text() for i in range(min(20, doc.page_count))]
            return "\n".join(p for p in parts if p)
        finally:
            doc.close()
    except Exception:
        return ""


def _extract_docx_text(path) -> str:
    try:
        import docx  # python-docx

        document = docx.Document(str(path))
        lines = [p.text for p in document.paragraphs if p.text and p.text.strip()]
        for table in document.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text and c.text.strip()]
                if cells:
                    lines.append(" | ".join(cells))
        return "\n".join(lines)
    except Exception:
        logger.exception("docx extract failed path=%s", path)
        return ""


def _read_text_file(path) -> str:
    try:
        raw = Path(path).read_bytes()
        for enc in ("utf-8", "cp1251", "latin-1"):
            try:
                return raw.decode(enc)
            except Exception:
                continue
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_json_object(raw: str) -> dict:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"```\s*$", "", text).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


# ═══════════════════════════════════════════════════════════════════════════
# 3. STUDENT AI TEST RUNTIME
#    - taymer yo'q
#    - har bir javob darhol tekshiriladi
#    - xato bo'lsa shu savolda qolinadi (retry_until_correct)
#    - testdan chiqib ketilsa attempt bekor bo'ladi
# ═══════════════════════════════════════════════════════════════════════════

class AiTestStartRequest(BaseModel):
    source_type: str = "library_test"
    source_id: int | None = None
    homework_id: int | None = None


class AiTestAnswerRequest(BaseModel):
    question_index: int = Field(ge=0)
    answer_text: str | None = None
    audio_url: str | None = None
    #: matching uchun {"left": "right"}, scrambled uchun so'zlar ketma-ketligi
    pairs: dict[str, str] | None = None
    order: list[str] | None = None
    choice_index: int | None = None


def _attempt_state(attempt: dict) -> dict:
    """Attemptni studentga ko'rsatiladigan holatga aylantiradi."""
    questions = attempt.get("questions") or []
    answers = attempt.get("answers") or []
    solved: set[int] = set()
    tries: dict[int, int] = {}
    feedback: dict[int, dict] = {}
    for row in answers:
        idx = int(row.get("question_index") or 0)
        tries[idx] = max(tries.get(idx, 0), int(row.get("try_count") or 1))
        if str(row.get("verdict") or "") == "correct":
            solved.add(idx)
        parsed = _json_obj(row.get("ai_feedback_json"))
        if parsed:
            feedback[idx] = parsed
    current = next((i for i in range(len(questions)) if i not in solved), None)
    return {
        "attempt_id": int(attempt.get("id") or 0),
        "status": str(attempt.get("status") or "active"),
        "title": attempt.get("title"),
        "source_type": attempt.get("source_type"),
        "source_id": attempt.get("source_id"),
        "total_questions": len(questions),
        "solved_count": len(solved),
        "current_index": current,
        "is_finished": current is None,
        "has_timer": False,
        "questions": [_question_for_student(q) for q in questions],
        "solved_indexes": sorted(solved),
        "tries": tries,
        "last_feedback": feedback.get(current) if current is not None else None,
        "correct_count": int(attempt.get("correct_count") or 0),
        "wrong_count": int(attempt.get("wrong_count") or 0),
        "retry_count": int(attempt.get("retry_count") or 0),
        "dpoints_delta": float(attempt.get("dpoints_delta") or 0.0),
    }


def _questions_from_source(user: dict, source_type: str, source_id: int | None, homework_id: int | None) -> tuple[list[dict], str]:
    source_type = str(source_type or "library_test").strip().lower()
    if source_type == "homework":
        hid = int(homework_id or source_id or 0)
        if hid <= 0:
            raise HTTPException(status_code=400, detail="Homework tanlanmadi")
        homework = _safe(lambda: dbm.get_homework(hid))
        if not homework:
            raise HTTPException(status_code=404, detail="Homework topilmadi")
        test = _safe(lambda: dbm.get_content_test("homework", hid))
        questions = _normalize_questions((test or {}).get("questions"))
        if not questions:
            raise HTTPException(status_code=404, detail="Bu vazifada AI test yo'q")
        return questions, str(homework.get("title") or "Vazifa testi")
    if source_type == "library_test":
        nid = int(source_id or 0)
        node = _node_or_404(nid)
        if str(node.get("kind") or "") != "test":
            raise HTTPException(status_code=400, detail="Bu element test emas")
        if not node.get("is_public"):
            raise HTTPException(status_code=403, detail="Bu test siz uchun ochiq emas")
        questions = _normalize_questions(_json_obj(node.get("payload_json")).get("questions"))
        if not questions:
            raise HTTPException(status_code=404, detail="Testda savol yo'q")
        return questions, str(node.get("title") or "Kutubxona testi")
    if source_type == "weekly_review":
        questions = _weekly_review_questions(int(user.get("id") or 0))
        if not questions:
            raise HTTPException(status_code=404, detail="Haftalik takrorlash uchun material topilmadi")
        return questions, "Haftalik takrorlash"
    raise HTTPException(status_code=400, detail="Yaroqsiz test manbasi")


@router.get("/student/ai-tests/active")
async def ai_test_active(authorization: str | None = Header(default=None)):
    """Ilova qayta ochilganda: active attempt bor-yo'qligini tekshiradi."""
    user = _auth(authorization, STUDENT_ROLES)
    attempt = _safe(lambda: dbm.get_active_ai_test_attempt(int(user.get("id") or 0)))
    if not attempt:
        return {"active": False, "attempt": None}
    return {"active": True, "attempt": _attempt_state(attempt)}


@router.post("/student/ai-tests/start")
async def ai_test_start(payload: AiTestStartRequest, authorization: str | None = Header(default=None)):
    """Yangi attempt. Eski active attempt avtomatik bekor bo'ladi (boshqatdan boshlash)."""
    user = _auth(authorization, STUDENT_ROLES)
    from backend.main import _require_student_learning_access

    _require_student_learning_access(user)
    questions, title = _questions_from_source(user, payload.source_type, payload.source_id, payload.homework_id)
    # Polimorf savollarni (word_practice) shu student uchun random turga ochamiz.
    questions = _expand_polymorphic_questions(questions)
    blocked = [q for q in questions if q.get("needs_audio_upload")]
    if blocked:
        raise HTTPException(
            status_code=409,
            detail=f"Bu testda {len(blocked)} ta tinglash mashqiga audio yuklanmagan. O'qituvchiga murojaat qiling.",
        )
    attempt = _safe(
        lambda: dbm.start_ai_test_attempt(
            int(user.get("id") or 0),
            payload.source_type,
            int(payload.source_id or payload.homework_id or 0) or None,
            questions,
            title=title,
        )
    )
    if not attempt:
        raise HTTPException(status_code=500, detail="Test boshlanmadi")
    return {"message": "Test boshlandi", "attempt": _attempt_state(attempt)}


@router.post("/student/ai-tests/{attempt_id}/abandon")
async def ai_test_abandon(attempt_id: int, authorization: str | None = Header(default=None)):
    """Student testdan chiqsa — attempt bekor, keyingi kirishda boshidan."""
    user = _auth(authorization, STUDENT_ROLES)
    attempt = _safe(lambda: dbm.get_ai_test_attempt(int(attempt_id), int(user.get("id") or 0)))
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt topilmadi")
    dbm.abandon_active_ai_test_attempts(int(user.get("id") or 0))
    return {"message": "Test bekor qilindi, keyingi kirishda boshidan boshlanadi"}


@router.post("/student/ai-tests/upload-audio")
async def ai_test_upload_audio(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    """Speaking javoblari uchun audio yuklash (mikrofon yozuvi)."""
    user = _auth(authorization, STUDENT_ROLES)
    from backend.main import HOMEWORK_UPLOAD_DIR, _upload_web_file

    filename, _ = await _upload_web_file(
        file, HOMEWORK_UPLOAD_DIR, f"aitest_voice_{int(user.get('id') or 0)}", max_size_mb=10
    )
    return {"url": f"/homework/voices/{filename}", "filename": filename}


@router.post("/student/ai-tests/{attempt_id}/answer")
async def ai_test_answer(
    attempt_id: int,
    payload: AiTestAnswerRequest,
    authorization: str | None = Header(default=None),
    x_language: str | None = Header(default=None, alias="X-Language"),
):
    """Bitta savolga javob — darhol tekshiriladi va natija qaytadi."""
    user = _auth(authorization, STUDENT_ROLES)
    user_id = int(user.get("id") or 0)
    attempt = _safe(lambda: dbm.get_ai_test_attempt(int(attempt_id), user_id))
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt topilmadi")
    if str(attempt.get("status") or "") != "active":
        raise HTTPException(status_code=409, detail="Bu test yakunlangan yoki bekor qilingan")

    state = _attempt_state(attempt)
    index = int(payload.question_index)
    questions = attempt.get("questions") or []
    if index < 0 or index >= len(questions):
        raise HTTPException(status_code=400, detail="Savol raqami noto'g'ri")
    if index in set(state["solved_indexes"]):
        raise HTTPException(status_code=409, detail="Bu savol allaqachon yechilgan")
    if state["current_index"] is not None and index != state["current_index"]:
        raise HTTPException(
            status_code=409,
            detail="Avvalgi savolni tugatmaguncha keyingisiga o'tib bo'lmaydi",
        )

    question = questions[index]
    kind = str(question.get("kind") or "")
    meta = AI_TEST_TYPES.get(kind, {})
    subject = _student_subject(user)

    if meta.get("check") == "auto":
        verdict, feedback = _check_auto(question, payload)
    else:
        verdict, feedback = await _check_with_ai(question, payload, subject, x_language)

    try:
        saved = dbm.save_ai_test_answer(
            int(attempt_id),
            index,
            kind=kind,
            answer_text=payload.answer_text,
            audio_url=payload.audio_url,
            verdict=verdict,
            ai_feedback=feedback,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    try_count = int(saved.get("try_count") or 1)
    retry_until_correct = bool(meta.get("retry_until_correct", True))
    forced_pass = verdict != "correct" and try_count >= MAX_RETRIES_PER_QUESTION

    dpoints = 0.0
    if verdict == "correct":
        dpoints = _setting("ai_test_correct_reward", 2.0)
        if try_count > 1:
            dpoints -= _setting("ai_test_retry_penalty", 0.5) * (try_count - 1)
        dbm.bump_ai_test_counters(int(attempt_id), correct=1, retries=max(0, try_count - 1), dpoints=dpoints)
    elif not retry_until_correct or forced_pass:
        dpoints = -abs(_setting("ai_test_skip_penalty", 2.0))
        dbm.bump_ai_test_counters(int(attempt_id), wrong=1, retries=max(0, try_count - 1), dpoints=dpoints)
    else:
        dbm.bump_ai_test_counters(int(attempt_id), retries=1)

    if abs(dpoints) > 0:
        _safe(
            lambda: dbm.add_dpoints(
                user_id, float(dpoints), subject=subject, change_type=f"ai_test_{kind}"
            )
        )

    moved_on = verdict == "correct" or not retry_until_correct or forced_pass
    if moved_on and verdict != "correct":
        # Savol "yopiladi" — bir marta to'g'ri deb belgilanadi, lekin ball manfiy
        _safe(
            lambda: dbm.save_ai_test_answer(
                int(attempt_id), index, kind=kind, verdict="correct",
                answer_text="[limit]", ai_feedback={"forced_pass": True},
            )
        )

    fresh = _safe(lambda: dbm.get_ai_test_attempt(int(attempt_id), user_id)) or attempt
    new_state = _attempt_state(fresh)
    finished = new_state["current_index"] is None
    if finished:
        _finish_attempt(fresh, user, subject)
        fresh = _safe(lambda: dbm.get_ai_test_attempt(int(attempt_id), user_id)) or fresh
        new_state = _attempt_state(fresh)

    return {
        "verdict": verdict,
        "moved_on": moved_on,
        "try_count": try_count,
        "tries_left": max(0, MAX_RETRIES_PER_QUESTION - try_count) if retry_until_correct else 0,
        "feedback": feedback,
        "dpoints_delta": round(dpoints, 2),
        "attempt": new_state,
        "finished": finished,
    }


def _student_subject(user: dict) -> str:
    from backend.main import _user_subjects_from_row

    subjects = _safe(lambda: _user_subjects_from_row(user), []) or []
    return str(subjects[0]) if subjects else "English"


def _finish_attempt(attempt: dict, user: dict, subject: str) -> None:
    dbm.bump_ai_test_counters(int(attempt.get("id") or 0), complete=True)
    source_type = str(attempt.get("source_type") or "")
    if source_type == "homework":
        hid = int(attempt.get("source_id") or 0)
        if hid > 0:
            _safe(
                lambda: dbm.upsert_homework_submission(
                    homework_id=hid,
                    student_id=int(user.get("id") or 0),
                    status="pending_review",
                    note="AI test yakunlandi",
                    proof_image_url=None,
                    proof_images_json=None,
                )
            )
    if source_type == "weekly_review":
        week_start = _week_bounds()[0]
        _safe(lambda: dbm.complete_weekly_review(int(user.get("id") or 0), week_start))
        reward = _setting("weekly_review_reward", 10.0)
        if reward:
            _safe(
                lambda: dbm.add_dpoints(
                    int(user.get("id") or 0), float(reward), subject=subject, change_type="weekly_review_done"
                )
            )


# ── Avtomatik tekshirish ────────────────────────────────────────────────────

def _norm_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^\w\s'’-]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _check_auto(question: dict, payload: AiTestAnswerRequest) -> tuple[str, dict]:
    kind = str(question.get("kind") or "")
    if kind == "listening":
        options = question.get("options") or []
        correct = int(question.get("correct_index") or 0)
        chosen = payload.choice_index
        if chosen is None:
            return "wrong", {"reason": "Javob tanlanmadi"}
        ok = int(chosen) == correct
        return ("correct" if ok else "wrong"), {
            "correct_answer": options[correct] if 0 <= correct < len(options) else None,
        }
    if kind == "matching":
        pairs = {str(p.get("left")): str(p.get("right")) for p in (question.get("pairs") or [])}
        given = {str(k): str(v) for k, v in (payload.pairs or {}).items()}
        wrong_keys = [left for left, right in pairs.items() if _norm_text(given.get(left)) != _norm_text(right)]
        return ("correct" if not wrong_keys else "wrong"), {
            "wrong_items": wrong_keys,
            "wrong_count": len(wrong_keys),
        }
    if kind == "scrambled_sentence":
        expected = _norm_text(question.get("answer"))
        given = _norm_text(" ".join(payload.order or []) or payload.answer_text)
        return ("correct" if given == expected else "wrong"), {
            "hint": "So'zlar tartibini qayta ko'ring" if given != expected else None,
        }
    expected = [question.get("answer"), *(question.get("accepted_answers") or [])]
    normalized = {_norm_text(e) for e in expected if e}
    given = _norm_text(payload.answer_text)
    if not given:
        return "wrong", {"reason": "Javob bo'sh"}
    if given in normalized:
        return "correct", {}
    close = any(_levenshtein(given, e) <= 1 for e in normalized)
    return "wrong", {"almost": close, "hint": "Imloni tekshiring" if close else None}


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if abs(len(a) - len(b)) > 2:
        return 99
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# ── AI tekshirish (grammatika + talaffuz + daraja mosligi) ──────────────────

async def _transcribe(audio_url: str, subject: str, x_language: str | None) -> str:
    """xAI STT bilan audio -> matn."""
    from backend.main import HOMEWORK_UPLOAD_DIR, _speech_language_code
    from ai_generator import _get_xai_api_key
    import aiohttp

    api_key = _safe(lambda: _get_xai_api_key())
    if not api_key:
        raise HTTPException(status_code=503, detail="AI servis sozlanmagan")
    filename = Path(urlparse(str(audio_url or "")).path).name
    audio_path = HOMEWORK_UPLOAD_DIR / filename
    if not filename or not audio_path.is_file():
        raise HTTPException(status_code=404, detail="Audio fayl serverda topilmadi")
    form = aiohttp.FormData()
    form.add_field("language", _speech_language_code(subject, x_language))
    form.add_field("format", "true")
    content_type = mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream"
    with audio_path.open("rb") as fh:
        # Fayl maydoni xAI STT uchun oxirgi bo'lishi shart.
        form.add_field("file", fh, filename=audio_path.name, content_type=content_type)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.x.ai/v1/stt",
                headers={"Authorization": f"Bearer {api_key}"},
                data=form,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as resp:
                if resp.status != 200:
                    detail = (await resp.text())[:300]
                    logger.warning("ai-test stt failed status=%s detail=%s", resp.status, detail)
                    raise HTTPException(status_code=503, detail="Audio transkript qilinmadi, qayta urinib ko'ring")
                data = await resp.json(content_type=None)
                return str((data or {}).get("text") or "").strip()


def _ai_check_prompt(question: dict, answer: str, subject: str, result_language: str, spoken: bool) -> str:
    kind = str(question.get("kind") or "")
    level = str(question.get("target_level") or question.get("level") or "").strip()
    parts = [
        f"You are a strict but fair {subject} teacher checking one student answer.",
        f"Exercise type: {kind}.",
        f"Task given to the student: {question.get('prompt') or ''}",
    ]
    if question.get("word"):
        parts.append(f"The student MUST use this word: {question['word']}")
    if question.get("passage"):
        parts.append(f"Reference text:\n{question['passage']}")
    if question.get("reference_answer"):
        parts.append(f"A model answer (not the only valid one): {question['reference_answer']}")
    if level:
        parts.append(
            f"The student's level is {level}. The answer must be close to that level: "
            "not a trivial 2-word sentence for B1+, and not over-complicated for A1/A2."
        )
    parts.append(
        ("This answer was SPOKEN and transcribed by speech-to-text. "
         "Judge pronunciation from the transcript: if words came out as different words, "
         "flag them as pronunciation problems. Ignore missing punctuation and capitalisation."
         if spoken else
         "This answer was TYPED. Judge spelling, punctuation and grammar.")
    )
    parts.append(
        "Mark the answer as correct ONLY if: grammar is correct, the required word is used properly "
        "(if one was required), the meaning answers the task, and the level fits."
    )
    parts.append(
        f"Write every explanation field in {result_language}. Do not translate the student's own answer.\n"
        "Return ONLY valid JSON, no markdown:\n"
        '{"is_correct":true,'
        '"grammar_ok":true,"pronunciation_ok":true,"level_ok":true,'
        '"corrected":"the corrected version of the answer",'
        '"grammar_errors":[{"original":"...","correction":"...","explanation":"..."}],'
        '"pronunciation_errors":[{"word":"...","note":"..."}],'
        '"score":8.5,"feedback":"one short encouraging sentence with the main fix"}'
    )
    parts.append(f"Student answer:\n{answer}")
    return "\n\n".join(parts)


async def _check_with_ai(
    question: dict, payload: AiTestAnswerRequest, subject: str, x_language: str | None
) -> tuple[str, dict]:
    from backend.main import _ai_result_language

    kind = str(question.get("kind") or "")
    meta = AI_TEST_TYPES.get(kind, {})
    input_mode = str(meta.get("input") or "text")
    spoken = False
    answer = str(payload.answer_text or "").strip()

    if input_mode == "audio" or (input_mode == "audio_or_text" and payload.audio_url):
        if not payload.audio_url:
            raise HTTPException(status_code=400, detail="Ovozli javob yuborilmadi")
        answer = await _transcribe(payload.audio_url, subject, x_language)
        spoken = True
        if not answer:
            return "wrong", {
                "transcript": "",
                "feedback": "Ovozingiz aniq eshitilmadi. Yana bir marta, sekinroq va balandroq gapiring.",
                "pronunciation_ok": False,
            }
    if not answer:
        return "wrong", {"feedback": "Javob bo'sh qoldirilgan."}

    from ai_generator import XAI_ENDPOINT, _get_xai_api_key, _xai_apply_payload_tuning, get_grok_model_candidates
    import aiohttp

    api_key = _safe(lambda: _get_xai_api_key())
    if not api_key:
        raise HTTPException(status_code=503, detail="AI servis sozlanmagan")
    prompt = _ai_check_prompt(question, answer, subject, _ai_result_language(x_language), spoken)
    raw = ""
    try:
        async with aiohttp.ClientSession() as session:
            for model in get_grok_model_candidates()[:2]:
                body = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a precise language-exercise grader. Output only JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 1200,
                }
                _xai_apply_payload_tuning(body, model=model, stream=False)
                async with session.post(
                    XAI_ENDPOINT,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=body,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        raw = str(data.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()
                        if raw:
                            break
    except Exception as exc:
        logger.exception("ai-test grading failed kind=%s: %s", kind, exc)
        raise HTTPException(status_code=503, detail="AI tekshirish vaqtincha ishlamayapti, qayta urinib ko'ring")

    parsed = _extract_json_object(raw)
    if not parsed:
        raise HTTPException(status_code=503, detail="AI javobi tushunarsiz, qayta urinib ko'ring")
    verdict = "correct" if bool(parsed.get("is_correct")) else "wrong"
    parsed["transcript"] = answer if spoken else None
    parsed["was_spoken"] = spoken
    return verdict, parsed


# ═══════════════════════════════════════════════════════════════════════════
# 4. HAFTALIK MAJBURIY TAKRORIY TEST
# ═══════════════════════════════════════════════════════════════════════════

def _week_bounds(now: datetime | None = None) -> tuple[str, str]:
    """Joriy haftaning dushanba–yakshanba chegaralari (YYYY-MM-DD)."""
    current = now or datetime.now()
    monday = current - timedelta(days=current.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def _weekly_review_questions(user_id: int, limit: int = 15) -> list[dict]:
    """Hafta ichida ishlangan testlardan takroriy savollar to'plami."""
    week_start, week_end = _week_bounds()
    rows = _safe(
        lambda: dbm.list_user_week_attempts(user_id, f"{week_start} 00:00:00", f"{week_end} 23:59:59"), []
    ) or []
    collected: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        if str(row.get("origin") or "") == "ai_test":
            attempt = _safe(lambda aid=int(row.get("id") or 0): dbm.get_ai_test_attempt(aid, user_id))
            source = (attempt or {}).get("questions") or []
        else:
            test = _safe(
                lambda: dbm.get_content_test(
                    str(row.get("content_type") or "book"), int(row.get("content_id") or 0)
                )
            )
            source = _normalize_questions((test or {}).get("questions"))
        for question in source:
            key = f"{question.get('kind')}|{_norm_text(question.get('prompt') or question.get('word'))}"
            if not key.strip("|") or key in seen:
                continue
            if question.get("needs_audio_upload"):
                continue
            seen.add(key)
            collected.append(question)
        if len(collected) >= limit:
            break
    return collected[:limit]


@router.get("/student/weekly-review")
async def student_weekly_review(authorization: str | None = Header(default=None)):
    """Studentga haftalik takrorlash holati."""
    user = _auth(authorization, STUDENT_ROLES)
    week_start, week_end = _week_bounds()
    review = _safe(lambda: dbm.get_weekly_review(int(user.get("id") or 0), week_start))
    available = len(_weekly_review_questions(int(user.get("id") or 0)))
    return {
        "week_start": week_start,
        "week_end": week_end,
        "status": str((review or {}).get("status") or "none"),
        "homework_id": (review or {}).get("homework_id"),
        "question_count": available,
        "is_required": bool(review) and str((review or {}).get("status") or "") == "assigned",
    }


@router.post("/admin/weekly-review/run")
async def admin_weekly_review_run(
    authorization: str | None = Header(default=None),
    dry_run: bool = Query(default=False),
):
    """Haftalik takroriy testni barcha studentlarga homework qilib tarqatadi.

    Cron / scheduler shu endpointni hafta oxirida chaqiradi."""
    _auth(authorization, {"admin", "superadmin"})
    result = await asyncio.to_thread(_run_weekly_review_job, bool(dry_run))
    return result


def _run_weekly_review_job(dry_run: bool = False) -> dict:
    week_start, week_end = _week_bounds()
    conn = dbm.get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT DISTINCT u.id
            FROM users u
            JOIN user_groups ug ON ug.user_id = u.id
            WHERE u.login_type IN (1, 2)
            """
        )
        student_ids = [int(r["id"]) for r in (cur.fetchall() or []) if r and r.get("id")]
    except Exception:
        logger.exception("weekly review: student list failed")
        student_ids = []
    finally:
        conn.close()

    assigned = 0
    skipped = 0
    for student_id in student_ids:
        existing = _safe(lambda sid=student_id: dbm.get_weekly_review(sid, week_start))
        if existing:
            skipped += 1
            continue
        questions = _weekly_review_questions(student_id)
        if not questions:
            skipped += 1
            continue
        if dry_run:
            assigned += 1
            continue
        teacher_id = _weekly_review_teacher_id(student_id)
        homework = _safe(
            lambda sid=student_id, tid=teacher_id: dbm.create_homework(
                tid,
                sid,
                f"Haftalik takrorlash ({week_start} — {week_end})",
                description=(
                    "Bu hafta ishlagan testlaringiz takrorlanadi. Bajarish majburiy — "
                    "analitika foizingizga ta'sir qiladi."
                ),
                due_at=f"{(datetime.strptime(week_end, '%Y-%m-%d') + timedelta(days=3)).strftime('%Y-%m-%d')} 23:59:00",
                homework_kind="test",
            )
        )
        homework_id = int((homework or {}).get("id") or 0)
        if homework_id > 0:
            _safe(
                lambda hid=homework_id, tid=teacher_id: dbm.save_content_test(
                    "homework", hid, json.dumps(questions, ensure_ascii=False), tid,
                    title="Haftalik takrorlash", raw_questions=True,
                )
            )
        _safe(
            lambda sid=student_id, hid=homework_id: dbm.upsert_weekly_review(
                sid, week_start, week_end, hid or None, attempt_count=len(questions)
            )
        )
        assigned += 1
    logger.info("weekly review job week=%s assigned=%s skipped=%s dry_run=%s", week_start, assigned, skipped, dry_run)
    return {
        "week_start": week_start,
        "week_end": week_end,
        "students": len(student_ids),
        "assigned": assigned,
        "skipped": skipped,
        "dry_run": dry_run,
    }


def _weekly_review_teacher_id(student_id: int) -> int:
    """Studentning guruh o'qituvchisi; topilmasa 0 (tizim vazifasi)."""
    conn = dbm.get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT g.teacher_id
            FROM user_groups ug
            JOIN groups g ON g.id = ug.group_id
            WHERE ug.user_id = ? AND g.teacher_id IS NOT NULL
            ORDER BY ug.group_id DESC LIMIT 1
            """,
            (int(student_id),),
        )
        row = cur.fetchone()
        return int((row or {}).get("teacher_id") or 0)
    except Exception:
        return 0
    finally:
        conn.close()


@router.post("/admin/weekly-review/penalize")
async def admin_weekly_review_penalize(authorization: str | None = Header(default=None)):
    """O'tgan hafta takrorlashini bajarmaganlarga jarima (D'point)."""
    _auth(authorization, {"admin", "superadmin"})
    last_week_start = (datetime.now() - timedelta(days=7))
    week_start = (last_week_start - timedelta(days=last_week_start.weekday())).strftime("%Y-%m-%d")
    penalty = abs(_setting("weekly_review_missed_penalty", 5.0))
    dbm.ensure_weekly_reviews_schema()
    conn = dbm.get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT user_id FROM weekly_reviews WHERE week_start=? AND status='assigned'",
            (week_start,),
        )
        user_ids = [int(r["user_id"]) for r in (cur.fetchall() or []) if r and r.get("user_id")]
    finally:
        conn.close()
    if penalty > 0:
        for uid in user_ids:
            _safe(lambda u=uid: dbm.add_dpoints(u, -penalty, change_type="weekly_review_missed"))
    return {"week_start": week_start, "penalized": len(user_ids), "penalty": penalty}
