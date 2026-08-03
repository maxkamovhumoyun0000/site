from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from .face_engine import get_face_engine
from .quality import evaluate_face_quality
from .settings import (
    PROCTORING_CAPTURE_QUALITY_MIN,
    PROCTORING_ENROLL_MAX_SAMPLES,
    PROCTORING_ENROLL_MIN_SAMPLES,
    PROCTORING_FACE_MIN_BOX_RATIO,
    PROCTORING_FACE_MATCH_THRESHOLD,
    PROCTORING_FACE_PROFILE_TTL_DAYS,
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_insightface_provider(provider: str | None) -> bool:
    return str(provider or "").strip().lower().startswith("insightface")


def _engine_diagnostics(engine: Any) -> dict[str, Any]:
    diagnostics = getattr(engine, "diagnostics", None)
    if callable(diagnostics):
        try:
            return dict(diagnostics() or {})
        except Exception:
            return {}
    return {
        "provider": getattr(engine, "provider", "unknown"),
        "insightface_available": getattr(engine, "insightface_available", None),
        "last_errors": getattr(engine, "last_errors", []),
    }


def evaluate_enrollment_sample(image_bgr) -> dict[str, Any]:
    engine = get_face_engine()
    try:
        result = engine.analyze(image_bgr)
    except Exception as exc:
        return {
            "provider": getattr(engine, "provider", "unknown"),
            "face_count": 0,
            "bbox_ratio": 0.0,
            "yaw": None,
            "pitch": None,
            "confidence": 0.0,
            "embedding": None,
            "analyze_error": str(exc),
            "quality": {
                "accepted": False,
                "reason": "ENGINE_ERROR",
                "raw_reason": "ENGINE_ERROR",
                "quality_score": 0.0,
                "blur_score": 0.0,
                "centered": False,
                "capture_quality_min": PROCTORING_CAPTURE_QUALITY_MIN,
                "relaxed_accept": False,
            },
        }
    if not _is_insightface_provider(result.provider):
        diagnostics = _engine_diagnostics(engine)
        return {
            "provider": result.provider,
            "face_count": result.face_count,
            "bbox_ratio": result.bbox_ratio,
            "yaw": result.yaw,
            "pitch": result.pitch,
            "confidence": result.confidence,
            "embedding": None,
            "analyze_error": "INSIGHTFACE_PROVIDER_REQUIRED",
            "engine_diagnostics": diagnostics,
            "quality": {
                "accepted": False,
                "reason": "INSIGHTFACE_PROVIDER_REQUIRED",
                "raw_reason": "INSIGHTFACE_PROVIDER_REQUIRED",
                "quality_score": 0.0,
                "blur_score": 0.0,
                "centered": False,
                "capture_quality_min": PROCTORING_CAPTURE_QUALITY_MIN,
                "relaxed_accept": False,
            },
        }
    quality = evaluate_face_quality(
        image_bgr=image_bgr,
        face_count=result.face_count,
        bbox_ratio=result.bbox_ratio,
        yaw=result.yaw,
        pitch=result.pitch,
        center_offset_ratio=result.center_offset_ratio,
    )
    raw_reason = quality.reason

    if quality.accepted and not result.embedding:
        quality.accepted = False
        quality.reason = "EMBEDDING_MISSING"
        raw_reason = "EMBEDDING_MISSING"

    return {
        "provider": result.provider,
        "face_count": result.face_count,
        "bbox_ratio": result.bbox_ratio,
        "center_offset_ratio": result.center_offset_ratio,
        "yaw": result.yaw,
        "pitch": result.pitch,
        "confidence": result.confidence,
        "embedding": result.embedding,
        "quality": {
            "accepted": quality.accepted,
            "reason": quality.reason,
            "raw_reason": raw_reason,
            "quality_score": quality.quality_score,
            "blur_score": quality.blur_score,
            "centered": quality.centered,
            "capture_quality_min": PROCTORING_CAPTURE_QUALITY_MIN,
            "face_min_box_ratio": PROCTORING_FACE_MIN_BOX_RATIO,
            "center_offset_ratio": result.center_offset_ratio,
            "relaxed_accept": False,
        },
    }


def aggregate_enrollment_embeddings(sample_rows: list[dict[str, Any]]) -> list[float] | None:
    vectors: list[np.ndarray] = []
    for row in sample_rows:
        emb_raw = row.get("embedding_vector")
        if not emb_raw:
            continue
        try:
            vec = np.array(json.loads(str(emb_raw)), dtype=np.float32)
            if vec.size:
                vectors.append(vec)
        except Exception:
            continue
    if not vectors:
        return None
    min_len = min(int(v.shape[0]) for v in vectors)
    if min_len <= 0:
        return None
    stacked = np.stack([v[:min_len] for v in vectors], axis=0)
    avg = np.mean(stacked, axis=0)
    norm = float(np.linalg.norm(avg))
    if norm > 0:
        avg = avg / norm
    return avg.astype(np.float32).tolist()


def verify_against_profile(image_bgr, profile_embedding: list[float] | None, threshold: float | None = None) -> dict[str, Any]:
    engine = get_face_engine()
    threshold_value = float(threshold if threshold is not None else PROCTORING_FACE_MATCH_THRESHOLD)
    if not profile_embedding:
        return {
            "verified": False,
            "match_score": 0.0,
            "threshold": threshold_value,
            "reason": "PROFILE_EMBEDDING_MISSING",
            "face_count": 0,
            "bbox_ratio": 0.0,
            "yaw": None,
            "pitch": None,
            "provider": getattr(engine, "provider", "unknown"),
        }
    try:
        result = engine.analyze(image_bgr)
    except Exception as exc:
        return {
            "verified": False,
            "match_score": 0.0,
            "threshold": threshold_value,
            "reason": "ENGINE_ERROR",
            "face_count": 0,
            "bbox_ratio": 0.0,
            "yaw": None,
            "pitch": None,
            "provider": getattr(engine, "provider", "unknown"),
            "error": str(exc),
        }

    if not _is_insightface_provider(result.provider):
        diagnostics = _engine_diagnostics(engine)
        return {
            "verified": False,
            "match_score": 0.0,
            "threshold": threshold_value,
            "reason": "INSIGHTFACE_PROVIDER_REQUIRED",
            "face_count": result.face_count,
            "bbox_ratio": result.bbox_ratio,
            "yaw": result.yaw,
            "pitch": result.pitch,
            "provider": result.provider,
            "error": "INSIGHTFACE_PROVIDER_REQUIRED",
            "engine_diagnostics": diagnostics,
        }

    if result.face_count <= 0:
        return {
            "verified": False,
            "match_score": 0.0,
            "threshold": threshold_value,
            "reason": "NO_FACE",
            "face_count": 0,
            "bbox_ratio": result.bbox_ratio,
            "yaw": result.yaw,
            "pitch": result.pitch,
            "provider": result.provider,
        }
    if result.face_count > 1:
        return {
            "verified": False,
            "match_score": 0.0,
            "threshold": threshold_value,
            "reason": "MULTIPLE_FACES",
            "face_count": result.face_count,
            "bbox_ratio": result.bbox_ratio,
            "yaw": result.yaw,
            "pitch": result.pitch,
            "provider": result.provider,
        }

    similarity = engine.cosine_similarity(profile_embedding, result.embedding)
    if not result.embedding:
        return {
            "verified": False,
            "match_score": 0.0,
            "threshold": threshold_value,
            "reason": "EMBEDDING_MISSING",
            "face_count": result.face_count,
            "bbox_ratio": result.bbox_ratio,
            "yaw": result.yaw,
            "pitch": result.pitch,
            "provider": result.provider,
        }
    return {
        "verified": bool(similarity >= threshold_value),
        "match_score": float(similarity),
        "threshold": threshold_value,
        "reason": None if similarity >= threshold_value else "FACE_MISMATCH",
        "face_count": result.face_count,
        "bbox_ratio": result.bbox_ratio,
        "yaw": result.yaw,
        "pitch": result.pitch,
        "provider": result.provider,
    }


def enrollment_expiry_iso() -> str:
    return (_now_utc() + timedelta(days=PROCTORING_FACE_PROFILE_TTL_DAYS)).isoformat()


def enrollment_sample_target() -> tuple[int, int]:
    return PROCTORING_ENROLL_MIN_SAMPLES, PROCTORING_ENROLL_MAX_SAMPLES


def verify_start_exam_image(image_bgr, profile_embedding: list[float] | None, threshold: float | None = None) -> dict[str, Any]:
    return verify_against_profile(image_bgr, profile_embedding, threshold)


def verify_recheck_image(image_bgr, profile_embedding: list[float] | None, threshold: float | None = None) -> dict[str, Any]:
    return verify_against_profile(image_bgr, profile_embedding, threshold)
