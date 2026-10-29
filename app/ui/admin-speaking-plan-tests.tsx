"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";

type Subject = "english" | "russian";
type Status = "draft" | "published";

type PlanQuestion = {
  kind: string;
  question?: string;
  instruction?: string;
  options?: string[];
  correct_answer?: string;
  accepted_answers?: string[];
  pairs?: { left: string; right: string }[];
  reference_answer?: string;
  word?: string;
  explanation?: string;
  [key: string]: unknown;
};

type PlanTest = {
  id: number;
  subject: Subject;
  focus: string;
  band: string;
  title: string;
  status: Status;
  source: "ai" | "auto" | "manual";
  explanation_language: string;
  question_count: number;
  kinds: string[];
  uses: number;
  attempts: number;
  average_score: number | null;
  created_at: string | null;
  updated_at: string | null;
  questions?: PlanQuestion[];
};

type Meta = {
  focuses: string[];
  bands: Record<Subject, string[]>;
  focus_kinds: Record<string, string[]>;
  daily_question_limit: number;
  questions_per_test: number;
};

type Stats = { active_plans: number; learners_today: number; tests_today: number; questions_today: number };

interface AdminSpeakingPlanTestsProps {
  apiFetch: (path: string, options?: { method?: string; body?: any; timeoutMs?: number; signal?: AbortSignal }) => Promise<any>;
}

const DEFAULT_META: Meta = {
  focuses: [
    "part1_fluency", "part2_structure", "part3_discussion", "grammar_accuracy", "grammar_range", "pronunciation",
    "vocabulary_work_study", "vocabulary_hometown", "vocabulary_technology", "vocabulary_environment", "vocabulary_health", "vocabulary_travel",
  ],
  bands: { english: ["5.5", "6.0", "6.5", "7.0"], russian: ["6", "7", "8", "9"] },
  focus_kinds: {},
  daily_question_limit: 50,
  questions_per_test: 10,
};

const FOCUS_LABELS: Record<string, string> = {
  part1_fluency: "Part 1 — ravonlik",
  part2_structure: "Part 2 — javob tuzilishi",
  part3_discussion: "Part 3 — muhokama",
  grammar_accuracy: "Grammatika — aniqlik",
  grammar_range: "Grammatika — murakkab gaplar",
  pronunciation: "Talaffuz",
  vocabulary_work_study: "Lug'at — Ish va o'qish",
  vocabulary_hometown: "Lug'at — Shahar va joylar",
  vocabulary_technology: "Lug'at — Texnologiya",
  vocabulary_environment: "Lug'at — Tabiat va ekologiya",
  vocabulary_health: "Lug'at — Sog'liq",
  vocabulary_travel: "Lug'at — Sayohat va madaniyat",
};

const KIND_LABELS: Record<string, string> = {
  multiple_choice: "Variantli savol",
  true_false: "To'g'ri / noto'g'ri",
  gap_fill: "Bo'sh joyni to'ldirish",
  word_order: "So'zlardan gap tuzish",
  matching: "Juftlarni topish",
  write_sentence: "Gap yozish (AI)",
  paraphrase: "Qayta ifodalash (AI)",
  guided_writing: "Yo'naltirilgan javob (AI)",
  speak_sentence: "Ovozli javob (AI)",
  read_aloud: "Ovoz chiqarib o'qish (AI)",
};

const AI_KINDS = new Set(["write_sentence", "paraphrase", "guided_writing", "speak_sentence", "read_aloud"]);

function bandLabel(subject: string, band: string) {
  if (subject === "english") return band === "7.0" ? "IELTS 7.0+" : `IELTS ${band}`;
  return `${band}/10`;
}

function subjectLabel(subject: string) {
  return subject === "russian" ? "Rus tili" : "Ingliz tili";
}

function errorText(error: unknown, fallback: string) {
  const message = error instanceof Error ? error.message : String(error || "");
  return message.trim() || fallback;
}

