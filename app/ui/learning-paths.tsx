"use client";
import { FormEvent, MouseEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useWebT } from "./web-i18n";

type Row = Record<string, any>;
type ApiFetch = (path: string, options?: any) => Promise<any>;
const covers = ["star", "chest", "dolphin", "jellyfish", "ship", "trophy"];
const image = (key: string) => `/learning-paths/${covers.includes(key) ? key : "star"}.png`;
const errorText = (e: unknown, fallback: string) => e instanceof Error ? e.message : fallback;

/* ═══════════════════════════════════════════════════════════════════════════════
   STUDENT VIEW — Duolingo-style interactive learning path
   ═══════════════════════════════════════════════════════════════════════════════ */

export function StudentLearningPaths({ apiFetch }: { apiFetch: ApiFetch }) {
  const t = useWebT();
  const [tracks, setTracks] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeModule, setActiveModule] = useState<Row | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await apiFetch("/student/learning-tracks");
      setTracks(Array.isArray(data?.items) ? data.items : []);
    } catch (e) {
      setError(errorText(e, t("learning.loadError", "O'quv yo'li yuklanmadi.")));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return (
    <section className="premium-card m-4 grid min-h-64 place-items-center">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent" />
    </section>
  );

  return (
    <section className="mx-auto w-full max-w-4xl p-4 sm:p-6">
      <header className="premium-card p-5 sm:p-7">
        <p className="text-xs font-black uppercase tracking-[.18em] text-cyan-600 dark:text-cyan-300">Diamond Learning Path</p>
        <h1 className="mt-2 text-2xl font-black text-navy-900 dark:text-white">{t("learning.student.title", "Mening o'quv yo'lim")}</h1>
        <p className="mt-2 text-sm text-ink-600 dark:text-navy-300">Modullarni kamida 70% bilan tugating — keyingi track avtomatik ochiladi.</p>
      </header>
      {error ? <p className="mt-4 rounded-xl bg-rose-500/10 p-3 text-sm text-rose-700">{error}</p> : null}
      <div className="mt-6 space-y-8">
        {tracks.map((track, i) => (
          <StudentTrack
            key={track.id}
            track={track}
            index={i}
            onStartModule={(mod) => setActiveModule(mod)}
          />
        ))}
      </div>
      {!tracks.length ? (
        <div className="premium-card mt-5 p-10 text-center text-ink-500 dark:text-navy-300">
          Sizga hali o'quv yo'li biriktirilmagan.
        </div>
      ) : null}
      {activeModule ? (
        <LessonPlayerModal
          module={activeModule}
          apiFetch={apiFetch}
          onClose={() => {
            setActiveModule(null);
            void load();
          }}
        />
      ) : null}
    </section>
  );
}

function StudentTrack({ track, index, onStartModule }: { track: Row; index: number; onStartModule: (module: Row) => void }) {
  const locked = Boolean(track.locked);
  const modules = Array.isArray(track.modules) ? track.modules : [];

  return (
    <article className={`premium-card overflow-hidden p-5 sm:p-6 ${locked ? "opacity-55 grayscale" : ""}`}>
      <div className="flex items-center gap-4">
        <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-cyan-500/15 font-black text-cyan-700 dark:text-cyan-200">
          {index + 1}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-black uppercase tracking-wide text-cyan-600 dark:text-cyan-300">Track {index + 1} · {track.subject}</p>
          <h2 className="mt-1 text-xl font-black text-navy-900 dark:text-white">{track.title}</h2>
          <p className="mt-0.5 text-sm text-ink-500 dark:text-navy-300">{track.description || "Bosqichma-bosqich o'rganish yo'li"}</p>
        </div>
        <span className="h-fit rounded-full bg-cyan-500/15 px-3 py-1 text-xs font-black text-cyan-700 dark:text-cyan-200">
          {locked ? "🔒" : track.progress_status === "passed" ? "✓ Tugallandi" : `${track.passing_score || 70}% o'tish`}
        </span>
      </div>

      {/* Duolingo zig-zag path */}
      <div className="relative mx-auto mt-8 max-w-lg pb-4">
        <div className="space-y-6">
          {modules.map((module: Row, order: number) => (
            <ModuleNode
              key={module.id}
              module={module}
              order={order}
              locked={locked}
              onStart={() => onStartModule(module)}
            />
          ))}
        </div>
      </div>

      {track.certificate_eligible ? (
        <div className="mt-6 rounded-2xl bg-gradient-to-r from-amber-400/15 to-amber-500/15 p-4 text-sm font-semibold text-amber-800 dark:text-amber-100 border border-amber-400/20">
          🎓 Track tugadi — sertifikatingiz Profilim → Sertifikatlarim'da tayyor.
        </div>
      ) : null}
    </article>
  );
}

