from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_speaking_learning_has_isolated_storage_and_namespaced_routes():
    source = (ROOT / "backend" / "speaking_learning.py").read_text()
    assert "speaking_learning_tracks" in source
    assert "speaking_learning_modules" in source
    assert "speaking_learning_questions" in source
    # Caddy strips /api before forwarding to FastAPI.
    assert '"/speaking/learning/tracks"' in source
    assert '"/api/speaking/learning/tracks"' not in source
    assert '"/staff/speaking-learning/tracks"' in source
    assert "learning_tracks" not in source.replace("speaking_learning_tracks", "")


def test_speaking_learning_is_test_only_and_requires_progression():
    source = (ROOT / "backend" / "speaking_learning.py").read_text()
    admin = (ROOT / "app" / "ui" / "speaking-learning-paths.tsx").read_text()
    assert '"word_order", "matching", "translation", "spelling"' in source
    assert "data_json" in source
    assert '"/speaking/learning/modules/{module_id}/check"' in source
    assert '"/speaking/learning/upload-audio"' in source
    assert '"/speaking/learning/tracks/{track_id}/final-exam"' in source
    assert "speaking_learning_final_attempts" in source
    assert "_require_unlocked_module" in source
    assert "speaking_learning_attempts" in source
    assert "speaking_learning_answer_checks" in source
    assert "speaking_prompt" not in admin
    assert "speaking_learning_tracks" in source


def test_speaking_admin_gets_a_distinct_learning_management_page():
    navigation = (ROOT / "app" / "ui" / "navigation-config.ts").read_text()
    page = (ROOT / "app" / "page.tsx").read_text()
    assert '"speaking-learning-paths"' in navigation
    assert "SpeakingLearningPaths" in page


def test_speaking_flutter_exposes_learning_path_from_sidebar():
    app = ROOT.parent / "Diamond Speaking Questions"
    sidebar = (app / "lib" / "core" / "widgets" / "app_sidebar.dart").read_text()
    assert "onOpenLearningPath" in sidebar
    assert "SpeakingLearningPathsPage" in "\n".join(
        path.read_text() for path in (app / "lib").rglob("*.dart")
        if path.stat().st_size < 500_000
    )
