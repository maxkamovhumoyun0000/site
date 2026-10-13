from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_admin_group_creation_uses_one_idempotent_upsert_path() -> None:
    source = (ROOT / "app" / "page.tsx").read_text(encoding="utf-8")

    assert "function upsertAdminGroupRow" in source
    assert "existing.filter((row) => Number(row.id || 0) !== groupId)" in source
    # The create-panel callback must not append the same group after
    # `onAdminCall` has already made the single optimistic UI update.
    assert "setAdminGroupsFallback((prev) => [createdGroup" not in source
    assert "setAdminGroupsTotal((prev) => prev + 1);" not in source
