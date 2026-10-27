"""Website <-> backend API contract tests.

Stdlib only: no FastAPI, database or network. They run with pytest or with
plain ``python3 tests/test_website_api_contracts.py``.

What is checked:
* every literal API path the website calls (in the Speaking admin, Learning
  Path, Arena/Duel, admin competitions and personal plan UIs) maps to a
  registered backend route;
* the Speaking admin workspace guard allows every path the Speaking admin
  UI calls and still blocks general admin APIs;
* Speaking content/broadcast routes are not open to teacher/support;
* admin competition history reads the runtime web_competition_* tables;
* frontend result handling uses server data instead of local fallbacks.
"""
from __future__ import annotations

import ast
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
APP = ROOT / "app"

# Next.js rewrites "/api/:path*" to the backend "/:path*" (next.config.ts).
API_PREFIX = "/api"

ROUTE_DECORATOR_RE = re.compile(r'@(?:app|router)\.(get|post|put|patch|delete)\(\s*"([^"]+)"')
# apiFetch / requestJson / authedApiFetch prepend API_BASE ("/api").
WRAPPED_CALL_RE = re.compile(
    r'\b(?:apiFetch|requestJson|authedApiFetch)(?:<[^>()]*>)?\(\s*(["`])(/[^"`]*)\1'
)
# Raw fetch("/api/...") calls carry the prefix themselves.
RAW_FETCH_RE = re.compile(r'\bfetch\(\s*(["`])(/api/[^"`]*)\1')
TEMPLATE_EXPR_RE = re.compile(r"\$\{[^{}]*\}")

SPEAKING_ADMIN_UI_FILES = (
    "app/ui/speaking-learning-paths.tsx",
    "app/ui/admin-speaking-topics.tsx",
    "app/ui/admin-speaking-notifications.tsx",
    "app/ui/admin-speaking-users.tsx",
    "app/ui/speaking-live-lessons.tsx",
    "app/ui/speaking-live-management.tsx",
    "app/ui/livekit-moderator-room.tsx",
)

