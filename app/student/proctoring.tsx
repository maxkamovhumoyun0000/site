"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useWebT } from "../ui/web-i18n";

type GenericRow = Record<string, any>;

type ProctoringStatusPayload = {
  user_id: number;
  proctoring_required: boolean;
  face_enrollment_required: boolean;
  face_profile_status: string;
  face_profile_version: number;
  face_enrolled_at?: string | null;
  face_last_verified_at?: string | null;
  face_verification_method?: string | null;
  face_match_threshold?: number;
  proctoring_block_reason?: string | null;
  proctoring_hold_until?: string | null;
};

type ProctoringSessionResponse = {
  session_id: number;
  status: string;
  test_type?: string;
  test_attempt_ref?: string | null;
  selfie_preview_required?: boolean;
  failure_reason?: string | null;
  penalty_applied?: boolean;
};

type EnrollmentPanelProps = {
  status: ProctoringStatusPayload | null;
  onCompleted?: (payload: GenericRow) => void;
};

type EnrollmentCaptureResult = {
  enrollment_session_id: number;
  sample_id: number;
  accepted: boolean;
  reason?: string | null;
  raw_reason?: string | null;
  quality_score: number;
  face_count: number;
  face_box_ratio: number;
  yaw?: number | null;
  pitch?: number | null;
  provider?: string | null;
  relaxed_accept?: boolean;
  center_offset_ratio?: number;
  pose_check?: string;
  quality_breakdown?: GenericRow;
  collected_count: number;
};

type EnrollmentStartResult = {
  enrollment_session_id?: number;
  enroll_min_samples?: number;
  enroll_max_samples?: number;
  scan_window_sec?: number;
};

type StudentTestProctoringProps = {
  active: boolean;
  completed?: boolean;
  initialSessionId?: number | null;
  testType: string;
  testAttemptRef?: string | null;
  testRoute?: string | null;
  onSessionReady?: (sessionId: number) => void;
  onVerificationStateChange?: (ready: boolean, reason?: string) => void;
  onTerminated?: (reason: string) => void;
  className?: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
const VERIFY_INTERVAL_SEC = Number(process.env.NEXT_PUBLIC_PROCTORING_VERIFY_INTERVAL_SEC || 6);
const FACE_MIN_BOX_RATIO = Number(process.env.NEXT_PUBLIC_PROCTORING_FACE_MIN_BOX_RATIO || 0.1);
const ENROLL_MIN_SAMPLES_FALLBACK = 3;
const ENROLL_MAX_SAMPLES_FALLBACK = 5;
const ENROLL_SCAN_WINDOW_SEC_FALLBACK = 6;
const ENROLL_CENTER_OFFSET_MAX = 0.55;
const ENROLL_LOCAL_CANDIDATE_LIMIT = 24;
const CAMERA_IDLE_RELEASE_MS = 90000;
const MEDIAPIPE_WASM_ROOT =
  process.env.NEXT_PUBLIC_PROCTORING_MEDIAPIPE_WASM_ROOT ||
  "/proctoring/mediapipe/wasm";
const MEDIAPIPE_MODEL_URL =
  process.env.NEXT_PUBLIC_PROCTORING_MEDIAPIPE_MODEL_URL ||
  "/proctoring/mediapipe/blaze_face_short_range.tflite";
const PROCTORING_FETCH_TIMEOUT_MS = 18000;
const PROCTORING_START_FETCH_TIMEOUT_MS = Math.max(15000, Number(process.env.NEXT_PUBLIC_PROCTORING_START_TIMEOUT_MS || 20000));
const PROCTORING_VERIFY_FETCH_TIMEOUT_MS = Math.max(20000, Number(process.env.NEXT_PUBLIC_PROCTORING_VERIFY_TIMEOUT_MS || 30000));
const PROCTORING_START_RETRY_DELAY_MS = 250;
const PROCTORING_CAMERA_PERMISSION_CACHE_KEY = "diamond_proctoring_camera_permission";
const PROCTORING_CLIENT_RETRY_ATTEMPTS = Math.max(1, Math.min(6, Number(process.env.NEXT_PUBLIC_PROCTORING_START_VERIFY_ATTEMPTS || 5)));
const PROCTORING_CLIENT_GRACE_SEC = Math.max(3, Number(process.env.NEXT_PUBLIC_PROCTORING_CLIENT_GRACE_SEC || 5));
const PROCTORING_PERMISSION_GRACE_SEC = Math.max(60, Number(process.env.NEXT_PUBLIC_PROCTORING_PERMISSION_GRACE_SEC || 60));
const PROCTORING_CLIENT_OFFLINE_GRACE_SEC = Math.max(PROCTORING_CLIENT_GRACE_SEC, Number(process.env.NEXT_PUBLIC_PROCTORING_OFFLINE_GRACE_SEC || 25));
const PROCTORING_FACE_MISMATCH_CONFIRMATION_LIMIT = Math.max(3, Number(process.env.NEXT_PUBLIC_PROCTORING_FACE_MISMATCH_STRIKES || 5));
const PROCTORING_LOCAL_DETECT_INTERVAL_MS = Math.max(300, Number(process.env.NEXT_PUBLIC_PROCTORING_LOCAL_DETECT_INTERVAL_MS || 350));
const PROCTORING_FALLBACK_REVERIFY_INTERVAL_MS = Math.max(10000, VERIFY_INTERVAL_SEC * 1000);
const PROCTORING_PERIODIC_VERIFY_INTERVAL_MS = Math.max(14000, VERIFY_INTERVAL_SEC * 1000);
const PROCTORING_RECOVERY_VERIFY_COOLDOWN_MS = Math.max(1200, Math.floor(PROCTORING_PERIODIC_VERIFY_INTERVAL_MS / 4));
const PROCTORING_FACE_RECOVERY_STABLE_MS = Math.max(600, Number(process.env.NEXT_PUBLIC_PROCTORING_FACE_RECOVERY_STABLE_MS || 900));
const PROCTORING_CRITICAL_VERIFY_REASONS = new Set([
  "EMBEDDING_MISSING",
  "PROFILE_EMBEDDING_MISSING",
  "INSIGHTFACE_PROVIDER_REQUIRED",
]);
const PROCTORING_START_FATAL_VERIFY_REASONS = new Set([
  "EMBEDDING_MISSING",
  "PROFILE_EMBEDDING_MISSING",
  "INSIGHTFACE_PROVIDER_REQUIRED",
]);

type DetectorFace = { x: number; y: number; width: number; height: number };
type DetectorAdapter = {
  provider: string;
  detect: (video: HTMLVideoElement) => Promise<DetectorFace[]>;
  close?: () => void;
};

type CameraPermissionState = "unknown" | "prompt" | "granted" | "denied";

function cachedCameraPermissionState(): CameraPermissionState {
  if (typeof window === "undefined") return "unknown";
  try {
    const cached = String(localStorage.getItem(PROCTORING_CAMERA_PERMISSION_CACHE_KEY) || "");
    if (cached === "granted" || cached === "prompt" || cached === "denied") return cached;
  } catch {
    // no-op
  }
  return "unknown";
}

function rememberCameraPermissionState(state: CameraPermissionState) {
  if (typeof window === "undefined") return;
  try {
    if (state === "granted") {
      localStorage.setItem(PROCTORING_CAMERA_PERMISSION_CACHE_KEY, "granted");
    } else if (state === "denied") {
      localStorage.removeItem(PROCTORING_CAMERA_PERMISSION_CACHE_KEY);
    }
  } catch {
    // no-op
  }
}

function getToken() {
  if (typeof window === "undefined") return "";
  return String(localStorage.getItem("diamond_token") || "");
}

function isBrowserOffline() {
  return typeof navigator !== "undefined" && navigator.onLine === false;
}

function cameraErrorCode(error: unknown) {
  const message = String((error as Error)?.message || "").toLowerCase();
  const name = String((error as any)?.name || "").toLowerCase();
  const combined = `${name} ${message}`;
  if (combined.includes("notallowederror") || combined.includes("permission") || combined.includes("denied")) return "camera_permission_denied";
  if (message.includes("secure_context_required")) return "camera_secure_context_required";
  if (message.includes("camera_video_not_ready")) return "camera_video_not_ready";
  if (message.includes("camera_frame_wait_timeout") || message.includes("camera_no_frames") || message.includes("camera_metadata_timeout")) return "camera_frame_wait_timeout";
  if (combined.includes("notfounderror") || combined.includes("devicesnotfounderror")) return "camera_not_found";
  if (combined.includes("notreadableerror") || combined.includes("trackstarterror")) return "camera_not_readable";
  if (combined.includes("overconstrainederror") || combined.includes("constraint")) return "camera_constraint_failed";
  if (message.includes("camera_api_unsupported")) return "camera_api_unsupported";
  if (combined.includes("permissions policy") || combined.includes("permission policy")) return "camera_policy_blocked";
  return "camera_start_failed";
}

function isCameraPermissionDeniedError(error: unknown) {
  return cameraErrorCode(error) === "camera_permission_denied";
}

function isTransientCameraStartupError(error: unknown) {
  const code = cameraErrorCode(error);
  return code === "camera_video_not_ready" || code === "camera_frame_wait_timeout" || code === "camera_not_readable" || code === "camera_constraint_failed";
}

function cameraDiagnosticDetails(error: unknown, extra?: GenericRow) {
  return {
    error_name: String((error as any)?.name || ""),
    error_message: String((error as Error)?.message || error || ""),
    permission_state: cameraSession.permission,
    secure_context: isCameraSecureContext(),
    online: typeof navigator === "undefined" ? true : navigator.onLine,
    user_agent: typeof navigator === "undefined" ? "" : navigator.userAgent,
    ...extra,
  };
}

function isTransientProctoringError(message: string) {
  const lowered = String(message || "").toLowerCase();
  return (
    lowered.includes("timed out") ||
    lowered.includes("timeout") ||
    lowered.includes("request failed") ||
    lowered.includes("failed to fetch") ||
    lowered.includes("network") ||
    lowered.includes("so'rov vaqti") ||
    lowered.includes("so‘rov vaqti") ||
    lowered.includes("tarmoq")
  );
}

function normalizeProctoringRequestError(message: string) {
  const lowered = String(message || "").toLowerCase();
  if (isBrowserOffline() || lowered.includes("offline") || lowered.includes("internet lost")) {
    return "Internet aloqasi yo'q. Ulanishni tekshirib qayta urinib ko'ring.";
  }
  if (lowered.includes("request timeout") || lowered.includes("timed out") || lowered.includes("network timeout")) {
    return "So'rov vaqti tugadi. Qayta urinib ko'ring.";
  }
  if (lowered.includes("request aborted")) {
    return "So'rov bekor qilindi. Qayta urinib ko'ring.";
  }
  if (lowered.includes("session expired") || lowered.includes("not authenticated") || lowered.includes("invalid token")) {
    return "Sessiya muddati tugagan. Qayta kiring.";
  }
  return String(message || "So'rov bajarilmadi.");
}

async function requestJson<T>(path: string, options?: { method?: string; body?: unknown; token?: string | null; signal?: AbortSignal; timeoutMs?: number }): Promise<T> {
  const controller = new AbortController();
  let abortedByExternal = false;
  const onSignalAbort = () => {
    abortedByExternal = true;
    controller.abort();
  };
  if (options?.signal) {
    if (options.signal.aborted) {
      abortedByExternal = true;
      controller.abort();
    } else {
      options.signal.addEventListener("abort", onSignalAbort, { once: true });
    }
  }
  const timeout = window.setTimeout(() => controller.abort(), Number(options?.timeoutMs || PROCTORING_FETCH_TIMEOUT_MS));
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options?.method || "GET",
      headers: {
        ...(options?.token ? { Authorization: `Bearer ${options.token}` } : {}),
        ...(options?.body ? { "Content-Type": "application/json" } : {}),
      },
      ...(options?.body ? { body: JSON.stringify(options.body) } : {}),
      signal: controller.signal,
    });
  } catch (error) {
    if (abortedByExternal) {
      throw new Error("Request aborted");
    }
    if (controller.signal.aborted) {
      throw new Error("Request timed out. Please try again.");
    }
    if (isBrowserOffline()) {
      throw new Error("Offline");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
    if (options?.signal) {
      options.signal.removeEventListener("abort", onSignalAbort);
    }
  }
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    if (text) {
      let parsedMessage = "";
      try {
        const parsed = JSON.parse(text) as { detail?: string; message?: string };
        parsedMessage = String(parsed.detail || parsed.message || "").trim();
      } catch {
        parsedMessage = "";
      }
      throw new Error(normalizeProctoringRequestError(parsedMessage || text));
    }
    throw new Error("So'rov bajarilmadi.");
  }
  return response.json();
}

async function uploadImage(path: string, file: File, token: string): Promise<{ url: string; raw?: GenericRow }> {
  const form = new FormData();
  form.append("file", file);
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), PROCTORING_VERIFY_FETCH_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
      signal: controller.signal,
    });
  } catch (error) {
    if (controller.signal.aborted) throw new Error("Request timed out. Please try again.");
    if (isBrowserOffline()) throw new Error("Offline");
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(normalizeProctoringRequestError(text || "Upload failed"));
  }
  const payload = await response.json().catch(() => ({}));
  const url = String(
    payload?.url ||
    payload?.image_url ||
    payload?.snapshot_image_url ||
    payload?.file_url ||
    payload?.path ||
    "",
  ).trim();
  if (!url) {
    throw new Error("snapshot_upload_missing_url");
  }
  return { url, raw: payload };
}

// Proctoring/FaceID has been removed from all test flows. This hook is kept for API
// compatibility with existing callers but always reports proctoring disabled / not required,
// so no FaceID setup prompts, camera permission cards, or enrollment panels ever render.
const PROCTORING_DISABLED_STATUS: ProctoringStatusPayload = {
  user_id: 0,
  proctoring_required: false,
  face_enrollment_required: false,
  face_profile_status: "active",
  face_profile_version: 0,
  proctoring_block_reason: null,
  proctoring_hold_until: null,
};

export function useStudentProctoringStatus(_enabled = true) {
  const [status, setStatus] = useState<ProctoringStatusPayload | null>(PROCTORING_DISABLED_STATUS);
  async function reload() {
    setStatus(PROCTORING_DISABLED_STATUS);
  }
  return { status, loading: false, error: "", reload, setStatus };
}

function dataUrlToFile(dataUrl: string, filename: string) {
  const parts = dataUrl.split(",");
  const meta = parts[0] || "";
  const base64 = parts[1] || "";
  const match = /data:(.*?);base64/.exec(meta);
  const mime = match?.[1] || "image/jpeg";
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new File([bytes], filename, { type: mime });
}

