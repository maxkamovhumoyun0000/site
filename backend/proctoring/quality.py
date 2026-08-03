from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from .settings import PROCTORING_CAPTURE_QUALITY_MIN, PROCTORING_FACE_MIN_BOX_RATIO


@dataclass
class FaceQualityResult:
    accepted: bool
    reason: str | None
    quality_score: float
    face_count: int
    face_box_ratio: float
    blur_score: float
    centered: bool
    yaw: float | None = None
    pitch: float | None = None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def evaluate_face_quality(
    *,
    image_bgr: np.ndarray,
    face_count: int,
    bbox_ratio: float,
    yaw: float | None,
    pitch: float | None,
    center_offset_ratio: float | None,
) -> FaceQualityResult:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    centered = _safe_float(center_offset_ratio, 0.0) <= 0.22
    blur_norm = min(1.0, max(0.0, blur_score / 220.0))
    box_norm = min(1.0, max(0.0, _safe_float(bbox_ratio, 0.0) / max(PROCTORING_FACE_MIN_BOX_RATIO, 1e-6)))
    center_norm = 1.0 if centered else max(0.0, 1.0 - _safe_float(center_offset_ratio, 0.0))
    quality_score = float((0.45 * blur_norm) + (0.35 * box_norm) + (0.20 * center_norm))

    if face_count <= 0:
        return FaceQualityResult(False, "NO_FACE", quality_score, face_count, _safe_float(bbox_ratio), blur_score, centered, yaw, pitch)
    if face_count > 1:
        return FaceQualityResult(False, "MULTIPLE_FACES", quality_score, face_count, _safe_float(bbox_ratio), blur_score, centered, yaw, pitch)
    if _safe_float(bbox_ratio, 0.0) < PROCTORING_FACE_MIN_BOX_RATIO:
        return FaceQualityResult(False, "FACE_TOO_SMALL", quality_score, face_count, _safe_float(bbox_ratio), blur_score, centered, yaw, pitch)
    if quality_score < PROCTORING_CAPTURE_QUALITY_MIN:
        return FaceQualityResult(False, "LOW_QUALITY", quality_score, face_count, _safe_float(bbox_ratio), blur_score, centered, yaw, pitch)

    return FaceQualityResult(True, None, quality_score, face_count, _safe_float(bbox_ratio), blur_score, centered, yaw, pitch)
