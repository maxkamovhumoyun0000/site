"use client";
import { FormEvent, MouseEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useWebT } from "./web-i18n";

type Row = Record<string, any>;
type ApiFetch = (path: string, options?: any) => Promise<any>;
const covers = ["star", "chest", "dolphin", "jellyfish", "ship", "trophy"];
const image = (key: string) => `/learning-paths/${covers.includes(key) ? key : "star"}.png`;
const errorText = (e: unknown, fallback: string) => e instanceof Error ? e.message : fallback;

/* ═══════════════════════════════════════════════════════════════════════════════
   DUOLINGO SYNTHESIZER & SOUND SYSTEM (Zero dependencies, pure Web Audio API)
   ═══════════════════════════════════════════════════════════════════════════════ */

function playDuolingoSound(type: "correct" | "wrong" | "complete" | "pop" | "chest") {
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();

    if (type === "correct") {
      // Cheerful 2-tone ascending chime (E5 -> A5)
      const now = ctx.currentTime;
      const osc1 = ctx.createOscillator();
      const g1 = ctx.createGain();
      osc1.type = "sine";
      osc1.frequency.setValueAtTime(659.25, now);
      g1.gain.setValueAtTime(0.2, now);
      g1.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
      osc1.connect(g1);
      g1.connect(ctx.destination);
      osc1.start(now);
      osc1.stop(now + 0.18);

      const osc2 = ctx.createOscillator();
      const g2 = ctx.createGain();
      osc2.type = "sine";
      osc2.frequency.setValueAtTime(880, now + 0.12);
      g2.gain.setValueAtTime(0.25, now + 0.12);
      g2.gain.exponentialRampToValueAtTime(0.001, now + 0.42);
      osc2.connect(g2);
      g2.connect(ctx.destination);
      osc2.start(now + 0.12);
      osc2.stop(now + 0.42);
    } else if (type === "wrong") {
      // Gentle low double boop
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.type = "triangle";
      osc.frequency.setValueAtTime(220, now);
      osc.frequency.setValueAtTime(164.8, now + 0.12);
      g.gain.setValueAtTime(0.22, now);
      g.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
      osc.connect(g);
      g.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.35);
    } else if (type === "complete") {
      // Celebratory 4-note ascending fanfare: C5 -> E5 -> G5 -> C6
      const notes = [523.25, 659.25, 783.99, 1046.50];
      const now = ctx.currentTime;
      notes.forEach((freq, idx) => {
        const osc = ctx.createOscillator();
        const g = ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(freq, now + idx * 0.1);
        g.gain.setValueAtTime(0.22, now + idx * 0.1);
        g.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.1 + 0.35);
        osc.connect(g);
        g.connect(ctx.destination);
        osc.start(now + idx * 0.1);
        osc.stop(now + idx * 0.1 + 0.35);
      });
    } else if (type === "pop" || type === "chest") {
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(440, now);
      osc.frequency.exponentialRampToValueAtTime(880, now + 0.1);
      g.gain.setValueAtTime(0.15, now);
      g.gain.exponentialRampToValueAtTime(0.001, now + 0.1);
      osc.connect(g);
      g.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.1);
    }
  } catch {
    // Ignore if blocked by browser autoplay policy
  }
}

