from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EnrollmentCaptureRequest(BaseModel):
    enrollment_session_id: int
    sample_image_url: str
    sample_label: str | None = None
    pose_hint: str | None = None


class EnrollmentCaptureResponse(BaseModel):
    enrollment_session_id: int
    sample_id: int
    accepted: bool
    reason: str | None = None
    quality_score: float
    face_count: int
    face_box_ratio: float
    yaw: float | None = None
    pitch: float | None = None
    required_next_pose: str | None = None
    collected_count: int


class VerifyStartExamRequest(BaseModel):
    proctoring_session_id: int
    snapshot_image_url: str
    attempt_no: int = Field(default=1, ge=1)


class VerifyCheckRequest(BaseModel):
    proctoring_session_id: int
    snapshot_image_url: str
    context_reason: str | None = None


class VerifyResponse(BaseModel):
    verified: bool
    match_score: float | None = None
    threshold: float | None = None
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
