"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
const CRITERIA = ["fluency", "vocabulary", "grammar", "pronunciation"] as const;
const CRITERIA_LABELS: Record<string, string> = {
  fluency: "Fluency & Coherence",
  vocabulary: "Lexical Resource",
  grammar: "Grammar",
  pronunciation: "Pronunciation",
};
const STATUS_LABELS: Record<string, string> = {
  pending: "Kutilmoqda",
  in_review: "Tekshirilmoqda",
  answered: "Javob berilgan",
};
const STUDENT_STATUS_LABELS: Record<string, string> = {
  new: "O'quvchi hali belgilamagan",
  resolved: "O'quvchi: hal qilindi",
  practice_again: "O'quvchi: qayta mashq qiladi",
};
const RETRY_TEMPLATES = [
  "Shu savolga qaytadan 2 daqiqa javob bering va har bir fikrga misol qo'shing.",
  "Tuzatilgan gaplarni 3 marta ovoz chiqarib o'qing, keyin javobni qayta yozib yuboring.",
  "Javobni linking words (however, moreover, as a result) bilan qayta tuzing.",
  "Part 2 uchun 1 daqiqa reja tuzing (what, when, why, how) va qayta gapiring.",
];

type Role = "speaking_admin" | "teacher" | "support";

type ListItem = {
  id: number;
  subject: "english" | "russian";
  scale: "ielts" | "ten";
  max_score: number;
  question_text: string;
  topic_title: string;
  part: number | null;
  duration_seconds: number;
  ai_score: number | null;
  student_note: string;
  status: string;
  student_status: string;
  student_name: string;
  reviewer_name: string;
  created_at: string | null;
  answered_at: string | null;
};

type Correction = { original: string; correction: string; note: string };

type Reply = {
  reviewer_name: string;
  feedback_text: string;
  audio_url: string | null;
  band: number | null;
  criteria: Record<string, number>;
  corrections: Correction[];
  retry_task: string;
  updated_at: string | null;
};

type Detail = ListItem & {
  audio_url: string | null;
  transcript: string;
  ai: {
    score?: number;
    criteria?: Record<string, number>;
    summary?: string;
    strengths?: string[];
    improvements?: string[];
    grammar_errors?: { original: string; correction: string; explanation: string }[];
    vocabulary_suggestions?: { original: string; better: string; note: string }[];
    improved_answer?: string;
  };
  reply: Reply | null;
  previous_answers: { id: number; score: number | null; prompt: string; topic_title: string; part: number | null; transcript: string; created_at: string | null }[];
  past_feedback: { id: number; question_text: string; topic_title: string; band: number | null; student_status: string; created_at: string | null }[];
  progress: {
    answers: number;
    average_score: number | null;
    best_score: number | null;
    change: number | null;
    criteria: Record<string, number>;
    trend: { score: number; created_at: string | null }[];
  };
  navigation: { position: number | null; total: number; previous_id: number | null; next_id: number | null };
};

type Reviewer = { id: number; name: string; role: string; subject: string; answered?: number; assigned_at?: string | null };

interface SpeakingFeedbackProps {
  apiFetch: (path: string, options?: { method?: string; body?: any; timeoutMs?: number; signal?: AbortSignal }) => Promise<any>;
  role: Role;
}

function mediaUrl(raw: string | null | undefined) {
  const value = String(raw || "").trim();
  if (!value) return "";
  return value.startsWith("/") ? `${API_BASE}${value}` : value;
}

function errorText(error: unknown, fallback: string) {
  const message = error instanceof Error ? error.message : String(error || "");
  return message.trim() || fallback;
}

function formatScore(value: number | null | undefined, scale: string) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const num = Number(value);
  return scale === "ielts" ? num.toFixed(1) : `${Number.isInteger(num) ? num : num.toFixed(1)}/10`;
}

function timeAgo(iso: string | null) {
  if (!iso) return "";
  const diff = Math.max(0, Date.now() - new Date(iso).getTime());
  const minutes = Math.round(diff / 60000);
  if (minutes < 60) return `${minutes} daq oldin`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} soat oldin`;
  return new Date(iso).toLocaleDateString();
}

function formatDuration(seconds: number) {
  const total = Math.max(0, Math.round(seconds || 0));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

function bandOptions(scale: string) {
  const max = scale === "ielts" ? 9 : 10;
  const values: string[] = [];
  for (let v = max; v >= 0; v -= 0.5) values.push(v.toFixed(1));
  return values;
}

function ListSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-2" aria-hidden="true">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton-card space-y-2 p-3">
          <div className="skeleton-line title" />
          <div className="skeleton-line short" />
        </div>
      ))}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "answered"
      ? "bg-emerald-50 text-emerald-700"
      : status === "in_review"
        ? "bg-amber-50 text-amber-700"
        : "bg-blue-50 text-blue-700";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${color}`}>{STATUS_LABELS[status] || status}</span>;
}

