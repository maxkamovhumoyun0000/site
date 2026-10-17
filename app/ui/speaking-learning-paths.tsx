"use client";

import { useEffect, useState } from "react";

type ApiFetch = (path: string, options?: { method?: string; body?: any }) => Promise<any>;
type Item = { id: number; title: string; description?: string; subject?: string; is_published?: boolean };

export function SpeakingLearningPaths({ apiFetch }: { apiFetch: ApiFetch }) {
  const [tracks, setTracks] = useState<Item[]>([]);
  const [modules, setModules] = useState<Item[]>([]);
  const [questions, setQuestions] = useState<any[]>([]);
  const [trackId, setTrackId] = useState<number | null>(null);
  const [moduleId, setModuleId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [moduleTitle, setModuleTitle] = useState("");
  const [subject, setSubject] = useState("english");
  const [prompt, setPrompt] = useState("");
  const [kind, setKind] = useState("multiple_choice");
  const [answer, setAnswer] = useState("");
  const [options, setOptions] = useState("");
  const [explanation, setExplanation] = useState("");
  const [editingQuestionId, setEditingQuestionId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const loadTracks = async () => {
    const r = await apiFetch("/staff/speaking-learning/tracks");
    setTracks(r?.items || []);
  };
  const loadModules = async (id: number) => {
    setTrackId(id); setModuleId(null); setQuestions([]);
    const r = await apiFetch(`/staff/speaking-learning/tracks/${id}/modules`);
    setModules(r?.items || []);
  };
  const loadQuestions = async (id: number) => {
    setModuleId(id);
    setEditingQuestionId(null);
    const r = await apiFetch(`/staff/speaking-learning/modules/${id}/questions`);
    setQuestions(r?.items || []);
  };
  useEffect(() => { void loadTracks().catch(() => setError("Speaking Learning Path yuklanmadi.")); }, []);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await fn(); } catch (e: any) { setError(e?.message || "Saqlashda xatolik yuz berdi."); }
    finally { setBusy(false); }
  };

  const startEditingQuestion = (question: any) => {
    setEditingQuestionId(question.id);
    setPrompt(String(question.prompt || ""));
    setKind(String(question.question_type || "multiple_choice"));
    setOptions(Array.isArray(question.options) ? question.options.join("\n") : "");
    setAnswer(question.question_type === "true_false"
      ? (question.answer === true ? "True" : "False") : String(question.answer ?? ""));
    setExplanation(String(question.explanation || ""));
  };
  const resetQuestionForm = () => {
    setEditingQuestionId(null); setPrompt(""); setAnswer("");
    setOptions(""); setExplanation("");
  };
  const editTrack = (item: Item) => {
    const nextTitle = window.prompt("Yo‘lak nomi", item.title);
    if (nextTitle === null || !nextTitle.trim()) return;
    const nextDescription = window.prompt("Tavsif", item.description || "");
    if (nextDescription === null) return;
    void run(async () => {
      await apiFetch(`/staff/speaking-learning/tracks/${item.id}`, {
        method: "PATCH", body: { title: nextTitle.trim(), description: nextDescription.trim(), subject: item.subject || "english" },
      });
      await loadTracks();
    });
  };
  const editModule = (item: Item) => {
    const nextTitle = window.prompt("Modul nomi", item.title);
    if (nextTitle === null || !nextTitle.trim()) return;
    const nextDescription = window.prompt("Tavsif", item.description || "");
    if (nextDescription === null) return;
    void run(async () => {
      await apiFetch(`/staff/speaking-learning/modules/${item.id}`, {
        method: "PATCH", body: { title: nextTitle.trim(), description: nextDescription.trim() },
      });
      if (trackId) await loadModules(trackId);
    });
  };

  return <main className="mx-auto max-w-7xl space-y-5 p-4 md:p-6">
    <header className="premium-card p-5 sm:p-7"><p className="text-xs font-black uppercase tracking-[.18em] text-cyan-600 dark:text-cyan-300">Diamond Speaking</p><h1 className="mt-1 text-2xl font-black text-navy-900 dark:text-white">Learning Path boshqaruvi</h1><p className="mt-1 text-sm text-ink-600 dark:text-navy-300">Faqat Speaking ilovasi uchun test yo‘laklari. Student Learning Path ma’lumotlari bilan aralashmaydi.</p></header>
    {error && <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-3 text-red-700 dark:bg-red-500/10 dark:text-red-200">{error}</div>}
    <section className="grid gap-4 xl:grid-cols-3">
      <div className="premium-card p-4">
        <h2 className="mb-3 font-semibold">Yo‘laklar</h2>
        <form className="mb-4 space-y-2" onSubmit={(e) => { e.preventDefault(); void run(async () => { await apiFetch("/staff/speaking-learning/tracks", { method: "POST", body: { title, subject, is_published: false } }); setTitle(""); await loadTracks(); }); }}>
          <input className="w-full rounded-lg border bg-white p-2 text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white" placeholder="Yangi yo‘lak nomi" value={title} onChange={(e) => setTitle(e.target.value)} required />
          <select className="w-full rounded-lg border bg-white p-2 text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white" value={subject} onChange={(e) => setSubject(e.target.value)}><option value="english">English / IELTS</option><option value="russian">Русский</option></select>
          <button className="rounded-lg bg-blue-600 px-3 py-2 text-white disabled:opacity-50" disabled={busy}>Yo‘lak yaratish</button>
        </form>
        <div className="space-y-2">{tracks.map((item) => <div key={item.id} className={`rounded-lg border p-3 dark:border-slate-700 ${trackId === item.id ? "border-blue-500 bg-blue-50 dark:bg-blue-500/10" : ""}`}><button onClick={() => void loadModules(item.id)} className="w-full text-left"><span className="font-medium">{item.title}</span><small className="block opacity-60">{item.subject} · {item.is_published ? "Ochiq" : "Qoralama"}</small></button><div className="mt-2 flex flex-wrap gap-4 text-sm"><button disabled={busy} className="text-blue-700 dark:text-cyan-300" onClick={() => void run(async () => { await apiFetch(`/staff/speaking-learning/tracks/${item.id}/publish`, { method: "POST", body: { is_published: !item.is_published } }); await loadTracks(); })}>{item.is_published ? "Nashrdan olish" : "Nashr qilish"}</button><button disabled={busy} className="text-blue-700 dark:text-cyan-300" onClick={() => editTrack(item)}>Tahrirlash</button><button disabled={busy} className="text-red-700 dark:text-red-300" onClick={() => { if (confirm(`“${item.title}” yo‘lagi va ichidagi testlar o‘chirilsinmi?`)) void run(async () => { await apiFetch(`/staff/speaking-learning/tracks/${item.id}`, { method: "DELETE" }); if (trackId === item.id) { setTrackId(null); setModules([]); setQuestions([]); } await loadTracks(); }); }}>O‘chirish</button></div></div>)}</div>
      </div>
      <div className="premium-card p-4">
        <h2 className="mb-3 font-semibold">Modullar</h2>
        {trackId && <form className="mb-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); void run(async () => { await apiFetch(`/staff/speaking-learning/tracks/${trackId}/modules`, { method: "POST", body: { title: moduleTitle } }); setModuleTitle(""); await loadModules(trackId); }); }}><input className="min-w-0 flex-1 rounded-lg border bg-white p-2 text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white" placeholder="Modul nomi" value={moduleTitle} onChange={(e) => setModuleTitle(e.target.value)} required /><button disabled={busy} className="rounded-lg bg-blue-600 px-3 text-white">+</button></form>}
        <div className="space-y-2">{modules.map((item) => <div key={item.id} className="flex items-center gap-2 rounded-lg border p-3 dark:border-slate-700"><button onClick={() => void loadQuestions(item.id)} className={`flex-1 text-left ${moduleId === item.id ? "font-semibold text-blue-700 dark:text-cyan-300" : ""}`}>{item.title}</button><button disabled={busy} className="text-sm text-blue-700 dark:text-cyan-300" onClick={() => editModule(item)}>Tahrirlash</button><button disabled={busy} className="text-sm text-red-700 dark:text-red-300" onClick={() => { if (confirm(`“${item.title}” moduli o‘chirilsinmi?`)) void run(async () => { await apiFetch(`/staff/speaking-learning/modules/${item.id}`, { method: "DELETE" }); if (moduleId === item.id) { setModuleId(null); setQuestions([]); } if (trackId) await loadModules(trackId); }); }}>×</button></div>)}</div>
      </div>
      <div className="premium-card p-4">
        <h2 className="mb-3 font-semibold">Modul testlari</h2>
        {moduleId && <form className="mb-4 space-y-2" onSubmit={(e) => { e.preventDefault(); void run(async () => { let parsed = options.split("\n").map((x) => x.trim()).filter(Boolean); if (kind === "true_false") parsed = ["True", "False"]; if (kind === "multiple_choice" && (parsed.length < 2 || !parsed.includes(answer.trim()))) { throw new Error("Kamida 2 variant kiriting va to‘g‘ri javobni ulardan tanlang."); } const body = { prompt: prompt.trim(), question_type: kind, options: parsed, answer: kind === "true_false" ? answer === "True" : answer.trim(), explanation: explanation.trim() }; if (editingQuestionId) await apiFetch(`/staff/speaking-learning/questions/${editingQuestionId}`, { method: "PATCH", body }); else await apiFetch(`/staff/speaking-learning/modules/${moduleId}/questions`, { method: "POST", body }); resetQuestionForm(); await loadQuestions(moduleId); }); }}>
          <select className="w-full rounded-lg border bg-white p-2 text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white" value={kind} onChange={(e) => { setKind(e.target.value); setAnswer(""); }}><option value="multiple_choice">Variant tanlash</option><option value="true_false">To‘g‘ri / Noto‘g‘ri</option><option value="short_answer">Qisqa javob</option></select>
          <textarea className="w-full rounded-lg border bg-white p-2 text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white" placeholder="Savol / topshiriq" value={prompt} onChange={(e) => setPrompt(e.target.value)} required />
          {kind === "multiple_choice" && <textarea className="w-full rounded-lg border bg-white p-2 text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white" placeholder="Variantlar — har qatorda bittadan" value={options} onChange={(e) => setOptions(e.target.value)} required />}
          {kind === "true_false" ? <select className="w-full rounded-lg border bg-white p-2 text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white" value={answer} onChange={(e) => setAnswer(e.target.value)} required><option value="">To‘g‘ri javobni tanlang</option><option value="True">To‘g‘ri</option><option value="False">Noto‘g‘ri</option></select> : kind === "multiple_choice" ? <select className="w-full rounded-lg border bg-white p-2 text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white" value={answer} onChange={(e) => setAnswer(e.target.value)} required><option value="">To‘g‘ri javobni tanlang</option>{options.split("\n").map((x) => x.trim()).filter(Boolean).map((option, index) => <option key={`${index}-${option}`} value={option}>{option}</option>)}</select> : <input className="w-full rounded-lg border bg-white p-2 text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white" placeholder="To‘g‘ri javob" value={answer} onChange={(e) => setAnswer(e.target.value)} required />}
          <textarea className="w-full rounded-lg border bg-white p-2 text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white" placeholder="Izoh (ixtiyoriy)" value={explanation} onChange={(e) => setExplanation(e.target.value)} />
          <div className="flex gap-2"><button className="rounded-lg bg-blue-600 px-3 py-2 text-white" disabled={busy}>{editingQuestionId ? "Savolni saqlash" : "Savol qo‘shish"}</button>{editingQuestionId && <button type="button" className="rounded-lg border px-3 py-2" onClick={resetQuestionForm}>Bekor qilish</button>}</div>
        </form>}
        <ol className="list-decimal space-y-2 pl-5">{questions.map((q) => <li key={q.id} className="pl-1">{q.prompt}<small className="ml-2 opacity-60">{q.question_type}</small><div className="mt-1 flex gap-3"><button type="button" className="text-sm text-blue-700 dark:text-cyan-300" onClick={() => startEditingQuestion(q)}>Tahrirlash</button><button type="button" disabled={busy} className="text-sm text-red-700 dark:text-red-300" onClick={() => { if (confirm("Savol o‘chirilsinmi?")) void run(async () => { await apiFetch(`/staff/speaking-learning/questions/${q.id}`, { method: "DELETE" }); if (moduleId) await loadQuestions(moduleId); }); }}>O‘chirish</button></div></li>)}</ol>
      </div>
    </section>
  </main>;
}
