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
* the media workspace (MEDIA-X-01) lists and can load the competition
  history in its sidebar and on its home page;
* Arena/Duel skip buttons send ``skipped`` for vocabulary questions;
* the broadcast popup scrolls long announcements instead of overflowing;
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

# The Speaking admin's Learning Path page is StaffLearningPaths (in
# app/ui/learning-paths.tsx) rendered with scope="speaking"; its /staff/...
# calls are mapped to /speaking-lp/staff/... (see the Speaking LP tests below).
SPEAKING_ADMIN_UI_FILES = (
    "app/ui/admin-speaking-topics.tsx",
    "app/ui/admin-speaking-notifications.tsx",
    "app/ui/admin-speaking-videos.tsx",
    "app/ui/admin-speaking-plan-tests.tsx",
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


def _speaking_lp_mount() -> tuple[str, tuple[str, ...]]:
    """SPEAKING_LP_PREFIX and SPEAKING_LP_ROUTE_PREFIXES of personalization.py."""
    tree = ast.parse(_read("backend/personalization.py"))
    values: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"SPEAKING_LP_PREFIX", "SPEAKING_LP_ROUTE_PREFIXES"}:
                    values[target.id] = ast.literal_eval(node.value)
    assert set(values) == {"SPEAKING_LP_PREFIX", "SPEAKING_LP_ROUTE_PREFIXES"}, "Speaking LP mount constants missing"
    return values["SPEAKING_LP_PREFIX"], tuple(values["SPEAKING_LP_ROUTE_PREFIXES"])


def _speaking_lp_mounted_routes() -> list[tuple[str, str]]:
    """Routes personalization.py mounts a second time under /speaking-lp.

    They are added at import time (router.add_api_route), so the decorator
    regex cannot see them; derive them from the same constants instead.
    """
    prefix, route_prefixes = _speaking_lp_mount()
    text = _read("backend/personalization.py")
    return [
        (method.upper(), prefix + route)
        for method, route in ROUTE_DECORATOR_RE.findall(text)
        if route.startswith(route_prefixes)
    ]


def _backend_routes() -> list[tuple[str, str]]:
    routes: list[tuple[str, str]] = []
    for path in sorted(BACKEND.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        routes.extend((method.upper(), route) for method, route in ROUTE_DECORATOR_RE.findall(text))
    routes.extend(_speaking_lp_mounted_routes())
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
        "/speaking-lp/student/learning-tracks",
        "/teacher/library/upload",
        "/developer/deploy",
        "/notifications/42/read/extra",
        "/notifications/push-token/unregister/x",
        "/staff/speakingX/topics",
    ):
        assert not allowed(path), f"Speaking admin guard must block {path}"


# --------------------------------------------------------------------------
# Speaking Learning Path (StaffLearningPaths scope="speaking" + /speaking-lp)
# --------------------------------------------------------------------------

# Teacher Materials Library features; hidden in the Speaking scope and not
# mounted under /speaking-lp.
SPEAKING_LP_HIDDEN_STAFF_PATHS = {"/staff/teacher-library-tree", "/staff/materials-search"}


def _speaking_lp_path_mapper() -> Callable[[str], str]:
    """Python twin of speakingLearningPathApiPath() in learning-paths.tsx."""
    ui = _read("app/ui/learning-paths.tsx")
    match = re.search(
        r'export function speakingLearningPathApiPath\(path: string\): string \{\s*'
        r'return path\.startsWith\("([^"]+)"\) \? `([^`$]+)\$\{path\}` : path;\s*\}',
        ui,
    )
    assert match, "speakingLearningPathApiPath() not found or changed shape"
    source_prefix, target_prefix = match.groups()
    return lambda path: f"{target_prefix}{path}" if path.startswith(source_prefix) else path


def _speaking_lp_staff_ui_paths() -> set[str]:
    mapper = _speaking_lp_path_mapper()
    return {
        mapper(path)
        for path in _frontend_backend_paths("app/ui/learning-paths.tsx")
        if path.startswith("/staff/") and path not in SPEAKING_LP_HIDDEN_STAFF_PATHS
    }