function Panel({ title, children, right }: { title: string; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h4 className="text-sm font-bold text-slate-900 dark:text-white">{title}</h4>
        {right}
      </div>
      {children}
    </section>
  );
}

/** Records a short audio comment in the browser (WebM; the server converts it to m4a). */
function AudioRecorder({ onChange, disabled }: { onChange: (blob: Blob | null) => void; disabled?: boolean }) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [previewUrl, setPreviewUrl] = useState("");
  const [error, setError] = useState("");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const stopStream = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = null;
  };

  useEffect(
    () => () => {
      stopStream();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    },
    // Cleanup only on unmount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  async function start() {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"].find(
        (type) => typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(type),
      );
      const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        stopStream();
        setRecording(false);
        if (blob.size < 2048) {
          setError("Yozuv juda qisqa.");
          onChange(null);
          return;
        }
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        setPreviewUrl(URL.createObjectURL(blob));
        onChange(blob);
      };
      recorderRef.current = recorder;
      recorder.start();
      setSeconds(0);
      setRecording(true);
      timerRef.current = window.setInterval(() => {
        setSeconds((value) => {
          if (value + 1 >= 180) recorderRef.current?.stop();
          return value + 1;
        });
      }, 1000);
    } catch {
      setError("Mikrofonga ruxsat berilmadi.");
      stopStream();
    }
  }

  function stop() {
    recorderRef.current?.stop();
  }

  function clear() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl("");
    onChange(null);
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {recording ? (
          <button type="button" onClick={stop} className="rounded-xl bg-red-600 px-4 py-2 text-sm font-semibold text-white">
            ■ To'xtatish ({formatDuration(seconds)})
          </button>
        ) : (
          <button
            type="button"
            onClick={start}
            disabled={disabled}
            className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold disabled:opacity-50 dark:border-slate-600"
          >
            🎙 {previewUrl ? "Qayta yozish" : "Audio izoh yozish"}
          </button>
        )}
        {previewUrl && !recording ? (
          <button type="button" onClick={clear} className="rounded-xl border border-red-200 px-3 py-2 text-xs font-semibold text-red-600">
            Yozuvni o'chirish
          </button>
        ) : null}
        <span className="text-xs text-slate-500">3 daqiqagacha</span>
      </div>
      {previewUrl ? <audio controls src={previewUrl} className="w-full" /> : null}
      {error ? <div className="text-xs text-red-600">{error}</div> : null}
    </div>
  );
}

function AudioPlayer({ src }: { src: string }) {
  const ref = useRef<HTMLAudioElement | null>(null);
  const [rate, setRate] = useState(1);
  return (
    <div className="space-y-2">
      <audio ref={ref} controls preload="metadata" src={src} className="w-full" />
      <div className="flex flex-wrap gap-1">
        {[0.75, 1, 1.25, 1.5].map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => {
              setRate(value);
              if (ref.current) ref.current.playbackRate = value;
            }}
            className={`rounded-lg border px-2 py-1 text-xs font-semibold ${rate === value ? "border-blue-600 bg-blue-600 text-white" : "border-slate-300 dark:border-slate-600"}`}
          >
            {value}x
          </button>
        ))}
      </div>
    </div>
  );
}