function lines(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function ListSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-hidden="true">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton-card flex items-center gap-4 p-4">
          <div className="flex-1 space-y-2">
            <div className="skeleton-line title" />
            <div className="skeleton-line short" />
          </div>
          <div className="skeleton-line short w-24" />
        </div>
      ))}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
      <div className="text-xs font-semibold text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-bold text-slate-900 dark:text-white">{value}</div>
    </div>
  );
}

const inputClass = "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm font-normal dark:border-slate-700 dark:bg-slate-800";

function QuestionEditor({
  question,
  index,
  subject,
  onChange,
  onRemove,
}: {
  question: PlanQuestion;
  index: number;
  subject: Subject;
  onChange: (next: PlanQuestion) => void;
  onRemove: () => void;
}) {
  const kind = question.kind;
  const set = (patch: Partial<PlanQuestion>) => onChange({ ...question, ...patch });
  const trueFalse = subject === "english" ? ["True", "False"] : ["Верно", "Неверно"];
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/60">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-sm font-bold text-slate-800 dark:text-slate-100">
          {index + 1}. {KIND_LABELS[kind] || kind}
        </div>
        <button type="button" onClick={onRemove} className="rounded-lg border border-red-200 px-2 py-1 text-xs font-semibold text-red-600">
          Savolni o&apos;chirish
        </button>
      </div>
      <div className="space-y-3">
        <label className="block text-xs font-semibold text-slate-600">
          Savol matni{kind === "gap_fill" ? " (bitta ___ bo'lsin)" : ""}
          <textarea value={question.question || ""} onChange={(e) => set({ question: e.target.value })} rows={2} className={inputClass} />
        </label>
        {kind === "multiple_choice" || kind === "gap_fill" ? (
          <label className="block text-xs font-semibold text-slate-600">
            Variantlar (har biri alohida qatorda{kind === "gap_fill" ? ", ixtiyoriy" : ""})
            <textarea
              value={(question.options || []).join("\n")}
              onChange={(e) => set({ options: lines(e.target.value) })}
              rows={4}
              className={inputClass}
            />
          </label>
        ) : null}
        {kind === "true_false" ? (
          <label className="block text-xs font-semibold text-slate-600">
            To&apos;g&apos;ri javob
            <select value={question.correct_answer || trueFalse[0]} onChange={(e) => set({ correct_answer: e.target.value })} className={inputClass}>
              {trueFalse.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {kind === "multiple_choice" || kind === "gap_fill" || kind === "word_order" ? (
          <label className="block text-xs font-semibold text-slate-600">
            {kind === "word_order" ? "To'g'ri gap (so'zlar avtomatik aralashtiriladi)" : "To'g'ri javob"}
            <input value={question.correct_answer || ""} onChange={(e) => set({ correct_answer: e.target.value })} className={inputClass} />
          </label>
        ) : null}
        {kind === "gap_fill" && !(question.options || []).length ? (
          <label className="block text-xs font-semibold text-slate-600">
            Qabul qilinadigan boshqa javoblar (vergul bilan)
            <input
              value={(question.accepted_answers || []).filter((item) => item !== question.correct_answer).join(", ")}
              onChange={(e) =>
                set({
                  accepted_answers: e.target.value
                    .split(",")
                    .map((item) => item.trim())
                    .filter(Boolean),
                })
              }
              className={inputClass}
            />
          </label>
        ) : null}
        {kind === "matching" ? (
          <label className="block text-xs font-semibold text-slate-600">
            Juftlar (har qatorda: chap = o&apos;ng)
            <textarea
              value={(question.pairs || []).map((pair) => `${pair.left} = ${pair.right}`).join("\n")}
              onChange={(e) =>
                set({
                  pairs: lines(e.target.value)
                    .map((line) => {
                      const [left, ...rest] = line.split("=");
                      return { left: (left || "").trim(), right: rest.join("=").trim() };
                    })
                    .filter((pair) => pair.left || pair.right),
                })
              }
              rows={4}
              className={inputClass}
            />
          </label>
        ) : null}
        {AI_KINDS.has(kind) ? (
          <>
            {kind === "write_sentence" ? (
              <label className="block text-xs font-semibold text-slate-600">
                Kalit so&apos;z (ixtiyoriy)
                <input value={question.word || ""} onChange={(e) => set({ word: e.target.value })} className={inputClass} />
              </label>
            ) : null}
            <label className="block text-xs font-semibold text-slate-600">
              {kind === "read_aloud" ? "O'qiladigan gap" : "Namuna javob (AI shu bilan solishtiradi)"}
              <textarea value={question.reference_answer || ""} onChange={(e) => set({ reference_answer: e.target.value })} rows={2} className={inputClass} />
            </label>
          </>
        ) : null}
        <label className="block text-xs font-semibold text-slate-600">
          Izoh (javobdan keyin ko&apos;rsatiladi)
          <textarea value={question.explanation || ""} onChange={(e) => set({ explanation: e.target.value })} rows={2} className={inputClass} />
        </label>
      </div>
    </div>
  );
}

export function AdminSpeakingPlanTests({ apiFetch }: AdminSpeakingPlanTestsProps) {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<PlanTest[]>([]);
  const [meta, setMeta] = useState<Meta>(DEFAULT_META);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [subjectFilter, setSubjectFilter] = useState<"" | Subject>("");
  const [focusFilter, setFocusFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<"" | Status>("");

  const [genSubject, setGenSubject] = useState<Subject>("english");
  const [genFocus, setGenFocus] = useState("part1_fluency");
  const [genBand, setGenBand] = useState("6.0");
  const [genTests, setGenTests] = useState(1);
  const [genQuestions, setGenQuestions] = useState(10);
  const [genLanguage, setGenLanguage] = useState("uz");
  const [genPublish, setGenPublish] = useState(false);
  const [genNotes, setGenNotes] = useState("");
  const [generating, setGenerating] = useState(false);

  const [editing, setEditing] = useState<PlanTest | null>(null);
  const [editLoading, setEditLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams();
      if (subjectFilter) query.set("subject", subjectFilter);
      if (focusFilter) query.set("focus", focusFilter);
      if (statusFilter) query.set("status", statusFilter);
      const suffix = query.toString() ? `?${query.toString()}` : "";
      const res = await apiFetch(`/staff/speaking/plan-tests${suffix}`, { method: "GET" });
      setItems(Array.isArray(res?.items) ? res.items : []);
      if (res?.meta) setMeta({ ...DEFAULT_META, ...res.meta });
      if (res?.stats) setStats(res.stats);
    } catch (e) {
      setError(errorText(e, "Testlarni yuklab bo'lmadi."));
    } finally {
      setLoading(false);
    }
  }, [apiFetch, subjectFilter, focusFilter, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const genBands = meta.bands[genSubject] || DEFAULT_META.bands[genSubject];

  function changeGenSubject(subject: Subject) {
    const bands = meta.bands[subject] || DEFAULT_META.bands[subject];
    setGenSubject(subject);
    if (!bands.includes(genBand)) setGenBand(bands[1] || bands[0]);
    setGenLanguage(subject === "russian" ? "ru" : "uz");
  }

  async function generate() {
    setGenerating(true);
    setError("");
    setNotice("");
    try {
      const res = await apiFetch("/staff/speaking/plan-tests/generate", {
        method: "POST",
        timeoutMs: 360000,
        body: {
          subject: genSubject,
          focus: genFocus,
          band: genBand,
          tests: genTests,
          questions: genQuestions,
          explanation_language: genLanguage,
          publish: genPublish,
          notes: genNotes.trim(),
        },
      });
      const created: PlanTest[] = Array.isArray(res?.items) ? res.items : [];
      const failed = Array.isArray(res?.errors) ? res.errors.length : 0;
      setNotice(`${created.length} ta test yaratildi${failed ? `, ${failed} tasi xato bilan tugadi` : ""}.`);
      await load();
      if (created.length === 1) setEditing(created[0]);
    } catch (e) {
      setError(errorText(e, "AI test yarata olmadi. Qayta urinib ko'ring."));
    } finally {
      setGenerating(false);
    }
  }

  async function openEditor(test: PlanTest) {
    setEditLoading(true);
    setError("");
    try {
      const res = await apiFetch(`/staff/speaking/plan-tests/${test.id}`, { method: "GET" });
      setEditing(res?.item || null);
    } catch (e) {
      setError(errorText(e, "Testni ochib bo'lmadi."));
    } finally {
      setEditLoading(false);
    }
  }

  async function saveEditor() {
    if (!editing) return;
    setSaving(true);
    setError("");
    try {
      const res = await apiFetch(`/staff/speaking/plan-tests/${editing.id}`, {
        method: "PUT",
        body: { title: editing.title, status: editing.status, band: editing.band, questions: editing.questions || [] },
      });
      const saved: PlanTest | null = res?.item || null;
      if (saved) setItems((prev) => prev.map((item) => (item.id === saved.id ? { ...item, ...saved } : item)));
      setNotice("Test saqlandi.");
      setEditing(null);
    } catch (e) {
      setError(errorText(e, "Testni saqlab bo'lmadi."));
    } finally {
      setSaving(false);
    }
  }

  async function toggleStatus(test: PlanTest) {
    const status: Status = test.status === "published" ? "draft" : "published";
    try {
      await apiFetch(`/staff/speaking/plan-tests/${test.id}`, { method: "PUT", body: { status } });
      setItems((prev) => prev.map((item) => (item.id === test.id ? { ...item, status } : item)));
    } catch (e) {
      setError(errorText(e, "Holatni o'zgartirib bo'lmadi."));
    }
  }

  async function removeTest(test: PlanTest) {
    if (!confirm(`"${test.title}" testini o'chirmoqchimisiz?`)) return;
    try {
      await apiFetch(`/staff/speaking/plan-tests/${test.id}`, { method: "DELETE" });
      setItems((prev) => prev.filter((item) => item.id !== test.id));
      setNotice("Test o'chirildi.");
    } catch (e) {
      setError(errorText(e, "Testni o'chirib bo'lmadi."));
    }
  }

  const counts = useMemo(
    () => ({
      published: items.filter((item) => item.status === "published").length,
      draft: items.filter((item) => item.status === "draft").length,
    }),
    [items],
  );

  const editingBands = editing ? meta.bands[editing.subject] || DEFAULT_META.bands[editing.subject] : [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">Speaking Plan testlari</h2>
        <p className="text-sm text-slate-500">
          7 / 14 / 30 kunlik Speaking Plan uchun AI yaratadigan testlar. O&apos;quvchi kuniga ko&apos;pi bilan {meta.daily_question_limit} ta savol ishlaydi;
          bankda mos test bo&apos;lmasa, tizim uni avtomatik yaratadi.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatCard label="Faol planlar" value={stats ? stats.active_plans : "—"} />
        <StatCard label="Bugun ishlaganlar" value={stats ? stats.learners_today : "—"} />
        <StatCard label="Bugungi testlar" value={stats ? stats.tests_today : "—"} />
        <StatCard label="Bugungi savollar" value={stats ? stats.questions_today : "—"} />
        <StatCard label="Chop etilgan / qoralama" value={`${counts.published} / ${counts.draft}`} />
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
        <div className="mb-4 text-base font-bold text-slate-900 dark:text-white">AI bilan test yaratish</div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <label className="block text-sm font-semibold">
            Fan
            <select value={genSubject} onChange={(e) => changeGenSubject(e.target.value as Subject)} className={inputClass}>
              <option value="english">Ingliz tili (IELTS)</option>
              <option value="russian">Rus tili</option>
            </select>
          </label>
          <label className="block text-sm font-semibold">
            Yo&apos;nalish
            <select value={genFocus} onChange={(e) => setGenFocus(e.target.value)} className={inputClass}>
              {meta.focuses.map((focus) => (
                <option key={focus} value={focus}>
                  {FOCUS_LABELS[focus] || focus}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-semibold">
            Daraja (maqsad)
            <select value={genBand} onChange={(e) => setGenBand(e.target.value)} className={inputClass}>
              {genBands.map((band) => (
                <option key={band} value={band}>
                  {bandLabel(genSubject, band)}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-semibold">
            Testlar soni
            <select value={genTests} onChange={(e) => setGenTests(Number(e.target.value))} className={inputClass}>
              {[1, 2, 3].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-semibold">
            Har testdagi savollar
            <input
              type="number"
              min={5}
              max={15}
              value={genQuestions}
              onChange={(e) => setGenQuestions(Math.max(5, Math.min(15, Number(e.target.value) || 10)))}
              className={inputClass}
            />
          </label>
          <label className="block text-sm font-semibold">
            Izohlar tili
            <select value={genLanguage} onChange={(e) => setGenLanguage(e.target.value)} className={inputClass}>
              <option value="uz">O&apos;zbekcha</option>
              <option value="ru">Ruscha</option>
              <option value="en">Inglizcha</option>
            </select>
          </label>
        </div>
        <label className="mt-3 block text-sm font-semibold">
          Qo&apos;shimcha ko&apos;rsatma (ixtiyoriy)
          <input
            value={genNotes}
            onChange={(e) => setGenNotes(e.target.value)}
            maxLength={500}
            placeholder="Masalan: Present Perfect va Past Simple farqiga ko'proq savol"
            className={inputClass}
          />
        </label>
        <div className="mt-2 text-xs text-slate-500">
          Savol turlari: {(meta.focus_kinds[genFocus] || []).map((kind) => KIND_LABELS[kind] || kind).join(", ") || "yo'nalishga qarab tanlanadi"}
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-sm font-semibold">
            <input type="checkbox" checked={genPublish} onChange={(e) => setGenPublish(e.target.checked)} />
            Darhol chop etish (aks holda qoralama bo&apos;lib saqlanadi)
          </label>
          <button
            type="button"
            onClick={generate}
            disabled={generating}
            className="rounded-xl bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {generating ? "AI test tayyorlamoqda..." : "AI bilan yaratish"}
          </button>
        </div>
        {generating ? (
          <div className="mt-3 text-xs text-slate-500">Bitta test odatda 20–60 soniyada tayyor bo&apos;ladi. Sahifani yopmang.</div>
        ) : null}
      </div>

      {error ? (
        <div className="flex items-start justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <span>{error}</span>
          <button type="button" onClick={() => setError("")} className="font-semibold">
            ×
          </button>
        </div>
      ) : null}
      {notice ? (
        <div className="flex items-start justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          <span>{notice}</span>
          <button type="button" onClick={() => setNotice("")} className="font-semibold">
            ×
          </button>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-3">
        <select
          value={subjectFilter}
          onChange={(e) => setSubjectFilter(e.target.value as "" | Subject)}
          className="rounded-xl border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
        >
          <option value="">Barcha fanlar</option>
          <option value="english">Ingliz tili</option>
          <option value="russian">Rus tili</option>
        </select>
        <select
          value={focusFilter}
          onChange={(e) => setFocusFilter(e.target.value)}
          className="rounded-xl border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
        >
          <option value="">Barcha yo&apos;nalishlar</option>
          {meta.focuses.map((focus) => (
            <option key={focus} value={focus}>
              {FOCUS_LABELS[focus] || focus}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as "" | Status)}
          className="rounded-xl border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
        >
          <option value="">Barcha holatlar</option>
          <option value="published">Chop etilgan</option>
          <option value="draft">Qoralama</option>
        </select>
        <button type="button" onClick={() => load()} className="rounded-xl border px-4 py-2 text-sm font-semibold">
          Yangilash
        </button>
      </div>

      {loading ? (
        <ListSkeleton />
      ) : items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">
          Hali test yo&apos;q. Yuqoridagi &quot;AI bilan yaratish&quot; tugmasini bosing.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((test) => (
            <div key={test.id} className="flex flex-wrap items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
              <div className="min-w-0 flex-1">
                <div className="truncate font-semibold text-slate-900 dark:text-white">{test.title || `Test #${test.id}`}</div>
                <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
                  <span className="rounded-full bg-blue-50 px-2 py-0.5 text-blue-700">{subjectLabel(test.subject)}</span>
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 dark:bg-slate-800">{FOCUS_LABELS[test.focus] || test.focus}</span>
                  <span className="rounded-full bg-amber-50 px-2 py-0.5 text-amber-700">{bandLabel(test.subject, test.band)}</span>
                  <span>{test.question_count} ta savol</span>
                  <span>{test.source === "auto" ? "Avtomatik yaratilgan" : "AI (admin)"}</span>
                  <span>
                    {test.attempts} marta ishlangan{test.average_score !== null ? ` · o'rtacha ${test.average_score}%` : ""}
                  </span>
                </div>
              </div>
              <label className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                <input type="checkbox" checked={test.status === "published"} onChange={() => toggleStatus(test)} />
                {test.status === "published" ? "Chop etilgan" : "Qoralama"}
              </label>
              <div className="flex gap-1">
                <button
                  type="button"
                  onClick={() => openEditor(test)}
                  disabled={editLoading}
                  className="rounded-lg border px-3 py-1 text-xs font-semibold disabled:opacity-50"
                >
                  Ko&apos;rish / tahrirlash
                </button>
                <button type="button" onClick={() => removeTest(test)} className="rounded-lg border border-red-200 px-3 py-1 text-xs font-semibold text-red-600">
                  O&apos;chirish
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {editing ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true">
          <div className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-6 shadow-xl dark:bg-slate-900">
            <h3 className="mb-1 text-lg font-bold">Testni tahrirlash</h3>
            <div className="mb-4 text-xs text-slate-500">
              {subjectLabel(editing.subject)} · {FOCUS_LABELS[editing.focus] || editing.focus}
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <label className="block text-sm font-semibold md:col-span-2">
                Nomi
                <input value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })} className={inputClass} />
              </label>
              <label className="block text-sm font-semibold">
                Daraja
                <select value={editing.band} onChange={(e) => setEditing({ ...editing, band: e.target.value })} className={inputClass}>
                  {editingBands.map((band) => (
                    <option key={band} value={band}>
                      {bandLabel(editing.subject, band)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="mt-3 flex items-center gap-2 text-sm font-semibold">
              <input
                type="checkbox"
                checked={editing.status === "published"}
                onChange={(e) => setEditing({ ...editing, status: e.target.checked ? "published" : "draft" })}
              />
              Speaking ilovasida ishlatish (chop etilgan)
            </label>
            <div className="mt-5 space-y-3">
              {(editing.questions || []).map((question, index) => (
                <QuestionEditor
                  key={index}
                  question={question}
                  index={index}
                  subject={editing.subject}
                  onChange={(next) =>
                    setEditing({ ...editing, questions: (editing.questions || []).map((item, i) => (i === index ? next : item)) })
                  }
                  onRemove={() => setEditing({ ...editing, questions: (editing.questions || []).filter((_, i) => i !== index) })}
                />
              ))}
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button type="button" onClick={() => setEditing(null)} className="rounded-xl border px-4 py-2 text-sm font-semibold">
                Bekor qilish
              </button>
              <button
                type="button"
                onClick={saveEditor}
                disabled={saving}
                className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {saving ? "Saqlanmoqda..." : "Saqlash"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
