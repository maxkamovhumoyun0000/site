"use client";

import { useEffect, useMemo, useState } from "react";
import type { DragEvent } from "react";
import { ModalPortal } from "./modal-portal";
import { SharedTestEditor, TestQuestion, validateTestQuestions } from "./shared-test-editor";

type Subject = "English" | "Russian";
type Topic = { topic_id: string; subject: Subject; level: string; title: string; rule?: string; questions?: Array<{ prompt: string; options: string[]; correct_index: number }> };
const empty = (): Topic => ({ topic_id: "", subject: "English", level: "A1", title: "", rule: "", questions: [] });

export function AdminGrammar({ apiFetch }: { apiFetch: (path: string, options?: any) => Promise<any> }) {
  const [items, setItems] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [subject, setSubject] = useState<"all" | Subject>("all");
  const [editing, setEditing] = useState<Topic | null>(null);
  const [busy, setBusy] = useState(false);
  const [reorderingSubject, setReorderingSubject] = useState<Subject | null>(null);
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dragOverId, setDragOverId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const r = await apiFetch("/admin/grammar/topics");
      setItems(Array.isArray(r?.items) ? r.items : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Grammar yuklanmadi");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = useMemo(() => items.filter((x) => (
    (subject === "all" || x.subject === subject)
    && `${x.title} ${x.topic_id} ${x.level}`.toLowerCase().includes(query.toLowerCase())
  )), [items, query, subject]);

  const groupedItems = useMemo(() => ({
    English: filtered.filter((item) => item.subject === "English"),
    Russian: filtered.filter((item) => item.subject === "Russian"),
  }), [filtered]);

  const canReorder = !busy && !reorderingSubject && !query.trim();

  const remove = async (item: Topic) => {
    if (!window.confirm(`“${item.title}” mavzusini o‘chirasizmi?`)) return;
    setBusy(true);
    try {
      await apiFetch(`/admin/grammar/topics/${encodeURIComponent(item.topic_id)}`, { method: "DELETE" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "O‘chirib bo‘lmadi");
    } finally {
      setBusy(false);
    }
  };

  const clearDragState = () => {
    setDraggedId(null);
    setDragOverId(null);
  };

  const onDragStart = (event: DragEvent<HTMLElement>, item: Topic) => {
    if (!canReorder) {
      event.preventDefault();
      return;
    }
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", item.topic_id);
    setDraggedId(item.topic_id);
    setDragOverId(null);
  };

  const onDragOver = (event: DragEvent<HTMLElement>, item: Topic) => {
    const sourceId = draggedId || event.dataTransfer.getData("text/plain");
    const source = items.find((candidate) => candidate.topic_id === sourceId);
    if (!canReorder || !source || source.subject !== item.subject || source.topic_id === item.topic_id) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    setDragOverId(item.topic_id);
  };

  const onDrop = async (event: DragEvent<HTMLElement>, target: Topic) => {
    event.preventDefault();
    const sourceId = draggedId || event.dataTransfer.getData("text/plain");
    const source = items.find((candidate) => candidate.topic_id === sourceId);
    clearDragState();

    if (!canReorder || !source || source.topic_id === target.topic_id || source.subject !== target.subject) return;

    const orderedForSubject = items.filter((item) => item.subject === source.subject);
    const sourceIndex = orderedForSubject.findIndex((item) => item.topic_id === source.topic_id);
    const targetIndex = orderedForSubject.findIndex((item) => item.topic_id === target.topic_id);
    if (sourceIndex < 0 || targetIndex < 0) return;

    const reorderedForSubject = [...orderedForSubject];
    const [moved] = reorderedForSubject.splice(sourceIndex, 1);
    reorderedForSubject.splice(targetIndex, 0, moved);

    const previousItems = items;
    let nextSubjectIndex = 0;
    const nextItems = items.map((item) => (
      item.subject === source.subject ? reorderedForSubject[nextSubjectIndex++] : item
    ));
    setItems(nextItems);
    setReorderingSubject(source.subject);
    setError("");

    try {
      const response = await apiFetch("/admin/grammar/topics/reorder", {
        method: "POST",
        body: {
          subject: source.subject,
          topic_ids: reorderedForSubject.map((item) => item.topic_id),
        },
      });
      if (Array.isArray(response?.items)) setItems(response.items);
    } catch (e) {
      setItems(previousItems);
      setError(e instanceof Error ? e.message : "Mavzular tartibini saqlab bo‘lmadi");
    } finally {
      setReorderingSubject(null);
    }
  };

  const topicCard = (item: Topic) => (
    <article
      key={item.topic_id}
      draggable={canReorder}
      onDragStart={(event) => onDragStart(event, item)}
      onDragOver={(event) => onDragOver(event, item)}
      onDrop={(event) => void onDrop(event, item)}
      onDragEnd={clearDragState}
      aria-grabbed={draggedId === item.topic_id}
      className={`rounded-2xl border border-line bg-white p-5 shadow-sm transition dark:border-white/10 dark:bg-navy-900/50 ${canReorder ? "cursor-grab active:cursor-grabbing" : ""} ${draggedId === item.topic_id ? "opacity-50" : ""} ${dragOverId === item.topic_id ? "ring-2 ring-cyan-500 ring-offset-2 dark:ring-offset-navy-950" : ""}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <span className="rounded-full bg-cyan-100 px-2 py-1 text-xs font-black text-cyan-800 dark:bg-cyan-400/15 dark:text-cyan-200">
            {item.subject} · {item.level}
          </span>
          <h3 className="mt-3 font-black text-navy-950 dark:text-white">{item.title}</h3>
          <p className="mt-1 text-xs text-ink-500 dark:text-slate-400">{item.questions?.length || 0} ta test savoli</p>
        </div>
        <span
          title={canReorder ? "Tartiblash uchun ushlab torting" : "Qidiruvni tozalab, kartani ushlab torting"}
          className="select-none text-lg font-black tracking-[-2px] text-ink-400 dark:text-slate-500"
          aria-hidden="true"
        >
          ⠿
        </span>
      </div>
      <div className="mt-5 flex gap-2">
        <button className="rounded-lg border border-line px-3 py-2 text-xs font-black dark:border-white/10" onClick={() => setEditing(item)}>Tahrirlash</button>
        <button disabled={busy} className="rounded-lg border border-red-200 px-3 py-2 text-xs font-black text-red-600" onClick={() => remove(item)}>O‘chirish</button>
      </div>
    </article>
  );

  return <section className="space-y-5">
    <div className="flex flex-col gap-3 rounded-2xl border border-line bg-white p-5 shadow-sm dark:border-white/10 dark:bg-navy-900/50 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 className="text-xl font-black text-navy-950 dark:text-white">Grammar mavzulari va qoidalari</h2>
        <p className="mt-1 text-sm text-ink-500 dark:text-slate-300">English va Russian uchun yangi qoida yoki mavzu qo‘shing, izoh va test savollarini yangilang.</p>
      </div>
      <button className="rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-black text-white" onClick={() => setEditing(empty())}>+ Yangi qoida qo‘shish</button>
    </div>
    <div className="flex flex-col gap-3 sm:flex-row">
      <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Mavzu qidirish" className="w-full rounded-xl border border-line bg-white px-4 py-2.5 text-sm dark:border-white/10 dark:bg-navy-900"/>
      <select value={subject} onChange={(e) => setSubject(e.target.value as "all" | Subject)} className="rounded-xl border border-line bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-navy-900"><option value="all">Barcha fanlar</option><option>English</option><option>Russian</option></select>
    </div>
    <p className="rounded-xl border border-dashed border-cyan-200 bg-cyan-50/60 px-4 py-3 text-xs font-semibold text-cyan-900 dark:border-cyan-400/20 dark:bg-cyan-400/10 dark:text-cyan-100">
      <span className="mr-1 text-base" aria-hidden="true">⠿</span>
      Mavzularni kartasidan ushlab tortib tartiblang. Tartib har bir fan uchun alohida saqlanadi va student ilovasi hamda saytda shu ketma-ketlikda chiqadi.{query.trim() ? " Tartiblash uchun qidiruvni tozalang." : ""}
    </p>
    {error && <p className="rounded-xl bg-red-50 p-3 text-sm font-bold text-red-700 dark:bg-red-950/30 dark:text-red-200">{error}</p>}
    {loading ? <p className="p-8 text-center text-sm text-ink-500">Yuklanmoqda…</p> : <div className="space-y-6">
      {(["English", "Russian"] as Subject[]).map((groupSubject) => (
        (subject === "all" || subject === groupSubject) && groupedItems[groupSubject].length > 0 ? <section key={groupSubject}>
          {subject === "all" && <h3 className="mb-3 text-sm font-black uppercase tracking-wider text-ink-500 dark:text-slate-300">{groupSubject}</h3>}
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{groupedItems[groupSubject].map(topicCard)}</div>
        </section> : null
      ))}
    </div>}
    {!loading && !filtered.length && <p className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-ink-500">Mavzu topilmadi.</p>}
    <GrammarModal item={editing} close={() => setEditing(null)} saved={async () => { setEditing(null); await load(); }} apiFetch={apiFetch}/>
  </section>;
}

function GrammarModal({ item, close, saved, apiFetch }: { item: Topic | null; close: () => void; saved: () => Promise<void>; apiFetch: (path: string, options?: any) => Promise<any> }) {
  const [form, setForm] = useState<Topic>(empty()); const [questions, setQuestions] = useState<TestQuestion[]>([]); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  useEffect(() => { if (!item) return; setForm(item); setQuestions((item.questions || []).map((q) => ({ question: q.prompt, options: q.options, correct: q.options[q.correct_index] || "", explanation: "" }))); setError(""); }, [item]);
  if (!item) return null;
  const isExisting = Boolean(item.topic_id);
  const submit = async () => {
    const invalid = questions.length ? validateTestQuestions(questions) : null;
    if (invalid) return setError(invalid);
    if (!form.topic_id.trim() || !form.title.trim()) return setError("ID va mavzu nomini kiriting.");
    if (!(form.rule || "").trim() && questions.length === 0) return setError("Kamida qoida/izoh yoki test savolini kiriting.");
    setBusy(true); setError("");
    try {
      const payload = { ...form, topic_id: form.topic_id.trim(), title: form.title.trim(), questions: questions.map((q) => ({ prompt: q.question, options: q.options, correct_index: Math.max(0, q.options.indexOf(q.correct)) })) };
      await apiFetch(`/admin/grammar/topics${isExisting ? `/${encodeURIComponent(item.topic_id)}` : ""}`, { method: isExisting ? "PUT" : "POST", body: payload });
      await saved();
    } catch (e) { setError(e instanceof Error ? e.message : "Saqlab bo‘lmadi"); } finally { setBusy(false); }
  };
  return <ModalPortal open><div className="overlay-modal-backdrop" onClick={close}><article className="overlay-modal-card max-h-[92vh] w-[min(900px,calc(100vw-24px))] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}><div className="flex items-center justify-between"><h3 className="text-lg font-black">{isExisting ? "Grammar mavzusini tahrirlash" : "Yangi Grammar qoidasi"}</h3><button onClick={close}>✕</button></div><div className="mt-5 grid gap-3 sm:grid-cols-2"><label className="text-sm font-bold">Mavzu ID<input disabled={isExisting} value={form.topic_id} onChange={(e) => setForm({...form, topic_id:e.target.value})} className="mt-1 w-full rounded-lg border p-2 disabled:opacity-60" placeholder="english-a1-present-simple"/></label><label className="text-sm font-bold">Mavzu nomi<input value={form.title} onChange={(e) => setForm({...form, title:e.target.value})} className="mt-1 w-full rounded-lg border p-2"/></label><label className="text-sm font-bold">Fan<select value={form.subject} onChange={(e) => setForm({...form, subject:e.target.value as Topic['subject']})} className="mt-1 w-full rounded-lg border p-2"><option>English</option><option>Russian</option></select></label><label className="text-sm font-bold">Daraja<select value={form.level} onChange={(e) => setForm({...form, level:e.target.value})} className="mt-1 w-full rounded-lg border p-2">{["A1","A2","B1","B2","C1"].map((x)=><option key={x}>{x}</option>)}</select></label></div><label className="mt-3 block text-sm font-bold">Qoida / izoh<textarea value={form.rule || ""} onChange={(e) => setForm({...form, rule:e.target.value})} className="mt-1 min-h-28 w-full rounded-lg border p-2" placeholder="Student ko‘radigan grammar qoidasini yozing"/></label><p className="mt-2 text-xs text-ink-500 dark:text-slate-400">Test savollari ixtiyoriy: faqat qoida saqlansa student uni o‘qiydi, savol qo‘shilganda test boshlanadi.</p><div className="mt-5"><SharedTestEditor title="Test savollari (ixtiyoriy)" questions={questions} onChange={setQuestions}/></div>{error && <p className="mt-3 text-sm font-bold text-red-600">{error}</p>}<div className="mt-6 flex justify-end gap-2"><button className="rounded-lg border px-4 py-2 font-bold" onClick={close}>Bekor qilish</button><button disabled={busy} className="rounded-lg bg-cyan-600 px-4 py-2 font-black text-white disabled:opacity-60" onClick={submit}>{busy ? "Saqlanmoqda…" : "Saqlash"}</button></div></article></div></ModalPortal>;
}