function ReviewerManager({ apiFetch }: { apiFetch: SpeakingFeedbackProps["apiFetch"] }) {
  const [assigned, setAssigned] = useState<Reviewer[]>([]);
  const [candidates, setCandidates] = useState<Reviewer[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(
    async (search: string) => {
      setLoading(true);
      setError("");
      try {
        const res = await apiFetch(`/staff/speaking/feedback/reviewers?q=${encodeURIComponent(search)}`, { method: "GET" });
        setAssigned(Array.isArray(res?.assigned) ? res.assigned : []);
        setCandidates(Array.isArray(res?.candidates) ? res.candidates : []);
      } catch (e) {
        setError(errorText(e, "Ro'yxatni yuklab bo'lmadi."));
      } finally {
        setLoading(false);
      }
    },
    [apiFetch],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => load(query), 300);
    return () => window.clearTimeout(timer);
  }, [load, query]);

  async function add(id: number) {
    setBusyId(id);
    try {
      await apiFetch("/staff/speaking/feedback/reviewers", { method: "POST", body: { user_id: id } });
      await load(query);
    } catch (e) {
      setError(errorText(e, "Biriktirib bo'lmadi."));
    } finally {
      setBusyId(null);
    }
  }

  async function remove(reviewer: Reviewer) {
    if (!confirm(`${reviewer.name} Speaking feedback tekshiruvidan olib tashlansinmi?`)) return;
    setBusyId(reviewer.id);
    try {
      await apiFetch(`/staff/speaking/feedback/reviewers/${reviewer.id}`, { method: "DELETE" });
      await load(query);
    } catch (e) {
      setError(errorText(e, "Olib tashlab bo'lmadi."));
    } finally {
      setBusyId(null);
    }
  }

  const roleLabel = (role: string) => (role === "support" ? "Support teacher" : "Teacher");

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title={`Biriktirilgan ustozlar (${assigned.length})`}>
        <p className="mb-3 text-xs text-slate-500">
          Bu ustozlar Teachers app va saytda alohida &quot;Speaking feedback&quot; sahifasini ko&apos;radi va o&apos;quvchilarga javob yozadi.
        </p>
        {error ? <div className="mb-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div> : null}
        {loading && !assigned.length ? (
          <ListSkeleton rows={3} />
        ) : assigned.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
            Hozircha faqat Speaking admin javob beradi. O&apos;ngdagi ro&apos;yxatdan ustoz biriktiring.
          </div>
        ) : (
          <div className="space-y-2">
            {assigned.map((reviewer) => (
              <div key={reviewer.id} className="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-2 dark:bg-slate-800">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold">{reviewer.name}</div>
                  <div className="text-xs text-slate-500">
                    {roleLabel(reviewer.role)}
                    {reviewer.subject ? ` · ${reviewer.subject}` : ""} · {reviewer.answered || 0} ta javob
                  </div>
                </div>
                <button
                  type="button"
                  disabled={busyId === reviewer.id}
                  onClick={() => remove(reviewer)}
                  className="rounded-lg border border-red-200 px-3 py-1 text-xs font-semibold text-red-600 disabled:opacity-50"
                >
                  Olib tashlash
                </button>
              </div>
            ))}
          </div>
        )}
      </Panel>
      <Panel title="Ustoz qo'shish">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Ism yoki fan bo'yicha qidirish..."
          className="mb-3 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
        />
        {loading && !candidates.length ? (
          <ListSkeleton rows={4} />
        ) : candidates.length === 0 ? (
          <div className="text-sm text-slate-500">Teacher yoki support teacher topilmadi.</div>
        ) : (
          <div className="max-h-[420px] space-y-2 overflow-y-auto">
            {candidates.map((candidate) => (
              <div key={candidate.id} className="flex items-center gap-3 rounded-xl border border-slate-200 px-3 py-2 dark:border-slate-700">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold">{candidate.name}</div>
                  <div className="text-xs text-slate-500">
                    {roleLabel(candidate.role)}
                    {candidate.subject ? ` · ${candidate.subject}` : ""}
                  </div>
                </div>
                <button
                  type="button"
                  disabled={busyId === candidate.id}
                  onClick={() => add(candidate.id)}
                  className="rounded-lg bg-blue-600 px-3 py-1 text-xs font-semibold text-white disabled:opacity-50"
                >
                  Biriktirish
                </button>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}

export function SpeakingFeedback({ apiFetch, role }: SpeakingFeedbackProps) {
  const [tab, setTab] = useState<"queue" | "reviewers">("queue");
  const [status, setStatus] = useState("open");
  const [subject, setSubject] = useState("");
  const [query, setQuery] = useState("");
  const [mine, setMine] = useState(false);
  const [items, setItems] = useState<ListItem[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [feedbackText, setFeedbackText] = useState("");
  const [band, setBand] = useState("");
  const [criteria, setCriteria] = useState<Record<string, string>>({});
  const [corrections, setCorrections] = useState<Correction[]>([]);
  const [retryTask, setRetryTask] = useState("");
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [removeAudio, setRemoveAudio] = useState(false);
  const [recorderKey, setRecorderKey] = useState(0);
  const [saving, setSaving] = useState(false);
  const touchStart = useRef<{ x: number; y: number } | null>(null);

  const filterQuery = useMemo(() => {
    const params = new URLSearchParams({ status, subject, q: query.trim(), mine: mine ? "true" : "false" });
    return params.toString();
  }, [status, subject, query, mine]);

  const loadList = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch(`/staff/speaking/feedback/requests?${filterQuery}`, { method: "GET" });
      setItems(Array.isArray(res?.items) ? res.items : []);
      setCounts(res?.counts || {});
    } catch (e) {
      setError(errorText(e, "Javoblarni yuklab bo'lmadi."));
    } finally {
      setLoading(false);
    }
  }, [apiFetch, filterQuery]);

  useEffect(() => {
    const timer = window.setTimeout(() => loadList(), query ? 300 : 0);
    return () => window.clearTimeout(timer);
  }, [loadList, query]);

  const fillForm = useCallback((value: Detail | null) => {
    const reply = value?.reply;
    setFeedbackText(reply?.feedback_text || "");
    setBand(reply?.band !== null && reply?.band !== undefined ? Number(reply.band).toFixed(1) : "");
    setCriteria(Object.fromEntries(Object.entries(reply?.criteria || {}).map(([k, v]) => [k, Number(v).toFixed(1)])));
    setCorrections(reply?.corrections || []);
    setRetryTask(reply?.retry_task || "");
    setAudioBlob(null);
    setRemoveAudio(false);
    setRecorderKey((key) => key + 1);
  }, []);

  const openDetail = useCallback(
    async (id: number) => {
      setSelectedId(id);
      setDetailLoading(true);
      setError("");
      try {
        const res = await apiFetch(`/staff/speaking/feedback/requests/${id}?${filterQuery}`, { method: "GET" });
        const value: Detail | null = res?.request || null;
        setDetail(value);
        fillForm(value);
        if (value && value.status === "pending") {
          // Mark it "in review" so other reviewers pick another answer.
          apiFetch(`/staff/speaking/feedback/requests/${id}/claim`, { method: "POST" })
            .then((claim) => {
              if (claim?.ok) {
                setItems((prev) => prev.map((item) => (item.id === id ? { ...item, status: "in_review" } : item)));
              }
            })
            .catch(() => undefined);
        }
      } catch (e) {
        setError(errorText(e, "Javobni ochib bo'lmadi."));
      } finally {
        setDetailLoading(false);
      }
    },
    [apiFetch, filterQuery, fillForm],
  );

  const goPrevious = useCallback(() => {
    if (detail?.navigation.previous_id) openDetail(detail.navigation.previous_id);
  }, [detail, openDetail]);
  const goNext = useCallback(() => {
    if (detail?.navigation.next_id) openDetail(detail.navigation.next_id);
  }, [detail, openDetail]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (target?.isContentEditable) return;
      if (event.key === "ArrowRight" || event.key === "ArrowDown") {
        event.preventDefault();
        goNext();
      } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
        event.preventDefault();
        goPrevious();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goNext, goPrevious]);

  function onTouchStart(event: React.TouchEvent) {
    const touch = event.touches[0];
    touchStart.current = { x: touch.clientX, y: touch.clientY };
  }

  function onTouchEnd(event: React.TouchEvent) {
    const start = touchStart.current;
    touchStart.current = null;
    if (!start) return;
    const touch = event.changedTouches[0];
    const dx = touch.clientX - start.x;
    const dy = touch.clientY - start.y;
    // Horizontal swipe: left = next answer, right = previous answer.
    if (Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy) * 1.5) {
      if (dx < 0) goNext();
      else goPrevious();
    }
  }

  function addAiCorrections() {
    const errors = detail?.ai?.grammar_errors || [];
    const vocab = detail?.ai?.vocabulary_suggestions || [];
    const rows: Correction[] = [
      ...errors.map((item) => ({ original: item.original, correction: item.correction, note: item.explanation })),
      ...vocab.map((item) => ({ original: item.original, correction: item.better, note: item.note })),
    ].filter((row) => row.original || row.correction);
    setCorrections((prev) => {
      const seen = new Set(prev.map((row) => `${row.original}|${row.correction}`));
      return [...prev, ...rows.filter((row) => !seen.has(`${row.original}|${row.correction}`))];
    });
  }

  async function submit() {
    if (!detail) return;
    const hasContent =
      feedbackText.trim() || audioBlob || band || corrections.some((row) => row.original || row.correction) || retryTask.trim() || (detail.reply?.audio_url && !removeAudio);
    if (!hasContent) {
      setError("Feedback yozing yoki audio izoh yozib oling.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const form = new FormData();
      form.append("feedback_text", feedbackText.trim());
      form.append("band", band);
      form.append("criteria", JSON.stringify(Object.fromEntries(Object.entries(criteria).filter(([, v]) => v !== ""))));
      form.append("corrections", JSON.stringify(corrections.filter((row) => row.original.trim() || row.correction.trim())));
      form.append("retry_task", retryTask.trim());
      form.append("remove_audio", removeAudio ? "true" : "false");
      if (audioBlob) {
        const ext = audioBlob.type.includes("mp4") ? "m4a" : audioBlob.type.includes("ogg") ? "ogg" : "webm";
        form.append("audio", audioBlob, `feedback.${ext}`);
      }
      const res = await apiFetch(`/staff/speaking/feedback/requests/${detail.id}/reply`, { method: "POST", body: form, timeoutMs: 120000 });
      const nextId = detail.navigation.next_id;
      setNotice(`Feedback ${detail.student_name}ga Speaking ilovasida yuborildi.`);
      setItems((prev) =>
        status === "open" || status === "pending" || status === "in_review"
          ? prev.filter((item) => item.id !== detail.id)
          : prev.map((item) => (item.id === detail.id ? { ...item, status: "answered" } : item)),
      );
      setCounts((prev) => ({ ...prev, answered: (prev.answered || 0) + (detail.status === "answered" ? 0 : 1) }));
      if (nextId && (status === "open" || status === "pending")) {
        openDetail(nextId);
      } else if (res?.request) {
        openDetail(detail.id);
      }
    } catch (e) {
      setError(errorText(e, "Feedbackni yuborib bo'lmadi."));
    } finally {
      setSaving(false);
    }
  }

  const scale = detail?.scale || "ielts";
  const statusTabs: [string, string][] = [
    ["open", `Ochiq (${counts.open ?? 0})`],
    ["pending", `Yangi (${counts.pending ?? 0})`],
    ["in_review", `Tekshirilmoqda (${counts.in_review ?? 0})`],
    ["answered", `Javob berilgan (${counts.answered ?? 0})`],
    ["all", "Hammasi"],
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">Speaking feedback</h2>
          <p className="text-sm text-slate-500">
            O&apos;quvchilar Speaking ilovasidan yuborgan javoblar. Eshiting, baholang va feedback yuboring — u o&apos;quvchining Speaking ilovasida
            ko&apos;rinadi.
          </p>
        </div>
        {role === "speaking_admin" ? (
          <div className="flex gap-2">
            {(
              [
                ["queue", "Javoblar"],
                ["reviewers", "Ustozlar"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                className={`rounded-xl px-4 py-2 text-sm font-semibold ${tab === key ? "bg-blue-600 text-white" : "border border-slate-300 dark:border-slate-600"}`}
              >
                {label}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      {error ? (
        <div className="flex items-start justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <span>{error}</span>
          <button type="button" onClick={() => setError("")} className="font-semibold">
            ×
          </button>
        </div>
      ) : null}
      {notice ? (
        <div className="flex items-start justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          <span>{notice}</span>
          <button type="button" onClick={() => setNotice("")} className="font-semibold">
            ×
          </button>
        </div>
      ) : null}

      {tab === "reviewers" && role === "speaking_admin" ? (
        <ReviewerManager apiFetch={apiFetch} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(280px,360px)_1fr]">
          <div className={`space-y-3 ${detail ? "hidden lg:block" : ""}`}>
            <div className="flex flex-wrap gap-1">
              {statusTabs.map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setStatus(key)}
                  className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${status === key ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900" : "bg-slate-100 dark:bg-slate-800"}`}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="O'quvchi yoki topic..."
                className="min-w-0 flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
              />
              <select
                value={subject}
                onChange={(event) => setSubject(event.target.value)}
                className="rounded-xl border border-slate-300 px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
              >
                <option value="">Barcha fanlar</option>
                <option value="english">IELTS</option>
                <option value="russian">Rus tili</option>
              </select>
            </div>
            <label className="flex items-center gap-2 text-xs font-semibold text-slate-600">
              <input type="checkbox" checked={mine} onChange={(event) => setMine(event.target.checked)} />
              Faqat men tekshirayotganlar
            </label>
            {loading ? (
              <ListSkeleton />
            ) : items.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">Bu ro&apos;yxatda javob yo&apos;q.</div>
            ) : (
              <div className="max-h-[70vh] space-y-2 overflow-y-auto pr-1">
                {items.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => openDetail(item.id)}
                    className={`w-full rounded-2xl border p-3 text-left transition ${
                      selectedId === item.id
                        ? "border-blue-500 bg-blue-50/60 dark:bg-blue-950/30"
                        : "border-slate-200 bg-white hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-bold">{item.student_name}</span>
                      <StatusBadge status={item.status} />
                    </div>
                    <div className="mt-1 truncate text-xs font-semibold text-slate-600 dark:text-slate-300">
                      {item.subject === "russian" ? "Rus tili" : "IELTS"}
                      {item.part ? ` · Part ${item.part}` : ""} · {item.topic_title || "—"}
                    </div>
                    <div className="mt-1 line-clamp-2 text-xs text-slate-500">{item.question_text}</div>
                    <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-500">
                      <span>AI: {formatScore(item.ai_score, item.scale)}</span>
                      <span>{formatDuration(item.duration_seconds)}</span>
                      <span>{timeAgo(item.created_at)}</span>
                      {item.reviewer_name ? <span>👤 {item.reviewer_name}</span> : null}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div onTouchStart={onTouchStart} onTouchEnd={onTouchEnd} className={detail ? "" : "hidden lg:block"}>
            {detailLoading && !detail ? (
              <ListSkeleton rows={4} />
            ) : !detail ? (
              <div className="rounded-2xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">
                Chapdagi ro&apos;yxatdan javobni tanlang. ← → tugmalari yoki chapga/o&apos;ngga surish bilan keyingi javobga o&apos;tasiz.
              </div>
            ) : (
              <div className={`space-y-4 ${detailLoading ? "opacity-60" : ""}`}>
                <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                  <button
                    type="button"
                    onClick={() => {
                      setDetail(null);
                      setSelectedId(null);
                    }}
                    className="rounded-lg border px-2 py-1 text-xs font-semibold lg:hidden"
                  >
                    ← Ro&apos;yxat
                  </button>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-base font-bold">{detail.student_name}</div>
                    <div className="text-xs text-slate-500">
                      {detail.subject === "russian" ? "Rus tili" : "IELTS"}
                      {detail.part ? ` · Part ${detail.part}` : ""} · {timeAgo(detail.created_at)} · <StatusBadge status={detail.status} />
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={goPrevious}
                      disabled={!detail.navigation.previous_id}
                      className="rounded-lg border px-3 py-1 text-sm disabled:opacity-40"
                      title="Oldingi (←)"
                    >
                      ←
                    </button>
                    <span className="px-1 text-xs text-slate-500">
                      {detail.navigation.position ?? "–"} / {detail.navigation.total}
                    </span>
                    <button
                      type="button"
                      onClick={goNext}
                      disabled={!detail.navigation.next_id}
                      className="rounded-lg border px-3 py-1 text-sm disabled:opacity-40"
                      title="Keyingi (→)"
                    >
                      →
                    </button>
                  </div>
                </div>

                <Panel title={detail.topic_title || "Savol"}>
                  <p className="text-sm text-slate-800 dark:text-slate-100">{detail.question_text}</p>
                  {detail.student_note ? (
                    <div className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-800">
                      <b>O&apos;quvchi izohi:</b> {detail.student_note}
                    </div>
                  ) : null}
                  <div className="mt-3">
                    {detail.audio_url ? <AudioPlayer src={mediaUrl(detail.audio_url)} /> : <div className="text-xs text-red-600">Audio topilmadi.</div>}
                  </div>
                </Panel>

                <div className="grid gap-4 xl:grid-cols-2">
                  <Panel title="Transcript">
                    <p className="whitespace-pre-wrap text-sm leading-6 text-slate-700 dark:text-slate-200">
                      {detail.transcript || "Bu javob AI bilan tahlil qilinmagan, transcript yo'q."}
                    </p>
                  </Panel>
                  <Panel title="AI baholash" right={<span className="text-lg font-bold text-blue-600">{formatScore(detail.ai?.score ?? detail.ai_score, scale)}</span>}>
                    {detail.ai && Object.keys(detail.ai).length ? (
                      <div className="space-y-3 text-sm">
                        {detail.ai.criteria ? (
                          <div className="space-y-1">
                            {CRITERIA.map((key) =>
                              detail.ai.criteria?.[key] !== undefined ? (
                                <div key={key} className="flex items-center justify-between gap-2 text-xs">
                                  <span>{CRITERIA_LABELS[key]}</span>
                                  <b>{formatScore(detail.ai.criteria?.[key], scale)}</b>
                                </div>
                              ) : null,
                            )}
                          </div>
                        ) : null}
                        {detail.ai.summary ? <p className="text-xs text-slate-600 dark:text-slate-300">{detail.ai.summary}</p> : null}
                        {(detail.ai.grammar_errors || []).length ? (
                          <div className="space-y-1">
                            <div className="text-xs font-bold">Grammatik xatolar</div>
                            {(detail.ai.grammar_errors || []).map((item, index) => (
                              <div key={index} className="text-xs">
                                <span className="text-red-600 line-through">{item.original}</span> → <span className="font-semibold text-emerald-700">{item.correction}</span>
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <p className="text-sm text-slate-500">AI baholash yo&apos;q.</p>
                    )}
                  </Panel>
                </div>

                <div className="grid gap-4 xl:grid-cols-2">
                  <Panel title="O'quvchining progressi">
                    <div className="grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
                      {[
                        ["Javoblar", String(detail.progress.answers)],
                        ["O'rtacha", formatScore(detail.progress.average_score, scale)],
                        ["Eng yaxshi", formatScore(detail.progress.best_score, scale)],
                        [
                          "O'zgarish",
                          detail.progress.change === null ? "—" : `${detail.progress.change > 0 ? "+" : ""}${detail.progress.change.toFixed(1)}`,
                        ],
                      ].map(([label, value]) => (
                        <div key={label} className="rounded-xl bg-slate-50 px-2 py-2 dark:bg-slate-800">
                          <div className="text-[11px] text-slate-500">{label}</div>
                          <div className="text-sm font-bold">{value}</div>
                        </div>
                      ))}
                    </div>
                    {detail.progress.trend.length > 1 ? (
                      <div className="mt-3 flex h-16 items-end gap-1" aria-label="Ball dinamikasi">
                        {detail.progress.trend.map((point, index) => (
                          <div
                            key={index}
                            title={formatScore(point.score, scale)}
                            className="flex-1 rounded-t bg-blue-500/70"
                            style={{ height: `${Math.max(6, (point.score / detail.max_score) * 100)}%` }}
                          />
                        ))}
                      </div>
                    ) : null}
                    {Object.keys(detail.progress.criteria).length ? (
                      <div className="mt-3 space-y-1">
                        {CRITERIA.map((key) =>
                          detail.progress.criteria[key] !== undefined ? (
                            <div key={key} className="flex items-center gap-2 text-xs">
                              <span className="w-36 shrink-0">{CRITERIA_LABELS[key]}</span>
                              <div className="h-2 flex-1 rounded-full bg-slate-100 dark:bg-slate-800">
                                <div className="h-2 rounded-full bg-blue-500" style={{ width: `${(detail.progress.criteria[key] / detail.max_score) * 100}%` }} />
                              </div>
                              <b>{formatScore(detail.progress.criteria[key], scale)}</b>
                            </div>
                          ) : null,
                        )}
                      </div>
                    ) : null}
                  </Panel>
                  <Panel title="Oldingi javoblar">
                    {detail.previous_answers.length === 0 && detail.past_feedback.length === 0 ? (
                      <p className="text-sm text-slate-500">Oldingi javoblar yo&apos;q.</p>
                    ) : (
                      <div className="max-h-72 space-y-2 overflow-y-auto">
                        {detail.past_feedback.map((item) => (
                          <div key={`f${item.id}`} className="rounded-xl bg-emerald-50 px-3 py-2 text-xs dark:bg-emerald-950/30">
                            <b>Ustoz feedbacki</b> · {item.topic_title} · Band {formatScore(item.band, scale)} · {STUDENT_STATUS_LABELS[item.student_status] || ""}
                          </div>
                        ))}
                        {detail.previous_answers.map((item) => (
                          <details key={item.id} className="rounded-xl bg-slate-50 px-3 py-2 text-xs dark:bg-slate-800">
                            <summary className="cursor-pointer">
                              <b>{formatScore(item.score, scale)}</b> · {item.topic_title || "—"} · {timeAgo(item.created_at)}
                              <div className="text-slate-500">{item.prompt}</div>
                            </summary>
                            <p className="mt-2 whitespace-pre-wrap text-slate-600 dark:text-slate-300">{item.transcript}</p>
                          </details>
                        ))}
                      </div>
                    )}
                  </Panel>
                </div>

                <Panel
                  title={detail.reply ? `Feedback (${detail.reply.reviewer_name}) — tahrirlash` : "Feedback yozish"}
                  right={detail.student_status !== "new" ? <span className="text-xs text-slate-500">{STUDENT_STATUS_LABELS[detail.student_status]}</span> : null}
                >
                  <div className="space-y-4">
                    <label className="block text-sm font-semibold">
                      Yozma feedback
                      <textarea
                        value={feedbackText}
                        onChange={(event) => setFeedbackText(event.target.value)}
                        rows={5}
                        maxLength={6000}
                        placeholder="Nima yaxshi chiqdi, nimani yaxshilash kerak..."
                        className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm font-normal dark:border-slate-700 dark:bg-slate-800"
                      />
                    </label>

                    <div className="grid gap-3 sm:grid-cols-5">
                      <label className="block text-sm font-semibold sm:col-span-1">
                        {scale === "ielts" ? "Band tavsiyasi" : "Ball (10)"}
                        <select
                          value={band}
                          onChange={(event) => setBand(event.target.value)}
                          className="mt-1 w-full rounded-xl border border-slate-300 px-2 py-2 text-sm font-normal dark:border-slate-700 dark:bg-slate-800"
                        >
                          <option value="">—</option>
                          {bandOptions(scale).map((value) => (
                            <option key={value} value={value}>
                              {value}
                            </option>
                          ))}
                        </select>
                      </label>
                      {CRITERIA.map((key) => (
                        <label key={key} className="block text-xs font-semibold">
                          {CRITERIA_LABELS[key]}
                          <select
                            value={criteria[key] || ""}
                            onChange={(event) => setCriteria((prev) => ({ ...prev, [key]: event.target.value }))}
                            className="mt-1 w-full rounded-xl border border-slate-300 px-2 py-2 text-sm font-normal dark:border-slate-700 dark:bg-slate-800"
                          >
                            <option value="">—</option>
                            {bandOptions(scale).map((value) => (
                              <option key={value} value={value}>
                                {value}
                              </option>
                            ))}
                          </select>
                        </label>
                      ))}
                    </div>

                    <div>
                      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                        <span className="text-sm font-semibold">Tuzatishlar</span>
                        <div className="flex gap-2">
                          {(detail.ai?.grammar_errors || []).length || (detail.ai?.vocabulary_suggestions || []).length ? (
                            <button type="button" onClick={addAiCorrections} className="rounded-lg border px-2 py-1 text-xs font-semibold">
                              AI xatolarini qo&apos;shish
                            </button>
                          ) : null}
                          <button
                            type="button"
                            onClick={() => setCorrections((prev) => [...prev, { original: "", correction: "", note: "" }])}
                            className="rounded-lg border px-2 py-1 text-xs font-semibold"
                          >
                            + Qator
                          </button>
                        </div>
                      </div>
                      {corrections.length === 0 ? (
                        <p className="text-xs text-slate-500">O&apos;quvchi aytgan noto&apos;g&apos;ri gap va to&apos;g&apos;ri variantini qo&apos;shing.</p>
                      ) : (
                        <div className="space-y-2">
                          {corrections.map((row, index) => (
                            <div key={index} className="grid gap-2 rounded-xl bg-slate-50 p-2 sm:grid-cols-[1fr_1fr_1fr_auto] dark:bg-slate-800">
                              {(["original", "correction", "note"] as const).map((field) => (
                                <input
                                  key={field}
                                  value={row[field]}
                                  maxLength={field === "note" ? 400 : 300}
                                  onChange={(event) =>
                                    setCorrections((prev) => prev.map((item, i) => (i === index ? { ...item, [field]: event.target.value } : item)))
                                  }
                                  placeholder={field === "original" ? "O'quvchi aytgani" : field === "correction" ? "To'g'ri varianti" : "Izoh"}
                                  className="rounded-lg border border-slate-300 px-2 py-1 text-xs dark:border-slate-600 dark:bg-slate-900"
                                />
                              ))}
                              <button
                                type="button"
                                onClick={() => setCorrections((prev) => prev.filter((_, i) => i !== index))}
                                className="rounded-lg border border-red-200 px-2 text-xs text-red-600"
                              >
                                ×
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    <label className="block text-sm font-semibold">
                      Qayta bajarish topshirig&apos;i
                      <textarea
                        value={retryTask}
                        onChange={(event) => setRetryTask(event.target.value)}
                        rows={2}
                        maxLength={2000}
                        className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm font-normal dark:border-slate-700 dark:bg-slate-800"
                      />
                    </label>
                    <div className="flex flex-wrap gap-1">
                      {RETRY_TEMPLATES.map((template) => (
                        <button key={template} type="button" onClick={() => setRetryTask(template)} className="rounded-lg bg-slate-100 px-2 py-1 text-left text-[11px] dark:bg-slate-800">
                          {template}
                        </button>
                      ))}
                    </div>

                    <div>
                      <div className="mb-2 text-sm font-semibold">Audio feedback</div>
                      {detail.reply?.audio_url && !removeAudio && !audioBlob ? (
                        <div className="mb-2 space-y-2">
                          <AudioPlayer src={mediaUrl(detail.reply.audio_url)} />
                          <button type="button" onClick={() => setRemoveAudio(true)} className="text-xs font-semibold text-red-600">
                            Oldingi audio izohni o&apos;chirish
                          </button>
                        </div>
                      ) : null}
                      <AudioRecorder key={recorderKey} onChange={setAudioBlob} disabled={saving} />
                    </div>

                    <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-200 pt-3 dark:border-slate-700">
                      <button
                        type="button"
                        onClick={goNext}
                        disabled={!detail.navigation.next_id}
                        className="rounded-xl border px-4 py-2 text-sm font-semibold disabled:opacity-40"
                      >
                        O&apos;tkazib yuborish →
                      </button>
                      <button
                        type="button"
                        onClick={submit}
                        disabled={saving}
                        className="rounded-xl bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        {saving ? "Yuborilmoqda..." : detail.reply ? "Yangilab yuborish" : "O'quvchiga yuborish"}
                      </button>
                    </div>
                  </div>
                </Panel>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