WEBSITE_UI_FILES = SPEAKING_ADMIN_UI_FILES + (
    "app/ui/learning-paths.tsx",
    "app/ui/admin-competitions.tsx",
    "app/student/plan/page.tsx",
)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _backend_routes() -> list[tuple[str, str]]:
    routes: list[tuple[str, str]] = []
    for path in sorted(BACKEND.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        routes.extend((method.upper(), route) for method, route in ROUTE_DECORATOR_RE.findall(text))
    return routes


# A frontend template expression (${...}) becomes this marker; a segment that
# contains it may stand for any backend segment (an id or a literal action).
DYNAMIC = "{*}"

_ROUTES: list[list[str]] | None = None


def _route_matches(front: list[str], route: list[str]) -> bool:
    if route and route[-1].endswith(":path}"):
        if len(front) < len(route):
            return False
        front = front[: len(route) - 1] + ["/".join(front[len(route) - 1 :])]
    if len(front) != len(route):
        return False
    for f, r in zip(front, route):
        if DYNAMIC in f:
            continue
        if r.startswith("{") and r.endswith("}"):
            if not f:
                return False
            continue
        if f != r:
            return False
    return True


def _route_exists(path: str) -> bool:
    global _ROUTES
    if _ROUTES is None:
        _ROUTES = [route.rstrip("/").split("/") for _, route in _backend_routes()]
    front = path.split("/")
    return any(_route_matches(front, route) for route in _ROUTES)


def _normalize(path: str) -> str:
    clean = TEMPLATE_EXPR_RE.sub(DYNAMIC, path)
    clean = clean.split("?", 1)[0]
    return clean.rstrip("/") or "/"


def _frontend_backend_paths(relative: str) -> set[str]:
    """Backend paths (after the /api rewrite) that a UI file calls literally."""
    text = _read(relative)
    paths = {_normalize(match[1]) for match in WRAPPED_CALL_RE.findall(text)}
    for match in RAW_FETCH_RE.findall(text):
        paths.add(_normalize(match[1][len(API_PREFIX):]))
    return paths


def _load_main_symbols(names: set[str], extra_globals: dict[str, Any]) -> dict[str, Any]:
    """Execute only the selected top-level definitions of backend/main.py."""
    tree = ast.parse(_read("backend/main.py"))
    selected: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in names for target in node.targets
        ):
            selected.append(node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id in names:
            selected.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            selected.append(node)
    found = {
        getattr(node, "name", None)
        or next((t.id for t in getattr(node, "targets", []) if isinstance(t, ast.Name)), None)
        or getattr(getattr(node, "target", None), "id", None)
        for node in selected
    }
    missing = names - found
    assert not missing, f"backend/main.py is missing {sorted(missing)}"
    namespace: dict[str, Any] = dict(extra_globals)
    exec(compile(ast.Module(body=selected, type_ignores=[]), "backend/main.py", "exec"), namespace)
    return namespace


def _main_function_source(name: str) -> str:
    source = _read("backend/main.py")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            segment = ast.get_source_segment(source, node)
            assert segment
            return segment
    raise AssertionError(f"{name} not found in backend/main.py")


def _speaking_guard() -> Callable[[str], bool]:
    namespace = _load_main_symbols(
        {
            "_SPEAKING_ADMIN_WORKSPACE_PATHS",
            "_SPEAKING_ADMIN_WORKSPACE_PREFIXES",
            "_NOTIFICATION_READ_PATH_RE",
            "_speaking_admin_workspace_path_is_allowed",
        },
        {"re": re},
    )
    return namespace["_speaking_admin_workspace_path_is_allowed"]


# --------------------------------------------------------------------------
# Route existence
# --------------------------------------------------------------------------

def test_website_api_paths_map_to_backend_routes():
    missing: list[str] = []
    for relative in WEBSITE_UI_FILES:
        paths = _frontend_backend_paths(relative)
        assert paths, f"no API calls found in {relative}; extraction regex is stale"
        missing.extend(f"{relative}: {path}" for path in sorted(paths) if not _route_exists(path))
    assert not missing, "website calls routes the backend does not register:\n" + "\n".join(missing)


def test_arena_duel_runtime_paths_used_by_website_exist():
    # Question URLs are built into a variable first, so scan every literal.
    text = _read("app/student/test-views.tsx")
    paths = {_normalize(match[1]) for match in re.findall(r'(["`])(/competition/[^"`]*)\1', text)}
    for required in (
        "/competition/runtime/start",
        f"/competition/runtime/{DYNAMIC}/status",
        f"/competition/runtime/{DYNAMIC}/question",
        f"/competition/runtime/{DYNAMIC}/answer",
        f"/competition/runtime/{DYNAMIC}/result",
    ):
        assert required in paths, f"test-views.tsx no longer calls {required}"
    missing = sorted(path for path in paths if not _route_exists(path))
    assert not missing, f"Arena/Duel website paths without backend route: {missing}"


def test_admin_competitions_ui_routes_exist():
    paths = _frontend_backend_paths("app/ui/admin-competitions.tsx")
    assert "/admin/competitions/history" in paths
    assert f"/admin/competitions/{DYNAMIC}/results" in paths
    assert all(_route_exists(path) for path in paths)


# --------------------------------------------------------------------------
# Speaking admin workspace guard
# --------------------------------------------------------------------------

def test_speaking_admin_guard_allows_every_speaking_ui_path():
    allowed = _speaking_guard()
    blocked: list[str] = []
    for relative in SPEAKING_ADMIN_UI_FILES:
        blocked.extend(f"{relative}: {path}" for path in sorted(_frontend_backend_paths(relative)) if not allowed(path))
    assert not blocked, "Speaking admin UI paths rejected by the workspace guard:\n" + "\n".join(blocked)


def test_speaking_admin_guard_allows_dashboard_shell_paths():
    allowed = _speaking_guard()
    for path in (
        "/app/state",
        "/auth/login",
        "/auth/session/cookie",
        "/auth/me",
        "/auth/logout",
        "/auth/presence/heartbeat",
        "/user/account",
        "/user/language",
        "/notifications",
        "/notifications/unread-count",
        "/notifications/read-all",
        "/notifications/42/read",
        "/notifications/abc-123/read/",
        "/staff/speaking-learning/tracks",
        "/staff/speaking-learning/modules/7/questions",
    ):
        assert allowed(path), f"Speaking admin guard must allow {path}"


def test_speaking_admin_guard_still_blocks_general_admin_apis():
    allowed = _speaking_guard()
    for path in (
        "/admin/payments",
        "/admin/competitions/history",
        "/admin/system-metrics",
        "/staff/learning-tracks",
        "/student/learning-tracks",
        "/developer/deploy",
        "/notifications/42/read/extra",
        "/notifications/push-token/unregister/x",
        "/staff/speakingX/topics",
    ):
        assert not allowed(path), f"Speaking admin guard must block {path}"


def test_notification_read_routes_match_backend():
    assert _route_exists("/notifications/1/read")
    assert _route_exists("/notifications/read-all")
    assert not _route_exists("/definitely/not/a/route")


# --------------------------------------------------------------------------
# Speaking staff role scope
# --------------------------------------------------------------------------

def test_speaking_media_staff_roles_exclude_teacher_and_support():
    tree = ast.parse(_read("backend/speaking_admin.py"))
    roles: set[str] | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "MEDIA_STAFF_ROLES" for t in node.targets
        ):
            roles = set(ast.literal_eval(node.value))
    assert roles is not None, "MEDIA_STAFF_ROLES not found"
    assert "teacher" not in roles and "support" not in roles
    assert {"speaking_admin", "admin"} <= roles