/* ═══════════════════════════════════════════════════════════════════════════════
   STUDENT VIEW — Authentic Duolingo-style learning path & snake trail
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

  useEffect(() => {
    void load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <section className="m-6 flex min-h-72 items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-12 w-12 animate-spin rounded-full border-4 border-[#58cc02] border-t-transparent" />
          <p className="text-xs font-black uppercase tracking-wider text-slate-500">Duolingo yo'li yuklanmoqda...</p>
        </div>
      </section>
    );
  }

  // Calculate total student stats
  let totalCoins = 0;
  let passedModulesCount = 0;
  for (const tr of tracks) {
    for (const mod of tr.modules || []) {
      if (mod.progress?.status === "passed") {
        passedModulesCount++;
        totalCoins += Number(mod.reward_coins || 0);
      }
    }
  }

  return (
    <section className="mx-auto w-full max-w-2xl px-3 py-4 sm:px-6">
      {/* Duolingo Top Stats Pill Bar */}
      <div className="sticky top-2 z-30 mb-5 flex items-center justify-between gap-2 rounded-2xl border-2 border-b-4 border-slate-200 bg-white/95 px-4 py-2.5 shadow-sm backdrop-blur-md dark:border-navy-700 dark:bg-navy-900/95">
        <div className="flex items-center gap-1.5 font-black text-amber-500">
          <span className="text-xl">🔥</span>
          <span className="text-sm font-black text-amber-700 dark:text-amber-400">3 kun</span>
        </div>

        <div className="flex items-center gap-1.5 font-black text-cyan-500">
          <span className="text-xl">💎</span>
          <span className="text-sm font-black text-cyan-700 dark:text-cyan-300">
            {totalCoins} <span className="hidden sm:inline">D'Coin</span>
          </span>
        </div>

        <div className="flex items-center gap-1.5 font-black text-emerald-500">
          <span className="text-xl">⭐</span>
          <span className="text-sm font-black text-emerald-700 dark:text-emerald-400">
            {passedModulesCount} ta modul
          </span>
        </div>

        <div className="flex items-center gap-1.5 font-black text-rose-500">
          <span className="text-xl">❤️</span>
          <span className="text-sm font-black text-rose-700 dark:text-rose-400">5</span>
        </div>
      </div>

      {error ? (
        <p className="mb-4 rounded-2xl border-2 border-b-4 border-rose-300 bg-rose-50 p-3.5 text-sm font-bold text-rose-700 dark:border-rose-900 dark:bg-rose-950/50 dark:text-rose-300">
          {error}
        </p>
      ) : null}

      {/* Tracks List */}
      <div className="space-y-10">
        {tracks.map((track, i) => (
          <DuolingoTrack
            key={track.id}
            track={track}
            index={i}
            onStartModule={(mod) => {
              playDuolingoSound("pop");
              setActiveModule(mod);
            }}
          />
        ))}
      </div>

      {!tracks.length ? (
        <div className="rounded-3xl border-2 border-dashed border-slate-300 p-12 text-center text-slate-500 dark:border-navy-700 dark:text-navy-300">
          <span className="text-4xl">🌱</span>
          <p className="mt-3 text-base font-black text-navy-900 dark:text-white">Sizga hali o'quv yo'li biriktirilmagan.</p>
          <p className="mt-1 text-xs text-slate-500">O'qituvchingiz yangi track va modullarni taqdim etganda shu yerda ko'rinadi.</p>
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

/* ═══════════════════════════════════════════════════════════════════════════════
   DUOLINGO TRACK — Unit Header & Winding Stepping Stones Snake Trail
   ═══════════════════════════════════════════════════════════════════════════════ */

function DuolingoTrack({
  track,
  index,
  onStartModule,
}: {
  track: Row;
  index: number;
  onStartModule: (module: Row) => void;
}) {
  const locked = Boolean(track.locked);
  const modules = Array.isArray(track.modules) ? track.modules : [];

  const passedCount = modules.filter((m: Row) => m.progress?.status === "passed").length;
  const progressPercent = modules.length ? Math.round((passedCount / modules.length) * 100) : 0;

  // Duolingo Unit Colors by index (Green -> Blue -> Purple -> Orange)
  const unitGradients = [
    { bg: "bg-[#58cc02]", border: "border-[#46a302]", accent: "bg-[#46a302]" },
    { bg: "bg-[#1cb0f6]", border: "border-[#1899d6]", accent: "bg-[#1899d6]" },
    { bg: "bg-[#ce82ff]", border: "border-[#a559d8]", accent: "bg-[#a559d8]" },
    { bg: "bg-[#ff9600]", border: "border-[#d87c00]", accent: "bg-[#d87c00]" },
  ];
  const unitColor = unitGradients[index % unitGradients.length];

  // Sine-wave horizontal offsets for snake trail
  const OFFSETS = [0, 48, 72, 48, 0, -48, -72, -48];

  return (
    <article className={`relative select-none ${locked ? "opacity-55 grayscale" : ""}`}>
      {/* Duolingo Unit Header Banner */}
      <header
        className={`relative overflow-hidden rounded-3xl border-2 border-b-[6px] ${unitColor.border} ${unitColor.bg} p-5 text-white shadow-xl`}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <span className="inline-block rounded-lg bg-black/20 px-2.5 py-1 text-[11px] font-black uppercase tracking-wider text-white">
              Bo'lim {index + 1} · {track.subject || "Ingliz tili"}
            </span>
            <h2 className="mt-1.5 text-2xl font-black tracking-tight text-white drop-shadow-sm">
              {track.title}
            </h2>
            <p className="mt-0.5 text-xs font-semibold text-white/90">
              {track.description || "Bosqichma-bosqich o'rganish yo'li"}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="rounded-2xl bg-white/20 px-3.5 py-1.5 text-xs font-black text-white backdrop-blur-sm">
              {locked ? "🔒 Qulflangan" : `${passedCount}/${modules.length} modul`}
            </span>
          </div>
        </div>

        {/* Unit Progress Bar */}
        <div className="mt-4 flex items-center gap-3">
          <div className="h-3.5 min-w-0 flex-1 overflow-hidden rounded-full bg-black/20 p-0.5">
            <div
              className="h-full rounded-full bg-white transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <span className="text-xs font-black text-white">{progressPercent}%</span>
        </div>
      </header>

      {/* Duolingo Winding Stepping Stones Path */}
      <div className="relative mx-auto mt-8 max-w-sm py-4">
        {/* Winding Trail Column */}
        <div className="flex flex-col items-center gap-7">
          {modules.map((module: Row, order: number) => {
            const xOffset = OFFSETS[order % OFFSETS.length];
            const isLast = order === modules.length - 1;

            return (
              <div key={module.id} className="relative flex flex-col items-center">
                {/* Stepping node */}
                <DuolingoNode
                  module={module}
                  order={order}
                  parentLocked={locked}
                  xOffset={xOffset}
                  onStart={() => onStartModule(module)}
                />

                {/* Optional milestone chest after every 3 modules or at the end */}
                {(order + 1) % 4 === 0 || isLast ? (
                  <DuolingoChestNode
                    unlocked={module.progress?.status === "passed"}
                    rewardCoins={module.reward_coins || 10}
                    xOffset={0}
                  />
                ) : null}
              </div>
            );
          })}
        </div>
      </div>

      {track.certificate_eligible ? (
        <div className="mt-6 flex items-center gap-3 rounded-2xl border-2 border-b-4 border-amber-400 bg-amber-50 p-4 font-bold text-amber-900 shadow-sm dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200">
          <span className="text-2xl">🎓</span>
          <div>
            <p className="text-sm font-black">Bo'lim sertifikati ochildi!</p>
            <p className="text-xs font-medium text-amber-800 dark:text-amber-300">
              Siz bu bo'limdagi barcha darslarni a'lo baholarga bajardingiz. Sertifikat Profil sahifangizda tayyor.
            </p>
          </div>
        </div>
      ) : null}
    </article>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   DUOLINGO STEPPING STONE (3D Pushable Circular Node with Floating Speech Bubble)
   ═══════════════════════════════════════════════════════════════════════════════ */

function DuolingoNode({
  module,
  order,
  parentLocked,
  xOffset,
  onStart,
}: {
  module: Row;
  order: number;
  parentLocked: boolean;
  xOffset: number;
  onStart: () => void;
}) {
  const [showPopover, setShowPopover] = useState(false);
  const progress = module.progress || {};
  const isLocked = parentLocked || progress.status === "locked";
  const isPassed = progress.status === "passed";
  const isActive = !isLocked && !isPassed;
  const score = Number(progress.best_score || 0);
  const stars = isPassed ? (score >= 95 ? 3 : score >= 85 ? 2 : 1) : 0;
  const lessons = Array.isArray(module.lessons) ? module.lessons : [];

  const handleNodeClick = () => {
    if (isLocked) return;
    playDuolingoSound("pop");
    setShowPopover(!showPopover);
  };

  return (
    <div
      className="relative flex flex-col items-center transition-all duration-300"
      style={{ transform: `translateX(${xOffset}px)` }}
    >
      {/* Floating Animated "START" / "BOSHLASH" Speech Bubble for Active Node */}
      {isActive ? (
        <div className="absolute -top-11 z-20 flex flex-col items-center animate-bounce pointer-events-none">
          <div className="rounded-2xl border-2 border-[#58cc02] bg-white px-3.5 py-1 text-[11px] font-black uppercase tracking-wider text-[#58cc02] shadow-lg dark:bg-navy-800">
            Boshlash
          </div>
          <div className="h-0 w-0 border-x-4 border-t-4 border-x-transparent border-t-[#58cc02] -mt-[1px]" />
        </div>
      ) : null}

      {/* Floating stars for completed node */}
      {isPassed ? (
        <div className="absolute -top-6 z-20 flex items-center gap-0.5 text-xs text-amber-400 drop-shadow-md">
          {Array.from({ length: stars }, (_, i) => (
            <span key={i} className="animate-pulse">⭐</span>
          ))}
        </div>
      ) : null}

      {/* Circular 3D Pushable Duolingo Button */}
      <button
        type="button"
        onClick={handleNodeClick}
        disabled={isLocked}
        title={isLocked ? "Oldingi modulni tugating" : module.title}
        className={`group relative grid h-20 w-20 shrink-0 place-items-center rounded-full border-2 transition-all duration-150 select-none ${
          isPassed
            ? "border-[#e5a800] border-b-[8px] bg-[#ffc800] text-white shadow-xl active:translate-y-1.5 active:border-b-[2px] active:shadow-none hover:brightness-105"
            : isActive
            ? "border-[#46a302] border-b-[8px] bg-[#58cc02] text-white shadow-xl shadow-emerald-500/25 ring-4 ring-[#58cc02]/30 ring-offset-2 active:translate-y-1.5 active:border-b-[2px] active:shadow-none hover:brightness-105"
            : "border-[#cfcfcf] border-b-[8px] bg-[#e5e5e5] text-slate-400 cursor-not-allowed dark:border-[#1a252b] dark:bg-[#202f36] dark:text-slate-500"
        }`}
      >
        {/* Cover image or iconic icon */}
        <div className="relative z-10 flex flex-col items-center justify-center">
          {isLocked ? (
            <span className="text-2xl drop-shadow">🔒</span>
          ) : isPassed ? (
            <span className="text-3xl font-black drop-shadow">👑</span>
          ) : (
            <span className="text-3xl font-black drop-shadow">⭐</span>
          )}
        </div>
      </button>

      {/* Duolingo Popover Card when clicked */}
      {showPopover && !isLocked ? (
        <div className="absolute top-24 z-40 w-72 rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-4 shadow-2xl animate-fade-in dark:border-navy-700 dark:bg-navy-900">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2 dark:border-white/10">
            <span className="text-xs font-black uppercase tracking-wider text-[#58cc02]">
              Modul #{order + 1}
            </span>
            <button
              type="button"
              onClick={() => setShowPopover(false)}
              className="grid h-6 w-6 place-items-center rounded-full text-slate-400 hover:bg-slate-100 dark:hover:bg-white/10"
            >
              ✕
            </button>
          </div>

          <h3 className="mt-2 text-base font-black text-navy-900 dark:text-white">
            {module.title}
          </h3>

          <p className="mt-1 text-xs text-slate-500 dark:text-navy-300">
            {module.description || "Ushbu modul orqali bilimlaringizni sinang."}
          </p>

          <div className="mt-3 flex items-center justify-between rounded-xl bg-slate-50 p-2.5 text-xs font-bold text-slate-700 dark:bg-navy-800 dark:text-navy-200">
            <span>📝 {lessons.length} ta savol</span>
            {module.reward_coins > 0 ? (
              <span className="text-amber-500 font-black">💰 +{module.reward_coins} coin</span>
            ) : null}
            {isPassed ? (
              <span className="text-emerald-600 font-black">✓ {score}%</span>
            ) : (
              <span>{module.passing_score || 70}% o'tish</span>
            )}
          </div>

          <button
            type="button"
            onClick={() => {
              setShowPopover(false);
              onStart();
            }}
            className="mt-4 w-full rounded-2xl border-2 border-b-4 border-[#46a302] bg-[#58cc02] py-3 text-center text-sm font-black uppercase tracking-wider text-white shadow-md transition-all active:translate-y-1 active:border-b-2 hover:bg-[#4cb802]"
          >
            {isPassed ? "Qayta ishlash 🔄" : "Darsni boshlash →"}
          </button>
        </div>
      ) : null}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   DUOLINGO BONUS CHEST NODE (Treasure milestone along the path)
   ═══════════════════════════════════════════════════════════════════════════════ */

function DuolingoChestNode({
  unlocked,
  rewardCoins,
  xOffset,
}: {
  unlocked: boolean;
  rewardCoins: number;
  xOffset: number;
}) {
  const [opened, setOpened] = useState(false);

  const handleClick = () => {
    if (!unlocked || opened) return;
    playDuolingoSound("chest");
    setOpened(true);
  };

  return (
    <div
      className="relative mt-2 flex flex-col items-center"
      style={{ transform: `translateX(${xOffset}px)` }}
    >
      <button
        type="button"
        onClick={handleClick}
        disabled={!unlocked}
        title={unlocked ? (opened ? "Mukofot olindi!" : "Sandıqni oching!") : "Oldingi darslarni tugating"}
        className={`group relative grid h-16 w-16 place-items-center rounded-2xl border-2 transition-all duration-150 select-none ${
          opened
            ? "border-slate-300 border-b-4 bg-slate-100 text-slate-400 dark:border-navy-700 dark:bg-navy-800"
            : unlocked
            ? "border-amber-500 border-b-[6px] bg-gradient-to-b from-amber-300 to-amber-400 text-white shadow-lg shadow-amber-500/30 animate-pulse active:translate-y-1 active:border-b-2 cursor-pointer"
            : "border-slate-200 border-b-4 bg-slate-200 text-slate-400 dark:border-navy-800 dark:bg-navy-900 cursor-not-allowed"
        }`}
      >
        <span className="text-2xl">{opened ? "✨" : "🎁"}</span>
      </button>

      <span className="mt-1 text-[10px] font-black uppercase tracking-wider text-amber-700 dark:text-amber-400">
        {opened ? "Ochildi" : `+${rewardCoins} D'Coin`}
      </span>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   LESSON PLAYER MODAL — Authentic Duolingo test player experience
   ═══════════════════════════════════════════════════════════════════════════════ */

function LessonPlayerModal({
  module,
  apiFetch,
  onClose,
}: {
  module: Row;
  apiFetch: ApiFetch;
  onClose: () => void;
}) {
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
  const [hearts, setHearts] = useState(5);
  const [audioPlaying, setAudioPlaying] = useState(false);

  // For Word Order interactive exercise
  const [sentenceWords, setSentenceWords] = useState<string[]>([]);
  const [bankWords, setBankWords] = useState<{ id: number; text: string; used: boolean }[]>([]);

  // Hidden Audio Element ref
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const loadLesson = useCallback(async (index: number) => {
    if (index >= lessons.length) {
      setFinished(true);
      playDuolingoSound("complete");
      return;
    }
    const lesson = lessons[index];
    setLoading(true);
    setSelected("");
    setResult(null);
    setError("");
    setSentenceWords([]);
    setBankWords([]);

    try {
      const data = await apiFetch(`/student/learning-lessons/${lesson.id}`);
      const q = data?.question_payload || data || null;
      setQuestion(q);

      // Initialize word bank if Word Order test
      if (q && (q.test_type === "word_order" || q.test_type === "listening_order")) {
        const fullText = String(q.correct_answer || q.prompt || q.question || "");
        // Split and shuffle
        const rawWords = fullText.split(/\s+/).filter(Boolean);
        const shuffled = [...rawWords].sort(() => Math.random() - 0.5);
        setBankWords(shuffled.map((w, idx) => ({ id: idx, text: w, used: false })));
      }
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

  // Word Order tile handlers
  const handleTileClick = (tileId: number, word: string) => {
    if (result) return;
    playDuolingoSound("pop");
    setBankWords((prev) => prev.map((t) => (t.id === tileId ? { ...t, used: true } : t)));
    const newWords = [...sentenceWords, word];
    setSentenceWords(newWords);
    setSelected(newWords.join(" "));
  };

  const handleSentenceWordRemove = (wordIdx: number) => {
    if (result) return;
    playDuolingoSound("pop");
    const wordToRemove = sentenceWords[wordIdx];
    const newWords = sentenceWords.filter((_, idx) => idx !== wordIdx);
    setSentenceWords(newWords);
    setSelected(newWords.join(" "));

    // Re-enable the first used tile in bank that matches
    setBankWords((prev) => {
      let found = false;
      return prev.map((t) => {
        if (!found && t.used && t.text === wordToRemove) {
          found = true;
          return { ...t, used: false };
        }
        return t;
      });
    });
  };

  // Audio Playback
  const playAudio = (rate = 1.0) => {
    if (!audioRef.current || !question?.audio_url) return;
    audioRef.current.playbackRate = rate;
    audioRef.current.currentTime = 0;
    setAudioPlaying(true);
    audioRef.current.play().catch(() => setAudioPlaying(false));
  };

  const submit = async () => {
    if (!selected || result || !question) return;
    const lesson = lessons[currentIndex];
    const correct = String(question?.correct_answer || "").trim().toLowerCase() === selected.trim().toLowerCase();
    const newScore = score + (correct ? 1 : 0);
    const newTotal = total + 1;
    setScore(newScore);
    setTotal(newTotal);

    if (correct) {
      playDuolingoSound("correct");
    } else {
      playDuolingoSound("wrong");
      setHearts((h) => Math.max(0, h - 1));
    }

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
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/75 p-3 backdrop-blur-sm sm:p-6 animate-fade-in">
      <div className="relative flex h-full max-h-[96vh] w-full max-w-xl flex-col overflow-hidden rounded-3xl border-2 border-slate-200 bg-white shadow-2xl dark:border-navy-700 dark:bg-[#131f24]">
        {/* Hidden Audio Player */}
        {question?.audio_url ? (
          <audio
            ref={audioRef}
            src={question.audio_url}
            onEnded={() => setAudioPlaying(false)}
            onError={() => setAudioPlaying(false)}
            className="hidden"
          />
        ) : null}

        {/* ─── Duolingo Top Bar: Close, Glossy Progress Bar, Hearts ─── */}
        <div className="flex items-center gap-3 border-b border-slate-100 p-4 dark:border-white/10">
          <button
            onClick={() => {
              if (result || window.confirm("Haqiqatan ham darsni tark etmoqchimisiz?")) {
                onClose();
              }
            }}
            type="button"
            className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-white/10"
          >
            ✕
          </button>

          {/* Duolingo Rounded Glossy Progress Bar */}
          <div className="relative h-4 min-w-0 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-navy-800">
            <div
              className="h-full rounded-full bg-[#58cc02] transition-all duration-500 relative overflow-hidden"
              style={{ width: `${progressPercent}%` }}
            >
              {/* Glossy shine highlight stripe */}
              <div className="absolute top-1 left-2 right-2 h-1 rounded-full bg-white/40" />
            </div>
          </div>

          <div className="flex items-center gap-1 font-black text-rose-500">
            <span className="text-lg">❤️</span>
            <span className="text-sm font-black text-rose-600 dark:text-rose-400">{hearts}</span>
          </div>
        </div>

        {/* ─── Question Content Area ─── */}
        <div className="min-h-0 flex-1 overflow-y-auto p-5 sm:p-7">
          {error ? (
            <div className="rounded-2xl border-2 border-rose-300 bg-rose-50 p-4 text-sm font-bold text-rose-700">
              {error}
            </div>
          ) : null}

          {loading && !question && !finished ? (
            <div className="grid min-h-64 place-items-center">
              <div className="h-12 w-12 animate-spin rounded-full border-4 border-[#58cc02] border-t-transparent" />
            </div>
          ) : null}

          {/* Duolingo Completion Screen */}
          {finished ? (
            <div className="py-6 text-center animate-fade-in">
              <div className="relative mx-auto mb-4 grid h-28 w-28 place-items-center rounded-full border-4 border-[#b87d00] bg-gradient-to-b from-[#ffc800] to-[#e5a800] text-5xl shadow-2xl">
                👑
              </div>

              <h2 className="text-3xl font-black text-navy-900 dark:text-white">
                Dars yakunlandi!
              </h2>

              <p className="mt-1 text-sm font-semibold text-slate-500 dark:text-navy-300">
                Ajoyib mehnat qildingiz!
              </p>

              {/* Stats cards in Duolingo style */}
              <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
                <div className="rounded-2xl border-2 border-b-4 border-amber-300 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/40">
                  <span className="text-xs font-black uppercase text-amber-700 dark:text-amber-300">Aniqlik</span>
                  <p className="mt-1 text-2xl font-black text-amber-800 dark:text-amber-200">
                    {Math.round((score / Math.max(total, 1)) * 100)}%
                  </p>
                </div>

                <div className="rounded-2xl border-2 border-b-4 border-cyan-300 bg-cyan-50 p-3 dark:border-cyan-800 dark:bg-cyan-950/40">
                  <span className="text-xs font-black uppercase text-cyan-700 dark:text-cyan-300">D'Coin</span>
                  <p className="mt-1 text-2xl font-black text-cyan-800 dark:text-cyan-200">
                    +{moduleResult?.reward_coins || module.reward_coins || 10} 💎
                  </p>
                </div>

                <div className="col-span-2 rounded-2xl border-2 border-b-4 border-emerald-300 bg-emerald-50 p-3 sm:col-span-1 dark:border-emerald-800 dark:bg-emerald-950/40">
                  <span className="text-xs font-black uppercase text-emerald-700 dark:text-emerald-300">Natija</span>
                  <p className="mt-1 text-2xl font-black text-emerald-800 dark:text-emerald-200">
                    {score}/{total}
                  </p>
                </div>
              </div>

              {moduleResult?.module_progress?.passed || Math.round((score / Math.max(total, 1)) * 100) >= (module.passing_score || 70) ? (
                <div className="mt-5 rounded-2xl border-2 border-b-4 border-[#46a302] bg-[#d7ffb8] p-4 text-sm font-black text-[#2e6b00] dark:bg-[#1c381a] dark:text-[#a0ff6d]">
                  🎉 Tabriklaymiz! Modul muvaffaqiyatli yakunlandi va keyingi dars ochildi!
                </div>
              ) : null}

              <button
                type="button"
                onClick={onClose}
                className="mt-6 w-full rounded-2xl border-2 border-b-4 border-[#46a302] bg-[#58cc02] py-4 text-base font-black uppercase tracking-wider text-white shadow-xl active:translate-y-1 active:border-b-2 hover:bg-[#4cb802]"
              >
                Davom etish
              </button>
            </div>
          ) : null}

          {/* Active Question Render */}
          {question && !finished ? (
            <div className="space-y-5 animate-fade-in">
              {/* Category Pill */}
              <div className="flex items-center justify-between">
                <span className="rounded-xl bg-slate-100 px-3 py-1 text-xs font-black uppercase tracking-wider text-slate-600 dark:bg-navy-800 dark:text-navy-300">
                  {question.test_type === "word_order" || question.test_type === "listening_order"
                    ? "🧩 Gap tuzing"
                    : question.test_type === "true_false" || question.test_type === "listening_tf"
                    ? "⚖️ To'g'ri yoki Noto'g'ri"
                    : question.test_type === "fill_blank" || question.test_type === "listening_gap"
                    ? "✏️ Bo'sh joyni to'ldiring"
                    : question.test_type === "matching"
                    ? "🔄 Moslashtiring"
                    : question.audio_url
                    ? "🎧 Tinglab javob bering"
                    : "📝 To'g'ri variantni tanlang"}
                </span>
                <span className="text-xs font-bold text-slate-400">
                  {currentIndex + 1} / {lessons.length}
                </span>
              </div>

              {/* Duolingo Question Prompt Title */}
              <h2 className="text-xl sm:text-2xl font-black leading-snug text-slate-800 dark:text-white">
                {question.question || question.prompt || "Savolga javob bering:"}
              </h2>

              {/* Duolingo Speaker Button (if audio) */}
              {question.audio_url ? (
                <div className="flex items-center gap-3 pt-1">
                  <button
                    type="button"
                    onClick={() => playAudio(1.0)}
                    className={`group relative grid h-16 w-16 shrink-0 place-items-center rounded-2xl border-2 border-b-4 border-[#1899d6] bg-[#1cb0f6] text-white shadow-lg active:translate-y-1 active:border-b-2 hover:bg-[#1899d6] ${
                      audioPlaying ? "ring-4 ring-[#1cb0f6]/40 animate-pulse" : ""
                    }`}
                  >
                    <span className="text-3xl">🔊</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => playAudio(0.75)}
                    className="flex items-center gap-1.5 rounded-2xl border-2 border-b-4 border-amber-500 bg-amber-400 px-4 py-3 text-xs font-black text-amber-950 shadow-md active:translate-y-1 active:border-b-2 hover:bg-amber-500"
                  >
                    <span className="text-lg">🐢</span> Sekin eshitish
                  </button>
                </div>
              ) : null}

              {/* ─── Exercise Type 1: Word Order / Scrambled sentence (Duolingo Signature) ─── */}
              {question.test_type === "word_order" || question.test_type === "listening_order" ? (
                <div className="space-y-6 pt-2">
                  {/* Sentence Slots Line */}
                  <div className="min-h-24 rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50/70 p-3 flex flex-wrap gap-2 items-center dark:border-navy-700 dark:bg-navy-900/50">
                    {sentenceWords.length ? (
                      sentenceWords.map((w, idx) => (
                        <button
                          key={idx}
                          type="button"
                          disabled={Boolean(result)}
                          onClick={() => handleSentenceWordRemove(idx)}
                          className="rounded-xl border-2 border-b-4 border-slate-200 bg-white px-4 py-2.5 text-sm font-black text-navy-900 shadow-sm transition hover:bg-rose-50 active:translate-y-1 active:border-b-2 dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                        >
                          {w}
                        </button>
                      ))
                    ) : (
                      <span className="text-xs font-bold text-slate-400 italic">
                        Quyidagi so'zlarni bosing va gap tuzing...
                      </span>
                    )}
                  </div>

                  {/* Word Bank Chips */}
                  <div className="flex flex-wrap gap-2.5 justify-center border-t border-slate-100 pt-4 dark:border-white/10">
                    {bankWords.map((tile) => (
                      <button
                        key={tile.id}
                        type="button"
                        disabled={tile.used || Boolean(result)}
                        onClick={() => handleTileClick(tile.id, tile.text)}
                        className={`rounded-2xl border-2 px-4 py-2.5 text-sm font-black transition-all select-none ${
                          tile.used
                            ? "border-slate-200 bg-slate-200/50 text-transparent opacity-30 dark:border-navy-800 dark:bg-navy-900"
                            : "border-slate-200 border-b-4 bg-white text-navy-900 shadow-sm active:translate-y-1 active:border-b-2 hover:bg-slate-50 dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                        }`}
                      >
                        {tile.text}
                      </button>
                    ))}
                  </div>
                </div>
              ) : question.test_type === "true_false" || question.test_type === "listening_tf" ? (
                /* ─── Exercise Type 2: True / False ─── */
                <div className="grid grid-cols-2 gap-4 pt-4">
                  {["To'g'ri", "Noto'g'ri"].map((opt) => {
                    const isSelected = selected.toLowerCase() === opt.toLowerCase();
                    const isCorrectChoice = opt.toLowerCase() === String(question.correct_answer || "").trim().toLowerCase();

                    let btnStyle = "border-slate-200 border-b-4 bg-white hover:bg-slate-50 dark:border-navy-700 dark:bg-navy-800";
                    if (isSelected && !result) {
                      btnStyle = "border-[#84d8ff] border-b-4 bg-[#ddf4ff] text-[#1899d6] dark:border-[#1cb0f6] dark:bg-[#18394a]";
                    } else if (result) {
                      if (isCorrectChoice) {
                        btnStyle = "border-[#58cc02] border-b-4 bg-[#d7ffb8] text-[#2e6b00] dark:bg-[#183617] dark:text-[#a0ff6d]";
                      } else if (isSelected && !isCorrectChoice) {
                        btnStyle = "border-[#ff4b4b] border-b-4 bg-[#ffdfe0] text-[#a01818] dark:bg-[#3d1a1b] dark:text-[#ffa0a0]";
                      }
                    }

                    return (
                      <button
                        key={opt}
                        type="button"
                        disabled={Boolean(result)}
                        onClick={() => {
                          playDuolingoSound("pop");
                          setSelected(opt);
                        }}
                        className={`flex flex-col items-center justify-center gap-2 rounded-3xl p-6 text-base font-black transition-all active:translate-y-1 active:border-b-2 ${btnStyle}`}
                      >
                        <span className="text-3xl">{opt === "To'g'ri" ? "✓" : "✕"}</span>
                        <span>{opt}</span>
                      </button>
                    );
                  })}
                </div>
              ) : question.test_type === "fill_blank" && (!question.options || question.options.length < 2) ? (
                /* ─── Exercise Type 3: Fill in the Blank (Input) ─── */
                <div className="space-y-3 pt-2">
                  <input
                    type="text"
                    value={selected}
                    onChange={(e) => setSelected(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && !result && void submit()}
                    disabled={Boolean(result)}
                    placeholder="Javobingizni yozing..."
                    autoFocus
                    className="w-full rounded-2xl border-2 border-b-4 border-slate-200 bg-white p-4 text-lg font-black text-navy-900 focus:border-[#84d8ff] focus:outline-none dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                  />
                  <p className="text-xs text-slate-400">Javobni yozing va pastdagi "Tekshirish" tugmasini bosing.</p>
                </div>
              ) : (
                /* ─── Exercise Type 4: Multiple Choice (Duolingo 3D Cards) ─── */
                <div className="grid gap-3 pt-2">
                  {(question.options || []).map((opt: string, i: number) => {
                    const isSelected = selected === opt;
                    const isCorrectChoice = opt.trim().toLowerCase() === String(question.correct_answer || "").trim().toLowerCase();

                    let cardClass = "border-slate-200 border-b-4 bg-white text-navy-900 hover:bg-slate-50 dark:border-navy-700 dark:bg-navy-800 dark:text-white";
                    if (isSelected && !result) {
                      cardClass = "border-[#84d8ff] border-b-4 bg-[#ddf4ff] text-[#1899d6] dark:border-[#1cb0f6] dark:bg-[#18394a]";
                    } else if (result) {
                      if (isCorrectChoice) {
                        cardClass = "border-[#58cc02] border-b-4 bg-[#d7ffb8] text-[#2e6b00] dark:bg-[#183617] dark:text-[#a0ff6d]";
                      } else if (isSelected && !isCorrectChoice) {
                        cardClass = "border-[#ff4b4b] border-b-4 bg-[#ffdfe0] text-[#a01818] dark:bg-[#3d1a1b] dark:text-[#ffa0a0]";
                      }
                    }

                    return (
                      <button
                        key={i}
                        type="button"
                        disabled={Boolean(result)}
                        onClick={() => {
                          playDuolingoSound("pop");
                          setSelected(opt);
                        }}
                        className={`flex items-center justify-between rounded-2xl border-2 p-4 text-left text-sm font-black transition-all active:translate-y-1 active:border-b-2 ${cardClass}`}
                      >
                        <span className="flex items-center gap-3">
                          <span className="grid h-8 w-8 place-items-center rounded-xl border border-slate-200 bg-slate-50 text-xs font-black text-slate-600 dark:border-navy-700 dark:bg-navy-900 dark:text-navy-300">
                            {i + 1}
                          </span>
                          <span>{opt}</span>
                        </span>
                        {result && isCorrectChoice ? <span className="text-xl">✓</span> : null}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* ─── Duolingo Sticky Bottom Action Drawer ─── */}
        {!finished && question ? (
          <div
            className={`border-t-2 p-4 transition-all duration-300 ${
              result?.correct
                ? "border-[#b8f28b] bg-[#d7ffb8] dark:border-[#2b5928] dark:bg-[#152e14]"
                : result && !result.correct
                ? "border-[#fba4a6] bg-[#ffdfe0] dark:border-[#6b2528] dark:bg-[#381517]"
                : "border-slate-100 bg-white dark:border-white/10 dark:bg-[#131f24]"
            }`}
          >
            {/* Feedback Message if checked */}
            {result ? (
              <div className="mb-3 flex items-start gap-3">
                <div
                  className={`grid h-10 w-10 shrink-0 place-items-center rounded-full text-xl text-white ${
                    result.correct ? "bg-[#58cc02]" : "bg-[#ff4b4b]"
                  }`}
                >
                  {result.correct ? "✓" : "✕"}
                </div>
                <div className="min-w-0 flex-1">
                  <p
                    className={`text-base font-black ${
                      result.correct
                        ? "text-[#2e6b00] dark:text-[#a0ff6d]"
                        : "text-[#a01818] dark:text-[#ffa0a0]"
                    }`}
                  >
                    {result.correct ? "Ajoyib! Juda to'g'ri!" : "To'g'ri javob:"}
                  </p>
                  {!result.correct ? (
                    <p className="text-sm font-black text-slate-900 dark:text-white mt-0.5">
                      {String(question.correct_answer || "")}
                    </p>
                  ) : null}
                  {question.explanation ? (
                    <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                      💡 {question.explanation}
                    </p>
                  ) : null}
                </div>
              </div>
            ) : null}

            {/* Bottom Button */}
            {!result ? (
              <button
                type="button"
                onClick={submit}
                disabled={!selected || loading}
                className={`w-full rounded-2xl border-2 border-b-4 py-3.5 text-center text-sm font-black uppercase tracking-wider transition-all ${
                  selected && !loading
                    ? "border-[#46a302] bg-[#58cc02] text-white shadow-lg active:translate-y-1 active:border-b-2 hover:bg-[#4cb802] cursor-pointer"
                    : "border-slate-200 bg-slate-200 text-slate-400 cursor-not-allowed dark:border-navy-800 dark:bg-navy-900"
                }`}
              >
                {loading ? "Tekshirilmoqda..." : "Tekshirish"}
              </button>
            ) : (
              <button
                type="button"
                onClick={next}
                className={`w-full rounded-2xl border-2 border-b-4 py-3.5 text-center text-sm font-black uppercase tracking-wider text-white shadow-lg active:translate-y-1 active:border-b-2 ${
                  result.correct
                    ? "border-[#46a302] bg-[#58cc02] hover:bg-[#4cb802]"
                    : "border-[#d62828] bg-[#ff4b4b] hover:bg-[#ff3333]"
                }`}
              >
                {currentIndex + 1 < lessons.length ? "Davom etish →" : "Natijani ko'rish"}
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
  const [addMode, setAddMode] = useState<"library" | "ai" | "manual">("library");
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

      {/* ─── Test Qo'shish Markazi (Segmented Tab Bar) ─── */}
      <div className="rounded-3xl border-2 border-slate-200 bg-white p-5 shadow-sm dark:border-navy-700 dark:bg-navy-900/90">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4 dark:border-white/10">
          <div>
            <h4 className="text-sm font-black uppercase tracking-wider text-navy-900 dark:text-white flex items-center gap-2">
              <span>➕ Modulga Yangi Test Qo'shish</span>
            </h4>
            <p className="text-xs text-slate-500 dark:text-navy-300 mt-0.5">
              Quyidagi 3 xil qulay usuldan birini tanlang:
            </p>
          </div>

          {/* 3-Tab Segmented Controls */}
          <div className="flex rounded-2xl bg-slate-100 p-1 dark:bg-navy-800">
            <button
              type="button"
              onClick={() => setAddMode("library")}
              className={`flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-black transition-all ${
                addMode === "library"
                  ? "bg-white text-[#1cb0f6] shadow-sm dark:bg-navy-900 dark:text-[#1cb0f6]"
                  : "text-slate-600 hover:text-navy-900 dark:text-navy-300"
              }`}
            >
              <span>📂 Kutubxonadan</span>
            </button>

            <button
              type="button"
              onClick={() => setAddMode("ai")}
              className={`flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-black transition-all ${
                addMode === "ai"
                  ? "bg-white text-emerald-600 shadow-sm dark:bg-navy-900 dark:text-emerald-400"
                  : "text-slate-600 hover:text-navy-900 dark:text-navy-300"
              }`}
            >
              <span>✨ Diamondvoy AI</span>
            </button>

            <button
              type="button"
              onClick={() => setAddMode("manual")}
              className={`flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-black transition-all ${
                addMode === "manual"
                  ? "bg-white text-purple-600 shadow-sm dark:bg-navy-900 dark:text-purple-400"
                  : "text-slate-600 hover:text-navy-900 dark:text-navy-300"
              }`}
            >
              <span>✍️ Qo'lda kiritish</span>
            </button>
          </div>
        </div>

        {/* ─── TAB 1: Real Materials Library Picker ─── */}
        {addMode === "library" ? (
          <div className="mt-5 space-y-4 animate-fade-in">
            <div className="rounded-2xl border-2 border-dashed border-[#1cb0f6]/40 bg-[#1cb0f6]/5 p-6 text-center dark:border-[#1cb0f6]/20">
              <div className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-[#1cb0f6]/15 text-2xl text-[#1cb0f6]">
                📂
              </div>
              <h5 className="text-base font-black text-navy-900 dark:text-white">
                O'qituvchi Kutubxonasidagi Testlarni Ulash
              </h5>
              <p className="mx-auto mt-1 max-w-md text-xs text-slate-500 dark:text-navy-300">
                Papkalar daraxti orqali avval yaratilgan istalgan test yoki savollar to'plamini bir necha soniyada ushbu modulga biriktiring.
              </p>

              <button
                type="button"
                onClick={() => setShowLibraryModal(true)}
                className="mt-4 inline-flex items-center gap-2 rounded-2xl border-2 border-b-4 border-[#1899d6] bg-[#1cb0f6] px-6 py-3 text-xs font-black uppercase tracking-wider text-white shadow-md transition-all active:translate-y-1 active:border-b-2 hover:bg-[#1899d6]"
              >
                <span>📂 Kutubxona papkalarini ochish (Popup)</span>
              </button>
            </div>
          </div>
        ) : null}

        {/* ─── TAB 2: AI Diamondvoy Generator ─── */}
        {addMode === "ai" ? (
          <div className="mt-5 space-y-4 animate-fade-in">
            <div className="rounded-2xl border-2 border-emerald-500/20 bg-emerald-500/5 p-4 sm:p-5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-black uppercase tracking-wider text-emerald-800 dark:text-emerald-300 flex items-center gap-1.5">
                  <span>✨ Diamondvoy AI yordamida test yaratish</span>
                </span>
                <span className="rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-[10px] font-black text-emerald-800 dark:text-emerald-200">
                  Modulga to'g'ridan-to'g'ri qo'shiladi va kutubxonada saqlanadi
                </span>
              </div>

              {/* Quick Topic Suggestion Pills */}
              <div className="mt-3 flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] font-bold text-slate-500">Mavzular:</span>
                {[
                  "Present Perfect vs Past Simple",
                  "Irregular Verbs",
                  "Travel & Hotel Vocabulary",
                  "Job Interview Expressions",
                  "Conditional Sentences (0, 1, 2)",
                ].map((sug) => (
                  <button
                    key={sug}
                    type="button"
                    onClick={() => setTopic(sug)}
                    className="rounded-lg border border-emerald-400/40 bg-white px-2 py-0.5 text-[11px] font-bold text-emerald-700 hover:bg-emerald-50 dark:bg-navy-800 dark:text-emerald-300"
                  >
                    + {sug}
                  </button>
                ))}
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_130px]">
                <input
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="Test mavzusi (masalan: English Grammar, Food & Dining, B2 Vocabulary)..."
                  className="rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-emerald-400 focus:outline-none dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                />

                <div className="flex items-center gap-2">
                  <label className="text-xs font-black text-slate-600 dark:text-navy-300 whitespace-nowrap">
                    Soni:
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="25"
                    value={count}
                    onChange={(e) => setCount(Number(e.target.value))}
                    className="w-full rounded-2xl border-2 border-slate-200 bg-white p-3 text-center text-xs font-black text-navy-900 focus:border-emerald-400 focus:outline-none dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                  />
                </div>

                <select
                  value={types}
                  onChange={(e) => setTypes(e.target.value)}
                  className="sm:col-span-2 rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-black text-navy-900 dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                >
                  <option value="multiple_choice,true_false,fill_blank">Aralash (Ko'p tanlovli + True/False + Bo'sh joy to'ldirish)</option>
                  <option value="multiple_choice">Faqat Ko'p tanlovli (MCQ)</option>
                  <option value="true_false">Faqat To'g'ri / Noto'g'ri (True / False)</option>
                  <option value="fill_blank">Faqat Bo'sh joyni to'ldirish (Fill in blank)</option>
                  <option value="word_order">Faqat So'z tartibi (Word Order)</option>
                  <option value="matching">Faqat Moslashtirish (Matching Pairs)</option>
                  <option value="translation">Faqat Tarjima mashqlari</option>
                  <option value="spelling">Faqat Imlo (Spelling)</option>
                  <option value="multiple_choice,true_false,fill_blank,word_order,matching">Barcha turlar aralash</option>
                </select>

                <button
                  type="button"
                  disabled={busy || !topic.trim()}
                  onClick={() => void generate()}
                  className="sm:col-span-2 rounded-2xl border-2 border-b-4 border-[#46a302] bg-[#58cc02] py-3.5 text-center text-xs font-black uppercase tracking-wider text-white shadow-md transition-all active:translate-y-1 active:border-b-2 hover:bg-[#4cb802] disabled:opacity-40"
                >
                  {busy ? "⏳ Diamondvoy testlarni yaratmoqda..." : `💎 Diamondvoy ${count} ta savol yaratib modulga qo'shsin`}
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {/* ─── TAB 3: Manual Test Builder ─── */}
        {addMode === "manual" ? (
          <div className="mt-5 space-y-4 animate-fade-in">
            <div className="rounded-2xl border-2 border-purple-500/20 bg-purple-500/5 p-4 sm:p-5 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-black uppercase tracking-wider text-purple-900 dark:text-purple-300">
                  ✍️ Qo'lda Yangi Test Yaratish
                </span>
                <span className="rounded-full bg-purple-500/20 px-2.5 py-0.5 text-[10px] font-black text-purple-800 dark:text-purple-200">
                  20 ta turli test turi
                </span>
              </div>

              {/* Title and Test Kind Selector */}
              <div className="grid gap-2.5 sm:grid-cols-2">
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Test savoli nomi (masalan: 1-mashq, Vocabulary check)"
                  className="rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                />

                <select
                  value={manualType}
                  onChange={(e) => {
                    setManualType(e.target.value);
                    if (e.target.value === "true_false" || e.target.value === "listening_tf") {
                      setOptions("To'g'ri | Noto'g'ri");
                      setCorrect("To'g'ri");
                    } else if (e.target.value === "matching") {
                      setOptions("apple = olma | book = kitob | pen = ruchka");
                      setCorrect("");
                    }
                  }}
                  className="rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-black text-navy-900 dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                >
                  {ALL_TEST_KINDS.map((k) => (
                    <option key={k.key} value={k.key}>
                      {k.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Audio Section for Listening Test Kinds */}
              {curKindMeta.needsAudio ? (
                <div className="rounded-2xl border-2 border-cyan-400/40 bg-cyan-500/10 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-black text-cyan-900 dark:text-cyan-200 flex items-center gap-1.5">
                      <span>🎧 Audio biriktirish (Majburiy)</span>
                    </span>
                    {audioUploading && (
                      <span className="text-xs text-cyan-600 animate-pulse font-bold">
                        Yuklanmoqda...
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <label className="cursor-pointer rounded-xl border-2 border-b-4 border-cyan-500 bg-cyan-500 px-4 py-2 text-xs font-black text-white shadow-sm hover:bg-cyan-600 active:translate-y-0.5 active:border-b-2">
                      📁 Audio faylni tanlash (MP3, WAV, M4A)
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
                      className="min-w-0 flex-1 rounded-xl border border-line bg-white p-2 text-xs dark:bg-navy-800 dark:border-white/10"
                    />
                  </div>

                  {audioUrl ? (
                    <div className="pt-2 border-t border-cyan-400/20">
                      <audio controls src={audioUrl} className="w-full h-8" />
                    </div>
                  ) : null}
                </div>
              ) : null}

              {/* Question prompt */}
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={2}
                placeholder={
                  manualType === "fill_blank" || manualType === "listening_gap"
                    ? "Savol matni (bo'sh joy uchun _____ ishlating): He _____ a teacher."
                    : manualType === "word_order" || manualType === "listening_order"
                    ? "Aralash so'zlar: teacher / is / He / a"
                    : manualType === "matching"
                    ? "Ko'rsatma: So'zlarni o'zbekcha tarjimasi bilan moslashtiring"
                    : "Savol matni..."
                }
                className="w-full rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-navy-700 dark:bg-navy-800 dark:text-white"
              />

              {/* Dynamic contextual inputs per test type */}
              {manualType === "true_false" || manualType === "listening_tf" ? (
                <div className="flex items-center gap-4 py-1">
                  <span className="text-xs font-black text-slate-700 dark:text-navy-300">To'g'ri javob:</span>
                  <label className="flex items-center gap-1.5 text-xs font-black text-emerald-600 cursor-pointer">
                    <input
                      type="radio"
                      name={`tf_${module.id}`}
                      checked={correct === "To'g'ri"}
                      onChange={() => setCorrect("To'g'ri")}
                      className="accent-emerald-500"
                    />
                    ✓ To'g'ri
                  </label>
                  <label className="flex items-center gap-1.5 text-xs font-black text-rose-600 cursor-pointer">
                    <input
                      type="radio"
                      name={`tf_${module.id}`}
                      checked={correct === "Noto'g'ri"}
                      onChange={() => setCorrect("Noto'g'ri")}
                      className="accent-rose-500"
                    />
                    ✕ Noto'g'ri
                  </label>
                </div>
              ) : manualType === "fill_blank" || manualType === "listening_gap" ? (
                <div className="grid gap-2.5 sm:grid-cols-2">
                  <input
                    value={correct}
                    onChange={(e) => setCorrect(e.target.value)}
                    placeholder="To'g'ri to'ldiriladigan so'z (masalan: is)"
                    className="rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                  />
                  <input
                    value={options}
                    onChange={(e) => setOptions(e.target.value)}
                    placeholder="Qo'shimcha noto'g'ri variantlar (ixtiyoriy, | bilan)"
                    className="rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                  />
                </div>
              ) : manualType === "word_order" || manualType === "listening_order" ? (
                <input
                  value={correct}
                  onChange={(e) => setCorrect(e.target.value)}
                  placeholder="To'g'ri tartibdagi to'liq gap: He is a teacher."
                  className="w-full rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                />
              ) : manualType === "matching" ? (
                <input
                  value={options}
                  onChange={(e) => setOptions(e.target.value)}
                  placeholder="Juftliklar: book = kitob | pen = ruchka | cat = mushuk (| bilan)"
                  className="w-full rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                />
              ) : (
                <div className="grid gap-2.5 sm:grid-cols-2">
                  <input
                    value={options}
                    onChange={(e) => setOptions(e.target.value)}
                    placeholder="Variantlar: A | B | C | D (| bilan ajrating)"
                    className="rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                  />
                  <input
                    value={correct}
                    onChange={(e) => setCorrect(e.target.value)}
                    placeholder="To'g'ri javob matni"
                    className="rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                  />
                </div>
              )}

              <input
                value={explanation}
                onChange={(e) => setExplanation(e.target.value)}
                placeholder="Izoh / Tushuntirish (ixtiyoriy)"
                className="w-full rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-navy-700 dark:bg-navy-800 dark:text-white"
              />

              <button
                type="button"
                disabled={busy}
                onClick={() => void saveManual()}
                className="rounded-2xl border-2 border-b-4 border-purple-600 bg-purple-600 px-6 py-3 text-xs font-black uppercase tracking-wider text-white shadow-md transition-all active:translate-y-1 active:border-b-2 hover:bg-purple-700 disabled:opacity-40"
              >
                + Ushbu test savolini modulga qo'shish
              </button>
            </div>
          </div>
        ) : null}

        {/* Delete module button */}
        <div className="mt-5 flex justify-end border-t border-slate-100 pt-3 dark:border-white/10">
          <button
            type="button"
            disabled={busy}
            onClick={() => void remove()}
            className="rounded-xl border border-rose-400/40 px-3 py-1.5 text-xs font-bold text-rose-600 hover:bg-rose-500/10 dark:text-rose-300 transition"
          >
            Modulni to'liq o'chirish
          </button>
        </div>
      </div>

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

        {/* Selected Test Preview Box */}
        {selectedTest ? (
          <div className="border-t border-line bg-cyan-500/5 p-3.5 dark:border-white/10">
            <div className="flex items-center justify-between">
              <span className="text-xs font-black text-cyan-800 dark:text-cyan-200 flex items-center gap-1.5">
                <span>🧪 Tanlangan: {selectedTest.title}</span>
              </span>
              <span className="text-[11px] font-bold text-ink-500 dark:text-navy-300">
                {selectedTest.question_count} ta savol mavjud
              </span>
            </div>
            {Array.isArray(selectedTest.questions) && selectedTest.questions.length ? (
              <div className="mt-2 space-y-1 max-h-24 overflow-y-auto pr-1">
                {selectedTest.questions.slice(0, 3).map((q: Row, qi: number) => (
                  <div key={qi} className="text-[11px] text-ink-600 dark:text-navy-200 truncate flex items-center gap-1">
                    <span className="font-bold text-cyan-600">#{qi + 1}</span>
                    <span>{q.question || q.prompt || q.text || "Savol"}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

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
