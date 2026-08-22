"use client";

import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AssetIcon } from "../ui/primitives";
import { resolveLocale, useWebT } from "../ui/web-i18n";
import { StudentTestProctoring, useStudentProctoringStatus } from "./proctoring";

export type GenericRow = Record<string, any>;

type StudentGrammarLevelsPayload = {
  subject: string;
  items: Array<{ level: string; topic_count: number }>;
};

type StudentGrammarTopicsPayload = {
  subject: string;
  level: string;
  page: number;
  pages: number;
  total: number;
  items: Array<{ topic_id: string; level: string; title: string; question_count: number }>;
};

type DailyTestRuntimeSession = {
  attempt_id: number;
  status: string;
  subject: string;
  level: string;
  question_index: number;
  total_questions: number;
  progress_percent: number;
  time_limit_sec: number;
  time_remaining_sec: number;
  deadline_at?: string;
  question_started_at?: string;
  completed: boolean;
  question?: {
    question_index: number;
    prompt: string;
    options: string[];
    question_type?: string;
    instruction?: string;
  };
  stats?: {
    correct: number;
    wrong: number;
    unanswered: number;
  };
  correct?: number;
  wrong?: number;
  skipped?: number;
  dpoints?: number;
  dcoin_breakdown?: GenericRow;
  dpoint_breakdown?: GenericRow;
  exists?: boolean;
  blocked?: boolean;
  blocked_reason?: string | null;
  message?: string;
  proctoring_required?: boolean;
  face_enrollment_required?: boolean;
  proctoring_session_id?: number;
  proctoring_stopped?: boolean;
  proctoring_failure_reason?: string | null;
  proctoring_failure_message?: string | null;
};

const DAILY_TEST_FIXED_QUESTION_COUNT = 20;


type CompetitionMode = "daily" | "group" | "boss" | "duel-1v1" | "duel-3v3" | "duel-5v5";

type CompetitionPhase = "pending" | "generating" | "active" | "finished";

type CompetitionParticipant = {
  user_id: number;
  name: string;
  status: string;
};

type CompetitionStatusPayload = {
  session_id: string;
  mode: CompetitionMode;
  subject: string;
  level: string;
  theme: string;
  status: "pending" | "generating" | "running" | "finished" | "expired" | "cancelled";
  phase: CompetitionPhase;
  progress_percent: number;
  question_index: number;
  total_questions: number;
  participants?: CompetitionParticipant[];
  participants_count?: number;
  joined_count?: number;
  required_players?: number;
  max_players?: number;
  remaining_players?: number;
  entry_fee?: number;
  minimum_participants?: number | null;
  group_id?: number | null;
  group_name?: string | null;
  teacher_name?: string | null;
  reward_settings?: GenericRow;
  generation_started?: boolean;
  generation_percent?: number;
  stage_generation_percent?: number;
  stage?: number;
  total_stages?: number;
  initial_participants?: number;
  active_participants_count?: number;
  eliminated_participants_count?: number;
  finalists_target?: number;
  podium?: Array<{ user_id: number; rank: number; dpoints_delta: number }>;
  started_at?: string;
  first_joined_at?: string | null;
  last_joined_at?: string | null;
  wait_deadline_at?: string | null;
  lobby_deadline?: string | null;
  allowed_wait_seconds?: number | null;
  wait_seconds?: number | null;
  waiting_remaining_sec?: number | null;
  seconds_left?: number | null;
  server_now?: string | null;
  refunded?: boolean;
  cancel_reason?: string | null;
  live?: { remained: string[]; left: string[] };
  result?: GenericRow | null;
  proctoring_required?: boolean;
  face_enrollment_required?: boolean;
  proctoring_block_reason?: string | null;
  daily_scoreboard?: Array<{
    user_id: number;
    name: string;
    status: string;
    total_correct: number;
    total_wrong: number;
  }>;
};

function parseCompetitionTimeMs(value: unknown): number {
  const raw = String(value || "").trim();
  if (!raw) return Number.NaN;
  const cleanRaw = raw.replace(/(\.\d{3})\d+/, "$1").replace(/\+00:00$/, "Z");
  const direct = Date.parse(cleanRaw);
  if (Number.isFinite(direct)) return direct;
  return Date.parse(cleanRaw.replace(" ", "T"));
}

type CompetitionQuestionPayload = {
  completed: boolean;
  phase?: CompetitionPhase;
  question_index: number;
  total_questions: number;
  progress_percent: number;
  time_limit_sec: number;
  time_remaining_sec: number;
  generation_started?: boolean;
  generation_percent?: number;
  stage_generation_percent?: number;
  stage?: number;
  total_stages?: number;
  initial_participants?: number;
  active_participants_count?: number;
  eliminated_participants_count?: number;
  finalists_target?: number;
  waiting_stage_completion?: boolean;
  waiting_completion?: boolean;
  eliminated?: boolean;
  question?: TestQuestionPayload;
  live?: { remained: string[]; left: string[] };
};

type TestQuestionPayload = {
  question_index?: number;
  prompt: string;
  passage?: string;
  instruction?: string;
  question_type?: string;
  subject?: string;
  language?: string;
  tts_language?: SpeechLang | string;
  options?: string[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
const API_REQUEST_TIMEOUT_MS = 25000;
const LOCALE_KEY = "diamond_locale";
const DEVICE_ID_KEY = "diamond_device_id";
const VOCABULARY_PAGE_LIMIT = 40;
const VOCABULARY_FIXED_QUIZ_COUNT = 20;
const VOCABULARY_LIST_TIMEOUT_MS = 45000;

type TelegramWebApp = {
  initData?: string;
  initDataUnsafe?: {
    user?: {
      id?: number;
    };
  };
  ready?: () => void;
};

function isTransientRequestError(message: string) {
  const lowered = String(message || "").toLowerCase();
  return (
    lowered.includes("internet sekin") ||
    lowered.includes("internet aloqasi") ||
    lowered.includes("so'rov vaqti") ||
    lowered.includes("so‘rov vaqti") ||
    lowered.includes("timed out") ||
    lowered.includes("timeout") ||
    lowered.includes("failed to fetch") ||
    lowered.includes("network") ||
    lowered.includes("tarmoq") ||
    lowered.includes("request failed")
  );
}

function normalizeNetworkError(error: unknown) {
  if (error instanceof DOMException && error.name === "AbortError") {
    return new Error("So'rov vaqti tugadi. Qayta urinib ko'ring.");
  }
  if (error instanceof TypeError) {
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      return new Error("Internet aloqasi yo'q. Ulanishni tekshirib qayta urinib ko'ring.");
    }
    return new Error("Tarmoq so'rovi bajarilmadi. Qayta urinib ko'ring.");
  }
  return error instanceof Error ? error : new Error("Request failed");
}

function isAuthErrorMessage(message: string) {
  const lowered = message.toLowerCase();
  return (
    lowered.includes("session expired") ||
    lowered.includes("invalid token") ||
    lowered.includes("not authenticated")
  );
}

function proctoringFriendlyError(reason: string) {
  let msg = String(reason || "");
  try {
    const parsed = JSON.parse(msg);
    if (parsed?.detail) msg = String(parsed.detail);
  } catch {
    // not JSON
  }
  const low = msg.toLowerCase();
  if (low.includes("insightface_provider_required") || low.includes("engine_error")) {
    return "Server FaceID modeli tayyor emas. Iltimos birozdan keyin qayta urinib ko'ring yoki supportga xabar bering.";
  }
  if (low.includes("profile_embedding_missing") || low.includes("embedding_missing") || low.includes("requires re-enrollment")) {
    return "FaceID profilingizni qayta sozlash kerak. Profil sahifasidan FaceID setup qiling.";
  }
  if (low.includes("no_face") || low.includes("face_missing") || low.includes("yuz aniqlanmadi")) {
    return "Yuz kamerada aniqlanmadi. Test to'xtatildi.";
  }
  if (low.includes("face_mismatch") || low.includes("face_not_verified")) {
    return "Yuz mos kelmadi. FaceID tekshiruvi muvaffaqiyatsiz.";
  }
  if (low.includes("multiple_faces")) {
    return "Kamerada bir nechta yuz aniqlandi. Test to'xtatildi.";
  }
  if (low.includes("camera")) {
    return "Kamera muammosi yuzaga keldi. Kamerani tekshirib qayta urinib ko'ring.";
  }
  if (low.includes("proctoring_start_failed")) {
    return "Proctoring tizimi ishga tushmadi. Qayta urinib ko'ring.";
  }
  return msg || "Proctoring tekshiruvi yakunlanmadi. Qayta urinib ko'ring.";
}

function proctoringStopReason(input: unknown) {
  let message = String(input ?? "").trim();
  try {
    const parsed = JSON.parse(message);
    if (parsed?.detail) message = String(parsed.detail);
  } catch {
    // plain text
  }
  const marker = "test stopped by proctoring:";
  const lower = message.toLowerCase();
  if (lower.includes(marker)) {
    return message.slice(lower.indexOf(marker) + marker.length).trim() || "proctoring_failed";
  }
  const known = [
    "face_missing_timeout",
    "face_mismatch",
    "multiple_faces",
    "looking_away",
    "face_too_small",
    "camera_denied",
    "camera_stream_lost",
    "proctoring_failed",
    "verify_start_failed",
  ];
  return known.find((item) => lower.includes(item)) || "";
}

function proctoringStoppedPayload<T extends GenericRow | null | undefined>(previous: T, reason: unknown): GenericRow {
  const rawReason = proctoringStopReason(reason) || String(reason || "proctoring_failed");
  const base: GenericRow = previous && typeof previous === "object" ? (previous as GenericRow) : {};
  const total = Number(base.total_questions || base.question_count || 0);
  const correct = Number(base.correct ?? base.stats?.correct ?? 0);
  const wrong = Number(base.wrong ?? base.stats?.wrong ?? 0);
  const skipped = Number(base.skipped ?? base.stats?.unanswered ?? Math.max(0, total - correct - wrong));
  return {
    ...base,
    completed: true,
    question: undefined,
    proctoring_stopped: true,
    proctoring_failure_reason: rawReason,
    proctoring_failure_message: proctoringFriendlyError(rawReason),
    correct,
    wrong,
    skipped,
    stats: {
      ...(base.stats || {}),
      correct,
      wrong,
      unanswered: skipped,
    },
    dpoints: Number(base.dpoints ?? base.dpoint_breakdown?.total_points ?? base.dcoin_breakdown?.total_points ?? 0),
  };
}

function isProctoringStopped(row: GenericRow | null | undefined) {
  return Boolean(row?.proctoring_stopped || row?.proctoring_failure_reason);
}

function proctoringMonitorClass() {
  return "test-proctoring-monitor";
}

async function requestJson<T>(path: string, options?: {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  token?: string | null;
  timeoutMs?: number;
  retries?: number;
  signal?: AbortSignal;
}): Promise<T> {
  const language = resolveLocale(typeof window === "undefined" ? "uz" : localStorage.getItem(LOCALE_KEY));
  const attempts = Math.max(1, Number(options?.retries || 0) + 1);
  let lastError: Error | null = null;

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const controller = new AbortController();
    let abortedByExternal = false;
    const signalListener = () => {
      abortedByExternal = true;
      controller.abort();
    };
    if (options?.signal) {
      if (options.signal.aborted) {
        controller.abort();
      } else {
        options.signal.addEventListener("abort", signalListener, { once: true });
      }
    }
    const timeout = window.setTimeout(() => controller.abort(), Number(options?.timeoutMs || API_REQUEST_TIMEOUT_MS));
    let response: Response;
    try {
      response = await fetch(`${API_BASE}${path}`, {
        method: options?.method || "GET",
        signal: controller.signal,
        headers: {
          ...(options?.token ? { Authorization: `Bearer ${options.token}` } : {}),
          ...(options?.body ? { "Content-Type": "application/json" } : {}),
          "X-Language": language,
        },
        ...(options?.body ? { body: JSON.stringify(options.body) } : {}),
      });
    } catch (error) {
      if (abortedByExternal) {
        lastError = new Error("Request aborted");
      } else {
        const normalized = normalizeNetworkError(error);
        lastError = normalized instanceof Error ? normalized : new Error("Request failed");
      }
      if (attempt + 1 >= attempts) break;
      await new Promise((resolve) => window.setTimeout(resolve, 350));
      continue;
    } finally {
      window.clearTimeout(timeout);
      if (options?.signal) {
        options.signal.removeEventListener("abort", signalListener);
      }
    }

    if (!response.ok) {
      if (response.status === 401 && options?.token) {
        localStorage.removeItem("diamond_token");
      }
      const text = await response.text().catch(() => "");
      if (text) {
        let detail = "";
        try {
          const parsed = JSON.parse(text) as { detail?: unknown; message?: string; error?: string };
          const detailRaw = parsed.detail;
          detail =
            typeof detailRaw === "string"
              ? detailRaw
              : detailRaw && typeof detailRaw === "object"
                ? String(
                    (detailRaw as { message?: unknown; detail?: unknown; code?: unknown }).message ||
                    (detailRaw as { message?: unknown; detail?: unknown; code?: unknown }).detail ||
                    ((detailRaw as { code?: unknown }).code === "face_enrollment_required"
                      ? "FaceID setup kerak. Profil sahifasidan FaceID setup qiling."
                      : ""),
                  )
                : String(parsed.message || parsed.error || "");
        } catch {
          detail = text;
        }
        throw new Error(String(detail || text || "Request failed"));
      }
      throw new Error("Request failed");
    }
    return response.json();
  }

  throw lastError || new Error("Request failed");
}

function normalizeSubjectLabel(raw: string) {
  const compact = raw.trim().replace(/\s+/g, " ");
  if (!compact) return "";
  const low = compact.toLowerCase();
  if (["english", "eng", "ingliz", "en"].includes(low)) return "English";
  if (["russian", "rus", "ru", "русский", "russian language"].includes(low)) return "Russian";
  return "";
}

function normalizeSubjectList(values: Array<string | null | undefined>, fallback: string[] = ["English"]) {
  const seen = new Set<string>();
  const normalized: string[] = [];
  let hasAnyValidInput = false;
  
  for (const value of values) {
    const rawStr = String(value || "").trim();
    if (rawStr) hasAnyValidInput = true;
    
    const cleaned = normalizeSubjectLabel(rawStr);
    if (!cleaned) continue;
    const key = cleaned.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    normalized.push(cleaned);
  }
  
  if (!normalized.length && !hasAnyValidInput) {
    return fallback.map((item) => normalizeSubjectLabel(item)).filter(Boolean);
  }
  return normalized;
}

export function studentSubjectNames(data: GenericRow, fallback: string[] = ["English"]) {
  // Primary source: subjects derived from the student's ACTIVE group memberships.
  // The backend serialises this as data.subjects (array from _user_subjects_from_row
  // which already reads only from live group rows for students).
  // We use this as the single authoritative list and do NOT merge other stale
  // fields like data.user.subjects or data.user.subject to avoid showing
  // subjects from groups the student has already left.
  const values: Array<string | null | undefined> = [];

  // 1st priority: pre-computed group subjects array from backend
  const subjectRows = Array.isArray(data?.subjects) ? data.subjects : [];
  for (const item of subjectRows) {
    values.push(typeof item === "string" ? item : String(item?.name || item?.subject || ""));
  }

  // 2nd priority: placement_subject (used when groups haven't loaded yet)
  if (values.filter(Boolean).length === 0) {
    const placementSubject = String(
      data?.user?.placement_subject || data?.placement?.subject || data?.subject || ""
    ).trim();
    if (placementSubject) values.push(placementSubject);
  }

  return normalizeSubjectList(values, fallback);
}

function subjectFromUrlOrState(subjects: string[], fallback = "English") {
  const fromUrl = normalizeSubjectLabel(readQueryValue("subject"));
  if (fromUrl) return fromUrl;
  return subjects[0] || fallback;
}

function subjectFromUrl(subjects: string[]) {
  void subjects;
  const fromUrl = normalizeSubjectLabel(readQueryValue("subject"));
  if (fromUrl) return fromUrl;
  return "";
}

function readSessionCache<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function writeSessionCache(key: string, value: unknown) {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Cache failures should never block lesson loading.
  }
}

function readQueryValue(key: string) {
  if (typeof window === "undefined") return "";
  return String(new URLSearchParams(window.location.search).get(key) || "").trim();
}