def test_speaking_lp_wrapper_prefixes_staff_paths():
    mapper = _speaking_lp_path_mapper()
    assert mapper("/staff/learning-tracks") == "/speaking-lp/staff/learning-tracks"
    assert mapper("/staff/learning-modules/5/ai-question") == "/speaking-lp/staff/learning-modules/5/ai-question"
    assert mapper("/auth/me") == "/auth/me"
    page = _read("app/page.tsx")
    branch = page.split('currentSection === "speaking-learning-paths" && activeRole === "speaking_admin"', 1)[1][:600]
    assert "speakingLearningPathFetch(authedApiFetch)" in branch
    assert 'scope="speaking"' in branch and "<StaffLearningPaths" in branch
    assert not (APP / "ui" / "speaking-learning-paths.tsx").exists()
    assert 'from "./ui/speaking-learning-paths"' not in page


def test_speaking_admin_guard_allows_speaking_learning_path_staff_calls():
    allowed = _speaking_guard()
    paths = _speaking_lp_staff_ui_paths()
    assert "/speaking-lp/staff/learning-tracks" in paths, "staff path extraction is stale"
    blocked = sorted(path for path in paths if not allowed(path))
    assert not blocked, f"Speaking admin guard rejects Speaking LP calls: {blocked}"
    missing = sorted(path for path in paths if not _route_exists(path))
    assert not missing, f"Speaking LP UI calls without backend route: {missing}"
    # Media upload: raw fetch in the Speaking scope, not the teacher Library.
    assert "/speaking-lp/staff/upload" in _frontend_backend_paths("app/ui/learning-paths.tsx")
    assert allowed("/speaking-lp/staff/upload") and _route_exists("/speaking-lp/staff/upload")
    assert not allowed("/teacher/library/upload")


def test_speaking_lp_routes_are_mounted_for_staff_and_student():
    for path in (
        "/speaking-lp/staff/learning-tracks",
        "/speaking-lp/staff/learning-tracks/1/modules",
        "/speaking-lp/staff/learning-modules/1/lessons/batch",
        "/speaking-lp/staff/learning-module-topics/1",
        "/speaking-lp/staff/learning-lessons/1",
        "/speaking-lp/student/learning-tracks",
        "/speaking-lp/student/learning-lessons/1",
        "/speaking-lp/student/learning-lessons/1/submit",
        "/speaking-lp/student/learning-lessons/check-ai",
        "/speaking-lp/student/learning-lessons/1/check-ai",
        "/speaking-lp/student/learning-tracks/1/final-exam",
        "/speaking-lp/student/learning-tracks/1/final-exam/submit",
        "/speaking-lp/student/learning-tracks/1/certificate",
    ):
        assert _route_exists(path), f"missing mounted Speaking LP route {path}"
    assert not _route_exists("/speaking-lp/staff/teacher-library-tree")
    assert not _route_exists("/speaking-lp/student/study-rooms")


def test_speaking_lp_mount_covers_every_learning_path_route():
    source = _read("backend/personalization.py")
    _, route_prefixes = _speaking_lp_mount()
    lp_routes = [
        route for _, route in ROUTE_DECORATOR_RE.findall(source)
        if route.startswith(("/staff/learning", "/student/learning"))
    ]
    assert len(lp_routes) >= 25
    uncovered = sorted(route for route in lp_routes if not route.startswith(route_prefixes))
    assert not uncovered, f"Learning Path routes not mounted under /speaking-lp: {uncovered}"
    # Mounting runs once every route above is registered and wraps the
    # handler (functools.wraps keeps FastAPI's signature) in the namespace.
    mount_at = source.index("SPEAKING_LP_MOUNTED_ROUTES = _mount_speaking_learning_path_routes()")
    last_route = max(source.index(f'"{route}"') for route in lp_routes)
    assert mount_at > last_route
    body = source.split("def _speaking_lp_endpoint(", 1)[1].split("\ndef ", 1)[0]
    assert "@functools.wraps(endpoint)" in body and "_LP_NAMESPACE.set(SPEAKING_LP_NAMESPACE)" in body
    assert "_LP_NAMESPACE.reset(token)" in body
    mount = source.split("def _mount_speaking_learning_path_routes(", 1)[1].split("\nSPEAKING_LP_MOUNTED_ROUTES", 1)[0]
    assert "router.add_api_route(" in mount and "SPEAKING_LP_ROUTE_PREFIXES" in mount


