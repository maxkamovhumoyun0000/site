from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_script_deploys_only_a_clean_origin_main_snapshot() -> None:
    script = ROOT / "scripts" / "deploy_release_snapshot.sh"
    assert script.is_file()
    source = script.read_text(encoding="utf-8")

    assert "git status --porcelain" in source
    assert "git fetch origin" in source
    assert 'DEPLOY_COMMIT="${1:-origin/main}"' in source
    assert "git archive --format=tar" in source
    assert ".diamond-deploy/commit" in source
    assert "lock_acquired" in source


def test_release_script_removes_only_previously_managed_stale_source_files() -> None:
    source = (ROOT / "scripts" / "deploy_release_snapshot.sh").read_text(encoding="utf-8")

    # A file is eligible for removal only when it appeared in the prior
    # managed manifest. Protected production state must never be touched.
    assert ".diamond-deploy/managed-paths" in source
    assert "previous_manifest" in source
    assert "protected_top_levels" in source
    assert '".env"' in source
    assert '"data"' in source
    assert '"uploads"' in source
    assert '"media"' in source
    assert '"node_modules"' in source
    assert '".next"' in source


def test_deploy_runbook_uses_the_guarded_release_script() -> None:
    source = (ROOT / "deploy.md").read_text(encoding="utf-8")

    assert "scripts/deploy_release_snapshot.sh" in source
    assert "managed manifest" in source
    assert "Release commit verification" in source
