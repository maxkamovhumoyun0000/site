"use client";

import { useEffect, useMemo, useState } from "react";

type VocabularyRow = {
  id: number;
  word: string;
  subject: string;
  level: string;
  translation_uz?: string;
  translation_ru?: string;
  definition?: string;
  example?: string;
};

const LEVELS = ["A1", "A2", "B1", "B2", "C1", "BEGINNER", "ELEMENTARY", "PRE-INTERMEDIATE", "INTERMEDIATE", "UPPER-INTERMEDIATE", "ADVANCED"];
const UNSAFE_PATTERN = /\b(?:porn|sex|sexy|nude|naked|xxx|drug|cocaine|heroin|suicide|kill)\b/i;

function rowText(row: VocabularyRow) {
  return [row.word, row.translation_uz, row.translation_ru, row.definition, row.example].filter(Boolean).join(" ");
}

export function AdminVocabularyBank({ apiFetch }: { apiFetch: (path: string, options?: any) => Promise<any> }) {
  const [subject, setSubject] = useState<"English" | "Russian">("English");
  const [level, setLevel] = useState("B1");
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<VocabularyRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [analysisInstruction, setAnalysisInstruction] = useState("18+ so‘zlarni, tasodifan aralashib qolgan boshqa tildagi satrlarni va takrorlarni ajrating.");
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [drafts, setDrafts] = useState<Record<number, VocabularyRow>>({});
  const [removed, setRemoved] = useState<Set<number>>(new Set());
  const [editingId, setEditingId] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ subject, level, limit: "60" });
      if (query.trim()) params.set("query", query.trim());
      const result = await apiFetch(`/vocabulary?${params.toString()}`, { method: "GET" });
      setRows(Array.isArray(result?.items) ? result.items : []);
      setTotal(Number(result?.total || 0));
      setDrafts({});
      setRemoved(new Set());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Vocabulary bank yuklanmadi");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [subject, level]); // eslint-disable-line react-hooks/exhaustive-deps

  const visibleRows = useMemo(() => rows.filter((row) => !removed.has(Number(row.id))), [rows, removed]);
  const analysis = useMemo(() => {
    const seen = new Map<string, VocabularyRow>();
    const unsafe: VocabularyRow[] = [];
    const duplicates: VocabularyRow[] = [];
    const mixed: VocabularyRow[] = [];
    for (const row of visibleRows) {
      const text = rowText(row);
      const normalized = String(row.word || "").trim().toLowerCase();
      if (UNSAFE_PATTERN.test(text)) unsafe.push(row);
      if (normalized && seen.has(normalized)) duplicates.push(row);
      else if (normalized) seen.set(normalized, row);
      if (subject === "English" && /[А-Яа-яЁё]/.test(String(row.word || ""))) mixed.push(row);
      if (subject === "Russian" && /[A-Za-z]/.test(String(row.word || ""))) mixed.push(row);
    }
    return { unsafe, duplicates, mixed };
  }, [subject, visibleRows]);

  const rowValue = (row: VocabularyRow) => drafts[Number(row.id)] || row;
  const updateDraft = (row: VocabularyRow, field: keyof VocabularyRow, value: string) => {
    const id = Number(row.id);
    setDrafts((prev) => ({ ...prev, [id]: { ...rowValue(row), [field]: value } }));
  };

  const discardRow = (id: number) => setRemoved((prev) => new Set([...prev, id]));

  return (
    <section className="space-y-5">
      <div className="rounded-2xl border border-line bg-white p-5 shadow-sm dark:border-white/10 dark:bg-navy-900/50">
        <span className="text-xs font-black uppercase tracking-[0.16em] text-cyan-700 dark:text-cyan-300">Media workspace</span>
        <h2 className="mt-2 text-xl font-black text-navy-950 dark:text-white">Vocabulary Bank Editor</h2>
        <p className="mt-1 text-sm font-semibold text-ink-500 dark:text-slate-300">English yoki Russian vocabulary bankini qidirib ko‘ring, tahrir qoralamasini tayyorlang va AI review uchun ko‘rsatma yozing.</p>
      </div>

      <div className="grid gap-3 rounded-2xl border border-line bg-white p-4 shadow-sm dark:border-white/10 dark:bg-navy-900/50 md:grid-cols-4">
        <label className="text-sm font-black text-navy-900 dark:text-white">Til<select value={subject} onChange={(event) => setSubject(event.target.value as "English" | "Russian")} className="mt-1.5 w-full rounded-xl border border-line bg-white px-3 py-2 dark:border-white/10 dark:bg-navy-950 dark:text-white"><option value="English">English</option><option value="Russian">Russian</option></select></label>
        <label className="text-sm font-black text-navy-900 dark:text-white">Daraja<select value={level} onChange={(event) => setLevel(event.target.value)} className="mt-1.5 w-full rounded-xl border border-line bg-white px-3 py-2 dark:border-white/10 dark:bg-navy-950 dark:text-white">{LEVELS.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label className="text-sm font-black text-navy-900 dark:text-white md:col-span-2">Qidirish<input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void load(); }} placeholder="So‘z, tarjima yoki misol" className="mt-1.5 w-full rounded-xl border border-line bg-white px-3 py-2 dark:border-white/10 dark:bg-navy-950 dark:text-white" /></label>
        <button type="button" onClick={() => void load()} className="rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-black text-white md:col-span-4">{loading ? "Yuklanmoqda…" : "Bankni yangilash"}</button>
      </div>

      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-400/20 dark:bg-amber-400/10">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-black text-amber-950 dark:text-amber-100">AI review ko‘rsatmasi</h3><p className="text-xs font-semibold text-amber-800 dark:text-amber-200">Qaysi so‘zlarni ajratish yoki olib tashlash kerakligini yozing.</p></div><button type="button" onClick={() => setAnalysisOpen((value) => !value)} className="rounded-lg border border-amber-300 px-3 py-2 text-xs font-black text-amber-900 dark:border-amber-300/40 dark:text-amber-100">{analysisOpen ? "Yashirish" : "Analizni ko‘rish"}</button></div>
        <textarea value={analysisInstruction} onChange={(event) => setAnalysisInstruction(event.target.value)} rows={3} className="mt-3 w-full rounded-xl border border-amber-200 bg-white p-3 text-sm font-semibold text-navy-950 dark:border-amber-400/20 dark:bg-navy-950 dark:text-white" />
        {analysisOpen ? <div className="mt-3 grid gap-2 text-sm font-semibold text-amber-950 dark:text-amber-100 sm:grid-cols-3"><div>18+ / xavfli: <strong>{analysis.unsafe.length}</strong></div><div>Takror so‘zlar: <strong>{analysis.duplicates.length}</strong></div><div>Til aralashganlari: <strong>{analysis.mixed.length}</strong></div></div> : null}
      </div>

      {error ? <p className="rounded-xl bg-red-50 p-3 text-sm font-bold text-red-700 dark:bg-red-950/30 dark:text-red-200">{error}</p> : null}
      <div className="rounded-2xl border border-line bg-white shadow-sm dark:border-white/10 dark:bg-navy-900/50">
        <div className="flex items-center justify-between border-b border-line px-5 py-4 dark:border-white/10"><strong className="text-navy-950 dark:text-white">{total} ta so‘zdan ko‘rsatilgani: {visibleRows.length}</strong><span className="text-xs font-semibold text-ink-500 dark:text-slate-400">Tahrirlar qoralama rejimida</span></div>
        <div className="divide-y divide-line dark:divide-white/10">{visibleRows.map((row) => { const current = rowValue(row); const editing = editingId === Number(row.id); return <div key={row.id} className="p-4"><div className="flex items-start justify-between gap-3"><div className="min-w-0 flex-1">{editing ? <div className="grid gap-2 md:grid-cols-2"><input value={current.word || ""} onChange={(event) => updateDraft(row, "word", event.target.value)} className="rounded-lg border border-line bg-white px-3 py-2 font-black text-navy-950 dark:border-white/10 dark:bg-navy-950 dark:text-white" /><input value={current.translation_uz || ""} onChange={(event) => updateDraft(row, "translation_uz", event.target.value)} placeholder="O‘zbekcha tarjima" className="rounded-lg border border-line bg-white px-3 py-2 dark:border-white/10 dark:bg-navy-950 dark:text-white" /><input value={current.translation_ru || ""} onChange={(event) => updateDraft(row, "translation_ru", event.target.value)} placeholder="Русский перевод" className="rounded-lg border border-line bg-white px-3 py-2 dark:border-white/10 dark:bg-navy-950 dark:text-white" /><input value={current.example || ""} onChange={(event) => updateDraft(row, "example", event.target.value)} placeholder="Misol gap" className="rounded-lg border border-line bg-white px-3 py-2 dark:border-white/10 dark:bg-navy-950 dark:text-white" /></div> : <><strong className="text-navy-950 dark:text-white">{current.word}</strong><span className="ml-2 text-xs font-bold text-cyan-700 dark:text-cyan-300">{current.level}</span><p className="mt-1 text-sm text-ink-600 dark:text-slate-300">{current.translation_uz || "—"} · {current.translation_ru || "—"}</p>{current.example ? <p className="mt-1 text-xs text-ink-500 dark:text-slate-400">{current.example}</p> : null}</>}</div><div className="flex shrink-0 gap-2"><button type="button" onClick={() => setEditingId(editing ? null : Number(row.id))} className="rounded-lg border border-line px-3 py-2 text-xs font-black text-navy-900 dark:border-white/10 dark:text-white">{editing ? "Tayyor" : "Tahrirlash"}</button><button type="button" onClick={() => discardRow(Number(row.id))} className="rounded-lg border border-red-200 px-3 py-2 text-xs font-black text-red-700 dark:border-red-400/30 dark:text-red-200">Olib tashlash</button></div></div></div>; })}{!loading && !visibleRows.length ? <p className="p-8 text-center text-sm font-semibold text-ink-500 dark:text-slate-400">Bu filter uchun so‘z topilmadi.</p> : null}</div>
      </div>
    </section>
  );
}
