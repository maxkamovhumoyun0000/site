"use client";

import { FormEvent, useEffect, useRef, useState, useCallback } from "react";
import { useWebT } from "./web-i18n";
import { TestCompletionActions } from "./test-completion-actions";

type Row = Record<string, any>;

export function WeeklyStudyPlan({ apiFetch }: { apiFetch: (path: string, options?: any) => Promise<any> }) {
  const tt = useWebT();
  const [selectedSubject, setSelectedSubject] = useState<string>("English");
  const [availableSubjects, setAvailableSubjects] = useState<string[]>([]);
  const [analysis, setAnalysis] = useState<Row | null>(null);
  const [history, setHistory] = useState<Row[]>([]);
  const [selectedHistory, setSelectedHistory] = useState<Row | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [answerResult, setAnswerResult] = useState<Row | null>(null);
  const [practiceAttemptId, setPracticeAttemptId] = useState("");
  const [practiceCompleted, setPracticeCompleted] = useState(false);
  const [practiceHistory, setPracticeHistory] = useState<Row[]>([]);
  const [selectedPracticeHistory, setSelectedPracticeHistory] = useState<Row | null>(null);
  const [askText, setAskText] = useState("");
  const [askReply, setAskReply] = useState("");
  const [asking, setAsking] = useState(false);
  const autoStarted = useRef(false);

  const isRussian = selectedSubject.toLowerCase().includes("rus");

  const load = useCallback(async (sub?: string) => {
    try {
      const targetSub = sub || selectedSubject;
      const [current, previous, savedPractice] = await Promise.all([
        apiFetch(`/student/personal-plan/weekly-analysis?subject=${encodeURIComponent(targetSub)}`),
        apiFetch(`/student/personal-plan/analysis-history?subject=${encodeURIComponent(targetSub)}`),
        apiFetch("/student/personal-plan/practice-test/history"),
      ]);
      setAnalysis(current || null);
      setHistory(previous?.items || []);
      setPracticeHistory(savedPractice?.items || []);
      if (Array.isArray(current?.available_subjects) && current.available_subjects.length) {
        setAvailableSubjects(current.available_subjects);
      }
      if (current?.selected_subject) {
        setSelectedSubject(current.selected_subject);
      }
    } finally {
      setLoading(false);
    }
  }, [apiFetch, selectedSubject]);

  useEffect(() => {
    load().catch(() => null);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const generate = async () => {
    if (generating) return;
    setGenerating(true);
    try {
      const next = await apiFetch(`/student/personal-plan/weekly-analysis/generate?subject=${encodeURIComponent(selectedSubject)}`, { method: "POST" });
      setAnalysis((current) => ({ ...(current || {}), ...next, exists: true }));
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => {
    if (!analysis || analysis.status === "done") return;
    if (analysis.status === "not_generated" && !autoStarted.current) {
      autoStarted.current = true;
      generate().catch(() => null);
      return;
    }
    if (analysis.status !== "processing") return;
    const timer = window.setInterval(() => load(selectedSubject).catch(() => null), 3500);
    return () => window.clearInterval(timer);
  }, [analysis?.status, selectedSubject]); // eslint-disable-line react-hooks/exhaustive-deps

  const practice = Array.isArray(analysis?.practice_questions) ? analysis.practice_questions : [];
  const currentQuestion = practice[questionIndex];

  const checkAnswer = async () => {
    if (!currentQuestion || !answer || answerResult) return;
    const attemptId = practiceAttemptId || (typeof crypto !== "undefined" ? crypto.randomUUID() : `practice-${Date.now()}-${Math.random()}`);
    if (!practiceAttemptId) setPracticeAttemptId(attemptId);
    const result = await apiFetch("/student/personal-plan/practice-test/check", {
      method: "POST",
      body: {
        ...currentQuestion,
        selected: answer,
        subject: currentQuestion.subject || selectedSubject,
        attempt_id: attemptId,
        question_index: questionIndex + 1,
        total_questions: practice.length,
      },
    });
    setAnswerResult(result || {});
    if (result?.attempt_id) setPracticeAttemptId(String(result.attempt_id));
  };

  const nextQuestion = async () => {
    if (questionIndex + 1 >= practice.length) {
      if (practiceAttemptId) {
        await apiFetch(`/student/personal-plan/practice-test/${encodeURIComponent(practiceAttemptId)}/complete`, { method: "POST" });
        await load(selectedSubject);
      }
      setPracticeCompleted(true);
      return;
    }
    setQuestionIndex((value) => value + 1);
    setAnswer("");
    setAnswerResult(null);
  };

  const askDiamondvoy = async (event: FormEvent) => {
    event.preventDefault();
    const question = askText.trim();
    if (!question || asking) return;
    setAsking(true);
    setAskReply("");
    try {
      const result = await apiFetch("/student/personal-plan/weekly-analysis/ask", {
        method: "POST",
        body: { question, subject: selectedSubject },
      });
      setAskReply(String(result?.answer || ""));
    } finally {
      setAsking(false);
    }
  };

  const shown = selectedHistory || analysis;
  const stats = shown?.test_stats || {};
  const homework = shown?.homework_stats || {};
  const thinking = loading || generating || analysis?.status === "processing" || analysis?.status === "not_generated";

  // Prompts adapted strictly to subject language
  const subLower = (selectedSubject || "").toLowerCase();
  const isEnglish = subLower.includes("eng") || subLower.includes("ingliz") || subLower.includes("ielts") || subLower.includes("cefr");

  const getLearnPrompt = (topic: string) => {
    if (isRussian) {
      return `Объясните мне тему «${topic}». Я затрудняюсь в тестах по этой теме. После объяснения с правилами и примерами составьте 10 тестовых вопросов для проверки моих знаний.`;
    }
    if (isEnglish) {
      return `Please explain the topic "${topic}" to me. I am struggling with tests on this topic. After explaining with rules and examples, please generate 10 test questions to check my understanding.`;
    }
    return `Menga «${topic}» mavzusini tushuntirib bering. Men bu mavzudagi testlarda xatolarga yo'l qo'yyapman. Qoidalar va misollar bilan tushuntirgach, bilimimni tekshirish uchun 10 ta test savolini tuzib bering.`;
  };

  const getQuizPrompt = (topic: string) => {
    if (isRussian) {
      return `Составьте ровно 10 тестовых вопросов по теме «${topic}». Варианты не должны повторяться, в каждом вопросе должно быть 4 варианта ответов.`;
    }
    if (isEnglish) {
      return `Please generate exactly 10 test questions on the topic "${topic}". Make sure options do not repeat, with 4 options per question.`;
    }
    return `«${topic}» mavzusi bo'yicha aynan 10 ta test savolini tuzib bering. Variantlar takrorlanmasin, har bir savolda 4 tadan variant bo'lsin.`;
  };

  return (
    <div className="flex flex-col gap-6 pb-12 animate-fade-in">
      {/* Top Bar: Subject Switcher Filter */}
      {(availableSubjects.length > 1 || availableSubjects.length === 0) && (
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 rounded-2xl border-2 border-b-4 border-slate-200 bg-white p-1.5 shadow-sm dark:border-navy-700 dark:bg-navy-900">
            {(availableSubjects.length ? availableSubjects : ["English", "Russian"]).map((sub) => {
              const isSel = sub.toLowerCase() === selectedSubject.toLowerCase();
              const flag = sub.toLowerCase().includes("rus") ? "🇷🇺" : "🇬🇧";
              const label = sub.toLowerCase().includes("rus") ? "Русский язык" : "English";
              return (
                <button
                  key={sub}
                  type="button"
                  onClick={() => {
                    setSelectedSubject(sub);
                    load(sub);
                  }}
                  className={`flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-black uppercase tracking-wider transition-all border-2 ${
                    isSel
                      ? "border-[#001A88] border-b-4 bg-[#002DFF] text-white shadow-sm active:translate-y-0.5 active:border-b-2"
                      : "border-transparent text-ink-600 hover:text-navy-900 dark:text-navy-300 dark:hover:text-white"
                  }`}
                >
                  <span>{flag}</span>
                  <span>{label}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Hero Header Card */}
      <section className="relative overflow-hidden rounded-3xl border-2 border-b-4 border-[#001A88] bg-gradient-to-br from-[#001A88] via-[#002DFF] to-cyan-600 p-6 sm:p-8 text-white shadow-xl shadow-blue-500/10">
        <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/10 blur-3xl pointer-events-none" />
        <div className="relative max-w-3xl">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white/20 px-3.5 py-1 text-xs font-black uppercase tracking-wider backdrop-blur-md">
            💎 Diamondvoy · {isRussian ? "Русский язык" : "English"}
          </span>
          <h2 className="mt-2 text-2xl sm:text-3xl font-black">
            {isRussian ? "Мой учебный план" : tt("plan.weekly.title", "Shaxsiy o‘quv rejam")}
          </h2>
          <p className="mt-2 text-xs sm:text-sm leading-6 text-white/90">
            {isRussian
              ? "Diamondvoy еженедельно анализирует ваши результаты тестов, ошибки и домашние задания, формируя персональные рекомендации и лёгкие практические упражнения."
              : tt("plan.weekly.subtitle", "Diamondvoy har haftadagi test, xato va uyga vazifa natijalaringizdan sizga mos tushuntirish hamda yengil mashq tayyorlaydi.")}
          </p>
        </div>
      </section>

      {/* Thinking State */}
      {thinking ? (
        <section className="rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-6 dark:border-navy-700 dark:bg-navy-900 shadow-sm flex items-center gap-4">
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-[#002DFF]/10 text-3xl animate-pulse">
            💎
          </span>
          <div>
            <h3 className="font-black text-navy-900 dark:text-white">
              {isRussian ? "Diamondvoy думает…" : tt("plan.weekly.thinking", "Diamondvoy o‘ylanmoqda…")}
            </h3>
            <p className="mt-1 text-xs sm:text-sm text-ink-500 dark:text-navy-300">
              {isRussian
                ? "Анализируются результаты вашей недели. Вы можете закрыть страницу — результат сохранится."
                : tt("plan.weekly.thinkingHint", "Haftalik natijalaringiz tahlil qilinmoqda. Sahifani yopishingiz mumkin — natija tayyor holatda saqlanadi.")}
            </p>
          </div>
        </section>
      ) : null}

      {/* Failed State */}
      {shown?.status === "failed" ? (
        <section className="rounded-3xl border-2 border-b-4 border-rose-300 bg-rose-50 p-6 dark:border-rose-900 dark:bg-rose-950/40">
          <p className="font-black text-rose-700 dark:text-rose-300">
            {isRussian ? "Не удалось подготовить анализ." : tt("plan.weekly.failed", "Tahlilni tayyorlab bo‘lmadi.")}
          </p>
          <button
            className="mt-4 inline-flex items-center gap-2 rounded-2xl border-2 border-b-4 border-rose-700 bg-rose-600 px-5 py-2.5 text-xs font-black uppercase tracking-wider text-white shadow-md active:translate-y-0.5 active:border-b-2 hover:bg-rose-700"
            onClick={generate}
          >
            {isRussian ? "Попробовать снова" : tt("plan.weekly.retry", "Qayta tayyorlash")}
          </button>
        </section>
      ) : null}

      {/* Done State */}
      {shown?.status === "done" ? (
        <>
          {/* Stat Cards */}
          <section className="grid gap-3 sm:grid-cols-3">
            <article className="rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-5 dark:border-navy-700 dark:bg-navy-900 shadow-sm">
              <p className="text-xs font-black uppercase tracking-wider text-ink-500 dark:text-navy-400">
                {isRussian ? "Точность тестов" : tt("plan.weekly.accuracy", "Test aniqligi")}
              </p>
              <p className="mt-2 text-3xl font-black text-[#002DFF] dark:text-blue-400">
                {Number(stats.accuracy_pct || 0)}%
              </p>
              <p className="mt-1 text-xs font-bold text-ink-500 dark:text-navy-300">
                {stats.test_count || 0} {isRussian ? "тестов" : tt("plan.weekly.tests", "ta test")}
              </p>
            </article>

            <article className="rounded-3xl border-2 border-b-4 border-rose-200 bg-rose-50/70 p-5 dark:border-rose-900 dark:bg-rose-950/40 shadow-sm">
              <p className="text-xs font-black uppercase tracking-wider text-rose-700 dark:text-rose-400">
                {isRussian ? "Ошибки и пропуски" : tt("plan.weekly.errors", "Xato va o‘tkazilgan")}
              </p>
              <p className="mt-2 text-3xl font-black text-rose-600 dark:text-rose-300">
                {Number(stats.total_wrong || 0) + Number(stats.total_skipped || 0)}
              </p>
              <p className="mt-1 text-xs font-bold text-rose-600 dark:text-rose-400">
                {isRussian ? "Для повторения" : tt("plan.weekly.reviewReady", "Qayta mashq uchun")}
              </p>
            </article>

            <article className="rounded-3xl border-2 border-b-4 border-emerald-200 bg-emerald-50/70 p-5 dark:border-emerald-900 dark:bg-emerald-950/40 shadow-sm">
              <p className="text-xs font-black uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                {isRussian ? "Домашние задания" : tt("plan.weekly.homework", "Uyga vazifa")}
              </p>
              <p className="mt-2 text-3xl font-black text-emerald-600 dark:text-emerald-300">
                {homework.completed || 0}/{homework.total || 0}
              </p>
              <p className="mt-1 text-xs font-bold text-emerald-700 dark:text-emerald-400">
                {Number(homework.completion_pct || 0)}% {isRussian ? "выполнено" : tt("plan.weekly.done", "bajarilgan")}
              </p>
            </article>
          </section>

          {/* AI Narrative Analysis Card */}
          <section className="rounded-3xl border-2 border-b-4 border-blue-200 bg-gradient-to-br from-blue-50 to-indigo-50/50 p-6 dark:border-blue-900 dark:bg-blue-950/30 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-black uppercase tracking-wider text-[#002DFF] dark:text-blue-300">
                  🗓 {shown.week_start} — {shown.week_end}
                </p>
                <h3 className="mt-1 text-xl font-black text-navy-900 dark:text-white flex items-center gap-2">
                  <span>💎</span>
                  <span>{isRussian ? "Анализ Diamondvoy" : tt("plan.weekly.analysis", "Diamondvoy tahlili")}</span>
                </h3>
              </div>
              {selectedHistory ? (
                <button
                  className="rounded-xl border-2 border-b-4 border-slate-200 bg-white px-3.5 py-1.5 text-xs font-black uppercase text-navy-900 shadow-sm active:translate-y-0.5 active:border-b-2 dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                  onClick={() => setSelectedHistory(null)}
                >
                  {isRussian ? "Вернуться к текущей неделе" : tt("plan.weekly.backCurrent", "Joriy haftaga qaytish")}
                </button>
              ) : null}
            </div>
            <p className="mt-4 whitespace-pre-line text-sm leading-7 text-navy-950 dark:text-navy-100 font-medium">
              {shown.analysis}
            </p>
          </section>

          {/* Weak Topics & Next Steps */}
          <section className="grid gap-4 xl:grid-cols-2">
            {/* Weak Topics */}
            <article className="rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-6 dark:border-navy-700 dark:bg-navy-900 shadow-sm">
              <h3 className="text-lg font-black text-navy-900 dark:text-white flex items-center gap-2">
                <span>📚</span>
                <span>{isRussian ? "Темы для повторения" : tt("plan.weekly.weakTopics", "Tushunib olish kerak bo‘lgan mavzular")}</span>
              </h3>
              <div className="mt-4 space-y-3">
                {(shown.weak_topics || []).map((topic: Row, index: number) => (
                  <div
                    key={`${topic.topic}-${index}`}
                    className="rounded-2xl border-2 border-amber-200 bg-amber-50/50 p-4 dark:border-amber-900/60 dark:bg-amber-950/30"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <strong className="text-sm font-black text-navy-900 dark:text-white">
                        {topic.topic || (isRussian ? "Тема" : tt("plan.weekly.topic", "Mavzu"))}
                      </strong>
                      <span className="rounded-full px-2.5 py-0.5 text-xs font-black uppercase tracking-wider bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">
                        {topic.level === "weak"
                          ? (isRussian ? "Слабо" : tt("plan.weekly.weak", "Zaif"))
                          : (isRussian ? "Нужна практика" : tt("plan.weekly.practice", "Mashq kerak"))}
                      </span>
                    </div>

                    {topic.explanation ? (
                      <p className="mt-2 text-xs sm:text-sm leading-6 text-navy-800 dark:text-navy-200 font-medium">
                        {topic.explanation}
                      </p>
                    ) : null}

                    {Array.isArray(topic.rules) && topic.rules.length ? (
                      <ul className="mt-3 space-y-1.5 text-xs sm:text-sm text-navy-800 dark:text-navy-200 font-medium">
                        {topic.rules.map((rule: string, ruleIndex: number) => (
                          <li key={ruleIndex} className="flex items-start gap-1.5">
                            <span className="text-[#002DFF] font-bold">•</span>
                            <span>{rule}</span>
                          </li>
                        ))}
                      </ul>
                    ) : null}

                    {/* Action buttons with language adaptation */}
                    <div className="mt-4 flex flex-wrap gap-2 pt-3 border-t border-amber-200/80 dark:border-amber-900/60">
                      <button
                        type="button"
                        onClick={() => {
                          if (typeof window === "undefined") return;
                          window.sessionStorage.setItem("diamondvoy:initial-prompt:v1", getLearnPrompt(topic.topic || "ushbu"));
                          window.location.assign("/?role=student&section=chats&pane=diamondvoy");
                        }}
                        className="inline-flex items-center gap-1.5 rounded-xl border-2 border-b-4 border-[#001A88] bg-[#002DFF] px-3.5 py-2 text-xs font-black uppercase tracking-wider text-white shadow-sm active:translate-y-0.5 active:border-b-2 hover:bg-[#1429f2] transition-all cursor-pointer"
                      >
                        <span>💬</span>
                        <span>{isRussian ? "Учить с Diamondvoy" : "Diamondvoy bilan o‘rganish"}</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (typeof window === "undefined") return;
                          window.sessionStorage.setItem("diamondvoy:initial-prompt:v1", getQuizPrompt(topic.topic || "ushbu"));
                          window.location.assign("/?role=student&section=chats&pane=diamondvoy");
                        }}
                        className="inline-flex items-center gap-1.5 rounded-xl border-2 border-b-4 border-cyan-700 bg-cyan-600 px-3.5 py-2 text-xs font-black uppercase tracking-wider text-white shadow-sm active:translate-y-0.5 active:border-b-2 hover:bg-cyan-700 transition-all cursor-pointer"
                      >
                        <span>🎯</span>
                        <span>{isRussian ? "10 тестов по теме" : "10 ta test ishlash"}</span>
                      </button>
                    </div>
                  </div>
                ))}

                {!(shown.weak_topics || []).length ? (
                  <p className="text-sm font-bold text-ink-500 dark:text-navy-300 py-4 text-center">
                    {isRussian ? "Слабых тем не обнаружено — отличный результат! 🎉" : tt("plan.weekly.noWeak", "Hozircha yetarli zaif mavzu aniqlanmadi.")}
                  </p>
                ) : null}
              </div>
            </article>

            {/* Next Steps */}
            <article className="rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-6 dark:border-navy-700 dark:bg-navy-900 shadow-sm">
              <h3 className="text-lg font-black text-navy-900 dark:text-white flex items-center gap-2">
                <span>🎯</span>
                <span>{isRussian ? "Рекомендации" : tt("plan.weekly.nextSteps", "Keyingi qadamlar")}</span>
              </h3>
              <ol className="mt-4 space-y-3">
                {(shown.recommendations || []).map((recommendation: string, index: number) => (
                  <li key={index} className="flex gap-3 text-xs sm:text-sm leading-6 p-3 rounded-2xl border-2 border-slate-100 bg-slate-50 dark:border-navy-800 dark:bg-navy-800/50">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#002DFF] text-xs font-black text-white">
                      {index + 1}
                    </span>
                    <span className="font-semibold text-navy-900 dark:text-navy-100">{recommendation}</span>
                  </li>
                ))}
              </ol>
            </article>
          </section>

          {/* Practice Question Card */}
          {!selectedHistory && currentQuestion && !practiceCompleted ? (
            <section className="rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-6 dark:border-navy-700 dark:bg-navy-900 shadow-sm animate-fade-in">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                <div>
                  <p className="text-xs font-black uppercase tracking-wider text-[#002DFF] dark:text-blue-300">
                    {isRussian ? "Персональная практика" : tt("plan.weekly.easyPractice", "Sizga mos yengil mashq")}
                  </p>
                  <h3 className="mt-1 text-lg font-black text-navy-900 dark:text-white">
                    {currentQuestion.topic || (isRussian ? "Практика" : tt("plan.weekly.practice", "Mashq"))}
                  </h3>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-black text-ink-600 dark:bg-navy-800 dark:text-navy-300">
                  {questionIndex + 1} / {practice.length}
                </span>
              </div>

              <p className="text-base sm:text-lg font-black text-navy-900 dark:text-white mb-5 leading-relaxed">
                {currentQuestion.question}
              </p>

              <div className="grid gap-3 sm:grid-cols-2 mb-4">
                {(currentQuestion.options || []).map((option: string, index: number) => {
                  const isSelected = answer === option;
                  const isCorrect = answerResult && option.trim() === String(currentQuestion.correct || currentQuestion.correct_answer || "").trim();
                  const isWrong = answerResult && isSelected && !answerResult.correct;

                  let btnCls = "border-slate-200 border-b-4 bg-white hover:bg-slate-50 text-navy-900 dark:border-navy-700 dark:bg-navy-800 dark:text-white";
                  if (!answerResult) {
                    if (isSelected) {
                      btnCls = "border-[#001A88] border-b-4 bg-[#ddf4ff] text-[#002DFF] dark:border-[#002DFF] dark:bg-blue-950/50 dark:text-blue-200";
                    }
                  } else if (isCorrect) {
                    btnCls = "border-[#58cc02] border-b-4 bg-[#d7ffb8] text-[#2e6b00] dark:border-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-200";
                  } else if (isWrong) {
                    btnCls = "border-[#ff4b4b] border-b-4 bg-[#ffdfe0] text-[#a01818] dark:border-rose-600 dark:bg-rose-950/40 dark:text-rose-200";
                  } else {
                    btnCls = "border-slate-200 border-b-4 opacity-50";
                  }

                  return (
                    <button
                      key={index}
                      type="button"
                      disabled={Boolean(answerResult)}
                      onClick={() => setAnswer(option)}
                      className={`rounded-2xl border-2 p-4 text-left text-sm font-bold transition-all active:translate-y-0.5 active:border-b-2 ${btnCls}`}
                    >
                      {option}
                    </button>
                  );
                })}
              </div>

              {!answerResult ? (
                <button
                  type="button"
                  className="w-full sm:w-auto rounded-2xl border-2 border-b-4 border-[#001A88] bg-[#002DFF] px-8 py-3 text-xs font-black uppercase tracking-wider text-white shadow-md shadow-blue-500/25 active:translate-y-0.5 active:border-b-2 hover:bg-[#1429f2] disabled:opacity-40 transition-all cursor-pointer"
                  disabled={!answer}
                  onClick={checkAnswer}
                >
                  {isRussian ? "Проверить ответ" : tt("plan.weekly.check", "Javobni tekshirish")}
                </button>
              ) : (
                <div
                  className={`mt-4 rounded-2xl border-2 border-b-4 p-5 ${
                    answerResult.correct
                      ? "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200"
                      : "border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-200"
                  }`}
                >
                  <strong className="font-black text-sm">
                    {answerResult.correct
                      ? (isRussian ? "✓ Верно!" : tt("plan.weekly.correct", "To‘g‘ri!"))
                      : (isRussian ? "✗ Неверно" : tt("plan.weekly.notCorrect", "Hali to‘g‘ri emas."))}
                  </strong>
                  {answerResult.explanation ? (
                    <p className="mt-2 text-xs sm:text-sm leading-6 opacity-90">
                      💡 {answerResult.explanation}
                    </p>
                  ) : null}
                  <button
                    type="button"
                    className="mt-4 rounded-xl border-2 border-b-4 border-[#001A88] bg-[#002DFF] px-6 py-2.5 text-xs font-black uppercase tracking-wider text-white shadow-sm active:translate-y-0.5 active:border-b-2 hover:bg-[#1429f2] transition-all cursor-pointer"
                    onClick={nextQuestion}
                  >
                    {questionIndex + 1 >= practice.length
                      ? (isRussian ? "Завершить практику" : "Mashqni yakunlash")
                      : (isRussian ? "Следующий вопрос →" : tt("plan.weekly.next", "Keyingi mashq"))}
                  </button>
                </div>
              )}
            </section>
          ) : null}

          {/* Practice Completed */}
          {practiceCompleted ? (
            <section className="rounded-3xl border-2 border-b-4 border-emerald-300 bg-emerald-50 p-6 dark:border-emerald-800 dark:bg-emerald-950/40 shadow-sm animate-scale-up">
              <h3 className="text-lg font-black text-emerald-900 dark:text-emerald-200">
                ✓ {isRussian ? "Практика завершена!" : "Mashq yakunlandi"}
              </h3>
              <p className="mt-1 text-xs sm:text-sm text-emerald-800 dark:text-emerald-300">
                {isRussian
                  ? "Вопросы, выбранные и правильные ответы сохранены в истории практики."
                  : "Savol, belgilangan javob va to‘g‘ri javoblar mashq tarixida saqlandi."}
              </p>
            </section>
          ) : null}

          {/* Practice History Review */}
          {selectedPracticeHistory ? (
            <section className="rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-6 dark:border-navy-700 dark:bg-navy-900 shadow-sm">
              <button
                type="button"
                className="mb-4 inline-flex items-center gap-1 rounded-xl border-2 border-b-4 border-slate-200 bg-white px-3 py-1.5 text-xs font-black uppercase text-navy-900 shadow-sm active:translate-y-0.5 active:border-b-2 dark:border-navy-700 dark:bg-navy-800 dark:text-white"
                onClick={() => setSelectedPracticeHistory(null)}
              >
                ← {isRussian ? "Назад" : "Orqaga"}
              </button>
              <h3 className="text-lg font-black text-navy-900 dark:text-white mb-4">
                {isRussian ? "Ответы практики" : "Mashq javoblari"}
              </h3>
              <TestCompletionActions
                testTitle={isRussian ? "Персональная практика" : "Shaxsiy mashq"}
                subject={String(selectedPracticeHistory.subject || selectedSubject)}
                review={(selectedPracticeHistory.items || []).map((item: Row) => ({
                  prompt: String(item.prompt || ""),
                  options: Array.isArray(item.options) ? item.options : [],
                  selected_answer: item.selected_answer,
                  correct_answer: item.correct_answer,
                  is_correct: Boolean(Number(item.is_correct || 0)),
                  explanation: String(item.explanation || ""),
                }))}
              />
            </section>
          ) : practiceHistory.length ? (
            <section className="rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-6 dark:border-navy-700 dark:bg-navy-900 shadow-sm">
              <h3 className="text-lg font-black text-navy-900 dark:text-white mb-4">
                {isRussian ? "История практики" : "Mashq tarixi"}
              </h3>
              <div className="grid gap-3 md:grid-cols-2">
                {practiceHistory.map((item) => (
                  <button
                    type="button"
                    key={String(item.attempt_id)}
                    onClick={() => setSelectedPracticeHistory(item)}
                    className="rounded-2xl border-2 border-b-4 border-slate-200 bg-white p-4 text-left transition-all hover:border-[#002DFF] active:translate-y-0.5 active:border-b-2 dark:border-navy-700 dark:bg-navy-800/80"
                  >
                    <p className="text-xs font-black uppercase tracking-wider text-[#002DFF] dark:text-blue-300">
                      {item.completed_at
                        ? (isRussian ? "Завершенная практика" : "Yakunlangan mashq")
                        : (isRussian ? "Текущая практика" : "Davom etayotgan mashq")}
                    </p>
                    <p className="mt-1 text-sm font-black text-navy-900 dark:text-white">
                      {Number(item.correct || 0)} {isRussian ? "верно" : "to‘g‘ri"} · {Number(item.wrong || 0)} {isRussian ? "ошибок" : "xato"}
                    </p>
                    <p className="mt-2 text-xs font-bold text-ink-500 dark:text-navy-400">
                      {isRussian ? "Открыть вопросы и ответы →" : "Savollar va javoblarni ochish →"}
                    </p>
                  </button>
                ))}
              </div>
            </section>
          ) : null}

          {/* Ask Diamondvoy Section */}
          {!selectedHistory ? (
            <section className="rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-6 dark:border-navy-700 dark:bg-navy-900 shadow-sm">
              <h3 className="text-lg font-black text-navy-900 dark:text-white flex items-center gap-2">
                <span>💬</span>
                <span>{isRussian ? "Спросите у Diamondvoy" : tt("plan.weekly.askTitle", "Diamondvoydan so‘rang")}</span>
              </h3>
              <p className="mt-1 text-xs sm:text-sm text-ink-500 dark:text-navy-300">
                {isRussian
                  ? "Получите подробные объяснения по правилам и сложным темам этой недели."
                  : tt("plan.weekly.askHint", "Aynan shu haftadagi zaif mavzular va qoidalardan tushuntirish oling.")}
              </p>
              <form className="mt-4 flex flex-wrap sm:flex-nowrap gap-2.5" onSubmit={askDiamondvoy}>
                <input
                  className="min-w-0 flex-1 rounded-2xl border-2 border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-navy-900 dark:border-navy-700 dark:bg-navy-800 dark:text-white focus:border-[#002DFF] focus:outline-none"
                  value={askText}
                  onChange={(event) => setAskText(event.target.value)}
                  placeholder={
                    isRussian
                      ? "Например: объясните это правило на простом примере"
                      : tt("plan.weekly.askPlaceholder", "Masalan: bu qoidani oddiy misol bilan tushuntir")
                  }
                />
                <button
                  type="submit"
                  className="rounded-2xl border-2 border-b-4 border-[#001A88] bg-[#002DFF] px-6 py-3 text-xs font-black uppercase tracking-wider text-white shadow-md shadow-blue-500/25 active:translate-y-0.5 active:border-b-2 hover:bg-[#1429f2] disabled:opacity-40 transition-all cursor-pointer"
                  disabled={asking || !askText.trim()}
                >
                  {asking
                    ? (isRussian ? "Пишет…" : tt("plan.weekly.answering", "Javob yozmoqda…"))
                    : (isRussian ? "Спросить" : tt("plan.weekly.ask", "So‘rash"))}
                </button>
              </form>
              {askReply ? (
                <div className="mt-4 rounded-2xl border-2 border-blue-200 bg-blue-50/60 p-4 text-xs sm:text-sm leading-relaxed text-navy-900 dark:border-blue-900 dark:bg-blue-950/30 dark:text-navy-100 font-medium whitespace-pre-line animate-fade-in">
                  {askReply}
                </div>
              ) : null}
            </section>
          ) : null}
        </>
      ) : null}

      {/* History Section */}
      {history.length ? (
        <section className="rounded-3xl border-2 border-b-4 border-slate-200 bg-white p-6 dark:border-navy-700 dark:bg-navy-900 shadow-sm">
          <h3 className="text-lg font-black text-navy-900 dark:text-white mb-4">
            {isRussian ? "История предыдущих недель" : tt("plan.weekly.history", "Oldingi haftalar tahlili")}
          </h3>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {history.map((item) => (
              <button
                key={item.id || item.week_start}
                onClick={() => setSelectedHistory(item)}
                className="rounded-2xl border-2 border-b-4 border-slate-200 bg-white p-4 text-left transition-all hover:border-[#002DFF] active:translate-y-0.5 active:border-b-2 dark:border-navy-700 dark:bg-navy-800/80"
              >
                <p className="text-xs font-black uppercase tracking-wider text-[#002DFF] dark:text-blue-300">
                  {item.week_start} — {item.week_end}
                </p>
                <p className="mt-1 line-clamp-2 text-xs sm:text-sm text-ink-600 dark:text-navy-200 font-semibold">
                  {item.analysis || (isRussian ? "Открыть анализ" : tt("plan.weekly.viewAnalysis", "Tahlilni ochish"))}
                </p>
              </button>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
