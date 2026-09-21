"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BadgeAwardModal } from "../../ui/badge-award-modal";

/* ─── Types ──────────────────────────────────────────────────────── */
interface WeakTopic { topic: string; level: string; explanation: string; rules: string[]; }
interface PracticeQ { question: string; options: string[]; correct: string; topic: string; difficulty: string; explanation: string; }
interface WeekAnalysis {
  exists: boolean; week_start: string; week_end: string; status: string;
  analysis: string; weak_topics: WeakTopic[]; recommendations: string[];
  test_stats: any; homework_stats: any; practice_questions: PracticeQ[];
  created_at: string | null;
  available_subjects?: string[];
  selected_subject?: string;
}
interface HistoryItem extends Omit<WeekAnalysis, "exists" | "status"> { id: number; }

/* ─── Auth Helper ─────────────────────────────────────────────────── */
function getAuthHeaders(): Record<string, string> {
  const token = typeof window !== "undefined" ? localStorage.getItem("diamond_token") || "" : "";
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

/* ─── i18n Dictionary ────────────────────────────────────────────── */
const T: Record<string, Record<string, string>> = {
  ru: {
    backDashboard: "Панель управления",
    title: "Мой учебный план",
    subtitle: "Diamondvoy готовит ваш еженедельный адаптивный анализ",
    generate: "Создать AI анализ",
    refresh: "Обновить",
    thinking: "Diamondvoy думает...",
    thinkingDetail: "Анализируются ваши тесты, ошибки и домашние задания...",
    weekOf: "Неделя",
    stats: "Статистика",
    tests: "Тестов",
    correct: "Верно",
    wrong: "Ошибки",
    skipped: "Пропущено",
    accuracy: "Точность тестов",
    homework: "Домашние задания",
    completed: "Выполнено",
    of: "из",
    aiAnalysis: "Анализ Diamondvoy",
    weakTopics: "Темы для повторения",
    rules: "Правила и объяснения",
    recommendations: "Рекомендации",
    practice: "Практический тест",
    practiceDesc: "Индивидуальные тесты по вашим слабым темам",
    startPractice: "Начать практику",
    checkAnswer: "Проверить",
    nextQuestion: "Следующий вопрос",
    correctAnswer: "Отлично! Правильный ответ!",
    wrongAnswer: "Пока неверно",
    explanation: "Объяснение",
    history: "Предыдущие недели",
    noHistory: "История анализов пока пуста",
    noData: "Данные собираются",
    noDataHint: "Решайте тесты и выполняйте задания — Diamondvoy составит персональный анализ",
    question: "вопрос",
    topicLabel: "Тема",
    easy: "Легко",
    medium: "Средне",
    hard: "Сложно",
    finishPractice: "Завершить практику",
    restartPractice: "Пройти заново",
    congrats: "Потрясающе! Все вопросы решены правильно!",
    keepGoing: "Хороший результат! Закрепите пройденные темы.",
    learnWithAi: "Учить с Diamondvoy",
    generate10Tests: "10 тестов по теме",
  },
  en: {
    backDashboard: "Dashboard",
    title: "Personal Study Plan",
    subtitle: "Diamondvoy prepares your weekly adaptive learning analysis",
    generate: "Generate AI Analysis",
    refresh: "Refresh",
    thinking: "Diamondvoy is thinking...",
    thinkingDetail: "Analyzing your test performance, mistakes, and homework...",
    weekOf: "Week",
    stats: "Weekly Stats",
    tests: "Tests",
    correct: "Correct",
    wrong: "Mistakes",
    skipped: "Skipped",
    accuracy: "Test Accuracy",
    homework: "Homework",
    completed: "Completed",
    of: "of",
    aiAnalysis: "Diamondvoy Analysis",
    weakTopics: "Topics to Review",
    rules: "Rules & Explanations",
    recommendations: "Recommendations",
    practice: "Practice Test",
    practiceDesc: "Targeted practice on your weak topics",
    startPractice: "Start Practice",
    checkAnswer: "Check Answer",
    nextQuestion: "Next Question",
    correctAnswer: "Spot on! That's correct!",
    wrongAnswer: "Not quite right yet",
    explanation: "Explanation",
    history: "Previous Weeks",
    noHistory: "No weekly analyses yet",
    noData: "Collecting your data",
    noDataHint: "Take tests and complete homework — Diamondvoy will prepare your personalized plan",
    question: "question",
    topicLabel: "Topic",
    easy: "Easy",
    medium: "Medium",
    hard: "Hard",
    finishPractice: "Finish Practice",
    restartPractice: "Practice Again",
    congrats: "Awesome! You mastered all questions!",
    keepGoing: "Great effort! Keep practicing to strengthen your skills.",
    learnWithAi: "Learn with Diamondvoy",
    generate10Tests: "Take 10 Tests",
  },
  uz: {
    backDashboard: "Boshqaruv paneli",
    title: "Shaxsiy O'quv Rejam",
    subtitle: "Diamondvoy sizning haftalik moslashuvchan tahlilingizni tayyorlaydi",
    generate: "AI Tahlil Yaratish",
    refresh: "Yangilash",
    thinking: "Diamondvoy o'ylanmoqda...",
    thinkingDetail: "Sizning test natijalari, xatolar va uy vazifalari tahlil qilinmoqda...",
    weekOf: "Hafta",
    stats: "Haftalik Statistika",
    tests: "Testlar",
    correct: "To'g'ri",
    wrong: "Xatolar",
    skipped: "O'tkazilgan",
    accuracy: "Test aniqligi",
    homework: "Uy vazifalari",
    completed: "Bajarildi",
    of: "dan",
    aiAnalysis: "Diamondvoy Tahlili",
    weakTopics: "Tushunib olish kerak bo'lgan mavzular",
    rules: "Qoidalar va Tushuntirish",
    recommendations: "Keyingi qadamlar",
    practice: "Mashq Testi",
    practiceDesc: "Zaif mavzularingiz bo'yicha yengil testlar",
    startPractice: "Mashqni Boshlash",
    checkAnswer: "Javobni Tekshirish",
    nextQuestion: "Keyingi Savol",
    correctAnswer: "Ajoyib! To'g'ri javob!",
    wrongAnswer: "Hozircha noto'g'ri",
    explanation: "Tushuntirish",
    history: "Oldingi Haftalar",
    noHistory: "Hali haftalik tahlil mavjud emas",
    noData: "Bu hafta uchun ma'lumotlar to'planmoqda",
    noDataHint: "Test ishlang, uy vazifalarini bajaring — Diamondvoy siz uchun tahlil tayyorlaydi",
    question: "savol",
    topicLabel: "Mavzu",
    easy: "Oson",
    medium: "O'rta",
    hard: "Qiyin",
    finishPractice: "Mashqni yakunlash",
    restartPractice: "Qaytadan",
    congrats: "Ajoyib! Barcha savollarni muvaffaqiyatli bajardingiz!",
    keepGoing: "Yaxshi natija! Xatolar ustida ishlab, bilimingizni mustahkamlang.",
    learnWithAi: "Diamondvoy bilan o'rganish",
    generate10Tests: "10 ta test ishlash",
  },
};

/* ─── ThinkingAnimation ──────────────────────────────────────────── */
function ThinkingAnimation({ text, detail }: { text: string; detail: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4 rounded-3xl border-2 border-b-4 border-slate-200 bg-white dark:border-navy-700 dark:bg-navy-900 shadow-sm">
      <div className="relative w-20 h-20">
        <div className="absolute inset-0 rounded-full border-4 border-blue-200 dark:border-blue-800" />
        <div className="absolute inset-0 rounded-full border-4 border-t-blue-500 dark:border-t-blue-400 animate-spin" />
        <div className="absolute inset-2 rounded-full bg-gradient-to-br from-[#002DFF] to-cyan-500 flex items-center justify-center shadow-lg">
          <span className="text-2xl animate-pulse">💎</span>
        </div>
      </div>
      <div className="text-center">
        <p className="text-lg font-black text-navy-900 dark:text-white animate-pulse">{text}</p>
        <p className="text-xs text-ink-500 dark:text-navy-300 mt-1 max-w-xs">{detail}</p>
      </div>
      <div className="flex gap-1.5 mt-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="w-2.5 h-2.5 rounded-full bg-blue-500 dark:bg-blue-400 animate-bounce" style={{ animationDelay: `${i * 0.2}s` }} />
        ))}
      </div>
    </div>
  );
}

