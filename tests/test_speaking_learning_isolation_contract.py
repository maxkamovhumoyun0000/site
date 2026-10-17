from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_speaking_learning_has_isolated_storage_and_namespaced_routes():
    source = (ROOT / "backend" / "speaking_learning.py").read_text()
    assert "speaking_learning_tracks" in source
    assert "speaking_learning_modules" in source
    assert "speaking_learning_questions" in source
    assert '"/api/speaking/learning/tracks"' in source
    assert '"/staff/speaking-learning/tracks"' in source
    assert "learning_tracks" not in source.replace("speaking_learning_tracks", "")


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