function isLocalHost(hostname: string) {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}

function isCameraSecureContext() {
  if (typeof window === "undefined") return false;
  return Boolean(window.isSecureContext || isLocalHost(window.location.hostname));
}

async function attachVideoStream(video: HTMLVideoElement | null, stream: MediaStream) {
  if (!video) return;
  video.srcObject = stream;
  video.muted = true;
  video.playsInline = true;
  video.autoplay = true;

  await new Promise<void>((resolve, reject) => {
    const timeout = window.setTimeout(() => reject(new Error("camera_metadata_timeout")), 4000);
    const done = () => {
      window.clearTimeout(timeout);
      resolve();
    };
    if (video.readyState >= 1) {
      done();
      return;
    }
    const onLoaded = () => {
      video.removeEventListener("loadedmetadata", onLoaded);
      done();
    };
    video.addEventListener("loadedmetadata", onLoaded);
  });

  await video.play().catch(() => null);
}

async function waitForVideoFrame(video: HTMLVideoElement | null, timeoutMs = 1500) {
  if (!video) return false;
  const hasFrame = () => video.readyState >= 2 && (video.videoWidth || 0) > 0 && (video.videoHeight || 0) > 0;
  if (hasFrame()) return true;
  return new Promise<boolean>((resolve) => {
    let settled = false;
    let frameHandle = 0;
    const cleanup = () => {
      video.removeEventListener("loadeddata", onReady);
      video.removeEventListener("canplay", onReady);
      window.clearTimeout(timeout);
      if (frameHandle) window.cancelAnimationFrame(frameHandle);
    };
    const finish = (value: boolean) => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(value);
    };
    const tick = () => {
      if (hasFrame()) {
        finish(true);
        return;
      }
      frameHandle = window.requestAnimationFrame(tick);
    };
    const onReady = () => {
      if (hasFrame()) finish(true);
    };
    const timeout = window.setTimeout(() => finish(hasFrame()), timeoutMs);
    video.addEventListener("loadeddata", onReady);
    video.addEventListener("canplay", onReady);
    tick();
  });
}

async function openUserFacingCamera() {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
    throw new Error("camera_api_unsupported");
  }
  if (!isCameraSecureContext()) {
    throw new Error("camera_secure_context_required");
  }
  const videoInputs = navigator.mediaDevices.enumerateDevices
    ? await navigator.mediaDevices.enumerateDevices()
      .then((devices) => devices.filter((device) => device.kind === "videoinput"))
      .catch(() => [] as MediaDeviceInfo[])
    : [];
  const tries: MediaStreamConstraints[] = [
    {
      video: {
        facingMode: { ideal: "user" },
        width: { ideal: 960, max: 1280 },
        height: { ideal: 540, max: 720 },
        frameRate: { ideal: 24, max: 30 },
      },
      audio: false,
    },
    {
      video: {
        facingMode: { ideal: "user" },
        width: { ideal: 640 },
        height: { ideal: 480 },
      },
      audio: false,
    },
    { video: { facingMode: "user" }, audio: false },
    ...videoInputs.slice(0, 3).map((device) => ({
      video: { deviceId: { exact: device.deviceId } },
      audio: false,
    } as MediaStreamConstraints)),
    { video: true, audio: false },
  ];

  let lastError: unknown = null;
  for (const constraints of tries) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      cameraSession.permission = "granted";
      rememberCameraPermissionState("granted");
      return stream;
    } catch (error) {
      lastError = error;
      const name = String((error as any)?.name || "").toLowerCase();
      const msg = String((error as Error)?.message || "").toLowerCase();
      const isPermissionError =
        name.includes("notallowed") ||
        name.includes("security") ||
        msg.includes("permission") ||
        msg.includes("denied");
      if (isPermissionError) {
        cameraSession.permission = "denied";
        rememberCameraPermissionState("denied");
        break;
      }
    }
  }
  if (videoInputs.length === 0 && cameraErrorCode(lastError) === "camera_not_found") {
    throw new Error("camera_not_found");
  }
  throw (lastError instanceof Error ? lastError : new Error("camera_open_failed"));
}

const cameraSession: {
  stream: MediaStream | null;
  opening: Promise<MediaStream> | null;
  permission: CameraPermissionState;
  refCount: number;
  releaseTimer: number | null;
} = {
  stream: null,
  opening: null,
  permission: cachedCameraPermissionState(),
  refCount: 0,
  releaseTimer: null,
};

function hasLiveVideo(stream: MediaStream | null) {
  return Boolean(stream?.getVideoTracks().some((track) => track.readyState === "live"));
}

let proctoringCaptureVideoElement: HTMLVideoElement | null = null;

function getOrCreateProctoringCaptureVideo() {
  if (typeof document === "undefined") return null;
  if (proctoringCaptureVideoElement?.isConnected) return proctoringCaptureVideoElement;
  const video = document.createElement("video");
  video.className = "proctoring-hidden-video-source";
  video.autoplay = true;
  video.muted = true;
  video.playsInline = true;
  video.setAttribute("playsinline", "true");
  video.setAttribute("webkit-playsinline", "true");
  video.setAttribute("aria-hidden", "true");
  video.tabIndex = -1;
  try {
    (video as HTMLVideoElement & { disablePictureInPicture?: boolean }).disablePictureInPicture = true;
  } catch {
    // no-op
  }
  document.body.appendChild(video);
  proctoringCaptureVideoElement = video;
  return video;
}

function clearCameraReleaseTimer() {
  if (cameraSession.releaseTimer) {
    window.clearTimeout(cameraSession.releaseTimer);
    cameraSession.releaseTimer = null;
  }
}

async function refreshCameraPermissionState() {
  if (typeof navigator === "undefined") return cameraSession.permission;
  const permissionsAny = (navigator as any).permissions;
  if (!permissionsAny?.query) return cameraSession.permission;
  try {
    const state = await permissionsAny.query({ name: "camera" });
    if (state?.state === "granted" || state?.state === "prompt" || state?.state === "denied") {
      const cached = cachedCameraPermissionState();
      if (state.state === "prompt" && (cameraSession.permission === "granted" || cached === "granted" || hasLiveVideo(cameraSession.stream))) {
        cameraSession.permission = "granted";
        rememberCameraPermissionState("granted");
      } else {
        cameraSession.permission = state.state;
        rememberCameraPermissionState(state.state);
      }
    }
  } catch {
    // no-op
  }
  return cameraSession.permission;
}

async function acquireSharedUserFacingCamera() {
  clearCameraReleaseTimer();
  cameraSession.refCount += 1;
  if (hasLiveVideo(cameraSession.stream)) {
    return cameraSession.stream as MediaStream;
  }
  if (cameraSession.opening) {
    return cameraSession.opening;
  }
  cameraSession.opening = openUserFacingCamera()
    .then((stream) => {
      cameraSession.stream = stream;
      cameraSession.permission = "granted";
      rememberCameraPermissionState("granted");
      return stream;
    })
    .finally(() => {
      cameraSession.opening = null;
    });
  return cameraSession.opening;
}

function stopCameraStreamNow() {
  if (cameraSession.stream) {
    cameraSession.stream.getTracks().forEach((track) => track.stop());
  }
  cameraSession.stream = null;
}

function releaseSharedUserFacingCamera() {
  cameraSession.refCount = Math.max(0, cameraSession.refCount - 1);
  if (cameraSession.refCount > 0) return;
  clearCameraReleaseTimer();
  cameraSession.releaseTimer = window.setTimeout(() => {
    if (cameraSession.refCount === 0) {
      stopCameraStreamNow();
    }
  }, CAMERA_IDLE_RELEASE_MS);
}

async function createShapeDetectionAdapter(): Promise<DetectorAdapter | null> {
  if (!(window as any).FaceDetector) return null;
  try {
    const detector = new (window as any).FaceDetector({ fastMode: true, maxDetectedFaces: 3 });
    return {
      provider: "shape_detection_face_detector",
      async detect(video: HTMLVideoElement) {
        const faces = await detector.detect(video);
        return (faces || []).map((f: any) => {
          const b = f.boundingBox || {};
          return {
            x: Number(b.x || 0),
            y: Number(b.y || 0),
            width: Number(b.width || 0),
            height: Number(b.height || 0),
          };
        });
      },
    };
  } catch {
    return null;
  }
}

async function createMediaPipeAdapter(): Promise<DetectorAdapter | null> {
  try {
    const vision: any = await import("@mediapipe/tasks-vision");
    if (!vision?.FilesetResolver || !vision?.FaceDetector) return null;
    const fileset = await vision.FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_ROOT);
    let detector: any = null;
    try {
      detector = await vision.FaceDetector.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MEDIAPIPE_MODEL_URL, delegate: "GPU" },
        runningMode: "VIDEO",
        minDetectionConfidence: 0.5,
      });
    } catch {
      detector = await vision.FaceDetector.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MEDIAPIPE_MODEL_URL, delegate: "CPU" },
        runningMode: "VIDEO",
        minDetectionConfidence: 0.5,
      });
    }
    if (!detector) return null;
    return {
      provider: "mediapipe_face_detector",
      async detect(video: HTMLVideoElement) {
        const ts = performance.now();
        const result = detector.detectForVideo(video, ts);
        const detections = Array.isArray(result?.detections) ? result.detections : [];
        return detections.map((item: any) => {
          const b = item?.boundingBox || {};
          return {
            x: Number(b.originX || 0),
            y: Number(b.originY || 0),
            width: Number(b.width || 0),
            height: Number(b.height || 0),
          };
        });
      },
      close() {
        try {
          detector.close?.();
        } catch {
          // no-op
        }
      },
    };
  } catch {
    return null;
  }
}

async function createBrowserDetectorAdapter(): Promise<DetectorAdapter | null> {
  const mediaPipe = await Promise.race<DetectorAdapter | null>([
    createMediaPipeAdapter(),
    new Promise<DetectorAdapter | null>((resolve) => window.setTimeout(() => resolve(null), 1400)),
  ]);
  if (mediaPipe) return mediaPipe;
  return createShapeDetectionAdapter();
}

async function detectFacesOnVideo(video: HTMLVideoElement, detector: DetectorAdapter | null): Promise<DetectorFace[]> {
  if (!detector) return [];
  return detector.detect(video);
}

function humanizeCameraError(error: unknown) {
  const message = String((error as Error)?.message || "").toLowerCase();
  const name = String((error as any)?.name || "").toLowerCase();
  const combined = `${name} ${message}`;
  if (message.includes("secure_context_required")) {
    return "Kamera faqat xavfsiz ulanishda ishlaydi (HTTPS). Iltimos saytni HTTPS orqali oching.";
  }
  if (message.includes("camera_metadata_timeout") || message.includes("camera_no_frames")) {
    return "Kamera ochildi, lekin video kadr kelmadi. Kamerani boshqa ilovadan bo'shatib qayta urinib ko'ring.";
  }
  if (combined.includes("notallowederror") || combined.includes("permission") || combined.includes("denied")) {
    return "Kamera ruxsati berilmagan. Brauzerda camera permission ni yoqing.";
  }
  if (message.includes("camera_permission_cooldown")) {
    return "Kamera ruxsati so'rovi yaqinda rad etildi. Qisqa kutib qayta urinib ko'ring.";
  }
  if (message.includes("camera_not_found") || combined.includes("notfounderror") || combined.includes("devicesnotfounderror")) {
    return "Bu qurilmada kamera topilmadi. Kamerasiz qurilmada proctoring test ishlamaydi.";
  }
  if (combined.includes("notreadableerror") || combined.includes("trackstarterror")) {
    return "Kameraga ulanish band. Boshqa ilovada kamera ishlayotgan bo'lishi mumkin.";
  }
  if (combined.includes("overconstrainederror") || combined.includes("constraint")) {
    return "Kamera parametrlari mos kelmadi. Qayta urinish tavsiya etiladi.";
  }
  if (message.includes("camera_api_unsupported")) {
    return "Bu brauzer kamerani qo'llab-quvvatlamaydi.";
  }
  if (combined.includes("permissions policy") || combined.includes("permission policy")) {
    return "Brauzer policy kamerani bloklagan. MiniAppni rasmiy HTTPS domenida oching yoki browser sozlamalarini tekshiring.";
  }
  return "Kamerani ishga tushirib bo'lmadi. Iltimos ruxsat va brauzer sozlamalarini tekshiring.";
}

function isLikelyCameraError(error: unknown) {
  const message = String((error as Error)?.message || "").toLowerCase();
  const name = String((error as any)?.name || "").toLowerCase();
  const combined = `${name} ${message}`;
  return (
    combined.includes("camera") ||
    combined.includes("media") ||
    combined.includes("permission") ||
    combined.includes("notallowederror") ||
    combined.includes("notreadableerror") ||
    combined.includes("notfounderror") ||
    combined.includes("overconstrainederror")
  );
}

