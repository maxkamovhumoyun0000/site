"use client";

import { useEffect, useRef, useState } from "react";

export interface CompletedSessionItem {
  id: number;
  mode: string;
  duration_minutes: number;
  planned_seconds: number;
  completed_seconds: number;
  completed_at: string;
  created_at: string;
  completed: boolean;
}

export interface PomodoroSessionsResponse {
  sessions: CompletedSessionItem[];
  today_count: number;
  today_minutes: number;
  week_seconds: number;
  week_sessions: number;
}

export interface PomodoroStudioProps {
  apiFetch?: (url: string, options?: RequestInit) => Promise<unknown>;
  role?: "student" | "teacher" | "support";
  initialSummary?: { week_seconds?: number; sessions?: number };
}

function playCompletionChime() {
  if (typeof window === "undefined") return;
  try {
    const AudioCtx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const totalBeeps = 5;
    const beepInterval = 0.8;
    for (let i = 0; i < totalBeeps; i++) {
      const t = ctx.currentTime + i * beepInterval;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(i % 2 === 0 ? 880 : 1046.5, t);
      gain.gain.setValueAtTime(0, t);
      gain.gain.linearRampToValueAtTime(0.3, t + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.35);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.38);
    }
  } catch {
    // Audio context may be restricted
  }
}

