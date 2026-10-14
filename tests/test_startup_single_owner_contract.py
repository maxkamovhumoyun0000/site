from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_startup_maintenance_is_owned_by_one_web_worker() -> None:
    source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    start = source.index("async def startup_event()")
    end = source.index("@app.on_event(\"shutdown\")", start)
    startup = source[start:end]

    owner_lock = startup.index("scheduler_owner = _acquire_background_scheduler_lock()")
    first_database_init = startup.index("init_db()")
    assert owner_lock < first_database_init
    assert "if scheduler_owner:\n        step = time.perf_counter()\n        init_db()" in startup
    assert "if scheduler_owner:\n        step = time.perf_counter()\n        _ensure_final_chat_schema()" in startup
    assert "start_userbot_queue_worker()" in startup


def test_readiness_probe_checks_database_and_reports_release_without_secrets() -> None:
    source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    start = source.index('@app.get("/health/ready")')
    end = source.index("def _ensure_system_metrics_schema", start)
    readiness = source[start:end]

    assert 'cur.execute("SELECT 1")' in readiness
    assert 'status_code=503' in readiness
    assert '"release": release' in readiness
    assert "JWT_SECRET" not in readiness