export function StudentFaceEnrollmentPanel({ status, onCompleted }: EnrollmentPanelProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const enrollmentDetectorRef = useRef<DetectorAdapter | null>(null);
  const uploadLockRef = useRef(false);
  const scanFrameLockRef = useRef(false);
  const scanActiveRef = useRef(false);
  const completeLockRef = useRef(false);
  const completeAttemptsRef = useRef(0);
  const enrollmentSessionIdRef = useRef<number | null>(null);
  const busyRef = useRef(false);
  const snapshotsRef = useRef<Array<{ id: number; dataUrl: string }>>([]);
  const scanCandidatesRef = useRef<
    Array<{
      dataUrl: string;
      localScore: number;
      centerOffsetRatio: number;
      faceBoxRatio: number;
      sharpnessScore: number;
      capturedAt: number;
    }>
  >([]);
  const scanStartRef = useRef<number | null>(null);
  const sessionStartingRef = useRef(false);
  const sessionStartAbortRef = useRef<AbortController | null>(null);
  const scanRetryTimerRef = useRef<number | null>(null);
  const enrollmentBootedRef = useRef(false);
  const enrollmentCompletedRef = useRef(false);
  const scanInitSessionRef = useRef<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [snapshot, setSnapshot] = useState("");
  const [snapshots, setSnapshots] = useState<Array<{ id: number; dataUrl: string }>>([]);
  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [cameraPermissionState, setCameraPermissionState] = useState<CameraPermissionState>("unknown");
  const [enrollmentSessionId, setEnrollmentSessionId] = useState<number | null>(null);
  const [poseMessage, setPoseMessage] = useState("Yuz aniqlangach 10 soniyalik scan avtomatik boshlanadi.");
  const [scanRemainingSec, setScanRemainingSec] = useState<number | null>(null);
  const [scanActive, setScanActive] = useState(false);
  const [enrollMinSamples, setEnrollMinSamples] = useState(ENROLL_MIN_SAMPLES_FALLBACK);
  const [enrollMaxSamples, setEnrollMaxSamples] = useState(ENROLL_MAX_SAMPLES_FALLBACK);
  const [scanWindowSec, setScanWindowSec] = useState(ENROLL_SCAN_WINDOW_SEC_FALLBACK);
  const [completeRetryTick, setCompleteRetryTick] = useState(0);
  const [scanReadyTick, setScanReadyTick] = useState(0);
  const [enrollmentCompleted, setEnrollmentCompleted] = useState(false);
  const [sessionState, setSessionState] = useState<"idle" | "creating" | "ready" | "failed">("idle");
  const wizardStep = enrollmentCompleted ? 3 : !cameraEnabled ? 1 : snapshots.length < enrollMinSamples ? 2 : 3;
  const progressText = `${Math.min(snapshots.length, enrollMinSamples)}/${enrollMinSamples}`;

  useEffect(() => {
    enrollmentSessionIdRef.current = enrollmentSessionId;
  }, [enrollmentSessionId]);

  useEffect(() => {
    busyRef.current = busy;
  }, [busy]);

  useEffect(() => {
    snapshotsRef.current = snapshots;
  }, [snapshots]);

  useEffect(() => {
    scanActiveRef.current = scanActive;
  }, [scanActive]);

  function scheduleScanReadinessRetry(delayMs = 900) {
    if (scanRetryTimerRef.current) {
      window.clearTimeout(scanRetryTimerRef.current);
    }
    scanRetryTimerRef.current = window.setTimeout(() => {
      setScanReadyTick((value) => value + 1);
    }, Math.max(300, delayMs));
  }

  function normalizeMinSamples(raw: number | undefined) {
    const value = Math.max(1, Number(raw || 0));
    return value || ENROLL_MIN_SAMPLES_FALLBACK;
  }

  function normalizeMaxSamples(raw: number | undefined, minSamples: number) {
    const value = Math.max(minSamples, Number(raw || 0));
    return value || Math.max(minSamples, ENROLL_MAX_SAMPLES_FALLBACK);
  }

  function normalizeScanWindow(raw: number | undefined) {
    const value = Math.max(2, Number(raw || 0));
    return value || ENROLL_SCAN_WINDOW_SEC_FALLBACK;
  }

  function clamp01(value: number) {
    if (!Number.isFinite(value)) return 0;
    if (value <= 0) return 0;
    if (value >= 1) return 1;
    return value;
  }

  function humanizeEnrollmentReason(reason?: string | null) {
    const normalized = String(reason || "").trim().toUpperCase();
    if (!normalized) return "Server sample ni qabul qilmadi, qayta urinmoqda...";
    if (normalized === "NO_FACE") return "Yuz topilmadi, kameraga yaqinroq turing.";
    if (normalized === "MULTIPLE_FACES") return "Faqat bitta odam kamerada bo'lsin.";
    if (normalized === "FACE_TOO_SMALL") return "Yuz kichik ko'rinmoqda, kameraga yaqinroq turing.";
    if (normalized === "FACE_NOT_CENTERED") return "Yuz ko'rindi, sifatliroq kadr uchun kameraga qarab turing.";
    if (normalized === "LOW_QUALITY") return "Rasm sifati past, yorug'roq joyda turing.";
    if (normalized === "ENGINE_ERROR" || normalized === "EMBEDDING_MISSING") {
      return "Face analiz xizmati band. Fallback bilan davom etmoqda, iltimos kameraga qarab turing.";
    }
    if (normalized === "INSIGHTFACE_PROVIDER_REQUIRED") {
      return "Server FaceID modeli tayyor emas. Iltimos birozdan keyin qayta urinib ko'ring.";
    }
    return `Qabul qilinmadi (${normalized}), qayta urinmoqda...`;
  }

  function humanizeEnrollmentError(message: string) {
    const lowered = String(message || "").toLowerCase();
    if (lowered.includes("internet sekin")) {
      return "So'rov vaqti tugadi. Qayta urinib ko'ring.";
    }
    if (lowered.includes("request aborted")) {
      return "So'rov bekor qilindi. Qayta urinib ko'ring.";
    }
    if (lowered.includes("at least") && lowered.includes("valid samples")) {
      return "Namuna yetarli emas, tizim avtomatik davom etadi.";
    }
    if (lowered.includes("could not generate a valid face embedding")) {
      return "Yuz modeli yaratilolmadi, qayta urinish davom etmoqda.";
    }
    if (lowered.includes("enrollment session not found")) {
      return "Enrollment session topilmadi, qayta yaratilmoqda.";
    }
    if (lowered.includes("enrollment session is not active")) {
      return "Enrollment session yopilgan, yangidan boshlanmoqda.";
    }
    if (lowered.includes("already_enrolled")) {
      return "Bu account uchun Face ID allaqachon ro'yxatdan o'tgan.";
    }
    if (lowered.includes("session expired")) {
      return "Sessiya muddati tugagan. Qayta kiring.";
    }
    if (lowered.includes("engine_error") || lowered.includes("embedding_missing")) {
      return "Face analiz vaqtincha band. Tizim fallback bilan qayta urinmoqda.";
    }
    if (lowered.includes("internal server error")) {
      return "Serverda vaqtinchalik xatolik. Tizim qayta urinmoqda.";
    }
    return message || "Face enrollmentda vaqtinchalik xatolik.";
  }

  function markEnrollmentCompleted(payload: GenericRow) {
    if (enrollmentCompletedRef.current) return;
    enrollmentCompletedRef.current = true;
    completeLockRef.current = true;
    scanActiveRef.current = false;
    busyRef.current = false;
    uploadLockRef.current = false;
    setEnrollmentCompleted(true);
    setBusy(false);
    setCameraEnabled(false);
    setScanActive(false);
    setScanRemainingSec(null);
    setSessionState("ready");
    setPoseMessage("FaceID tayyor. Dashboard ochilmoqda...");
    try {
      releaseSharedUserFacingCamera();
    } catch {
      // no-op
    }
    streamRef.current = null;
    onCompleted?.(payload);
  }

  async function startEnrollmentSession() {
    const token = getToken();
    if (enrollmentCompletedRef.current) return true;
    if (!token || sessionStartingRef.current) return false;
    if (enrollmentSessionIdRef.current) {
      setSessionState("ready");
      return true;
    }
    sessionStartingRef.current = true;
    setSessionState("creating");
    setPoseMessage("FaceID sozlanmoqda...");
    setError("");
    const controller = new AbortController();
    sessionStartAbortRef.current = controller;
    try {
      const started = await requestJson<EnrollmentStartResult>("/student/proctoring/enrollment/start", {
        method: "POST",
        token,
        signal: controller.signal,
        body: {
          device_id: navigator.userAgent,
          platform: navigator.platform,
          browser: navigator.userAgent,
        },
      });
      const nextMin = normalizeMinSamples(started.enroll_min_samples);
      const nextMax = normalizeMaxSamples(started.enroll_max_samples, nextMin);
      const nextScanWindow = normalizeScanWindow(started.scan_window_sec);
      setEnrollMinSamples(nextMin);
      setEnrollMaxSamples(nextMax);
      setScanWindowSec(nextScanWindow);
      const nextSessionId = Number(started.enrollment_session_id || 0) || null;
      setEnrollmentSessionId(nextSessionId);
      if (nextSessionId) {
        scanInitSessionRef.current = null;
        setSessionState("ready");
        setPoseMessage("Enrollment session tayyor. Yuz aniqlangach scan avtomatik boshlanadi.");
        return true;
      }
      setSessionState("failed");
      setError("FaceID sessiyasi yaratilmadi. Qayta urinib ko‘ring.");
      return false;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Enrollment sessionni ochib bo'lmadi.";
      if (String(message).toLowerCase().includes("already_enrolled")) {
        setError("Bu account uchun Face ID allaqachon tayyor. Holat yangilanmoqda...");
        setPoseMessage("Face ID tayyor. Keyingi bosqichga o'tilmoqda...");
        setCameraEnabled(false);
        setSessionState("ready");
        markEnrollmentCompleted({ already_enrolled: true });
        return true;
      }
      setError(humanizeEnrollmentError(message));
      setSessionState("failed");
      setPoseMessage("FaceID sessiyasi yaratilmadi. Qayta urinib ko‘ring.");
      return false;
    } finally {
      sessionStartingRef.current = false;
      sessionStartAbortRef.current = null;
    }
  }

  async function startEnrollmentCamera() {
    const token = getToken();
    if (enrollmentCompletedRef.current) return;
    if (!token) return;
    setError("");
    setPoseMessage("Kamera tayyorlanmoqda...");
    try {
      await refreshCameraPermissionState();
      setCameraPermissionState(cameraSession.permission);
      const stream = await acquireSharedUserFacingCamera();
      streamRef.current = stream;
      await attachVideoStream(videoRef.current, stream);
      if (!enrollmentDetectorRef.current) {
        enrollmentDetectorRef.current = await createBrowserDetectorAdapter();
      }
      setCameraPermissionState(cameraSession.permission);
      setCameraEnabled(true);
      setPoseMessage(`Kamera tayyor. Yuz tekshirilmoqda...`);
      const started = await startEnrollmentSession();
      if (!started) {
        return;
      }
      setPoseMessage(`Kamera tayyor. Yuz aniqlangach ${scanWindowSec} soniyalik scan boshlanadi.`);
    } catch (err) {
      if (isLikelyCameraError(err)) {
        setCameraEnabled(false);
        setCameraPermissionState("denied");
        setError(humanizeCameraError(err));
      } else {
        const message = err instanceof Error ? err.message : "Face enrollment sessionni boshlab bo'lmadi.";
        setError(humanizeEnrollmentError(message || "Face enrollment sessionni boshlab bo'lmadi."));
        setSessionState("failed");
        setPoseMessage("FaceID sessiyasi yaratilmadi. Qayta urinib ko‘ring.");
      }
    }
  }

  useEffect(() => {
    if (enrollmentBootedRef.current) return;
    enrollmentBootedRef.current = true;
    startEnrollmentCamera().catch(() => null);
    return () => {
      if (scanRetryTimerRef.current) {
        window.clearTimeout(scanRetryTimerRef.current);
        scanRetryTimerRef.current = null;
      }
      if (sessionStartAbortRef.current) {
        sessionStartAbortRef.current.abort();
        sessionStartAbortRef.current = null;
      }
      streamRef.current = null;
      releaseSharedUserFacingCamera();
      enrollmentDetectorRef.current?.close?.();
      enrollmentDetectorRef.current = null;
      scanStartRef.current = null;
      scanCandidatesRef.current = [];
      scanActiveRef.current = false;
      sessionStartingRef.current = false;
      setScanRemainingSec(null);
    };
  }, []);

  function faceCenterOffset(box: { x: number; y: number; width: number; height: number }, vw: number, vh: number) {
    const cx = (box.x + (box.width / 2)) / Math.max(1, vw);
    const cy = (box.y + (box.height / 2)) / Math.max(1, vh);
    return Math.sqrt(((cx - 0.5) ** 2) + ((cy - 0.5) ** 2));
  }

  function captureDataUrl() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return "";
    const width = video.videoWidth || 640;
    const height = video.videoHeight || 480;
    const maxSide = 960;
    const scale = Math.min(1, maxSide / Math.max(width, height));
    const targetWidth = Math.max(320, Math.round(width * scale));
    const targetHeight = Math.max(240, Math.round(height * scale));
    canvas.width = targetWidth;
    canvas.height = targetHeight;
    const context = canvas.getContext("2d");
    if (!context) return "";
    context.drawImage(video, 0, 0, targetWidth, targetHeight);
    return canvas.toDataURL("image/jpeg", 0.88);
  }

  function estimateSharpnessScore() {
    const canvas = canvasRef.current;
    if (!canvas) return 0;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) return 0;
    const width = canvas.width || 0;
    const height = canvas.height || 0;
    if (width <= 2 || height <= 2) return 0;
    const imageData = context.getImageData(0, 0, width, height).data;
    const step = Math.max(2, Math.floor(Math.max(width, height) / 180));
    let totalGradient = 0;
    let count = 0;
    const luminance = (idx: number) =>
      (imageData[idx] * 0.299) + (imageData[idx + 1] * 0.587) + (imageData[idx + 2] * 0.114);
    for (let y = 0; y < height - step; y += step) {
      for (let x = 0; x < width - step; x += step) {
        const i = ((y * width) + x) * 4;
        const right = ((y * width) + (x + step)) * 4;
        const down = (((y + step) * width) + x) * 4;
        const l = luminance(i);
        const lr = luminance(right);
        const ld = luminance(down);
        totalGradient += Math.abs(l - lr) + Math.abs(l - ld);
        count += 2;
      }
    }
    if (!count) return 0;
    const normalized = (totalGradient / count) / 255;
    return clamp01(normalized / 0.12);
  }

  async function beginScanWindowWhenReady() {
    if (!videoRef.current || scanActiveRef.current) return;
    const activeSessionId = enrollmentSessionIdRef.current;
    if (!activeSessionId || sessionState !== "ready") return;
    if (scanInitSessionRef.current === activeSessionId) return;
    const detector = enrollmentDetectorRef.current;
    if (detector) {
      const faces = await detectFacesOnVideo(videoRef.current, detector);
      if (faces.length !== 1) {
        setPoseMessage(faces.length > 1 ? "Faqat account egasi kamerada bo'lsin." : "Yuz aniqlanmadi. Scan hali boshlanmaydi.");
        scheduleScanReadinessRetry(900);
        return;
      }
      const primary = faces[0];
      const vw = videoRef.current.videoWidth || 1;
      const vh = videoRef.current.videoHeight || 1;
      const boxRatio = (Number(primary.width || 0) * Number(primary.height || 0)) / Math.max(1, vw * vh);
      if (boxRatio < FACE_MIN_BOX_RATIO) {
        setPoseMessage("Yuz kichik ko'rinmoqda, kameraga yaqinroq turing. Scan hali boshlanmaydi.");
        scheduleScanReadinessRetry(900);
        return;
      }
    }
    scanInitSessionRef.current = activeSessionId;
    scanCandidatesRef.current = [];
    scanStartRef.current = Date.now();
    scanActiveRef.current = true;
    setScanRemainingSec(scanWindowSec);
    setScanActive(true);
    setPoseMessage(`Scan boshlandi (${scanWindowSec}s). Kameraga qarab turing.`);
  }

  async function collectCandidateFrame() {
    if (!cameraEnabled || !videoRef.current || !canvasRef.current) return;
    if (!scanActiveRef.current || scanFrameLockRef.current) return;
    scanFrameLockRef.current = true;
    try {
      const detector = enrollmentDetectorRef.current;
      let boxRatio = FACE_MIN_BOX_RATIO;
      let centerOffsetRatio = 0.0;
      if (detector) {
        const faces = await detectFacesOnVideo(videoRef.current, detector);
        if (faces.length !== 1) {
          setPoseMessage(faces.length > 1 ? "Faqat account egasi kamerada bo'lsin." : "Yuz topilmadi, scan davom etmaydi.");
          return;
        }
        const primary = faces[0];
        const vw = videoRef.current.videoWidth || 1;
        const vh = videoRef.current.videoHeight || 1;
        boxRatio = (Number(primary.width || 0) * Number(primary.height || 0)) / Math.max(1, vw * vh);
        centerOffsetRatio = faceCenterOffset(primary, vw, vh);
        if (boxRatio < FACE_MIN_BOX_RATIO) {
          setPoseMessage("Yuz kichik ko'rinmoqda, kameraga yaqinroq turing.");
          return;
        }
      } else {
        // Detector bo'lmasa ham timed scan to'xtab qolmasin: server-side validation final gate bo'ladi.
        setPoseMessage("Face detector yuklanmadi, server tekshiruvi bilan davom etmoqda...");
      }

      const imageData = captureDataUrl();
      if (!imageData) {
        setPoseMessage("Kadr olinmadi, qayta urinmoqda...");
        return;
      }
      const sharpnessScore = estimateSharpnessScore();
      const sizeScore = clamp01((boxRatio - FACE_MIN_BOX_RATIO) / Math.max(0.01, 0.40 - FACE_MIN_BOX_RATIO));
      const centerScore = clamp01(1 - (centerOffsetRatio / ENROLL_CENTER_OFFSET_MAX));
      const localScore = (sizeScore * 0.55) + (sharpnessScore * 0.30) + (centerScore * 0.15);
      const next = [
        ...scanCandidatesRef.current,
        {
          dataUrl: imageData,
          localScore,
          centerOffsetRatio,
          faceBoxRatio: boxRatio,
          sharpnessScore,
          capturedAt: Date.now(),
        },
      ]
        .sort((a, b) => b.localScore - a.localScore)
        .slice(0, ENROLL_LOCAL_CANDIDATE_LIMIT);
      scanCandidatesRef.current = next;
      setSnapshot(imageData);
      setPoseMessage(`Skanerlash davom etmoqda... (${next.length} candidate)`);
    } finally {
      scanFrameLockRef.current = false;
    }
  }

  async function flushScanCandidates() {
    const token = getToken();
    const activeSessionId = enrollmentSessionIdRef.current;
    if (!token || !activeSessionId) {
      setPoseMessage("Enrollment session tayyorlanmoqda...");
      return;
    }
    if (uploadLockRef.current) return;
    const existingCount = snapshotsRef.current.length;
    const allowedToStore = Math.max(0, enrollMaxSamples - existingCount);
    if (allowedToStore <= 0) return;
    const selected = scanCandidatesRef.current
      .slice(0, allowedToStore)
      .sort((a, b) => b.localScore - a.localScore);
    if (!selected.length) {
      setPoseMessage("Sifatli frame topilmadi, timed scan qayta boshlanadi.");
      return;
    }
    uploadLockRef.current = true;
    setBusy(true);
    setError("");
    let acceptedCount = 0;
    let lastAccepted: string | null = null;
    try {
      for (const candidate of selected) {
        if (snapshotsRef.current.length >= enrollMaxSamples) break;
        const file = dataUrlToFile(candidate.dataUrl, `face-enrollment-${Date.now()}.jpg`);
        setPoseMessage("Eng yaxshi frame serverga yuborilmoqda...");
        const uploaded = await uploadImage("/student/proctoring/upload-image", file, token);
        const captured = await requestJson<EnrollmentCaptureResult>("/student/proctoring/enrollment/capture", {
          method: "POST",
          token,
          body: {
            enrollment_session_id: activeSessionId,
            sample_image_url: uploaded.url,
            sample_label: `AUTO_SCAN_${snapshotsRef.current.length + 1}`,
            pose_hint: "AUTO",
          },
        });
        if (!captured.accepted) {
          setPoseMessage(humanizeEnrollmentReason(captured.reason));
          continue;
        }
        const next = [...snapshotsRef.current, { id: captured.sample_id, dataUrl: candidate.dataUrl }];
        snapshotsRef.current = next;
        setSnapshots(next);
        setSnapshot(candidate.dataUrl);
        acceptedCount += 1;
        lastAccepted = candidate.dataUrl;
      }
      if (acceptedCount <= 0) {
        setPoseMessage("Skan natijasi qabul qilinmadi, tizim qayta scan qiladi.");
        return;
      }
      if (lastAccepted) {
        setSnapshot(lastAccepted);
      }
      const total = snapshotsRef.current.length;
      if (total >= enrollMinSamples) {
        setPoseMessage("Yetarli sample yig'ildi. Face ID avtomatik yakunlanmoqda...");
      } else {
        setPoseMessage(`Sample qabul qilindi (${total}/${enrollMinSamples}). Timed scan davom etadi.`);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Face enrollment failed";
      setError(humanizeEnrollmentError(message));
      setPoseMessage("Sample yuborishda xatolik, qayta urinmoqda...");
    } finally {
      setBusy(false);
      uploadLockRef.current = false;
    }
  }

  async function submitEnrollment(): Promise<boolean> {
    if (enrollmentCompletedRef.current) return true;
    const token = getToken();
    const currentSamples = snapshotsRef.current;
    const reference = currentSamples[0]?.dataUrl || snapshot;
    const activeSessionId = enrollmentSessionIdRef.current;
    if (!token || !reference || !activeSessionId) return false;
    setBusy(true);
    setError("");
    try {
      setPoseMessage("Yakuniy model tayyorlanmoqda...");
      const file = dataUrlToFile(reference, `face-enrollment-final-${Date.now()}.jpg`);
      const uploaded = await uploadImage("/student/proctoring/upload-image", file, token);
      const payload = await requestJson<GenericRow>("/student/proctoring/enrollment/complete", {
        method: "POST",
        token,
        body: {
          enrollment_session_id: activeSessionId,
          sample_ids: currentSamples.map((s) => s.id),
          reference_image_url: uploaded.url,
          capture_device_info: JSON.stringify({
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            width: window.innerWidth,
            height: window.innerHeight,
          }),
          verification_method: "selfie_liveness",
          embedding_model: "insightface_onnx",
          liveness_model: `automatic_scan_${scanWindowSec}s`,
          device_id: navigator.userAgent,
          platform: navigator.platform,
          browser: navigator.userAgent,
        },
      });
      markEnrollmentCompleted(payload);
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Face enrollment failed";
      setError(humanizeEnrollmentError(message));
      setPoseMessage("Yakunlashda xatolik, qayta urinmoqda...");
      return false;
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (enrollmentCompletedRef.current) return;
    if (!cameraEnabled || !enrollmentSessionIdRef.current || sessionState !== "ready") return;
    if (busy || uploadLockRef.current || completeLockRef.current) return;
    if (snapshotsRef.current.length >= enrollMinSamples) return;
    if (scanActiveRef.current) return;
    beginScanWindowWhenReady().catch(() => {
      setPoseMessage("Yuzni tekshirib bo'lmadi, qayta urinmoqda...");
      scheduleScanReadinessRetry(900);
    });
  }, [cameraEnabled, enrollmentSessionId, busy, snapshots.length, enrollMinSamples, scanWindowSec, scanReadyTick, sessionState]);

  useEffect(() => {
    if (!scanActive) return;
    const timer = window.setInterval(() => {
      if (!scanActiveRef.current) return;
      const startedAt = scanStartRef.current || Date.now();
      const elapsedMs = Date.now() - startedAt;
      const remaining = Math.max(0, Math.ceil((scanWindowSec * 1000 - elapsedMs) / 1000));
      setScanRemainingSec(remaining);
      if (elapsedMs >= scanWindowSec * 1000) {
        scanActiveRef.current = false;
        setScanActive(false);
        setScanRemainingSec(0);
        flushScanCandidates()
          .catch(() => null)
          .finally(() => {
            scanCandidatesRef.current = [];
            scanStartRef.current = null;
            scanInitSessionRef.current = null;
            window.setTimeout(() => setScanRemainingSec(null), 300);
          });
        return;
      }
      if (busyRef.current || uploadLockRef.current) return;
      collectCandidateFrame().catch(() => null);
    }, 280);
    return () => window.clearInterval(timer);
  }, [scanActive, scanWindowSec]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (enrollmentCompletedRef.current) return;
    if (snapshots.length < enrollMinSamples) {
      completeAttemptsRef.current = 0;
      return;
    }
    if (busy || completeLockRef.current) return;
    if (completeAttemptsRef.current >= 3) {
      setPoseMessage("Yakunlashda xatolik davom etmoqda. Sahifani yangilab qayta urinib ko'ring.");
      return;
    }
    completeLockRef.current = true;
    completeAttemptsRef.current += 1;
    submitEnrollment()
      .then((completedOk) => {
        if (!completedOk && completeAttemptsRef.current < 3) {
          window.setTimeout(() => setCompleteRetryTick((value) => value + 1), 1800);
        }
      })
      .finally(() => {
        if (!enrollmentCompletedRef.current) {
          completeLockRef.current = false;
        }
      });
  }, [snapshots.length, busy, completeRetryTick, enrollMinSamples]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="bg-white dark:bg-navy-900/50 rounded-[2rem] shadow-premium border border-line dark:border-white/10 p-6 md:p-8 accent proctoring-enrollment">
      <div className="enroll-header">
        <div className="enroll-icon" aria-hidden="true">📷</div>
        <h2>Face ID Setup</h2>
        <p>Yuz aniqlangach tizim {scanWindowSec} soniyalik scan qiladi va eng yaxshi frame’larni avtomatik saqlaydi.</p>
      </div>
      <div className="enroll-steps" aria-label={`Step ${wizardStep} of 3`}>
        <span className={`enroll-step-dot ${wizardStep >= 1 ? "active" : ""}`} />
        <span className={`enroll-step-dot ${wizardStep >= 2 ? "active" : ""}`} />
        <span className={`enroll-step-dot ${wizardStep >= 3 ? "active" : ""}`} />
      </div>
      {status?.proctoring_block_reason ? <div className="proctoring-block-alert">{status.proctoring_block_reason}</div> : null}
      {error ? <div className="error-box">{error}</div> : null}
      <div className="enroll-camera-area">
        <div className="enroll-camera-ring">
          <video ref={videoRef} className="proctoring-video" autoPlay muted playsInline />
          <div className="enroll-ring-overlay" aria-live="polite">
            <span className="enroll-ring-progress">{progressText}</span>
            {scanRemainingSec !== null ? <span className="enroll-ring-countdown">SCAN: {scanRemainingSec}s</span> : null}
            <span className="enroll-ring-status">{poseMessage}</span>
          </div>
        </div>
        <canvas ref={canvasRef} hidden />
      </div>
      <div className="enroll-instructions">
        <div className="enroll-instruction-item">
          <span className="enroll-instruction-num">1</span>
          <span>Kameraga bir marta ruxsat bering (session davomida qayta ishlatiladi)</span>
        </div>
        <div className="enroll-instruction-item">
          <span className="enroll-instruction-num">2</span>
          <span>{scanWindowSec} soniya kameraga qarab turing, yuz to'liq va yirik ko'rinsin</span>
        </div>
        <div className="enroll-instruction-item">
          <span className="enroll-instruction-num">3</span>
          <span>Tizim up to {enrollMaxSamples} best sample saqlaydi, {enrollMinSamples} ta bo'lgach avtomatik yakunlanadi</span>
        </div>
      </div>
      {cameraPermissionState === "denied" ? (
        <div className="info-box">Kamera ruxsati o'chirilgan. Brauzer/telefon sozlamasidan camera permissionni yoqing.</div>
      ) : null}
      {!cameraEnabled ? (
        <div className="enroll-actions">
          <button className="btn btn-soft" onClick={() => startEnrollmentCamera()} disabled={busy}>
            Kamerani qayta yoqish
          </button>
        </div>
      ) : null}
      {cameraEnabled && sessionState === "failed" ? (
        <div className="enroll-actions">
          <button
            className="btn btn-primary"
            onClick={() => startEnrollmentSession().catch(() => null)}
            disabled={busy || sessionStartingRef.current}
          >
            {sessionStartingRef.current ? "FaceID sozlanmoqda..." : "FaceID sessiyasini qayta yaratish"}
          </button>
        </div>
      ) : null}
    </section>
  );
}

