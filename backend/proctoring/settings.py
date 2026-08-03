from __future__ import annotations

import os


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "on"}


def _env_str(name: str, default: str) -> str:
    raw = str(os.getenv(name, "")).strip()
    return raw or str(default)


PROCTORING_VERIFY_INTERVAL_SEC = max(5, _env_int("PROCTORING_VERIFY_INTERVAL_SEC", 20))
PROCTORING_NO_FACE_GRACE_SEC = max(1, _env_int("PROCTORING_NO_FACE_GRACE_SEC", 5))
PROCTORING_LOOKING_AWAY_GRACE_SEC = max(1, _env_int("PROCTORING_LOOKING_AWAY_GRACE_SEC", 5))
PROCTORING_FACE_TOO_SMALL_GRACE_SEC = max(1, _env_int("PROCTORING_FACE_TOO_SMALL_GRACE_SEC", 5))
PROCTORING_OFFLINE_GRACE_SEC = max(1, _env_int("PROCTORING_OFFLINE_GRACE_SEC", 25))
PROCTORING_FULLSCREEN_EXIT_GRACE_SEC = max(1, _env_int("PROCTORING_FULLSCREEN_EXIT_GRACE_SEC", 5))
PROCTORING_START_VERIFY_MAX_RETRIES = max(1, _env_int("PROCTORING_START_VERIFY_MAX_RETRIES", 5))
PROCTORING_ENROLL_MIN_SAMPLES = max(1, _env_int("PROCTORING_ENROLL_MIN_SAMPLES", 3))
PROCTORING_ENROLL_MAX_SAMPLES = max(PROCTORING_ENROLL_MIN_SAMPLES, _env_int("PROCTORING_ENROLL_MAX_SAMPLES", 5))
PROCTORING_ENROLL_SCAN_WINDOW_SEC = max(2, _env_int("PROCTORING_ENROLL_SCAN_WINDOW_SEC", 6))
PROCTORING_CAPTURE_QUALITY_MIN = max(0.0, min(1.0, _env_float("PROCTORING_CAPTURE_QUALITY_MIN", 0.60)))
PROCTORING_FACE_MIN_BOX_RATIO = max(0.01, min(0.95, _env_float("PROCTORING_FACE_MIN_BOX_RATIO", 0.10)))
PROCTORING_FACE_MATCH_THRESHOLD = max(0.0, min(1.0, _env_float("PROCTORING_FACE_MATCH_THRESHOLD", 0.82)))
PROCTORING_START_FACE_MATCH_THRESHOLD = max(
    0.0,
    min(
        PROCTORING_FACE_MATCH_THRESHOLD,
        _env_float("PROCTORING_START_FACE_MATCH_THRESHOLD", 0.72),
    ),
)
PROCTORING_RECHECK_FACE_MATCH_THRESHOLD = max(
    0.0,
    min(
        PROCTORING_START_FACE_MATCH_THRESHOLD,
        _env_float("PROCTORING_RECHECK_FACE_MATCH_THRESHOLD", 0.72),
    ),
)
PROCTORING_FACE_MISMATCH_CONFIRMATION_LIMIT = max(3, _env_int("PROCTORING_FACE_MISMATCH_STRIKES", 5))
PROCTORING_FACE_PROFILE_TTL_DAYS = max(1, _env_int("PROCTORING_FACE_PROFILE_TTL_DAYS", 180))
PROCTORING_SNAPSHOT_JPEG_QUALITY = max(0.1, min(0.99, _env_float("PROCTORING_SNAPSHOT_JPEG_QUALITY", 0.72)))
PROCTORING_SNAPSHOT_MAX_SIDE = max(256, _env_int("PROCTORING_SNAPSHOT_MAX_SIDE", 720))
PROCTORING_FACE_ENGINE = _env_str("PROCTORING_FACE_ENGINE", "insightface").strip().lower()
# Production policy: recognition is locked to InsightFace-only.
if PROCTORING_FACE_ENGINE != "insightface":
    PROCTORING_FACE_ENGINE = "insightface"
PROCTORING_DEEPFACE_MODEL = _env_str("PROCTORING_DEEPFACE_MODEL", "ArcFace").strip() or "ArcFace"
PROCTORING_DEEPFACE_DETECTOR_BACKEND = _env_str("PROCTORING_DEEPFACE_DETECTOR_BACKEND", "mediapipe").strip() or "mediapipe"
PROCTORING_ENGINE_FALLBACK_ENABLED = _env_bool("PROCTORING_ENGINE_FALLBACK_ENABLED", True)

# strict immediate policy knobs
PROCTORING_IMMEDIATE_FAIL_EVENTS = {
}
