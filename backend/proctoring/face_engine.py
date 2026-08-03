from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging
from typing import Any

import cv2
import numpy as np

from .settings import (
    PROCTORING_ENGINE_FALLBACK_ENABLED,
)

logger = logging.getLogger(__name__)


@dataclass
class FaceEngineResult:
    face_count: int
    bbox_ratio: float
    center_offset_ratio: float
    yaw: float | None
    pitch: float | None
    confidence: float
    embedding: list[float] | None
    provider: str


@dataclass
class _FaceBox:
    x: int
    y: int
    w: int
    h: int
    confidence: float


def _sanitize_embedding(raw: Any) -> list[float] | None:
    if raw is None:
        return None
    try:
        arr = np.asarray(raw, dtype=np.float32).flatten()
    except Exception:
        return None
    if arr.size <= 0:
        return None
    norm = float(np.linalg.norm(arr))
    if norm > 0:
        arr = arr / norm
    return arr.tolist()


def _bbox_metrics(box: _FaceBox, width: int, height: int) -> tuple[float, float]:
    bbox_ratio = float((float(box.w) * float(box.h)) / float(max(1, width * height)))
    cx = float(box.x + (box.w / 2.0))
    cy = float(box.y + (box.h / 2.0))
    center_offset_ratio = float(np.sqrt(((cx - (width / 2.0)) / width) ** 2 + ((cy - (height / 2.0)) / height) ** 2))
    return bbox_ratio, center_offset_ratio


def _extract_face_crop(image_bgr: np.ndarray, box: _FaceBox) -> np.ndarray:
    height, width = image_bgr.shape[:2]
    x1 = max(0, min(width - 1, int(box.x)))
    y1 = max(0, min(height - 1, int(box.y)))
    x2 = max(x1 + 1, min(width, int(box.x + box.w)))
    y2 = max(y1 + 1, min(height, int(box.y + box.h)))
    return image_bgr[y1:y2, x1:x2]


class OpenCvFallbackEngine:
    def __init__(self, provider: str = "opencv_fallback") -> None:
        self.provider = provider
        self._haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self.available = True

    def analyze(self, image_bgr: np.ndarray) -> FaceEngineResult:
        h, w = image_bgr.shape[:2]
        if h <= 0 or w <= 0:
            return FaceEngineResult(0, 0.0, 1.0, None, None, 0.0, None, self.provider)
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        faces = self._haar.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))
        face_count = int(len(faces))
        if face_count <= 0:
            return FaceEngineResult(0, 0.0, 1.0, None, None, 0.0, None, self.provider)

        x, y, fw, fh = max(faces, key=lambda b: int(b[2]) * int(b[3]))
        box = _FaceBox(int(x), int(y), int(fw), int(fh), 0.55)
        bbox_ratio, center_offset_ratio = _bbox_metrics(box, w, h)
        face_roi = _extract_face_crop(image_bgr, box)
        embedding = self._fallback_embedding(face_roi)
        return FaceEngineResult(face_count, bbox_ratio, center_offset_ratio, None, None, box.confidence, embedding, self.provider)

    @staticmethod
    def _fallback_embedding(face_bgr: np.ndarray) -> list[float]:
        if face_bgr.size == 0:
            return []
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
        hist = cv2.calcHist([small], [0], None, [64], [0, 256]).flatten().astype(np.float32)
        norm = np.linalg.norm(hist)
        if norm > 0:
            hist /= norm
        return hist.tolist()