function ModuleNode({ module, order, locked: parentLocked, onStart }: { module: Row; order: number; locked: boolean; onStart: () => void }) {
  const progress = module.progress || {};
  const locked = parentLocked || progress.status === "locked";
  const topics = Array.isArray(module.topic_keys) ? module.topic_keys : [];
  const lessons = Array.isArray(module.lessons) ? module.lessons : [];
  const passed = progress.status === "passed";
  const active = !locked && !passed;
  const isLeft = order % 2 === 0;
  const score = Number(progress.best_score || 0);
  const stars = passed ? (score >= 95 ? 3 : score >= 85 ? 2 : 1) : 0;

  return (
    <div
      className={`relative flex items-center gap-4 transition-all duration-300 ${locked ? "opacity-50" : ""}`}
      style={{
        flexDirection: isLeft ? "row" : "row-reverse",
        paddingLeft: isLeft ? "4%" : "12%",
        paddingRight: isLeft ? "12%" : "4%",
      }}
    >
      {/* Circular module node */}
      <button
        onClick={locked ? undefined : onStart}
        disabled={locked}
        type="button"
        title={locked ? "Oldingi modulni tugating" : module.title}
        className={`group relative grid h-20 w-20 shrink-0 place-items-center overflow-hidden rounded-full border-[5px] shadow-xl transition-all duration-300 ${
          passed
            ? "border-emerald-400 bg-emerald-500 shadow-emerald-500/30 hover:scale-105"
            : active
            ? "border-cyan-400 bg-navy-900 shadow-cyan-500/40 hover:scale-110 hover:shadow-cyan-500/60 ring-4 ring-cyan-400/20"
            : "border-gray-300 bg-gray-400 dark:border-navy-700 dark:bg-navy-800"
        }`}
      >
        <img src={image(module.cover_key)} alt="" className="absolute inset-0 h-full w-full object-cover opacity-85" />
        <span className="relative z-10 text-2xl font-black text-white drop-shadow-lg">
          {locked ? "🔒" : passed ? "✓" : order + 1}
        </span>
        {topics.length > 1 ? (
          <span className="absolute inset-1 rounded-full border-2 border-dashed border-white/70" />
        ) : null}
      </button>

      {/* Info card */}
      <div
        className={`min-w-0 flex-1 rounded-2xl border p-4 transition-all ${
          passed
            ? "border-emerald-400/30 bg-emerald-500/5 dark:bg-emerald-500/10"
            : active
            ? "border-cyan-400/30 bg-cyan-500/5 dark:bg-cyan-500/10 shadow-sm"
            : "border-line bg-white/50 dark:border-white/10 dark:bg-white/5"
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-black text-navy-900 dark:text-white truncate">{module.title}</h3>
          {passed ? (
            <span className="text-xs font-bold text-amber-500">{Array.from({ length: stars }, () => "⭐").join("")}</span>
          ) : (
            <span className="text-xs font-bold text-ink-500 dark:text-navy-300">{score}%</span>
          )}
        </div>
        {topics.length ? (
          <p className="mt-1 text-xs text-cyan-700 dark:text-cyan-300 truncate">{topics.join(" · ")}</p>
        ) : null}
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-ink-500 dark:text-navy-300">
          <span>{lessons.length} ta savol/test · {module.passing_score || 70}% o'tish</span>
          {module.reward_coins > 0 ? (
            <span className="font-bold text-amber-600 dark:text-amber-400">💰 +{module.reward_coins} coin</span>
          ) : null}
        </div>
        {active ? (
          <button
            onClick={onStart}
            type="button"
            className="mt-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-4 py-1.5 text-xs font-black text-white shadow-md transition hover:from-cyan-600 hover:to-blue-700"
          >
            Boshlash →
          </button>
        ) : null}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   LESSON PLAYER MODAL — Duolingo-style test player
   ═══════════════════════════════════════════════════════════════════════════════ */

function LessonPlayerModal({ module, apiFetch, onClose }: { module: Row; apiFetch: ApiFetch; onClose: () => void }) {
  const lessons = Array.isArray(module.lessons) ? module.lessons : [];
  const [currentIndex, setCurrentIndex] = useState(0);
  const [question, setQuestion] = useState<Row | null>(null);
  const [selected, setSelected] = useState("");
  const [result, setResult] = useState<Row | null>(null);
  const [loading, setLoading] = useState(false);
  const [score, setScore] = useState(0);
  const [total, setTotal] = useState(0);
  const [finished, setFinished] = useState(false);
  const [moduleResult, setModuleResult] = useState<Row | null>(null);
  const [error, setError] = useState("");

  const loadLesson = useCallback(async (index: number) => {
    if (index >= lessons.length) {
      setFinished(true);
      return;
    }
    const lesson = lessons[index];
    setLoading(true);
    setSelected("");
    setResult(null);
    setError("");
    try {
      const data = await apiFetch(`/student/learning-lessons/${lesson.id}`);
      setQuestion(data?.question_payload || data || null);
    } catch (e) {
      setError(errorText(e, "Dars yuklanmadi"));
    } finally {
      setLoading(false);
    }
  }, [lessons, apiFetch]);

  useEffect(() => {
    if (lessons.length > 0) {
      void loadLesson(0);
    } else {
      setFinished(true);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async () => {
    if (!selected || result || !question) return;
    const lesson = lessons[currentIndex];
    const correct = String(question?.correct_answer || "").trim().toLowerCase() === selected.trim().toLowerCase();
    const newScore = score + (correct ? 1 : 0);
    const newTotal = total + 1;
    setScore(newScore);
    setTotal(newTotal);
    setLoading(true);
    try {
      const lessonPassScore = correct ? 100 : 0;
      const submitResult = await apiFetch(`/student/learning-lessons/${lesson.id}/submit`, {
        method: "POST",
        body: { score: lessonPassScore, answers: [{ question: question?.question, selected, correct }] },
      });
      setResult({ correct, explanation: question?.explanation || "", ...submitResult });
      if (submitResult?.module_progress?.passed) {
        setModuleResult(submitResult);
      }
    } catch {
      setResult({ correct, explanation: question?.explanation || "" });
    } finally {
      setLoading(false);
    }
  };

  const next = () => {
    const nextIdx = currentIndex + 1;
    setCurrentIndex(nextIdx);
    void loadLesson(nextIdx);
  };

  const progressPercent = lessons.length ? Math.round(((currentIndex + (result ? 1 : 0)) / lessons.length) * 100) : 0;

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-navy-950/80 p-4 backdrop-blur-sm animate-fade-in">
      <div className="relative flex max-h-[92vh] w-full max-w-lg flex-col overflow-hidden rounded-3xl bg-white shadow-2xl dark:bg-navy-900 border border-line dark:border-white/10">
        {/* Header with progress bar */}
        <div className="flex items-center gap-3 border-b border-line p-4 dark:border-white/10">
          <button
            onClick={onClose}
            type="button"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-ink-500 transition hover:bg-rose-500/10 hover:text-rose-600"
          >
            ✕
          </button>
          <div className="h-3 min-w-0 flex-1 overflow-hidden rounded-full bg-gray-200 dark:bg-navy-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-emerald-400 transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <span className="text-xs font-black text-ink-500 dark:text-navy-300">
            {Math.min(currentIndex + 1, lessons.length)}/{lessons.length}
          </span>
        </div>

        {/* Content body */}
        <div className="min-h-0 flex-1 overflow-y-auto p-5 sm:p-6">
          {error ? (
            <div className="rounded-xl bg-rose-500/10 p-4 text-sm text-rose-700 dark:text-rose-200">{error}</div>
          ) : null}

          {loading && !question ? (
            <div className="grid min-h-48 place-items-center">
              <div className="h-10 w-10 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent" />
            </div>
          ) : null}

          {finished ? (
            <div className="py-8 text-center">
              <div className="mx-auto mb-4 grid h-24 w-24 place-items-center rounded-full bg-gradient-to-br from-cyan-400 to-emerald-400 text-3xl font-black text-white shadow-xl">
                {Math.round((score / Math.max(total, 1)) * 100)}%
              </div>
              <h2 className="text-2xl font-black text-navy-900 dark:text-white">Modul tugadi!</h2>
              <p className="mt-2 text-sm text-ink-500 dark:text-navy-300">{score}/{total} to'g'ri javob berildi</p>

              {moduleResult?.module_progress?.passed || (total > 0 && Math.round((score / total) * 100) >= (module.passing_score || 70)) ? (
                <div className="mt-4 rounded-2xl bg-emerald-500/15 p-4 text-sm font-bold text-emerald-800 dark:text-emerald-200 border border-emerald-500/20">
                  🎉 Modul muvaffaqiyatli yakunlandi!
                </div>
              ) : null}

              {moduleResult?.reward_coins > 0 || (module.reward_coins > 0 && Math.round((score / Math.max(total, 1)) * 100) >= (module.passing_score || 70)) ? (
                <div className="mt-3 rounded-2xl bg-amber-400/15 p-4 text-sm font-black text-amber-800 dark:text-amber-200 border border-amber-400/20">
                  💰 +{moduleResult?.reward_coins || module.reward_coins} D'Coin hisobingizga qo'shildi!
                </div>
              ) : null}

              {moduleResult?.track_completed ? (
                <div className="mt-3 rounded-2xl bg-purple-500/15 p-4 text-sm font-bold text-purple-800 dark:text-purple-200 border border-purple-500/20">
                  🎓 Tabriklaymiz! Barcha modullar tugadi va Track sertifikatingiz berildi!
                </div>
              ) : (
                <div className="mt-3 rounded-2xl bg-blue-500/10 p-3 text-xs font-medium text-blue-700 dark:text-blue-300 border border-blue-500/20">
                  ℹ️ Sertifikat ushbu trackdagi barcha modullar to'liq yakunlanganda beriladi.
                </div>
              )}

              <button onClick={onClose} type="button" className="btn btn-primary mt-6 w-full">
                Yo'lga qaytish
              </button>
            </div>
          ) : null}

          {question && !finished ? (
            <div>
              <div className="flex items-center justify-between">
                <span className="rounded-full bg-cyan-500/10 px-3 py-1 text-xs font-black text-cyan-700 dark:text-cyan-300">
                  {question.test_type === "true_false"
                    ? "To'g'ri / Noto'g'ri"
                    : question.test_type === "fill_blank"
                    ? "Bo'sh joyni to'ldiring"
                    : question.test_type === "word_order"
                    ? "So'z tartibi"
                    : question.test_type === "matching"
                    ? "Moslashtiring"
                    : "To'g'ri javobni tanlang"}
                </span>
                <span className="text-xs font-bold text-ink-400 dark:text-navy-400">
                  {lessons[currentIndex]?.title || `Savol ${currentIndex + 1}`}
                </span>
              </div>

              <h3 className="mt-4 text-lg font-bold leading-7 text-navy-900 dark:text-white">
                {question.question}
              </h3>

              {/* If question has audio (listening/dictation), render audio player */}
              {question.audio_url ? (
                <div className="mt-4 rounded-2xl bg-cyan-500/10 p-3.5 border border-cyan-400/30">
                  <div className="flex items-center gap-2 mb-2 text-xs font-black text-cyan-700 dark:text-cyan-300">
                    <span>🎧 Audioni diqqat bilan eshiting:</span>
                  </div>
                  <audio controls src={question.audio_url} className="w-full h-10 rounded-xl" />
                </div>
              ) : null}

              {/* Test question interactive input based on type */}
              {question.test_type === "fill_blank" && (!question.options || question.options.length < 2) ? (
                <div className="mt-6 space-y-3">
                  <input
                    type="text"
                    value={selected}
                    onChange={(e) => setSelected(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && !result && void submit()}
                    disabled={Boolean(result)}
                    placeholder="Javobingizni shu yerga yozing..."
                    className="w-full rounded-2xl border-2 border-line bg-surface-soft p-4 text-base font-bold text-navy-900 focus:border-cyan-400 focus:outline-none dark:border-white/10 dark:bg-white/5 dark:text-white"
                  />
                  <p className="text-xs text-ink-400 dark:text-navy-400">
                    Javobni yozib "Tekshirish" tugmasini bosing yoki Enter'ni bosing.
                  </p>
                </div>
              ) : question.test_type === "true_false" ? (
                <div className="mt-6 grid grid-cols-2 gap-3">
                  {["To'g'ri", "Noto'g'ri"].map((opt) => {
                    const isSelected = selected.toLowerCase() === opt.toLowerCase();
                    const isCorrect = result && opt.toLowerCase() === String(question.correct_answer || "").trim().toLowerCase();
                    const isWrong = result && isSelected && !isCorrect;

                    return (
                      <button
                        key={opt}
                        disabled={Boolean(result)}
                        type="button"
                        onClick={() => setSelected(opt)}
                        className={`rounded-2xl border-2 p-5 text-center text-base font-black transition-all ${
                          isCorrect
                            ? "border-emerald-400 bg-emerald-500/15 text-emerald-900 dark:text-emerald-100"
                            : isWrong
                            ? "border-rose-400 bg-rose-500/15 text-rose-900 dark:text-rose-100"
                            : isSelected
                            ? "border-cyan-400 bg-cyan-500/15 text-navy-900 dark:text-white shadow-md scale-102"
                            : "border-line bg-white/50 hover:border-cyan-400 dark:border-white/10 dark:bg-white/5"
                        }`}
                      >
                        <span className="text-xl mr-2">{opt === "To'g'ri" ? "✓" : "✕"}</span>
                        {opt}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div className="mt-6 grid gap-2.5">
                  {(question.options || []).map((opt: string, i: number) => {
                    const isSelected = selected === opt;
                    const isCorrect = result && opt.trim().toLowerCase() === String(question.correct_answer || "").trim().toLowerCase();
                    const isWrong = result && isSelected && !isCorrect;

                    return (
                      <button
                        key={i}
                        disabled={Boolean(result)}
                        type="button"
                        onClick={() => setSelected(opt)}
                        className={`rounded-2xl border-2 p-4 text-left text-sm font-semibold transition-all ${
                          isCorrect
                            ? "border-emerald-400 bg-emerald-500/15 text-emerald-900 dark:text-emerald-100"
                            : isWrong
                            ? "border-rose-400 bg-rose-500/15 text-rose-900 dark:text-rose-100"
                            : isSelected
                            ? "border-cyan-400 bg-cyan-500/10 text-navy-900 dark:text-white shadow-sm"
                            : "border-line bg-white/50 hover:border-cyan-400 dark:border-white/10 dark:bg-white/5"
                        }`}
                      >
                        <span className="mr-3 inline-grid h-7 w-7 place-items-center rounded-xl bg-surface-soft text-xs font-black text-navy-800 dark:bg-white/10 dark:text-white">
                          {String.fromCharCode(65 + i)}
                        </span>
                        {opt}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          ) : null}

          {/* Feedback drawer */}
          {result && !finished ? (
            <div className={`mt-6 rounded-2xl p-4 border ${result.correct ? "border-emerald-400/30 bg-emerald-500/10" : "border-rose-400/30 bg-rose-500/10"}`}>
              <div className="flex items-center gap-2.5">
                <span className="text-2xl">{result.correct ? "🎉" : "❌"}</span>
                <strong className={result.correct ? "text-emerald-800 dark:text-emerald-200" : "text-rose-800 dark:text-rose-200"}>
                  {result.correct ? "Ajoyib! To'g'ri javob!" : "Noto'g'ri javob"}
                </strong>
              </div>
              {!result.correct ? (
                <p className="mt-2 text-sm text-rose-700 dark:text-rose-300">
                  To'g'ri javob: <strong>{question?.correct_answer}</strong>
                </p>
              ) : null}
              {question?.explanation ? (
                <p className="mt-2 text-xs text-ink-600 dark:text-navy-300 border-t border-line/40 pt-2 dark:border-white/10">
                  💡 {question.explanation}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>

        {/* Action footer */}
        {!finished && question ? (
          <div className="border-t border-line p-4 dark:border-white/10 bg-surface-soft/40 dark:bg-navy-950/40">
            {!result ? (
              <button
                onClick={submit}
                type="button"
                disabled={!selected || loading}
                className="btn btn-primary w-full py-3 text-sm font-black disabled:opacity-40"
              >
                Tekshirish
              </button>
            ) : (
              <button
                onClick={next}
                type="button"
                className="btn btn-primary w-full py-3 text-sm font-black"
              >
                {currentIndex + 1 < lessons.length ? "Keyingi savol →" : "Natijani ko'rish"}
              </button>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   STAFF VIEW — Track/Module/Lesson management
   ═══════════════════════════════════════════════════════════════════════════════ */

export function StaffLearningPaths({ apiFetch }: { apiFetch: ApiFetch }) {
  const t = useWebT();
  const [tracks, setTracks] = useState<Row[]>([]);
  const [selected, setSelected] = useState<Row | null>(null);
  const [title, setTitle] = useState("");
  const [moduleTitle, setModuleTitle] = useState("");
  const [topics, setTopics] = useState("");
  const [rewardCoins, setRewardCoins] = useState(0);
  const [cover, setCover] = useState("star");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [editModuleId, setEditModuleId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editTopics, setEditTopics] = useState("");
  const [editRewardCoins, setEditRewardCoins] = useState(0);

  const load = async () => {
    try {
      const data = await apiFetch("/staff/learning-tracks");
      const items = Array.isArray(data?.items) ? data.items : [];
      setTracks(items);
      setSelected((value) => items.find((x: Row) => x.id === value?.id) || items[0] || null);
    } catch (e) {
      setError(errorText(e, "Tracklar yuklanmadi."));
    }
  };

  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const create = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    try {
      await apiFetch("/staff/learning-tracks", {
        method: "POST",
        body: { title: title.trim(), passing_score: 70 },
      });
      setTitle("");
      await load();
    } catch (e) {
      setError(errorText(e, "Track yaratilmadi."));
    } finally {
      setBusy(false);
    }
  };

  const addModule = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected || !moduleTitle.trim()) return;
    setBusy(true);
    try {
      await apiFetch(`/staff/learning-tracks/${selected.id}/modules`, {
        method: "POST",
        body: {
          title: moduleTitle.trim(),
          cover_key: cover,
          position: (selected.modules || []).length,
          topic_keys: topics.split(",").map((value) => value.trim()).filter(Boolean),
          reward_coins: rewardCoins,
        },
      });
      setModuleTitle("");
      setTopics("");
      setRewardCoins(0);
      await load();
    } catch (e) {
      setError(errorText(e, "Modul qo'shilmadi."));
    } finally {
      setBusy(false);
    }
  };

  const deleteTrack = async () => {
    if (!selected || !window.confirm(`"${selected.title}" track va barcha unga tegishli modullar o'chirilsinmi?`)) return;
    setBusy(true);
    try {
      await apiFetch(`/staff/learning-tracks/${selected.id}`, { method: "DELETE" });
      setSelected(null);
      await load();
    } catch (e) {
      setError(errorText(e, "Track o'chirilmadi."));
    } finally {
      setBusy(false);
    }
  };

  const updateModule = async (moduleId: number) => {
    setBusy(true);
    try {
      await apiFetch(`/staff/learning-modules/${moduleId}`, {
        method: "PATCH",
        body: {
          title: editTitle.trim(),
          topic_keys: editTopics.split(",").map((v) => v.trim()).filter(Boolean),
          reward_coins: editRewardCoins,
        },
      });
      setEditModuleId(null);
      await load();
    } catch (e) {
      setError(errorText(e, "Modul saqlanmadi."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="mx-auto w-full max-w-6xl p-4 sm:p-6">
      <header className="premium-card p-5 sm:p-7">
        <p className="text-xs font-black uppercase tracking-[.18em] text-cyan-600 dark:text-cyan-300">Diamond Learning Path</p>
        <h1 className="mt-2 text-2xl font-black text-navy-900 dark:text-white">{t("learning.staff.title", "Learning Path boshqaruvi")}</h1>
        <p className="mt-2 text-sm text-ink-600 dark:text-navy-300">Duolingo uslubida track, ketma-ket modul va sertifikat yo'lini yarating.</p>
      </header>

      {error ? <p className="mt-4 rounded-xl bg-rose-500/10 p-3 text-sm text-rose-700">{error}</p> : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-[320px_1fr]">
        {/* Track sidebar */}
        <aside className="premium-card p-4">
          <form onSubmit={create} className="space-y-3">
            <h2 className="font-black text-navy-900 dark:text-white text-base">Yangi track</h2>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full rounded-xl border border-line bg-transparent p-3 text-sm dark:border-white/10"
              placeholder="Track nomi"
            />
            <p className="text-xs text-ink-500 dark:text-navy-300">Fan teacher profilingizdan avtomatik olinadi.</p>
            <button disabled={busy} className="btn btn-primary w-full">Track yaratish</button>
          </form>

          <div className="mt-6 border-t border-line pt-4 dark:border-white/10 space-y-2">
            <p className="text-xs font-black uppercase tracking-wide text-ink-500 dark:text-navy-400 mb-3">Mavjud tracklar</p>
            {tracks.map((track, index) => (
              <button
                key={track.id}
                onClick={() => setSelected(track)}
                className={`flex w-full items-center gap-3 rounded-xl border p-3 text-left transition ${
                  selected?.id === track.id ? "border-cyan-400 bg-cyan-500/10 shadow-sm" : "border-line hover:border-cyan-300 dark:border-white/10"
                }`}
              >
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-cyan-500/15 text-sm font-black text-cyan-700 dark:text-cyan-300">
                  {index + 1}
                </span>
                <span className="min-w-0 flex-1">
                  <b className="block truncate text-sm text-navy-900 dark:text-white">{track.title}</b>
                  <small className="text-xs text-ink-500 dark:text-navy-300">{track.subject} · {track.passing_score}% o'tish</small>
                </span>
              </button>
            ))}
          </div>
        </aside>

        {/* Selected track main view */}
        <main className="premium-card p-5 sm:p-6">
          {selected ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4 dark:border-white/10">
                <div>
                  <p className="text-xs font-black uppercase tracking-wide text-cyan-600 dark:text-cyan-300">{selected.subject} · {selected.status}</p>
                  <h2 className="mt-1 text-2xl font-black text-navy-900 dark:text-white">{selected.title}</h2>
                </div>
                <button
                  type="button"
                  disabled={busy}
                  onClick={deleteTrack}
                  className="rounded-xl border border-rose-400/40 px-4 py-2 text-xs font-bold text-rose-600 hover:bg-rose-500/10 dark:text-rose-300 transition"
                >
                  Trackni o'chirish
                </button>
              </div>

              {/* Certificate settings */}
              <TrackSettings track={selected} apiFetch={apiFetch} onSaved={load} />

              {/* Add module form */}
              <form onSubmit={addModule} className="mt-6 rounded-2xl border border-line p-5 dark:border-white/10 bg-surface-soft/20 dark:bg-white/5">
                <h3 className="font-black text-navy-900 dark:text-white text-base">+ Yangi Modul qo'shish</h3>
                <p className="mt-1 text-xs text-ink-500 dark:text-navy-300">Har bir modul Duolingo bosqichidek dumaloq belgi bilan ko'rinadi.</p>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <input
                    value={moduleTitle}
                    onChange={(e) => setModuleTitle(e.target.value)}
                    className="rounded-xl border border-line bg-transparent p-3 text-sm dark:border-white/10"
                    placeholder="Modul nomi (masalan: 1-bosqich)"
                  />
                  <input
                    value={topics}
                    onChange={(e) => setTopics(e.target.value)}
                    className="rounded-xl border border-line bg-transparent p-3 text-sm dark:border-white/10"
                    placeholder="Mavzular (vergul bilan): Present Simple, Fe'llar"
                  />
                </div>
                <div className="mt-3">
                  <label className="text-xs font-bold text-ink-600 dark:text-navy-300">
                    Muvaffaqiyatli tugatilganda beriladigan D'Coinlar soni
                    <input
                      value={rewardCoins}
                      type="number"
                      min="0"
                      max="10000"
                      onChange={(e) => setRewardCoins(Number(e.target.value))}
                      className="mt-1 w-full sm:w-48 rounded-xl border border-line bg-transparent p-2.5 text-sm dark:border-white/10"
                      placeholder="0"
                    />
                  </label>
                </div>
                <div className="mt-4 flex flex-wrap items-center justify-between gap-4 border-t border-line/40 pt-4 dark:border-white/10">
                  <div>
                    <p className="text-xs font-bold text-ink-500 mb-2">Modul belgisi (ikonka):</p>
                    <CoverPicker value={cover} onChange={setCover} />
                  </div>
                  <button disabled={busy} className="btn btn-primary self-end">+ Modul yaratish</button>
                </div>
              </form>

              {/* Modules list */}
              <div className="mt-8 space-y-4">
                <h3 className="text-lg font-black text-navy-900 dark:text-white">Modullar va Testlar ro'yxati</h3>
                {(selected.modules || []).map((module: Row, index: number) => (
                  <div key={module.id} className="rounded-2xl border border-line p-4 dark:border-white/10 transition hover:shadow-sm">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <img src={image(module.cover_key)} alt="" className="h-14 w-14 rounded-full object-cover border-2 border-cyan-400" />
                        <div>
                          <p className="font-black text-navy-900 dark:text-white text-base">
                            {index + 1}. {module.title}
                          </p>
                          <p className="text-xs text-ink-500 dark:text-navy-300 mt-0.5">
                            {(module.topic_keys || []).join(" · ") || "Mavzu kiritilmagan"} · {(module.lessons || []).length} dars/savol
                            {module.reward_coins > 0 ? ` · 💰 +${module.reward_coins} coin` : ""}
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          if (editModuleId === module.id) {
                            setEditModuleId(null);
                          } else {
                            setEditModuleId(module.id);
                            setEditTitle(module.title);
                            setEditTopics((module.topic_keys || []).join(", "));
                            setEditRewardCoins(Number(module.reward_coins || 0));
                          }
                        }}
                        className="btn btn-soft text-xs"
                      >
                        {editModuleId === module.id ? "Bekor qilish" : "✏️ Tahrirlash"}
                      </button>
                    </div>

                    {/* Inline edit form */}
                    {editModuleId === module.id ? (
                      <div className="mt-4 rounded-xl bg-surface-soft p-4 dark:bg-white/5 space-y-3">
                        <div className="grid gap-3 sm:grid-cols-2">
                          <input
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            className="rounded-xl border border-line bg-transparent p-2.5 text-xs dark:border-white/10"
                            placeholder="Modul nomi"
                          />
                          <input
                            value={editTopics}
                            onChange={(e) => setEditTopics(e.target.value)}
                            className="rounded-xl border border-line bg-transparent p-2.5 text-xs dark:border-white/10"
                            placeholder="Mavzular (vergul bilan)"
                          />
                        </div>
                        <div className="flex items-center gap-3">
                          <label className="text-xs font-bold">
                            Coin:
                            <input
                              value={editRewardCoins}
                              type="number"
                              min="0"
                              onChange={(e) => setEditRewardCoins(Number(e.target.value))}
                              className="ml-2 w-28 rounded-lg border border-line bg-transparent p-1.5 text-xs dark:border-white/10"
                            />
                          </label>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => void updateModule(module.id)}
                            className="btn btn-primary text-xs ml-auto"
                          >
                            Saqlash
                          </button>
                        </div>
                      </div>
                    ) : null}

                    {/* Lesson editor component */}
                    <LessonEditor module={module} apiFetch={apiFetch} onSaved={load} />
                  </div>
                ))}
                {!(selected.modules || []).length ? (
                  <p className="text-sm text-ink-500 dark:text-navy-300 text-center py-6">
                    Bu trackda hali modul yo'q. Yuqoridagi formadan birinchi modulni qo'shing.
                  </p>
                ) : null}
              </div>
            </>
          ) : (
            <p className="text-sm text-ink-500 py-10 text-center">Track tanlang yoki chap tomondan yangi track yarating.</p>
          )}
        </main>
      </div>
    </section>
  );
}

function TrackSettings({ track, apiFetch, onSaved }: { track: Row; apiFetch: ApiFetch; onSaved: () => Promise<void> }) {
  const layer = (track.certificate_layers || [])[0] || {};
  const [score, setScore] = useState(String(track.passing_score || 70));

  // Auto-detect template matching teacher's subject: Russian if subject contains rus, otherwise English
  const detectSubjectTemplate = (subj?: string) => {
    const s = String(subj || "").toLowerCase();
    if (s.includes("rus") || s.includes("рус")) return "russian";
    return "english";
  };

  const initialTemplate = track.certificate_template_key || detectSubjectTemplate(track.subject);
  const [template, setTemplate] = useState(initialTemplate);
  const [text, setText] = useState(String(layer.text || ""));
  const [x, setX] = useState(Number(layer.x ?? 0.5));
  const [y, setY] = useState(Number(layer.y ?? 0.5));
  const [size, setSize] = useState(Number(layer.font_size ?? 16));
  const [color, setColor] = useState(layer.color === "ink" ? "ink" : "blue");
  const [bold, setBold] = useState(Boolean(layer.bold));
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const next = (track.certificate_layers || [])[0] || {};
    setScore(String(track.passing_score || 70));
    setTemplate(track.certificate_template_key || detectSubjectTemplate(track.subject));
    setText(String(next.text || ""));
    setX(Number(next.x ?? 0.5));
    setY(Number(next.y ?? 0.5));
    setSize(Number(next.font_size ?? 16));
    setColor(next.color === "ink" ? "ink" : "blue");
    setBold(Boolean(next.bold));
  }, [track]);

  const applyPreset = (preset: "english" | "russian" | "math" | "professional") => {
    if (preset === "english") {
      setTemplate("english");
      setText("English Language Mastery Track");
      setSize(18);
      setColor("blue");
      setBold(true);
      setX(0.5);
      setY(0.44);
    } else if (preset === "russian") {
      setTemplate("russian");
      setText("Курс практического русского языка");
      setSize(18);
      setColor("blue");
      setBold(true);
      setX(0.5);
      setY(0.44);
    } else if (preset === "math") {
      setTemplate("english");
      setText("Mathematics & Logic Mastery Track");
      setSize(18);
      setColor("ink");
      setBold(true);
      setX(0.5);
      setY(0.44);
    } else if (preset === "professional") {
      setTemplate(detectSubjectTemplate(track.subject));
      setText(`${track.title || "Diamond Track"} · Certified Graduate`);
      setSize(18);
      setColor("blue");
      setBold(true);
      setX(0.5);
      setY(0.44);
    }
  };

  const place = (event: MouseEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setX(Math.min(0.95, Math.max(0.05, (event.clientX - rect.left) / rect.width)));
    setY(Math.min(0.95, Math.max(0.05, 1 - (event.clientY - rect.top) / rect.height)));
  };

  const save = async () => {
    setBusy(true);
    try {
      await apiFetch(`/staff/learning-tracks/${track.id}`, {
        method: "PATCH",
        body: {
          passing_score: Number(score),
          certificate_template_key: template,
          certificate_layers: text.trim() ? [{ text: text.trim(), x, y, font_size: size, color, bold }] : [],
        },
      });
      await onSaved();
    } finally {
      setBusy(false);
    }
  };

  const previewColor = color === "blue" ? "#2138b8" : "#1f294d";

  return (
    <section className="mt-5 rounded-2xl border border-cyan-500/20 bg-cyan-500/5 p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-black text-navy-900 dark:text-white uppercase tracking-wide">
          Sertifikat va O'tish Sozlamalari (Faqat butun track tugaganda beriladi)
        </h3>
        <span className="rounded-full bg-cyan-500/15 px-2.5 py-0.5 text-xs font-bold text-cyan-700 dark:text-cyan-300">
          Fan: {track.subject || "General"}
        </span>
      </div>

      {/* Ready Templates / Tayyor shablonlar */}
      <div className="mt-3 rounded-xl border border-line bg-white/70 p-3 dark:border-white/10 dark:bg-white/5">
        <p className="text-xs font-black uppercase text-ink-500 dark:text-navy-300 mb-2">
          ✨ Tayyor shablonlar (bitta bosishda sozlash):
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => applyPreset("english")}
            className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-1.5 text-xs font-bold text-cyan-800 dark:text-cyan-200 hover:bg-cyan-500/20 transition"
          >
            🇬🇧 English Track
          </button>
          <button
            type="button"
            onClick={() => applyPreset("russian")}
            className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-3 py-1.5 text-xs font-bold text-indigo-800 dark:text-indigo-200 hover:bg-indigo-500/20 transition"
          >
            🇷🇺 Русский язык
          </button>
          <button
            type="button"
            onClick={() => applyPreset("math")}
            className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-bold text-amber-800 dark:text-amber-200 hover:bg-amber-500/20 transition"
          >
            📐 Matematika / Aniq fanlar
          </button>
          <button
            type="button"
            onClick={() => applyPreset("professional")}
            className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-bold text-emerald-800 dark:text-emerald-200 hover:bg-emerald-500/20 transition"
          >
            🏆 Fan kursi bitiruvchisi
          </button>
        </div>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="text-xs font-bold">
          Track o'tish bali (%)
          <input
            value={score}
            min="1"
            max="100"
            type="number"
            onChange={(e) => setScore(e.target.value)}
            className="mt-1 w-full rounded-lg border border-line bg-transparent p-2.5 dark:border-white/10"
          />
        </label>
        <label className="text-xs font-bold">
          Sertifikat tili (O'qituvchi fani: {track.subject || "General"})
          <select
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
            className="mt-1 w-full rounded-lg border border-line bg-transparent p-2.5 dark:border-white/10 font-medium"
          >
            <option value="english">English (Inglizcha sertifikat)</option>
            <option value="russian">Русский (Ruscha sertifikat)</option>
          </select>
        </label>
      </div>

      <label className="mt-3 block text-xs font-bold">
        Sertifikatdagi qo'shimcha matn (kurs yo'nalishi)
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="mt-1 w-full rounded-lg border border-line bg-transparent p-2.5 dark:border-white/10"
          placeholder="Masalan: English Language Mastery Track"
        />
      </label>

      <div className="mt-3 grid gap-3 sm:grid-cols-4">
        <label className="text-xs font-bold">
          Shrift o'lchami
          <input
            type="number"
            min="8"
            max="42"
            value={size}
            onChange={(e) => setSize(Number(e.target.value))}
            className="mt-1 w-full rounded-lg border border-line bg-transparent p-2 dark:border-white/10"
          />
        </label>
        <label className="text-xs font-bold">
          Matn rangi
          <select
            value={color}
            onChange={(e) => setColor(e.target.value)}
            className="mt-1 w-full rounded-lg border border-line bg-transparent p-2 dark:border-white/10"
          >
            <option value="blue">Ko'k (#2138b8)</option>
            <option value="ink">Qora-ko'k (#1f294d)</option>
          </select>
        </label>
        <label className="flex items-end gap-2 pb-2 text-xs font-bold">
          <input type="checkbox" checked={bold} onChange={(e) => setBold(e.target.checked)} />
          Qalin shrift (Bold)
        </label>
        <button
          type="button"
          disabled={busy}
          onClick={() => void save()}
          className="btn btn-primary text-xs self-end py-2.5"
        >
          {busy ? "Saqlanmoqda…" : "Sozlamani saqlash"}
        </button>
      </div>

      <div className="mt-4 flex items-center justify-between">
        <p className="text-xs font-bold text-ink-600 dark:text-navy-300">
          👇 Sertifikat maketi — uzun chiziq ustiga Ism-familiya, pastiga sana tushadi:
        </p>
        <span className="text-xs font-mono font-bold text-cyan-600 dark:text-cyan-300">
          Qo'shimcha matn o'rni: X: {Math.round(x * 100)}%, Y: {Math.round((1 - y) * 100)}%
        </span>
      </div>

      {/* Live Certificate SVG Interactive Canvas */}
      <div
        onClick={place}
        role="button"
        tabIndex={0}
        className="relative mt-2 aspect-[1123/794] cursor-crosshair overflow-hidden rounded-2xl border-2 border-line bg-white shadow-xl select-none"
      >
        <img
          src={`/learning-paths/certificate-${template}.svg`}
          alt="Certificate preview"
          className="pointer-events-none absolute inset-0 h-full w-full object-cover"
        />

        {/* Long line indicator & Student Full Name Preview (centered right above line x1=249, x2=854, y=354.5) */}
        <div
          className="pointer-events-none absolute left-1/2 -translate-x-1/2 -translate-y-1/2 text-center"
          style={{ top: "43.5%" }}
        >
          <span className="inline-block rounded-md bg-white/90 px-3 py-1 font-serif text-sm sm:text-base font-black text-navy-950 shadow border border-cyan-500/40 tracking-wide">
            [ TALABA ISM FAMILIYASI ]
          </span>
          <p className="text-[10px] font-bold text-cyan-800 dark:text-cyan-800 mt-0.5">
            ↑ Uzun chiziq ustidagi ism-familiya joyi
          </p>
        </div>

        {/* Course / Track Title directly under the line */}
        <div
          className="pointer-events-none absolute left-1/2 -translate-x-1/2 -translate-y-1/2 text-center"
          style={{ top: "50%" }}
        >
          <span className="inline-block rounded bg-white/80 px-2 py-0.5 text-xs font-bold text-indigo-900 shadow-sm">
            {track.title || "Diamond Education Track"}
          </span>
        </div>

        {/* Date line preview (bottom-left line x=147.5, y=631) */}
        <div
          className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 text-center"
          style={{ left: "13.5%", top: "77.5%" }}
        >
          <span className="inline-block rounded bg-white/90 px-2 py-0.5 font-mono text-[11px] font-black text-navy-950 border border-cyan-500/40 shadow-sm">
            {new Date().toLocaleDateString("uz-UZ")}
          </span>
          <p className="text-[9px] font-bold text-cyan-800 dark:text-cyan-800 mt-0.5">
            Sana o'rni
          </p>
        </div>

        {/* Live placed custom teacher text */}
        {text.trim() ? (
          <span
            style={{
              left: `${x * 100}%`,
              top: `${(1 - y) * 100}%`,
              color: previewColor,
              fontSize: `${Math.max(10, size * 0.45)}px`,
              fontWeight: bold ? 700 : 400,
            }}
            className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 whitespace-nowrap drop-shadow bg-white/60 px-1 rounded"
          >
            {text}
          </span>
        ) : null}

        {/* Target indicator ring */}
        {text.trim() ? (
          <span
            className="pointer-events-none absolute h-6 w-6 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-cyan-500 animate-pulse"
            style={{ left: `${x * 100}%`, top: `${(1 - y) * 100}%` }}
          />
        ) : null}
      </div>
    </section>
  );
}

