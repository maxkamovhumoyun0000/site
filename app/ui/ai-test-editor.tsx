"use client";

/**
 * AI test savollari muharriri — kutubxona testlari, skrinshotdan import qilingan
 * mashqlar va homeworkka biriktiriladigan testlar shu komponentdan foydalanadi.
 * Sayt va ikkala mobil ilova bir xil `kind` registridan foydalanadi.
 */

import React, { useMemo, useState } from "react";

export type AiTestKind =
  | "speak_sentence"
  | "write_sentence"
  | "guided_writing"
  | "translation"
  | "reading_open"
  | "read_aloud"
  | "paraphrase"
  | "dialogue_completion"
  | "picture_description"
  | "listening"
  | "dictation"
  | "spelling"
  | "matching"
  | "scrambled_sentence"
  | "gap_fill"
  | "word_practice";

export type AiTestQuestion = {
  kind: AiTestKind;
  prompt?: string | null;
  instruction?: string | null;
  word?: string | null;
  translation?: string | null;
  meaning?: string | null;
  passage?: string | null;
  image_url?: string | null;
  audio_url?: string | null;
  level?: string | null;
  answer?: string | null;
  accepted_answers?: string[];
  reference_answer?: string | null;
  options?: string[];
  correct_index?: number;
  pairs?: { left: string; right: string }[];
  tokens?: string[];
  needs_audio_upload?: boolean;
};

type KindMeta = {
  label: string;
  hint: string;
  check: "ai" | "auto";
  input: "text" | "audio" | "audio_or_text" | "choice" | "order" | "pairs";
  needsAudio: boolean;
  icon: string;
};

export const AI_TEST_KIND_META: Record<AiTestKind, KindMeta> = {
  speak_sentence: {
    label: "Gap tuzib gapirish",
    hint: "Studentga so'z beriladi, u mikrofonga gap aytadi. AI talaffuz + grammatikani tekshiradi.",
    check: "ai", input: "audio", needsAudio: false, icon: "🎙️",
  },
  write_sentence: {
    label: "Gap tuzib yozish",
    hint: "Studentga so'z beriladi, u gap yozadi. AI grammatikani tekshiradi.",
    check: "ai", input: "text", needsAudio: false, icon: "✍️",
  },
  guided_writing: {
    label: "Mavzu bo'yicha yozma mashq",
    hint: "Mavzu beriladi, student matn yozadi. AI grammatika va mazmunni tekshiradi.",
    check: "ai", input: "text", needsAudio: false, icon: "📝",
  },
  translation: {
    label: "Tarjima",
    hint: "Gapni tarjima qilish. AI ma'no va grammatikani tekshiradi.",
    check: "ai", input: "text", needsAudio: false, icon: "🔁",
  },
  reading_open: {
    label: "Matn bo'yicha ochiq savol",
    hint: "Matn + ochiq savol. AI javob mazmunini tekshiradi.",
    check: "ai", input: "text", needsAudio: false, icon: "📖",
  },
  read_aloud: {
    label: "Ovoz chiqarib o'qish",
    hint: "Student matnni o'qiydi, AI talaffuzni tekshiradi.",
    check: "ai", input: "audio", needsAudio: false, icon: "🔊",
  },
  paraphrase: {
    label: "Boshqacha aytish",
    hint: "Gapni o'z so'zlari bilan aytish/yozish. AI tekshiradi.",
    check: "ai", input: "text", needsAudio: false, icon: "♻️",
  },
  dialogue_completion: {
    label: "Dialogni to'ldirish",
    hint: "Dialogdagi bo'sh javobni to'ldirish. Yozma yoki ovozli.",
    check: "ai", input: "audio_or_text", needsAudio: false, icon: "💬",
  },
  picture_description: {
    label: "Rasmni tasvirlash",
    hint: "Rasm beriladi, student tasvirlaydi. Yozma yoki ovozli.",
    check: "ai", input: "audio_or_text", needsAudio: false, icon: "🖼️",
  },
  listening: {
    label: "Tinglab tushunish",
    hint: "Audio yuklash SHART. Variantlardan to'g'risini tanlaydi, avtomatik tekshiriladi.",
    check: "auto", input: "choice", needsAudio: true, icon: "🎧",
  },
  dictation: {
    label: "Diktant",
    hint: "Audio yuklash SHART. Student eshitganini yozadi, avtomatik tekshiriladi.",
    check: "auto", input: "text", needsAudio: true, icon: "🎼",
  },
  spelling: {
    label: "To'g'ri yozish",
    hint: "So'zni imlo bilan yozish. Avtomatik tekshiriladi.",
    check: "auto", input: "text", needsAudio: false, icon: "🔤",
  },
  matching: {
    label: "Juftlab moslashtirish",
    hint: "Chap–o'ng juftliklar. Avtomatik tekshiriladi.",
    check: "auto", input: "pairs", needsAudio: false, icon: "🔗",
  },
  scrambled_sentence: {
    label: "So'zlarni tartibga solish",
    hint: "So'zlar aralashtiriladi, student to'g'ri gap tuzadi. Avtomatik tekshiriladi.",
    check: "auto", input: "order", needsAudio: false, icon: "🧩",
  },
  gap_fill: {
    label: "Bo'sh joyni to'ldirish",
    hint: "Gapdagi ___ ni to'ldirish. Avtomatik tekshiriladi.",
    check: "auto", input: "text", needsAudio: false, icon: "␣",
  },
  word_practice: {
    label: "So'z mashqi (random tur)",
    hint: "Bitta so'z. Studentga tushganda avtomatik random turga (gapirish/yozish/imlo/tarjima) aylanadi.",
    check: "ai", input: "text", needsAudio: false, icon: "🎲",
  },
};