export function StudentTestProctoring({
  active,
  completed = false,
  initialSessionId = null,
  testType,
  testAttemptRef,
  testRoute,
  onSessionReady,
  onVerificationStateChange,
  onTerminated,
  className = "",
}: StudentTestProctoringProps) {
  const tt = useWebT();
  const sourceVideoRef = useRef<HTMLVideoElement | null>(null);
  const previewVideoRef = useRef<HTMLVideoElement | null>(null);
  const [mounted, setMounted] = useState(false);
  const streamRef = useRef<MediaStream | null>(null);
  const detectorRef = useRef<DetectorAdapter | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(() => Number(initialSessionId || 0) || null);
  const [statusText, setStatusText] = useState("No face");
  const [fatalError, setFatalError] = useState("");
  const [cameraError, setCameraError] = useState("");
  const [cameraReady, setCameraReady] = useState(false);
  const [startVerified, setStartVerified] = useState(false);
  const [monitorState, setMonitorState] = useState<"ok" | "grace" | "error">("grace");
  const [startupStage, setStartupStage] = useState<
    "idle" | "session" | "camera" | "verifying" | "retrying" | "ready" | "failed"
  >("idle");
  const [graceRemainingSec, setGraceRemainingSec] = useState<number | null>(null);
  const [online, setOnline] = useState<boolean>(() => (typeof navigator === "undefined" ? true : navigator.onLine));
  const [sessionRetryTick, setSessionRetryTick] = useState(0);
  const [verifyRetryTick, setVerifyRetryTick] = useState(0);
  const [cameraRetryTick, setCameraRetryTick] = useState(0);
  const cameraStartingRef = useRef(false);
  const finishedRef = useRef(false);
  const missingRef = useRef(false);
  const multipleFaceRef = useRef(false);
  const tooSmallRef = useRef(false);
  const lookingAwayRef = useRef(false);
  const hiddenRef = useRef(false);
  const internetLostRef = useRef(false);
  const fullscreenLostRef = useRef(false);
  const fallbackModeRef = useRef(false);
  const verifyingRef = useRef(false);
  const activeRef = useRef(active);
  const completedRef = useRef(Boolean(completed));
  const sessionIdRef = useRef<number | null>(Number(initialSessionId || 0) || null);
  const onSessionReadyRef = useRef(onSessionReady);
  const onVerificationStateChangeRef = useRef(onVerificationStateChange);
  const onTerminatedRef = useRef(onTerminated);
  const externalVerificationReadyRef = useRef(false);
  const sessionStartInFlightRef = useRef<Promise<number | null> | null>(null);
  const sessionStartAbortRef = useRef<AbortController | null>(null);
  const mismatchStrikeRef = useRef(0);
  const lastValidFaceAtRef = useRef(0);
  const graceTimeoutRef = useRef<number | null>(null);
  const graceTickerRef = useRef<number | null>(null);
  const graceTimeoutEventRef = useRef<GenericRow | null>(null);
  const permissionGraceStartedAtRef = useRef<number>(0);
  const eventQueueRef = useRef<Array<{ events: GenericRow[]; snapshots: GenericRow[] }>>([]);
  const eventFlushInFlightRef = useRef(false);
  const recoveryVerifyInFlightRef = useRef(false);
  const serverVerifyInFlightRef = useRef(false);
  const lastServerVerifyAtRef = useRef(0);
  const lastFallbackVerifyAtRef = useRef(0);
  const recoveryStableSinceRef = useRef(0);
  const retryTimerRef = useRef<number | null>(null);

  useEffect(() => {
    onSessionReadyRef.current = onSessionReady;
    onVerificationStateChangeRef.current = onVerificationStateChange;
    onTerminatedRef.current = onTerminated;
  }, [onSessionReady, onTerminated, onVerificationStateChange]);

  useEffect(() => {
    activeRef.current = active;
    completedRef.current = Boolean(completed);
    sessionIdRef.current = sessionId;
  }, [active, completed, sessionId]);

  function setExternalVerificationReady(ready: boolean, reason?: string) {
    if (externalVerificationReadyRef.current === ready) return;
    externalVerificationReadyRef.current = ready;
    onVerificationStateChangeRef.current?.(ready, reason);
  }

  function beginServerVerify(minIntervalMs = PROCTORING_RECOVERY_VERIFY_COOLDOWN_MS, force = false) {
    const now = Date.now();
    if (serverVerifyInFlightRef.current) return false;
    if (!force && lastServerVerifyAtRef.current && now - lastServerVerifyAtRef.current < minIntervalMs) return false;
    serverVerifyInFlightRef.current = true;
    lastServerVerifyAtRef.current = now;
    return true;
  }

  function finishServerVerify() {
    serverVerifyInFlightRef.current = false;
  }

  function clearGraceCountdown() {
    if (graceTimeoutRef.current) {
      window.clearTimeout(graceTimeoutRef.current);
      graceTimeoutRef.current = null;
    }
    if (graceTickerRef.current) {
      window.clearInterval(graceTickerRef.current);
      graceTickerRef.current = null;
    }
    graceTimeoutEventRef.current = null;
    setGraceRemainingSec(null);
  }

  function startGraceCountdown(seconds: number, timeoutEvent?: GenericRow | null) {
    clearGraceCountdown();
    setExternalVerificationReady(false, String(timeoutEvent?.reason_code || timeoutEvent?.event_type || "proctoring_grace"));
    graceTimeoutEventRef.current = timeoutEvent || null;
    setMonitorState("grace");
    setGraceRemainingSec(seconds);
    const startedAt = Date.now();
    graceTickerRef.current = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      const remaining = Math.max(0, seconds - elapsed);
      setGraceRemainingSec(remaining);
    }, 250);
    graceTimeoutRef.current = window.setTimeout(() => {
      setGraceRemainingSec(0);
      setMonitorState("error");
      const event = graceTimeoutEventRef.current;
      if (event) {
        graceTimeoutEventRef.current = null;
        sendEvents(
          [{ ...event, event_status: "failed", reason_code: event.reason_code || "grace_timeout" }],
          [snapshotBase({ grace_timeout: true })],
        ).catch(() => null);
      }
    }, seconds * 1000);
  }

  function snapshotBase(extra?: GenericRow) {
    return {
      app_visibility: typeof document === "undefined" ? "visible" : document.visibilityState,
      network_online: typeof navigator === "undefined" ? true : navigator.onLine,
      grace_remaining_sec: graceRemainingSec ?? undefined,
      ...extra,
    };
  }

  function startPermissionGrace(details: GenericRow, reasonCode: string) {
    const now = Date.now();
    const startedAt = permissionGraceStartedAtRef.current || now;
    permissionGraceStartedAtRef.current = startedAt;
    const elapsed = Math.floor((now - startedAt) / 1000);
    const remaining = Math.max(0, PROCTORING_PERMISSION_GRACE_SEC - elapsed);
    const waitingText = tt("proctoring.permissionWaiting", "Camera ruxsati kutilmoqda. Iltimos, ruxsat bering.");
    setCameraReady(false);
    setCameraError(waitingText);
    setStatusText(waitingText);
    setStartupStage("retrying");
    setMonitorState("grace");
    sendEvents(
      [{
        event_type: "camera_permission_pending",
        event_status: "grace",
        reason_code: reasonCode || "camera_permission_pending",
        details: {
          ...details,
          permission_grace_sec: PROCTORING_PERMISSION_GRACE_SEC,
          permission_grace_remaining_sec: remaining,
        },
      }],
      [snapshotBase({ permission_pending: true, ...details })],
    ).catch(() => null);
    if (remaining <= 0) {
      setMonitorState("error");
      sendEvents(
        [{
          event_type: "camera_denied",
          event_status: "failed",
          reason_code: "camera_permission_timeout",
          details: {
            ...details,
            permission_grace_sec: PROCTORING_PERMISSION_GRACE_SEC,
          },
        }],
        [snapshotBase({ permission_timeout: true, ...details })],
      ).catch(() => null);
      return;
    }
    if (!graceTimeoutRef.current) {
      startGraceCountdown(remaining, {
        event_type: "camera_denied",
        event_status: "failed",
        reason_code: "camera_permission_timeout",
        details: {
          ...details,
          permission_grace_sec: PROCTORING_PERMISSION_GRACE_SEC,
        },
      });
    } else {
      setGraceRemainingSec(remaining);
    }
    if (retryTimerRef.current) {
      window.clearTimeout(retryTimerRef.current);
    }
    retryTimerRef.current = window.setTimeout(() => setCameraRetryTick((value) => value + 1), 1200);
  }

  function videoDiagnostics(extra?: GenericRow) {
    const describe = (video: HTMLVideoElement | null) => ({
      present: Boolean(video),
      connected: Boolean(video?.isConnected),
      ready_state: video?.readyState ?? null,
      video_width: video?.videoWidth || null,
      video_height: video?.videoHeight || null,
      has_src_object: Boolean(video?.srcObject),
      paused: video?.paused ?? null,
    });
    const source = describe(sourceVideoRef.current);
    const preview = describe(previewVideoRef.current);
    const fallback = describe(proctoringCaptureVideoElement);
    return {
      source_video_ref: source.present,
      source_video_connected: source.connected,
      source_ready_state: source.ready_state,
      source_video_width: source.video_width,
      source_video_height: source.video_height,
      source_has_src_object: source.has_src_object,
      preview_video_ref: preview.present,
      preview_video_connected: preview.connected,
      preview_ready_state: preview.ready_state,
      preview_video_width: preview.video_width,
      preview_video_height: preview.video_height,
      preview_has_src_object: preview.has_src_object,
      fallback_video_ref: fallback.present,
      fallback_video_connected: fallback.connected,
      fallback_ready_state: fallback.ready_state,
      fallback_video_width: fallback.video_width,
      fallback_video_height: fallback.video_height,
      fallback_has_src_object: fallback.has_src_object,
      stream_live: hasLiveVideo(streamRef.current),
      permission_state: cameraSession.permission,
      secure_context: isCameraSecureContext(),
      ...extra,
    };
  }

  useEffect(() => {
    if (!active) return;
    setSessionId(Number(initialSessionId || 0) || null);
    finishedRef.current = false;
    missingRef.current = false;
    multipleFaceRef.current = false;
    tooSmallRef.current = false;
    lookingAwayRef.current = false;
    hiddenRef.current = false;
    internetLostRef.current = false;
    fullscreenLostRef.current = false;
    fallbackModeRef.current = false;
    verifyingRef.current = false;
    recoveryVerifyInFlightRef.current = false;
    lastFallbackVerifyAtRef.current = 0;
    recoveryStableSinceRef.current = 0;
    setStartVerified(false);
    mismatchStrikeRef.current = 0;
    lastValidFaceAtRef.current = 0;
    permissionGraceStartedAtRef.current = 0;
    setFatalError("");
    setCameraError("");
    setCameraReady(false);
    externalVerificationReadyRef.current = false;
    onVerificationStateChangeRef.current?.(false, "proctoring_starting");
    setStatusText("No face");
    setStartupStage("session");
    setMonitorState("grace");
    clearGraceCountdown();
  }, [active, initialSessionId, testAttemptRef, testType]);

  useEffect(() => {
    const nextSessionId = Number(initialSessionId || 0) || null;
    if (!active || !nextSessionId || sessionId === nextSessionId) return;
    setSessionId(nextSessionId);
  }, [active, initialSessionId, sessionId]);

  async function flushQueuedEvents() {
    if (eventFlushInFlightRef.current || !sessionId || !eventQueueRef.current.length) return;
    eventFlushInFlightRef.current = true;
    try {
      while (eventQueueRef.current.length && sessionId) {
        const next = eventQueueRef.current[0];
        try {
          const response = await requestJson<ProctoringSessionResponse>(`/student/proctoring/session/${sessionId}/events`, {
            method: "POST",
            token: getToken(),
            body: { events: next.events, snapshots: next.snapshots },
            timeoutMs: PROCTORING_START_FETCH_TIMEOUT_MS,
          });
          eventQueueRef.current.shift();
          if (response.status === "failed" || response.status === "aborted") {
            finishedRef.current = true;
            setFatalError(response.failure_reason || "proctoring_failed");
            setMonitorState("error");
            onTerminatedRef.current?.(String(response.failure_reason || "proctoring_failed"));
            break;
          }
        } catch {
          break;
        }
      }
    } finally {
      eventFlushInFlightRef.current = false;
    }
  }

  async function sendEvents(events: GenericRow[], snapshots: GenericRow[] = []) {
    const token = getToken();
    if (!token || !sessionId) return null;
    if (eventQueueRef.current.length) {
      await flushQueuedEvents();
    }
    try {
      const response = await requestJson<ProctoringSessionResponse>(`/student/proctoring/session/${sessionId}/events`, {
        method: "POST",
        token,
        body: { events, snapshots },
        timeoutMs: PROCTORING_START_FETCH_TIMEOUT_MS,
      });
      if (response.status === "failed" || response.status === "aborted") {
        finishedRef.current = true;
        setFatalError(response.failure_reason || "proctoring_failed");
        setMonitorState("error");
        onTerminatedRef.current?.(String(response.failure_reason || "proctoring_failed"));
      }
      return response;
    } catch (err) {
      const message = normalizeProctoringRequestError(err instanceof Error ? err.message : "Proctoring event failed");
      eventQueueRef.current.push({ events, snapshots });
      if (isBrowserOffline()) {
        setStatusText("Offline");
        setMonitorState("grace");
      } else if (isTransientProctoringError(message)) {
        setStatusText(startVerified ? "Face detected" : "FaceID tekshirilmoqda...");
        setMonitorState("grace");
      } else {
        setStatusText(message);
        setMonitorState("grace");
      }
      return null;
    }
  }

  function failImmediately(eventType: string, reasonCode: string) {
    const token = getToken();
    const targetSessionId = Number(sessionIdRef.current || sessionId || 0) || null;
    if (!token || !targetSessionId || finishedRef.current || completedRef.current) return;
    finishedRef.current = true;
    clearGraceCountdown();
    setMonitorState("error");
    setStatusText("Test bloklandi");
    setFatalError(reasonCode || "proctoring_failed");
    setExternalVerificationReady(false, reasonCode || "proctoring_failed");
    onTerminatedRef.current?.(reasonCode || "proctoring_failed");
    const body = JSON.stringify({
      events: [
        {
          event_type: eventType || "app_hidden",
          event_status: "failed",
          reason_code: reasonCode || "app_closed",
          client_ts: new Date().toISOString(),
          details: {
            immediate_block: true,
            visibility: typeof document === "undefined" ? "unknown" : document.visibilityState,
          },
        },
      ],
      snapshots: [snapshotBase({ immediate_block: true })],
    });
    try {
      fetch(`${API_BASE}/student/proctoring/session/${targetSessionId}/events`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body,
        keepalive: true,
      }).catch(() => null);
    } catch {
      // Closing/unloading pages can cancel network work; backend also fails aborted sessions.
    }
  }

  const setSourceVideoNode = useCallback((node: HTMLVideoElement | null) => {
    sourceVideoRef.current = node;
    if (node && hasLiveVideo(streamRef.current)) {
      attachVideoStream(node, streamRef.current as MediaStream).catch(() => null);
    }
  }, []);

  const setPreviewVideoNode = useCallback((node: HTMLVideoElement | null) => {
    previewVideoRef.current = node;
    if (node && hasLiveVideo(streamRef.current)) {
      attachVideoStream(node, streamRef.current as MediaStream).catch(() => null);
    }
  }, []);

  function getCaptureVideoElement() {
    const fallback = getOrCreateProctoringCaptureVideo();
    const candidates = [previewVideoRef.current, sourceVideoRef.current, fallback].filter(Boolean) as HTMLVideoElement[];
    return candidates.find((video) => video.readyState >= 2 && Boolean(video.videoWidth || video.videoHeight)) || candidates[0] || null;
  }

  async function waitForCaptureVideoElement(frameAttempts = 24) {
    let video = getCaptureVideoElement();
    for (let attempt = 0; attempt < frameAttempts && !video; attempt += 1) {
      await new Promise((resolve) => window.requestAnimationFrame(resolve));
      video = getCaptureVideoElement();
    }
    return video;
  }

  async function attachStreamToProctoringVideos(stream: MediaStream) {
    const source = await waitForCaptureVideoElement(60);
    if (!source) throw new Error("camera_video_not_ready");
    await attachVideoStream(source, stream);
    const fallback = getOrCreateProctoringCaptureVideo();
    if (fallback && fallback !== source) {
      attachVideoStream(fallback, stream).catch(() => null);
    }
    if (previewVideoRef.current && previewVideoRef.current !== source) {
      attachVideoStream(previewVideoRef.current, stream).catch(() => null);
    }
    return source;
  }

  async function captureSnapshotAndUpload(): Promise<string | null> {
    const token = getToken();
    const video = await waitForCaptureVideoElement(30);
    if (!token) return null;
    if (!video) return null;
    const frameReady = await waitForVideoFrame(video, 7000);
    if (!frameReady) return null;
    const canvas = document.createElement("canvas");
    const sourceWidth = video.videoWidth || 640;
    const sourceHeight = video.videoHeight || 480;
    const maxSide = 512;
    const scale = Math.min(1, maxSide / Math.max(sourceWidth, sourceHeight));
    const width = Math.max(240, Math.round(sourceWidth * scale));
    const height = Math.max(180, Math.round(sourceHeight * scale));
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    try {
      ctx.drawImage(video, 0, 0, width, height);
    } catch {
      return null;
    }
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.68));
    if (!blob) return null;
    const file = new File([blob], `proctoring-${Date.now()}.jpg`, { type: "image/jpeg" });
    const uploaded = await uploadImage("/student/proctoring/upload-image", file, token);
    return String(uploaded.url || "").trim() || null;
  }

  async function reverifyCurrentFace(reasonCode: string, snapshotMeta: GenericRow = {}) {
    const token = getToken();
    if (!token || !sessionId || recoveryVerifyInFlightRef.current) return false;
    const forceNow = /recovered|warning|returned|restored/i.test(String(reasonCode || ""));
    if (!beginServerVerify(PROCTORING_RECOVERY_VERIFY_COOLDOWN_MS, forceNow)) return false;
    recoveryVerifyInFlightRef.current = true;
    try {
      setExternalVerificationReady(false, reasonCode || "face_reverify");
      setStatusText("FaceID qayta tekshirilmoqda...");
      clearGraceCountdown();
      setMonitorState("grace");
      setGraceRemainingSec(null);
      const snapshotUrl = await captureSnapshotAndUpload();
      if (!snapshotUrl) return false;
      const response = await requestJson<{ verified: boolean; reason?: string; match_score?: number; threshold?: number; warning?: boolean; confirmed_mismatch?: boolean; fail_applied?: boolean; mismatch_strikes?: number; mismatch_limit?: number }>(
        "/student/proctoring/verify/check",
        {
          method: "POST",
          token,
          timeoutMs: PROCTORING_VERIFY_FETCH_TIMEOUT_MS,
          body: {
            proctoring_session_id: sessionId,
            snapshot_image_url: snapshotUrl,
            context_reason: reasonCode,
          },
        },
      );
      if (!response.verified) {
        const rawReason = String(response.reason || "face_mismatch").trim();
        const upperReason = rawReason.toUpperCase();
        if (upperReason === "FACE_MISMATCH" && !response.confirmed_mismatch && !response.fail_applied) {
          mismatchStrikeRef.current = Math.max(
            mismatchStrikeRef.current + 1,
            Number(response.mismatch_strikes || 0),
          );
          clearGraceCountdown();
          setMonitorState("grace");
          setStatusText(tt("proctoring.faceMismatchWarning", "Yuz mosligi tekshirilmoqda. Kameraga to'g'ri qarang."));
          setExternalVerificationReady(false, "face_mismatch_warning");
          recoveryStableSinceRef.current = 0;
          return false;
        }
        if (upperReason === "ENGINE_ERROR") {
          clearGraceCountdown();
          setMonitorState("grace");
          setStatusText(tt("proctoring.faceRechecking", "Yuz qayta tekshirilmoqda..."));
          setExternalVerificationReady(false, "face_recheck_engine_warning");
          recoveryStableSinceRef.current = 0;
          return false;
        }
        const reason = rawReason.toLowerCase() || "verify_failed";
        setMonitorState("error");
        setFatalError(reason);
        onTerminatedRef.current?.(reason);
        return false;
      }
      missingRef.current = false;
      tooSmallRef.current = false;
      lookingAwayRef.current = false;
      multipleFaceRef.current = false;
      mismatchStrikeRef.current = 0;
      lastValidFaceAtRef.current = Date.now();
      recoveryStableSinceRef.current = 0;
      clearGraceCountdown();
      setMonitorState("ok");
      setStatusText("Face verified");
      setExternalVerificationReady(true, reasonCode || "face_reverified");
      await sendEvents(
        [{ event_type: "face_detected", event_status: "ok", reason_code: reasonCode, score: Number(response.match_score || 1) }],
        [snapshotBase({ ...snapshotMeta, is_live: true, match_score: Number(response.match_score || 1) })],
      );
      return true;
    } catch (err) {
      if (!isBrowserOffline()) {
        const message = normalizeProctoringRequestError(err instanceof Error ? err.message : "face_reverify_failed");
        if (!isTransientProctoringError(message)) {
          setMonitorState("error");
          setFatalError(message);
          onTerminatedRef.current?.("face_reverify_failed");
        }
      }
      return false;
    } finally {
      recoveryVerifyInFlightRef.current = false;
      finishServerVerify();
    }
  }

  useEffect(() => {
    const providedInitialSessionId = Number(initialSessionId || 0) || null;
    if (!active || sessionId || completed || providedInitialSessionId) return;
    const token = getToken();
    if (!token) return;
    if (sessionStartInFlightRef.current) return;
    const controller = new AbortController();
    sessionStartAbortRef.current = controller;
    setStartupStage("session");
    setStatusText("FaceID tayyorlanmoqda...");
    sessionStartInFlightRef.current = (async () => {
      let lastMessage = "";
      for (let attempt = 1; attempt <= PROCTORING_CLIENT_RETRY_ATTEMPTS; attempt += 1) {
        if (controller.signal.aborted) return null;
        try {
          const payload = await requestJson<ProctoringSessionResponse>("/student/proctoring/session/start", {
            method: "POST",
            token,
            signal: controller.signal,
            timeoutMs: PROCTORING_START_FETCH_TIMEOUT_MS,
            body: {
              test_type: testType,
              test_attempt_ref: testAttemptRef,
              test_route: testRoute,
              device_id: navigator.userAgent,
              platform: navigator.platform,
              browser: navigator.userAgent,
            },
          });
          const sid = Number(payload.session_id || 0) || null;
          setSessionId(sid);
          return sid;
        } catch (err) {
          const message = normalizeProctoringRequestError(err instanceof Error ? err.message : "FaceID tayyorlanmadi. Qayta urinib ko'ring.");
          lastMessage = message;
          if (String(message).toLowerCase().includes("aborted")) return null;
          if (!isTransientProctoringError(message) || isBrowserOffline()) break;
          setStartupStage("retrying");
          setStatusText("FaceID sekin yuklanmoqda...");
          await new Promise((resolve) => window.setTimeout(resolve, PROCTORING_START_RETRY_DELAY_MS));
        }
      }
      const fatal = isBrowserOffline()
        ? "Internet aloqasi yo'q. Ulanishni tekshirib qayta urinib ko'ring."
        : lastMessage || "FaceID tayyorlanmadi. Qayta urinib ko'ring.";
      if (isTransientProctoringError(fatal) && !isBrowserOffline()) {
        setStartupStage("retrying");
        setStatusText("FaceID sekin yuklanmoqda...");
        retryTimerRef.current = window.setTimeout(() => setSessionRetryTick((value) => value + 1), 2500);
        return null;
      }
      setFatalError(fatal);
      onTerminatedRef.current?.("proctoring_start_failed");
      return null;
    })().finally(() => {
      sessionStartInFlightRef.current = null;
      sessionStartAbortRef.current = null;
    });
    return () => {
      if (sessionStartAbortRef.current) {
        sessionStartAbortRef.current.abort();
        sessionStartAbortRef.current = null;
      }
    };
  }, [active, completed, initialSessionId, sessionId, sessionRetryTick, testAttemptRef, testRoute, testType]);

  useEffect(() => {
    if (!active || !mounted || !sessionId || completed || cameraReady || fatalError || startVerified) return;

    async function startCamera() {
      if (cameraStartingRef.current) return;
      cameraStartingRef.current = true;
      try {
        let lastError: unknown = null;
        for (let attempt = 1; attempt <= PROCTORING_CLIENT_RETRY_ATTEMPTS; attempt += 1) {
          try {
            setCameraError("");
            setStartupStage(attempt > 1 ? "retrying" : "camera");
            setStatusText(attempt > 1 ? "Kamera kadri kutilmoqda, qayta urinilmoqda..." : "Kamera tayyorlanmoqda...");
            await refreshCameraPermissionState();
            setCameraReady(false);
            detectorRef.current?.close?.();
            const stream = hasLiveVideo(streamRef.current) ? (streamRef.current as MediaStream) : await acquireSharedUserFacingCamera();
            streamRef.current = stream;
            stream.getVideoTracks().forEach((track) => {
              track.addEventListener("ended", () => {
                sendEvents([{
                  event_type: "camera_stream_lost",
                  event_status: "failed",
                  reason_code: "track_ended",
                  details: { permission_state: cameraSession.permission },
                }]).catch(() => null);
                setCameraReady(false);
                setStartVerified(false);
                setExternalVerificationReady(false, "camera_stream_lost");
                setMonitorState("grace");
                setStatusText(tt("proctoring.cameraStreamLost", "Kamera ulanishi uzildi. Qayta ulanmoqda..."));
                if (retryTimerRef.current) {
                  window.clearTimeout(retryTimerRef.current);
                }
                retryTimerRef.current = window.setTimeout(() => setCameraRetryTick((value) => value + 1), 1200);
              }, { once: true });
            });
            const videoEl = await attachStreamToProctoringVideos(stream);
            const frameReady = await waitForVideoFrame(videoEl, attempt > 1 ? 12000 : 8500);
            if (!frameReady) {
              throw new Error("camera_frame_wait_timeout");
            }
            setStartupStage("verifying");
            setStatusText("FaceID tekshirilmoqda...");
            setMonitorState("grace");
            const detector = await createBrowserDetectorAdapter().catch(() => null);
            detectorRef.current = detector;
            fallbackModeRef.current = !detector;
            setCameraReady(true);
            permissionGraceStartedAtRef.current = 0;
            clearGraceCountdown();
            await sendEvents([{
              event_type: "camera_started",
              event_status: "ok",
              reason_code: fallbackModeRef.current
                ? "face_detector_unavailable_basic_monitor"
                : String(detectorRef.current?.provider || "detector_ready"),
              details: {
                startup_attempt: attempt,
                permission_state: cameraSession.permission,
                detector_provider: detector?.provider || null,
                fallback_mode: !detector,
                video_width: videoEl.videoWidth || null,
                video_height: videoEl.videoHeight || null,
              },
            }]);
            return;
          } catch (err) {
            lastError = err;
            const code = cameraErrorCode(err);
            const details = cameraDiagnosticDetails(err, {
              startup_attempt: attempt,
              source_video_ref: Boolean(sourceVideoRef.current),
              preview_video_ref: Boolean(previewVideoRef.current),
              fallback_video_ref: Boolean(proctoringCaptureVideoElement?.isConnected),
            });
            setCameraReady(false);
            const message = humanizeCameraError(err);
            setCameraError(message);

            if (isCameraPermissionDeniedError(err)) {
              startPermissionGrace(details, code);
              return;
            }

            const transientStartup = isTransientCameraStartupError(err) && !isBrowserOffline();
            const canRetry = transientStartup && attempt < PROCTORING_CLIENT_RETRY_ATTEMPTS;
            const willRetryLater = transientStartup && attempt >= PROCTORING_CLIENT_RETRY_ATTEMPTS;
            await sendEvents([{
              event_type: code === "camera_frame_wait_timeout" || code === "camera_video_not_ready" ? "camera_frame_wait_timeout" : "camera_start_retry",
              event_status: canRetry || willRetryLater ? "grace" : "failed",
              reason_code: code,
              details,
            }]).catch(() => null);

            if (canRetry) {
              setStartupStage("retrying");
              setStatusText("Kamera kadri kutilmoqda, qayta urinilmoqda...");
              setMonitorState("grace");
              await new Promise((resolve) => window.setTimeout(resolve, PROCTORING_START_RETRY_DELAY_MS * 2));
              continue;
            }

            if (willRetryLater) {
              setStartupStage("retrying");
              setStatusText("Kamera kadri kutilmoqda, qayta urinilmoqda...");
              setMonitorState("grace");
              if (retryTimerRef.current) {
                window.clearTimeout(retryTimerRef.current);
              }
              retryTimerRef.current = window.setTimeout(() => setCameraRetryTick((value) => value + 1), 900);
              return;
            }

            setStatusText(message);
            setMonitorState("error");
            finishedRef.current = true;
            setFatalError(message || code);
            onTerminatedRef.current?.(code);
            return;
          }
        }
        const finalCode = cameraErrorCode(lastError);
        setMonitorState("error");
        setFatalError(humanizeCameraError(lastError) || finalCode);
        onTerminatedRef.current?.(finalCode);
      } finally {
        cameraStartingRef.current = false;
      }
    }

    startCamera().catch(() => null);
  }, [active, mounted, completed, sessionId, startVerified, cameraReady, fatalError, cameraRetryTick]);

  useEffect(() => {
    if (!active || !mounted || !sessionId || completed || !cameraReady || fatalError) return;
    if (startVerified) return;
    const token = getToken();
    if (!token) return;
    let cancelled = false;
    (async () => {
      if (verifyingRef.current) return;
      verifyingRef.current = true;
      try {
        setStartupStage("verifying");
        setStatusText("FaceID tekshirilmoqda...");
        setMonitorState("grace");
        let transientFailure = "";
        for (let attempt = 1; attempt <= PROCTORING_CLIENT_RETRY_ATTEMPTS; attempt += 1) {
          if (cancelled) return;
          try {
            const snapshotUrl = await captureSnapshotAndUpload();
            if (!snapshotUrl || cancelled) {
              transientFailure = "Kamera kadri kutilmoqda. Qayta urinilmoqda...";
              setStatusText("Kamera kadri kutilmoqda...");
              await sendEvents([{
                event_type: "snapshot_capture_retry",
                event_status: attempt >= PROCTORING_CLIENT_RETRY_ATTEMPTS ? "failed" : "grace",
                reason_code: "snapshot_not_ready",
                details: videoDiagnostics({ startup_verify_attempt: attempt }),
              }], [snapshotBase(videoDiagnostics({ startup_verify_attempt: attempt }))]).catch(() => null);
              await new Promise((resolve) => window.setTimeout(resolve, 650));
              continue;
            }
            const response = await requestJson<{ verified: boolean; reason?: string; match_score?: number; threshold?: number }>(
              "/student/proctoring/verify/start-exam",
              {
                method: "POST",
                token,
                timeoutMs: PROCTORING_VERIFY_FETCH_TIMEOUT_MS,
                body: {
                  proctoring_session_id: sessionId,
                  snapshot_image_url: snapshotUrl,
                  attempt_no: attempt,
                },
              },
            );
            if (response.verified) {
              setStartVerified(true);
              onSessionReadyRef.current?.(sessionId);
              setExternalVerificationReady(true, "start_verified");
              setStartupStage("ready");
              setStatusText("Face verified");
              setMonitorState("ok");
              flushQueuedEvents().catch(() => null);
              return;
            }
            const reason = String(response.reason || "face_mismatch").trim() || "face_mismatch";
            const normalizedReason = reason.toUpperCase();
            if (PROCTORING_START_FATAL_VERIFY_REASONS.has(normalizedReason) || attempt >= PROCTORING_CLIENT_RETRY_ATTEMPTS) {
              setMonitorState("error");
              setFatalError(reason);
              onTerminatedRef.current?.(reason.toLowerCase());
              return;
            }
            transientFailure = reason;
            setStatusText("FaceID tekshirilmoqda...");
            await new Promise((resolve) => window.setTimeout(resolve, 250));
          } catch (err) {
            const message = normalizeProctoringRequestError(err instanceof Error ? err.message : "verify_start_failed");
            transientFailure = message;
            await sendEvents([{
              event_type: "snapshot_verify_retry",
              event_status: "grace",
              reason_code: message,
              details: videoDiagnostics({ startup_verify_attempt: attempt }),
            }], [snapshotBase(videoDiagnostics({ startup_verify_attempt: attempt }))]).catch(() => null);
            if (isBrowserOffline()) {
              setMonitorState("grace");
              setStatusText("Offline");
              return;
            }
            if (!isTransientProctoringError(message)) {
              setMonitorState("error");
              setFatalError(message);
              onTerminatedRef.current?.("verify_start_failed");
              return;
            }
            setStartupStage("retrying");
            setStatusText("FaceID tekshiruvi sekinlashdi, qayta urinilmoqda...");
            await new Promise((resolve) => window.setTimeout(resolve, PROCTORING_START_RETRY_DELAY_MS));
          }
        }
        if (!cancelled) {
          const finalReason = transientFailure || "face_not_verified";
          setStartupStage("failed");
          setMonitorState("error");
          setStatusText("FaceID tasdiqlanmadi");
          setFatalError(finalReason);
          onTerminatedRef.current?.(String(finalReason).toLowerCase());
        }
      } catch (err) {
        if (!cancelled) {
          const message = normalizeProctoringRequestError(err instanceof Error ? err.message : "verify_start_failed");
          if (isTransientProctoringError(message) && !isBrowserOffline()) {
            setStartupStage("retrying");
            setStatusText("FaceID tekshiruvi sekinlashdi, qayta urinilmoqda...");
            retryTimerRef.current = window.setTimeout(() => setVerifyRetryTick((value) => value + 1), 1000);
          } else {
            setMonitorState("error");
            setFatalError(message);
            onTerminatedRef.current?.("verify_start_failed");
          }
        }
      } finally {
        verifyingRef.current = false;
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [active, sessionId, completed, cameraReady, fatalError, mounted, startVerified, verifyRetryTick]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!active || !sessionId || completed || !cameraReady || fatalError) return;
    if (!startVerified) return;
    const token = getToken();
    if (!token) return;
    const timer = window.setInterval(async () => {
      if (finishedRef.current || verifyingRef.current || recoveryVerifyInFlightRef.current) return;
      if (!beginServerVerify(PROCTORING_PERIODIC_VERIFY_INTERVAL_MS)) return;
      verifyingRef.current = true;
      try {
        const snapshotUrl = await captureSnapshotAndUpload();
        if (!snapshotUrl) return;
        const response = await requestJson<{ verified: boolean; reason?: string; match_score?: number; threshold?: number; warning?: boolean; confirmed_mismatch?: boolean; fail_applied?: boolean; mismatch_strikes?: number; mismatch_limit?: number }>(
          "/student/proctoring/verify/check",
          {
            method: "POST",
            token,
            body: {
              proctoring_session_id: sessionId,
              snapshot_image_url: snapshotUrl,
              context_reason: "periodic_check",
            },
          },
        );
        const reason = String(response.reason || "").toUpperCase();
        if (response.verified) {
          mismatchStrikeRef.current = 0;
        }
        if (!response.verified && reason === "FACE_MISMATCH") {
          mismatchStrikeRef.current = Math.max(
            mismatchStrikeRef.current + 1,
            Number(response.mismatch_strikes || 0),
          );
          const limit = Number(response.mismatch_limit || PROCTORING_FACE_MISMATCH_CONFIRMATION_LIMIT);
          if (!response.confirmed_mismatch && !response.fail_applied && mismatchStrikeRef.current < limit) {
            setMonitorState("grace");
            setStatusText(tt("proctoring.faceMismatchWarning", "Yuz mosligi tekshirilmoqda. Kameraga to'g'ri qarang."));
            setExternalVerificationReady(false, "face_mismatch_warning");
            return;
          }
          setMonitorState("error");
          setFatalError("confirmed_face_mismatch");
          onTerminatedRef.current?.("confirmed_face_mismatch");
          return;
        }
        if (!response.verified && reason === "ENGINE_ERROR") {
          setStatusText(tt("proctoring.faceRechecking", "Yuz qayta tekshirilmoqda..."));
          setExternalVerificationReady(false, "face_recheck_engine_warning");
          return;
        }
        if (!response.verified && reason === "MULTIPLE_FACES") {
          mismatchStrikeRef.current = 0;
          setStatusText("Multiple faces");
          if (!multipleFaceRef.current) {
            multipleFaceRef.current = true;
            startGraceCountdown(PROCTORING_CLIENT_GRACE_SEC, { event_type: "different_face", event_status: "failed", reason_code: "multiple_faces_timeout" });
            await sendEvents(
              [{ event_type: "different_face", event_status: "grace", reason_code: "multiple_faces" }],
              [snapshotBase({ face_count: Number((response as GenericRow).face_count || 2) || 2, verify_reason: reason })],
            );
          }
          return;
        }
        if (!response.verified && PROCTORING_CRITICAL_VERIFY_REASONS.has(reason)) {
          mismatchStrikeRef.current = 0;
          setMonitorState("error");
          setFatalError(reason.toLowerCase() || "verify_failed");
          onTerminatedRef.current?.(reason.toLowerCase() || "verify_failed");
        }
      } catch {
        // keep test running on transient verify errors; events stream already captures network/app states
      } finally {
        verifyingRef.current = false;
        finishServerVerify();
      }
    }, PROCTORING_PERIODIC_VERIFY_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [active, sessionId, completed, cameraReady, fatalError, startVerified]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!active || !sessionId || completed || !cameraReady) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      const video = getCaptureVideoElement();
      if (cancelled || !video || finishedRef.current) return;
      try {
        const preview = previewVideoRef.current || video;
        const rect = preview.getBoundingClientRect();
        const previewVisible = rect.width > 20 && rect.height > 20 && getComputedStyle(preview).visibility !== "hidden";
        if (!previewVisible) {
          recoveryStableSinceRef.current = 0;
          if (!missingRef.current) {
            missingRef.current = true;
            multipleFaceRef.current = false;
            setStatusText("No face");
            startGraceCountdown(PROCTORING_CLIENT_GRACE_SEC, { event_type: "face_missing", event_status: "failed", reason_code: "preview_hidden_timeout" });
            await sendEvents([{ event_type: "face_missing", event_status: "grace", reason_code: "preview_hidden" }], [snapshotBase({ face_count: 0, preview_visible: false })]);
          }
          return;
        }

        if (fallbackModeRef.current) {
          if (!startVerified || recoveryVerifyInFlightRef.current || verifyingRef.current) {
            setStatusText(startVerified ? "Face detected" : "FaceID tekshirilmoqda...");
            setMonitorState(startVerified ? "ok" : "grace");
            return;
          }
          const hadRecoverableWarning = missingRef.current || tooSmallRef.current || lookingAwayRef.current || multipleFaceRef.current;
          const now = Date.now();
          if (hadRecoverableWarning) {
            clearGraceCountdown();
            if (!recoveryStableSinceRef.current) recoveryStableSinceRef.current = now;
            const stableForMs = now - recoveryStableSinceRef.current;
            if (stableForMs < PROCTORING_FACE_RECOVERY_STABLE_MS) {
              setStatusText(tt("proctoring.faceRecoveredChecking", "Yuz qaytdi. FaceID tekshirilmoqda..."));
              setMonitorState("grace");
              setExternalVerificationReady(false, "face_recovery_stabilizing");
              return;
            }
          }
          const fallbackCooldown = hadRecoverableWarning ? 0 : PROCTORING_FALLBACK_REVERIFY_INTERVAL_MS;
          if (!hadRecoverableWarning && lastFallbackVerifyAtRef.current && now - lastFallbackVerifyAtRef.current < fallbackCooldown) {
            setStatusText("Face detected");
            setMonitorState("ok");
            setExternalVerificationReady(true, "fallback_throttled_face_detected");
            return;
          }
          if (!beginServerVerify(fallbackCooldown, hadRecoverableWarning)) {
            setStatusText(hadRecoverableWarning ? "FaceID qayta tekshirilmoqda..." : "Face detected");
            if (!hadRecoverableWarning) {
              setMonitorState("ok");
              setExternalVerificationReady(true, "fallback_throttled_face_detected");
            }
            return;
          }
          lastFallbackVerifyAtRef.current = now;
          recoveryVerifyInFlightRef.current = true;
          try {
            const snapshotUrl = await captureSnapshotAndUpload();
            if (!snapshotUrl) {
              if (!missingRef.current) {
                recoveryStableSinceRef.current = 0;
                missingRef.current = true;
                setStatusText("No face");
                startGraceCountdown(PROCTORING_CLIENT_GRACE_SEC, { event_type: "face_missing", event_status: "failed", reason_code: "fallback_snapshot_not_ready_timeout" });
                await sendEvents([{ event_type: "face_missing", event_status: "grace", reason_code: "fallback_snapshot_not_ready" }], [snapshotBase({ face_count: 0, preview_visible: previewVisible })]);
              }
              return;
            }
            const response = await requestJson<{ verified: boolean; reason?: string; match_score?: number; threshold?: number; warning?: boolean; confirmed_mismatch?: boolean; fail_applied?: boolean; mismatch_strikes?: number; mismatch_limit?: number }>(
              "/student/proctoring/verify/check",
              {
                method: "POST",
                token: getToken(),
                timeoutMs: PROCTORING_VERIFY_FETCH_TIMEOUT_MS,
                body: {
                  proctoring_session_id: sessionId,
                  snapshot_image_url: snapshotUrl,
                  context_reason: "fallback_monitor",
                },
              },
            );
            const reason = String(response.reason || "").toUpperCase();
            if (response.verified) {
              missingRef.current = false;
              tooSmallRef.current = false;
              lookingAwayRef.current = false;
              multipleFaceRef.current = false;
              mismatchStrikeRef.current = 0;
              lastValidFaceAtRef.current = Date.now();
              clearGraceCountdown();
              setMonitorState("ok");
              setStatusText(hadRecoverableWarning ? "Face verified" : "Face detected");
              setExternalVerificationReady(true, hadRecoverableWarning ? "fallback_reverified" : "fallback_face_detected");
              return;
            }
            if (reason === "NO_FACE") {
              recoveryStableSinceRef.current = 0;
              if (!missingRef.current) {
                missingRef.current = true;
                multipleFaceRef.current = false;
                setStatusText("No face");
                startGraceCountdown(PROCTORING_CLIENT_GRACE_SEC, { event_type: "face_missing", event_status: "failed", reason_code: "fallback_face_missing_timeout" });
                await sendEvents([{ event_type: "face_missing", event_status: "grace", reason_code: "fallback_no_face" }], [snapshotBase({ face_count: 0, preview_visible: previewVisible })]);
              }
              return;
            }
            if (reason === "MULTIPLE_FACES") {
              recoveryStableSinceRef.current = 0;
              setStatusText("Multiple faces");
              if (!multipleFaceRef.current) {
                multipleFaceRef.current = true;
                startGraceCountdown(PROCTORING_CLIENT_GRACE_SEC, { event_type: "different_face", event_status: "failed", reason_code: "multiple_faces_timeout" });
                await sendEvents(
                  [{ event_type: "different_face", event_status: "grace", reason_code: "multiple_faces" }],
                  [snapshotBase({ face_count: Number((response as GenericRow).face_count || 2) || 2, verify_reason: reason, preview_visible: previewVisible })],
                );
              }
              return;
            }
            if (reason === "FACE_MISMATCH") {
              mismatchStrikeRef.current = Math.max(
                mismatchStrikeRef.current + 1,
                Number(response.mismatch_strikes || 0),
              );
              const limit = Number(response.mismatch_limit || PROCTORING_FACE_MISMATCH_CONFIRMATION_LIMIT);
              if (!response.confirmed_mismatch && !response.fail_applied && mismatchStrikeRef.current < limit) {
                setMonitorState("grace");
                setStatusText(tt("proctoring.faceMismatchWarning", "Yuz mosligi tekshirilmoqda. Kameraga to'g'ri qarang."));
                setExternalVerificationReady(false, "face_mismatch_warning");
                recoveryStableSinceRef.current = 0;
                return;
              }
              setMonitorState("error");
              setFatalError("confirmed_face_mismatch");
              setExternalVerificationReady(false, "confirmed_face_mismatch");
              onTerminatedRef.current?.("confirmed_face_mismatch");
              return;
            }
            if (reason === "ENGINE_ERROR") {
              setStatusText(tt("proctoring.faceRechecking", "Yuz qayta tekshirilmoqda..."));
              setExternalVerificationReady(false, "face_recheck_engine_warning");
              recoveryStableSinceRef.current = 0;
              return;
            }
            if (PROCTORING_CRITICAL_VERIFY_REASONS.has(reason)) {
              setMonitorState("error");
              setFatalError(String(response.reason || "verify_failed").toLowerCase());
              setExternalVerificationReady(false, String(response.reason || "verify_failed").toLowerCase());
              onTerminatedRef.current?.(String(response.reason || "verify_failed").toLowerCase());
              return;
            }
            setStatusText("FaceID qayta tekshirilmoqda...");
            setExternalVerificationReady(false, String(response.reason || "fallback_recheck_failed"));
          } catch {
            // Keep the previous ready/grace state for transient fallback monitor failures.
          } finally {
            recoveryVerifyInFlightRef.current = false;
            finishServerVerify();
          }
          return;
        }

        if (!detectorRef.current) return;
        const faces = await detectorRef.current.detect(video);
        const faceCount = Array.isArray(faces) ? faces.length : 0;
        const vw = video.videoWidth || 1;
        const vh = video.videoHeight || 1;
        if (faceCount <= 0) {
          recoveryStableSinceRef.current = 0;
          if (!missingRef.current) {
            missingRef.current = true;
            multipleFaceRef.current = false;
            setStatusText("No face");
            startGraceCountdown(PROCTORING_CLIENT_GRACE_SEC, { event_type: "face_missing", event_status: "failed", reason_code: "face_missing_timeout" });
            await sendEvents([{ event_type: "face_missing", event_status: "grace" }], [snapshotBase({ face_count: 0, preview_visible: previewVisible })]);
          }
          return;
        }
        if (faceCount > 1) {
          recoveryStableSinceRef.current = 0;
          setStatusText("Multiple faces");
          if (!multipleFaceRef.current) {
            multipleFaceRef.current = true;
            startGraceCountdown(PROCTORING_CLIENT_GRACE_SEC, { event_type: "different_face", event_status: "failed", reason_code: "multiple_faces_timeout" });
            await sendEvents([{ event_type: "different_face", event_status: "grace", reason_code: "multiple_faces" }], [snapshotBase({ face_count: faceCount, preview_visible: previewVisible })]);
          }
          return;
        }
        const primary = faces[0];
        const bw = Number(primary?.width || 0);
        const bh = Number(primary?.height || 0);
        const bx = Number(primary?.x || 0);
        const by = Number(primary?.y || 0);
        const boxRatio = (bw * bh) / Math.max(1, vw * vh);
        const cx = (bx + (bw / 2)) / Math.max(1, vw);
        const cy = (by + (bh / 2)) / Math.max(1, vh);
        const centerOffset = Math.sqrt(((cx - 0.5) ** 2) + ((cy - 0.5) ** 2));

        if (boxRatio < FACE_MIN_BOX_RATIO) {
          recoveryStableSinceRef.current = 0;
          setStatusText("No face");
          if (!tooSmallRef.current) {
            tooSmallRef.current = true;
            startGraceCountdown(PROCTORING_CLIENT_GRACE_SEC, { event_type: "face_too_small", event_status: "failed", reason_code: "face_too_small_timeout" });
            await sendEvents(
              [{ event_type: "face_too_small", event_status: "grace", reason_code: "face_too_small" }],
              [snapshotBase({ face_count: 1, face_box_ratio: boxRatio, preview_visible: previewVisible })],
            );
          }
          return;
        }
        if (centerOffset > 0.34) {
          recoveryStableSinceRef.current = 0;
          setStatusText("Looking away");
          if (!lookingAwayRef.current) {
            lookingAwayRef.current = true;
            startGraceCountdown(PROCTORING_CLIENT_GRACE_SEC, { event_type: "looking_away", event_status: "failed", reason_code: "looking_away_timeout" });
            await sendEvents(
              [{ event_type: "looking_away", event_status: "grace", reason_code: "looking_away" }],
              [snapshotBase({ face_count: 1, face_box_ratio: boxRatio, preview_visible: previewVisible })],
            );
          }
          return;
        }
        const hadRecoverableWarning = missingRef.current || tooSmallRef.current || lookingAwayRef.current || multipleFaceRef.current;
        if (hadRecoverableWarning) {
          const now = Date.now();
          clearGraceCountdown();
          if (!recoveryStableSinceRef.current) recoveryStableSinceRef.current = now;
          const stableForMs = now - recoveryStableSinceRef.current;
          if (stableForMs < PROCTORING_FACE_RECOVERY_STABLE_MS) {
            setStatusText(tt("proctoring.faceRecoveredChecking", "Yuz qaytdi. FaceID tekshirilmoqda..."));
            setMonitorState("grace");
            setExternalVerificationReady(false, "face_recovery_stabilizing");
            return;
          }
          await reverifyCurrentFace("warning_recovered_reverified", {
            face_count: 1,
            preview_visible: previewVisible,
            face_box_ratio: boxRatio,
            center_offset_ratio: centerOffset,
          });
        } else {
          lastValidFaceAtRef.current = Date.now();
          recoveryStableSinceRef.current = 0;
          setStatusText("Face detected");
          clearGraceCountdown();
          setMonitorState("ok");
          setExternalVerificationReady(true, "face_detected");
        }
      } catch {
        if (!missingRef.current) {
          missingRef.current = true;
          setStatusText("No face");
          startGraceCountdown(PROCTORING_CLIENT_GRACE_SEC, { event_type: "face_missing", event_status: "failed", reason_code: "detector_error_timeout" });
          await sendEvents([{ event_type: "face_missing", event_status: "grace", reason_code: "detector_error" }], [snapshotBase({ face_count: 0 })]);
        }
      }
    }, PROCTORING_LOCAL_DETECT_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [active, cameraReady, completed, sessionId, startVerified]);

  useEffect(() => {
    if (!active || !sessionId || completed) return;
    const canImmediateBlockForPageExit = () => Boolean(cameraReady || startVerified || externalVerificationReadyRef.current);
    function onVisibility() {
      if (document.visibilityState === "hidden") {
        if (!canImmediateBlockForPageExit()) return;
        hiddenRef.current = true;
        failImmediately("app_hidden", "app_closed_or_hidden");
      }
    }
    function onBlur() {
      if (document.visibilityState === "visible") return;
      if (!canImmediateBlockForPageExit()) return;
      if (hiddenRef.current) return;
      hiddenRef.current = true;
      failImmediately("window_blur", "window_blur_or_closed");
    }
    function onFocus() {
      // Once the app is hidden during a protected test, backend owns the failed state.
    }
    function onOffline() {
      if (internetLostRef.current) return;
      internetLostRef.current = true;
      setOnline(false);
      setStatusText("Offline");
      startGraceCountdown(PROCTORING_CLIENT_OFFLINE_GRACE_SEC, { event_type: "internet_lost", event_status: "failed", reason_code: "internet_lost_timeout" });
      sendEvents([{ event_type: "internet_lost", event_status: "grace", reason_code: "internet_lost" }], [snapshotBase({ network_online: false })]).catch(() => null);
    }
    function onOnline() {
      if (!internetLostRef.current) return;
      internetLostRef.current = false;
      setOnline(true);
      clearGraceCountdown();
      setMonitorState("ok");
      setStatusText(startVerified ? "Face detected" : "FaceID tekshirilmoqda...");
      flushQueuedEvents().catch(() => null);
      if (!startVerified) {
        setVerifyRetryTick((value) => value + 1);
      }
      sendEvents([{ event_type: "internet_restored", event_status: "ok", reason_code: "internet_restored" }], [snapshotBase({ network_online: true })]).catch(() => null);
    }
    function onFullscreenChange() {
      const fullscreenNow = Boolean(document.fullscreenElement);
      if (!fullscreenNow && !fullscreenLostRef.current) {
        fullscreenLostRef.current = true;
        startGraceCountdown(PROCTORING_CLIENT_GRACE_SEC, { event_type: "fullscreen_exit", event_status: "failed", reason_code: "fullscreen_exit_timeout" });
        setStatusText("No face");
        sendEvents([{ event_type: "fullscreen_exit", event_status: "grace", reason_code: "fullscreen_exit" }], [snapshotBase()]).catch(() => null);
      } else if (fullscreenNow && fullscreenLostRef.current) {
        fullscreenLostRef.current = false;
        clearGraceCountdown();
        setMonitorState("ok");
        sendEvents([{ event_type: "fullscreen_restored", event_status: "ok", reason_code: "fullscreen_restored" }], [snapshotBase()]).catch(() => null);
      }
    }
    function onPageHide() {
      if (!canImmediateBlockForPageExit()) return;
      failImmediately("app_hidden", "page_closed");
    }
    function onBeforeUnload() {
      if (!canImmediateBlockForPageExit()) return;
      failImmediately("app_hidden", "page_unload");
    }
    function onKey(event: KeyboardEvent) {
      const key = String(event.key || "").toLowerCase();
      const code = String(event.code || "").toLowerCase();
      const isPrintScreen = key === "printscreen" || code === "printscreen";
      const isShiftCapture = event.ctrlKey && event.shiftKey && (key === "s" || code === "keys");
      const isMacCapture = (event.metaKey || event.ctrlKey) && event.shiftKey && (key === "3" || key === "4");
      if (!isPrintScreen && !isShiftCapture && !isMacCapture) return;
      const combo = isPrintScreen ? "PrintScreen" : isShiftCapture ? "Ctrl+Shift+S" : "Meta/Ctrl+Shift+3/4";
      sendEvents([{ event_type: "screenshot_attempt", event_status: "warning", reason_code: "keyboard_capture", details: { key_combination: combo } }], [snapshotBase()]).catch(() => null);
    }
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur", onBlur);
    window.addEventListener("focus", onFocus);
    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("beforeunload", onBeforeUnload);
    window.addEventListener("offline", onOffline);
    window.addEventListener("online", onOnline);
    document.addEventListener("fullscreenchange", onFullscreenChange);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("pagehide", onPageHide);
      window.removeEventListener("beforeunload", onBeforeUnload);
      window.removeEventListener("offline", onOffline);
      window.removeEventListener("online", onOnline);
      document.removeEventListener("fullscreenchange", onFullscreenChange);
      window.removeEventListener("keydown", onKey);
    };
  }, [active, completed, sessionId, cameraReady, startVerified]);

  useEffect(() => {
    if (!sessionId) return;
    if (!active && !completed) return;
    if (!completed || finishedRef.current) return;
    const token = getToken();
    if (!token) return;
    requestJson(`/student/proctoring/session/${sessionId}/complete`, {
      method: "POST",
      token,
      body: { final_status: "passed" },
    }).catch(() => null);
    finishedRef.current = true;
  }, [active, completed, sessionId]);

  useEffect(() => {
    return () => {
      if (!activeRef.current || completedRef.current || finishedRef.current) return;
      failImmediately("app_hidden", "route_left_test");
    };
  }, []);

  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  useEffect(() => {
    if (active && !completed) return;
    if (sessionStartAbortRef.current) {
      sessionStartAbortRef.current.abort();
      sessionStartAbortRef.current = null;
    }
    if (retryTimerRef.current) {
      window.clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current = null;
      releaseSharedUserFacingCamera();
    }
    detectorRef.current?.close?.();
    detectorRef.current = null;
    cameraStartingRef.current = false;
    verifyingRef.current = false;
    setCameraReady(false);
    setStartVerified(false);
    clearGraceCountdown();
  }, [active, completed]);

  useEffect(() => {
    return () => {
      if (sessionStartAbortRef.current) {
        sessionStartAbortRef.current.abort();
        sessionStartAbortRef.current = null;
      }
      sessionStartInFlightRef.current = null;
      streamRef.current = null;
      if (retryTimerRef.current) {
        window.clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
      releaseSharedUserFacingCamera();
      detectorRef.current?.close?.();
      detectorRef.current = null;
      cameraStartingRef.current = false;
      clearGraceCountdown();
    };
  }, []);

  const overlayMessage = useMemo(() => {
    if (fatalError) return normalizeProctoringRequestError(fatalError);
    if (startupStage === "session") return "FaceID tayyorlanmoqda...";
    if (startupStage === "camera") return "Kamera tayyorlanmoqda...";
    if (startupStage === "verifying") return "FaceID tekshirilmoqda...";
    if (startupStage === "retrying") return "FaceID qayta urinmoqda...";
    if (startupStage === "failed") return "FaceID tasdiqlanmadi";
    if (!cameraReady || cameraError) return cameraError || "Kamera tayyorlanmoqda...";
    if (!online) return "Offline";
    const lastSeenAgoMs = Date.now() - Number(lastValidFaceAtRef.current || 0);
    if (lastValidFaceAtRef.current > 0 && lastSeenAgoMs > 3200 && monitorState !== "error") {
      return "No face";
    }
    const normalized = String(statusText || "").trim().toLowerCase();
    if (normalized.includes("multiple")) return "Multiple faces";
    if (normalized.includes("looking")) return "Looking away";
    if (normalized.includes("offline")) return "Offline";
    if (normalized.includes("camera")) return "Camera unavailable";
    if (normalized.includes("face detected")) return "Face detected";
    return "No face";
  }, [cameraReady, cameraError, fatalError, online, startupStage, statusText]);

  if (!active) return null;
  const monitor = (
    <aside className={`proctoring-inline-card proctoring-floating-monitor ${className}`.trim()} aria-live="polite">
      <div className={`proctoring-cam-ring status-${monitorState}`}>
        {graceRemainingSec !== null ? (
          <div className="proctoring-grace-countdown">
            <span className="proctoring-grace-number">{graceRemainingSec}</span>
          </div>
        ) : null}
        <video ref={setPreviewVideoNode} className="proctoring-floating-video" autoPlay muted playsInline />
      </div>
      <div className={`proctoring-status-badge ${monitorState === "ok" ? "badge-ok" : monitorState === "grace" ? "badge-grace" : "badge-error"}`}>
        <span className="proctoring-status-dot" />
        <span>{overlayMessage}</span>
      </div>
    </aside>
  );

  const sourceVideo = (
    <video
      ref={setSourceVideoNode}
      className="proctoring-hidden-video-source"
      autoPlay
      muted
      playsInline
      aria-hidden="true"
      tabIndex={-1}
    />
  );

  if (!mounted) return sourceVideo;
  return (
    <>
      {sourceVideo}
      {monitor}
    </>
  );
}
