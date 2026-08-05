"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useParams, usePathname, useSearchParams, useRouter } from "next/navigation";
import { StudentTestProctoring, useStudentProctoringStatus } from "../../proctoring";
import { AssetIcon } from "../../../ui/primitives";
import { resolveLocale, t as translateWeb } from "../../../ui/web-i18n";

type GenericRow = Record<string, any>;

type StudentGrammarTopicDetailPayload = {
  subject: string;
  level: string;
  topic_id: string;
  title: string;
  rule: string;
  question_count: number;
  attempts_allowed: number;
  attempts_used: number;
  attempts_left: number;
  can_start_test: boolean;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

function grammarFriendlyErrorMessage(input: string, tt?: (key: string, fallback: string) => string) {
  const t = tt || ((k: string, fb: string) => fb);
  const message = sanitizeServerText(input);
  const lowered = message.toLowerCase();
  if (!message) return t("common.error.generic", "So'rov bajarilmadi.");
  if (lowered.includes("topic_id is required")) return t("student.grammar.error.topicRequired", "Mavzu ID yuborilmadi.");
  if (lowered.includes("grammar topic not found")) return t("student.grammar.error.topicNotFound", "Grammar mavzusi topilmadi.");
  if (lowered.includes("attempt limit")) return t("student.grammar.error.attemptLimit", "Urinishlar limiti tugagan.");
  if (lowered.includes("temporarily unavailable")) return t("student.grammar.error.temporarilyUnavailable", "Mavzu hozircha vaqtincha ishlamayapti. Birozdan so'ng qayta urinib ko'ring.");
  if (lowered.includes("no grammar questions")) return t("student.grammar.error.noQuestions", "Bu mavzu uchun test savollari hozircha tayyor emas.");
  if (lowered.includes("face enrollment is required before starting tests")) {
    return t("proctoring.error.enrollmentRequired", "Testni boshlash uchun avval Face ID enrollmentni yakunlang.");
  }
  if (lowered.includes("proctoring access is temporarily blocked")) {
    return t("proctoring.error.temporarilyBlocked", "Proctoring vaqtincha bloklangan. Birozdan keyin qayta urinib ko'ring.");
  }
  if (lowered.includes("face profile is disabled")) {
    return t("proctoring.error.profileDisabled", "Face profile o'chirilgan. Admin bilan bog'laning yoki profilni qayta aktiv qiling.");
  }
  if (lowered.includes("insightface_provider_required") || lowered.includes("engine_error")) {
    return t("proctoring.error.engineError", "Server FaceID modeli tayyor emas. Iltimos birozdan keyin qayta urinib ko'ring yoki supportga xabar bering.");
  }
  if (lowered.includes("profile_embedding_missing") || lowered.includes("embedding_missing") || lowered.includes("requires re-enrollment")) {
    return t("proctoring.error.reEnrollmentRequired", "FaceID profilingizni qayta sozlash kerak. Profil sahifasidan FaceID setup qiling.");
  }
  if (lowered.includes("face_mismatch") || lowered.includes("face_not_verified")) {
    return t("proctoring.error.faceMismatch", "Yuz mos kelmadi. FaceID tekshiruvi muvaffaqiyatsiz.");
  }
  if (lowered.includes("no_face") || lowered.includes("face_missing")) {
    return t("proctoring.error.noFace", "Yuz kamerada aniqlanmadi. Test to'xtatildi.");
  }
  if (lowered.includes("multiple_faces")) {
    return t("proctoring.error.multipleFaces", "Kamerada bir nechta yuz aniqlandi. Test to'xtatildi.");
  }
  if (lowered.includes("internal server error")) {
    return t("common.error.serverError", "Serverda vaqtinchalik xatolik yuz berdi. Iltimos, qayta urinib ko'ring.");
  }
  if (lowered.includes("request timed out") || lowered.includes("so'rov vaqti") || lowered.includes("so‘rov vaqti")) return t("common.error.timeout", "So'rov vaqti tugadi. Qayta urinib ko'ring.");
  if (lowered.includes("network error") || lowered.includes("tarmoq")) return t("common.error.network", "Tarmoq so'rovi bajarilmadi. Qayta urinib ko'ring.");
  return t("student.grammar.error.loadFailed", "Mavzu ma'lumotini yuklab bo'lmadi. Iltimos, qayta urinib ko'ring.");
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

function proctoringStoppedPayload(previous: GenericRow | null | undefined, reason: unknown, tt?: (key: string, fallback: string) => string): GenericRow {
  const rawReason = proctoringStopReason(reason) || String(reason || "proctoring_failed");
  const base: GenericRow = previous && typeof previous === "object" ? (previous as GenericRow) : {};
  const total = Number(base.total_questions || base.question_count || 0);
  const correct = Number(base.correct || 0);
  const wrong = Number(base.wrong || 0);
  const skipped = Number(base.skipped ?? Math.max(0, total - correct - wrong));
  return {
    ...base,
    completed: true,
    question: undefined,
    proctoring_stopped: true,
    proctoring_failure_reason: rawReason,
    proctoring_failure_message: grammarFriendlyErrorMessage(rawReason, tt),
    correct,
    wrong,
    skipped,
    dpoints: Number(base.dpoints || 0),
  };
}

function isProctoringStopped(row: GenericRow | null | undefined) {
  return Boolean(row?.proctoring_stopped || row?.proctoring_failure_reason);
}

function proctoringMonitorClass() {
  return "test-proctoring-monitor";
}

function sanitizeServerText(input: unknown) {
  const raw = String(input ?? "").trim();
  if (!raw) return "";
  const withoutHtml = raw
    .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?>[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!withoutHtml) return "";
  if (/traceback|exception|stack| at /i.test(withoutHtml)) {
    return "Serverda xatolik yuz berdi";
  }
  return withoutHtml.slice(0, 320);
}

function cleanGrammarDisplayText(input: unknown) {
  return String(input ?? "")
    .replace(/\\r\\n/g, "\n")
    .replace(/\\n/g, "\n")
    .replace(/\\r/g, "\n")
    .replace(/\\t/g, " ")
    .trim();
}

function normalizeTopicPayload(payload: StudentGrammarTopicDetailPayload): StudentGrammarTopicDetailPayload {
  return {
    ...payload,
    title: sanitizeServerText(payload.title || "Grammar") || "Grammar",
    rule: cleanGrammarDisplayText(payload.rule),
  };
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

async function requestJson<T>(path: string, options?: { method?: "GET" | "POST"; body?: unknown; token?: string | null }): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 12000);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options?.method || "GET",
      signal: controller.signal,
      headers: {
        ...(options?.token ? { Authorization: `Bearer ${options.token}` } : {}),
        ...(options?.body ? { "Content-Type": "application/json" } : {}),
      },
      ...(options?.body ? { body: JSON.stringify(options.body) } : {}),
    });
  } catch (error) {
    throw normalizeNetworkError(error);
  } finally {
    window.clearTimeout(timeout);
  }
  if (!response.ok) {
    if (response.status === 401 && options?.token) {
      localStorage.removeItem("diamond_token");
    }
    const text = await response.text().catch(() => "");
    if (text) {
      let detail = text;
      try {
        const parsed = JSON.parse(text) as { detail?: unknown; message?: string; error?: string };
        if (typeof parsed.detail === "string") {
          detail = parsed.detail;
        } else if (parsed.detail && typeof parsed.detail === "object") {
          detail = String(
            (parsed.detail as { message?: unknown; detail?: unknown; code?: unknown }).message ||
            (parsed.detail as { message?: unknown; detail?: unknown; code?: unknown }).detail ||
            ((parsed.detail as { code?: unknown }).code === "face_enrollment_required"
              ? "FaceID setup kerak. Profil sahifasidan FaceID setup qiling."
              : ""),
          );
        } else {
          detail = String(parsed.message || parsed.error || text || "Request failed");
        }
      } catch {
        detail = text;
      }
      throw new Error(detail);
    }
    throw new Error("Request failed");
  }
  return response.json();
}

function StudentGrammarTopicContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const routeParams = useParams<{ topicId?: string }>();
  const [topic, setTopic] = useState<StudentGrammarTopicDetailPayload | null>(null);
  const [quizSession, setQuizSession] = useState<GenericRow | null>(null);
  const [quizResult, setQuizResult] = useState<GenericRow | null>(null);
  const [quizSelectedIndex, setQuizSelectedIndex] = useState<{ key: string; index: number | null }>({ key: "", index: null });
  const [reviewOpen, setReviewOpen] = useState(false);
  const [crossedOptions, setCrossedOptions] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [timeLeft, setTimeLeft] = useState(30);
  const [proctoringSessionId, setProctoringSessionId] = useState<number | null>(null);
  const [proctoringReady, setProctoringReady] = useState(true);
  const autoStartRef = useRef(false);
  const answerInFlightRef = useRef(false);
  const longPressTimerRef = useRef<number | null>(null);
  const longPressTriggeredRef = useRef(false);
  const activeLongPressKeyRef = useRef("");
  const { loading: proctoringLoading } = useStudentProctoringStatus(true);
  const locale = useMemo(() => resolveLocale(typeof window === "undefined" ? "uz" : localStorage.getItem("diamond_locale")), []);
  const tt = (key: string, fallback: string) => translateWeb(locale, key, fallback);

  const subject = useMemo(() => (searchParams.get("subject") || "English").trim(), [searchParams]);
  const level = useMemo(() => (searchParams.get("level") || "A1").trim().toUpperCase(), [searchParams]);
  const topicTitleHint = useMemo(() => (searchParams.get("title") || "").trim(), [searchParams]);
  const questionCountHint = useMemo(() => Math.max(0, Number(searchParams.get("question_count") || 0)), [searchParams]);
  const topicId = useMemo(() => {
    const fromPath = String(routeParams?.topicId || "").trim();
    if (fromPath) return decodeURIComponent(fromPath);
    return (searchParams.get("topic_id") || "").trim();
  }, [routeParams, searchParams]);
  const isRuntimePage = pathname.includes("/run");
  const isRussianGrammarTopic = String(topic?.subject || subject || "").trim().toLowerCase() === "russian";

  function clearLongPressTimer() {
    if (longPressTimerRef.current !== null) {
      window.clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
    activeLongPressKeyRef.current = "";
  }

  function toggleCrossedOption(key: string) {
    setCrossedOptions((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function startLongPress(key: string) {
    if (busy || timeLeft <= 0 || !proctoringReady) return;
    clearLongPressTimer();
    longPressTriggeredRef.current = false;
    activeLongPressKeyRef.current = key;
    longPressTimerRef.current = window.setTimeout(() => {
      if (activeLongPressKeyRef.current !== key) return;
      longPressTriggeredRef.current = true;
      toggleCrossedOption(key);
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
  const autoStart = searchParams.get("autostart") === "1";

  useEffect(() => {
    if (!isRuntimePage) return;
    document.body.classList.add("proctoring-test-mode");
    return () => {
      document.body.classList.remove("proctoring-test-mode");
    };
  }, [isRuntimePage]);

  function backToList() {
    router.back();
  }

  useEffect(() => {
    const webApp = (window as any)?.Telegram?.WebApp;
    if (!webApp?.BackButton) return;
    const onBack = () => backToList();
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
  }, [subject, level]);

  async function loadTopic() {
    const token = localStorage.getItem("diamond_token");
    if (!token) {
      router.push("/login");
      return;
    }
    if (!topicId) {
      setError("Mavzu ID topilmadi.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const payload = await requestJson<StudentGrammarTopicDetailPayload>(
        `/student/grammar/topic?subject=${encodeURIComponent(subject)}&level=${encodeURIComponent(level)}&topic_id=${encodeURIComponent(topicId)}`,
        { token },
      );
      setTopic(normalizeTopicPayload(payload));
    } catch (err) {
      const message = sanitizeServerText(err instanceof Error ? err.message : "Grammar mavzusini yuklab bo'lmadi");
      if (isAuthErrorMessage(message)) {
        router.push("/login");
        return;
      }
      setError(grammarFriendlyErrorMessage(message, tt));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTopic();
  }, [subject, level, topicId, isRuntimePage]); // eslint-disable-line react-hooks/exhaustive-deps

  function openRuntimePage() {
    const params = new URLSearchParams();
    params.set("subject", topic?.subject || subject);
    params.set("level", topic?.level || level);
    params.set("topic_id", topic?.topic_id || topicId);
    params.set("title", topic?.title || topicTitleHint || "");
    params.set("question_count", String(topic?.question_count || questionCountHint || 0));
    params.set("autostart", "1");
    router.push(`/student/grammar/${encodeURIComponent(topic?.topic_id || topicId)}/run?${params.toString()}`);
  }

  async function startTopicQuiz() {
    if (!topic) return;
    const token = localStorage.getItem("diamond_token");
    if (!token) {
      router.push("/login");
      return;
    }
    setBusy(true);
    setError("");
    setQuizSelectedIndex({ key: "", index: null });
    setCrossedOptions(new Set());
    longPressTriggeredRef.current = false;
    clearLongPressTimer();
    setQuizResult(null);
    setProctoringReady(false);
    try {
      const payload = await requestJson<GenericRow>("/student/grammar/quiz/start", {
        method: "POST",
        token,
        body: {
          subject: topic.subject,
          level: topic.level,
          topic_id: topic.topic_id,
        },
      });
      setQuizSession(payload);
      setTimeLeft(30);
      const nextProctoringId = Number(payload.proctoring_session_id || 0) || null;
      const requiresProctoring = Boolean(payload.proctoring_required);
      setProctoringSessionId(nextProctoringId);
      setProctoringReady(!requiresProctoring);
      setTopic((prev) =>
        prev
          ? {
              ...prev,
              attempts_allowed: Number(payload.attempts_allowed ?? prev.attempts_allowed),
              attempts_used: Number(payload.attempts_used ?? prev.attempts_used),
              attempts_left: Number(payload.attempts_left ?? prev.attempts_left),
              can_start_test: Number(payload.attempts_left ?? prev.attempts_left) > 0,
            }
          : prev,
      );
    } catch (err) {
      setQuizSession(null);
      const message = err instanceof Error ? err.message : "Grammar testi boshlanmadi";
      setError(grammarFriendlyErrorMessage(message, tt));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!isRuntimePage || !autoStart || autoStartRef.current) return;
    if (loading || busy || quizSession || quizResult || !topic?.can_start_test) return;
    autoStartRef.current = true;
    startTopicQuiz().catch(() => {
      autoStartRef.current = false;
    });
  }, [isRuntimePage, autoStart, loading, busy, quizSession, quizResult, topic?.topic_id, topic?.can_start_test]); // eslint-disable-line react-hooks/exhaustive-deps

  async function submitQuizAnswer(skip = false, selectedIndex?: number) {
    const token = localStorage.getItem("diamond_token");
    if (!token || !quizSession?.session_id) return;
    if (isRuntimePage && (proctoringSessionId || quizSession?.proctoring_required) && !proctoringReady) return;
    const currentQuestionKey = [
      quizSession.session_id || "",
      quizSession.question_index || "",
      quizSession.question?.prompt || "",
      (quizSession.question?.options || []).join("|"),
    ].join("|");
    const selectedForCurrentQuestion = quizSelectedIndex.key === currentQuestionKey ? quizSelectedIndex.index : null;
    const answerIndex = typeof selectedIndex === "number" ? selectedIndex : selectedForCurrentQuestion;
    if (!skip && answerIndex === null) return;
    if (answerInFlightRef.current) return;
    answerInFlightRef.current = true;
    setBusy(true);
    setError("");
    try {
      const payload = await requestJson<GenericRow>("/student/grammar/quiz/answer", {
        method: "POST",
        token,
        body: {
          session_id: quizSession.session_id,
          selected_option_index: skip ? null : answerIndex,
          proctoring_session_id: proctoringSessionId,
        },
      });
      if (payload.completed) {
        setQuizSession(null);
        setQuizResult(payload);
        setTopic((prev) =>
          prev
            ? {
                ...prev,
                attempts_allowed: Number(payload.attempts_allowed ?? prev.attempts_allowed),
                attempts_used: Number(payload.attempts_used ?? prev.attempts_used),
                attempts_left: Number(payload.attempts_left ?? prev.attempts_left),
                can_start_test: Number(payload.attempts_left ?? prev.attempts_left) > 0,
              }
            : prev,
        );
      } else {
        setQuizSession((prev) => ({
          ...(prev || {}),
          ...payload,
        }));
        setTimeLeft(30);
      }
      setQuizSelectedIndex({ key: "", index: null });
      setCrossedOptions(new Set());
      longPressTriggeredRef.current = false;
      clearLongPressTimer();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Javobni yuborib bo'lmadi";
      const reason = proctoringStopReason(message);
      if (reason) {
        setError("");
        setProctoringReady(false);
        setQuizResult(proctoringStoppedPayload(quizSession, reason, tt));
        setQuizSession(null);
      } else {
        setError(grammarFriendlyErrorMessage(message, tt));
      }
    } finally {
      setBusy(false);
      answerInFlightRef.current = false;
    }
  }

  useEffect(() => {
    if (!quizSession?.question || quizResult || busy) return;
    setTimeLeft(30);
  }, [quizSession?.question?.prompt, quizSession?.question_index, quizResult, busy]);

  useEffect(() => {
    clearLongPressTimer();
    longPressTriggeredRef.current = false;
    setQuizSelectedIndex({ key: "", index: null });
    setCrossedOptions(new Set());
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
    return clearLongPressTimer;
  }, [quizSession?.session_id, quizSession?.question_index, quizSession?.question?.prompt]);

  useEffect(() => {
    if (!quizSession?.question || quizResult || busy || (isRuntimePage && !proctoringReady)) return;
    const timer = window.setInterval(() => {
      setTimeLeft((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [quizSession?.question?.prompt, quizSession?.question_index, quizResult, busy, isRuntimePage, proctoringReady]);

  useEffect(() => {
    if (!quizSession?.question || quizResult || busy || (isRuntimePage && !proctoringReady)) return;
    if (timeLeft > 0) return;
    submitQuizAnswer(true);
  }, [timeLeft, quizSession?.question?.prompt, quizSession?.question_index, quizResult, busy, proctoringReady]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <main className="flex min-h-screen flex-col bg-background relative selection:bg-cyan-500/30 selection:text-cyan-900 dark:selection:text-cyan-100">
      {error && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[60] bg-red-50 text-red-500 px-6 py-3 rounded-2xl shadow-premium border border-red-100 dark:bg-red-500/10 dark:border-red-500/20 text-sm font-bold animate-fade-in-up flex items-center gap-4">
          <span>{error}</span>
          <button className="underline underline-offset-2 hover:text-red-700 dark:hover:text-red-400 transition-colors" disabled={loading || busy} onClick={loadTopic}>{tt("common.retry", "Qayta urinish")}</button>
        </div>
      )}
      
      <div className="flex-1 overflow-y-auto w-full p-6 lg:p-12">
        <div className="max-w-4xl mx-auto space-y-8 relative">
          
          {isRuntimePage && proctoringLoading && (
            <div className="bg-white dark:bg-navy-900/50 rounded-[2rem] p-12 shadow-premium border border-line dark:border-white/10 text-center relative overflow-hidden mt-8">
               <div className="w-12 h-12 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin mx-auto mb-6" />
               <p className="text-ink-500 font-medium">{tt("common.loading", "Yuklanmoqda...")}</p>
            </div>
          )}
          
	          {!proctoringLoading && (
            <>
              {isRuntimePage && (
                null
              )}

              {!quizSession && !quizResult && (
                <div className="grammar-topic-wrapper w-full max-w-4xl mx-auto">
                  <div className="flex items-start justify-between mb-8 pb-6 border-b border-line dark:border-white/10">
                    <div>
                      <h1 className="text-3xl sm:text-4xl font-black text-navy-900 font-display dark:text-white tracking-tight mb-3">{topic?.title || "Grammar"}</h1>
                      <div className="flex flex-wrap gap-4 text-sm text-ink-500 dark:text-navy-300 font-bold">
                        <span className="px-3 py-1 bg-surface-soft dark:bg-white/5 rounded-lg border border-line dark:border-white/10">{topic?.subject}</span>
                        {!isRussianGrammarTopic && <span className="px-3 py-1 bg-surface-soft dark:bg-white/5 rounded-lg border border-line dark:border-white/10">{tt("student.grammar.level", "Level")} {topic?.level}</span>}
                        <span className="px-3 py-1 bg-surface-soft dark:bg-white/5 rounded-lg border border-line dark:border-white/10">{topic?.question_count} {tt("student.grammar.questions", "savol")}</span>
                      </div>
                    </div>
                    <button 
                      className="text-ink-400 hover:text-navy-900 dark:hover:text-white transition-colors p-2 bg-surface-soft hover:bg-line dark:bg-white/5 dark:hover:bg-white/10 rounded-full" 
                      onClick={backToList}
                      aria-label={tt("student.grammar.backToTopics", "Mavzularga qaytish")}
                    >
                      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                  </div>

                  {loading ? (
                    <div className="py-16 text-center">
                      <div className="w-10 h-10 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin mx-auto mb-6" />
                      <p className="text-ink-500 dark:text-navy-200 font-medium">{tt("student.grammar.loadingTopic", "Mavzu yuklanmoqda...")}</p>
                    </div>
                  ) : topic ? (
                    <>
                      <div className="mb-16">
                        {topic.rule ? (
                          <article className="prose prose-lg prose-cyan dark:prose-invert max-w-none font-sans text-gray-900 dark:text-gray-100 leading-loose whitespace-pre-wrap">
                            {topic.rule}
                          </article>
                        ) : (
                          <div className="bg-gold-50 dark:bg-gold-500/10 text-gold-600 dark:text-gold-400 p-6 rounded-xl text-sm font-bold border border-gold-100 dark:border-gold-500/20">
                            {tt("student.grammar.ruleMissing", "Mavzu qoidasi mavjud emas.")}
                          </div>
                        )}
                      </div>

                      {topic.question_count <= 0 ? (
                        <div className="bg-surface-soft dark:bg-white/5 text-ink-600 dark:text-navy-300 p-8 rounded-2xl text-center font-bold border border-line dark:border-white/10">
                          {tt("student.grammar.questionsMissing", "Bu mavzu uchun test savollari hali tayyor emas.")}
                        </div>
                      ) : (
                        <div className="flex flex-col sm:flex-row items-center justify-between gap-6 bg-surface-soft dark:bg-white/5 p-6 sm:p-8 rounded-[2rem] border border-line dark:border-white/10">
                          <div>
                            <p className="text-xl font-black text-navy-900 dark:text-white mb-1">{tt("student.grammar.practiceTime", "Test ishlab ko'ring")}</p>
                            <p className="text-sm font-bold text-ink-500 dark:text-navy-300">
                              {tt("student.grammar.attempts", "Urinishlar")}: {topic.attempts_used}/{topic.attempts_allowed} ({tt("student.grammar.remaining", "Qoldi")}: {topic.attempts_left})
                            </p>
                          </div>
                          <button 
                            className="w-full sm:w-auto bg-cyan-500 hover:bg-cyan-600 text-white px-10 py-4 rounded-2xl font-black text-lg transition-all hover:scale-105 hover:shadow-cyan-500/30 shadow-lg disabled:opacity-50 disabled:hover:scale-100 whitespace-nowrap"
                            disabled={busy || !topic.can_start_test} 
                            onClick={isRuntimePage ? startTopicQuiz : openRuntimePage}
                          >
                            {busy ? tt("common.wait", "Kuting...") : tt("student.grammar.startTopicTest", "Testni boshlash")}
                          </button>
                        </div>
                      )}
                    </>
                  ) : null}
                </div>
              )}

              {isRuntimePage && quizSession?.question && (
                <div className="test-runtime-card bg-white dark:bg-navy-900/50 rounded-[2rem] p-8 md:p-12 shadow-premium border border-line dark:border-white/10 relative overflow-hidden">
                  <div className="grid grid-cols-[auto_1fr_auto] items-center gap-3 sm:gap-5 mb-10">
                    <div className={`px-5 py-2.5 rounded-xl font-bold text-lg flex items-center gap-3 border shadow-sm ${timeLeft > 15 ? "bg-green-50 border-green-100 text-green-600 dark:bg-green-500/10 dark:border-green-500/20 dark:text-green-400" : timeLeft > 5 ? "bg-gold-50 border-gold-100 text-gold-600 dark:bg-gold-500/10 dark:border-gold-500/20 dark:text-gold-400" : "bg-red-50 border-red-100 text-red-500 dark:bg-red-500/10 dark:border-red-500/20 dark:text-red-400 animate-pulse"}`}>
                      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      00:{timeLeft.toString().padStart(2, '0')}
                    </div>
                    <div className="text-center min-w-0">
                      <h2 className="text-xl sm:text-2xl font-black text-navy-900 font-display dark:text-white tracking-tight truncate">
                        {quizSession.topic_title || topic?.title || "Grammar Quiz"}
                      </h2>
                      <p className="text-sm text-ink-500 dark:text-navy-300 font-bold uppercase tracking-wider">{tt("duel.question", "Savol")} {quizSession.question_index || 1} / {quizSession.total_questions || 0}</p>
                    </div>
                    <div className="hidden sm:block" />
                  </div>

                  <div className="w-full h-3 bg-transparent rounded-full mb-10 overflow-hidden border border-line dark:border-white/10">
                    <div 
                      className="h-full bg-gradient-to-r from-cyan-400 to-cyan-500 transition-all duration-500 ease-out"
                      style={{ width: `${Math.max(0, Math.min(100, ((quizSession.question_index || 1) / Math.max(1, quizSession.total_questions || 1)) * 100))}%` }}
                    />
                  </div>
                  
                  <h3 className="text-2xl sm:text-3xl font-black text-navy-900 font-display dark:text-white mb-12 leading-tight">
                    {quizSession.question.prompt || "-"}
                  </h3>
                  
                  <div className="grid sm:grid-cols-2 gap-5 mb-10">
	                    {(quizSession.question.options || []).map((option: string, idx: number) => {
	                      const questionKey = [
	                        quizSession.session_id || "",
                        quizSession.question_index || "",
                        quizSession.question?.prompt || "",
	                        (quizSession.question?.options || []).join("|"),
	                      ].join("|");
                        const optionKey = `${questionKey}::${idx}`;
	                      const selected = quizSelectedIndex.key === questionKey && quizSelectedIndex.index === idx;
                        const crossed = crossedOptions.has(optionKey);
	                      return (
	                      <button
	                        key={`opt-${questionKey}-${idx}`}
		                        className={`test-option-button ${selected ? "is-selected" : ""} ${crossed ? "test-option-crossed border-rose-200 bg-rose-50/60 dark:border-rose-400/35 dark:bg-rose-500/10" : ""} relative group p-6 rounded-[1.5rem] text-left transition-all duration-200 border-2 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed overflow-hidden ${
	                          selected
	                            ? "bg-cyan-50 border-cyan-500 dark:bg-cyan-500/10 dark:border-cyan-500 shadow-md" 
	                            : "bg-surface-soft border-transparent hover:border-cyan-300 hover:shadow-premium hover:-translate-y-1 dark:bg-white/5 dark:hover:border-cyan-500/50"
	                        }`}
                        onPointerDown={() => startLongPress(optionKey)}
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
	                          setQuizSelectedIndex({ key: questionKey, index: idx });
	                          event.currentTarget.blur();
	                          submitQuizAnswer(false, idx);
                        }}
                        disabled={busy || timeLeft <= 0 || !proctoringReady}
                      >
                        {!selected && <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />}
                        <div className="relative flex items-center gap-5">
	                          <span className={`test-option-letter w-10 h-10 rounded-xl shadow-sm flex items-center justify-center font-black transition-colors ${
                            selected
                              ? "bg-cyan-500 text-white" 
                              : "bg-white dark:bg-navy-800 text-ink-500 dark:text-navy-300 group-hover:text-cyan-500 dark:group-hover:text-cyan-400"
                          }`}>
                            {String.fromCharCode(65 + idx)}
                          </span>
	                          <span className={`font-bold text-lg leading-tight ${crossed ? "line-through decoration-2 decoration-rose-500/80 dark:decoration-rose-300/90" : ""} ${
	                            selected
	                              ? "text-navy-900 dark:text-white" 
                              : "text-ink-700 dark:text-navy-200 group-hover:text-navy-900 dark:group-hover:text-white"
                          }`}>
                            {option}
                          </span>
                        </div>
                      </button>
                    );
                    })}
                  </div>

                  <div className="flex justify-end pt-8 border-t border-line dark:border-white/10">
                    <button 
                      className="text-ink-500 hover:text-navy-900 dark:hover:text-white font-bold flex items-center gap-3 px-6 py-3 rounded-xl hover:bg-surface-soft dark:hover:bg-white/5 transition-all disabled:opacity-50 hover:shadow-sm border border-transparent hover:border-line dark:hover:border-white/10" 
                      disabled={busy || !proctoringReady} 
                      onClick={() => submitQuizAnswer(true)}
                    >
                      <span>{tt("common.skip", "O'tkazib yuborish")}</span>
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                    </button>
                  </div>
                </div>
              )}

              {isRuntimePage && quizResult && (
                <div className="test-result-card bg-white dark:bg-navy-900/80 rounded-[2rem] p-8 md:p-12 shadow-premium border border-line dark:border-white/10 text-center relative overflow-hidden">
                  <div className="absolute top-0 left-0 right-0 h-40 bg-gradient-to-b from-cyan-500/10 to-transparent" />
                  
                  <div className={`w-24 h-24 mx-auto ${isProctoringStopped(quizResult) ? "bg-red-50 dark:bg-red-500/10 text-red-500 dark:text-red-400 border-red-100 dark:border-red-500/20" : "bg-green-50 dark:bg-green-500/10 text-green-500 dark:text-green-400 border-green-100 dark:border-green-500/20"} rounded-[2rem] flex items-center justify-center mb-8 relative border shadow-sm rotate-3`}>
                    {isProctoringStopped(quizResult) ? (
                      <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" /></svg>
                    ) : (
                      <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    )}
                  </div>
                  
                  <h3 className="text-3xl md:text-4xl font-black text-navy-900 font-display dark:text-white mb-3 tracking-tight">
                    {isProctoringStopped(quizResult) ? tt("student.tests.proctorStopped", "Test proctoring sabab to'xtatildi") : tt("student.tests.finished", "Test yakunlandi!")}
                  </h3>
                  <p className="text-ink-500 dark:text-navy-200 font-medium mb-4">
                    {isProctoringStopped(quizResult) ? tt("duel.proctorStoppedDesc", "Test xavfsizlik tekshiruvi sabab yakunlandi.") : tt("student.tests.resultsBelow", "Natijalaringiz quyida keltirilgan.")}
                  </p>
                  {isProctoringStopped(quizResult) ? (
                    <div className="mb-10 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-bold text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200">
                      {tt("common.reason", "Sabab")}: {quizResult.proctoring_failure_message || grammarFriendlyErrorMessage(String(quizResult.proctoring_failure_reason || ""), tt)}
                    </div>
                  ) : <div className="mb-8" />}
                  
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-5 mb-12">
                    <div className="bg-transparent p-6 rounded-2xl border border-line dark:border-white/10 shadow-sm">
                      <p className="text-xs font-bold text-ink-400 dark:text-navy-300 uppercase tracking-wider mb-2">{tt("duel.correct", "To'g'ri")}</p>
                      <p className="text-3xl font-black text-green-600 dark:text-green-400">{quizResult.correct || 0}</p>
                    </div>
                    <div className="bg-transparent p-6 rounded-2xl border border-line dark:border-white/10 shadow-sm">
                      <p className="text-xs font-bold text-ink-400 dark:text-navy-300 uppercase tracking-wider mb-2">{tt("duel.wrong", "Xato")}</p>
                      <p className="text-3xl font-black text-red-500 dark:text-red-400">{quizResult.wrong || 0}</p>
                    </div>
                    <div className="bg-cyan-50 dark:bg-navy-900 p-6 rounded-2xl border border-cyan-100 dark:border-cyan-500/20 shadow-sm relative overflow-hidden">
                      <div className="absolute top-0 right-0 w-16 h-16 bg-cyan-500/20 blur-xl rounded-full" />
                      <p className="currency-inline text-xs font-bold text-cyan-600 dark:text-cyan-400 uppercase tracking-wider mb-2">
                        <AssetIcon type="dpoint" size={18} />
                        {tt("student.tests.dpoints", "D'Pointlar")}
                      </p>
                      <p className="text-3xl font-black text-cyan-600 dark:text-cyan-400">
                        {`${Number(quizResult.dpoints || 0) > 0 ? "+" : ""}${Number(quizResult.dpoints || 0).toFixed(1)}`}
                      </p>
                    </div>
                    <div className="bg-transparent p-6 rounded-2xl border border-line dark:border-white/10 shadow-sm">
                      <p className="text-xs font-bold text-ink-400 dark:text-navy-300 uppercase tracking-wider mb-2">{tt("student.grammar.remaining", "Qoldi")}</p>
                      <p className="text-3xl font-black text-navy-900 dark:text-white">{quizResult.attempts_left ?? "-"}</p>
                    </div>
                  </div>
                  
                  <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                    {Array.isArray((quizResult as GenericRow).details) && ((quizResult as GenericRow).details as GenericRow[]).length > 0 && (
                      <button
                        className="bg-indigo-50 hover:bg-indigo-100 text-indigo-700 dark:bg-indigo-500/15 dark:hover:bg-indigo-500/25 dark:text-indigo-300 px-6 py-4 rounded-2xl font-bold border border-indigo-100 dark:border-indigo-500/30 transition-all hover:-translate-y-1 flex items-center justify-center gap-2"
                        onClick={() => setReviewOpen(true)}
                      >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
                        {tt("student.dailyTest.reviewAnswers", "Javoblarni ko'rish")}
                      </button>
                    )}
                    <button
                      className="bg-navy-900 hover:bg-navy-800 text-white dark:bg-cyan-500 dark:hover:bg-cyan-600 px-8 py-4 rounded-2xl font-bold text-lg transition-all shadow-lg shadow-cyan-500/20 hover:-translate-y-1"
                      onClick={() => {
                        setQuizResult(null);
                        setQuizSession(null);
                        setQuizSelectedIndex({ key: "", index: null });
                        setProctoringReady(false);
                        startTopicQuiz().catch(() => null);
                      }}
                    >
                      {tt("student.tests.startNew", "Yangi test boshlash")}
                    </button>
                    <button
                      className="bg-surface-soft hover:bg-line dark:bg-white/5 dark:hover:bg-white/10 text-navy-900 dark:text-white px-8 py-4 rounded-2xl font-bold text-lg transition-all shadow-sm border border-line dark:border-white/10 hover:-translate-y-1"
                      onClick={backToList}
                    >
                      {tt("student.grammar.backToTopics", "Mavzularga qaytish")}
                    </button>
                  </div>
                </div>
              )}

              {/* ── Grammar Test Review Popup ── */}
              {reviewOpen && quizResult && (
                <div className="fixed inset-0 z-[90] flex items-end sm:items-center justify-center p-0 sm:p-4 text-left text-navy-900 dark:text-white" onClick={(e) => { if (e.target === e.currentTarget) setReviewOpen(false); }}>
                  <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setReviewOpen(false)} />
                  <div className="relative z-10 w-full sm:max-w-2xl max-h-[90dvh] rounded-t-[2rem] border border-line bg-white shadow-2xl dark:border-white/10 dark:bg-slate-950 sm:rounded-[2rem] flex flex-col overflow-hidden">
                    {/* Header */}
                    <div className="flex items-center justify-between px-5 py-4 border-b border-line dark:border-white/10 shrink-0">
                      <div>
                        <h3 className="text-lg font-black text-navy-900 dark:text-white">{tt("student.dailyTest.reviewAnswers", "Javoblarni ko'rish")}</h3>
                        <p className="text-xs font-semibold text-ink-500 dark:text-navy-300 mt-0.5">
                          {tt("duel.correct", "To'g'ri")}: {quizResult.correct || 0} · {tt("duel.wrong", "Noto'g'ri")}: {quizResult.wrong || 0} · {tt("student.dailyTest.skipped", "O'tkazilgan")}: {quizResult.skipped || 0}
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
                    <div className="overflow-y-auto flex-1 space-y-3 bg-white p-4 dark:bg-slate-950">
                      {((quizResult as GenericRow).details as GenericRow[] || []).map((detail: GenericRow, idx: number) => {
                        const isCorrect = Boolean(detail.is_correct);
                        const isSkipped = Boolean(detail.is_skipped) || detail.selected_index === null || detail.selected_index === undefined;
                        const options = Array.isArray(detail.options) ? detail.options as string[] : [];
                        const selectedIdx = detail.selected_index !== null && detail.selected_index !== undefined ? Number(detail.selected_index) : null;
                        const correctIdx = detail.correct_index !== null && detail.correct_index !== undefined ? Number(detail.correct_index) : null;
                        return (
                          <div key={`grammar-review-${idx}`} className={`rounded-2xl border p-4 ${
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
                                  {tt("duel.question", "Savol")} #{idx + 1}
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
                                        : "text-gray-700 dark:text-slate-300 font-medium"
                                    }`}>
                                      <span className={`w-5 h-5 shrink-0 rounded-full flex items-center justify-center text-[10px] font-black ${
                                        isCorrectOpt ? "bg-emerald-500 text-white" :
                                        isSelected && !isCorrect ? "bg-rose-500 text-white" :
                                        "bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-slate-300"
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
                    <div className="shrink-0 border-t border-line bg-white px-5 py-4 dark:border-white/10 dark:bg-slate-950">
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
            </>
          )}
        </div>
      </div>
    </main>
  );
}

export default function StudentGrammarTopicPage() {
  return (
    <Suspense
      fallback={(
        <main className="flex min-h-screen flex-col bg-background">
          <div className="flex-1 flex items-center justify-center p-6">
            <div className="bg-white dark:bg-navy-900/50 rounded-[2rem] p-12 shadow-premium border border-line dark:border-white/10 text-center animate-fade-in-up">
              <div className="w-10 h-10 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin mx-auto mb-4" />
              <p className="text-ink-500 dark:text-navy-200 font-medium">Yuklanmoqda...</p>
            </div>
          </div>
        </main>
      )}
    >
      <StudentGrammarTopicContent />
    </Suspense>
  );
}
