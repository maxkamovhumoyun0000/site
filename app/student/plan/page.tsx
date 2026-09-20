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

/* ─── i18n ───────────────────────────────────────────────────────── */
const T: Record<string, Record<string, string>> = {
  uz: {
    backDashboard: "Boshqaruv paneli",
    title: "Shaxsiy O'quv Rejam", subtitle: "Diamondvoy sizning haftalik tahlilingizni tayyorlaydi",
    generate: "AI Tahlil Yaratish", refresh: "Yangilash",
    thinking: "Diamondvoy o'ylanmoqda", thinkingDetail: "Sizning test natijalari, xatolar va uy vazifalari tahlil qilinmoqda...",
    weekOf: "Hafta", stats: "Haftalik Statistika", tests: "Testlar",
    correct: "To'g'ri", wrong: "Noto'g'ri", skipped: "O'tkazilgan",
    accuracy: "Aniqlik", homework: "Uy vazifalari", completed: "Bajarildi", of: "dan",
    aiAnalysis: "Diamondvoy Tahlili", weakTopics: "Zaif Mavzular",
    rules: "Qoidalar va Tushuntirish", recommendations: "Tavsiyalar",
    practice: "Mashq Testi", practiceDesc: "Zaif mavzularingiz bo'yicha yengil testlar",
    startPractice: "Mashqni Boshlash", checkAnswer: "Tekshirish", nextQuestion: "Keyingi",
    correctAnswer: "To'g'ri!", wrongAnswer: "Noto'g'ri", explanation: "Tushuntirish",
    history: "Oldingi Haftalar", noHistory: "Hali haftalik tahlil mavjud emas",
    noData: "Bu hafta uchun ma'lumotlar to'planmoqda",
    noDataHint: "Test ishlang, uy vazifalarini bajaring — Diamondvoy siz uchun tahlil tayyorlaydi",
    question: "savol", topicLabel: "Mavzu", easy: "Oson", medium: "O'rta", hard: "Qiyin",
    finishPractice: "Mashqni yakunlash", restartPractice: "Qaytadan",
    congrats: "Ajoyib! Barcha savollarni muvaffaqiyatli bajardingiz!",
    keepGoing: "Yaxshi natija! Xatolar ustida ishlab, bilimingizni mustahkamlang.",
  },
  ru: {
    backDashboard: "Панель управления",
    title: "Мой учебный план", subtitle: "Diamondvoy готовит ваш еженедельный анализ",
    generate: "Создать AI анализ", refresh: "Обновить",
    thinking: "Diamondvoy думает", thinkingDetail: "Анализируются результаты тестов, ошибки и задания...",
    weekOf: "Неделя", stats: "Статистика", tests: "Тесты",
    correct: "Правильно", wrong: "Неправильно", skipped: "Пропущено",
    accuracy: "Точность", homework: "Домашние задания", completed: "Выполнено", of: "из",
    aiAnalysis: "Анализ Diamondvoy", weakTopics: "Слабые темы",
    rules: "Правила и объяснения", recommendations: "Рекомендации",
    practice: "Практический тест", practiceDesc: "Лёгкие тесты по слабым темам",
    startPractice: "Начать практику", checkAnswer: "Проверить", nextQuestion: "Дальше",
    correctAnswer: "Правильно!", wrongAnswer: "Неправильно", explanation: "Объяснение",
    history: "Предыдущие недели", noHistory: "Анализов пока нет",
    noData: "Данные собираются", noDataHint: "Решайте тесты — Diamondvoy подготовит анализ",
    question: "вопрос", topicLabel: "Тема", easy: "Легко", medium: "Средне", hard: "Сложно",
    finishPractice: "Завершить практику", restartPractice: "Заново",
    congrats: "Отлично! Все вопросы выполнены верно!",
    keepGoing: "Хороший результат! Продолжайте закреплять материал.",
  },
  en: {
    backDashboard: "Dashboard",
    title: "My Study Plan", subtitle: "Diamondvoy prepares your weekly analysis",
    generate: "Generate AI Analysis", refresh: "Refresh",
    thinking: "Diamondvoy is thinking", thinkingDetail: "Analyzing your test results, errors and homework...",
    weekOf: "Week of", stats: "Statistics", tests: "Tests",
    correct: "Correct", wrong: "Wrong", skipped: "Skipped",
    accuracy: "Accuracy", homework: "Homework", completed: "Completed", of: "of",
    aiAnalysis: "Diamondvoy Analysis", weakTopics: "Weak Topics",
    rules: "Rules & Explanations", recommendations: "Recommendations",
    practice: "Practice Test", practiceDesc: "Easy tests on your weak topics",
    startPractice: "Start Practice", checkAnswer: "Check", nextQuestion: "Next",
    correctAnswer: "Correct!", wrongAnswer: "Incorrect", explanation: "Explanation",
    history: "Previous Weeks", noHistory: "No weekly analyses yet",
    noData: "Data is being collected", noDataHint: "Take tests, do homework — Diamondvoy will prepare your analysis",
    question: "question", topicLabel: "Topic", easy: "Easy", medium: "Medium", hard: "Hard",
    finishPractice: "Finish Practice", restartPractice: "Restart",
    congrats: "Awesome! You got every question right!",
    keepGoing: "Good effort! Keep practicing your weak areas.",
  },
};