export function PomodoroFocusStudio({
  apiFetch,
  role = "student",
  initialSummary,
}: PomodoroStudioProps) {
  const [totalSeconds, setTotalSeconds] = useState(25 * 60);
  const [secondsLeft, setSecondsLeft] = useState(25 * 60);
  const [isRunning, setIsRunning] = useState(false);
  const [isEditingTime, setIsEditingTime] = useState(false);
  const [editMinutesInput, setEditMinutesInput] = useState("25");
  const [editSecondsInput, setEditSecondsInput] = useState("00");

  const [completedSessions, setCompletedSessions] = useState<CompletedSessionItem[]>([]);
  const [todayCount, setTodayCount] = useState(0);
  const [todayMinutes, setTodayMinutes] = useState(0);
  const [weekSeconds, setWeekSeconds] = useState(initialSummary?.week_seconds || 0);
  const [weekSessions, setWeekSessions] = useState(initialSummary?.sessions || 0);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const prefix = role === "student" ? "/student" : "/staff";

  // Load custom timer duration from localStorage
  useEffect(() => {
    try {
      const savedDuration = localStorage.getItem("diamond_pomodoro_duration_sec");
      if (savedDuration) {
        const val = parseInt(savedDuration, 10);
        if (!isNaN(val) && val > 0 && val <= 86400) {
          setTotalSeconds(val);
          setSecondsLeft(val);
          setEditMinutesInput(String(Math.floor(val / 60)));
          setEditSecondsInput(String(val % 60).padStart(2, "0"));
        }
      }
    } catch {
      // LocalStorage access fallback
    }
  }, []);

  // Fetch completed sessions from backend
  const fetchSessions = async () => {
    if (!apiFetch) return;
    setIsLoadingSessions(true);
    try {
      const res = (await apiFetch(`${prefix}/pomodoro/sessions`)) as PomodoroSessionsResponse;
      if (res && Array.isArray(res.sessions)) {
        setCompletedSessions(res.sessions);
        setTodayCount(res.today_count || 0);
        setTodayMinutes(res.today_minutes || 0);
        setWeekSeconds(res.week_seconds || 0);
        setWeekSessions(res.week_sessions || 0);
      }
    } catch {
      // Offline fallback
    } finally {
      setIsLoadingSessions(false);
    }
  };

  useEffect(() => {
    void fetchSessions();
  }, [prefix]);

  // Handle timer completion
  const handleComplete = async () => {
    setIsRunning(false);
    playCompletionChime();
    setNotice("🎉 Ajoyib natija! Pomodoro fokus sessiyasi muvaffaqiyatli yakunlandi.");

    const durationMin = Math.max(1, Math.round(totalSeconds / 60));
    const nowIso = new Date().toISOString();

    // Optimistic update
    const optimisticSession: CompletedSessionItem = {
      id: Date.now(),
      mode: "work",
      duration_minutes: durationMin,
      planned_seconds: totalSeconds,
      completed_seconds: totalSeconds,
      completed_at: nowIso,
      created_at: nowIso,
      completed: true,
    };
    setCompletedSessions((prev) => [optimisticSession, ...prev]);
    setTodayCount((c) => c + 1);
    setTodayMinutes((m) => m + durationMin);
    setWeekSeconds((w) => w + totalSeconds);
    setWeekSessions((s) => s + 1);

    // Save to backend
    if (apiFetch) {
      try {
        await apiFetch(`${prefix}/pomodoro/sessions`, {
          method: "POST",
          body: JSON.stringify({
            mode: "work",
            planned_seconds: totalSeconds,
            completed_seconds: totalSeconds,
            completed: true,
          }),
        });
        await fetchSessions();
      } catch {
        // Fallback
      }
    }

    setSecondsLeft(totalSeconds);
  };

  // Timer interval
  useEffect(() => {
    if (isRunning) {
      timerRef.current = setInterval(() => {
        setSecondsLeft((prev) => {
          if (prev <= 1) {
            void handleComplete();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isRunning, totalSeconds]);

  // Toggle Start / Pause
  const toggleRunning = () => {
    if (isEditingTime) {
      applyEditTime();
    }
    setIsRunning((r) => !r);
  };

  // Reset
  const handleReset = () => {
    setIsRunning(false);
    setSecondsLeft(totalSeconds);
  };

  // Apply edited time
  const applyEditTime = () => {
    let m = parseInt(editMinutesInput, 10);
    let s = parseInt(editSecondsInput, 10);
    if (isNaN(m) || m < 0) m = 0;
    if (isNaN(s) || s < 0) s = 0;
    if (m === 0 && s === 0) m = 25;
    const newSec = m * 60 + s;
    setTotalSeconds(newSec);
    setSecondsLeft(newSec);
    setIsEditingTime(false);
    try {
      localStorage.setItem("diamond_pomodoro_duration_sec", String(newSec));
    } catch {
      // LocalStorage access fallback
    }
  };

  // Delete session
  const handleDeleteSession = async (sessionId: number) => {
    setCompletedSessions((prev) => prev.filter((s) => s.id !== sessionId));
    if (apiFetch) {
      try {
        await apiFetch(`${prefix}/pomodoro/sessions/${sessionId}`, { method: "DELETE" });
        await fetchSessions();
      } catch {
        // Fallback
      }
    }
  };

  // Format display digits
  const displayMinutes = String(Math.floor(secondsLeft / 60)).padStart(2, "0");
  const displaySeconds = String(secondsLeft % 60).padStart(2, "0");
  const progressRatio = totalSeconds > 0 ? (totalSeconds - secondsLeft) / totalSeconds : 0;
  const strokeDash = Math.round(progressRatio * 283);

  // Format timestamp helper
  const formatTimestamp = (dateStr: string) => {
    if (!dateStr) return "Yaqinda";
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      const today = new Date();
      const isToday =
        d.getDate() === today.getDate() &&
        d.getMonth() === today.getMonth() &&
        d.getFullYear() === today.getFullYear();
      const timeStr = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
      if (isToday) return `Bugun, ${timeStr}`;
      const day = String(d.getDate()).padStart(2, "0");
      const month = String(d.getMonth() + 1).padStart(2, "0");
      return `${day}.${month}.${d.getFullYear()}, ${timeStr}`;
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="w-full space-y-6">
      {/* Notice Banner */}
      {notice && (
        <div className="flex items-center justify-between rounded-2xl bg-cyan-500/15 border border-cyan-500/30 p-3.5 text-xs font-bold text-cyan-800 dark:text-cyan-200 shadow-sm animate-fade-in">
          <span>{notice}</span>
          <button
            type="button"
            onClick={() => setNotice(null)}
            className="ml-2 hover:opacity-80 p-1"
          >
            ✕
          </button>
        </div>
      )}

      {/* Main Minimalist Timer Card */}
      <div className="relative overflow-hidden rounded-3xl bg-white dark:bg-navy-900 border border-line dark:border-white/10 shadow-premium p-6 sm:p-8 flex flex-col items-center justify-center">
        <div className="absolute -right-16 -top-16 h-60 w-60 rounded-full blur-3xl bg-[#1E56CC]/15 pointer-events-none" />
        <div className="absolute -left-16 -bottom-16 h-60 w-60 rounded-full blur-3xl bg-cyan-500/15 pointer-events-none" />

        <div className="w-full flex items-center justify-between pb-3 border-b border-line dark:border-white/10 mb-6">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-2xl bg-[#1E56CC]/10 text-lg">
              ⏱️
            </span>
            <div>
              <h2 className="text-lg font-black text-navy-900 dark:text-white">Pomodoro Taymer</h2>
              <p className="text-xs text-ink-500 dark:text-navy-300">
                Vaqtni o'zgartirish uchun raqam ustiga bosing
              </p>
            </div>
          </div>
          <span className="rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 px-3 py-1 text-xs font-bold flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            Sinxronlangan
          </span>
        </div>

        {/* Circular Dial with Direct Editable Digits */}
        <div className="relative w-64 h-64 sm:w-72 sm:h-72 flex items-center justify-center my-2">
          <svg className="absolute inset-0 -rotate-90" width="100%" height="100%" viewBox="0 0 100 100">
            <circle
              cx="50"
              cy="50"
              r="44"
              fill="none"
              stroke="currentColor"
              strokeWidth="5"
              className="text-gray-200 dark:text-navy-800"
            />
            <circle
              cx="50"
              cy="50"
              r="44"
              fill="none"
              stroke="url(#timerGradientWeb)"
              strokeWidth="5"
              strokeDasharray={`${strokeDash} 283`}
              strokeLinecap="round"
              className="transition-all duration-1000 ease-linear"
            />
            <defs>
              <linearGradient id="timerGradientWeb" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#0B2A6B" />
                <stop offset="100%" stopColor="#1E56CC" />
              </linearGradient>
            </defs>
          </svg>

          <div className="text-center z-10 flex flex-col items-center">
            {isEditingTime ? (
              <div className="flex flex-col items-center gap-2 p-2 bg-gray-50 dark:bg-navy-800 rounded-2xl border border-line dark:border-white/10 shadow-lg">
                <div className="flex items-center gap-1 text-4xl font-mono font-black text-navy-900 dark:text-white">
                  <input
                    type="number"
                    min="0"
                    max="180"
                    value={editMinutesInput}
                    onChange={(e) => setEditMinutesInput(e.target.value)}
                    className="w-16 text-center rounded-xl bg-white dark:bg-navy-900 border border-line dark:border-white/20 p-1 focus:outline-none focus:border-[#1E56CC]"
                    autoFocus
                  />
                  <span>:</span>
                  <input
                    type="number"
                    min="0"
                    max="59"
                    value={editSecondsInput}
                    onChange={(e) => setEditSecondsInput(e.target.value)}
                    className="w-16 text-center rounded-xl bg-white dark:bg-navy-900 border border-line dark:border-white/20 p-1 focus:outline-none focus:border-[#1E56CC]"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={applyEditTime}
                    className="px-3 py-1 rounded-xl bg-[#1E56CC] text-white text-xs font-bold hover:bg-[#1542a3] transition"
                  >
                    ✓ Saqlash
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsEditingTime(false)}
                    className="px-3 py-1 rounded-xl bg-gray-200 dark:bg-white/10 text-ink-700 dark:text-white text-xs font-bold hover:opacity-80 transition"
                  >
                    Bekor
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => {
                  if (!isRunning) {
                    setEditMinutesInput(String(Math.floor(secondsLeft / 60)));
                    setEditSecondsInput(String(secondsLeft % 60).padStart(2, "0"));
                    setIsEditingTime(true);
                  }
                }}
                title={isRunning ? "Vaqtni o'zgartirish uchun avval pauza qiling" : "Vaqtni o'zgartirish uchun bosing"}
                className={`group flex flex-col items-center rounded-2xl p-2 transition hover:bg-black/5 dark:hover:bg-white/5 ${
                  isRunning ? "cursor-default" : "cursor-pointer"
                }`}
              >
                <span
                  className={`text-6xl sm:text-7xl font-mono font-black tracking-tight text-navy-900 dark:text-white transition group-hover:scale-105 ${
                    isRunning ? "animate-pulse text-[#1E56CC] dark:text-[#7EB3FF]" : ""
                  }`}
                >
                  {displayMinutes}:{displaySeconds}
                </span>
                {!isRunning && (
                  <span className="mt-1 text-2xs font-bold text-ink-400 dark:text-navy-400 group-hover:text-[#1E56CC] dark:group-hover:text-[#7EB3FF] flex items-center gap-1">
                    ✏️ Tahrirlash
                  </span>
                )}
              </button>
            )}

            <span className="mt-2 rounded-full bg-[#1E56CC]/10 dark:bg-[#1E56CC]/20 px-3 py-0.5 text-xs font-bold text-[#1E56CC] dark:text-[#7EB3FF]">
              {isRunning ? "⚡ Taymer ishlamoqda" : "Diqqat vaqti"}
            </span>
          </div>
        </div>

        {/* 3 Main Action Buttons: Start/Stop, Reset, Time Edit */}
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          <button
            type="button"
            onClick={toggleRunning}
            className={`min-w-36 px-8 py-3.5 rounded-2xl font-black text-base text-white shadow-xl transition-all transform hover:scale-105 active:scale-95 flex items-center justify-center gap-2 ${
              isRunning
                ? "bg-amber-500 hover:bg-amber-600 shadow-amber-500/25"
                : "bg-gradient-to-r from-[#0B2A6B] to-[#1E56CC] hover:from-[#081e4d] hover:to-[#1744a4] shadow-blue-500/25"
            }`}
          >
            {isRunning ? "⏸ Pauza" : "▶ Boshlash"}
          </button>

          <button
            type="button"
            onClick={handleReset}
            className="px-5 py-3.5 rounded-2xl border border-line dark:border-white/10 bg-surface-soft dark:bg-white/5 text-ink-700 dark:text-navy-200 hover:bg-black/5 dark:hover:bg-white/10 font-bold text-sm transition flex items-center gap-1.5"
            title="Qayta o'rnatish"
          >
            ↺ Reset
          </button>

          <button
            type="button"
            onClick={() => {
              if (isRunning) setIsRunning(false);
              setEditMinutesInput(String(Math.floor(totalSeconds / 60)));
              setEditSecondsInput(String(totalSeconds % 60).padStart(2, "0"));
              setIsEditingTime(true);
            }}
            className="px-5 py-3.5 rounded-2xl border border-line dark:border-white/10 bg-surface-soft dark:bg-white/5 text-ink-700 dark:text-navy-200 hover:bg-black/5 dark:hover:bg-white/10 font-bold text-sm transition flex items-center gap-1.5"
            title="Vaqtni o'zgartirish"
          >
            ⏱️ {Math.floor(totalSeconds / 60)} daq
          </button>
        </div>
      </div>

      {/* Expanded Completed Sessions Section */}
      <div className="rounded-3xl bg-white dark:bg-navy-900 border border-line dark:border-white/10 shadow-premium p-6 sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-line dark:border-white/10">
          <div>
            <h3 className="text-lg font-black text-navy-900 dark:text-white flex items-center gap-2">
              🏆 Tugatilgan Sessiyalar
              <span className="rounded-full bg-[#1E56CC]/10 px-2.5 py-0.5 text-xs font-bold text-[#1E56CC] dark:text-[#7EB3FF]">
                {completedSessions.length} ta
              </span>
            </h3>
            <p className="text-xs text-ink-500 dark:text-navy-300 mt-0.5">
              Ilova va sayt o'rtasida to'liq sinxronlangan natijalar
            </p>
          </div>
          <button
            type="button"
            onClick={() => void fetchSessions()}
            disabled={isLoadingSessions}
            className="rounded-xl border border-line dark:border-white/10 px-3.5 py-1.5 text-xs font-bold text-ink-700 dark:text-navy-200 hover:bg-black/5 dark:hover:bg-white/5 transition flex items-center gap-1.5 disabled:opacity-50"
          >
            {isLoadingSessions ? "Yangilanmoqda..." : "🔄 Yangilash"}
          </button>
        </div>

        {/* Aggregate Stats Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 my-5">
          <div className="rounded-2xl bg-surface-soft dark:bg-white/5 p-4 border border-line dark:border-white/5 text-center">
            <span className="text-2xl font-black text-[#1E56CC] dark:text-[#7EB3FF] block">
              {todayCount}
            </span>
            <span className="text-2xs font-bold uppercase tracking-wider text-ink-500 dark:text-navy-300">
              Bugungi sessiyalar
            </span>
          </div>

          <div className="rounded-2xl bg-surface-soft dark:bg-white/5 p-4 border border-line dark:border-white/5 text-center">
            <span className="text-2xl font-black text-emerald-500 block">
              {todayMinutes}m
            </span>
            <span className="text-2xs font-bold uppercase tracking-wider text-ink-500 dark:text-navy-300">
              Bugungi fokus
            </span>
          </div>

          <div className="rounded-2xl bg-surface-soft dark:bg-white/5 p-4 border border-line dark:border-white/5 text-center">
            <span className="text-2xl font-black text-cyan-500 block">
              {Math.round(weekSeconds / 60)}m
            </span>
            <span className="text-2xs font-bold uppercase tracking-wider text-ink-500 dark:text-navy-300">
              Haftalik vaqt
            </span>
          </div>

          <div className="rounded-2xl bg-surface-soft dark:bg-white/5 p-4 border border-line dark:border-white/5 text-center">
            <span className="text-2xl font-black text-purple-500 block">
              {weekSessions || completedSessions.length}
            </span>
            <span className="text-2xs font-bold uppercase tracking-wider text-ink-500 dark:text-navy-300">
              Jami yakunlangan
            </span>
          </div>
        </div>

        {/* Detailed Session List */}
        <div className="space-y-2.5">
          {completedSessions.length > 0 ? (
            completedSessions.map((item, idx) => (
              <div
                key={item.id || idx}
                className="group flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-surface-soft/60 dark:bg-white/5 hover:bg-surface-soft dark:hover:bg-white/10 p-3.5 border border-line dark:border-white/5 transition"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-black text-sm">
                    ✓
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-navy-900 dark:text-white">
                        {item.duration_minutes} daqiqa fokus
                      </span>
                      <span className="rounded-md bg-emerald-500/10 px-2 py-0.5 text-2xs font-bold text-emerald-600 dark:text-emerald-400">
                        Yakunlandi
                      </span>
                    </div>
                    <span className="text-xs text-ink-400 dark:text-navy-400">
                      {formatTimestamp(item.completed_at || item.created_at)}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-medium text-ink-500 dark:text-navy-300">
                    +{item.duration_minutes} min
                  </span>
                  <button
                    type="button"
                    onClick={() => handleDeleteSession(item.id)}
                    className="opacity-0 group-hover:opacity-100 text-ink-400 hover:text-rose-500 p-1 transition"
                    title="O'chirish"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))
          ) : (
            <div className="py-12 text-center rounded-2xl bg-surface-soft/40 dark:bg-white/5 border border-dashed border-line dark:border-white/10">
              <span className="text-4xl block mb-2">🌱</span>
              <p className="text-sm font-bold text-navy-900 dark:text-white">
                Hozircha tugatilgan sessiyalar yo'q
              </p>
              <p className="text-xs text-ink-400 mt-1 max-w-sm mx-auto">
                Taymerni ishga tushiring va belgilangan vaqt to'lgach, sessiyangiz avtomatik tarzda bu yerda aks etadi.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function PomodoroWidget() {
  const [seconds, setSeconds] = useState(25 * 60);
  const [running, setRunning] = useState(false);
  const ref = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (running) {
      ref.current = setInterval(() => {
        setSeconds((s) => {
          if (s <= 1) {
            setRunning(false);
            playCompletionChime();
            return 0;
          }
          return s - 1;
        });
      }, 1000);
    } else if (ref.current) {
      clearInterval(ref.current);
    }
    return () => {
      if (ref.current) clearInterval(ref.current);
    };
  }, [running]);

  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");

  return (
    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-100 dark:bg-gray-800 text-sm font-mono font-semibold text-gray-800 dark:text-gray-200">
      <span>🍅</span>
      <span>
        {mm}:{ss}
      </span>
      <button
        type="button"
        onClick={() => setRunning((r) => !r)}
        className="text-xs px-2 py-0.5 rounded-full bg-red-500 text-white hover:bg-red-600 transition"
      >
        {running ? "⏸" : "▶"}
      </button>
    </div>
  );
}