def test_speaking_lp_roles_and_isolation():
    source = _read("backend/personalization.py")
    match = re.search(r"^SPEAKING_LP_MANAGER_ROLES\s*=\s*(\{[^}]*\})", source, re.M)
    assert match and ast.literal_eval(match.group(1)) == {"speaking_admin"}
    assert '"speaking-learning-track"' in source  # distinct certificate course_key
    assert "_require(user, LEARNING_MANAGER_ROLES)" not in source
    for name in ("student_learning_tracks", "student_learning_lesson", "submit_learning_lesson",
                 "claim_track_certificate", "get_track_final_exam", "submit_track_final_exam"):
        body = source.split(f"async def {name}(", 1)[1].split("\n@router.", 1)[0]
        assert "_require_lp_student(user)" in body, name
    for name in ("_archive_learning_path_test", "_delete_learning_path_library_branch",
                 "_delete_learning_path_library_bundle", "rebuild_learning_path_library_mirrors"):
        body = source.split(f"def {name}(", 1)[1].split("\ndef ", 1)[0]
        assert "_lp_is_speaking()" in body, f"{name} must not mirror the Speaking LP into Libraries"


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


def _ts_string_list(text: str, marker: str) -> list[str]:
    """String items of the first `[...]` literal that follows ``marker``."""
    assert marker in text, f"{marker!r} not found"
    return re.findall(r'"([^"]+)"', text.split(marker, 1)[1].split("]", 1)[0])


def test_media_workspace_shows_and_loads_competitions_history():
    section = "competitions-history"
    # 1) Navigation: the media allow-list has it; no retired/hidden filter drops it.
    nav = _read("app/ui/navigation-config.ts")
    assert section in _ts_string_list(nav, "  media: [")
    for name in ("RETIRED_SECTION_IDS", "HIDDEN_SECTION_IDS"):
        ids = _ts_string_list(nav, f"export const {name} = new Set([")
        assert ids and section not in ids, f"{name} hides {section}"
    assert '"competitions-history": "Musobaqalar Tarixi"' in nav
    # 2) Sidebar order of the media workspace (the branch keyed on vocabulary-bank).
    sidebar = _read("app/ui/dashboard-sidebar.tsx")
    assert section in _ts_string_list(sidebar, 'sectionSet.has("vocabulary-bank")\n      ? [')
    page = _read("app/page.tsx")
    # 3) MEDIA-X-01 (backend role "admin") becomes the media workspace, whose
    #    sections are the allow-list above.
    role = page.split("function roleFromUser(", 1)[1].split("\n}\n", 1)[0]
    assert 'loginId === "media-x-01") return "media";' in role
    resolve = page.split("function resolveRoleSections(", 1)[1].split("\n}\n", 1)[0]
    assert 'role === "media" || role === "limited_admin"' in resolve
    assert "!RETIRED_SECTION_IDS.has(item)" in resolve
    # 4) Media home lists every MEDIA_WORKSPACE_SECTIONS entry.
    assert section in _ts_string_list(page, "const MEDIA_WORKSPACE_SECTIONS = [")
    home = page.split("function MediaWorkspaceHome(", 1)[1].split("\n}\n", 1)[0]
    slices = sorted(
        (int(start), int(end) if end else None)
        for start, end in re.findall(r"MEDIA_WORKSPACE_SECTIONS\.slice\((\d+)(?:,\s*(\d+))?\)", home)
    )
    assert slices and slices[0][0] == 0 and slices[-1][1] is None, slices
    assert all(prev[1] == nxt[0] for prev, nxt in zip(slices, slices[1:])), f"media home skips sections: {slices}"
    # 5) The media shell renders AdminSection in media mode, and AdminSection
    #    reaches the history page (no media-only early return before it).
    assert "mediaMode={activeRole === \"media\"}" in page
    admin_section = page.split("function AdminSection({", 1)[1].split("\nfunction ", 1)[0]
    branch = 'if (section === "competitions-history") {\n    return <AdminCompetitions />;'
    assert branch in admin_section
    before = admin_section.split(branch, 1)[0]
    for match in re.findall(r"^  if \(mediaMode[^\n]*", before, re.M):
        assert '&& section === "' in match, f"media early return hides other sections: {match}"
    # 6) Backend: MEDIA-X-01 is login_type 4 -> "admin", both routes accept
    #    "admin", and the only workspace guards are for the developer and
    #    Speaking admin logins.
    ns = _load_main_symbols({"_role_from_login_type", "_is_developer_account", "_is_speaking_admin_account"}, {"os": __import__("os")})
    assert ns["_role_from_login_type"](4, "MEDIA-X-01") == "admin"
    assert not ns["_is_developer_account"]({"login_id": "MEDIA-X-01"})
    assert not ns["_is_speaking_admin_account"]({"login_id": "MEDIA-X-01"})
    for name in ("get_admin_competitions_history", "get_admin_competition_results"):
        assert '_require_role(user, {"admin"})' in _main_function_source(name)
    paths = _frontend_backend_paths("app/ui/admin-competitions.tsx")
    assert {"/admin/competitions/history", f"/admin/competitions/{DYNAMIC}/results"} <= paths