export const AI_TEST_KINDS = Object.keys(AI_TEST_KIND_META) as AiTestKind[];

const INPUT_CLS =
  "w-full rounded-xl border border-line bg-surface-soft px-3.5 py-2.5 text-sm font-semibold text-navy-900 outline-none transition focus:ring-2 focus:ring-cyan-500 dark:border-white/10 dark:bg-navy-950 dark:text-white";
const LABEL_CLS = "mb-1 block text-xs font-black uppercase tracking-wide text-ink-500 dark:text-navy-300";

export function emptyAiQuestion(kind: AiTestKind): AiTestQuestion {
  const base: AiTestQuestion = { kind, prompt: "", instruction: "" };
  if (kind === "matching") return { ...base, pairs: [{ left: "", right: "" }, { left: "", right: "" }] };
  if (kind === "listening") return { ...base, options: ["", ""], correct_index: 0 };
  if (kind === "scrambled_sentence") return { ...base, answer: "", tokens: [] };
  if (kind === "word_practice") return { kind, word: "", translation: "", meaning: "" };
  if (AI_TEST_KIND_META[kind].check === "auto") return { ...base, answer: "", accepted_answers: [] };
  return { ...base, reference_answer: "" };
}

export function validateAiQuestions(questions: AiTestQuestion[]): string | null {
  if (!questions.length) return "Kamida bitta mashq qo'shilishi kerak.";
  for (let i = 0; i < questions.length; i++) {
    const q = questions[i];
    const meta = AI_TEST_KIND_META[q.kind];
    if (!meta) return `${i + 1}-mashq turi noto'g'ri.`;
    const n = i + 1;
    if (q.kind === "word_practice") {
      if (!String(q.word || "").trim()) return `${n}-mashq uchun so'z kiritilishi kerak.`;
      continue;
    }
    if (!String(q.prompt || "").trim() && !String(q.word || "").trim()) {
      return `${n}-mashqda topshiriq matni yoki so'z bo'lishi kerak.`;
    }
    if (meta.needsAudio && !String(q.audio_url || "").trim()) {
      return `${n}-mashq (${meta.label}) uchun audio fayl yuklanishi shart.`;
    }
    if (q.kind === "listening") {
      const opts = (q.options || []).map((o) => String(o || "").trim()).filter(Boolean);
      if (opts.length < 2) return `${n}-mashqda kamida 2 ta variant bo'lishi kerak.`;
      if (new Set(opts).size !== opts.length) return `${n}-mashq variantlari takrorlangan.`;
      const idx = Number(q.correct_index ?? 0);
      if (!Number.isInteger(idx) || idx < 0 || idx >= opts.length) return `${n}-mashqda to'g'ri variant belgilanmagan.`;
    } else if (q.kind === "matching") {
      const pairs = (q.pairs || []).filter((p) => String(p.left || "").trim() && String(p.right || "").trim());
      if (pairs.length < 2) return `${n}-mashqda kamida 2 ta to'liq juftlik bo'lishi kerak.`;
    } else if (meta.check === "auto") {
      if (!String(q.answer || "").trim()) return `${n}-mashq uchun to'g'ri javob kiritilmagan.`;
    }
    if (q.kind === "picture_description" && !String(q.image_url || "").trim()) {
      return `${n}-mashq uchun rasm yuklanishi kerak.`;
    }
    if (q.kind === "reading_open" && !String(q.passage || "").trim()) {
      return `${n}-mashq uchun matn (passage) kiritilishi kerak.`;
    }
  }
  return null;
}

