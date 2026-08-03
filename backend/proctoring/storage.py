from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def resolve_proctoring_upload_path(base_dir: Path, image_url: str) -> Path:
    raw = str(image_url or "").strip()
    if not raw:
        raise ValueError("image_url_required")
    filename = Path(raw).name
    if not filename:
        raise ValueError("invalid_image_url")
    file_path = (base_dir / filename).resolve()
    if not str(file_path).startswith(str(base_dir.resolve())):
        raise ValueError("invalid_image_path")
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError("image_not_found")
    return file_path


def read_image_bgr(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("invalid_image")
    return img
