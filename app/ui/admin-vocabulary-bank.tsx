"use client";

import { useEffect, useState } from "react";

type VocabularyRow = { id: number; word: string; subject: string; level: string; translation_uz?: string; translation_ru?: string; definition?: string; example?: string };
type AiProposal = { summary: string; reviewed: number; delete_ids: number[]; updates: Array<Partial<VocabularyRow> & { id: number; reason?: string }> };

const LEVELS = ["ALL", "A1", "A2", "B1", "B2", "C1", "BEGINNER", "ELEMENTARY", "PRE-INTERMEDIATE", "INTERMEDIATE", "UPPER-INTERMEDIATE", "ADVANCED"];
const EMPTY_PROPOSAL: AiProposal = { summary: "", reviewed: 0, delete_ids: [], updates: [] };
const messageOf = (cause: unknown, fallback: string) => cause instanceof Error && cause.message ? cause.message : fallback;

export function AdminVocabularyBank({ apiFetch }: { apiFetch: (path: string, options?: any) => Promise<any> }) {
  const [subject, setSubject] = useState<"English" | "Russian">("English");
  const [level, setLevel] = useState("ALL");
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<VocabularyRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [instruction, setInstruction] = useState("18+ so‘zlarni, tasodifan aralashib qolgan boshqa tildagi satrlarni va takrorlarni ajrating.");
  const [analyzing, setAnalyzing] = useState(false);
  const [applying, setApplying] = useState(false);
  const [proposal, setProposal] = useState<AiProposal>(EMPTY_PROPOSAL);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState<VocabularyRow | null>(null);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const load = async () => {
    setLoading(true); setError("");
    try {
      const params = new URLSearchParams({ subject, level, limit: "100" });
      if (query.trim()) params.set("query", query.trim());
      const result = await apiFetch(`/admin/vocabulary-bank?${params.toString()}`, { method: "GET" });
      setRows(Array.isArray(result?.items) ? result.items : []);
      setTotal(Number(result?.total || 0));
      setEditingId(null); setDraft(null);
    } catch (cause) { setError(messageOf(cause, "Vocabulary bank yuklanmadi")); }
    finally { setLoading(false); }
  };

  useEffect(() => { void load(); }, [subject, level]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = async () => {
    if (!draft || !editingId) return;
    setSavingId(editingId); setError("");
    try {
      const result = await apiFetch(`/admin/vocabulary-bank/${editingId}`, { method: "PATCH", body: {
        word: draft.word, translation_uz: draft.translation_uz || "", translation_ru: draft.translation_ru || "",
        definition: draft.definition || "", example: draft.example || "", level: draft.level,
      } });
      const saved = result?.item as VocabularyRow;
      setRows((current) => current.map((row) => row.id === editingId ? saved : row));
      setEditingId(null); setDraft(null); setNotice("So‘z bankda saqlandi.");
    } catch (cause) { setError(messageOf(cause, "Tahrir saqlanmadi")); }
    finally { setSavingId(null); }
  };

  const remove = async (row: VocabularyRow) => {
    if (!window.confirm(`“${row.word}” so‘zini bankdan o‘chirasizmi?`)) return;
    setDeletingId(row.id); setError("");
    try {
      await apiFetch(`/admin/vocabulary-bank/${row.id}`, { method: "DELETE" });
      setRows((current) => current.filter((item) => item.id !== row.id));
      setTotal((current) => Math.max(0, current - 1)); setNotice("So‘z bankdan o‘chirildi.");
    } catch (cause) { setError(messageOf(cause, "So‘z o‘chirilmadi")); }
    finally { setDeletingId(null); }
  };

  const analyze = async () => {
    setAnalyzing(true); setError(""); setNotice(""); setProposal(EMPTY_PROPOSAL);
    try {
      const result = await apiFetch("/admin/vocabulary-bank/analyze", { method: "POST", body: { subject, level, query: query.trim() || undefined, instruction, limit: 100 } });
      setProposal({ summary: String(result?.summary || "AI review tayyor."), reviewed: Number(result?.reviewed || 0), delete_ids: Array.isArray(result?.delete_ids) ? result.delete_ids.map(Number).filter(Number.isFinite) : [], updates: Array.isArray(result?.updates) ? result.updates : [] });
    } catch (cause) { setError(messageOf(cause, "AI analiz bajarilmadi")); }
    finally { setAnalyzing(false); }
  };

  const applyProposal = async () => {
    if (!proposal.delete_ids.length && !proposal.updates.length) return;
    if (!window.confirm("AI taklif qilgan tahrir va o‘chirishlarni bankga qo‘llaysizmi?")) return;
    setApplying(true); setError("");
    try {
      const result = await apiFetch("/admin/vocabulary-bank/apply", { method: "POST", body: { delete_ids: proposal.delete_ids, updates: proposal.updates } });
      const deleted = Array.isArray(result?.deleted_ids) ? result.deleted_ids.length : 0;
      const updated = Array.isArray(result?.updated_ids) ? result.updated_ids.length : 0;
      setProposal(EMPTY_PROPOSAL); setNotice(`${updated} ta tahrir va ${deleted} ta o‘chirish saqlandi.`); await load();
    } catch (cause) { setError(messageOf(cause, "AI taklifi qo‘llanmadi")); }
    finally { setApplying(false); }
  };

  return <section className="space-y-5">
    <div className="rounded-2xl border border-line bg-white p-5 shadow-sm dark:border-white/10 dark:bg-navy-900/50">
      <span className="text-xs font-black uppercase tracking-[0.16em] text-cyan-700 dark:text-cyan-300">Media workspace</span>
      <h2 className="mt-2 text-xl font-black text-navy-950 dark:text-white">Vocabulary Bank Editor</h2>
      <p className="mt-1 text-sm font-semibold text-ink-500 dark:text-slate-300">English yoki Russian so‘z bankini tahrirlang, so‘zlarni o‘chiring va AI review taklifini tekshirib saqlang.</p>
    </div>

    <div className="grid gap-3 rounded-2xl border border-line bg-white p-4 shadow-sm dark:border-white/10 dark:bg-navy-900/50 md:grid-cols-4">
      <label className="text-sm font-black text-navy-900 dark:text-white">Til<select value={subject} onChange={(event) => setSubject(event.target.value as "English" | "Russian")} className="mt-1.5 w-full rounded-xl border border-line bg-white px-3 py-2 dark:border-white/10 dark:bg-navy-950 dark:text-white"><option value="English">English</option><option value="Russian">Russian</option></select></label>
      <label className="text-sm font-black text-navy-900 dark:text-white">Daraja<select value={level} onChange={(event) => setLevel(event.target.value)} className="mt-1.5 w-full rounded-xl border border-line bg-white px-3 py-2 dark:border-white/10 dark:bg-navy-950 dark:text-white">{LEVELS.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label className="text-sm font-black text-navy-900 dark:text-white md:col-span-2">Qidirish<input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void load(); }} placeholder="So‘z, tarjima, definition yoki misol" className="mt-1.5 w-full rounded-xl border border-line bg-white px-3 py-2 dark:border-white/10 dark:bg-navy-950 dark:text-white" /></label>
      <button type="button" onClick={() => void load()} disabled={loading} className="rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-black text-white disabled:opacity-60 md:col-span-4">{loading ? "Yuklanmoqda…" : "Bankni yangilash"}</button>
    </div>

    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-400/20 dark:bg-amber-400/10">
      <h3 className="font-black text-amber-950 dark:text-amber-100">AI review ko‘rsatmasi</h3><p className="mt-1 text-xs font-semibold text-amber-800 dark:text-amber-200">Masalan: 18+ so‘zlarni o‘chirish, noto‘g‘ri til aralashmalarini ajratish yoki takrorlarni tekshirish.</p>
      <textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} rows={3} className="mt-3 w-full rounded-xl border border-amber-200 bg-white p-3 text-sm font-semibold text-navy-950 dark:border-amber-400/20 dark:bg-navy-950 dark:text-white" />
      <button type="button" onClick={() => void analyze()} disabled={analyzing || !instruction.trim()} className="mt-3 rounded-xl bg-amber-500 px-4 py-2.5 text-sm font-black text-amber-950 disabled:opacity-60">{analyzing ? "AI analiz qilmoqda…" : "AI analizni boshlash"}</button>
      {proposal.reviewed ? <div className="mt-4 rounded-xl border border-amber-300 bg-white/80 p-3 text-sm dark:border-amber-400/30 dark:bg-navy-950/70"><p className="font-bold text-navy-950 dark:text-white">{proposal.summary}</p><p className="mt-1 text-ink-600 dark:text-slate-300">{proposal.reviewed} ta so‘z tekshirildi · {proposal.updates.length} ta tahrir · {proposal.delete_ids.length} ta o‘chirish taklifi</p>{proposal.updates.length ? <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-ink-600 dark:text-slate-300">{proposal.updates.slice(0, 8).map((item) => <li key={item.id}>#{item.id}: {item.reason || "Tahrir taklifi"}</li>)}</ul> : null}<button type="button" onClick={() => void applyProposal()} disabled={applying || (!proposal.updates.length && !proposal.delete_ids.length)} className="mt-3 rounded-lg bg-navy-950 px-3 py-2 text-xs font-black text-white disabled:opacity-60 dark:bg-cyan-400 dark:text-navy-950">{applying ? "Saqlanmoqda…" : "Taklifni bankga qo‘llash"}</button></div> : null}
    </div>

    {error ? <p className="rounded-xl bg-red-50 p-3 text-sm font-bold text-red-700 dark:bg-red-950/30 dark:text-red-200">{error}</p> : null}
    {notice ? <p className="rounded-xl bg-emerald-50 p-3 text-sm font-bold text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-200">{notice}</p> : null}
    <div className="rounded-2xl border border-line bg-white shadow-sm dark:border-white/10 dark:bg-navy-900/50">
      <div className="flex items-center justify-between border-b border-line px-5 py-4 dark:border-white/10"><strong className="text-navy-950 dark:text-white">{total} ta so‘zdan ko‘rsatilgani: {rows.length}</strong><span className="text-xs font-semibold text-ink-500 dark:text-slate-400">O‘zgarishlar darhol bankda saqlanadi</span></div>
      <div className="divide-y divide-line dark:divide-white/10">{rows.map((row) => { const editing = editingId === row.id; const current = editing && draft ? draft : row; const change = (field: keyof VocabularyRow, value: string) => setDraft((valueRow) => valueRow ? { ...valueRow, [field]: value } : valueRow); return <div key={row.id} className="p-4"><div className="flex items-start justify-between gap-3"><div className="min-w-0 flex-1">{editing ? <div className="grid gap-2 md:grid-cols-2"><input value={current.word || ""} onChange={(event) => change("word", event.target.value)} placeholder="So‘z" className="rounded-lg border border-line bg-white px-3 py-2 font-black text-navy-950 dark:border-white/10 dark:bg-navy-950 dark:text-white" /><select value={current.level || "B1"} onChange={(event) => change("level", event.target.value)} className="rounded-lg border border-line bg-white px-3 py-2 dark:border-white/10 dark:bg-navy-950 dark:text-white">{LEVELS.filter((item) => item !== "ALL").map((item) => <option key={item}>{item}</option>)}</select><input value={current.translation_uz || ""} onChange={(event) => change("translation_uz", event.target.value)} placeholder="O‘zbekcha tarjima" className="rounded-lg border border-line bg-white px-3 py-2 dark:border-white/10 dark:bg-navy-950 dark:text-white" /><input value={current.translation_ru || ""} onChange={(event) => change("translation_ru", event.target.value)} placeholder="Русский перевод" className="rounded-lg border border-line bg-white px-3 py-2 dark:border-white/10 dark:bg-navy-950 dark:text-white" /><input value={current.definition || ""} onChange={(event) => change("definition", event.target.value)} placeholder="Definition" className="rounded-lg border border-line bg-white px-3 py-2 dark:border-white/10 dark:bg-navy-950 dark:text-white" /><input value={current.example || ""} onChange={(event) => change("example", event.target.value)} placeholder="Misol gap" className="rounded-lg border border-line bg-white px-3 py-2 dark:border-white/10 dark:bg-navy-950 dark:text-white" /></div> : <><strong className="text-navy-950 dark:text-white">{row.word}</strong><span className="ml-2 text-xs font-bold text-cyan-700 dark:text-cyan-300">{row.level}</span><p className="mt-1 text-sm text-ink-600 dark:text-slate-300">{row.translation_uz || "—"} · {row.translation_ru || "—"}</p>{row.definition ? <p className="mt-1 text-xs text-ink-500 dark:text-slate-400">{row.definition}</p> : null}{row.example ? <p className="mt-1 text-xs italic text-ink-500 dark:text-slate-400">{row.example}</p> : null}</>}</div><div className="flex shrink-0 gap-2">{editing ? <><button type="button" onClick={() => void save()} disabled={savingId === row.id} className="rounded-lg bg-cyan-600 px-3 py-2 text-xs font-black text-white disabled:opacity-60">{savingId === row.id ? "Saqlanmoqda…" : "Saqlash"}</button><button type="button" onClick={() => { setEditingId(null); setDraft(null); }} className="rounded-lg border border-line px-3 py-2 text-xs font-black text-navy-900 dark:border-white/10 dark:text-white">Bekor</button></> : <><button type="button" onClick={() => { setNotice(""); setEditingId(row.id); setDraft({ ...row }); }} className="rounded-lg border border-line px-3 py-2 text-xs font-black text-navy-900 dark:border-white/10 dark:text-white">Tahrirlash</button><button type="button" onClick={() => void remove(row)} disabled={deletingId === row.id} className="rounded-lg border border-red-200 px-3 py-2 text-xs font-black text-red-700 disabled:opacity-60 dark:border-red-400/30 dark:text-red-200">{deletingId === row.id ? "O‘chirilmoqda…" : "Olib tashlash"}</button></>}</div></div></div>; })}{!loading && !rows.length ? <p className="p-8 text-center text-sm font-semibold text-ink-500 dark:text-slate-400">Bu filter uchun so‘z topilmadi.</p> : null}</div>
    </div>
  </section>;
}