async function uploadAudioFile(file: File): Promise<string | null> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/teacher/library/upload", {
    method: "POST",
    headers: { Authorization: `Bearer ${localStorage.getItem("diamond_token") || ""}` },
    body: form,
  });
  const data = await res.json().catch(() => ({}));
  return (data && (data.url || data.file_url)) || null;
}

const ALL_TEST_KINDS = [
  { key: "multiple_choice", label: "🔘 Ko'p variantli (MCQ)", needsAudio: false },
  { key: "true_false", label: "⚖️ To'g'ri / Noto'g'ri", needsAudio: false },
  { key: "fill_blank", label: "✏️ Bo'sh joyni to'ldirish", needsAudio: false },
  { key: "word_order", label: "🔤 So'z tartibi", needsAudio: false },
  { key: "matching", label: "🔗 Moslashtirish (Juftliklar)", needsAudio: false },
  { key: "listening", label: "🎧 Tinglab tushunish (Variantli)", needsAudio: true },
  { key: "dictation", label: "🎼 Diktant (Eshitib yozish)", needsAudio: true },
  { key: "listening_tf", label: "🎧 Listening: True / False / Not Given", needsAudio: true },
  { key: "listening_gap", label: "␣ Listening: Bo'sh joyni to'ldirish", needsAudio: true },
  { key: "listening_order", label: "🧩 Listening: So'zlar tartibi", needsAudio: true },
  { key: "spelling", label: "🔤 To'g'ri yozish (Imlo)", needsAudio: false },
  { key: "translation", label: "🔁 Tarjima", needsAudio: false },
  { key: "speak_sentence", label: "🎙️ Gap tuzib gapirish", needsAudio: false },
  { key: "write_sentence", label: "✍️ Gap tuzib yozish", needsAudio: false },
  { key: "guided_writing", label: "📝 Mavzu bo'yicha yozma mashq", needsAudio: false },
  { key: "reading_open", label: "📖 Matn bo'yicha ochiq savol", needsAudio: false },
  { key: "read_aloud", label: "🔊 Ovoz chiqarib o'qish", needsAudio: false },
  { key: "dialogue_completion", label: "💬 Dialogni to'ldirish", needsAudio: false },
  { key: "picture_description", label: "🖼️ Rasmni tasvirlash", needsAudio: false },
  { key: "passage_cloze", label: "📃 Matnni to'ldirish (so'zlar banki)", needsAudio: false },
];