class InsightFaceEngine:
    def __init__(self) -> None:
        self.provider = "insightface_onnx"
        self.available = False
        self._face_app = None
        self.init_error: str | None = None
        try:
            from insightface.app import FaceAnalysis  # type: ignore

            app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
            app.prepare(ctx_id=0, det_size=(640, 640))
            self._face_app = app
            self.available = True
            self.init_error = None
        except Exception as exc:
            self._face_app = None
            self.available = False
            self.init_error = f"{type(exc).__name__}: {exc}"
            logger.exception("proctoring.face_engine.insightface_init_failed")

    def analyze(self, image_bgr: np.ndarray) -> FaceEngineResult:
        if self._face_app is None:
            raise RuntimeError("insightface_unavailable")
        h, w = image_bgr.shape[:2]
        if h <= 0 or w <= 0:
            return FaceEngineResult(0, 0.0, 1.0, None, None, 0.0, None, self.provider)
        faces = self._face_app.get(image_bgr) or []
        if not faces:
            return FaceEngineResult(0, 0.0, 1.0, None, None, 0.0, None, self.provider)
        primary = max(faces, key=lambda f: float(getattr(f, "det_score", 0.0) or 0.0))
        bbox = np.array(getattr(primary, "bbox", [0, 0, 0, 0]), dtype=float)
        x1, y1, x2, y2 = bbox.tolist()
        box = _FaceBox(
            max(0, int(x1)),
            max(0, int(y1)),
            max(1, int(max(1.0, x2 - x1))),
            max(1, int(max(1.0, y2 - y1))),
            float(getattr(primary, "det_score", 0.0) or 0.0),
        )
        bbox_ratio, center_offset_ratio = _bbox_metrics(box, w, h)
        pose = getattr(primary, "pose", None)
        yaw = float(pose[1]) if pose is not None and len(pose) > 1 else None
        pitch = float(pose[0]) if pose is not None and len(pose) > 0 else None
        embedding = _sanitize_embedding(getattr(primary, "normed_embedding", None))
        if not embedding:
            embedding = _sanitize_embedding(getattr(primary, "embedding", None))
        return FaceEngineResult(
            int(len(faces)),
            bbox_ratio,
            center_offset_ratio,
            yaw,
            pitch,
            box.confidence,
            embedding,
            self.provider,
        )


class DeepFaceEngine:
    def __init__(self, model_name: str, detector_backend: str) -> None:
        self.model_name = model_name
        self.detector_backend = detector_backend
        self.provider = f"deepface_{self.model_name.strip().lower() or 'arcface'}"
        self.available = False
        self._deepface = None
        try:
            from deepface import DeepFace  # type: ignore

            self._deepface = DeepFace
            self.available = True
        except Exception:
            self._deepface = None
            self.available = False

    @staticmethod
    def _parse_faces(raw_faces: Any, width: int, height: int) -> list[_FaceBox]:
        parsed: list[_FaceBox] = []
        if not isinstance(raw_faces, list):
            return parsed
        for item in raw_faces:
            if not isinstance(item, dict):
                continue
            area = item.get("facial_area") or {}
            if not isinstance(area, dict):
                continue
            x = int(area.get("x", 0) or 0)
            y = int(area.get("y", 0) or 0)
            fw = int(area.get("w", area.get("width", 0)) or 0)
            fh = int(area.get("h", area.get("height", 0)) or 0)
            if fw <= 0 or fh <= 0:
                continue
            x = max(0, min(width - 1, x))
            y = max(0, min(height - 1, y))
            fw = max(1, min(width - x, fw))
            fh = max(1, min(height - y, fh))
            confidence = float(item.get("confidence", 0.0) or 0.0)
            parsed.append(_FaceBox(x, y, fw, fh, confidence))
        return parsed

    def _embed_face_crop(self, face_crop_bgr: np.ndarray) -> list[float] | None:
        if self._deepface is None:
            return None
        reps = self._deepface.represent(
            img_path=face_crop_bgr,
            model_name=self.model_name,
            detector_backend="skip",
            enforce_detection=False,
        )
        if isinstance(reps, list) and reps:
            first = reps[0]
        elif isinstance(reps, dict):
            first = reps
        else:
            first = None
        if not isinstance(first, dict):
            return None
        return _sanitize_embedding(first.get("embedding"))

    def analyze(self, image_bgr: np.ndarray) -> FaceEngineResult:
        if self._deepface is None:
            raise RuntimeError("deepface_unavailable")
        h, w = image_bgr.shape[:2]
        if h <= 0 or w <= 0:
            return FaceEngineResult(0, 0.0, 1.0, None, None, 0.0, None, self.provider)
        raw_faces = self._deepface.extract_faces(
            img_path=image_bgr,
            detector_backend=self.detector_backend,
            enforce_detection=False,
            align=True,
        )
        faces = self._parse_faces(raw_faces, w, h)
        if not faces:
            return FaceEngineResult(0, 0.0, 1.0, None, None, 0.0, None, self.provider)
        primary = max(faces, key=lambda box: int(box.w) * int(box.h))
        bbox_ratio, center_offset_ratio = _bbox_metrics(primary, w, h)
        face_crop = _extract_face_crop(image_bgr, primary)
        embedding = self._embed_face_crop(face_crop)
        return FaceEngineResult(
            int(len(faces)),
            bbox_ratio,
            center_offset_ratio,
            None,
            None,
            primary.confidence,
            embedding,
            self.provider,
        )


