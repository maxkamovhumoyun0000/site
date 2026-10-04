from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
PAGE = (ROOT / "app" / "page.tsx").read_text(encoding="utf-8")
NAVIGATION = (ROOT / "app" / "ui" / "navigation-config.ts").read_text(encoding="utf-8")


def test_developer_workspace_routes_and_controls_are_restored():
    workspace = ROOT / "app" / "ui" / "developer-workspace.tsx"
    assert workspace.is_file()
    source = workspace.read_text(encoding="utf-8")
    required_sections = (
        "developer-deploy",
        "developer-server",
        "developer-maintenance",
        "developer-flags",
        "developer-audit",
        "developer-jobs",
        "developer-database",
        "developer-api-metrics",
    )
    for section in required_sections:
        assert section in source
        assert section in NAVIGATION
    assert "FullDeveloperWorkspace" in PAGE


def test_developer_workspace_backend_contract_is_available_and_protected():
    routes = (
        "/developer/deploy/info",
        "/developer/deploy/backup",
        "/developer/server/status",
        "/developer/server/service-restart",
        "/developer/server/logs",
        "/developer/feature-flags",
        "/developer/audit/logs",
        "/developer/jobs/status",
        "/developer/database/stats",
        "/developer/database/purge-cache",
        "/developer/api-metrics/telemetry",
    )
    for route in routes:
        assert route in BACKEND
    allowed_paths = BACKEND.split("_DEVELOPER_WORKSPACE_ALLOWED_PATHS =", 1)[1].split("def _developer_workspace_path_is_allowed", 1)[0]
    for route in routes:
        assert f'"{route}"' in allowed_paths
    assert "def _ensure_developer_tables" in BACKEND
    assert "_require_developer_access(user)" in BACKEND
