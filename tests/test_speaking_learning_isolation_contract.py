"""The Speaking app has its own Learning Path, isolated from the student one.

Design: backend/personalization.py mounts every Learning Path route a second
time under /speaking-lp; those copies run in the "speaking" namespace, which
rewrites the Learning Path tables to speaking_lp_* copies.  The website's
Speaking admin manages it with the same StaffLearningPaths UI (scope
"speaking").  The legacy backend/speaking_learning.py routes stay for already
installed Speaking app versions and keep their own speaking_learning_* tables.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_legacy_speaking_learning_keeps_isolated_storage_and_routes():
    source = _read("backend/speaking_learning.py")
    assert "speaking_learning_tracks" in source
    assert "speaking_learning_modules" in source
    assert "speaking_learning_questions" in source
    # Caddy strips /api before forwarding to FastAPI.
    assert '"/speaking/learning/tracks"' in source
    assert '"/api/speaking/learning/tracks"' not in source
    assert '"/staff/speaking-learning/tracks"' in source
    assert "learning_tracks" not in source.replace("speaking_learning_tracks", "")
    assert '"/speaking/learning/modules/{module_id}/check"' in source
    assert '"/speaking/learning/upload-audio"' in source
    assert '"/speaking/learning/tracks/{track_id}/final-exam"' in source
    assert "_require_unlocked_module" in source
    assert "speaking_learning_answer_checks" in source


def test_speaking_learning_path_namespace_uses_isolated_tables():
    source = _read("backend/personalization.py")
    assert 'SPEAKING_LP_TABLE_PREFIX = "speaking_lp_"' in source
    for table in (
        "learning_tracks", "learning_modules", "learning_module_topics", "learning_module_lessons",
        "learning_track_assignments", "learning_lesson_attempts", "learning_module_progress",
        "learning_certificate_shares", "learning_track_final_progress", "learning_track_final_attempts",
        "learning_answer_checks",
    ):
        assert f'"{table}",' in source.split("LEARNING_PATH_TABLES = (", 1)[1].split(")", 1)[0], table
    # Shared tables are never renamed.
    tables = source.split("LEARNING_PATH_TABLES = (", 1)[1].split(")", 1)[0]
    for shared in ("users", "certificates", "diamond_history", "library_nodes"):
        assert f'"{shared}"' not in tables
    # The namespace has its own schema flag and creates only the LP tables.
    body = source.split("def _ensure_speaking_lp_schema(", 1)[1].split("\ndef ", 1)[0]
    assert "_speaking_lp_schema_ready" in body and "_LEARNING_PATH_TABLE_DDL" in body
    assert "_migrate_legacy_speaking_learning_paths()" in body


def test_legacy_speaking_content_is_migrated_once():
    source = _read("backend/personalization.py")
    body = source.split("def _migrate_legacy_speaking_learning_paths(", 1)[1].split("\ndef ", 1)[0]
    assert "pg_advisory_xact_lock" in body
    assert "speaking_lp_schema_migrations" in body
    assert "SELECT COUNT(*) AS n FROM speaking_lp_learning_tracks" in body
    for legacy in ("speaking_learning_tracks", "speaking_learning_modules", "speaking_learning_questions"):
        assert legacy in body
    assert '"published" if published else "draft"' in body


def test_speaking_admin_manages_it_with_the_student_learning_path_ui():
    navigation = _read("app/ui/navigation-config.ts")
    page = _read("app/page.tsx")
    assert '"speaking-learning-paths"' in navigation
    assert "SpeakingLearningPaths" not in page
    assert 'scope="speaking"' in page and "speakingLearningPathFetch(authedApiFetch)" in page
    assert not (ROOT / "app" / "ui" / "speaking-learning-paths.tsx").exists()
    ui = _read("app/ui/learning-paths.tsx")
    assert 'fetch("/api/speaking-lp/staff/upload"' in ui


def test_speaking_flutter_exposes_learning_path_from_sidebar():
    app = ROOT.parent / "Diamond Speaking Questions"
    if not (app / "lib").exists():
        return  # The Speaking Flutter app is a separate checkout.
    dart = "\n".join(
        path.read_text() for path in (app / "lib").rglob("*.dart")
        if path.stat().st_size < 500_000
    )
    # The app shell (core/navigation/speaking_app_shell.dart) opens the
    # Learning Path ported from the Student app, which talks to the isolated
    # /speaking-lp namespace and sends raw answers (the server grades).
    shell = (app / "lib" / "core" / "navigation" / "speaking_app_shell.dart").read_text()
    assert "LearningPathsScreen" in shell
    assert "SpeakingLearningPathsPage" not in dart, "the old Speaking Learning Path page is back"
    service = (app / "lib" / "features" / "learning_paths" / "data" / "learning_paths_service.dart").read_text()
    assert "/api/speaking-lp/student" in service
    assert "'score'" not in service, "the client must never send its own score"
    assert "'exam_key'" in service and "'answers'" in service


if __name__ == "__main__":
    import sys
    import traceback

    failures = 0
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        try:
            fn()
        except Exception:  # noqa: BLE001
            failures += 1
            print(f"FAIL {name}")
            traceback.print_exc()
        else:
            print(f"ok   {name}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