export type UploadFn = (file: File) => Promise<string | null>;

function AssetField({
  label, value, accept, uploading, onUpload, onClear, required,
}: {
  label: string;
  value?: string | null;
  accept: string;
  uploading: boolean;
  onUpload: (file: File) => void;
  onClear: () => void;
  required?: boolean;
}) {
  return (
    <div>
      <label className={LABEL_CLS}>
        {label} {required ? <span className="text-red-500">*</span> : null}
      </label>
      {value ? (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-green-300 bg-green-50 px-3 py-2 dark:border-green-500/40 dark:bg-green-500/10">
          <span className="text-sm font-bold text-green-800 dark:text-green-100">Yuklandi ✓</span>
          {accept.startsWith("audio") ? (
            <audio controls src={value} className="h-8 max-w-[220px]" />
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={value} alt={label} className="h-12 w-12 rounded-lg object-cover" />
          )}
          <button type="button" onClick={onClear} className="ml-auto text-xs font-black text-red-500 hover:underline">
            O'chirish
          </button>
        </div>
      ) : (
        <label
          className={`flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed px-3 py-3 text-sm font-bold transition ${
            required
              ? "border-amber-400 bg-amber-50 text-amber-800 dark:border-amber-500/50 dark:bg-amber-500/10 dark:text-amber-100"
              : "border-line bg-surface-soft text-ink-600 dark:border-white/10 dark:bg-white/5 dark:text-navy-200"
          }`}
        >
          {uploading ? "Yuklanmoqda…" : `+ ${label}`}
          <input
            type="file"
            accept={accept}
            className="hidden"
            disabled={uploading}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onUpload(file);
              e.target.value = "";
            }}
          />
        </label>
      )}
    </div>
  );
}

