"""Small, dependency-free host metric helpers for the restricted admin dashboard.

Only aggregate host resource counters are collected.  No process command line,
environment variables, user data, request payloads, or log contents are ever
returned from this module.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from threading import Lock
from typing import Any


_CPU_SAMPLE_LOCK = Lock()
_PREVIOUS_CPU_SAMPLE: tuple[int, int] | None = None


def _meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        for raw_line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, _, raw_value = raw_line.partition(":")
            amount = raw_value.strip().split(" ", 1)[0]
            if amount.isdigit():
                values[key] = int(amount) * 1024
    except OSError:
        pass
    return values


def _cpu_percent(cpu_count: int, load_1: float) -> float:
    """Return process-independent CPU use from /proc/stat.

    The first call has no time delta, so it uses normalized one-minute load as
    a conservative estimate. Subsequent requests use consecutive kernel CPU
    counters and are capped to the valid percentage range.
    """
    global _PREVIOUS_CPU_SAMPLE
    try:
        fields = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0].split()[1:]
        counters = [int(value) for value in fields]
        total = sum(counters)
        idle = counters[3] + (counters[4] if len(counters) > 4 else 0)
    except (OSError, ValueError, IndexError):
        return round(max(0.0, min(100.0, (load_1 / max(cpu_count, 1)) * 100.0)), 1)

    with _CPU_SAMPLE_LOCK:
        previous = _PREVIOUS_CPU_SAMPLE
        _PREVIOUS_CPU_SAMPLE = (total, idle)
    if not previous:
        return round(max(0.0, min(100.0, (load_1 / max(cpu_count, 1)) * 100.0)), 1)
    total_delta = total - previous[0]
    idle_delta = idle - previous[1]
    if total_delta <= 0:
        return 0.0
    return round(max(0.0, min(100.0, (1.0 - (idle_delta / total_delta)) * 100.0)), 1)


def collect_system_metrics() -> dict[str, Any]:
    """Collect a privacy-safe snapshot of CPU, memory, disk and uptime."""
    cpu_count = max(1, int(os.cpu_count() or 1))
    try:
        load_1, load_5, load_15 = (float(value) for value in os.getloadavg())
    except OSError:
        load_1 = load_5 = load_15 = 0.0
    memory = _meminfo()
    mem_total = max(0, int(memory.get("MemTotal", 0)))
    mem_available = max(0, int(memory.get("MemAvailable", memory.get("MemFree", 0))))
    swap_total = max(0, int(memory.get("SwapTotal", 0)))
    swap_free = max(0, int(memory.get("SwapFree", 0)))
    disk = shutil.disk_usage("/")
    try:
        uptime_seconds = int(float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0]))
    except (OSError, ValueError, IndexError):
        uptime_seconds = 0

    memory_percent = round(((mem_total - mem_available) / mem_total) * 100.0, 1) if mem_total else 0.0
    disk_percent = round((disk.used / disk.total) * 100.0, 1) if disk.total else 0.0
    swap_percent = round(((swap_total - swap_free) / swap_total) * 100.0, 1) if swap_total else 0.0
    return {
        "cpu_percent": _cpu_percent(cpu_count, load_1),
        "cpu_cores": cpu_count,
        "load_1": round(load_1, 2),
        "load_5": round(load_5, 2),
        "load_15": round(load_15, 2),
        "load_per_cpu": round(load_1 / cpu_count, 2),
        "memory_total_bytes": mem_total,
        "memory_available_bytes": mem_available,
        "memory_percent": memory_percent,
        "swap_total_bytes": swap_total,
        "swap_used_bytes": max(0, swap_total - swap_free),
        "swap_percent": swap_percent,
        "disk_total_bytes": int(disk.total),
        "disk_used_bytes": int(disk.used),
        "disk_free_bytes": int(disk.free),
        "disk_percent": disk_percent,
        "uptime_seconds": uptime_seconds,
        "captured_monotonic": round(time.monotonic(), 3),
    }


def build_system_advice(metrics: dict[str, Any]) -> list[dict[str, str]]:
    """Translate thresholds into small, operator-actionable recommendations."""
    advice: list[dict[str, str]] = []
    if float(metrics.get("disk_percent") or 0) >= 85:
        advice.append({"code": "disk", "level": "critical", "action": "Disk joyini bo'shating yoki disk hajmini oshiring."})
    if float(metrics.get("memory_percent") or 0) >= 85:
        advice.append({"code": "memory", "level": "warning", "action": "RAM yuklamasini tekshiring; ko'p workerlarni kamaytiring yoki RAMni oshiring."})
    if float(metrics.get("cpu_percent") or 0) >= 85 or float(metrics.get("load_per_cpu") or 0) >= 1.0:
        advice.append({"code": "cpu", "level": "warning", "action": "CPU yuklamasini tekshiring; og'ir ishlarni navbatlang yoki CPUni oshiring."})
    if float(metrics.get("swap_percent") or 0) >= 50:
        advice.append({"code": "swap", "level": "warning", "action": "Swap ishlatilmoqda; RAM yetarliligini tekshiring."})
    if not advice:
        return [{"code": "healthy", "level": "ok", "action": "Server resurslari normal diapazonda."}]
    return advice


def find_latest_pressure_event(samples: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the newest (not largest) observed resource-pressure event."""
    for sample in sorted(samples, key=lambda item: str(item.get("captured_at") or ""), reverse=True):
        causes: list[str] = []
        if float(sample.get("cpu_percent") or 0) >= 85 or float(sample.get("load_per_cpu") or 0) >= 1.0:
            causes.append("cpu")
        if float(sample.get("memory_percent") or 0) >= 85:
            causes.append("memory")
        if float(sample.get("disk_percent") or 0) >= 85:
            causes.append("disk")
        if causes:
            return {"captured_at": sample.get("captured_at"), "causes": causes}
    return None