def test_broadcast_popup_scrolls_long_messages():
    # Long announcements (the trilingual platform notice is ~1,100 characters)
    # must keep the close buttons reachable on phones and in Telegram.
    page = _read("app/page.tsx")
    popup = page.split("{!isChatsFullscreen && broadcastPopup ? (() => {", 1)[1].split("})() : null}", 1)[0]
    assert 'maxHeight: "calc(var(--tg-viewport-height, 100dvh) - 40px)"' in popup
    assert 'overflowY: "auto"' in popup
    assert "whitespace-pre-wrap" in popup and "onClick={closeBroadcast}" in popup
    bridge = _read("public/csp-style-bridge.js")
    assert '"maxHeight"' in bridge and '"overflowY"' in bridge


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


def _ts_function_source(text: str, name: str) -> str:
    """Body of a top-level TS function (up to the first closing brace at column 0)."""
    marker = f"function {name}("
    assert marker in text, f"{name} not found"
    return text.split(marker, 1)[1].split("\n}\n", 1)[0]


def test_arena_duel_answer_body_carries_vocabulary_fields():
    ui = _read("app/student/test-views.tsx")
    body = _ts_function_source(ui, "answerBody")
    for field in ("selected_option_index", "answer_text", "matching_answer", "audio_url", "timed_out", "skipped"):
        assert field in body, f"competition answer body cannot carry {field}"
    # The Arena/Duel submit forwards the widened body; the timer sends timed_out.
    assert "...answerBody(answer, options)" in ui
    assert "submitAnswer(null, { timedOut: true })" in ui
    # AI test runner payloads map onto the competition answer fields.
    mapper = _ts_function_source(ui, "competitionAnswerFromRunnerPayload")
    for runner_field, body_field in (
        ("answer_text", "answer_text"),
        ("audio_url", "audio_url"),
        ("pairs", "matching_answer"),
        ("choice_index", "selected_option_index"),
    ):
        assert f"payload.{runner_field}" in mapper and f"answer.{body_field}" in mapper
    # Vocabulary questions reuse the AI test runner answer UI; MCQ keeps its renderer.
    assert 'from "../ui/ai-test-runner"' in ui
    assert "<CompetitionVocabularyQuestion" in ui
    assert "key={question.question_index}" in ui
    # The backend request model accepts every field the website sends.
    backend = _read("backend/main.py")
    model = backend.split("class CompetitionAnswerRequest(BaseModel):", 1)[1].split("\nclass ", 1)[0]
    for field in ("selected_option_index", "answer_text", "audio_url", "matching_answer", "timed_out", "skipped", "question_index"):
        assert f"{field}:" in model, f"CompetitionAnswerRequest no longer accepts {field}"
    # Recorded answers come from the shared AI test upload route.
    assert _route_exists("/student/ai-tests/upload-audio")
    assert '"/student/ai-tests/upload-audio"' in _read("app/ui/ai-test-runner.tsx")


