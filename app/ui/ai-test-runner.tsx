"use client";

/**
 * Student AI test runner — yangi test turlari uchun.
 *  • Taymer YO'Q.
 *  • Har bir savol javobi darhol tekshiriladi ("Tekshirilmoqda…" holati).
 *  • Xato bo'lsa shu savolda qolinadi (retry_until_correct).
 *  • Testdan chiqib ketilsa attempt bekor bo'ladi — keyingi kirishda boshidan.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useWebT } from "./web-i18n";

type Kind =
  | "speak_sentence" | "write_sentence" | "guided_writing" | "translation"
  | "reading_open" | "read_aloud" | "paraphrase" | "dialogue_completion"
  | "picture_description" | "listening" | "dictation" | "spelling"
  | "matching" | "scrambled_sentence" | "gap_fill";

type Question = {
  kind: Kind;
  check: "ai" | "auto";
  input: "text" | "audio" | "audio_or_text" | "choice" | "order" | "pairs";
  retry_until_correct: boolean;
  prompt?: string;
  instruction?: string;
  word?: string;
  passage?: string;
  image_url?: string;
  audio_url?: string;
  level?: string;
  options?: string[];
  left_items?: string[];
  right_items?: string[];
  tokens?: string[];
};

type Attempt = {
  attempt_id: number;
  status: string;
  title?: string;
  total_questions: number;
  solved_count: number;
  current_index: number | null;
  is_finished: boolean;
  questions: Question[];
  solved_indexes: number[];
  tries: Record<string, number>;
  correct_count: number;
  wrong_count: number;
  dpoints_delta: number;
};

type AnswerResult = {
  verdict: "correct" | "wrong";
  moved_on: boolean;
  try_count: number;
  tries_left: number;
  feedback?: Record<string, unknown>;
  dpoints_delta: number;
  attempt: Attempt;
  finished: boolean;
};

const ASSET = (url?: string) => (url && url.startsWith("/") ? `/api${url}` : url || "");

export function AiTestRunner({
  sourceType,
  sourceId,
  homeworkId,
  onExit,
}: {
  sourceType: "library_test" | "homework" | "weekly_review";
  sourceId?: number;
  homeworkId?: number;
  onExit: () => void;
}) {
  const tt = useWebT();
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(false);
  const [feedback, setFeedback] = useState<AnswerResult | null>(null);
  const startedRef = useRef(false);

  const start = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/student/ai-tests/start", {
        method: "POST",
        body: { source_type: sourceType, source_id: sourceId, homework_id: homeworkId },
      });
      setAttempt(res.attempt);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Test boshlanmadi");
    }
    setLoading(false);
  }, [sourceType, sourceId, homeworkId]);

  // Ilova qayta ochilsa: active attempt bo'lsa davom emas — qoida bo'yicha boshidan.
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    start();
  }, [start]);

  // Chiqib ketilsa attempt SAQLANADI — 5 soat ichida qaytganda o'sha joyidan
  // davom etadi (abandon qilinmaydi).

  const submit = useCallback(
    async (payload: Record<string, unknown>) => {
      if (!attempt || attempt.current_index === null) return;
      setChecking(true);
      setFeedback(null);
      setError("");
      try {
        const res: AnswerResult = await apiFetch(`/student/ai-tests/${attempt.attempt_id}/answer`, {
          method: "POST",
          body: { question_index: attempt.current_index, ...payload },
        });
        setFeedback(res);
        setAttempt(res.attempt);
        // To'g'ri javobda avtomatik keyingi savolga o'tamiz (tugma kerak emas).
        // Xato javobda esa shu savolda qolamiz (retry).
        if (res.verdict === "correct" && !res.finished) {
          setTimeout(() => setFeedback(null), 950);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Tekshirishda xato");
      }
      setChecking(false);
    },
    [attempt]
  );

  if (loading) return <Centered>{tt("aitest.preparing", "Test tayyorlanmoqda…")}</Centered>;
  if (error && !attempt) {
    return (
      <Centered>
        <p className="mb-4 font-bold text-red-500">{error}</p>
        <button onClick={onExit} className="rounded-xl bg-cyan-600 px-5 py-2.5 font-black text-white">{tt("aitest.back", "Ortga")}</button>
      </Centered>
    );
  }
  if (!attempt) return <Centered>{tt("aitest.loading", "Yuklanmoqda…")}</Centered>;

  if (attempt.is_finished || attempt.current_index === null) {
    return <FinishedView attempt={attempt} onExit={onExit} />;
  }

  const q = attempt.questions[attempt.current_index];
  const progress = Math.round((attempt.solved_count / Math.max(1, attempt.total_questions)) * 100);
  const currentTries = Number(attempt.tries[String(attempt.current_index)] || 0);

  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <header className="mb-5">
        <div className="mb-2 flex items-center justify-between">
          <button onClick={onExit} className="text-sm font-black text-ink-500 dark:text-navy-300">← {tt("aitest.exit", "Chiqish")}</button>
          <span className="text-sm font-black text-navy-900 dark:text-white">
            {attempt.solved_count} / {attempt.total_questions}
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-surface-soft dark:bg-white/10">
          <div className="h-full rounded-full bg-cyan-500 transition-all" style={{ width: `${progress}%` }} />
        </div>
        {q.retry_until_correct && (
          <p className="mt-2 text-xs font-bold text-amber-600 dark:text-amber-300">
            {tt("aitest.mustCorrect", "To'g'ri javob bermaguningizcha keyingi savolga o'tolmaysiz.")}
            {currentTries > 0 ? ` (${currentTries})` : ""}
          </p>
        )}
      </header>

      <QuestionCard
        key={attempt.current_index}
        question={q}
        attemptId={attempt.attempt_id}
        checking={checking}
        feedback={feedback}
        onSubmit={submit}
        onNext={() => setFeedback(null)}
      />

      {error && <p className="mt-3 text-center text-sm font-bold text-red-500">{error}</p>}
    </div>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center text-center font-bold text-ink-500 dark:text-navy-300">
      {children}
    </div>
  );
}

function FinishedView({ attempt, onExit }: { attempt: Attempt; onExit: () => void }) {
  const tt = useWebT();
  return (
    <div className="mx-auto max-w-md px-4 py-16 text-center">
      <div className="mb-4 text-6xl">🎉</div>
      <h2 className="mb-2 text-2xl font-black text-navy-900 dark:text-white">{tt("aitest.finishedTitle", "Test yakunlandi!")}</h2>
      <p className="mb-6 font-semibold text-ink-500 dark:text-navy-300">
        {tt("aitest.finishedSubtitle", "{count} ta mashqni tugatdingiz.", { count: attempt.total_questions })}
      </p>
      <div className="mb-6 flex justify-center gap-4">
        <Stat label={tt("aitest.correct", "To'g'ri")} value={attempt.correct_count} tone="green" />
        <Stat label={tt("aitest.dpoint", "D'point")} value={`${attempt.dpoints_delta > 0 ? "+" : ""}${attempt.dpoints_delta.toFixed(1)}`} tone={attempt.dpoints_delta >= 0 ? "green" : "red"} />
      </div>
      <button onClick={onExit} className="rounded-xl bg-cyan-600 px-6 py-3 font-black text-white">Tugatish</button>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: React.ReactNode; tone: "green" | "red" }) {
  return (
    <div className={`rounded-2xl px-5 py-3 ${tone === "green" ? "bg-emerald-50 dark:bg-emerald-500/10" : "bg-red-50 dark:bg-red-500/10"}`}>
      <div className={`text-2xl font-black ${tone === "green" ? "text-emerald-700 dark:text-emerald-200" : "text-red-600 dark:text-red-300"}`}>{value}</div>
      <div className="text-xs font-bold text-ink-500 dark:text-navy-300">{label}</div>
    </div>
  );
}

const KIND_TITLE: Record<Kind, string> = {
  speak_sentence: "So'z bilan gap tuzib gapiring",
  write_sentence: "So'z bilan gap tuzib yozing",
  guided_writing: "Mavzu bo'yicha yozing",
  translation: "Tarjima qiling",
  reading_open: "Matnni o'qib javob bering",
  read_aloud: "Matnni ovoz chiqarib o'qing",
  paraphrase: "Boshqacha aytib bering",
  dialogue_completion: "Dialogni to'ldiring",
  picture_description: "Rasmni tasvirlang",
  listening: "Tinglang va tanlang",
  dictation: "Tinglang va yozing",
  spelling: "To'g'ri yozing",
  matching: "Juftlarni moslang",
  scrambled_sentence: "So'zlardan gap tuzing",
  gap_fill: "Bo'sh joyni to'ldiring",
};

function QuestionCard({
  question, attemptId, checking, feedback, onSubmit, onNext,
}: {
  question: Question;
  attemptId: number;
  checking: boolean;
  feedback: AnswerResult | null;
  onSubmit: (payload: Record<string, unknown>) => void;
  onNext: () => void;
}) {
  const tt = useWebT();
  const wasCorrect = feedback?.verdict === "correct";
  const showFeedback = !!feedback;
  const canRetry = feedback && feedback.verdict === "wrong" && !feedback.moved_on;

  return (
    <article className="rounded-3xl border border-line bg-white p-6 shadow-sm dark:border-white/10 dark:bg-navy-900/70">
      <p className="mb-1 text-xs font-black uppercase tracking-wide text-cyan-600 dark:text-cyan-300">
        {KIND_TITLE[question.kind]}
      </p>
      {question.word && (
        <div className="mb-3 inline-block rounded-xl bg-cyan-50 px-4 py-2 text-xl font-black text-cyan-800 dark:bg-cyan-500/15 dark:text-cyan-100">
          {question.word}
        </div>
      )}
      {question.prompt && <p className="mb-3 text-lg font-bold text-navy-900 dark:text-white">{question.prompt}</p>}
      {question.instruction && <p className="mb-3 text-sm font-semibold text-ink-500 dark:text-navy-300">{question.instruction}</p>}
      {question.passage && (
        <div className="mb-4 max-h-56 overflow-y-auto rounded-2xl bg-surface-soft p-4 text-sm leading-relaxed text-navy-900 dark:bg-white/5 dark:text-white">
          {question.passage}
        </div>
      )}
      {question.image_url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={ASSET(question.image_url)} alt="" className="mb-4 w-full rounded-2xl" />
      )}
      {question.audio_url && (
        <audio controls src={ASSET(question.audio_url)} className="mb-4 w-full" />
      )}

      {!showFeedback || canRetry ? (
        <AnswerInput question={question} attemptId={attemptId} checking={checking} onSubmit={onSubmit} retrying={!!canRetry} />
      ) : null}

      {checking && (
        <div className="mt-4 flex items-center gap-3 rounded-2xl bg-violet-50 px-4 py-3 dark:bg-violet-500/10">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-violet-400 border-t-transparent" />
          <span className="font-black text-violet-700 dark:text-violet-200">{tt("aitest.checking", "Tekshirilmoqda…")}</span>
        </div>
      )}

      {showFeedback && !checking && (
        <FeedbackBox
          result={feedback!}
          onNext={onNext}
          canRetry={!!canRetry}
        />
      )}
      {wasCorrect && (
        <p className="mt-2 text-center text-sm font-black text-emerald-600 dark:text-emerald-300">
          {feedback!.finished ? tt("aitest.finishedTitle", "Test yakunlandi!") : tt("aitest.correctVerdict", "✅ To'g'ri!")}
        </p>
      )}
    </article>
  );
}

function AnswerInput({
  question, attemptId, checking, onSubmit, retrying,
}: {
  question: Question;
  attemptId: number;
  checking: boolean;
  onSubmit: (payload: Record<string, unknown>) => void;
  retrying: boolean;
}) {
  const tt = useWebT();
  const [text, setText] = useState("");
  const [choice, setChoice] = useState<number | null>(null);
  const [pairs, setPairs] = useState<Record<string, string>>({});
  const [order, setOrder] = useState<string[]>([]);
  const [audioUrl, setAudioUrl] = useState("");

  const disabled = checking;

  // ── Ovozli javob (mikrofon) ──
  if (question.input === "audio" || (question.input === "audio_or_text" && audioUrl)) {
    return (
      <div className="space-y-3">
        <Recorder attemptId={attemptId} onUploaded={setAudioUrl} disabled={disabled} />
        {audioUrl && (
          <button
            onClick={() => onSubmit({ audio_url: audioUrl })}
            disabled={disabled}
            className="w-full rounded-2xl bg-cyan-600 py-3 font-black text-white disabled:opacity-60"
          >
            {retrying ? tt("aitest.resend","Qayta yuborish") : tt("aitest.submitAnswer","Javobni yuborish")}
          </button>
        )}
      </div>
    );
  }

  if (question.input === "choice") {
    return (
      <div className="space-y-2">
        {(question.options || []).map((opt, i) => (
          <button
            key={i}
            onClick={() => setChoice(i)}
            className={`w-full rounded-2xl border-2 px-4 py-3 text-left font-bold transition ${
              choice === i
                ? "border-cyan-500 bg-cyan-50 text-cyan-900 dark:bg-cyan-500/15 dark:text-cyan-100"
                : "border-line bg-surface-soft text-navy-900 dark:border-white/10 dark:bg-white/5 dark:text-white"
            }`}
          >
            {opt}
          </button>
        ))}
        <button
          onClick={() => choice !== null && onSubmit({ choice_index: choice })}
          disabled={disabled || choice === null}
          className="w-full rounded-2xl bg-cyan-600 py-3 font-black text-white disabled:opacity-60"
        >
          {tt("aitest.submit","Tekshirish")}
        </button>
      </div>
    );
  }

  if (question.input === "order") {
    const chosen = order;
    const remaining = (question.tokens || []).filter((t, i) => {
      const usedCount = chosen.filter((c) => c === t).length;
      const totalCount = (question.tokens || []).filter((x) => x === t).length;
      // Har bir token nusxasi bir marta ishlatiladi (indeks bo'yicha emas, sonli)
      return usedCount < totalCount || chosen.indexOf(t) === -1 ? true : usedCount < totalCount;
    });
    // Soddaroq: token pool, tanlanganini olib tashlash indeks bilan
    return (
      <div className="space-y-3">
        <div className="min-h-[52px] rounded-2xl border-2 border-dashed border-cyan-300 bg-cyan-50/40 p-2 dark:border-cyan-500/40 dark:bg-cyan-500/5">
          <div className="flex flex-wrap gap-2">
            {chosen.map((tok, i) => (
              <button
                key={`c-${i}`}
                onClick={() => setOrder(chosen.filter((_, idx) => idx !== i))}
                className="rounded-xl bg-cyan-600 px-3 py-1.5 text-sm font-black text-white"
              >
                {tok}
              </button>
            ))}
            {chosen.length === 0 && <span className="p-2 text-sm font-bold text-ink-400">{tt("aitest.orderHint","So'zlarni bosib tartiblang")}</span>}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {(question.tokens || []).map((tok, i) => {
            const used = chosen.filter((c) => c === tok).length;
            const total = (question.tokens || []).filter((x) => x === tok).length;
            const poolIndex = (question.tokens || []).slice(0, i + 1).filter((x) => x === tok).length;
            const alreadyUsed = poolIndex <= used;
            return (
              <button
                key={`p-${i}`}
                disabled={alreadyUsed}
                onClick={() => setOrder([...chosen, tok])}
                className={`rounded-xl border px-3 py-1.5 text-sm font-bold ${
                  alreadyUsed
                    ? "border-line bg-line/40 text-ink-300 dark:border-white/5 dark:bg-white/5"
                    : "border-line bg-surface-soft text-navy-900 dark:border-white/10 dark:bg-white/10 dark:text-white"
                }`}
              >
                {tok}
              </button>
            );
          })}
        </div>
        <button
          onClick={() => onSubmit({ order: chosen })}
          disabled={disabled || chosen.length === 0}
          className="w-full rounded-2xl bg-cyan-600 py-3 font-black text-white disabled:opacity-60"
        >
          {tt("aitest.submit","Tekshirish")}
        </button>
      </div>
    );
  }

  if (question.input === "pairs") {
    return (
      <div className="space-y-3">
        {(question.left_items || []).map((left, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="min-w-[110px] rounded-xl bg-surface-soft px-3 py-2 font-bold text-navy-900 dark:bg-white/5 dark:text-white">{left}</span>
            <span className="font-black text-ink-400">→</span>
            <select
              value={pairs[left] || ""}
              onChange={(e) => setPairs({ ...pairs, [left]: e.target.value })}
              className="flex-1 rounded-xl border border-line bg-surface-soft px-3 py-2 font-semibold text-navy-900 dark:border-white/10 dark:bg-navy-950 dark:text-white"
            >
              <option value="">{tt("aitest.chooseHint","Tanlang…")}</option>
              {(question.right_items || []).map((r, ri) => (
                <option key={ri} value={r}>{r}</option>
              ))}
            </select>
          </div>
        ))}
        <button
          onClick={() => onSubmit({ pairs })}
          disabled={disabled || Object.keys(pairs).length < (question.left_items || []).length}
          className="w-full rounded-2xl bg-cyan-600 py-3 font-black text-white disabled:opacity-60"
        >
          {tt("aitest.submit","Tekshirish")}
        </button>
      </div>
    );
  }

  // text input (+ audio_or_text: yozma tanlash)
  return (
    <div className="space-y-3">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="min-h-[100px] w-full rounded-2xl border border-line bg-surface-soft px-4 py-3 font-semibold text-navy-900 outline-none focus:ring-2 focus:ring-cyan-500 dark:border-white/10 dark:bg-navy-950 dark:text-white"
        placeholder={tt("aitest.answerPlaceholder","Javobingizni yozing…")}
      />
      <button
        onClick={() => text.trim() && onSubmit({ answer_text: text })}
        disabled={disabled || !text.trim()}
        className="w-full rounded-2xl bg-cyan-600 py-3 font-black text-white disabled:opacity-60"
      >
        {retrying ? tt("aitest.resend","Qayta yuborish") : tt("aitest.submit","Tekshirish")}
      </button>
    </div>
  );
}

function Recorder({ attemptId, onUploaded, disabled }: { attemptId: number; onUploaded: (url: string) => void; disabled: boolean }) {
  const tt = useWebT();
  const [recording, setRecording] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [ready, setReady] = useState(false);
  const [err, setErr] = useState("");
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRec = async () => {
    setErr("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = (e) => e.data.size > 0 && chunksRef.current.push(e.data);
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setUploading(true);
        try {
          const form = new FormData();
          form.append("file", blob, "answer.webm");
          const res = await apiFetch("/student/ai-tests/upload-audio", { method: "POST", body: form });
          if (res?.url) { onUploaded(res.url); setReady(true); }
        } catch {
          setErr("Yuklashda xato, qayta urinib ko'ring");
        }
        setUploading(false);
      };
      mediaRef.current = mr;
      mr.start();
      setRecording(true);
      setReady(false);
    } catch {
      setErr(tt("aitest.micDenied", "Mikrofonga ruxsat berilmadi"));
    }
  };

  const stopRec = () => {
    mediaRef.current?.stop();
    setRecording(false);
  };

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        onClick={recording ? stopRec : startRec}
        disabled={disabled || uploading}
        className={`flex h-20 w-20 items-center justify-center rounded-full text-3xl text-white shadow-lg transition disabled:opacity-60 ${
          recording ? "animate-pulse bg-red-500" : "bg-cyan-600"
        }`}
      >
        {recording ? "⏹" : "🎙️"}
      </button>
      <span className="text-sm font-bold text-ink-500 dark:text-navy-300">
        {uploading ? tt("aitest.uploading", "Yuklanmoqda…") : recording ? tt("aitest.recording", "Yozilmoqda… tugatish uchun bosing") : ready ? tt("aitest.recorded", "Yozildi ✓ — qaytadan yozish mumkin") : tt("aitest.speakToStart", "Gapirish uchun bosing")}
      </span>
      {err && <span className="text-sm font-bold text-red-500">{err}</span>}
    </div>
  );
}

function FeedbackBox({ result, onNext, canRetry }: { result: AnswerResult; onNext: () => void; canRetry: boolean }) {
  const tt = useWebT();
  const fb = (result.feedback || {}) as Record<string, unknown>;
  const grammarErrors = (fb.grammar_errors as { original?: string; correction?: string; explanation?: string }[]) || [];
  const pronErrors = (fb.pronunciation_errors as { word?: string; note?: string }[]) || [];
  const wrong = result.verdict === "wrong";

  return (
    <div className={`mt-4 rounded-2xl p-4 ${wrong ? "bg-red-50 dark:bg-red-500/10" : "bg-emerald-50 dark:bg-emerald-500/10"}`}>
      <p className={`font-black ${wrong ? "text-red-600 dark:text-red-300" : "text-emerald-700 dark:text-emerald-200"}`}>
        {wrong ? tt("aitest.wrongVerdict", "❌ Hali to'g'ri emas") : tt("aitest.correctVerdict", "✅ To'g'ri!")}
      </p>
      {typeof fb.feedback === "string" && <p className="mt-1 text-sm font-semibold text-navy-900 dark:text-white">{fb.feedback}</p>}
      {typeof fb.transcript === "string" && fb.transcript && (
        <p className="mt-2 rounded-lg bg-white/60 px-3 py-1.5 text-sm font-semibold text-ink-700 dark:bg-white/5 dark:text-navy-100">
          {tt("aitest.youSaid", "Siz aytdingiz")}: “{fb.transcript}”
        </p>
      )}
      {typeof fb.corrected === "string" && fb.corrected && wrong && (
        <p className="mt-1 text-sm font-bold text-navy-900 dark:text-white">{tt("aitest.correctIs", "To'g'risi")}: {fb.corrected}</p>
      )}
      {grammarErrors.length > 0 && (
        <ul className="mt-2 space-y-1 text-sm">
          {grammarErrors.slice(0, 3).map((g, i) => (
            <li key={i} className="text-navy-800 dark:text-navy-100">
              <b>{g.original}</b> → <b className="text-emerald-700 dark:text-emerald-300">{g.correction}</b>
              {g.explanation ? <span className="text-ink-500 dark:text-navy-300"> — {g.explanation}</span> : null}
            </li>
          ))}
        </ul>
      )}
      {pronErrors.length > 0 && (
        <p className="mt-2 text-sm font-semibold text-amber-700 dark:text-amber-300">
          {tt("aitest.pron", "Talaffuz")}: {pronErrors.slice(0, 4).map((p) => p.word).join(", ")}
        </p>
      )}
      {typeof fb.hint === "string" && fb.hint && <p className="mt-1 text-sm font-semibold text-amber-700 dark:text-amber-300">💡 {fb.hint}</p>}
      {canRetry && (
        <p className="mt-2 text-xs font-black text-red-500">
          {result.tries_left > 0 ? tt("aitest.triesLeft", "Yana urinib ko'ring ({n} urinish qoldi)", { n: result.tries_left }) : tt("aitest.lastTry", "Oxirgi urinish")}
        </p>
      )}
      {!canRetry && !result.finished && (
        <button onClick={onNext} className="mt-3 w-full rounded-xl bg-cyan-600 py-2.5 font-black text-white">
          {tt("aitest.nextQuestion", "Keyingi savol →")}
        </button>
      )}
    </div>
  );
}
