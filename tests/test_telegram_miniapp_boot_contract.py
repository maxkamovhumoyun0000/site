from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_delayed_telegram_init_data_keeps_the_miniapp_on_the_loading_screen() -> None:
    source = (ROOT / "app" / "page.tsx").read_text(encoding="utf-8")

    # Telegram injects WebApp.initData asynchronously on some Android clients.
    # That is not a public-browser session, so it must retry in the loading
    # gate rather than render PublicLandingScreen.
    assert "function isTelegramRuntime" in source
    assert "const [isTelegramClient, setIsTelegramClient] = useState(() => isTelegramRuntime())" in source
    assert "Telegram sessiyasi yuklanmoqda" in source
    assert "scheduleTelegramSdkRetry" in source


def test_deploy_runbook_releases_a_committed_snapshot_with_relative_paths() -> None:
    source = (ROOT / "deploy.md").read_text(encoding="utf-8")

    # A deploy must not accidentally publish uncommitted IDE edits or flatten
    # app/page.tsx into the server root.
    assert "git status --short" in source
    assert "DEPLOY_COMMIT" in source
    assert "git archive --format=tar" in source
    assert "tar -xf -" in source
    assert "relative paths" in source