def test_arena_duel_skip_buttons_send_skipped_for_vocabulary():
    ui = _read("app/student/test-views.tsx")
    body = _ts_function_source(ui, "answerBody")
    assert "if (options?.timedOut) body.timed_out = true;" in body
    assert "if (options?.skipped) body.skipped = true;" in body
    page = ui.split("export function StudentCompetitionPage(", 1)[1].split(
        "export function StudentCompetitionRuntimePage(", 1
    )[0]
    skip = page.split("function skipCurrentQuestion() {", 1)[1].split("\n  }\n", 1)[0]
    # Vocabulary questions send the explicit skip flag; MCQ keeps the null answer.
    assert "submitAnswer(null, competitionVocabularyType(question?.question) ? { skipped: true } : undefined)" in skip
    # Previous / Next / Finish and the question pills all use the skip helper
    # and none of them posts a bare null answer any more.
    assert page.count("onClick={skipCurrentQuestion}") == 3
    assert "skipCurrentQuestion();" in page
    assert "submitAnswer(null)" not in page
    # The countdown keeps sending the timeout flag, not the skip flag.
    assert "submitAnswer(null, { timedOut: true })" in page
    model = _read("backend/main.py").split("class CompetitionAnswerRequest(BaseModel):", 1)[1].split("\nclass ", 1)[0]
    assert "skipped: bool = False" in model


def test_retired_teacher_arena_is_gone_from_website():
    page = _read("app/page.tsx")
    assert "/teacher/arena" not in page, "app/page.tsx still calls the retired /teacher/arena API"
    sidebar = _read("app/ui/dashboard-sidebar.tsx")
    teacher_order = sidebar.split('sectionSet.has("performance") && sectionSet.has("homework")', 1)[1].split("]", 1)[0]
    assert '"arena"' not in teacher_order, "teacher sidebar order still lists arena"
    # Students keep the Arena hub (Boss Arena and duels).
    assert 'if (item === "arena" && (role === "student" || role === "speaking_user")) return true;' in page
    assert "<StudentArena" in page


# --------------------------------------------------------------------------
# Teacher group creation: course list and price tiers
# --------------------------------------------------------------------------

def _component_function_source(text: str, name: str) -> str:
    """Body of a function nested one level inside a component (2-space indent)."""
    marker = f"  async function {name}("
    assert marker in text, f"{name} not found"
    return text.split(marker, 1)[1].split("\n  }\n", 1)[0]


def test_teacher_group_create_loads_courses_from_teacher_route():
    # The website modal and the Teachers app both load the course list from
    # /teacher/courses; it returned 404 before, so the app showed no courses.
    assert _route_exists("/teacher/courses")
    source = _main_function_source("teacher_list_courses")
    assert '_require_role(user, {"teacher"})' in source
    assert "include_drafts=False" in source
    loader = _component_function_source(_read("app/page.tsx"), "loadTeacherCourses")
    assert '"/teacher/courses"' in loader


def test_teacher_group_create_offers_every_pricing_type_with_prices():
    page = _read("app/page.tsx")
    for value in ('value: "group"', 'value: "individual"', 'value: "mini_group"'):
        assert value in page
    tiers = _ts_function_source(page, "groupPriceTiers")
    for field in ("price_text", "individual_price_text", "mini_group_${size}_price_text"):
        assert field in tiers
    submit = _component_function_source(page, "handleTeacherCreateGroup")
    # The course decides the price, so it must be chosen explicitly.
    assert "teacherCoursesList[0]" not in submit
    assert "pricing_type" in submit


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
