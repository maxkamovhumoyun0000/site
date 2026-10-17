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
  const [subject, setSubject] = useState("english");
  const [prompt, setPrompt] = useState("");
  const [kind, setKind] = useState("multiple_choice");
  const [answer, setAnswer] = useState("");
  const [options, setOptions] = useState("");
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
    const r = await apiFetch(`/staff/speaking-learning/modules/${id}/questions`);
    setQuestions(r?.items || []);
  };
  useEffect(() => { void loadTracks().catch(() => setError("Speaking Learning Path yuklanmadi.")); }, []);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await fn(); } catch (e: any) { setError(e?.message || "Saqlashda xatolik yuz berdi."); }
    finally { setBusy(false); }
  };

  return <main className="space-y-5 p-4 md:p-6">
    <header><h1 className="text-2xl font-bold">Speaking Learning Path</h1><p className="mt-1 text-sm opacity-70">Bu yerdagi yo‘lak, modullar, testlar va natijalar Student Learning Path’dan alohida saqlanadi.</p></header>
    {error && <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-3 text-red-700">{error}</div>}
    <section className="grid gap-4 xl:grid-cols-3">
      <div className="rounded-2xl border bg-white p-4 shadow-sm">
        <h2 className="mb-3 font-semibold">Yo‘laklar</h2>
        <form className="mb-4 space-y-2" onSubmit={(e) => { e.preventDefault(); void run(async () => { await apiFetch("/staff/speaking-learning/tracks", { method: "POST", body: { title, subject, is_published: false } }); setTitle(""); await loadTracks(); }); }}>
          <input className="w-full rounded-lg border p-2" placeholder="Yangi yo‘lak nomi" value={title} onChange={(e) => setTitle(e.target.value)} required />
          <select className="w-full rounded-lg border p-2" value={subject} onChange={(e) => setSubject(e.target.value)}><option value="english">English / IELTS</option><option value="russian">Русский</option></select>
          <button className="rounded-lg bg-blue-600 px-3 py-2 text-white disabled:opacity-50" disabled={busy}>Yo‘lak yaratish</button>
        </form>
        <div className="space-y-2">{tracks.map((item) => <div key={item.id} className={`rounded-lg border p-3 ${trackId === item.id ? "border-blue-500 bg-blue-50" : ""}`}><button onClick={() => void loadModules(item.id)} className="w-full text-left"><span className="font-medium">{item.title}</span><small className="block opacity-60">{item.subject} · {item.is_published ? "Ochiq" : "Qoralama"}</small></button><div className="mt-2 flex gap-4 text-sm"><button className="text-blue-700" onClick={() => void run(async () => { await apiFetch(`/staff/speaking-learning/tracks/${item.id}/publish`, { method: "POST", body: { is_published: !item.is_published } }); await loadTracks(); })}>{item.is_published ? "Nashrdan olish" : "Nashr qilish"}</button><button className="text-red-700" onClick={() => { if (confirm(`“${item.title}” yo‘lagi va ichidagi testlar o‘chirilsinmi?`)) void run(async () => { await apiFetch(`/staff/speaking-learning/tracks/${item.id}`, { method: "DELETE" }); if (trackId === item.id) { setTrackId(null); setModules([]); setQuestions([]); } await loadTracks(); }); }}>O‘chirish</button></div></div>)}</div>
      </div>
      <div className="rounded-2xl border bg-white p-4 shadow-sm">
        <h2 className="mb-3 font-semibold">Modullar</h2>
        {trackId && <form className="mb-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); void run(async () => { await apiFetch(`/staff/speaking-learning/tracks/${trackId}/modules`, { method: "POST", body: { title } }); setTitle(""); await loadModules(trackId); }); }}><input className="min-w-0 flex-1 rounded-lg border p-2" placeholder="Modul nomi" value={title} onChange={(e) => setTitle(e.target.value)} required /><button className="rounded-lg bg-blue-600 px-3 text-white">+</button></form>}
        <div className="space-y-2">{modules.map((item) => <div key={item.id} className="flex items-center gap-2 rounded-lg border p-3"><button onClick={() => void loadQuestions(item.id)} className={`flex-1 text-left ${moduleId === item.id ? "font-semibold text-blue-700" : ""}`}>{item.title}</button><button className="text-sm text-red-700" onClick={() => { if (confirm(`“${item.title}” moduli o‘chirilsinmi?`)) void run(async () => { await apiFetch(`/staff/speaking-learning/modules/${item.id}`, { method: "DELETE" }); if (moduleId === item.id) { setModuleId(null); setQuestions([]); } if (trackId) await loadModules(trackId); }); }}>×</button></div>)}</div>
      </div>
      <div className="rounded-2xl border bg-white p-4 shadow-sm">
        <h2 className="mb-3 font-semibold">Modul testlari</h2>
        {moduleId && <form className="mb-4 space-y-2" onSubmit={(e) => { e.preventDefault(); void run(async () => { let parsed: any = options.split("\n").map((x) => x.trim()).filter(Boolean); if (kind === "true_false") parsed = ["True", "False"]; await apiFetch(`/staff/speaking-learning/modules/${moduleId}/questions`, { method: "POST", body: { prompt, question_type: kind, options: parsed, answer: kind === "multiple_choice" ? answer : (kind === "true_false" ? answer === "True" : answer), explanation: "" } }); setPrompt(""); setAnswer(""); await loadQuestions(moduleId); }); }}>
          <select className="w-full rounded-lg border p-2" value={kind} onChange={(e) => setKind(e.target.value)}><option value="multiple_choice">Multiple choice</option><option value="true_false">True / False</option><option value="short_answer">Short answer</option><option value="speaking_prompt">Speaking prompt</option></select>
          <textarea className="w-full rounded-lg border p-2" placeholder="Savol / topshiriq" value={prompt} onChange={(e) => setPrompt(e.target.value)} required />
          {kind === "multiple_choice" && <textarea className="w-full rounded-lg border p-2" placeholder="Variantlar — har qatorda bittadan" value={options} onChange={(e) => setOptions(e.target.value)} />}
          {kind !== "speaking_prompt" && <input className="w-full rounded-lg border p-2" placeholder={kind === "true_false" ? "True yoki False" : "To‘g‘ri javob"} value={answer} onChange={(e) => setAnswer(e.target.value)} required />}
          <button className="rounded-lg bg-blue-600 px-3 py-2 text-white" disabled={busy}>Savol qo‘shish</button>
        </form>}
        <ol className="list-decimal space-y-2 pl-5">{questions.map((q) => <li key={q.id} className="pl-1">{q.prompt}<small className="ml-2 opacity-60">{q.question_type}</small><button className="ml-3 text-sm text-red-700" onClick={() => void run(async () => { await apiFetch(`/staff/speaking-learning/questions/${q.id}`, { method: "DELETE" }); if (moduleId) await loadQuestions(moduleId); })}>O‘chirish</button></li>)}</ol>
      </div>
    </section>
  </main>;
}
