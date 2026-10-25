"use client";

import React, { useState } from "react";

// ─────────────────────────────────────────────────────────────────────────────
// STITCH LUMINOUS SOFT UI: ARENA & DUELS COMPONENTS (1:1 Web Implementation)
// Google Stitch Screens:
//  - d695be25a26f46069d2bb13abdcba7db (Arena Home)
//  - efec3ecd86df4a95ac2b0fd8ced3118f (Matchmaking & Active Test)
//  - 62ab01898f2247569974bf0e1cb11a78 (Results & History Review)
// ─────────────────────────────────────────────────────────────────────────────

export function StitchWebArenaHeader({
  dcoin = 0,
  dpoint = 0,
  onOpenHistory,
}: {
  dcoin?: number;
  dpoint?: number;
  onOpenHistory?: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 p-5 sm:p-6 bg-white dark:bg-[#131C2E] rounded-3xl border border-[#E6EBF5] dark:border-[#233352] shadow-[0_8px_24px_-4px_rgba(23,35,60,0.06)] mb-6 transition-all">
      <div className="flex items-center gap-3.5">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-[#1736E8] to-[#384BD4] flex items-center justify-center text-white shadow-[0_4px_14px_rgba(23,54,232,0.35)] shrink-0">
          <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2c-4.42 0-8 3.58-8 8 0 4.14 3.12 7.55 7.15 7.95L12 22l.85-4.05C16.88 17.55 20 14.14 20 10c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6s2.69-6 6-6 6 2.69 6 6-2.69 6-6 6z" />
          </svg>
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-black text-[#0F1B34] dark:text-[#F4F7FC] tracking-tight">
              Arena &amp; Duellar
            </h1>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#13A879]/12 text-[#13A879] text-xs font-black">
              <span className="w-1.5 h-1.5 rounded-full bg-[#13A879] animate-pulse" />
              LIVE
            </span>
          </div>
          <div className="flex items-center gap-3 mt-1 text-xs sm:text-sm font-semibold text-[#68758D] dark:text-[#A1B0CC]">
            <span className="flex items-center gap-1 text-[#E8A33D] font-bold">
              💰 {dcoin} D&apos;Coin
            </span>
            <span className="text-[#E6EBF5] dark:text-[#233352]">•</span>
            <span className="flex items-center gap-1 text-[#1736E8] dark:text-[#00D2FF] font-bold">
              ⚡ {dpoint} XP
            </span>
          </div>
        </div>
      </div>

      {onOpenHistory && (
        <button
          type="button"
          onClick={onOpenHistory}
          className="flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-[#F6F8FD] dark:bg-[#1B273F] border border-[#E6EBF5] dark:border-[#233352] text-sm font-bold text-[#0F1B34] dark:text-[#F4F7FC] hover:bg-[#1736E8]/10 hover:text-[#1736E8] transition-all active:scale-95"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>Tarix (History)</span>
        </button>
      )}
    </div>
  );
}

export function StitchWebArenaCard({
  title,
  subtitle,
  badgeText,
  activeInfo,
  icon,
  gradientClass,
  btnText = "Boshlash",
  onStart,
}: {
  title: string;
  subtitle: string;
  badgeText: string;
  activeInfo?: string;
  icon: React.ReactNode;
  gradientClass: string;
  btnText?: string;
  onStart: () => void;
}) {
  return (
    <div className="group relative flex flex-col justify-between p-5 sm:p-6 bg-white dark:bg-[#131C2E] rounded-3xl border border-[#E6EBF5] dark:border-[#233352] shadow-[0_8px_24px_-4px_rgba(23,35,60,0.06)] hover:shadow-[0_16px_32px_-6px_rgba(23,35,60,0.12)] transition-all hover:-translate-y-1">
      <div>
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className={`w-14 h-14 rounded-2xl ${gradientClass} flex items-center justify-center text-white text-2xl shadow-lg shrink-0`}>
            {icon}
          </div>
          <span className="px-3 py-1 rounded-full bg-[#1736E8]/10 text-[#1736E8] dark:text-[#00D2FF] text-xs font-black tracking-wide">
            {badgeText}
          </span>
        </div>

        <h3 className="text-lg sm:text-xl font-extrabold text-[#0F1B34] dark:text-[#F4F7FC] mb-1.5 leading-snug">
          {title}
        </h3>
        <p className="text-xs sm:text-sm text-[#68758D] dark:text-[#A1B0CC] leading-relaxed mb-4">
          {subtitle}
        </p>
      </div>

      <div className="pt-2 border-t border-[#E6EBF5] dark:border-[#233352]/50 flex items-center justify-between gap-3">
        {activeInfo ? (
          <span className="inline-flex items-center gap-1.5 text-xs font-bold text-[#13A879]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#13A879] animate-ping" />
            {activeInfo}
          </span>
        ) : (
          <span />
        )}

        <button
          type="button"
          onClick={onStart}
          className="px-5 py-2.5 rounded-2xl bg-[#1736E8] hover:bg-[#1429F2] text-white text-xs sm:text-sm font-extrabold shadow-[0_4px_12px_rgba(23,54,232,0.3)] transition-all active:scale-95 flex items-center gap-1.5"
        >
          <span>{btnText}</span>
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>
  );
}

export function StitchWebRadarMatchmaking({
  participantCount,
  requiredPlayers,
  secondsLeft,
  playerName = "Siz",
  opponentName,
  onCancel,
}: {
  participantCount: number;
  requiredPlayers: number;
  secondsLeft: number;
  playerName?: string;
  opponentName?: string;
  onCancel: () => void;
}) {
  const mm = Math.floor(Math.max(0, secondsLeft) / 60).toString().padStart(2, "0");
  const ss = (Math.max(0, secondsLeft) % 60).toString().padStart(2, "0");

  return (
    <div className="w-full max-w-lg mx-auto flex flex-col gap-5 p-4 sm:p-6 bg-white dark:bg-[#131C2E] rounded-3xl border border-[#E6EBF5] dark:border-[#233352] shadow-[0_16px_32px_-6px_rgba(23,35,60,0.08)]">
      {/* Top title */}
      <div className="flex items-center justify-between pb-3 border-b border-[#E6EBF5] dark:border-[#233352]">
        <button
          type="button"
          onClick={onCancel}
          className="w-9 h-9 rounded-xl flex items-center justify-center text-[#68758D] hover:bg-[#F6F8FD] dark:hover:bg-[#1B273F] transition-colors"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
        <h2 className="text-lg font-black text-[#0F1B34] dark:text-[#F4F7FC]">
          Duel Matchmaking
        </h2>
        <div className="w-9 h-9" />
      </div>

      {/* Pulsing Radar Visualizer */}
      <div className="relative py-8 flex flex-col items-center justify-center overflow-hidden rounded-2xl bg-[#F6F8FD] dark:bg-[#0C1322]">
        <div className="relative flex items-center justify-center w-40 h-40">
          <div className="absolute inset-0 rounded-full border-2 border-[#1736E8]/30 animate-ping pointer-events-none" />
          <div className="w-32 h-32 rounded-full border-2 border-[#1736E8]/20 flex items-center justify-center bg-[#1736E8]/5">
            <div className="w-20 h-20 rounded-full bg-gradient-to-br from-[#1736E8] to-[#384BD4] text-white flex items-center justify-center shadow-lg">
              <svg className="w-8 h-8 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6.364 1.636l-.707.707M20 12h-1m-1.636 6.364l-.707-.707M12 20v-1m-6.364-1.636l.707-.707M4 12h1m1.636-6.364l.707.707" />
              </svg>
            </div>
          </div>
        </div>

        <div className="mt-4 text-center space-y-1">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#1736E8]/10 text-[#1736E8] text-xs font-black">
            <span className="w-1.5 h-1.5 rounded-full bg-[#1736E8] animate-ping" />
            <span>{participantCount} / {requiredPlayers || 2} Ishtirokchilar</span>
          </div>
          <p className="text-base font-extrabold text-[#0F1B34] dark:text-[#F4F7FC]">
            Raqib qidirilmoqda...
          </p>
          <p className="text-xs font-bold text-[#68758D] dark:text-[#A1B0CC]">
            Qidiruv davom etmoqda • <span className="text-[#1736E8]">{mm}:{ss} qoldi</span>
          </p>
        </div>
      </div>

      {/* Participants Slots */}
      <div className="space-y-2.5">
        <h4 className="text-xs font-bold uppercase tracking-wider text-[#68758D] dark:text-[#A1B0CC]">
          DUEL ISHTIROKCHILARI
        </h4>

        {/* Slot 1: You */}
        <div className="p-3.5 rounded-2xl bg-[#F6F8FD] dark:bg-[#1B273F] border border-[#E6EBF5] dark:border-[#233352] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-[#1736E8] text-white flex items-center justify-center font-black text-sm">
              {playerName.slice(0, 2).toUpperCase()}
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-extrabold text-sm text-[#0F1B34] dark:text-[#F4F7FC]">{playerName}</span>
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-[#1736E8]/10 text-[#1736E8]">Siz</span>
              </div>
              <p className="text-xs text-[#68758D] dark:text-[#A1B0CC]">Tayyor holatda</p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1 text-xs font-bold text-[#13A879]">
            <span className="w-2 h-2 rounded-full bg-[#13A879]" /> Tayyor
          </span>
        </div>

        {/* Slot 2: Searching or Matched */}
        {opponentName ? (
          <div className="p-3.5 rounded-2xl bg-[#F6F8FD] dark:bg-[#1B273F] border border-[#E6EBF5] dark:border-[#233352] flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-xl bg-[#E8A33D] text-white flex items-center justify-center font-black text-sm">
                {opponentName.slice(0, 2).toUpperCase()}
              </div>
              <div>
                <span className="font-extrabold text-sm text-[#0F1B34] dark:text-[#F4F7FC]">{opponentName}</span>
                <p className="text-xs text-[#68758D] dark:text-[#A1B0CC]">Raqib ulandi</p>
              </div>
            </div>
            <span className="inline-flex items-center gap-1 text-xs font-bold text-[#13A879]">
              <span className="w-2 h-2 rounded-full bg-[#13A879]" /> Tayyor
            </span>
          </div>
        ) : (
          <div className="p-3.5 rounded-2xl border-2 border-dashed border-[#E6EBF5] dark:border-[#233352] flex items-center justify-between animate-pulse">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-xl bg-slate-100 dark:bg-white/5 flex items-center justify-center text-[#68758D]">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              <div>
                <span className="font-bold text-sm text-[#68758D] dark:text-[#A1B0CC]">Raqib kutilmoqda...</span>
                <p className="text-xs text-[#68758D]/70">Mos darajadagi foydalanuvchi ulanmoqda</p>
              </div>
            </div>
            <span className="text-xs font-semibold px-2 py-1 rounded-full bg-slate-100 dark:bg-white/5 text-[#68758D]">
              Kutilmoqda
            </span>
          </div>
        )}
      </div>

      {/* Cancel CTA */}
      <button
        type="button"
        onClick={onCancel}
        className="w-full py-3 rounded-2xl bg-[#F6F8FD] dark:bg-[#1B273F] hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-500/10 text-[#68758D] text-xs sm:text-sm font-bold transition-all active:scale-98"
      >
        Juftlikni bekor qilish (Cancel)
      </button>
    </div>
  );
}

export function StitchWebGeneratingState({
  percent = 68,
  playerName = "Azizbek K.",
  opponentName = "Dilshod R.",
}: {
  percent?: number;
  playerName?: string;
  opponentName?: string;
}) {
  return (
    <div className="w-full max-w-lg mx-auto flex flex-col gap-5 p-5 sm:p-6 bg-white dark:bg-[#131C2E] rounded-3xl border border-[#E6EBF5] dark:border-[#233352] shadow-xl text-center">
      <div className="py-6 flex flex-col items-center">
        {/* Circular Progress SVG */}
        <div className="relative w-36 h-36 flex items-center justify-center">
          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="40" stroke="currentColor" strokeWidth="8" fill="none" className="text-[#E6EBF5] dark:text-[#233352]" />
            <circle
              cx="50"
              cy="50"
              r="40"
              stroke="#1736E8"
              strokeWidth="8"
              fill="none"
              strokeDasharray="251"
              strokeDashoffset={251 - (251 * percent) / 100}
              strokeLinecap="round"
              className="transition-all duration-500"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-black text-[#0F1B34] dark:text-[#F4F7FC]">{percent}%</span>
            <span className="text-[10px] font-bold text-[#1736E8] uppercase">Yuklanmoqda</span>
          </div>
        </div>

        <h3 className="text-lg font-extrabold text-[#0F1B34] dark:text-[#F4F7FC] mt-4 mb-1">
          Savollar tayyorlanmoqda...
        </h3>
        <p className="text-xs text-[#68758D] dark:text-[#A1B0CC] max-w-xs">
          AI test moduli siz va raqibingiz darajasiga mos vazifalarni shakllantirmoqda.
        </p>
      </div>

      {/* Matched Duel Opponents */}
      <div className="grid grid-cols-2 gap-3 p-3 rounded-2xl bg-[#F6F8FD] dark:bg-[#1B273F]">
        <div className="flex items-center gap-2 p-2 rounded-xl bg-white dark:bg-[#131C2E]">
          <div className="w-9 h-9 rounded-lg bg-[#1736E8] text-white flex items-center justify-center font-bold text-xs">
            {playerName.slice(0, 2).toUpperCase()}
          </div>
          <div className="text-left overflow-hidden">
            <p className="text-xs font-bold text-[#0F1B34] dark:text-[#F4F7FC] truncate">{playerName}</p>
            <span className="text-[10px] font-bold text-[#13A879]">Tayyor</span>
          </div>
        </div>
        <div className="flex items-center gap-2 p-2 rounded-xl bg-white dark:bg-[#131C2E]">
          <div className="w-9 h-9 rounded-lg bg-[#E8A33D] text-white flex items-center justify-center font-bold text-xs">
            {opponentName.slice(0, 2).toUpperCase()}
          </div>
          <div className="text-left overflow-hidden">
            <p className="text-xs font-bold text-[#0F1B34] dark:text-[#F4F7FC] truncate">{opponentName}</p>
            <span className="text-[10px] font-bold text-[#13A879]">Tayyor</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function StitchWebResultView({
  isWinner,
  isTie,
  correctCount = 0,
  wrongCount = 0,
  skippedCount = 0,
  dcoinEarned = 0,
  dpointEarned = 0,
  onReview,
  onDone,
}: {
  isWinner: boolean;
  isTie?: boolean;
  correctCount: number;
  wrongCount: number;
  skippedCount?: number;
  dcoinEarned?: number;
  dpointEarned?: number;
  onReview?: () => void;
  onDone: () => void;
}) {
  return (
    <div className="w-full max-w-lg mx-auto flex flex-col gap-5 p-5 sm:p-6 bg-white dark:bg-[#131C2E] rounded-3xl border border-[#E6EBF5] dark:border-[#233352] shadow-2xl text-center">
      {/* Hero Victory Card */}
      <div className={`relative overflow-hidden rounded-3xl p-6 text-white ${
        isWinner
          ? "bg-gradient-to-br from-[#1736E8] via-[#1429F2] to-[#0A16A8] shadow-[0_12px_32px_rgba(23,54,232,0.35)]"
          : isTie
          ? "bg-gradient-to-br from-slate-700 to-slate-900"
          : "bg-gradient-to-br from-[#1736E8]/80 to-[#131C2E]"
      }`}>
        <div className="relative z-10 flex flex-col items-center">
          <div className="w-20 h-20 rounded-full bg-white/15 backdrop-blur-md flex items-center justify-center border-2 border-white/30 text-3xl mb-3">
            {isWinner ? "🏆" : isTie ? "🤝" : "💪"}
          </div>
          <span className="text-[11px] font-black uppercase tracking-widest text-[#BCC2FF]">
            DUEL NATIJASI
          </span>
          <h2 className="text-2xl sm:text-3xl font-black mt-1 mb-1">
            {isWinner ? "G‘ALABA! (VICTORY)" : isTie ? "DURANG! (TIE)" : "O‘YIN YAKUNLANDI"}
          </h2>
        </div>
      </div>

      {/* Rewards Row */}
      <div className="grid grid-cols-2 gap-3">
        <div className="p-3.5 rounded-2xl bg-[#F6F8FD] dark:bg-[#1B273F] border border-[#E6EBF5] dark:border-[#233352]">
          <p className="text-[10px] font-bold uppercase tracking-wider text-[#68758D] dark:text-[#A1B0CC]">
            D&apos;Coin Mukofoti
          </p>
          <p className="text-lg font-black text-[#E8A33D] mt-0.5">
            +{dcoinEarned} D&apos;Coin
          </p>
        </div>
        <div className="p-3.5 rounded-2xl bg-[#F6F8FD] dark:bg-[#1B273F] border border-[#E6EBF5] dark:border-[#233352]">
          <p className="text-[10px] font-bold uppercase tracking-wider text-[#68758D] dark:text-[#A1B0CC]">
            Tajriba (XP)
          </p>
          <p className="text-lg font-black text-[#1736E8] dark:text-[#00D2FF] mt-0.5">
            +{dpointEarned} XP
          </p>
        </div>
      </div>

      {/* Score Breakdown */}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="p-3 rounded-xl bg-[#13A879]/10 border border-[#13A879]/20">
          <p className="text-xs font-bold text-[#13A879]">To‘g‘ri</p>
          <p className="text-xl font-black text-[#13A879] mt-1">{correctCount}</p>
        </div>
        <div className="p-3 rounded-xl bg-[#E53935]/10 border border-[#E53935]/20">
          <p className="text-xs font-bold text-[#E53935]">Noto‘g‘ri</p>
          <p className="text-xl font-black text-[#E53935] mt-1">{wrongCount}</p>
        </div>
        <div className="p-3 rounded-xl bg-[#68758D]/10 border border-[#68758D]/20">
          <p className="text-xs font-bold text-[#68758D]">Qoldirilgan</p>
          <p className="text-xl font-black text-[#68758D] mt-1">{skippedCount}</p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-2.5 pt-2">
        {onReview && (
          <button
            type="button"
            onClick={onReview}
            className="w-full py-3.5 rounded-2xl bg-[#1736E8]/10 hover:bg-[#1736E8]/20 text-[#1736E8] dark:text-[#00D2FF] text-sm font-black transition-all active:scale-98"
          >
            Savollar Tahlili (Review)
          </button>
        )}
        <button
          type="button"
          onClick={onDone}
          className="w-full py-3.5 rounded-2xl bg-[#1736E8] hover:bg-[#1429F2] text-white text-sm font-black shadow-lg transition-all active:scale-98"
        >
          Arenaga Qaytish
        </button>
      </div>
    </div>
  );
}

export function StitchWebAnswerReview({
  items = [],
  onClose,
}: {
  items: Array<{
    question_index?: number;
    prompt?: string;
    passage?: string;
    options?: string[];
    selected_option?: number | null;
    correct_option?: number | null;
    is_correct?: boolean;
    explanation?: string;
  }>;
  onClose: () => void;
}) {
  const [filter, setFilter] = useState<"all" | "correct" | "wrong" | "skipped">("all");

  const correctCount = items.filter((i) => i.is_correct === true).length;
  const wrongCount = items.filter((i) => i.is_correct === false && i.selected_option !== null && i.selected_option !== undefined).length;
  const skippedCount = items.filter((i) => i.selected_option === null || i.selected_option === undefined).length;

  const filteredItems = items.filter((item) => {
    if (filter === "correct") return item.is_correct === true;
    if (filter === "wrong") return item.is_correct === false && item.selected_option !== null && item.selected_option !== undefined;
    if (filter === "skipped") return item.selected_option === null || item.selected_option === undefined;
    return true;
  });

  return (
    <div className="w-full max-w-2xl mx-auto flex flex-col gap-5 p-4 sm:p-6 bg-white dark:bg-[#131C2E] rounded-3xl border border-[#E6EBF5] dark:border-[#233352] shadow-xl">
      <div className="flex items-center justify-between pb-4 border-b border-[#E6EBF5] dark:border-[#233352]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#1736E8]/10 text-[#1736E8] flex items-center justify-center font-black">
            📊
          </div>
          <div>
            <h3 className="text-lg font-black text-[#0F1B34] dark:text-[#F4F7FC]">Savollar Tahlili</h3>
            <p className="text-xs text-[#68758D] dark:text-[#A1B0CC]">Javoblaringiz va AI grammatika izohlari</p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="w-9 h-9 rounded-xl flex items-center justify-center text-[#68758D] hover:bg-[#F6F8FD] dark:hover:bg-[#1B273F]"
        >
          ✕
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setFilter("all")}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
            filter === "all"
              ? "bg-[#1736E8] text-white shadow-sm"
              : "bg-[#F6F8FD] dark:bg-[#1B273F] text-[#68758D] hover:text-[#0F1B34] dark:hover:text-[#F4F7FC]"
          }`}
        >
          Barchasi ({items.length})
        </button>
        <button
          type="button"
          onClick={() => setFilter("correct")}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
            filter === "correct"
              ? "bg-[#13A879] text-white shadow-sm"
              : "bg-[#13A879]/10 text-[#13A879] hover:bg-[#13A879]/20"
          }`}
        >
          To‘g‘ri ({correctCount})
        </button>
        <button
          type="button"
          onClick={() => setFilter("wrong")}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
            filter === "wrong"
              ? "bg-[#DC5261] text-white shadow-sm"
              : "bg-[#DC5261]/10 text-[#DC5261] hover:bg-[#DC5261]/20"
          }`}
        >
          Noto‘g‘ri ({wrongCount})
        </button>
        <button
          type="button"
          onClick={() => setFilter("skipped")}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
            filter === "skipped"
              ? "bg-[#68758D] text-white shadow-sm"
              : "bg-[#68758D]/10 text-[#68758D] hover:bg-[#68758D]/20"
          }`}
        >
          Qoldirilgan ({skippedCount})
        </button>
      </div>

      {/* Questions List */}
      <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
        {filteredItems.map((item, idx) => {
          const qIndex = item.question_index ?? idx + 1;
          const options = item.options || [];
          return (
            <div
              key={qIndex}
              className="p-4 rounded-2xl bg-[#F6F8FD] dark:bg-[#1B273F] border border-[#E6EBF5] dark:border-[#233352] space-y-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-black px-2.5 py-1 rounded-lg bg-white dark:bg-[#131C2E] text-[#1736E8]">
                  {qIndex}-Savol
                </span>
                <span
                  className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                    item.is_correct
                      ? "bg-[#13A879]/15 text-[#13A879]"
                      : item.selected_option === null || item.selected_option === undefined
                      ? "bg-slate-200 text-slate-700 dark:bg-white/10 dark:text-slate-300"
                      : "bg-[#DC5261]/15 text-[#DC5261]"
                  }`}
                >
                  {item.is_correct ? "✓ To‘g‘ri" : item.selected_option === null || item.selected_option === undefined ? "— Qoldirilgan" : "✕ Noto‘g‘ri"}
                </span>
              </div>

              {item.passage && (
                <div className="p-3 rounded-xl bg-white dark:bg-[#131C2E] text-xs leading-relaxed text-[#68758D] dark:text-[#A1B0CC]">
                  {item.passage}
                </div>
              )}

              <p className="text-sm font-bold text-[#0F1B34] dark:text-[#F4F7FC]">
                {item.prompt}
              </p>

              <div className="grid gap-2">
                {options.map((opt, oIdx) => {
                  const isCorrectOpt = item.correct_option === oIdx;
                  const isSelectedOpt = item.selected_option === oIdx;
                  return (
                    <div
                      key={oIdx}
                      className={`p-2.5 rounded-xl text-xs font-semibold flex items-center justify-between border ${
                        isCorrectOpt
                          ? "bg-[#13A879]/10 border-[#13A879] text-[#13A879]"
                          : isSelectedOpt
                          ? "bg-[#DC5261]/10 border-[#DC5261] text-[#DC5261]"
                          : "bg-white dark:bg-[#131C2E] border-[#E6EBF5] dark:border-[#233352] text-[#68758D] dark:text-[#A1B0CC]"
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <span className="w-5 h-5 rounded-md flex items-center justify-center font-bold text-[10px] bg-black/5 dark:bg-white/5">
                          {String.fromCharCode(65 + oIdx)}
                        </span>
                        <span>{opt}</span>
                      </span>
                      {isCorrectOpt && <span className="font-bold text-[10px]">To‘g‘ri javob</span>}
                      {isSelectedOpt && !isCorrectOpt && <span className="font-bold text-[10px]">Sizning javobingiz</span>}
                    </div>
                  );
                })}
              </div>

              {item.explanation && (
                <div className="p-3 rounded-xl bg-[#1736E8]/5 border border-[#1736E8]/20 text-xs text-[#1736E8] dark:text-[#00D2FF]">
                  <strong>AI Tushuntirishi: </strong>
                  {item.explanation}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function StitchWebSubjectModal({
  isOpen,
  subjects = ["English", "Russian"],
  onSelect,
  onClose,
}: {
  isOpen: boolean;
  subjects?: string[];
  onSelect: (subject: string) => void;
  onClose: () => void;
}) {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-sm bg-white dark:bg-[#131C2E] rounded-3xl p-6 border border-[#E6EBF5] dark:border-[#233352] shadow-2xl space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">🌍</span>
            <h3 className="text-lg font-black text-[#0F1B34] dark:text-[#F4F7FC]">
              Fanni tanlang (Subject)
            </h3>
          </div>
          <button type="button" onClick={onClose} className="text-[#68758D] hover:text-[#0F1B34]">✕</button>
        </div>
        <p className="text-xs text-[#68758D] dark:text-[#A1B0CC]">
          Duel va bellashuv uchun asosiy til yo‘nalishini tanlang:
        </p>
        <div className="space-y-2.5">
          {subjects.map((sub) => {
            const isEng = sub.toLowerCase().includes("eng") || sub.toLowerCase().includes("ingliz");
            return (
              <button
                key={sub}
                type="button"
                onClick={() => onSelect(sub)}
                className="w-full p-4 rounded-2xl bg-[#F6F8FD] dark:bg-[#1B273F] border border-[#E6EBF5] dark:border-[#233352] hover:border-[#1736E8] hover:shadow-md transition-all flex items-center justify-between group text-left"
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{isEng ? "🇬🇧" : "🇷🇺"}</span>
                  <div>
                    <h4 className="font-extrabold text-sm text-[#0F1B34] dark:text-[#F4F7FC] group-hover:text-[#1736E8]">
                      {isEng ? "English (Ingliz tili)" : "Russian (Rus tili)"}
                    </h4>
                    <p className="text-[11px] text-[#68758D] dark:text-[#A1B0CC]">
                      {isEng ? "IELTS & General Grammar" : "Rus tili grammatikasi"}
                    </p>
                  </div>
                </div>
                <span className="text-xs font-bold text-[#1736E8] opacity-0 group-hover:opacity-100 transition-opacity">
                  Tanlash →
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