function LessonEditor({ module, apiFetch, onSaved }: { module: Row; apiFetch: ApiFetch; onSaved: () => Promise<void> }) {
  const lessons = Array.isArray(module.lessons) ? module.lessons : [];
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [manualType, setManualType] = useState("multiple_choice");
  const [options, setOptions] = useState("");
  const [correct, setCorrect] = useState("");
  const [explanation, setExplanation] = useState("");
  const [audioUrl, setAudioUrl] = useState("");
  const [audioUploading, setAudioUploading] = useState(false);

  // Lesson Edit states
  const [editingLessonId, setEditingLessonId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editPrompt, setEditPrompt] = useState("");
  const [editType, setEditType] = useState("multiple_choice");
  const [editOptions, setEditOptions] = useState("");
  const [editCorrect, setEditCorrect] = useState("");
  const [editExplanation, setEditExplanation] = useState("");
  const [editAudioUrl, setEditAudioUrl] = useState("");
  const [editAudioUploading, setEditAudioUploading] = useState(false);

  // AI & Library states
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(5);
  const [types, setTypes] = useState("multiple_choice,true_false,fill_blank");
  const [busy, setBusy] = useState(false);
  const [showLibraryModal, setShowLibraryModal] = useState(false);

  const curKindMeta = ALL_TEST_KINDS.find((k) => k.key === manualType) || { needsAudio: false };
  const editKindMeta = ALL_TEST_KINDS.find((k) => k.key === editType) || { needsAudio: false };

  const startEdit = (lesson: Row) => {
    setEditingLessonId(Number(lesson.id));
    setEditTitle(String(lesson.title || ""));
    const p = (lesson.question_payload as Row) || {};
    setEditPrompt(String(p.question || ""));
    setEditType(String(p.test_type || lesson.source_version || "multiple_choice"));
    const opts = Array.isArray(p.options) ? p.options.join(" | ") : "";
    setEditOptions(opts);
    setEditCorrect(String(p.correct_answer || ""));
    setEditExplanation(String(p.explanation || ""));
    setEditAudioUrl(String(p.audio_url || ""));
  };

  const saveEdit = async () => {
    if (!editingLessonId) return;
    if (!editTitle.trim() || !editPrompt.trim()) {
      alert("Iltimos, dars nomi va savol matnini kiriting.");
      return;
    }
    if (editKindMeta.needsAudio && !editAudioUrl.trim()) {
      alert("Listening testi uchun audio fayl yuklash yoki audio URL kiritish shart!");
      return;
    }

    let choices: string[] = [];
    let answer = editCorrect.trim();

    if (editType === "true_false" || editType === "listening_tf") {
      choices = ["To'g'ri", "Noto'g'ri"];
      if (!answer) answer = "To'g'ri";
    } else if (editType === "multiple_choice" || editType === "listening") {
      choices = editOptions.split("|").map((x) => x.trim()).filter(Boolean);
      if (choices.length < 2) {
        alert("Variantli test uchun kamida 2 ta variant kiriting (| bilan ajrating).");
        return;
      }
      if (!choices.includes(answer)) {
        choices.push(answer);
      }
    } else if (editType === "matching") {
      choices = editOptions.split("|").map((x) => x.trim()).filter(Boolean);
      if (choices.length < 2) {
        alert("Moslashtirish uchun kamida 2 ta juftlik kiriting (masalan: olma = apple | kitob = book).");
        return;
      }
      if (!answer && choices.length) answer = choices[0];
    } else {
      choices = editOptions ? editOptions.split("|").map((x) => x.trim()).filter(Boolean) : [];
    }

    setBusy(true);
    try {
      await apiFetch(`/staff/learning-lessons/${editingLessonId}`, {
        method: "PATCH",
        body: {
          title: editTitle.trim(),
          question_payload: {
            question: editPrompt.trim(),
            options: choices,
            correct_answer: answer,
            explanation: editExplanation.trim(),
            test_type: editType,
            audio_url: editAudioUrl.trim() || null,
          },
        },
      });
      setEditingLessonId(null);
      await onSaved();
    } catch (err) {
      alert("Testni saqlashda xatolik: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setBusy(false);
    }
  };

  const deleteLesson = async (lessonId: number) => {
    if (!window.confirm("Ushbu test savolini moduldan o'chirmoqchimisiz?")) return;
    setBusy(true);
    try {
      await apiFetch(`/staff/learning-lessons/${lessonId}`, { method: "DELETE" });
      await onSaved();
    } catch (err) {
      alert("O'chirishda xatolik: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setBusy(false);
    }
  };

  const saveManual = async () => {
    if (!title.trim() || !prompt.trim()) {
      alert("Iltimos, dars nomi va savol matnini kiriting.");
      return;
    }
    if (curKindMeta.needsAudio && !audioUrl.trim()) {
      alert("Listening testi uchun audio fayl yuklash yoki audio URL kiritish shart!");
      return;
    }

    let choices: string[] = [];
    let answer = correct.trim();

    if (manualType === "true_false" || manualType === "listening_tf") {
      choices = ["To'g'ri", "Noto'g'ri"];
      if (!answer) answer = "To'g'ri";
    } else if (manualType === "multiple_choice" || manualType === "listening") {
      choices = options.split("|").map((x) => x.trim()).filter(Boolean);
      if (choices.length < 2) {
        alert("Variantli test uchun kamida 2 ta variant kiriting (| bilan ajrating).");
        return;
      }
      if (!choices.includes(answer)) {
        choices.push(answer);
      }
    } else if (manualType === "matching") {
      choices = options.split("|").map((x) => x.trim()).filter(Boolean);
      if (choices.length < 2) {
        alert("Moslashtirish uchun kamida 2 ta juftlik kiriting (masalan: olma = apple | kitob = book).");
        return;
      }
      if (!answer && choices.length) answer = choices[0];
    } else {
      choices = options ? options.split("|").map((x) => x.trim()).filter(Boolean) : [];
    }

    if (!answer && manualType !== "matching") {
      alert("Iltimos, to'g'ri javobni kiriting.");
      return;
    }

    setBusy(true);
    try {
      await apiFetch(`/staff/learning-modules/${module.id}/lessons`, {
        method: "POST",
        body: {
          title: title.trim(),
          source_kind: "manual",
          position: lessons.length,
          question_payload: {
            question: prompt.trim(),
            options: choices,
            correct_answer: answer,
            explanation: explanation.trim(),
            test_type: manualType,
            audio_url: audioUrl.trim() || null,
          },
        },
      });
      setTitle("");
      setPrompt("");
      setOptions("");
      setCorrect("");
      setExplanation("");
      setAudioUrl("");
      await onSaved();
    } catch (err) {
      alert("Test qo'shishda xatolik: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setBusy(false);
    }
  };

  const generate = async () => {
    if (!topic.trim()) return;
    setBusy(true);
    try {
      const result = await apiFetch(`/staff/learning-modules/${module.id}/ai-question`, {
        method: "POST",
        body: {
          topic: topic.trim(),
          question_count: count,
          test_types: types.split(",").map((value) => value.trim()).filter(Boolean),
        },
      });
      const items = Array.isArray(result?.items) ? result.items : (result ? [result] : []);
      if (!items.length) {
        alert("Diamondvoy savol yarata olmadi. Iltimos, boshqa mavzu bilan qayta urinib ko'ring.");
        return;
      }
      const basePos = lessons.length;
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        await apiFetch(`/staff/learning-modules/${module.id}/lessons`, {
          method: "POST",
          body: {
            title: item.title || `${topic.trim()} · ${i + 1}`,
            source_kind: "ai",
            position: basePos + i,
            question_payload: item.question_payload,
          },
        });
      }
      setTopic("");
      await onSaved();
    } catch (err) {
      alert("AI test yaratishda xatolik yuz berdi: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setBusy(false);
    }
  };

  const attachLibrary = async (contentId: number, cType = "library_node", qCount = count) => {
    if (!contentId) return;
    setBusy(true);
    try {
      await apiFetch(`/staff/learning-modules/${module.id}/library-test`, {
        method: "POST",
        body: { content_type: cType, content_id: contentId, question_count: qCount },
      });
      setShowLibraryModal(false);
      await onSaved();
    } catch (err) {
      alert("Material testini biriktirishda xatolik: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!window.confirm(`"${module.title}" moduli va uning barcha darslari o'chirilsinmi?`)) return;
    setBusy(true);
    try {
      await apiFetch(`/staff/learning-modules/${module.id}`, { method: "DELETE" });
      await onSaved();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-4 border-t border-line/60 pt-4 dark:border-white/10 space-y-4">
      {/* ─── Moduldagi mavjud testlar ro'yxati (Tahrirlash va O'chirish) ─── */}
      <div className="rounded-2xl border border-line p-4 dark:border-white/10 bg-white/70 dark:bg-navy-900/80">
        <div className="flex items-center justify-between">
          <p className="text-xs font-black uppercase text-navy-900 dark:text-white flex items-center gap-2">
            <span>📋 Moduldagi mavjud testlar ({lessons.length} ta)</span>
          </p>
          <span className="text-[10px] font-bold text-ink-500 dark:text-navy-300">
            Har bir testni tahrirlash yoki o'chirish mumkin
          </span>
        </div>

        <div className="mt-3 space-y-2.5">
          {lessons.length ? (
            lessons.map((lesson: Row, idx: number) => {
              const p = (lesson.question_payload as Row) || {};
              const qType = String(p.test_type || lesson.source_version || "multiple_choice");
              const isEditing = editingLessonId === lesson.id;
              const meta = ALL_TEST_KINDS.find((k) => k.key === qType) || { label: qType, needsAudio: false };

              return (
                <div
                  key={lesson.id}
                  className={`rounded-xl border p-3 transition ${
                    isEditing
                      ? "border-cyan-400 bg-cyan-500/5 shadow-sm"
                      : "border-line bg-surface-soft/40 hover:border-cyan-300 dark:border-white/10 dark:bg-white/5"
                  }`}
                >
                  {isEditing ? (
                    /* Inline Lesson Edit Form */
                    <div className="space-y-3">
                      <div className="flex items-center justify-between border-b border-line/40 pb-2 dark:border-white/10">
                        <span className="text-xs font-black text-cyan-700 dark:text-cyan-300">
                          ✏️ Testni tahrirlash (#{idx + 1})
                        </span>
                        <button
                          type="button"
                          onClick={() => setEditingLessonId(null)}
                          className="text-xs text-ink-500 hover:text-rose-500"
                        >
                          ✕ Bekor
                        </button>
                      </div>

                      <div className="grid gap-2 sm:grid-cols-2">
                        <input
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          className="rounded-xl border border-line bg-transparent p-2 text-xs dark:border-white/10 font-bold"
                          placeholder="Dars nomi"
                        />
                        <select
                          value={editType}
                          onChange={(e) => setEditType(e.target.value)}
                          className="rounded-xl border border-line bg-transparent p-2 text-xs font-semibold dark:border-white/10"
                        >
                          {ALL_TEST_KINDS.map((k) => (
                            <option key={k.key} value={k.key}>
                              {k.label}
                            </option>
                          ))}
                        </select>
                      </div>

                      {editKindMeta.needsAudio ? (
                        <div className="rounded-xl border border-cyan-400/40 bg-cyan-500/10 p-2.5 space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-[11px] font-black text-cyan-800 dark:text-cyan-200">
                              🎧 Audio biriktirish (Majburiy)
                            </span>
                            {editAudioUploading && <span className="text-[10px] text-cyan-600 animate-pulse">Yuklanmoqda...</span>}
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            <label className="btn btn-soft text-xs py-1 px-3 cursor-pointer">
                              📁 Yangi audio yuklash
                              <input
                                type="file"
                                accept="audio/*"
                                className="hidden"
                                onChange={async (e) => {
                                  const file = e.target.files?.[0];
                                  if (!file) return;
                                  setEditAudioUploading(true);
                                  try {
                                    const url = await uploadAudioFile(file);
                                    if (url) setEditAudioUrl(url);
                                  } finally {
                                    setEditAudioUploading(false);
                                  }
                                }}
                              />
                            </label>
                            <input
                              value={editAudioUrl}
                              onChange={(e) => setEditAudioUrl(e.target.value)}
                              placeholder="Audio URL (/homework/files/... yoki https://...)"
                              className="min-w-0 flex-1 rounded-xl border border-line bg-transparent p-1.5 text-xs dark:border-white/10"
                            />
                          </div>
                          {editAudioUrl ? (
                            <audio controls src={editAudioUrl} className="w-full h-8 mt-1" />
                          ) : null}
                        </div>
                      ) : null}

                      <textarea
                        value={editPrompt}
                        onChange={(e) => setEditPrompt(e.target.value)}
                        rows={2}
                        className="w-full rounded-xl border border-line bg-transparent p-2 text-xs dark:border-white/10"
                        placeholder="Savol matni..."
                      />

                      <div className="grid gap-2 sm:grid-cols-2">
                        <input
                          value={editOptions}
                          onChange={(e) => setEditOptions(e.target.value)}
                          className="rounded-xl border border-line bg-transparent p-2 text-xs dark:border-white/10"
                          placeholder="Variantlar: A | B | C | D (| bilan)"
                        />
                        <input
                          value={editCorrect}
                          onChange={(e) => setEditCorrect(e.target.value)}
                          className="rounded-xl border border-line bg-transparent p-2 text-xs dark:border-white/10"
                          placeholder="To'g'ri javob matni"
                        />
                      </div>

                      <input
                        value={editExplanation}
                        onChange={(e) => setEditExplanation(e.target.value)}
                        className="w-full rounded-xl border border-line bg-transparent p-2 text-xs dark:border-white/10"
                        placeholder="Tushuntirish / Izoh"
                      />

                      <div className="flex justify-end gap-2 pt-1">
                        <button
                          type="button"
                          onClick={() => setEditingLessonId(null)}
                          className="btn btn-soft text-xs"
                        >
                          Bekor qilish
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void saveEdit()}
                          className="btn btn-primary text-xs"
                        >
                          ✓ Saqlash
                        </button>
                      </div>
                    </div>
                  ) : (
                    /* Normal Lesson Card View */
                    <div>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-cyan-500/15 text-xs font-black text-cyan-700 dark:text-cyan-300">
                            {idx + 1}
                          </span>
                          <span className="font-bold text-xs text-navy-900 dark:text-white truncate">
                            {lesson.title}
                          </span>
                          <span className="rounded-full bg-cyan-500/10 px-2 py-0.5 text-[10px] font-bold text-cyan-700 dark:text-cyan-300">
                            {meta.label}
                          </span>
                          {p.audio_url ? (
                            <span className="rounded-full bg-amber-400/20 px-2 py-0.5 text-[10px] font-bold text-amber-800 dark:text-amber-200 flex items-center gap-1">
                              🎧 Audio
                            </span>
                          ) : null}
                          <span className="text-[10px] text-ink-400">
                            ({lesson.source_kind})
                          </span>
                        </div>

                        <div className="flex items-center gap-1.5 ml-auto">
                          <button
                            type="button"
                            onClick={() => startEdit(lesson)}
                            className="rounded-lg border border-cyan-400/40 px-2.5 py-1 text-xs font-bold text-cyan-700 hover:bg-cyan-500/10 dark:text-cyan-300 transition"
                          >
                            ✏️ Tahrirlash
                          </button>
                          <button
                            type="button"
                            onClick={() => void deleteLesson(Number(lesson.id))}
                            className="rounded-lg border border-rose-400/40 px-2 py-1 text-xs font-bold text-rose-600 hover:bg-rose-500/10 dark:text-rose-300 transition"
                            title="O'chirish"
                          >
                            🗑
                          </button>
                        </div>
                      </div>

                      {/* Question text & choices preview */}
                      <p className="mt-2 text-xs font-medium text-ink-600 dark:text-navy-200">
                        {p.question || "Savol matni mavjud emas"}
                      </p>

                      {p.audio_url ? (
                        <div className="mt-2">
                          <audio controls src={String(p.audio_url)} className="w-full h-8" />
                        </div>
                      ) : null}

                      {Array.isArray(p.options) && p.options.length ? (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {p.options.map((opt: string, oi: number) => {
                            const isCorrect = String(opt).trim().toLowerCase() === String(p.correct_answer || "").trim().toLowerCase();
                            return (
                              <span
                                key={oi}
                                className={`rounded-lg px-2 py-0.5 text-[11px] font-semibold border ${
                                  isCorrect
                                    ? "border-emerald-400 bg-emerald-500/15 text-emerald-800 dark:text-emerald-200 font-bold"
                                    : "border-line/60 bg-white/50 text-ink-500 dark:border-white/10 dark:bg-white/5 dark:text-navy-300"
                                }`}
                              >
                                {isCorrect ? "✓ " : ""}{opt}
                              </span>
                            );
                          })}
                        </div>
                      ) : p.correct_answer ? (
                        <p className="mt-1 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300">
                          To'g'ri javob: <strong>{String(p.correct_answer)}</strong>
                        </p>
                      ) : null}
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <p className="text-xs text-ink-400 italic p-3 bg-surface-soft/40 rounded-xl text-center">
              Hozircha bu modulda testlar yo'q. Quyidagi 3 usuldan biri orqali test qo'shing.
            </p>
          )}
        </div>
      </div>

      {/* ─── Test Qo'shish Bo'limlari (Accordion) ─── */}
      <details className="rounded-2xl border border-cyan-400/40 bg-white dark:bg-navy-900/60 p-4 transition">
        <summary className="cursor-pointer text-xs font-black text-cyan-700 dark:text-cyan-300 select-none flex items-center justify-between">
          <span>+ Yangi test qo'shish: Qo'lda, AI (Diamondvoy) yoki Kutubxonadan</span>
          <span className="text-[11px] text-ink-400">Ochish / Yopish ▾</span>
        </summary>

        <div className="mt-4 space-y-4">
          {/* Method 1: Manual question builder */}
          <div className="rounded-2xl border border-line p-4 dark:border-white/10 bg-white dark:bg-navy-900/60">
            <div className="flex items-center justify-between">
              <p className="text-xs font-black uppercase text-navy-900 dark:text-white">1. Qo'lda test savoli kiritish</p>
              <span className="rounded-full bg-cyan-500/10 px-2 py-0.5 text-[10px] font-bold text-cyan-700 dark:text-cyan-300">
                Barcha 20 xil test turi
              </span>
            </div>
            <div className="mt-3 grid gap-3">
              <div className="grid gap-2 sm:grid-cols-2">
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="rounded-xl border border-line bg-transparent p-2.5 text-xs dark:border-white/10 font-bold"
                  placeholder="Dars/savol nomi (masalan: 1-mashq)"
                />
                <select
                  value={manualType}
                  onChange={(e) => {
                    setManualType(e.target.value);
                    if (e.target.value === "true_false" || e.target.value === "listening_tf") {
                      setOptions("To'g'ri | Noto'g'ri");
                      setCorrect("To'g'ri");
                    } else if (e.target.value === "matching") {
                      setOptions("cat = mushuk | dog = kuchuk | book = kitob");
                      setCorrect("");
                    }
                  }}
                  className="rounded-xl border border-line bg-transparent p-2.5 text-xs font-bold text-navy-900 dark:text-white dark:border-white/10"
                >
                  {ALL_TEST_KINDS.map((k) => (
                    <option key={k.key} value={k.key}>
                      {k.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Audio upload section for listening kinds */}
              {curKindMeta.needsAudio ? (
                <div className="rounded-xl border border-cyan-400/40 bg-cyan-500/10 p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-black text-cyan-800 dark:text-cyan-200 flex items-center gap-1.5">
                      <span>🎧 Audio biriktirish (Majburiy)</span>
                    </span>
                    {audioUploading && <span className="text-xs text-cyan-600 animate-pulse font-bold">Yuklanmoqda...</span>}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <label className="btn btn-soft text-xs py-2 px-4 cursor-pointer">
                      📁 Audio fayl yuklash (MP3, WAV, M4A)
                      <input
                        type="file"
                        accept="audio/*"
                        className="hidden"
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          setAudioUploading(true);
                          try {
                            const url = await uploadAudioFile(file);
                            if (url) setAudioUrl(url);
                          } finally {
                            setAudioUploading(false);
                          }
                        }}
                      />
                    </label>
                    <input
                      value={audioUrl}
                      onChange={(e) => setAudioUrl(e.target.value)}
                      placeholder="Yoki Audio URL (masalan: /homework/files/... yoki https://...)"
                      className="min-w-0 flex-1 rounded-xl border border-line bg-transparent p-2 text-xs dark:border-white/10"
                    />
                  </div>
                  {audioUrl ? (
                    <div className="pt-2 border-t border-cyan-400/20">
                      <audio controls src={audioUrl} className="w-full h-8" />
                    </div>
                  ) : null}
                </div>
              ) : null}

              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={2}
                className="rounded-xl border border-line bg-transparent p-2.5 text-xs dark:border-white/10"
                placeholder={
                  manualType === "fill_blank" || manualType === "listening_gap"
                    ? "Savol matni (bo'sh joy uchun _____ ishlating): He _____ a teacher."
                    : manualType === "word_order" || manualType === "listening_order"
                    ? "Aralash so'zlar: teacher / is / He / a"
                    : manualType === "matching"
                    ? "Ko'rsatma: So'zlarni o'zbekcha tarjimasi bilan moslashtiring"
                    : "Savol matni..."
                }
              />

              {manualType === "true_false" || manualType === "listening_tf" ? (
                <div className="flex items-center gap-4 py-1">
                  <span className="text-xs font-bold">To'g'ri javob:</span>
                  <label className="flex items-center gap-1.5 text-xs font-bold cursor-pointer">
                    <input type="radio" name={`tf_${module.id}`} checked={correct === "To'g'ri"} onChange={() => setCorrect("To'g'ri")} />
                    ✓ To'g'ri
                  </label>
                  <label className="flex items-center gap-1.5 text-xs font-bold cursor-pointer">
                    <input type="radio" name={`tf_${module.id}`} checked={correct === "Noto'g'ri"} onChange={() => setCorrect("Noto'g'ri")} />
                    ✕ Noto'g'ri
                  </label>
                </div>
              ) : manualType === "fill_blank" || manualType === "listening_gap" ? (
                <div className="grid gap-2 sm:grid-cols-2">
                  <input
                    value={correct}
                    onChange={(e) => setCorrect(e.target.value)}
                    className="rounded-xl border border-line bg-transparent p-2.5 text-xs dark:border-white/10"
                    placeholder="To'g'ri to'ldiriladigan so'z (masalan: is)"
                  />
                  <input
                    value={options}
                    onChange={(e) => setOptions(e.target.value)}
                    className="rounded-xl border border-line bg-transparent p-2.5 text-xs dark:border-white/10"
                    placeholder="Qo'shimcha variantlar (ixtiyoriy, | bilan)"
                  />
                </div>
              ) : manualType === "word_order" || manualType === "listening_order" ? (
                <input
                  value={correct}
                  onChange={(e) => setCorrect(e.target.value)}
                  className="rounded-xl border border-line bg-transparent p-2.5 text-xs dark:border-white/10"
                  placeholder="To'g'ri tartibdagi to'liq gap: He is a teacher."
                />
              ) : manualType === "matching" ? (
                <input
                  value={options}
                  onChange={(e) => setOptions(e.target.value)}
                  className="rounded-xl border border-line bg-transparent p-2.5 text-xs dark:border-white/10"
                  placeholder="Juftliklar: book = kitob | pen = ruchka | cat = mushuk (| bilan)"
                />
              ) : (
                <div className="grid gap-2 sm:grid-cols-2">
                  <input
                    value={options}
                    onChange={(e) => setOptions(e.target.value)}
                    className="rounded-xl border border-line bg-transparent p-2.5 text-xs dark:border-white/10"
                    placeholder="Variantlar: A | B | C | D (| bilan ajrating)"
                  />
                  <input
                    value={correct}
                    onChange={(e) => setCorrect(e.target.value)}
                    className="rounded-xl border border-line bg-transparent p-2.5 text-xs dark:border-white/10"
                    placeholder="To'g'ri javob matni"
                  />
                </div>
              )}

              <input
                value={explanation}
                onChange={(e) => setExplanation(e.target.value)}
                className="rounded-xl border border-line bg-transparent p-2.5 text-xs dark:border-white/10"
                placeholder="Izoh / Tushuntirish (ixtiyoriy)"
              />

              <button
                type="button"
                disabled={busy}
                onClick={() => void saveManual()}
                className="btn btn-soft text-xs self-start"
              >
                + Ushbu savolni modulga qo'shish
              </button>
            </div>
          </div>

          {/* Method 2: AI Diamondvoy test generator */}
          <div className="rounded-2xl border border-line p-4 dark:border-white/10 bg-cyan-500/5">
            <div className="flex items-center justify-between">
              <p className="text-xs font-black uppercase text-cyan-700 dark:text-cyan-300">2. Diamondvoy AI bilan test yaratish</p>
              <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold text-emerald-700 dark:text-emerald-300">
                To'g'ridan-to'g'ri modulga qo'shiladi va kutubxonaga saqlanadi
              </span>
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_120px]">
              <input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                className="rounded-xl border border-line bg-transparent p-2.5 text-xs dark:border-white/10 font-bold"
                placeholder="Diamondvoy uchun mavzu (masalan: Present Perfect, Irregular verbs, Travel vocabulary)"
              />
              <div className="flex items-center gap-2">
                <label className="text-xs font-bold whitespace-nowrap">Soni:</label>
                <input
                  value={count}
                  type="number"
                  min="1"
                  max="30"
                  onChange={(e) => setCount(Number(e.target.value))}
                  className="w-full rounded-xl border border-line bg-transparent p-2.5 text-xs dark:border-white/10"
                />
              </div>
              <select
                value={types}
                onChange={(e) => setTypes(e.target.value)}
                className="sm:col-span-2 rounded-xl border border-line bg-transparent p-2.5 text-xs font-semibold dark:border-white/10"
              >
                <option value="multiple_choice,true_false,fill_blank">Aralash (MCQ + True/False + Fill blank)</option>
                <option value="multiple_choice">Faqat MCQ (Ko'p variantli)</option>
                <option value="true_false">Faqat To'g'ri / Noto'g'ri</option>
                <option value="fill_blank">Faqat Bo'sh joy to'ldirish</option>
                <option value="word_order">Faqat So'z tartibi</option>
                <option value="matching">Faqat Moslashtirish</option>
                <option value="translation">Faqat Tarjima mashqlari</option>
                <option value="spelling">Faqat Imlo (Spelling)</option>
                <option value="guided_writing">Faqat Yozma mashq</option>
                <option value="multiple_choice,true_false,fill_blank,word_order,matching">Barcha turlar aralash</option>
              </select>
              <button
                type="button"
                disabled={busy || !topic.trim()}
                onClick={() => void generate()}
                className="btn btn-primary text-xs sm:col-span-2 py-2.5 font-bold"
              >
                {busy ? "⏳ Diamondvoy yaratmoqda..." : `💎 Diamondvoy ${count} ta savol yaratib to'g'ridan-to'g'ri modulga qo'shsin`}
              </button>
            </div>
          </div>

          {/* Method 3: Real Materials Library Folder-tree Picker */}
          <div className="rounded-2xl border border-line p-4 dark:border-white/10 bg-white dark:bg-navy-900/60">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-black uppercase text-navy-900 dark:text-white">
                  3. Materiallar kutubxonasidan test biriktirish
                </p>
                <p className="text-xs text-ink-500 dark:text-navy-300 mt-0.5">
                  O'qituvchining haqiqiy papkalar daraxtidan testni tanlab to'g'ridan-to'g'ri biriktirish
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowLibraryModal(true)}
                className="btn btn-soft text-xs flex items-center gap-2 border-cyan-400 text-cyan-700 dark:text-cyan-300 font-bold"
              >
                📂 Kutubxona papkalarini ochish (Popup)
              </button>
            </div>
          </div>

          <button
            type="button"
            disabled={busy}
            onClick={() => void remove()}
            className="rounded-xl border border-rose-400/40 px-3 py-1.5 text-xs font-bold text-rose-600 hover:bg-rose-500/10 dark:text-rose-300 transition"
          >
            Modulni o'chirish
          </button>
        </div>
      </details>

      {/* Real Folder-tree Materials Library Popup Modal */}
      {showLibraryModal ? (
        <MaterialsLibraryModal
          apiFetch={apiFetch}
          onSelect={(contentId, cType, qCount) => void attachLibrary(contentId, cType, qCount)}
          onClose={() => setShowLibraryModal(false)}
        />
      ) : null}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   REAL MATERIALS LIBRARY POPUP MODAL — Folder tree & test picker
   ═══════════════════════════════════════════════════════════════════════════════ */

type LibTreeNode = {
  id: number;
  parent_id: number | null;
  kind: "folder" | "test";
  title: string;
  description?: string | null;
  subject?: string | null;
  level?: string | null;
  question_count: number;
  questions?: Row[];
};

function MaterialsLibraryModal({
  apiFetch,
  onSelect,
  onClose,
}: {
  apiFetch: ApiFetch;
  onSelect: (contentId: number, contentType: string, count: number) => void;
  onClose: () => void;
}) {
  const [nodes, setNodes] = useState<LibTreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [selectedTest, setSelectedTest] = useState<LibTreeNode | null>(null);
  const [questionCount, setQuestionCount] = useState(10);

  const loadTree = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch("/staff/teacher-library-tree");
      if (Array.isArray(data?.nodes)) {
        setNodes(data.nodes);
        // Expand root folders by default
        const rootFolderIds = data.nodes.filter((n: LibTreeNode) => n.kind === "folder" && !n.parent_id).map((n: LibTreeNode) => n.id);
        setExpanded(new Set(rootFolderIds));
      }
    } catch {
      setNodes([]);
    } finally {
      setLoading(false);
    }
  }, [apiFetch]);

  useEffect(() => {
    void loadTree();
  }, [loadTree]);

  const toggle = (id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const childrenOf = useMemo(() => {
    const map = new Map<number, LibTreeNode[]>();
    for (const node of nodes) {
      const pKey = node.parent_id || 0;
      if (!map.has(pKey)) map.set(pKey, []);
      map.get(pKey)!.push(node);
    }
    return map;
  }, [nodes]);

  const filteredTests = useMemo(() => {
    if (!search.trim()) return null;
    const q = search.trim().toLowerCase();
    return nodes.filter((n) => n.kind === "test" && n.title.toLowerCase().includes(q));
  }, [nodes, search]);

  const renderFolderNode = (node: LibTreeNode, depth: number) => {
    const kids = childrenOf.get(node.id) || [];
    const isOpen = expanded.has(node.id);

    if (node.kind === "folder") {
      return (
        <div key={node.id}>
          <div
            onClick={() => toggle(node.id)}
            className="flex items-center gap-2 rounded-xl px-2 py-2 transition hover:bg-surface-soft dark:hover:bg-white/5 cursor-pointer select-none"
            style={{ paddingLeft: depth * 18 + 8 }}
          >
            <span className="w-4 text-xs font-black text-ink-500 dark:text-navy-300">
              {isOpen ? "▾" : "▸"}
            </span>
            <span className="text-base">📁</span>
            <span className="font-bold text-xs text-navy-900 dark:text-white">
              {node.title}
            </span>
            <span className="ml-auto text-[10px] text-ink-400">
              {kids.filter((k) => k.kind === "test").length} ta test
            </span>
          </div>
          {isOpen && kids.map((child) => renderFolderNode(child, depth + 1))}
        </div>
      );
    }

    // It's a test node
    const isSelected = selectedTest?.id === node.id;
    return (
      <div
        key={node.id}
        onClick={() => {
          setSelectedTest(node);
          setQuestionCount(node.question_count || 10);
        }}
        className={`flex items-center gap-2 rounded-xl px-3 py-2 transition cursor-pointer my-0.5 ${
          isSelected
            ? "border-2 border-cyan-400 bg-cyan-500/15 shadow-sm"
            : "hover:bg-cyan-500/5"
        }`}
        style={{ paddingLeft: depth * 18 + 24 }}
      >
        <span className="text-base">🧪</span>
        <div className="min-w-0 flex-1">
          <p className="font-bold text-xs text-navy-900 dark:text-white truncate">
            {node.title}
          </p>
          <p className="text-[10px] text-ink-400 dark:text-navy-400">
            {node.subject || "English"} {node.level ? `· ${node.level}` : ""}
          </p>
        </div>
        <span className="rounded-full bg-cyan-500/15 px-2 py-0.5 text-[10px] font-black text-cyan-700 dark:text-cyan-300 shrink-0">
          {node.question_count} ta savol
        </span>
        <input
          type="radio"
          name="selected_lib_test"
          checked={isSelected}
          onChange={() => {
            setSelectedTest(node);
            setQuestionCount(node.question_count || 10);
          }}
          className="accent-cyan-500"
        />
      </div>
    );
  };

  const roots = childrenOf.get(0) || [];

  return (
    <div className="fixed inset-0 z-[250] flex items-center justify-center bg-navy-950/80 p-4 backdrop-blur-sm animate-fade-in">
      <div className="relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-3xl bg-white shadow-2xl dark:bg-navy-900 border border-line dark:border-white/10">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-line p-4 sm:p-5 dark:border-white/10">
          <div>
            <h3 className="text-lg font-black text-navy-900 dark:text-white flex items-center gap-2">
              📂 Materiallar Kutubxonasi Testlari
            </h3>
            <p className="text-xs text-ink-500 dark:text-navy-300 mt-0.5">
              Papkalar ichidan kerakli testni tanlab modulga biriktiring
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-9 w-9 place-items-center rounded-full text-ink-500 hover:bg-rose-500/10 hover:text-rose-600 transition"
          >
            ✕
          </button>
        </div>

        {/* Search bar */}
        <div className="p-4 border-b border-line dark:border-white/10">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Test nomi bo'yicha qidiring (masalan: Present Simple, Unit 1)..."
            className="w-full rounded-xl border border-line bg-surface-soft p-2.5 text-xs text-navy-900 placeholder:text-ink-400 focus:border-cyan-400 focus:outline-none dark:border-white/10 dark:bg-white/5 dark:text-white font-medium"
          />
        </div>

        {/* Folder tree or Search results */}
        <div className="min-h-0 flex-1 overflow-y-auto p-4 space-y-1">
          {loading ? (
            <div className="grid min-h-48 place-items-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent" />
            </div>
          ) : filteredTests ? (
            /* Search results mode */
            filteredTests.length ? (
              filteredTests.map((test) => {
                const isSelected = selectedTest?.id === test.id;
                return (
                  <div
                    key={test.id}
                    onClick={() => {
                      setSelectedTest(test);
                      setQuestionCount(test.question_count || 10);
                    }}
                    className={`flex items-center justify-between p-3 rounded-2xl border-2 transition cursor-pointer ${
                      isSelected
                        ? "border-cyan-400 bg-cyan-500/10 shadow-sm"
                        : "border-line/60 hover:border-cyan-300 dark:border-white/10 bg-white dark:bg-white/5"
                    }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="text-xl">🧪</span>
                      <div className="min-w-0">
                        <p className="font-bold text-xs text-navy-900 dark:text-white truncate">
                          {test.title}
                        </p>
                        <p className="text-[10px] text-ink-400">
                          {test.subject || "English"} {test.level ? `· ${test.level}` : ""}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className="rounded-full bg-cyan-500/15 px-2.5 py-0.5 text-xs font-black text-cyan-700 dark:text-cyan-300">
                        {test.question_count} ta savol
                      </span>
                      <input
                        type="radio"
                        name="search_selected_test"
                        checked={isSelected}
                        onChange={() => {
                          setSelectedTest(test);
                          setQuestionCount(test.question_count || 10);
                        }}
                        className="accent-cyan-500"
                      />
                    </div>
                  </div>
                );
              })
            ) : (
              <p className="py-12 text-center text-xs text-ink-500">
                "{search}" bo'yicha hech qanday test topilmadi.
              </p>
            )
          ) : roots.length ? (
            /* Folder Tree Mode */
            roots.map((node) => renderFolderNode(node, 0))
          ) : (
            <div className="py-12 text-center text-xs text-ink-500 dark:text-navy-400 space-y-2">
              <p className="font-bold">Kutubxonada testlar topilmadi.</p>
              <p className="text-[11px]">Avval Materiallar Kutubxonasi bo'limida papka va testlar yarating.</p>
            </div>
          )}
        </div>

        {/* Selected Test Action Footer */}
        <div className="border-t border-line p-4 dark:border-white/10 bg-surface-soft/60 dark:bg-navy-950/40 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-ink-600 dark:text-navy-300">
              Qo'shiladigan savollar soni:
            </span>
            <input
              type="number"
              min="1"
              max={selectedTest ? Math.max(1, selectedTest.question_count) : 100}
              value={questionCount}
              onChange={(e) => setQuestionCount(Number(e.target.value))}
              className="w-20 rounded-xl border border-line bg-transparent p-2 text-xs font-bold text-center dark:border-white/10"
            />
            {selectedTest ? (
              <span className="text-[11px] text-ink-400">
                (jami: {selectedTest.question_count} ta)
              </span>
            ) : null}
          </div>

          <button
            type="button"
            disabled={!selectedTest}
            onClick={() => {
              if (selectedTest) {
                onSelect(selectedTest.id, "library_node", questionCount);
              }
            }}
            className="btn btn-primary text-xs py-2.5 px-6 font-bold disabled:opacity-40"
          >
            ✓ Tanlangan testni modulga biriktirish
          </button>
        </div>
      </div>
    </div>
  );
}

function CoverPicker({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {covers.map((key) => (
        <button
          type="button"
          onClick={() => onChange(key)}
          key={key}
          className={`h-11 w-11 overflow-hidden rounded-full border-2 transition ${
            key === value ? "border-cyan-400 scale-105 shadow-md" : "border-transparent opacity-65 hover:opacity-100"
          }`}
        >
          <img src={image(key)} alt={key} className="h-full w-full object-cover" />
        </button>
      ))}
    </div>
  );
}
