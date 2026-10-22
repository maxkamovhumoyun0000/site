from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_diamondvoy_modes_route_to_real_tools_and_memory_is_user_scoped() -> None:
    backend = (ROOT / "backend/main.py").read_text(encoding="utf-8")
    generator = (ROOT / "ai_generator.py").read_text(encoding="utf-8")
    web = (ROOT / "app/ui/universal-chat.tsx").read_text(encoding="utf-8")

    assert 'pattern="^(auto|standard|study|web_search|deep_research)$"' in backend
    assert '_xai_generate_text_with_web_search(' in backend
    assert 'deep_research=mode == "deep_research"' in backend
    assert '"tools": [{"type": "web_search"}]' in generator
    assert '"store": False' in generator
    assert "mode: selectedMode" in web
    assert '@app.get("/chats/diamondvoy/memory")' in backend
    assert '@app.delete("/chats/diamondvoy/memory")' in backend
    assert 'DELETE FROM diamondvoy_memory WHERE user_id=?' in backend


def test_diamondvoy_auto_mode_and_chat_history_survive_reentry() -> None:
    backend = (ROOT / "backend/main.py").read_text(encoding="utf-8")

    assert 'mode: str = Field(default="auto"' in backend
    assert "def _diamondvoy_resolve_mode(requested_mode: str, user_text: str) -> str:" in backend
    assert 'mode = _diamondvoy_resolve_mode(payload.mode, user_text)' in backend
    assert 'ORDER BY COALESCE(c.updated_at, c.created_at) DESC, c.id DESC LIMIT ?' in backend
    fresh_session = backend.split("def _diamondvoy_start_fresh_session_final", 1)[1].split("\ndef ", 1)[0]
    assert "deleted_at=CURRENT_TIMESTAMP" not in fresh_session

    stream = backend.split("async def _diamondvoy_stream_events", 1)[1].split("\n@app.", 1)[0]
    assert "Generation is intentionally independent of this HTTP stream." in stream
    assert "cancel_event.set()" not in stream


def test_speaking_diamondvoy_does_not_substitute_fake_answers_on_api_errors() -> None:
    speaking = ROOT.parent / "Diamond Speaking Questions"
    page = (speaking / "lib/features/speaking_chats_page.dart").read_text(encoding="utf-8")
    assert "_createRichFallbackResponse" not in page
    assert "Cambridge English (https://cambridgeenglish.org)" not in page

