from backend.system_metrics import build_system_advice, find_latest_pressure_event


def test_system_metrics_flags_resource_pressure_with_actionable_advice():
    advice = build_system_advice(
        {
            "cpu_percent": 91.0,
            "load_per_cpu": 1.4,
            "memory_percent": 88.0,
            "disk_percent": 92.0,
        }
    )

    codes = {item["code"] for item in advice}
    assert {"cpu", "memory", "disk"}.issubset(codes)
    assert any("disk" in item["action"].lower() for item in advice)


def test_system_metrics_reports_healthy_when_all_resource_thresholds_are_safe():
    advice = build_system_advice(
        {
            "cpu_percent": 22.0,
            "load_per_cpu": 0.3,
            "memory_percent": 48.0,
            "disk_percent": 57.0,
        }
    )

    assert advice == [{"code": "healthy", "level": "ok", "action": "Server resurslari normal diapazonda."}]


def test_latest_pressure_event_uses_most_recent_high_load_sample_not_the_highest_one():
    event = find_latest_pressure_event(
        [
            {"captured_at": "2026-10-02T08:00:00Z", "cpu_percent": 95, "memory_percent": 40, "disk_percent": 30, "load_per_cpu": 1.2},
            {"captured_at": "2026-10-02T09:15:00Z", "cpu_percent": 40, "memory_percent": 87, "disk_percent": 30, "load_per_cpu": 0.5},
        ]
    )

    assert event == {"captured_at": "2026-10-02T09:15:00Z", "causes": ["memory"]}
