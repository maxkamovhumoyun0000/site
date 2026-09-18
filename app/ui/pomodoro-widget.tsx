"use client";

import { useEffect, useRef, useState } from "react";

export type PomodoroMode = "work" | "short_break" | "long_break";

export interface PomodoroTask {
  id: string;
  text: string;
  done: boolean;
  pomodoros: number;
}

export interface DistractionNote {
  id: string;
  text: string;
  time: string;
}

export interface PomodoroSettings {
  workMinutes: number;
  shortBreakMinutes: number;
  longBreakMinutes: number;
  autoStartBreaks: boolean;
  autoStartFocus: boolean;
  ambientSound: "none" | "rain" | "ocean" | "forest" | "cafe" | "binaural";
  volume: number;
  tickSound: boolean;
}

const DEFAULT_SETTINGS: PomodoroSettings = {
  workMinutes: 25,
  shortBreakMinutes: 5,
  longBreakMinutes: 15,
  autoStartBreaks: false,
  autoStartFocus: false,
  ambientSound: "none",
  volume: 0.5,
  tickSound: false,
};

// Web Audio Ambient Synthesizer
class AmbientAudioEngine {
  private ctx: AudioContext | null = null;
  private noiseNode: AudioNode | null = null;
  private gainNode: GainNode | null = null;
  private oscillators: OscillatorNode[] = [];
  private lfo: OscillatorNode | null = null;

  private initCtx() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.ctx = new AudioCtx();
    }
    if (this.ctx.state === "suspended") {
      void this.ctx.resume();
    }
  }

  playChime() {
    try {
      this.initCtx();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;
      const freqs = [528, 660, 792, 1056]; // Solfeggio / harmonious chime
      freqs.forEach((f, i) => {
        if (!this.ctx) return;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(f, now + i * 0.08);
        gain.gain.setValueAtTime(0.25 / (i + 1), now + i * 0.08);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 1.8 + i * 0.2);
        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start(now + i * 0.08);
        osc.stop(now + 2.5);
      });
    } catch {
      // Audio not permitted or unsupported
    }
  }

  playTick() {
    try {
      this.initCtx();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = "triangle";
      osc.frequency.setValueAtTime(1200, now);
      gain.gain.setValueAtTime(0.02, now);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.03);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(now);
      osc.stop(now + 0.04);
    } catch {
      // Safe fallback
    }
  }

  setAmbient(type: PomodoroSettings["ambientSound"], volume: number) {
    this.stopAmbient();
    if (type === "none" || volume <= 0) return;

    try {
      this.initCtx();
      if (!this.ctx) return;

      this.gainNode = this.ctx.createGain();
      this.gainNode.gain.setValueAtTime(volume * 0.4, this.ctx.currentTime);
      this.gainNode.connect(this.ctx.destination);

      if (type === "binaural") {
        // 432Hz deep focus alpha drone (432Hz + 440Hz -> 8Hz alpha wave)
        const osc1 = this.ctx.createOscillator();
        const osc2 = this.ctx.createOscillator();
        const pan1 = this.ctx.createStereoPanner ? this.ctx.createStereoPanner() : null;
        const pan2 = this.ctx.createStereoPanner ? this.ctx.createStereoPanner() : null;

        osc1.type = "sine";
        osc1.frequency.setValueAtTime(216, this.ctx.currentTime);
        osc2.type = "sine";
        osc2.frequency.setValueAtTime(224, this.ctx.currentTime);

        if (pan1 && pan2) {
          pan1.pan.setValueAtTime(-0.8, this.ctx.currentTime);
          pan2.pan.setValueAtTime(0.8, this.ctx.currentTime);
          osc1.connect(pan1);
          pan1.connect(this.gainNode);
          osc2.connect(pan2);
          pan2.connect(this.gainNode);
        } else {
          osc1.connect(this.gainNode);
          osc2.connect(this.gainNode);
        }

        osc1.start();
        osc2.start();
        this.oscillators = [osc1, osc2];
        return;
      }

      // Noise generator for rain, ocean, cafe, forest
      const bufferSize = this.ctx.sampleRate * 2;
      const noiseBuffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
      const output = noiseBuffer.getChannelData(0);
      let b0 = 0, b1 = 0, b2 = 0;
      for (let i = 0; i < bufferSize; i++) {
        const white = Math.random() * 2 - 1;
        // Pink noise approximation
        b0 = 0.99886 * b0 + white * 0.0555179;
        b1 = 0.99332 * b1 + white * 0.0750759;
        b2 = 0.96900 * b2 + white * 0.1538520;
        output[i] = (b0 + b1 + b2 + white * 0.5362) * 0.11;
      }

      const whiteNoise = this.ctx.createBufferSource();
      whiteNoise.buffer = noiseBuffer;
      whiteNoise.loop = true;

      const filter = this.ctx.createBiquadFilter();

      if (type === "rain") {
        filter.type = "lowpass";
        filter.frequency.setValueAtTime(950, this.ctx.currentTime);
      } else if (type === "ocean") {
        filter.type = "lowpass";
        filter.frequency.setValueAtTime(450, this.ctx.currentTime);

        // LFO for rhythmic waves
        this.lfo = this.ctx.createOscillator();
        const lfoGain = this.ctx.createGain();
        this.lfo.frequency.setValueAtTime(0.12, this.ctx.currentTime); // Wave every 8s
        lfoGain.gain.setValueAtTime(320, this.ctx.currentTime);
        this.lfo.connect(lfoGain);
        lfoGain.connect(filter.frequency);
        this.lfo.start();
      } else if (type === "forest") {
        filter.type = "bandpass";
        filter.frequency.setValueAtTime(700, this.ctx.currentTime);
        filter.Q.setValueAtTime(1.8, this.ctx.currentTime);
      } else if (type === "cafe") {
        filter.type = "lowpass";
        filter.frequency.setValueAtTime(600, this.ctx.currentTime);
      }

      whiteNoise.connect(filter);
      filter.connect(this.gainNode);
      whiteNoise.start();
      this.noiseNode = whiteNoise;
    } catch {
      // Audio not permitted
    }
  }

  setVolume(vol: number) {
    if (this.gainNode && this.ctx) {
      this.gainNode.gain.setValueAtTime(vol * 0.4, this.ctx.currentTime);
    }
  }

  stopAmbient() {
    try {
      if (this.noiseNode && "stop" in this.noiseNode) {
        (this.noiseNode as AudioScheduledSourceNode).stop();
        this.noiseNode.disconnect();
      }
      this.noiseNode = null;
      if (this.lfo) {
        this.lfo.stop();
        this.lfo.disconnect();
        this.lfo = null;
      }
      this.oscillators.forEach(o => {
        try { o.stop(); o.disconnect(); } catch { /* noop */ }
      });
      this.oscillators = [];
    } catch {
      // Ignore cleanup error
    }
  }
}

