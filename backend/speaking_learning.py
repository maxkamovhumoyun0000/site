"""Speaking-only Learning Path API. Data is intentionally isolated from student learning tables."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from db import get_conn

router = APIRouter()
STAFF_ROLES = {"speaking_admin", "admin", "superadmin", "developer"}
QUESTION_TYPES = {
    "multiple_choice", "true_false", "short_answer", "fill_blank", "gap_fill",
    "word_order", "matching", "translation", "spelling", "write_sentence",
    "guided_writing", "paraphrase", "dialogue_completion", "reading_open",
    "listening_open", "listening_tf", "listening_gap", "listening_dictation",
    "dictation", "passage_cloze", "picture_description", "speak_sentence",
    "speaking_repeat", "speaking_response", "read_aloud", "reading_set",
    "listening_set", "multiple_choice_set", "word_practice",
}
AI_CHECKED_TYPES = {
    "write_sentence", "guided_writing", "paraphrase", "dialogue_completion",
    "reading_open", "listening_open", "picture_description", "translation",
    "word_practice", "speak_sentence", "speaking_repeat", "speaking_response", "read_aloud",
}


def _user(authorization: str | None, *, staff: bool = False) -> dict[str, Any]:
    from backend.main import _require_role, _user_row_from_bearer
    user = _user_row_from_bearer(authorization)
    _require_role(user, STAFF_ROLES if staff else {"speaking_user", "student", "teacher", "speaking_admin", "admin", "superadmin", "developer"})
    return user


def ensure_tables() -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""CREATE TABLE IF NOT EXISTS speaking_learning_tracks (
            id BIGSERIAL PRIMARY KEY, title TEXT NOT NULL, description TEXT DEFAULT '',
            subject TEXT NOT NULL DEFAULT 'english', is_published BOOLEAN NOT NULL DEFAULT FALSE,
            sort_order INTEGER NOT NULL DEFAULT 0, created_by INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS speaking_learning_modules (
            id BIGSERIAL PRIMARY KEY, track_id BIGINT NOT NULL REFERENCES speaking_learning_tracks(id) ON DELETE CASCADE,
            title TEXT NOT NULL, description TEXT DEFAULT '', cover_key TEXT NOT NULL DEFAULT 'star', sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("ALTER TABLE speaking_learning_modules ADD COLUMN IF NOT EXISTS cover_key TEXT NOT NULL DEFAULT 'star'")
        cur.execute("""CREATE TABLE IF NOT EXISTS speaking_learning_questions (
            id BIGSERIAL PRIMARY KEY, module_id BIGINT NOT NULL REFERENCES speaking_learning_modules(id) ON DELETE CASCADE,
            prompt TEXT NOT NULL, question_type TEXT NOT NULL DEFAULT 'multiple_choice', options_json TEXT DEFAULT '[]',
            answer_json TEXT DEFAULT 'null', explanation TEXT DEFAULT '', sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        # Additive migration: older Speaking installs keep their existing questions.
        cur.execute("ALTER TABLE speaking_learning_questions ADD COLUMN IF NOT EXISTS data_json TEXT NOT NULL DEFAULT '{}'")
        cur.execute("""CREATE TABLE IF NOT EXISTS speaking_learning_answer_checks (
            user_id BIGINT NOT NULL, module_id BIGINT NOT NULL REFERENCES speaking_learning_modules(id) ON DELETE CASCADE,
            question_id BIGINT NOT NULL REFERENCES speaking_learning_questions(id) ON DELETE CASCADE,
            answer_hash TEXT NOT NULL, result_json TEXT NOT NULL DEFAULT '{}',
            checked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id,module_id,question_id))""")
        cur.execute("""CREATE TABLE IF NOT EXISTS speaking_learning_attempts (
            id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, module_id BIGINT NOT NULL REFERENCES speaking_learning_modules(id) ON DELETE CASCADE,
            score INTEGER NOT NULL, answers_json TEXT NOT NULL DEFAULT '{}', passed BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS speaking_learning_final_attempts (
            id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL,
            track_id BIGINT NOT NULL REFERENCES speaking_learning_tracks(id) ON DELETE CASCADE,
            score INTEGER NOT NULL, answers_json TEXT NOT NULL DEFAULT '{}', passed BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit()
    finally:
        cur.close()
        conn.close()


class TrackInput(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=2000)
    subject: str = Field(default="english", pattern="^(english|russian)$")
    is_published: bool = False


class ModuleInput(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=2000)
    cover_key: str = Field(default="star", pattern="^(dolphin|chest|jellyfish|ship|star|trophy)$")


class QuestionInput(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    question_type: str = Field(default="multiple_choice", min_length=2, max_length=48)
    options: list[Any] = Field(default_factory=list, max_length=20)
    answer: Any = None
    explanation: str = Field(default="", max_length=2000)
    data: dict[str, Any] = Field(default_factory=dict)


class SubmitInput(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class CheckAnswerInput(BaseModel):
    question_id: int
    answer: Any = None


def _answer_hash(answer: Any) -> str:
    encoded = json.dumps(answer, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _grade_submission(kind: str, expected: Any, given: Any, data: dict[str, Any], saved_check: tuple[str, dict[str, Any]] | None) -> tuple[int, int]:
    if kind in AI_CHECKED_TYPES:
        if saved_check and saved_check[0] == _answer_hash(given):
            result = saved_check[1]
            return max(0, int(result.get("correct_count", int(result.get("correct") is True)))), max(1, int(result.get("total", 1)))
        # Never trust an unverified client-provided answer for an AI-graded test.
        return 0, 1
    return _grade(kind, expected, given, data)


def _save_answer_check(cur: Any, user_id: int, module_id: int, question_id: int, answer: Any, result: dict[str, Any]) -> None:
    cur.execute("""INSERT INTO speaking_learning_answer_checks
        (user_id,module_id,question_id,answer_hash,result_json,checked_at)
        VALUES(%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)
        ON CONFLICT(user_id,module_id,question_id) DO UPDATE SET
        answer_hash=EXCLUDED.answer_hash,result_json=EXCLUDED.result_json,checked_at=CURRENT_TIMESTAMP""",
        (user_id,module_id,question_id,_answer_hash(answer),json.dumps(result,ensure_ascii=False)))


def _invalidate_track_final_exam(cur: Any, track_id: int) -> None:
    cur.execute("DELETE FROM speaking_learning_final_attempts WHERE track_id=%s", (track_id,))


def _invalidate_module_progress(cur: Any, module_id: int) -> None:
    cur.execute("DELETE FROM speaking_learning_attempts WHERE module_id=%s", (module_id,))
    cur.execute("DELETE FROM speaking_learning_answer_checks WHERE module_id=%s", (module_id,))
    cur.execute("DELETE FROM speaking_learning_final_attempts WHERE track_id=(SELECT track_id FROM speaking_learning_modules WHERE id=%s)", (module_id,))


def _owned_audio_path(audio_url: str, user_id: int) -> Path:
    """Accept only audio uploaded for this user's Speaking Learning Path attempt."""
    from backend.main import HOMEWORK_UPLOAD_DIR

    filename = Path(urlparse(str(audio_url or "")).path).name
    if not filename.startswith(f"speaking_lp_voice_{user_id}_") or Path(filename).suffix.lower() != ".m4a":
        raise HTTPException(422, "Invalid Speaking answer audio")
    root = Path(HOMEWORK_UPLOAD_DIR).resolve()
    target = (root / filename).resolve()
    if target.parent != root or not target.is_file():
        raise HTTPException(422, "Speaking answer audio was not found")
    return target


def _validate_question(payload: QuestionInput) -> None:
    if payload.question_type not in QUESTION_TYPES:
        raise HTTPException(422, "Unsupported Speaking test type")
    if len(json.dumps(payload.data, ensure_ascii=False)) > 50000:
        raise HTTPException(413, "Speaking test data is too large")
    if payload.question_type == "multiple_choice":
        options = [str(value).strip() for value in payload.options]
        if len(options) < 2 or len(set(options)) != len(options) or not all(options):
            raise HTTPException(422, "Provide at least two distinct answer options")
        if not isinstance(payload.answer, str) or payload.answer.strip() not in options:
            raise HTTPException(422, "The correct answer must match one of the options")
    elif payload.question_type in {"true_false", "listening_tf"} and not isinstance(payload.answer, bool):
        raise HTTPException(422, "The correct answer must be true or false")
    elif payload.question_type == "matching":
        pairs = payload.data.get("pairs", [])
        if not isinstance(pairs, list) or not pairs or not all(
            isinstance(pair, dict) and str(pair.get("left", "")).strip() and str(pair.get("right", "")).strip()
            for pair in pairs
        ):
            raise HTTPException(422, "Matching questions require data.pairs with left and right values")
        if payload.answer is None:
            payload.answer = {str(pair["left"]): str(pair["right"]) for pair in pairs}
    elif payload.question_type in {"word_order", "fill_blank", "gap_fill", "passage_cloze", "reading_set", "listening_set", "multiple_choice_set"}:
        sub_questions = payload.data.get("sub_questions")
        if payload.question_type in {"reading_set", "listening_set", "multiple_choice_set"} and sub_questions:
            if not isinstance(payload.answer, dict) or len(payload.answer) < len(sub_questions):
                raise HTTPException(422, "Provide an answer key for every sub-question")
        elif payload.answer is None or (isinstance(payload.answer, str) and not payload.answer.strip()):
            raise HTTPException(422, "Provide an answer key or sub_questions")
    elif payload.answer is None or (isinstance(payload.answer, str) and not payload.answer.strip()):
        raise HTTPException(422, "Provide an answer key so the module can be graded")


def _decode_question(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    item = dict(row) if hasattr(row, "keys") else dict(zip(fields, row))
    for json_key, output_key, fallback in (
        ("options_json", "options", "[]"),
        ("answer_json", "answer", "null"),
        ("data_json", "data", "{}"),
    ):
        if json_key in item:
            raw = item.pop(json_key)
            try:
                item[output_key] = json.loads(raw or fallback)
            except (TypeError, json.JSONDecodeError):
                item[output_key] = json.loads(fallback)
    return item


def _public_data(value: Any) -> Any:
    """Remove accidentally embedded answer keys from author-supplied payloads."""
    private_keys = {"answer", "correct", "correct_answer", "accepted_answers", "answer_key", "expected"}
    if isinstance(value, dict):
        return {key: _public_data(item) for key, item in value.items() if str(key).casefold() not in private_keys}
    if isinstance(value, list):
        return [_public_data(item) for item in value]
    return value


def _norm(value: Any) -> str:
    return " ".join(str(value if value is not None else "").casefold().split())


def _is_correct(kind: str, expected: Any, given: Any, data: dict[str, Any]) -> bool:
    correct, total = _grade(kind, expected, given, data)
    return total > 0 and correct == total


def _grade(kind: str, expected: Any, given: Any, data: dict[str, Any]) -> tuple[int, int]:
    accepted = data.get("accepted_answers")
    candidates = accepted if isinstance(accepted, list) else [expected]
    if kind == "matching" and isinstance(expected, dict):
        submitted = given if isinstance(given, dict) else {}
        total = len(expected)
        correct = sum(1 for key, value in expected.items() if _norm(submitted.get(key)) == _norm(value))
        return correct, total
    if kind in {"reading_set", "listening_set", "multiple_choice_set"} and isinstance(expected, dict):
        submitted = given if isinstance(given, dict) else {}
        total = len(expected)
        correct = sum(1 for key, value in expected.items() if _norm(submitted.get(str(key))) in {_norm(item) for item in (value if isinstance(value, list) else [value])})
        return correct, total
    if kind in {"word_order"}:
        matched = _norm(given).strip(" .!?\"'") == _norm(expected).strip(" .!?\"'")
        return int(matched), 1
    if kind in {"fill_blank", "gap_fill", "passage_cloze", "listening_gap"} and isinstance(expected, list):
        actual = given if isinstance(given, list) else [given]
        correct = sum(1 for index, item in enumerate(expected) if index < len(actual) and _norm(actual[index]) in {_norm(v) for v in (item if isinstance(item, list) else [item])})
        return correct, len(expected)
    if isinstance(expected, bool):
        matched = given is expected or _norm(given) == _norm(expected)
        return int(matched), 1
    matched = any(_norm(given) == _norm(candidate) for candidate in candidates)
    return int(matched), 1


@router.get("/staff/speaking-learning/tracks")
def staff_tracks(authorization: str | None = Header(default=None)):
    _user(authorization, staff=True)
    ensure_tables()
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT id,title,description,subject,is_published,sort_order FROM speaking_learning_tracks ORDER BY sort_order,id")
        rows = cur.fetchall()
        return {"items": [dict(row) if hasattr(row, "keys") else {"id": row[0], "title": row[1], "description": row[2], "subject": row[3], "is_published": row[4], "sort_order": row[5]} for row in rows]}
    finally:
        cur.close(); conn.close()


@router.post("/staff/speaking-learning/tracks")
def create_track(payload: TrackInput, authorization: str | None = Header(default=None)):
    user = _user(authorization, staff=True); ensure_tables()
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO speaking_learning_tracks(title,description,subject,is_published,created_by) VALUES(%s,%s,%s,%s,%s) RETURNING id", (payload.title.strip(), payload.description, payload.subject, payload.is_published, int(user.get("id") or 0)))
        row = cur.fetchone(); conn.commit()
        return {"id": row[0], "title": payload.title.strip()}
    finally:
        cur.close(); conn.close()


@router.patch("/staff/speaking-learning/tracks/{track_id}")
def update_track(track_id: int, payload: TrackInput, authorization: str | None = Header(default=None)):
    _user(authorization, staff=True); ensure_tables()
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("""UPDATE speaking_learning_tracks SET title=%s,description=%s,subject=%s,
            updated_at=CURRENT_TIMESTAMP WHERE id=%s RETURNING id""",
            (payload.title.strip(), payload.description.strip(), payload.subject, track_id))
        if not cur.fetchone():
            raise HTTPException(404, "Speaking learning track not found")
        conn.commit()
        return {"id": track_id}
    finally:
        cur.close(); conn.close()


@router.post("/staff/speaking-learning/tracks/{track_id}/publish")
def publish_track(track_id: int, payload: dict[str, bool], authorization: str | None = Header(default=None)):
    _user(authorization, staff=True); ensure_tables()
    conn = get_conn(); cur = conn.cursor()
    try:
        if bool(payload.get("is_published")):
            cur.execute("""SELECT COUNT(*), COUNT(*) FILTER (WHERE EXISTS (
                SELECT 1 FROM speaking_learning_questions q WHERE q.module_id=m.id
            )) FROM speaking_learning_modules m WHERE m.track_id=%s""", (track_id,))
            readiness = cur.fetchone()
            total = readiness[0] if not hasattr(readiness, "keys") else list(readiness.values())[0]
            ready = readiness[1] if not hasattr(readiness, "keys") else list(readiness.values())[1]
            if not total or ready != total:
                raise HTTPException(422, "Every module needs at least one test before publication")
        cur.execute("UPDATE speaking_learning_tracks SET is_published=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s RETURNING id,is_published", (bool(payload.get("is_published")), track_id))
        row=cur.fetchone()
        if not row: raise HTTPException(404, "Speaking learning track not found")
        conn.commit()
        return {"id": row[0], "is_published": row[1]}
    finally: cur.close(); conn.close()


@router.delete("/staff/speaking-learning/tracks/{track_id}")
def delete_track(track_id: int, authorization: str | None = Header(default=None)):
    _user(authorization, staff=True); ensure_tables(); conn=get_conn(); cur=conn.cursor()
    try:
        cur.execute("DELETE FROM speaking_learning_tracks WHERE id=%s RETURNING id", (track_id,))
        if not cur.fetchone(): raise HTTPException(404, "Speaking learning track not found")
        conn.commit(); return {"ok": True}
    finally: cur.close(); conn.close()


@router.get("/staff/speaking-learning/tracks/{track_id}/modules")
def staff_modules(track_id: int, authorization: str | None = Header(default=None)):
    _user(authorization, staff=True); ensure_tables()
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT id,title,description,cover_key,sort_order FROM speaking_learning_modules WHERE track_id=%s ORDER BY sort_order,id", (track_id,))
        return {"items": [dict(row) if hasattr(row, "keys") else {"id": row[0], "title": row[1], "description": row[2], "cover_key": row[3], "sort_order": row[4]} for row in cur.fetchall()]}
    finally:
        cur.close(); conn.close()


@router.post("/staff/speaking-learning/tracks/{track_id}/modules")
def create_module(track_id: int, payload: ModuleInput, authorization: str | None = Header(default=None)):
    _user(authorization, staff=True); ensure_tables()
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO speaking_learning_modules(track_id,title,description,cover_key) SELECT id,%s,%s,%s FROM speaking_learning_tracks WHERE id=%s RETURNING id", (payload.title.strip(), payload.description, payload.cover_key, track_id))
        row = cur.fetchone()
        if not row: raise HTTPException(404, "Speaking learning track not found")
        _invalidate_track_final_exam(cur,track_id)
        conn.commit(); return {"id": row[0], "title": payload.title.strip()}
    finally:
        cur.close(); conn.close()


@router.patch("/staff/speaking-learning/modules/{module_id}")
def update_module(module_id: int, payload: ModuleInput, authorization: str | None = Header(default=None)):
    _user(authorization, staff=True); ensure_tables()
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("UPDATE speaking_learning_modules SET title=%s,description=%s,cover_key=%s WHERE id=%s RETURNING id",
                    (payload.title.strip(), payload.description.strip(), payload.cover_key, module_id))
        if not cur.fetchone():
            raise HTTPException(404, "Speaking learning module not found")
        conn.commit()
        return {"id": module_id}
    finally:
        cur.close(); conn.close()


@router.delete("/staff/speaking-learning/modules/{module_id}")
def delete_module(module_id: int, authorization: str | None = Header(default=None)):
    _user(authorization, staff=True); ensure_tables(); conn=get_conn(); cur=conn.cursor()
    try:
        cur.execute("SELECT track_id FROM speaking_learning_modules WHERE id=%s", (module_id,))
        existing=cur.fetchone()
        if not existing: raise HTTPException(404, "Speaking learning module not found")
        track_id=existing["track_id"] if hasattr(existing,"keys") else existing[0]
        _invalidate_track_final_exam(cur,int(track_id))
        cur.execute("DELETE FROM speaking_learning_modules WHERE id=%s", (module_id,))
        conn.commit(); return {"ok": True}
    finally: cur.close(); conn.close()


@router.get("/staff/speaking-learning/modules/{module_id}/questions")
def staff_questions(module_id: int, authorization: str | None = Header(default=None)):
    _user(authorization, staff=True); ensure_tables()
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT id,prompt,question_type,options_json,answer_json,data_json,explanation,sort_order FROM speaking_learning_questions WHERE module_id=%s ORDER BY sort_order,id", (module_id,))
        rows = cur.fetchall()
        fields = ("id", "prompt", "question_type", "options_json", "answer_json", "data_json", "explanation", "sort_order")
        return {"items": [_decode_question(row, fields) for row in rows]}
    finally:
        cur.close(); conn.close()


@router.post("/staff/speaking-learning/modules/{module_id}/questions")
def create_question(module_id: int, payload: QuestionInput, authorization: str | None = Header(default=None)):
    _user(authorization, staff=True); ensure_tables()
    _validate_question(payload)
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO speaking_learning_questions(module_id,prompt,question_type,options_json,answer_json,explanation,data_json) SELECT id,%s,%s,%s,%s,%s,%s FROM speaking_learning_modules WHERE id=%s RETURNING id", (payload.prompt.strip(), payload.question_type, json.dumps(payload.options, ensure_ascii=False), json.dumps(payload.answer, ensure_ascii=False), payload.explanation, json.dumps(payload.data, ensure_ascii=False), module_id))
        row=cur.fetchone()
        if not row: raise HTTPException(404, "Speaking learning module not found")
        _invalidate_module_progress(cur,module_id)
        conn.commit(); return {"id": row[0]}
    finally:
        cur.close(); conn.close()


@router.patch("/staff/speaking-learning/questions/{question_id}")
def update_question(question_id: int, payload: QuestionInput, authorization: str | None = Header(default=None)):
    _user(authorization, staff=True); _validate_question(payload); ensure_tables()
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("""UPDATE speaking_learning_questions SET prompt=%s,question_type=%s,
            options_json=%s,answer_json=%s,explanation=%s,data_json=%s WHERE id=%s RETURNING id,module_id""",
            (payload.prompt.strip(), payload.question_type,
             json.dumps(payload.options, ensure_ascii=False),
             json.dumps(payload.answer, ensure_ascii=False),
             payload.explanation.strip(), json.dumps(payload.data, ensure_ascii=False), question_id))
        row=cur.fetchone()
        if not row:
            raise HTTPException(404, "Speaking learning question not found")
        module_id = int(row["module_id"] if hasattr(row,"keys") else row[1])
        _invalidate_module_progress(cur,module_id)
        conn.commit()
        return {"id": question_id}
    finally:
        cur.close(); conn.close()


@router.delete("/staff/speaking-learning/questions/{question_id}")
def delete_question(question_id: int, authorization: str | None = Header(default=None)):
    _user(authorization, staff=True); ensure_tables(); conn=get_conn(); cur=conn.cursor()
    try:
        cur.execute("DELETE FROM speaking_learning_questions WHERE id=%s RETURNING id,module_id", (question_id,))
        row=cur.fetchone()
        if not row: raise HTTPException(404, "Speaking learning question not found")
        module_id=int(row["module_id"] if hasattr(row,"keys") else row[1])
        _invalidate_module_progress(cur,module_id)
        conn.commit(); return {"ok": True}
    finally: cur.close(); conn.close()


@router.get("/speaking/learning/tracks")
def public_tracks(authorization: str | None = Header(default=None)):
    user = _user(authorization); ensure_tables()
    conn=get_conn(); cur=conn.cursor()
    try:
        cur.execute("""SELECT t.id,t.title,t.description,t.subject,
            COUNT(DISTINCT m.id) AS module_count,
            COUNT(DISTINCT CASE WHEN a.passed=TRUE THEN m.id END) AS passed_modules,
            EXISTS(SELECT 1 FROM speaking_learning_final_attempts fa WHERE fa.track_id=t.id AND fa.user_id=%s AND fa.passed=TRUE) AS final_exam_passed
            FROM speaking_learning_tracks t
            LEFT JOIN speaking_learning_modules m ON m.track_id=t.id
            LEFT JOIN speaking_learning_attempts a ON a.module_id=m.id AND a.user_id=%s
            WHERE t.is_published=TRUE GROUP BY t.id ORDER BY t.sort_order,t.id""", (int(user.get("id") or 0), int(user.get("id") or 0)))
        rows=cur.fetchall(); items=[]
        fields=("id","title","description","subject","module_count","passed_modules","final_exam_passed")
        for row in rows:
            item=dict(row) if hasattr(row,"keys") else dict(zip(fields,row))
            count=int(item.get("module_count") or 0); passed=int(item.get("passed_modules") or 0)
            final_passed=bool(item.get("final_exam_passed"))
            item["progress_percent"]=round((passed+int(final_passed))*100/(count+1)) if count else 0
            items.append(item)
        return {"items": items}
    finally: cur.close(); conn.close()


@router.get("/speaking/learning/tracks/{track_id}/final-exam")
def public_final_exam(track_id: int, authorization: str | None = Header(default=None)):
    user = _user(authorization); ensure_tables(); user_id = int(user.get("id") or 0)
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT id,title FROM speaking_learning_tracks WHERE id=%s AND is_published=TRUE", (track_id,))
        track = cur.fetchone()
        if not track:
            raise HTTPException(404, "Speaking learning track not found")
        cur.execute("SELECT COUNT(*) AS total FROM speaking_learning_modules WHERE track_id=%s", (track_id,))
        module_count = cur.fetchone()
        module_count = int(module_count["total"] if hasattr(module_count,"keys") else module_count[0]) if module_count else 0
        if not module_count:
            raise HTTPException(404, "Speaking learning track has no modules")
        modules = _module_progress(cur, track_id, user_id)
        if any(module.get("passed") is not True for module in modules):
            raise HTTPException(423, "Complete every module before starting the final exam")
        cur.execute("""SELECT q.id,q.module_id,m.title AS module_title,q.prompt,q.question_type,q.options_json,q.data_json,q.sort_order
            FROM speaking_learning_questions q JOIN speaking_learning_modules m ON m.id=q.module_id
            WHERE m.track_id=%s ORDER BY m.sort_order,m.id,q.sort_order,q.id""", (track_id,))
        rows = cur.fetchall(); items = []
        fields = ("id","module_id","module_title","prompt","question_type","options_json","data_json","sort_order")
        for row in rows:
            item = _decode_question(row, fields)
            item["data"] = _public_data(item.get("data", {}))
            items.append(item)
        if not items:
            raise HTTPException(404, "Speaking learning track has no final exam questions")
        cur.execute("SELECT MAX(score) AS best_score,BOOL_OR(passed) AS passed FROM speaking_learning_final_attempts WHERE user_id=%s AND track_id=%s", (user_id,track_id))
        state = cur.fetchone()
        best_score, passed = (state[0],state[1]) if state and not hasattr(state,"keys") else ((state.get("best_score") if state else None),(state.get("passed") if state else False))
        return {"track_id":track_id,"track_title":track["title"] if hasattr(track,"keys") else track[1],"passing_score":70,"unlocked":True,"passed":bool(passed),"best_score":int(best_score or 0),"items":items}
    finally:
        cur.close(); conn.close()


@router.post("/speaking/learning/tracks/{track_id}/final-exam/submit")
def submit_final_exam(track_id: int, payload: SubmitInput, authorization: str | None = Header(default=None)):
    user = _user(authorization); ensure_tables(); user_id = int(user.get("id") or 0)
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM speaking_learning_tracks WHERE id=%s AND is_published=TRUE", (track_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Speaking learning track not found")
        modules = _module_progress(cur, track_id, user_id)
        if not modules or any(module.get("passed") is not True for module in modules):
            raise HTTPException(423, "Complete every module before submitting the final exam")
        cur.execute("""SELECT q.id,q.module_id,q.question_type,q.answer_json,q.data_json,q.explanation
            FROM speaking_learning_questions q JOIN speaking_learning_modules m ON m.id=q.module_id
            WHERE m.track_id=%s ORDER BY m.sort_order,m.id,q.sort_order,q.id""", (track_id,))
        questions = cur.fetchall()
        if not questions:
            raise HTTPException(404, "Speaking learning track has no final exam questions")
        cur.execute("""SELECT c.question_id,c.answer_hash,c.result_json FROM speaking_learning_answer_checks c
            JOIN speaking_learning_modules m ON m.id=c.module_id WHERE c.user_id=%s AND m.track_id=%s""", (user_id,track_id))
        saved_checks = {}
        for row in cur.fetchall():
            qid, digest, raw_result = (row["question_id"],row["answer_hash"],row["result_json"]) if hasattr(row,"keys") else row
            try: saved_checks[int(qid)] = (str(digest),json.loads(raw_result or "{}"))
            except (TypeError,ValueError,json.JSONDecodeError): continue
        correct = total = 0; results=[]
        for row in questions:
            qid,_,kind,answer_json,data_json,explanation = (row["id"],row["module_id"],row["question_type"],row["answer_json"],row["data_json"],row["explanation"]) if hasattr(row,"keys") else row
            expected=json.loads(answer_json or "null"); data=json.loads(data_json or "{}")
            given=payload.answers.get(str(qid))
            if isinstance(given,dict) and given.get("audio_url"):
                _owned_audio_path(str(given["audio_url"]),user_id)
            item_correct,item_total=_grade_submission(kind,expected,given,data,saved_checks.get(int(qid)))
            correct+=item_correct; total+=item_total
            results.append({"question_id":qid,"correct":item_total>0 and item_correct==item_total,"correct_count":item_correct,"total":item_total,"correct_answer":expected,"explanation":explanation})
        score=round(correct*100/total) if total else 0; passed=score>=70
        cur.execute("INSERT INTO speaking_learning_final_attempts(user_id,track_id,score,answers_json,passed) VALUES(%s,%s,%s,%s,%s)", (user_id,track_id,score,json.dumps(payload.answers,ensure_ascii=False),passed))
        conn.commit()
        return {"score":score,"passed":passed,"correct":correct,"total":total,"results":results}
    finally:
        cur.close(); conn.close()


def _module_progress(cur: Any, track_id: int, user_id: int) -> list[dict[str, Any]]:
    cur.execute("""SELECT m.id,m.title,m.description,m.cover_key,m.sort_order,
        (SELECT COUNT(*) FROM speaking_learning_questions q WHERE q.module_id=m.id) AS question_count,
        (SELECT MAX(a.score) FROM speaking_learning_attempts a WHERE a.module_id=m.id AND a.user_id=%s) AS best_score,
        EXISTS(SELECT 1 FROM speaking_learning_attempts a WHERE a.module_id=m.id AND a.user_id=%s) AS attempted,
        EXISTS(SELECT 1 FROM speaking_learning_attempts a WHERE a.module_id=m.id AND a.user_id=%s AND a.passed=TRUE) AS passed
        FROM speaking_learning_modules m WHERE m.track_id=%s ORDER BY m.sort_order,m.id""",
        (user_id, user_id, user_id, track_id))
    fields = ("id", "title", "description", "cover_key", "sort_order", "question_count", "best_score", "attempted", "passed")
    modules = [dict(row) if hasattr(row, "keys") else dict(zip(fields, row)) for row in cur.fetchall()]
    previous_passed = True
    for module in modules:
        module["locked"] = not previous_passed
        previous_passed = bool(module["passed"])
    return modules


def _require_unlocked_module(cur: Any, module_id: int, user_id: int) -> None:
    cur.execute("""SELECT m.track_id,t.is_published FROM speaking_learning_modules m
        JOIN speaking_learning_tracks t ON t.id=m.track_id WHERE m.id=%s""", (module_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Speaking learning module not found")
    track_id, published = (row["track_id"], row["is_published"]) if hasattr(row, "keys") else row
    if not published:
        raise HTTPException(404, "Speaking learning module not found")
    modules = _module_progress(cur, track_id, user_id)
    module = next((item for item in modules if item["id"] == module_id), None)
    if module is None:
        raise HTTPException(404, "Speaking learning module not found")
    if module["locked"]:
        raise HTTPException(403, "Complete the previous module first")


@router.get("/speaking/learning/tracks/{track_id}/modules")
def public_modules(track_id: int, authorization: str | None = Header(default=None)):
    user = _user(authorization); ensure_tables()
    conn=get_conn(); cur=conn.cursor()
    try:
        cur.execute("SELECT 1 FROM speaking_learning_tracks WHERE id=%s AND is_published=TRUE", (track_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Speaking learning track not found")
        return {"items": _module_progress(cur, track_id, int(user.get("id") or 0))}
    finally: cur.close(); conn.close()


@router.get("/speaking/learning/modules/{module_id}/questions")
def public_questions(module_id: int, authorization: str | None = Header(default=None)):
    user = _user(authorization); ensure_tables()
    conn=get_conn(); cur=conn.cursor()
    try:
        _require_unlocked_module(cur, module_id, int(user.get("id") or 0))
        cur.execute("""SELECT q.id,q.prompt,q.question_type,q.options_json,q.data_json,q.sort_order FROM speaking_learning_questions q
            JOIN speaking_learning_modules m ON m.id=q.module_id JOIN speaking_learning_tracks t ON t.id=m.track_id
            WHERE q.module_id=%s AND t.is_published=TRUE
            ORDER BY q.sort_order,q.id""", (module_id,))
        rows=cur.fetchall(); items=[]
        for row in rows:
            d=_decode_question(row, ("id", "prompt", "question_type", "options_json", "data_json", "sort_order"))
            # Answer keys must never be sent before an attempt is submitted.
            d["data"] = _public_data(d.get("data", {}))
            items.append(d)
        return {"items": items}
    finally: cur.close(); conn.close()


@router.post("/speaking/learning/upload-audio")
async def upload_learning_audio(file: UploadFile = File(...), authorization: str | None = Header(default=None)):
    user = _user(authorization)
    filename = Path(file.filename or "").name
    if Path(filename).suffix.lower() != ".m4a":
        raise HTTPException(422, "Upload an M4A audio recording")
    raw = await file.read(10 * 1024 * 1024 + 1)
    if not raw:
        raise HTTPException(400, "The audio recording is empty")
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, "Audio recordings are limited to 10 MB")
    # record's AAC-LC/M4A output is an ISO-BMFF file with an ftyp box.
    if len(raw) < 12 or raw[4:8] != b"ftyp":
        raise HTTPException(422, "The uploaded file is not a valid M4A recording")
    from backend.main import HOMEWORK_UPLOAD_DIR

    upload_dir = Path(HOMEWORK_UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = (
        f"speaking_lp_voice_{int(user.get('id') or 0)}_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(6)}.m4a"
    )
    (upload_dir / stored_name).write_bytes(raw)
    return {"url": f"/homework/voices/{stored_name}"}


@router.post("/speaking/learning/modules/{module_id}/check")
async def check_module_answer(module_id: int, payload: CheckAnswerInput, authorization: str | None = Header(default=None), x_language: str | None = Header(default=None, alias="X-Language")):
    user = _user(authorization); ensure_tables(); user_id = int(user.get("id") or 0)
    conn = get_conn(); cur = conn.cursor()
    try:
        _require_unlocked_module(cur, module_id, user_id)
        cur.execute("""SELECT q.question_type,q.answer_json,q.data_json,q.explanation,t.subject,q.prompt
            FROM speaking_learning_questions q
            JOIN speaking_learning_modules m ON m.id=q.module_id
            JOIN speaking_learning_tracks t ON t.id=m.track_id
            WHERE q.id=%s AND q.module_id=%s""", (payload.question_id, module_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Speaking learning question not found")
        kind, answer_json, data_json, explanation, subject, prompt = (row["question_type"], row["answer_json"], row["data_json"], row["explanation"], row["subject"], row["prompt"]) if hasattr(row, "keys") else row
        expected = json.loads(answer_json or "null")
        data = json.loads(data_json or "{}")
        subject = str(subject or "English")
    finally:
        cur.close(); conn.close()
    answer_payload = payload.answer
    audio_url = str(answer_payload.get("audio_url") or "") if isinstance(answer_payload, dict) else ""
    if audio_url:
        _owned_audio_path(audio_url, user_id)
    if kind in AI_CHECKED_TYPES:
        from backend.library_ai import AiTestAnswerRequest, _check_with_ai
        reference = expected if isinstance(expected, str) else json.dumps(expected, ensure_ascii=False)
        accepted = data.get("accepted_answers", [])
        ai_question = {
            "kind": kind,
            "prompt": prompt,
            "instruction": data.get("instruction") or "",
            "question": prompt,
            "passage": data.get("passage") or "",
            "reference_answer": reference,
            "accepted_answers": accepted if isinstance(accepted, list) else [accepted],
            "target_level": data.get("target_level") or data.get("level"),
            "translation": data.get("translation"),
            "meaning": data.get("meaning"),
            "word": data.get("word") or data.get("target_word"),
        }
        answer_text = answer_payload.get("text") if isinstance(answer_payload, dict) else answer_payload
        if answer_text is not None and not isinstance(answer_text, str):
            answer_text = json.dumps(answer_text, ensure_ascii=False)
        verdict, feedback = await _check_with_ai(
            ai_question,
            AiTestAnswerRequest(question_index=0, answer_text=answer_text, audio_url=audio_url or None),
            subject,
            x_language or "en",
        )
        matched = verdict == "correct"
        result = {
            "correct": matched,
            "correct_count": int(matched),
            "total": 1,
            "correct_answer": expected,
            "explanation": explanation,
            "feedback": feedback.get("feedback"),
            "corrected": feedback.get("corrected"),
            "transcript": feedback.get("transcript"),
            "score": feedback.get("score"),
        }
    else:
        item_correct, item_total = _grade(kind, expected, answer_payload, data)
        result = {
            "correct": item_total > 0 and item_correct == item_total,
            "correct_count": item_correct,
            "total": item_total,
            "correct_answer": expected,
            "explanation": explanation,
        }
    conn = get_conn(); cur = conn.cursor()
    try:
        _save_answer_check(cur, user_id, module_id, payload.question_id, answer_payload, result)
        conn.commit()
    finally:
        cur.close(); conn.close()
    return result


@router.post("/speaking/learning/modules/{module_id}/submit")
def submit_module(module_id: int, payload: SubmitInput, authorization: str | None = Header(default=None)):
    user=_user(authorization); ensure_tables(); user_id=int(user.get("id") or 0); conn=get_conn(); cur=conn.cursor()
    try:
        _require_unlocked_module(cur, module_id, int(user.get("id") or 0))
        cur.execute("""SELECT q.id,q.question_type,q.answer_json,q.data_json,q.explanation FROM speaking_learning_questions q
            JOIN speaking_learning_modules m ON m.id=q.module_id JOIN speaking_learning_tracks t ON t.id=m.track_id
            WHERE q.module_id=%s AND t.is_published=TRUE
            ORDER BY q.sort_order,q.id""", (module_id,))
        rows=cur.fetchall()
        if not rows: raise HTTPException(404,"Speaking learning module not found")
        cur.execute("SELECT question_id,answer_hash,result_json FROM speaking_learning_answer_checks WHERE user_id=%s AND module_id=%s", (user_id,module_id))
        check_rows = cur.fetchall()
        verified_checks = {}
        for check_row in check_rows:
            qid, answer_hash, result_json = (check_row["question_id"],check_row["answer_hash"],check_row["result_json"]) if hasattr(check_row,"keys") else check_row
            try: verified_checks[int(qid)] = (str(answer_hash),json.loads(result_json or "{}"))
            except (TypeError,ValueError,json.JSONDecodeError): continue
        correct=0; gradable=0
        results=[]
        for row in rows:
            qid,kind,answer_json,data_json,explanation = (row["id"],row["question_type"],row["answer_json"],row["data_json"],row["explanation"]) if hasattr(row,"keys") else row
            answer=json.loads(answer_json or "null")
            data=json.loads(data_json or "{}")
            given=payload.answers.get(str(qid))
            if isinstance(given, dict) and given.get("audio_url"):
                _owned_audio_path(str(given["audio_url"]), user_id)
            saved_check = verified_checks.get(int(qid))
            item_correct, item_total = _grade_submission(kind, answer, given, data, saved_check)
            correct += item_correct; gradable += item_total
            results.append({"question_id": qid, "correct": item_total > 0 and item_correct == item_total, "correct_count": item_correct, "total": item_total, "correct_answer": answer, "explanation": explanation})
        score=round(correct*100/gradable) if gradable else 0
        passed=score>=70
        cur.execute("INSERT INTO speaking_learning_attempts(user_id,module_id,score,answers_json,passed) VALUES(%s,%s,%s,%s,%s)", (int(user.get("id") or 0),module_id,score,json.dumps(payload.answers,ensure_ascii=False),passed))
        conn.commit(); return {"score":score,"passed":passed,"correct":correct,"total":gradable,"results":results}
    finally: cur.close(); conn.close()