class FaceEngine:
    """InsightFace-first engine with optional OpenCV runtime fallback diagnostics."""

    def __init__(self) -> None:
        self._mode = "insightface"
        self._fallback_enabled = bool(PROCTORING_ENGINE_FALLBACK_ENABLED)
        self._insight = InsightFaceEngine()
        self._opencv = OpenCvFallbackEngine("opencv_fallback")
        self._active_provider = self._resolve_default_provider()
        self._last_errors: list[str] = []

    def _resolve_default_provider(self) -> str:
        return self._insight.provider

    @property
    def provider(self) -> str:
        return self._active_provider

    def _ordered_engines(self) -> list[Any]:
        return [self._insight]

    @property
    def insightface_available(self) -> bool:
        return bool(getattr(self._insight, "available", False))

    @property
    def last_errors(self) -> list[str]:
        return list(self._last_errors)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "mode": self._mode,
            "insightface_available": self.insightface_available,
            "insightface_init_error": getattr(self._insight, "init_error", None),
            "fallback_enabled": self._fallback_enabled,
            "active_provider": self._active_provider,
            "last_errors": self.last_errors,
        }

    def analyze(self, image_bgr: np.ndarray) -> FaceEngineResult:
        h, w = image_bgr.shape[:2]
        if h <= 0 or w <= 0:
            return FaceEngineResult(0, 0.0, 1.0, None, None, 0.0, None, self.provider)

        errors: list[str] = []
        for engine in self._ordered_engines():
            if not bool(getattr(engine, "available", False)):
                init_error = getattr(engine, "init_error", None)
                errors.append(f"{getattr(engine, 'provider', 'unknown')}:unavailable{f':{init_error}' if init_error else ''}")
                continue
            try:
                result = engine.analyze(image_bgr)
                self._active_provider = result.provider
                self._last_errors = []
                return result
            except Exception as exc:
                errors.append(f"{getattr(engine, 'provider', 'unknown')}:{exc}")
                if not self._fallback_enabled:
                    break

        self._last_errors = errors
        if self._fallback_enabled:
            fallback_provider = "opencv_fallback_runtime" if errors else "opencv_fallback"
            runtime_fallback = OpenCvFallbackEngine(fallback_provider)
            result = runtime_fallback.analyze(image_bgr)
            self._active_provider = result.provider
            return result

        raise RuntimeError(f"face_engine_failed:{';'.join(errors) if errors else 'no_provider_available'}")

    @staticmethod
    def cosine_similarity(vec_a: list[float] | None, vec_b: list[float] | None) -> float:
        if not vec_a or not vec_b:
            return 0.0
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        if a.shape != b.shape:
            n = min(a.shape[0], b.shape[0])
            if n <= 0:
                return 0.0
            a = a[:n]
            b = b[:n]
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom <= 0:
            return 0.0
        return float(np.dot(a, b) / denom)


@lru_cache(maxsize=1)
def get_face_engine() -> FaceEngine:
    return FaceEngine()
