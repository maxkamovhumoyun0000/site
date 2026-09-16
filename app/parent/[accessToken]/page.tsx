"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

type Row = Record<string, unknown>;

function countPresent(rows: Row[]) {
  return rows.filter((row) => String(row.status || "").toLowerCase() === "present").length;
}

export default function ParentProgressPage() {
  const params = useParams<{ accessToken?: string }>();
  const token = String(params?.accessToken || "");
  const [data, setData] = useState<Row | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    fetch(`/api/parent/progress/${encodeURIComponent(token)}`)
      .then(async (response) => {
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(String(payload?.detail || "Progress topilmadi"));
        return payload;
      })
      .then(setData)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Progress yuklanmadi"));
  }, [token]);

  if (error) {
    return <main className="min-h-screen grid place-items-center p-6 bg-slate-50 dark:bg-navy-950"><section className="premium-card max-w-md text-center"><h1 className="text-xl font-black">Havola faol emas</h1><p className="mt-2 text-ink-500 dark:text-navy-300">{error}</p></section></main>;
  }
  if (!data) {
    return <main className="min-h-screen grid place-items-center bg-slate-50 dark:bg-navy-950"><div className="h-10 w-10 rounded-full border-4 border-cyan-500 border-t-transparent animate-spin" /></main>;
  }

  const student = (data.student || {}) as Row;
  const attendance = (data.attendance || []) as Row[];
  const homework = (data.homework || []) as Row[];
  const tests = (data.tests || []) as Row[];
  const weak = (data.weak_topics || []) as Row[];
  const certificates = (data.certificates || []) as Row[];
  const plan = (data.plan || {}) as Row;
  const tasks = (plan.tasks || []) as Row[];

  return (
    <main className="min-h-screen bg-slate-50 text-navy-950 dark:bg-navy-950 dark:text-white">
      <header className="border-b border-line bg-white/85 px-5 py-6 backdrop-blur dark:border-white/10 dark:bg-navy-900/80">
        <div className="mx-auto max-w-6xl"><p className="text-xs font-black uppercase tracking-[.18em] text-cyan-600">Diamond Education · Ota-ona progressi</p><h1 className="mt-1 text-2xl font-black sm:text-3xl">{String(student.name || "O‘quvchi")}</h1><p className="mt-1 text-sm text-ink-500 dark:text-navy-300">Login ID: {String(student.login_id || "—")} · {String(student.subject || "—")}</p></div>
      </header>
      <section className="mx-auto grid max-w-6xl gap-4 p-5 sm:grid-cols-2 lg:grid-cols-4">
        <article className="premium-card"><p className="text-sm text-ink-500 dark:text-navy-300">Davomat</p><strong className="mt-2 block text-3xl">{countPresent(attendance)}/{attendance.length}</strong><p className="mt-1 text-xs">Oxirgi 40 dars</p></article>
        <article className="premium-card"><p className="text-sm text-ink-500 dark:text-navy-300">Uyga vazifalar</p><strong className="mt-2 block text-3xl">{homework.length}</strong><p className="mt-1 text-xs">Topshiriqlar tarixi</p></article>
        <article className="premium-card"><p className="text-sm text-ink-500 dark:text-navy-300">Testlar</p><strong className="mt-2 block text-3xl">{tests.length}</strong><p className="mt-1 text-xs">Natijalar tarixi</p></article>
        <article className="premium-card"><p className="text-sm text-ink-500 dark:text-navy-300">Sertifikatlar</p><strong className="mt-2 block text-3xl">{certificates.length}</strong><p className="mt-1 text-xs">Tugallangan kurs/modullar</p></article>
      </section>
      <section className="mx-auto grid max-w-6xl gap-5 px-5 pb-10 lg:grid-cols-2">
        <article className="premium-card"><h2 className="text-lg font-black">Bugungi o‘quv rejasi</h2><p className="mt-1 text-sm text-ink-500 dark:text-navy-300">{String(plan.summary || "Reja hali shakllanmoqda")}</p><div className="mt-4 space-y-2">{tasks.length ? tasks.map((task, index) => <div key={String(task.id || index)} className="rounded-xl border border-line p-3 text-sm dark:border-white/10">{String(task.title || "Mashq")}</div>) : <p className="text-sm text-ink-500">Bugun uchun vazifa yo‘q.</p>}</div></article>
        <article className="premium-card"><h2 className="text-lg font-black">E’tibor beriladigan mavzular</h2><div className="mt-4 space-y-2">{weak.length ? weak.map((item, index) => <div key={`${String(item.subject)}-${index}`} className="flex justify-between rounded-xl bg-surface-soft p-3 text-sm dark:bg-white/5"><span>{String(item.subject || "Fan")} · {String(item.topic_key || "Mavzu")}</span><strong>{String(item.mistakes || 0)} xato</strong></div>) : <p className="text-sm text-ink-500">Faol xatolar yo‘q.</p>}</div></article>
        <article className="premium-card"><h2 className="text-lg font-black">Davomat tarixi</h2><div className="mt-4 max-h-72 space-y-2 overflow-auto">{attendance.map((item, index) => <div key={`${String(item.date)}-${index}`} className="flex justify-between border-b border-line py-2 text-sm dark:border-white/10"><span>{String(item.date || "—")}</span><strong>{String(item.status || "—")}</strong></div>)}</div></article>
        <article className="premium-card"><h2 className="text-lg font-black">Test va homework tarixi</h2><div className="mt-4 max-h-72 space-y-2 overflow-auto">{tests.map((item, index) => <div key={`test-${index}`} className="rounded-xl border border-line p-3 text-sm dark:border-white/10"><strong>{String(item.test_type || "Test")}</strong><p className="text-ink-500 dark:text-navy-300">To‘g‘ri: {String(item.correct_count || 0)} · Xato: {String(item.wrong_count || 0)}</p></div>)}{homework.map((item, index) => <div key={`homework-${index}`} className="rounded-xl border border-line p-3 text-sm dark:border-white/10"><strong>{String(item.title || "Uyga vazifa")}</strong><p className="text-ink-500 dark:text-navy-300">{String(item.submission_status || item.status || "—")}</p></div>)}</div></article>
      </section>
    </main>
  );
}