/* ─── ThinkingAnimation ──────────────────────────────────────────── */
function ThinkingAnimation({ text, detail }: { text: string; detail: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      <div className="relative w-20 h-20">
        <div className="absolute inset-0 rounded-full border-4 border-blue-200 dark:border-blue-800" />
        <div className="absolute inset-0 rounded-full border-4 border-t-blue-500 dark:border-t-blue-400 animate-spin" />
        <div className="absolute inset-2 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg">
          <span className="text-2xl animate-pulse">💎</span>
        </div>
      </div>
      <div className="text-center">
        <p className="text-lg font-semibold text-gray-900 dark:text-white animate-pulse">{text}</p>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-xs">{detail}</p>
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
  const r = 36, circ = 2 * Math.PI * r, offset = circ - (pct / 100) * circ;
  const color = pct >= 80 ? "#22c55e" : pct >= 50 ? "#eab308" : "#ef4444";
  return (
    <div className="flex items-center justify-center">
      <svg width="90" height="90" viewBox="0 0 90 90">
        <circle cx="45" cy="45" r={r} fill="none" stroke="#e5e7eb" strokeWidth="7" className="dark:stroke-gray-700" />
        <circle cx="45" cy="45" r={r} fill="none" stroke={color} strokeWidth="7" strokeDasharray={`${circ}`} strokeDashoffset={offset} strokeLinecap="round" className="transition-all duration-1000" style={{ transform: "rotate(-90deg)", transformOrigin: "center" }} />
        <text x="45" y="45" textAnchor="middle" dominantBaseline="central" className="fill-gray-900 dark:fill-white text-lg font-bold">{pct}%</text>
      </svg>
    </div>
  );
}

/* ─── PracticeTest ───────────────────────────────────────────────── */
function PracticeTest({ questions, t }: { questions: PracticeQ[]; t: Record<string, string> }) {
  const [idx, setIdx] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<{ correct: boolean; explanation: string } | null>(null);
  const [checking, setChecking] = useState(false);
  const [score, setScore] = useState(0);
  const [done, setDone] = useState(false);

  const q = questions[idx];
  if (!q || done) return (
    <div className="text-center py-8 animate-fade-in">
      <div className="text-5xl mb-4">🎉</div>
      <p className="text-xl font-bold text-gray-900 dark:text-white">{score}/{questions.length} {t.correct}</p>
      <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">{score === questions.length ? t.congrats : t.keepGoing}</p>
      <button onClick={() => { setIdx(0); setSelected(null); setResult(null); setScore(0); setDone(false); }}
        className="mt-4 px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-medium transition shadow-md">
        ↺ {t.restartPractice}
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
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">{idx + 1}/{questions.length} {t.question}</span>
        <div className="flex gap-1">{questions.map((_, i) => (
          <div key={i} className={`w-2 h-2 rounded-full transition-all ${i < idx ? "bg-green-500" : i === idx ? "bg-blue-500 scale-125" : "bg-gray-300 dark:bg-gray-600"}`} />
        ))}</div>
      </div>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-full font-medium">{t.topicLabel}: {q.topic}</span>
        <span className="text-xs px-2 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400 rounded-full font-medium">{q.difficulty === "easy" ? t.easy : q.difficulty === "medium" ? t.medium : t.hard}</span>
      </div>
      <p className="text-base font-semibold text-gray-900 dark:text-white mb-4 leading-relaxed">{q.question}</p>
      <div className="space-y-2 mb-4">
        {q.options.map(opt => {
          const isCorrect = result && opt.trim() === q.correct.trim();
          const isSelected = opt === selected;
          const isWrong = result && isSelected && !result.correct;
          let cls = "w-full text-left p-3.5 rounded-xl border-2 transition-all font-medium text-sm ";
          if (!result) cls += isSelected ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 ring-2 ring-blue-200 dark:ring-blue-800" : "border-gray-200 dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-700 text-gray-800 dark:text-gray-200";
          else if (isCorrect) cls += "border-green-500 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400";
          else if (isWrong) cls += "border-red-500 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400";
          else cls += "border-gray-200 dark:border-gray-700 text-gray-400 dark:text-gray-500 opacity-60";
          return <button key={opt} className={cls} onClick={() => !result && setSelected(opt)} disabled={!!result}>{opt}</button>;
        })}
      </div>
      {result && (
        <div className={`p-4 rounded-xl mb-4 ${result.correct ? "bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800" : "bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800"}`}>
          <p className={`font-bold text-sm ${result.correct ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>{result.correct ? `✓ ${t.correctAnswer}` : `✗ ${t.wrongAnswer}`}</p>
          {result.explanation && <p className="text-sm text-gray-700 dark:text-gray-300 mt-2 leading-relaxed">💡 {result.explanation}</p>}
        </div>
      )}
      <div className="flex gap-3">
        {!result ? (
          <button onClick={check} disabled={!selected || checking} className="flex-1 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white rounded-xl text-sm font-semibold transition shadow-sm">{checking ? "⏳" : t.checkAnswer}</button>
        ) : (
          <button onClick={next} className="flex-1 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold transition shadow-sm">{idx + 1 >= questions.length ? `🏁 ${t.finishPractice}` : `${t.nextQuestion} →`}</button>
        )}
      </div>
    </div>
  );
}

/* ═══ MAIN PAGE ══════════════════════════════════════════════════ */
export default function PersonalPlanPage() {
  const localeRaw = typeof window !== "undefined" ? localStorage.getItem("diamond_locale") || "uz" : "uz";
  const locale = (["uz", "ru", "en"].includes(localeRaw) ? localeRaw : "uz") as "uz" | "ru" | "en";
  const t = T[locale] || T.uz;

  const [analysis, setAnalysis] = useState<WeekAnalysis | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "topics" | "practice" | "history">("overview");
  const [practiceStarted, setPracticeStarted] = useState(false);
  const [selectedHistory, setSelectedHistory] = useState<HistoryItem | null>(null);
  const autoTriggered = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const headers = getAuthHeaders();
      const [aRes, hRes] = await Promise.all([
        fetch("/api/student/personal-plan/weekly-analysis", { headers }).then(r => r.json()).catch(() => null),
        fetch("/api/student/personal-plan/analysis-history", { headers }).then(r => r.json()).catch(() => ({ items: [] })),
      ]);
      setAnalysis(aRes);
      setHistory(hRes?.items || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const generate = useCallback(async () => {
    if (generating) return;
    setGenerating(true);
    try {
      const headers = getAuthHeaders();
      const res = await fetch("/api/student/personal-plan/weekly-analysis/generate", {
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
  }, [generating]);

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
        load();
      }, 3500);
      return () => clearInterval(timer);
    }
  }, [analysis?.status, generate, load]);

  const hasAnalysis = analysis?.exists && analysis?.status === "done";
  const stats = analysis?.test_stats || {};
  const hwStats = analysis?.homework_stats || {};
  const tabs = [
    { id: "overview" as const, label: locale === "uz" ? "📊 Umumiy" : locale === "ru" ? "📊 Обзор" : "📊 Overview" },
    { id: "topics" as const, label: locale === "uz" ? "📚 Mavzular" : locale === "ru" ? "📚 Темы" : "📚 Topics" },
    { id: "practice" as const, label: locale === "uz" ? "✍️ Mashq" : locale === "ru" ? "✍️ Практика" : "✍️ Practice" },
    { id: "history" as const, label: locale === "uz" ? "📅 Tarix" : locale === "ru" ? "📅 История" : "📅 History" },
  ];

  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-50 via-white to-gray-50 dark:from-gray-950 dark:via-gray-900 dark:to-gray-950 transition-colors">
      <BadgeAwardModal onNavigateToProfile={() => { if (typeof window !== "undefined") window.location.assign("/?role=student&section=profile"); }} />
      <div className="max-w-3xl mx-auto px-4 py-6 sm:px-6">
        {/* Back navigation */}
        <div className="mb-4">
          <a
            href="/?role=student"
            className="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 dark:border-gray-800 bg-white/80 dark:bg-gray-800/80 px-3.5 py-1.5 text-xs font-semibold text-gray-700 dark:text-gray-300 backdrop-blur-sm transition-all hover:bg-gray-100 dark:hover:bg-gray-700 shadow-sm"
          >
            <span>←</span>
            <span>{t.backDashboard}</span>
          </a>
        </div>

        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white flex items-center gap-2">💎 {t.title}</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{t.subtitle}</p>
            {analysis?.week_start && <p className="text-xs text-blue-600 dark:text-blue-400 mt-1 font-medium">{t.weekOf}: {analysis.week_start} — {analysis.week_end}</p>}
          </div>
          <button onClick={generate} disabled={generating || analysis?.status === "processing"}
            className="px-4 py-2.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:opacity-60 text-white rounded-xl text-sm font-semibold transition-all shadow-md hover:shadow-lg flex items-center gap-2">
            {generating || analysis?.status === "processing" ? "⏳" : "✨"} {hasAnalysis ? t.refresh : t.generate}
          </button>
        </div>

        {(generating || analysis?.status === "processing" || (loading && !hasAnalysis)) && (
          <ThinkingAnimation text={t.thinking} detail={t.thinkingDetail} />
        )}

        {!loading && !generating && analysis?.status !== "processing" && (<>
          {/* Tab Bar */}
          <div className="flex gap-1 mb-6 bg-gray-100 dark:bg-gray-800/60 rounded-xl p-1 overflow-x-auto">
            {tabs.map(tab => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                className={`flex-1 px-3 py-2.5 rounded-lg text-xs sm:text-sm font-semibold transition-all whitespace-nowrap ${activeTab === tab.id ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm" : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"}`}>
                {tab.label}
              </button>
            ))}
          </div>

          {/* ═══ Overview ═══ */}
          {activeTab === "overview" && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-4 rounded-2xl bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 shadow-sm">
                  <div className="flex items-center gap-3"><div className="w-10 h-10 rounded-xl flex items-center justify-center text-lg bg-blue-100 dark:bg-blue-900/30">📝</div><div><p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.test_count ?? 0}</p><p className="text-xs text-gray-500 dark:text-gray-400">{t.tests}</p></div></div>
                </div>
                <div className="p-4 rounded-2xl bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 shadow-sm">
                  <div className="flex items-center gap-3"><div className="w-10 h-10 rounded-xl flex items-center justify-center text-lg bg-green-100 dark:bg-green-900/30">✅</div><div><p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.total_correct ?? 0}</p><p className="text-xs text-gray-500 dark:text-gray-400">{t.correct}</p></div></div>
                </div>
                <div className="p-4 rounded-2xl bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 shadow-sm">
                  <div className="flex items-center gap-3"><div className="w-10 h-10 rounded-xl flex items-center justify-center text-lg bg-red-100 dark:bg-red-900/30">❌</div><div><p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.total_wrong ?? 0}</p><p className="text-xs text-gray-500 dark:text-gray-400">{t.wrong}</p></div></div>
                </div>
                <div className="p-4 rounded-2xl bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 shadow-sm">
                  <div className="flex items-center gap-3"><div className="w-10 h-10 rounded-xl flex items-center justify-center text-lg bg-purple-100 dark:bg-purple-900/30">📚</div><div><p className="text-2xl font-bold text-gray-900 dark:text-white">{hwStats.completed ?? 0}/{hwStats.total ?? 0}</p><p className="text-xs text-gray-500 dark:text-gray-400">{t.homework}</p></div></div>
                </div>
              </div>

              {(stats.accuracy_pct !== undefined) && (
                <div className="flex flex-col items-center py-4 bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700">
                  <AccuracyRing pct={stats.accuracy_pct || 0} />
                  <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mt-2">{t.accuracy}</p>
                </div>
              )}

              {hasAnalysis && analysis?.analysis && (
                <div className="bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 border border-blue-200 dark:border-blue-800 rounded-2xl p-5 shadow-sm">
                  <div className="flex items-center gap-2 mb-3"><span className="text-lg">💎</span><h3 className="font-bold text-gray-900 dark:text-white">{t.aiAnalysis}</h3></div>
                  <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-line">{analysis.analysis}</p>
                </div>
              )}

              {hasAnalysis && Array.isArray(analysis?.recommendations) && analysis.recommendations.length > 0 && (
                <div className="bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-2xl p-5 shadow-sm">
                  <h3 className="font-bold text-gray-900 dark:text-white mb-3 flex items-center gap-2">🎯 {t.recommendations}</h3>
                  <div className="space-y-2">{analysis.recommendations.map((rec, i) => (
                    <div key={i} className="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-xl">
                      <span className="text-blue-500 font-bold text-sm mt-0.5">{i + 1}</span>
                      <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{rec}</p>
                    </div>
                  ))}</div>
                </div>
              )}

              {!hasAnalysis && (
                <div className="text-center py-12 bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700">
                  <span className="text-5xl block mb-3">🤖</span>
                  <p className="text-gray-600 dark:text-gray-400 font-medium">{t.noData}</p>
                  <p className="text-sm text-gray-400 dark:text-gray-500 mt-1 max-w-sm mx-auto">{t.noDataHint}</p>
                  <button onClick={generate} className="mt-5 px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-semibold text-sm shadow-md hover:shadow-lg transition-all">✨ {t.generate}</button>
                </div>
              )}
            </div>
          )}

          {/* ═══ Topics ═══ */}
          {activeTab === "topics" && (
            <div className="space-y-4">
              {hasAnalysis && Array.isArray(analysis?.weak_topics) && analysis.weak_topics.length > 0 ? analysis.weak_topics.map((topic, i) => (
                <details key={i} className="group bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-2xl overflow-hidden shadow-sm">
                  <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition">
                    <div className="flex items-center gap-3">
                      <span className={`w-3 h-3 rounded-full ${topic.level === "weak" ? "bg-red-500" : "bg-yellow-500"}`} />
                      <span className="font-semibold text-gray-900 dark:text-white text-sm">{topic.topic}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${topic.level === "weak" ? "bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400" : "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400"}`}>{topic.level}</span>
                    </div>
                    <svg className="w-5 h-5 text-gray-400 transition group-open:rotate-180" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                  </summary>
                  <div className="px-4 pb-4 border-t border-gray-100 dark:border-gray-700 pt-3">
                    {topic.explanation && <p className="text-sm text-gray-700 dark:text-gray-300 mb-3 leading-relaxed">{topic.explanation}</p>}
                    {Array.isArray(topic.rules) && topic.rules.length > 0 && (
                      <div><h4 className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase mb-2">📖 {t.rules}</h4>
                        <div className="space-y-2">{topic.rules.map((rule, j) => (
                          <div key={j} className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl"><p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed">{rule}</p></div>
                        ))}</div>
                      </div>
                    )}
                    <div className="mt-4 flex flex-wrap gap-2 pt-3 border-t border-gray-100 dark:border-gray-700/60">
                      <button
                        type="button"
                        onClick={() => {
                          if (typeof window === "undefined") return;
                          window.sessionStorage.setItem("diamondvoy:initial-prompt:v1", `Menga “${topic.topic}” mavzusini tushuntirib bering. Men bu mavzuda testlarda qiynalyapman. Qoidalar va misollar bilan tushuntirgach, bilimimni tekshirish uchun 10 ta test tuzib bering.`);
                          window.location.assign("/?role=student&section=chats&pane=diamondvoy");
                        }}
                        className="inline-flex items-center gap-1.5 rounded-xl bg-cyan-500 px-3.5 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-cyan-600 dark:text-navy-950"
                      >
                        <span>💬</span>
                        <span>Diamondvoy bilan o‘rganish</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (typeof window === "undefined") return;
                          window.sessionStorage.setItem("diamondvoy:initial-prompt:v1", `“${topic.topic}” mavzusi bo‘yicha menga roppa-rosa 10 ta test savolini tuzib bering. Variantlar takrorlanmasin, 4 ta variant bo‘lsin.`);
                          window.location.assign("/?role=student&section=chats&pane=diamondvoy");
                        }}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-cyan-500/30 bg-cyan-50 px-3.5 py-2 text-xs font-bold text-cyan-700 transition hover:bg-cyan-100 dark:bg-cyan-950/30 dark:text-cyan-300 dark:hover:bg-cyan-950/50"
                      >
                        <span>🎯</span>
                        <span>10 ta test ishlash</span>
                      </button>
                    </div>
                  </div>
                </details>
              )) : (
                <div className="text-center py-12"><span className="text-4xl block mb-3">📚</span><p className="text-gray-500 dark:text-gray-400">{hasAnalysis ? "Zaif mavzular topilmadi — yaxshi natija! 🎉" : t.noData}</p></div>
              )}
            </div>
          )}

          {/* ═══ Practice ═══ */}
          {activeTab === "practice" && (
            <div>
              {hasAnalysis && Array.isArray(analysis?.practice_questions) && analysis.practice_questions.length > 0 ? (
                !practiceStarted ? (
                  <div className="text-center py-12 bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700">
                    <span className="text-5xl block mb-3">✍️</span>
                    <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">{t.practice}</h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-6 max-w-sm mx-auto">{t.practiceDesc} ({analysis.practice_questions.length} {t.question})</p>
                    <button onClick={() => setPracticeStarted(true)} className="px-8 py-3 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 text-white rounded-xl font-semibold text-sm shadow-md transition-all">{t.startPractice} →</button>
                  </div>
                ) : (
                  <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5 shadow-sm">
                    <PracticeTest questions={analysis.practice_questions} t={t} />
                  </div>
                )
              ) : (
                <div className="text-center py-12"><span className="text-4xl block mb-3">✍️</span><p className="text-gray-500 dark:text-gray-400">{hasAnalysis ? "Mashq savollari mavjud emas" : `${t.noData}. ${t.generate} tugmasini bosing.`}</p></div>
              )}
            </div>
          )}

          {/* ═══ History ═══ */}
          {activeTab === "history" && (
            <div className="space-y-4">
              {selectedHistory ? (
                <div>
                  <button onClick={() => setSelectedHistory(null)} className="text-sm text-blue-600 dark:text-blue-400 hover:underline mb-4 inline-flex items-center gap-1">← Orqaga</button>
                  <div className="bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-2xl p-5 shadow-sm">
                    <h3 className="font-bold text-gray-900 dark:text-white mb-1">{t.weekOf}: {selectedHistory.week_start} — {selectedHistory.week_end}</h3>
                    <p className="text-sm text-gray-700 dark:text-gray-300 mt-3 leading-relaxed whitespace-pre-line">{selectedHistory.analysis}</p>
                    {Array.isArray(selectedHistory.recommendations) && selectedHistory.recommendations.length > 0 && (
                      <div className="mt-4 space-y-2">
                        <h4 className="font-semibold text-sm text-gray-800 dark:text-gray-200">🎯 {t.recommendations}</h4>
                        {selectedHistory.recommendations.map((r, i) => <p key={i} className="text-sm text-gray-600 dark:text-gray-400 pl-4">{i + 1}. {r}</p>)}
                      </div>
                    )}
                  </div>
                </div>
              ) : history.length > 0 ? history.map(h => (
                <button key={h.id} onClick={() => setSelectedHistory(h)} className="w-full text-left p-4 bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-2xl hover:shadow-md transition-all">
                  <div className="flex items-center justify-between">
                    <div><p className="font-semibold text-gray-900 dark:text-white text-sm">{t.weekOf}: {h.week_start} — {h.week_end}</p><p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">{h.analysis}</p></div>
                    <svg className="w-5 h-5 text-gray-400 flex-shrink-0 ml-2" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                  </div>
                </button>
              )) : (
                <div className="text-center py-12"><span className="text-4xl block mb-3">📅</span><p className="text-gray-500 dark:text-gray-400">{t.noHistory}</p></div>
              )}
            </div>
          )}
        </>)}
      </div>
    </main>
  );
}