export function AiTestEditor({
  questions,
  onChange,
  onUploadAsset,
  title = "Mashqlar",
}: {
  questions: AiTestQuestion[];
  onChange: (next: AiTestQuestion[]) => void;
  onUploadAsset: UploadFn;
  title?: string;
}) {
  const [addKind, setAddKind] = useState<AiTestKind>("write_sentence");
  const [uploadingIndex, setUploadingIndex] = useState<string>("");

  const stats = useMemo(() => {
    const missingAudio = questions.filter(
      (q) => AI_TEST_KIND_META[q.kind]?.needsAudio && !String(q.audio_url || "").trim()
    ).length;
    const aiCount = questions.filter((q) => AI_TEST_KIND_META[q.kind]?.check === "ai").length;
    return { missingAudio, aiCount, autoCount: questions.length - aiCount };
  }, [questions]);

  const patch = (index: number, next: Partial<AiTestQuestion>) =>
    onChange(questions.map((q, i) => (i === index ? { ...q, ...next } : q)));

  const move = (index: number, delta: number) => {
    const target = index + delta;
    if (target < 0 || target >= questions.length) return;
    const next = [...questions];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  };

  const upload = async (index: number, field: "audio_url" | "image_url", file: File) => {
    const key = `${index}-${field}`;
    setUploadingIndex(key);
    try {
      const url = await onUploadAsset(file);
      if (url) patch(index, { [field]: url, needs_audio_upload: false } as Partial<AiTestQuestion>);
    } finally {
      setUploadingIndex("");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-lg font-black text-navy-900 dark:text-white">{title}</h3>
        <span className="rounded-full bg-cyan-50 px-3 py-1 text-xs font-black text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-100">
          {questions.length} mashq · {stats.aiCount} AI · {stats.autoCount} avtomatik
        </span>
        {stats.missingAudio > 0 && (
          <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-black text-amber-800 dark:bg-amber-500/15 dark:text-amber-100">
            ⚠ {stats.missingAudio} ta mashqqa audio kerak
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          <select
            value={addKind}
            onChange={(e) => setAddKind(e.target.value as AiTestKind)}
            className="rounded-xl border border-line bg-surface-soft px-3 py-2 text-sm font-bold text-navy-900 dark:border-white/10 dark:bg-navy-950 dark:text-white"
          >
            {AI_TEST_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {AI_TEST_KIND_META[kind].icon} {AI_TEST_KIND_META[kind].label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => onChange([...questions, emptyAiQuestion(addKind)])}
            className="rounded-xl bg-cyan-500 px-4 py-2 text-sm font-black text-white shadow-sm transition hover:bg-cyan-600"
          >
            + Qo'shish
          </button>
        </div>
      </div>

      {questions.map((q, index) => {
        const meta = AI_TEST_KIND_META[q.kind];
        if (!meta) return null;
        const needsAudio = meta.needsAudio;
        return (
          <article
            key={`aiq-${index}`}
            className="rounded-2xl border border-line bg-white p-4 shadow-sm dark:border-white/10 dark:bg-navy-900/70"
          >
            <header className="mb-3 flex flex-wrap items-center gap-2">
              <span className="text-lg">{meta.icon}</span>
              <strong className="font-black text-navy-900 dark:text-white">
                {index + 1}. {meta.label}
              </strong>
              <span
                className={`rounded-full px-2.5 py-0.5 text-[11px] font-black ${
                  meta.check === "ai"
                    ? "bg-violet-50 text-violet-700 dark:bg-violet-500/15 dark:text-violet-100"
                    : "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-100"
                }`}
              >
                {meta.check === "ai" ? "AI tekshiradi" : "Avtomatik"}
              </span>
              <div className="ml-auto flex items-center gap-1">
                <button type="button" onClick={() => move(index, -1)} className="rounded-lg px-2 py-1 text-sm font-black text-ink-500 hover:bg-line dark:text-navy-300 dark:hover:bg-white/10">↑</button>
                <button type="button" onClick={() => move(index, 1)} className="rounded-lg px-2 py-1 text-sm font-black text-ink-500 hover:bg-line dark:text-navy-300 dark:hover:bg-white/10">↓</button>
                <button
                  type="button"
                  onClick={() => onChange(questions.filter((_, i) => i !== index))}
                  className="rounded-lg bg-red-50 px-2.5 py-1 text-sm font-black text-red-500 hover:bg-red-100 dark:bg-red-500/10"
                >
                  ✕
                </button>
              </div>
            </header>

            <p className="mb-3 text-xs font-semibold text-ink-500 dark:text-navy-300">{meta.hint}</p>

            <div className="grid gap-3 sm:grid-cols-2">
              {q.kind === "word_practice" ? (
                <>
                  <div>
                    <label className={LABEL_CLS}>So'z *</label>
                    <input
                      value={String(q.word || "")}
                      onChange={(e) => patch(index, { word: e.target.value })}
                      className={INPUT_CLS}
                      placeholder="decide"
                    />
                  </div>
                  <div>
                    <label className={LABEL_CLS}>Tarjimasi (ixtiyoriy)</label>
                    <input
                      value={String(q.translation || "")}
                      onChange={(e) => patch(index, { translation: e.target.value })}
                      className={INPUT_CLS}
                      placeholder="qaror qilmoq"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className={LABEL_CLS}>Ma'nosi (ixtiyoriy)</label>
                    <input
                      value={String(q.meaning || "")}
                      onChange={(e) => patch(index, { meaning: e.target.value })}
                      className={INPUT_CLS}
                      placeholder="to make a choice"
                    />
                  </div>
                </>
              ) : (
                <div className="sm:col-span-2">
                  <label className={LABEL_CLS}>Topshiriq matni *</label>
                  <textarea
                    value={String(q.prompt || "")}
                    onChange={(e) => patch(index, { prompt: e.target.value })}
                    className={`${INPUT_CLS} min-h-[70px]`}
                    placeholder={
                      q.kind === "gap_fill"
                        ? "She ___ to school every day."
                        : "Studentga ko'rinadigan topshiriq"
                    }
                  />
                </div>
              )}

              {(q.kind === "speak_sentence" || q.kind === "write_sentence" || q.kind === "spelling") && (
                <div>
                  <label className={LABEL_CLS}>Ishlatilishi shart so'z</label>
                  <input
                    value={String(q.word || "")}
                    onChange={(e) => patch(index, { word: e.target.value })}
                    className={INPUT_CLS}
                    placeholder="although"
                  />
                </div>
              )}

              <div>
                <label className={LABEL_CLS}>Daraja (ixtiyoriy)</label>
                <input
                  value={String(q.level || "")}
                  onChange={(e) => patch(index, { level: e.target.value })}
                  className={INPUT_CLS}
                  placeholder="A2 / B1"
                />
              </div>

              {(q.kind === "reading_open" || q.kind === "paraphrase" || q.kind === "read_aloud" || q.kind === "dialogue_completion") && (
                <div className="sm:col-span-2">
                  <label className={LABEL_CLS}>
                    Matn / dialog {q.kind === "reading_open" ? <span className="text-red-500">*</span> : null}
                  </label>
                  <textarea
                    value={String(q.passage || "")}
                    onChange={(e) => patch(index, { passage: e.target.value })}
                    className={`${INPUT_CLS} min-h-[90px]`}
                  />
                </div>
              )}

              {needsAudio && (
                <div className="sm:col-span-2">
                  <AssetField
                    label="Audio fayl (o'qituvchi yuklaydi)"
                    value={q.audio_url}
                    accept="audio/*"
                    required
                    uploading={uploadingIndex === `${index}-audio_url`}
                    onUpload={(file) => upload(index, "audio_url", file)}
                    onClear={() => patch(index, { audio_url: "" })}
                  />
                </div>
              )}

              {q.kind === "picture_description" && (
                <div className="sm:col-span-2">
                  <AssetField
                    label="Rasm"
                    value={q.image_url}
                    accept="image/*"
                    required
                    uploading={uploadingIndex === `${index}-image_url`}
                    onUpload={(file) => upload(index, "image_url", file)}
                    onClear={() => patch(index, { image_url: "" })}
                  />
                </div>
              )}

              {q.kind === "listening" && (
                <div className="sm:col-span-2 space-y-2">
                  <label className={LABEL_CLS}>Variantlar *</label>
                  {(q.options || []).map((opt, oIndex) => (
                    <div key={`opt-${index}-${oIndex}`} className="flex items-center gap-2">
                      <input
                        type="radio"
                        name={`ai-correct-${index}`}
                        checked={Number(q.correct_index ?? 0) === oIndex}
                        onChange={() => patch(index, { correct_index: oIndex })}
                        className="h-4 w-4 accent-cyan-500"
                      />
                      <input
                        value={opt}
                        onChange={(e) => {
                          const next = [...(q.options || [])];
                          next[oIndex] = e.target.value;
                          patch(index, { options: next });
                        }}
                        className={INPUT_CLS}
                        placeholder={`Variant ${oIndex + 1}`}
                      />
                      {(q.options || []).length > 2 && (
                        <button
                          type="button"
                          onClick={() => {
                            const next = (q.options || []).filter((_, i) => i !== oIndex);
                            patch(index, {
                              options: next,
                              correct_index: Math.min(Number(q.correct_index ?? 0), next.length - 1),
                            });
                          }}
                          className="text-red-400 hover:text-red-600"
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={() => patch(index, { options: [...(q.options || []), ""] })}
                    className="rounded-xl border border-line bg-surface-soft px-3 py-1.5 text-xs font-black dark:border-white/10 dark:bg-white/5 dark:text-white"
                  >
                    + Variant
                  </button>
                </div>
              )}

              {q.kind === "matching" && (
                <div className="sm:col-span-2 space-y-2">
                  <label className={LABEL_CLS}>Juftliklar *</label>
                  {(q.pairs || []).map((pair, pIndex) => (
                    <div key={`pair-${index}-${pIndex}`} className="flex items-center gap-2">
                      <input
                        value={pair.left}
                        onChange={(e) => {
                          const next = [...(q.pairs || [])];
                          next[pIndex] = { ...next[pIndex], left: e.target.value };
                          patch(index, { pairs: next });
                        }}
                        className={INPUT_CLS}
                        placeholder="brave"
                      />
                      <span className="font-black text-ink-400">→</span>
                      <input
                        value={pair.right}
                        onChange={(e) => {
                          const next = [...(q.pairs || [])];
                          next[pIndex] = { ...next[pIndex], right: e.target.value };
                          patch(index, { pairs: next });
                        }}
                        className={INPUT_CLS}
                        placeholder="not afraid"
                      />
                      {(q.pairs || []).length > 2 && (
                        <button
                          type="button"
                          onClick={() => patch(index, { pairs: (q.pairs || []).filter((_, i) => i !== pIndex) })}
                          className="text-red-400 hover:text-red-600"
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={() => patch(index, { pairs: [...(q.pairs || []), { left: "", right: "" }] })}
                    className="rounded-xl border border-line bg-surface-soft px-3 py-1.5 text-xs font-black dark:border-white/10 dark:bg-white/5 dark:text-white"
                  >
                    + Juftlik
                  </button>
                </div>
              )}

              {q.kind === "scrambled_sentence" && (
                <div className="sm:col-span-2">
                  <label className={LABEL_CLS}>To'g'ri gap *</label>
                  <input
                    value={String(q.answer || "")}
                    onChange={(e) =>
                      patch(index, {
                        answer: e.target.value,
                        tokens: e.target.value.replace(/[.,!?]/g, "").split(/\s+/).filter(Boolean),
                      })
                    }
                    className={INPUT_CLS}
                    placeholder="I have never been to Paris."
                  />
                  {(q.tokens || []).length > 0 && (
                    <p className="mt-1.5 flex flex-wrap gap-1.5">
                      {(q.tokens || []).map((token, tIndex) => (
                        <span
                          key={`tok-${index}-${tIndex}`}
                          className="rounded-lg bg-surface-soft px-2 py-0.5 text-xs font-bold text-navy-900 dark:bg-white/10 dark:text-white"
                        >
                          {token}
                        </span>
                      ))}
                    </p>
                  )}
                </div>
              )}

              {meta.check === "auto" && !["listening", "matching", "scrambled_sentence"].includes(q.kind) && (
                <>
                  <div>
                    <label className={LABEL_CLS}>To'g'ri javob *</label>
                    <input
                      value={String(q.answer || "")}
                      onChange={(e) => patch(index, { answer: e.target.value })}
                      className={INPUT_CLS}
                    />
                  </div>
                  <div>
                    <label className={LABEL_CLS}>Qabul qilinadigan boshqa javoblar</label>
                    <input
                      value={(q.accepted_answers || []).join(", ")}
                      onChange={(e) =>
                        patch(index, {
                          accepted_answers: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                        })
                      }
                      className={INPUT_CLS}
                      placeholder="vergul bilan ajratib yozing"
                    />
                  </div>
                </>
              )}

              {meta.check === "ai" && q.kind !== "word_practice" && (
                <div className="sm:col-span-2">
                  <label className={LABEL_CLS}>Namuna javob (AI uchun yo'riqnoma, ixtiyoriy)</label>
                  <textarea
                    value={String(q.reference_answer || "")}
                    onChange={(e) => patch(index, { reference_answer: e.target.value })}
                    className={`${INPUT_CLS} min-h-[60px]`}
                    placeholder="Although it was raining, we went out."
                  />
                </div>
              )}
            </div>
          </article>
        );
      })}

      {questions.length === 0 && (
        <div className="rounded-2xl border border-dashed border-line bg-surface-soft/50 p-8 text-center dark:border-white/10 dark:bg-white/[0.02]">
          <p className="font-bold text-ink-500 dark:text-navy-300">
            Hozircha mashq yo'q. Yuqoridan tur tanlab qo'shing yoki skrinshotdan AI bilan import qiling.
          </p>
        </div>
      )}
    </div>
  );
}