def test_speaking_learning_staff_routes_require_speaking_staff():
    source = _read("backend/speaking_learning.py")
    match = re.search(r"^STAFF_ROLES\s*=\s*(\{[^}]*\})", source, re.M)
    assert match
    roles = set(ast.literal_eval(match.group(1)))
    assert "speaking_admin" in roles
    assert not roles & {"teacher", "support", "student", "speaking_user"}


# --------------------------------------------------------------------------
# Admin competitions history (runtime tables, string session ids)
# --------------------------------------------------------------------------

def test_admin_competition_history_reads_runtime_tables():
    history = _main_function_source("get_admin_competitions_history")
    results = _main_function_source("get_admin_competition_results")
    for source in (history, results):
        assert "_ADMIN_COMPETITION_RUNTIME_MODES" in source
        assert "web_competition_sessions" in source
        assert "arena_boss_sessions" not in source
        assert "arena_boss_session_attempts" not in source
        assert "arena_duel_match_participants" not in source
    assert "web_competition_participants" in results
    assert "web_competition_history" in results
    runtime_branch = results.split("elif mode in _ADMIN_COMPETITION_RUNTIME_MODES:", 1)[1].split("else:", 1)[0]
    assert "int(session_id)" not in runtime_branch, "runtime session ids are strings like cmp_..."


def test_admin_competition_modes_match_runtime_modes():
    namespace = _load_main_symbols({"_ADMIN_COMPETITION_RUNTIME_MODES"}, {"Any": Any})
    mapping = namespace["_ADMIN_COMPETITION_RUNTIME_MODES"]
    ui = _read("app/ui/admin-competitions.tsx")
    for tab in ("arena-boss", "duel"):
        assert f'id: "{tab}"' in ui
        assert tab in mapping
    start_modes = re.search(r"class CompetitionStartRequest\(BaseModel\):\s*\n\s*mode:\s*Literal\[([^\]]+)\]", _read("backend/main.py"))
    assert start_modes
    runtime_modes = set(ast.literal_eval("[" + start_modes.group(1) + "]"))
    assert set(mapping["arena-boss"]) == {"boss"}
    assert set(mapping["duel"]) == {mode for mode in runtime_modes if mode.startswith("duel-")}


