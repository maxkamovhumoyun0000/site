from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_diamondvoy_modes_route_to_real_tools_and_memory_is_user_scoped() -> None:
    backend = (ROOT / "backend/main.py").read_text(encoding="utf-8")
    generator = (ROOT / "ai_generator.py").read_text(encoding="utf-8")
    web = (ROOT / "app/ui/universal-chat.tsx").read_text(encoding="utf-8")

    assert 'pattern="^(standard|study|web_search|deep_research)$"' in backend
    assert '_xai_generate_text_with_web_search(' in backend
    assert 'deep_research=mode == "deep_research"' in backend
    assert '"tools": [{"type": "web_search"}]' in generator
    assert '"store": False' in generator
    assert "mode: selectedMode" in web
    assert '@app.get("/chats/diamondvoy/memory")' in backend
    assert '@app.delete("/chats/diamondvoy/memory")' in backend
    assert 'DELETE FROM diamondvoy_memory WHERE user_id=?' in backend


def test_speaking_diamondvoy_does_not_substitute_fake_answers_on_api_errors() -> None:
    speaking = ROOT.parent / "Diamond Speaking Questions"
    page = (speaking / "lib/features/speaking_chats_page.dart").read_text(encoding="utf-8")
    assert "_createRichFallbackResponse" not in page
    assert "Cambridge English (https://cambridgeenglish.org)" not in page

