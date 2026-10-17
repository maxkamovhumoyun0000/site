"""Speaking-only Learning Path API. Data is intentionally isolated from student learning tables."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from db import get_conn

router = APIRouter()
STAFF_ROLES = {"speaking_admin", "admin", "superadmin", "developer"}


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
            title TEXT NOT NULL, description TEXT DEFAULT '', sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS speaking_learning_questions (
            id BIGSERIAL PRIMARY KEY, module_id BIGINT NOT NULL REFERENCES speaking_learning_modules(id) ON DELETE CASCADE,
            prompt TEXT NOT NULL, question_type TEXT NOT NULL DEFAULT 'multiple_choice', options_json TEXT DEFAULT '[]',
            answer_json TEXT DEFAULT 'null', explanation TEXT DEFAULT '', sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS speaking_learning_attempts (
            id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, module_id BIGINT NOT NULL REFERENCES speaking_learning_modules(id) ON DELETE CASCADE,
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


class QuestionInput(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    question_type: str = Field(default="multiple_choice", pattern="^(multiple_choice|true_false|short_answer|speaking_prompt)$")
    options: list[Any] = Field(default_factory=list, max_length=20)
    answer: Any = None
    explanation: str = Field(default="", max_length=2000)


class SubmitInput(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


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


@router.post("/staff/speaking-learning/tracks/{track_id}/publish")
def publish_track(track_id: int, payload: dict[str, bool], authorization: str | None = Header(default=None)):
    _user(authorization, staff=True); ensure_tables()
    conn = get_conn(); cur = conn.cursor()
    try:
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
        cur.execute("SELECT id,title,description,sort_order FROM speaking_learning_modules WHERE track_id=%s ORDER BY sort_order,id", (track_id,))
        return {"items": [dict(row) if hasattr(row, "keys") else {"id": row[0], "title": row[1], "description": row[2], "sort_order": row[3]} for row in cur.fetchall()]}
    finally:
        cur.close(); conn.close()


@router.post("/staff/speaking-learning/tracks/{track_id}/modules")
def create_module(track_id: int, payload: ModuleInput, authorization: str | None = Header(default=None)):
    _user(authorization, staff=True); ensure_tables()
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO speaking_learning_modules(track_id,title,description) SELECT id,%s,%s FROM speaking_learning_tracks WHERE id=%s RETURNING id", (payload.title.strip(), payload.description, track_id))
        row = cur.fetchone()
        if not row: raise HTTPException(404, "Speaking learning track not found")
        conn.commit(); return {"id": row[0], "title": payload.title.strip()}
    finally:
        cur.close(); conn.close()


@router.delete("/staff/speaking-learning/modules/{module_id}")
def delete_module(module_id: int, authorization: str | None = Header(default=None)):
    _user(authorization, staff=True); ensure_tables(); conn=get_conn(); cur=conn.cursor()
    try:
        cur.execute("DELETE FROM speaking_learning_modules WHERE id=%s RETURNING id", (module_id,))
        if not cur.fetchone(): raise HTTPException(404, "Speaking learning module not found")
        conn.commit(); return {"ok": True}
    finally: cur.close(); conn.close()


@router.get("/staff/speaking-learning/modules/{module_id}/questions")
def staff_questions(module_id: int, authorization: str | None = Header(default=None)):
    _user(authorization, staff=True); ensure_tables()
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT id,prompt,question_type,options_json,answer_json,explanation,sort_order FROM speaking_learning_questions WHERE module_id=%s ORDER BY sort_order,id", (module_id,))
        rows = cur.fetchall()
        items=[]
        for row in rows:
            d = dict(row) if hasattr(row, "keys") else dict(zip(("id","prompt","question_type","options_json","answer_json","explanation","sort_order"), row))
            d["options"] = json.loads(d.pop("options_json") or "[]")
            d["answer"] = json.loads(d.pop("answer_json") or "null")
            items.append(d)
        return {"items": items}
    finally:
        cur.close(); conn.close()


@router.post("/staff/speaking-learning/modules/{module_id}/questions")
def create_question(module_id: int, payload: QuestionInput, authorization: str | None = Header(default=None)):
    _user(authorization, staff=True); ensure_tables()
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO speaking_learning_questions(module_id,prompt,question_type,options_json,answer_json,explanation) SELECT id,%s,%s,%s,%s,%s FROM speaking_learning_modules WHERE id=%s RETURNING id", (payload.prompt.strip(), payload.question_type, json.dumps(payload.options, ensure_ascii=False), json.dumps(payload.answer, ensure_ascii=False), payload.explanation, module_id))
        row=cur.fetchone()
        if not row: raise HTTPException(404, "Speaking learning module not found")
        conn.commit(); return {"id": row[0]}
    finally:
        cur.close(); conn.close()


@router.delete("/staff/speaking-learning/questions/{question_id}")
def delete_question(question_id: int, authorization: str | None = Header(default=None)):
    _user(authorization, staff=True); ensure_tables(); conn=get_conn(); cur=conn.cursor()
    try:
        cur.execute("DELETE FROM speaking_learning_questions WHERE id=%s RETURNING id", (question_id,))
        if not cur.fetchone(): raise HTTPException(404, "Speaking learning question not found")
        conn.commit(); return {"ok": True}
    finally: cur.close(); conn.close()


@router.get("/api/speaking/learning/tracks")
def public_tracks(authorization: str | None = Header(default=None)):
    _user(authorization); ensure_tables()
    conn=get_conn(); cur=conn.cursor()
    try:
        cur.execute("SELECT id,title,description,subject FROM speaking_learning_tracks WHERE is_published=TRUE ORDER BY sort_order,id")
        rows=cur.fetchall()
        return {"items": [dict(row) if hasattr(row,"keys") else dict(zip(("id","title","description","subject"),row)) for row in rows]}
    finally: cur.close(); conn.close()


@router.get("/api/speaking/learning/tracks/{track_id}/modules")
def public_modules(track_id: int, authorization: str | None = Header(default=None)):
    _user(authorization); ensure_tables()
    conn=get_conn(); cur=conn.cursor()
    try:
        cur.execute("SELECT id,title,description,sort_order FROM speaking_learning_modules WHERE track_id=%s AND EXISTS(SELECT 1 FROM speaking_learning_tracks WHERE id=%s AND is_published=TRUE) ORDER BY sort_order,id", (track_id,track_id))
        return {"items": [dict(row) if hasattr(row,"keys") else dict(zip(("id","title","description","sort_order"),row)) for row in cur.fetchall()]}
    finally: cur.close(); conn.close()


@router.get("/api/speaking/learning/modules/{module_id}/questions")
def public_questions(module_id: int, authorization: str | None = Header(default=None)):
    _user(authorization); ensure_tables()
    conn=get_conn(); cur=conn.cursor()
    try:
        cur.execute("""SELECT q.id,q.prompt,q.question_type,q.options_json,q.sort_order FROM speaking_learning_questions q
            JOIN speaking_learning_modules m ON m.id=q.module_id JOIN speaking_learning_tracks t ON t.id=m.track_id
            WHERE q.module_id=%s AND t.is_published=TRUE ORDER BY q.sort_order,q.id""", (module_id,))
        rows=cur.fetchall(); items=[]
        for row in rows:
            d=dict(row) if hasattr(row,"keys") else dict(zip(("id","prompt","question_type","options_json","sort_order"),row))
            d["options"]=json.loads(d.pop("options_json") or "[]"); items.append(d)
        return {"items": items}
    finally: cur.close(); conn.close()


@router.post("/api/speaking/learning/modules/{module_id}/submit")
def submit_module(module_id: int, payload: SubmitInput, authorization: str | None = Header(default=None)):
    user=_user(authorization); ensure_tables(); conn=get_conn(); cur=conn.cursor()
    try:
        cur.execute("""SELECT q.id,q.question_type,q.answer_json FROM speaking_learning_questions q
            JOIN speaking_learning_modules m ON m.id=q.module_id JOIN speaking_learning_tracks t ON t.id=m.track_id
            WHERE q.module_id=%s AND t.is_published=TRUE ORDER BY q.sort_order,q.id""", (module_id,))
        rows=cur.fetchall()
        if not rows: raise HTTPException(404,"Speaking learning module not found")
        correct=0
        for row in rows:
            qid,kind,answer_json = (row["id"],row["question_type"],row["answer_json"]) if hasattr(row,"keys") else row
            answer=json.loads(answer_json or "null")
            given=payload.answers.get(str(qid))
            if kind == "speaking_prompt": continue
            if isinstance(answer, bool):
                matched = given is answer or str(given).strip().casefold() == str(answer).casefold()
            else:
                matched = str(given if given is not None else "").strip().casefold() == str(answer if answer is not None else "").strip().casefold()
            if matched: correct+=1
        gradable=sum(1 for row in rows if (row["question_type"] if hasattr(row,"keys") else row[1]) != "speaking_prompt")
        score=round(correct*100/gradable) if gradable else 0
        passed=score>=70 or gradable==0
        cur.execute("INSERT INTO speaking_learning_attempts(user_id,module_id,score,answers_json,passed) VALUES(%s,%s,%s,%s,%s)", (int(user.get("id") or 0),module_id,score,json.dumps(payload.answers,ensure_ascii=False),passed))
        conn.commit(); return {"score":score,"passed":passed,"correct":correct,"total":gradable}
    finally: cur.close(); conn.close()