def test_admin_competition_timestamps_are_naive_utc_iso():
    namespace = _load_main_symbols(
        {"_admin_competition_naive_utc_iso"},
        {"Any": Any, "datetime": datetime, "timezone": timezone},
    )
    convert = namespace["_admin_competition_naive_utc_iso"]
    assert convert(None) is None
    assert convert("") is None
    assert convert("2026-10-27T10:00:00+05:00") == "2026-10-27T05:00:00"
    assert convert("2026-10-27T05:00:00Z") == "2026-10-27T05:00:00"
    assert convert("2026-10-27T05:00:00") == "2026-10-27T05:00:00"
    assert convert(datetime(2026, 10, 27, 5, 0, tzinfo=timezone.utc)) == "2026-10-27T05:00:00"
    assert convert(datetime(2026, 10, 27, 5, 0)) == "2026-10-27T05:00:00"
    # The admin UI appends "Z"; the value must therefore carry no offset.
    assert "new Date(item.created_at + 'Z')" in _read("app/ui/admin-competitions.tsx")


# --------------------------------------------------------------------------
# Learning Path contracts
# --------------------------------------------------------------------------

def test_learning_module_update_ignores_null_required_fields():
    source = _read("backend/personalization.py")
    body = source.split("async def update_learning_module(", 1)[1].split("\n@router.", 1)[0]
    assert '("title", "reward_coins", "cover_key", "topic_keys")' in body
    assert "values.pop(required_key)" in body


def test_learning_path_ui_trusts_server_results():
    ui = _read("app/ui/learning-paths.tsx")
    # Certificate claim: 200 + ok:false is a refusal, not a reward.
    assert "res?.ok === false" in ui
    # Final exam: result screen only after the server stored the attempt.
    assert "if (saved) setFinished(true);" in ui
    # Module pass/fail comes from the server's module_progress.
    assert "moduleResult?.module_progress?.passed || finalPercent >= passingScore" not in ui
    assert "lastSubmitResult?.module_progress" in ui
    # Both check-ai calls send the lesson id so the backend picks the subject.
    check_ai_bodies = re.findall(r"/student/learning-lessons/check-ai`, \{(.*?)\}\);", ui, re.S)
    assert len(check_ai_bodies) >= 2
    assert all("lesson_id" in body for body in check_ai_bodies)


def test_learning_path_submit_and_certificate_backend_shapes():
    source = _read("backend/personalization.py")
    assert '"required_score":threshold,"module_progress":progress' in source
    assert '"ok": False' in source  # certificate refusal shape used by the UI


def test_personal_plan_practice_check_contract():
    ui = _read("app/student/plan/page.tsx")
    backend = _read("backend/personalization.py")
    check_body = ui.split('"/api/student/personal-plan/practice-test/check"', 1)[1].split("} finally", 1)[0]
    for field in ("attempt_id", "question_index", "total_questions", "subject"):
        assert field in check_body, f"practice check must send {field}"
        assert f'payload.get("{field}")' in backend, f"backend no longer reads {field}"
    assert "if (!res.ok)" in check_body
    assert "setResult({ correct: isCorrect" not in ui, "no local grading when the server check fails"


# --------------------------------------------------------------------------
# Arena / Duel result handling
# --------------------------------------------------------------------------

def test_arena_result_rewards_come_from_server():
    ui = _read("app/student/test-views.tsx")
    assert "isWinner ? 25 : 5" not in ui
    assert "isWinner ? 50 : 10" not in ui
    assert "result.result?.dcoin" in ui
    backend = _read("backend/main.py")
    assert '"dcoin": _competition_dpoints_to_dcoin(uid, dpoints_delta)' in backend
    assert '"dpoints_delta": dpoints_delta' in backend


def test_arena_errors_keep_backend_code_and_timer_zero():
    ui = _read("app/student/test-views.tsx")
    assert "requestError.code = detailCode" in ui
    assert 'errorCode === "active_session_mismatch"' in ui
    assert '"code": "active_session_mismatch"' in _read("backend/main.py")
    assert "questionPayload.time_remaining_sec || questionPayload.time_limit_sec" not in ui
    assert "question.time_remaining_sec || question.time_limit_sec" not in ui
    # A finished session without a ready result keeps polling.
    assert "waitingForResult ? 2500" in ui


if __name__ == "__main__":
    import sys
    import traceback

    failures = 0
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        try:
            fn()
        except Exception:  # noqa: BLE001 - report every failing contract
            failures += 1
            print(f"FAIL {name}")
            traceback.print_exc()
        else:
            print(f"ok   {name}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
