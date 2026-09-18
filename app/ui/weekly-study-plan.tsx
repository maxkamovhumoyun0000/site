"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useWebT } from "./web-i18n";
import { TestCompletionActions } from "./test-completion-actions";

type Row = Record<string, any>;

export function WeeklyStudyPlan({ apiFetch }: { apiFetch: (path: string, options?: any) => Promise<any> }) {
  const tt = useWebT();
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

  const load = async () => {
    try {
      const [current, previous, savedPractice] = await Promise.all([
        apiFetch("/student/personal-plan/weekly-analysis"),
        apiFetch("/student/personal-plan/analysis-history"),
        apiFetch("/student/personal-plan/practice-test/history"),
      ]);
      setAnalysis(current || null);
      setHistory(previous?.items || []);
      setPracticeHistory(savedPractice?.items || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load().catch(() => null); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const generate = async () => {
    if (generating) return;
    setGenerating(true);
    try {
      const next = await apiFetch("/student/personal-plan/weekly-analysis/generate", { method: "POST" });
      setAnalysis((current) => ({ ...(current || {}), ...next, exists: true }));
    } finally { setGenerating(false); }
  };

  useEffect(() => {
    if (!analysis || analysis.status === "done") return;
    if (analysis.status === "not_generated" && !autoStarted.current) {
      autoStarted.current = true;
      generate().catch(() => null);
      return;
    }
    if (analysis.status !== "processing") return;
    const timer = window.setInterval(() => load().catch(() => null), 3500);
    return () => window.clearInterval(timer);
  }, [analysis?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const practice = Array.isArray(analysis?.practice_questions) ? analysis.practice_questions : [];
  const currentQuestion = practice[questionIndex];
  const checkAnswer = async () => {
    if (!currentQuestion || !answer || answerResult) return;
    const attemptId = practiceAttemptId || (typeof crypto !== "undefined" ? crypto.randomUUID() : `practice-${Date.now()}-${Math.random()}`);
    if (!practiceAttemptId) setPracticeAttemptId(attemptId);
    const result = await apiFetch("/student/personal-plan/practice-test/check", {
      method: "POST",
      body: { ...currentQuestion, selected: answer, subject: currentQuestion.subject || "", attempt_id: attemptId, question_index: questionIndex + 1, total_questions: practice.length },
    });
    setAnswerResult(result || {});
    if (result?.attempt_id) setPracticeAttemptId(String(result.attempt_id));
  };
  const nextQuestion = async () => {
    if (questionIndex + 1 >= practice.length) {
      if (practiceAttemptId) {
        await apiFetch(`/student/personal-plan/practice-test/${encodeURIComponent(practiceAttemptId)}/complete`, { method: "POST" });
        await load();
      }
      setPracticeCompleted(true);
      return;
    }
    setQuestionIndex((value) => value + 1); setAnswer(""); setAnswerResult(null);
  };
  const askDiamondvoy = async (event: FormEvent) => {
    event.preventDefault();
    const question = askText.trim(); if (!question || asking) return;
    setAsking(true); setAskReply("");
    try {
      const result = await apiFetch("/student/personal-plan/weekly-analysis/ask", { method: "POST", body: { question } });
      setAskReply(String(result?.answer || ""));
    } finally { setAsking(false); }
  };

  const shown = selectedHistory || analysis;
  const stats = shown?.test_stats || {};
  const homework = shown?.homework_stats || {};
  const thinking = loading || generating || analysis?.status === "processing" || analysis?.status === "not_generated";

  return <div className="flex flex-col gap-5 pb-10 animate-fade-in">
    <section className="relative overflow-hidden rounded-3xl border border-cyan-400/20 bg-gradient-to-br from-navy-950 via-indigo-900 to-cyan-800 p-6 text-white shadow-premium sm:p-8">
      <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-cyan-300/20 blur-3xl" />
      <div className="relative max-w-3xl"><p className="text-xs font-black uppercase tracking-[.18em] text-cyan-200">Diamondvoy · {tt("plan.weekly.kicker", "Haftalik tahlil")}</p><h2 className="mt-2 text-2xl font-black sm:text-3xl">{tt("plan.weekly.title", "Shaxsiy o‘quv rejam")}</h2><p className="mt-2 text-sm leading-6 text-white/80">{tt("plan.weekly.subtitle", "Diamondvoy har haftadagi test, xato va uyga vazifa natijalaringizdan sizga mos tushuntirish hamda yengil mashq tayyorlaydi.")}</p></div>
    </section>

    {thinking ? <section className="premium-card flex items-center gap-4 border-cyan-500/25 bg-cyan-500/5"><span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-cyan-500/15 text-2xl animate-pulse">💎</span><div><h3 className="font-black">{tt("plan.weekly.thinking", "Diamondvoy o‘ylanmoqda…")}</h3><p className="mt-1 text-sm text-ink-500 dark:text-navy-300">{tt("plan.weekly.thinkingHint", "Haftalik natijalaringiz tahlil qilinmoqda. Sahifani yopishingiz mumkin — natija tayyor holatda saqlanadi.")}</p></div></section> : null}

    {shown?.status === "failed" ? <section className="premium-card border-rose-500/25"><p className="font-bold text-rose-600 dark:text-rose-300">{tt("plan.weekly.failed", "Tahlilni tayyorlab bo‘lmadi.")}</p><button className="btn btn-soft mt-3" onClick={generate}>{tt("plan.weekly.retry", "Qayta tayyorlash")}</button></section> : null}

    {shown?.status === "done" ? <>
      <section className="grid gap-3 sm:grid-cols-3"><article className="premium-card"><p className="text-xs font-black uppercase tracking-wide text-ink-500 dark:text-navy-300">{tt("plan.weekly.accuracy", "Test aniqligi")}</p><p className="mt-2 text-3xl font-black text-cyan-600">{Number(stats.accuracy_pct || 0)}%</p><p className="mt-1 text-xs text-ink-500 dark:text-navy-300">{stats.test_count || 0} {tt("plan.weekly.tests", "ta test")}</p></article><article className="premium-card"><p className="text-xs font-black uppercase tracking-wide text-ink-500 dark:text-navy-300">{tt("plan.weekly.errors", "Xato va o‘tkazilgan")}</p><p className="mt-2 text-3xl font-black text-rose-500">{Number(stats.total_wrong || 0) + Number(stats.total_skipped || 0)}</p><p className="mt-1 text-xs text-ink-500 dark:text-navy-300">{tt("plan.weekly.reviewReady", "Qayta mashq uchun")}</p></article><article className="premium-card"><p className="text-xs font-black uppercase tracking-wide text-ink-500 dark:text-navy-300">{tt("plan.weekly.homework", "Uyga vazifa")}</p><p className="mt-2 text-3xl font-black text-emerald-600">{homework.completed || 0}/{homework.total || 0}</p><p className="mt-1 text-xs text-ink-500 dark:text-navy-300">{Number(homework.completion_pct || 0)}% {tt("plan.weekly.done", "bajarilgan")}</p></article></section>

      <section className="premium-card"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-black uppercase tracking-wide text-cyan-700 dark:text-cyan-300">{shown.week_start} — {shown.week_end}</p><h3 className="mt-1 text-xl font-black">{tt("plan.weekly.analysis", "Diamondvoy tahlili")}</h3></div>{!selectedHistory ? <button className="btn btn-soft text-xs" disabled={generating} onClick={generate}>{tt("plan.weekly.refresh", "Yangilash")}</button> : <button className="btn btn-soft text-xs" onClick={() => setSelectedHistory(null)}>{tt("plan.weekly.backCurrent", "Joriy haftaga qaytish")}</button>}</div><p className="mt-4 whitespace-pre-line text-sm leading-7 text-ink-700 dark:text-navy-100">{shown.analysis}</p></section>

      <section className="grid gap-4 xl:grid-cols-2"><article className="premium-card"><h3 className="text-lg font-black">{tt("plan.weekly.weakTopics", "Tushunib olish kerak bo‘lgan mavzular")}</h3><div className="mt-4 space-y-3">{(shown.weak_topics || []).map((topic: Row, index: number) => <div key={`${topic.topic}-${index}`} className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4"><div className="flex items-center justify-between gap-3"><strong>{topic.topic || tt("plan.weekly.topic", "Mavzu")}</strong><span className="rounded-full bg-amber-500/15 px-2 py-1 text-xs font-black text-amber-700 dark:text-amber-300">{topic.level === "weak" ? tt("plan.weekly.weak", "Zaif") : tt("plan.weekly.practice", "Mashq kerak")}</span></div>{topic.explanation ? <p className="mt-2 text-sm leading-6 text-ink-600 dark:text-navy-200">{topic.explanation}</p> : null}{Array.isArray(topic.rules) && topic.rules.length ? <ul className="mt-3 space-y-1 text-sm text-ink-600 dark:text-navy-200">{topic.rules.map((rule: string, ruleIndex: number) => <li key={ruleIndex}>• {rule}</li>)}</ul> : null}</div>)}{!(shown.weak_topics || []).length ? <p className="text-sm text-ink-500 dark:text-navy-300">{tt("plan.weekly.noWeak", "Hozircha yetarli zaif mavzu aniqlanmadi.")}</p> : null}</div></article><article className="premium-card"><h3 className="text-lg font-black">{tt("plan.weekly.nextSteps", "Keyingi qadamlar")}</h3><ol className="mt-4 space-y-3">{(shown.recommendations || []).map((recommendation: string, index: number) => <li key={index} className="flex gap-3 text-sm leading-6"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-cyan-500/15 text-xs font-black text-cyan-700 dark:text-cyan-300">{index + 1}</span><span>{recommendation}</span></li>)}</ol></article></section>

      {!selectedHistory && currentQuestion && !practiceCompleted ? <section className="premium-card"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-black uppercase tracking-wide text-cyan-700 dark:text-cyan-300">{tt("plan.weekly.easyPractice", "Sizga mos yengil mashq")}</p><h3 className="mt-1 text-lg font-black">{currentQuestion.topic || tt("plan.weekly.practice", "Mashq")}</h3></div><span className="text-xs font-bold text-ink-500">{questionIndex + 1}/{practice.length}</span></div><p className="mt-4 font-semibold leading-6">{currentQuestion.question}</p><div className="mt-4 grid gap-2 sm:grid-cols-2">{(currentQuestion.options || []).map((option: string, index: number) => <button key={index} disabled={Boolean(answerResult)} onClick={() => setAnswer(option)} className={`rounded-xl border p-3 text-left text-sm font-semibold transition ${answer === option ? "border-cyan-500 bg-cyan-500/10" : "border-line hover:border-cyan-400 dark:border-white/10"}`}>{option}</button>)}</div>{!answerResult ? <button className="btn btn-primary mt-4" disabled={!answer} onClick={checkAnswer}>{tt("plan.weekly.check", "Javobni tekshirish")}</button> : <div className={`mt-4 rounded-xl p-4 text-sm ${answerResult.correct ? "bg-emerald-500/10 text-emerald-800 dark:text-emerald-200" : "bg-rose-500/10 text-rose-800 dark:text-rose-200"}`}><strong>{answerResult.correct ? tt("plan.weekly.correct", "To‘g‘ri!") : tt("plan.weekly.notCorrect", "Hali to‘g‘ri emas.")}</strong><p className="mt-2 leading-6">{answerResult.explanation}</p><button className="btn btn-soft mt-3 text-xs" onClick={nextQuestion}>{questionIndex + 1 >= practice.length ? "Mashqni yakunlash" : tt("plan.weekly.next", "Keyingi mashq")}</button></div>}</section> : null}

      {practiceCompleted ? <section className="premium-card border-emerald-500/25 bg-emerald-500/5"><h3 className="text-lg font-black text-emerald-800 dark:text-emerald-200">✓ Mashq yakunlandi</h3><p className="mt-1 text-sm text-ink-600 dark:text-navy-200">Savol, belgilangan javob va to‘g‘ri javoblar mashq tarixida saqlandi.</p></section> : null}

      {selectedPracticeHistory ? <section className="premium-card"><button type="button" className="btn btn-soft mb-4 text-xs" onClick={() => setSelectedPracticeHistory(null)}>← Orqaga</button><h3 className="text-lg font-black">Mashq javoblari</h3><TestCompletionActions testTitle="Shaxsiy mashq" subject={String(selectedPracticeHistory.subject || "")} review={(selectedPracticeHistory.items || []).map((item: Row) => ({ prompt: String(item.prompt || ""), options: Array.isArray(item.options) ? item.options : [], selected_answer: item.selected_answer, correct_answer: item.correct_answer, is_correct: Boolean(Number(item.is_correct || 0)), explanation: String(item.explanation || "") }))} /></section> : practiceHistory.length ? <section className="premium-card"><h3 className="text-lg font-black">Mashq tarixi</h3><div className="mt-4 grid gap-2 md:grid-cols-2">{practiceHistory.map((item) => <button type="button" key={String(item.attempt_id)} onClick={() => setSelectedPracticeHistory(item)} className="rounded-xl border border-line p-3 text-left transition hover:border-cyan-400 dark:border-white/10"><p className="text-xs font-black text-cyan-700 dark:text-cyan-300">{item.completed_at ? "Yakunlangan mashq" : "Davom etayotgan mashq"}</p><p className="mt-1 text-sm font-bold">{Number(item.correct || 0)} to‘g‘ri · {Number(item.wrong || 0)} xato · {Number(item.skipped || 0)} o‘tkazilgan</p><p className="mt-1 text-xs text-ink-500 dark:text-navy-300">Savollar va javoblarni ochish →</p></button>)}</div></section> : null}

      {!selectedHistory ? <section className="premium-card"><h3 className="text-lg font-black">{tt("plan.weekly.askTitle", "Diamondvoydan so‘rang")}</h3><p className="mt-1 text-sm text-ink-500 dark:text-navy-300">{tt("plan.weekly.askHint", "Aynan shu haftadagi zaif mavzular va qoidalardan tushuntirish oling.")}</p><form className="mt-4 flex gap-2" onSubmit={askDiamondvoy}><input className="min-w-0 flex-1 rounded-xl border border-line bg-transparent px-3 py-2 text-sm dark:border-white/10" value={askText} onChange={(event) => setAskText(event.target.value)} placeholder={tt("plan.weekly.askPlaceholder", "Masalan: bu qoidani oddiy misol bilan tushuntir")} /><button className="btn btn-primary" disabled={asking || !askText.trim()}>{asking ? tt("plan.weekly.answering", "Javob yozmoqda…") : tt("plan.weekly.ask", "So‘rash")}</button></form>{askReply ? <div className="mt-4 rounded-xl bg-cyan-500/10 p-4 text-sm leading-6 text-ink-700 dark:text-navy-100">{askReply}</div> : null}</section> : null}
    </> : null}

    {history.length ? <section className="premium-card"><h3 className="text-lg font-black">{tt("plan.weekly.history", "Oldingi haftalar tahlili")}</h3><div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">{history.map((item) => <button key={item.id || item.week_start} onClick={() => setSelectedHistory(item)} className="rounded-xl border border-line p-3 text-left transition hover:border-cyan-400 dark:border-white/10"><p className="text-xs font-black text-cyan-700 dark:text-cyan-300">{item.week_start} — {item.week_end}</p><p className="mt-1 line-clamp-2 text-sm text-ink-600 dark:text-navy-200">{item.analysis || tt("plan.weekly.viewAnalysis", "Tahlilni ochish")}</p></button>)}</div></section> : null}
  </div>;
}