const audioEngine = typeof window !== "undefined" ? new AmbientAudioEngine() : null;

export interface PomodoroStudioProps {
  apiFetch?: (url: string, options?: RequestInit) => Promise<unknown>;
  role?: "student" | "teacher" | "support";
  initialSummary?: { week_seconds?: number; sessions?: number };
}

export function PomodoroFocusStudio({ apiFetch, role = "student", initialSummary }: PomodoroStudioProps) {
  const [settings, setSettings] = useState<PomodoroSettings>(DEFAULT_SETTINGS);
  const [mode, setMode] = useState<PomodoroMode>("work");
  const [secondsLeft, setSecondsLeft] = useState(DEFAULT_SETTINGS.workMinutes * 60);
  const [isRunning, setIsRunning] = useState(false);
  const [cyclesCompleted, setCyclesCompleted] = useState(0);
  const [todayCompletedCount, setTodayCompletedCount] = useState(0);
  const [todayFocusMinutes, setTodayFocusMinutes] = useState(0);
  const [weekSummary, setWeekSummary] = useState(initialSummary || { week_seconds: 0, sessions: 0 });
  const [currentGoal, setCurrentGoal] = useState("");
  const [tasks, setTasks] = useState<PomodoroTask[]>([]);
  const [newTaskText, setNewTaskText] = useState("");
  const [distractions, setDistractions] = useState<DistractionNote[]>([]);
  const [newDistraction, setNewDistraction] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [showTips, setShowTips] = useState(false);
  const [isZenMode, setIsZenMode] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const prefix = role === "student" ? "/student" : "/staff";

  // Load saved state from localStorage
  useEffect(() => {
    try {
      const savedSettings = localStorage.getItem("diamond_pomodoro_settings");
      if (savedSettings) setSettings(prev => ({ ...prev, ...JSON.parse(savedSettings) }));

      const savedGoal = localStorage.getItem("diamond_pomodoro_goal");
      if (savedGoal) setCurrentGoal(savedGoal);

      const savedTasks = localStorage.getItem("diamond_pomodoro_tasks");
      if (savedTasks) setTasks(JSON.parse(savedTasks));

      const savedDistractions = localStorage.getItem("diamond_pomodoro_distractions");
      if (savedDistractions) setDistractions(JSON.parse(savedDistractions));

      const savedToday = localStorage.getItem("diamond_pomodoro_today");
      if (savedToday) {
        const parsed = JSON.parse(savedToday);
        const todayStr = new Date().toDateString();
        if (parsed.date === todayStr) {
          setTodayCompletedCount(parsed.count || 0);
          setTodayFocusMinutes(parsed.minutes || 0);
        }
      }
    } catch {
      // Storage access fail safe
    }
  }, []);

  // Save settings when changed
  const updateSettings = (partial: Partial<PomodoroSettings>) => {
    setSettings(prev => {
      const updated = { ...prev, ...partial };
      try {
        localStorage.setItem("diamond_pomodoro_settings", JSON.stringify(updated));
      } catch { /* noop */ }
      return updated;
    });
  };

  // Sync mode duration to seconds
  const getModeTotalSeconds = (m: PomodoroMode = mode) => {
    if (m === "work") return settings.workMinutes * 60;
    if (m === "short_break") return settings.shortBreakMinutes * 60;
    return settings.longBreakMinutes * 60;
  };

  // Switch phase
  const switchMode = (newMode: PomodoroMode, autoStart = false) => {
    setIsRunning(false);
    setMode(newMode);
    setSecondsLeft(getModeTotalSeconds(newMode));
    if (autoStart) {
      setTimeout(() => setIsRunning(true), 250);
    }
  };

  // Handle timer completion
  const handlePhaseComplete = async () => {
    audioEngine?.playChime();

    if (mode === "work") {
      const earnedMins = settings.workMinutes;
      const newCycles = cyclesCompleted + 1;
      const newTodayCount = todayCompletedCount + 1;
      const newTodayMins = todayFocusMinutes + earnedMins;

      setCyclesCompleted(newCycles);
      setTodayCompletedCount(newTodayCount);
      setTodayFocusMinutes(newTodayMins);

      try {
        localStorage.setItem(
          "diamond_pomodoro_today",
          JSON.stringify({ date: new Date().toDateString(), count: newTodayCount, minutes: newTodayMins })
        );
      } catch { /* noop */ }

      // Save to backend if available
      if (apiFetch) {
        try {
          await apiFetch(`${prefix}/pomodoro/sessions`, {
            method: "POST",
            body: JSON.stringify({
              mode: "work",
              planned_seconds: settings.workMinutes * 60,
              completed_seconds: settings.workMinutes * 60,
              completed: true,
            }),
          });
          const summaryRes = await apiFetch(`${prefix}/pomodoro/summary`);
          if (summaryRes && typeof summaryRes === "object") {
            setWeekSummary(summaryRes as { week_seconds?: number; sessions?: number });
          }
        } catch {
          // Offline fallback
        }
      }

      setNotice("🎉 Ajoyib natija! 25 daqiqa to'liq diqqat yakunlandi.");

      // Switch to long break after every 4 cycles, else short break
      if (newCycles % 4 === 0) {
        switchMode("long_break", settings.autoStartBreaks);
      } else {
        switchMode("short_break", settings.autoStartBreaks);
      }
    } else {
      setNotice("☕ Tanaffus tugadi! Yangi diqqat sessiyasiga tayyormisiz?");
      switchMode("work", settings.autoStartFocus);
    }
  };

  // Timer loop
  useEffect(() => {
    if (isRunning) {
      // Start ambient sound if selected
      if (settings.ambientSound !== "none" && audioEngine) {
        audioEngine.setAmbient(settings.ambientSound, settings.volume);
      }

      timerRef.current = setInterval(() => {
        setSecondsLeft(prev => {
          if (settings.tickSound && audioEngine) {
            audioEngine.playTick();
          }
          if (prev <= 1) {
            void handlePhaseComplete();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      audioEngine?.stopAmbient();
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      audioEngine?.stopAmbient();
    };
  }, [isRunning, mode, settings]);

  // Ambient sound selector change
  const handleAmbientChange = (sound: PomodoroSettings["ambientSound"]) => {
    updateSettings({ ambientSound: sound });
    if (audioEngine) {
      if (sound === "none") {
        audioEngine.stopAmbient();
      } else if (isRunning) {
        audioEngine.setAmbient(sound, settings.volume);
      }
    }
  };

  // Reset current phase
  const handleReset = () => {
    setIsRunning(false);
    setSecondsLeft(getModeTotalSeconds(mode));
  };

  // Add a task
  const addTask = () => {
    if (!newTaskText.trim()) return;
    const next: PomodoroTask = { id: Date.now().toString(), text: newTaskText.trim(), done: false, pomodoros: 0 };
    const updated = [next, ...tasks];
    setTasks(updated);
    setNewTaskText("");
    try { localStorage.setItem("diamond_pomodoro_tasks", JSON.stringify(updated)); } catch { /* noop */ }
  };

  const toggleTask = (id: string) => {
    const updated = tasks.map(t => (t.id === id ? { ...t, done: !t.done } : t));
    setTasks(updated);
    try { localStorage.setItem("diamond_pomodoro_tasks", JSON.stringify(updated)); } catch { /* noop */ }
  };

  const deleteTask = (id: string) => {
    const updated = tasks.filter(t => t.id !== id);
    setTasks(updated);
    try { localStorage.setItem("diamond_pomodoro_tasks", JSON.stringify(updated)); } catch { /* noop */ }
  };

  // Add distraction note
  const addDistraction = () => {
    if (!newDistraction.trim()) return;
    const now = new Date();
    const timeStr = `${now.getHours().toString().padStart(2, "0")}:${now.getMinutes().toString().padStart(2, "0")}`;
    const next: DistractionNote = { id: Date.now().toString(), text: newDistraction.trim(), time: timeStr };
    const updated = [next, ...distractions];
    setDistractions(updated);
    setNewDistraction("");
    try { localStorage.setItem("diamond_pomodoro_distractions", JSON.stringify(updated)); } catch { /* noop */ }
  };

  const deleteDistraction = (id: string) => {
    const updated = distractions.filter(d => d.id !== id);
    setDistractions(updated);
    try { localStorage.setItem("diamond_pomodoro_distractions", JSON.stringify(updated)); } catch { /* noop */ }
  };

  // Calculate progress
  const totalSeconds = getModeTotalSeconds(mode);
  const progressPercent = Math.max(0, Math.min(100, ((totalSeconds - secondsLeft) / totalSeconds) * 100));
  const strokeDash = (progressPercent / 100) * 283;

  const minutesStr = Math.floor(secondsLeft / 60).toString().padStart(2, "0");
  const secondsStr = (secondsLeft % 60).toString().padStart(2, "0");

  const modeColor =
    mode === "work"
      ? "from-red-500 to-rose-600"
      : mode === "short_break"
      ? "from-emerald-500 to-teal-600"
      : "from-indigo-500 to-purple-600";

  const modeBadge =
    mode === "work" ? "🎯 Chuqur Diqqat" : mode === "short_break" ? "☕ Qisqa Tanaffus" : "🌴 Uzun Tanaffus";

  return (
    <div
      className={`relative w-full rounded-3xl transition-all duration-500 ${
        isZenMode
          ? "fixed inset-0 z-50 flex flex-col items-center justify-center bg-gray-950 p-6 text-white"
          : "p-4 sm:p-7 bg-white dark:bg-navy-900 border border-line dark:border-white/10 shadow-premium"
      }`}
    >
      {/* Notice Banner */}
      {notice && (
        <div className="mb-4 flex items-center justify-between rounded-2xl bg-emerald-500/15 border border-emerald-500/30 p-3 text-xs font-bold text-emerald-800 dark:text-emerald-200">
          <span>{notice}</span>
          <button type="button" onClick={() => setNotice(null)} className="ml-2 hover:opacity-80">✕</button>
        </div>
      )}

      {/* Header Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-line dark:border-white/10">
        <div>
          <h2 className="text-xl font-black text-navy-900 dark:text-white flex items-center gap-2">
            🍅 Pomodoro Focus Studio
            <span className="rounded-full bg-red-500/10 px-2.5 py-0.5 text-xs font-bold text-red-600 dark:text-red-400">
              {modeBadge}
            </span>
          </h2>
          <p className="text-xs text-ink-500 dark:text-navy-300 mt-0.5">
            Diqqatni jamlash va charchoqlarni oldini olish uchun maxsus vositalar
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIsZenMode(z => !z)}
            className="rounded-xl border border-line dark:border-white/10 px-3 py-1.5 text-xs font-bold text-ink-700 dark:text-navy-200 hover:bg-black/5 dark:hover:bg-white/5 transition flex items-center gap-1.5"
            title="Zen (To'liq ekran) rejimi"
          >
            {isZenMode ? "🗗 Chiqish" : "🔲 Zen Rejim"}
          </button>
          <button
            type="button"
            onClick={() => setShowTips(t => !t)}
            className="rounded-xl border border-line dark:border-white/10 px-3 py-1.5 text-xs font-bold text-ink-700 dark:text-navy-200 hover:bg-black/5 dark:hover:bg-white/5 transition"
          >
            💡 Qoidalar
          </button>
          <button
            type="button"
            onClick={() => setShowSettings(s => !s)}
            className="rounded-xl border border-line dark:border-white/10 px-3 py-1.5 text-xs font-bold text-ink-700 dark:text-navy-200 hover:bg-black/5 dark:hover:bg-white/5 transition"
          >
            ⚙️ Sozlamalar
          </button>
        </div>
      </div>

      {/* Pomodoro Rules Drawer */}
      {showTips && (
        <div className="mt-4 rounded-2xl bg-amber-500/10 border border-amber-500/20 p-4 text-xs leading-relaxed text-amber-900 dark:text-amber-200">
          <h4 className="font-black text-sm mb-1.5">Pomodoro usulining 5 ta oltin qoidasi:</h4>
          <ol className="list-decimal pl-4 space-y-1">
            <li><strong>1 sessiya = 1 vazifa:</strong> Butun diqqat faqat bitta ishga qaratiladi, ko'p vazifalilik taqiqlanadi.</li>
            <li><strong>Chalg'ishlarni yozib qo'ying:</strong> Miyaga kelgan har qanday o'y-fikrni pastdagi <em>Chalg'ishlar daftarchasiga</em> yozing va darhol o'qishga qayting.</li>
            <li><strong>Tanaffusda ekrandan uzoqlashing:</strong> Tanaffus vaqtida telefonga qaramang, biroz qimirlang, ko'zni dam oldiring va suv iching.</li>
            <li><strong>Har 4 siklda katta dam oling:</strong> 4 ta pomodoro (100 daqiqa) o'tgach, 15-20 daqiqa uzun tanaffus qiling.</li>
            <li><strong>Yutuqlarni nishonlang:</strong> Har bir yakunlangan sessiya sizni maqsadingizga 1 qadam yaqinlashtiradi!</li>
          </ol>
        </div>
      )}

      {/* Settings Modal Drawer */}
      {showSettings && (
        <div className="mt-4 rounded-2xl bg-surface-soft dark:bg-white/5 border border-line dark:border-white/10 p-4">
          <h4 className="font-black text-sm text-navy-900 dark:text-white mb-3">Vaqt va Bildirishnomalar Sozlamalari</h4>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="text-xs font-bold text-ink-600 dark:text-navy-300 block mb-1">
                Diqqat vaqti (daqiqa)
              </label>
              <input
                type="number"
                min="5"
                max="90"
                value={settings.workMinutes}
                onChange={e => {
                  const val = Number(e.target.value);
                  updateSettings({ workMinutes: val });
                  if (mode === "work" && !isRunning) setSecondsLeft(val * 60);
                }}
                className="w-full rounded-xl border border-line dark:border-white/10 bg-transparent p-2 text-sm font-bold text-navy-900 dark:text-white"
              />
            </div>
            <div>
              <label className="text-xs font-bold text-ink-600 dark:text-navy-300 block mb-1">
                Qisqa tanaffus (daqiqa)
              </label>
              <input
                type="number"
                min="1"
                max="30"
                value={settings.shortBreakMinutes}
                onChange={e => {
                  const val = Number(e.target.value);
                  updateSettings({ shortBreakMinutes: val });
                  if (mode === "short_break" && !isRunning) setSecondsLeft(val * 60);
                }}
                className="w-full rounded-xl border border-line dark:border-white/10 bg-transparent p-2 text-sm font-bold text-navy-900 dark:text-white"
              />
            </div>
            <div>
              <label className="text-xs font-bold text-ink-600 dark:text-navy-300 block mb-1">
                Uzun tanaffus (daqiqa)
              </label>
              <input
                type="number"
                min="5"
                max="60"
                value={settings.longBreakMinutes}
                onChange={e => {
                  const val = Number(e.target.value);
                  updateSettings({ longBreakMinutes: val });
                  if (mode === "long_break" && !isRunning) setSecondsLeft(val * 60);
                }}
                className="w-full rounded-xl border border-line dark:border-white/10 bg-transparent p-2 text-sm font-bold text-navy-900 dark:text-white"
              />
            </div>
          </div>

          <div className="mt-3 flex flex-wrap gap-4 pt-3 border-t border-line dark:border-white/10">
            <label className="flex items-center gap-2 text-xs font-medium cursor-pointer">
              <input
                type="checkbox"
                checked={settings.autoStartBreaks}
                onChange={e => updateSettings({ autoStartBreaks: e.target.checked })}
                className="rounded text-cyan-600"
              />
              Tanaffusni avtomatik boshlash
            </label>
            <label className="flex items-center gap-2 text-xs font-medium cursor-pointer">
              <input
                type="checkbox"
                checked={settings.autoStartFocus}
                onChange={e => updateSettings({ autoStartFocus: e.target.checked })}
                className="rounded text-cyan-600"
              />
              Diqqatni avtomatik davom ettirish
            </label>
            <label className="flex items-center gap-2 text-xs font-medium cursor-pointer">
              <input
                type="checkbox"
                checked={settings.tickSound}
                onChange={e => updateSettings({ tickSound: e.target.checked })}
                className="rounded text-cyan-600"
              />
              Soat chiqillash ovozi (Sekundomer tiktak)
            </label>
          </div>
        </div>
      )}

      {/* Main Focus Studio Area */}
      <div className="mt-6 flex flex-col items-center">
        {/* Phase Selector Tabs */}
        <div className="inline-flex rounded-full bg-gray-100 dark:bg-navy-800 p-1 mb-6 border border-line dark:border-white/10">
          <button
            type="button"
            onClick={() => switchMode("work")}
            className={`px-5 py-2 rounded-full text-xs font-black transition ${
              mode === "work"
                ? "bg-red-500 text-white shadow-md"
                : "text-ink-600 dark:text-navy-200 hover:text-navy-900 dark:hover:text-white"
            }`}
          >
            🎯 Diqqat ({settings.workMinutes}m)
          </button>
          <button
            type="button"
            onClick={() => switchMode("short_break")}
            className={`px-5 py-2 rounded-full text-xs font-black transition ${
              mode === "short_break"
                ? "bg-emerald-500 text-white shadow-md"
                : "text-ink-600 dark:text-navy-200 hover:text-navy-900 dark:hover:text-white"
            }`}
          >
            ☕ Qisqa tanaffus ({settings.shortBreakMinutes}m)
          </button>
          <button
            type="button"
            onClick={() => switchMode("long_break")}
            className={`px-5 py-2 rounded-full text-xs font-black transition ${
              mode === "long_break"
                ? "bg-indigo-500 text-white shadow-md"
                : "text-ink-600 dark:text-navy-200 hover:text-navy-900 dark:hover:text-white"
            }`}
          >
            🌴 Uzun tanaffus ({settings.longBreakMinutes}m)
          </button>
        </div>

        {/* Current Focus Goal Input */}
        <div className="w-full max-w-md mb-6">
          <input
            type="text"
            value={currentGoal}
            onChange={e => {
              setCurrentGoal(e.target.value);
              try { localStorage.setItem("diamond_pomodoro_goal", e.target.value); } catch { /* noop */ }
            }}
            placeholder="🎯 Hozirgi sessiya maqsadi nima? (masalan: IELTS Reading 2-matn)"
            className="w-full rounded-2xl border border-line dark:border-white/15 bg-surface-soft dark:bg-white/5 px-4 py-2.5 text-center text-sm font-bold text-navy-900 dark:text-white placeholder:text-ink-400 dark:placeholder:text-navy-400 focus:border-cyan-500 focus:outline-none transition"
          />
        </div>

        {/* Circular Countdown Ring */}
        <div className="relative w-64 h-64 sm:w-72 sm:h-72 flex items-center justify-center">
          <svg className="absolute inset-0 -rotate-90" width="100%" height="100%" viewBox="0 0 100 100">
            <circle
              cx="50"
              cy="50"
              r="45"
              fill="none"
              stroke="currentColor"
              strokeWidth="5"
              className="text-gray-200 dark:text-navy-800"
            />
            <circle
              cx="50"
              cy="50"
              r="45"
              fill="none"
              stroke="url(#timerGradient)"
              strokeWidth="5"
              strokeDasharray={`${strokeDash} 283`}
              strokeLinecap="round"
              className="transition-all duration-1000 ease-linear"
            />
            <defs>
              <linearGradient id="timerGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor={mode === "work" ? "#ef4444" : mode === "short_break" ? "#10b981" : "#6366f1"} />
                <stop offset="100%" stopColor={mode === "work" ? "#f43f5e" : mode === "short_break" ? "#14b8a6" : "#a855f7"} />
              </linearGradient>
            </defs>
          </svg>

          <div className="text-center z-10">
            <span className={`text-6xl sm:text-7xl font-mono font-black tracking-tight text-navy-900 dark:text-white ${isRunning ? "animate-pulse" : ""}`}>
              {minutesStr}:{secondsStr}
            </span>
            <p className="text-xs font-black uppercase tracking-widest text-ink-500 dark:text-navy-400 mt-2">
              {modeBadge}
            </p>
            {/* 4-cycle indicator dots */}
            <div className="mt-3 flex items-center justify-center gap-1.5">
              {[0, 1, 2, 3].map(i => {
                const filled = (cyclesCompleted % 4) > i;
                return (
                  <span
                    key={i}
                    title={`Sikl ${i + 1}`}
                    className={`h-2.5 w-2.5 rounded-full transition-all ${
                      filled ? "bg-red-500 scale-110 shadow-sm" : "bg-gray-300 dark:bg-navy-700"
                    }`}
                  />
                );
              })}
            </div>
          </div>
        </div>

        {/* Primary Controls */}
        <div className="mt-8 flex items-center gap-3">
          <button
            type="button"
            onClick={() => setIsRunning(r => !r)}
            className={`px-8 py-3.5 rounded-2xl text-white font-black text-base shadow-xl transition-all hover:scale-105 active:scale-95 bg-gradient-to-r ${modeColor}`}
          >
            {isRunning ? "⏸ Pauza" : "▶ Boshlash"}
          </button>
          <button
            type="button"
            onClick={handleReset}
            className="px-4 py-3.5 rounded-2xl border border-line dark:border-white/10 bg-surface-soft dark:bg-white/5 text-ink-700 dark:text-navy-200 hover:bg-black/5 dark:hover:bg-white/10 font-bold text-sm transition"
            title="Qayta o'rnatish"
          >
            ↺ Reset
          </button>
          <button
            type="button"
            onClick={() => void handlePhaseComplete()}
            className="px-4 py-3.5 rounded-2xl border border-line dark:border-white/10 bg-surface-soft dark:bg-white/5 text-ink-700 dark:text-navy-200 hover:bg-black/5 dark:hover:bg-white/10 font-bold text-sm transition"
            title="Keyingi bosqichga o'tish"
          >
            ⏭ O'tkazish
          </button>
        </div>

        {/* Ambient Soundscapes Bar */}
        <div className="mt-7 w-full max-w-xl rounded-2xl border border-line dark:border-white/10 bg-surface-soft/60 dark:bg-white/5 p-3.5">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2.5">
            <span className="text-xs font-black uppercase tracking-wider text-ink-600 dark:text-navy-300 flex items-center gap-1.5">
              🎧 Diqqat foni (Tabiat & Oq shovqin):
            </span>
            <div className="flex items-center gap-2">
              <span className="text-xs text-ink-400">Ovoz:</span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={settings.volume}
                onChange={e => {
                  const vol = parseFloat(e.target.value);
                  updateSettings({ volume: vol });
                  audioEngine?.setVolume(vol);
                }}
                className="w-20 accent-cyan-500 cursor-pointer"
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-1.5">
            {[
              { key: "none", label: "🔇 O'chirilgan" },
              { key: "rain", label: "🌧️ Yomg'ir" },
              { key: "ocean", label: "🌊 Dengiz to'lqini" },
              { key: "forest", label: "🌲 O'rmon shamoli" },
              { key: "cafe", label: "☕ Qahvaxona" },
              { key: "binaural", label: "🧠 432Hz Alfa dron" },
            ].map(snd => (
              <button
                key={snd.key}
                type="button"
                onClick={() => handleAmbientChange(snd.key as PomodoroSettings["ambientSound"])}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition ${
                  settings.ambientSound === snd.key
                    ? "bg-cyan-500 text-white shadow-sm"
                    : "bg-white/80 dark:bg-white/5 text-ink-700 dark:text-navy-200 hover:bg-white dark:hover:bg-white/10 border border-line dark:border-white/10"
                }`}
              >
                {snd.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Focus Productivity Tools: Tasks + Distraction Pad + Stats */}
      <div className="mt-8 grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* 1. Task Checklist */}
        <div className="rounded-2xl border border-line dark:border-white/10 bg-surface-soft/40 dark:bg-white/5 p-4 flex flex-col">
          <h3 className="text-sm font-black text-navy-900 dark:text-white flex items-center justify-between mb-3">
            <span>📋 Sessiya Vazifalari</span>
            <span className="text-xs text-ink-400 font-normal">
              {tasks.filter(t => t.done).length}/{tasks.length}
            </span>
          </h3>

          <div className="flex gap-2 mb-3">
            <input
              type="text"
              value={newTaskText}
              onChange={e => setNewTaskText(e.target.value)}
              onKeyDown={e => e.key === "Enter" && addTask()}
              placeholder="Vazifa qo'shish..."
              className="min-w-0 flex-1 rounded-xl border border-line dark:border-white/10 bg-white dark:bg-navy-800 px-3 py-1.5 text-xs font-medium text-navy-900 dark:text-white focus:outline-none"
            />
            <button
              type="button"
              onClick={addTask}
              className="rounded-xl bg-cyan-500 hover:bg-cyan-600 text-white px-3 py-1.5 text-xs font-bold transition"
            >
              +
            </button>
          </div>

          <div className="min-h-28 max-h-48 overflow-y-auto space-y-1.5 pr-1">
            {tasks.length ? (
              tasks.map(t => (
                <div
                  key={t.id}
                  className="flex items-center justify-between rounded-xl bg-white/80 dark:bg-navy-800/80 p-2 text-xs border border-line dark:border-white/5"
                >
                  <label className="flex items-center gap-2 cursor-pointer min-w-0 flex-1">
                    <input
                      type="checkbox"
                      checked={t.done}
                      onChange={() => toggleTask(t.id)}
                      className="rounded text-cyan-600"
                    />
                    <span className={`truncate ${t.done ? "line-through text-ink-400" : "font-semibold text-navy-900 dark:text-white"}`}>
                      {t.text}
                    </span>
                  </label>
                  <button
                    type="button"
                    onClick={() => deleteTask(t.id)}
                    className="ml-2 text-ink-400 hover:text-rose-500"
                  >
                    ✕
                  </button>
                </div>
              ))
            ) : (
              <p className="text-xs text-center text-ink-400 py-6">
                Ushbu pomodoro davomida qilmoqchi bo'lgan vazifalarni qo'shing.
              </p>
            )}
          </div>
        </div>

        {/* 2. Distraction Capture Pad */}
        <div className="rounded-2xl border border-line dark:border-white/10 bg-surface-soft/40 dark:bg-white/5 p-4 flex flex-col">
          <h3 className="text-sm font-black text-navy-900 dark:text-white flex items-center justify-between mb-1">
            <span>🧠 Chalg'ishlar Daftarchasi</span>
            <span className="text-xs text-amber-500 font-bold">Anti-chalg'ish</span>
          </h3>
          <p className="text-2xs text-ink-400 mb-3">
            Miyangizga kelgan fikrni shu yerga yozing-u, sessiyadan keyin bajaring!
          </p>

          <div className="flex gap-2 mb-3">
            <input
              type="text"
              value={newDistraction}
              onChange={e => setNewDistraction(e.target.value)}
              onKeyDown={e => e.key === "Enter" && addDistraction()}
              placeholder="Masalan: Telegramga qarash..."
              className="min-w-0 flex-1 rounded-xl border border-line dark:border-white/10 bg-white dark:bg-navy-800 px-3 py-1.5 text-xs font-medium text-navy-900 dark:text-white focus:outline-none"
            />
            <button
              type="button"
              onClick={addDistraction}
              className="rounded-xl bg-amber-500 hover:bg-amber-600 text-white px-3 py-1.5 text-xs font-bold transition"
            >
              Yozish
            </button>
          </div>

          <div className="min-h-28 max-h-48 overflow-y-auto space-y-1.5 pr-1">
            {distractions.length ? (
              distractions.map(d => (
                <div
                  key={d.id}
                  className="flex items-center justify-between rounded-xl bg-amber-500/10 p-2 text-xs border border-amber-500/20"
                >
                  <div className="min-w-0 flex-1 pr-2">
                    <span className="text-navy-900 dark:text-white font-medium block truncate">{d.text}</span>
                    <span className="text-2xs text-ink-400">{d.time} da qayd etildi</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => deleteDistraction(d.id)}
                    className="text-ink-400 hover:text-rose-500"
                  >
                    ✕
                  </button>
                </div>
              ))
            ) : (
              <p className="text-xs text-center text-ink-400 py-6">
                Hozircha chalg'ituvchi fikrlar yo'q. Diqqat 100%!
              </p>
            )}
          </div>
        </div>

        {/* 3. Stats & Daily Progress */}
        <div className="rounded-2xl border border-line dark:border-white/10 bg-surface-soft/40 dark:bg-white/5 p-4 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-black text-navy-900 dark:text-white mb-3">
              📊 Diqqat Statistikasi
            </h3>

            <div className="grid grid-cols-2 gap-2.5">
              <div className="rounded-xl bg-white dark:bg-navy-800 p-3 border border-line dark:border-white/5 text-center">
                <span className="text-2xl font-black text-red-500 block">{todayCompletedCount}</span>
                <span className="text-2xs font-bold uppercase tracking-wider text-ink-500 dark:text-navy-300">Bugungi Pomodoro</span>
              </div>
              <div className="rounded-xl bg-white dark:bg-navy-800 p-3 border border-line dark:border-white/5 text-center">
                <span className="text-2xl font-black text-cyan-500 block">{todayFocusMinutes}m</span>
                <span className="text-2xs font-bold uppercase tracking-wider text-ink-500 dark:text-navy-300">Bugungi Diqqat</span>
              </div>
              <div className="rounded-xl bg-white dark:bg-navy-800 p-3 border border-line dark:border-white/5 text-center">
                <span className="text-2xl font-black text-emerald-500 block">
                  {Math.round(Number(weekSummary.week_seconds || 0) / 60)}m
                </span>
                <span className="text-2xs font-bold uppercase tracking-wider text-ink-500 dark:text-navy-300">Haftalik vaqt</span>
              </div>
              <div className="rounded-xl bg-white dark:bg-navy-800 p-3 border border-line dark:border-white/5 text-center">
                <span className="text-2xl font-black text-purple-500 block">
                  {weekSummary.sessions || todayCompletedCount}
                </span>
                <span className="text-2xs font-bold uppercase tracking-wider text-ink-500 dark:text-navy-300">Haftalik sessiya</span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-line dark:border-white/10 flex items-center justify-between text-xs text-ink-500 dark:text-navy-400">
            <span>Ketma-ketlik sikli: <strong>{cyclesCompleted} ta</strong></span>
            <span className="text-emerald-600 font-bold">✓ Faol intizom</span>
          </div>
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
        setSeconds(s => {
          if (s <= 1) {
            setRunning(false);
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
      <span>{mm}:{ss}</span>
      <button
        type="button"
        onClick={() => setRunning(r => !r)}
        className="text-xs px-2 py-0.5 rounded-full bg-red-500 text-white hover:bg-red-600 transition"
      >
        {running ? "⏸" : "▶"}
      </button>
    </div>
  );
}