/* ─── AccuracyRing ───────────────────────────────────────────────── */
function AccuracyRing({ pct }: { pct: number }) {
  const r = 38, circ = 2 * Math.PI * r, offset = circ - (pct / 100) * circ;
  const color = pct >= 80 ? "#22c55e" : pct >= 50 ? "#0284c7" : "#ef4444";
  return (
    <div className="flex items-center justify-center">
      <svg width="96" height="96" viewBox="0 0 96 96">
        <circle cx="48" cy="48" r={r} fill="none" stroke="#e2e8f0" strokeWidth="8" className="dark:stroke-navy-700" />
        <circle cx="48" cy="48" r={r} fill="none" stroke={color} strokeWidth="8" strokeDasharray={`${circ}`} strokeDashoffset={offset} strokeLinecap="round" className="transition-all duration-1000" style={{ transform: "rotate(-90deg)", transformOrigin: "center" }} />
        <text x="48" y="48" textAnchor="middle" dominantBaseline="central" className="fill-navy-900 dark:fill-white text-xl font-black">{pct}%</text>
      </svg>
    </div>
  );
}

/* ─── PracticeTest (Learning Path 3D Style) ───────────────────────── */
function PracticeTest({ questions, t }: { questions: PracticeQ[]; t: Record<string, string> }) {
  const [idx, setIdx] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<{ correct: boolean; explanation: string } | null>(null);
  const [checking, setChecking] = useState(false);
  const [score, setScore] = useState(0);
  const [done, setDone] = useState(false);

  const q = questions[idx];
  if (!q || done) return (
    <div className="text-center py-10 rounded-3xl border-2 border-b-4 border-slate-200 bg-white dark:border-navy-700 dark:bg-navy-900 p-6 shadow-sm animate-scale-up">
      <div className="text-6xl mb-4">🎉</div>
      <p className="text-2xl font-black text-navy-900 dark:text-white">{score} / {questions.length} {t.correct}</p>
      <p className="text-sm text-ink-600 dark:text-navy-300 mt-2 max-w-sm mx-auto">{score === questions.length ? t.congrats : t.keepGoing}</p>
      <button
        onClick={() => { setIdx(0); setSelected(null); setResult(null); setScore(0); setDone(false); }}
        className="mt-6 inline-flex items-center gap-2 rounded-2xl border-2 border-b-4 border-[#001A88] bg-[#002DFF] px-6 py-3 text-xs font-black uppercase tracking-wider text-white shadow-md shadow-blue-500/25 active:translate-y-0.5 active:border-b-2 hover:bg-[#1429f2] transition-all cursor-pointer"
      >
        <span>↺</span>
        <span>{t.restartPractice}</span>
      </button>
    </div>
  );

  async function check() {
    if (!selected || checking) return;
    setChecking(true);
    try {
      const headers = getAuthHeaders();
      const res = await fetch("/api/student/personal-plan/practice-test/check", {
        method: "POST",
        headers,
        body: JSON.stringify({
          question: q.question,
          options: q.options,
          selected,
          correct: q.correct,
          topic: q.topic,
          explanation: q.explanation,
        }),
      });
      const data = await res.json();
      setResult(data);
      if (data?.correct) setScore(s => s + 1);
    } catch {
      const isCorrect = selected.trim() === q.correct.trim();
      setResult({ correct: isCorrect, explanation: q.explanation || "" });
      if (isCorrect) setScore(s => s + 1);
    } finally { setChecking(false); }
  }

  function next() {
    if (idx + 1 >= questions.length) {
      setDone(true);
    } else {
      setIdx(i => i + 1);
      setSelected(null);
      setResult(null);
    }
  }

  return (
    <div className="rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-5 sm:p-6 dark:border-navy-700 dark:bg-navy-900 shadow-sm animate-fade-in">
      {/* Progress header */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-black uppercase tracking-wider text-ink-500 dark:text-navy-300">
          {idx + 1} / {questions.length} {t.question}
        </span>
        <div className="flex gap-1.5">
          {questions.map((_, i) => (
            <div
              key={i}
              className={`h-2.5 rounded-full transition-all ${
                i < idx
                  ? "w-4 bg-emerald-500"
                  : i === idx
                  ? "w-7 bg-[#002DFF]"
                  : "w-2.5 bg-slate-200 dark:bg-navy-700"
              }`}
            />
          ))}
        </div>
      </div>

      {/* Badges */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <span className="rounded-full border-2 border-b-2 border-blue-200 bg-blue-50 px-3 py-0.5 text-xs font-black text-[#002DFF] dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-300">
          {t.topicLabel}: {q.topic}
        </span>
        <span className="rounded-full border-2 border-b-2 border-emerald-200 bg-emerald-50 px-3 py-0.5 text-xs font-black text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
          {q.difficulty === "easy" ? t.easy : q.difficulty === "medium" ? t.medium : t.hard}
        </span>
      </div>

      {/* Question Prompt */}
      <p className="text-base sm:text-lg font-black text-navy-900 dark:text-white mb-5 leading-relaxed">
        {q.question}
      </p>

      {/* 3D Option Buttons */}
      <div className="space-y-3 mb-5">
        {q.options.map((opt) => {
          const isCorrect = result && opt.trim() === q.correct.trim();
          const isSelected = opt === selected;
          const isWrong = result && isSelected && !result.correct;

          let btnStyle = "border-slate-200 border-b-4 bg-white hover:bg-slate-50 text-navy-900 dark:border-navy-700 dark:bg-navy-800 dark:text-white";
          if (!result) {
            if (isSelected) {
              btnStyle = "border-[#001A88] border-b-4 bg-[#ddf4ff] text-[#002DFF] shadow-sm dark:border-[#002DFF] dark:bg-blue-950/50 dark:text-blue-200";
            }
          } else if (isCorrect) {
            btnStyle = "border-[#58cc02] border-b-4 bg-[#d7ffb8] text-[#2e6b00] dark:border-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-200";
          } else if (isWrong) {
            btnStyle = "border-[#ff4b4b] border-b-4 bg-[#ffdfe0] text-[#a01818] dark:border-rose-600 dark:bg-rose-950/40 dark:text-rose-200";
          } else {
            btnStyle = "border-slate-200 border-b-4 bg-white/50 text-slate-400 dark:border-navy-800 dark:bg-navy-900/40 dark:text-slate-500 opacity-60";
          }

          return (
            <button
              key={opt}
              type="button"
              disabled={Boolean(result)}
              onClick={() => !result && setSelected(opt)}
              className={`w-full text-left p-4 rounded-2xl border-2 text-sm font-bold transition-all active:translate-y-0.5 active:border-b-2 ${btnStyle}`}
            >
              {opt}
            </button>
          );
        })}
      </div>

      {/* Result feedback */}
      {result && (
        <div className={`p-4 rounded-2xl border-2 border-b-4 mb-5 animate-fade-in ${
          result.correct
            ? "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200"
            : "border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-200"
        }`}>
          <p className="font-black text-sm">
            {result.correct ? `✓ ${t.correctAnswer}` : `✗ ${t.wrongAnswer}`}
          </p>
          {result.explanation && (
            <p className="text-xs sm:text-sm mt-2 leading-relaxed opacity-90">
              💡 {result.explanation}
            </p>
          )}
        </div>
      )}

      {/* Bottom Actions */}
      <div className="flex gap-3">
        {!result ? (
          <button
            type="button"
            onClick={check}
            disabled={!selected || checking}
            className="w-full rounded-2xl border-2 border-b-4 border-[#001A88] bg-[#002DFF] py-3.5 text-center text-xs font-black uppercase tracking-wider text-white shadow-md shadow-blue-500/25 active:translate-y-0.5 active:border-b-2 hover:bg-[#1429f2] disabled:opacity-40 transition-all cursor-pointer"
          >
            {checking ? "⏳..." : t.checkAnswer}
          </button>
        ) : (
          <button
            type="button"
            onClick={next}
            className="w-full rounded-2xl border-2 border-b-4 border-[#001A88] bg-[#002DFF] py-3.5 text-center text-xs font-black uppercase tracking-wider text-white shadow-md shadow-blue-500/25 active:translate-y-0.5 active:border-b-2 hover:bg-[#1429f2] transition-all cursor-pointer"
          >
            {idx + 1 >= questions.length ? `🏁 ${t.finishPractice}` : `${t.nextQuestion} →`}
          </button>
        )}
      </div>
    </div>
  );
}

/* ═══ MAIN PAGE ══════════════════════════════════════════════════ */
export default function PersonalPlanPage() {
  const [selectedSubject, setSelectedSubject] = useState<string>("English");
  const [availableSubjects, setAvailableSubjects] = useState<string[]>([]);
  const [analysis, setAnalysis] = useState<WeekAnalysis | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "topics" | "practice" | "history">("overview");
  const [practiceStarted, setPracticeStarted] = useState(false);
  const [selectedHistory, setSelectedHistory] = useState<HistoryItem | null>(null);
  const autoTriggered = useRef(false);

  // Determine active locale based on the subject
  const subLower = (selectedSubject || "").toLowerCase();
  const isRussianSubject = subLower.includes("rus") || subLower.includes("рус");
  const isEnglishSubject = subLower.includes("eng") || subLower.includes("ingliz") || subLower.includes("ielts") || subLower.includes("cefr");
  const localeKey = isRussianSubject ? "ru" : isEnglishSubject ? "en" : "uz";
  const t = T[localeKey] || T.uz;

  const load = useCallback(async (sub?: string) => {
    setLoading(true);
    try {
      const targetSub = sub || selectedSubject;
      const headers = getAuthHeaders();
      const [aRes, hRes] = await Promise.all([
        fetch(`/api/student/personal-plan/weekly-analysis?subject=${encodeURIComponent(targetSub)}`, { headers }).then(r => r.json()).catch(() => null),
        fetch(`/api/student/personal-plan/analysis-history?subject=${encodeURIComponent(targetSub)}`, { headers }).then(r => r.json()).catch(() => ({ items: [] })),
      ]);
      setAnalysis(aRes);
      setHistory(hRes?.items || []);
      if (Array.isArray(aRes?.available_subjects) && aRes.available_subjects.length) {
        setAvailableSubjects(aRes.available_subjects);
      }
      if (aRes?.selected_subject) {
        setSelectedSubject(aRes.selected_subject);
      }
    } finally {
      setLoading(false);
    }
  }, [selectedSubject]);

  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const generate = useCallback(async () => {
    if (generating) return;
    setGenerating(true);
    try {
      const headers = getAuthHeaders();
      const res = await fetch(`/api/student/personal-plan/weekly-analysis/generate?subject=${encodeURIComponent(selectedSubject)}`, {
        method: "POST",
        headers,
      });
      const data = await res.json();
      if (data) {
        setAnalysis(prev => ({ ...(prev || {}), ...data, exists: true }));
      }
    } finally {
      setGenerating(false);
    }
  }, [generating, selectedSubject]);

  // Polling logic when status is processing or auto trigger if not generated
  useEffect(() => {
    if (!analysis || analysis.status === "done" || analysis.status === "failed") return;

    if (analysis.status === "not_generated" && !autoTriggered.current) {
      autoTriggered.current = true;
      generate();
      return;
    }

    if (analysis.status === "processing") {
      const timer = setInterval(() => {
        load(selectedSubject);
      }, 3500);
      return () => clearInterval(timer);
    }
  }, [analysis?.status, generate, load, selectedSubject]);

  const hasAnalysis = analysis?.exists && analysis?.status === "done";
  const stats = analysis?.test_stats || {};
  const hwStats = analysis?.homework_stats || {};

  const tabs = [
    { id: "overview" as const, label: isRussianSubject ? "📊 Обзор" : isEnglishSubject ? "📊 Overview" : "📊 Umumiy" },
    { id: "topics" as const, label: isRussianSubject ? "📚 Темы" : isEnglishSubject ? "📚 Topics" : "📚 Mavzular" },
    { id: "practice" as const, label: isRussianSubject ? "✍️ Практика" : isEnglishSubject ? "✍️ Practice" : "✍️ Mashq" },
    { id: "history" as const, label: isRussianSubject ? "📅 История" : isEnglishSubject ? "📅 History" : "📅 Tarix" },
  ];

  // Diamondvoy prompts adapted strictly to the subject language
  const getLearnPrompt = (topicName: string) => {
    if (isRussianSubject) {
      return `Объясните мне тему «${topicName}». Я затрудняюсь в тестах по этой теме. После объяснения с правилами и примерами составьте 10 тестовых вопросов для проверки моих знаний.`;
    }
    if (isEnglishSubject) {
      return `Please explain the topic "${topicName}" to me. I am struggling with tests on this topic. After explaining with rules and examples, please generate 10 test questions to check my understanding.`;
    }
    return `Menga «${topicName}» mavzusini tushuntirib bering. Men bu mavzudagi testlarda xatolarga yo'l qo'yyapman. Qoidalar va misollar bilan tushuntirgach, bilimimni tekshirish uchun 10 ta test savolini tuzib bering.`;
  };

  const getQuizPrompt = (topicName: string) => {
    if (isRussianSubject) {
      return `Составьте ровно 10 тестовых вопросов по теме «${topicName}». Варианты не должны повторяться, в каждом вопросе должно быть 4 варианта ответов.`;
    }
    if (isEnglishSubject) {
      return `Please generate exactly 10 test questions on the topic "${topicName}". Make sure options do not repeat, with 4 options per question.`;
    }
    return `«${topicName}» mavzusi bo'yicha aynan 10 ta test savolini tuzib bering. Variantlar takrorlanmasin, har bir savolda 4 tadan variant bo'lsin.`;
  };

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-100 dark:from-navy-950 dark:via-navy-900 dark:to-navy-950 transition-colors pb-16">
      <BadgeAwardModal onNavigateToProfile={() => { if (typeof window !== "undefined") window.location.assign("/?role=student&section=profile"); }} />
      <div className="max-w-3xl mx-auto px-4 py-6 sm:px-6">
        
        {/* Top bar with back navigation and subject switcher */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <a
            href="/?role=student"
            className="inline-flex items-center gap-2 rounded-2xl border-2 border-b-4 border-slate-200 bg-white px-4 py-2 text-xs font-black uppercase tracking-wider text-navy-900 shadow-sm transition-all active:translate-y-0.5 active:border-b-2 hover:border-[#002DFF] dark:border-navy-700 dark:bg-navy-800 dark:text-white"
          >
            <span>←</span>
            <span>{t.backDashboard}</span>
          </a>

          {/* Subject Switcher Filter (English / Russian) */}
          {(availableSubjects.length > 1 || availableSubjects.length === 0) && (
            <div className="flex items-center gap-1.5 rounded-2xl border-2 border-b-4 border-slate-200 bg-white p-1 shadow-sm dark:border-navy-700 dark:bg-navy-900">
              {(availableSubjects.length ? availableSubjects : ["English", "Russian"]).map((sub) => {
                const isSel = sub.toLowerCase() === selectedSubject.toLowerCase();
                const flag = sub.toLowerCase().includes("rus") ? "🇷🇺" : "🇬🇧";
                const label = sub.toLowerCase().includes("rus") ? "Русский" : "English";
                return (
                  <button
                    key={sub}
                    type="button"
                    onClick={() => {
                      setSelectedSubject(sub);
                      load(sub);
                    }}
                    className={`flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 text-xs font-black uppercase tracking-wider transition-all border-2 ${
                      isSel
                        ? "border-[#001A88] border-b-4 bg-[#002DFF] text-white shadow-sm active:translate-y-0.5 active:border-b-2"
                        : "border-transparent text-ink-500 hover:text-navy-900 dark:text-navy-300 dark:hover:text-white"
                    }`}
                  >
                    <span>{flag}</span>
                    <span>{label}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Hero Header Card */}
        <div className="relative overflow-hidden rounded-3xl border-2 border-b-4 border-[#001A88] bg-gradient-to-br from-[#001A88] via-[#002DFF] to-cyan-600 p-6 sm:p-8 text-white shadow-xl shadow-blue-500/10 mb-6">
          <div className="absolute -right-16 -top-16 h-52 w-52 rounded-full bg-white/10 blur-2xl pointer-events-none" />
          <div className="relative flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-xl">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-white/20 px-3 py-1 text-xs font-black uppercase tracking-wider backdrop-blur-md">
                💎 Diamondvoy · {selectedSubject}
              </span>
              <h1 className="text-2xl sm:text-3xl font-black mt-2 leading-tight">
                {t.title}
              </h1>
              <p className="text-xs sm:text-sm text-white/85 mt-2 leading-relaxed">
                {t.subtitle}
              </p>
              {analysis?.week_start && (
                <p className="text-xs font-bold text-cyan-200 mt-2">
                  🗓 {t.weekOf}: {analysis.week_start} — {analysis.week_end}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2 self-start sm:self-auto rounded-2xl border border-white/20 bg-white/10 px-4 py-2.5 text-xs font-black uppercase tracking-wider text-white backdrop-blur-sm shadow-sm">
              <span>{analysis?.status === "processing" ? "⏳" : "🗓"}</span>
              <span>{analysis?.status === "processing" ? t.thinking : `${t.weekOf}: ${analysis?.week_start || ""}`}</span>
            </div>
          </div>
        </div>

        {(generating || analysis?.status === "processing" || (loading && !hasAnalysis)) && (
          <ThinkingAnimation text={t.thinking} detail={t.thinkingDetail} />
        )}

        {!loading && !generating && analysis?.status !== "processing" && (<>
          {/* Tab Bar in Learning Path 3D style */}
          <div className="flex gap-2 mb-6 rounded-2xl border-2 border-b-4 border-slate-200 bg-white p-1.5 dark:border-navy-700 dark:bg-navy-900 shadow-sm overflow-x-auto">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 rounded-xl px-4 py-2.5 text-xs sm:text-sm font-black uppercase tracking-wider transition-all whitespace-nowrap border-2 ${
                  activeTab === tab.id
                    ? "border-[#001A88] border-b-4 bg-[#002DFF] text-white shadow-sm active:translate-y-0.5 active:border-b-2"
                    : "border-transparent text-ink-500 hover:text-navy-900 hover:bg-slate-100 dark:text-navy-300 dark:hover:text-white dark:hover:bg-navy-800"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* ═══ Overview Tab ═══ */}
          {activeTab === "overview" && (
            <div className="space-y-6 animate-fade-in">
              {/* Stat Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="rounded-2xl border-2 border-b-4 border-slate-200 bg-white p-4 shadow-sm dark:border-navy-700 dark:bg-navy-900">
                  <span className="text-2xl">📝</span>
                  <p className="mt-2 text-2xl sm:text-3xl font-black text-navy-900 dark:text-white">
                    {stats.test_count ?? 0}
                  </p>
                  <p className="text-xs font-black uppercase tracking-wider text-ink-500 dark:text-navy-400 mt-1">
                    {t.tests}
                  </p>
                </div>
                <div className="rounded-2xl border-2 border-b-4 border-emerald-300 bg-emerald-50/70 p-4 shadow-sm dark:border-emerald-800 dark:bg-emerald-950/40">
                  <span className="text-2xl">✅</span>
                  <p className="mt-2 text-2xl sm:text-3xl font-black text-emerald-700 dark:text-emerald-300">
                    {stats.total_correct ?? 0}
                  </p>
                  <p className="text-xs font-black uppercase tracking-wider text-emerald-800 dark:text-emerald-400 mt-1">
                    {t.correct}
                  </p>
                </div>
                <div className="rounded-2xl border-2 border-b-4 border-rose-300 bg-rose-50/70 p-4 shadow-sm dark:border-rose-800 dark:bg-rose-950/40">
                  <span className="text-2xl">❌</span>
                  <p className="mt-2 text-2xl sm:text-3xl font-black text-rose-600 dark:text-rose-300">
                    {stats.total_wrong ?? 0}
                  </p>
                  <p className="text-xs font-black uppercase tracking-wider text-rose-700 dark:text-rose-400 mt-1">
                    {t.wrong}
                  </p>
                </div>
                <div className="rounded-2xl border-2 border-b-4 border-blue-300 bg-blue-50/70 p-4 shadow-sm dark:border-blue-800 dark:bg-blue-950/40">
                  <span className="text-2xl">📚</span>
                  <p className="mt-2 text-2xl sm:text-3xl font-black text-[#002DFF] dark:text-blue-300">
                    {hwStats.completed ?? 0}/{hwStats.total ?? 0}
                  </p>
                  <p className="text-xs font-black uppercase tracking-wider text-blue-700 dark:text-blue-400 mt-1">
                    {t.homework}
                  </p>
                </div>
              </div>

              {/* Accuracy Ring Card */}
              {stats.accuracy_pct !== undefined && (
                <div className="flex flex-col items-center justify-center p-6 rounded-3xl border-2 border-b-4 border-slate-200 bg-white dark:border-navy-700 dark:bg-navy-900 shadow-sm">
                  <AccuracyRing pct={stats.accuracy_pct || 0} />
                  <p className="text-sm font-black text-navy-900 dark:text-white mt-3 uppercase tracking-wider">
                    {t.accuracy}
                  </p>
                </div>
              )}

              {/* AI Analysis Narrative */}
              {hasAnalysis && analysis?.analysis && (
                <div className="rounded-3xl border-2 border-b-4 border-blue-200 bg-gradient-to-br from-blue-50 to-indigo-50/50 p-6 dark:border-blue-900 dark:bg-blue-950/30 shadow-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-2xl">💎</span>
                    <h3 className="font-black text-lg text-navy-900 dark:text-white">
                      {t.aiAnalysis}
                    </h3>
                  </div>
                  <p className="text-sm text-navy-950 dark:text-navy-100 leading-relaxed whitespace-pre-line font-medium">
                    {analysis.analysis}
                  </p>
                </div>
              )}

              {/* Recommendations */}
              {hasAnalysis && Array.isArray(analysis?.recommendations) && analysis.recommendations.length > 0 && (
                <div className="rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-6 dark:border-navy-700 dark:bg-navy-900 shadow-sm">
                  <h3 className="font-black text-lg text-navy-900 dark:text-white mb-4 flex items-center gap-2">
                    <span>🎯</span>
                    <span>{t.recommendations}</span>
                  </h3>
                  <div className="space-y-3">
                    {analysis.recommendations.map((rec, i) => (
                      <div key={i} className="flex items-start gap-3 p-3.5 rounded-2xl border-2 border-slate-100 bg-slate-50 dark:border-navy-800 dark:bg-navy-800/60">
                        <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-[#002DFF] text-xs font-black text-white">
                          {i + 1}
                        </span>
                        <p className="text-sm font-semibold text-navy-900 dark:text-navy-100 leading-relaxed">
                          {rec}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {!hasAnalysis && (
                <div className="text-center py-12 rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-6 dark:border-navy-700 dark:bg-navy-900 shadow-sm">
                  <span className="text-5xl block mb-3">🤖</span>
                  <p className="text-navy-900 dark:text-white font-black text-lg">{t.noData}</p>
                  <p className="text-xs sm:text-sm text-ink-500 dark:text-navy-300 mt-2 max-w-md mx-auto leading-relaxed">{t.noDataHint}</p>
                </div>
              )}
            </div>
          )}

          {/* ═══ Topics Tab ═══ */}
          {activeTab === "topics" && (
            <div className="space-y-4 animate-fade-in">
              {hasAnalysis && Array.isArray(analysis?.weak_topics) && analysis.weak_topics.length > 0 ? (
                analysis.weak_topics.map((topic, i) => (
                  <details
                    key={i}
                    className="group rounded-3xl border-2 border-b-4 border-slate-200 bg-white dark:border-navy-700 dark:bg-navy-900 shadow-sm overflow-hidden"
                  >
                    <summary className="flex items-center justify-between p-5 cursor-pointer hover:bg-slate-50 dark:hover:bg-navy-800/50 transition">
                      <div className="flex items-center gap-3">
                        <span className={`w-3.5 h-3.5 rounded-full ${topic.level === "weak" ? "bg-rose-500" : "bg-amber-500"}`} />
                        <span className="font-black text-navy-900 dark:text-white text-base">
                          {topic.topic}
                        </span>
                        <span className={`rounded-full px-2.5 py-0.5 text-xs font-black uppercase tracking-wider ${
                          topic.level === "weak"
                            ? "bg-rose-100 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300"
                            : "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300"
                        }`}>
                          {topic.level}
                        </span>
                      </div>
                      <span className="text-xs font-black text-ink-400 group-open:rotate-180 transition-transform">
                        ▼
                      </span>
                    </summary>
                    <div className="px-5 pb-5 border-t border-slate-100 dark:border-navy-800 pt-4">
                      {topic.explanation && (
                        <p className="text-sm text-navy-800 dark:text-navy-200 mb-4 leading-relaxed font-medium">
                          {topic.explanation}
                        </p>
                      )}
                      {Array.isArray(topic.rules) && topic.rules.length > 0 && (
                        <div className="mb-4">
                          <h4 className="text-xs font-black text-ink-500 dark:text-navy-400 uppercase tracking-wider mb-2">
                            📖 {t.rules}
                          </h4>
                          <div className="space-y-2">
                            {topic.rules.map((rule, j) => (
                              <div key={j} className="p-3.5 rounded-2xl border-2 border-blue-100 bg-blue-50/50 dark:border-blue-900/50 dark:bg-blue-950/30">
                                <p className="text-xs sm:text-sm text-navy-900 dark:text-navy-100 leading-relaxed font-medium">
                                  {rule}
                                </p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {/* Action buttons with language-accurate prompts */}
                      <div className="mt-4 flex flex-wrap gap-2.5 pt-3 border-t border-slate-100 dark:border-navy-800">
                        <button
                          type="button"
                          onClick={() => {
                            if (typeof window === "undefined") return;
                            window.sessionStorage.setItem("diamondvoy:initial-prompt:v1", getLearnPrompt(topic.topic));
                            window.location.assign("/?role=student&section=chats&pane=diamondvoy");
                          }}
                          className="inline-flex items-center gap-2 rounded-2xl border-2 border-b-4 border-[#001A88] bg-[#002DFF] px-4 py-2.5 text-xs font-black uppercase tracking-wider text-white shadow-md shadow-blue-500/25 active:translate-y-0.5 active:border-b-2 hover:bg-[#1429f2] transition-all cursor-pointer"
                        >
                          <span>💬</span>
                          <span>{t.learnWithAi}</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            if (typeof window === "undefined") return;
                            window.sessionStorage.setItem("diamondvoy:initial-prompt:v1", getQuizPrompt(topic.topic));
                            window.location.assign("/?role=student&section=chats&pane=diamondvoy");
                          }}
                          className="inline-flex items-center gap-2 rounded-2xl border-2 border-b-4 border-cyan-700 bg-cyan-600 px-4 py-2.5 text-xs font-black uppercase tracking-wider text-white shadow-md active:translate-y-0.5 active:border-b-2 hover:bg-cyan-700 transition-all cursor-pointer"
                        >
                          <span>🎯</span>
                          <span>{t.generate10Tests}</span>
                        </button>
                      </div>
                    </div>
                  </details>
                ))
              ) : (
                <div className="text-center py-12 rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-6 dark:border-navy-700 dark:bg-navy-900 shadow-sm">
                  <span className="text-4xl block mb-3">🎉</span>
                  <p className="text-navy-900 dark:text-white font-bold">{hasAnalysis ? "No weak topics identified — excellent work!" : t.noData}</p>
                </div>
              )}
            </div>
          )}

          {/* ═══ Practice Tab ═══ */}
          {activeTab === "practice" && (
            <div className="animate-fade-in">
              {hasAnalysis && Array.isArray(analysis?.practice_questions) && analysis.practice_questions.length > 0 ? (
                !practiceStarted ? (
                  <div className="text-center py-12 rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-6 dark:border-navy-700 dark:bg-navy-900 shadow-sm">
                    <span className="text-5xl block mb-3">✍️</span>
                    <h3 className="text-xl font-black text-navy-900 dark:text-white mb-2">{t.practice}</h3>
                    <p className="text-xs sm:text-sm text-ink-500 dark:text-navy-300 mb-6 max-w-sm mx-auto">
                      {t.practiceDesc} ({analysis.practice_questions.length} {t.question})
                    </p>
                    <button
                      onClick={() => setPracticeStarted(true)}
                      className="inline-flex items-center gap-2 rounded-2xl border-2 border-b-4 border-[#001A88] bg-[#002DFF] px-8 py-3.5 text-xs font-black uppercase tracking-wider text-white shadow-md shadow-blue-500/25 active:translate-y-0.5 active:border-b-2 hover:bg-[#1429f2] transition-all cursor-pointer"
                    >
                      <span>{t.startPractice}</span>
                      <span>→</span>
                    </button>
                  </div>
                ) : (
                  <PracticeTest questions={analysis.practice_questions} t={t} />
                )
              ) : (
                <div className="text-center py-12 rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-6 dark:border-navy-700 dark:bg-navy-900 shadow-sm">
                  <span className="text-4xl block mb-3">✍️</span>
                  <p className="text-ink-500 dark:text-navy-300 font-bold">{hasAnalysis ? (isRussianSubject ? "Нет практических вопросов" : isEnglishSubject ? "No practice questions available" : "Amaliy savollar mavjud emas") : t.noData}</p>
                </div>
              )}
            </div>
          )}

          {/* ═══ History Tab ═══ */}
          {activeTab === "history" && (
            <div className="space-y-4 animate-fade-in">
              {selectedHistory ? (
                <div className="rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-6 dark:border-navy-700 dark:bg-navy-900 shadow-sm">
                  <button
                    onClick={() => setSelectedHistory(null)}
                    className="mb-4 inline-flex items-center gap-1.5 rounded-xl border-2 border-b-4 border-slate-200 bg-white px-3 py-1.5 text-xs font-black uppercase text-navy-900 shadow-sm active:translate-y-0.5 active:border-b-2 dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                  >
                    ← Back
                  </button>
                  <h3 className="font-black text-navy-900 dark:text-white text-lg mb-2">
                    {t.weekOf}: {selectedHistory.week_start} — {selectedHistory.week_end}
                  </h3>
                  <p className="text-sm text-navy-800 dark:text-navy-200 leading-relaxed whitespace-pre-line font-medium mt-3">
                    {selectedHistory.analysis}
                  </p>
                  {Array.isArray(selectedHistory.recommendations) && selectedHistory.recommendations.length > 0 && (
                    <div className="mt-5 space-y-2">
                      <h4 className="font-black text-xs uppercase tracking-wider text-ink-500 dark:text-navy-400">
                        🎯 {t.recommendations}
                      </h4>
                      {selectedHistory.recommendations.map((r, i) => (
                        <p key={i} className="text-xs sm:text-sm font-semibold text-navy-800 dark:text-navy-200 pl-3 border-l-2 border-[#002DFF]">
                          {i + 1}. {r}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              ) : history.length > 0 ? (
                history.map((h) => (
                  <button
                    key={h.id}
                    onClick={() => setSelectedHistory(h)}
                    className="w-full text-left p-5 rounded-3xl border-2 border-b-4 border-slate-200 bg-white hover:border-[#002DFF] active:translate-y-0.5 active:border-b-2 dark:border-navy-700 dark:bg-navy-900 shadow-sm transition-all"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-black text-navy-900 dark:text-white text-sm">
                          {t.weekOf}: {h.week_start} — {h.week_end}
                        </p>
                        <p className="text-xs text-ink-500 dark:text-navy-300 mt-1 line-clamp-2">
                          {h.analysis}
                        </p>
                      </div>
                      <span className="text-lg text-ink-400 dark:text-navy-400">›</span>
                    </div>
                  </button>
                ))
              ) : (
                <div className="text-center py-12 rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-6 dark:border-navy-700 dark:bg-navy-900 shadow-sm">
                  <span className="text-4xl block mb-3">📅</span>
                  <p className="text-ink-500 dark:text-navy-300 font-bold">{t.noHistory}</p>
                </div>
              )}
            </div>
          )}
        </>)}
      </div>
    </main>
  );
}
