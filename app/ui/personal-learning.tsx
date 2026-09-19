"use client";

import { useEffect, useState } from "react";
import { PomodoroFocusStudio } from "./pomodoro-widget";

type Row = Record<string, any>;

export function PersonalLearningPanel({ apiFetch, role, view }: { apiFetch: (path: string, options?: any) => Promise<any>; role: "student" | "teacher" | "support"; view: string }) {
  const student = role === "student";
  const prefix = student ? "/student" : "/staff";
  const title = view === "pomodoro" ? "Pomodoro" : "Student insightlari";
  const [summary, setSummary] = useState<Row>({ week_seconds: 0, sessions: 0 });
  const [insights, setInsights] = useState<Row[]>([]);
  const [notice, setNotice] = useState("");
  const [insightFilter, setInsightFilter] = useState("");

  const load = async () => {
    try {
      const calls: Promise<any>[] = [apiFetch(`${prefix}/pomodoro/summary`)];
      if (!student) calls.push(apiFetch("/teacher/student-insights"));
      const [pomo, extra] = await Promise.all(calls);
      setSummary(pomo || {});
      if (!student) setInsights(extra?.items || []);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Ma'lumot yuklanmadi"); }
  };
  useEffect(() => { const timer = window.setTimeout(() => { void load(); }, 0); return () => window.clearTimeout(timer); }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
    <section className="relative overflow-hidden rounded-3xl border border-cyan-500/20 bg-gradient-to-br from-navy-950 to-indigo-800 p-5 text-white shadow-premium sm:p-7"><div className="absolute -right-16 -top-16 h-48 w-48 rounded-full bg-cyan-400/20 blur-3xl" /><p className="relative text-xs font-black uppercase tracking-[.18em] text-cyan-200">Diamondvoy · {student ? "O'quv vositalari" : "Ish vositalari"}</p><h2 className="relative mt-2 text-2xl font-black">{title}</h2><p className="relative mt-2 max-w-2xl text-sm text-white/75">{view === "pomodoro" ? "Diqqat bilan ishlash va statistikangiz." : "Studentlar qiynalayotgan mavzular va tavsiyalar."}</p></section>
    {notice ? <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-sm font-semibold text-cyan-800 dark:text-cyan-100">{notice}</div> : null}

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
