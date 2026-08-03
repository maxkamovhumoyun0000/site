"use client";

import React, { useEffect, useMemo, useState } from "react";
import { StudentTestProctoring } from "../student/proctoring";

type BookQuestion = {
  id: number;
  question: string;
  option_a?: string;
  option_b?: string;
  option_c?: string;
  option_d?: string;
  options?: Record<string, string> | string[];
  order?: number;
  time_limit_sec?: number;
  time_limit_seconds?: number;
  seconds?: number;
};

type BookTestResult = {
  total_questions?: number;
  total?: number;
  correct?: number;
  correct_count?: number;
  wrong?: number;
  wrong_count?: number;
  unanswered?: number;
  skipped?: number;
  skipped_count?: number;
  score_percent?: number;
  dpoints_delta?: number;
  passed?: boolean;
  review?: Array<{
    question_id: number;
    selected_option?: string | null;
    correct_option: string;
    is_correct: boolean;
    explanation?: string | null;
  }>;
};

function decodeDisplayText(value: unknown) {
  const text = String(value ?? "");
  if (!text) return "";
  return text
    .replace(/&apos;|&#39;|&#x27;/gi, "'")
    .replace(/&quot;|&#34;|&#x22;/gi, '"')
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">");
}

function questionTimeLimitSec(question?: BookQuestion | null) {
  const raw = Number(question?.time_limit_sec ?? question?.time_limit_seconds ?? question?.seconds ?? 30);
  if (!Number.isFinite(raw) || raw <= 0) return 30;
  return Math.max(10, Math.min(300, Math.round(raw)));
}

export function StudentBookTest({
  bookTitle,
  contentType,
  contentId,
  questions,
  initialResult,
  autoSubmitWhenAllAnswered = false,
  onSubmit,
  onExit,
}: {
  bookTitle: string;
  contentType: "book" | "homework" | "video";
  contentId: number;
  questions: BookQuestion[];
  initialResult?: BookTestResult | null;
  autoSubmitWhenAllAnswered?: boolean;
  onSubmit: (answers: Record<string, string>, proctoringSessionId: number | null) => Promise<BookTestResult>;
  onExit: () => void;
}) {
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<BookTestResult | null>(initialResult || null);
  const [timeLeftSec, setTimeLeftSec] = useState(30);
  const [proctoringSessionId, setProctoringSessionId] = useState<number | null>(null);
  const [proctoringReady, setProctoringReady] = useState(true);
  const [proctoringStopped, setProctoringStopped] = useState("");
  const normalizedContentType = contentType === "video" ? "video" : contentType === "homework" ? "homework" : "book";
  const contentLabel = normalizedContentType === "video" ? "Video Test" : normalizedContentType === "homework" ? "Homework Test" : "Book Test";
  const returnLabel = normalizedContentType === "book" ? "Kutubxonaga qaytish" : normalizedContentType === "video" ? "Videoga qaytish" : "Homeworkga qaytish";
  const retryMessage = normalizedContentType === "video"
    ? "Bu safar yetarli bo'lmadi. Keyingi videolarda ko'proq natija qilasiz."
    : normalizedContentType === "homework"
      ? "Bu safar yetarli bo'lmadi. Keyingi homeworklarda ko'proq natija qilasiz."
      : "Bu safar yetarli bo'lmadi. Keyingi kitoblarda ko'proq natija qilasiz.";
  const testRoute = `/student/content-tests/${normalizedContentType}/${Number(contentId || 0)}`;

  const progressPercent = useMemo(() => {
    if (!questions.length) return 0;
    return Math.round(((current + 1) / questions.length) * 100);
  }, [current, questions.length]);

  const answeredCount = useMemo(() => Object.keys(answers).length, [answers]);

  const currentQuestion = questions[current];
  const currentTimeLimitSec = useMemo(() => questionTimeLimitSec(currentQuestion), [currentQuestion]);
  const currentQuestionOptions = useMemo(() => {
    if (!currentQuestion) return [] as Array<{ key: string; value: string; index: number }>;
    const rawOptions = currentQuestion.options;
    const list = Array.isArray(rawOptions)
      ? rawOptions.map((value) => String(value || ""))
      : rawOptions && typeof rawOptions === "object"
        ? Object.keys(rawOptions).sort().map((key) => String((rawOptions as Record<string, string>)[key] || ""))
        : [currentQuestion.option_a, currentQuestion.option_b, currentQuestion.option_c, currentQuestion.option_d].map((value) => String(value || ""));
    return list
      .map((value, index) => ({ key: String.fromCharCode(65 + index), value: decodeDisplayText(value), index }))
      .filter((item) => item.value.trim());
  }, [currentQuestion]);

  useEffect(() => {
    setResult(initialResult || null);
  }, [initialResult]);

  useEffect(() => {
    setTimeLeftSec(questionTimeLimitSec(questions[current]));
  }, [current, questions]);

  useEffect(() => {
    if (result || submitting || !proctoringReady || proctoringStopped) return;
    const timer = window.setInterval(() => {
      setTimeLeftSec((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [result, submitting, proctoringReady, proctoringStopped]);

  useEffect(() => {
    if (timeLeftSec > 0 || result || submitting || !proctoringReady || proctoringStopped) return;
    if (current < questions.length - 1) {
      setCurrent((prev) => Math.min(questions.length - 1, prev + 1));
      return;
    }
    void submitTest(true);
  }, [timeLeftSec, result, submitting, current, questions.length, proctoringReady, proctoringStopped]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!autoSubmitWhenAllAnswered || result || submitting || !proctoringReady || proctoringStopped) return;
    if (!questions.length || answeredCount < questions.length || current < questions.length - 1) return;
    const timer = window.setTimeout(() => {
      void submitTest(true);
    }, 700);
    return () => window.clearTimeout(timer);
  }, [autoSubmitWhenAllAnswered, answeredCount, current, questions.length, result, submitting, proctoringReady, proctoringStopped]); // eslint-disable-line react-hooks/exhaustive-deps

  function choose(optionIndex: number) {
    if (!currentQuestion || result || submitting) return;
    setAnswers((prev) => {
      const nextAnswers = { ...prev, [String(currentQuestion.id)]: String(optionIndex) };
      if (current < questions.length - 1) {
        window.setTimeout(() => {
          setCurrent((c) => Math.min(questions.length - 1, c + 1));
        }, 200);
      }
      return nextAnswers;
    });
  }

  async function submitTest(auto = false) {
    if (submitting || result) return;
    setSubmitting(true);
    setError("");
    try {
      const payload = await onSubmit(answers, null);
      setResult(payload);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Testni yuborib bo'lmadi.");
      if (auto) {
        setError("Vaqt tugadi, lekin testni yuborishda xatolik yuz berdi.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (!questions.length) {
    return (
      <div className="p-4 md:p-6 lg:p-8 max-w-3xl mx-auto">
        <div className="rounded-2xl border border-amber-200 bg-amber-50 text-amber-700 px-4 py-3 text-sm">
          Ushbu test uchun savollar topilmadi.
        </div>
      </div>
    );
  }

  if (result) {
    const correct = Number(result.correct_count ?? result.correct ?? 0);
    const wrong = Number(result.wrong_count ?? result.wrong ?? 0);
    const skipped = Number(result.skipped_count ?? result.skipped ?? result.unanswered ?? 0);
    const total = Number(result.total_questions ?? result.total ?? questions.length);
    const scorePercent = Number(result.score_percent ?? (total > 0 ? Math.round((correct * 10000) / total) / 100 : 0));
    const passed = Boolean(result.passed ?? scorePercent >= 70);
    return (
      <div className="p-4 md:p-6 lg:p-8 max-w-4xl mx-auto space-y-6">
        <div className="rounded-3xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6 sm:p-8 shadow-xl">
          <h2 className="text-2xl sm:text-3xl font-bold text-slate-800 dark:text-white mb-2">{contentLabel} Natijasi</h2>
          <p className="text-sm text-slate-500 dark:text-slate-300 mb-6">{decodeDisplayText(bookTitle)}</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
            <div className="rounded-2xl border border-slate-200 dark:border-slate-700 p-4 bg-slate-50 dark:bg-slate-800/40">
              <p className="text-xs text-slate-500 dark:text-slate-300">To'g'ri</p>
              <p className="text-2xl font-bold text-green-600 dark:text-green-400">{correct}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 dark:border-slate-700 p-4 bg-slate-50 dark:bg-slate-800/40">
              <p className="text-xs text-slate-500 dark:text-slate-300">Noto'g'ri</p>
              <p className="text-2xl font-bold text-red-600 dark:text-red-400">{wrong}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 dark:border-slate-700 p-4 bg-slate-50 dark:bg-slate-800/40">
              <p className="text-xs text-slate-500 dark:text-slate-300">Javobsiz</p>
              <p className="text-2xl font-bold text-slate-600 dark:text-slate-300">{skipped}</p>
            </div>
            <div className={`rounded-2xl border p-4 ${passed ? "border-green-200 bg-green-50 dark:bg-green-500/10 dark:border-green-500/30" : "border-amber-200 bg-amber-50 dark:bg-amber-500/10 dark:border-amber-500/30"}`}>
              <p className="text-xs text-slate-500 dark:text-slate-300">Foiz</p>
              <p className={`text-2xl font-bold ${passed ? "text-green-700 dark:text-green-400" : "text-amber-700 dark:text-amber-400"}`}>
                {scorePercent}%
              </p>
            </div>
          </div>
          <div className={`rounded-2xl border px-4 py-3 text-sm mb-6 ${passed ? "border-green-200 bg-green-50 text-green-700 dark:bg-green-500/10 dark:text-green-300 dark:border-green-500/30" : "border-amber-200 bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30"}`}>
            {passed ? "Ajoyib! Siz testdan muvaffaqiyatli o'tdingiz." : retryMessage}
          </div>
          {(result.review || []).length ? (
            <div className="space-y-3 max-h-[38dvh] overflow-y-auto pr-1">
              {(result.review || []).map((item, index) => (
                <div key={`review-${item.question_id}-${index}`} className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 bg-slate-50 dark:bg-slate-800/40">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-500">Savol #{index + 1}</span>
                    <span className={item.is_correct ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}>
                      {item.is_correct ? "To'g'ri" : "Xato"}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-300 mt-1">Siz: {decodeDisplayText(item.selected_option || "-")}, To'g'ri: {decodeDisplayText(item.correct_option)}</p>
                  {item.explanation ? <p className="text-xs text-slate-600 dark:text-slate-300 mt-1">{decodeDisplayText(item.explanation)}</p> : null}
                </div>
              ))}
            </div>
          ) : null}
          <div className="pt-6 flex justify-end">
            <button onClick={onExit} className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold">
              {returnLabel}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-3 sm:p-6 lg:p-8 max-w-5xl mx-auto space-y-4 sm:space-y-5 relative text-slate-900 dark:text-white">
      <div className="sticky top-4 z-40 rounded-3xl border border-slate-200 bg-white/90 dark:border-slate-700 dark:bg-slate-900/90 backdrop-blur-xl p-3.5 sm:p-5 shadow-premium space-y-2 sm:space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 sm:gap-3">
          <div>
            <h2 className="text-lg sm:text-2xl font-black text-navy-900 dark:text-white font-display tracking-tight">{contentLabel}</h2>
            <p className="text-[10px] sm:text-sm text-cyan-600 dark:text-cyan-400 font-bold tracking-wide uppercase">{decodeDisplayText(bookTitle)}</p>
          </div>
          <div className={`px-3 py-2 rounded-xl text-sm font-black ${timeLeftSec > Math.min(10, currentTimeLimitSec / 2) ? "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-100 border border-slate-200 dark:border-slate-700" : "bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-200 border border-red-200 dark:border-red-500/30 animate-pulse"}`}>
            ⏳ {Math.floor(timeLeftSec / 60)}:{String(timeLeftSec % 60).padStart(2, "0")}
          </div>
        </div>
        <div className="h-2.5 rounded-full bg-slate-200/50 dark:bg-navy-950 overflow-hidden shadow-inner border border-white/10">
          <div className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-blue-500 transition-all duration-500 shadow-[0_0_10px_rgba(34,211,238,0.5)]" style={{ width: `${progressPercent}%` }} />
        </div>
        <div className="flex flex-wrap items-center justify-between text-xs font-bold text-slate-500 dark:text-slate-400">
          <span>Savol {current + 1} / {questions.length}</span>
          <span className="text-cyan-600 dark:text-cyan-400">Javob berilgan: {answeredCount}</span>
        </div>
      </div>

      {error ? <div className="rounded-xl bg-red-50 text-red-700 border border-red-200 px-4 py-2 text-sm dark:bg-red-500/10 dark:text-red-200 dark:border-red-500/30">{error}</div> : null}

      <div className="relative rounded-3xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 backdrop-blur-sm p-4 sm:p-8 shadow-xl space-y-4 sm:space-y-6">
        <h3 className="text-base sm:text-2xl font-bold text-navy-900 dark:text-white leading-relaxed tracking-tight">
          {decodeDisplayText(currentQuestion?.question)}
        </h3>
        <div className="grid gap-4">
          {currentQuestionOptions.map((opt) => {
            const selected = answers[String(currentQuestion.id)] === String(opt.index);
            return (
              <button
                key={`${currentQuestion.id}-${opt.key}`}
                onClick={() => choose(opt.index)}
                disabled={!proctoringReady || Boolean(proctoringStopped)}
                className={`text-left rounded-2xl border px-4 py-3 sm:px-5 sm:py-4 transition-all duration-300 ${
                  selected
                    ? "border-cyan-400 bg-cyan-50 text-cyan-900 dark:bg-cyan-500/20 dark:text-cyan-100 shadow-[0_0_15px_rgba(34,211,238,0.3)] scale-[1.01]"
                    : "border-slate-200 hover:border-cyan-300 bg-slate-50 dark:bg-slate-950 dark:border-slate-700 dark:hover:border-cyan-400 text-slate-700 dark:text-slate-200"
                }`}
              >
                <span className={`font-black mr-3 text-lg ${selected ? "text-cyan-600 dark:text-cyan-400" : "text-slate-400 dark:text-slate-500"}`}>{opt.key}.</span>
                <span className="font-medium text-[15px]">{opt.value || "-"}</span>
              </button>
            );
          })}
        </div>
        <div className="flex flex-wrap justify-end gap-3 pt-4 border-t border-slate-100 dark:border-white/10">
          <div className="inline-flex gap-3">
            {current < questions.length - 1 ? (
              <button
                onClick={() => setCurrent((prev) => Math.min(questions.length - 1, prev + 1))}
                className="px-8 py-3 rounded-2xl bg-cyan-100 hover:bg-cyan-200 dark:bg-cyan-900/40 dark:hover:bg-cyan-800/60 text-cyan-800 dark:text-cyan-100 text-sm font-bold transition-colors"
              >
                Keyingi →
              </button>
            ) : null}
            <button
              onClick={() => submitTest(false)}
              disabled={submitting || !proctoringReady || Boolean(proctoringStopped)}
              className="px-8 py-3 rounded-2xl bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-navy-900 text-sm font-black transition-all shadow-[0_0_20px_rgba(34,211,238,0.4)]"
            >
              {submitting ? "Yuborilmoqda..." : "Testni yakunlash"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
