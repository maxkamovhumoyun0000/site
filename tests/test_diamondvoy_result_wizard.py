from __future__ import annotations

import io
import sqlite3

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

import backend.main as api


@pytest.fixture
def wizard_env(monkeypatch, tmp_path):
    db_path = tmp_path / "test.sqlite"
    def connection():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    with connection() as conn:
        conn.execute("CREATE TABLE diamondvoy_chats(id INTEGER PRIMARY KEY, user_id INTEGER, expires_at TIMESTAMP)")
        conn.execute("INSERT INTO diamondvoy_chats(id, user_id) VALUES (10, 7)")
        conn.execute("""CREATE TABLE web_results (
            id INTEGER PRIMARY KEY, student_name TEXT, result_type TEXT, subject TEXT,
            score_text TEXT, level_text TEXT, description TEXT, image_url TEXT, media_json TEXT,
            status TEXT, created_by INTEGER, updated_at TIMESTAMP
        )""")
    monkeypatch.setattr(api, "get_conn", connection)
    monkeypatch.setattr(api, "RESULT_UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(api, "_ensure_web_tables", lambda: None)
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _: {"id": 7, "login_type": 4, "login_id": "MEDIA-X-01"})
    monkeypatch.setattr(api, "_diamondvoy_get_chat_for_user_final", lambda chat, user: {"id": chat, "user_id": user})
    async def offline(*args, **kwargs):
        raise RuntimeError("AI unavailable")
    monkeypatch.setattr(api, "_xai_generate_text", offline)
    async def vision_offline(*args, **kwargs):
        raise RuntimeError("AI unavailable")
        yield ""
    monkeypatch.setattr(api, "_xai_generate_text_stream_with_images", vision_offline)
    return connection


@pytest.mark.asyncio
async def test_draft_resumes_webp_and_publish_is_idempotent(wizard_env):
    wizard_id = api._result_wizard_new(10, 7)
    image = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(image, "PNG")
    image.seek(0)
    uploaded = await api.result_wizard_image(10, wizard_id, UploadFile(file=image, filename="certificate.png"), "Bearer test")
    assert uploaded["state"]["step"] == "name"
    assert uploaded["state"]["image_url"].endswith(".webp")
    assert Image.open(api.RESULT_UPLOAD_DIR / uploaded["state"]["image_url"].split("/")[-1]).format == "WEBP"
    draft = api.ResultWizardDraft(step="certificate", student_name="Ali Karimov", result_type="Boshqa sertifikat", subject="Matematika", certificate_name="SAT", score_text="1450")
    await api.result_wizard_draft(10, wizard_id, draft, "Bearer test")
    restored = (await api.result_wizard_get(10, wizard_id, "Bearer test"))["state"]
    assert (restored["step"], restored["certificate_name"], restored["student_name"]) == ("certificate", "SAT", "Ali Karimov")
    payload = api.ResultWizardUpdate(student_name="Ali Karimov", result_type="Boshqa sertifikat", subject="Matematika", certificate_name="SAT", score_text="1450")
    first = await api.result_wizard_publish(10, wizard_id, payload, "Bearer test")
    second = await api.result_wizard_publish(10, wizard_id, payload, "Bearer test")
    assert first["state"]["result_id"] == second["state"]["result_id"]
    with wizard_env() as conn:
        rows = conn.execute("SELECT * FROM web_results").fetchall()
    assert len(rows) == 1
    assert rows[0]["level_text"] == "SAT" and rows[0]["status"] == "published"
    assert (await api.result_wizard_get(10, wizard_id, "Bearer test"))["state"]["step"] == "done"


@pytest.mark.asyncio
async def test_wizard_is_restricted_to_owner_and_admin(wizard_env, monkeypatch):
    wizard_id = api._result_wizard_new(10, 7)
    with pytest.raises(HTTPException) as exc:
        await api.result_wizard_get(11, wizard_id, "Bearer test")
    assert exc.value.status_code == 404
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _: {"id": 8, "login_type": 1})
    with pytest.raises(HTTPException) as exc:
        await api.result_wizard_get(10, wizard_id, "Bearer test")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_intent_uses_model_for_arbitrary_wording(monkeypatch):
    async def yes(*args, **kwargs):
        return "YES"
    monkeypatch.setattr(api, "_xai_generate_text", yes)
    assert await api._result_wizard_intent("Put her achievement on the website")
    async def no(*args, **kwargs):
        return "NO"
    monkeypatch.setattr(api, "_xai_generate_text", no)
    assert not await api._result_wizard_intent("How do certificates work?")
