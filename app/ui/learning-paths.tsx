"use client";
import { FormEvent, MouseEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useWebT } from "./web-i18n";
import { TestCompletionActions, type TestReviewItem } from "./test-completion-actions";

type Row = Record<string, any>;
type ApiFetch = (path: string, options?: any) => Promise<any>;
const TRACKS_CACHE_KEY = "diamond_learning_tracks_cache_v2";
const covers = ["star", "trophy", "chest", "dolphin", "jellyfish", "ship"];
const image = (key: string) => `/learning-paths/${covers.includes(key) ? key : "star"}.png`;
const COVER_LABELS: Record<string, string> = {
  star: "Yulduz",
  trophy: "Kubok",
  chest: "Sandiq",
  dolphin: "Delfin",
  jellyfish: "Meduza",
  ship: "Kema",
};
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
  const [activeFinalExamTrack, setActiveFinalExamTrack] = useState<Row | null>(null);
  const [selectedSubject, setSelectedSubject] = useState<string>("");

  // Extract distinct subjects from available tracks (ignoring any "all" / "barchasi")
  const subjects = useMemo(() => {
    const list: string[] = [];
    for (const tr of tracks) {
      const sub = String(tr.subject || "").trim();
      if (
        sub &&
        !["all", "barchasi", "barcha fanlar", "все"].includes(sub.toLowerCase()) &&
        !list.some((s) => s.toLowerCase() === sub.toLowerCase())
      ) {
        list.push(sub);
      }
    }
    return list;
  }, [tracks]);

  // Keep selected subject valid (defaults to first subject, never "all")
  useEffect(() => {
    if (subjects.length > 0) {
      setSelectedSubject((curr) => {
        if (curr && subjects.some((s) => s.toLowerCase() === curr.toLowerCase())) {
          return curr;
        }
        return subjects[0];
      });
    }
  }, [subjects]);

  const load = useCallback(async () => {
    try {
      const data = await apiFetch("/student/learning-tracks");
      const items = Array.isArray(data?.items) ? data.items : [];
      setTracks(items);
      try {
        localStorage.setItem(
          TRACKS_CACHE_KEY,
          JSON.stringify({ items, timestamp: Date.now() })
        );
      } catch {}
    } catch (e) {
      if (!tracks.length) {
        setError(errorText(e, t("learning.loadError", "O'quv yo'li yuklanmadi.")));
      }
    } finally {
      setLoading(false);
    }
  }, [apiFetch, t, tracks.length]);

  // Load from local storage cache immediately for instant render, and preload images
  useEffect(() => {
    covers.forEach((key) => {
      try {
        const img = new Image();
        img.src = image(key);
      } catch {}
    });

    try {
      const raw = localStorage.getItem(TRACKS_CACHE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed?.items) && parsed.items.length > 0) {
          setTracks(parsed.items);
          setLoading(false);
        }
      }
    } catch {}

    void load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Filter tracks by selected subject
  const filteredTracks = useMemo(() => {
    if (!selectedSubject) {
      return subjects.length > 0
        ? tracks.filter((t) => String(t.subject || "").trim().toLowerCase() === subjects[0].toLowerCase())
        : tracks;
    }
    return tracks.filter(
      (t) => String(t.subject || "").trim().toLowerCase() === selectedSubject.toLowerCase()
    );
  }, [tracks, selectedSubject, subjects]);

  if (loading && !tracks.length) {
    return (
      <section className="m-6 flex min-h-72 items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-12 w-12 animate-spin rounded-full border-4 border-[#002DFF] border-t-transparent" />
          <p className="text-xs font-black uppercase tracking-wider text-slate-500">O'quv yo'li yuklanmoqda...</p>
        </div>
      </section>
    );
  }

  return (
    <section className="mx-auto w-full max-w-2xl px-3 py-4 sm:px-6">
      {/* ─── Fan Tanlash / Subject Selector Bar (Barchasi olib tashlangan) ─── */}
      <div className="sticky top-2 z-30 mb-6 flex flex-wrap items-center justify-between gap-2 rounded-2xl border-2 border-b-4 border-slate-200 bg-white/95 p-2.5 shadow-sm backdrop-blur-md dark:border-navy-700 dark:bg-navy-900/95">
        <div className="flex flex-wrap items-center gap-2">
          {subjects.map((sub) => {
            const lower = sub.toLowerCase();
            const flag = lower.includes("ingliz") || lower.includes("english")
              ? "🇬🇧"
              : lower.includes("rus")
              ? "🇷🇺"
              : lower.includes("matem")
              ? "📐"
              : "📚";
            const active = selectedSubject.toLowerCase() === lower;
            return (
              <button
                key={sub}
                type="button"
                onClick={() => setSelectedSubject(sub)}
                className={`flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-black uppercase tracking-wider transition ${
                  active
                    ? "border-2 border-b-4 border-[#001A88] bg-[#002DFF] text-white shadow-md shadow-blue-500/25 active:translate-y-0.5 active:border-b-2"
                    : "border border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100 dark:border-navy-700 dark:bg-navy-800 dark:text-navy-200"
                }`}
              >
                <span>{flag}</span>
                <span>{sub}</span>
              </button>
            );
          })}
        </div>

        <span className="shrink-0 rounded-xl bg-slate-100 px-3 py-1.5 text-xs font-black text-slate-500 dark:bg-navy-800 dark:text-navy-300">
          {filteredTracks.length} ta track
        </span>
      </div>

      {error ? (
        <p className="mb-4 rounded-2xl border-2 border-b-4 border-rose-300 bg-rose-50 p-3.5 text-sm font-bold text-rose-700 dark:border-rose-900 dark:bg-rose-950/50 dark:text-rose-300">
          {error}
        </p>
      ) : null}

      {/* Tracks List */}
      <div className="flex flex-col space-y-4">
        {filteredTracks.map((track, i) => {
          const nextTrack = filteredTracks[i + 1];
          const nextTrackUnlocked = nextTrack ? !nextTrack.locked : false;
          const nextTrackStarted = nextTrack && Array.isArray(nextTrack.modules)
            ? nextTrack.modules.some((m: Row) => m.progress?.status === "passed")
            : false;

          return (
            <DuolingoTrack
              key={track.id}
              track={track}
              index={i}
              totalTracks={filteredTracks.length}
              hasNext={i < filteredTracks.length - 1}
              hasPrev={i > 0}
              nextTrackTitle={nextTrack?.title}
              nextTrackUnlocked={nextTrackUnlocked}
              nextTrackStarted={nextTrackStarted}
              apiFetch={apiFetch}
              onStartModule={(mod) => {
                playDuolingoSound("pop");
                setActiveModule(mod);
              }}
              onStartFinalExam={(t) => {
                playDuolingoSound("pop");
                setActiveFinalExamTrack(t);
              }}
            />
          );
        })}
      </div>

      {!filteredTracks.length ? (
        <div className="rounded-3xl border-2 border-dashed border-slate-300 p-12 text-center text-slate-500 dark:border-navy-700 dark:text-navy-300">
          <span className="text-4xl">🌱</span>
          <p className="mt-3 text-base font-black text-navy-900 dark:text-white">
            {selectedSubject
              ? `"${selectedSubject}" fani bo'yicha hali o'quv yo'li mavjud emas.`
              : "O'quv yo'li hali tashkillashtirilmagan."}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            O'qituvchingiz yangi track va modullarni taqdim etganda shu yerda ko'rinadi.
          </p>
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

      {activeFinalExamTrack ? (
        <FinalExamPlayerModal
          track={activeFinalExamTrack}
          apiFetch={apiFetch}
          onClose={() => {
            setActiveFinalExamTrack(null);
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
  totalTracks = 1,
  hasNext = false,
  hasPrev = false,
  nextTrackTitle = "",
  nextTrackUnlocked = false,
  nextTrackStarted = false,
  apiFetch,
  onStartModule,
  onStartFinalExam,
}: {
  track: Row;
  index: number;
  totalTracks?: number;
  hasNext?: boolean;
  hasPrev?: boolean;
  nextTrackTitle?: string;
  nextTrackUnlocked?: boolean;
  nextTrackStarted?: boolean;
  apiFetch: ApiFetch;
  onStartModule: (module: Row) => void;
  onStartFinalExam: (track: Row) => void;
}) {
  const locked = Boolean(track.locked);
  const modules = Array.isArray(track.modules) ? track.modules : [];

  const passedCount = modules.filter((m: Row) => m.progress?.status === "passed").length;
  const progressPercent = modules.length ? Math.round((passedCount / modules.length) * 100) : 0;
  const allPassed = modules.length > 0 && passedCount === modules.length;
  const finalExam = (track as any).final_exam || {};
  const finalExamPassed = Boolean(finalExam.passed);
  const examReady = allPassed && !finalExamPassed;
  const chestUnlocked = allPassed && finalExamPassed;

  const [showChestModal, setShowChestModal] = useState(false);
  const [claimingCert, setClaimingCert] = useState(false);
  const [certRewardData, setCertRewardData] = useState<Row | null>(null);
  const [certError, setCertError] = useState("");

  const certAlreadyClaimed = Boolean(
    certRewardData ||
    (track as any).certificate_claimed ||
    (track as any).final_exam?.certificate_id ||
    (track as any).final_exam?.certificate
  );

  // Stop pulsing if:
  // 1. Certificate has already been claimed / finished (certAlreadyClaimed)
  // 2. Or the student moved to the next track (nextTrackStarted or (hasNext && nextTrackUnlocked))
  const shouldPulseChest = chestUnlocked && !certAlreadyClaimed && !nextTrackStarted && !(hasNext && nextTrackUnlocked);

  const handleFinalChestClick = async () => {
    setShowChestModal(true);
    setCertError("");
    if (chestUnlocked && !certRewardData) {
      setClaimingCert(true);
      try {
        const res = await apiFetch(`/student/learning-tracks/${track.id}/certificate`, { method: "POST" });
        setCertRewardData(res);
        playDuolingoSound("complete");
      } catch (err: any) {
        setCertError(err?.message || "Sertifikat yuklanmadi.");
      } finally {
        setClaimingCert(false);
      }
    } else if (chestUnlocked) {
      playDuolingoSound("chest");
    } else if (examReady) {
      playDuolingoSound("pop");
    }
  };

  // Diamond Education Logo Brand Themes by index (Royal Electric Blue -> Deep Sapphire Navy -> Diamond Cyan -> Royal Cobalt)
  const unitGradients = [
    {
      bg: "bg-gradient-to-r from-[#002DFF] via-[#1429f2] to-[#001A88]",
      border: "border-[#001A88]",
      accent: "bg-[#001A88]",
      badge: "bg-[#000B3B]/40",
    },
    {
      bg: "bg-gradient-to-r from-[#001A88] via-[#000B3B] to-[#0a256e]",
      border: "border-[#000B3B]",
      accent: "bg-[#000B3B]",
      badge: "bg-[#000B3B]/40",
    },
    {
      bg: "bg-gradient-to-r from-[#0284c7] via-[#002DFF] to-[#001A88]",
      border: "border-[#0369a1]",
      accent: "bg-[#0369a1]",
      badge: "bg-[#001A88]/40",
    },
    {
      bg: "bg-gradient-to-r from-[#1d4ed8] via-[#1e40af] to-[#001A88]",
      border: "border-[#1e3a8a]",
      accent: "bg-[#1e3a8a]",
      badge: "bg-[#001A88]/40",
    },
  ];
  const unitColor = unitGradients[index % unitGradients.length];

  // Organic pseudo-random offset for snake trail (tasodifiy joylashuv, chap va o'ngga)
  const getModuleOffset = useCallback((moduleId: number, order: number): number => {
    const hash = Math.sin((moduleId || order + 1) * 997 + order * 1237) * 10000;
    const pseudoRnd = Math.abs(hash - Math.floor(hash));
    const side = (order % 2 === 0) ? -1 : 1;
    const magnitude = 28 + pseudoRnd * 48; // 28px to 76px
    return Math.round(side * magnitude);
  }, []);

  // Continuous winding snake path ("ilon izi") connecting all nodes, chest, and adjacent tracks
  const snakePathD = useMemo(() => {
    if (!modules.length) return "";
    const cx = 192;
    const stepY = 116;
    const startY = 56;
    const points: { x: number; y: number }[] = [];

    // If hasPrev (Unit 2, Unit 3...), incoming snake trail enters from top center
    if (hasPrev) {
      points.push({ x: cx, y: 0 });
    }

    modules.forEach((mod: any, i: number) => {
      const xOffset = getModuleOffset(Number(mod.id), i);
      points.push({ x: cx + xOffset, y: startY + i * stepY });
    });

    // Final chest center
    const chestY = startY + modules.length * stepY + 28;
    points.push({ x: cx, y: chestY });

    // If hasNext, snake trail CONTINUES downwards past the chest to connect seamlessly with the next track!
    if (hasNext) {
      points.push({ x: cx, y: chestY + 54 });
    }

    if (points.length < 2) return "";

    let d = `M ${points[0].x} ${points[0].y}`;
    for (let i = 0; i < points.length - 1; i++) {
      const p1 = points[i];
      const p2 = points[i + 1];
      const dy = (p2.y - p1.y) * 0.55;
      const cp1x = p1.x;
      const cp1y = p1.y + dy;
      const cp2x = p2.x;
      const cp2y = p2.y - dy;
      d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
    }
    return d;
  }, [modules, track.id, hasPrev, hasNext]);

  const svgHeight = useMemo(() => {
    const base = Math.max(200, modules.length * 116 + 180);
    return hasNext ? base + 40 : base;
  }, [modules.length, hasNext]);

  return (
    <article className={`relative select-none`}>
      {/* Top continuous road connector coming from previous track */}
      {hasPrev ? (
        <div className="mx-auto -mb-2 flex justify-center relative z-0 pointer-events-none">
          <div className="w-5 h-5 bg-gradient-to-b from-[#001A88] via-[#002DFF] to-[#001A88] rounded-t-sm relative border-x-2 border-slate-300 dark:border-navy-700 shadow-sm flex items-center justify-center">
            <div className="w-0.5 h-full border-r-2 border-dashed border-white/80" />
          </div>
        </div>
      ) : null}

      {/* Diamond Logo Themed Unit Header Banner */}
      <header
        className={`relative overflow-hidden rounded-3xl border-2 border-b-[6px] ${unitColor.border} ${unitColor.bg} p-5 text-white shadow-xl shadow-blue-950/20`}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <span className="inline-block rounded-lg bg-black/25 px-2.5 py-1 text-[11px] font-black uppercase tracking-wider text-white backdrop-blur-sm">
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
            <span className="rounded-2xl bg-white/20 px-3.5 py-1.5 text-xs font-black text-white backdrop-blur-sm shadow-sm">
              {locked ? "🔒 Qulflangan" : `${passedCount}/${modules.length} modul`}
            </span>
          </div>
        </div>

        {/* Unit Progress Bar with Diamond Cyan Crystal glow */}
        <div className="mt-4 flex items-center gap-3">
          <div className="h-3.5 min-w-0 flex-1 overflow-hidden rounded-full bg-black/30 p-0.5">
            <div
              className="h-full rounded-full bg-gradient-to-r from-[#38bdf8] to-[#00e5ff] transition-all duration-500 shadow-[0_0_10px_rgba(56,189,248,0.5)]"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <span className="text-xs font-black text-white">{progressPercent}%</span>
        </div>
      </header>

      {/* Duolingo Winding Stepping Stones Path */}
      <div className="relative mx-auto mt-8 max-w-sm py-4">
        {/* Continuous Snake Trail SVG ("Ilon Izi") */}
        {snakePathD ? (
          <svg
            className="absolute left-1/2 top-4 -translate-x-1/2 pointer-events-none overflow-visible"
            width="384"
            height={svgHeight}
            viewBox={`0 0 384 ${svgHeight}`}
            fill="none"
          >
            <defs>
              <linearGradient id={`snake-grad-${track.id}`} x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#38bdf8" />
                <stop offset="50%" stopColor="#002DFF" />
                <stop offset="100%" stopColor="#001A88" />
              </linearGradient>
            </defs>

            {/* Road Bed / Shadow track */}
            <path
              d={snakePathD}
              stroke="currentColor"
              className="text-slate-300/80 dark:text-navy-700/80"
              strokeWidth="22"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {/* Glowing Brand Gradient Inner Trail */}
            <path
              d={snakePathD}
              stroke={`url(#snake-grad-${track.id})`}
              strokeWidth="10"
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity="0.85"
            />

            {/* Stepping Stones / Cobblestones center line */}
            <path
              d={snakePathD}
              stroke="#ffffff"
              strokeWidth="3.5"
              strokeDasharray="6 10"
              strokeLinecap="round"
              opacity="0.85"
            />
          </svg>
        ) : null}

        {/* Winding Trail Column */}
        <div className="relative z-10 flex flex-col items-center gap-7">
          {modules.map((module: Row, order: number) => {
            const xOffset = getModuleOffset(Number(module.id), order);

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
              </div>
            );
          })}

          {/* Final Brand Chest Node at the end of the track */}
          <div className="relative flex flex-col items-center mt-3">
            {/* Solid Opaque Backing Disc to block snake path underneath */}
            <div className="absolute h-22 w-22 sm:h-24 sm:w-24 rounded-full bg-white dark:bg-[#070d1e] shadow-md pointer-events-none" />

            {/* 3D Circular Chest Pushable Button - ALWAYS COLORFUL, NEVER GRAY */}
            <button
              type="button"
              onClick={handleFinalChestClick}
              className={`group relative grid h-20 w-20 sm:h-22 sm:w-22 shrink-0 place-items-center rounded-full border-2 transition-all duration-150 select-none ${
                chestUnlocked
                  ? `border-[#001A88] border-b-[8px] bg-gradient-to-b from-[#1429f2] to-[#001A88] text-white shadow-xl shadow-blue-900/30 ring-4 ring-[#002DFF]/50 active:translate-y-1.5 active:border-b-[2px] active:shadow-none hover:scale-105 hover:brightness-110 cursor-pointer ${
                      shouldPulseChest ? "animate-pulse" : ""
                    }`
                  : examReady
                  ? "border-[#001A88] border-b-[8px] bg-gradient-to-b from-[#1429f2] to-[#002DFF] text-white shadow-xl shadow-blue-600/30 ring-4 ring-[#002DFF]/60 active:translate-y-1.5 active:border-b-[2px] active:shadow-none hover:scale-105 hover:brightness-110 cursor-pointer animate-pulse"
                  : "border-[#001A88] border-b-[8px] bg-gradient-to-b from-[#1429f2] via-[#002DFF] to-[#001A88] text-white shadow-lg shadow-blue-900/20 ring-4 ring-[#002DFF]/30 cursor-pointer active:translate-y-1.5 active:border-b-[2px] active:shadow-none hover:scale-105 hover:brightness-105"
              }`}
            >
              <div className="relative h-full w-full p-2 flex items-center justify-center">
                <img
                  src="/learning-paths/chest.png"
                  alt="Sandiq"
                  className="h-full w-full rounded-full object-contain drop-shadow-md transition-all"
                />
                {!chestUnlocked && !examReady ? (
                  <div className="absolute inset-0 grid place-items-center">
                    <span className="grid h-7 w-7 place-items-center rounded-full bg-[#000B3B] border border-blue-400 text-xs text-blue-200 shadow-md">
                      🔒
                    </span>
                  </div>
                ) : examReady ? (
                  <div className="absolute -bottom-1 -right-1 grid h-6 w-6 place-items-center rounded-full border-2 border-white bg-[#002DFF] text-[11px] text-white shadow-md">
                    ⚡
                  </div>
                ) : certAlreadyClaimed ? (
                  <div className="absolute -bottom-1 -right-1 grid h-6 w-6 place-items-center rounded-full border-2 border-white bg-emerald-500 text-[11px] font-bold text-white shadow-md">
                    ✓
                  </div>
                ) : (
                  <div className="absolute -bottom-1 -right-1 grid h-6 w-6 place-items-center rounded-full border-2 border-white bg-[#002DFF] text-[11px] text-white shadow-md">
                    ✨
                  </div>
                )}
              </div>
            </button>

            {chestUnlocked && !certAlreadyClaimed ? (
              <span className="mt-2 text-xs font-black uppercase tracking-wider text-[#002DFF] dark:text-[#38bdf8]">
                🎓 Sertifikat & Mukofot
              </span>
            ) : examReady ? (
              <span className="mt-2 text-xs font-black uppercase tracking-wider text-[#002DFF] dark:text-[#38bdf8]">
                ⚡ Yakuniy Imtihon
              </span>
            ) : null}
          </div>
        </div>

        {/* Bottom continuous road connector leading into next track */}
        {hasNext ? (
          <div className="flex justify-center -mt-2 -mb-4 relative z-0 pointer-events-none">
            <div className="w-5 h-6 bg-gradient-to-b from-[#001A88] via-[#002DFF] to-[#001A88] rounded-b-sm relative border-x-2 border-slate-300 dark:border-navy-700 shadow-sm flex items-center justify-center">
              <div className="w-0.5 h-full border-r-2 border-dashed border-white/80" />
            </div>
          </div>
        ) : null}
      </div>

      {/* Pop-up Modal for Final Chest / Certificate Celebration via createPortal */}
      {showChestModal && typeof document !== "undefined"
        ? createPortal(
            <div
              className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/75 p-4 backdrop-blur-md animate-fade-in"
              onClick={() => setShowChestModal(false)}
            >
              <div
                className="relative w-full max-w-md overflow-hidden rounded-3xl border-2 border-[#002DFF]/40 bg-white p-6 shadow-2xl dark:border-[#002DFF]/40 dark:bg-[#0f172a] animate-scale-up"
                onClick={(e) => e.stopPropagation()}
              >
                {/* Close Button */}
                <button
                  type="button"
                  onClick={() => setShowChestModal(false)}
                  className="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-white/10 dark:hover:text-white transition"
                >
                  ✕
                </button>

                {chestUnlocked ? (
                  <div className="flex flex-col items-center text-center">
                    {/* Animated Chest & Sparkles */}
                    <div className="relative my-2">
                      <div className="h-28 w-28 rounded-3xl bg-gradient-to-tr from-[#1429f2] to-[#002DFF] p-2 shadow-xl ring-4 ring-[#002DFF]/40 flex items-center justify-center animate-bounce">
                        <img src="/learning-paths/chest.png" alt="Sandiq" className="h-full w-full object-contain" />
                      </div>
                      <span className="absolute -top-2 -right-2 text-2xl animate-spin">✨</span>
                      <span className="absolute -bottom-1 -left-2 text-2xl animate-pulse">🌟</span>
                    </div>

                    <span className="rounded-full bg-[#002DFF]/10 px-3 py-1 text-xs font-black uppercase tracking-wider text-[#002DFF] dark:text-[#38bdf8]">
                      Bo'lim yakunlandi
                    </span>

                    <h3 className="mt-2 text-2xl font-black text-navy-900 dark:text-white">
                      🎉 Tabriklaymiz!
                    </h3>

                    <p className="mt-1 text-xs text-slate-600 dark:text-navy-200 max-w-sm">
                      Siz «<strong>{track.title}</strong>» bo'limidagi barcha modullarni a'lo darajada tamomlab, rasmiy sertifikat va mukofotlarni qo'lga kiritdingiz!
                    </p>

                    {/* Dual Reward Badges */}
                    <div className="mt-4 grid grid-cols-2 gap-3 w-full">
                      <div className="rounded-2xl border-2 border-blue-400/30 bg-blue-500/10 p-3 text-center">
                        <span className="text-xl">💎</span>
                        <p className="text-base font-black text-[#002DFF] dark:text-[#38bdf8] mt-0.5">
                          +50 D'Point
                        </p>
                        <p className="text-[10px] text-blue-600/80 font-bold">Reyting uchun</p>
                      </div>

                      <div className="rounded-2xl border-2 border-amber-400/30 bg-amber-500/10 p-3 text-center">
                        <span className="text-xl">🪙</span>
                        <p className="text-base font-black text-amber-700 dark:text-amber-300 mt-0.5">
                          +50 D'Coin
                        </p>
                        <p className="text-[10px] text-amber-600/80 font-bold">Sovg'alar uchun</p>
                      </div>
                    </div>

                    {/* Certificate Card */}
                    {claimingCert ? (
                      <div className="mt-5 flex items-center justify-center gap-2 py-4 text-xs font-bold text-slate-500">
                        <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#002DFF] border-t-transparent" />
                        <span>Sertifikat rasmiylashtirilmoqda...</span>
                      </div>
                    ) : certRewardData?.certificate ? (
                      <div className="mt-4 w-full rounded-2xl border-2 border-blue-200 bg-gradient-to-br from-blue-50/80 to-indigo-50/80 p-4 text-left dark:border-blue-800/40 dark:bg-blue-950/30">
                        <div className="flex items-center gap-2.5">
                          <span className="text-2xl">🎓</span>
                          <div>
                            <p className="text-xs font-black text-blue-950 dark:text-blue-200">
                              {certRewardData.certificate.course_title || track.title}
                            </p>
                            <p className="text-[10px] font-mono text-blue-700 dark:text-blue-400">
                              ID: {certRewardData.certificate.certificate_id}
                            </p>
                          </div>
                        </div>

                        <div className="mt-3 flex flex-col gap-2">
                          <a
                            href={`/api/student/certificates/${certRewardData.certificate.certificate_id}/pdf`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center justify-center gap-2 rounded-xl border-2 border-b-4 border-[#001A88] bg-[#002DFF] hover:bg-[#1429f2] py-2.5 px-4 text-xs font-black text-white shadow-md transition active:scale-98 active:border-b-2"
                          >
                            <span>📄 Sertifikatni PDF ko'rish / Yuklab olish</span>
                          </a>
                        </div>
                      </div>
                    ) : certError ? (
                      <p className="mt-3 text-xs text-rose-500">{certError}</p>
                    ) : null}

                    <p className="mt-3 text-[11px] text-slate-400 dark:text-navy-400">
                      💡 Sertifikat shuningdek Profilingizning <strong>«🎓 Sertifikatlarim»</strong> bo'limida doimiy saqlandi.
                    </p>

                    <button
                      type="button"
                      onClick={() => setShowChestModal(false)}
                      className="mt-4 w-full rounded-2xl border-2 border-b-4 border-slate-300 bg-slate-100 py-3 text-center text-xs font-black uppercase tracking-wider text-slate-700 hover:bg-slate-200 active:translate-y-0.5 active:border-b-2 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                    >
                      Yopish
                    </button>
                  </div>
                ) : examReady ? (
                  <div className="flex flex-col items-center text-center">
                    <div className="relative my-2">
                      <div className="h-24 w-24 rounded-3xl bg-gradient-to-tr from-[#002DFF] via-indigo-600 to-[#001A88] p-2 shadow-xl ring-4 ring-blue-400/40 flex items-center justify-center animate-pulse">
                        <span className="text-5xl">🏆</span>
                      </div>
                    </div>

                    <h3 className="mt-2 text-2xl font-black text-navy-900 dark:text-white">
                      🎓 Yakuniy Imtihon
                    </h3>

                    <p className="mt-2 text-xs text-slate-600 dark:text-slate-300 max-w-sm leading-relaxed">
                      Siz barcha modullarni muvaffaqiyatli tamomladingiz! Endi rasmiy <strong>Sertifikat</strong> olish va keyingi trackni ochish uchun ushbu yakuniy imtihonni topshiring.
                    </p>

                    <div className="mt-4 grid grid-cols-2 gap-3 w-full">
                      <div className="rounded-2xl border border-blue-200 bg-blue-50 p-3 text-center dark:border-blue-800/40 dark:bg-blue-950/30">
                        <p className="text-[10px] font-bold uppercase text-slate-400">O'tish bali</p>
                        <p className="text-base font-black text-[#002DFF] dark:text-[#38bdf8] mt-0.5">
                          {track.passing_score || 70}%
                        </p>
                      </div>
                      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-center dark:border-amber-800/40 dark:bg-amber-950/30">
                        <p className="text-[10px] font-bold uppercase text-amber-600">Mukofot</p>
                        <p className="text-base font-black text-amber-700 dark:text-amber-300 mt-0.5">
                          +50 D'Point & Coin
                        </p>
                      </div>
                    </div>

                    <div className="mt-3 rounded-2xl bg-blue-50 p-3 text-left text-xs font-bold text-blue-900 dark:bg-blue-950/40 dark:text-blue-200 border border-blue-200 dark:border-blue-800/50">
                      💡 Bu imtihonda oldingi barcha modullardagi savollar <strong>aralash holda</strong> tushadi.
                    </div>

                    <button
                      type="button"
                      onClick={() => {
                        setShowChestModal(false);
                        onStartFinalExam(track);
                      }}
                      className="mt-5 w-full rounded-2xl border-2 border-b-4 border-[#001A88] bg-[#002DFF] py-3.5 text-center text-sm font-black uppercase tracking-wider text-white shadow-xl shadow-blue-600/30 active:translate-y-1 active:border-b-2 hover:bg-[#1429f2] cursor-pointer"
                    >
                      🚀 Imtihonni boshlash
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center text-center">
                    {/* Locked Chest */}
                    <div className="relative my-2">
                      <div className="h-24 w-24 rounded-3xl bg-gradient-to-tr from-[#1429f2] to-[#002DFF] p-2 shadow-md ring-4 ring-[#002DFF]/40 flex items-center justify-center">
                        <img src="/learning-paths/chest.png" alt="Sandiq" className="h-full w-full object-contain drop-shadow-md" />
                      </div>
                      <div className="absolute inset-0 grid place-items-center">
                        <span className="grid h-10 w-10 place-items-center rounded-full bg-[#000B3B] border-2 border-blue-400 text-lg text-blue-200 shadow-lg">
                          🔒
                        </span>
                      </div>
                    </div>

                    <h3 className="mt-2 text-xl font-black text-navy-900 dark:text-white">
                      Yakuniy Sandiq Qulflangan
                    </h3>

                    <p className="mt-2 text-xs text-slate-600 dark:text-slate-300 max-w-sm leading-relaxed">
                      Ushbu maxsus sandiq ichida siz uchun rasmiy <strong>Sertifikat</strong> hamda <strong>+50 D'Point</strong> va <strong>+50 D'Coin</strong> mukofoti saqlangan.
                    </p>

                    <div className="mt-4 w-full rounded-2xl bg-slate-50 p-3.5 dark:bg-slate-800/80 border border-slate-100 dark:border-slate-700">
                      <div className="flex items-center justify-between text-xs font-bold text-slate-700 dark:text-slate-200 mb-2">
                        <span>O'tilgan darslar:</span>
                        <span className="font-black text-[#002DFF] dark:text-[#38bdf8]">{passedCount} / {modules.length} modul ({progressPercent}%)</span>
                      </div>
                      <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-900">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-[#002DFF] to-[#38bdf8] transition-all duration-300"
                          style={{ width: `${progressPercent}%` }}
                        />
                      </div>
                      <p className="mt-2 text-[11px] font-bold text-[#002DFF] dark:text-[#38bdf8]">
                        Sandiqni ochish uchun yana {modules.length - passedCount} ta modulni yakunlang!
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={() => setShowChestModal(false)}
                      className="mt-5 w-full rounded-2xl border-2 border-b-4 border-[#001A88] bg-[#002DFF] py-3 text-center text-xs font-black uppercase tracking-wider text-white shadow-md hover:bg-[#1429f2] active:translate-y-0.5 active:border-b-2"
                    >
                      Tushundim, davom etaman →
                    </button>
                  </div>
                )}
              </div>
            </div>,
            document.body
          )
        : null}
    </article>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   DUOLINGO STEPPING STONE (3D Pushable Circular Node with Floating Speech Bubble)
   ═══════════════════════════════════════════════════════════════════════════════ */

function SegmentedProgressRing({
  total,
  completed,
  radius = 46,
  strokeWidth = 4.5,
}: {
  total: number;
  completed: number;
  radius?: number;
  strokeWidth?: number;
}) {
  const count = Math.min(5, Math.max(1, total));
  const size = (radius + strokeWidth) * 2 + 10;
  const cx = size / 2;
  const cy = size / 2;

  // Ishlangan mavzu: to'qroq Diamond brand ko'k (Light: #1429F2 / Dark: #00F0FF)
  // Ishlanmagan mavzu: ochroq Diamond ko'k (Light: #93C5FD / Dark: rgba(0, 240, 255, 0.25))
  if (count === 1) {
    const isDone = completed >= 1;
    return (
      <svg
        width={size}
        height={size}
        className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 overflow-visible"
        viewBox={`0 0 ${size} ${size}`}
      >
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke={isDone ? "#1429F2" : "#93C5FD"}
          strokeWidth={isDone ? strokeWidth + 0.8 : strokeWidth}
          className={isDone ? "stroke-[#1429F2] dark:stroke-[#00F0FF]" : "stroke-[#93C5FD] dark:stroke-[#00F0FF]/25"}
        />
      </svg>
    );
  }

  // Multi-segment circular ring (2 to 5 arcs) with distinct gaps ("uzuk-uzuk chiziqlar")
  const gapDeg = count === 2 ? 30 : count === 3 ? 22 : count === 4 ? 18 : 14;
  const segDeg = 360 / count - gapDeg;
  const segments = [];

  for (let i = 0; i < count; i++) {
    const startAngle = -90 + i * (360 / count) + gapDeg / 2;
    const endAngle = startAngle + segDeg;

    const startRad = (startAngle * Math.PI) / 180;
    const endRad = (endAngle * Math.PI) / 180;

    const x1 = cx + radius * Math.cos(startRad);
    const y1 = cy + radius * Math.sin(startRad);
    const x2 = cx + radius * Math.cos(endRad);
    const y2 = cy + radius * Math.sin(endRad);

    const largeArc = segDeg > 180 ? 1 : 0;
    const d = `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`;
    const isDone = i < completed;

    segments.push(
      <path
        key={i}
        d={d}
        fill="none"
        stroke={isDone ? "#1429F2" : "#93C5FD"}
        strokeWidth={isDone ? strokeWidth + 0.8 : strokeWidth}
        strokeLinecap="round"
        className={`transition-all duration-300 ${
          isDone ? "stroke-[#1429F2] dark:stroke-[#00F0FF]" : "stroke-[#93C5FD] dark:stroke-[#00F0FF]/25"
        }`}
      />
    );
  }

  return (
    <svg
      width={size}
      height={size}
      className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 overflow-visible"
      viewBox={`0 0 ${size} ${size}`}
    >
      {segments}
    </svg>
  );
}

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
  const isFailed = progress.status === "failed";
  const isActive = !isLocked && !isPassed;
  const score = Number(progress.best_score || 0);
  const stars = isPassed ? (score >= 95 ? 3 : score >= 85 ? 2 : 1) : 0;
  const lessons = Array.isArray(module.lessons) ? module.lessons : [];
  const topicKeys = (Array.isArray(module.topic_keys) ? module.topic_keys : [])
    .map((t: any) => String(t || "").trim())
    .filter(Boolean);
  const totalTopics = Math.min(5, Math.max(1, module.total_topics || (topicKeys.length > 0 ? topicKeys.length : 1)));
  const completedTopics = isLocked
    ? 0
    : Math.min(
        totalTopics,
        Math.max(
          0,
          isPassed
            ? totalTopics
            : (module.completed_topics ?? (totalTopics > 1 && lessons.length > 0 ? Math.min(totalTopics - 1, Math.floor((lessons.filter((l: any) => l.passed).length / lessons.length) * totalTopics)) : 0))
        )
      );
  const moduleImage = module.image_url || image(module.cover_key || "star");

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


      {/* Floating stars for completed node */}
      {isPassed ? (
        <div className="absolute -top-6 z-20 flex items-center gap-0.5 text-xs text-amber-400 drop-shadow-md">
          {Array.from({ length: stars }, (_, i) => (
            <span key={i} className="animate-pulse">⭐</span>
          ))}
        </div>
      ) : null}

      <div className="relative grid place-items-center">
        {/* Solid Opaque Backing Disc to completely block snake path underneath */}
        <div className="absolute h-[86px] w-[86px] sm:h-[94px] sm:w-[94px] rounded-full bg-white dark:bg-[#070d1e] shadow-md pointer-events-none" />

        {/* Segmented Circular Progress Ring around the button (1 to 5 topics) */}
        <SegmentedProgressRing
          total={totalTopics}
          completed={completedTopics}
          radius={46}
          strokeWidth={4.5}
        />

        {/* Circular 3D Pushable Duolingo Button with chosen Brand Cover Image */}
        <button
          type="button"
          onClick={handleNodeClick}
          disabled={isLocked}
          title={isLocked ? "Oldingi modulni tugating" : module.title}
          className={`group relative grid h-20 w-20 sm:h-22 sm:w-22 shrink-0 place-items-center rounded-full border-2 transition-all duration-150 select-none ${
            isPassed
              ? "border-[#001A88] border-b-[8px] bg-gradient-to-b from-[#1429f2] to-[#001A88] text-white shadow-xl shadow-blue-900/30 active:translate-y-1.5 active:border-b-[2px] active:shadow-none hover:brightness-110"
              : isFailed
              ? "border-rose-700 border-b-[8px] bg-rose-500 text-white shadow-xl shadow-rose-500/25 ring-4 ring-rose-500/30 ring-offset-2 active:translate-y-1.5 active:border-b-[2px] active:shadow-none hover:brightness-105"
              : isActive
              ? "border-[#001A88] border-b-[8px] bg-gradient-to-b from-[#1429f2] to-[#002DFF] text-white shadow-xl shadow-blue-600/30 ring-4 ring-[#002DFF]/40 ring-offset-2 active:translate-y-1.5 active:border-b-[2px] active:shadow-none hover:brightness-110"
              : "border-slate-400 border-b-[8px] bg-slate-200 text-slate-500 cursor-not-allowed dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400"
          }`}
        >
          {/* Module circular brand image */}
          <div className="relative h-full w-full p-1 flex items-center justify-center">
            <img
              src={moduleImage}
              alt={module.title || "Modul"}
              className="h-full w-full rounded-full object-cover shadow-inner transition"
            />
            {/* Status badge overlays */}
            {isLocked ? (
              <div className="absolute inset-0 grid place-items-center">
                <span className="grid h-8 w-8 place-items-center rounded-full bg-slate-900 border-2 border-slate-700 text-xs text-white shadow-md">
                  🔒
                </span>
              </div>
            ) : isPassed ? (
              <div className="absolute -bottom-1 -right-1 grid h-6 w-6 place-items-center rounded-full border-2 border-white bg-amber-400 text-[11px] text-amber-950 shadow-md dark:border-navy-900">
                👑
              </div>
            ) : isFailed ? (
              <div className="absolute -bottom-1 -right-1 grid h-6 w-6 place-items-center rounded-full border-2 border-white bg-rose-500 text-[11px] text-white shadow-md dark:border-navy-900">
                ⚠️
              </div>
            ) : null}
          </div>
        </button>
      </div>

      {/* Centered Modal Pop-up Dialog via createPortal */}
      {showPopover && !isLocked && typeof document !== "undefined" ? (
        createPortal(
          <div
            className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm animate-fade-in"
            onClick={() => setShowPopover(false)}
          >
            <div
              className="relative w-full max-w-sm rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-[#0f172a] animate-scale-up"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between border-b border-slate-100 pb-3 dark:border-slate-800">
                <div className="flex items-center gap-2.5">
                  <img src={moduleImage} alt="" className="h-8 w-8 rounded-full object-cover border-2 border-[#002DFF]" />
                  <span className="text-xs font-black uppercase tracking-wider text-[#002DFF] dark:text-[#38bdf8]">
                    Modul #{order + 1}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setShowPopover(false)}
                  className="grid h-8 w-8 place-items-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-white transition"
                >
                  ✕
                </button>
              </div>

              <div className="mt-4 flex flex-col items-center text-center">
                <div className="h-20 w-20 rounded-full p-1 border-4 border-[#002DFF]/20 bg-gradient-to-b from-[#1429f2] to-[#002DFF] shadow-lg mb-3 flex items-center justify-center">
                  <img src={moduleImage} alt="" className="h-full w-full rounded-full object-cover" />
                </div>
                <h3 className="text-lg font-black text-navy-900 dark:text-white">
                  {module.title}
                </h3>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 leading-relaxed max-w-xs">
                  {module.description || "Ushbu modul orqali bilimlaringizni sinang va mustahkamlang."}
                </p>
              </div>

              {/* Topics Breakdown List (1 to 5 topics) */}
              <div className="mt-4 space-y-2 text-left w-full">
                <div className="flex items-center justify-between text-xs font-black uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  <span>Modul mavzulari ({completedTopics}/{totalTopics})</span>
                  <span className="text-[10px] text-[#002DFF] dark:text-[#38bdf8] font-black">
                    {Math.round((completedTopics / totalTopics) * 100)}%
                  </span>
                </div>
                <div className="space-y-1.5">
                  {Array.from({ length: totalTopics }, (_, tIdx) => {
                    const lesson = lessons[tIdx];
                    const topicTitle = lesson?.title || topicKeys[tIdx] || `Mavzu ${tIdx + 1}`;
                    const isTopPassed = isPassed || tIdx < completedTopics;
                    const isTopActive = !isLocked && !isPassed && tIdx === completedTopics;

                    return (
                      <div
                        key={tIdx}
                        className={`flex items-center justify-between rounded-xl border p-2 text-xs font-bold transition ${
                          isTopPassed
                            ? "border-[#1429F2]/30 bg-blue-50/70 text-[#0C188B] dark:border-[#00F0FF]/30 dark:bg-[#00F0FF]/10 dark:text-[#00F0FF]"
                            : isTopActive
                            ? "border-[#002DFF] bg-blue-50 text-[#002DFF] dark:border-blue-700 dark:bg-blue-950/30 dark:text-blue-300 shadow-xs"
                            : "border-slate-200 bg-slate-50 text-slate-400 dark:border-slate-800 dark:bg-slate-800/40"
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span
                            className={`grid h-5 w-5 shrink-0 place-items-center rounded-full text-[10px] font-black ${
                              isTopPassed
                                ? "bg-[#1429F2] text-white dark:bg-[#00F0FF] dark:text-[#010954]"
                                : isTopActive
                                ? "bg-[#002DFF] text-white"
                                : "bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300"
                            }`}
                          >
                            {tIdx + 1}
                          </span>
                          <span className="truncate">{topicTitle}</span>
                        </div>
                        <span className="shrink-0 text-[11px] font-black">
                          {isTopPassed ? "✅ Bajarildi" : isTopActive ? "⚡ Joriy" : "🔒"}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="mt-4 space-y-2">
                <div className="flex items-center justify-between rounded-xl bg-slate-50 p-3 text-xs font-bold text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                  <span className="flex items-center gap-1.5">
                    <span>📝</span>
                    <span>Jami savollar: {lessons.length} ta</span>
                  </span>
                  {isPassed ? (
                    <span className="text-[#002DFF] dark:text-[#00F0FF] font-black">✓ {score}% (O'tilgan)</span>
                  ) : isFailed ? (
                    <span className="text-rose-600 font-black">✗ {score}% (O'tilmadi)</span>
                  ) : (
                    <span>{module.passing_score || 70}% o'tish</span>
                  )}
                </div>

                {Number(module.reward_coins || 0) > 0 ? (
                  <div className="flex items-center justify-between rounded-xl bg-amber-50 px-3 py-2 text-xs font-black text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800/40">
                    <span className="flex items-center gap-1.5">
                      <span>💎</span>
                      <span>Mukofot:</span>
                    </span>
                    <span className="text-amber-600 font-black">+{module.reward_coins} D'Point</span>
                  </div>
                ) : null}
              </div>

              <button
                type="button"
                onClick={() => {
                  setShowPopover(false);
                  onStart();
                }}
                className={`mt-5 w-full rounded-2xl border-2 border-b-4 py-3.5 text-center text-sm font-black uppercase tracking-wider text-white shadow-md transition-all active:translate-y-1 active:border-b-2 ${
                  isPassed
                    ? "border-[#001A88] bg-[#002DFF] hover:bg-[#1429f2]"
                    : isFailed
                    ? "border-rose-700 bg-rose-600 hover:bg-rose-700"
                    : "border-[#001A88] bg-[#002DFF] hover:bg-[#1429f2]"
                }`}
              >
                {isPassed
                  ? "Qayta takrorlash 🔄"
                  : isFailed
                  ? "Qayta topshirish 🔄"
                  : completedTopics > 0
                  ? `${completedTopics + 1}-mavzuni boshlash ➔`
                  : "Darsni boshlash →"}
              </button>
            </div>
          </div>,
          document.body
        )
      ) : null}
    </div>
  );
}

function speakWord(word: string, lang = "en-US") {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(word);
  utterance.lang = lang;
  utterance.rate = 0.9;
  window.speechSynthesis.speak(utterance);
}

function TargetWordBanner({
  word,
  phonetic,
  targetLevel,
  definition,
  meaning,
  hint,
  exampleSentence,
}: {
  word?: string;
  phonetic?: string;
  targetLevel?: string;
  definition?: string;
  meaning?: string;
  hint?: string;
  exampleSentence?: string;
}) {
  if (!word) return null;
  const rawWord = word || "";
  const posMatch = rawWord.match(/\(([a-zA-Z\s\.,-]+)\)/);
  const posRaw = posMatch ? posMatch[1].trim().toLowerCase() : "";
  const posLabel =
    posRaw === "v" ? "Fe'l" :
    posRaw === "n" ? "Ot" :
    posRaw === "adj" ? "Sifat" :
    posRaw === "adv" ? "Ravish" :
    posRaw === "n phr" ? "Ot birikmasi" :
    posRaw === "v phr" ? "Fe'l birikmasi" :
    posMatch ? posMatch[1].trim() : "";
  const cleanWord = rawWord.replace(/\s*\([a-zA-Z\s\.,-]+\)\s*/g, " ").trim() || rawWord;

  return (
    <div className="rounded-2xl border-2 border-indigo-200 bg-gradient-to-br from-indigo-50/90 to-blue-50/80 p-4 shadow-sm dark:border-indigo-900/60 dark:bg-gradient-to-br dark:from-indigo-950/40 dark:to-blue-950/30">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <span className="text-2xl sm:text-3xl font-black text-[#002DFF] dark:text-[#38bdf8] tracking-tight">
            {cleanWord}
          </span>
          {posLabel ? (
            <span className="rounded-lg border border-blue-300 bg-blue-100 px-2 py-0.5 text-xs font-black text-blue-800 dark:border-blue-700 dark:bg-blue-900/60 dark:text-blue-200">
              {posLabel}
            </span>
          ) : null}
          {phonetic ? (
            <span className="text-sm font-mono font-semibold text-slate-500 dark:text-slate-400">
              {phonetic}
            </span>
          ) : null}
          <button
            type="button"
            onClick={() => speakWord(cleanWord)}
            className="grid h-9 w-9 place-items-center rounded-xl border border-indigo-200 bg-white text-indigo-600 shadow-sm transition hover:bg-indigo-50 active:scale-95 dark:border-indigo-800 dark:bg-navy-800 dark:text-indigo-400"
            title="Ovozini eshitish"
          >
            🔊
          </button>
        </div>
        {targetLevel ? (
          <span className="rounded-lg border border-indigo-300 bg-indigo-100 px-2 py-0.5 text-xs font-black text-indigo-800 dark:border-indigo-700 dark:bg-indigo-900/60 dark:text-indigo-200">
            {targetLevel}
          </span>
        ) : null}
      </div>

      {(meaning || definition || hint) ? (
        <p className="mt-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
          💡 <span className="font-bold">Ma'nosi: </span>
          {meaning || definition || hint}
        </p>
      ) : null}

      {exampleSentence ? (
        <div className="mt-2 rounded-xl bg-white/70 p-2.5 text-xs font-semibold text-slate-800 dark:bg-navy-900/60 dark:text-slate-200 border border-indigo-100 dark:border-indigo-900">
          <div className="flex items-center justify-between gap-2">
            <div>
              <span className="font-black text-indigo-600 dark:text-indigo-400">Misol: </span>
              <span>{exampleSentence}</span>
            </div>
            <button
              type="button"
              onClick={() => speakWord(exampleSentence)}
              className="shrink-0 text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400"
              title="Misolni eshitish"
            >
              🔊
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function cleanAnswer(s: string): string {
  if (!s) return "";
  let res = String(s).trim().toLowerCase();
  // Strip option prefixes like "1. ", "a) ", "b. ", "1) ", "A: "
  res = res.replace(/^[a-d0-9][\.\)\-\:\s]+\s*/i, "");
  // Strip POS tag parentheticals like " (v)", " (n)", " (adj)", " (n phr)", etc.
  res = res.replace(/\s*\([a-zA-Z\s\.,-]+\)\s*/g, " ");
  // Normalize smart quotes and apostrophes
  res = res.replace(/[\u2018\u2019\u201B\u0060\u00B4]/g, "'");
  res = res.replace(/[\u201C\u201D]/g, '"');
  // Strip surrounding punctuation like trailing periods, exclamation marks, commas, quotes
  res = res.replace(/^["'\s]+|["'\s\.\,\!\?]+$/g, "");
  // Collapse whitespace
  res = res.replace(/\s+/g, " ");
  return res.trim();
}

export function getCurrentLang(): "uz" | "ru" | "en" {
  if (typeof window === "undefined") return "uz";
  try {
    const stored = (localStorage.getItem("diamond_locale") || localStorage.getItem("lang") || "uz").toLowerCase();
    if (stored.startsWith("ru")) return "ru";
    if (stored.startsWith("en")) return "en";
  } catch {
    // ignore
  }
  return "uz";
}

export function getWordPracticeCondition(q: any, lang: "uz" | "ru" | "en"): string {
  if (!q) return "";
  if (lang === "ru" && q.condition_ru) return String(q.condition_ru);
  if (lang === "en" && q.condition_en) return String(q.condition_en);
  if (q.condition_uz) return String(q.condition_uz);
  if (q.condition) return String(q.condition);

  const mode = q.practice_mode || q.test_type;
  if (mode === "spelling") {
    return lang === "ru"
      ? "Введите правильное написание слова:"
      : lang === "en"
      ? "Type the correct spelling of the word:"
      : "So'zning to'g'ri yozilishini kiriting:";
  }
  if (mode === "translation") {
    return lang === "ru"
      ? "Введите перевод данного слова:"
      : lang === "en"
      ? "Type the translation of the word:"
      : "Berilgan so'zning tarjimasini kiriting:";
  }
  if (mode === "write_sentence") {
    return lang === "ru"
      ? "Напишите полное предложение на английском с этим словом:"
      : lang === "en"
      ? "Write a complete English sentence using this word:"
      : "Ushbu so'z qatnashgan to'liq inglizcha gap yozing:";
  }
  if (mode === "speak_sentence") {
    return lang === "ru"
      ? "Произнесите вслух предложение на английском с этим словом:"
      : lang === "en"
      ? "Speak an English sentence aloud using this word:"
      : "Ushbu so'z qatnashgan inglizcha gapni ovoz chiqarib ayting:";
  }
  return lang === "ru"
    ? "Выполните задание со словом:"
    : lang === "en"
    ? "Complete the task with this word:"
    : "So'z bilan bog'liq topshiriqni bajaring:";
}

export function extractCorrectCandidates(q: any): string[] {
  if (!q) return [];
  const rawList: string[] = [];

  const add = (val: any) => {
    if (val === null || val === undefined) return;
    if (Array.isArray(val)) {
      val.forEach(add);
      return;
    }
    const str = String(val).trim();
    if (!str) return;
    rawList.push(str);
    const cleaned = cleanAnswer(str);
    if (cleaned) rawList.push(cleaned);

    if (str.includes(";") || str.includes("\n")) {
      str.split(/[;\n]+/).forEach(add);
    }
  };

  add(q.correct_answer);
  add(q.acceptable_answers);
  add(q.accepted_answers);
  add(q.clean_word);
  add(q.word);

  if (Array.isArray(q.translations)) {
    q.translations.forEach(add);
  } else if (typeof q.translations === "string") {
    q.translations.split(/[,;\n]+/).forEach(add);
  }

  // If correct_answer matches an option, also add that option and its clean version
  if (Array.isArray(q.options) && q.correct_answer) {
    const normCorrect = cleanAnswer(q.correct_answer);
    q.options.forEach((opt: string, idx: number) => {
      const normOpt = cleanAnswer(opt);
      if (
        normOpt === normCorrect ||
        cleanAnswer(String(idx + 1)) === normCorrect ||
        opt.trim().toLowerCase() === String(q.correct_answer).trim().toLowerCase()
      ) {
        add(opt);
        add(String(idx + 1));
      }
    });
  }

  // If question contains '___' and correct_answer is a full sentence
  const promptText = String(q.passage_template || q.passage || q.question || "");
  if (promptText.includes("___") && q.correct_answer) {
    const rawCorr = String(q.correct_answer).trim();
    const parts = promptText.split("___");
    if (parts.length === 2) {
      const prefix = cleanAnswer(parts[0]);
      const suffix = cleanAnswer(parts[1]);
      const normCorr = cleanAnswer(rawCorr);
      if (prefix && normCorr.startsWith(prefix)) {
        let inside = normCorr.slice(prefix.length).trim();
        if (suffix && inside.endsWith(suffix)) {
          inside = inside.slice(0, inside.length - suffix.length).trim();
        }
        if (inside) add(inside);
      }
      if (rawCorr) {
        const reconstructed = `${parts[0]}${rawCorr}${parts[1]}`;
        add(reconstructed);
      }
    }
  }

  return Array.from(new Set(rawList.map((s) => cleanAnswer(s)).filter(Boolean)));
}

export function isAnswerCorrect(userAns: string, q: any): boolean {
  if (!userAns || !q) return false;
  const normUser = cleanAnswer(userAns);
  if (!normUser) return false;

  const candidates = extractCorrectCandidates(q);
  if (candidates.includes(normUser)) return true;

  // Also check if user entered an option index like "1" or "2"
  if (Array.isArray(q.options)) {
    for (let i = 0; i < q.options.length; i++) {
      const opt = q.options[i];
      const normOpt = cleanAnswer(opt);
      if (normUser === normOpt || normUser === String(i + 1)) {
        if (candidates.includes(normOpt) || candidates.includes(String(i + 1))) {
          return true;
        }
      }
    }
  }

  // Check if candidate matches after stripping all non-alphanumeric punctuation
  const stripPunct = (s: string) => s.replace(/[^a-z0-9\s]/gi, "").replace(/\s+/g, " ").trim();
  const strippedUser = stripPunct(normUser);
  if (strippedUser) {
    for (const cand of candidates) {
      const strippedCand = stripPunct(cand);
      if (strippedUser === strippedCand) return true;
    }
  }

  return false;
}

function InstantVoiceRecorder({
  apiFetch,
  onRecorded,
  disabled,
}: {
  apiFetch: ApiFetch;
  onRecorded: (audioUrl: string) => Promise<void> | void;
  disabled?: boolean;
}) {
  const [recording, setRecording] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [err, setErr] = useState("");
  const [seconds, setSeconds] = useState(0);

  const mediaRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef<number>(0);
  const timerRef = useRef<any>(null);
  const isHoldingRef = useRef<boolean>(false);
  const tapModeRef = useRef<boolean>(false);

  const cleanup = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  };

  useEffect(() => {
    return () => cleanup();
  }, []);

  const start = async () => {
    if (disabled || uploading || recording) return;
    setErr("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mr = new MediaRecorder(stream);
      mediaRef.current = mr;
      chunksRef.current = [];
      startTimeRef.current = Date.now();

      mr.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mr.onstop = async () => {
        cleanup();
        const duration = Date.now() - startTimeRef.current;
        if (duration < 400) {
          setErr("Ovoz juda qisqa bo'ldi. Bosib turib gapiring.");
          setRecording(false);
          setUploading(false);
          tapModeRef.current = false;
          return;
        }

        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setUploading(true);
        try {
          const form = new FormData();
          form.append("file", blob, "voice_answer.webm");
          const res = await apiFetch("/student/ai-tests/upload-audio", {
            method: "POST",
            body: form,
          });
          if (res?.url) {
            await onRecorded(res.url);
          } else {
            setErr("Ovoz yuklanmadi. Qayta urinib ko'ring.");
          }
        } catch (e: any) {
          setErr(e?.message || "Ovozni yuklashda xatolik yuz berdi");
        } finally {
          setUploading(false);
          setRecording(false);
          tapModeRef.current = false;
        }
      };

      mr.start();
      setRecording(true);
      setSeconds(0);
      timerRef.current = setInterval(() => {
        setSeconds((prev) => prev + 1);
      }, 1000);
    } catch {
      cleanup();
      setErr("Mikrofonga ruxsat berilmadi yoki mikrofon topilmadi.");
    }
  };

  const stop = () => {
    if (mediaRef.current && mediaRef.current.state === "recording") {
      mediaRef.current.stop();
    }
  };

  const handlePointerDown = () => {
    if (disabled || uploading) return;
    if (recording && tapModeRef.current) {
      tapModeRef.current = false;
      stop();
      return;
    }
    if (!recording) {
      isHoldingRef.current = true;
      tapModeRef.current = false;
      void start();
    }
  };

  const handlePointerUp = () => {
    if (!recording || !isHoldingRef.current) return;
    isHoldingRef.current = false;
    const elapsed = Date.now() - startTimeRef.current;
    if (elapsed < 400) {
      tapModeRef.current = true;
    } else {
      stop();
    }
  };

  const handlePointerCancel = () => {
    if (recording && isHoldingRef.current) {
      isHoldingRef.current = false;
      stop();
    }
  };

  const formatTime = (s: number) => {
    const mins = Math.floor(s / 60);
    const secs = s % 60;
    return `${mins < 10 ? "0" : ""}${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  return (
    <div className="flex flex-col items-center justify-center py-4 space-y-3 select-none">
      <div className="relative flex items-center justify-center">
        {recording ? (
          <>
            <div className="absolute h-28 w-28 animate-ping rounded-full bg-rose-500/20" />
            <div className="absolute h-24 w-24 animate-pulse rounded-full bg-rose-500/30" />
          </>
        ) : null}

        <button
          type="button"
          disabled={disabled || uploading}
          onPointerDown={handlePointerDown}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerCancel}
          className={`relative grid h-20 w-20 place-items-center rounded-full border-4 text-3xl shadow-xl transition-all duration-200 active:scale-95 touch-none cursor-pointer ${
            uploading
              ? "border-amber-400 bg-amber-50 text-amber-600 animate-spin"
              : recording
              ? "border-rose-600 bg-rose-500 text-white shadow-rose-500/40"
              : "border-[#001A88] bg-[#002DFF] text-white shadow-blue-600/30 hover:bg-[#1429f2]"
          }`}
        >
          {uploading ? "⏳" : recording ? "⏹" : "🎙️"}
        </button>
      </div>

      <div className="text-center">
        <p className="text-sm font-black text-slate-800 dark:text-white">
          {uploading ? (
            <span className="text-amber-600 dark:text-amber-400 animate-pulse">
              AI javobingizni tekshirmoqda...
            </span>
          ) : recording ? (
            <span className="text-rose-600 dark:text-rose-400 flex items-center justify-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-rose-600 animate-ping inline-block" />
              Yozilmoqda: {formatTime(seconds)} — qo'yib yuborsangiz tekshiriladi
            </span>
          ) : (
            <span className="text-slate-600 dark:text-slate-300">
              Mikrofonni bosib turib gapiring (qo'yib yuborganingizda tekshiriladi)
            </span>
          )}
        </p>
        <p className="text-xs font-semibold text-slate-400 mt-0.5">
          {recording
            ? "Gapirib bo'lgach qo'yib yuboring (yoki tugatish uchun yana bir marta bosing)"
            : "Yoki bir marta bosib gapiring va to'xtatish uchun yana bosing"}
        </p>
      </div>

      {err ? (
        <p className="rounded-xl bg-rose-50 border border-rose-200 px-3 py-1.5 text-xs font-bold text-rose-600 dark:bg-rose-950/40 dark:border-rose-900 dark:text-rose-300">
          ⚠️ {err}
        </p>
      ) : null}
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
  const [audioPlaying, setAudioPlaying] = useState(false);
  const [voiceMode, setVoiceMode] = useState(false);
  const [reviewItems, setReviewItems] = useState<TestReviewItem[]>([]);

  // For Word Order interactive exercise
  const [sentenceWords, setSentenceWords] = useState<string[]>([]);
  const [bankWords, setBankWords] = useState<{ id: number; text: string; used: boolean }[]>([]);

  // For Matching interactive exercise
  const [matchedPairs, setMatchedPairs] = useState<Record<string, string>>({});
  const [matchingPairs, setMatchingPairs] = useState<{ left: string; right: string }[]>([]);
  const [matchingLefts, setMatchingLefts] = useState<string[]>([]);
  const [matchingRights, setMatchingRights] = useState<string[]>([]);

  // For Passage Cloze interactive exercise (materials library style)
  const [clozeBlanks, setClozeBlanks] = useState<string[]>([]);
  const [usedWordBank, setUsedWordBank] = useState<Set<number>>(() => new Set());
  const [wordBankAssignments, setWordBankAssignments] = useState<Record<number, number>>({});
  const [wrongBlankPositions, setWrongBlankPositions] = useState<number[]>([]);

  // For Reading Set and Listening Set sub-questions
  const [subAnswers, setSubAnswers] = useState<string[]>([]);

  // Hidden Audio Element ref
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Lock body scroll & hide any sticky topbars / mobile bottom bars
  useEffect(() => {
    document.body.classList.add("learning-test-mode");
    const origOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.classList.remove("learning-test-mode");
      document.body.style.overflow = origOverflow;
    };
  }, []);

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
    setMatchedPairs({});
    setMatchingPairs([]);
    setMatchingLefts([]);
    setMatchingRights([]);
    setClozeBlanks([]);
    setSubAnswers([]);
    setUsedWordBank(new Set());
    setWordBankAssignments({});
    setWrongBlankPositions([]);

    try {
      const data = await apiFetch(`/student/learning-lessons/${lesson.id}`);
      const q = data?.question_payload || data || null;
      setQuestion(q);
      const isVoice =
        q?.input === "audio" ||
        q?.test_type === "speak_sentence" ||
        q?.test_type === "read_aloud" ||
        q?.test_type === "speaking_repeat" ||
        q?.test_type === "speaking_response" ||
        q?.kind === "speak_sentence" ||
        q?.kind === "read_aloud" ||
        q?.kind === "speaking_repeat" ||
        q?.kind === "speaking_response";
      setVoiceMode(Boolean(isVoice));

      // Initialize matching if matching test or pairs provided
      if (q && (q.test_type === "matching" || (Array.isArray(q.pairs) && q.pairs.length > 0))) {
        let pairs: { left: string; right: string }[] = [];
        if (Array.isArray(q.pairs) && q.pairs.length > 0) {
          pairs = q.pairs.filter((p: any) => p && typeof p === "object" && p.left && p.right);
        } else if (Array.isArray(q.options)) {
          for (const opt of q.options) {
            if (typeof opt === "string" && opt.includes("=")) {
              const [l, r] = opt.split("=").map((s: string) => s.trim());
              if (l && r) pairs.push({ left: l, right: r });
            } else if (typeof opt === "string" && opt.includes(" - ")) {
              const [l, r] = opt.split(" - ").map((s: string) => s.trim());
              if (l && r) pairs.push({ left: l, right: r });
            }
          }
        }
        setMatchingPairs(pairs);
        const lefts = q.left_items && Array.isArray(q.left_items) && q.left_items.length
          ? q.left_items
          : pairs.map((p) => p.left);
        const rights = q.right_items && Array.isArray(q.right_items) && q.right_items.length
          ? q.right_items
          : [...pairs.map((p) => p.right)].sort(() => Math.random() - 0.5);
        setMatchingLefts(lefts);
        setMatchingRights(rights);
      }

      // Initialize cloze blanks if passage_cloze or text with ___ (only if NOT multiple choice with options)
      const hasOptions = Array.isArray(q?.options) && q.options.length >= 2;
      const isClozeQ =
        !hasOptions &&
        (q?.test_type === "passage_cloze" ||
          q?.input === "cloze" ||
          Boolean(q?.passage_template) ||
          (typeof q?.passage === "string" && q.passage.includes("___")) ||
          (typeof q?.question === "string" && q.question.includes("___")));
      if (q && isClozeQ) {
        const tmpl = String(q.passage_template || q.passage || q.question || "");
        const total = (tmpl.match(/___/g) || []).length || (Array.isArray(q.blanks) ? q.blanks.length : 0);
        setClozeBlanks(Array.from({ length: total }, () => ""));
      }

      // Initialize word bank if Word Order / Scrambled sentence test OR options are chopped words of answer
      const isWordsOfAnswer =
        Array.isArray(q?.options) &&
        q.options.length > 1 &&
        q.options.map((w: string) => w.trim().toLowerCase()).join(" ") === String(q.correct_answer || "").trim().toLowerCase();

      if (q && (q.test_type === "word_order" || q.test_type === "listening_order" || q.test_type === "scrambled_sentence" || isWordsOfAnswer || (Array.isArray(q.tokens) && q.tokens.length > 0))) {
        let rawWords: string[] = [];
        if (Array.isArray(q.tokens) && q.tokens.length > 0) {
          rawWords = [...q.tokens, ...(Array.isArray(q.distractors) ? q.distractors : [])];
        } else {
          const fullText = String(q.correct_answer || q.prompt || q.question || "");
          rawWords = fullText.split(/\s+/).filter(Boolean);
        }
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

  // Keyboard Navigation: 1-4 for options, Enter for Submit / Next
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input or textarea
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea") return;

      if (e.key >= "1" && e.key <= "4" && question?.options && !result) {
        const idx = parseInt(e.key, 10) - 1;
        if (question.options[idx]) {
          setSelected(question.options[idx]);
          playDuolingoSound("pop");
        }
      }

      if (e.key === "Enter") {
        if (result) {
          next();
        } else if (selected || clozeBlanks.some((x) => x && x.trim())) {
          void submit();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selected, result, question, clozeBlanks]); // eslint-disable-line react-hooks/exhaustive-deps

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

  const hasCurrentOptions = Array.isArray(question?.options) && question.options.length >= 2;
  const isCurrentCloze =
    !hasCurrentOptions &&
    (question?.test_type === "passage_cloze" ||
      question?.input === "cloze" ||
      Boolean(question?.passage_template) ||
      (typeof question?.passage === "string" && question.passage.includes("___")) ||
      (typeof question?.question === "string" && question.question.includes("___")));

  const isReadingSet =
    question?.test_type === "reading_set" ||
    question?.kind === "reading_set" ||
    question?.input === "reading_set" ||
    (Array.isArray(question?.sub_questions) && question.sub_questions.length > 0 && !question?.audio_url);

  const isListeningSet =
    question?.test_type === "listening_set" ||
    question?.kind === "listening_set" ||
    question?.input === "listening_set" ||
    (Array.isArray(question?.sub_questions) && question.sub_questions.length > 0 && Boolean(question?.audio_url));

  const isSetQuestion = isReadingSet || isListeningSet;

  const submit = async (override?: { answer_text?: string; audio_url?: string }) => {
    if (!question || result) return;
    const lesson = lessons[currentIndex];
    const isCloze = isCurrentCloze;
    const isSet = isSetQuestion;
    const subs = Array.isArray(question?.sub_questions) ? question.sub_questions : [];
    const audioUrl = override?.audio_url;

    if (
      !audioUrl &&
      !selected &&
      !override?.answer_text &&
      matchingPairs.length === 0 &&
      (!isCloze || clozeBlanks.every((x) => !x || !x.trim())) &&
      (!isSet || subs.length === 0 || subAnswers.length < subs.length || subAnswers.every((x) => !x || !x.trim()))
    )
      return;

    const currentAnsText = override?.answer_text !== undefined ? override.answer_text : selected;
    const normSelected = currentAnsText.trim().toLowerCase();
    const acceptable = Array.isArray(question?.acceptable_answers)
      ? question.acceptable_answers.map((a: unknown) => String(a).trim().toLowerCase())
      : [];
    const correctAns = String(question?.correct_answer || "").trim().toLowerCase();
    const correctParts = correctAns.includes(";")
      ? correctAns.split(";").map((p) => p.trim().toLowerCase()).filter(Boolean)
      : correctAns.includes("\n")
      ? correctAns.split("\n").map((p) => p.trim().toLowerCase()).filter(Boolean)
      : [];

    let correct = false;
    let selectedAnswer = audioUrl ? "[Ovozli javob]" : currentAnsText;
    let correctAnswerStr = String(question?.correct_answer || "");

    const qTestType = String(question?.test_type || "").toLowerCase();
    const qKind = String(question?.kind || "").toLowerCase();
    const isAiCheck =
      Boolean(audioUrl) ||
      question?.check === "ai" ||
      [
        "write_sentence",
        "guided_writing",
        "reading_open",
        "open",
        "translation",
        "paraphrase",
        "picture_description",
        "dialogue_completion",
        "speak_sentence",
        "read_aloud",
        "speaking_repeat",
        "speaking_response",
        "listening_open",
        "word_practice",
      ].includes(qTestType) ||
      [
        "write_sentence",
        "guided_writing",
        "reading_open",
        "open",
        "translation",
        "paraphrase",
        "picture_description",
        "dialogue_completion",
        "speak_sentence",
        "read_aloud",
        "speaking_repeat",
        "speaking_response",
        "listening_open",
        "word_practice",
      ].includes(qKind) ||
      (!isCloze &&
        !isSet &&
        question?.test_type !== "matching" &&
        matchingPairs.length === 0 &&
        question?.test_type !== "word_order" &&
        question?.test_type !== "scrambled_sentence" &&
        !correctAns &&
        (!Array.isArray(question?.options) || question.options.length === 0));

    let aiFeedbackText = "";
    let aiCorrectedText = "";
    let aiTranscriptText = "";
    let aiPronErrors: any[] = [];
    let aiGrammarErrors: any[] = [];

    if (isAiCheck) {
      setLoading(true);
      try {
        const aiRes = await apiFetch(`/student/learning-lessons/check-ai`, {
          method: "POST",
          body: {
            lesson_id: lesson?.id,
            question_payload: question,
            answer_text: currentAnsText,
            audio_url: audioUrl,
          },
        });
        correct = Boolean(aiRes?.is_correct ?? (aiRes?.verdict === "correct"));
        aiFeedbackText = String(aiRes?.feedback || (correct ? "Ajoyib! Juda to'g'ri!" : "Javobingizda xatolik mavjud."));
        aiCorrectedText = String(aiRes?.corrected || aiRes?.correct_answer || "");
        aiTranscriptText = String(aiRes?.transcript || "");
        aiPronErrors = Array.isArray(aiRes?.pronunciation_errors) ? aiRes.pronunciation_errors : [];
        aiGrammarErrors = Array.isArray(aiRes?.grammar_errors) ? aiRes.grammar_errors : [];
        if (aiCorrectedText) {
          correctAnswerStr = aiCorrectedText;
        }
        if (aiTranscriptText) {
          selectedAnswer = `[Ovozli]: ${aiTranscriptText}`;
        }
      } catch (err) {
        correct = false;
        aiFeedbackText = errorText(err, "AI tekshirish xizmati javob bermadi. Qayta urinib ko'ring.");
      } finally {
        setLoading(false);
      }
    } else if (isSet) {
      let wrongSubs = 0;
      const subLabels: string[] = [];
      const expLabels: string[] = [];

      for (let i = 0; i < subs.length; i++) {
        const s = subs[i];
        const given = (subAnswers[i] || "").trim().toLowerCase();
        const expectedAnswers = [
          String(s.answer || s.correct_answer || s.correct || "").trim().toLowerCase(),
          ...(Array.isArray(s.accepted_answers) ? s.accepted_answers.map((x: any) => String(x).trim().toLowerCase()) : []),
        ].filter(Boolean);

        const ok = expectedAnswers.length > 0
          ? expectedAnswers.some((exp) => exp === given || given.includes(exp) || exp.includes(given))
          : Boolean(given);
        if (!ok) wrongSubs++;

        subLabels.push(`${i + 1}. ${subAnswers[i] || "—"}`);
        expLabels.push(`${i + 1}. ${s.answer || s.correct_answer || (expectedAnswers[0] || "")}`);
      }

      correct = wrongSubs === 0 && subs.length > 0;
      selectedAnswer = subLabels.join(" | ");
      correctAnswerStr = expLabels.join(" | ");
    } else if (isCloze) {
      const blanks = Array.isArray(question.blanks) ? question.blanks : [];
      const wrongPositions: number[] = [];
      const expectedAnswersList: string[] = [];

      for (let i = 0; i < clozeBlanks.length; i++) {
        const b = blanks[i];
        const given = (clozeBlanks[i] || "").trim().toLowerCase();
        let isBlankCorrect = false;
        let expectedLabel = "";

        if (b && typeof b === "object") {
          const mainAns = String(b.answer || "").trim();
          expectedLabel = mainAns;
          const expectedSet = new Set([
            mainAns.toLowerCase(),
            ...(Array.isArray(b.accepted_answers) ? b.accepted_answers.map((x: any) => String(x).trim().toLowerCase()) : []),
          ]);
          expectedSet.delete("");
          if (expectedSet.has(given)) {
            isBlankCorrect = true;
          }
        } else if (typeof b === "string") {
          expectedLabel = b.trim();
          if (given === b.trim().toLowerCase()) {
            isBlankCorrect = true;
          }
        } else if (Array.isArray(question.answers) && question.answers[i]) {
          expectedLabel = String(question.answers[i]).trim();
          if (given === expectedLabel.toLowerCase()) {
            isBlankCorrect = true;
          }
        } else if (correctAns) {
          const parts = correctAns.split(/[,;\n]+/).map((s) => s.trim());
          if (parts[i]) {
            expectedLabel = parts[i];
            if (given === parts[i].toLowerCase()) {
              isBlankCorrect = true;
            }
          }
        }

        if (expectedLabel) {
          expectedAnswersList.push(`${i + 1}. ${expectedLabel}`);
        }
        if (!isBlankCorrect) {
          wrongPositions.push(i + 1);
        }
      }

      setWrongBlankPositions(wrongPositions);
      correct = wrongPositions.length === 0 && clozeBlanks.length > 0;
      selectedAnswer = clozeBlanks.map((ans, idx) => `${idx + 1}. ${ans || "___"}`).join(", ");
      if (expectedAnswersList.length > 0) {
        correctAnswerStr = expectedAnswersList.join(" | ");
      }
    } else if (question.test_type === "matching" || matchingPairs.length > 0) {
      correct =
        matchingPairs.length > 0 &&
        matchingPairs.every(
          (p) => (matchedPairs[p.left] || "").trim().toLowerCase() === p.right.trim().toLowerCase()
        );
      selectedAnswer = Object.entries(matchedPairs).map(([l, r]) => `${l} = ${r}`).join("; ");
      correctAnswerStr = matchingPairs.map((p) => `${p.left} = ${p.right}`).join("; ");
    } else {
      correct = isAnswerCorrect(currentAnsText, question);
    }

    const newScore = score + (correct ? 1 : 0);
    const newTotal = total + 1;
    setScore(newScore);
    setTotal(newTotal);

    setReviewItems((prev) => [
      ...prev,
      {
        prompt: String(question?.instruction || question?.question || question?.prompt || lesson?.title || `Savol ${currentIndex + 1}`),
        selected_answer: selectedAnswer,
        correct_answer: correctAnswerStr || question?.correct_answer || "",
        options: Array.isArray(question?.options) ? question.options : [],
        is_correct: correct,
        explanation: String(question?.explanation || ""),
        question_type: String(question?.test_type || "multiple_choice"),
      },
    ]);

    if (correct) {
      playDuolingoSound("correct");
    } else {
      playDuolingoSound("wrong");
    }

    setLoading(true);
    try {
      const lessonPassScore = correct ? 100 : 0;
      const submitResult = await apiFetch(`/student/learning-lessons/${lesson.id}/submit`, {
        method: "POST",
        body: { score: lessonPassScore, answers: [{ question: question?.question || question?.instruction, selected: selectedAnswer, correct }] },
      });
      setResult({
        correct,
        selected: selectedAnswer,
        correct_answer: correctAnswerStr,
        explanation: question?.explanation || "",
        ai_feedback: aiFeedbackText,
        ai_corrected: aiCorrectedText,
        ai_transcript: aiTranscriptText,
        pronunciation_errors: aiPronErrors,
        grammar_errors: aiGrammarErrors,
        ...submitResult,
      });
      if (submitResult?.module_progress?.passed) {
        setModuleResult(submitResult);
      }
    } catch {
      setResult({
        correct,
        selected: selectedAnswer,
        correct_answer: correctAnswerStr,
        explanation: question?.explanation || "",
        ai_feedback: aiFeedbackText,
        ai_corrected: aiCorrectedText,
        ai_transcript: aiTranscriptText,
        pronunciation_errors: aiPronErrors,
        grammar_errors: aiGrammarErrors,
      });
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

  if (typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-[999999] flex items-center justify-center bg-black/75 p-3 backdrop-blur-sm sm:p-6 animate-fade-in">
      <div className="relative flex h-full max-h-[96vh] w-full max-w-xl flex-col overflow-hidden rounded-3xl border-2 border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-[#0f172a]">
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
        <div className="flex items-center gap-3 border-b border-slate-100 p-4 dark:border-slate-800">
          <button
            onClick={() => {
              if (result || window.confirm("Haqiqatan ham darsni tark etmoqchimisiz?")) {
                onClose();
              }
            }}
            type="button"
            className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:text-slate-400"
          >
            ✕
          </button>

          {/* Duolingo Rounded Glossy Progress Bar */}
          <div className="relative h-4 min-w-0 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-[#002DFF] to-[#38bdf8] transition-all duration-500 relative overflow-hidden shadow-[0_0_10px_rgba(56,189,248,0.4)]"
              style={{ width: `${progressPercent}%` }}
            >
              {/* Glossy shine highlight stripe */}
              <div className="absolute top-1 left-2 right-2 h-1 rounded-full bg-white/40" />
            </div>
          </div>

          <span className="shrink-0 text-xs font-black text-slate-400">
            {currentIndex + 1} / {lessons.length}
          </span>
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
              <div className="h-12 w-12 animate-spin rounded-full border-4 border-[#002DFF] border-t-transparent" />
            </div>
          ) : null}

          {/* Duolingo Completion Screen */}
          {finished ? (
            (() => {
              const finalPercent = total > 0 ? Math.round((score / total) * 100) : 0;
              const passingScore = Number(module.passing_score || 70);
              const passed = Boolean(moduleResult?.module_progress?.passed || finalPercent >= passingScore);

              return (
                <div className="py-6 text-center animate-fade-in">
                  {passed ? (
                    <>
                      <div className="relative mx-auto mb-4 grid h-28 w-28 place-items-center rounded-full border-4 border-[#b87d00] bg-gradient-to-b from-[#ffc800] to-[#e5a800] text-5xl shadow-2xl">
                        👑
                      </div>

                      <h2 className="text-3xl font-black text-navy-900 dark:text-white">
                        Modul muvaffaqiyatli topshirildi!
                      </h2>

                      <p className="mt-1 text-sm font-semibold text-emerald-600 dark:text-emerald-400">
                        Ajoyib natija! Keyingi modul ochildi.
                      </p>
                    </>
                  ) : (
                    <>
                      <div className="relative mx-auto mb-4 grid h-28 w-28 place-items-center rounded-full border-4 border-rose-600 bg-gradient-to-b from-rose-500 to-rose-700 text-5xl shadow-2xl text-white">
                        ❌
                      </div>

                      <h2 className="text-3xl font-black text-rose-600 dark:text-rose-400">
                        Moduldan o'ta olmadingiz!
                      </h2>

                      <p className="mt-1 text-sm font-semibold text-slate-500 dark:text-navy-300">
                        Keyingi modul ochilishi uchun kamida {passingScore}% to'plashingiz shart.
                      </p>
                    </>
                  )}

                  {/* Clean Result Stats cards */}
                  <div className="mt-6 grid grid-cols-3 gap-3">
                    <div className="rounded-2xl border-2 border-b-4 border-slate-200 bg-slate-50 p-3 dark:border-navy-700 dark:bg-navy-900/60">
                      <span className="text-xs font-black uppercase text-slate-500">Savollar</span>
                      <p className="mt-1 text-2xl font-black text-slate-800 dark:text-slate-200">
                        {total} ta
                      </p>
                    </div>

                    <div className="rounded-2xl border-2 border-b-4 border-emerald-300 bg-emerald-50 p-3 dark:border-emerald-800 dark:bg-emerald-950/40">
                      <span className="text-xs font-black uppercase text-emerald-700 dark:text-emerald-300">To'g'ri</span>
                      <p className="mt-1 text-2xl font-black text-emerald-800 dark:text-emerald-200">
                        {score} ta
                      </p>
                    </div>

                    <div
                      className={`rounded-2xl border-2 border-b-4 p-3 ${
                        passed
                          ? "border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/40"
                          : "border-rose-300 bg-rose-50 dark:border-rose-800 dark:bg-rose-950/40"
                      }`}
                    >
                      <span
                        className={`text-xs font-black uppercase ${
                          passed ? "text-amber-700 dark:text-amber-300" : "text-rose-700 dark:text-rose-300"
                        }`}
                      >
                        Natija
                      </span>
                      <p
                        className={`mt-1 text-2xl font-black ${
                          passed ? "text-amber-800 dark:text-amber-200" : "text-rose-800 dark:text-rose-200"
                        }`}
                      >
                        {finalPercent}%
                      </p>
                    </div>
                  </div>

                  {passed ? (
                    <div className="mt-5 rounded-2xl border-2 border-b-4 border-[#001A88] bg-blue-50 p-4 text-sm font-black text-[#001A88] dark:bg-blue-950/40 dark:text-blue-200 dark:border-blue-800">
                      🎉 Tabriklaymiz! O'tish balli ({passingScore}%) bajarildi va keyingi modul ochildi!
                    </div>
                  ) : (
                    <div className="mt-5 rounded-2xl border-2 border-b-4 border-rose-400 bg-rose-50 p-4 text-sm font-black text-rose-700 dark:bg-rose-950/50 dark:text-rose-300">
                      ⚠️ O'tish balli: {passingScore}%. Sizning ballingiz: {finalPercent}%. Keyingi modul ochilishi uchun modulni qayta topshiring.
                    </div>
                  )}

                  {passed && Number(module.reward_coins || 0) > 0 ? (
                    <div className="mt-3 flex items-center justify-center gap-2 rounded-2xl border border-amber-300 bg-amber-50 px-4 py-2.5 text-xs font-black text-amber-800 dark:border-amber-700 dark:bg-amber-950/50 dark:text-amber-300">
                      <span>🎁 Mukofot:</span>
                      <span>💎 +{module.reward_coins} D'Point</span>
                      <span>va</span>
                      <span>💰 +{module.reward_coins} D'Coin qo'shildi!</span>
                    </div>
                  ) : null}

                  {reviewItems.length > 0 ? (
                    <TestCompletionActions
                      testTitle={String(module.title || "Modul testi")}
                      subject={String(module.subject || "")}
                      review={reviewItems}
                      className="mt-5"
                    />
                  ) : null}

                  {passed ? (
                    <button
                      type="button"
                      onClick={onClose}
                      className="mt-6 w-full rounded-2xl border-2 border-b-4 border-[#001A88] bg-[#002DFF] py-4 text-base font-black uppercase tracking-wider text-white shadow-xl shadow-blue-600/30 active:translate-y-1 active:border-b-2 hover:bg-[#1429f2]"
                    >
                      Davom etish
                    </button>
                  ) : (
                    <div className="mt-6 space-y-3">
                      <button
                        type="button"
                        onClick={() => {
                          setScore(0);
                          setTotal(0);
                          setFinished(false);
                          setReviewItems([]);
                          setCurrentIndex(0);
                          void loadLesson(0);
                        }}
                        className="flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-b-4 border-rose-600 bg-rose-500 py-4 text-base font-black uppercase tracking-wider text-white shadow-xl active:translate-y-1 active:border-b-2 hover:bg-rose-600"
                      >
                        <span>🔄</span>
                        <span>Qayta urinish</span>
                      </button>
                      <button
                        type="button"
                        onClick={onClose}
                        className="w-full rounded-2xl border border-slate-200 bg-white py-3 text-sm font-bold text-slate-600 transition hover:bg-slate-50 dark:border-navy-700 dark:bg-navy-800 dark:text-navy-300"
                      >
                        Chiqish
                      </button>
                    </div>
                  )}
                </div>
              );
            })()
          ) : null}

          {/* Active Question Render */}
          {question && !finished ? (
            <div className="space-y-5 animate-fade-in">
              {/* Category Pill */}
              <div className="flex items-center justify-between">
                <span className="rounded-xl bg-slate-100 px-3 py-1 text-xs font-black uppercase tracking-wider text-slate-600 dark:bg-navy-800 dark:text-navy-300">
                  {isReadingSet
                    ? "📚 Matn va savollar (Reading Set)"
                    : isListeningSet
                    ? "🎧 Audio va savollar (Listening Set)"
                    : isCurrentCloze || question.test_type === "passage_cloze"
                    ? "📝 Matnni to'ldiring"
                    : question.test_type === "speak_sentence" || question.kind === "speak_sentence"
                    ? "🗣️ Ovozli gap tuzish"
                    : question.test_type === "read_aloud" || question.kind === "read_aloud"
                    ? "🗣️ Ovoz chiqarib o'qish"
                    : question.test_type === "word_practice" || question.kind === "word_practice"
                    ? "📚 So'z mashqi (Vocabulary)"
                    : question.test_type === "spelling" || question.kind === "spelling"
                    ? "🔤 To'g'ri yozilish (spelling)"
                    : question.test_type === "translation" || question.kind === "translation"
                    ? "🌐 Tarjima qiling"
                    : question.test_type === "picture_description" || question.kind === "picture_description"
                    ? "🖼️ Rasmni tasvirlang"
                    : question.test_type === "write_sentence" || question.test_type === "guided_writing"
                    ? "✍️ Gap yozish"
                    : question.test_type === "word_order" || question.test_type === "listening_order" || question.test_type === "scrambled_sentence"
                    ? "🧩 Gap tuzing"
                    : question.test_type === "true_false" || question.test_type === "listening_tf"
                    ? "⚖️ To'g'ri yoki Noto'g'ri"
                    : question.test_type === "fill_blank" || question.test_type === "listening_gap" || question.test_type === "gap_fill"
                    ? "✏️ Bo'sh joyni to'ldiring"
                    : question.test_type === "matching"
                    ? "🔄 Moslashtiring"
                    : question.test_type === "paraphrase"
                    ? "🔄 Qayta ifodalash"
                    : question.test_type === "listening_dictation"
                    ? "✍️ Diktant (eshitib yozish)"
                    : question.test_type === "reading_open" || question.test_type === "listening_open"
                    ? "📖 Savolga javob yozing"
                    : question.test_type === "speaking_repeat" || question.test_type === "speaking_response"
                    ? "🗣️ Gapirish mashqi"
                    : question.audio_url
                    ? "🎧 Tinglab javob bering"
                    : "📝 To'g'ri variantni tanlang"}
                </span>
                <span className="text-xs font-bold text-slate-400">
                  {currentIndex + 1} / {lessons.length}
                </span>
              </div>

              {/* Target Word Banner (Duolingo / Materials Library style) */}
              {question.word ? (
                <TargetWordBanner
                  word={question.word}
                  phonetic={question.phonetic || question.pronunciation}
                  targetLevel={question.target_level || question.level}
                  definition={question.definition}
                  meaning={question.meaning}
                  hint={question.hint}
                  exampleSentence={question.example_sentence}
                />
              ) : null}

              {/* Question Image if present */}
              {question.image_url ? (
                <div className="overflow-hidden rounded-2xl border-2 border-slate-200 dark:border-slate-800">
                  <img
                    src={question.image_url.startsWith("/") ? `/api${question.image_url}` : question.image_url}
                    alt="Savol rasmi"
                    className="max-h-64 w-full object-contain bg-slate-50 dark:bg-slate-900"
                  />
                </div>
              ) : null}

              {/* Duolingo Question Prompt Title */}
              <h2 className="text-xl sm:text-2xl font-black leading-snug text-slate-800 dark:text-white">
                {question.instruction ||
                  (question.question && question.question.trim() !== question.passage?.trim()
                    ? question.question
                    : null) ||
                  question.prompt ||
                  "Topshiriqni bajaring:"}
              </h2>

              {/* Question Condition Banner (especially for word_practice and tasks with clear conditions) */}
              {question.test_type === "word_practice" || question.practice_mode || question.condition_uz || question.condition ? (
                <div className="flex items-start gap-3 rounded-2xl border-2 border-amber-300 bg-amber-50/90 p-4 text-amber-950 shadow-sm dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-100">
                  <span className="text-2xl shrink-0 mt-0.5">🎯</span>
                  <div className="space-y-1">
                    <span className="inline-block rounded-md bg-amber-200/80 px-2 py-0.5 text-[11px] font-black uppercase tracking-wider text-amber-900 dark:bg-amber-900/60 dark:text-amber-200">
                      {getCurrentLang() === "ru" ? "Условие задания" : getCurrentLang() === "en" ? "Task Instruction" : "Topshiriq sharti"}
                    </span>
                    <p className="text-sm sm:text-base font-bold leading-snug">
                      {getWordPracticeCondition(question, getCurrentLang())}
                    </p>
                  </div>
                </div>
              ) : null}

              {/* Passage / Context if available (hidden for passage_cloze to avoid duplication) */}
              {!isCurrentCloze && (question.passage || question.context) && (question.question?.trim() !== question.passage?.trim()) ? (
                <div className="rounded-2xl border-2 border-indigo-200 bg-indigo-50/70 p-4 text-sm leading-relaxed text-slate-800 dark:border-indigo-900/60 dark:bg-indigo-950/40 dark:text-indigo-200 max-h-56 overflow-y-auto whitespace-pre-wrap font-medium">
                  <div className="flex items-center gap-1.5 text-xs font-black uppercase text-indigo-700 dark:text-indigo-300 mb-1.5">
                    <span>📖</span>
                    <span>Matn / Passage</span>
                  </div>
                  {String(question.passage || question.context)}
                </div>
              ) : null}

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

              {/* ─── Exercise Types Evaluation ─── */}
              {(() => {
                const isVoiceQuestion =
                  question.input === "audio" ||
                  question.test_type === "speak_sentence" ||
                  question.test_type === "read_aloud" ||
                  question.test_type === "speaking_repeat" ||
                  question.test_type === "speaking_response" ||
                  question.kind === "speak_sentence" ||
                  question.kind === "read_aloud" ||
                  question.kind === "speaking_repeat" ||
                  question.kind === "speaking_response";
                const isVoiceOrText = question.input === "audio_or_text" || isVoiceQuestion;

                // ─── Voice Exercise (Instant Voice Recorder with auto-check on release) ───
                if (isVoiceQuestion || (isVoiceOrText && voiceMode)) {
                  return (
                    <div className="space-y-4 pt-2">
                      <InstantVoiceRecorder
                        apiFetch={apiFetch}
                        disabled={Boolean(result) || loading}
                        onRecorded={async (audioUrl) => {
                          await submit({ audio_url: audioUrl });
                        }}
                      />
                      {isVoiceOrText && (
                        <div className="text-center">
                          <button
                            type="button"
                            disabled={Boolean(result)}
                            onClick={() => setVoiceMode(false)}
                            className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-[#002DFF] dark:text-slate-400 dark:hover:text-[#38bdf8]"
                          >
                            ✍️ Yozma javob berishga o'tish
                          </button>
                        </div>
                      )}
                    </div>
                  );
                }

                // ─── Exercise Type: Reading Set & Listening Set (Materials Library & Homework) ───
                if (isSetQuestion) {
                  const subs = Array.isArray(question.sub_questions) ? question.sub_questions : [];
                  const setSub = (i: number, v: string) => {
                    setSubAnswers((prev) => {
                      const next = [...prev];
                      while (next.length < subs.length) next.push("");
                      next[i] = v;
                      return next;
                    });
                  };
                  const currentAnswers = Array.from({ length: subs.length }, (_, i) => subAnswers[i] || "");

                  return (
                    <div className="space-y-4 pt-1">
                      {isReadingSet && question.passage && (
                        <div className="max-h-64 overflow-y-auto rounded-2xl border-2 border-indigo-200 bg-indigo-50/70 p-4 text-sm leading-relaxed text-slate-800 dark:border-indigo-900/60 dark:bg-indigo-950/40 dark:text-indigo-200 whitespace-pre-wrap font-medium">
                          <div className="flex items-center gap-1.5 text-xs font-black uppercase text-indigo-700 dark:text-indigo-300 mb-1.5">
                            <span>📖</span>
                            <span>Matnni diqqat bilan o'qing:</span>
                          </div>
                          {question.passage}
                        </div>
                      )}
                      <div className="space-y-3">
                        {subs.map((s: any, i: number) => {
                          const opts = Array.isArray(s.options) && s.options.length > 0
                            ? s.options
                            : (s.type === "tf" || s.type === "true_false_ng" ? ["True", "False", "Not Given"] : []);
                          return (
                            <div key={i} className="rounded-2xl border-2 border-slate-200 bg-white p-3.5 shadow-sm dark:border-navy-700 dark:bg-navy-800">
                              <p className="mb-2.5 text-xs font-black text-navy-900 dark:text-white">
                                {i + 1}. {s.prompt || s.question || `Savol ${i + 1}`}
                              </p>
                              {opts.length > 0 ? (
                                <div className="flex flex-wrap gap-2">
                                  {opts.map((opt: string) => {
                                    const isChosen = currentAnswers[i]?.trim().toLowerCase() === opt.trim().toLowerCase();
                                    return (
                                      <button
                                        key={opt}
                                        type="button"
                                        disabled={Boolean(result)}
                                        onClick={() => {
                                          playDuolingoSound("pop");
                                          setSub(i, opt);
                                        }}
                                        className={`rounded-xl border-2 border-b-4 px-3.5 py-2 text-xs font-black transition-all active:translate-y-1 active:border-b-2 ${
                                          isChosen
                                            ? "border-[#1899d6] bg-[#ddf4ff] text-[#1899d6] dark:border-[#1cb0f6] dark:bg-[#18394a]"
                                            : "border-slate-200 bg-white text-navy-900 hover:bg-slate-50 dark:border-navy-600 dark:bg-navy-900 dark:text-white"
                                        }`}
                                      >
                                        {opt}
                                      </button>
                                    );
                                  })}
                                </div>
                              ) : (
                                <input
                                  type="text"
                                  value={currentAnswers[i]}
                                  disabled={Boolean(result)}
                                  onChange={(e) => setSub(i, e.target.value)}
                                  placeholder="Javobingizni yozing..."
                                  className="w-full rounded-xl border border-slate-200 bg-slate-50 p-2.5 text-xs font-bold text-navy-900 focus:border-[#84d8ff] focus:outline-none dark:border-navy-600 dark:bg-navy-900 dark:text-white"
                                />
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                }

                // ─── Exercise Type 0: Passage Cloze (Materials Library / Homework style) ───
                if (isCurrentCloze) {
                  const template = String(question.passage_template || question.passage || question.question || "");
                  const totalBlanks = (template.match(/___/g) || []).length || (Array.isArray(question.blanks) ? question.blanks.length : 0);
                  const setBlank = (i: number, v: string) => {
                    setClozeBlanks((prev) => {
                      const next = [...prev];
                      while (next.length < totalBlanks) next.push("");
                      next[i] = v;
                      return next;
                    });
                  };
                  const filled = Array.from({ length: totalBlanks }, (_, i) => clozeBlanks[i] || "");
                  const lines = template.split("\n");
                  let blankCursor = 0;
                  const wordBank: string[] = Array.isArray(question.word_bank) ? question.word_bank : [];
                  const textForCheck = `${question.instruction || ""} ${question.question || ""} ${question.prompt || ""} ${template}`.toLowerCase();
                  const isTenseOrForm =
                    textForCheck.includes("form") ||
                    textForCheck.includes("tense") ||
                    textForCheck.includes("zamon") ||
                    textForCheck.includes("shakl") ||
                    textForCheck.includes("put the verb") ||
                    textForCheck.includes("in brackets") ||
                    textForCheck.includes("qavs");
                  const hasBrackets = /\(\s*[a-zA-Z'\s-]+\s*\)/.test(template);
                  const blanksList = Array.isArray(question.blanks) ? question.blanks : Array.isArray(question.answers) ? question.answers : [];
                  const ansSet = new Set(blanksList.map((b: any) => String(b?.answer || b || "").trim().toLowerCase()));
                  const bankSet = new Set(wordBank.map((w) => String(w || "").trim().toLowerCase()));
                  const showWordBank =
                    wordBank.length > 0 &&
                    !(isTenseOrForm && hasBrackets) &&
                    !(isTenseOrForm && ansSet.size > 0 && [...ansSet].every((a) => bankSet.has(a)));

                  return (
                    <div className="space-y-4 pt-1">
                      {/* Word bank chips — displayed at the TOP above sentences */}
                      {showWordBank && (
                        <div className="rounded-2xl border-2 border-slate-200 bg-white p-3.5 shadow-sm dark:border-navy-700 dark:bg-navy-800">
                          <p className="text-xs font-black uppercase tracking-wider text-[#002DFF] dark:text-[#38bdf8] mb-2">
                            💡 So'zlar banki — joylash uchun bosing:
                          </p>
                          <div className="flex flex-wrap gap-2 justify-center">
                            {wordBank.map((w, i) => {
                              const marked = usedWordBank.has(i);
                              return (
                                <button
                                  key={`${w}-${i}`}
                                  type="button"
                                  disabled={Boolean(result)}
                                  onClick={() => {
                                    playDuolingoSound("pop");
                                    if (marked) {
                                      const blankIndex = Object.entries(wordBankAssignments).find(([, value]) => value === i)?.[0];
                                      if (blankIndex !== undefined) setBlank(Number(blankIndex), "");
                                      setWordBankAssignments((prev) => {
                                        const next = { ...prev };
                                        if (blankIndex !== undefined) delete next[Number(blankIndex)];
                                        return next;
                                      });
                                      setUsedWordBank((prev) => {
                                        const next = new Set(prev);
                                        next.delete(i);
                                        return next;
                                      });
                                      return;
                                    }
                                    const idx = filled.findIndex((x) => !x.trim());
                                    if (idx < 0) return;
                                    setBlank(idx, w);
                                    setWordBankAssignments((prev) => ({ ...prev, [idx]: i }));
                                    setUsedWordBank((prev) => new Set(prev).add(i));
                                  }}
                                  className={`rounded-2xl border-2 px-3.5 py-2 text-sm font-black transition-all select-none ${
                                    marked
                                      ? "border-slate-200 bg-slate-200/50 text-slate-400 line-through opacity-40 dark:border-navy-800 dark:bg-navy-900"
                                      : "border-slate-200 border-b-4 bg-white text-navy-900 shadow-sm active:translate-y-1 active:border-b-2 hover:bg-cyan-50 hover:border-cyan-400 dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                                  }`}
                                >
                                  {w}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Interactive cloze text container */}
                      <div className="space-y-2.5 rounded-3xl border-2 border-slate-200 bg-slate-50/80 p-4 sm:p-5 text-base leading-loose text-slate-900 dark:border-navy-700 dark:bg-navy-900/50 dark:text-white font-medium">
                        {lines.map((line, li) => {
                          const segs = line.split("___");
                          const rowGaps = segs.length - 1;
                          const startIdx = blankCursor;
                          blankCursor += rowGaps;
                          return (
                            <div key={li} className="leading-loose">
                              {segs.map((seg, si) => {
                                const gi = startIdx + si;
                                const isWrong = result && wrongBlankPositions.includes(gi + 1);
                                const isCorrect = result && !isWrong;

                                return (
                                  <span key={si}>
                                    {seg}
                                    {si < rowGaps && (
                                      <span className="relative inline-block mx-1">
                                        <input
                                          type="text"
                                          value={filled[gi] || ""}
                                          disabled={Boolean(result)}
                                          onChange={(e) => {
                                            setBlank(gi, e.target.value);
                                            const bankIndex = wordBankAssignments[gi];
                                            if (bankIndex !== undefined) {
                                              setWordBankAssignments((prev) => {
                                                const next = { ...prev };
                                                delete next[gi];
                                                return next;
                                              });
                                              setUsedWordBank((prev) => {
                                                const next = new Set(prev);
                                                next.delete(bankIndex);
                                                return next;
                                              });
                                            }
                                          }}
                                          className={`w-28 sm:w-32 rounded-xl border-2 px-2 py-1 text-center text-sm sm:text-base font-black outline-none transition-all ${
                                            result
                                              ? isCorrect
                                                ? "border-[#58cc02] bg-[#d7ffb8] text-[#2e6b00] dark:bg-[#183617] dark:text-[#a0ff6d]"
                                                : "border-[#ff4b4b] bg-[#ffdfe0] text-[#a01818] dark:bg-[#3d1a1b] dark:text-[#ffa0a0]"
                                              : filled[gi]
                                              ? "border-[#84d8ff] border-b-4 bg-[#ddf4ff] text-[#1899d6] dark:border-[#1cb0f6] dark:bg-[#18394a] dark:text-white"
                                              : "border-slate-300 border-b-4 bg-white text-navy-900 focus:border-[#002DFF] dark:border-navy-600 dark:bg-navy-800 dark:text-white"
                                          }`}
                                          placeholder={`(${gi + 1})`}
                                        />
                                        {isWrong && Array.isArray(question.blanks) && question.blanks[gi] ? (
                                          <span className="block text-[11px] font-black text-[#a01818] dark:text-[#ffa0a0] text-center">
                                            {String(question.blanks[gi]?.answer || question.blanks[gi])}
                                          </span>
                                        ) : null}
                                      </span>
                                    )}
                                  </span>
                                );
                              })}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                }

                const isWordsOfAnswer =
                  Array.isArray(question.options) &&
                  question.options.length > 1 &&
                  question.options.map((w: string) => w.trim().toLowerCase()).join(" ") === String(question.correct_answer || "").trim().toLowerCase();

                const hasCorrectChoice =
                  Array.isArray(question.options) &&
                  question.options.some((opt: string) => isAnswerCorrect(opt, question));

                const correctParts = String(question.correct_answer || "").includes(";")
                  ? String(question.correct_answer || "").split(";").map((p) => p.trim().toLowerCase()).filter(Boolean)
                  : [];

                if (question.test_type === "word_order" || question.test_type === "listening_order" || question.test_type === "scrambled_sentence" || isWordsOfAnswer) {
                  return (
                    /* ─── Exercise Type 1: Word Order / Scrambled sentence (Duolingo Signature) ─── */
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
                  );
                } else if (question.test_type === "true_false" || question.test_type === "listening_tf") {
                  /* ─── Exercise Type 2: True / False ─── */
                  return (
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
                  );
                } else if (question.test_type === "matching" || matchingPairs.length > 0) {
                  /* ─── Exercise Type 3: Matching / Pairs ─── */
                  return (
                    <div className="space-y-3 pt-2">
                      <p className="text-xs font-bold text-slate-500 dark:text-slate-400">
                        Har bir chapdagi so'zga mos o'ngdagi tarjima/javobni tanlang:
                      </p>
                      {matchingLefts.map((left, idx) => {
                        const currentVal = matchedPairs[left] || "";
                        const targetPair = matchingPairs.find((p) => p.left.trim().toLowerCase() === left.trim().toLowerCase());
                        const isPairCorrect = result && targetPair && (currentVal.trim().toLowerCase() === targetPair.right.trim().toLowerCase());
                        const isPairWrong = result && targetPair && currentVal && (currentVal.trim().toLowerCase() !== targetPair.right.trim().toLowerCase());

                        return (
                          <div
                            key={idx}
                            className={`flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 rounded-2xl border-2 p-3 transition-all ${
                              result
                                ? isPairCorrect
                                  ? "border-[#58cc02] bg-[#d7ffb8]/30 dark:bg-[#183617]/30"
                                  : isPairWrong
                                  ? "border-[#ff4b4b] bg-[#ffdfe0]/30 dark:bg-[#3d1a1b]/30"
                                  : "border-slate-200 bg-white dark:border-navy-700 dark:bg-navy-800"
                                : "border-slate-200 border-b-4 bg-white dark:border-navy-700 dark:bg-navy-800"
                            }`}
                          >
                            <span className="min-w-[120px] text-sm font-black text-navy-900 dark:text-white flex items-center gap-2">
                              <span className="grid h-6 w-6 place-items-center rounded-lg bg-slate-100 text-xs text-slate-600 dark:bg-navy-900 dark:text-navy-300">
                                {idx + 1}
                              </span>
                              <span>{left}</span>
                            </span>
                            <div className="flex items-center gap-2 flex-1">
                              <span className="hidden sm:inline font-black text-slate-300">→</span>
                              <select
                                value={currentVal}
                                disabled={Boolean(result)}
                                onChange={(e) => {
                                  playDuolingoSound("pop");
                                  const newPairs = { ...matchedPairs, [left]: e.target.value };
                                  setMatchedPairs(newPairs);
                                  setSelected(Object.entries(newPairs).map(([l, r]) => `${l} = ${r}`).join("; "));
                                }}
                                className="flex-1 rounded-xl border border-slate-200 bg-slate-50 p-2.5 text-xs font-black text-navy-900 focus:border-[#84d8ff] focus:outline-none dark:border-navy-600 dark:bg-navy-900 dark:text-white"
                              >
                                <option value="">Tanlang...</option>
                                {matchingRights.map((r, ri) => (
                                  <option key={ri} value={r}>
                                    {r}
                                  </option>
                                ))}
                              </select>
                              {result && isPairCorrect && <span className="text-lg text-emerald-600 font-black">✓</span>}
                              {result && isPairWrong && <span className="text-lg text-rose-600 font-black">✕</span>}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  );
                } else if (
                  question.test_type === "write_sentence" ||
                  question.test_type === "guided_writing" ||
                  question.test_type === "open"
                ) {
                  /* ─── Exercise Type 4: Written Sentences / Guided Writing (Textarea + word count) ─── */
                  const wordCount = selected.trim().split(/\s+/).filter(Boolean).length;
                  const minWords = typeof question.word_count === "number" ? question.word_count : 0;

                  return (
                    <div className="space-y-3 pt-2">
                      <div className="flex flex-wrap gap-2 items-center">
                        {question.direction ? (
                          <span className="rounded-xl border border-cyan-300 bg-cyan-50 px-2.5 py-1 text-xs font-black text-cyan-800 dark:border-cyan-800 dark:bg-cyan-950 dark:text-cyan-300">
                            🌐 {question.direction}
                          </span>
                        ) : null}
                        {question.hint ? (
                          <span className="rounded-xl border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-black text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
                            💡 {question.hint}
                          </span>
                        ) : null}
                        {isVoiceOrText && !voiceMode ? (
                          <button
                            type="button"
                            disabled={Boolean(result)}
                            onClick={() => setVoiceMode(true)}
                            className="inline-flex items-center gap-1.5 rounded-xl border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-black text-[#002DFF] transition hover:bg-blue-100 dark:border-blue-900 dark:bg-blue-950/50 dark:text-blue-300"
                          >
                            🎙️ Ovozli javob berish (mikrofon)
                          </button>
                        ) : null}
                      </div>

                      <textarea
                        value={selected}
                        onChange={(e) => setSelected(e.target.value)}
                        disabled={Boolean(result)}
                        rows={3}
                        placeholder="Javobingizni shu yerga yozing..."
                        autoFocus
                        className="w-full rounded-2xl border-2 border-b-4 border-slate-200 bg-white p-4 text-base font-semibold text-navy-900 focus:border-[#84d8ff] focus:outline-none dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                      />

                      <div className="flex items-center justify-between text-xs font-bold text-slate-400">
                        <span>Javobingizni to'liq yozing va pastdagi "Tekshirish" tugmasini bosing.</span>
                        {minWords > 0 ? (
                          <span className={wordCount >= minWords ? "text-emerald-600 font-black" : "text-amber-600 font-bold"}>
                            {wordCount} / {minWords} so'z {wordCount >= minWords ? "✓" : ""}
                          </span>
                        ) : null}
                      </div>

                      {result && (question.sample_answer || question.reference_answer) ? (
                        <div className="rounded-2xl border border-emerald-300 bg-emerald-50 p-3 text-xs font-semibold text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
                          <p className="font-black mb-1">📝 Namunaviy javob:</p>
                          <p>{String(question.sample_answer || question.reference_answer)}</p>
                        </div>
                      ) : null}
                    </div>
                  );
                } else if (!question.options || !Array.isArray(question.options) || question.options.length < 2 || ((question.test_type === "fill_blank" || question.test_type === "gap_fill") && !hasCorrectChoice)) {
                  /* ─── Exercise Type 5: Fill Blank, Dictation, Open, Translation, Spelling (Single Text Input) ─── */
                  const wordCount = selected.trim().split(/\s+/).filter(Boolean).length;
                  const minWords = typeof question.word_count === "number" ? question.word_count : 0;

                  return (
                    <div className="space-y-3 pt-2">
                      {/* Contextual Badges: Direction / Hint / Example */}
                      <div className="flex flex-wrap gap-2 items-center">
                        {question.direction ? (
                          <span className="rounded-xl border border-cyan-300 bg-cyan-50 px-2.5 py-1 text-xs font-black text-cyan-800 dark:border-cyan-800 dark:bg-cyan-950 dark:text-cyan-300">
                            🌐 {question.direction}
                          </span>
                        ) : null}
                        {question.hint ? (
                          <span className="rounded-xl border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-black text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
                            💡 Yordam: {question.hint}
                          </span>
                        ) : null}
                        {question.example_sentence ? (
                          <span className="rounded-xl border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs font-bold text-indigo-700 dark:border-indigo-800 dark:bg-indigo-950 dark:text-indigo-300">
                            📝 Misol: {question.example_sentence}
                          </span>
                        ) : null}
                        {isVoiceOrText && !voiceMode ? (
                          <button
                            type="button"
                            disabled={Boolean(result)}
                            onClick={() => setVoiceMode(true)}
                            className="inline-flex items-center gap-1.5 rounded-xl border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-black text-[#002DFF] transition hover:bg-blue-100 dark:border-blue-900 dark:bg-blue-950/50 dark:text-blue-300"
                          >
                            🎙️ Ovozli javob berish (mikrofon)
                          </button>
                        ) : null}
                      </div>

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

                      <div className="flex items-center justify-between text-xs font-bold text-slate-400">
                        <span>Javobni yozing va pastdagi "Tekshirish" tugmasini bosing.</span>
                        {minWords > 0 ? (
                          <span className={wordCount >= minWords ? "text-emerald-600 font-black" : "text-amber-600 font-bold"}>
                            {wordCount} / {minWords} so'z {wordCount >= minWords ? "✓" : ""}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  );
                } else {
                  /* ─── Exercise Type 6: Multiple Choice (Duolingo 3D Cards) ─── */
                  return (
                    <div className="grid gap-3 pt-2">
                      {(question.options || []).map((opt: string, i: number) => {
                        const isSelected = selected === opt;
                        const isCorrectChoice = isAnswerCorrect(opt, question);

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
                  );
                }
              })()}
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
                    {result.correct
                      ? (result.ai_feedback || "Ajoyib! Juda to'g'ri!")
                      : "Javobingizda xatolik mavjud:"}
                  </p>
                  {result.ai_transcript ? (
                    <div className="mt-1.5 rounded-xl bg-blue-50/80 px-3 py-2 text-xs font-semibold text-blue-950 dark:bg-blue-950/40 dark:text-blue-200 border border-blue-200 dark:border-blue-900">
                      <span className="font-bold">🎙️ Siz aytdingiz:</span> “{result.ai_transcript}”
                    </div>
                  ) : null}
                  {!result.correct && (result.ai_feedback || result.correct_answer) ? (
                    <div className="mt-1 space-y-1">
                      {result.ai_feedback && result.ai_feedback !== result.correct_answer ? (
                        <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">
                          💬 {result.ai_feedback}
                        </p>
                      ) : null}
                      {result.correct_answer ? (
                        <p className="text-xs font-bold text-slate-900 dark:text-white">
                          <span className="text-slate-500 dark:text-slate-400">To'g'ri / Namunaviy variant: </span>
                          {String(result.correct_answer)}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                  {Array.isArray(result.pronunciation_errors) && result.pronunciation_errors.length > 0 ? (
                    <div className="mt-2 space-y-1">
                      <p className="text-xs font-black text-amber-700 dark:text-amber-300">🗣️ Talaffuz bo'yicha maslahatlar:</p>
                      {result.pronunciation_errors.map((pe: any, pei: number) => (
                        <div key={pei} className="rounded-lg bg-amber-50 p-2 text-xs text-amber-900 dark:bg-amber-950/40 dark:text-amber-200 border border-amber-200 dark:border-amber-800">
                          <span className="font-bold">{pe.word}:</span> {pe.note || pe.tip || pe.explanation}
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {Array.isArray(result.grammar_errors) && result.grammar_errors.length > 0 ? (
                    <div className="mt-2 space-y-1">
                      {result.grammar_errors.map((ge: any, gei: number) => (
                        <div key={gei} className="rounded-lg bg-red-100/70 p-2 text-xs text-red-900 dark:bg-red-950/40 dark:text-red-200">
                          <span className="font-bold line-through mr-1">{ge.original}</span>
                          <span>→ </span>
                          <span className="font-bold text-emerald-700 dark:text-emerald-300">{ge.correction}</span>
                          {ge.explanation ? <p className="mt-0.5 text-[11px] text-slate-600 dark:text-slate-400">{ge.explanation}</p> : null}
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {question.explanation && !result.ai_feedback ? (
                    <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                      💡 {question.explanation}
                    </p>
                  ) : null}
                </div>
              </div>
            ) : null}

            {/* Bottom Button */}
            {!result ? (
              (() => {
                const canSubmit = isCurrentCloze
                  ? clozeBlanks.length > 0 && clozeBlanks.every((x) => x && x.trim())
                  : isSetQuestion
                  ? Array.isArray(question.sub_questions) &&
                    question.sub_questions.length > 0 &&
                    subAnswers.length >= question.sub_questions.length &&
                    subAnswers.every((x) => x && x.trim())
                  : question.test_type === "matching" || matchingPairs.length > 0
                  ? matchingPairs.length > 0 && Object.keys(matchedPairs).length >= matchingPairs.length
                  : question.test_type === "word_order" || question.test_type === "listening_order" || question.test_type === "scrambled_sentence"
                  ? sentenceWords.length > 0
                  : Boolean(selected.trim());

                return (
                  <button
                    type="button"
                    onClick={() => void submit()}
                    disabled={!canSubmit || loading}
                    className={`w-full rounded-2xl border-2 border-b-4 py-3.5 text-center text-sm font-black uppercase tracking-wider transition-all ${
                      canSubmit && !loading
                        ? "border-[#001A88] bg-[#002DFF] text-white shadow-lg shadow-blue-600/30 active:translate-y-1 active:border-b-2 hover:bg-[#1429f2] cursor-pointer"
                        : "border-slate-200 bg-slate-200 text-slate-400 cursor-not-allowed dark:border-navy-800 dark:bg-navy-900"
                    }`}
                  >
                    {loading ? "Tekshirilmoqda..." : "Tekshirish"}
                  </button>
                );
              })()
            ) : (
              <button
                type="button"
                onClick={next}
                className={`w-full rounded-2xl border-2 border-b-4 py-3.5 text-center text-sm font-black uppercase tracking-wider text-white shadow-lg active:translate-y-1 active:border-b-2 ${
                  result.correct
                    ? "border-[#001A88] bg-[#002DFF] hover:bg-[#1429f2]"
                    : "border-[#d62828] bg-[#ff4b4b] hover:bg-[#ff3333]"
                }`}
              >
                {currentIndex + 1 < lessons.length ? "Davom etish →" : "Natijani ko'rish"}
              </button>
            )}
          </div>
        ) : null}
      </div>
    </div>,
    document.body
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   FINAL EXAM PLAYER MODAL — Comprehensive all-module exam test runner
   ═══════════════════════════════════════════════════════════════════════════════ */

function FinalExamPlayerModal({
  track,
  apiFetch,
  onClose,
}: {
  track: Row;
  apiFetch: ApiFetch;
  onClose: () => void;
}) {
  const [questions, setQuestions] = useState<Row[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selected, setSelected] = useState("");
  const [result, setResult] = useState<Row | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [score, setScore] = useState(0);
  const [finished, setFinished] = useState(false);
  const [examResult, setExamResult] = useState<Row | null>(null);
  const [error, setError] = useState("");
  const [audioPlaying, setAudioPlaying] = useState(false);
  const [voiceMode, setVoiceMode] = useState(false);
  const [reviewItems, setReviewItems] = useState<TestReviewItem[]>([]);
  const [passingScore, setPassingScore] = useState(70);

  const [sentenceWords, setSentenceWords] = useState<string[]>([]);
  const [bankWords, setBankWords] = useState<{ id: number; text: string; used: boolean }[]>([]);

  // For Matching interactive exercise
  const [matchedPairs, setMatchedPairs] = useState<Record<string, string>>({});
  const [matchingPairs, setMatchingPairs] = useState<{ left: string; right: string }[]>([]);
  const [matchingLefts, setMatchingLefts] = useState<string[]>([]);
  const [matchingRights, setMatchingRights] = useState<string[]>([]);

  // For Passage Cloze interactive exercise
  const [clozeBlanks, setClozeBlanks] = useState<string[]>([]);
  const [usedWordBank, setUsedWordBank] = useState<Set<number>>(() => new Set());
  const [wordBankAssignments, setWordBankAssignments] = useState<Record<number, number>>({});
  const [wrongBlankPositions, setWrongBlankPositions] = useState<number[]>([]);

  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    document.body.classList.add("learning-test-mode");
    const origOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.classList.remove("learning-test-mode");
      document.body.style.overflow = origOverflow;
    };
  }, []);

  const loadExam = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch(`/student/learning-tracks/${track.id}/final-exam`);
      const qs = Array.isArray(data?.questions) ? data.questions : [];
      setQuestions(qs);
      setPassingScore(Number(data?.passing_score || track.passing_score || 70));
      if (!qs.length) {
        setError("Yakuniy imtihon uchun savollar topilmadi.");
      }
    } catch (e) {
      setError(errorText(e, "Yakuniy imtihon savollarini yuklab bo'lmadi."));
    } finally {
      setLoading(false);
    }
  }, [track.id, track.passing_score, apiFetch]);

  useEffect(() => {
    void loadExam();
  }, [loadExam]);

  const currentQuestion = questions[currentIndex] || null;

  useEffect(() => {
    if (currentQuestion) {
      // Initialize matching if matching test or pairs provided
      if (currentQuestion.test_type === "matching" || (Array.isArray(currentQuestion.pairs) && currentQuestion.pairs.length > 0)) {
        let pairs: { left: string; right: string }[] = [];
        if (Array.isArray(currentQuestion.pairs) && currentQuestion.pairs.length > 0) {
          pairs = currentQuestion.pairs.filter((p: any) => p && typeof p === "object" && p.left && p.right);
        } else if (Array.isArray(currentQuestion.options)) {
          for (const opt of currentQuestion.options) {
            if (typeof opt === "string" && opt.includes("=")) {
              const [l, r] = opt.split("=").map((s: string) => s.trim());
              if (l && r) pairs.push({ left: l, right: r });
            } else if (typeof opt === "string" && opt.includes(" - ")) {
              const [l, r] = opt.split(" - ").map((s: string) => s.trim());
              if (l && r) pairs.push({ left: l, right: r });
            }
          }
        }
        setMatchingPairs(pairs);
        const lefts = currentQuestion.left_items && Array.isArray(currentQuestion.left_items) && currentQuestion.left_items.length
          ? currentQuestion.left_items
          : pairs.map((p) => p.left);
        const rights = currentQuestion.right_items && Array.isArray(currentQuestion.right_items) && currentQuestion.right_items.length
          ? currentQuestion.right_items
          : [...pairs.map((p) => p.right)].sort(() => Math.random() - 0.5);
        setMatchingLefts(lefts);
        setMatchingRights(rights);
        setMatchedPairs({});
      } else {
        setMatchingPairs([]);
        setMatchingLefts([]);
        setMatchingRights([]);
        setMatchedPairs({});
      }

      setClozeBlanks([]);
      setUsedWordBank(new Set());
      setWordBankAssignments({});
      setWrongBlankPositions([]);

      const examHasOptions = Array.isArray(currentQuestion.options) && currentQuestion.options.length >= 2;
      const isClozeQ =
        !examHasOptions &&
        (currentQuestion.test_type === "passage_cloze" ||
          currentQuestion.input === "cloze" ||
          Boolean(currentQuestion.passage_template) ||
          (typeof currentQuestion.passage === "string" && currentQuestion.passage.includes("___")) ||
          (typeof currentQuestion.question === "string" && currentQuestion.question.includes("___")));
      if (isClozeQ) {
        const tmpl = String(currentQuestion.passage_template || currentQuestion.passage || currentQuestion.question || "");
        const total = (tmpl.match(/___/g) || []).length || (Array.isArray(currentQuestion.blanks) ? currentQuestion.blanks.length : 0);
        setClozeBlanks(Array.from({ length: total }, () => ""));
      }

      const isWordsOfAnswer =
        Array.isArray(currentQuestion.options) &&
        currentQuestion.options.length > 1 &&
        currentQuestion.options.map((w: string) => w.trim().toLowerCase()).join(" ") === String(currentQuestion.correct_answer || "").trim().toLowerCase();

      if (currentQuestion.test_type === "word_order" || currentQuestion.test_type === "listening_order" || currentQuestion.test_type === "scrambled_sentence" || isWordsOfAnswer || (Array.isArray(currentQuestion.tokens) && currentQuestion.tokens.length > 0)) {
        let rawWords: string[] = [];
        if (Array.isArray(currentQuestion.tokens) && currentQuestion.tokens.length > 0) {
          rawWords = [...currentQuestion.tokens, ...(Array.isArray(currentQuestion.distractors) ? currentQuestion.distractors : [])];
        } else {
          const fullText = String(currentQuestion.correct_answer || currentQuestion.prompt || currentQuestion.question || "");
          rawWords = fullText.split(/\s+/).filter(Boolean);
        }
        const shuffled = [...rawWords].sort(() => Math.random() - 0.5);
        setBankWords(shuffled.map((w, idx) => ({ id: idx, text: w, used: false })));
        setSentenceWords([]);
        setSelected("");
      } else {
        setSentenceWords([]);
        setBankWords([]);
        setSelected("");
      }
    } else {
      setSentenceWords([]);
      setBankWords([]);
      setSelected("");
      setMatchingPairs([]);
      setMatchingLefts([]);
      setMatchingRights([]);
      setMatchedPairs({});
      setClozeBlanks([]);
      setUsedWordBank(new Set());
      setWordBankAssignments({});
      setWrongBlankPositions([]);
    }
    const isVoice =
      currentQuestion?.input === "audio" ||
      currentQuestion?.test_type === "speak_sentence" ||
      currentQuestion?.test_type === "read_aloud" ||
      currentQuestion?.test_type === "speaking_repeat" ||
      currentQuestion?.test_type === "speaking_response" ||
      currentQuestion?.kind === "speak_sentence" ||
      currentQuestion?.kind === "read_aloud" ||
      currentQuestion?.kind === "speaking_repeat" ||
      currentQuestion?.kind === "speaking_response";
    setVoiceMode(Boolean(isVoice));
    setResult(null);
  }, [currentIndex, currentQuestion]);

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

  const playAudio = (rate = 1.0) => {
    if (!audioRef.current || !currentQuestion?.audio_url) return;
    audioRef.current.playbackRate = rate;
    audioRef.current.currentTime = 0;
    setAudioPlaying(true);
    audioRef.current.play().catch(() => setAudioPlaying(false));
  };

  const examHasCurrentOptions = Array.isArray(currentQuestion?.options) && currentQuestion.options.length >= 2;
  const isExamCloze =
    !examHasCurrentOptions &&
    (currentQuestion?.test_type === "passage_cloze" ||
      currentQuestion?.input === "cloze" ||
      Boolean(currentQuestion?.passage_template) ||
      (typeof currentQuestion?.passage === "string" && currentQuestion.passage.includes("___")) ||
      (typeof currentQuestion?.question === "string" && currentQuestion.question.includes("___")));

  const checkAnswer = async (override?: { answer_text?: string; audio_url?: string }) => {
    if (!currentQuestion || result) return;
    const isCloze = isExamCloze;
    const audioUrl = override?.audio_url;

    if (!audioUrl && !selected && !override?.answer_text && matchingPairs.length === 0 && (!isCloze || clozeBlanks.every((x) => !x || !x.trim()))) return;

    const currentAnsText = override?.answer_text !== undefined ? override.answer_text : selected;
    const normSelected = currentAnsText.trim().toLowerCase();
    const acceptable = Array.isArray(currentQuestion?.acceptable_answers)
      ? currentQuestion.acceptable_answers.map((a: unknown) => String(a).trim().toLowerCase())
      : [];
    const correctAns = String(currentQuestion.correct_answer || "").trim().toLowerCase();
    const correctParts = correctAns.includes(";")
      ? correctAns.split(";").map((p) => p.trim().toLowerCase()).filter(Boolean)
      : correctAns.includes("\n")
      ? correctAns.split("\n").map((p) => p.trim().toLowerCase()).filter(Boolean)
      : [];

    let correct = false;
    let selectedAnswer = audioUrl ? "[Ovozli javob]" : currentAnsText;
    let correctAnswerStr = String(currentQuestion.correct_answer || "");

    const qTestType = String(currentQuestion.test_type || "").toLowerCase();
    const qKind = String(currentQuestion.kind || "").toLowerCase();
    const isAiCheck =
      Boolean(audioUrl) ||
      currentQuestion.check === "ai" ||
      [
        "write_sentence",
        "guided_writing",
        "reading_open",
        "open",
        "translation",
        "paraphrase",
        "picture_description",
        "dialogue_completion",
        "speak_sentence",
        "read_aloud",
        "speaking_repeat",
        "speaking_response",
        "listening_open",
        "word_practice",
      ].includes(qTestType) ||
      [
        "write_sentence",
        "guided_writing",
        "reading_open",
        "open",
        "translation",
        "paraphrase",
        "picture_description",
        "dialogue_completion",
        "speak_sentence",
        "read_aloud",
        "speaking_repeat",
        "speaking_response",
        "listening_open",
        "word_practice",
      ].includes(qKind) ||
      (!isCloze &&
        currentQuestion.test_type !== "matching" &&
        matchingPairs.length === 0 &&
        currentQuestion.test_type !== "word_order" &&
        currentQuestion.test_type !== "scrambled_sentence" &&
        !correctAns &&
        (!Array.isArray(currentQuestion.options) || currentQuestion.options.length === 0));

    let aiFeedbackText = "";
    let aiCorrectedText = "";
    let aiTranscriptText = "";
    let aiPronErrors: any[] = [];
    let aiGrammarErrors: any[] = [];

    if (isAiCheck) {
      setLoading(true);
      try {
        const aiRes = await apiFetch(`/student/learning-lessons/check-ai`, {
          method: "POST",
          body: {
            question_payload: currentQuestion,
            answer_text: currentAnsText,
            audio_url: audioUrl,
          },
        });
        correct = Boolean(aiRes?.is_correct ?? (aiRes?.verdict === "correct"));
        aiFeedbackText = String(aiRes?.feedback || (correct ? "Ajoyib! Juda to'g'ri!" : "Javobingizda xatolik mavjud."));
        aiCorrectedText = String(aiRes?.corrected || aiRes?.correct_answer || "");
        aiTranscriptText = String(aiRes?.transcript || "");
        aiPronErrors = Array.isArray(aiRes?.pronunciation_errors) ? aiRes.pronunciation_errors : [];
        aiGrammarErrors = Array.isArray(aiRes?.grammar_errors) ? aiRes.grammar_errors : [];
        if (aiCorrectedText) {
          correctAnswerStr = aiCorrectedText;
        }
        if (aiTranscriptText) {
          selectedAnswer = `[Ovozli]: ${aiTranscriptText}`;
        }
      } catch (err) {
        correct = false;
        aiFeedbackText = errorText(err, "AI tekshirish xizmati javob bermadi. Qayta urinib ko'ring.");
      } finally {
        setLoading(false);
      }
    } else if (isCloze) {
      const blanks = Array.isArray(currentQuestion.blanks) ? currentQuestion.blanks : [];
      const wrongPositions: number[] = [];
      const expectedAnswersList: string[] = [];

      for (let i = 0; i < clozeBlanks.length; i++) {
        const b = blanks[i];
        const given = (clozeBlanks[i] || "").trim().toLowerCase();
        let isBlankCorrect = false;
        let expectedLabel = "";

        if (b && typeof b === "object") {
          const mainAns = String(b.answer || "").trim();
          expectedLabel = mainAns;
          const expectedSet = new Set([
            mainAns.toLowerCase(),
            ...(Array.isArray(b.accepted_answers) ? b.accepted_answers.map((x: any) => String(x).trim().toLowerCase()) : []),
          ]);
          expectedSet.delete("");
          if (expectedSet.has(given)) {
            isBlankCorrect = true;
          }
        } else if (typeof b === "string") {
          expectedLabel = b.trim();
          if (given === b.trim().toLowerCase()) {
            isBlankCorrect = true;
          }
        } else if (Array.isArray(currentQuestion.answers) && currentQuestion.answers[i]) {
          expectedLabel = String(currentQuestion.answers[i]).trim();
          if (given === expectedLabel.toLowerCase()) {
            isBlankCorrect = true;
          }
        } else if (correctAns) {
          const parts = correctAns.split(/[,;\n]+/).map((s) => s.trim());
          if (parts[i]) {
            expectedLabel = parts[i];
            if (given === parts[i].toLowerCase()) {
              isBlankCorrect = true;
            }
          }
        }

        if (expectedLabel) {
          expectedAnswersList.push(`${i + 1}. ${expectedLabel}`);
        }
        if (!isBlankCorrect) {
          wrongPositions.push(i + 1);
        }
      }

      setWrongBlankPositions(wrongPositions);
      correct = wrongPositions.length === 0 && clozeBlanks.length > 0;
      selectedAnswer = clozeBlanks.map((ans, idx) => `${idx + 1}. ${ans || "___"}`).join(", ");
      if (expectedAnswersList.length > 0) {
        correctAnswerStr = expectedAnswersList.join(" | ");
      }
    } else if (currentQuestion.test_type === "matching" || matchingPairs.length > 0) {
      correct =
        matchingPairs.length > 0 &&
        matchingPairs.every(
          (p) => (matchedPairs[p.left] || "").trim().toLowerCase() === p.right.trim().toLowerCase()
        );
      selectedAnswer = Object.entries(matchedPairs).map(([l, r]) => `${l} = ${r}`).join("; ");
      correctAnswerStr = matchingPairs.map((p) => `${p.left} = ${p.right}`).join("; ");
    } else {
      correct = isAnswerCorrect(currentAnsText, currentQuestion);
    }

    const newScore = score + (correct ? 1 : 0);
    setScore(newScore);

    setReviewItems((prev) => [
      ...prev,
      {
        prompt: String(currentQuestion.instruction || currentQuestion.question || currentQuestion.prompt || currentQuestion.title || `Savol ${currentIndex + 1}`),
        selected_answer: selectedAnswer,
        correct_answer: correctAnswerStr || String(currentQuestion.correct_answer || ""),
        options: Array.isArray(currentQuestion.options) ? currentQuestion.options : [],
        is_correct: correct,
        explanation: String(currentQuestion.explanation || ""),
        question_type: String(currentQuestion.test_type || "multiple_choice"),
      },
    ]);

    if (correct) {
      playDuolingoSound("correct");
    } else {
      playDuolingoSound("wrong");
    }
    setResult({
      correct,
      selected: selectedAnswer,
      correct_answer: correctAnswerStr,
      explanation: currentQuestion.explanation || "",
      ai_feedback: aiFeedbackText,
      ai_corrected: aiCorrectedText,
      ai_transcript: aiTranscriptText,
      pronunciation_errors: aiPronErrors,
      grammar_errors: aiGrammarErrors,
    });
  };

  const handleNext = async () => {
    if (currentIndex + 1 < questions.length) {
      setCurrentIndex((prev) => prev + 1);
    } else {
      setSubmitting(true);
      const finalPercent = questions.length ? Math.round((score / questions.length) * 100) : 0;
      try {
        const res = await apiFetch(`/student/learning-tracks/${track.id}/final-exam/submit`, {
          method: "POST",
          body: {
            score: finalPercent,
            answers: reviewItems.map((r) => ({
              question: r.prompt,
              selected: r.selected_answer,
              correct: r.is_correct,
            })),
          },
        });
        setExamResult(res);
        if (res?.passed) {
          playDuolingoSound("complete");
        }
      } catch (err: any) {
        setError(err?.message || "Natija saqlanmadi.");
      } finally {
        setSubmitting(false);
        setFinished(true);
      }
    }
  };

  const progressPercent = questions.length
    ? Math.round(((currentIndex + (result ? 1 : 0)) / questions.length) * 100)
    : 0;

  if (typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-[999999] flex items-center justify-center bg-black/75 p-3 backdrop-blur-sm sm:p-6 animate-fade-in">
      <div className="relative flex h-full max-h-[96vh] w-full max-w-xl flex-col overflow-hidden rounded-3xl border-2 border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-[#0f172a]">
        {currentQuestion?.audio_url ? (
          <audio
            ref={audioRef}
            src={currentQuestion.audio_url}
            onEnded={() => setAudioPlaying(false)}
            onError={() => setAudioPlaying(false)}
          />
        ) : null}

        {/* Top Header */}
        <div className="flex items-center gap-3 border-b border-slate-100 p-4 dark:border-slate-800">
          <button
            type="button"
            onClick={onClose}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-xl text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:text-slate-400"
            title="Chiqish"
          >
            ✕
          </button>
          <div className="relative h-3 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-[#002DFF] to-[#38bdf8] transition-all duration-300 relative overflow-hidden shadow-[0_0_10px_rgba(56,189,248,0.4)]"
              style={{ width: `${progressPercent}%` }}
            >
              <div className="absolute top-1 left-2 right-2 h-1 rounded-full bg-white/40" />
            </div>
          </div>
          <span className="flex items-center gap-1 text-xs font-black text-[#002DFF] dark:text-[#38bdf8]">
            <span>🏆</span>
            <span>Yakuniy Imtihon</span>
          </span>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6">
          {loading ? (
            <div className="flex h-64 flex-col items-center justify-center gap-3 text-slate-400">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-[#002DFF] border-t-transparent" />
              <p className="text-xs font-bold">Imtihon savollari tayyorlanmoqda...</p>
            </div>
          ) : error && !questions.length ? (
            <div className="rounded-2xl border-2 border-rose-300 bg-rose-50 p-5 text-center text-sm font-bold text-rose-700 dark:border-rose-900 dark:bg-rose-950/40">
              <p>{error}</p>
              <button
                type="button"
                onClick={onClose}
                className="mt-4 rounded-xl bg-rose-600 px-4 py-2 text-xs font-black text-white hover:bg-rose-700"
              >
                Chiqish
              </button>
            </div>
          ) : finished ? (
            (() => {
              const finalPercent = questions.length ? Math.round((score / questions.length) * 100) : 0;
              const isPassed = examResult ? Boolean(examResult.passed) : finalPercent >= passingScore;

              return (
                <div className="flex flex-col items-center py-4 text-center animate-scale-up">
                  <div className="relative my-2">
                    <div
                      className={`grid h-24 w-24 place-items-center rounded-3xl text-4xl shadow-xl ring-4 ${
                        isPassed
                          ? "border-4 border-[#001A88] bg-gradient-to-b from-[#1429f2] to-[#002DFF] text-white shadow-2xl ring-4 ring-[#002DFF]/40 animate-bounce"
                          : "bg-rose-100 text-rose-600 ring-rose-300 dark:bg-rose-950/50 dark:ring-rose-800"
                      }`}
                    >
                      {isPassed ? "🎓" : "⚠️"}
                    </div>
                  </div>

                  <h3 className="mt-3 text-2xl font-black text-navy-900 dark:text-white">
                    {isPassed ? "🎉 Tabriklaymiz!" : "Qayta topshirish kerak"}
                  </h3>

                  <div className="mt-4 grid grid-cols-2 gap-3 w-full max-w-xs">
                    <div className="rounded-2xl border-2 border-b-4 border-slate-200 bg-slate-50 p-3 dark:border-white/10 dark:bg-navy-800">
                      <p className="text-[10px] font-bold text-slate-400 uppercase">To'g'ri javoblar</p>
                      <p className="mt-0.5 text-xl font-black text-navy-900 dark:text-white">
                        {score} / {questions.length}
                      </p>
                    </div>
                    <div
                      className={`rounded-2xl border-2 border-b-4 p-3 ${
                        isPassed
                          ? "border-[#001A88] bg-blue-50 dark:border-blue-800 dark:bg-blue-950/40"
                          : "border-rose-300 bg-rose-50 dark:border-rose-800 dark:bg-rose-950/40"
                      }`}
                    >
                      <p className="text-[10px] font-bold uppercase text-slate-500">Natija</p>
                      <p
                        className={`mt-0.5 text-xl font-black ${
                          isPassed ? "text-[#001A88] dark:text-blue-200" : "text-rose-800 dark:text-rose-200"
                        }`}
                      >
                        {finalPercent}%
                      </p>
                    </div>
                  </div>

                  {isPassed ? (
                    <div className="mt-4 rounded-2xl border-2 border-b-4 border-[#001A88] bg-blue-50 p-4 text-sm font-black text-[#001A88] dark:bg-blue-950/40 dark:text-blue-200 dark:border-blue-800">
                      🎓 Yakuniy imtihon muvaffaqiyatli topshirildi ({finalPercent}% ≥ {passingScore}%)! Rasmiy sertifikat berildi va keyingi track ochildi!
                    </div>
                  ) : (
                    <div className="mt-4 rounded-2xl border-2 border-b-4 border-rose-400 bg-rose-50 p-4 text-sm font-black text-rose-700 dark:bg-rose-950/50 dark:text-rose-300">
                      ⚠️ O'tish bali: {passingScore}%. Sizning ballingiz: {finalPercent}%. Keyingi track ochilishi va sertifikat olish uchun imtihonni qayta topshiring.
                    </div>
                  )}

                  {isPassed ? (
                    <div className="mt-3 flex items-center justify-center gap-2 rounded-2xl border border-blue-200 bg-blue-50 px-4 py-2.5 text-xs font-black text-[#001A88] dark:border-blue-800 dark:bg-blue-950/50 dark:text-blue-200">
                      <span>🎁 Mukofot:</span>
                      <span>💎 +50 D'Point</span>
                      <span>va</span>
                      <span>💰 +50 D'Coin qo'shildi!</span>
                    </div>
                  ) : null}

                  {isPassed && examResult?.certificate ? (
                    <div className="mt-4 w-full rounded-2xl border-2 border-blue-200 bg-gradient-to-br from-blue-50/80 to-indigo-50/80 p-4 text-left dark:border-blue-800/40 dark:bg-blue-950/30">
                      <div className="flex items-center gap-2.5">
                        <span className="text-2xl">🎓</span>
                        <div>
                          <p className="text-xs font-black text-blue-950 dark:text-blue-200">
                            {examResult.certificate.course_title || track.title}
                          </p>
                          <p className="text-[10px] font-mono text-blue-700 dark:text-blue-400">
                            ID: {examResult.certificate.certificate_id}
                          </p>
                        </div>
                      </div>
                      <div className="mt-3">
                        <a
                          href={`/api/student/certificates/${examResult.certificate.certificate_id}/pdf`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex w-full items-center justify-center gap-2 rounded-xl border-2 border-b-4 border-[#001A88] bg-[#002DFF] hover:bg-[#1429f2] py-2.5 px-4 text-xs font-black text-white shadow-md transition active:translate-y-0.5 active:border-b-2"
                        >
                          <span>📄 Sertifikatni PDF ko'rish / Yuklab olish</span>
                        </a>
                      </div>
                    </div>
                  ) : null}

                  {reviewItems.length > 0 ? (
                    <TestCompletionActions
                      testTitle={String(track.title || "Yakuniy Imtihon")}
                      subject={String(track.subject || "")}
                      review={reviewItems}
                      className="mt-4"
                    />
                  ) : null}

                  {isPassed ? (
                    <button
                      type="button"
                      onClick={onClose}
                      className="mt-6 w-full rounded-2xl border-2 border-b-4 border-[#001A88] bg-[#002DFF] hover:bg-[#1429f2] py-4 text-base font-black uppercase tracking-wider text-white shadow-xl shadow-blue-600/30 active:translate-y-1 active:border-b-2 cursor-pointer"
                    >
                      Tugatish & Davom etish
                    </button>
                  ) : (
                    <div className="mt-6 space-y-3 w-full">
                      <button
                        type="button"
                        onClick={() => {
                          setScore(0);
                          setFinished(false);
                          setReviewItems([]);
                          setCurrentIndex(0);
                          void loadExam();
                        }}
                        className="flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-b-4 border-rose-600 bg-rose-500 py-4 text-base font-black uppercase tracking-wider text-white shadow-xl active:translate-y-1 active:border-b-2 hover:bg-rose-600"
                      >
                        <span>🔄</span>
                        <span>Qayta topshirish</span>
                      </button>
                      <button
                        type="button"
                        onClick={onClose}
                        className="w-full rounded-2xl border border-slate-200 bg-white py-3 text-sm font-bold text-slate-600 transition hover:bg-slate-50 dark:border-navy-700 dark:bg-navy-800 dark:text-navy-300"
                      >
                        Chiqish
                      </button>
                    </div>
                  )}
                </div>
              );
            })()
          ) : currentQuestion ? (
            <div className="space-y-5 animate-fade-in">
              <div className="flex items-center justify-between">
                <span className="rounded-xl bg-amber-500/10 px-3 py-1 text-xs font-black uppercase tracking-wider text-amber-700 dark:text-amber-300">
                  {isExamCloze || currentQuestion.test_type === "passage_cloze"
                    ? "📝 Matnni to'ldiring"
                    : currentQuestion.test_type === "speak_sentence" || currentQuestion.kind === "speak_sentence"
                    ? "🗣️ Ovozli gap tuzish"
                    : currentQuestion.test_type === "read_aloud" || currentQuestion.kind === "read_aloud"
                    ? "🗣️ Ovoz chiqarib o'qish"
                    : currentQuestion.test_type === "word_practice" || currentQuestion.kind === "word_practice"
                    ? "📚 So'z mashqi (Vocabulary)"
                    : currentQuestion.test_type === "spelling" || currentQuestion.kind === "spelling"
                    ? "🔤 To'g'ri yozilish (spelling)"
                    : currentQuestion.test_type === "translation" || currentQuestion.kind === "translation"
                    ? "🌐 Tarjima qiling"
                    : currentQuestion.test_type === "picture_description" || currentQuestion.kind === "picture_description"
                    ? "🖼️ Rasmni tasvirlang"
                    : currentQuestion.test_type === "write_sentence" || currentQuestion.test_type === "guided_writing"
                    ? "✍️ Gap yozish"
                    : currentQuestion.test_type === "word_order" || currentQuestion.test_type === "listening_order" || currentQuestion.test_type === "scrambled_sentence"
                    ? "🧩 Gap tuzing"
                    : currentQuestion.test_type === "true_false" || currentQuestion.test_type === "listening_tf"
                    ? "⚖️ To'g'ri yoki Noto'g'ri"
                    : currentQuestion.test_type === "fill_blank" || currentQuestion.test_type === "listening_gap" || currentQuestion.test_type === "gap_fill"
                    ? "✏️ Bo'sh joyni to'ldiring"
                    : currentQuestion.test_type === "matching"
                    ? "🔄 Moslashtiring"
                    : currentQuestion.test_type === "paraphrase"
                    ? "🔄 Qayta ifodalash"
                    : currentQuestion.test_type === "listening_dictation"
                    ? "✍️ Diktant (eshitib yozish)"
                    : currentQuestion.test_type === "reading_open" || currentQuestion.test_type === "listening_open"
                    ? "📖 Savolga javob yozing"
                    : currentQuestion.module_title
                    ? `📌 ${currentQuestion.module_title}`
                    : "🎓 Yakuniy Imtihon"}
                </span>
                <span className="text-xs font-bold text-slate-400">
                  {currentIndex + 1} / {questions.length}
                </span>
              </div>

              {/* Target Word Banner (Duolingo / Materials Library style) */}
              {currentQuestion.word ? (
                <TargetWordBanner
                  word={currentQuestion.word}
                  phonetic={currentQuestion.phonetic || currentQuestion.pronunciation}
                  targetLevel={currentQuestion.target_level || currentQuestion.level}
                  definition={currentQuestion.definition}
                  meaning={currentQuestion.meaning}
                  hint={currentQuestion.hint}
                  exampleSentence={currentQuestion.example_sentence}
                />
              ) : null}

              {/* Question Image if present */}
              {currentQuestion.image_url ? (
                <div className="overflow-hidden rounded-2xl border-2 border-slate-200 dark:border-slate-800">
                  <img
                    src={currentQuestion.image_url.startsWith("/") ? `/api${currentQuestion.image_url}` : currentQuestion.image_url}
                    alt="Savol rasmi"
                    className="max-h-64 w-full object-contain bg-slate-50 dark:bg-slate-900"
                  />
                </div>
              ) : null}

              <h2 className="text-xl sm:text-2xl font-black leading-snug text-slate-800 dark:text-white">
                {currentQuestion.instruction ||
                  (currentQuestion.question && currentQuestion.question.trim() !== currentQuestion.passage?.trim()
                    ? currentQuestion.question
                    : null) ||
                  currentQuestion.prompt ||
                  "Savolga javob bering:"}
              </h2>

              {/* Question Condition Banner (especially for word_practice and tasks with clear conditions) */}
              {currentQuestion.test_type === "word_practice" || currentQuestion.practice_mode || currentQuestion.condition_uz || currentQuestion.condition ? (
                <div className="flex items-start gap-3 rounded-2xl border-2 border-amber-300 bg-amber-50/90 p-4 text-amber-950 shadow-sm dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-100">
                  <span className="text-2xl shrink-0 mt-0.5">🎯</span>
                  <div className="space-y-1">
                    <span className="inline-block rounded-md bg-amber-200/80 px-2 py-0.5 text-[11px] font-black uppercase tracking-wider text-amber-900 dark:bg-amber-900/60 dark:text-amber-200">
                      {getCurrentLang() === "ru" ? "Условие задания" : getCurrentLang() === "en" ? "Task Instruction" : "Topshiriq sharti"}
                    </span>
                    <p className="text-sm sm:text-base font-bold leading-snug">
                      {getWordPracticeCondition(currentQuestion, getCurrentLang())}
                    </p>
                  </div>
                </div>
              ) : null}

              {/* Passage / Context if available (hidden for cloze) */}
              {!isExamCloze && (currentQuestion.passage || currentQuestion.context) && (currentQuestion.question?.trim() !== currentQuestion.passage?.trim()) ? (
                <div className="rounded-2xl border-2 border-amber-200 bg-amber-50/60 p-4 text-sm leading-relaxed text-slate-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200 max-h-56 overflow-y-auto whitespace-pre-wrap font-medium">
                  <div className="flex items-center gap-1.5 text-xs font-black uppercase text-amber-700 dark:text-amber-300 mb-1.5">
                    <span>📖</span>
                    <span>Matn / Passage</span>
                  </div>
                  {String(currentQuestion.passage || currentQuestion.context)}
                </div>
              ) : null}

              {currentQuestion.audio_url ? (
                <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-3 dark:border-white/10 dark:bg-navy-800">
                  <button
                    type="button"
                    onClick={() => playAudio(1.0)}
                    disabled={audioPlaying}
                    className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-[#002DFF] text-white shadow-md hover:bg-[#1429f2] disabled:opacity-50"
                  >
                    {audioPlaying ? "🔊" : "▶️"}
                  </button>
                  <p className="text-xs font-bold text-slate-600 dark:text-slate-300">Audiolavhani tinglang</p>
                </div>
              ) : null}

              {(() => {
                const isVoiceQuestion =
                  currentQuestion.input === "audio" ||
                  currentQuestion.test_type === "speak_sentence" ||
                  currentQuestion.test_type === "read_aloud" ||
                  currentQuestion.test_type === "speaking_repeat" ||
                  currentQuestion.test_type === "speaking_response" ||
                  currentQuestion.kind === "speak_sentence" ||
                  currentQuestion.kind === "read_aloud" ||
                  currentQuestion.kind === "speaking_repeat" ||
                  currentQuestion.kind === "speaking_response";
                const isVoiceOrText = currentQuestion.input === "audio_or_text" || isVoiceQuestion;

                // ─── Voice Exercise (Instant Voice Recorder with auto-check on release) ───
                if (isVoiceQuestion || (isVoiceOrText && voiceMode)) {
                  return (
                    <div className="space-y-4 pt-2">
                      <InstantVoiceRecorder
                        apiFetch={apiFetch}
                        disabled={Boolean(result) || loading || submitting}
                        onRecorded={async (audioUrl) => {
                          await checkAnswer({ audio_url: audioUrl });
                        }}
                      />
                      {isVoiceOrText && (
                        <div className="text-center">
                          <button
                            type="button"
                            disabled={Boolean(result)}
                            onClick={() => setVoiceMode(false)}
                            className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-[#002DFF] dark:text-slate-400 dark:hover:text-[#38bdf8]"
                          >
                            ✍️ Yozma javob berishga o'tish
                          </button>
                        </div>
                      )}
                    </div>
                  );
                }
                // ─── Exercise Type 0: Passage Cloze ───
                if (isExamCloze) {
                  const template = String(currentQuestion.passage_template || currentQuestion.passage || currentQuestion.question || "");
                  const totalBlanks = (template.match(/___/g) || []).length || (Array.isArray(currentQuestion.blanks) ? currentQuestion.blanks.length : 0);
                  const setBlank = (i: number, v: string) => {
                    setClozeBlanks((prev) => {
                      const next = [...prev];
                      while (next.length < totalBlanks) next.push("");
                      next[i] = v;
                      return next;
                    });
                  };
                  const filled = Array.from({ length: totalBlanks }, (_, i) => clozeBlanks[i] || "");
                  const lines = template.split("\n");
                  let blankCursor = 0;
                  const wordBank: string[] = Array.isArray(currentQuestion.word_bank) ? currentQuestion.word_bank : [];
                  const textForCheck = `${currentQuestion.instruction || ""} ${currentQuestion.question || ""} ${currentQuestion.prompt || ""} ${template}`.toLowerCase();
                  const isTenseOrForm =
                    textForCheck.includes("form") ||
                    textForCheck.includes("tense") ||
                    textForCheck.includes("zamon") ||
                    textForCheck.includes("shakl") ||
                    textForCheck.includes("put the verb") ||
                    textForCheck.includes("in brackets") ||
                    textForCheck.includes("qavs");
                  const hasBrackets = /\(\s*[a-zA-Z'\s-]+\s*\)/.test(template);
                  const blanksList = Array.isArray(currentQuestion.blanks) ? currentQuestion.blanks : Array.isArray(currentQuestion.answers) ? currentQuestion.answers : [];
                  const ansSet = new Set(blanksList.map((b: any) => String(b?.answer || b || "").trim().toLowerCase()));
                  const bankSet = new Set(wordBank.map((w) => String(w || "").trim().toLowerCase()));
                  const showWordBank =
                    wordBank.length > 0 &&
                    !(isTenseOrForm && hasBrackets) &&
                    !(isTenseOrForm && ansSet.size > 0 && [...ansSet].every((a) => bankSet.has(a)));

                  return (
                    <div className="space-y-4 pt-1">
                      {/* Word bank chips — displayed at the TOP above sentences */}
                      {showWordBank && (
                        <div className="rounded-2xl border-2 border-slate-200 bg-white p-3.5 shadow-sm dark:border-navy-700 dark:bg-navy-800">
                          <p className="text-xs font-black uppercase tracking-wider text-[#002DFF] dark:text-[#38bdf8] mb-2">
                            💡 So'zlar banki — joylash uchun bosing:
                          </p>
                          <div className="flex flex-wrap gap-2 justify-center">
                            {wordBank.map((w, i) => {
                              const marked = usedWordBank.has(i);
                              return (
                                <button
                                  key={`${w}-${i}`}
                                  type="button"
                                  disabled={Boolean(result)}
                                  onClick={() => {
                                    playDuolingoSound("pop");
                                    if (marked) {
                                      const blankIndex = Object.entries(wordBankAssignments).find(([, value]) => value === i)?.[0];
                                      if (blankIndex !== undefined) setBlank(Number(blankIndex), "");
                                      setWordBankAssignments((prev) => {
                                        const next = { ...prev };
                                        if (blankIndex !== undefined) delete next[Number(blankIndex)];
                                        return next;
                                      });
                                      setUsedWordBank((prev) => {
                                        const next = new Set(prev);
                                        next.delete(i);
                                        return next;
                                      });
                                      return;
                                    }
                                    const idx = filled.findIndex((x) => !x.trim());
                                    if (idx < 0) return;
                                    setBlank(idx, w);
                                    setWordBankAssignments((prev) => ({ ...prev, [idx]: i }));
                                    setUsedWordBank((prev) => new Set(prev).add(i));
                                  }}
                                  className={`rounded-2xl border-2 px-3.5 py-2 text-sm font-black transition-all select-none ${
                                    marked
                                      ? "border-slate-200 bg-slate-200/50 text-slate-400 line-through opacity-40 dark:border-navy-800 dark:bg-navy-900"
                                      : "border-slate-200 border-b-4 bg-white text-navy-900 shadow-sm active:translate-y-1 active:border-b-2 hover:bg-cyan-50 hover:border-cyan-400 dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                                  }`}
                                >
                                  {w}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Interactive cloze text container */}
                      <div className="space-y-2.5 rounded-3xl border-2 border-slate-200 bg-slate-50/80 p-4 sm:p-5 text-base leading-loose text-slate-900 dark:border-navy-700 dark:bg-navy-900/50 dark:text-white font-medium">
                        {lines.map((line, li) => {
                          const segs = line.split("___");
                          const rowGaps = segs.length - 1;
                          const startIdx = blankCursor;
                          blankCursor += rowGaps;
                          return (
                            <div key={li} className="leading-loose">
                              {segs.map((seg, si) => {
                                const gi = startIdx + si;
                                const isWrong = result && wrongBlankPositions.includes(gi + 1);
                                const isCorrect = result && !isWrong;

                                return (
                                  <span key={si}>
                                    {seg}
                                    {si < rowGaps && (
                                      <span className="relative inline-block mx-1">
                                        <input
                                          type="text"
                                          value={filled[gi] || ""}
                                          disabled={Boolean(result)}
                                          onChange={(e) => {
                                            setBlank(gi, e.target.value);
                                            const bankIndex = wordBankAssignments[gi];
                                            if (bankIndex !== undefined) {
                                              setWordBankAssignments((prev) => {
                                                const next = { ...prev };
                                                delete next[gi];
                                                return next;
                                              });
                                              setUsedWordBank((prev) => {
                                                const next = new Set(prev);
                                                next.delete(bankIndex);
                                                return next;
                                              });
                                            }
                                          }}
                                          className={`w-28 sm:w-32 rounded-xl border-2 px-2 py-1 text-center text-sm sm:text-base font-black outline-none transition-all ${
                                            result
                                              ? isCorrect
                                                ? "border-[#58cc02] bg-[#d7ffb8] text-[#2e6b00] dark:bg-[#183617] dark:text-[#a0ff6d]"
                                                : "border-[#ff4b4b] bg-[#ffdfe0] text-[#a01818] dark:bg-[#3d1a1b] dark:text-[#ffa0a0]"
                                              : filled[gi]
                                              ? "border-[#84d8ff] border-b-4 bg-[#ddf4ff] text-[#1899d6] dark:border-[#1cb0f6] dark:bg-[#18394a] dark:text-white"
                                              : "border-slate-300 border-b-4 bg-white text-navy-900 focus:border-[#002DFF] dark:border-navy-600 dark:bg-navy-800 dark:text-white"
                                          }`}
                                          placeholder={`(${gi + 1})`}
                                        />
                                        {isWrong && Array.isArray(currentQuestion.blanks) && currentQuestion.blanks[gi] ? (
                                          <span className="block text-[11px] font-black text-[#a01818] dark:text-[#ffa0a0] text-center">
                                            {String(currentQuestion.blanks[gi]?.answer || currentQuestion.blanks[gi])}
                                          </span>
                                        ) : null}
                                      </span>
                                    )}
                                  </span>
                                );
                              })}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                }

                const isWordsOfAnswer =
                  Array.isArray(currentQuestion.options) &&
                  currentQuestion.options.length > 1 &&
                  currentQuestion.options.map((w: string) => w.trim().toLowerCase()).join(" ") === String(currentQuestion.correct_answer || "").trim().toLowerCase();

                const hasCorrectChoice =
                  Array.isArray(currentQuestion.options) &&
                  currentQuestion.options.some((opt: string) => isAnswerCorrect(opt, currentQuestion));

                const correctParts = String(currentQuestion.correct_answer || "").includes(";")
                  ? String(currentQuestion.correct_answer || "").split(";").map((p) => p.trim().toLowerCase()).filter(Boolean)
                  : [];

                if (currentQuestion.test_type === "word_order" || currentQuestion.test_type === "listening_order" || currentQuestion.test_type === "scrambled_sentence" || isWordsOfAnswer) {
                  return (
                    <div className="space-y-6">
                      <div className="min-h-20 rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50/70 p-3 flex flex-wrap gap-2 items-center dark:border-navy-700 dark:bg-navy-900/60">
                        {sentenceWords.map((word, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => handleSentenceWordRemove(idx)}
                            disabled={Boolean(result)}
                            className="rounded-xl border-2 border-b-4 border-slate-300 bg-white px-3.5 py-2 text-sm font-black text-navy-900 shadow-sm transition active:translate-y-0.5 active:border-b-2 hover:border-[#002DFF] dark:border-navy-600 dark:bg-navy-800 dark:text-white"
                          >
                            {word}
                          </button>
                        ))}
                        {!sentenceWords.length ? (
                          <span className="text-xs font-bold text-slate-400">Pastdagi so'zlarni ketma-ket bosing</span>
                        ) : null}
                      </div>
                      <div className="flex flex-wrap gap-2 justify-center pt-2">
                        {bankWords.map((tile) => (
                          <button
                            key={tile.id}
                            type="button"
                            onClick={() => handleTileClick(tile.id, tile.text)}
                            disabled={tile.used || Boolean(result)}
                            className={`rounded-xl border-2 border-b-4 px-3.5 py-2 text-sm font-black transition ${
                              tile.used
                                ? "border-transparent bg-slate-100 text-transparent pointer-events-none dark:bg-navy-900/40"
                                : "border-slate-300 bg-white text-navy-900 shadow-md active:translate-y-0.5 active:border-b-2 hover:border-[#002DFF] dark:border-navy-600 dark:bg-navy-800 dark:text-white"
                            }`}
                          >
                            {tile.text}
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                } else if (currentQuestion.test_type === "true_false" || currentQuestion.test_type === "listening_tf") {
                  return (
                    <div className="grid grid-cols-2 gap-4 pt-2">
                      {["To'g'ri", "Noto'g'ri"].map((opt) => {
                        const isSelected = selected.toLowerCase() === opt.toLowerCase();
                        const isCorrectChoice = opt.toLowerCase() === String(currentQuestion.correct_answer || "").trim().toLowerCase();

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
                  );
                } else if (currentQuestion.test_type === "matching" || matchingPairs.length > 0) {
                  /* ─── Exercise Type 3: Matching / Pairs ─── */
                  return (
                    <div className="space-y-3 pt-2">
                      <p className="text-xs font-bold text-slate-500 dark:text-slate-400">
                        Har bir chapdagi so'zga mos o'ngdagi tarjima/javobni tanlang:
                      </p>
                      {matchingLefts.map((left, idx) => {
                        const currentVal = matchedPairs[left] || "";
                        const targetPair = matchingPairs.find((p) => p.left.trim().toLowerCase() === left.trim().toLowerCase());
                        const isPairCorrect = result && targetPair && (currentVal.trim().toLowerCase() === targetPair.right.trim().toLowerCase());
                        const isPairWrong = result && targetPair && currentVal && (currentVal.trim().toLowerCase() !== targetPair.right.trim().toLowerCase());

                        return (
                          <div
                            key={idx}
                            className={`flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 rounded-2xl border-2 p-3 transition-all ${
                              result
                                ? isPairCorrect
                                  ? "border-[#58cc02] bg-[#d7ffb8]/30 dark:bg-[#183617]/30"
                                  : isPairWrong
                                  ? "border-[#ff4b4b] bg-[#ffdfe0]/30 dark:bg-[#3d1a1b]/30"
                                  : "border-slate-200 bg-white dark:border-navy-700 dark:bg-navy-800"
                                : "border-slate-200 border-b-4 bg-white dark:border-navy-700 dark:bg-navy-800"
                            }`}
                          >
                            <span className="min-w-[120px] text-sm font-black text-navy-900 dark:text-white flex items-center gap-2">
                              <span className="grid h-6 w-6 place-items-center rounded-lg bg-slate-100 text-xs text-slate-600 dark:bg-navy-900 dark:text-navy-300">
                                {idx + 1}
                              </span>
                              <span>{left}</span>
                            </span>
                            <div className="flex items-center gap-2 flex-1">
                              <span className="hidden sm:inline font-black text-slate-300">→</span>
                              <select
                                value={currentVal}
                                disabled={Boolean(result)}
                                onChange={(e) => {
                                  playDuolingoSound("pop");
                                  const newPairs = { ...matchedPairs, [left]: e.target.value };
                                  setMatchedPairs(newPairs);
                                  setSelected(Object.entries(newPairs).map(([l, r]) => `${l} = ${r}`).join("; "));
                                }}
                                className="flex-1 rounded-xl border border-slate-200 bg-slate-50 p-2.5 text-xs font-black text-navy-900 focus:border-[#84d8ff] focus:outline-none dark:border-navy-600 dark:bg-navy-900 dark:text-white"
                              >
                                <option value="">Tanlang...</option>
                                {matchingRights.map((r, ri) => (
                                  <option key={ri} value={r}>
                                    {r}
                                  </option>
                                ))}
                              </select>
                              {result && isPairCorrect && <span className="text-lg text-emerald-600 font-black">✓</span>}
                              {result && isPairWrong && <span className="text-lg text-rose-600 font-black">✕</span>}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  );
                } else if (
                  currentQuestion.test_type === "write_sentence" ||
                  currentQuestion.test_type === "guided_writing" ||
                  currentQuestion.test_type === "open"
                ) {
                  /* ─── Exercise Type 4: Written Sentences / Guided Writing (Textarea + word count) ─── */
                  const wordCount = selected.trim().split(/\s+/).filter(Boolean).length;
                  const minWords = typeof currentQuestion.word_count === "number" ? currentQuestion.word_count : 0;

                  return (
                    <div className="space-y-3 pt-2">
                      <div className="flex flex-wrap gap-2 items-center">
                        {currentQuestion.direction ? (
                          <span className="rounded-xl border border-cyan-300 bg-cyan-50 px-2.5 py-1 text-xs font-black text-cyan-800 dark:border-cyan-800 dark:bg-cyan-950 dark:text-cyan-300">
                            🌐 {currentQuestion.direction}
                          </span>
                        ) : null}
                        {currentQuestion.hint ? (
                          <span className="rounded-xl border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-black text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
                            💡 Yordam: {currentQuestion.hint}
                          </span>
                        ) : null}
                        {isVoiceOrText && !voiceMode ? (
                          <button
                            type="button"
                            disabled={Boolean(result)}
                            onClick={() => setVoiceMode(true)}
                            className="inline-flex items-center gap-1.5 rounded-xl border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-black text-[#002DFF] transition hover:bg-blue-100 dark:border-blue-900 dark:bg-blue-950/50 dark:text-blue-300"
                          >
                            🎙️ Ovozli javob berish (mikrofon)
                          </button>
                        ) : null}
                      </div>

                      <textarea
                        value={selected}
                        onChange={(e) => setSelected(e.target.value)}
                        disabled={Boolean(result)}
                        rows={3}
                        placeholder="Javobingizni shu yerga yozing..."
                        autoFocus
                        className="w-full rounded-2xl border-2 border-b-4 border-slate-200 bg-white p-4 text-base font-semibold text-navy-900 focus:border-[#84d8ff] focus:outline-none dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                      />

                      <div className="flex items-center justify-between text-xs font-bold text-slate-400">
                        <span>Javobingizni to'liq yozing va pastdagi "Tekshirish" tugmasini bosing.</span>
                        {minWords > 0 ? (
                          <span className={wordCount >= minWords ? "text-emerald-600 font-black" : "text-amber-600 font-bold"}>
                            {wordCount} / {minWords} so'z {wordCount >= minWords ? "✓" : ""}
                          </span>
                        ) : null}
                      </div>

                      {result && (currentQuestion.sample_answer || currentQuestion.reference_answer) ? (
                        <div className="rounded-2xl border border-emerald-300 bg-emerald-50 p-3 text-xs font-semibold text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
                          <p className="font-black mb-1">📝 Namunaviy javob:</p>
                          <p>{String(currentQuestion.sample_answer || currentQuestion.reference_answer)}</p>
                        </div>
                      ) : null}
                    </div>
                  );
                } else if (!currentQuestion.options || !Array.isArray(currentQuestion.options) || currentQuestion.options.length < 2 || ((currentQuestion.test_type === "fill_blank" || currentQuestion.test_type === "gap_fill") && !hasCorrectChoice)) {
                  /* ─── Exercise Type 5: Fill Blank, Dictation, Open, Translation, Spelling (Text Input) ─── */
                  const wordCount = selected.trim().split(/\s+/).filter(Boolean).length;
                  const minWords = typeof currentQuestion.word_count === "number" ? currentQuestion.word_count : 0;

                  return (
                    <div className="space-y-3 pt-2">
                      <div className="flex flex-wrap gap-2 items-center">
                        {currentQuestion.direction ? (
                          <span className="rounded-xl border border-cyan-300 bg-cyan-50 px-2.5 py-1 text-xs font-black text-cyan-800 dark:border-cyan-800 dark:bg-cyan-950 dark:text-cyan-300">
                            🌐 {currentQuestion.direction}
                          </span>
                        ) : null}
                        {currentQuestion.hint ? (
                          <span className="rounded-xl border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-black text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
                            💡 Yordam: {currentQuestion.hint}
                          </span>
                        ) : null}
                        {currentQuestion.example_sentence ? (
                          <span className="rounded-xl border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs font-bold text-indigo-700 dark:border-indigo-800 dark:bg-indigo-950 dark:text-indigo-300">
                            📝 Misol: {currentQuestion.example_sentence}
                          </span>
                        ) : null}
                        {isVoiceOrText && !voiceMode ? (
                          <button
                            type="button"
                            disabled={Boolean(result)}
                            onClick={() => setVoiceMode(true)}
                            className="inline-flex items-center gap-1.5 rounded-xl border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-black text-[#002DFF] transition hover:bg-blue-100 dark:border-blue-900 dark:bg-blue-950/50 dark:text-blue-300"
                          >
                            🎙️ Ovozli javob berish (mikrofon)
                          </button>
                        ) : null}
                      </div>

                      <input
                        type="text"
                        value={selected}
                        onChange={(e) => setSelected(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && !result && void checkAnswer()}
                        disabled={Boolean(result)}
                        placeholder="Javobingizni yozing..."
                        autoFocus
                        className="w-full rounded-2xl border-2 border-b-4 border-slate-200 bg-white p-4 text-lg font-black text-navy-900 focus:border-[#84d8ff] focus:outline-none dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                      />

                      <div className="flex items-center justify-between text-xs font-bold text-slate-400">
                        <span>Javobni yozing va pastdagi "Tekshirish" tugmasini bosing.</span>
                        {minWords > 0 ? (
                          <span className={wordCount >= minWords ? "text-emerald-600 font-black" : "text-amber-600 font-bold"}>
                            {wordCount} / {minWords} so'z {wordCount >= minWords ? "✓" : ""}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  );
                } else {
                  return (
                    <div className="space-y-2.5">
                      {(Array.isArray(currentQuestion.options) ? currentQuestion.options : []).map((opt: string, i: number) => {
                        const isSelected = selected === opt;
                        const isCorrectChoice = result && isAnswerCorrect(opt, currentQuestion);
                        const isWrongChoice = result && isSelected && !result.correct;

                        return (
                          <button
                            key={i}
                            type="button"
                            onClick={() => {
                              if (result) return;
                              playDuolingoSound("pop");
                              setSelected(opt);
                            }}
                            disabled={Boolean(result)}
                            className={`flex w-full items-center justify-between rounded-2xl border-2 border-b-4 p-4 text-left text-sm font-black transition-all ${
                              isCorrectChoice
                                ? "border-[#58cc02] bg-[#d7ffb8] text-[#2e6b00] dark:bg-[#152e14] dark:text-[#a0ff6d]"
                                : isWrongChoice
                                ? "border-[#ff4b4b] bg-[#ffdfe0] text-[#a01818] dark:bg-[#381517] dark:text-[#ffa0a0]"
                                : isSelected
                                ? "border-[#001A88] bg-blue-50/80 text-[#001A88] ring-2 ring-[#002DFF]/40 dark:bg-navy-800 dark:text-blue-300"
                                : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50 dark:border-navy-700 dark:bg-navy-800/80 dark:text-navy-100"
                            }`}
                          >
                            <span className="flex items-center gap-3">
                              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-xl border border-slate-200 bg-slate-50 text-xs font-black text-slate-500 dark:border-navy-700 dark:bg-navy-700 dark:text-navy-300">
                                {i + 1}
                              </span>
                              <span>{opt}</span>
                            </span>
                            {result && isCorrectChoice ? <span className="text-xl">✓</span> : null}
                          </button>
                        );
                      })}
                    </div>
                  );
                }
              })()}
            </div>
          ) : null}
        </div>

        {/* Bottom Action Drawer */}
        {!finished && currentQuestion ? (
          <div
            className={`border-t-2 p-4 transition-all duration-300 ${
              result?.correct
                ? "border-[#b8f28b] bg-[#d7ffb8] dark:border-[#2b5928] dark:bg-[#152e14]"
                : result && !result.correct
                ? "border-[#fba4a6] bg-[#ffdfe0] dark:border-[#6b2528] dark:bg-[#381517]"
                : "border-slate-100 bg-white dark:border-white/10 dark:bg-[#131f24]"
            }`}
          >
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
                    {result.correct
                      ? (result.ai_feedback || "Ajoyib! Juda to'g'ri!")
                      : "Javobingizda xatolik mavjud:"}
                  </p>
                  {result.ai_transcript ? (
                    <div className="mt-1.5 rounded-xl bg-blue-50/80 px-3 py-2 text-xs font-semibold text-blue-950 dark:bg-blue-950/40 dark:text-blue-200 border border-blue-200 dark:border-blue-900">
                      <span className="font-bold">🎙️ Siz aytdingiz:</span> “{result.ai_transcript}”
                    </div>
                  ) : null}
                  {!result.correct && (result.ai_feedback || result.correct_answer) ? (
                    <div className="mt-1 space-y-1">
                      {result.ai_feedback && result.ai_feedback !== result.correct_answer ? (
                        <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">
                          💬 {result.ai_feedback}
                        </p>
                      ) : null}
                      {result.correct_answer ? (
                        <p className="text-xs font-bold text-slate-900 dark:text-white">
                          <span className="text-slate-500 dark:text-slate-400">To'g'ri / Namunaviy variant: </span>
                          {String(result.correct_answer)}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                  {Array.isArray(result.pronunciation_errors) && result.pronunciation_errors.length > 0 ? (
                    <div className="mt-2 space-y-1">
                      <p className="text-xs font-black text-amber-700 dark:text-amber-300">🗣️ Talaffuz bo'yicha maslahatlar:</p>
                      {result.pronunciation_errors.map((pe: any, pei: number) => (
                        <div key={pei} className="rounded-lg bg-amber-50 p-2 text-xs text-amber-900 dark:bg-amber-950/40 dark:text-amber-200 border border-amber-200 dark:border-amber-800">
                          <span className="font-bold">{pe.word}:</span> {pe.note || pe.tip || pe.explanation}
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {Array.isArray(result.grammar_errors) && result.grammar_errors.length > 0 ? (
                    <div className="mt-2 space-y-1">
                      {result.grammar_errors.map((ge: any, gei: number) => (
                        <div key={gei} className="rounded-lg bg-red-100/70 p-2 text-xs text-red-900 dark:bg-red-950/40 dark:text-red-200">
                          <span className="font-bold line-through mr-1">{ge.original}</span>
                          <span>→ </span>
                          <span className="font-bold text-emerald-700 dark:text-emerald-300">{ge.correction}</span>
                          {ge.explanation ? <p className="mt-0.5 text-[11px] text-slate-600 dark:text-slate-400">{ge.explanation}</p> : null}
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {currentQuestion.explanation && !result.ai_feedback ? (
                    <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                      💡 {currentQuestion.explanation}
                    </p>
                  ) : null}
                </div>
              </div>
            ) : null}

            {!result ? (
              (() => {
                const canSubmit = isExamCloze
                  ? clozeBlanks.length > 0 && clozeBlanks.every((x) => x && x.trim())
                  : currentQuestion.test_type === "matching" || matchingPairs.length > 0
                  ? matchingPairs.length > 0 && Object.keys(matchedPairs).length >= matchingPairs.length
                  : currentQuestion.test_type === "word_order" || currentQuestion.test_type === "listening_order" || currentQuestion.test_type === "scrambled_sentence"
                  ? sentenceWords.length > 0
                  : Boolean(selected.trim());

                return (
                  <button
                    type="button"
                    onClick={() => void checkAnswer()}
                    disabled={!canSubmit || loading || submitting}
                    className={`w-full rounded-2xl border-2 border-b-4 py-3.5 text-center text-sm font-black uppercase tracking-wider transition-all ${
                      canSubmit && !loading && !submitting
                        ? "border-[#001A88] bg-[#002DFF] hover:bg-[#1429f2] text-white shadow-xl shadow-blue-600/30 active:translate-y-1 active:border-b-2 cursor-pointer"
                        : "border-slate-200 bg-slate-200 text-slate-400 cursor-not-allowed dark:border-navy-800 dark:bg-navy-900"
                    }`}
                  >
                    {loading ? "Yuklanmoqda..." : "Tekshirish"}
                  </button>
                );
              })()
            ) : (
              <button
                type="button"
                onClick={handleNext}
                disabled={submitting}
                className={`w-full rounded-2xl border-2 border-b-4 py-3.5 text-center text-sm font-black uppercase tracking-wider text-white shadow-lg active:translate-y-1 active:border-b-2 ${
                  result.correct
                    ? "border-[#001A88] bg-[#002DFF] hover:bg-[#1429f2]"
                    : "border-[#d62828] bg-[#ff4b4b] hover:bg-[#ff3333]"
                }`}
              >
                {submitting
                  ? "Natija hisoblanmoqda..."
                  : currentIndex + 1 < questions.length
                  ? "Keyingi savol →"
                  : "Natijani ko'rish"}
              </button>
            )}
          </div>
        ) : null}
      </div>
    </div>,
    document.body
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   STAFF VIEW — Track/Module/Lesson management
   ═══════════════════════════════════════════════════════════════════════════════ */

export function StaffLearningPaths({ apiFetch }: { apiFetch: ApiFetch }) {
  const t = useWebT();
  const [tracks, setTracks] = useState<Row[]>([]);
  const [selected, setSelected] = useState<Row | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [title, setTitle] = useState("");
  const [trackSubject, setTrackSubject] = useState("Ingliz tili");
  const [moduleTitle, setModuleTitle] = useState("");
  const [topics, setTopics] = useState("");
  const [rewardCoins, setRewardCoins] = useState<string>("");
  const [cover, setCover] = useState("star");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [moduleFormError, setModuleFormError] = useState("");
  const [showCreateTrackModal, setShowCreateTrackModal] = useState(false);
  const [showAddModuleInline, setShowAddModuleInline] = useState(false);
  const [showCertModal, setShowCertModal] = useState(false);
  const [selectedModuleId, setSelectedModuleId] = useState<number | null>(null);
  const [openAddTestOnModuleOpen, setOpenAddTestOnModuleOpen] = useState(false);
  const [editModuleId, setEditModuleId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editTopics, setEditTopics] = useState("");
  const [editRewardCoins, setEditRewardCoins] = useState(0);
  const [editCover, setEditCover] = useState("star");

  const selectedModule = useMemo(() => {
    if (!selected || !selectedModuleId) return null;
    return (selected.modules || []).find((m: Row) => m.id === selectedModuleId) || null;
  }, [selected, selectedModuleId]);

  // Determine previous module's cover key to forbid consecutive duplicates
  const lastModuleCover = useMemo(() => {
    const mods = selected?.modules;
    if (Array.isArray(mods) && mods.length > 0) {
      return String(mods[mods.length - 1]?.cover_key || "star");
    }
    return null;
  }, [selected]);

  useEffect(() => {
    if (lastModuleCover && cover === lastModuleCover) {
      const allowed = covers.find((c) => c !== lastModuleCover) || "trophy";
      setCover(allowed);
    }
  }, [lastModuleCover]);

  const load = async () => {
    try {
      const data = await apiFetch("/staff/learning-tracks");
      const items = Array.isArray(data?.items) ? data.items : [];
      setTracks(items);
      setSelected((curr) => (curr ? items.find((x: Row) => x.id === curr.id) || null : null));
    } catch (e) {
      setError(errorText(e, "Tracklar yuklanmadi."));
    }
  };

  useEffect(() => {
    void load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const filteredTracks = useMemo(() => {
    if (!searchQuery.trim()) return tracks;
    const q = searchQuery.toLowerCase().trim();
    return tracks.filter(
      (t) =>
        String(t.title || "").toLowerCase().includes(q) ||
        String(t.subject || "").toLowerCase().includes(q)
    );
  }, [tracks, searchQuery]);

  const totalModulesCount = useMemo(() => {
    return tracks.reduce((acc, tr) => acc + (Array.isArray(tr.modules) ? tr.modules.length : 0), 0);
  }, [tracks]);

  const create = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    setError("");
    try {
      await apiFetch("/staff/learning-tracks", {
        method: "POST",
        body: { title: title.trim(), subject: trackSubject.trim() || undefined, passing_score: 70 },
      });
      setTitle("");
      setShowCreateTrackModal(false);
      await load();
    } catch (e) {
      setError(errorText(e, "Track yaratilmadi."));
    } finally {
      setBusy(false);
    }
  };

  const addModule = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    if (!moduleTitle.trim()) {
      setModuleFormError("Modul nomini kiritish majburiy.");
      return;
    }
    if (!topics.trim()) {
      setModuleFormError("Mavzularni kiritish majburiy.");
      return;
    }
    const coinsNum = parseInt(String(rewardCoins).trim(), 10);
    if (!rewardCoins || isNaN(coinsNum) || coinsNum <= 0) {
      setModuleFormError("D'Point & D'Coin mukofotini kiritish majburiy (musbat son kiriting).");
      return;
    }
    if (lastModuleCover && cover === lastModuleCover) {
      setModuleFormError("Ketma-ket ikkita modulga bir xil rasm tanlab bo'lmaydi. Boshqa rasm tanlang.");
      return;
    }
    setBusy(true);
    setModuleFormError("");
    setError("");
    try {
      await apiFetch(`/staff/learning-tracks/${selected.id}/modules`, {
        method: "POST",
        body: {
          title: moduleTitle.trim(),
          cover_key: cover,
          position: (selected.modules || []).length,
          topic_keys: topics.split(",").map((value) => value.trim()).filter(Boolean),
          reward_coins: coinsNum,
        },
      });
      setModuleTitle("");
      setTopics("");
      setRewardCoins("");
      const nextCover = covers.find((c) => c !== cover) || "trophy";
      setCover(nextCover);
      setShowAddModuleInline(false);
      await load();
    } catch (e) {
      const msg = errorText(e, "Modul qo'shilmadi.");
      setModuleFormError(msg);
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const deleteTrack = async (trackId?: number) => {
    const tr = trackId ? tracks.find((x) => x.id === trackId) : selected;
    if (!tr) return;
    if (!window.confirm(`"${tr.title}" track va barcha unga tegishli modullar o'chirilsinmi?`)) return;
    setBusy(true);
    try {
      await apiFetch(`/staff/learning-tracks/${tr.id}`, { method: "DELETE" });
      if (selected?.id === tr.id) setSelected(null);
      await load();
    } catch (e) {
      setError(errorText(e, "Track o'chirilmadi."));
    } finally {
      setBusy(false);
    }
  };

  const deleteModule = async (moduleId: number) => {
    if (!window.confirm("Modul va uning barcha savollari o'chirilsinmi?")) return;
    setBusy(true);
    try {
      await apiFetch(`/staff/learning-modules/${moduleId}`, { method: "DELETE" });
      await load();
    } catch (e) {
      setError(errorText(e, "Modul o'chirilmadi."));
    } finally {
      setBusy(false);
    }
  };

  const updateModule = async (moduleId: number, prevCover?: string | null, nextCover?: string | null) => {
    if (prevCover && editCover === prevCover) {
      setError("Oldingi modul bilan bir xil rasm tanlab bo'lmaydi.");
      return;
    }
    if (nextCover && editCover === nextCover) {
      setError("Keyingi modul bilan bir xil rasm tanlab bo'lmaydi.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await apiFetch(`/staff/learning-modules/${moduleId}`, {
        method: "PATCH",
        body: {
          title: editTitle.trim(),
          topic_keys: editTopics.split(",").map((v) => v.trim()).filter(Boolean),
          reward_coins: editRewardCoins,
          cover_key: editCover,
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
    <section className="mx-auto w-full max-w-6xl p-4 sm:p-6 space-y-6">
      {/* Header Bar */}
      <header className="premium-card p-5 sm:p-7">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-black uppercase tracking-[.18em] text-cyan-600 dark:text-cyan-300">
              Diamond Learning Path
            </p>
            <h1 className="mt-1.5 text-2xl sm:text-3xl font-black text-navy-900 dark:text-white">
              {t("learning.staff.title", "Learning Path boshqaruvi")}
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-ink-600 dark:text-navy-300">
              Mavjud tracklar jadvali: har bir trackni tanlab, uning modullari, sertifikati va savollarini popup oynada to'liq boshqaring.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setShowCreateTrackModal(true)}
              className="inline-flex items-center gap-2 rounded-2xl border-2 border-b-4 border-cyan-600 bg-cyan-600 px-5 py-3 text-xs font-black uppercase tracking-wider text-white shadow-md transition-all active:translate-y-0.5 active:border-b-2 hover:bg-cyan-700"
            >
              <span>➕ Yangi Track Yaratish</span>
            </button>
          </div>
        </div>
      </header>

      {error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/15 p-4 text-xs font-bold text-rose-700 dark:text-rose-200">
          ⚠️ {error}
        </div>
      ) : null}

      {/* Main Tracks Table Card */}
      <div className="premium-card overflow-hidden">
        {/* Table Search & Filter Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line p-4 sm:p-5 dark:border-slate-800 bg-surface-soft/40 dark:bg-slate-800/40">
          <div className="flex items-center gap-2">
            <span className="text-sm font-black text-navy-900 dark:text-white">
              {t("learning_paths.teacher.available_tracks", "Mavjud O'quv Yo'llari (Tracklar)")}
            </span>
            <span className="rounded-full bg-cyan-500/15 px-2.5 py-0.5 text-xs font-bold text-cyan-700 dark:text-cyan-300">
              {tracks.length} {t("learning_paths.tracks_count", "{count} ta track").replace("{count}", String(tracks.length))} · {totalModulesCount} {t("learning_paths.modules_count", "{count} ta modul").replace("{count}", String(totalModulesCount))}
            </span>
          </div>

          <div className="w-full sm:w-72">
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t("learning_paths.teacher.search_placeholder", "Track yoki fan nomi bo'yicha qidirish...")}
              className="w-full rounded-xl border border-line bg-white px-3.5 py-2 text-xs font-medium text-navy-900 placeholder:text-ink-400 focus:border-cyan-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder-slate-400"
            />
          </div>
        </div>

        {/* Tracks Table */}
        {filteredTracks.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-line dark:border-slate-800 bg-surface-soft/60 dark:bg-[#090d16]/80 text-[11px] font-black uppercase tracking-wider text-ink-500 dark:text-slate-400">
                  <th className="py-3.5 px-4 text-center w-12">#</th>
                  <th className="py-3.5 px-4">{t("learning_paths.teacher.col_track", "Track Nomi")}</th>
                  <th className="py-3.5 px-4">{t("learning_paths.teacher.col_subject", "Fan")}</th>
                  <th className="py-3.5 px-4 text-center">{t("learning_paths.teacher.col_modules", "Modullar")}</th>
                  <th className="py-3.5 px-4 text-center">{t("learning_paths.teacher.col_passing_score", "O'tish Bali")}</th>
                  <th className="py-3.5 px-4 text-center">{t("learning_paths.teacher.col_status", "Holati")}</th>
                  <th className="py-3.5 px-4 text-right">{t("learning_paths.teacher.col_actions", "Amallar")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line dark:divide-slate-800">
                {filteredTracks.map((track, idx) => {
                  const mods = Array.isArray(track.modules) ? track.modules : [];
                  return (
                    <tr
                      key={track.id}
                      onClick={() => setSelected(track)}
                      className="group cursor-pointer hover:bg-cyan-500/5 dark:hover:bg-slate-800/50 transition"
                    >
                      <td className="py-4 px-4 text-center font-mono font-black text-xs text-ink-500 dark:text-slate-400">
                        {idx + 1}
                      </td>

                      <td className="py-4 px-4 min-w-[220px]">
                        <div className="flex items-center gap-3">
                          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-cyan-500/15 text-lg font-black text-cyan-700 dark:text-cyan-300">
                            🎓
                          </span>
                          <div>
                            <p className="font-black text-sm text-navy-900 dark:text-white group-hover:text-cyan-600 dark:group-hover:text-cyan-400 transition">
                              {track.title}
                            </p>
                            <p className="text-[11px] text-ink-400 dark:text-slate-400 mt-0.5">
                              ID: #{track.id} · Duolingo Snake Path
                            </p>
                          </div>
                        </div>
                      </td>

                      <td className="py-4 px-4 whitespace-nowrap">
                        <span className="inline-flex items-center gap-1 rounded-xl bg-slate-100 dark:bg-slate-800 px-3 py-1 text-xs font-bold text-slate-800 dark:text-slate-200 border border-slate-200/60 dark:border-slate-700">
                          <span>📖</span>
                          <span>{track.subject || "General"}</span>
                        </span>
                      </td>

                      <td className="py-4 px-4 text-center whitespace-nowrap">
                        <span className="inline-flex items-center gap-1 rounded-xl bg-cyan-500/10 dark:bg-cyan-500/20 px-2.5 py-1 text-xs font-bold text-cyan-700 dark:text-cyan-300">
                          <span>📦</span>
                          <span>{mods.length} {t("learning_paths.modules_count", "{count} ta modul").replace("{count}", String(mods.length))}</span>
                        </span>
                      </td>

                      <td className="py-4 px-4 text-center whitespace-nowrap">
                        <span className="inline-flex items-center gap-1 rounded-xl bg-emerald-500/10 px-2.5 py-1 text-xs font-bold text-emerald-700 dark:text-emerald-300">
                          <span>🎯</span>
                          <span>{track.passing_score || 70}%</span>
                        </span>
                      </td>

                      <td className="py-4 px-4 text-center whitespace-nowrap">
                        <span className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-600 dark:text-emerald-400">
                          <span className="h-2 w-2 rounded-full bg-emerald-500" />
                          <span>{t("learning_paths.teacher.status_active", "Faol")}</span>
                        </span>
                      </td>

                      <td className="py-4 px-4 text-right whitespace-nowrap">
                        <div
                          className="flex items-center justify-end gap-2"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            type="button"
                            onClick={() => setSelected(track)}
                            className="inline-flex items-center gap-1.5 rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-1.5 text-xs font-bold text-cyan-700 hover:bg-cyan-500/20 dark:text-cyan-300 transition"
                          >
                            <span>⚙️</span>
                            <span>{t("learning_paths.teacher.action_manage", "Boshqarish")}</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => void deleteTrack(track.id)}
                            className="grid h-8 w-8 place-items-center rounded-xl text-ink-400 hover:bg-rose-500/15 hover:text-rose-600 transition"
                            title={t("learning_paths.teacher.delete_track", "Trackni o'chirish")}
                          >
                            🗑
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-16 text-center">
            <div className="mx-auto mb-3 grid h-16 w-16 place-items-center rounded-3xl bg-cyan-500/10 text-3xl">
              📚
            </div>
            <h3 className="font-black text-lg text-navy-900 dark:text-white">
              {searchQuery ? "Hech qanday track topilmadi" : "Hali birorta ham track yaratilmagan"}
            </h3>
            <p className="mt-1 text-xs text-ink-500 dark:text-navy-300 max-w-sm mx-auto">
              {searchQuery
                ? "Qidiruv so'zini o'zgartirib ko'ring yoki filtrni tozalang."
                : "Talabalaringiz uchun birinchi Duolingo uslubidagi o'quv yo'lini yarating."}
            </p>
            {!searchQuery ? (
              <button
                type="button"
                onClick={() => setShowCreateTrackModal(true)}
                className="mt-4 inline-flex items-center gap-2 rounded-2xl border-2 border-b-4 border-cyan-600 bg-cyan-600 px-5 py-2.5 text-xs font-black uppercase tracking-wider text-white shadow hover:bg-cyan-700"
              >
                <span>➕ Yangi Track Yaratish</span>
              </button>
            ) : null}
          </div>
        )}
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════════
          COMPREHENSIVE POPUP MODAL: Track Details, Modules & Questions Management
          ═══════════════════════════════════════════════════════════════════════════ */}
      {selected && typeof document !== "undefined" && createPortal(
        <div
          className="fixed inset-0 z-[200] flex items-center justify-center bg-black/75 p-3 sm:p-6 backdrop-blur-sm overflow-hidden animate-fade-in"
          onClick={() => setSelected(null)}
        >
          <div
            className="relative w-full max-w-5xl max-h-[92vh] flex flex-col rounded-3xl bg-white shadow-2xl dark:bg-[#0f172a] border border-line dark:border-slate-800 overflow-hidden animate-scale-up"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-6 py-4 dark:border-slate-800 bg-surface-soft/60 dark:bg-[#090d16]/80">
              <div className="flex items-center gap-3 min-w-0">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-cyan-500/15 text-2xl font-black text-cyan-700 dark:text-cyan-300">
                  🎓
                </span>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="font-black text-navy-900 dark:text-white text-lg sm:text-xl truncate">
                      {selected.title}
                    </h2>
                    <span className="rounded-xl bg-cyan-500/15 px-2.5 py-0.5 text-xs font-black text-cyan-700 dark:text-cyan-300">
                      {selected.subject || "General"}
                    </span>
                    <span className="rounded-xl bg-emerald-500/15 px-2.5 py-0.5 text-xs font-black text-emerald-700 dark:text-emerald-300">
                      {selected.passing_score || 70}% {t("learning_paths.passing_score", "o'tish").replace("🎯 O‘tish bali: ", "")}
                    </span>
                  </div>
                  <p className="text-xs text-ink-500 dark:text-slate-400 mt-0.5">
                    ID: #{selected.id} · Barcha modullar, test savollari va sertifikat sozlamalari
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2.5">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void deleteTrack(selected.id)}
                  className="rounded-xl border border-rose-400/40 px-3 py-1.5 text-xs font-bold text-rose-600 hover:bg-rose-500/10 dark:text-rose-300 transition"
                >
                  🗑 {t("learning_paths.teacher.delete_track", "Trackni o'chirish")}
                </button>
                <button
                  type="button"
                  onClick={() => setSelected(null)}
                  className="grid h-9 w-9 place-items-center rounded-full text-ink-500 hover:bg-rose-500/10 hover:text-rose-600 transition text-base font-bold dark:text-slate-400 dark:hover:text-white"
                  title={t("common.close", "Yopish")}
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Modal Body (Scrollable) */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 custom-scrollbar">
              {error ? (
                <div className="rounded-2xl border border-rose-500/30 bg-rose-500/15 p-4 text-xs font-bold text-rose-700 dark:text-rose-200 flex items-center justify-between gap-3">
                  <span>⚠️ {error}</span>
                  <button type="button" onClick={() => setError("")} className="text-xs font-black text-rose-700 dark:text-rose-200 hover:opacity-75">✕</button>
                </div>
              ) : null}

              {/* Certificate & Passing Score Card */}
              <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-cyan-500/30 bg-gradient-to-r from-cyan-500/10 via-indigo-500/10 to-purple-500/10 dark:from-cyan-950/30 dark:via-indigo-950/30 dark:to-purple-950/30 p-5 shadow-sm">
                <div className="flex items-center gap-3.5 min-w-0">
                  <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-cyan-500/20 text-2xl shadow-inner">
                    🎓
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-black text-navy-900 dark:text-white text-base">
                        {t("learning_paths.teacher.cert_popup_title", "Bitiruv Sertifikati Sozlamalari")}
                      </h3>
                      {(() => {
                        const isRussian = (selected.subject || "").toLowerCase().includes("rus") || (selected.subject || "").toLowerCase().includes("рус");
                        return (
                          <span className="rounded-lg bg-cyan-500/20 px-2 py-0.5 text-xs font-bold text-cyan-800 dark:text-cyan-200">
                            {isRussian ? "🇷🇺 Rus tili shabloni (russian.svg)" : "🇬🇧 Ingliz tili shabloni (english.svg)"}
                          </span>
                        );
                      })()}
                      <span className="rounded-lg bg-emerald-500/20 px-2 py-0.5 text-xs font-bold text-emerald-800 dark:text-emerald-200">
                        {selected.passing_score || 70}% o'tish bali
                      </span>
                    </div>
                    <p className="text-xs text-ink-500 dark:text-slate-400 mt-1">
                      {t("learning_paths.teacher.cert_hint", "Sertifikat matni, shrift, rang va shablonni alohida popup oynada vizual tahrirlang.")}
                    </p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => setShowCertModal(true)}
                  className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 px-4 py-2.5 text-xs font-black uppercase tracking-wider text-white shadow-md hover:from-cyan-700 hover:to-indigo-700 active:scale-[0.98] transition"
                >
                  <span>{t("learning_paths.teacher.cert_btn", "🎓 Sertifikatni Sozlash (Popup)")}</span>
                </button>
              </div>

              {/* Modules Management Section */}
              <div className="rounded-2xl border border-line p-5 dark:border-slate-800 bg-white dark:bg-[#090d16]/50 shadow-xs">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4 dark:border-slate-800">
                  <div>
                    <h3 className="text-base font-black text-navy-900 dark:text-white flex items-center gap-2">
                      <span>📦 {t("learning_paths.teacher.modules_list", "Modullar Ro'yxati")}</span>
                    </h3>
                    <p className="text-xs text-ink-500 dark:text-slate-400 mt-0.5">
                      Jami {(selected.modules || []).length} ta bosqich. Har bir modulni alohida popup oynada to'liq sozlang va testlarini boshqaring.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setShowAddModuleInline(!showAddModuleInline);
                      setModuleFormError("");
                    }}
                    className="inline-flex items-center gap-2 rounded-xl border-2 border-b-4 border-[#1899d6] bg-[#1cb0f6] px-4 py-2 text-xs font-black uppercase tracking-wider text-white shadow transition hover:bg-[#1899d6] active:translate-y-0.5 active:border-b-2"
                  >
                    <span>{showAddModuleInline ? "✕ Formani yopish" : `➕ ${t("learning_paths.teacher.new_module", "Yangi Modul Qo'shish")}`}</span>
                  </button>
                </div>

                {/* Inline Add Module Form inside Modal */}
                {showAddModuleInline ? (
                  <form
                    onSubmit={addModule}
                    className="mt-4 rounded-2xl border border-cyan-500/30 bg-cyan-500/5 dark:bg-cyan-950/20 p-4 sm:p-5 space-y-4 animate-fade-in"
                  >
                    {moduleFormError ? (
                      <div className="rounded-xl border border-rose-500/40 bg-rose-500/15 p-3 text-xs font-bold text-rose-700 dark:text-rose-200 flex items-center justify-between gap-2">
                        <span className="flex items-center gap-2">
                          <span>⚠️</span>
                          <span>{moduleFormError}</span>
                        </span>
                        <button type="button" onClick={() => setModuleFormError("")} className="hover:opacity-70 font-black">✕</button>
                      </div>
                    ) : null}

                    <div>
                      <h4 className="font-black text-sm text-navy-900 dark:text-white">
                        + "{selected.title}" ga yangi modul qo'shish
                      </h4>
                      <p className="text-xs text-ink-500 dark:text-slate-400 mt-0.5">
                        Modul nomi va unga tegishli mavzularni kiriting.
                      </p>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-xs font-bold text-ink-600 dark:text-slate-300">
                          {t("learning_paths.teacher.module_title", "Modul nomi")}
                        </label>
                        <input
                          value={moduleTitle}
                          onChange={(e) => {
                            setModuleTitle(e.target.value);
                            setModuleFormError("");
                          }}
                          className="w-full rounded-xl border border-line bg-white p-2.5 text-xs font-bold text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder-slate-400"
                          placeholder="Masalan: 1-bosqich: Basic Grammar"
                          required
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs font-bold text-ink-600 dark:text-slate-300">
                          {t("learning_paths.teacher.topics", "Mavzular")} (vergul bilan, maksimal 5 ta) *
                        </label>
                        <input
                          value={topics}
                          onChange={(e) => {
                            setTopics(e.target.value);
                            setModuleFormError("");
                          }}
                          className="w-full rounded-xl border border-line bg-white p-2.5 text-xs dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder-slate-400"
                          placeholder="Present Simple, To be, Fe'llar (maksimal 5 ta)"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="text-xs font-bold text-ink-600 dark:text-slate-300 block mb-1">
                        {t("learning_paths.teacher.reward_coins", "Topshirilsa beriladigan D'Point (+ D'Coin)")} *
                      </label>
                      <input
                        value={rewardCoins}
                        type="number"
                        min="1"
                        max="10000"
                        required
                        onChange={(e) => {
                          setRewardCoins(e.target.value);
                          setModuleFormError("");
                        }}
                        className="w-full sm:w-48 rounded-xl border border-line bg-white p-2.5 text-xs font-bold text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                        placeholder="Masalan: 50"
                      />
                    </div>

                    <div className="border-t border-line/40 pt-3 dark:border-slate-800">
                      <p className="text-xs font-bold text-ink-500 dark:text-slate-400 mb-2">Modul belgisi (ikonka):</p>
                      <CoverPicker value={cover} onChange={setCover} forbiddenKey={lastModuleCover} />
                    </div>

                    <div className="flex justify-end gap-2.5 pt-2 border-t border-line/40 dark:border-slate-800">
                      <button
                        type="button"
                        onClick={() => setShowAddModuleInline(false)}
                        className="rounded-xl border border-line px-4 py-2 text-xs font-bold text-ink-500 hover:bg-surface-soft dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                      >
                        {t("common.cancel", "Bekor qilish")}
                      </button>
                      <button
                        type="submit"
                        disabled={busy || !moduleTitle.trim()}
                        className="rounded-xl border-2 border-b-4 border-[#1899d6] bg-[#1cb0f6] px-5 py-2 text-xs font-black uppercase text-white shadow hover:bg-[#1899d6] disabled:opacity-40"
                      >
                        {busy ? "Qo'shilmoqda..." : "+ Modul yaratish"}
                      </button>
                    </div>
                  </form>
                ) : null}

                {/* Modules List Cards (Opens each module in dedicated popup) */}
                <div className="mt-5 space-y-3">
                  {(selected.modules || []).map((module: Row, index: number) => {
                    const lessonsCount = (module.lessons || []).length;
                    return (
                      <div
                        key={module.id}
                        className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-line p-4 dark:border-slate-800 transition hover:shadow-md bg-surface-soft/30 dark:bg-slate-800/40"
                      >
                        <div className="flex items-center gap-3.5 min-w-0">
                          <img
                            src={module.image_url || image(module.cover_key)}
                            alt=""
                            className="h-12 w-12 rounded-full object-cover border-2 border-[#002DFF] shadow-sm shrink-0"
                          />
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="grid h-6 w-6 place-items-center rounded-lg bg-navy-100 dark:bg-slate-800 text-xs font-black text-navy-900 dark:text-white">
                                {index + 1}
                              </span>
                              <p className="font-black text-navy-900 dark:text-white text-base truncate">
                                {module.title}
                              </p>
                            </div>
                            <div className="flex items-center gap-2 flex-wrap mt-1 text-xs text-ink-500 dark:text-slate-400">
                              <span>{(module.topic_keys || []).join(" · ") || "Mavzu kiritilmagan"}</span>
                              <span>•</span>
                              <span className="font-bold text-cyan-700 dark:text-cyan-300">
                                🎯 {lessonsCount} ta savol
                              </span>
                              {module.reward_coins > 0 ? (
                                <>
                                  <span>•</span>
                                  <span className="font-bold text-amber-600 dark:text-amber-400">
                                    💎 +{module.reward_coins} D'Point
                                  </span>
                                </>
                              ) : null}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedModuleId(module.id);
                              setOpenAddTestOnModuleOpen(true);
                            }}
                            className="inline-flex items-center gap-1.5 rounded-xl border border-cyan-500/40 bg-cyan-500/10 hover:bg-[#1cb0f6] hover:border-[#1cb0f6] text-cyan-700 dark:text-cyan-300 hover:text-white dark:hover:text-white font-black text-xs px-3 py-2 shadow-xs transition"
                            title="Ushbu modulga yangi savol qo'shish oynasini ochish"
                          >
                            <span>➕ {t("learning_paths.teacher.add_test_btn", "Savol qo'shish")}</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedModuleId(module.id);
                              setOpenAddTestOnModuleOpen(false);
                            }}
                            className="inline-flex items-center gap-2 rounded-xl bg-[#002DFF] hover:bg-blue-700 text-white font-black text-xs px-3.5 py-2 shadow-sm transition"
                          >
                            <span>⚙️ {t("learning_paths.teacher.edit_module", "Modulni Sozlash & Testlar")}</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => void deleteModule(module.id)}
                            className="grid h-8 w-8 place-items-center rounded-xl text-rose-500 hover:bg-rose-500/15 transition"
                            title="Modulni o'chirish"
                          >
                            🗑
                          </button>
                        </div>
                      </div>
                    );
                  })}

                  {!(selected.modules || []).length ? (
                    <div className="py-8 text-center text-xs text-ink-400 dark:text-slate-400">
                      Bu trackda hali birorta modul yo'q. Yuqoridagi <strong>«➕ Yangi Modul Qo'shish»</strong> tugmasi orqali qo'shing.
                    </div>
                  ) : null}
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-between border-t border-line px-6 py-3.5 dark:border-slate-800 bg-surface-soft/40 dark:bg-[#090d16]/80">
              <span className="text-xs font-bold text-ink-500 dark:text-slate-400">
                Track ID: #{selected.id} · O'zgarishlar avtomatik sinxronlanadi
              </span>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="btn btn-primary text-xs py-2 px-5 font-bold"
              >
                {t("common.close", "Yopish")}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* 🎓 Alohida Bitiruv Sertifikati Sozlash Modali (Portal) */}
      {showCertModal && selected && typeof document !== "undefined" && createPortal(
        <CertificateSettingsModal
          track={selected}
          apiFetch={apiFetch}
          onSaved={load}
          onClose={() => setShowCertModal(false)}
        />,
        document.body
      )}

      {/* ⚙️ Alohida Har Bir Modulni Sozlash & Testlar Modali (Portal) */}
      {selectedModule && selected && typeof document !== "undefined" && createPortal(
        <ModuleDetailModal
          track={selected}
          module={selectedModule}
          allModules={selected.modules || []}
          apiFetch={apiFetch}
          onSaved={load}
          onClose={() => {
            setSelectedModuleId(null);
            setOpenAddTestOnModuleOpen(false);
          }}
          initialOpenAddTest={openAddTestOnModuleOpen}
        />,
        document.body
      )}

      {/* Yangi Track Yaratish Modali (Portal) */}
      {showCreateTrackModal && typeof document !== "undefined" && createPortal(
        <div className="fixed inset-0 z-[250] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-fade-in">
          <div className="relative w-full max-w-lg overflow-hidden rounded-3xl bg-white p-6 shadow-2xl dark:bg-[#0f172a] border border-line dark:border-slate-800 animate-scale-up">
            <div className="flex items-center justify-between border-b border-line pb-3 dark:border-slate-800">
              <h3 className="text-lg font-black text-navy-900 dark:text-white flex items-center gap-2">
                <span>➕ {t("learning_paths.teacher.new_track", "Yangi Track Yaratish")}</span>
              </h3>
              <button
                type="button"
                onClick={() => setShowCreateTrackModal(false)}
                className="grid h-8 w-8 place-items-center rounded-full text-ink-500 hover:bg-rose-500/10 hover:text-rose-600 transition dark:text-slate-400 dark:hover:text-white"
                title={t("common.close", "Yopish")}
              >
                ✕
              </button>
            </div>
            {error ? (
              <div className="mt-3 rounded-xl border border-rose-500/30 bg-rose-500/15 p-3 text-xs font-bold text-rose-700 dark:text-rose-200">
                ⚠️ {error}
              </div>
            ) : null}
            <form onSubmit={create} className="mt-4 space-y-4">
              <div>
                <label className="mb-1 block text-xs font-black text-ink-600 dark:text-slate-300">
                  {t("learning_paths.teacher.track_title", "Track nomi")}
                </label>
                <input
                  value={title}
                  onChange={(e) => {
                    setTitle(e.target.value);
                    setError("");
                  }}
                  className="w-full rounded-2xl border border-line bg-white p-3 text-sm font-bold text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder-slate-400"
                  placeholder="Masalan: General English B1, Matematika Asoslari"
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-black text-ink-600 dark:text-slate-300">
                  {t("learning_paths.teacher.choose_subject", "Fanni tanlang")}
                </label>
                <select
                  value={trackSubject}
                  onChange={(e) => setTrackSubject(e.target.value)}
                  className="w-full rounded-2xl border border-line bg-white p-3 text-sm font-bold text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                >
                  <option value="Ingliz tili">🇬🇧 Ingliz tili</option>
                  <option value="Rus tili">🇷🇺 Rus tili</option>
                  <option value="Matematika">📐 Matematika</option>
                  <option value="Ona tili">📖 Ona tili</option>
                  <option value="General">🌐 Boshqa / Umumiy</option>
                </select>
              </div>
              <div className="flex justify-end gap-2.5 pt-2 border-t border-line/40 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowCreateTrackModal(false)}
                  className="rounded-xl border border-line px-4 py-2.5 text-xs font-bold text-ink-500 hover:bg-surface-soft dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  {t("common.cancel", "Bekor qilish")}
                </button>
                <button
                  type="submit"
                  disabled={busy || !title.trim()}
                  className="rounded-xl border-2 border-b-4 border-cyan-600 bg-cyan-600 px-5 py-2.5 text-xs font-black uppercase text-white shadow hover:bg-cyan-700 disabled:opacity-40"
                >
                  {busy ? "Yaratilmoqda..." : t("learning_paths.teacher.create_track_btn", "Track yaratish")}
                </button>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}
    </section>
  );
}

function CertificateSettingsModal({
  track,
  apiFetch,
  onSaved,
  onClose,
}: {
  track: Row;
  apiFetch: ApiFetch;
  onSaved: () => Promise<void>;
  onClose: () => void;
}) {
  const t = useWebT();
  const layer = (track.certificate_layers || [])[0] || {};
  const [score, setScore] = useState(String(track.passing_score || 70));

  // Auto-detect template matching teacher's subject: Russian if subject contains rus / рус, otherwise English
  const isRussian = (track.subject || "").toLowerCase().includes("rus") || (track.subject || "").toLowerCase().includes("рус");
  const template = isRussian ? "russian" : "english";

  // Shablonlar avtomatik kiritilgan bo'lsin
  const defaultCongratulations = isRussian
    ? `Поздравляем! Вы успешно завершили курс и освоили программу «${track.title || "Курс"}». Желаем дальнейших академических успехов!`
    : `Congratulations! Successfully completed the «${track.title || "Course"}» curriculum with outstanding excellence.`;

  const [text, setText] = useState(layer.text ? String(layer.text) : defaultCongratulations);
  const [x, setX] = useState(Number(layer.x ?? 0.5));
  const [y, setY] = useState(Number(layer.y ?? 0.44));
  const [size, setSize] = useState(Number(layer.font_size ?? 16));
  const [color, setColor] = useState(layer.color === "ink" ? "ink" : "blue");
  const [bold, setBold] = useState(layer.bold !== undefined ? Boolean(layer.bold) : true);
  const [busy, setBusy] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    const next = (track.certificate_layers || [])[0] || {};
    setScore(String(track.passing_score || 70));
    setText(next.text ? String(next.text) : defaultCongratulations);
    setX(Number(next.x ?? 0.5));
    setY(Number(next.y ?? 0.44));
    setSize(Number(next.font_size ?? 16));
    setColor(next.color === "ink" ? "ink" : "blue");
    setBold(next.bold !== undefined ? Boolean(next.bold) : true);
  }, [track, defaultCongratulations]);

  const place = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const nx = Math.max(0.05, Math.min(0.95, (e.clientX - rect.left) / rect.width));
    const ny = Math.max(0.05, Math.min(0.95, 1 - (e.clientY - rect.top) / rect.height));
    setX(Number(nx.toFixed(4)));
    setY(Number(ny.toFixed(4)));
  };

  const applyPreset = (preset: "default" | "honors" | "specialist" | "short") => {
    if (isRussian) {
      if (preset === "default") {
        setText(`Поздравляем! Вы успешно завершили курс и освоили программу «${track.title || "Курс"}». Желаем дальнейших академических успехов!`);
        setSize(16);
        setBold(true);
      } else if (preset === "honors") {
        setText(`С отличием окончил(а) полный курс углубленного изучения «${track.title || "Курс"}» с наивысшими баллами.`);
        setSize(18);
        setBold(true);
      } else if (preset === "specialist") {
        setText(`Настоящий сертификат подтверждает квалификационное освоение учебной программы «${track.title || "Курс"}».`);
        setSize(15);
        setBold(false);
      } else {
        setText(`Успешно завершил(а) обучение по программе «${track.title || "Курс"}».`);
        setSize(16);
        setBold(true);
      }
    } else {
      if (preset === "default") {
        setText(`Congratulations! Successfully completed the «${track.title || "Course"}» curriculum with outstanding excellence.`);
        setSize(16);
        setBold(true);
      } else if (preset === "honors") {
        setText(`Graduated with High Honors and exceptional mastery in the «${track.title || "Course"}» program.`);
        setSize(18);
        setBold(true);
      } else if (preset === "specialist") {
        setText(`This certificate officially verifies the successful qualification in «${track.title || "Course"}».`);
        setSize(15);
        setBold(false);
      } else {
        setText(`Successfully completed all modules of «${track.title || "Course"}».`);
        setSize(16);
        setBold(true);
      }
    }
  };

  const save = async () => {
    setBusy(true);
    try {
      await apiFetch(`/staff/learning-tracks/${track.id}`, {
        method: "PATCH",
        body: {
          passing_score: Math.max(1, Math.min(100, Number(score) || 70)),
          certificate_layers: [
            {
              text: text.trim(),
              x,
              y,
              font_size: size,
              color,
              bold,
            },
          ],
        },
      });
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
      await onSaved();
    } finally {
      setBusy(false);
    }
  };

  const previewColor = color === "ink" ? "#1f294d" : "#2138b8";

  return (
    <div
      className="fixed inset-0 z-[250] flex items-center justify-center bg-black/75 p-3 sm:p-6 backdrop-blur-sm overflow-hidden animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl max-h-[92vh] flex flex-col rounded-3xl bg-white shadow-2xl dark:bg-[#0f172a] border border-line dark:border-slate-800 overflow-hidden animate-scale-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-line px-6 py-4 dark:border-slate-800 bg-surface-soft/60 dark:bg-[#090d16]/80">
          <div className="flex items-center gap-3 min-w-0">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-cyan-500/15 text-2xl font-black text-cyan-700 dark:text-cyan-300">
              🎓
            </span>
            <div className="min-w-0">
              <h2 className="font-black text-navy-900 dark:text-white text-base sm:text-lg truncate">
                {t("learning_paths.teacher.cert_popup_title", "Bitiruv Sertifikati Sozlamalari")}
              </h2>
              <p className="text-xs text-ink-500 dark:text-slate-400 truncate">
                Track: {track.title} · Faqat butun kurs muvaffaqiyatli yakunlanganda beriladi
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-9 w-9 place-items-center rounded-full text-ink-500 hover:bg-rose-500/10 hover:text-rose-600 transition text-base font-bold dark:text-slate-400 dark:hover:text-white"
            title={t("common.close", "Yopish")}
          >
            ✕
          </button>
        </div>

        {/* Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 custom-scrollbar">
          {/* Auto-detected Subject Banner */}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-cyan-500/30 bg-cyan-500/10 dark:bg-cyan-950/20 p-3.5">
            <div className="flex items-center gap-2.5">
              <span className="text-2xl">{isRussian ? "🇷🇺" : "🇬🇧"}</span>
              <div>
                <p className="text-xs font-black uppercase text-cyan-900 dark:text-cyan-200">
                  {isRussian ? "Rus tili sertifikat shabloni (russian.svg)" : "Ingliz tili sertifikat shabloni (english.svg)"}
                </p>
                <p className="text-[11px] text-cyan-800 dark:text-cyan-300">
                  Fan o'qituvchi yo'nalishidan («{track.subject || "General"}») avtomatik aniqlandi.
                </p>
              </div>
            </div>
            <span className="rounded-lg bg-white/80 dark:bg-slate-800 px-2.5 py-1 text-xs font-bold text-navy-900 dark:text-white shadow-xs">
              {template}.svg
            </span>
          </div>

          {/* Quick Preset Buttons */}
          <div className="rounded-2xl border border-line bg-surface-soft/40 p-3.5 dark:border-slate-800 dark:bg-slate-800/40 space-y-2">
            <p className="text-xs font-black uppercase text-ink-600 dark:text-slate-300">
              ✨ Tayyor tabrik va yutuq shablonlari (1 bosishda matnni to'ldirish):
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => applyPreset("default")}
                className="rounded-xl border border-cyan-500/40 bg-cyan-500/15 px-3 py-1.5 text-xs font-bold text-cyan-800 dark:text-cyan-200 hover:bg-cyan-500/25 transition"
              >
                🎓 Standart Tabriknoma
              </button>
              <button
                type="button"
                onClick={() => applyPreset("honors")}
                className="rounded-xl border border-amber-500/40 bg-amber-500/15 px-3 py-1.5 text-xs font-bold text-amber-800 dark:text-amber-200 hover:bg-amber-500/25 transition"
              >
                🌟 A'lo Natija (Honors)
              </button>
              <button
                type="button"
                onClick={() => applyPreset("specialist")}
                className="rounded-xl border border-indigo-500/40 bg-indigo-500/15 px-3 py-1.5 text-xs font-bold text-indigo-800 dark:text-indigo-200 hover:bg-indigo-500/25 transition"
              >
                🏆 Mutaxassislik Guvohnomasi
              </button>
              <button
                type="button"
                onClick={() => applyPreset("short")}
                className="rounded-xl border border-emerald-500/40 bg-emerald-500/15 px-3 py-1.5 text-xs font-bold text-emerald-800 dark:text-emerald-200 hover:bg-emerald-500/25 transition"
              >
                🏅 Qisqa Tabrik
              </button>
            </div>
          </div>

          {/* Settings Fields */}
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-bold text-ink-600 dark:text-slate-300">
                Track o'tish bali (%)
              </label>
              <input
                value={score}
                min="1"
                max="100"
                type="number"
                onChange={(e) => setScore(e.target.value)}
                className="w-full rounded-xl border border-line bg-white p-2.5 text-xs font-bold text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-bold text-ink-600 dark:text-slate-300">
                Shrift o'lchami (px)
              </label>
              <input
                type="number"
                min="8"
                max="42"
                value={size}
                onChange={(e) => setSize(Number(e.target.value))}
                className="w-full rounded-xl border border-line bg-white p-2.5 text-xs font-bold text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-bold text-ink-600 dark:text-slate-300">
                Matn rangi
              </label>
              <select
                value={color}
                onChange={(e) => setColor(e.target.value)}
                className="w-full rounded-xl border border-line bg-white p-2.5 text-xs font-bold text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
              >
                <option value="blue">Ko'k (#2138b8)</option>
                <option value="ink">To'q qora-ko'k (#1f294d)</option>
              </select>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-bold text-ink-600 dark:text-slate-300">
                Sertifikatdagi tabrik yoki erishilgan natija matni:
              </label>
              <label className="flex items-center gap-1.5 text-xs font-bold text-ink-600 dark:text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={bold}
                  onChange={(e) => setBold(e.target.checked)}
                  className="rounded"
                />
                Qalin shrift (Bold)
              </label>
            </div>
            <textarea
              rows={2}
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="w-full rounded-xl border border-line bg-white p-2.5 text-xs font-bold text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white resize-none dark:placeholder-slate-400"
              placeholder="Tabriknoma yoki kurs nomi..."
            />
          </div>

          <div className="flex items-center justify-between pt-1">
            <p className="text-xs font-bold text-ink-600 dark:text-slate-300">
              👇 Sertifikat maketi — matnni siljitish uchun rasm ustiga bosing:
            </p>
            <span className="text-xs font-mono font-bold text-cyan-700 dark:text-cyan-300">
              Matn koordinatasi: X: {Math.round(x * 100)}%, Y: {Math.round((1 - y) * 100)}%
            </span>
          </div>

          {/* Certificate Live Interactive Canvas */}
          <div
            onClick={place}
            role="button"
            tabIndex={0}
            className="relative aspect-[1123/794] cursor-crosshair overflow-hidden rounded-2xl border-2 border-line bg-white shadow-xl select-none"
          >
            <img
              src={`/learning-paths/certificate-${template}.svg`}
              alt="Certificate preview"
              className="pointer-events-none absolute inset-0 h-full w-full object-cover"
            />

            {/* Full name line preview */}
            <div
              className="pointer-events-none absolute left-1/2 -translate-x-1/2 -translate-y-1/2 text-center"
              style={{ top: "43.5%" }}
            >
              <span className="inline-block rounded-md bg-white/90 px-3 py-1 font-serif text-sm sm:text-base font-black text-[#0C188B] shadow border border-[#0C188B]/30 tracking-wide">
                [ TALABA ISM FAMILIYASI ]
              </span>
              <p className="text-[10px] font-bold text-[#0C188B]/80 mt-0.5">
                ↑ Uzun chiziq ustidagi ism-familiya joyi
              </p>
            </div>

            {/* Course Title */}
            <div
              className="pointer-events-none absolute left-1/2 -translate-x-1/2 -translate-y-1/2 text-center"
              style={{ top: "50%" }}
            >
              <span className="inline-block rounded bg-white/80 px-2 py-0.5 text-xs font-bold text-[#0C188B] shadow-sm">
                {track.title || "Diamond Education Track"}
              </span>
            </div>

            {/* Date line preview */}
            <div
              className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 text-center"
              style={{ left: "13.5%", top: "77.5%" }}
            >
              <span className="inline-block rounded bg-white/90 px-2 py-0.5 font-mono text-[11px] font-black text-[#0C188B] border border-[#0C188B]/30 shadow-sm">
                {new Date().toLocaleDateString("uz-UZ")}
              </span>
              <p className="text-[9px] font-bold text-[#0C188B]/80 mt-0.5">
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
                className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 whitespace-nowrap drop-shadow bg-white/70 px-1.5 py-0.5 rounded"
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
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-line px-6 py-4 dark:border-slate-800 bg-surface-soft/40 dark:bg-[#090d16]/80">
          <div>
            {savedSuccess ? (
              <span className="text-xs font-black text-emerald-600 dark:text-emerald-400 animate-fade-in">
                ✅ Sertifikat sozlamalari muvaffaqiyatli saqlandi!
              </span>
            ) : (
              <span className="text-xs text-ink-500 dark:text-slate-400">
                Sertifikat {isRussian ? "ruscha" : "inglizcha"} dizaynda avtomatik yaratiladi
              </span>
            )}
          </div>
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-line px-4 py-2 text-xs font-bold text-ink-500 hover:bg-surface-soft dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {t("common.close", "Yopish")}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void save()}
              className="rounded-xl border-2 border-b-4 border-cyan-600 bg-cyan-600 px-5 py-2 text-xs font-black uppercase text-white shadow hover:bg-cyan-700 disabled:opacity-40 transition active:translate-y-0.5 active:border-b-2"
            >
              {busy ? "Saqlanmoqda..." : "✓ Sertifikatni saqlash"}
            </button>
          </div>
        </div>
      </div>
    </div>
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
  { key: "gap_fill", label: "␣ Bo'sh joy to'ldirish (Gap fill)", needsAudio: false },
  { key: "word_order", label: "🔤 So'z tartibi (Word Order)", needsAudio: false },
  { key: "scrambled_sentence", label: "🔀 So'zlarni tartibga solish", needsAudio: false },
  { key: "matching", label: "🔗 Moslashtirish (Juftliklar)", needsAudio: false },
  { key: "listening", label: "🎧 Tinglab tushunish (Variantli)", needsAudio: true },
  { key: "dictation", label: "🎼 Diktant (Eshitib yozish)", needsAudio: true },
  { key: "listening_dictation", label: "🎧 Diktant (Audio tinglab yozish)", needsAudio: true },
  { key: "listening_tf", label: "🎧 Listening: True / False / Not Given", needsAudio: true },
  { key: "listening_gap", label: "␣ Listening: Bo'sh joyni to'ldirish", needsAudio: true },
  { key: "listening_order", label: "🧩 Listening: So'zlar tartibi", needsAudio: true },
  { key: "listening_open", label: "🎧 Listening: Ochiq savol", needsAudio: true },
  { key: "listening_set", label: "🎧 Listening Set (1 audio + ko'p savol)", needsAudio: true },
  { key: "spelling", label: "🔤 To'g'ri yozish (Imlo)", needsAudio: false },
  { key: "translation", label: "🔁 Tarjima qilish", needsAudio: false },
  { key: "speak_sentence", label: "🎙️ Gap tuzib gapirish", needsAudio: false },
  { key: "write_sentence", label: "✍️ Gap tuzib yozish", needsAudio: false },
  { key: "guided_writing", label: "📝 Mavzu bo'yicha yozma mashq", needsAudio: false },
  { key: "reading_open", label: "📖 Matn bo'yicha ochiq savol", needsAudio: false, needsPassage: true },
  { key: "read_aloud", label: "🔊 Ovoz chiqarib o'qish", needsAudio: false },
  { key: "paraphrase", label: "🔄 Gapni boshqacha aytish (Paraphrase)", needsAudio: false },
  { key: "dialogue_completion", label: "💬 Dialogni to'ldirish", needsAudio: false },
  { key: "picture_description", label: "🖼️ Rasmni tasvirlash", needsAudio: false },
  { key: "passage_cloze", label: "📃 Matnni to'ldirish (so'zlar banki)", needsAudio: false, needsPassage: true },
  { key: "reading_set", label: "📚 Matn va savollar (Reading Set)", needsAudio: false, needsPassage: true },
  { key: "word_practice", label: "💡 So'z mashqi (Random tur)", needsAudio: false },
];

function LessonEditor({
  module,
  apiFetch,
  onSaved,
  initialOpenAddTest = false,
}: {
  module: Row;
  apiFetch: ApiFetch;
  onSaved: () => Promise<void>;
  initialOpenAddTest?: boolean;
}) {
  const t = useWebT();
  const lessons = Array.isArray(module.lessons) ? module.lessons : [];
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [passage, setPassage] = useState("");
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
  const [editPassage, setEditPassage] = useState("");
  const [editType, setEditType] = useState("multiple_choice");
  const [editOptions, setEditOptions] = useState("");
  const [editCorrect, setEditCorrect] = useState("");
  const [editExplanation, setEditExplanation] = useState("");
  const [editAudioUrl, setEditAudioUrl] = useState("");
  const [editAudioUploading, setEditAudioUploading] = useState(false);
  const [editHint, setEditHint] = useState("");
  const [editDirection, setEditDirection] = useState("");
  const [editWordCount, setEditWordCount] = useState(0);

  // AI & Library states
  const [addMode, setAddMode] = useState<"library" | "ai" | "manual">("library");
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(10);
  const [types, setTypes] = useState("multiple_choice,true_false,fill_blank,word_order,matching");
  const [busy, setBusy] = useState(false);
  const [showAddTestModal, setShowAddTestModal] = useState(initialOpenAddTest);
  const [hint, setHint] = useState("");
  const [direction, setDirection] = useState("");
  const [wordCount, setWordCount] = useState(0);

  useEffect(() => {
    if (initialOpenAddTest) {
      setShowAddTestModal(true);
    }
  }, [initialOpenAddTest]);
  const [showLibraryModal, setShowLibraryModal] = useState(false);

  const curKindMeta = ALL_TEST_KINDS.find((k) => k.key === manualType) || { needsAudio: false, needsPassage: false };
  const editKindMeta = ALL_TEST_KINDS.find((k) => k.key === editType) || { needsAudio: false, needsPassage: false };

  const startEdit = (lesson: Row) => {
    setEditingLessonId(Number(lesson.id));
    setEditTitle(String(lesson.title || ""));
    const p = (lesson.question_payload as Row) || {};
    setEditPrompt(String(p.question || p.prompt || ""));
    setEditPassage(String(p.passage || p.context || ""));
    setEditType(String(p.test_type || lesson.source_version || "multiple_choice"));
    const opts = Array.isArray(p.options) ? p.options.join(" | ") : "";
    setEditOptions(opts);
    setEditCorrect(String(p.correct_answer || p.answer || ""));
    setEditExplanation(String(p.explanation || ""));
    setEditAudioUrl(String(p.audio_url || ""));
    setEditHint(String(p.hint || p.definition || ""));
    setEditDirection(String(p.direction || ""));
    setEditWordCount(Number(p.word_count || 0));
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
    let pairs: { left: string; right: string }[] = [];

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
      for (const c of choices) {
        if (c.includes("=")) {
          const [l, r] = c.split("=").map((s) => s.trim());
          if (l && r) pairs.push({ left: l, right: r });
        } else if (c.includes(" - ")) {
          const [l, r] = c.split(" - ").map((s) => s.trim());
          if (l && r) pairs.push({ left: l, right: r });
        }
      }
      if (pairs.length < 2 && choices.length >= 2) {
        for (let i = 0; i < choices.length - 1; i += 2) {
          pairs.push({ left: choices[i], right: choices[i + 1] });
        }
      }
      if (pairs.length < 2) {
        alert("Moslashtirish uchun kamida 2 ta juftlik kiriting (masalan: olma = apple | kitob = book).");
        return;
      }
      if (!answer && pairs.length) answer = pairs.map((p) => `${p.left} = ${p.right}`).join("; ");
    } else {
      choices = editOptions ? editOptions.split("|").map((x) => x.trim()).filter(Boolean) : [];
    }

    const openTypes = [
      "speak_sentence", "write_sentence", "guided_writing", "reading_open",
      "listening_open", "read_aloud", "picture_description", "paraphrase", "word_practice",
    ];
    if (!answer && !openTypes.includes(editType) && editType !== "matching") {
      alert("Iltimos, to'g'ri javobni kiriting.");
      return;
    }

    const origLesson = lessons.find((l) => Number(l.id) === editingLessonId);
    const origPayload = (origLesson?.question_payload as Row) || {};

    setBusy(true);
    try {
      await apiFetch(`/staff/learning-lessons/${editingLessonId}`, {
        method: "PATCH",
        body: {
          title: editTitle.trim(),
          question_payload: {
            ...origPayload,
            question: editPrompt.trim(),
            options: choices,
            correct_answer: answer || editPrompt.trim(),
            explanation: editExplanation.trim(),
            test_type: editType,
            audio_url: editAudioUrl.trim() || null,
            ...(editPassage.trim() ? { passage: editPassage.trim() } : {}),
            ...(pairs.length > 0
              ? {
                  pairs,
                  left_items: pairs.map((p) => p.left),
                  right_items: [...pairs.map((p) => p.right)].sort(),
                }
              : {}),
            ...(editType === "word_order" || editType === "scrambled_sentence" || editType === "listening_order"
              ? { tokens: choices.length ? choices : (answer ? answer.split(/\s+/).filter(Boolean) : []) }
              : {}),
            ...(editHint.trim() ? { hint: editHint.trim() } : {}),
            ...(editDirection.trim() ? { direction: editDirection.trim() } : {}),
            ...(editWordCount > 0 ? { word_count: editWordCount } : {}),
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
    let pairs: { left: string; right: string }[] = [];

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
      for (const c of choices) {
        if (c.includes("=")) {
          const [l, r] = c.split("=").map((s) => s.trim());
          if (l && r) pairs.push({ left: l, right: r });
        } else if (c.includes(" - ")) {
          const [l, r] = c.split(" - ").map((s) => s.trim());
          if (l && r) pairs.push({ left: l, right: r });
        }
      }
      if (pairs.length < 2 && choices.length >= 2) {
        for (let i = 0; i < choices.length - 1; i += 2) {
          pairs.push({ left: choices[i], right: choices[i + 1] });
        }
      }
      if (pairs.length < 2) {
        alert("Moslashtirish uchun kamida 2 ta juftlik kiriting (masalan: olma = apple | kitob = book).");
        return;
      }
      if (!answer && pairs.length) answer = pairs.map((p) => `${p.left} = ${p.right}`).join("; ");
    } else {
      choices = options ? options.split("|").map((x) => x.trim()).filter(Boolean) : [];
    }

    const openTypes = [
      "speak_sentence", "write_sentence", "guided_writing", "reading_open",
      "listening_open", "read_aloud", "picture_description", "paraphrase", "word_practice",
    ];
    if (!answer && !openTypes.includes(manualType) && manualType !== "matching") {
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
            correct_answer: answer || prompt.trim(),
            explanation: explanation.trim(),
            test_type: manualType,
            audio_url: audioUrl.trim() || null,
            ...(passage.trim() ? { passage: passage.trim() } : {}),
            ...(pairs.length > 0
              ? {
                  pairs,
                  left_items: pairs.map((p) => p.left),
                  right_items: [...pairs.map((p) => p.right)].sort(),
                }
              : {}),
            ...(manualType === "word_order" || manualType === "scrambled_sentence" || manualType === "listening_order"
              ? { tokens: choices.length ? choices : (answer ? answer.split(/\s+/).filter(Boolean) : []) }
              : {}),
            ...(hint.trim() ? { hint: hint.trim() } : {}),
            ...(direction.trim() ? { direction: direction.trim() } : {}),
            ...(wordCount > 0 ? { word_count: wordCount } : {}),
          },
        },
      });
      setTitle("");
      setPrompt("");
      setPassage("");
      setOptions("");
      setCorrect("");
      setExplanation("");
      setAudioUrl("");
      setHint("");
      setDirection("");
      setWordCount(0);
      setShowAddTestModal(false);
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
          test_types: (types || "multiple_choice,true_false,fill_blank,word_order,matching").split(",").map((value) => value.trim()).filter(Boolean),
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
      setShowAddTestModal(false);
      await onSaved();
    } catch (err) {
      alert("AI test yaratishda xatolik yuz berdi: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setBusy(false);
    }
  };

  const attachLibrary = async (contentId: number, cType = "library_node", qCount?: number) => {
    if (!contentId) return;
    setBusy(true);
    try {
      await apiFetch(`/staff/learning-modules/${module.id}/library-test`, {
        method: "POST",
        body: {
          content_type: cType,
          content_id: contentId,
          ...(typeof qCount === "number" && qCount > 0 ? { question_count: qCount } : {}),
        },
      });
      setShowLibraryModal(false);
      setShowAddTestModal(false);
      await onSaved();
    } catch (err) {
      alert("Material testini biriktirishda xatolik: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!window.confirm(t("learning_paths.teacher.delete_module_prompt", { title: String(module.title || "") }))) return;
    setBusy(true);
    try {
      await apiFetch(`/staff/learning-modules/${module.id}`, { method: "DELETE" });
      await onSaved();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-4 border-t border-line/60 pt-4 dark:border-slate-800 space-y-4">
      {/* ─── Moduldagi mavjud testlar ro'yxati (Tahrirlash va O'chirish) ─── */}
      <div className="rounded-2xl border border-line p-4 dark:border-slate-800 bg-white/70 dark:bg-[#0f172a]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase text-navy-900 dark:text-white flex items-center gap-2">
              <span>📋 {t("learning_paths.teacher.lessons_in_module", { count: lessons.length })}</span>
            </p>
            <span className="text-[10px] font-bold text-ink-500 dark:text-slate-400">
              {t("learning_paths.teacher.lessons_hint")}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setShowAddTestModal(true)}
            className="inline-flex items-center gap-1.5 rounded-xl border-2 border-b-4 border-[#1899d6] bg-[#1cb0f6] px-4 py-2 text-xs font-black uppercase tracking-wider text-white shadow-md transition-all active:translate-y-0.5 active:border-b-2 hover:bg-[#1899d6]"
          >
            <span>{t("learning_paths.teacher.add_test_btn")}</span>
          </button>
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
                      ? "border-cyan-400 bg-cyan-500/5 shadow-sm dark:bg-cyan-950/20"
                      : "border-line bg-surface-soft/40 hover:border-cyan-300 dark:border-slate-800 dark:bg-[#090d16]/50"
                  }`}
                >
                  {isEditing ? (
                    /* Inline Lesson Edit Form */
                    <div className="space-y-3">
                      <div className="flex items-center justify-between border-b border-line/40 pb-2 dark:border-slate-800">
                        <span className="text-xs font-black text-cyan-700 dark:text-cyan-300">
                          ✏️ {t("learning_paths.teacher.edit_test_title")} (#{idx + 1})
                        </span>
                        <button
                          type="button"
                          onClick={() => setEditingLessonId(null)}
                          className="text-xs text-ink-500 hover:text-rose-500 dark:text-slate-400"
                        >
                          ✕ {t("learning_paths.teacher.cancel")}
                        </button>
                      </div>

                      <div className="grid gap-2 sm:grid-cols-2">
                        <input
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          className="rounded-xl border border-line bg-white dark:bg-slate-800/80 p-2 text-xs dark:border-slate-700 dark:text-white font-bold placeholder:text-slate-400 dark:placeholder:text-slate-500"
                          placeholder={t("learning_paths.teacher.module_title")}
                        />
                        <select
                          value={editType}
                          onChange={(e) => setEditType(e.target.value)}
                          className="rounded-xl border border-line bg-white dark:bg-slate-800/80 p-2 text-xs font-semibold dark:border-slate-700 dark:text-white"
                        >
                          {ALL_TEST_KINDS.map((k) => (
                            <option key={k.key} value={k.key}>
                              {k.label}
                            </option>
                          ))}
                        </select>
                      </div>

                      {editKindMeta.needsAudio ? (
                        <div className="rounded-xl border border-cyan-400/40 bg-cyan-500/10 p-2.5 space-y-2 dark:bg-cyan-950/30">
                          <div className="flex items-center justify-between">
                            <span className="text-[11px] font-black text-cyan-800 dark:text-cyan-200">
                              🎧 {t("learning_paths.teacher.upload_audio")}
                            </span>
                            {editAudioUploading && <span className="text-[10px] text-cyan-600 animate-pulse">{t("learning_paths.teacher.uploading")}</span>}
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            <label className="btn btn-soft text-xs py-1 px-3 cursor-pointer">
                              📁 {t("learning_paths.teacher.upload_new_audio")}
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
                              placeholder={t("learning_paths.teacher.audio_url_placeholder")}
                              className="min-w-0 flex-1 rounded-xl border border-line bg-white dark:bg-slate-800 p-1.5 text-xs dark:border-slate-700 dark:text-white"
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
                        className="w-full rounded-xl border border-line bg-white dark:bg-slate-800/80 p-2 text-xs dark:border-slate-700 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500"
                        placeholder={t("learning_paths.teacher.question_prompt")}
                      />

                      <div className="grid gap-2 sm:grid-cols-2">
                        <input
                          value={editOptions}
                          onChange={(e) => setEditOptions(e.target.value)}
                          className="rounded-xl border border-line bg-white dark:bg-slate-800/80 p-2 text-xs dark:border-slate-700 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500"
                          placeholder={
                            editType === "matching"
                              ? "Juftliklar: olma = apple | kitob = book"
                              : editType === "true_false" || editType === "listening_tf"
                              ? "To'g'ri | Noto'g'ri"
                              : `${t("learning_paths.teacher.options")}: A | B | C | D`
                          }
                        />
                        <input
                          value={editCorrect}
                          onChange={(e) => setEditCorrect(e.target.value)}
                          className="rounded-xl border border-line bg-white dark:bg-slate-800/80 p-2 text-xs dark:border-slate-700 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500"
                          placeholder={t("learning_paths.teacher.correct_answer")}
                        />
                      </div>

                      {/* Contextual Extra Inputs for Inline Edit */}
                      {editKindMeta.needsPassage ? (
                        <textarea
                          rows={2}
                          value={editPassage}
                          onChange={(e) => setEditPassage(e.target.value)}
                          className="w-full rounded-xl border border-line bg-white dark:bg-slate-800/80 p-2 text-xs dark:border-slate-700 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500"
                          placeholder="Matn (Passage / Context)..."
                        />
                      ) : null}

                      {editType === "spelling" || editType === "dictation" || editType === "listening_dictation" || editType === "gap_fill" || editType === "listening_gap" ? (
                        <input
                          value={editHint}
                          onChange={(e) => setEditHint(e.target.value)}
                          className="w-full rounded-xl border border-line bg-white dark:bg-slate-800/80 p-2 text-xs dark:border-slate-700 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500"
                          placeholder="Yordamchi ko'rsatma / Ta'rif / Hint..."
                        />
                      ) : null}

                      {editType === "translation" ? (
                        <input
                          value={editDirection}
                          onChange={(e) => setEditDirection(e.target.value)}
                          className="w-full rounded-xl border border-line bg-white dark:bg-slate-800/80 p-2 text-xs dark:border-slate-700 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500"
                          placeholder="Tarjima yo'nalishi (masalan: UZ → EN yoki EN → UZ)"
                        />
                      ) : null}

                      {editType === "guided_writing" ? (
                        <input
                          type="number"
                          value={editWordCount || ""}
                          onChange={(e) => setEditWordCount(Number(e.target.value) || 0)}
                          className="w-full rounded-xl border border-line bg-white dark:bg-slate-800/80 p-2 text-xs dark:border-slate-700 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500"
                          placeholder="Minimal so'zlar soni (masalan: 30)"
                        />
                      ) : null}

                      <input
                        value={editExplanation}
                        onChange={(e) => setEditExplanation(e.target.value)}
                        className="w-full rounded-xl border border-line bg-white dark:bg-slate-800/80 p-2 text-xs dark:border-slate-700 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500"
                        placeholder={t("learning_paths.teacher.explanation")}
                      />

                      <div className="flex justify-end gap-2 pt-1">
                        <button
                          type="button"
                          onClick={() => setEditingLessonId(null)}
                          className="btn btn-soft text-xs"
                        >
                          {t("learning_paths.teacher.cancel")}
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void saveEdit()}
                          className="btn btn-primary text-xs"
                        >
                          ✓ {t("learning_paths.teacher.save")}
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
                            ✏️ {t("learning_paths.teacher.edit")}
                          </button>
                          <button
                            type="button"
                            onClick={() => void deleteLesson(Number(lesson.id))}
                            className="rounded-lg border border-rose-400/40 px-2 py-1 text-xs font-bold text-rose-600 hover:bg-rose-500/10 dark:text-rose-300 transition"
                            title={t("learning_paths.teacher.delete")}
                          >
                            🗑
                          </button>
                        </div>
                      </div>

                      {/* Question text & choices preview */}
                      <p className="mt-2 text-xs font-medium text-ink-600 dark:text-slate-300">
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
                                    : "border-line/60 bg-white/50 text-ink-500 dark:border-slate-800 dark:bg-slate-800/40 dark:text-slate-300"
                                }`}
                              >
                                {isCorrect ? "✓ " : ""}{opt}
                              </span>
                            );
                          })}
                        </div>
                      ) : p.correct_answer ? (
                        <p className="mt-1 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300">
                          {t("learning_paths.teacher.correct_answer")}: <strong>{String(p.correct_answer)}</strong>
                        </p>
                      ) : null}
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <p className="text-xs text-ink-400 italic p-3 bg-surface-soft/40 dark:bg-slate-800/40 rounded-xl text-center">
              {t("learning_paths.teacher.no_lessons_yet")}
            </p>
          )}
        </div>
      </div>

      {/* ─── Modul amallari paneli ─── */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line/80 bg-surface-soft/40 p-4 dark:border-slate-800 dark:bg-[#0f172a]">
        <button
          type="button"
          onClick={() => setShowAddTestModal(true)}
          className="inline-flex items-center gap-2 rounded-2xl border-2 border-b-4 border-[#1899d6] bg-[#1cb0f6] px-5 py-2.5 text-xs font-black uppercase tracking-wider text-white shadow-md transition-all active:translate-y-0.5 active:border-b-2 hover:bg-[#1899d6]"
        >
          <span>{t("learning_paths.teacher.module_add_test_btn")}</span>
        </button>

        <button
          type="button"
          disabled={busy}
          onClick={() => void remove()}
          className="rounded-xl border border-rose-400/40 px-3 py-1.5 text-xs font-bold text-rose-600 hover:bg-rose-500/10 dark:text-rose-300 transition"
        >
          {t("learning_paths.teacher.delete_module_btn")}
        </button>
      </div>

      {/* ─── Test Qo'shish Qalqib chiquvchi Oynasi (Modal Dialog Portal) ─── */}
      {showAddTestModal && typeof document !== "undefined" && createPortal(
        <div
          className="fixed inset-0 z-[300] flex items-center justify-center bg-black/75 p-3 sm:p-4 backdrop-blur-sm animate-fade-in"
          onClick={() => setShowAddTestModal(false)}
        >
          <div
            className="relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-3xl bg-white shadow-2xl dark:bg-[#0f172a] border border-line dark:border-slate-800 animate-scale-up"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-line p-4 sm:p-5 dark:border-slate-800 dark:bg-[#090d16]/80">
              <div>
                <h4 className="text-sm font-black uppercase tracking-wider text-navy-900 dark:text-white flex items-center gap-2">
                  <span>{t("learning_paths.teacher.add_test_modal_title")}</span>
                </h4>
                <p className="text-xs text-ink-500 dark:text-slate-400 mt-0.5">
                  {t("learning_paths.teacher.method_choose", { title: String(module.title || "") })}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowAddTestModal(false)}
                className="grid h-9 w-9 place-items-center rounded-full text-ink-500 hover:bg-rose-500/10 hover:text-rose-600 dark:text-slate-400 transition"
              >
                ✕
              </button>
            </div>

            {/* 3-Tab Segmented Controls */}
            <div className="flex border-b border-line bg-surface-soft/40 p-2 dark:border-slate-800 dark:bg-[#090d16]/50 gap-1.5">
              <button
                type="button"
                onClick={() => setAddMode("library")}
                className={`flex-1 flex items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-xs font-black transition-all ${
                  addMode === "library"
                    ? "bg-white text-[#1cb0f6] shadow-sm dark:bg-slate-800 dark:text-[#38bdf8]"
                    : "text-slate-600 hover:text-navy-900 dark:text-slate-400 dark:hover:text-white"
                }`}
              >
                <span>📂 {t("learning_paths.teacher.from_library")}</span>
              </button>

              <button
                type="button"
                onClick={() => setAddMode("ai")}
                className={`flex-1 flex items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-xs font-black transition-all ${
                  addMode === "ai"
                    ? "bg-white text-emerald-600 shadow-sm dark:bg-slate-800 dark:text-emerald-400"
                    : "text-slate-600 hover:text-navy-900 dark:text-slate-400 dark:hover:text-white"
                }`}
              >
                <span>✨ {t("learning_paths.teacher.from_ai")}</span>
              </button>

              <button
                type="button"
                onClick={() => setAddMode("manual")}
                className={`flex-1 flex items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-xs font-black transition-all ${
                  addMode === "manual"
                    ? "bg-white text-purple-600 shadow-sm dark:bg-slate-800 dark:text-purple-400"
                    : "text-slate-600 hover:text-navy-900 dark:text-slate-400 dark:hover:text-white"
                }`}
              >
                <span>✍️ {t("learning_paths.teacher.manual")}</span>
              </button>
            </div>

            {/* Modal Body with Scroll */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-5">
              {/* TAB 1: Real Materials Library Picker */}
              {addMode === "library" ? (
                <div className="space-y-4 animate-fade-in">
                  <div className="rounded-2xl border-2 border-dashed border-[#1cb0f6]/40 bg-[#1cb0f6]/5 p-6 text-center dark:border-[#1cb0f6]/20 dark:bg-cyan-950/20">
                    <div className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-[#1cb0f6]/15 text-2xl text-[#1cb0f6]">
                      📂
                    </div>
                    <h5 className="text-base font-black text-navy-900 dark:text-white">
                      {t("learning_paths.teacher.library_title")}
                    </h5>
                    <p className="mx-auto mt-1 max-w-md text-xs text-slate-500 dark:text-slate-400">
                      {t("learning_paths.teacher.library_desc")}
                    </p>

                    <button
                      type="button"
                      onClick={() => setShowLibraryModal(true)}
                      className="mt-4 inline-flex items-center gap-2 rounded-2xl border-2 border-b-4 border-[#1899d6] bg-[#1cb0f6] px-6 py-3 text-xs font-black uppercase tracking-wider text-white shadow-md transition-all active:translate-y-1 active:border-b-2 hover:bg-[#1899d6]"
                    >
                      <span>{t("learning_paths.teacher.library_open_btn")}</span>
                    </button>
                  </div>
                </div>
              ) : null}

              {/* TAB 2: AI Diamondvoy Generator */}
              {addMode === "ai" ? (
                <div className="space-y-4 animate-fade-in">
                  <div className="rounded-2xl border-2 border-emerald-500/20 bg-emerald-500/5 p-4 sm:p-5 dark:bg-emerald-950/20 dark:border-emerald-500/30">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-black uppercase tracking-wider text-emerald-800 dark:text-emerald-300 flex items-center gap-1.5">
                        <span>{t("learning_paths.teacher.ai_title")}</span>
                      </span>
                      <span className="rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-[10px] font-black text-emerald-800 dark:text-emerald-200">
                        {t("learning_paths.teacher.ai_direct_add")}
                      </span>
                    </div>

                    {/* Quick Topic Suggestion Pills */}
                    <div className="mt-3 flex flex-wrap items-center gap-1.5">
                      <span className="text-[11px] font-bold text-slate-500 dark:text-slate-400">{t("learning_paths.teacher.ai_topic_label")}</span>
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
                          className="rounded-lg border border-emerald-400/40 bg-white px-2 py-0.5 text-[11px] font-bold text-emerald-700 hover:bg-emerald-50 dark:border-slate-700 dark:bg-slate-800 dark:text-emerald-300"
                        >
                          + {sug}
                        </button>
                      ))}
                    </div>

                    <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_130px]">
                      <input
                        value={topic}
                        onChange={(e) => setTopic(e.target.value)}
                        placeholder={t("learning_paths.teacher.ai_topic_placeholder")}
                        className="rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-emerald-400 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500"
                      />

                      <div className="flex items-center gap-2">
                        <label className="text-xs font-black text-slate-600 dark:text-slate-300 whitespace-nowrap">
                          {t("learning_paths.teacher.ai_count_label")}
                        </label>
                        <input
                          type="number"
                          min="1"
                          max="25"
                          value={count}
                          onChange={(e) => setCount(Number(e.target.value))}
                          className="w-full rounded-2xl border-2 border-slate-200 bg-white p-3 text-center text-xs font-black text-navy-900 focus:border-emerald-400 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                        />
                      </div>

                      <select
                        value={types}
                        onChange={(e) => setTypes(e.target.value)}
                        className="sm:col-span-2 rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-black text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                      >
                        <option value="multiple_choice,true_false,fill_blank,word_order,matching">🎲 Barchasi aralash (MCQ + True/False + Bo'sh joy + So'z tartibi + Moslashtirish) — Standart</option>
                        <option value="multiple_choice,true_false,fill_blank">Aralash (Ko'p tanlovli + True/False + Bo'sh joy to'ldirish)</option>
                        <option value="multiple_choice">Faqat Ko'p tanlovli (MCQ)</option>
                        <option value="true_false">Faqat To'g'ri / Noto'g'ri (True / False)</option>
                        <option value="fill_blank">Faqat Bo'sh joyni to'ldirish (Fill in blank)</option>
                        <option value="word_order">Faqat So'z tartibi (Word Order)</option>
                        <option value="matching">Faqat Moslashtirish (Matching Pairs)</option>
                        <option value="translation">Faqat Tarjima mashqlari</option>
                        <option value="spelling">Faqat Imlo (Spelling)</option>
                      </select>

                      <button
                        type="button"
                        disabled={busy || !topic.trim()}
                        onClick={() => void generate()}
                        className="sm:col-span-2 rounded-2xl border-2 border-b-4 border-[#46a302] bg-[#58cc02] py-3.5 text-center text-xs font-black uppercase tracking-wider text-white shadow-md transition-all active:translate-y-1 active:border-b-2 hover:bg-[#4cb802] disabled:opacity-40"
                      >
                        {busy ? t("learning_paths.teacher.ai_busy") : t("learning_paths.teacher.ai_generate_btn")}
                      </button>
                    </div>
                  </div>
                </div>
              ) : null}

              {/* TAB 3: Manual Test Builder */}
              {addMode === "manual" ? (
                <div className="space-y-4 animate-fade-in">
                  <div className="rounded-2xl border-2 border-purple-500/20 bg-purple-500/5 p-4 sm:p-5 space-y-3 dark:bg-purple-950/20 dark:border-purple-500/30">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-black uppercase tracking-wider text-purple-900 dark:text-purple-300">
                        {t("learning_paths.teacher.manual_title")}
                      </span>
                      <span className="rounded-full bg-purple-500/20 px-2.5 py-0.5 text-[10px] font-black text-purple-800 dark:text-purple-200">
                        {t("learning_paths.teacher.manual_kinds_count")}
                      </span>
                    </div>

                    {/* Title and Test Kind Selector */}
                    <div className="grid gap-2.5 sm:grid-cols-2">
                      <input
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder={t("learning_paths.teacher.manual_name_placeholder")}
                        className="rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500"
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
                        className="rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-black text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
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
                      <div className="rounded-2xl border-2 border-cyan-400/40 bg-cyan-500/10 p-4 space-y-3 dark:bg-cyan-950/30">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-black text-cyan-900 dark:text-cyan-200 flex items-center gap-1.5">
                            <span>🎧 {t("learning_paths.teacher.upload_audio")}</span>
                          </span>
                          {audioUploading && (
                            <span className="text-xs text-cyan-600 animate-pulse font-bold">
                              {t("learning_paths.teacher.uploading")}
                            </span>
                          )}
                        </div>

                        <div className="flex flex-wrap items-center gap-2">
                          <label className="cursor-pointer rounded-xl border-2 border-b-4 border-cyan-500 bg-cyan-500 px-4 py-2 text-xs font-black text-white shadow-sm hover:bg-cyan-600 active:translate-y-0.5 active:border-b-2">
                            📁 {t("learning_paths.teacher.choose_audio_file")}
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
                            placeholder={t("learning_paths.teacher.or_audio_url")}
                            className="min-w-0 flex-1 rounded-xl border border-line bg-white p-2 text-xs dark:bg-slate-800 dark:border-slate-700 dark:text-white"
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
                          : t("learning_paths.teacher.question_prompt")
                      }
                      className="w-full rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500"
                    />

                    {/* Dynamic contextual inputs per test type */}
                    {manualType === "true_false" || manualType === "listening_tf" ? (
                      <div className="flex items-center gap-4 py-1">
                        <span className="text-xs font-black text-slate-700 dark:text-slate-300">{t("learning_paths.teacher.correct_answer")}:</span>
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
                          className="rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500"
                        />
                        <input
                          value={options}
                          onChange={(e) => setOptions(e.target.value)}
                          placeholder="Qo'shimcha noto'g'ri variantlar (ixtiyoriy, | bilan)"
                          className="rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500"
                        />
                      </div>
                    ) : manualType === "word_order" || manualType === "listening_order" ? (
                      <input
                        value={correct}
                        onChange={(e) => setCorrect(e.target.value)}
                        placeholder="To'g'ri tartibdagi to'liq gap: He is a teacher."
                        className="w-full rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500"
                      />
                    ) : manualType === "matching" ? (
                      <input
                        value={options}
                        onChange={(e) => setOptions(e.target.value)}
                        placeholder="Juftliklar: book = kitob | pen = ruchka | cat = mushuk (| bilan)"
                        className="w-full rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500"
                      />
                    ) : (
                      <div className="grid gap-2.5 sm:grid-cols-2">
                        <input
                          value={options}
                          onChange={(e) => setOptions(e.target.value)}
                          placeholder={`${t("learning_paths.teacher.options")}: A | B | C | D`}
                          className="rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500"
                        />
                        <input
                          value={correct}
                          onChange={(e) => setCorrect(e.target.value)}
                          placeholder={t("learning_paths.teacher.correct_answer")}
                          className="rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500"
                        />
                      </div>
                    )}

                    {/* Passage / Context if needed */}
                    {curKindMeta.needsPassage ? (
                      <div className="space-y-1">
                        <span className="text-[11px] font-black text-slate-500 dark:text-slate-400">
                          Matn / Passage (Reading & Listening context)
                        </span>
                        <textarea
                          value={passage}
                          onChange={(e) => setPassage(e.target.value)}
                          rows={4}
                          placeholder="Matn (Passage / Context)..."
                          className="w-full rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500"
                        />
                      </div>
                    ) : null}

                    {/* Rich contextual inputs: Hint, Direction, Word Count */}
                    <div className="grid gap-2 sm:grid-cols-3">
                      <input
                        value={direction}
                        onChange={(e) => setDirection(e.target.value)}
                        placeholder="Ko'rsatma / Direction (ixtiyoriy)"
                        className="rounded-2xl border-2 border-slate-200 bg-white p-2.5 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500"
                      />
                      <input
                        value={hint}
                        onChange={(e) => setHint(e.target.value)}
                        placeholder="Yordam / Hint (ixtiyoriy)"
                        className="rounded-2xl border-2 border-slate-200 bg-white p-2.5 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500"
                      />
                      {manualType === "guided_writing" || manualType === "essay" || manualType === "open_answer" || manualType === "reading_open" ? (
                        <input
                          type="number"
                          value={wordCount || ""}
                          onChange={(e) => setWordCount(Number(e.target.value) || 0)}
                          placeholder="So'zlar soni (Word count)"
                          className="rounded-2xl border-2 border-slate-200 bg-white p-2.5 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500"
                        />
                      ) : null}
                    </div>

                    <input
                      value={explanation}
                      onChange={(e) => setExplanation(e.target.value)}
                      placeholder={t("learning_paths.teacher.explanation")}
                      className="w-full rounded-2xl border-2 border-slate-200 bg-white p-3 text-xs font-bold text-navy-900 placeholder:text-slate-400 focus:border-purple-400 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500"
                    />

                    <div className="flex justify-end gap-2.5 pt-2">
                      <button
                        type="button"
                        onClick={() => setShowAddTestModal(false)}
                        className="rounded-xl border border-line px-4 py-2.5 text-xs font-bold text-ink-500 hover:bg-surface-soft dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800"
                      >
                        {t("learning_paths.teacher.cancel")}
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void saveManual()}
                        className="rounded-2xl border-2 border-b-4 border-purple-600 bg-purple-600 px-6 py-3 text-xs font-black uppercase tracking-wider text-white shadow-md transition-all active:translate-y-1 active:border-b-2 hover:bg-purple-700 disabled:opacity-40"
                      >
                        {t("learning_paths.teacher.manual_create_btn")}
                      </button>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>,
        document.body
      )}

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
  const t = useWebT();
  const [modalTab, setModalTab] = useState<"tree" | "materials">("tree");
  const [nodes, setNodes] = useState<LibTreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [selectedTest, setSelectedTest] = useState<LibTreeNode | null>(null);
  const [questionCount, setQuestionCount] = useState(0);
  const [takeAllQuestions, setTakeAllQuestions] = useState(true);

  // Materials Library Search State
  const [matItems, setMatItems] = useState<any[]>([]);
  const [matLoading, setMatLoading] = useState(false);
  const [matFilter, setMatFilter] = useState<string>("all");
  const [matQuery, setMatQuery] = useState("");
  const [selectedMatItem, setSelectedMatItem] = useState<any | null>(null);

  const loadTree = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch("/staff/teacher-library-tree");
      if (Array.isArray(data?.nodes)) {
        setNodes(data.nodes);
        const rootFolderIds = data.nodes.filter((n: LibTreeNode) => n.kind === "folder" && !n.parent_id).map((n: LibTreeNode) => n.id);
        setExpanded(new Set(rootFolderIds));
      }
    } catch {
      setNodes([]);
    } finally {
      setLoading(false);
    }
  }, [apiFetch]);

  const fetchMaterials = useCallback(async (q = "", filter = "all") => {
    setMatLoading(true);
    try {
      const typeParam = filter === "all" ? "" : filter;
      const res = await apiFetch(`/staff/materials-search?q=${encodeURIComponent(q)}&content_type=${typeParam}`);
      setMatItems(Array.isArray(res?.items) ? res.items : []);
    } catch {
      setMatItems([]);
    } finally {
      setMatLoading(false);
    }
  }, [apiFetch]);

  useEffect(() => {
    void loadTree();
  }, [loadTree]);

  useEffect(() => {
    if (modalTab === "materials") {
      void fetchMaterials(matQuery, matFilter);
    }
  }, [modalTab, matQuery, matFilter, fetchMaterials]);

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
            className="flex items-center gap-2 rounded-xl px-2 py-2 transition hover:bg-surface-soft dark:hover:bg-slate-800/40 cursor-pointer select-none"
            style={{ paddingLeft: depth * 18 + 8 }}
          >
            <span className="w-4 text-xs font-black text-ink-500 dark:text-slate-400">
              {isOpen ? "▾" : "▸"}
            </span>
            <span className="text-base">📁</span>
            <span className="font-bold text-xs text-navy-900 dark:text-white">
              {node.title}
            </span>
            <span className="ml-auto text-[10px] text-ink-400 dark:text-slate-400">
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
          setQuestionCount(node.question_count || (node.questions ? node.questions.length : 0));
          setTakeAllQuestions(true);
        }}
        className={`flex items-center gap-2 rounded-xl px-3 py-2 transition cursor-pointer my-0.5 ${
          isSelected
            ? "border-2 border-cyan-400 bg-cyan-500/15 shadow-sm dark:bg-cyan-950/30"
            : "hover:bg-cyan-500/5 dark:hover:bg-slate-800/40"
        }`}
        style={{ paddingLeft: depth * 18 + 24 }}
      >
        <span className="text-base">🧪</span>
        <div className="min-w-0 flex-1">
          <p className="font-bold text-xs text-navy-900 dark:text-white truncate">
            {node.title}
          </p>
          <p className="text-[10px] text-ink-400 dark:text-slate-400">
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
            setQuestionCount(node.question_count || (node.questions ? node.questions.length : 0));
            setTakeAllQuestions(true);
          }}
          className="accent-cyan-500"
        />
      </div>
    );
  };

  const roots = childrenOf.get(0) || [];

  if (typeof document === "undefined") return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[350] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-3xl bg-white shadow-2xl dark:bg-[#0f172a] border border-line dark:border-slate-800 animate-scale-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-line p-4 sm:p-5 dark:border-slate-800 dark:bg-[#090d16]/80">
          <div>
            <h3 className="text-lg font-black text-navy-900 dark:text-white flex items-center gap-2">
              <span>{t("learning_paths.teacher.materials_modal_title")}</span>
            </h3>
            <p className="text-xs text-ink-500 dark:text-slate-400 mt-0.5">
              {t("learning_paths.teacher.library_desc")}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-9 w-9 place-items-center rounded-full text-ink-500 hover:bg-rose-500/10 hover:text-rose-600 dark:text-slate-400 transition"
          >
            ✕
          </button>
        </div>

        {/* Dual Tab Bar */}
        <div className="flex border-b border-line bg-surface-soft/40 px-4 pt-2.5 dark:border-slate-800 dark:bg-[#090d16]/50 gap-2">
          <button
            type="button"
            onClick={() => setModalTab("tree")}
            className={`pb-2.5 px-3.5 text-xs font-black transition border-b-2 ${
              modalTab === "tree"
                ? "border-cyan-500 text-cyan-700 dark:text-cyan-300"
                : "border-transparent text-ink-500 hover:text-navy-900 dark:text-slate-400 dark:hover:text-white"
            }`}
          >
            {t("learning_paths.teacher.folders_tree")}
          </button>
          <button
            type="button"
            onClick={() => setModalTab("materials")}
            className={`pb-2.5 px-3.5 text-xs font-black transition border-b-2 ${
              modalTab === "materials"
                ? "border-cyan-500 text-cyan-700 dark:text-cyan-300"
                : "border-transparent text-ink-500 hover:text-navy-900 dark:text-slate-400 dark:hover:text-white"
            }`}
          >
            {t("learning_paths.teacher.materials_tab")}
          </button>
        </div>

        {modalTab === "tree" ? (
          <>
            {/* Search bar for tree */}
            <div className="p-4 border-b border-line dark:border-slate-800">
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t("learning_paths.teacher.search_placeholder")}
                className="w-full rounded-xl border border-line bg-surface-soft p-2.5 text-xs text-navy-900 placeholder:text-ink-400 focus:border-cyan-400 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500 font-medium"
              />
            </div>

            {/* Folder tree or Search results */}
            <div className="min-h-0 flex-1 overflow-y-auto p-4 space-y-1">
              {loading ? (
                <div className="grid min-h-48 place-items-center">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent" />
                </div>
              ) : filteredTests ? (
                filteredTests.length ? (
                  filteredTests.map((test) => {
                    const isSelected = selectedTest?.id === test.id;
                    return (
                      <div
                        key={test.id}
                        onClick={() => {
                          setSelectedTest(test);
                          setQuestionCount(test.question_count || 0);
                          setTakeAllQuestions(true);
                        }}
                        className={`flex items-center justify-between p-3 rounded-2xl border-2 transition cursor-pointer ${
                          isSelected
                            ? "border-cyan-400 bg-cyan-500/10 shadow-sm dark:bg-cyan-950/30"
                            : "border-line/60 hover:border-cyan-300 dark:border-slate-800 bg-white dark:bg-slate-800/40"
                        }`}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <span className="text-xl">🧪</span>
                          <div className="min-w-0">
                            <p className="font-bold text-xs text-navy-900 dark:text-white truncate">
                              {test.title}
                            </p>
                            <p className="text-[10px] text-ink-400 dark:text-slate-400">
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
                              setQuestionCount(test.question_count || 0);
                              setTakeAllQuestions(true);
                            }}
                            className="accent-cyan-500"
                          />
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <p className="py-12 text-center text-xs text-ink-500 dark:text-slate-400">
                    "{search}" bo'yicha hech qanday test topilmadi.
                  </p>
                )
              ) : roots.length ? (
                roots.map((node) => renderFolderNode(node, 0))
              ) : (
                <div className="py-12 text-center text-xs text-ink-500 dark:text-slate-400 space-y-2">
                  <p className="font-bold">Kutubxonada testlar topilmadi.</p>
                  <p className="text-[11px]">Avval Materiallar Kutubxonasi bo'limida papka va testlar yarating.</p>
                </div>
              )}
            </div>

            {selectedTest ? (
              <div className="border-t border-line bg-cyan-500/5 p-3.5 dark:border-slate-800 dark:bg-cyan-950/20">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-black text-cyan-800 dark:text-cyan-200 flex items-center gap-1.5">
                    <span>🧪 Tanlangan: {selectedTest.title}</span>
                  </span>
                  <span className="text-[11px] font-bold text-ink-500 dark:text-slate-400">
                    {selectedTest.question_count} ta savol mavjud
                  </span>
                </div>
              </div>
            ) : null}
          </>
        ) : (
          /* Materials Library Search View (Books, Videos, Homeworks) */
          <>
            <div className="p-4 border-b border-line dark:border-slate-800 space-y-2.5">
              {/* Type Filter Chips */}
              <div className="flex flex-wrap gap-1.5">
                {[
                  { key: "all", label: "Barchasi" },
                  { key: "book", label: "📖 Kitoblar" },
                  { key: "video", label: "🎬 Videolar" },
                  { key: "homework", label: "📝 Vazifalar" },
                  { key: "ai_generated", label: "✨ AI Testlar" },
                ].map((f) => (
                  <button
                    key={f.key}
                    type="button"
                    onClick={() => setMatFilter(f.key)}
                    className={`rounded-xl px-3 py-1 text-xs font-bold transition ${
                      matFilter === f.key
                        ? "bg-cyan-500 text-white shadow-sm"
                        : "bg-surface-soft text-ink-500 hover:bg-cyan-500/10 dark:bg-slate-800 dark:text-slate-300"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>

              <input
                value={matQuery}
                onChange={(e) => setMatQuery(e.target.value)}
                placeholder={t("learning_paths.teacher.search_materials")}
                className="w-full rounded-xl border border-line bg-surface-soft p-2.5 text-xs text-navy-900 placeholder:text-ink-400 focus:border-cyan-400 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500 font-medium"
              />
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto p-4 space-y-2">
              {matLoading ? (
                <div className="grid min-h-48 place-items-center">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent" />
                </div>
              ) : matItems.length ? (
                matItems.map((item, idx) => {
                  const isSel = selectedMatItem?.content_id === item.content_id && selectedMatItem?.content_type === item.content_type;
                  const typeIcon = item.content_type === "book" ? "📖" : item.content_type === "video" ? "🎬" : item.content_type === "homework" ? "📝" : "✨";
                  const typeLabel = item.content_type === "book" ? "Kitob" : item.content_type === "video" ? "Video" : item.content_type === "homework" ? "Vazifa" : "AI";

                  return (
                    <div
                      key={`${item.content_type}_${item.content_id}_${idx}`}
                      onClick={() => {
                        setSelectedMatItem(item);
                        setQuestionCount(item.question_count || 10);
                      }}
                      className={`flex items-center justify-between p-3.5 rounded-2xl border-2 transition cursor-pointer ${
                        isSel
                          ? "border-cyan-400 bg-cyan-500/10 shadow-sm dark:bg-cyan-950/30"
                          : "border-line/60 hover:border-cyan-300 dark:border-slate-800 bg-white dark:bg-slate-800/40"
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="text-xl">{typeIcon}</span>
                        <div className="min-w-0">
                          <p className="font-bold text-xs text-navy-900 dark:text-white truncate">
                            {item.title}
                          </p>
                          <span className="rounded-md bg-cyan-500/10 px-2 py-0.5 text-[10px] font-bold text-cyan-700 dark:text-cyan-300">
                            {typeLabel}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="rounded-full bg-cyan-500/15 px-2.5 py-0.5 text-xs font-black text-cyan-700 dark:text-cyan-300">
                          {item.question_count} ta savol
                        </span>
                        <input
                          type="radio"
                          name="mat_selected_test"
                          checked={isSel}
                          onChange={() => {
                            setSelectedMatItem(item);
                            setQuestionCount(item.question_count || 0);
                            setTakeAllQuestions(true);
                          }}
                          className="accent-cyan-500"
                        />
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="py-12 text-center text-xs text-ink-500 dark:text-slate-400">
                  Ushbu turkumda material testlari topilmadi.
                </div>
              )}
            </div>

            {selectedMatItem ? (
              <div className="border-t border-line bg-cyan-500/5 p-3.5 dark:border-slate-800 dark:bg-cyan-950/20">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-black text-cyan-800 dark:text-cyan-200">
                    🧪 Tanlangan: {selectedMatItem.title} ({selectedMatItem.content_type})
                  </span>
                  <span className="text-[11px] font-bold text-ink-500 dark:text-slate-400">
                    {selectedMatItem.question_count} ta savol mavjud
                  </span>
                </div>
              </div>
            ) : null}
          </>
        )}

        {/* Selected Test Action Footer */}
        <div className="border-t border-line p-4 dark:border-slate-800 bg-surface-soft/60 dark:bg-[#090d16]/80 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer select-none text-xs font-black text-navy-900 dark:text-white">
              <input
                type="checkbox"
                checked={takeAllQuestions}
                onChange={(e) => setTakeAllQuestions(e.target.checked)}
                className="h-4 w-4 rounded accent-cyan-500 cursor-pointer"
              />
              <span>
                Barcha savollarni olish ({selectedTest ? (selectedTest.question_count || "barcha") : (selectedMatItem?.question_count || "barcha")} ta)
              </span>
            </label>

            {!takeAllQuestions ? (
              <div className="flex items-center gap-2 animate-fade-in">
                <span className="text-xs font-bold text-ink-600 dark:text-slate-300">
                  miqdori:
                </span>
                <input
                  type="number"
                  min="1"
                  max="1000"
                  value={questionCount || 1}
                  onChange={(e) => setQuestionCount(Math.max(1, Number(e.target.value)))}
                  className="w-20 rounded-xl border border-line bg-white dark:bg-slate-800 p-2 text-xs font-bold text-center dark:border-slate-700 dark:text-white"
                />
              </div>
            ) : null}
          </div>

          <button
            type="button"
            disabled={modalTab === "tree" ? !selectedTest : !selectedMatItem}
            onClick={() => {
              const finalCount = takeAllQuestions ? 0 : questionCount;
              if (modalTab === "tree" && selectedTest) {
                onSelect(selectedTest.id, "library_node", finalCount);
              } else if (modalTab === "materials" && selectedMatItem) {
                onSelect(selectedMatItem.content_id, selectedMatItem.content_type, finalCount);
              }
            }}
            className="btn btn-primary text-xs py-2.5 px-6 font-bold disabled:opacity-40"
          >
            {t("learning_paths.teacher.attach_test_btn")}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

function CoverPicker({
  value,
  onChange,
  forbiddenKey,
  forbiddenKeys,
}: {
  value: string;
  onChange: (value: string) => void;
  forbiddenKey?: string | null;
  forbiddenKeys?: (string | null | undefined)[];
}) {
  const forbidden = useMemo(() => {
    const set = new Set<string>();
    if (forbiddenKey) set.add(forbiddenKey);
    if (Array.isArray(forbiddenKeys)) {
      forbiddenKeys.forEach((k) => {
        if (k) set.add(k);
      });
    }
    return set;
  }, [forbiddenKey, forbiddenKeys]);

  // Auto-switch to an allowed cover if current selection is forbidden
  useEffect(() => {
    if (forbidden.has(value)) {
      const allowed = covers.find((c) => !forbidden.has(c));
      if (allowed) onChange(allowed);
    }
  }, [value, forbidden, onChange]);

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-2.5">
        {covers.map((key) => {
          const isForbidden = forbidden.has(key);
          const isSelected = key === value;
          const label = COVER_LABELS[key] || key;

          return (
            <button
              type="button"
              key={key}
              disabled={isForbidden}
              onClick={() => {
                if (!isForbidden) onChange(key);
              }}
              title={
                isForbidden
                  ? `${label} (Ketma-ket bir xil rasm tanlash taqiqlangan)`
                  : `${label} rasmini tanlash`
              }
              className={`group relative h-12 w-12 overflow-hidden rounded-full border-2 transition-all select-none ${
                isSelected
                  ? "border-[#002DFF] ring-4 ring-[#002DFF]/30 scale-110 shadow-lg"
                  : isForbidden
                  ? "border-slate-300 opacity-25 cursor-not-allowed grayscale dark:border-navy-700"
                  : "border-slate-200 opacity-70 hover:opacity-100 hover:scale-105 dark:border-white/20"
              }`}
            >
              <img src={image(key)} alt={label} className="h-full w-full object-cover" />
              {isForbidden ? (
                <div className="absolute inset-0 grid place-items-center bg-slate-900/60 text-xs font-black text-white">
                  🚫
                </div>
              ) : isSelected ? (
                <div className="absolute bottom-0 inset-x-0 bg-[#002DFF]/85 py-0.5 text-[8px] font-black text-white text-center">
                  ✓
                </div>
              ) : null}
            </button>
          );
        })}
      </div>
      {forbidden.size > 0 ? (
        <p className="text-[11px] font-semibold text-slate-500 dark:text-navy-300">
          ℹ️ Qoidaga ko'ra ketma-ket ikkita modulda bir xil rasm bo'lishi mumkin emas.
        </p>
      ) : null}
    </div>
  );
}

function ModuleDetailModal({
  track,
  module,
  allModules,
  apiFetch,
  onSaved,
  onClose,
  initialOpenAddTest = false,
}: {
  track: Row;
  module: Row;
  allModules: Row[];
  apiFetch: ApiFetch;
  onSaved: () => Promise<void>;
  onClose: () => void;
  initialOpenAddTest?: boolean;
}) {
  const t = useWebT();
  const [modTitle, setModTitle] = useState(module.title || "");
  const [modTopics, setModTopics] = useState((module.topic_keys || []).join(", "));
  const [modRewardCoins, setModRewardCoins] = useState<number>(Number(module.reward_coins || 0));
  const [modCover, setModCover] = useState<string>(module.cover_key || "star");
  const [busy, setBusy] = useState(false);
  const [savedNotice, setSavedNotice] = useState(false);

  useEffect(() => {
    setModTitle(module.title || "");
    setModTopics((module.topic_keys || []).join(", "));
    setModRewardCoins(Number(module.reward_coins || 0));
    setModCover(module.cover_key || "star");
  }, [module]);

  const modIdx = allModules.findIndex((m) => m.id === module.id);
  const prevCover = modIdx > 0 ? allModules[modIdx - 1]?.cover_key : null;
  const nextCover = modIdx >= 0 && modIdx < allModules.length - 1 ? allModules[modIdx + 1]?.cover_key : null;
  const forbiddenEditKeys = [prevCover, nextCover].filter(Boolean) as string[];

  const saveModuleSettings = async () => {
    setBusy(true);
    try {
      await apiFetch(`/staff/learning-modules/${module.id}`, {
        method: "PATCH",
        body: {
          title: modTitle.trim(),
          topic_keys: modTopics.split(",").map((x) => x.trim()).filter(Boolean),
          reward_coins: Number(modRewardCoins),
          cover_key: modCover,
        },
      });
      setSavedNotice(true);
      setTimeout(() => setSavedNotice(false), 2500);
      await onSaved();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[250] flex items-center justify-center bg-black/75 p-3 sm:p-6 backdrop-blur-md overflow-hidden animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-5xl max-h-[94vh] flex flex-col rounded-3xl bg-white shadow-2xl dark:bg-[#0f172a] border border-line dark:border-slate-800 overflow-hidden animate-scale-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-line px-6 py-4 dark:border-slate-800 bg-surface-soft/60 dark:bg-[#090d16]/80">
          <div className="flex items-center gap-3.5 min-w-0">
            <img
              src={module.image_url || image(modCover)}
              alt=""
              className="h-11 w-11 rounded-full object-cover border-2 border-[#002DFF] shadow-sm shrink-0"
            />
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="font-black text-navy-900 dark:text-white text-base sm:text-lg truncate">
                  {module.title}
                </h2>
                <span className="rounded-xl bg-cyan-500/15 px-2.5 py-0.5 text-xs font-black text-cyan-700 dark:text-cyan-300">
                  Modul ID: #{module.id}
                </span>
                <span className="rounded-xl bg-indigo-500/15 px-2.5 py-0.5 text-xs font-black text-indigo-700 dark:text-indigo-300">
                  Track: {track.title}
                </span>
              </div>
              <p className="text-xs text-ink-500 dark:text-slate-400 mt-0.5 truncate">
                {t("learning_paths.teacher.module_params")}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="grid h-9 w-9 place-items-center rounded-full text-ink-500 hover:bg-rose-500/10 hover:text-rose-600 dark:text-slate-400 transition text-base font-bold"
            title={t("learning_paths.teacher.close")}
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 custom-scrollbar">
          {/* Module Settings Card */}
          <div className="rounded-2xl border border-line p-5 dark:border-slate-800 bg-surface-soft/40 dark:bg-[#090d16]/50 space-y-4">
            <div className="flex items-center justify-between border-b border-line pb-3 dark:border-slate-800">
              <h3 className="text-sm font-black text-navy-900 dark:text-white flex items-center gap-2">
                <span>⚙️ {t("learning_paths.teacher.module_params")}</span>
              </h3>
              {savedNotice ? (
                <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 animate-fade-in">
                  ✅ Saqlandi!
                </span>
              ) : null}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-bold text-ink-600 dark:text-slate-300">
                  {t("learning_paths.teacher.module_title")}
                </label>
                <input
                  value={modTitle}
                  onChange={(e) => setModTitle(e.target.value)}
                  className="w-full rounded-xl border border-line bg-white p-2.5 text-xs font-bold text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500"
                  placeholder={t("learning_paths.teacher.module_title")}
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-bold text-ink-600 dark:text-slate-300">
                  {t("learning_paths.teacher.topics")}
                </label>
                <input
                  value={modTopics}
                  onChange={(e) => setModTopics(e.target.value)}
                  className="w-full rounded-xl border border-line bg-white p-2.5 text-xs font-bold text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500"
                  placeholder="Present Simple, Fe'llar, So'z boyligi"
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 items-center">
              <div>
                <label className="mb-1 block text-xs font-bold text-ink-600 dark:text-slate-300">
                  {t("learning_paths.teacher.reward_coins")}:
                </label>
                <input
                  type="number"
                  min="0"
                  max="10000"
                  value={modRewardCoins}
                  onChange={(e) => setModRewardCoins(Number(e.target.value))}
                  className="w-full sm:w-48 rounded-xl border border-line bg-white p-2.5 text-xs font-bold text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                />
              </div>

              <div className="flex justify-end sm:pt-4">
                <button
                  type="button"
                  disabled={busy || !modTitle.trim()}
                  onClick={() => void saveModuleSettings()}
                  className="rounded-xl border-2 border-b-4 border-cyan-600 bg-cyan-600 px-5 py-2.5 text-xs font-black uppercase text-white shadow hover:bg-cyan-700 disabled:opacity-40 transition"
                >
                  {busy ? "..." : `💾 ${t("learning_paths.teacher.save_module")}`}
                </button>
              </div>
            </div>

            <div className="border-t border-line/40 pt-3 dark:border-slate-800">
              <p className="text-xs font-bold text-ink-500 dark:text-slate-400 mb-2">Modul belgisi (ikonka):</p>
              <CoverPicker
                value={modCover}
                onChange={setModCover}
                forbiddenKeys={forbiddenEditKeys}
              />
            </div>
          </div>

          {/* Test Questions and Lessons Editor */}
          <div className="rounded-2xl border border-line p-5 dark:border-slate-800 bg-white dark:bg-[#0f172a] shadow-xs">
            <h3 className="text-sm font-black text-navy-900 dark:text-white mb-4 flex items-center gap-2">
              <span>🎯 {t("learning_paths.teacher.tests_manager")}</span>
            </h3>
            <LessonEditor
              module={module}
              apiFetch={apiFetch}
              onSaved={onSaved}
              initialOpenAddTest={initialOpenAddTest}
            />
          </div>
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between border-t border-line px-6 py-3.5 dark:border-slate-800 bg-surface-soft/40 dark:bg-[#090d16]/80">
          <span className="text-xs font-bold text-ink-500 dark:text-slate-400">
            {t("learning_paths.teacher.lessons_in_module", { count: (module.lessons || []).length })}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="btn btn-primary text-xs py-2 px-5 font-bold"
          >
            {t("learning_paths.teacher.close")}
          </button>
        </div>
      </div>
    </div>
  );
}

