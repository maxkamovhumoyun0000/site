from __future__ import annotations

import pytest

import backend.main as api


def _student_user(user_id: int = 11) -> dict:
    return {"id": user_id, "login_type": 1, "login_id": f"STU{user_id}", "language": "uz", "access_enabled": 1, "blocked": 0}


@pytest.mark.asyncio
async def test_student_diamondvoy_chats_returns_items_without_cleanup_field(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _student_user())
    monkeypatch.setattr(
        api,
        "list_diamondvoy_chats_for_user",
        lambda _uid, limit=100: [
            {
                "id": 7,
                "title": "Grammar help",
                "created_at": "2026-04-25T10:00:00+00:00",
                "updated_at": "2026-04-26T11:00:00+00:00",
                "last_message_preview": "Past simple haqida aytib bering",
            }
        ],
    )

    payload = await api.student_diamondvoy_chats(authorization="Bearer test")

    assert "items" in payload
    assert "cleanup_removed" not in payload
    assert payload["items"][0]["id"] == 7


@pytest.mark.asyncio
async def test_student_diamondvoy_messages_endpoint_returns_items(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _student_user())
    monkeypatch.setattr(api, "get_diamondvoy_chat", lambda _chat_id: {"id": 5, "user_id": 11, "title": "Chat"})
    monkeypatch.setattr(
        api,
        "list_diamondvoy_chat_messages",
        lambda _chat_id, limit=800: [
            {"id": 1, "chat_id": 5, "role": "user", "content": "Hello", "created_at": "2026-04-26T08:00:00+00:00"},
            {"id": 2, "chat_id": 5, "role": "assistant", "content": "Hi!", "created_at": "2026-04-26T08:00:01+00:00"},
        ],
    )

    payload = await api.student_diamondvoy_chat_messages(5, authorization="Bearer test")

    assert payload["chat"]["id"] == 5
    assert len(payload["items"]) == 2
    assert payload["items"][1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_student_diamondvoy_stream_emits_status_and_done_for_info_shortcut(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _student_user())
    monkeypatch.setattr(api, "get_diamondvoy_chat", lambda _chat_id: {"id": 5, "user_id": 11, "title": None})
    monkeypatch.setattr(api, "update_diamondvoy_chat_title", lambda _chat_id, _title: None)
    monkeypatch.setattr(api, "list_diamondvoy_chat_messages", lambda _chat_id, limit=200: [])
    monkeypatch.setattr(
        api,
        "add_diamondvoy_chat_message",
        lambda _chat_id, _role, content: {"id": 1, "chat_id": 5, "role": _role, "content": content, "created_at": "2026-04-26T08:00:00+00:00"},
    )
    monkeypatch.setattr(api, "default_subjects_for_diamondvoy", lambda _user: ["English"])
    monkeypatch.setattr(api, "detect_query_language", lambda _text, fallback="uz": fallback)
    monkeypatch.setattr(api, "try_diamondvoy_bot_info", lambda *args, **kwargs: "Bot statistikasi")
    logged: list[dict] = []
    monkeypatch.setattr(
        api,
        "log_diamondvoy_query",
        lambda user_id, query, response, subject=None, bot_scope=None: logged.append(
            {"user_id": user_id, "query": query, "response": response, "subject": subject, "bot_scope": bot_scope}
        ),
    )

    resp = await api.student_diamondvoy_send_stream(
        5,
        api.DiamondvoySendMessageRequest(message="Mening statistikam"),
        authorization="Bearer test",
    )

    chunks: list[str] = []
    async for item in resp.body_iterator:
        chunks.append(item.decode("utf-8") if isinstance(item, (bytes, bytearray)) else str(item))
    stream_text = "".join(chunks)

    assert "event: status" in stream_text
    assert "event: delta" in stream_text
    assert "event: done" in stream_text
    assert logged and logged[0]["bot_scope"] == "student_web"


@pytest.mark.asyncio
async def test_student_diamondvoy_stream_subject_gate_finishes_with_done(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _student_user())
    monkeypatch.setattr(api, "get_diamondvoy_chat", lambda _chat_id: {"id": 8, "user_id": 11, "title": "Chat"})
    monkeypatch.setattr(api, "list_diamondvoy_chat_messages", lambda _chat_id, limit=200: [])
    monkeypatch.setattr(
        api,
        "add_diamondvoy_chat_message",
        lambda _chat_id, _role, content: {"id": 1, "chat_id": 8, "role": _role, "content": content, "created_at": "2026-04-26T08:00:00+00:00"},
    )
    monkeypatch.setattr(api, "default_subjects_for_diamondvoy", lambda _user: ["English"])
    monkeypatch.setattr(api, "detect_query_language", lambda _text, fallback="uz": fallback)
    monkeypatch.setattr(api, "try_diamondvoy_bot_info", lambda *args, **kwargs: None)

    async def _not_related(*_args, **_kwargs):
        return False

    monkeypatch.setattr(api, "diamondvoy_is_subject_related", _not_related)

    resp = await api.student_diamondvoy_send_stream(
        8,
        api.DiamondvoySendMessageRequest(message="Bugun ob-havo qanday"),
        authorization="Bearer test",
    )

    chunks: list[str] = []
    async for item in resp.body_iterator:
        chunks.append(item.decode("utf-8") if isinstance(item, (bytes, bytearray)) else str(item))
    stream_text = "".join(chunks)

    assert "event: done" in stream_text
    assert "event: error" not in stream_text
