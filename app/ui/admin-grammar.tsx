"use client";

import { useEffect, useMemo, useState } from "react";
import type { DragEvent } from "react";
import { ModalPortal } from "./modal-portal";
import { SharedTestEditor, TestQuestion, validateTestQuestions } from "./shared-test-editor";

type Subject = "English" | "Russian";
type Topic = { topic_id: string; subject: Subject; level: string; title: string; rule?: string; questions?: Array<{ prompt: string; options: string[]; correct_index: number }> };
const ENGLISH_LEVELS = ["A1", "A2", "B1", "B2", "C1"] as const;
type DropTarget = {
  subject: Subject;
  index: number;
  targetId?: string;
  side?: "before" | "after";
};

const empty = (): Topic => ({ topic_id: "", subject: "English", level: "A1", title: "", rule: "", questions: [] });

export function AdminGrammar({ apiFetch }: { apiFetch: (path: string, options?: any) => Promise<any> }) {
  const [items, setItems] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSubject, setSelectedSubject] = useState<Subject>("English");
  const [selectedEnglishLevel, setSelectedEnglishLevel] = useState<string>("A1");
  const [editing, setEditing] = useState<Topic | null>(null);
  const [busy, setBusy] = useState(false);
  const [reorderingSubject, setReorderingSubject] = useState<Subject | null>(null);
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<DropTarget | null>(null);
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

  const groupedItems = useMemo(() => ({
    English: items.filter((item) => item.subject === "English"),
    Russian: items.filter((item) => item.subject === "Russian"),
  }), [items]);

  const visibleItems = useMemo(() => ({
    English: selectedSubject === "English"
      ? groupedItems.English.filter((item) => item.level === selectedEnglishLevel)
      : [],
    Russian: selectedSubject === "Russian" ? groupedItems.Russian : [],
  }), [groupedItems, selectedEnglishLevel, selectedSubject]);

  const canReorder = !busy && !reorderingSubject;

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
    setDropTarget(null);
  };

  const onDragStart = (event: DragEvent<HTMLElement>, item: Topic) => {
    if (!canReorder) {
      event.preventDefault();
      return;
    }
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", item.topic_id);
    setDraggedId(item.topic_id);
    setDropTarget(null);
  };

  const sourceForEvent = (event: DragEvent<HTMLElement>) => {
    const sourceId = draggedId || event.dataTransfer.getData("text/plain");
    return items.find((candidate) => candidate.topic_id === sourceId);
  };

  const insertionIndexForCard = (event: DragEvent<HTMLElement>, index: number) => {
    const rect = event.currentTarget.getBoundingClientRect();
    // Cards are a grid on desktop and a vertical list on mobile.  Use the
    // visible direction in each layout: left/right on desktop, top/bottom
    // on mobile.  This makes the insertion point unambiguous.
    const desktopGrid = typeof window !== "undefined" && window.matchMedia("(min-width: 768px)").matches;
    const after = desktopGrid
      ? event.clientX >= rect.left + rect.width / 2
      : event.clientY >= rect.top + rect.height / 2;
    return { index: index + (after ? 1 : 0), side: after ? "after" as const : "before" as const };
  };

  const onDragOverCard = (event: DragEvent<HTMLElement>, item: Topic, index: number) => {
    const source = sourceForEvent(event);
    if (!canReorder || !source || source.subject !== item.subject || source.topic_id === item.topic_id) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    const insertion = insertionIndexForCard(event, index);
    setDropTarget({ subject: item.subject, index: insertion.index, targetId: item.topic_id, side: insertion.side });
  };

  const onDragOverEnd = (event: DragEvent<HTMLElement>, subject: Subject, index: number) => {
    const source = sourceForEvent(event);
    if (!canReorder || !source || source.subject !== subject) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    setDropTarget({ subject, index });
  };

  const onDropAt = async (event: DragEvent<HTMLElement>, subject: Subject, rawInsertIndex: number) => {
    event.preventDefault();
    const source = sourceForEvent(event);
    clearDragState();

    if (!canReorder || !source || source.subject !== subject) return;

    const orderedForSubject = groupedItems[subject];
    const listedForSubject = visibleItems[subject];
    const sourceIndex = listedForSubject.findIndex((item) => item.topic_id === source.topic_id);
    if (sourceIndex < 0) return;

    const reorderedVisible = [...listedForSubject];
    const [moved] = reorderedVisible.splice(sourceIndex, 1);
    // The drop slot was calculated while the source card was still in the
    // list. Once it is removed, slots after it shift one place to the left.
    const insertionIndex = Math.max(
      0,
      Math.min(
        sourceIndex < rawInsertIndex ? rawInsertIndex - 1 : rawInsertIndex,
        reorderedVisible.length,
      ),
    );
    if (insertionIndex === sourceIndex) return;
    reorderedVisible.splice(insertionIndex, 0, moved);

    // English can be filtered by level.  Preserve every topic that is not
    // currently visible, while replacing just the visible slots with the
    // newly dragged order.  The API still receives the complete subject
    // order, so the persisted catalogue cannot lose hidden topics.
    const reorderedForSubject = listedForSubject.length === orderedForSubject.length
      ? reorderedVisible
      : (() => {
          const visibleIds = new Set(listedForSubject.map((item) => item.topic_id));
          let nextVisibleIndex = 0;
          return orderedForSubject.map((item) => (
            visibleIds.has(item.topic_id) ? reorderedVisible[nextVisibleIndex++] : item
          ));
        })();

    const previousItems = items;
    let nextSubjectIndex = 0;
    const nextItems = items.map((item) => (
      item.subject === subject ? reorderedForSubject[nextSubjectIndex++] : item
    ));
    setItems(nextItems);
    setReorderingSubject(subject);
    setError("");

    try {
      const response = await apiFetch("/admin/grammar/topics/reorder", {
        method: "POST",
        body: {
          subject,
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

  const topicCard = (item: Topic, index: number) => {
    const isDropTarget = dropTarget?.targetId === item.topic_id;
    const insertionSide = isDropTarget ? dropTarget.side : undefined;
    return (
    <article
      key={item.topic_id}
      onDragOver={(event) => onDragOverCard(event, item, index)}
      onDrop={(event) => {
        const insertion = insertionIndexForCard(event, index);
        void onDropAt(event, item.subject, insertion.index);
      }}
      className={`relative rounded-2xl border border-line bg-white p-5 shadow-sm transition dark:border-white/10 dark:bg-navy-900/50 ${draggedId === item.topic_id ? "opacity-50" : ""}`}
    >
      {isDropTarget ? (
        <span
          className={`pointer-events-none absolute inset-y-3 z-10 w-1 rounded-full bg-cyan-500 shadow-[0_0_0_3px_rgba(34,211,238,0.2)] ${insertionSide === "after" ? "-right-2" : "-left-2"}`}
          aria-hidden="true"
        />
      ) : null}
      <div className="flex items-start justify-between gap-3">
        <div>
          <span className="rounded-full bg-cyan-100 px-2 py-1 text-xs font-black text-cyan-800 dark:bg-cyan-400/15 dark:text-cyan-200">
            {item.subject === "English" ? `${item.subject} · ${item.level}` : item.subject}
          </span>
          <h3 className="mt-3 font-black text-navy-950 dark:text-white">{item.title}</h3>
          <p className="mt-1 text-xs text-ink-500 dark:text-slate-400">{item.questions?.length || 0} ta test savoli</p>
        </div>
        <button
          type="button"
          draggable={canReorder}
          onDragStart={(event) => onDragStart(event, item)}
          onDragEnd={clearDragState}
          title={canReorder ? "Tartiblash uchun ushlab torting" : "Tartiblash saqlanmoqda"}
          className={`select-none rounded-lg px-2 py-1 text-lg font-black tracking-[-2px] text-ink-400 transition hover:bg-cyan-50 hover:text-cyan-600 dark:text-slate-500 dark:hover:bg-cyan-400/10 ${canReorder ? "cursor-grab active:cursor-grabbing" : "cursor-wait opacity-50"}`}
          aria-label={`${item.title} tartibini o‘zgartirish`}
        >
          ⠿
        </button>
      </div>
      <div className="mt-5 flex gap-2">
        <button className="rounded-lg border border-line px-3 py-2 text-xs font-black dark:border-white/10" onClick={() => setEditing(item)}>Tahrirlash</button>
        <button disabled={busy} className="rounded-lg border border-red-200 px-3 py-2 text-xs font-black text-red-600" onClick={() => remove(item)}>O‘chirish</button>
      </div>
    </article>
    );
  };

  return <section className="space-y-5">
    <div className="flex flex-col gap-3 rounded-2xl border border-line bg-white p-5 shadow-sm dark:border-white/10 dark:bg-navy-900/50 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 className="text-xl font-black text-navy-950 dark:text-white">Grammar mavzulari va qoidalari</h2>
        <p className="mt-1 text-sm text-ink-500 dark:text-slate-300">English va Russian uchun yangi qoida yoki mavzu qo‘shing, izoh va test savollarini yangilang.</p>
      </div>
      <button
        className="rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-black text-white"
        onClick={() => setEditing({
          ...empty(),
          subject: selectedSubject,
          level: selectedSubject === "English" ? selectedEnglishLevel : "",
        })}
      >
        + Yangi qoida qo‘shish
      </button>
    </div>
    <div className="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 shadow-sm dark:border-white/10 dark:bg-navy-900/50 sm:flex-row sm:items-end">
      <label className="min-w-52 text-sm font-black text-navy-900 dark:text-white">
        Fan
        <select
          value={selectedSubject}
          onChange={(event) => setSelectedSubject(event.target.value as Subject)}
          className="mt-1.5 w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm font-semibold dark:border-white/10 dark:bg-navy-950 dark:text-white"
        >
          <option value="English">English</option>
          <option value="Russian">Russian</option>
        </select>
      </label>
      {selectedSubject === "English" ? (
        <label className="min-w-40 text-sm font-black text-navy-900 dark:text-white">
          Daraja
          <select
            value={selectedEnglishLevel}
            onChange={(event) => setSelectedEnglishLevel(event.target.value)}
            className="mt-1.5 w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm font-semibold dark:border-white/10 dark:bg-navy-950 dark:text-white"
          >
            {ENGLISH_LEVELS.map((level) => <option key={level} value={level}>{level}</option>)}
          </select>
        </label>
      ) : null}
    </div>
    <p className="rounded-xl border border-dashed border-cyan-200 bg-cyan-50/60 px-4 py-3 text-xs font-semibold text-cyan-900 dark:border-cyan-400/20 dark:bg-cyan-400/10 dark:text-cyan-100">
      <span className="mr-1 text-base" aria-hidden="true">⠿</span>
      Mavzuni ⠿ tugmasidan ushlab torting. Karta chap/o‘ng chetiga olib borish — undan oldin/keyin qo‘yish; pastdagi keng maydon esa mavzuni eng oxiriga qo‘yadi. Tartib har bir fan uchun alohida saqlanadi.
    </p>
    {error && <p className="rounded-xl bg-red-50 p-3 text-sm font-bold text-red-700 dark:bg-red-950/30 dark:text-red-200">{error}</p>}
    {loading ? <p className="p-8 text-center text-sm text-ink-500">Yuklanmoqda…</p> : <div className="space-y-6">
      {([selectedSubject] as Subject[]).map((groupSubject) => (
        <section key={groupSubject}>
          <h3 className="mb-3 text-sm font-black uppercase tracking-wider text-ink-500 dark:text-slate-300">
            {groupSubject}{groupSubject === "English" ? ` · ${selectedEnglishLevel}` : ""}
          </h3>
          {visibleItems[groupSubject].length ? <>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {visibleItems[groupSubject].map((item, index) => topicCard(item, index))}
          </div>
          <div
            onDragOver={(event) => onDragOverEnd(event, groupSubject, visibleItems[groupSubject].length)}
            onDrop={(event) => void onDropAt(event, groupSubject, visibleItems[groupSubject].length)}
            className={`mt-3 flex min-h-12 items-center justify-center rounded-xl border-2 border-dashed px-4 text-center text-xs font-black transition ${dropTarget?.subject === groupSubject && !dropTarget.targetId ? "border-cyan-500 bg-cyan-50 text-cyan-800 dark:bg-cyan-400/10 dark:text-cyan-100" : "border-line text-ink-400 dark:border-white/10 dark:text-slate-500"}`}
          >
            {dropTarget?.subject === groupSubject && !dropTarget.targetId ? "Shu yerga qo‘ying — eng oxiriga qo‘shiladi" : "Mavzuni eng oxiriga qo‘yish uchun shu maydonga torting"}
          </div>
          </> : <p className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-ink-500">
            {groupSubject === "English" ? `${selectedEnglishLevel} darajasi uchun mavzu yo‘q.` : "Hozircha Russian Grammar mavzulari yo‘q."}
          </p>}
        </section>
      ))}
    </div>}
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
      const payload = {
        ...form,
        topic_id: form.topic_id.trim(),
        title: form.title.trim(),
        // Russian grammar is one shared ordered catalogue, not CEFR-based.
        // Omit the technical storage level so the API can normalize it.
        level: form.subject === "English" ? form.level : undefined,
        questions: questions.map((q) => ({ prompt: q.question, options: q.options, correct_index: Math.max(0, q.options.indexOf(q.correct)) })),
      };
      await apiFetch(`/admin/grammar/topics${isExisting ? `/${encodeURIComponent(item.topic_id)}` : ""}`, { method: isExisting ? "PUT" : "POST", body: payload });
      await saved();
    } catch (e) { setError(e instanceof Error ? e.message : "Saqlab bo‘lmadi"); } finally { setBusy(false); }
  };
  return <ModalPortal open><div className="overlay-modal-backdrop" onClick={close}><article className="overlay-modal-card max-h-[92vh] w-[min(900px,calc(100vw-24px))] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}><div className="flex items-center justify-between"><h3 className="text-lg font-black">{isExisting ? "Grammar mavzusini tahrirlash" : "Yangi Grammar qoidasi"}</h3><button onClick={close}>✕</button></div><div className="mt-5 grid gap-3 sm:grid-cols-2"><label className="text-sm font-bold">Mavzu ID<input disabled={isExisting} value={form.topic_id} onChange={(e) => setForm({...form, topic_id:e.target.value})} className="mt-1 w-full rounded-lg border p-2 disabled:opacity-60" placeholder="english-a1-present-simple"/></label><label className="text-sm font-bold">Mavzu nomi<input value={form.title} onChange={(e) => setForm({...form, title:e.target.value})} className="mt-1 w-full rounded-lg border p-2"/></label><label className="text-sm font-bold">Fan<select value={form.subject} onChange={(e) => { const subject = e.target.value as Topic['subject']; setForm({...form, subject, level: subject === "English" ? (form.level || "A1") : ""}); }} className="mt-1 w-full rounded-lg border p-2"><option>English</option><option>Russian</option></select></label>{form.subject === "English" ? <label className="text-sm font-bold">Daraja<select value={form.level} onChange={(e) => setForm({...form, level:e.target.value})} className="mt-1 w-full rounded-lg border p-2">{ENGLISH_LEVELS.map((x)=><option key={x}>{x}</option>)}</select></label> : <p className="self-end rounded-lg bg-cyan-50 px-3 py-2 text-xs font-semibold text-cyan-800 dark:bg-cyan-400/10 dark:text-cyan-100">Russian Grammar darajalarga bo‘linmaydi.</p>}</div><label className="mt-3 block text-sm font-bold">Qoida / izoh<textarea value={form.rule || ""} onChange={(e) => setForm({...form, rule:e.target.value})} className="mt-1 min-h-28 w-full rounded-lg border p-2" placeholder="Student ko‘radigan grammar qoidasini yozing"/></label><p className="mt-2 text-xs text-ink-500 dark:text-slate-400">Test savollari ixtiyoriy: faqat qoida saqlansa student uni o‘qiydi, savol qo‘shilganda test boshlanadi.</p><div className="mt-5"><SharedTestEditor title="Test savollari (ixtiyoriy)" questions={questions} onChange={setQuestions}/></div>{error && <p className="mt-3 text-sm font-bold text-red-600">{error}</p>}<div className="mt-6 flex justify-end gap-2"><button className="rounded-lg border px-4 py-2 font-bold" onClick={close}>Bekor qilish</button><button disabled={busy} className="rounded-lg bg-cyan-600 px-4 py-2 font-black text-white disabled:opacity-60" onClick={submit}>{busy ? "Saqlanmoqda…" : "Saqlash"}</button></div></article></div></ModalPortal>;
}
