"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PomodoroFocusStudio } from "./pomodoro-widget";

type Row = Record<string, any>;

export function PersonalLearningPanel({ apiFetch, role, view }: { apiFetch: (path: string, options?: any) => Promise<any>; role: "student" | "teacher" | "support"; view: string }) {
  const student = role === "student";
  const prefix = student ? "/student" : "/staff";
  const title = view === "my-mistakes" ? "Mening xatolarim" : view === "mistake-notebook" ? "Xatolar daftari" : view === "pomodoro" ? "Pomodoro" : "Student insightlari";
  const [notebook, setNotebook] = useState<Row>({ items: [], due_count: 0, total_count: 0, sources: {} });
  const [summary, setSummary] = useState<Row>({ week_seconds: 0, sessions: 0 });
  const [insights, setInsights] = useState<Row[]>([]);
  const [practice, setPractice] = useState<Row | null>(null);
  const [position, setPosition] = useState(0);
  const [chosen, setChosen] = useState("");
  const [result, setResult] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [insightFilter, setInsightFilter] = useState("");

  const load = async () => {
    try {
      const calls: Promise<any>[] = [apiFetch(`${prefix}/pomodoro/summary`)];
      if (student) calls.push(apiFetch("/student/mistake-notebook")); else calls.push(apiFetch("/teacher/student-insights"));
      const [pomo, extra] = await Promise.all(calls);
      setSummary(pomo || {});
      if (student) setNotebook(extra || { items: [] }); else setInsights(extra?.items || []);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Ma'lumot yuklanmadi"); }
  };
  useEffect(() => { const timer = window.setTimeout(() => { void load(); }, 0); return () => window.clearTimeout(timer); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const savePomodoro = async (mode: "work" | "short_break" | "long_break", seconds: number) => { setBusy(true); try { await apiFetch(`${prefix}/pomodoro/sessions`, { method: "POST", body: { mode, planned_seconds: seconds, completed_seconds: seconds, completed: true } }); setNotice("Pomodoro sessiyasi saqlandi"); await load(); } catch (error) { setNotice(error instanceof Error ? error.message : "Saqlanmadi"); } finally { setBusy(false); } };
  const startPractice = async () => { setBusy(true); setNotice(""); try { const next = await apiFetch("/student/mistake-notebook/start", { method: "POST" }); setPractice(next); setPosition(0); setChosen(""); setResult(null); if (!next?.questions?.length) setNotice("Hozircha takrorlashga tayyor xato yo'q."); } catch (error) { setNotice(error instanceof Error ? error.message : "Mashq yuklanmadi"); } finally { setBusy(false); } };
  const submitPractice = async () => { const question = practice?.questions?.[position]; if (!question || !chosen || busy) return; setBusy(true); try { const next = await apiFetch(`/student/mistake-notebook/${question.id}/answer`, { method: "POST", body: { selected_answer: chosen } }); setResult(next || {}); await load(); } catch (error) { setNotice(error instanceof Error ? error.message : "Javob tekshirilmadi"); } finally { setBusy(false); } };
  const nextPractice = () => { if (position + 1 >= (practice?.questions?.length || 0)) { setPractice(null); setChosen(""); setResult(null); return; } setPosition((value) => value + 1); setChosen(""); setResult(null); };
  const current = practice?.questions?.[position];
  const sourceEntries = Object.entries(notebook.sources || {}).filter(([, count]) => Number(count) > 0);

  /* Filtered insights for teacher view */
  const filteredInsights = insightFilter
    ? insights.filter(item => {
        const q = insightFilter.toLowerCase();
        return (String(item.first_name || "").toLowerCase().includes(q)
          || String(item.last_name || "").toLowerCase().includes(q)
          || String(item.login_id || "").toLowerCase().includes(q)
          || String(item.subject || "").toLowerCase().includes(q)
          || String(item.topic_key || "").toLowerCase().includes(q));
      })
    : insights;

  /* Group insights by student for better visualization */
  const groupedInsights = (() => {
    const map = new Map<number, { name: string; login: string; items: Row[]; total: number }>();
    for (const item of filteredInsights) {
      const uid = Number(item.user_id || 0);
      if (!map.has(uid)) map.set(uid, { name: `${item.first_name || ""} ${item.last_name || ""}`.trim() || item.login_id || "Student", login: item.login_id || "", items: [], total: 0 });
      const entry = map.get(uid)!;
      entry.items.push(item);
      entry.total += Number(item.mistakes || 0);
    }
    return Array.from(map.entries()).sort((a, b) => b[1].total - a[1].total);
  })();

  return <div className="flex flex-col gap-5 pb-10 animate-fade-in">
    <section className="relative overflow-hidden rounded-3xl border border-cyan-500/20 bg-gradient-to-br from-navy-950 to-indigo-800 p-5 text-white shadow-premium sm:p-7"><div className="absolute -right-16 -top-16 h-48 w-48 rounded-full bg-cyan-400/20 blur-3xl" /><p className="relative text-xs font-black uppercase tracking-[.18em] text-cyan-200">Diamondvoy · {student ? "O'quv vositalari" : "Ish vositalari"}</p><h2 className="relative mt-2 text-2xl font-black">{title}</h2><p className="relative mt-2 max-w-2xl text-sm text-white/75">{view === "mistake-notebook" ? "Har xato interval bilan qaytadi. To'g'ri ishlaganingiz sari u kamroq chiqadi va yakunda yopiladi." : view === "my-mistakes" ? "Barcha test oqimlaridan yig'ilgan xatolaringiz xaritasi." : view === "saved" ? "Video, kitob va grammatika bo'yicha saqlangan joylaringiz." : view === "pomodoro" ? "Diqqat bilan ishlash va statistikangiz." : "Studentlar qiynalayotgan mavzular va tavsiyalar."}</p></section>
    {notice ? <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-sm font-semibold text-cyan-800 dark:text-cyan-100">{notice}</div> : null}

    {student && (view === "my-mistakes" || view === "mistake-notebook") ? <>
      <section className="grid gap-3 sm:grid-cols-3"><article className="premium-card"><p className="text-xs font-black uppercase tracking-wide text-ink-500 dark:text-navy-300">Faol xatolar</p><p className="mt-2 text-3xl font-black text-rose-500">{notebook.total_count || 0}</p></article><article className="premium-card"><p className="text-xs font-black uppercase tracking-wide text-ink-500 dark:text-navy-300">Bugun qaytariladi</p><p className="mt-2 text-3xl font-black text-amber-500">{notebook.due_count || 0}</p></article><article className="premium-card"><p className="text-xs font-black uppercase tracking-wide text-ink-500 dark:text-navy-300">Test turlari</p><p className="mt-2 text-3xl font-black text-cyan-600">{sourceEntries.length}</p></article></section>
      {sourceEntries.length ? <section className="premium-card"><h3 className="text-lg font-black">Qayerda xato bo'lgan</h3><div className="mt-3 flex flex-wrap gap-2">{sourceEntries.map(([source, count]) => <span key={source} className="rounded-full bg-rose-500/10 px-3 py-1 text-xs font-bold text-rose-700 dark:text-rose-200">{source} · {String(count)}</span>)}</div></section> : null}
      {view === "my-mistakes" ? <section className="premium-card"><h3 className="text-lg font-black">Oxirgi qayta mashqlar</h3><div className="mt-4 space-y-2">{(notebook.items || []).slice(0, 6).map((item: Row) => <div key={item.id} className="rounded-xl border border-line p-3 text-sm dark:border-white/10"><div className="flex justify-between gap-3"><strong>{item.topic_key || item.subject || "Mashq"}</strong><span className="text-xs font-bold text-ink-500 dark:text-navy-300">{item.source_type}</span></div><p className="mt-1 line-clamp-2 text-ink-500 dark:text-navy-300">{item.prompt}</p></div>)}{!(notebook.items || []).length ? <p className="text-sm text-ink-500 dark:text-navy-300">Hozircha takrorlashga tayyor xato yo'q.</p> : null}</div><Link className="btn btn-soft mt-4 text-sm" href="/?role=student&section=mistake-notebook">Xatolar daftarini ochish</Link></section> : null}
      {view === "mistake-notebook" ? <section className="premium-card"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-lg font-black">Xatolarimdan mashq</h3><p className="mt-1 text-sm text-ink-500 dark:text-navy-300">Faqat navbati kelgan savollar chiqadi; har to'g'ri javob keyingi takrorlashni uzoqlashtiradi.</p></div>{!current ? <button className="btn btn-primary" disabled={busy || !(notebook.due_count > 0)} onClick={startPractice}>Mashqni boshlash</button> : null}</div>{current ? <div className="mt-5 rounded-2xl border border-line p-4 dark:border-white/10"><p className="text-xs font-black uppercase tracking-wide text-cyan-700 dark:text-cyan-300">{position + 1}/{practice.questions.length} · {current.topic || current.subject || "Mashq"}</p><p className="mt-3 font-semibold leading-6">{current.question}</p><div className="mt-4 grid gap-2 sm:grid-cols-2">{(current.options || []).map((option: string, index: number) => <button key={index} disabled={Boolean(result)} onClick={() => setChosen(option)} className={`rounded-xl border p-3 text-left text-sm font-semibold transition ${chosen === option ? "border-cyan-500 bg-cyan-500/10" : "border-line hover:border-cyan-400 dark:border-white/10"}`}>{option}</button>)}</div>{!result ? <button className="btn btn-primary mt-4" disabled={!chosen || busy} onClick={submitPractice}>Tekshirish</button> : <div className={`mt-4 rounded-xl p-4 text-sm ${result.correct ? "bg-emerald-500/10 text-emerald-800 dark:text-emerald-200" : "bg-rose-500/10 text-rose-800 dark:text-rose-200"}`}><strong>{result.correct ? "To'g'ri — savol uzoqroq muddatdan keyin qaytadi." : "To'g'ri javobni eslab qoling."}</strong>{!result.correct ? <p className="mt-2">To'g'ri javob: {result.correct_answer}</p> : null}<button className="btn btn-soft mt-3 text-xs" onClick={nextPractice}>{position + 1 < practice.questions.length ? "Keyingi savol" : "Yakunlash"}</button></div>}</div> : null}</section> : null}
    </> : null}

    {!student && view === "student-insights" ? <>
      {/* Summary stats */}
      <section className="grid gap-3 sm:grid-cols-3">
        <article className="premium-card"><p className="text-xs font-black uppercase tracking-wide text-ink-500 dark:text-navy-300">Studentlar soni</p><p className="mt-2 text-3xl font-black text-cyan-600">{groupedInsights.length}</p></article>
        <article className="premium-card"><p className="text-xs font-black uppercase tracking-wide text-ink-500 dark:text-navy-300">Jami faol xatolar</p><p className="mt-2 text-3xl font-black text-rose-500">{insights.reduce((sum, i) => sum + Number(i.mistakes || 0), 0)}</p></article>
        <article className="premium-card"><p className="text-xs font-black uppercase tracking-wide text-ink-500 dark:text-navy-300">Eng ko'p xato mavzular</p><p className="mt-2 text-3xl font-black text-amber-500">{new Set(insights.map(i => i.topic_key)).size}</p></article>
      </section>

      {/* Search filter */}
      <section className="premium-card">
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="text-lg font-black">Studentlar qiynalayotgan mavzular</h3>
          <input value={insightFilter} onChange={e => setInsightFilter(e.target.value)} className="ml-auto min-w-0 max-w-xs rounded-xl border border-line bg-transparent p-2 text-sm dark:border-white/10" placeholder="Student yoki mavzu qidirish..."/>
        </div>

        {/* Grouped by student */}
        <div className="mt-4 space-y-3">
          {groupedInsights.slice(0, 30).map(([uid, data]) => <details key={uid} className="rounded-xl border border-line dark:border-white/10">
            <summary className="flex cursor-pointer items-center justify-between gap-3 p-3">
              <div className="flex items-center gap-3">
                <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-rose-500/10 text-sm font-black text-rose-600">{data.total}</div>
                <div><strong className="text-sm">{data.name}</strong>{data.login ? <span className="ml-2 text-xs text-ink-400">@{data.login}</span> : null}</div>
              </div>
              <span className="text-xs font-bold text-ink-500">{data.items.length} mavzu</span>
            </summary>
            <div className="border-t border-line px-3 pb-3 pt-2 dark:border-white/10">
              <div className="flex flex-wrap gap-2">
                {data.items.map((item, i) => <span key={i} className="rounded-full bg-rose-500/10 px-3 py-1 text-xs font-bold text-rose-700 dark:text-rose-200">{item.subject} · {item.topic_key} · {item.mistakes} xato</span>)}
              </div>
            </div>
          </details>)}
          {!groupedInsights.length ? <p className="py-4 text-center text-sm text-ink-500">Hozircha xato insightlari yo'q.</p> : null}
        </div>
      </section>
    </> : null}

    {view === "pomodoro" ? (
      <PomodoroFocusStudio apiFetch={apiFetch} role={role} initialSummary={summary} />
    ) : null}
  </div>;
}