function getOrCreateDeviceId() {
  if (typeof window === "undefined") return "";
  const existing = localStorage.getItem(DEVICE_ID_KEY);
  if (existing) return existing;
  const next = `dev_${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
  localStorage.setItem(DEVICE_ID_KEY, next);
  return next;
}

function getTelegramMiniAppAuthPayload() {
  if (typeof window === "undefined") return null;
  const webApp = (window as Window & { Telegram?: { WebApp?: TelegramWebApp } }).Telegram?.WebApp;
  if (!webApp) return null;
  try {
    webApp.ready?.();
  } catch {
    // Telegram API is optional in normal browsers.
  }
  const telegramId = Number(webApp.initDataUnsafe?.user?.id || 0);
  const initData = String(webApp.initData || "").trim();
  if (telegramId > 0 && initData) return { telegram_id: telegramId, init_data: initData };
  return null;
}

async function ensureStandaloneStudentToken() {
  const currentToken = localStorage.getItem("diamond_token");
  const telegramPayload = getTelegramMiniAppAuthPayload();
  if (currentToken) {
    if (!telegramPayload) return currentToken;
    try {
      const me = await requestJson<GenericRow>("/auth/me", { token: currentToken, timeoutMs: 12000, retries: 1 });
      const tokenTelegramId = Number(me?.telegram_id || 0);
      if (!tokenTelegramId || tokenTelegramId === Number(telegramPayload.telegram_id || 0)) {
        return currentToken;
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      if (!isAuthErrorMessage(message) && !String(message).toLowerCase().includes("401")) {
        return currentToken;
      }
    }
    localStorage.removeItem("diamond_token");
  }
  if (!telegramPayload) return "";
  const response = await requestJson<{ access_token: string }>("/auth/telegram", {
    method: "POST",
    timeoutMs: 18000,
    retries: 1,
    body: {
      ...telegramPayload,
      device_id: getOrCreateDeviceId() || null,
      sync_bot_session: true,
    },
  });
  const token = String(response?.access_token || "");
  if (token) localStorage.setItem("diamond_token", token);
  return token;
}

type SpeechLang = "en-GB" | "ru-RU";
let vocabularySpeechAudio: HTMLAudioElement | null = null;
let speechVoicesWarmupPromise: Promise<void> | null = null;
let vocabularySpeechRequestId = 0;
let vocabularySpeechBlobUrl: string | null = null;

function speechLangForVocabularySubject(subject: string, word?: GenericRow): SpeechLang {
  const explicitLanguage = String(word?.language || "").trim().toLowerCase();
  if (explicitLanguage.startsWith("ru")) return "ru-RU";
  if (explicitLanguage.startsWith("en")) return "en-GB";

  const normalizedSubject = String(subject || word?.subject || "").trim().toLowerCase();
  if (normalizedSubject.includes("russian") || normalizedSubject.includes("рус")) return "ru-RU";
  return "en-GB";
}

function emitUiToast(message: string) {
  if (typeof window === "undefined") return;
  const text = String(message || "").trim();
  if (!text) return;
  window.dispatchEvent(new CustomEvent("diamond:toast", { detail: { message: text } }));
}

async function warmupSpeechVoices() {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  const synth = window.speechSynthesis;
  if (synth.getVoices().length) return;
  if (speechVoicesWarmupPromise) return speechVoicesWarmupPromise;
  speechVoicesWarmupPromise = new Promise<void>((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      try {
        synth.removeEventListener("voiceschanged", onVoicesChanged);
      } catch {
        // no-op
      }
      resolve();
    };
    const onVoicesChanged = () => finish();
    try {
      synth.addEventListener("voiceschanged", onVoicesChanged);
    } catch {
      // Safari may not support this reliably.
    }
    window.setTimeout(finish, 1200);
  }).finally(() => {
    speechVoicesWarmupPromise = null;
  });
  return speechVoicesWarmupPromise;
}

function pickPreferredVoice(voices: SpeechSynthesisVoice[], lang: SpeechLang) {
  const preferred = voices.filter((voice) => String(voice.lang || "").toLowerCase().startsWith(lang.toLowerCase()));
  if (!preferred.length) return null;
  const femaleHints = ["female", "woman", "zira", "susan", "hazel", "katya", "irina", "alina", "microsoft"];
  const byFemaleName = preferred.find((voice) =>
    femaleHints.some((hint) => String(voice.name || "").toLowerCase().includes(hint)),
  );
  return byFemaleName || preferred[0];
}

function stopVocabularySpeechPlayback() {
  if (typeof window === "undefined") return;
  try {
    window.speechSynthesis?.cancel();
  } catch {
    // no-op
  }
  if (vocabularySpeechAudio) {
    try {
      vocabularySpeechAudio.pause();
      vocabularySpeechAudio.currentTime = 0;
    } catch {
      // no-op
    }
  }
  if (vocabularySpeechBlobUrl) {
    try {
      URL.revokeObjectURL(vocabularySpeechBlobUrl);
    } catch {
      // no-op
    }
    vocabularySpeechBlobUrl = null;
  }
}

async function speakTextByLanguage(text: string, lang: SpeechLang) {
  if (typeof window === "undefined") return;
  const content = String(text || "").trim();
  if (!content) return;

  vocabularySpeechRequestId += 1;
  const requestId = vocabularySpeechRequestId;
  stopVocabularySpeechPlayback();

  if (!vocabularySpeechAudio) vocabularySpeechAudio = new Audio();
  (vocabularySpeechAudio as HTMLAudioElement & { playsInline?: boolean }).playsInline = true;

  const playViaBackendTts = async () => {
    if (requestId !== vocabularySpeechRequestId) return false;
    const voiceLang = lang === "ru-RU" ? "ru" : "en";
    const token = String(localStorage.getItem("diamond_token") || "").trim();
    const qs = new URLSearchParams();
    qs.set("text", content.slice(0, 220));
    qs.set("lang", voiceLang);
    const response = await fetch(`${API_BASE}/learning/tts?${qs.toString()}`, {
      method: "GET",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).catch(() => null);
    if (!response || !response.ok) return false;
    const blob = await response.blob().catch(() => null);
    if (!blob || !blob.size) return false;
    if (vocabularySpeechBlobUrl) {
      try {
        URL.revokeObjectURL(vocabularySpeechBlobUrl);
      } catch {
        // no-op
      }
    }
    vocabularySpeechBlobUrl = URL.createObjectURL(blob);
    vocabularySpeechAudio!.src = vocabularySpeechBlobUrl;
    vocabularySpeechAudio!.preload = "auto";
    try {
      await vocabularySpeechAudio!.play();
      return true;
    } catch {
      return false;
    }
  };

  const backendOk = await playViaBackendTts();
  if (!backendOk) emitUiToast("Audio ijro etilmadi. Qayta urinib ko'ring.");
}

function supportsTelegramBackButton(webApp: any): boolean {
  if (!webApp?.BackButton) return false;
  const btn = webApp.BackButton;
  return typeof btn.show === "function" && typeof btn.hide === "function";
}

function competitionRuntimePath(modeOrSection: string, options?: { subject?: string; autoJoin?: boolean }) {
  const normalized = String(modeOrSection || "").trim().toLowerCase();
  const map: Record<string, { path: string; arenaMode: string }> = {
    daily: { path: "/student/arena/daily/run", arenaMode: "arena-daily" },
    group: { path: "/student/arena/group/run", arenaMode: "arena-group" },
    boss: { path: "/student/arena/boss/run", arenaMode: "arena-boss" },
    "arena-daily": { path: "/student/arena/daily/run", arenaMode: "arena-daily" },
    "arena-group": { path: "/student/arena/group/run", arenaMode: "arena-group" },
    "arena-boss": { path: "/student/arena/boss/run", arenaMode: "arena-boss" },
    "duel-1v1": { path: "/student/duel/1v1/run", arenaMode: "duel-1v1" },
    "duel-3v3": { path: "/student/duel/3v3/run", arenaMode: "duel-3v3" },
    "duel-5v5": { path: "/student/duel/5v5/run", arenaMode: "duel-5v5" },
  };
  const target = map[normalized];
  if (!target) return null;
  const params = new URLSearchParams();
  params.set("arena_mode", target.arenaMode);
  if (options?.subject) params.set("subject", options.subject);
  if (options?.autoJoin) params.set("auto_join", "1");
  return `${target.path}?${params.toString()}`;
}

export function studentSectionToPath(section: string, options?: { subject?: string; autoJoin?: boolean }) {
  const normalized = String(section || "").trim().toLowerCase();
  const pageMap: Record<string, string> = {
    arena: "/?role=student&section=arena",
    "daily-test": "/?role=student&section=daily-test",
    vocabulary: "/?role=student&section=vocabulary",
    payments: "/?role=student&section=payments",
    gamified: "/?role=student&section=gamified",
  };
  if (pageMap[normalized]) return pageMap[normalized];
  if (normalized === "grammar" || normalized === "learn") {
    return "/?role=student&section=grammar";
  }
  const runtimePath = competitionRuntimePath(normalized, options || { autoJoin: false });
  if (runtimePath) return runtimePath;
  const testMap: Record<string, string> = {
    "vocabulary-process": "/?role=student&section=vocabulary-process",
    "daily-test-process": "/?role=student&section=daily-test-process",
  };
  if (testMap[normalized]) return testMap[normalized];
  return `/?role=student&section=${encodeURIComponent(normalized || "home")}`;
}

function answerBody(answer: number | null) {
  return { selected_option_index: answer };
}

function StudentQuestionRenderer({
  question,
  disabled,
  hideInstruction,
  singleColumn,
  onSubmit,
}: {
  question: TestQuestionPayload;
  disabled?: boolean;
  hideInstruction?: boolean;
  singleColumn?: boolean;
  onSubmit: (answer: number | null) => void;
}) {
  const [crossedOptions, setCrossedOptions] = useState<Set<string>>(new Set());
  const [selectedAnswer, setSelectedAnswer] = useState<{ key: string; index: number | null }>({ key: "", index: null });
  const longPressTimerRef = useRef<number | null>(null);
  const longPressTriggeredRef = useRef(false);
  const activeLongPressKeyRef = useRef("");
  const questionResetKey = [question.question_index ?? "", question.prompt || "", (question.options || []).join("|")].join("|");
  const selectedIndex = selectedAnswer.key === questionResetKey ? selectedAnswer.index : null;

  useEffect(() => {
    clearLongPressTimer();
    longPressTriggeredRef.current = false;
    setCrossedOptions(new Set());
    setSelectedAnswer({ key: questionResetKey, index: null });
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
    return clearLongPressTimer;
  }, [questionResetKey]);

  function clearLongPressTimer() {
    if (longPressTimerRef.current !== null) {
      window.clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
    activeLongPressKeyRef.current = "";
  }

  function toggleCrossed(key: string) {
    setCrossedOptions((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function startLongPress(key: string) {
    if (disabled) return;
    clearLongPressTimer();
    longPressTriggeredRef.current = false;
    activeLongPressKeyRef.current = key;
    longPressTimerRef.current = window.setTimeout(() => {
      if (activeLongPressKeyRef.current !== key) return;
      longPressTriggeredRef.current = true;
      toggleCrossed(key);
      clearLongPressTimer();
      if (typeof navigator !== "undefined" && "vibrate" in navigator) {
        navigator.vibrate?.(18);
      }
    }, 2000);
  }

  function finishLongPress() {
    const wasTriggered = longPressTriggeredRef.current;
    clearLongPressTimer();
    if (wasTriggered) {
      window.setTimeout(() => {
        longPressTriggeredRef.current = false;
      }, 80);
    }
  }

  const optionClass = (selected = false, crossed = false) =>
    `test-option-button ${selected ? "is-selected" : ""} relative group px-4 py-3.5 sm:p-5 rounded-2xl text-left transition-all duration-200 border-2 overflow-hidden ${
      selected
        ? "border-cyan-500 bg-cyan-50 text-navy-950 shadow-md dark:border-cyan-400 dark:bg-cyan-500/15 dark:text-white"
        : "border-line bg-surface-soft text-navy-900 hover:border-cyan-300 hover:bg-cyan-50 dark:border-white/10 dark:bg-navy-950/70 dark:text-slate-100 dark:hover:border-cyan-400 dark:hover:bg-cyan-500/10"
    } ${crossed ? "test-option-crossed border-rose-200 bg-rose-50/60 text-ink-600 dark:border-rose-400/35 dark:bg-rose-500/10 dark:text-slate-200" : ""} disabled:opacity-50 disabled:cursor-not-allowed`;

  const options = Array.isArray(question.options) ? question.options.slice(0, 4) : [];

  return (
    <>
      {question.instruction && !hideInstruction ? (
        <p className="mb-2 text-sm font-black uppercase tracking-wide text-cyan-700 dark:text-cyan-300">
          {question.instruction.replace(/[:\s-]+$/, "")}:
        </p>
      ) : null}
      {question.passage ? (
        <div className="mb-4 sm:mb-5 rounded-2xl border border-line bg-surface-soft p-3 sm:p-5 text-[15px] sm:text-base leading-relaxed sm:leading-7 text-navy-900 dark:border-white/10 dark:bg-navy-950/70 dark:text-slate-100">
          {question.passage}
        </div>
      ) : null}
      <div className="mb-6 sm:mb-8 flex items-start justify-between gap-3">
        {question.prompt && question.prompt.toLowerCase() !== (question.instruction || "").toLowerCase() ? (
          <h3 className="text-xl sm:text-3xl font-bold text-navy-900 dark:text-white leading-tight">
            {question.instruction && question.prompt.toLowerCase().startsWith(question.instruction.toLowerCase())
              ? question.prompt.substring(question.instruction.length).replace(/^[:\s-]+/, '')
              : question.prompt}
          </h3>
        ) : <span />}
      </div>
      <div className={`grid gap-4 ${singleColumn ? "grid-cols-1" : "sm:grid-cols-2"}`}>
        {options.map((option, idx) => {
          const key = `main-${idx}`;
          const crossed = crossedOptions.has(key);
          const selected = selectedIndex === idx;
          return (
            <button
              type="button"
              key={`mcq-${questionResetKey}-${idx}`}
              className={optionClass(selected, crossed)}
              disabled={disabled}
              onPointerDown={() => startLongPress(key)}
              onPointerUp={finishLongPress}
              onPointerCancel={finishLongPress}
              onPointerLeave={finishLongPress}
              onContextMenu={(event) => event.preventDefault()}
              onClick={(event) => {
                if (longPressTriggeredRef.current) {
                  event.preventDefault();
                  event.currentTarget.blur();
                  window.setTimeout(() => {
                    longPressTriggeredRef.current = false;
                  }, 0);
                  return;
                }
                clearLongPressTimer();
                setSelectedAnswer({ key: questionResetKey, index: idx });
                event.currentTarget.blur();
                onSubmit(idx);
              }}
            >
              <div className="relative flex items-center gap-3 sm:gap-4">
                <span className={`test-option-letter w-7 h-7 sm:w-8 sm:h-8 text-sm sm:text-base rounded-xl shadow-sm flex items-center justify-center font-bold flex-shrink-0 ${
                  selected
                    ? "bg-cyan-500 text-white dark:bg-cyan-400 dark:text-navy-950"
                    : "bg-white text-ink-500 group-hover:text-cyan-600 dark:bg-navy-800 dark:group-hover:text-cyan-400"
                }`}>
                  {String.fromCharCode(65 + idx)}
                </span>
                <span className={`font-medium text-[15px] sm:text-lg ${crossed ? "line-through decoration-2 decoration-rose-500/80 dark:decoration-rose-300/90" : ""}`}>{option}</span>
              </div>
            </button>
          );
        })}
      </div>
    </>
  );
}


export function StudentStandaloneTestShell({
  children,
  fullscreen = false,
}: {
  children: (payload: { data: GenericRow; onNavigate: (section: string) => void }) => ReactNode;
  fullscreen?: boolean;
}) {
  const router = useRouter();
  const tt = useWebT();
  const [data, setData] = useState<GenericRow>({});
  const [authReady, setAuthReady] = useState(false);
  const navigateStudent = (section: string) => {
    router.push(studentSectionToPath(section));
  };

  // Proctoring class is managed dynamically by child test views (e.g. StudentGamified on phase === "playing")


  useEffect(() => {
    const webApp = (window as any)?.Telegram?.WebApp;
    if (!supportsTelegramBackButton(webApp)) return;
    const onBack = () => {
      navigateStudent("home");
    };
    try {
      webApp.initBackButton?.();
      webApp.BackButton.offClick?.(onBack);
      webApp.BackButton.onClick(onBack);
      webApp.BackButton.show();
    } catch {
      // ignore Telegram API errors
    }
    return () => {
      try {
        webApp.BackButton.offClick?.(onBack);
        webApp.BackButton.hide();
      } catch {
        // ignore Telegram API errors
      }
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function loadState() {
      const token = await ensureStandaloneStudentToken().catch(() => "");
      if (!token) {
        router.replace("/login");
        return;
      }
      if (!cancelled) setAuthReady(true);
      try {
        const payload = await requestJson<GenericRow>("/app/state", { token, timeoutMs: 30000, retries: 1 });
        if (cancelled) return;
        setData((payload?.student || {}) as GenericRow);
      } catch (err) {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : "Could not load student data";
        if (isAuthErrorMessage(message)) {
          localStorage.removeItem("diamond_token");
          router.replace("/login");
          return;
        }
        // Runtime test pages own their loading/error UI; keep them mounted on slow app-state refreshes.
      }
    }
    loadState();
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (!authReady) {
    return (
      <main className={fullscreen ? "duel-fullscreen-page" : "placement-page"}>
        <section className={fullscreen ? "duel-fullscreen-shell" : "placement-card"}>
          <div className="flex min-h-[40vh] items-center justify-center text-center font-bold text-navy-900 dark:text-white">
            {tt("common.loading", "Yuklanmoqda...")}
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className={fullscreen ? "duel-fullscreen-page" : "placement-page"}>
      <section className={fullscreen ? "duel-fullscreen-shell" : "placement-card"}>
        {children({ data, onNavigate: navigateStudent })}
      </section>
    </main>
  );
}
export function StudentGrammar({ data }: { data: GenericRow }) {
  const router = useRouter();
  const tt = useWebT();
  const studentSubjects = studentSubjectNames(data);
  const allowedSubjects: string[] = studentSubjects.filter((s) => s === "English" || s === "Russian");
  const showSubjectSelector = allowedSubjects.includes("English") && allowedSubjects.includes("Russian");
  const [selectedSubject, setSelectedSubject] = useState<string>(allowedSubjects[0] || "English");
  const [selectedLevel, setSelectedLevel] = useState("A1");
  const [levels, setLevels] = useState<Array<{ level: string; topic_count: number }>>([
    { level: "A1", topic_count: 0 },
    { level: "A2", topic_count: 0 },
    { level: "B1", topic_count: 0 },
    { level: "B2", topic_count: 0 },
    { level: "C1", topic_count: 0 },
  ]);
  const [topics, setTopics] = useState<Array<{ topic_id: string; level: string; title: string; question_count: number }>>([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [levelsLoading, setLevelsLoading] = useState(false);
  const [error, setError] = useState("");
  const levelsAbortRef = useRef<AbortController | null>(null);
  const topicsAbortRef = useRef<AbortController | null>(null);
  const topicsCacheRef = useRef<Map<string, StudentGrammarTopicsPayload>>(new Map());
  const isRussianGrammar = selectedSubject === "Russian";

  useEffect(() => {
    if (allowedSubjects.length && !allowedSubjects.includes(selectedSubject)) {
      setSelectedSubject(allowedSubjects[0]);
    }
  }, [allowedSubjects, selectedSubject]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const subjectFromUrl = normalizeSubjectLabel(params.get("subject") || "");
    if (subjectFromUrl && allowedSubjects.includes(subjectFromUrl)) {
      setSelectedSubject(subjectFromUrl);
    }
    const levelFromUrl = String(params.get("level") || "").trim().toUpperCase();
    if (["A1", "A2", "B1", "B2", "C1"].includes(levelFromUrl)) {
      setSelectedLevel(levelFromUrl);
    }
  }, [allowedSubjects]);

  useEffect(() => {
    setPage(1);
  }, [selectedSubject]);

  useEffect(() => {
    if (isRussianGrammar) {
      if (selectedLevel !== "ALL") setSelectedLevel("ALL");
      setPage(1);
    } else if (selectedLevel === "ALL") {
      setSelectedLevel("A1");
      setPage(1);
    }
  }, [isRussianGrammar, selectedLevel]);

  useEffect(() => {
    const token = localStorage.getItem("diamond_token");
    if (!token) return;
    if (isRussianGrammar) {
      levelsAbortRef.current?.abort();
      setLevels([]);
      setLevelsLoading(false);
      setError("");
      return;
    }
    let cancelled = false;
    levelsAbortRef.current?.abort();
    const controller = new AbortController();
    levelsAbortRef.current = controller;
    async function loadLevels() {
      setError("");
      const cacheKey = `student:grammar:levels:${selectedSubject.toLowerCase()}`;
      const cached = readSessionCache<StudentGrammarLevelsPayload>(cacheKey);
      if (cached) {
        const items = cached.items || [];
        setLevels(items);
        const allowed = items.map((x) => x.level);
        if (items.length && !allowed.includes(selectedLevel)) {
          setSelectedLevel(items[0]?.level || "A1");
        }
      }
      setLevelsLoading(!cached);
      try {
        const payload = await requestJson<StudentGrammarLevelsPayload>(`/student/grammar/levels?subject=${encodeURIComponent(selectedSubject)}`, {
          token,
          timeoutMs: 12000,
          retries: 1,
          signal: controller.signal,
        });
        if (cancelled) return;
        const items = payload.items || [];
        writeSessionCache(cacheKey, payload);
        setLevels(items);
        const allowed = items.map((x) => x.level);
        if (!allowed.includes(selectedLevel)) {
          setSelectedLevel(items[0]?.level || "A1");
        }
      } catch (err) {
        if (!cancelled && !(err instanceof Error && err.message === "Request aborted")) {
          setError(err instanceof Error ? err.message : tt("student.grammar.error.loadLevels", "Could not load grammar levels"));
        }
      } finally {
        if (!cancelled) {
          setLevelsLoading(false);
        }
      }
    }
    loadLevels();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [selectedSubject, isRussianGrammar]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const token = localStorage.getItem("diamond_token");
    if (!token) return;
    let cancelled = false;
    topicsAbortRef.current?.abort();
    const controller = new AbortController();
    topicsAbortRef.current = controller;
    async function loadTopics() {
      setError("");
      try {
        const level = isRussianGrammar ? "ALL" : selectedLevel === "ALL" ? "A1" : selectedLevel;
        const cacheKey = `${selectedSubject}|${level}|${page}`;
        const cached = topicsCacheRef.current.get(cacheKey);
        if (cached) {
          setTopics(cached.items || []);
          setPages(Math.max(1, Number(cached.pages || 1)));
          setLoading(false);
          return;
        }
        const persistedKey = `student:grammar:topics:${selectedSubject.toLowerCase()}:${level}:${page}`;
        const persisted = readSessionCache<StudentGrammarTopicsPayload>(persistedKey);
        if (persisted) {
          topicsCacheRef.current.set(cacheKey, persisted);
          setTopics(persisted.items || []);
          setPages(Math.max(1, Number(persisted.pages || 1)));
        }
        setLoading(!persisted);
        const payload = await requestJson<StudentGrammarTopicsPayload>(
          `/student/grammar/topics?subject=${encodeURIComponent(selectedSubject)}&level=${encodeURIComponent(level)}&page=${page}&per_page=24`,
          { token, timeoutMs: 12000, retries: 1, signal: controller.signal },
        );
        if (cancelled) return;
        topicsCacheRef.current.set(cacheKey, payload);
        writeSessionCache(persistedKey, payload);
        setTopics(payload.items || []);
        setPages(Math.max(1, Number(payload.pages || 1)));
      } catch (err) {
        if (!cancelled && !(err instanceof Error && err.message === "Request aborted")) {
          setError(err instanceof Error ? err.message : tt("student.grammar.error.loadTopics", "Could not load grammar topics"));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadTopics();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [selectedSubject, selectedLevel, page, isRussianGrammar]);

  useEffect(() => {
    if (page < 1) setPage(1);
  }, [selectedLevel, page]);

  function openTopic(lesson: { topic_id: string; level: string; title: string; question_count: number }) {
    const url = `/student/grammar/${encodeURIComponent(lesson.topic_id)}?subject=${encodeURIComponent(selectedSubject)}&level=${encodeURIComponent(lesson.level)}&topic_id=${encodeURIComponent(lesson.topic_id)}&title=${encodeURIComponent(lesson.title || "")}&question_count=${encodeURIComponent(String(lesson.question_count || 0))}`;
    router.push(url);
  }

  return (
    <div className="flex flex-col gap-4 pb-12 animate-fade-in">
      <section className="grammar-filter-panel p-4 sm:p-5 bg-white border border-line dark:bg-navy-900/60 dark:border-white/10 rounded-2xl shadow-premium flex flex-col md:flex-row gap-4 sm:gap-6">
        {showSubjectSelector ? (
          <div className="flex-1 min-w-0">
            <p className="text-[11px] font-bold text-ink-500 dark:text-navy-300 uppercase tracking-wider mb-2">{tt("duel.subject", "Fan")}</p>
            <div className="flex flex-wrap gap-1.5">
              {allowedSubjects.map((subject) => (
                <button key={subject} className={`grammar-filter-button px-3 py-2 text-sm font-bold rounded-xl transition-all ${selectedSubject === subject ? "is-active bg-navy-900 text-white shadow-md dark:bg-cyan-500 dark:text-navy-900" : "bg-surface-soft text-navy-700 hover:bg-line dark:bg-white/10 dark:text-white/70 dark:hover:bg-white/20"}`} onClick={() => setSelectedSubject(subject)}>
                  {subject}
                </button>
              ))}
            </div>
          </div>
        ) : null}
        {!isRussianGrammar ? (
          <div className="flex-1 min-w-0">
            <p className="text-[11px] font-bold text-ink-500 dark:text-navy-300 uppercase tracking-wider mb-2">{tt("student.grammar.level", "Level")}</p>
            <div className="flex flex-wrap gap-1.5">
              {(levels.length ? levels.map((item) => item.level) : ["A1", "A2", "B1", "B2", "C1"]).map((level) => (
                <button
                  key={level}
                  className={`grammar-filter-button px-3 py-2 text-sm font-bold rounded-xl transition-all ${selectedLevel === level ? "is-active bg-cyan-500 text-white shadow-md" : "bg-surface-soft text-navy-700 hover:bg-line dark:bg-white/10 dark:text-white/70 dark:hover:bg-white/20"}`}
                  onClick={() => {
                    setSelectedLevel(level);
                    setPage(1);
                  }}
                >
                  {level}
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </section>
      {error ? <div className="px-4 py-3 text-sm font-semibold text-red-200 bg-red-500/20 border border-red-500/30 rounded-xl">{error}</div> : null}
      <section className="grammar-topic-grid grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4" aria-busy={loading || levelsLoading}>
        {loading ? <article className="p-5 text-center text-ink-500 dark:text-navy-200 font-medium bg-transparent rounded-2xl sm:col-span-2 lg:col-span-3 animate-pulse">{tt("student.grammar.loadingTopics", "Mavzular yuklanmoqda...")}</article> : null}
        {!loading && !topics.length ? <article className="p-5 text-center text-ink-500 dark:text-navy-200 font-medium bg-transparent rounded-2xl sm:col-span-2 lg:col-span-3">{isRussianGrammar ? tt("student.grammar.emptyAllTopics", "Grammar mavzulari topilmadi.") : tt("student.grammar.emptyTopics", "Bu level uchun grammatika mavzulari topilmadi.")}</article> : null}
        {topics.map((lesson) => (
          <article className="grammar-topic-card p-4 sm:p-5 bg-white border border-line dark:bg-navy-950/70 dark:border-white/10 rounded-2xl shadow-premium hover:shadow-premium-hover transition-all flex flex-col justify-between min-w-0" key={lesson.topic_id}>
            <div>
              {!isRussianGrammar ? <span className="px-2.5 py-1 text-[11px] font-bold tracking-wider uppercase rounded-md bg-cyan-500/10 text-cyan-500 inline-block mb-2">{lesson.level}</span> : null}
              <h3 className="grammar-topic-title text-base font-bold text-navy-900 font-display dark:text-white mb-1.5" title={lesson.title}>{lesson.title}</h3>
              <p className="text-xs font-medium text-ink-500 dark:text-navy-300 mb-4">{lesson.question_count || 0} {tt("student.grammar.questions", "savol")}</p>
            </div>
            <button className="w-full px-3 py-2.5 text-xs sm:text-sm font-bold text-navy-900 bg-surface-soft hover:bg-line dark:bg-white/10 dark:text-white dark:hover:bg-white/20 rounded-xl transition-colors" onClick={() => openTopic(lesson)}>
              {tt("student.grammar.openRuleTest", "Qoida va testni ochish")}
            </button>
          </article>
        ))}
      </section>
      {pages > 1 ? (
        <section className="flex items-center justify-center gap-4 mt-4">
          <button className="px-5 py-2.5 font-bold text-navy-900 bg-white shadow-sm border border-line rounded-xl hover:bg-surface-soft dark:bg-navy-900/50 dark:border-white/10 dark:text-white dark:hover:bg-white/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" disabled={page <= 1} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>{tt("common.prev", "Oldingi")}</button>
          <span className="px-4 py-2 font-bold text-ink-700 dark:text-ink-300">{tt("common.page", "Sahifa")} {page} / {pages}</span>
          <button className="px-5 py-2.5 font-bold text-navy-900 bg-white shadow-sm border border-line rounded-xl hover:bg-surface-soft dark:bg-navy-900/50 dark:border-white/10 dark:text-white dark:hover:bg-white/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" disabled={page >= pages} onClick={() => setPage((prev) => Math.min(pages, prev + 1))}>{tt("common.next", "Keyingi")}</button>
        </section>
      ) : null}
    </div>
  );
}

export function StudentVocabulary({
  data,
  onNavigate,
}: {
  data: GenericRow;
  onNavigate?: (section: string) => void;
}) {
  const router = useRouter();
  const tt = useWebT();
  const studentSubjects = studentSubjectNames(data);
  const allowedSubjects: string[] = studentSubjects.filter((s) => s === "English" || s === "Russian");
  const showSubjectSelector = allowedSubjects.includes("English") && allowedSubjects.includes("Russian");
  const [selectedSubject, setSelectedSubject] = useState<string>(allowedSubjects[0] || "English");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [words, setWords] = useState<GenericRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [vocabularyStatus, setVocabularyStatus] = useState("");
  // Qidirilgan so'z bazada yo'q bo'lsa backend AI bilan tayyorlaydi —
  // 1 sekunddan ortiq ketsa kutish banneri chiqadi (i18n).
  const [aiPreparing, setAiPreparing] = useState(false);
  const aiPrepareTimerRef = useRef<number | null>(null);
  const [speakingKey, setSpeakingKey] = useState("");
  const [testStarting, setTestStarting] = useState(false);
  const vocabularyCacheRef = useRef(new Map<string, { items: GenericRow[]; total: number; has_more: boolean }>());

  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const synth = window.speechSynthesis;
    const warmup = () => {
      synth.getVoices();
    };
    warmup();
    synth.addEventListener("voiceschanged", warmup);
    return () => {
      synth.removeEventListener("voiceschanged", warmup);
      stopVocabularySpeechPlayback();
    };
  }, []);

  useEffect(() => {
    if (allowedSubjects.length && !allowedSubjects.includes(selectedSubject)) {
      setSelectedSubject(allowedSubjects[0]);
    }
  }, [allowedSubjects, selectedSubject]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedQuery(query.trim());
    }, 450);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    setPage(1);
  }, [selectedSubject, debouncedQuery]);

  useEffect(() => {
    const token = localStorage.getItem("diamond_token");
    if (!token) return;
    const controller = new AbortController();
    let cancelled = false;
    async function loadWords() {
      const cacheKey = `v2::${selectedSubject.toLowerCase()}::${debouncedQuery.toLowerCase()}::${page}::${VOCABULARY_PAGE_LIMIT}`;
      const persistedKey = `student:vocabulary:${cacheKey}`;
      const cached = vocabularyCacheRef.current.get(cacheKey);
      let displayedCached = false;
      if (cached) {
        setWords((prev) => (page === 1 ? cached.items : [...prev.filter((item) => !cached.items.some((next) => String(next.id) === String(item.id))), ...cached.items]));
        setTotal(cached.total);
        setHasMore(cached.has_more);
        setError("");
        displayedCached = true;
      } else {
        const persisted = readSessionCache<{ items: GenericRow[]; total: number; has_more: boolean }>(persistedKey);
        if (persisted) {
          vocabularyCacheRef.current.set(cacheKey, persisted);
          setWords((prev) => (page === 1 ? persisted.items : [...prev.filter((item) => !persisted.items.some((next) => String(next.id) === String(item.id))), ...persisted.items]));
          setTotal(persisted.total);
          setHasMore(persisted.has_more);
          setError("");
          displayedCached = true;
        }
      }
      setLoading(!displayedCached);
      setError("");
      setVocabularyStatus(displayedCached ? "Lug'at yangilanmoqda..." : "");
      const isSearchFetch = debouncedQuery.trim().length > 0 && !displayedCached;
      if (aiPrepareTimerRef.current !== null) {
        window.clearTimeout(aiPrepareTimerRef.current);
        aiPrepareTimerRef.current = null;
      }
      setAiPreparing(false);
      if (isSearchFetch) {
        aiPrepareTimerRef.current = window.setTimeout(() => {
          if (!cancelled) setAiPreparing(true);
        }, 1000);
      }
      try {
        const path = `/vocabulary?subject=${encodeURIComponent(selectedSubject)}&query=${encodeURIComponent(debouncedQuery)}&page=${page}&limit=${VOCABULARY_PAGE_LIMIT}`;
        const payload = await requestJson<{ items: GenericRow[]; total?: number; has_more?: boolean }>(path, {
          token,
          signal: controller.signal,
          timeoutMs: VOCABULARY_LIST_TIMEOUT_MS,
          retries: 2,
        });
        if (cancelled) return;
        const items = payload.items || [];
        const nextCache = {
          items,
          total: Number(payload.total || items.length || 0),
          has_more: Boolean(payload.has_more),
        };
        vocabularyCacheRef.current.set(cacheKey, nextCache);
        writeSessionCache(persistedKey, nextCache);
        setWords((prev) => (page === 1 ? items : [...prev.filter((item) => !items.some((next) => String(next.id) === String(item.id))), ...items]));
        setTotal(Number(payload.total || items.length || 0));
        setHasMore(Boolean(payload.has_more));
        setVocabularyStatus("");
      } catch (err) {
        if (!cancelled && !controller.signal.aborted) {
          const message = err instanceof Error ? err.message : "Could not load vocabulary";
          if (displayedCached && isTransientRequestError(message)) {
            setVocabularyStatus("Internet sekin, qayta urinilyapti...");
          } else {
            setError(message);
            setVocabularyStatus("");
          }
        }
      } finally {
        if (aiPrepareTimerRef.current !== null) {
          window.clearTimeout(aiPrepareTimerRef.current);
          aiPrepareTimerRef.current = null;
        }
        if (!cancelled) {
          setAiPreparing(false);
          setLoading(false);
        }
      }
    }
    loadWords();
    return () => {
      cancelled = true;
      if (aiPrepareTimerRef.current !== null) {
        window.clearTimeout(aiPrepareTimerRef.current);
        aiPrepareTimerRef.current = null;
      }
      controller.abort();
    };
  }, [selectedSubject, debouncedQuery, page]);

  async function handleSpeak(text: string, lang: SpeechLang, key: string) {
    const content = String(text || "").trim();
    if (!content) return;
    setSpeakingKey(key);
    await speakTextByLanguage(content, lang);
    window.setTimeout(() => {
      setSpeakingKey((prev) => (prev === key ? "" : prev));
    }, 300);
  }

  return (
    <div className="flex flex-col gap-4 pb-12 animate-fade-in">
      <section className="p-4 sm:p-5 bg-white border border-line dark:bg-white/5 dark:border-white/10 rounded-2xl shadow-premium text-navy-900 dark:text-white">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="min-w-0">
            <h3 className="mb-1 text-base sm:text-lg font-black font-display tracking-tight">{tt("section.vocabulary-process", "Vocabulary Test Process")}</h3>
            <p className="text-xs sm:text-sm text-ink-500 dark:text-navy-300 font-medium">{tt("student.vocabulary.processHint", "Vocabulary test flow alohida runtime test sahifada ochiladi.")}</p>
          </div>
          <div className="flex w-full flex-col gap-2 sm:w-auto sm:min-w-[240px]">
            <label className="text-[11px] font-bold text-ink-500 dark:text-navy-300 uppercase tracking-wider">{tt("duel.subject", "Fan")}</label>
            {showSubjectSelector ? (
              <select className="px-3 py-2.5 bg-white border border-line dark:bg-navy-800 dark:border-white/10 rounded-xl outline-none focus:ring-2 focus:ring-cyan-500 transition-all font-semibold text-sm text-navy-900 dark:text-white w-full" value={selectedSubject} onChange={(event) => setSelectedSubject(event.target.value)}>
                {allowedSubjects.map((subject) => (
                  <option key={`vocab-start-${subject}`} value={subject}>{subject}</option>
                ))}
              </select>
            ) : (
              <strong className="px-3 py-2.5 bg-surface-soft border border-line dark:bg-navy-900/50 dark:border-white/10 rounded-xl font-bold text-sm text-navy-900 dark:text-white w-full">{selectedSubject}</strong>
            )}
            <button
              className="px-4 py-2.5 text-sm font-bold text-white bg-navy-900 dark:bg-cyan-500 dark:text-navy-950 rounded-xl shadow-sm hover:scale-[1.02] transition-all whitespace-nowrap disabled:opacity-70 disabled:hover:scale-100"
              disabled={testStarting || !selectedSubject}
              onClick={() => {
                if (!selectedSubject) {
                  setError(tt("arena.subjectRequired", "Fan tanlang"));
                  return;
                }
                setTestStarting(true);
                const params = new URLSearchParams({
                  subject: selectedSubject,
                  quiz_type: "mixed",
                  question_count: String(VOCABULARY_FIXED_QUIZ_COUNT),
                });
                router.push(`/student/vocabulary/process/run?${params.toString()}`);
              }}
            >
              {testStarting ? tt("common.loading", "Yuklanmoqda...") : tt("student.dailyTest.openProcess", "Testni boshlash")}
            </button>
          </div>
        </div>
      </section>
      
      <section className="p-4 sm:p-5 bg-white border border-line dark:bg-white/5 dark:border-white/10 rounded-2xl shadow-premium flex flex-col md:flex-row gap-3 items-center">
        {showSubjectSelector ? (
          <div className="flex flex-col gap-1 w-full md:w-auto">
            <label className="text-[11px] font-bold text-ink-500 dark:text-navy-300 uppercase tracking-wider ml-1">{tt("duel.subject", "Fan")}</label>
            <select className="px-3 py-2.5 bg-white border border-line dark:bg-navy-800 dark:border-white/10 rounded-xl outline-none focus:ring-2 focus:ring-cyan-500 transition-all font-semibold text-sm text-navy-900 dark:text-white min-w-[140px]" value={selectedSubject} onChange={(event) => setSelectedSubject(event.target.value)}>
              {allowedSubjects.map((subject) => (
                <option key={subject} value={subject}>{subject}</option>
              ))}
            </select>
          </div>
        ) : (
          <div className="flex flex-col gap-1 w-full md:w-auto">
            <span className="text-[11px] font-bold text-ink-500 dark:text-navy-300 uppercase tracking-wider ml-1">{tt("duel.subject", "Fan")}</span>
            <strong className="px-3 py-2.5 bg-surface-soft border border-line dark:bg-navy-900/50 dark:border-white/10 rounded-xl font-bold text-sm text-navy-900 dark:text-white min-w-[140px]">{selectedSubject}</strong>
          </div>
        )}
        <div className="flex flex-col gap-1 w-full flex-1">
          <label className="text-[11px] font-bold text-ink-500 dark:text-navy-300 uppercase tracking-wider ml-1">{tt("common.search", "Qidirish")}</label>
          <div className="relative">
            <input className="w-full px-3 py-2.5 pl-10 bg-surface-soft border border-line dark:bg-navy-900/50 dark:border-white/10 rounded-xl outline-none focus:ring-2 focus:ring-cyan-500 transition-all font-medium text-sm text-navy-900 dark:text-white placeholder:text-ink-400" placeholder={tt("student.vocabulary.searchPlaceholder", "So'z yoki tarjima qidiring...")} value={query} onChange={(event) => setQuery(event.target.value)} />
            <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-400 text-base">🔍</span>
          </div>
        </div>
      </section>
      
      {error ? <div className="px-4 py-3 text-sm font-semibold text-red-200 bg-red-500/20 border border-red-500/30 rounded-xl">{error}</div> : null}
      {aiPreparing && !error ? (
        <div className="px-4 py-3 flex items-center justify-center gap-3 text-sm font-bold text-cyan-700 bg-cyan-500/10 border border-cyan-500/20 rounded-xl dark:text-cyan-200">
          <span className="inline-block w-4 h-4 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" aria-hidden="true"></span>
          {tt("student.vocabulary.aiPreparing", "So'z bazada topilmadi — AI tayyorlamoqda, biroz kuting...")}
        </div>
      ) : null}
      {vocabularyStatus ? (
        <div className="px-4 py-2 text-xs font-bold text-cyan-700 bg-cyan-500/10 border border-cyan-500/20 rounded-xl dark:text-cyan-200">
          {vocabularyStatus}
        </div>
      ) : null}
      {loading && words.length ? (
        <div className="px-4 py-2 text-xs font-bold text-cyan-700 bg-cyan-500/10 border border-cyan-500/20 rounded-xl dark:text-cyan-200">
          {tt("student.vocabulary.loading", "Lug'at yuklanmoqda...")}
        </div>
      ) : null}
      
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {loading && page === 1 && !words.length ? <article className="p-8 text-center text-ink-500 font-medium bg-transparent rounded-2xl md:col-span-2 lg:col-span-3 animate-pulse">{tt("student.vocabulary.loading", "Lug'at yuklanmoqda...")}</article> : null}
        {!loading && !words.length ? <article className="p-8 text-center text-ink-500 font-medium bg-transparent rounded-2xl md:col-span-2 lg:col-span-3">{tt("student.vocabulary.empty", "So'zlar topilmadi.")}</article> : null}
        {words.map((word, idx) => {
          const wordSpeechLang = speechLangForVocabularySubject(selectedSubject, word);
          const wordSpeechKey = `word-${wordSpeechLang}-${word.id || idx}`;
          return (
          <article className="p-6 bg-white border border-line dark:bg-white/5 dark:border-white/10 rounded-2xl shadow-premium flex flex-col gap-4 transition-transform hover:-translate-y-1" key={`${word.id || word.word || "w"}`}>
            <div>
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-xl font-bold text-navy-900 font-display dark:text-white">{word.word || "-"}</h3>
                <button
                  type="button"
                  aria-label={wordSpeechLang === "ru-RU" ? "Russian pronunciation" : "English pronunciation"}
                  className="p-2 rounded-xl border border-line dark:border-white/10 bg-surface-soft dark:bg-white/5 text-cyan-600 dark:text-cyan-300 hover:bg-cyan-50 dark:hover:bg-cyan-500/20 transition-colors"
                  onClick={() => handleSpeak(String(word.word || ""), wordSpeechLang, wordSpeechKey)}
                >
                  {speakingKey === wordSpeechKey ? (
                    <span className="text-[10px] font-bold uppercase tracking-wide">...</span>
                  ) : (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5 6 9H2v6h4l5 4V5zm7.54 2.46a5 5 0 010 7.08M15.5 9.5a2 2 0 010 5" /></svg>
                  )}
                </button>
              </div>
              <p className="text-sm text-ink-500 italic mt-1">{word.definition || "-"}</p>
            </div>
            
            <div className="flex flex-col gap-2 mt-auto pt-4 border-t border-line dark:border-white/10">
              <div className="flex items-center justify-between text-sm">
                <span className="font-bold text-ink-400 uppercase tracking-wider text-xs">UZ:</span>
                <strong className="font-semibold text-navy-900 dark:text-white">{word.translation_uz || "-"}</strong>
              </div>
              {(!selectedSubject.toLowerCase().includes("rus") && !selectedSubject.toLowerCase().includes("ру")) && (
                <div className="flex items-center justify-between text-sm">
                  <span className="font-bold text-ink-400 uppercase tracking-wider text-xs">RU:</span>
                  <div className="flex items-center gap-2">
                    <strong className="font-semibold text-navy-900 dark:text-white">{word.translation_ru || "-"}</strong>
                    <button
                      type="button"
                      aria-label="Russian pronunciation"
                      className="p-1.5 rounded-lg border border-line dark:border-white/10 bg-surface-soft dark:bg-white/5 text-cyan-600 dark:text-cyan-300 hover:bg-cyan-50 dark:hover:bg-cyan-500/20 transition-colors"
                      onClick={() => handleSpeak(String(word.translation_ru || word.word || ""), "ru-RU", `ru-${word.id || idx}`)}
                    >
                      {speakingKey === `ru-${word.id || idx}` ? (
                        <span className="text-[9px] font-bold uppercase tracking-wide">...</span>
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5 6 9H2v6h4l5 4V5zm7.54 2.46a5 5 0 010 7.08M15.5 9.5a2 2 0 010 5" /></svg>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </div>
            
            {word.example ? (
              <div className="mt-2 p-3 bg-transparent rounded-lg border-l-2 border-cyan-500">
                <p className="text-sm text-ink-700 dark:text-ink-300">"{word.example}"</p>
              </div>
            ) : null}
          </article>
          );
        })}
      </section>
      <section className="flex flex-col items-center gap-3">
        {total > 0 ? (
          <p className="text-sm font-semibold text-ink-500">
            {words.length}/{total}
          </p>
        ) : null}
        {hasMore ? (
          <button
            className="px-5 py-3 rounded-xl border border-line bg-white text-navy-900 font-bold shadow-sm hover:bg-surface-soft dark:bg-white/5 dark:border-white/10 dark:text-white dark:hover:bg-white/10 disabled:opacity-60"
            type="button"
            disabled={loading}
            onClick={() => setPage((prev) => prev + 1)}
          >
            {loading ? tt("common.loading", "Yuklanmoqda...") : tt("common.loadMore", "Ko'proq yuklash")}
          </button>
        ) : null}
      </section>
    </div>
  );
}

export function StudentVocabularyProcess({
  data,
  onNavigate,
  mode = "launcher",
}: {
  data: GenericRow;
  onNavigate: (section: string) => void;
  mode?: "launcher" | "runtime";
}) {
  const router = useRouter();
  const tt = useWebT();
  const runtimeMode = mode === "runtime";
  const studentSubjects = useMemo(() => studentSubjectNames(data), [data]);
  const studentSubjectKey = studentSubjects.join("|");
  const allowedSubjects = useMemo<string[]>(() => studentSubjects.filter((s) => s === "English" || s === "Russian"), [studentSubjects]);
  const showSubjectSelector = allowedSubjects.includes("English") && allowedSubjects.includes("Russian");
  const [subject, setSubject] = useState<string>(() => subjectFromUrlOrState(allowedSubjects));
  const [quizSession, setQuizSession] = useState<GenericRow | null>(null);
  const [quizBusy, setQuizBusy] = useState(false);
  const [error, setError] = useState("");
  const [timeLeft, setTimeLeft] = useState(30);
  const [proctoringSessionId, setProctoringSessionId] = useState<number | null>(null);
  const [proctoringReady, setProctoringReady] = useState(false);
  const [runtimeBooted, setRuntimeBooted] = useState(false);
  const [runtimeConfigReady, setRuntimeConfigReady] = useState(!runtimeMode);
  const quizAnswerInFlightRef = useRef(false);
  const [runtimeStartConfig, setRuntimeStartConfig] = useState<{
    subject: string;
  } | null>(null);

  async function startQuiz(overrides?: {
    overrideSubject?: string;
  }) {
    const token = localStorage.getItem("diamond_token");
    if (!token) return;
    const targetSubject = normalizeSubjectLabel(String(overrides?.overrideSubject || subject || "")) || subjectFromUrlOrState(allowedSubjects);
    const targetQuizType = "mixed";
    const targetQuizCount = VOCABULARY_FIXED_QUIZ_COUNT;
    setQuizBusy(true);
    setError("");
    setProctoringReady(false);
    try {
      const payload = await requestJson<GenericRow>("/vocabulary/quiz/start", {
        token,
        method: "POST",
        body: {
          subject: targetSubject,
          level: "ALL",
          quiz_type: targetQuizType,
          question_count: targetQuizCount,
        },
      });
      setQuizSession(payload);
      setTimeLeft(30);
      const nextProctoringId = Number(payload.proctoring_session_id || 0) || null;
      const requiresProctoring = Boolean((payload as GenericRow).proctoring_required);
      setProctoringSessionId(nextProctoringId);
      setProctoringReady(!requiresProctoring);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start vocabulary quiz");
    } finally {
      setQuizBusy(false);
    }
  }

  async function submitQuizAnswer(answer: number | null) {
    const token = localStorage.getItem("diamond_token");
    if (!token || !quizSession?.session_id) return;
    if (runtimeMode && (proctoringSessionId || quizSession?.proctoring_required) && !proctoringReady) return;
    if (quizAnswerInFlightRef.current) return;
    quizAnswerInFlightRef.current = true;
    setQuizBusy(true);
    setError("");
    try {
      const payload = await requestJson<GenericRow>("/vocabulary/quiz/answer", {
        token,
        method: "POST",
        body: {
          session_id: quizSession.session_id,
          ...answerBody(answer),
          proctoring_session_id: proctoringSessionId,
        },
      });
      setQuizSession(payload);
      setTimeLeft(30);
    } catch (err) {
      const reason = proctoringStopReason(err instanceof Error ? err.message : err);
      if (reason) {
        setError("");
        setProctoringReady(false);
        setQuizSession((prev) => proctoringStoppedPayload(prev, reason));
      } else {
        setError(err instanceof Error ? err.message : "Could not submit vocabulary answer");
      }
    } finally {
      setQuizBusy(false);
      quizAnswerInFlightRef.current = false;
    }
  }

  useEffect(() => {
    const initialSubject = subjectFromUrlOrState(allowedSubjects);
    setSubject((prev) => (allowedSubjects.includes(prev) ? prev : initialSubject));
    if (!runtimeMode) {
      setRuntimeConfigReady(true);
      return;
    }
    setRuntimeStartConfig({
      subject: allowedSubjects.includes(initialSubject) ? initialSubject : (allowedSubjects[0] || "English"),
    });
    setRuntimeConfigReady(true);
  }, [studentSubjectKey, runtimeMode, allowedSubjects]);

  useEffect(() => {
    if (!runtimeMode) return;
    if (!runtimeConfigReady) return;
    if (!runtimeStartConfig) return;
    if (runtimeBooted || quizBusy || quizSession?.question || quizSession?.completed) return;
    setRuntimeBooted(true);
    startQuiz({
      overrideSubject: runtimeStartConfig.subject,
    }).catch(() => null);
  }, [runtimeMode, runtimeConfigReady, runtimeStartConfig, runtimeBooted, quizBusy, quizSession?.question, quizSession?.completed]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!runtimeMode) {
    const runtimeParams = new URLSearchParams({
      subject,
      quiz_type: "mixed",
      question_count: String(VOCABULARY_FIXED_QUIZ_COUNT),
    });
    return (
      <div className="flex flex-col gap-8 pb-12 animate-fade-in">
        <section className="p-8 bg-white border border-line dark:bg-white/5 dark:border-white/10 rounded-[2rem] shadow-premium max-w-3xl mx-auto w-full">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            {showSubjectSelector ? (
              <div className="flex flex-col gap-2">
                <label className="text-xs font-bold text-ink-500 uppercase tracking-wider ml-1">Subject</label>
                <select
                  className="px-4 py-3 bg-white border border-line dark:bg-navy-800 dark:border-white/10 rounded-xl outline-none focus:ring-2 focus:ring-cyan-500 transition-all font-semibold text-navy-900 dark:text-white w-full"
                  value={subject}
                  onChange={(event) => setSubject(event.target.value)}
                >
                  {allowedSubjects.map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                <span className="text-xs font-bold text-ink-500 uppercase tracking-wider ml-1">Subject</span>
                <strong className="px-4 py-3 bg-surface-soft border border-line dark:bg-navy-900/50 dark:border-white/10 rounded-xl font-bold text-navy-900 dark:text-white w-full">{subject}</strong>
              </div>
            )}
            <div className="flex flex-col gap-2">
              <span className="text-xs font-bold text-ink-500 uppercase tracking-wider ml-1">Test</span>
              <strong className="px-4 py-3 bg-surface-soft border border-line dark:bg-navy-900/50 dark:border-white/10 rounded-xl font-bold text-navy-900 dark:text-white w-full">
                Mixed · {VOCABULARY_FIXED_QUIZ_COUNT} savol
              </strong>
            </div>
          </div>
          <button
            className="w-full px-6 py-4 text-lg font-bold text-white bg-cyan-500 hover:bg-cyan-600 rounded-xl shadow-[0_0_20px_rgba(6,182,212,0.3)] hover:shadow-[0_0_30px_rgba(6,182,212,0.5)] transition-all hover:-translate-y-1"
            onClick={() => router.push(`/student/vocabulary/process/run?${runtimeParams.toString()}`)}
          >
            Start Vocabulary Test
          </button>
        </section>
      </div>
    );
  }

  useEffect(() => {
    if (!runtimeMode) return;
    if (!quizSession?.question || quizSession?.completed || quizBusy) return;
    setTimeLeft(30);
  }, [runtimeMode, quizSession?.question_index, quizSession?.completed, quizBusy]);

  useEffect(() => {
    if (!runtimeMode) return;
    if (!quizSession?.question || quizSession?.completed || quizBusy || !proctoringReady) return;
    const timer = window.setInterval(() => {
      setTimeLeft((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [runtimeMode, quizSession?.question_index, quizSession?.completed, quizBusy, proctoringReady]);

  useEffect(() => {
    if (!runtimeMode) return;
    if (!quizSession?.question || quizSession?.completed || quizBusy || !proctoringReady) return;
    if (timeLeft > 0) return;
    submitQuizAnswer(null);
  }, [runtimeMode, timeLeft, quizSession?.question_index, quizSession?.completed, quizBusy, proctoringReady]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex min-h-[100dvh] max-h-[100dvh] flex-col overflow-hidden bg-background selection:bg-cyan-500/30 selection:text-cyan-900 dark:selection:text-cyan-100 relative">
      {error && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[60] bg-red-100 text-red-700 px-4 py-2 rounded-xl shadow-lg border border-red-200 text-sm font-medium animate-fade-in-up">
          {error}
        </div>
      )}
      
      <div className="flex-1 overflow-y-auto w-full p-3 sm:p-6 lg:p-8">
        <div className="max-w-4xl mx-auto space-y-6 relative">
          
          <StudentTestProctoring
            active={Boolean(proctoringSessionId && quizSession?.question && !quizSession?.completed)}
            completed={Boolean(quizSession?.completed)}
            initialSessionId={proctoringSessionId}
            testType="vocabulary"
            testAttemptRef={String(quizSession?.session_id || "") || undefined}
            testRoute="/student/vocabulary/process/run"
            onSessionReady={(id) => {
              setProctoringSessionId(id);
              setTimeLeft(30);
            }}
            onVerificationStateChange={(ready) => {
              setProctoringReady(ready);
            }}
            onTerminated={(reason) => {
              setError("");
              setProctoringReady(false);
              setQuizSession((prev) => proctoringStoppedPayload(prev, reason));
            }}
            className={proctoringMonitorClass()}
          />

          {quizSession?.question && !quizSession?.completed && (
            <div className={`space-y-4 sm:space-y-5 relative text-slate-900 dark:text-white ${!proctoringReady ? "select-none" : ""}`}>
              {!proctoringReady ? (
                <div className="proctoring-blur-overlay absolute inset-0 z-50 bg-white/65 dark:bg-navy-950/65 backdrop-blur-[2px] flex items-center justify-center text-center p-5 rounded-3xl">
                  <div className="test-proctoring-wait-card px-5 py-4 rounded-2xl bg-white dark:bg-navy-900 border border-cyan-200 dark:border-cyan-500/30 shadow-premium">
                    <p className="font-black text-navy-900 dark:text-white">
                      {quizSession?.face_enrollment_required ? tt("duel.faceSetup", "FaceID setup kerak") : tt("duel.faceChecking", "FaceID tekshirilmoqda...")}
                    </p>
                    <p className="text-sm text-ink-500 dark:text-navy-200">
                      {quizSession?.face_enrollment_required ? tt("duel.faceSetupDesc", "Profil sahifasidan FaceID setup qiling. Kamerasiz test ishlamaydi.") : tt("duel.faceCheckingDesc", "Test FaceID tasdiqlangandan keyin boshlanadi.")}
                    </p>
                  </div>
                </div>
              ) : null}
              
              <div className="sticky top-4 z-40 rounded-3xl border border-slate-200 bg-white/90 dark:border-slate-700 dark:bg-slate-900/90 backdrop-blur-xl p-3.5 sm:p-5 shadow-premium space-y-2 sm:space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2 sm:gap-3">
                  <div>
                    <h2 className="text-lg sm:text-2xl font-black text-navy-900 dark:text-white font-display tracking-tight">{tt("student.vocabulary.testTitle", "Vocabulary test")}</h2>
                    <p className="text-[10px] sm:text-sm text-cyan-600 dark:text-cyan-400 font-bold tracking-wide uppercase">{subject}</p>
                  </div>
                  <div className={`px-3 py-2 rounded-xl text-sm font-black ${timeLeft > 10 ? "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-100 border border-slate-200 dark:border-slate-700" : "bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-200 border border-red-200 dark:border-red-500/30 animate-pulse"}`}>
                    ⏳ {Math.floor(timeLeft / 60)}:{String(timeLeft % 60).padStart(2, "0")}
                  </div>
                </div>
                <div className="h-2.5 rounded-full bg-slate-200/50 dark:bg-navy-950 overflow-hidden shadow-inner border border-white/10">
                  <div className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-blue-500 transition-all duration-500 shadow-[0_0_10px_rgba(34,211,238,0.5)]" style={{ width: `${Math.max(0, Math.min(100, Number(quizSession.progress_percent || 0)))}%` }} />
                </div>
                <div className="flex flex-wrap items-center justify-between text-xs font-bold text-slate-500 dark:text-slate-400">
                  <span>Savol {quizSession.question_index || 1} / {quizSession.total_questions || 10}</span>
                </div>
              </div>

              <div className="relative rounded-3xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 backdrop-blur-sm p-4 sm:p-8 shadow-xl space-y-4 sm:space-y-6">
                <StudentQuestionRenderer
                  question={quizSession.question as TestQuestionPayload}
                  disabled={quizBusy || timeLeft <= 0 || !proctoringReady}
                  hideInstruction={true}
                  onSubmit={submitQuizAnswer}
                />
              </div>
            </div>
          )}

          {!quizSession?.question && !quizSession?.completed ? (
            <div className="vocabulary-preparing-card bg-white text-navy-900 dark:bg-navy-950/85 dark:text-white rounded-[2rem] p-6 sm:p-8 shadow-premium border border-line dark:border-cyan-300/15 text-center">
              <div className="mx-auto mb-5 h-14 w-14 rounded-2xl bg-cyan-500/10 text-cyan-600 dark:text-cyan-300 flex items-center justify-center">
                {error ? (
                  <span className="text-2xl font-black">!</span>
                ) : (
                  <svg className="h-7 w-7 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                  </svg>
                )}
              </div>
              <h2 className="text-2xl font-black text-navy-900 dark:text-white">
                {error ? tt("student.vocabulary.startFailed", "Vocabulary test boshlanmadi") : tt("student.vocabulary.preparing", "Vocabulary test tayyorlanmoqda...")}
              </h2>
              <p className="mt-2 text-sm font-medium text-ink-500 dark:text-navy-200">
                {error || tt("student.vocabulary.preparingDesc", "Savollar tayyorlanmoqda, bir necha soniya kuting.")}
              </p>
              {quizBusy && !error ? <p className="mt-4 text-xs font-bold uppercase tracking-wide text-cyan-600 dark:text-cyan-300">{tt("student.vocabulary.preparingShort", "Tayyorlanmoqda")}</p> : null}
              {error ? (
                <button
                  className="mt-5 px-5 py-3 rounded-xl bg-navy-900 text-white dark:bg-cyan-500 font-bold"
                  type="button"
                  onClick={() => {
                    setError("");
                    setRuntimeBooted(false);
                  }}
                >
                  {tt("student.vocabulary.retry", "Qayta urinish")}
                </button>
              ) : null}
            </div>
          ) : null}

          {quizSession?.completed && (
            <div className="test-result-card bg-white dark:bg-navy-950/90 rounded-[2rem] p-4 sm:p-6 shadow-premium border border-line dark:border-white/10 text-center relative overflow-hidden">
              <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-blue-500/10 to-transparent" />
              
              <div className={`w-24 h-24 mx-auto ${isProctoringStopped(quizSession) ? "bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400" : "bg-green-100 dark:bg-green-500/20 text-green-600 dark:text-green-400"} rounded-full flex items-center justify-center mb-6 relative`}>
                {isProctoringStopped(quizSession) ? (
                  <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" /></svg>
                ) : (
                  <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                )}
              </div>
              
              <h3 className="text-3xl font-bold text-navy-900 dark:text-white mb-2">
                {isProctoringStopped(quizSession) ? tt("student.tests.proctorStopped", "Test proctoring sabab to'xtatildi") : tt("student.tests.finished", "Test yakunlandi!")}
              </h3>
              <p className="text-ink-500 mb-4">
                {isProctoringStopped(quizSession) ? tt("duel.proctorStoppedDesc", "Test xavfsizlik tekshiruvi sabab yakunlandi.") : tt("student.tests.resultReady", "Natijalaringiz tayyor.")}
              </p>
              {isProctoringStopped(quizSession) ? (
                <div className="mb-8 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-bold text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200">
                  {tt("common.reason", "Sabab")}: {quizSession.proctoring_failure_message || proctoringFriendlyError(String(quizSession.proctoring_failure_reason || ""))}
	                  </div>
	                ) : null}

		                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-10">
                <div className="bg-transparent p-4 rounded-2xl border border-line dark:border-white/10">
                  <p className="text-sm font-medium text-ink-500 mb-1">{tt("student.dailyTest.correct", "To'g'ri")}</p>
                  <p className="text-2xl font-bold text-green-600 dark:text-green-400">{Number(quizSession.correct || 0)}</p>
                </div>
                <div className="bg-transparent p-4 rounded-2xl border border-line dark:border-white/10">
                  <p className="text-sm font-medium text-ink-500 mb-1">{tt("student.dailyTest.wrong", "Noto'g'ri")}</p>
                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{Number(quizSession.wrong || 0)}</p>
                </div>
                <div className="bg-transparent p-4 rounded-2xl border border-line dark:border-white/10">
                  <p className="text-sm font-medium text-ink-500 mb-1">{tt("student.dailyTest.skipped", "O'tkazilgan")}</p>
                  <p className="text-2xl font-bold text-ink-600 dark:text-navy-300">{Number(quizSession.skipped || 0)}</p>
                </div>
                <div className="bg-transparent p-4 rounded-2xl border border-blue-100 dark:border-blue-500/20">
                  <p className="currency-inline text-sm font-medium text-ink-500 mb-1">
                    <AssetIcon type="dpoint" size={18} />
                    D'Points
                  </p>
                  <p className="text-2xl font-bold text-cyan-600 dark:text-cyan-400">
                    {`${Number(quizSession.dpoints || 0) > 0 ? "+" : ""}${Number(quizSession.dpoints || 0).toFixed(1)}`}
                  </p>
                </div>
              </div>
              
              <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                <button
                  className="bg-navy-900 hover:bg-navy-800 text-white dark:bg-cyan-500 dark:hover:bg-cyan-600 px-8 py-4 rounded-2xl font-bold text-lg shadow-lg shadow-blue-500/30 transition-all hover:-translate-y-1"
                  onClick={() => {
                    setQuizSession(null);
                    setRuntimeBooted(false);
                  }}
                >
                  {tt("student.tests.startNew", "Yangi test boshlash")}
                </button>
                <button
                  className="bg-surface-soft hover:bg-line dark:bg-white/10 dark:hover:bg-white/20 text-navy-900 dark:text-white px-8 py-4 rounded-2xl font-bold text-lg border border-line dark:border-white/10 transition-all hover:-translate-y-1"
                  onClick={() => {
                    setQuizSession(null);
                    setRuntimeBooted(false);
                    if (runtimeMode) router.push(studentSectionToPath("vocabulary"));
                    else onNavigate("vocabulary");
                  }}
                >
                  {tt("common.back", "Orqaga")}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Gamified tests. 20 questions, mixed interactive types.
// Scoring: correct +2 / wrong -3 / skipped -1.5 — graded server-side on
// final submit. Immediate per-question feedback via /check-answer and
// /check-pair endpoints (read-only, never leaks the full answer key).
// ---------------------------------------------------------------------------
type GamifiedType = "word_match" | "word_order" | "fill_gap" | "mcq" | "heading_match" | "reading_mcq" | "reading_true_false";

type GamifiedQuestion = {
  index: number;
  type: GamifiedType;
  prompt: string;
  score_units?: number;
  options?: string[];
  sentence?: string;
  words?: string[];
  left?: string[];
  right?: string[];
  items?: Array<{ id: string; text: string }>;
  headings?: string[];
  passage?: string;
};

type GamifiedScoring = { correct: number; wrong: number; skipped: number };

type GamifiedStartResponse = {
  session_id: string;
  subject: string;
  level?: string;
  total: number;
  question_blocks?: number;
  score_units?: number;
  requested_count?: number;
  ready_count?: number;
  ready_percent?: number;
  generated_by_ai?: boolean;
  scoring: GamifiedScoring;
  questions: GamifiedQuestion[];
};

type GamifiedSummary = {
  correct: number;
  wrong: number;
  skipped: number;
  total: number;
  score: number;
  subject: string;
  awarded_dpoints: number;
  scoring: GamifiedScoring;
};

// Feedback state for a single question (shown as overlay before advancing)
type GamifiedFeedback = { correct: boolean; checked: boolean } | null;

const GAMIFIED_LETTERS = ["A", "B", "C", "D", "E", "F"];
const GAMIFIED_TARGET_QUESTIONS = 20;

function gamifiedQuestionUnits(question?: GamifiedQuestion | null): number {
  if (!question) return 0;
  const direct = Number(question.score_units || 0);
  if (direct > 0) return Math.max(1, Math.round(direct));
  if (question.type === "word_match") return Math.max(1, question.left?.length || 0);
  if (question.type === "heading_match") return Math.max(1, question.items?.length || 0);
  return 1;
}

// ── Feedback overlay shown after checking an MCQ/fill_gap answer ─────────────
function GamifiedFeedbackOverlay({
  feedback,
  onNext,
  nextLabel,
  busy,
}: {
  feedback: GamifiedFeedback;
  onNext: () => void;
  nextLabel: string;
  busy: boolean;
}) {
  if (!feedback?.checked) return null;
  const ok = feedback.correct;
  return (
    <div
      className={`fixed bottom-0 left-0 right-0 z-50 px-4 pb-safe-bottom pt-5 shadow-2xl transition-all duration-300 ${
        ok
          ? "bg-emerald-500 dark:bg-emerald-600"
          : "bg-rose-500 dark:bg-rose-600"
      }`}
    >
      <div className="mx-auto max-w-lg">
        <div className="mb-3 flex items-center gap-3">
          <div className={`grid h-10 w-10 shrink-0 place-items-center rounded-full ${
            ok ? "bg-white/20" : "bg-white/20"
          }`}>
            {ok ? (
              <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            )}
          </div>
          <p className="text-lg font-black text-white">
            {ok ? "To'g'ri! " : "Xato"}
          </p>
        </div>
        <button
          type="button"
          onClick={onNext}
          disabled={busy}
          className="w-full rounded-2xl bg-white/20 hover:bg-white/30 border border-white/30 py-3.5 text-base font-black text-white transition active:scale-95 disabled:opacity-60"
        >
          {nextLabel}
        </button>
      </div>
    </div>
  );
}

// ── MCQ / fill_gap choice ───────────────────────────────────────────────────
function GamifiedChoice({
  options,
  value,
  onChange,
  feedback,
  disabled,
}: {
  options: string[];
  value: number | null;
  onChange: (index: number) => void;
  feedback?: GamifiedFeedback;
  disabled?: boolean;
}) {
  return (
    <div className="grid gap-2.5">
      {options.map((option, idx) => {
        const active = value === idx;
        let borderClass = "border-line bg-surface-soft/60 hover:border-cyan-300/50 hover:bg-cyan-400/[0.04] dark:border-white/10 dark:bg-white/[0.04]";
        let badgeClass = "bg-white text-ink-600 shadow-sm dark:bg-white/10 dark:text-slate-200";
        if (active && feedback?.checked) {
          if (feedback.correct) {
            borderClass = "border-emerald-400/70 bg-emerald-400/10 dark:border-emerald-300/50 dark:bg-emerald-300/10";
            badgeClass = "bg-emerald-500 text-white";
          } else {
            borderClass = "border-rose-400/70 bg-rose-400/10 dark:border-rose-300/50 dark:bg-rose-300/10";
            badgeClass = "bg-rose-500 text-white";
          }
        } else if (active) {
          borderClass = "border-cyan-400/70 bg-cyan-400/10 shadow-sm dark:border-cyan-300/50 dark:bg-cyan-300/10";
          badgeClass = "bg-cyan-500 text-white dark:bg-cyan-400 dark:text-navy-950";
        }
        return (
          <button
            key={`${idx}-${option}`}
            type="button"
            onClick={() => !disabled && onChange(idx)}
            disabled={disabled}
            className={`flex items-center gap-3 rounded-2xl border px-4 py-3.5 text-left transition-all ${
              borderClass
            } ${disabled && !active ? "opacity-60" : ""}`}
          >
            <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl text-sm font-black transition-colors ${badgeClass}`}>
              {GAMIFIED_LETTERS[idx] || idx + 1}
            </span>
            <span className="min-w-0 flex-1 text-sm font-bold text-navy-900 dark:text-white">{option}</span>
            {active && feedback?.checked && (
              <span className="ml-auto shrink-0">
                {feedback.correct ? (
                  <svg className="w-5 h-5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                ) : (
                  <svg className="w-5 h-5 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                )}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// ── Word order ───────────────────────────────────────────────────────────────
function GamifiedWordOrder({
  words,
  value,
  onChange,
  disabled,
}: {
  words: string[];
  value: number[];
  onChange: (next: number[]) => void;
  disabled?: boolean;
}) {
  const used = new Set(value);
  const available = words.map((w, i) => ({ w, i })).filter(({ i }) => !used.has(i));
  return (
    <div className="grid gap-3">
      <div className="min-h-[56px] rounded-2xl border border-dashed border-line bg-surface-soft/50 p-3 dark:border-white/10 dark:bg-white/[0.03]">
        {value.length ? (
          <div className="flex flex-wrap gap-2">
            {value.map((wi, pos) => (
              <button
                key={`sel-${wi}-${pos}`}
                type="button"
                onClick={() => !disabled && onChange(value.filter((_, p) => p !== pos))}
                disabled={disabled}
                className="rounded-xl border border-cyan-400/50 bg-cyan-400/10 px-3 py-2 text-sm font-black text-navy-900 transition hover:-translate-y-0.5 dark:border-cyan-300/40 dark:bg-cyan-300/10 dark:text-white disabled:opacity-60"
              >
                {words[wi]}
              </button>
            ))}
          </div>
        ) : (
          <span className="text-xs font-semibold text-ink-400 dark:text-slate-500">So'zlarni tanlab gapni tuzing</span>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        {available.map(({ w, i }) => (
          <button
            key={`av-${i}`}
            type="button"
            onClick={() => !disabled && onChange([...value, i])}
            disabled={disabled}
            className="rounded-xl border border-line bg-white px-3 py-2 text-sm font-black text-navy-900 shadow-sm transition hover:-translate-y-0.5 hover:border-cyan-300/60 dark:border-white/10 dark:bg-white/10 dark:text-white disabled:opacity-60"
          >
            {w}
          </button>
        ))}
        {!available.length ? (
          <span className="text-xs font-semibold text-ink-400 dark:text-slate-500">Barcha so'zlar ishlatildi</span>
        ) : null}
      </div>
    </div>
  );
}

// ── Word match ───────────────────────────────────────────────────────────────
function GamifiedWordMatch({
  left,
  right,
  value,
  onChange,
  pairResults,
  disabled,
}: {
  left: string[];
  right: string[];
  value: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
  pairResults?: Record<string, boolean | null>;
  disabled?: boolean;
}) {
  const [activeLeft, setActiveLeft] = useState<string | null>(null);
  const usedRight = new Set(Object.values(value));

  function pickRight(r: string) {
    if (!activeLeft || disabled) return;
    const next = { ...value };
    for (const k of Object.keys(next)) {
      if (next[k] === r) delete next[k];
    }
    next[activeLeft] = r;
    onChange(next);
    setActiveLeft(null);
  }

  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="grid gap-2">
        {left.map((l) => {
          const paired = value[l];
          const active = activeLeft === l;
          const pairOk = pairResults?.[l];
          let cls = "border-line bg-surface-soft/60 dark:border-white/10 dark:bg-white/[0.04]";
          if (active) cls = "border-cyan-400/70 bg-cyan-400/10 dark:border-cyan-300/50 dark:bg-cyan-300/10";
          else if (paired && pairOk === true) cls = "border-emerald-400/50 bg-emerald-400/10 dark:border-emerald-300/40 dark:bg-emerald-300/10";
          else if (paired && pairOk === false) cls = "border-rose-400/50 bg-rose-400/10 dark:border-rose-300/40 dark:bg-rose-300/10";
          else if (paired) cls = "border-emerald-400/50 bg-emerald-400/10 dark:border-emerald-300/40 dark:bg-emerald-300/10";
          return (
            <button
              key={`l-${l}`}
              type="button"
              onClick={() => !disabled && setActiveLeft(active ? null : l)}
              disabled={disabled}
              className={`rounded-2xl border px-3 py-3 text-left text-sm font-black transition-all ${cls} text-navy-900 dark:text-white`}
            >
              <span className="block truncate">{l}</span>
              {paired ? <span className={`mt-0.5 block truncate text-[11px] font-bold ${
                pairOk === true ? "text-emerald-600 dark:text-emerald-300" :
                pairOk === false ? "text-rose-600 dark:text-rose-300" :
                "text-emerald-600 dark:text-emerald-300"
              }`}>→ {paired}</span> : null}
            </button>
          );
        })}
      </div>
      <div className="grid gap-2">
        {right.map((r) => {
          const isUsed = usedRight.has(r);
          return (
            <button
              key={`r-${r}`}
              type="button"
              onClick={() => pickRight(r)}
              disabled={!activeLeft && !isUsed || disabled}
              className={`rounded-2xl border px-3 py-3 text-left text-sm font-black transition-all ${
                isUsed
                  ? "border-emerald-400/40 bg-emerald-400/[0.06] text-ink-500 dark:border-emerald-300/30 dark:text-slate-400"
                  : "border-line bg-white text-navy-900 hover:border-cyan-300/60 dark:border-white/10 dark:bg-white/10 dark:text-white"
              } ${!activeLeft && !isUsed ? "opacity-70" : ""}`}
            >
              {r}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Heading match ────────────────────────────────────────────────────────────
function GamifiedHeadingMatch({
  items,
  headings,
  value,
  onChange,
  disabled,
}: {
  items: Array<{ id: string; text: string }>;
  headings: string[];
  value: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
  disabled?: boolean;
}) {
  return (
    <div className="grid gap-3">
      {items.map((item) => (
        <div key={`hm-${item.id}`} className="rounded-2xl border border-line bg-surface-soft/60 p-3.5 dark:border-white/10 dark:bg-white/[0.04]">
          <p className="mb-2.5 text-sm font-semibold leading-relaxed text-navy-900 dark:text-slate-100">{item.text}</p>
          <select
            value={value[item.id] || ""}
            onChange={(e) => !disabled && onChange({ ...value, [item.id]: e.target.value })}
            disabled={disabled}
            className="w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm font-bold text-navy-900 outline-none focus:border-cyan-400 dark:border-white/10 dark:bg-navy-900 dark:text-white"
          >
            <option value="">— Sarlavhani tanlang —</option>
            {headings.map((h) => (
              <option key={h} value={h}>{h}</option>
            ))}
          </select>
        </div>
      ))}
    </div>
  );
}

// ── Main StudentGamified component ───────────────────────────────────────────
export function StudentGamified({
  data,
  onNavigate,
}: {
  data: GenericRow;
  onNavigate: (section: string) => void;
}) {
  const tt = useWebT();
  const studentSubjects = useMemo(() => studentSubjectNames(data), [data]);
  const allowedSubjects = useMemo<string[]>(() => studentSubjects.filter((s) => s === "English" || s === "Russian"), [studentSubjects]);
  const showSubjectSelector = allowedSubjects.includes("English") && allowedSubjects.includes("Russian");
  const [subject, setSubject] = useState<string>(() => subjectFromUrlOrState(allowedSubjects));
  const [phase, setPhase] = useState<"intro" | "playing" | "result">("intro");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [scoring, setScoring] = useState<GamifiedScoring>({ correct: 2, wrong: -3, skipped: -1.5 });
  const [questions, setQuestions] = useState<GamifiedQuestion[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, any>>({});
  const [summary, setSummary] = useState<GamifiedSummary | null>(null);

  // Per-question feedback state
  const [feedback, setFeedback] = useState<GamifiedFeedback>(null);
  // For word_match real-time pair results
  const [pairResults, setPairResults] = useState<Record<number, Record<string, boolean | null>>>({});
  const [checkingPair, setCheckingPair] = useState(false);
  const [genProgress, setGenProgress] = useState(0);
  const [readyCount, setReadyCount] = useState(0);
  const [requestedCount, setRequestedCount] = useState(GAMIFIED_TARGET_QUESTIONS);

  useEffect(() => {
    if (phase === "playing") {
      document.body.classList.add("proctoring-test-mode");
    } else {
      document.body.classList.remove("proctoring-test-mode");
    }
    return () => {
      document.body.classList.remove("proctoring-test-mode");
    };
  }, [phase]);

  const current = questions[currentIndex];
  const blockTotal = questions.length;
  const scoreUnitTotal = Math.max(0, questions.reduce((sum, item) => sum + gamifiedQuestionUnits(item), 0));
  const currentUnitStart = questions.slice(0, currentIndex).reduce((sum, item) => sum + gamifiedQuestionUnits(item), 0) + 1;
  const currentScoreUnits = gamifiedQuestionUnits(current);
  const currentUnitEnd = Math.min(scoreUnitTotal || currentUnitStart, currentUnitStart + Math.max(1, currentScoreUnits) - 1);
  const progressPct = scoreUnitTotal ? Math.round(((currentUnitStart - 1) / scoreUnitTotal) * 100) : 0;

  const draft = current ? answers[current.index] : undefined;
  const hasAnswer = (() => {
    if (!current) return false;
    if (current.type === "mcq" || current.type === "fill_gap" || current.type === "reading_mcq" || current.type === "reading_true_false") return typeof draft === "number";
    if (current.type === "word_order") return Array.isArray(draft) && draft.length > 0;
    if (current.type === "word_match") return draft && Object.keys(draft).length >= (current.left?.length || 0);
    if (current.type === "heading_match") return draft && Object.keys(draft).filter((k) => draft[k]).length >= (current.items?.length || 0);
    return false;
  })();

  // Can we advance? MCQ/fill_gap/reading types require checking first; others go directly.
  const needsCheck = current && (current.type === "mcq" || current.type === "fill_gap" || current.type === "reading_mcq" || current.type === "reading_true_false") && !feedback?.checked;
  const canAdvance = !needsCheck && hasAnswer;

  function setDraft(next: any) {
    if (!current || feedback?.checked) return;
    setAnswers((prev) => ({ ...prev, [current.index]: next }));
    // Reset feedback when selecting a new answer
    if (feedback) setFeedback(null);
  }

  async function startSession() {
    const token = localStorage.getItem("diamond_token");
    if (!token) { setError(tt("student.gamified.needLogin", "Sessiya topilmadi. Iltimos qayta login qiling.")); return; }
    setBusy(true);
    setError("");
    setReadyCount(0);
    setRequestedCount(GAMIFIED_TARGET_QUESTIONS);
    setGenProgress(8);
    const progressTimer = window.setInterval(() => {
      setGenProgress((prev) => (prev < 92 ? Math.min(92, prev + Math.floor(Math.random() * 7) + 3) : prev));
    }, 400);

    try {
      const payload = await requestJson<GamifiedStartResponse>("/student/gamified-tests/start", {
        method: "POST",
        token,
        body: { subject },
        timeoutMs: 45000,
      });
      const nextRequested = Math.max(1, Number(payload.requested_count || GAMIFIED_TARGET_QUESTIONS));
      const nextReady = Math.max(0, Math.min(nextRequested, Number(payload.ready_count || payload.total || 0)));
      const nextPercent = Math.max(0, Math.min(100, Number(payload.ready_percent || Math.round((nextReady * 100) / nextRequested) || 100)));
      setRequestedCount(nextRequested);
      setReadyCount(nextReady);
      setGenProgress(nextPercent);
      if (!Array.isArray(payload.questions) || payload.questions.length === 0) {
        throw new Error(tt("student.gamified.emptyStart", "Savollar tayyorlanmadi. Qayta urinib ko'ring."));
      }
      setSessionId(payload.session_id);
      setQuestions(Array.isArray(payload.questions) ? payload.questions : []);
      setScoring(payload.scoring || { correct: 2, wrong: -3, skipped: -1.5 });
      setSubject(payload.subject || subject);
      setAnswers({});
      setCurrentIndex(0);
      setSummary(null);
      setFeedback(null);
      setPairResults({});
      setPhase("playing");
    } catch (err) {
      const raw = err instanceof Error ? err.message : tt("student.gamified.startError", "Testni boshlab bo'lmadi");
      const clean = isTransientRequestError(raw)
        ? tt("student.gamified.prepareSlow", "Savollar tayyorlash kutilganidan uzoq davom etdi. Qayta Boshlashni bosing.")
        : raw;
      setError(clean);
    } finally {
      window.clearInterval(progressTimer);
      setBusy(false);
    }
  }

  async function submitSession(finalAnswers: Record<number, any>) {
    const token = localStorage.getItem("diamond_token");
    if (!token) { setError(tt("student.gamified.needLogin", "Sessiya topilmadi. Iltimos qayta login qiling.")); return; }
    setBusy(true);
    setError("");
    try {
      const answersList = questions.map((q) => {
        const raw = finalAnswers[q.index];
        let answer: any = null;
        if (q.type === "mcq" || q.type === "fill_gap" || q.type === "reading_mcq" || q.type === "reading_true_false") {
          answer = typeof raw === "number" ? raw : null;
        } else if (q.type === "word_order") {
          answer = Array.isArray(raw) ? raw.map((wi: number) => (q.words || [])[wi]) : null;
        } else if (q.type === "word_match" || q.type === "heading_match") {
          answer = raw && Object.keys(raw).length ? raw : null;
        }
        return { index: q.index, answer };
      });
      const result = await requestJson<GamifiedSummary>("/student/gamified-tests/submit", {
        method: "POST",
        token,
        body: { session_id: sessionId, answers: answersList },
      });
      setSummary(result);
      setPhase("result");
    } catch (err) {
      setError(err instanceof Error ? err.message : tt("student.gamified.submitError", "Natijani yuborib bo'lmadi"));
    } finally {
      setBusy(false);
    }
  }

  // Check MCQ/fill_gap answer immediately
  async function checkAnswer() {
    if (!current || !sessionId || typeof draft !== "number") return;
    const token = localStorage.getItem("diamond_token");
    if (!token) return;
    setBusy(true);
    try {
      const res = await requestJson<{ correct: boolean }>("/student/gamified-tests/check-answer", {
        method: "POST",
        token,
        body: { session_id: sessionId, question_index: current.index, selected_option_index: draft },
      });
      setFeedback({ correct: res.correct, checked: true });
    } catch {
      // On network error, allow advancing without feedback
      setFeedback({ correct: true, checked: true });
    } finally {
      setBusy(false);
    }
  }

  // Check a word_match / heading_match pair in real time
  async function checkPair(questionIndex: number, key: string, pairValue: string) {
    if (!sessionId || checkingPair) return;
    const token = localStorage.getItem("diamond_token");
    if (!token) return;
    setCheckingPair(true);
    try {
      const res = await requestJson<{ correct: boolean }>("/student/gamified-tests/check-pair", {
        method: "POST",
        token,
        body: { session_id: sessionId, question_index: questionIndex, key, value: pairValue },
      });
      setPairResults((prev) => ({
        ...prev,
        [questionIndex]: { ...(prev[questionIndex] || {}), [key]: res.correct },
      }));
    } catch {
      // ignore
    } finally {
      setCheckingPair(false);
    }
  }

  function advanceOrSubmit() {
    const newAnswers = answers;
    const nextIndex = currentIndex + 1;
    setFeedback(null);
    if (nextIndex >= blockTotal) {
      submitSession(newAnswers);
    } else {
      setCurrentIndex(nextIndex);
    }
  }

  function skip() {
    if (feedback?.checked) {
      // Already showed feedback, now skipping to next
      advanceOrSubmit();
      return;
    }
    setAnswers((prev) => ({ ...prev, [current?.index ?? -1]: null }));
    setFeedback(null);
    const nextIndex = currentIndex + 1;
    if (nextIndex >= blockTotal) {
      submitSession({ ...answers, [current?.index ?? -1]: null });
    } else {
      setCurrentIndex(nextIndex);
    }
  }

  function onCheckOrAdvance() {
    if (!current) return;
    if (current.type === "mcq" || current.type === "fill_gap" || current.type === "reading_mcq" || current.type === "reading_true_false") {
      if (!feedback?.checked) {
        checkAnswer();
      } else {
        advanceOrSubmit();
      }
    } else {
      advanceOrSubmit();
    }
  }

  // ── No allowed subjects ──
  if (allowedSubjects.length === 0) {
    return (
      <div className="flex flex-col gap-4 pb-24 md:pb-12 animate-fade-in">
        <div className="rounded-2xl border border-dashed border-line bg-surface-soft/60 px-4 py-10 text-center text-sm font-bold text-ink-500 dark:border-white/10 dark:bg-white/[0.03] dark:text-slate-300">
          {tt("student.gamified.langOnly", "Gamified testlar faqat English va Russian fanlari uchun mavjud.")}
        </div>
      </div>
    );
  }

  // ── Intro screen ──
  if (phase === "intro") {
    return (
      <div className="flex flex-col gap-4 pb-24 md:pb-12 animate-fade-in">
        <article className="overflow-hidden rounded-2xl border border-line bg-white shadow-premium dark:border-white/10 dark:bg-white/[0.05]">
          <div className="relative bg-gradient-to-br from-cyan-500 to-navy-700 p-6 text-white dark:from-cyan-500/90 dark:to-navy-900">
            <h2 className="font-display text-2xl font-black tracking-tight">
              {tt("student.gamified.title", "Gamified testlar")}
            </h2>
            <p className="mt-1.5 max-w-lg text-sm font-semibold text-white/85">
              {tt("student.gamified.subtitle", "20 ta interaktiv savol. Har safar yangi savollar!")}
            </p>
          </div>
          <div className="p-5">
            {/* Scoring pills */}
            <div className="mb-4 grid grid-cols-3 gap-2 text-center">
              <div className="rounded-xl bg-emerald-500/10 px-2 py-3 text-emerald-600 dark:text-emerald-300">
                <div className="text-lg font-black">+{scoring.correct}</div>
                <div className="text-[10px] font-bold uppercase tracking-wide">{tt("student.gamified.correct", "To'g'ri")}</div>
              </div>
              <div className="rounded-xl bg-rose-500/10 px-2 py-3 text-rose-600 dark:text-rose-300">
                <div className="text-lg font-black">{scoring.wrong}</div>
                <div className="text-[10px] font-bold uppercase tracking-wide">{tt("student.gamified.wrong", "Xato")}</div>
              </div>
              <div className="rounded-xl bg-slate-500/10 px-2 py-3 text-ink-500 dark:text-slate-300">
                <div className="text-lg font-black">{scoring.skipped}</div>
                <div className="text-[10px] font-bold uppercase tracking-wide">{tt("student.gamified.skipped", "O'tkazilgan")}</div>
              </div>
            </div>

            {showSubjectSelector ? (
              <div className="mb-4">
                <div className="mb-1.5 text-xs font-black uppercase tracking-wide text-ink-500 dark:text-slate-400">{tt("student.gamified.subject", "Fan")}</div>
                <div className="flex gap-2">
                  {allowedSubjects.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setSubject(s)}
                      className={`flex-1 rounded-xl border px-3 py-2.5 text-sm font-black transition ${
                        subject === s
                          ? "border-cyan-400/70 bg-cyan-400/10 text-navy-900 dark:border-cyan-300/50 dark:bg-cyan-300/10 dark:text-white"
                          : "border-line bg-surface-soft/60 text-ink-600 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300"
                      }`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {error ? <div className="mb-3 rounded-xl bg-rose-500/10 px-3 py-2 text-sm font-bold text-rose-600 dark:text-rose-300">{error}</div> : null}

            {busy && (
              <div className="mb-4 rounded-xl border border-cyan-500/20 bg-cyan-500/10 p-4 text-center">
                <p className="text-xs font-black uppercase tracking-wider text-cyan-700 dark:text-cyan-300 mb-2">
                  {tt("student.gamified.preparing", "Savollar tayyorlanmoqda...")} {Math.max(readyCount, Math.round((genProgress / 100) * requestedCount))}/{requestedCount} · {genProgress}%
                </p>
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-surface-soft dark:bg-white/10">
                  <div
                    className="h-full rounded-full bg-cyan-500 transition-all duration-300 dark:bg-cyan-400"
                    style={{ width: `${genProgress}%` }}
                  />
                </div>
              </div>
            )}

            <div className="flex flex-col gap-2 sm:flex-row">
              <button
                className="rounded-xl border border-line bg-surface-soft px-4 py-2.5 text-sm font-black text-ink-700 transition hover:bg-line dark:border-white/10 dark:bg-white/10 dark:text-slate-100"
                onClick={() => onNavigate("home")}
              >
                {tt("student.gamified.dashboard", "Dashboard")}
              </button>
              <button
                className="flex-1 rounded-xl bg-navy-900 px-4 py-2.5 text-sm font-black text-white shadow-lg transition hover:-translate-y-0.5 hover:bg-navy-800 disabled:opacity-60 dark:bg-cyan-500 dark:text-navy-950 dark:hover:bg-cyan-400"
                onClick={startSession}
                disabled={busy}
              >
                {busy ? `${tt("student.gamified.starting", "Boshlanmoqda...")} (${genProgress}%)` : tt("student.gamified.start", "Boshlash")}
              </button>
            </div>
          </div>
        </article>
      </div>
    );
  }

  // ── Result screen ──
  if (phase === "result" && summary) {
    const net = Number(summary.awarded_dpoints ?? summary.score ?? 0);
    const pct = summary.total ? Math.round((summary.correct / summary.total) * 100) : 0;
    const isGood = pct >= 60;
    return (
      <div className="flex flex-col gap-4 pb-24 md:pb-12 animate-fade-in">
        <article className="overflow-hidden rounded-2xl border border-line bg-white shadow-premium dark:border-white/10 dark:bg-white/[0.05]">
          {/* Header */}
          <div className={`p-6 text-center ${
            isGood
              ? "bg-gradient-to-br from-emerald-500 to-teal-600"
              : "bg-gradient-to-br from-rose-500 to-red-600"
          }`}>
            <div className="mx-auto mb-3 grid h-20 w-20 place-items-center rounded-full bg-white/20 text-4xl">
              {isGood ? "🏆" : "💪"}
            </div>
            <h2 className="font-display text-2xl font-black text-white">{tt("student.gamified.done", "Test yakunlandi!")}</h2>
            <p className={`mt-2 text-4xl font-black text-white`}>
              {net >= 0 ? "+" : ""}{net.toFixed(1)}
              <span className="ml-1 text-lg font-bold text-white/80">D'Points</span>
            </p>
            <p className="mt-1 text-sm font-semibold text-white/70">
              {pct}% to'g'ri ({summary.correct}/{summary.total})
            </p>
          </div>

          <div className="p-5">
            {/* Stats */}
            <div className="mb-5 grid grid-cols-3 gap-2">
              <div className="rounded-xl bg-emerald-500/10 px-2 py-3 text-center text-emerald-600 dark:text-emerald-300">
                <div className="text-2xl font-black">{summary.correct}</div>
                <div className="text-[10px] font-bold uppercase tracking-wide">{tt("student.gamified.correct", "To'g'ri")}</div>
              </div>
              <div className="rounded-xl bg-rose-500/10 px-2 py-3 text-center text-rose-600 dark:text-rose-300">
                <div className="text-2xl font-black">{summary.wrong}</div>
                <div className="text-[10px] font-bold uppercase tracking-wide">{tt("student.gamified.wrong", "Xato")}</div>
              </div>
              <div className="rounded-xl bg-slate-500/10 px-2 py-3 text-center text-ink-500 dark:text-slate-300">
                <div className="text-2xl font-black">{summary.skipped}</div>
                <div className="text-[10px] font-bold uppercase tracking-wide">{tt("student.gamified.skipped", "O'tkazilgan")}</div>
              </div>
            </div>

            {/* Progress bar */}
            <div className="mb-5">
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-xs font-bold text-ink-500 dark:text-slate-400">Natija</span>
                <span className="text-xs font-black text-navy-900 dark:text-white">{pct}%</span>
              </div>
              <div className="h-3 overflow-hidden rounded-full bg-surface-soft dark:bg-white/10">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${
                    isGood ? "bg-emerald-500" : "bg-rose-500"
                  }`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row">
              <button
                className="flex-1 rounded-xl border border-line bg-surface-soft px-4 py-2.5 text-sm font-black text-ink-700 transition hover:bg-line dark:border-white/10 dark:bg-white/10 dark:text-slate-100"
                onClick={() => onNavigate("home")}
              >
                {tt("student.gamified.dashboard", "Dashboard")}
              </button>
              <button
                className="flex-1 rounded-xl bg-navy-900 px-4 py-2.5 text-sm font-black text-white shadow-lg transition hover:-translate-y-0.5 hover:bg-navy-800 dark:bg-cyan-500 dark:text-navy-950 dark:hover:bg-cyan-400"
                onClick={() => setPhase("intro")}
              >
                {tt("student.gamified.again", "Yana o'ynash")}
              </button>
            </div>
          </div>
        </article>
      </div>
    );
  }

  // ── Playing screen ──
  const currentPairResults = current ? (pairResults[current.index] || {}) : {};
  const isCheckedMcq = (current?.type === "mcq" || current?.type === "fill_gap" || current?.type === "reading_mcq" || current?.type === "reading_true_false") && feedback?.checked;
  const nextLabel = currentIndex + 1 >= blockTotal
    ? tt("student.gamified.finish", "Yakunlash")
    : tt("student.gamified.next", "Keyingisi");

  return (
    <div className="flex flex-col gap-4 pb-40 md:pb-24 animate-fade-in">
      {/* Header: progress + counter */}
      <div className="flex items-center gap-3">
        {/* Progress bar */}
        <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-surface-soft dark:bg-white/10">
          <div
            className="h-full rounded-full bg-cyan-500 transition-all duration-500 dark:bg-cyan-400"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        {/* Counter */}
        <span className="shrink-0 rounded-full bg-surface-soft px-3 py-1 text-xs font-black text-ink-600 dark:bg-white/10 dark:text-slate-200">
          {currentUnitStart === currentUnitEnd ? currentUnitStart : `${currentUnitStart}-${currentUnitEnd}`}/{scoreUnitTotal || requestedCount}
        </span>
      </div>

      <article className={`rounded-2xl border bg-white p-5 shadow-premium transition-all duration-300 dark:bg-white/[0.05] ${
        isCheckedMcq && feedback?.correct
          ? "border-emerald-300/60 dark:border-emerald-400/30"
          : isCheckedMcq && !feedback?.correct
          ? "border-rose-300/60 dark:border-rose-400/30"
          : "border-line dark:border-white/10"
      }`}>
        {current ? (
          <>
            <div className="mb-4">
              <span className="inline-block rounded-full bg-cyan-500/10 px-2.5 py-1 text-[10px] font-black uppercase tracking-wide text-cyan-700 dark:text-cyan-300">
                {tt(`student.gamified.type.${current.type}`, current.type.replace(/_/g, " "))}
              </span>
              <h3 className="mt-2 font-display text-lg font-black tracking-tight text-navy-900 dark:text-white">
                {current.prompt}
              </h3>
              {current.type === "fill_gap" && current.sentence ? (
                <p className="mt-2 rounded-xl bg-surface-soft/60 px-3 py-2.5 text-base font-bold text-navy-900 dark:bg-white/[0.04] dark:text-slate-100">
                  {current.sentence}
                </p>
              ) : null}
              {(current.type === "reading_mcq" || current.type === "reading_true_false") && current.passage ? (
                <div className="mt-3 rounded-xl border border-line bg-surface-soft/50 px-4 py-3 text-sm font-medium leading-relaxed text-navy-800 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-200">
                  {current.passage}
                </div>
              ) : null}
            </div>

            {(current.type === "mcq" || current.type === "fill_gap" || current.type === "reading_mcq" || current.type === "reading_true_false") ? (
              <GamifiedChoice
                options={current.options || (current.type === "reading_true_false" ? ["True", "False"] : [])}
                value={typeof draft === "number" ? draft : null}
                onChange={(i) => setDraft(i)}
                feedback={feedback}
                disabled={feedback?.checked}
              />
            ) : null}
            {current.type === "word_order" ? (
              <GamifiedWordOrder
                words={current.words || []}
                value={Array.isArray(draft) ? draft : []}
                onChange={(v) => setDraft(v)}
                disabled={feedback?.checked}
              />
            ) : null}
            {current.type === "word_match" ? (
              <GamifiedWordMatch
                left={current.left || []}
                right={current.right || []}
                value={draft || {}}
                onChange={(v) => {
                  if (feedback?.checked) return;
                  // Find the newly added key-value pair
                  const prevDraft = (draft || {}) as Record<string, string>;
                  for (const k of Object.keys(v)) {
                    if (v[k] !== prevDraft[k]) {
                      checkPair(current.index, k, v[k]);
                      break;
                    }
                  }
                  setDraft(v);
                }}
                pairResults={currentPairResults}
                disabled={feedback?.checked}
              />
            ) : null}
            {current.type === "heading_match" ? (
              <GamifiedHeadingMatch
                items={current.items || []}
                headings={current.headings || []}
                value={draft || {}}
                onChange={(v) => {
                  if (feedback?.checked) return;
                  // Check the changed pair
                  const prevDraft = (draft || {}) as Record<string, string>;
                  for (const k of Object.keys(v)) {
                    if (v[k] && v[k] !== prevDraft[k]) {
                      checkPair(current.index, k, v[k]);
                      break;
                    }
                  }
                  setDraft(v);
                }}
                disabled={feedback?.checked}
              />
            ) : null}

            {error ? <div className="mt-3 rounded-xl bg-rose-500/10 px-3 py-2 text-sm font-bold text-rose-600 dark:text-rose-300">{error}</div> : null}

            {/* Action buttons — only show if feedback not shown as bottom overlay */}
            {!(isCheckedMcq) && (
              <div className="mt-5 flex items-center gap-2">
                <button
                  className="rounded-xl border border-line bg-surface-soft px-4 py-2.5 text-sm font-black text-ink-600 transition hover:bg-line disabled:opacity-50 dark:border-white/10 dark:bg-white/10 dark:text-slate-300"
                  onClick={skip}
                  disabled={busy}
                >
                  {tt("student.gamified.skip", "O'tkazib yuborish")}
                </button>
                <button
                  className="flex-1 rounded-xl bg-navy-900 px-4 py-2.5 text-sm font-black text-white shadow-lg transition hover:-translate-y-0.5 hover:bg-navy-800 disabled:opacity-50 dark:bg-cyan-500 dark:text-navy-950 dark:hover:bg-cyan-400"
                  onClick={onCheckOrAdvance}
                  disabled={busy || !hasAnswer}
                >
                  {busy
                    ? tt("student.gamified.saving", "Tekshirilmoqda...")
                    : needsCheck
                    ? tt("student.gamified.check", "Tekshirish")
                    : nextLabel}
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="py-8 text-center text-sm font-bold text-ink-500 dark:text-slate-300">
            {tt("student.gamified.loading", "Yuklanmoqda...")}
          </div>
        )}
      </article>

      {/* Bottom feedback overlay for MCQ/fill_gap */}
      {isCheckedMcq && (
        <GamifiedFeedbackOverlay
          feedback={feedback}
          onNext={advanceOrSubmit}
          nextLabel={nextLabel}
          busy={busy}
        />
      )}
    </div>
  );
}


export function StudentDailyTest({
  data,
  onNavigate,
}: {
  data: GenericRow;
  onNavigate: (section: string) => void;
}) {
  const tt = useWebT();
  const [history, setHistory] = useState<GenericRow[]>(() => {
    const initial = Array.isArray(data.daily_test_history) ? (data.daily_test_history as GenericRow[]) : [];
    const cached = readSessionCache<{ items: GenericRow[] }>("student:daily-test:history");
    return initial.length ? initial : (cached?.items || []);
  });
  useEffect(() => {
    const incoming = Array.isArray(data.daily_test_history) ? (data.daily_test_history as GenericRow[]) : [];
    if (incoming.length) {
      setHistory(incoming);
      writeSessionCache("student:daily-test:history", { items: incoming });
    }
  }, [data.daily_test_history]);
  useEffect(() => {
    const token = localStorage.getItem("diamond_token");
    if (!token) return;
    const controller = new AbortController();
    let cancelled = false;
    requestJson<{ items: GenericRow[] }>("/tests", {
      token,
      signal: controller.signal,
      timeoutMs: 9000,
      retries: 1,
    })
      .then((payload) => {
        if (cancelled || controller.signal.aborted) return;
        const items = payload.items || [];
        setHistory(items);
        writeSessionCache("student:daily-test:history", { items });
      })
      .catch(() => null);
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);
  const recent = history.slice(0, 4);
  return (
    <div className="flex flex-col gap-4 pb-24 md:pb-12 animate-fade-in">
      <section className="grid gap-3 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <article className="rounded-2xl border border-line bg-white p-4 shadow-premium transition hover:-translate-y-0.5 dark:border-white/10 dark:bg-white/[0.05] sm:p-5">
          <div className="flex h-full min-h-[118px] flex-col justify-between gap-3">
            <div>
              <h3 className="mb-2 flex items-center gap-3 font-display text-base font-black tracking-tight text-navy-900 dark:text-white sm:text-lg">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-cyan-500/10 text-xs font-black text-cyan-700 dark:bg-cyan-400/15 dark:text-cyan-200">T</span>
                {tt("student.dailyTest.today", "Bugungi test")}
              </h3>
              <p className="max-w-lg text-xs font-semibold leading-relaxed text-ink-500 dark:text-slate-300 sm:text-sm">
                {tt("student.dailyTest.todayDesc", "Savollar alohida fullscreen sahifada ochiladi va proctoring bilan himoyalanadi.")}
              </p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <button className="rounded-xl border border-line bg-surface-soft px-3.5 py-2 text-xs font-black text-ink-700 transition hover:bg-line dark:border-white/10 dark:bg-white/10 dark:text-slate-100 dark:hover:bg-white/15 sm:text-sm" onClick={() => onNavigate("home")}>
                {tt("student.dailyTest.dashboard", "Dashboard")}
              </button>
              <button className="rounded-xl bg-navy-900 px-4 py-2 text-xs font-black text-white shadow-lg transition hover:-translate-y-0.5 hover:bg-navy-800 dark:bg-cyan-500 dark:text-navy-950 dark:hover:bg-cyan-400 sm:text-sm" onClick={() => onNavigate("daily-test-process")}>
                {tt("student.dailyTest.openProcess", "Testni boshlash")}
              </button>
            </div>
          </div>
        </article>

        <article className="rounded-2xl border border-line bg-white p-4 shadow-premium dark:border-white/10 dark:bg-white/[0.05] sm:p-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="font-display text-base font-black text-navy-900 dark:text-white">{tt("student.dailyTest.recentAttempts", "So'nggi urinishlar")}</h3>
            <span className="rounded-full bg-surface-soft px-3 py-1 text-xs font-black text-ink-500 dark:bg-white/10 dark:text-slate-300">{recent.length}</span>
          </div>
          {recent.length ? (
            <div className="grid gap-2 sm:grid-cols-2">
              {recent.map((row, idx) => (
                <article key={`${row.test_date}-${idx}`} className="rounded-xl border border-line bg-surface-soft/70 p-3 dark:border-white/10 dark:bg-white/[0.04]">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <strong className="truncate text-sm font-black text-navy-900 dark:text-white">{row.test_date || "-"}</strong>
                    <span className="rounded-full bg-cyan-500/10 px-2 py-1 text-[11px] font-black text-cyan-700 dark:text-cyan-300">
                      {Number(row.net_dpoints ?? row.net_dcoins ?? 0).toFixed(1)}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-1.5 text-center">
                    <span className="rounded-lg bg-emerald-500/10 px-2 py-1.5 text-xs font-black text-emerald-600 dark:text-emerald-300">{row.correct || 0}<small className="block text-[9px] uppercase">{tt("student.dailyTest.correctShort", "T")}</small></span>
                    <span className="rounded-lg bg-rose-500/10 px-2 py-1.5 text-xs font-black text-rose-600 dark:text-rose-300">{row.wrong || 0}<small className="block text-[9px] uppercase">{tt("student.dailyTest.wrongShort", "N")}</small></span>
                    <span className="rounded-lg bg-slate-500/10 px-2 py-1.5 text-xs font-black text-ink-500 dark:text-slate-300">{row.unanswered || 0}<small className="block text-[9px] uppercase">{tt("student.dailyTest.skippedShort", "O")}</small></span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-line bg-surface-soft/60 px-4 py-7 text-center text-sm font-bold text-ink-500 dark:border-white/10 dark:bg-white/[0.03] dark:text-slate-300">
              {tt("student.dailyTest.noAttempts", "Hozircha urinishlar yo'q")}
            </div>
          )}
        </article>
      </section>
    </div>
  );
}

export function StudentDailyTestProcess({
  data,
  onNavigate,
  mode = "launcher",
}: {
  data: GenericRow;
  onNavigate: (section: string) => void;
  mode?: "launcher" | "runtime";
}) {
  const router = useRouter();
  const tt = useWebT();
  const runtimeMode = mode === "runtime";
  const studentSubjects = useMemo(() => studentSubjectNames(data), [data]);
  const studentSubjectKey = studentSubjects.join("|");
  const allowedSubjects = useMemo<string[]>(() => studentSubjects.filter((s) => s === "English" || s === "Russian"), [studentSubjects]);
  const showSubjectSelector = allowedSubjects.includes("English") && allowedSubjects.includes("Russian");
  const [subject, setSubject] = useState<string>(() => subjectFromUrlOrState(allowedSubjects));
  const [session, setSession] = useState<DailyTestRuntimeSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [timeLeft, setTimeLeft] = useState(0);
  const [proctoringSessionId, setProctoringSessionId] = useState<number | null>(null);
  const [proctoringReady, setProctoringReady] = useState(false);
  const [runtimeBooted, setRuntimeBooted] = useState(false);
  const [runtimeSessionChecked, setRuntimeSessionChecked] = useState(!runtimeMode);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [runtimeStartSubject, setRuntimeStartSubject] = useState<string>(() => subjectFromUrlOrState(allowedSubjects));
  const dailyAnswerInFlightRef = useRef(false);
  const [dailyHistory, setDailyHistory] = useState<GenericRow[]>(() => {
    const initial = Array.isArray(data.daily_test_history) ? (data.daily_test_history as GenericRow[]) : [];
    const cached = readSessionCache<{ items: GenericRow[] }>("student:daily-test:history");
    return initial.length ? initial : (cached?.items || []);
  });
  useEffect(() => {
    const incoming = Array.isArray(data.daily_test_history) ? (data.daily_test_history as GenericRow[]) : [];
    if (incoming.length) {
      setDailyHistory(incoming);
      writeSessionCache("student:daily-test:history", { items: incoming });
    }
  }, [data.daily_test_history]);
  useEffect(() => {
    if (runtimeMode) return;
    const token = localStorage.getItem("diamond_token");
    if (!token) return;
    const controller = new AbortController();
    let cancelled = false;
    requestJson<{ items: GenericRow[] }>("/tests", { token, signal: controller.signal, timeoutMs: 9000, retries: 1 })
      .then((payload) => {
        if (cancelled || controller.signal.aborted) return;
        const items = payload.items || [];
        setDailyHistory(items);
        writeSessionCache("student:daily-test:history", { items });
      })
      .catch(() => null);
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [runtimeMode]);
  const completedDailySubjects = useMemo(() => {
    const today = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Tashkent",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date());
    const done = new Set<string>();
    for (const row of dailyHistory) {
      const testDate = String(row.test_date || "").slice(0, 10);
      const status = String(row.status || "").toLowerCase();
      const rowSubject = normalizeSubjectLabel(String(row.subject || row.subj || ""));
      if (testDate === today && status === "completed" && rowSubject) {
        done.add(rowSubject);
      }
    }
    return done;
  }, [dailyHistory]);

  async function loadSession(targetSubject: string, attemptId?: number) {
    const normalizedTargetSubject = normalizeSubjectLabel(String(targetSubject || "")) || subjectFromUrlOrState(studentSubjects);
    const token = localStorage.getItem("diamond_token");
    if (!token) {
      setError("Sessiya topilmadi. Iltimos qayta login qiling.");
      setRuntimeSessionChecked(true);
      return;
    }
    setError("");
    const query = attemptId
      ? `/student/daily-tests/session?attempt_id=${attemptId}&subject=${encodeURIComponent(normalizedTargetSubject)}`
      : `/student/daily-tests/session?subject=${encodeURIComponent(normalizedTargetSubject)}`;
    try {
      setProctoringReady(false);
      const payload = await requestJson<DailyTestRuntimeSession>(query, { token });
      if (payload?.blocked) {
        setSubject((prev) => (prev === normalizedTargetSubject ? prev : normalizedTargetSubject));
        setSession(payload);
        setTimeLeft(0);
        setRuntimeSessionChecked(true);
        return;
      }
      if (payload?.exists === false) {
        setSubject((prev) => (prev === normalizedTargetSubject ? prev : normalizedTargetSubject));
        setRuntimeStartSubject(normalizedTargetSubject);
        setSession(null);
        setTimeLeft(0);
        setRuntimeSessionChecked(true);
        return;
      }
      setSubject((prev) => (prev === normalizedTargetSubject ? prev : normalizedTargetSubject));
      setRuntimeStartSubject(normalizedTargetSubject);
      setSession(payload);
      const nextProctoringId = Number(payload.proctoring_session_id || 0) || null;
      const requiresProctoring = Boolean((payload as GenericRow).proctoring_required);
      setProctoringSessionId(nextProctoringId);
      setProctoringReady(!requiresProctoring);
      setTimeLeft(Math.max(0, Number(payload.time_remaining_sec || payload.time_limit_sec || 0)));
      setRuntimeSessionChecked(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load daily test session");
      setRuntimeSessionChecked(true);
    }
  }

  async function startSession(targetSubject?: string) {
    const normalizedTargetSubject = normalizeSubjectLabel(String(targetSubject || subject || "")) || subjectFromUrlOrState(studentSubjects);
    const token = localStorage.getItem("diamond_token");
    if (!token) {
      setError("Sessiya topilmadi. Iltimos qayta login qiling.");
      setRuntimeSessionChecked(true);
      return;
    }
    setBusy(true);
    setError("");
    setProctoringReady(false);
    try {
      const payload = await requestJson<DailyTestRuntimeSession>("/student/daily-tests/start", {
        token,
        method: "POST",
        body: { subject: normalizedTargetSubject },
      });
      setSubject((prev) => (prev === normalizedTargetSubject ? prev : normalizedTargetSubject));
      setRuntimeStartSubject(normalizedTargetSubject);
      setSession(payload);
      const nextProctoringId = Number(payload.proctoring_session_id || 0) || null;
      const requiresProctoring = Boolean((payload as GenericRow).proctoring_required);
      setProctoringSessionId(nextProctoringId);
      setProctoringReady(!requiresProctoring);
      setTimeLeft(Math.max(0, Number(payload.time_remaining_sec || payload.time_limit_sec || 0)));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not start daily test";
      if (String(message).toLowerCase().includes("already") || String(message).toLowerCase().includes("completed") || String(message).toLowerCase().includes("failed")) {
        setSession({ blocked: true, blocked_reason: message } as DailyTestRuntimeSession);
      }
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  async function submitAnswer(answer: number | null) {
    if (!session?.attempt_id || !session.question?.question_index || busy || (runtimeMode && (proctoringSessionId || session?.proctoring_required) && !proctoringReady)) return;
    if (dailyAnswerInFlightRef.current) return;
    const token = localStorage.getItem("diamond_token");
    if (!token) return;
    dailyAnswerInFlightRef.current = true;
    setBusy(true);
    setError("");
    try {
      const payload = await requestJson<DailyTestRuntimeSession>("/student/daily-tests/answer", {
        token,
        method: "POST",
        body: {
          attempt_id: session.attempt_id,
          question_index: session.question.question_index,
          ...answerBody(answer),
          proctoring_session_id: proctoringSessionId,
        },
      });
      setSession(payload);
      setTimeLeft(Math.max(0, Number(payload.time_remaining_sec || payload.time_limit_sec || 0)));
    } catch (err) {
      const reason = proctoringStopReason(err instanceof Error ? err.message : err);
      if (reason) {
        setError("");
        setProctoringReady(false);
        setSession((prev) => proctoringStoppedPayload(prev, reason) as DailyTestRuntimeSession);
      } else if (String(err instanceof Error ? err.message : err).toLowerCase().includes("question mismatch")) {
        setError("");
        loadSession(runtimeStartSubject || subject, Number(session.attempt_id || 0) || undefined).catch(() => null);
      } else {
        setError(err instanceof Error ? err.message : "Could not submit daily test answer");
      }
    } finally {
      setBusy(false);
      dailyAnswerInFlightRef.current = false;
    }
  }

  useEffect(() => {
    const initialSubject = subjectFromUrlOrState(allowedSubjects);
    setSubject((prev) => (allowedSubjects.includes(prev) ? prev : initialSubject));
    setRuntimeStartSubject((prev) => (allowedSubjects.includes(prev) ? prev : initialSubject));
    if (runtimeMode) {
      setRuntimeSessionChecked(false);
      loadSession(initialSubject).catch(() => null);
    }
  }, [studentSubjectKey, runtimeMode, allowedSubjects]);

  useEffect(() => {
    setTimeLeft(Math.max(0, Number(session?.time_remaining_sec || session?.time_limit_sec || 0)));
  }, [session?.attempt_id, session?.question?.question_index, session?.time_remaining_sec, session?.time_limit_sec]);

  useEffect(() => {
    if (!session?.question || session.completed || busy || !proctoringReady) return;
    const timer = window.setInterval(() => {
      setTimeLeft((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [session?.attempt_id, session?.question?.question_index, session?.completed, busy, proctoringReady]);

  useEffect(() => {
    if (!runtimeMode) return;
    if (!session?.question || session.completed || busy || !proctoringReady) return;
    if (timeLeft > 0) return;
    submitAnswer(null);
  }, [timeLeft, session?.attempt_id, session?.question?.question_index, session?.completed, busy, runtimeMode, proctoringReady]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!runtimeMode) return;
    if (runtimeBooted || busy) return;
    if (!runtimeSessionChecked) return;
    if (session?.blocked) return;
    if (session?.question || session?.completed) return;
    setRuntimeBooted(true);
    startSession(runtimeStartSubject || subject).catch(() => null);
  }, [runtimeMode, runtimeBooted, busy, runtimeSessionChecked, session?.question, session?.completed, session?.blocked, runtimeStartSubject, subject]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!runtimeMode) {
    const launcherSubjects = allowedSubjects.length ? allowedSubjects : ["English"];
    return (
      <div className="flex flex-col gap-5 pb-24 md:pb-12 animate-fade-in">
        <section className="daily-test-launcher-card mx-auto w-full max-w-4xl rounded-[1.35rem] border border-line bg-white p-5 shadow-[0_10px_24px_rgba(15,23,42,0.06)] dark:border-white/10 dark:bg-navy-950/75 sm:p-6">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="flex flex-col gap-2 sm:col-span-1">
              <span className="ml-1 text-xs font-black uppercase tracking-wide text-ink-500 dark:text-slate-400">{tt("common.subject", "Fan")}</span>
              {showSubjectSelector ? (
                <div className="grid grid-cols-2 gap-2">
                  {launcherSubjects.map((item) => {
                    const normalized = normalizeSubjectLabel(item) || item;
                    const active = subject === normalized;
                    const completed = completedDailySubjects.has(normalized);
                    return (
                      <button
                        key={normalized}
                        type="button"
                        className={`daily-test-subject-button min-h-[46px] rounded-xl border px-3 py-2 text-left transition ${
                          active
                            ? "is-active border-cyan-500 bg-cyan-500 text-white shadow-lg shadow-cyan-500/20 dark:border-cyan-300 dark:bg-cyan-400 dark:text-navy-950"
                            : "border-line bg-white text-navy-900 hover:bg-slate-50 dark:border-white/10 dark:bg-navy-800 dark:text-white dark:hover:bg-navy-700"
                        }`}
                        onClick={() => setSubject(normalized)}
                      >
                        <span className="block truncate text-sm font-black">{normalized}</span>
                        {completed ? (
                          <span className={`mt-1 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-black ${active ? "bg-white/20 text-white dark:bg-navy-950/15 dark:text-navy-950" : "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"}`}>
                            ✓ {tt("student.dailyTest.completedToday", "Bugun bajarilgan")}
                          </span>
                        ) : null}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <strong className="daily-test-launcher-control min-h-[46px] rounded-xl border border-line bg-white px-3 py-3 text-sm font-black text-navy-900 dark:border-white/10 dark:bg-navy-800 dark:text-white">
                  {launcherSubjects[0] || "English"}
                </strong>
              )}
            </div>
            
            <div className="flex flex-col gap-2">
              <span className="ml-1 text-xs font-black uppercase tracking-wide text-ink-500 dark:text-slate-400">{tt("student.dailyTest.totalQuestions", "Savollar")}</span>
              <strong className="daily-test-launcher-control w-full rounded-xl border border-line bg-white px-4 py-3 font-black text-navy-900 dark:border-white/10 dark:bg-navy-800 dark:text-white">{DAILY_TEST_FIXED_QUESTION_COUNT}</strong>
            </div>
            
            <div className="flex flex-col gap-2">
              <span className="ml-1 text-xs font-black uppercase tracking-wide text-ink-500 dark:text-slate-400">{tt("student.dailyTest.mode", "Rejim")}</span>
              <strong className="daily-test-launcher-control flex w-full items-center gap-2 rounded-xl border border-line bg-surface-soft px-4 py-3 font-black text-cyan-600 dark:border-white/10 dark:bg-navy-900/70 dark:text-cyan-300">
                <span aria-hidden="true">T</span> {tt("student.dailyTest.fullscreenMode", "Fullscreen test")}
              </strong>
            </div>
          </div>
          
          <button
            className="mt-5 w-full rounded-xl bg-navy-900 px-6 py-4 text-base font-black text-white shadow-[0_14px_28px_rgba(15,23,42,0.18)] transition hover:-translate-y-0.5 hover:bg-navy-800 dark:bg-cyan-400 dark:text-navy-950 dark:hover:bg-cyan-300"
            onClick={() => router.push(`/student/daily/process/run?subject=${encodeURIComponent(subject || launcherSubjects[0] || "English")}`)}
          >
            {tt("student.dailyTest.startTest", "Testni boshlash")}
          </button>
        </section>
      </div>
    );
  }

  if (session?.blocked) {
    return (
      <div className="daily-test-blocked-page flex min-h-[100dvh] items-center justify-center bg-background p-4 text-center dark:bg-navy-950">
        <section className="test-result-card w-full max-w-xl rounded-[1.35rem] border border-orange-200 bg-white p-6 shadow-[0_18px_42px_rgba(15,23,42,0.12)] dark:border-orange-400/25 dark:bg-navy-950/90 sm:p-8">
          <div className="mx-auto mb-5 grid h-16 w-16 place-items-center rounded-2xl bg-orange-500/10 text-orange-600 dark:text-orange-300">
            <svg className="h-9 w-9" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
          </div>
          <h3 className="font-display text-2xl font-black text-navy-900 dark:text-white">{tt("student.dailyTest.blockedTitle", "Test bloklangan")}</h3>
          <p className="mt-2 text-sm font-bold text-ink-500 dark:text-slate-300">
            {session.blocked_reason === "daily_completed_today"
              ? tt("student.dailyTest.completedTodayDesc", "Bugungi kunlik testni muvaffaqiyatli yakunladingiz. Yangi test ertaga ochiladi.")
              : session.blocked_reason === "daily_failed_today"
              ? tt("student.dailyTest.failedTodayDesc", "Bugungi kunlik testda muvaffaqiyatsizlikka uchradingiz. Ertaga qayta urinib ko'rishingiz mumkin.")
              : session.blocked_reason === "daily_bank_insufficient"
              ? tt("student.dailyTest.bankInsufficientDesc", "Bu daraja uchun kunlik test savollari yetarli emas. Yangi savollar qo'shilishini kuting.")
              : (session.blocked_reason || tt("student.dailyTest.blockedDefault", "Bugungi test allaqachon yakunlangan yoki yopilgan."))}
          </p>
          <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
            <button
              className="rounded-2xl bg-navy-900 px-6 py-3 font-black text-white transition hover:bg-navy-800 dark:bg-cyan-400 dark:text-navy-950"
              onClick={() => router.push(studentSectionToPath("daily-test"))}
            >
              {tt("common.back", "Orqaga")}
            </button>
            <button
              className="rounded-2xl border border-line bg-surface-soft px-6 py-3 font-black text-navy-900 transition hover:bg-line dark:border-white/10 dark:bg-white/10 dark:text-white dark:hover:bg-white/20"
              onClick={() => {
                setError("");
                setSession(null);
                setRuntimeBooted(false);
                setRuntimeSessionChecked(false);
                loadSession(runtimeStartSubject || subject).catch(() => null);
              }}
            >
              {tt("common.retry", "Qayta urinish")}
            </button>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="flex h-[100dvh] max-h-[100dvh] min-h-[100dvh] flex-col overflow-hidden bg-background selection:bg-cyan-500/30 selection:text-cyan-900 dark:bg-navy-950 dark:selection:text-cyan-100 relative">
      {error && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[60] bg-red-100 text-red-700 px-4 py-2 rounded-xl shadow-lg border border-red-200 text-sm font-medium animate-fade-in-up">
          {error}
        </div>
      )}
      
      <div className="flex-1 overflow-y-auto w-full p-3 sm:p-6 lg:p-8">
        <div className="max-w-4xl mx-auto space-y-6 relative">
          
          <StudentTestProctoring
            active={Boolean(proctoringSessionId && session?.question && !session?.completed)}
            completed={Boolean(session?.completed)}
            initialSessionId={proctoringSessionId}
            testType="daily"
            testAttemptRef={session?.attempt_id ? String(session.attempt_id) : undefined}
            testRoute="/student/daily/process/run"
            onSessionReady={(id) => {
              setProctoringSessionId(id);
              setTimeLeft(Math.max(0, Number(session?.time_remaining_sec || session?.time_limit_sec || 0)));
            }}
            onVerificationStateChange={(ready) => {
              setProctoringReady(ready);
            }}
            onTerminated={(reason) => {
              setError("");
              setProctoringReady(false);
              setSession((prev) => proctoringStoppedPayload(prev, reason) as DailyTestRuntimeSession);
            }}
            className={proctoringMonitorClass()}
          />

          {runtimeMode && !session?.question && !session?.completed && !session?.blocked ? (
            <div className="daily-test-preparing-card rounded-[1.35rem] border border-line bg-white p-6 text-center shadow-[0_16px_36px_rgba(15,23,42,0.10)] dark:border-cyan-300/15 dark:bg-navy-950/90 sm:p-8">
              <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-cyan-500/10 text-2xl font-black text-cyan-600 dark:text-cyan-300">
                T
              </div>
              <h3 className="font-display text-2xl font-black text-navy-900 dark:text-white">
                {busy || !runtimeSessionChecked ? tt("student.dailyTest.preparingTitle", "Savollar tayyorlanmoqda") : tt("student.dailyTest.openFailed", "Daily test ochilmadi")}
              </h3>
              <p className="mx-auto mt-3 max-w-xl text-sm font-medium text-ink-500 dark:text-ink-300">
                {busy || !runtimeSessionChecked
                  ? tt("student.dailyTest.preparingDesc", "Savollar tayyorlanmoqda. Kamera ruxsati kerak bo'lsa, so'rov chiqadi.")
                  : (error || session?.message || tt("student.dailyTest.notEnoughQuestions", "Bu daraja uchun daily test savollari yetarli emas. Admin yangi savollar qo'shgandan keyin qayta urinib ko'ring."))}
              </p>
              {busy || !runtimeSessionChecked ? (
                <div className="mx-auto mt-6 h-2 w-44 overflow-hidden rounded-full bg-surface-soft dark:bg-white/10">
                  <span className="block h-full w-1/2 animate-pulse rounded-full bg-indigo-500" />
                </div>
              ) : (
                <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
                  <button
                    className="rounded-2xl bg-navy-900 px-6 py-3 font-bold text-white shadow-lg shadow-blue-500/20 transition hover:-translate-y-0.5 dark:bg-cyan-500 dark:text-navy-950"
                    onClick={() => {
                      setError("");
                      setRuntimeBooted(false);
                      setRuntimeSessionChecked(false);
                      loadSession(runtimeStartSubject || subject).catch(() => null);
                    }}
                  >
                    {tt("common.retry", "Qayta urinish")}
                  </button>
                  <button
                    className="rounded-2xl border border-line bg-surface-soft px-6 py-3 font-bold text-navy-900 transition hover:bg-line dark:border-white/10 dark:bg-white/10 dark:text-white dark:hover:bg-white/20"
                    onClick={() => router.push(studentSectionToPath("daily-test"))}
                  >
                    {tt("common.back", "Orqaga")}
                  </button>
                </div>
              )}
            </div>
          ) : null}

          {session?.question && !session.completed && (
            <div className={`test-runtime-card bg-white dark:bg-navy-900/50 rounded-[2rem] p-4 sm:p-6 shadow-premium border border-line dark:border-white/10 relative overflow-hidden ${!proctoringReady ? "select-none" : ""} ${
              new Date().getDay() === 0 ? "border-t-purple-500" :
              new Date().getDay() === 1 ? "border-t-blue-500" :
              new Date().getDay() === 2 ? "border-t-green-500" :
              new Date().getDay() === 3 ? "border-t-yellow-500" :
              new Date().getDay() === 4 ? "border-t-orange-500" :
              new Date().getDay() === 5 ? "border-t-red-500" :
              "border-t-indigo-500"
            }`}>
              {!proctoringReady ? (
                <div className="proctoring-blur-overlay absolute inset-0 z-20 bg-white/65 dark:bg-navy-950/65 backdrop-blur-[2px] flex items-center justify-center text-center p-5">
                  <div className="test-proctoring-wait-card px-5 py-4 rounded-2xl bg-white dark:bg-navy-900 border border-cyan-200 dark:border-cyan-500/30 shadow-premium">
                    <p className="font-black text-navy-900 dark:text-white">
                      {session?.face_enrollment_required ? tt("duel.faceSetup", "FaceID setup kerak") : tt("duel.faceChecking", "FaceID tekshirilmoqda...")}
                    </p>
                    <p className="text-sm text-ink-500 dark:text-navy-200">
                      {session?.face_enrollment_required ? tt("duel.faceSetupDesc", "Profil sahifasidan FaceID setup qiling. Kamerasiz test ishlamaydi.") : tt("duel.faceCheckingDesc", "Test FaceID tasdiqlangandan keyin boshlanadi.")}
                    </p>
                  </div>
                </div>
              ) : null}
              
              <div className="grid grid-cols-[auto_1fr_auto] items-center gap-3 sm:gap-5 mb-8">
                <div className={`px-4 py-2 rounded-2xl font-bold text-lg flex items-center gap-2 ${timeLeft > 15 ? "bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400" : timeLeft > 5 ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-500/20 dark:text-yellow-400" : "bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400 animate-pulse"}`}>
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                  00:{timeLeft.toString().padStart(2, '0')}
                </div>
                <div className="text-center min-w-0">
                  <h2 className="text-xl sm:text-2xl font-black text-navy-900 dark:text-white">{tt("student.dailyTest.kicker", "Kunlik Test")}</h2>
                  {session.subject ? (
                    <p className="text-[11px] sm:text-xs font-black uppercase tracking-wide text-cyan-600 dark:text-cyan-400">{session.subject}</p>
                  ) : null}
                  <p className="text-sm text-ink-500 font-bold">{tt("student.dailyTest.question", "Savol")} {session.question.question_index} / {session.total_questions}</p>
                </div>
                <div className="hidden sm:block" />
              </div>

              <div className="w-full h-2 bg-transparent border border-line dark:border-white/5 rounded-full mb-8 overflow-hidden">
                <div 
                  className="h-full bg-cyan-500 transition-all duration-500 ease-out"
                  style={{ width: `${Math.max(0, Math.min(100, Number(session.progress_percent || 0)))}%` }}
                />
              </div>
              
              <StudentQuestionRenderer
                question={session.question as TestQuestionPayload}
                disabled={busy || timeLeft <= 0 || !proctoringReady}
                singleColumn
                onSubmit={submitAnswer}
              />
            </div>
          )}

          {session?.completed && (
            <div className="test-result-card bg-white dark:bg-navy-950/90 rounded-[2rem] p-4 sm:p-6 shadow-premium border border-line dark:border-white/10 text-center relative overflow-hidden">
              <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-blue-500/10 to-transparent" />
              
              <div className={`w-24 h-24 mx-auto ${isProctoringStopped(session) ? "bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400" : "bg-green-100 dark:bg-green-500/20 text-green-600 dark:text-green-400"} rounded-full flex items-center justify-center mb-6 relative`}>
                {isProctoringStopped(session) ? (
                  <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" /></svg>
                ) : (
                  <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                )}
              </div>
              
              <h3 className="text-3xl font-bold text-navy-900 dark:text-white mb-2">
                {isProctoringStopped(session) ? tt("student.tests.proctorStopped", "Test proctoring sabab to'xtatildi") : tt("student.tests.finished", "Test yakunlandi!")}
              </h3>
              <p className="text-ink-500 mb-4">
                {isProctoringStopped(session) ? tt("duel.proctorStoppedDesc", "Test xavfsizlik tekshiruvi sabab yakunlandi.") : tt("student.dailyTest.finishDesc", "Kunlik test har 24 soatda bir marta beriladi.")}
              </p>
              {isProctoringStopped(session) ? (
                <div className="mb-8 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-bold text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200">
                  {tt("common.reason", "Sabab")}: {session.proctoring_failure_message || proctoringFriendlyError(String(session.proctoring_failure_reason || ""))}
                </div>
              ) : null}
              
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
                <div className="bg-transparent p-4 rounded-2xl border border-line dark:border-white/10">
                  <p className="text-sm font-medium text-ink-500 mb-1">{tt("student.dailyTest.correct", "To'g'ri")}</p>
                  <p className="text-2xl font-bold text-green-600 dark:text-green-400">{session.stats?.correct || 0}</p>
                </div>
                <div className="bg-transparent p-4 rounded-2xl border border-line dark:border-white/10">
                  <p className="text-sm font-medium text-ink-500 mb-1">{tt("student.dailyTest.wrong", "Noto'g'ri")}</p>
                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{session.stats?.wrong || 0}</p>
                </div>
                <div className="bg-transparent p-4 rounded-2xl border border-line dark:border-white/10">
                  <p className="text-sm font-medium text-ink-500 mb-1">{tt("student.dailyTest.skipped", "O'tkazilgan")}</p>
                  <p className="text-2xl font-bold text-ink-600 dark:text-navy-300">{session.stats?.unanswered || 0}</p>
                </div>
                <div className="bg-transparent p-4 rounded-2xl border border-blue-100 dark:border-blue-500/20">
                  <p className="currency-inline text-sm font-medium text-ink-500 mb-1">
                    <AssetIcon type="dpoint" size={18} />
                    D'Points
                  </p>
                  <p className="text-2xl font-bold text-cyan-600 dark:text-cyan-400">{Number(session.dpoints ?? session.dpoint_breakdown?.total_points ?? session.dcoin_breakdown?.total_points ?? 0).toFixed(1)}</p>
                </div>
              </div>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                {Array.isArray((session as GenericRow).details) && ((session as GenericRow).details as GenericRow[]).length > 0 && (
                  <button
                    className="bg-indigo-50 hover:bg-indigo-100 text-indigo-700 dark:bg-indigo-500/15 dark:hover:bg-indigo-500/25 dark:text-indigo-300 px-6 py-3 rounded-2xl font-bold border border-indigo-100 dark:border-indigo-500/30 transition-all hover:-translate-y-0.5 flex items-center gap-2"
                    onClick={() => setReviewOpen(true)}
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
                    {tt("student.dailyTest.reviewAnswers", "Javoblarni ko'rish")}
                  </button>
                )}
                {!(session?.subject ? (completedDailySubjects.has(normalizeSubjectLabel(session.subject) || session.subject) || session?.completed) : false) && (
                  <button
                    className="bg-navy-900 hover:bg-navy-800 text-white dark:bg-cyan-500 dark:hover:bg-cyan-600 px-8 py-4 rounded-2xl font-bold text-lg shadow-lg shadow-blue-500/30 transition-all hover:-translate-y-1"
                    onClick={() => {
                      setSession(null);
                      setRuntimeBooted(false);
                    }}
                  >
                    {tt("student.tests.startNew", "Yangi test boshlash")}
                  </button>
                )}
                <button
                  className="bg-surface-soft hover:bg-line dark:bg-white/10 dark:hover:bg-white/20 text-navy-900 dark:text-white px-8 py-4 rounded-2xl font-bold text-lg border border-line dark:border-white/10 transition-all hover:-translate-y-1"
                  onClick={() => {
                    setSession(null);
                    setRuntimeBooted(false);
                    if (runtimeMode) router.push(studentSectionToPath("daily-test"));
                    else onNavigate("daily-test");
                  }}
                >
                  {tt("common.back", "Orqaga")}
                </button>
              </div>
            </div>
          )}

          {/* ── Test Review Popup ── */}
          {reviewOpen && session?.completed && (
            <div className="fixed inset-0 z-[90] flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={(e) => { if (e.target === e.currentTarget) setReviewOpen(false); }}>
              <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setReviewOpen(false)} />
              <div className="relative z-10 w-full sm:max-w-2xl max-h-[90dvh] bg-white dark:bg-navy-950 rounded-t-[2rem] sm:rounded-[2rem] shadow-2xl flex flex-col overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between px-5 py-4 border-b border-line dark:border-white/10 shrink-0">
                  <div>
                    <h3 className="text-lg font-black text-navy-900 dark:text-white">{tt("student.dailyTest.reviewAnswers", "Javoblarni ko'rish")}</h3>
                    <p className="text-xs font-semibold text-ink-500 dark:text-navy-300 mt-0.5">
                      {tt("student.dailyTest.correct", "To'g'ri")}: {session.stats?.correct || 0} · {tt("student.dailyTest.wrong", "Noto'g'ri")}: {session.stats?.wrong || 0} · {tt("student.dailyTest.skipped", "O'tkazilgan")}: {session.stats?.unanswered || 0}
                    </p>
                  </div>
                  <button
                    onClick={() => setReviewOpen(false)}
                    className="w-9 h-9 flex items-center justify-center rounded-xl bg-surface-soft hover:bg-line dark:bg-white/10 dark:hover:bg-white/20 transition text-ink-600 dark:text-navy-200"
                  >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" /></svg>
                  </button>
                </div>
                {/* Body */}
                <div className="overflow-y-auto flex-1 p-4 space-y-3">
                  {((session as GenericRow).details as GenericRow[] || []).map((detail: GenericRow, idx: number) => {
                    const isCorrect = Boolean(detail.is_correct);
                    const isSkipped = Boolean(detail.is_skipped) || detail.selected_index === null || detail.selected_index === undefined;
                    const options = Array.isArray(detail.options) ? detail.options as string[] : [];
                    const selectedIdx = detail.selected_index !== null && detail.selected_index !== undefined ? Number(detail.selected_index) : null;
                    const correctIdx = detail.correct_index !== null && detail.correct_index !== undefined ? Number(detail.correct_index) : null;
                    return (
                      <div key={`review-${idx}`} className={`rounded-2xl border p-4 ${
                        isSkipped ? "border-line dark:border-white/10 bg-surface-soft/60 dark:bg-white/[0.03]" :
                        isCorrect ? "border-emerald-200 dark:border-emerald-500/30 bg-emerald-50/60 dark:bg-emerald-500/[0.06]" :
                        "border-rose-200 dark:border-rose-500/30 bg-rose-50/60 dark:bg-rose-500/[0.06]"
                      }`}>
                        <div className="flex items-start gap-3 mb-3">
                          <span className={`shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-black ${
                            isSkipped ? "bg-slate-200 text-slate-600 dark:bg-white/10 dark:text-slate-300" :
                            isCorrect ? "bg-emerald-500 text-white" :
                            "bg-rose-500 text-white"
                          }`}>
                            {isSkipped ? "–" : isCorrect ? "✓" : "✗"}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-[11px] font-bold uppercase tracking-wide text-ink-400 dark:text-navy-400 mb-1">
                              {tt("student.dailyTest.questionNum", "Savol")} #{idx + 1}
                            </p>
                            <p className="text-sm font-bold text-navy-900 dark:text-white leading-snug">{String(detail.prompt || "")}</p>
                          </div>
                        </div>
                        {options.length > 0 && (
                          <div className="grid gap-1.5 ml-10">
                            {options.map((opt: string, oi: number) => {
                              const isSelected = selectedIdx === oi;
                              const isCorrectOpt = correctIdx === oi;
                              return (
                                <div key={oi} className={`flex items-center gap-2 rounded-xl px-3 py-2 text-sm ${
                                  isCorrectOpt
                                    ? "bg-emerald-100 dark:bg-emerald-500/20 text-emerald-800 dark:text-emerald-200 font-bold"
                                    : isSelected && !isCorrect
                                    ? "bg-rose-100 dark:bg-rose-500/15 text-rose-700 dark:text-rose-300 font-bold"
                                    : "text-gray-700 dark:text-navy-300 font-medium"
                                }`}>
                                  <span className={`w-5 h-5 shrink-0 rounded-full flex items-center justify-center text-[10px] font-black ${
                                    isCorrectOpt ? "bg-emerald-500 text-white" :
                                    isSelected && !isCorrect ? "bg-rose-500 text-white" :
                                    "bg-gray-100 dark:bg-white/10 text-gray-600 dark:text-ink-500"
                                  }`}>{String.fromCharCode(65 + oi)}</span>
                                  {opt}
                                  {isCorrectOpt && <svg className="ml-auto w-4 h-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg>}
                                  {isSelected && !isCorrect && <svg className="ml-auto w-4 h-4 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" /></svg>}
                                </div>
                              );
                            })}
                          </div>
                        )}
                        {isSkipped && (
                          <p className="ml-10 text-xs font-bold text-ink-400 dark:text-navy-400">{tt("student.dailyTest.skipped", "O'tkazilgan")}</p>
                        )}
                      </div>
                    );
                  })}
                </div>
                {/* Footer */}
                <div className="shrink-0 px-5 py-4 border-t border-line dark:border-white/10">
                  <button
                    className="w-full bg-navy-900 hover:bg-navy-800 dark:bg-cyan-500 dark:hover:bg-cyan-600 text-white dark:text-navy-950 py-3 rounded-2xl font-bold transition"
                    onClick={() => setReviewOpen(false)}
                  >
                    {tt("common.close", "Yopish")}
                  </button>
                </div>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

export function StudentArena({
  data,
  onNavigate,
}: {
  data: GenericRow;
  onNavigate: (section: string) => void;
}) {
  const tt = useWebT();
  const router = useRouter();
  void data;

  function runtimeStartPath(sectionId: string) {
    const path = studentSectionToPath(sectionId, { autoJoin: false });
    if (path.includes("arena_mode=")) return path;
    const joiner = path.includes("?") ? "&" : "?";
    return `${path}${joiner}arena_mode=${encodeURIComponent(sectionId)}`;
  }

  return (
    <div className="flex flex-col gap-4 pb-12 animate-fade-in">
      <section className="grid grid-cols-2 gap-3 sm:gap-4 arena-duel-grid">
        {[
          { id: "arena-daily", title: tt("arena.daily.title", "Daily Arena"), description: tt("arena.daily.subtitle", "Kamida 10 o'quvchi, 5 bosqich va final 4 uchun arena."), icon: "⚔️" },
          { id: "arena-group", title: tt("arena.group.title", "Group Arena"), description: tt("arena.group.subtitle", "O'qituvchi boshlagan guruh arenasi. Faqat Keldi o'quvchilar qatnashadi."), icon: "🛡️" },
          { id: "arena-boss", title: tt("arena.boss.title", "Boss Arena"), description: tt("arena.boss.subtitle", "Kamida 5 o'quvchi, 15 qiyin savol."), icon: "👹" },
          { id: "duel-1v1", title: tt("duel.duel-1v1.title", "Duel 1v1"), description: tt("duel.duel-1v1.subtitle", "Fan bo'yicha 1 ga 1 duel. Level faqat ma'lumot uchun ko'rsatiladi."), icon: "🤺" },
          { id: "duel-3v3", title: tt("duel.duel-3v3.title", "Duel 3v3"), description: tt("duel.duel-3v3.subtitle", "Fan bo'yicha 6 o'quvchilik jamoaviy duel. Level faqat ma'lumot uchun ko'rsatiladi."), icon: "👥" },
          { id: "duel-5v5", title: tt("duel.duel-5v5.title", "Duel 5v5"), description: tt("duel.duel-5v5.subtitle", "Fan bo'yicha 10 o'quvchilik jamoaviy duel."), icon: "🔥" },
        ].map((battle) => (
          <article className="relative flex min-w-0 flex-col justify-between p-3.5 sm:p-4 bg-gradient-to-br from-navy-800 to-navy-900 border border-white/10 rounded-2xl shadow-premium group overflow-hidden transition-all hover:-translate-y-1 hover:shadow-[0_10px_40px_rgba(0,11,59,0.3)]" key={battle.id}>
            <div className="absolute -top-10 -right-10 w-32 h-32 bg-cyan-500/10 blur-[40px] group-hover:bg-cyan-500/20 transition-colors pointer-events-none" />
            
            <div className="relative z-10 flex flex-col h-full">
              <div className="flex items-start justify-between mb-2.5 gap-2">
                <div className="arena-menu-icon flex items-center justify-center w-10 h-10 bg-white/10 rounded-lg text-xl backdrop-blur-sm border border-white/10 shrink-0">
                  {battle.icon}
                </div>
              </div>
              
              <h3 className="text-sm sm:text-base font-bold text-white font-display mb-1.5 break-words leading-snug">{battle.title}</h3>
              <p className="text-[11px] sm:text-xs font-medium text-navy-100 mb-3 leading-snug flex-grow line-clamp-3 break-words">{battle.description}</p>
              
              <button 
                className="w-full px-3 py-2.5 text-xs sm:text-sm font-bold text-navy-900 bg-white hover:bg-cyan-50 rounded-xl shadow-[0_0_15px_rgba(255,255,255,0.1)] transition-colors mt-auto whitespace-nowrap overflow-hidden text-ellipsis" 
                onClick={() => router.push(runtimeStartPath(String(battle.id)))}
              >
                {String(battle.id).startsWith("duel-") ? tt("duel.start", "Duel boshlash") : tt("arena.startShort", "Start")} {battle.title}
              </button>
            </div>
          </article>
        ))}
      </section>

      <section className="mt-8 bg-surface-soft dark:bg-navy-950/40 rounded-[2rem] border border-line dark:border-white/5 overflow-hidden">
        <div className="p-5 sm:p-8 border-b border-line dark:border-white/5">
          <h2 className="text-xl sm:text-2xl font-black text-navy-900 dark:text-white">
            {tt("arena.faq.title", "Ko'p so'raladigan savollar va Qoidalar")}
          </h2>
          <p className="text-sm font-medium text-ink-500 dark:text-navy-300 mt-1">
            {tt("arena.faq.subtitle", "Har bir arena turi va o'yin qoidalari haqida qisqacha ma'lumot.")}
          </p>
        </div>
        <div className="p-5 sm:p-8 grid gap-6 sm:grid-cols-2">
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-black text-navy-900 dark:text-white flex items-center gap-2 mb-2">
                <span className="w-6 h-6 rounded-lg bg-indigo-50 dark:bg-indigo-500/20 text-indigo-600 flex items-center justify-center">⚔️</span>
                {tt("arena.rules.daily.title", "Daily Arena qoidalari")}
              </h3>
              <ul className="text-sm text-ink-600 dark:text-navy-200 space-y-1.5 list-disc pl-5 marker:text-cyan-500">
                <li>{tt("arena.rules.dailyNoStartBelowMin", "Daily Arena 10 tadan kam qatnashchi bilan boshlanmaydi.")}</li>
                <li>{tt("arena.rules.stages", "Bosqichlar")}: 5. {tt("arena.rules.elimination", "Studentlar bosqichma-bosqich chiqariladi.")}</li>
                <li>{tt("arena.rules.finalFour", "Final bosqichida faqat 4 student qoladi.")}</li>
                <li>{tt("arena.rules.harderEachStage", "Har bosqichda yangi va qiyinroq savollar beriladi.")}</li>
              </ul>
            </div>
            <div>
              <h3 className="text-sm font-black text-navy-900 dark:text-white flex items-center gap-2 mb-2">
                <span className="w-6 h-6 rounded-lg bg-indigo-50 dark:bg-indigo-500/20 text-indigo-600 flex items-center justify-center">🛡️</span>
                {tt("arena.rules.group.title", "Group Arena qoidalari")}
              </h3>
              <ul className="text-sm text-ink-600 dark:text-navy-200 space-y-1.5 list-disc pl-5 marker:text-cyan-500">
                <li>{tt("arena.rules.groupOnly", "Faqat tanlangan guruh studentlari qatnashadi.")}</li>
                <li>{tt("arena.rules.presentOnly", "Faqat davomatda 'Keldi' bo'lgan studentlar kira oladi.")}</li>
                <li>{tt("arena.rules.lessonTimeOnly", "Teacher Group Arenani faqat dars vaqtida boshlaydi.")}</li>
              </ul>
            </div>
            <div>
              <h3 className="text-sm font-black text-navy-900 dark:text-white flex items-center gap-2 mb-2">
                <span className="w-6 h-6 rounded-lg bg-indigo-50 dark:bg-indigo-500/20 text-indigo-600 flex items-center justify-center">👹</span>
                {tt("arena.rules.boss.title", "Boss Arena qoidalari")}
              </h3>
              <ul className="text-sm text-ink-600 dark:text-navy-200 space-y-1.5 list-disc pl-5 marker:text-cyan-500">
                <li>{tt("arena.rules.bossAnytime", "Boss Arena istalgan vaqtda boshlanishi mumkin.")}</li>
                <li>{tt("arena.rules.bossSameQuestions", "Barcha qatnashchilar uchun bir xil 15 ta qiyin savol beriladi.")}</li>
                <li>{tt("arena.rules.bossRewardCondition", "Mukofot olish uchun ko'rsatilgan foizdan yuqori natija ko'rsatish kerak.")}</li>
              </ul>
            </div>
          </div>
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-black text-navy-900 dark:text-white flex items-center gap-2 mb-2">
                <span className="w-6 h-6 rounded-lg bg-indigo-50 dark:bg-indigo-500/20 text-indigo-600 flex items-center justify-center">🤺</span>
                {tt("duel.rules.1v1.title", "1v1 Duel qoidalari")}
              </h3>
              <ul className="text-sm text-ink-600 dark:text-navy-200 space-y-1.5 list-disc pl-5 marker:text-cyan-500">
                <li>{tt("duel.rules.matchSubjectOnly", "Raqib faqat tanlangan fan bo'yicha topiladi. (Level shart emas)")}</li>
                <li>{tt("duel.rules.sameQuestions", "Ikkala student bir xil savollarga javob beradi.")}</li>
                <li>{tt("duel.rules.moreCorrectWins", "Ko'proq to'g'ri javob bergan g'olib bo'ladi.")}</li>
                <li>{tt("duel.rules.tieNoBreaker", "To'g'ri javoblar teng bo'lsa Durang hisoblanadi.")}</li>
              </ul>
            </div>
            <div>
              <h3 className="text-sm font-black text-navy-900 dark:text-white flex items-center gap-2 mb-2">
                <span className="w-6 h-6 rounded-lg bg-indigo-50 dark:bg-indigo-500/20 text-indigo-600 flex items-center justify-center">👥</span>
                {tt("duel.rules.team.title", "Jamoaviy Duel (3v3 va 5v5) qoidalari")}
              </h3>
              <ul className="text-sm text-ink-600 dark:text-navy-200 space-y-1.5 list-disc pl-5 marker:text-cyan-500">
                <li>{tt("duel.rules.matchSubjectOnly", "Jamoalar fan bo'yicha yig'iladi.")}</li>
                <li>{tt("duel.rules.teamCorrectWins", "Jamoaning jami to'g'ri javoblari hisoblanadi va ko'p topgan jamoa yutadi.")}</li>
              </ul>
            </div>
            <div>
              <h3 className="text-sm font-black text-navy-900 dark:text-white flex items-center gap-2 mb-2">
                <span className="w-6 h-6 rounded-lg bg-indigo-50 dark:bg-indigo-500/20 text-indigo-600 flex items-center justify-center">ℹ️</span>
                {tt("arena.rules.general", "Umumiy qoidalar")}
              </h3>
              <ul className="text-sm text-ink-600 dark:text-navy-200 space-y-1.5 list-disc pl-5 marker:text-cyan-500">
                <li>{tt("arena.rules.timerBackend", "Timer backend tomonidan qat'iy nazorat qilinadi.")}</li>
                <li>{tt("arena.rules.lateSkipped", "Kechikkan javoblar o'tkazilgan yoki noto'g'ri hisoblanadi.")}</li>
                <li>{tt("competition.waitTimerHint", "Agar kutish vaqtida ishtirokchilar yig'ilmasa, arena/duel yopiladi va mablag' qaytariladi.")}</li>
              </ul>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

const COMPETITION_META: Record<CompetitionMode, { section: string; title: string; kicker: string; subtitle: string; cta: string }> = {
  daily: {
    section: "arena-daily",
    title: "Daily Arena",
    kicker: "Daily Arena",
    subtitle: "Date-seeded visual theme + live remained/left participants and per-question progress",
    cta: "Start Daily Arena",
  },
  group: {
    section: "arena-group",
    title: "Group Arena",
    kicker: "Group Arena",
    subtitle: "Group-focused competition flow with one shared question set and live ranking",
    cta: "Start Group Arena",
  },
  boss: {
    section: "arena-boss",
    title: "Boss Arena",
    kicker: "Boss Arena",
    subtitle: "Higher intensity rounds with strong winner/loser result treatment",
    cta: "Start Boss Arena",
  },
  "duel-1v1": {
    section: "duel-1v1",
    title: "Duel 1v1",
    kicker: "Duel 1v1",
    subtitle: "Subject-based head-to-head duel. Level is informational only.",
    cta: "Enter Duel 1v1",
  },
  "duel-3v3": {
    section: "duel-3v3",
    title: "Duel 3v3",
    kicker: "Duel 3v3",
    subtitle: "Subject-based 6-player team match. Level is informational only.",
    cta: "Enter Duel 3v3",
  },
  "duel-5v5": {
    section: "duel-5v5",
    title: "Duel 5v5",
    kicker: "Duel 5v5",
    subtitle: "Subject-based 10-player team battle with one shared question set.",
    cta: "Enter Duel 5v5",
  },
};

function CompetitionLobbyRules({
  mode,
  status,
  subject,
  group,
  settings,
  open,
  onToggle,
  tt,
}: {
  mode: CompetitionMode;
  status: CompetitionStatusPayload | null;
  subject: string;
  group?: GenericRow | null;
  settings?: GenericRow;
  open: boolean;
  onToggle: () => void;
  tt: (key: string, fallback?: string) => string;
}) {
  const rules = (status?.reward_settings || settings || {}) as GenericRow;
  // Prefer backend-provided required_players; only fall back to defaults when not yet loaded
  const defaultRequired = mode === "duel-1v1" ? 2 : mode === "duel-3v3" ? 6 : mode === "duel-5v5" ? 10 : mode === "boss" ? 5 : mode === "daily" ? 10 : 0;
  const required = status?.required_players != null ? Number(status.required_players) : defaultRequired;
  const joined = Number(status?.participants_count ?? status?.joined_count ?? 0);
  const entryFee = Number(status?.entry_fee ?? (mode.startsWith("duel-") ? rules.duel_entry_fee_dcoin : mode === "group" ? 0 : rules.arena_entry_fee_dcoin) ?? 0);
  const dailyFirst = Number(rules.daily_arena_reward_first ?? 25);
  const dailySecond = Number(rules.daily_arena_reward_second ?? 20);
  const dailyThird = Number(rules.daily_arena_reward_third ?? 15);
  const groupReward = Number(rules.group_arena_winner_reward ?? 10);
  const bossPerCorrect = Number(rules.boss_arena_reward_per_correct ?? 3);
  const bossThreshold = Number(rules.boss_arena_global_threshold_percent ?? 86);
  const title =
    mode === "duel-1v1" ? tt("duel.rules.1v1.title", "1v1 Duel qoidalari") :
    mode === "duel-3v3" ? tt("duel.rules.3v3.title", "3v3 Duel qoidalari") :
    mode === "duel-5v5" ? tt("duel.rules.5v5.title", "5v5 Duel qoidalari") :
    mode === "daily" ? tt("arena.rules.daily.title", "Daily Arena qoidalari") :
    mode === "group" ? tt("arena.rules.group.title", "Group Arena qoidalari") :
    tt("arena.rules.boss.title", "Boss Arena qoidalari");
  const base = [
    `${tt("arena.rules.subject", "Fan")}: ${subject || status?.subject || "-"}`,
    `${tt("arena.rules.entryFee", "Kirish narxi")}: ${entryFee.toFixed(entryFee % 1 ? 1 : 0)} D'coin`,
    tt("arena.rules.timerBackend", "Timer backend tomonidan nazorat qilinadi"),
    tt("arena.rules.lateSkipped", "Kechikkan javoblar o'tkazilgan yoki noto'g'ri hisoblanadi"),
  ];
  let modeRules: string[] = [];
  if (mode === "duel-1v1") {
    modeRules = [
      `${tt("arena.rules.requiredPlayers", "Kerakli o'yinchilar")}: ${required}`,
      tt("duel.rules.matchSubjectOnly", "Raqib faqat tanlangan fan bo'yicha topiladi"),
      tt("duel.rules.noLevelMatch", "Level bo'yicha matching talab qilinmaydi"),
      tt("duel.rules.sameQuestions", "Ikkala student bir xil savollarga javob beradi"),
      tt("duel.rules.moreCorrectWins", "Ko'proq to'g'ri javob bergan g'olib bo'ladi"),
      tt("duel.rules.tieNoBreaker", "To'g'ri javoblar teng bo'lsa Durang, user_id bo'yicha g'olib tanlanmaydi"),
    ];
  } else if (mode === "duel-3v3" || mode === "duel-5v5") {
    const teamSize = mode === "duel-3v3" ? 3 : 5;
    modeRules = [
      `${tt("arena.rules.requiredPlayers", "Kerakli o'yinchilar")}: ${required}`,
      `${tt("duel.rules.teamFormat", "Jamoa formati")}: ${teamSize} vs ${teamSize}`,
      tt("duel.rules.matchSubjectOnly", "Raqib faqat tanlangan fan bo'yicha topiladi"),
      tt("duel.rules.noLevelMatch", "Level bo'yicha matching talab qilinmaydi"),
      tt("duel.rules.teamCorrectWins", "Jamoaning jami to'g'ri javoblari ko'p bo'lsa g'olib bo'ladi"),
      tt("duel.rules.teamTieNoBreaker", "Jamoalar teng bo'lsa Durang, team raqami bo'yicha g'olib tanlanmaydi"),
    ];
  } else if (mode === "daily") {
    modeRules = [
      `${tt("arena.rules.minimumParticipants", "Minimum qatnashchilar")}: ${required}`,
      tt("arena.rules.dailyNoStartBelowMin", "Daily Arena 10 tadan kam qatnashchi bilan boshlanmaydi"),
      `${tt("arena.rules.stages", "Bosqichlar")}: 5`,
      tt("arena.rules.elimination", "Studentlar bosqichma-bosqich chiqariladi"),
      tt("arena.rules.finalFour", "Final bosqichida 4 student qoladi"),
      `${tt("arena.rules.podiumRewards", "Final mukofotlari")}: 1-${dailyFirst}, 2-${dailySecond}, 3-${dailyThird} D'point`,
      tt("arena.rules.harderEachStage", "Har bosqichda yangi va qiyinroq savollar beriladi"),
    ];
  } else if (mode === "group") {
    modeRules = [
      `${tt("arena.group", "Guruh")}: ${group?.name || status?.group_name || "-"}`,
      tt("arena.rules.groupOnly", "Faqat tanlangan guruh studentlari qatnashadi"),
      tt("arena.rules.presentOnly", "Faqat davomatda Keldi bo'lgan studentlar kira oladi"),
      tt("arena.rules.attendanceRequired", "Arena boshlanishidan oldin davomat yakunlangan bo'lishi kerak"),
      tt("arena.rules.lessonTimeOnly", "Teacher Group Arenani faqat dars vaqtida boshlaydi"),
      tt("arena.rules.teacherQuestions", "Teacher AI yoki qo'lda kiritilgan savollardan foydalanadi"),
      `${tt("arena.rules.groupWinnerReward", "1-o'rin mukofoti")}: ${groupReward} D'point`,
    ];
  } else {
    modeRules = [
      `${tt("arena.rules.minimumParticipants", "Minimum qatnashchilar")}: ${required}`,
      tt("arena.rules.bossAnytime", "Boss Arena istalgan vaqtda boshlanishi mumkin"),
      tt("arena.rules.bossSameQuestions", "Barcha qatnashchilar uchun bir xil 15 ta qiyin savollar beriladi"),
      `${tt("arena.rules.bossRewardCondition", "Mukofot sharti")}: ${bossThreshold}%+`,
      `${tt("arena.rules.bossPerCorrect", "Har to'g'ri javob uchun")}: ${bossPerCorrect} D'point`,
    ];
  }
  const allRules = [...modeRules, ...base];
  const visibleRules = open ? allRules : allRules.slice(0, 5);
  return (
    <div className="rounded-2xl border border-line bg-surface-soft p-4 shadow-sm dark:border-white/10 dark:bg-navy-950/70">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-black uppercase tracking-wide text-navy-900 dark:text-white">{tt("arena.rules.title", "Qoidalar")}</h3>
          <p className="text-xs font-semibold text-ink-500 dark:text-navy-300">{title}</p>
        </div>
        <span className="shrink-0 rounded-full bg-white px-3 py-1 text-xs font-black text-navy-900 dark:bg-white/10 dark:text-white">
          {joined} / {required || "?"}
        </span>
      </div>
      <ul className="grid gap-2 text-sm font-semibold text-ink-700 dark:text-navy-100 sm:grid-cols-2">
        {visibleRules.map((item, idx) => (
          <li key={`rule-${mode}-${idx}`} className="flex gap-2 leading-snug">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-500" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
      {allRules.length > 5 ? (
        <button type="button" className="mt-3 text-xs font-black text-cyan-600 dark:text-cyan-300" onClick={onToggle}>
          {open ? tt("common.less", "Kamroq") : tt("common.more", "Ko'proq")}
        </button>
      ) : null}
    </div>
  );
}

export function StudentCompetitionPage({
  data,
  mode,
  onNavigate,
  viewMode = "launcher",
}: {
  data: GenericRow;
  mode: CompetitionMode;
  onNavigate: (section: string) => void;
  viewMode?: "launcher" | "runtime";
}) {
  const tt = useWebT();
  const runtimeMode = viewMode === "runtime";
  const meta = COMPETITION_META[mode];
  const studentSubjects = useMemo(() => studentSubjectNames(data), [data]);
  const studentSubjectKey = studentSubjects.join("|");
  const groups = (data.groups || []) as GenericRow[];
  const [subject, setSubject] = useState(() => subjectFromUrl(studentSubjects) || (studentSubjects.length === 1 ? studentSubjects[0] : ""));
  const [groupId, setGroupId] = useState(() => {
    const urlGroupId = Number(readQueryValue("group_id"));
    if (urlGroupId > 0) return urlGroupId;
    if (mode === "group") return 0;
    return Number(groups[0]?.id || 0);
  });
  const [groupArenaOptions, setGroupArenaOptions] = useState<GenericRow[]>([]);
  const selectedGroupArenaOption = groupArenaOptions.find((item) => Number(item.group_id || 0) === Number(groupId || 0)) || null;
  const selectedCompetitionGroup =
    mode === "group"
      ? (selectedGroupArenaOption || groups.find((group) => Number(group.id || 0) === Number(groupId || 0)) || null)
      : (groups.find((group) => Number(group.id || 0) === Number(groupId || 0)) || groups[0] || null);

  useEffect(() => {
    const urlGroupId = Number(readQueryValue("group_id"));
    if (urlGroupId > 0) {
      setGroupId(urlGroupId);
    } else if (mode !== "group" && groups.length > 0 && !groupId) {
      setGroupId(Number(groups[0]?.id || 0));
    }
  }, [groups, mode]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (mode !== "group" || groupId) return;
    const token = localStorage.getItem("diamond_token");
    if (!token) return;
    let cancelled = false;
    requestJson<GenericRow>("/arena/battles", { token, timeoutMs: 8000, retries: 0 })
      .then((payload) => {
        if (cancelled) return;
        const items = Array.isArray(payload.items) ? (payload.items as GenericRow[]) : [];
        const activeGroupArenas = items.filter((item) => {
          const id = String(item.id || "");
          return id.startsWith("group-") && Number(item.group_id || 0) > 0;
        });
        setGroupArenaOptions(activeGroupArenas);
        const activeGroupArena = activeGroupArenas[0];
        if (!activeGroupArena) return;
        setGroupId(Number(activeGroupArena.group_id || 0));
        const arenaSubject = normalizeSubjectLabel(String(activeGroupArena.subject || ""));
        if (arenaSubject) setSubject(arenaSubject);
      })
      .catch(() => null);
    return () => {
      cancelled = true;
    };
  }, [mode, groupId]);

  useEffect(() => {
    if (mode !== "group") return;
    const token = localStorage.getItem("diamond_token");
    if (!token) return;
    let cancelled = false;
    requestJson<GenericRow>("/arena/battles", { token, timeoutMs: 8000, retries: 0 })
      .then((payload) => {
        if (cancelled) return;
        const items = Array.isArray(payload.items) ? (payload.items as GenericRow[]) : [];
        const activeGroupArenas = items.filter((item) => String(item.id || "").startsWith("group-") && Number(item.group_id || 0) > 0);
        setGroupArenaOptions(activeGroupArenas);
        if (!groupId && activeGroupArenas[0]) {
          setGroupId(Number(activeGroupArenas[0].group_id || 0));
          const arenaSubject = normalizeSubjectLabel(String(activeGroupArenas[0].subject || ""));
          if (arenaSubject) setSubject(arenaSubject);
        }
      })
      .catch(() => {
        if (!cancelled) setGroupArenaOptions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [mode]);

  const [sessionId, setSessionId] = useState("");
  const [theme, setTheme] = useState("core");
  const [status, setStatus] = useState<CompetitionStatusPayload | null>(null);
  const [question, setQuestion] = useState<CompetitionQuestionPayload | null>(null);
  const [result, setResult] = useState<GenericRow | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [timeLeft, setTimeLeft] = useState(0);
  const [waitingRemaining, setWaitingRemaining] = useState<number | null>(null);
  const waitExpiryRefreshKeyRef = useRef("");
  const lastSubmittedIndexRef = useRef<number | null>(null);
  const lastTimerInitIndexRef = useRef<number | null>(null);
  const notParticipantErrorCountRef = useRef(0);
  const missingSessionRecoveryRef = useRef(false);
  const missingSessionRecoveredKeyRef = useRef("");
  const missingSessionAutoRecoveriesRef = useRef(0);
  const [autoTriggered, setAutoTriggered] = useState(false);
  const [lobbyRulesOpen, setLobbyRulesOpen] = useState(true);
  const [proctoringSessionId, setProctoringSessionId] = useState<number | null>(null);
  // Competition (Arena/Duel) never requires proctoring — always ready
  const [proctoringReady, setProctoringReady] = useState(true);
  const [duelView, setDuelView] = useState<"setup" | "history">("setup");
  const [duelHistory, setDuelHistory] = useState<GenericRow[]>([]);
  const [duelHistoryLoading, setDuelHistoryLoading] = useState(false);
  const [duelBlocked, setDuelBlocked] = useState("");
  const groupArenaSubject = normalizeSubjectLabel(String(selectedGroupArenaOption?.subject || selectedCompetitionGroup?.subject || "")) || studentSubjects[0] || "";
  const subjectPromptRequired = mode !== "group" && studentSubjects.length > 1;
  const effectiveSubject = mode === "group" ? groupArenaSubject : (subjectPromptRequired ? subject : (subject || studentSubjects[0])) || "";
  const selectedSubjectReady = mode === "group" ? Boolean(groupId && effectiveSubject) : Boolean(effectiveSubject && (!subjectPromptRequired || studentSubjects.includes(effectiveSubject)));
  const isDuel = mode.startsWith("duel-");
  const fullscreenCompetition = runtimeMode || isDuel;
  const displayTitle = isDuel ? tt(`duel.${mode}.title`, meta.title) : tt(`arena.${mode}.title`, meta.title);
  const displaySubtitle = isDuel ? tt(`duel.${mode}.subtitle`, meta.subtitle) : tt(`arena.${mode}.subtitle`, meta.subtitle);
  const displayCta = isDuel ? tt(`duel.${mode}.cta`, meta.cta) : tt(`arena.${mode}.cta`, meta.cta);
  // Boss Arena is intentionally always available (no schedule window) per spec.
  const isBoss = mode === "boss";
  const economySettings = (data.dpoint_settings || data.economy_rules || {}) as GenericRow;

  function requestRuntimeStart(token: string) {
    return requestJson<GenericRow>("/competition/runtime/start", {
      token,
      method: "POST",
      body: {
        mode,
        subject: effectiveSubject,
        ...(mode === "group" && groupId ? { group_id: groupId } : {}),
      },
    });
  }

  async function loadDuelHistory() {
    const token = localStorage.getItem("diamond_token");
    if (!token) return;
    setDuelHistoryLoading(true);
    setError("");
    try {
      const payload = await requestJson<GenericRow>(`/competition/runtime/history?mode=${encodeURIComponent(mode)}&limit=20`, { token });
      setDuelHistory(Array.isArray(payload.items) ? payload.items as GenericRow[] : []);
      setDuelView("history");
    } catch (err) {
      setError(err instanceof Error ? err.message : tt("arena.historyError", "Tarix yuklanmadi"));
    } finally {
      setDuelHistoryLoading(false);
    }
  }

  async function startOrQueue() {
    if (busy) return;
    const token = localStorage.getItem("diamond_token");
    if (!token) return;
    if (!selectedSubjectReady) {
      const msg = tt("arena.subjectRequired", "Fan tanlang");
      if (isDuel) setDuelBlocked(msg);
      else setError(msg);
      return;
    }
    setBusy(true);
    setError("");
    setDuelBlocked("");
    setResult(null);
    setDuelView("setup");
    setSessionId("");
    setQuestion(null);
    setStatus(null);
    setTimeLeft(0);
    setWaitingRemaining(null);
    missingSessionRecoveredKeyRef.current = "";
    missingSessionAutoRecoveriesRef.current = 0;
    setProctoringReady(true); // proctoring disabled for competition
    try {
      const payload = await requestRuntimeStart(token);
      notParticipantErrorCountRef.current = 0;
      setStatus(payload as CompetitionStatusPayload);
      setTheme(String(payload.theme || theme));
      if (payload.session_id) setSessionId(String(payload.session_id));
      const nextProctoringId = Number(payload.proctoring_session_id || 0) || null;
      const requiresProctoring = Boolean((payload as GenericRow).proctoring_required);
      setProctoringSessionId(nextProctoringId);
      setProctoringReady(true); // proctoring disabled for competition
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not start competition";
      const clean = /active_session_mismatch/i.test(message)
        ? tt("arena.activeSessionMismatch", "Oldingi aktiv sessiya tanlangan rejim yoki fanga mos emas. Iltimos, to'g'ri sessiyani davom ettiring yoki qayta urinib ko'ring.")
        : /insufficient/i.test(message) ? tt("duel.insufficientDcoin", "D'coin yetarli emas") : message;
      if (isDuel) setDuelBlocked(clean);
      else setError(clean);
    } finally {
      setBusy(false);
    }
  }

  async function recoverMissingRuntimeSession(fallbackMessage: string, staleSessionId: string) {
    const recoveryKey = `${mode}|${effectiveSubject}|${groupId || 0}|${staleSessionId || ""}`;
    if (missingSessionRecoveryRef.current || !staleSessionId || missingSessionRecoveredKeyRef.current === recoveryKey || missingSessionAutoRecoveriesRef.current >= 1) {
      setSessionId("");
      setQuestion(null);
      setStatus(null);
      const clean = tt("arena.sessionExpiredRetry", "Sessiya topilmadi yoki tugagan. Qayta boshlash tugmasini bosing.");
      if (isDuel) setDuelBlocked(clean);
      else setError(clean);
      return;
    }
    const token = localStorage.getItem("diamond_token");
    if (!token || !selectedSubjectReady) {
      setSessionId("");
      setQuestion(null);
      setStatus(null);
      const clean = fallbackMessage || tt("arena.sessionMissing", "Sessiya topilmadi. Qayta boshlang.");
      if (isDuel) setDuelBlocked(clean);
      else setError(clean);
      return;
    }
    missingSessionRecoveryRef.current = true;
    missingSessionRecoveredKeyRef.current = recoveryKey;
    missingSessionAutoRecoveriesRef.current += 1;
    setBusy(true);
    setError("");
    setDuelBlocked("");
    setResult(null);
    setSessionId("");
    setQuestion(null);
    setStatus(null);
    setTimeLeft(0);
    setWaitingRemaining(null);
    setProctoringReady(true);
    try {
      const payload = await requestRuntimeStart(token);
      notParticipantErrorCountRef.current = 0;
      missingSessionRecoveredKeyRef.current = "";
      setStatus(payload as CompetitionStatusPayload);
      setTheme(String(payload.theme || theme));
      if (payload.session_id) setSessionId(String(payload.session_id));
      const nextProctoringId = Number(payload.proctoring_session_id || 0) || null;
      setProctoringSessionId(nextProctoringId);
      setProctoringReady(true);
      setDuelView("setup");
    } catch (err) {
      const raw = err instanceof Error ? err.message : fallbackMessage || tt("arena.sessionMissing", "Sessiya topilmadi. Qayta boshlang.");
      const clean = /insufficient/i.test(raw) ? tt("duel.insufficientDcoin", "D'coin yetarli emas") : raw;
      if (isDuel) setDuelBlocked(clean);
      else setError(clean);
    } finally {
      missingSessionRecoveryRef.current = false;
      setBusy(false);
    }
  }

  async function leaveCompetitionQueue() {
    if (!sessionId || busy) return;
    const token = localStorage.getItem("diamond_token");
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      const payload = await requestJson<GenericRow>(`/competition/runtime/${encodeURIComponent(sessionId)}/leave`, {
        token,
        method: "POST",
      });
      setStatus(null);
      setQuestion(null);
      setSessionId("");
      setDuelView("setup");
      setDuelBlocked(payload.refunded ? tt("duel.refundMessage", "Duel boshlanmadi va kirish narxi qaytarildi.") : tt("duel.leftQueue", "Lobby tark etildi."));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (/topilmadi|not found/i.test(msg)) {
        setStatus(null);
        setQuestion(null);
        setSessionId("");
        setDuelView("setup");
      } else {
        setError(msg || tt("duel.cancelFailed", "Lobby tark etilmadi"));
      }
    } finally {
      setBusy(false);
    }
  }

  const refreshingRef = useRef(false);

  async function refreshRuntime() {
    if (!sessionId || refreshingRef.current) return;
    const token = localStorage.getItem("diamond_token");
    if (!token) return;
    const requestedSessionId = sessionId;
    refreshingRef.current = true;
    try {
      const statusPayload = await requestJson<CompetitionStatusPayload>(`/competition/runtime/${encodeURIComponent(requestedSessionId)}/status`, { token });
      const resolvedSessionId = String(statusPayload.session_id || requestedSessionId);
      notParticipantErrorCountRef.current = 0;
      setStatus(statusPayload);
      setTheme(String(statusPayload.theme || theme));
      if (resolvedSessionId && resolvedSessionId !== requestedSessionId) {
        setSessionId(resolvedSessionId);
      }
      const phaseNow = String(statusPayload.phase || "").toLowerCase();
      if (phaseNow === "finished" || String(statusPayload.status || "") === "finished") {
        const resultPayload = await requestJson<GenericRow>(`/competition/runtime/${encodeURIComponent(resolvedSessionId)}/result`, { token });
        if (resultPayload.ready) {
          setResult(resultPayload);
          setSessionId("");
          setQuestion(null);
        }
        return;
      }
      if (phaseNow === "active") {
        const statusQIndex = Number(statusPayload.question_index || 0);
        const currentQIndex = Number(question?.question_index || 0);
        const shouldFetchQuestion =
          !question
          || question.completed
          || String(question.phase || "").toLowerCase() !== "active"
          || statusQIndex > currentQIndex;
        if (shouldFetchQuestion) {
          const qUrl = proctoringSessionId
            ? `/competition/runtime/${encodeURIComponent(resolvedSessionId)}/question?proctoring_session_id=${encodeURIComponent(String(proctoringSessionId))}`
            : `/competition/runtime/${encodeURIComponent(resolvedSessionId)}/question`;
          const questionPayload = await requestJson<CompetitionQuestionPayload>(qUrl, { token });
          setQuestion(questionPayload);
          setTimeLeft(Math.max(0, Number(questionPayload.time_remaining_sec || questionPayload.time_limit_sec || 0)));
          if (questionPayload.completed) {
            const resultPayload = await requestJson<GenericRow>(`/competition/runtime/${encodeURIComponent(resolvedSessionId)}/result`, { token });
            if (resultPayload.ready) {
              setResult(resultPayload);
              setSessionId("");
              setQuestion(null);
            }
          }
        }
      } else {
        setQuestion(null);
        setTimeLeft(0);
      }
    } catch (err) {
      const reason = proctoringStopReason(err instanceof Error ? err.message : err);
      if (reason) {
        setError("");
        setProctoringReady(false);
        setResult({
          ready: true,
          proctoring_stopped: true,
          proctoring_failure_reason: reason,
          proctoring_failure_message: proctoringFriendlyError(reason),
          result: {
            correct: 0,
            wrong: 0,
            unanswered: Number(question?.total_questions || status?.total_questions || 0),
            dpoints_delta: 0,
          },
        });
        setSessionId("");
        setQuestion(null);
      } else {
        const clean = err instanceof Error ? err.message : "Could not refresh competition state";
        const cleanLower = clean.toLowerCase();
        if (cleanLower.includes("not found")) {
          await recoverMissingRuntimeSession(clean, requestedSessionId);
          return;
        } else if (cleanLower.includes("not assigned") || cleanLower.includes("not participant")) {
          notParticipantErrorCountRef.current += 1;
          if (notParticipantErrorCountRef.current >= 3) {
            setSessionId("");
            setQuestion(null);
            setStatus(null);
          } else {
            window.setTimeout(() => {
              refreshRuntime();
            }, 1200);
          }
        }
        if (isDuel) setDuelBlocked(clean);
        else setError(clean);
      }
    } finally {
      refreshingRef.current = false;
    }
  }

  async function submitAnswer(answer: number | null) {
    if (!sessionId || !question || busy || question.completed) return;
    const requestedSessionId = sessionId;
    const qIndex = question.question_index;
    if (lastSubmittedIndexRef.current === qIndex) return;
    lastSubmittedIndexRef.current = qIndex;

    const token = localStorage.getItem("diamond_token");
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      const payload = await requestJson<GenericRow>(`/competition/runtime/${encodeURIComponent(requestedSessionId)}/answer`, {
        token,
        method: "POST",
        body: {
          ...answerBody(answer),
          question_index: qIndex,
          proctoring_session_id: null,
        },
      });
      notParticipantErrorCountRef.current = 0;
      if (payload.completed) {
        const resultPayload = await requestJson<GenericRow>(`/competition/runtime/${encodeURIComponent(requestedSessionId)}/result`, { token });
        if (resultPayload.ready) {
          setResult(resultPayload);
          setSessionId("");
          setQuestion(null);
        } else {
          await refreshRuntime();
        }
      } else {
        // Don't call refreshRuntime() immediately — it can race and return old question_index.
        // Fetch next question directly.
        const qUrl = `/competition/runtime/${encodeURIComponent(requestedSessionId)}/question`;
        const questionPayload = await requestJson<CompetitionQuestionPayload>(qUrl, { token });
        setQuestion(questionPayload);
        setTimeLeft(Math.max(0, Number(questionPayload.time_remaining_sec || questionPayload.time_limit_sec || 0)));
        if (questionPayload.completed) {
          const resultPayload = await requestJson<GenericRow>(`/competition/runtime/${encodeURIComponent(requestedSessionId)}/result`, { token });
          if (resultPayload.ready) {
            setResult(resultPayload);
            setSessionId("");
            setQuestion(null);
          }
        }
      }
    } catch (err) {
      lastSubmittedIndexRef.current = null;
      if (timeLeft <= 0) {
        setTimeLeft(5);
      }
      const reason = proctoringStopReason(err instanceof Error ? err.message : err);
      if (reason) {
        setError("");
        setProctoringReady(false);
        setResult({
          ready: true,
          proctoring_stopped: true,
          proctoring_failure_reason: reason,
          proctoring_failure_message: proctoringFriendlyError(reason),
          result: {
            correct: 0,
            wrong: 0,
            unanswered: Number(question?.total_questions || status?.total_questions || 0),
            dpoints_delta: 0,
          },
        });
        setSessionId("");
        setQuestion(null);
      } else {
        const clean = err instanceof Error ? err.message : "Could not submit answer";
        const cleanLower = clean.toLowerCase();
        if (cleanLower.includes("not found")) {
          await recoverMissingRuntimeSession(clean, requestedSessionId);
          return;
        } else if (cleanLower.includes("not assigned") || cleanLower.includes("not participant")) {
          notParticipantErrorCountRef.current += 1;
          if (notParticipantErrorCountRef.current >= 3) {
            setSessionId("");
            setQuestion(null);
            setStatus(null);
          } else {
            window.setTimeout(() => {
              refreshRuntime();
            }, 1200);
          }
        }
        setError(clean);
      }
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    const fromUrl = normalizeSubjectLabel(readQueryValue("subject"));
    if (fromUrl) {
      setSubject(fromUrl);
      return;
    }
    setSubject((prev) => {
      if (studentSubjects.length === 1) return studentSubjects[0] || "";
      return prev && studentSubjects.includes(prev) ? prev : "";
    });
  }, [studentSubjectKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setSessionId("");
    setStatus(null);
    setQuestion(null);
    setResult(null);
    setError("");
    setDuelBlocked("");
    setAutoTriggered(false);
    setLobbyRulesOpen(false);
    setTimeLeft(0);
    setWaitingRemaining(null);
    lastSubmittedIndexRef.current = null;
    notParticipantErrorCountRef.current = 0;
    missingSessionRecoveredKeyRef.current = "";
    missingSessionAutoRecoveriesRef.current = 0;
  }, [mode, effectiveSubject, groupId]);

  useEffect(() => {
    if (autoTriggered || sessionId || busy) return;
    const modeFromUrl = String(readQueryValue("arena_mode") || "").trim().toLowerCase();
    const autoJoin = String(readQueryValue("auto_join") || "").trim() === "1";
    const subjectFromUrl = normalizeSubjectLabel(readQueryValue("subject"));
    const normalized =
      modeFromUrl === "1v1" ? "duel-1v1"
      : modeFromUrl === "3v3" ? "duel-3v3"
      : modeFromUrl === "5v5" ? "duel-5v5"
      : modeFromUrl === "arena-daily" ? "daily"
      : modeFromUrl === "arena-group" ? "group"
      : modeFromUrl === "arena-boss" ? "boss"
      : modeFromUrl;
    if (!autoJoin || normalized !== mode) return;
    if (subjectPromptRequired && !subjectFromUrl) return;
    if (mode === "group" && !groupId) return;
    if (!selectedSubjectReady) return;
    setAutoTriggered(true);
    startOrQueue()
      .catch(() => null)
      .finally(() => {
        if (typeof window === "undefined") return;
        const url = new URL(window.location.href);
        if (!url.searchParams.has("auto_join")) return;
        url.searchParams.delete("auto_join");
        window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
      });
  }, [autoTriggered, mode, sessionId, busy, effectiveSubject, subjectPromptRequired, selectedSubjectReady]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let cancelled = false;
    const token = localStorage.getItem("diamond_token");
    if (!token) return;
    if (!selectedSubjectReady) return;
    async function checkActive() {
      try {
        const params = new URLSearchParams();
        params.set("mode", mode);
        params.set("subject", effectiveSubject);
        if (mode === "group" && groupId) params.set("group_id", String(groupId));
        const payload = await requestJson<GenericRow>(`/competition/runtime/my-active?${params.toString()}`, { token });
        if (cancelled) return;
        const sameSubject = normalizeSubjectLabel(payload.subject) === normalizeSubjectLabel(effectiveSubject);
        const sameGroup = mode !== "group" || Number(payload.group_id || 0) === Number(groupId || 0);
        if (payload.active && String(payload.mode || "") === mode && sameSubject && sameGroup && payload.session_id) {
          setSessionId(String(payload.session_id));
          setStatus(payload as CompetitionStatusPayload);
          await refreshRuntime();
        }
      } catch {
        // ignore initial probe errors
      }
    }
    checkActive();
    return () => {
      cancelled = true;
    };
  }, [mode, effectiveSubject, groupId, selectedSubjectReady]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!sessionId) return;
    refreshRuntime();
    const pollPhase = String(status?.phase || question?.phase || (result?.ready ? "finished" : "pending"));
  const isLobbyExpired = ["expired", "cancelled", "timeout"].includes(pollPhase.toLowerCase()) || (status?.status || "").toLowerCase().includes("expir");
    const intervalMs = isDuel
      ? (pollPhase === "pending" ? 1800 : pollPhase === "generating" ? 1200 : pollPhase === "active" ? 6500 : 0)
      : (pollPhase === "pending" ? 2000 : pollPhase === "generating" ? 1200 : pollPhase === "active" ? 6500 : 0);
    if (!intervalMs) return;
    const timer = window.setInterval(refreshRuntime, intervalMs);
    return () => window.clearInterval(timer);
  }, [sessionId, status?.phase, question?.phase, result?.ready, isDuel]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!question || question.completed || busy || status?.phase !== "active") return;
    setTimeLeft(Math.max(0, Number(question.time_remaining_sec || question.time_limit_sec || 0)));
    lastTimerInitIndexRef.current = question.question_index;
  }, [question?.question_index, question?.time_remaining_sec, question?.time_limit_sec, question?.completed, busy, status?.phase]);

  useEffect(() => {
    if (!question || question.completed || busy || status?.phase !== "active") return;
    const timer = window.setInterval(() => {
      setTimeLeft((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [question?.question_index, question?.completed, busy, status?.phase]);

  useEffect(() => {
    if (!question || question.completed || busy || !sessionId || status?.phase !== "active") return;
    if (lastTimerInitIndexRef.current !== question.question_index) return;
    if (timeLeft > 0) return;
    submitAnswer(null);
  }, [timeLeft, question?.question_index, question?.completed, busy, sessionId, status?.phase]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep server clock skew in a ref so it updates on every status poll
  // WITHOUT triggering the countdown interval to restart.
  const serverClockSkewRef = useRef(0);
  useEffect(() => {
    if (!status?.server_now) return;
    const serverMs = parseCompetitionTimeMs(status.server_now);
    if (Number.isFinite(serverMs)) {
      serverClockSkewRef.current = serverMs - Date.now();
    }
  }, [status?.server_now]);

  useEffect(() => {
    const phaseNow = String(status?.phase || "");
    if (!sessionId || (phaseNow !== "pending" && phaseNow !== "generating")) {
      setWaitingRemaining(null);
      return;
    }
    const skew = serverClockSkewRef.current;
    const waitSeconds = Number(status?.wait_seconds || status?.allowed_wait_seconds || 300);

    // Priority 1: use the absolute UTC deadline from the server (most reliable, never resets).
    // Priority 2: first_joined_at + waitSeconds — first_joined_at is set once and never changes.
    // Priority 3: server's pre-computed remaining — seed once so refresh shows correct value instantly.
    // Priority 4: last resort client-side estimate (only when nothing else is available).
    let deadlineMs: number | null = null;

    if (status?.wait_deadline_at) {
      const ms = parseCompetitionTimeMs(status.wait_deadline_at);
      if (Number.isFinite(ms)) deadlineMs = ms;
    }
    if (deadlineMs === null && status?.first_joined_at) {
      const ms = parseCompetitionTimeMs(status.first_joined_at);
      if (Number.isFinite(ms)) deadlineMs = ms + waitSeconds * 1000;
    }

    // Seed initial display immediately from server-computed remaining (so refresh looks correct at once)
    if (deadlineMs === null && status?.waiting_remaining_sec != null) {
      const serverRemaining = Number(status.waiting_remaining_sec);
      if (serverRemaining > 0) {
        deadlineMs = Date.now() + skew + serverRemaining * 1000;
        setWaitingRemaining(serverRemaining);
      }
    }

    // Last resort: start fresh countdown (only when server sent no anchor at all)
    if (deadlineMs === null) {
      deadlineMs = Date.now() + skew + waitSeconds * 1000;
    }

    const deadlineMsFinal = deadlineMs;
    const tick = () => {
      const nowMs = Date.now() + serverClockSkewRef.current;
      setWaitingRemaining(Math.max(0, Math.ceil((deadlineMsFinal - nowMs) / 1000)));
    };
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  // Intentionally exclude last_joined_at — it changes on every new player join and would reset the timer.
   
  }, [sessionId, status?.phase, status?.wait_deadline_at, status?.first_joined_at, status?.waiting_remaining_sec, status?.wait_seconds, status?.allowed_wait_seconds]);

  useEffect(() => {
    const phaseNow = String(status?.phase || "");
    if (!sessionId || (phaseNow !== "pending" && phaseNow !== "generating") || waitingRemaining !== 0) return;
    const refreshKey = `${sessionId}:${String(status?.wait_deadline_at || status?.last_joined_at || "")}`;
    if (waitExpiryRefreshKeyRef.current === refreshKey) return;
    waitExpiryRefreshKeyRef.current = refreshKey;
    const timer = window.setTimeout(() => {
      refreshRuntime();
    }, 250);
    return () => window.clearTimeout(timer);
  }, [sessionId, status?.phase, status?.wait_deadline_at, status?.last_joined_at, waitingRemaining]); // eslint-disable-line react-hooks/exhaustive-deps

  const statusLive = status?.live || question?.live || { remained: [], left: [] };
  const phase = (status?.phase || question?.phase || (result?.ready ? "finished" : "pending")) as CompetitionPhase;
  const participants = (status?.participants || []) as CompetitionParticipant[];
  const participantsCount = Number(status?.participants_count || participants.length || 0);
  const requiredPlayers = Number(status?.required_players || 0);
  const maxPlayers = Number(status?.max_players || requiredPlayers || 0);
  const remainingPlayers = Number(status?.remaining_players ?? Math.max(0, requiredPlayers - participantsCount));
  const rawGenerationPercent = Math.max(0, Math.min(100, Number(status?.stage_generation_percent ?? status?.generation_percent ?? question?.stage_generation_percent ?? question?.generation_percent ?? 0)));
  const generationStarted = Boolean(status?.generation_started || question?.generation_started || phase === "generating" || phase === "active");
  const generationPercent = generationStarted ? rawGenerationPercent : 0;
  const showPending = Boolean(!result?.ready && sessionId && (phase === "pending" || phase === "generating"));
  const showRuntime = Boolean(!result?.ready && sessionId && phase === "active");
  const progressPercent = Number(question?.progress_percent ?? status?.progress_percent ?? 0);
  const hasDailyStages = mode === "daily";
  const stage = Math.max(0, Number(status?.stage ?? question?.stage ?? 0));
  const totalStages = Math.max(1, Number(status?.total_stages ?? question?.total_stages ?? (mode === "daily" ? 5 : 1)));
  const initialParticipants = Math.max(0, Number(status?.initial_participants ?? question?.initial_participants ?? participantsCount));
  const activeParticipantsCount = Math.max(0, Number(status?.active_participants_count ?? question?.active_participants_count ?? statusLive.remained?.length ?? 0));
  const eliminatedParticipantsCount = Math.max(0, Number(status?.eliminated_participants_count ?? question?.eliminated_participants_count ?? statusLive.left?.length ?? 0));
  const finalistsTarget = Math.max(0, Number(status?.finalists_target ?? question?.finalists_target ?? (mode === "daily" ? 4 : 0)));
  const waitingStageCompletion = Boolean(question?.waiting_stage_completion);
  const waitingForOtherParticipants = Boolean(question?.waiting_completion || (waitingStageCompletion && !hasDailyStages));
  const eliminatedNow = Boolean(question?.eliminated);
  const isTie = Boolean(result?.tie || result?.result?.tie || result?.result?.result_status === "tie");
  const isRefunded = Boolean(result?.result?.refunded);
  const isWinner = Boolean(result?.result?.winner && !isTie);
  const bossSummary = (result?.boss_summary || {}) as GenericRow;
  const bossParticipants = Array.isArray(bossSummary.participants) ? bossSummary.participants as GenericRow[] : [];
  const resultParticipants = Array.isArray(result?.participants_result) ? result.participants_result as GenericRow[] : [];
  const runtimeRoute = competitionRuntimePath(mode, { subject: effectiveSubject, autoJoin: false }) || studentSectionToPath(meta.section);
  const timeLabel = `${Math.floor(timeLeft / 60).toString().padStart(2, "0")}:${(timeLeft % 60).toString().padStart(2, "0")}`;
  const waitTotalSeconds = Math.max(1, Number(status?.wait_seconds ?? status?.allowed_wait_seconds ?? 300));
  const shellClass = fullscreenCompetition
    ? "duel-screen-root flex min-h-[100dvh] flex-col overflow-hidden bg-background selection:bg-cyan-500/30 selection:text-cyan-900 dark:selection:text-cyan-100 relative"
    : "flex h-[calc(100vh-80px)] max-h-screen flex-col overflow-hidden bg-background selection:bg-cyan-500/30 selection:text-cyan-900 dark:selection:text-cyan-100 relative";
  const contentClass = fullscreenCompetition
    ? "flex-1 overflow-y-auto w-full p-3 sm:p-5 lg:p-6"
    : "flex-1 overflow-y-auto w-full p-3 sm:p-6 lg:p-8";
  const contentInnerClass = fullscreenCompetition
    ? "max-w-6xl mx-auto space-y-5 relative"
    : "max-w-4xl mx-auto space-y-6 relative";

  return (
    <div className={shellClass}>
      {error && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[60] bg-red-100 text-red-700 px-4 py-2 rounded-xl shadow-lg border border-red-200 text-sm font-medium animate-fade-in-up">
          {error}
        </div>
      )}
      
      <div className={contentClass}>
        <div className={contentInnerClass}>
          
          {!runtimeMode && (
            <div className="mb-8">
              <h1 className="text-2xl font-bold text-navy-900 dark:text-white mb-1">{displayTitle}</h1>
              <p className="text-sm text-ink-500 dark:text-navy-300">{displaySubtitle}</p>
            </div>
          )}

          {isDuel && duelBlocked && !showPending && !showRuntime && !result?.ready && (
            <div className="competition-surface-card bg-white dark:bg-navy-900/70 rounded-[1.5rem] p-5 sm:p-7 shadow-premium border border-red-200 dark:border-red-500/30 text-center">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-red-100 text-2xl font-black text-red-700 dark:bg-red-500/15 dark:text-red-200">!</div>
              <h2 className="mb-2 text-2xl font-black text-navy-900 dark:text-white">{tt("duel.blocked", "Duel ochilmadi")}</h2>
              <p className="mx-auto mb-6 max-w-lg text-sm font-semibold text-ink-600 dark:text-navy-200">{duelBlocked}</p>
              <div className="flex flex-wrap justify-center gap-3">
                <button
                  className="rounded-2xl bg-navy-900 px-6 py-3 font-bold text-white transition hover:bg-navy-800 dark:bg-cyan-500 dark:hover:bg-cyan-600"
                  onClick={() => {
                    setDuelBlocked("");
                    startOrQueue();
                  }}
                >
                  {tt("duel.playAgain", "Qayta o'ynash")}
                </button>
                <button
                  className="rounded-2xl bg-surface-soft px-6 py-3 font-bold text-ink-700 transition hover:bg-line dark:bg-white/10 dark:text-navy-100 dark:hover:bg-white/15"
                  onClick={() => {
                    setDuelBlocked("");
                    setDuelView("setup");
                  }}
                >
                  {tt("duel.back", "Orqaga")}
                </button>
              </div>
            </div>
          )}
          
          {duelView === "history" && !duelBlocked && !showPending && !showRuntime && !result?.ready && (
            <div className="competition-surface-card bg-white dark:bg-navy-900/70 rounded-[1.5rem] p-4 sm:p-6 shadow-premium border border-line dark:border-white/10">
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-xl font-black text-navy-900 dark:text-white">{tt("arena.history", "Tarix")}</h2>
                  <p className="text-sm font-medium text-ink-500 dark:text-navy-300">{displayTitle}</p>
                </div>
                <button className="rounded-2xl bg-surface-soft px-5 py-3 font-bold text-ink-700 transition hover:bg-line dark:bg-white/10 dark:text-navy-100 dark:hover:bg-white/15" onClick={() => setDuelView("setup")}>
                  {tt("duel.back", "Orqaga")}
                </button>
              </div>
              {duelHistoryLoading ? (
                <div className="py-12 text-center font-bold text-ink-500 dark:text-navy-200">{tt("common.loading", "Yuklanmoqda...")}</div>
              ) : duelHistory.length ? (
                <div className="duel-history-grid grid gap-3 sm:grid-cols-2">
                  {duelHistory.map((item) => {
                    const statusText = String(item.result_status || "");
                    const tie = statusText === "tie" || Number(item.tie || 0) === 1;
                    return (
                      <article key={`${item.session_id}-${item.created_at}`} className="rounded-2xl border border-line bg-surface-soft p-4 dark:border-white/10 dark:bg-navy-950/70">
                        <div className="mb-3 flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-black text-navy-900 dark:text-white">{item.subject || effectiveSubject}</p>
                            <p className="text-xs font-semibold text-ink-500 dark:text-navy-300">{item.mode || mode}</p>
                          </div>
                          <span className={`rounded-full px-3 py-1 text-xs font-black ${tie ? "bg-slate-100 text-slate-700 dark:bg-white/10 dark:text-slate-100" : statusText === "win" ? "bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-200" : "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-200"}`}>
                            {tie ? tt("duel.tie", "Durang") : statusText === "win" ? tt("duel.winner", "G'olib") : statusText === "lose" ? tt("duel.lose", "Yutqazdi") : `${tt("arena.place", "O'rin")}: ${item.rank || "-"}`}
                          </span>
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-center">
                          <div className="rounded-xl bg-white p-2 dark:bg-navy-900">
                            <p className="text-[11px] font-bold text-ink-500">{tt("duel.correct", "To'g'ri")}</p>
                            <p className="text-lg font-black text-green-600 dark:text-green-300">{Number(item.correct_count || 0)}</p>
                          </div>
                          <div className="rounded-xl bg-white p-2 dark:bg-navy-900">
                            <p className="text-[11px] font-bold text-ink-500">{tt("duel.wrong", "Xato")}</p>
                            <p className="text-lg font-black text-red-600 dark:text-red-300">{Number(item.wrong_count || 0)}</p>
                          </div>
                          <div className="rounded-xl bg-white p-2 dark:bg-navy-900">
                            <p className="text-[11px] font-bold text-ink-500">{tt("duel.skipped", "O'tkazildi")}</p>
                            <p className="text-lg font-black text-ink-700 dark:text-navy-100">{Number(item.skipped_count || 0)}</p>
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </div>
              ) : (
                <div className="py-12 text-center font-bold text-ink-500 dark:text-navy-200">{tt("arena.historyEmpty", "Hali tarix yo'q")}</div>
              )}
            </div>
          )}

          {!duelBlocked && !showPending && !showRuntime && !result?.ready && (!isDuel || duelView === "setup") && (
            <div className={`bg-white dark:bg-slate-950/80 rounded-[2rem] p-6 sm:p-8 shadow-[0_8px_30px_rgb(0,0,0,0.04)] dark:shadow-[0_8px_30px_rgba(6,182,212,0.15)] border border-line dark:border-cyan-500/20 relative overflow-hidden backdrop-blur-xl`}>
              <div className="absolute top-0 inset-x-0 h-32 bg-gradient-to-b from-indigo-500/10 via-cyan-500/5 to-transparent dark:from-indigo-500/20 dark:via-cyan-500/10 pointer-events-none" />
              
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-10 relative z-10">
                <div className="flex items-center gap-4">
                  <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-50 to-cyan-50 dark:from-indigo-500/20 dark:to-cyan-500/10 border border-white dark:border-white/5 shadow-sm flex items-center justify-center text-indigo-600 dark:text-cyan-400 relative">
                    <span className="absolute -right-1 -top-1 w-3 h-3 bg-green-500 rounded-full border-2 border-white dark:border-navy-900 animate-pulse" />
                    <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                  </div>
                  <div>
                    <h2 className="text-2xl sm:text-3xl font-black text-navy-900 dark:text-white tracking-tight">{displayTitle} {tt("competition.setup", "Sozlash")}</h2>
                    <p className="text-sm text-ink-500 dark:text-navy-300 font-medium mt-1">{tt("duel.ready", "Tayyor bo'ling. 5 daqiqalik kutilish vaqti beriladi.")}</p>
                  </div>
                </div>
              </div>

              <div className="grid sm:grid-cols-3 gap-5 mb-10 relative z-10">
                {mode === "group" ? (
                  <label className="flex flex-col gap-2 sm:col-span-2 relative group">
                    <span className="text-xs font-black uppercase tracking-wider text-indigo-600 dark:text-indigo-400 ml-1">{tt("arena.group", "Guruh")}</span>
                    <select
                      value={groupId || ""}
                      onChange={(event) => {
                        const nextGroupId = Number(event.target.value || 0);
                        setGroupId(nextGroupId);
                        const nextArena = groupArenaOptions.find((item) => Number(item.group_id || 0) === nextGroupId);
                        const nextSubject = normalizeSubjectLabel(String(nextArena?.subject || ""));
                        if (nextSubject) setSubject(nextSubject);
                      }}
                      className="appearance-none bg-surface-soft dark:bg-navy-950/50 border border-line dark:border-white/10 text-navy-900 dark:text-white rounded-2xl px-5 py-4 font-bold focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 w-full transition-all group-hover:border-indigo-300 dark:group-hover:border-indigo-500/50 cursor-pointer"
                    >
                      <option value="">{tt("arena.selectOpenGroup", "Ochiq arenani tanlang")}</option>
                      {groupArenaOptions.map((item) => (
                        <option key={`group-arena-${item.session_id || item.id}`} value={Number(item.group_id || 0)}>
                          {item.group_name || item.title || `Group #${item.group_id}`} · {item.subject || "-"}
                        </option>
                      ))}
                    </select>
                    {!groupArenaOptions.length ? <span className="absolute -bottom-6 left-1 text-[11px] font-black text-amber-600 dark:text-amber-400">{tt("arena.noOpenGroupArena", "Hozir ochiq Group Arena yo'q")}</span> : null}
                  </label>
                ) : subjectPromptRequired ? (
                  <label className="flex flex-col gap-2 relative group">
                    <span className="text-xs font-black uppercase tracking-wider text-indigo-600 dark:text-indigo-400 ml-1">{tt("duel.subject", "Fan")}</span>
                    <div className="relative w-full">
                      <select 
                        value={subject} 
                        onChange={(event) => setSubject(event.target.value)}
                        className="appearance-none bg-surface-soft dark:bg-navy-950/50 border border-line dark:border-white/10 text-navy-900 dark:text-white rounded-2xl px-5 py-4 pr-12 font-bold focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 w-full transition-all group-hover:border-indigo-300 dark:group-hover:border-indigo-500/50 cursor-pointer"
                      >
                        <option value="">{tt("arena.selectSubject", "Fan tanlang")}</option>
                        {studentSubjects.map((item) => <option key={item} value={item}>{item}</option>)}
                      </select>
                      <svg className="absolute right-5 top-1/2 -translate-y-1/2 w-5 h-5 text-ink-400 dark:text-navy-400 pointer-events-none transition-transform group-hover:text-indigo-500 dark:group-hover:text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                    {!selectedSubjectReady ? <span className="absolute -bottom-6 left-1 text-[11px] font-black text-red-500">{tt("arena.subjectRequired", "Fan tanlang")}</span> : null}
                  </label>
                ) : (
                  <div className="flex flex-col gap-2">
                    <span className="text-xs font-black uppercase tracking-wider text-ink-400 dark:text-navy-400 ml-1">{tt("duel.subject", "Fan")}</span>
                    <div className="bg-slate-50 dark:bg-navy-950/30 border border-line dark:border-white/5 text-navy-900 dark:text-white rounded-2xl px-5 py-4 font-bold opacity-80 cursor-not-allowed">
                      {effectiveSubject || "-"}
                    </div>
                  </div>
                )}
                
              </div>

              {/* Lobby info pills — dynamic from economy settings */}
              {(() => {
                const eco = economySettings as GenericRow;
                const entryFeeVal = Number(
                  mode.startsWith("duel-") ? (eco.duel_entry_fee_dcoin ?? eco.duel_entry_fee ?? 0) :
                  mode === "group" ? 0 :
                  (eco.arena_entry_fee_dcoin ?? eco.arena_entry_fee ?? 0)
                );
                const minPlayers = mode === "duel-1v1" ? 2 : mode === "duel-3v3" ? 6 : mode === "duel-5v5" ? 10 : mode === "boss" ? (eco.boss_arena_min_participants ?? 5) : mode === "daily" ? (eco.daily_arena_min_participants ?? 10) : 0;
                const pills: Array<{ icon: string; label: string; value: string; color: string }> = [];
                if (entryFeeVal > 0) pills.push({ icon: "💎", label: tt("arena.entryFee", "Kirish narxi"), value: `${entryFeeVal.toFixed(entryFeeVal % 1 ? 1 : 0)} D'coin`, color: "bg-amber-50 border-amber-200/60 text-amber-800 dark:bg-amber-500/10 dark:border-amber-400/20 dark:text-amber-200" });
                if (mode !== "group" && Number(minPlayers) > 0) pills.push({ icon: "👥", label: tt("arena.rules.minimumParticipants", "Min o'yinchilar"), value: String(minPlayers), color: "bg-indigo-50 border-indigo-200/60 text-indigo-800 dark:bg-indigo-500/10 dark:border-indigo-400/20 dark:text-indigo-200" });
                if (mode === "boss") {
                  const bossThreshold = Number(eco.boss_arena_global_threshold_percent ?? 86);
                  const bossPerCorrect = Number(eco.boss_arena_reward_per_correct ?? 3);
                  pills.push({ icon: "🎯", label: tt("arena.bossThreshold", "Mukofot chegarasi"), value: `${bossThreshold}%+`, color: "bg-rose-50 border-rose-200/60 text-rose-800 dark:bg-rose-500/10 dark:border-rose-400/20 dark:text-rose-200" });
                  pills.push({ icon: "⭐", label: tt("arena.bossPerCorrect", "Har to'g'ri javob"), value: `+${bossPerCorrect} D'pt`, color: "bg-emerald-50 border-emerald-200/60 text-emerald-800 dark:bg-emerald-500/10 dark:border-emerald-400/20 dark:text-emerald-200" });
                }
                if (!pills.length) return <div className="mb-10 relative z-10" />;
                return (
                  <div className="flex flex-wrap gap-2.5 mb-8 relative z-10">
                    {pills.map((p, i) => (
                      <div key={i} className={`flex items-center gap-2 rounded-2xl border px-4 py-2.5 ${p.color}`}>
                        <span className="text-base">{p.icon}</span>
                        <div>
                          <p className="text-[10px] font-bold uppercase tracking-wider opacity-70">{p.label}</p>
                          <p className="text-sm font-black">{p.value}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                );
              })()}

              <div className="flex flex-col sm:flex-row flex-wrap gap-4 relative z-10">
                <button 
                  className="group relative flex-grow sm:flex-grow-0 bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white px-10 py-4 rounded-2xl font-black transition-all shadow-[0_0_20px_rgba(99,102,241,0.3)] hover:shadow-[0_0_25px_rgba(99,102,241,0.5)] flex items-center justify-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed overflow-hidden"
                  disabled={busy || !selectedSubjectReady || (Boolean(sessionId) && phase !== "finished")} 
                  onClick={startOrQueue}
                >
                  <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-out" />
                  <span className="relative flex items-center gap-3">
                    {busy ? (
                      <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : (
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    )}
                    {displayCta}
                  </span>
                </button>
                {/* History button removed as requested */}
                {!runtimeMode && (
                  <button 
                    className="bg-surface-soft hover:bg-red-50 dark:bg-white/5 dark:hover:bg-red-500/10 text-ink-700 hover:text-red-600 dark:text-navy-100 dark:hover:text-red-400 px-8 py-4 rounded-2xl font-bold transition-all flex-grow sm:flex-grow-0 text-center"
                    onClick={() => onNavigate("arena")}
                  >
                    {tt("duel.back", "Orqaga")}
                  </button>
                )}
              </div>
            </div>
          )}

          {showPending && (
            <div className={`bg-white dark:bg-slate-950/80 rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] dark:shadow-[0_8px_30px_rgba(6,182,212,0.15)] border border-line dark:border-cyan-500/20 overflow-hidden backdrop-blur-xl relative`}>
              <div className="absolute top-0 inset-x-0 h-40 bg-gradient-to-b from-indigo-500/10 to-transparent dark:from-indigo-500/20 pointer-events-none" />
              
              <div className="p-6 sm:p-8 border-b border-line dark:border-white/10 relative z-10">
                <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mb-6">
                  <div className="flex items-center gap-3">
                    <div className="relative flex items-center justify-center w-12 h-12 rounded-2xl bg-indigo-50 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400">
                      <span className="absolute inset-0 rounded-2xl border border-indigo-500/30 animate-pulse" />
                      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    </div>
                    <div>
                      <h3 className="text-xl sm:text-2xl font-black text-navy-900 dark:text-white tracking-tight">
                        {tt("duel.pendingLobby", "Kutilayotgan lobby")}
                      </h3>
                      <p className="text-sm font-medium text-ink-500 dark:text-navy-300">
                        {generationStarted 
                          ? tt("duel.matchStarted", "Duel boshlandi")
                          : tt("duel.waitingPlayers", "O'yinchilar kutilmoqda")}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 px-4 py-2 rounded-2xl bg-white dark:bg-slate-900/80 border border-line dark:border-cyan-500/30 shadow-sm">
                      <div className="flex -space-x-2">
                        {[...Array(Math.min(3, participantsCount))].map((_, i) => (
                          <div key={i} className="w-8 h-8 rounded-full bg-cyan-100 dark:bg-cyan-900/60 border-2 border-white dark:border-slate-900 flex items-center justify-center text-xs font-black text-cyan-700 dark:text-cyan-300 shadow-sm">
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
                          </div>
                        ))}
                      </div>
                      <span className="pl-2 text-sm font-black text-navy-900 dark:text-white">
                        {participantsCount} / {requiredPlayers || "?"}
                      </span>
                    </div>
                    {phase === "pending" && !generationStarted && (
                      <button
                        className="w-10 h-10 flex shrink-0 items-center justify-center rounded-2xl bg-red-50 text-red-600 hover:bg-red-100 hover:text-red-700 transition dark:bg-red-500/10 dark:text-red-400 dark:hover:bg-red-500/20"
                        title={tt("duel.leaveQueue", "Lobbyni tark etish")}
                        disabled={busy}
                        onClick={leaveCompetitionQueue}
                      >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
                      </button>
                    )}
                  </div>
                </div>

                {waitingRemaining !== null && !generationStarted ? (
                  <div className="bg-gradient-to-r from-cyan-500/10 to-indigo-500/10 dark:from-cyan-500/20 dark:to-indigo-500/20 rounded-2xl p-5 border border-cyan-500/20 dark:border-cyan-400/30 flex flex-col sm:flex-row items-center gap-5 relative overflow-hidden">
                    <div className="shrink-0 relative w-16 h-16">
                      <svg className="w-full h-full transform -rotate-90" viewBox="0 0 64 64">
                        <circle cx="32" cy="32" r="28" stroke="currentColor" strokeWidth="6" fill="none" className="text-cyan-200/50 dark:text-cyan-900/50" />
                        <circle cx="32" cy="32" r="28" stroke="currentColor" strokeWidth="6" fill="none" className="text-cyan-600 dark:text-cyan-400 transition-all duration-1000 ease-linear" strokeDasharray={175.93} strokeDashoffset={175.93 - (175.93 * Math.max(0, Math.min(waitTotalSeconds, waitingRemaining))) / waitTotalSeconds} strokeLinecap="round" />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-lg font-black text-cyan-700 dark:text-cyan-300">
                          {Math.floor(Math.max(0, waitingRemaining) / 60)}:{(Math.max(0, waitingRemaining) % 60).toString().padStart(2, '0')}
                        </span>
                      </div>
                    </div>
                    <div className="flex-grow text-center sm:text-left z-10">
                      <p className="text-sm font-black uppercase tracking-wider text-cyan-800 dark:text-cyan-200 mb-1">
                        {tt("competition.waitTime", "Kutish vaqti")}
                      </p>
                      <p className="text-sm font-medium text-navy-700 dark:text-navy-100 opacity-80">
                        {tt("competition.waitTimerHint", "Agar ishtirokchilar yig'ilmasa arena/duel yopiladi va mablag' qaytariladi.")}
                      </p>
                    </div>
                  </div>
                ) : null}

                {generationStarted && (
                  <div className="bg-indigo-50 dark:bg-indigo-500/10 rounded-2xl p-6 border border-indigo-100 dark:border-indigo-500/20 text-center relative overflow-hidden">
                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/50 to-transparent dark:via-white/10 translate-x-[-100%] animate-[shimmer_2s_infinite]" />
                    <div className="w-12 h-12 mx-auto mb-4 border-4 border-indigo-200 dark:border-indigo-800 border-t-indigo-600 dark:border-t-indigo-400 rounded-full animate-spin" />
                    <h4 className="text-base font-black text-navy-900 dark:text-white mb-3 tracking-wide">{tt("duel.generatingQuestions", "Savollar tayyorlanmoqda...")}</h4>
                    <div className="w-full h-3 bg-white dark:bg-navy-950 rounded-full overflow-hidden shadow-inner border border-line dark:border-white/5">
                      <div 
                        className="h-full bg-gradient-to-r from-indigo-500 to-cyan-400 transition-all duration-500"
                        style={{ width: `${generationPercent}%` }}
                      />
                    </div>
                    <p className="text-sm font-bold text-indigo-600 dark:text-indigo-300 mt-3">{generationPercent}%</p>
                  </div>
                )}
              </div>

              <div className="p-6 sm:p-8 relative z-10">
                <div className="mb-5" />
                {/* Leave queue button moved to header */}
                <div className={`grid grid-cols-2 ${hasDailyStages ? "sm:grid-cols-4" : "sm:grid-cols-3"} gap-4 mb-8`}>
                  {hasDailyStages && (
                    <div className="bg-surface-soft dark:bg-navy-950/60 p-5 rounded-2xl border border-line dark:border-white/5">
                      <p className="text-xs text-ink-500 dark:text-navy-300 uppercase font-bold tracking-wider mb-2">{tt("duel.stage", "Bosqich")}</p>
                      <p className="text-xl font-black text-navy-900 dark:text-white">{stage} <span className="text-ink-400 dark:text-navy-400 text-base">/ {totalStages}</span></p>
                    </div>
                  )}
                  <div className="bg-surface-soft dark:bg-navy-950/60 p-5 rounded-2xl border border-line dark:border-white/5">
                    <p className="text-xs text-ink-500 dark:text-navy-300 uppercase font-bold tracking-wider mb-2">{tt("duel.remaining", "Qoldi")}</p>
                    <p className="text-xl font-black text-navy-900 dark:text-white">{remainingPlayers}</p>
                  </div>
                  <div className="bg-surface-soft dark:bg-navy-950/60 p-5 rounded-2xl border border-line dark:border-white/5">
                    <p className="text-xs text-ink-500 dark:text-navy-300 uppercase font-bold tracking-wider mb-2">{tt("duel.active", "Aktiv")}</p>
                    <p className="text-xl font-black text-cyan-600 dark:text-cyan-400">{activeParticipantsCount}</p>
                  </div>
                  {hasDailyStages && (
                    <div className="bg-surface-soft dark:bg-navy-950/60 p-5 rounded-2xl border border-line dark:border-white/5">
                      <p className="text-xs text-ink-500 dark:text-navy-300 uppercase font-bold tracking-wider mb-2">{tt("duel.eliminated", "Chiqqan")}</p>
                      <p className="text-xl font-black text-red-600 dark:text-red-400">{eliminatedParticipantsCount}</p>
                    </div>
                  )}
                </div>

                <div className="border border-line dark:border-white/10 rounded-2xl overflow-hidden shadow-sm">
                  <div className="bg-surface-soft dark:bg-navy-950/80 px-5 py-4 border-b border-line dark:border-white/10 flex justify-between items-center">
                    <h4 className="font-bold text-sm text-navy-900 dark:text-white">
                      {mode === "daily" && status?.daily_scoreboard?.length 
                        ? tt("arena.scoreboard", "Scoreboard (Natijalar)")
                        : tt("duel.joinedStudents", "Qo'shilgan o'quvchilar")}
                    </h4>
                  </div>
                  <div className="overflow-x-auto bg-white dark:bg-navy-900">
                    {mode === "daily" && status?.daily_scoreboard?.length ? (
                      <table className="min-w-full text-left text-sm">
                        <thead className="bg-slate-50 dark:bg-navy-950/40 text-[11px] uppercase tracking-wider text-ink-500 dark:text-navy-300">
                          <tr>
                            <th className="px-5 py-3 font-black">#</th>
                            <th className="px-5 py-3 font-black">{tt("common.name", "Ism")}</th>
                            <th className="px-5 py-3 font-black text-center">{tt("duel.correct", "To'g'ri")}</th>
                            <th className="px-5 py-3 font-black text-right">{tt("common.status", "Holat")}</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-line dark:divide-white/5">
                          {status.daily_scoreboard.slice(0, 50).map((row, index) => {
                            const isEliminated = row.status === "eliminated";
                            return (
                              <tr key={`sb-${row.user_id}`} className={`hover:bg-slate-50 dark:hover:bg-navy-800/50 transition-colors ${isEliminated ? "opacity-60" : ""}`}>
                                <td className="px-5 py-3 font-black text-ink-400 dark:text-navy-400">{index + 1}</td>
                                <td className="px-5 py-3 font-bold text-navy-900 dark:text-white flex items-center gap-3">
                                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-black ${
                                    isEliminated 
                                      ? "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400" 
                                      : "bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300"
                                  }`}>
                                    {String(row.name || "U")[0].toUpperCase()}
                                  </div>
                                  <span className={isEliminated ? "line-through decoration-red-500/40" : ""}>{row.name}</span>
                                </td>
                                <td className="px-5 py-3 text-center font-black text-green-600 dark:text-green-400">
                                  {row.total_correct}
                                </td>
                                <td className="px-5 py-3 text-right">
                                  {isEliminated ? (
                                    <span className="inline-flex items-center gap-1.5 rounded-full bg-red-50 px-3 py-1 text-[11px] font-black uppercase tracking-wide text-red-700 dark:bg-red-500/10 dark:text-red-400 border border-red-100 dark:border-red-500/20">
                                      {tt("arena.eliminated", "Chiqdi")}
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-3 py-1 text-[11px] font-black uppercase tracking-wide text-green-700 dark:bg-green-500/10 dark:text-green-400 border border-green-100 dark:border-green-500/20">
                                      <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                                      {tt("duel.active", "Aktiv")}
                                    </span>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    ) : (participants || []).length ? (
                      <table className="min-w-full text-left text-sm">
                        <thead className="bg-slate-50 dark:bg-navy-950/40 text-[11px] uppercase tracking-wider text-ink-500 dark:text-navy-300">
                          <tr>
                            <th className="px-5 py-3 font-black">#</th>
                            <th className="px-5 py-3 font-black">{tt("common.name", "Ism")}</th>
                            <th className="px-5 py-3 font-black text-right">{tt("common.status", "Holat")}</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-line dark:divide-white/5">
                          {(participants || []).slice(0, 30).map((row, index) => (
                            <tr key={`p-${row.user_id}`} className="hover:bg-slate-50 dark:hover:bg-navy-800/50 transition-colors">
                              <td className="px-5 py-3 font-black text-ink-400 dark:text-navy-400">{index + 1}</td>
                              <td className="px-5 py-3 font-bold text-navy-900 dark:text-white flex items-center gap-3">
                                <div className="w-7 h-7 rounded-full bg-cyan-100 dark:bg-cyan-900 flex items-center justify-center text-cyan-700 dark:text-cyan-300 text-xs font-black">
                                  {String(row.name || "U")[0].toUpperCase()}
                                </div>
                                {row.name}
                              </td>
                              <td className="px-5 py-3 text-right">
                                <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-3 py-1 text-[11px] font-black uppercase tracking-wide text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300 border border-indigo-100 dark:border-indigo-500/20">
                                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
                                  {row.status || tt("duel.active", "Aktiv")}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    ) : (
                      <div className="p-8 text-center text-sm font-medium text-ink-500 dark:text-navy-400">
                        {tt("duel.noPlayersJoined", "Hozircha hech kim qo'shilmadi")}
                      </div>
                    )}
                  </div>
                </div>

                {mode === "daily" && (statusLive.remained?.length || statusLive.left?.length) ? (
                  <div className="mt-8 grid gap-4 md:grid-cols-2">
                    <div className="rounded-2xl border border-green-200 bg-gradient-to-br from-green-50 to-white p-5 dark:border-green-500/20 dark:from-green-500/10 dark:to-navy-950 shadow-sm relative overflow-hidden">
                      <div className="absolute -right-4 -top-4 w-24 h-24 bg-green-500/10 rounded-full blur-2xl" />
                      <h4 className="mb-4 text-xs font-black uppercase tracking-wider text-green-700 dark:text-green-400 flex items-center gap-2">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        {tt("arena.advanced", "Keyingi bosqichga o'tganlar")} <span className="text-green-500/50">•</span> {tt("duel.stage", "Bosqich")} {stage}
                      </h4>
                      <div className="flex flex-wrap gap-2 relative z-10">
                        {(statusLive.remained || []).slice(0, 24).map((name: string, idx: number) => (
                          <span key={`adv-${idx}`} className="rounded-xl border border-green-200/50 bg-white/80 px-3 py-1.5 text-xs font-bold text-green-800 dark:border-green-500/30 dark:bg-navy-900/80 dark:text-green-200 shadow-sm">
                            {name}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-red-200 bg-gradient-to-br from-red-50 to-white p-5 dark:border-red-500/20 dark:from-red-500/10 dark:to-navy-950 shadow-sm relative overflow-hidden">
                      <div className="absolute -right-4 -top-4 w-24 h-24 bg-red-500/10 rounded-full blur-2xl" />
                      <h4 className="mb-4 text-xs font-black uppercase tracking-wider text-red-700 dark:text-red-400 flex items-center gap-2">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        {tt("arena.eliminated", "Chiqarilganlar")}
                      </h4>
                      {(statusLive.left || []).length ? (
                        <div className="flex flex-wrap gap-2 relative z-10">
                          {(statusLive.left || []).slice(0, 24).map((name: string, idx: number) => (
                            <span key={`elim-${idx}`} className="rounded-xl border border-red-200/50 bg-white/80 px-3 py-1.5 text-xs font-bold text-red-800 line-through decoration-red-500/50 dark:border-red-500/30 dark:bg-navy-900/80 dark:text-red-300 opacity-75 shadow-sm">
                              {name}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm font-medium text-red-700/60 dark:text-red-400/60 relative z-10">-</p>
                      )}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          )}

          {showRuntime && (
            <div className="relative">
              <StudentTestProctoring
                active={false}
                completed={Boolean(result?.ready)}
                initialSessionId={null}
                testType={mode}
                testAttemptRef={sessionId || undefined}
                testRoute={runtimeRoute}
                onSessionReady={() => {}}
                onVerificationStateChange={() => {}}
                onTerminated={() => {}}
                className={proctoringMonitorClass()}
              />

              <div className={`competition-surface-card test-runtime-card relative bg-white dark:bg-navy-900/50 rounded-[2rem] p-4 sm:p-6 shadow-premium border border-line dark:border-white/10 ${
                theme === "red" ? "border-t-red-500" :
                theme === "blue" ? "border-t-blue-500" :
                theme === "green" ? "border-t-green-500" :
                theme === "orange" ? "border-t-orange-500" :
                "border-t-indigo-500"
              }`}>
                {/* Proctoring disabled for competition modes */}
                
                <div className="grid grid-cols-[auto_1fr_auto] items-center gap-3 sm:gap-5 mb-8">
                  <div className={`px-4 py-2 rounded-xl font-bold text-lg flex items-center gap-2 ${timeLeft > 15 ? "bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400" : timeLeft > 5 ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-500/20 dark:text-yellow-400" : "bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400 animate-pulse"}`}>
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    {timeLabel}
                  </div>
                  <div className="text-center min-w-0">
                    <h2 className="text-xl sm:text-2xl font-black text-navy-900 dark:text-white truncate">{displayTitle}</h2>
                    <p className="text-sm text-ink-500 font-bold">{tt("duel.question", "Savol")} {question?.question_index || 1} / {question?.total_questions || status?.total_questions || 0}</p>
                  </div>
                  <div className="hidden sm:flex gap-2 justify-end">
                    {hasDailyStages ? (
                      <div className="px-3 py-1.5 rounded-lg bg-transparent border border-line dark:border-white/5 text-ink-700 dark:text-navy-200 text-sm font-bold">
                        {tt("duel.stage", "Bosqich")} {stage} / {totalStages}
                      </div>
                    ) : null}
                    <div className="px-3 py-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 text-sm font-bold border border-indigo-100 dark:border-indigo-500/20">
                      {Math.max(0, Math.min(100, progressPercent))}%
                    </div>
                  </div>
                </div>

                <div className="w-full h-2 bg-transparent border border-line dark:border-white/5 rounded-full mb-10 overflow-hidden">
                  <div 
                    className="h-full bg-indigo-500 transition-all duration-500 ease-out"
                    style={{ width: `${Math.max(0, Math.min(100, progressPercent))}%` }}
                  />
                </div>

                {question?.question && !eliminatedNow && !waitingStageCompletion && !waitingForOtherParticipants ? (
                  <div className="mb-10 flex flex-col gap-6">
                    {/* Question Pills Navigator */}
                    {(question.total_questions || 1) > 1 && (
                      <div className="flex flex-wrap items-center justify-center gap-2 p-3 bg-surface-soft rounded-2xl border border-line dark:border-white/5">
                        <span className="text-xs font-bold uppercase text-ink-500 mr-2">{tt("duel.questions", "Savollar")}:</span>
                        {Array.from({ length: question.total_questions || 1 }).map((_, idx) => {
                          const qNum = idx + 1;
                          const isCurrent = qNum === (question.question_index || 1);
                          return (
                            <button
                              key={qNum}
                              type="button"
                              className={`w-9 h-9 rounded-xl font-black text-sm flex items-center justify-center transition-all ${
                                isCurrent
                                  ? "bg-indigo-600 text-white shadow-md scale-105 ring-2 ring-indigo-500/40"
                                  : "bg-white dark:bg-navy-900 border border-line dark:border-white/10 text-ink-700 dark:text-navy-200 hover:bg-indigo-50 dark:hover:bg-navy-800"
                              }`}
                              disabled={busy || timeLeft <= 0}
                              onClick={() => {
                                if (qNum !== question.question_index) {
                                  submitAnswer(null);
                                }
                              }}
                            >
                              {qNum}
                            </button>
                          );
                        })}
                      </div>
                    )}

                    <StudentQuestionRenderer
                      question={question.question}
                      disabled={busy || timeLeft <= 0 || !proctoringReady || eliminatedNow || waitingStageCompletion || waitingForOtherParticipants}
                      onSubmit={submitAnswer}
                    />

                    {/* Navigation Controls: Previous / Next / Submit */}
                    <div className="flex items-center justify-between gap-3 pt-4 border-t border-line dark:border-white/10">
                      <button
                        type="button"
                        className="btn btn-secondary flex items-center gap-2 text-sm font-bold disabled:opacity-40"
                        disabled={busy || (question.question_index || 1) <= 1}
                        onClick={() => submitAnswer(null)}
                      >
                        ⬅️ {tt("common.previous", "Oldingi")}
                      </button>

                      {(question.question_index || 1) < (question.total_questions || 1) ? (
                        <button
                          type="button"
                          className="btn btn-primary flex items-center gap-2 text-sm font-bold"
                          disabled={busy || timeLeft <= 0}
                          onClick={() => submitAnswer(null)}
                        >
                          {tt("common.next", "Keyingi")} ➡️
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="btn btn-primary bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white shadow-lg flex items-center gap-2 text-sm font-bold"
                          disabled={busy || timeLeft <= 0}
                          onClick={() => submitAnswer(null)}
                        >
                          🚀 {tt("competition.finishTest", "Testni Tugatish")}
                        </button>
                      )}
                    </div>
                  </div>
                ) : hasDailyStages && eliminatedNow ? (
                  <div className="text-center py-12">
                    <div className="w-20 h-20 mx-auto bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400 rounded-full flex items-center justify-center mb-6">
                      <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                    </div>
                    <h3 className="text-2xl font-bold text-navy-900 dark:text-white mb-2">{tt("duel.stageLost", "Siz ushbu bosqichda yutqazdingiz")}</h3>
                    <p className="text-ink-500">{tt("duel.finalWaiting", "Final natijalar kutilmoqda.")}</p>
                  </div>
                ) : hasDailyStages && waitingStageCompletion ? (
                  <div className="text-center py-12">
                    <div className="w-20 h-20 mx-auto bg-blue-100 dark:bg-cyan-500/20 text-cyan-600 dark:text-cyan-400 rounded-full flex items-center justify-center mb-6">
                      <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                    <h3 className="text-2xl font-bold text-navy-900 dark:text-white mb-2">{tt("duel.stageFinished", "Bosqich yakunlandi")}</h3>
                    <p className="text-ink-500">{tt("duel.nextStageGenerating", "Keyingi bosqich savollari tayyorlanmoqda.")}</p>
                  </div>
                ) : waitingForOtherParticipants ? (
                  <div className="text-center py-10 max-w-lg mx-auto">
                    <div className="w-16 h-16 mx-auto bg-indigo-100 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 rounded-2xl flex items-center justify-center mb-5 border border-indigo-200 dark:border-indigo-500/30">
                      <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent dark:border-indigo-400 dark:border-t-transparent rounded-full animate-spin" />
                    </div>
                    <h3 className="text-2xl font-black text-navy-900 dark:text-white mb-2">{tt("competition.answersSent", "Javoblaringiz yuborildi!")}</h3>
                    <p className="text-sm font-medium text-ink-500 mb-6">{tt("competition.waitingOthers", "Raqibingiz testni yakunlagach, g'olib va natijalar aniqlanadi.")}</p>

                    {/* LIVE OPPONENT PROGRESS CARDS */}
                    {Array.isArray((question as any)?.opponent_progress || (status as any)?.opponent_progress) && ((question as any)?.opponent_progress || (status as any)?.opponent_progress).length > 0 && (
                      <div className="flex flex-col gap-3 text-left bg-surface-soft p-4 rounded-2xl border border-line dark:border-white/5">
                        <h4 className="text-xs font-bold uppercase tracking-wider text-ink-500 mb-1">👥 Raqiblar Holati:</h4>
                        {((question as any)?.opponent_progress || (status as any)?.opponent_progress).map((opp: any) => {
                          const oppTotal = Number(opp.total_questions || question?.total_questions || status?.total_questions || 5);
                          const oppCompleted = Number(opp.completed_count || 0);
                          const pct = Math.round((oppCompleted / Math.max(1, oppTotal)) * 100);
                          return (
                            <div key={opp.user_id} className="p-3 rounded-xl border border-line bg-white dark:bg-navy-900 flex flex-col gap-2 shadow-sm">
                              <div className="flex items-center justify-between text-xs font-bold">
                                <span className="text-navy-900 dark:text-white flex items-center gap-1.5">
                                  <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
                                  {opp.name}
                                </span>
                                <span className={opp.is_finished ? "text-green-600 dark:text-green-400" : "text-indigo-600 dark:text-indigo-400"}>
                                  {opp.is_finished ? "✅ Yakunladi" : `${oppCompleted} / ${oppTotal} ta bajarildi (${pct}%)`}
                                </span>
                              </div>
                              <div className="w-full h-2 bg-slate-100 dark:bg-navy-950 rounded-full overflow-hidden">
                                <div 
                                  className={`h-full transition-all duration-500 ${opp.is_finished ? "bg-green-500" : "bg-gradient-to-r from-cyan-500 to-indigo-500"}`}
                                  style={{ width: `${pct}%` }}
                                />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>

                ) : (
                  <div className="text-center py-12">
                    <div className="w-8 h-8 border-4 border-slate-300 border-t-slate-800 dark:border-white/10 dark:border-t-white rounded-full animate-spin mx-auto mb-4" />
                    <p className="text-ink-500 font-medium">{tt("duel.waitingQuestion", "Savol kutilmoqda...")}</p>
                  </div>
                )}
	              </div>
	            </div>
	          )}

          {result?.ready && (
            <div className="competition-surface-card test-result-card bg-white dark:bg-navy-950/90 rounded-[2rem] p-4 sm:p-6 shadow-premium border border-line dark:border-white/10 text-center relative overflow-hidden">
              <div className={`absolute top-0 left-0 right-0 h-40 bg-gradient-to-b ${isRefunded ? "from-cyan-500/20" : isTie ? "from-slate-500/20" : isWinner ? "from-yellow-500/20" : "from-slate-500/10"} to-transparent`} />
              
              <div className="relative">
                <div className={`w-28 h-28 mx-auto rounded-full flex items-center justify-center mb-6 shadow-xl border-4 ${isProctoringStopped(result) ? "bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400 border-red-200 dark:border-red-500/30" : isRefunded ? "bg-cyan-100 dark:bg-cyan-500/20 text-cyan-700 dark:text-cyan-200 border-cyan-200 dark:border-cyan-500/30" : isTie ? "bg-slate-100 dark:bg-white/10 text-slate-700 dark:text-slate-100 border-slate-200 dark:border-white/20" : isWinner ? "bg-yellow-100 dark:bg-yellow-500/20 text-yellow-600 dark:text-yellow-400 border-yellow-200 dark:border-yellow-500/30" : "bg-transparent border border-line dark:border-white/5 text-ink-500 dark:text-navy-300 border-line dark:border-white/10"}`}>
                  <span className="text-5xl">{isProctoringStopped(result) ? "!" : isRefunded ? "↩" : isTie ? "=" : isWinner ? "👑" : "💪"}</span>
                </div>
                
                <h3 className="text-3xl sm:text-4xl font-bold text-navy-900 dark:text-white mb-4">
                  {isProctoringStopped(result) ? tt("duel.proctorStoppedTitle", "Test proctoring sabab to'xtatildi") : isRefunded ? tt("duel.refunded", "Qaytarildi") : isTie ? tt("duel.tie", "Durang") : isWinner ? tt("duel.champion", "G'alaba") : tt("duel.keepPushing", "Yana urinib ko'ring")}
                </h3>
                <p className="text-ink-500 dark:text-navy-300 text-lg max-w-md mx-auto mb-10">
                  {isProctoringStopped(result) ? tt("duel.proctorStoppedDesc", "Test xavfsizlik tekshiruvi sabab yakunlandi.") : isRefunded ? tt("duel.refundMessage", "Duel boshlanmadi va kirish narxi qaytarildi.") : isTie ? tt("duel.tieMessage", "Natija teng. G'olib belgilanmadi.") : isWinner ? tt("duel.championMsg", "Bu raundda g'olib bo'ldingiz.") : tt("duel.loseMsg", "Yaqin qoldingiz. Yana bir duel boshlang.")}
                </p>
                {isProctoringStopped(result) ? (
                  <div className="mb-8 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-bold text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200">
                    {tt("duel.reason", "Sabab")}: {result.proctoring_failure_message || proctoringFriendlyError(String(result.proctoring_failure_reason || ""))}
                  </div>
                ) : null}
                
                {mode === "daily" && Array.isArray(result.podium) && result.podium.length > 0 && (
                  <div className="bg-transparent rounded-2xl p-6 border border-line dark:border-white/10 mb-10">
                    <h4 className="text-sm font-bold text-ink-500 uppercase tracking-wider mb-4">{tt("arena.podium", "Podium")}</h4>
                    <div className="flex flex-wrap justify-center gap-3">
                      {result.podium.map((row: GenericRow, i: number) => (
                        <div key={i} className={`flex items-center gap-2 px-4 py-2 rounded-xl font-bold ${row.rank === 1 ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-500/20 dark:text-yellow-400" : row.rank === 2 ? "bg-line text-ink-700 dark:bg-navy-800 dark:text-slate-300" : row.rank === 3 ? "bg-orange-100 text-orange-700 dark:bg-orange-500/20 dark:text-orange-400" : "bg-white text-ink-600 border border-line"}`}>
                          <span>#{row.rank}</span>
                          <span className="currency-inline text-sm">
                            <AssetIcon type="dpoint" size={18} />
                            +{row.dpoints_delta} D'Points
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {mode === "boss" && bossSummary && Object.keys(bossSummary).length > 0 ? (
                  <div className="mb-10 rounded-2xl border border-line bg-surface-soft p-5 text-left dark:border-white/10 dark:bg-navy-950/60">
                    <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                      <h4 className="text-sm font-black uppercase tracking-wider text-ink-600 dark:text-navy-200">
                        {tt("arena.bossRewardDetails", "Boss Arena reward details")}
                      </h4>
                      <span className={`rounded-full px-3 py-1 text-xs font-black ${bossSummary.passed ? "bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-200" : "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-200"}`}>
                        {bossSummary.passed ? tt("arena.rewardPassed", "Reward active") : tt("arena.rewardNotPassed", "Reward inactive")}
                      </span>
                    </div>
                    <p className="mb-4 text-sm font-semibold text-ink-600 dark:text-navy-300">
                      {tt("arena.bossRewardRuleDynamic", "Agar umumiy to'g'ri javoblar {threshold}% yoki undan yuqori bo'lsa, har bir to'g'ri javob uchun {perCorrect} D'point beriladi.", {
                        threshold: Number(bossSummary.threshold_percent ?? 86).toFixed(Number(bossSummary.threshold_percent ?? 86) % 1 ? 1 : 0),
                        perCorrect: Number(bossSummary.reward_per_correct ?? 3).toFixed(Number(bossSummary.reward_per_correct ?? 3) % 1 ? 1 : 0),
                      })}
                    </p>
                    <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                      <div className="rounded-xl border border-line bg-white p-3 dark:border-white/10 dark:bg-navy-900/70">
                        <p className="text-xs font-bold text-ink-500">{tt("arena.totalParticipants", "Participants")}</p>
                        <p className="text-xl font-black text-navy-900 dark:text-white">{bossSummary.participant_count || 0}</p>
                      </div>
                      <div className="rounded-xl border border-line bg-white p-3 dark:border-white/10 dark:bg-navy-900/70">
                        <p className="text-xs font-bold text-ink-500">{tt("arena.totalCorrect", "Total correct")}</p>
                        <p className="text-xl font-black text-green-600 dark:text-green-300">{bossSummary.total_correct || 0}</p>
                      </div>
                      <div className="rounded-xl border border-line bg-white p-3 dark:border-white/10 dark:bg-navy-900/70">
                        <p className="text-xs font-bold text-ink-500">{tt("arena.totalPossible", "Total possible")}</p>
                        <p className="text-xl font-black text-navy-900 dark:text-white">{bossSummary.total_possible || 0}</p>
                      </div>
                      <div className="rounded-xl border border-line bg-white p-3 dark:border-white/10 dark:bg-navy-900/70">
                        <p className="text-xs font-bold text-ink-500">{tt("arena.bossGlobalRate", "Global rate")}</p>
                        <p className="text-xl font-black text-cyan-600 dark:text-cyan-300">{Number(bossSummary.global_accuracy || 0).toFixed(1)}%</p>
                      </div>
                    </div>
                    {bossParticipants.length ? (
                      <div className="grid gap-2">
                        {bossParticipants.map((row, idx) => (
                          <div key={`boss-reward-${row.user_id || idx}`} className="grid grid-cols-[1fr_auto] items-center gap-3 rounded-xl border border-line bg-white px-3 py-2 dark:border-white/10 dark:bg-navy-900/70">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-black text-navy-900 dark:text-white">{row.name || `#${row.user_id}`}</p>
                              <p className="text-xs font-semibold text-ink-500 dark:text-navy-300">{tt("duel.correct", "To'g'ri")}: {row.correct || 0} / {row.total_questions || 0}</p>
                            </div>
                            <span className="currency-inline text-sm font-black text-cyan-600 dark:text-cyan-300">
                              <AssetIcon type="dpoint" size={18} />
                              +{Number(row.dpoints_delta || 0).toFixed(1)}
                            </span>
                          </div>
                        ))}
                      </div>
	                    ) : null}
	                  </div>
	                ) : null}

	                {resultParticipants.length ? (
	                  <div className="mb-10 rounded-2xl border border-line bg-surface-soft p-4 text-left dark:border-white/10 dark:bg-navy-950/60">
	                    <h4 className="mb-3 text-sm font-black uppercase tracking-wider text-ink-600 dark:text-navy-200">
	                      {tt("duel.finalStandings", "Yakuniy natija")}
	                    </h4>
	                    <div className="grid gap-2">
	                      {resultParticipants.map((row, index) => {
	                        const rank = Number(row.rank || index + 1);
	                        const rowWinner = Boolean(row.winner);
	                        const rowLeft = Boolean(row.left) || ["left", "cancelled", "blocked", "failed", "eliminated"].includes(String(row.status || "").toLowerCase());
	                        const rankSticker =
	                          rank === 1 ? "🥇" :
	                          rank === 2 ? "🥈" :
	                          rank === 3 ? "🥉" :
	                          `${rank}`;
	                        const isTopThree = rank <= 3;
	                        const rowBg =
	                          rank === 1 ? "bg-yellow-50 dark:bg-yellow-500/10 border-yellow-200 dark:border-yellow-500/20" :
	                          rank === 2 ? "bg-slate-50 dark:bg-white/5 border-line dark:border-white/10" :
	                          rank === 3 ? "bg-orange-50 dark:bg-orange-500/10 border-orange-200 dark:border-orange-500/20" :
	                          "bg-white dark:bg-navy-900/40 border-line dark:border-white/5";
	                        return (
	                          <div key={`result-participant-${row.user_id || index}`}
	                            className={`flex items-center gap-2 sm:gap-3 rounded-2xl border p-2.5 sm:p-3 transition-all ${rowBg}`}>
	                            {/* Rank sticker */}
	                            <div className={`shrink-0 w-8 h-8 sm:w-11 sm:h-11 flex items-center justify-center rounded-xl font-black text-lg sm:text-xl
	                              ${isTopThree ? "text-xl sm:text-2xl" :
	                                "bg-line/60 dark:bg-white/10 text-ink-600 dark:text-navy-200 text-xs sm:text-sm"}`}>
	                              {rankSticker}
	                            </div>
	                            {/* Avatar */}
	                            <div className="hidden xs:flex shrink-0 w-8 h-8 rounded-full bg-cyan-100 dark:bg-cyan-900/50 flex items-center justify-center text-cyan-700 dark:text-cyan-300 text-xs font-black">
	                              {String(row.name || "U")[0].toUpperCase()}
	                            </div>
	                            {/* Name + correct count */}
	                            <div className="flex-1 min-w-0">
	                              <p className="font-black text-xs sm:text-sm text-navy-900 dark:text-white truncate">{row.name || `#${row.user_id}`}</p>
	                              <p className="text-[10px] sm:text-xs text-ink-500 dark:text-navy-300 font-semibold">
	                                ✅ {Number(row.correct || 0)} &nbsp; ❌ {Number(row.wrong || 0)}
	                              </p>
	                            </div>
	                            {/* Status sticker */}
	                            <span className={`shrink-0 rounded-full px-2 py-0.5 sm:px-3 sm:py-1 text-[10px] sm:text-xs font-black flex items-center gap-1
	                              ${rowWinner
	                                ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-500/20 dark:text-yellow-200"
	                                : rowLeft
	                                ? "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-200"
	                                : "bg-slate-100 text-slate-700 dark:bg-white/10 dark:text-slate-100"}`}>
	                              {rowWinner ? "🏆" : rowLeft ? "🚪" : "✓"}
	                              <span className="hidden sm:inline">
	                                &nbsp;{rowWinner ? tt("duel.winner", "G'olib") : rowLeft ? tt("duel.left", "Chiqqan") : tt("duel.finished", "Yakunladi")}
	                              </span>
	                            </span>
	                            {/* D'Points */}
	                            <span className="shrink-0 text-xs sm:text-sm font-black text-cyan-600 dark:text-cyan-300">
	                              {Number(row.dpoints_delta || 0) >= 0 ? "+" : ""}{Number(row.dpoints_delta || 0).toFixed(1)}
	                            </span>
	                          </div>
	                        );
	                      })}
	                    </div>
	                  </div>
	                ) : null}
	                
	                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-10">
                  <div className="bg-transparent p-4 rounded-2xl border border-line dark:border-white/10">
                    <p className="text-sm font-medium text-ink-500 mb-1">{tt("duel.correct", "To'g'ri")}</p>
                    <p className="text-2xl font-bold text-green-600 dark:text-green-400">{result.result?.correct || 0}</p>
                  </div>
                  <div className="bg-transparent p-4 rounded-2xl border border-line dark:border-white/10">
                    <p className="text-sm font-medium text-ink-500 mb-1">{tt("duel.wrong", "Xato")}</p>
                    <p className="text-2xl font-bold text-red-600 dark:text-red-400">{result.result?.wrong || 0}</p>
                  </div>
                  <div className="bg-transparent p-4 rounded-2xl border border-line dark:border-white/10">
                    <p className="text-sm font-medium text-ink-500 mb-1">{tt("duel.skipped", "O'tkazildi")}</p>
                    <p className="text-2xl font-bold text-ink-600 dark:text-navy-300">{result.result?.unanswered || 0}</p>
                  </div>
                  <div className="bg-transparent p-4 rounded-2xl border border-blue-100 dark:border-blue-500/20">
                    <p className="currency-inline text-sm font-medium text-ink-500 mb-1">
                      <AssetIcon type="dpoint" size={18} />
                      {tt("duel.dpoints", "D'Points")}
                    </p>
                    <p className="text-2xl font-bold text-cyan-600 dark:text-cyan-400">{Number(result.result?.dpoints_delta || 0) >= 0 ? "+" : ""}{Number(result.result?.dpoints_delta || 0).toFixed(1)}</p>
                  </div>
                </div>
                
                <div className="flex flex-wrap justify-center gap-4">
                  <button
                    className="bg-navy-900 hover:bg-navy-800 text-white dark:bg-cyan-500 dark:hover:bg-cyan-600 px-8 py-4 rounded-2xl font-bold text-lg shadow-lg shadow-indigo-500/30 transition-all hover:-translate-y-1"
                    onClick={() => {
                      setResult(null);
                      setStatus(null);
                      setQuestion(null);
                      setSessionId("");
                    }}
                  >
                    {tt("duel.playAgain", "Qayta o'ynash")}
                  </button>
                  <button
                    className="bg-surface-soft hover:bg-line dark:bg-white/10 dark:hover:bg-navy-800 text-ink-700 dark:text-navy-200 px-8 py-4 rounded-2xl font-bold text-lg transition-colors"
                    onClick={() => onNavigate(mode.startsWith("duel") ? "duel" : "arena")}
                  >
                    {tt("common.back", "Orqaga")}
                  </button>
                  <button 
                    className="bg-surface-soft hover:bg-line dark:bg-white/10 dark:hover:bg-navy-800 text-ink-700 dark:text-navy-200 px-8 py-4 rounded-2xl font-bold text-lg transition-colors"
                    onClick={() => onNavigate("leaderboard")}
                  >
                    {tt("duel.ranking", "Reyting")}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function StudentCompetitionRuntimePage({ mode }: { mode: CompetitionMode }) {
  return (
    <StudentStandaloneTestShell fullscreen>
      {({ data, onNavigate }) => <StudentCompetitionPage data={data} mode={mode} onNavigate={onNavigate} viewMode="runtime" />}
    </StudentStandaloneTestShell>
  );
}
