"use client";

/**
 * AI test savollari muharriri — kutubxona testlari, skrinshotdan import qilingan
 * mashqlar va homeworkka biriktiriladigan testlar shu komponentdan foydalanadi.
 * Har bir `kind` uchun o'ziga xos maydonlar ko'rsatiladi.
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
  | "listening_tf"
  | "listening_dictation"
  | "listening_open"
  | "listening_gap"
  | "listening_order"
  | "listening_set"
  | "spelling"
  | "matching"
  | "scrambled_sentence"
  | "gap_fill"
  | "passage_cloze"
  | "reading_set"
  | "word_practice";

export type AiTestQuestion = {
  kind: AiTestKind;
  prompt?: string | null;
  instruction?: string | null;
  word?: string | null;
  translation?: string | null;
  translation_uz?: string | null;
  translation_ru?: string | null;
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
  distractors?: string[];
  answers?: { answer: string; accepted_answers?: string[] }[];
  word_bank?: string[];
  questions?: {
    type?: string;
    prompt?: string;
    options?: string[];
    answer?: string;
    accepted_answers?: string[];
  }[];
  sub_questions?: {
    type?: string;
    prompt?: string;
    options?: string[];
    correct_index?: number;
    answer?: string;
    accepted_answers?: string[];
    tokens?: string[];
    reference_answer?: string;
  }[];
  needs_audio_upload?: boolean;
  // Kengaytirilgan maydonlar
  hint?: string | null;          // spelling: ta'rif; gap_fill: qavs so'z; dictation: mavzu
  word_count?: number | null;    // guided_writing: minimal so'zlar soni
  example_sentence?: string | null; // word_practice: misol gap
  direction?: string | null;     // translation: UZ→EN, EN→UZ, RU→EN va h.k.
};

type KindMeta = {
  label: string;
  hint: string;
  check: "ai" | "auto";
  input: "text" | "audio" | "audio_or_text" | "choice" | "order" | "pairs" | "cloze" | "reading_set" | "listening_set";
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
    hint: "Audio yuklash SHART. Variantlardan to'g'risini tanlaydi, avtomatik tekshiriladi. Bitta audio uchun bir nechta savol qo'shish mumkin.",
    check: "auto", input: "choice", needsAudio: true, icon: "🎧",
  },
  dictation: {
    label: "Diktant",
    hint: "Audio yuklash SHART. Student eshitganini yozadi, avtomatik tekshiriladi.",
    check: "auto", input: "text", needsAudio: true, icon: "🎼",
  },
  listening_tf: {
    label: "Listening: True / False / Not Given",
    hint: "Audio yuklash shart. Student audio asosida True, False yoki Not Given ni tanlaydi.",
    check: "auto", input: "choice", needsAudio: true, icon: "🎧",
  },
  listening_dictation: {
    label: "Listening: diktant",
    hint: "Audio yuklash shart. Student eshitgan gap yoki matnni yozadi.",
    check: "auto", input: "text", needsAudio: true, icon: "🎙️",
  },
  listening_open: {
    label: "Listening: ochiq savol",
    hint: "Audio yuklash shart. Student audio asosida yozma javob beradi, AI tekshiradi.",
    check: "ai", input: "text", needsAudio: true, icon: "💭",
  },
  listening_gap: {
    label: "Listening: bo'sh joyni to'ldirish",
    hint: "Audio yuklash shart. Student eshitib kerakli so'z yoki iborani yozadi.",
    check: "auto", input: "text", needsAudio: true, icon: "␣",
  },
  listening_order: {
    label: "Listening: so'zlar tartibi",
    hint: "Audio yuklash shart. Student so'zlarni eshitgan gap tartibida joylaydi.",
    check: "auto", input: "order", needsAudio: true, icon: "🧩",
  },
  listening_set: {
    label: "Listening Set: bitta audio, ko'p savol",
    hint: "Bitta audio ostida bir nechta savol. Student hammasini bir oynada bajaradi.",
    check: "auto", input: "listening_set", needsAudio: true, icon: "🎧",
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
  passage_cloze: {
    label: "Matnni to'ldirish (so'zlar banki)",
    hint: "Yaxlit matn + bir nechta bo'sh joy (___) + so'zlar banki. Bitta kartada. Avtomatik tekshiriladi.",
    check: "auto", input: "cloze", needsAudio: false, icon: "📃",
  },
  reading_set: {
    label: "Matn va savollar",
    hint: "O'qish matni + bir nechta turli savol (True/False/NG, tanlov, sinonim, bo'sh joy, kim aytdi). Bitta kartada.",
    check: "auto", input: "reading_set", needsAudio: false, icon: "📚",
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
const SECTION_CLS = "sm:col-span-2";

export function emptyAiQuestion(kind: AiTestKind): AiTestQuestion {
  const base: AiTestQuestion = { kind, prompt: "", instruction: "" };
  switch (kind) {
    case "matching": return { ...base, pairs: [{ left: "", right: "" }, { left: "", right: "" }] };
    case "listening": return { ...base, audio_url: "", options: ["", "", "", ""], correct_index: 0 };
    case "listening_tf": return { ...base, audio_url: "", correct_index: 0 };
    case "listening_dictation": return { ...base, audio_url: "", answer: "", accepted_answers: [], hint: "" };
    case "listening_open": return { ...base, audio_url: "", reference_answer: "" };
    case "listening_gap": return { ...base, audio_url: "", answer: "", accepted_answers: [], hint: "" };
    case "listening_order": return { ...base, audio_url: "", answer: "", tokens: [], distractors: [] };
    case "listening_set": return { ...base, audio_url: "", sub_questions: [{ type: "mcq", prompt: "", options: ["", ""], correct_index: 0 }] };
    case "scrambled_sentence": return { ...base, answer: "", tokens: [], distractors: [] };
    case "passage_cloze": return { kind, instruction: "", passage: "", answers: [{ answer: "" }], word_bank: [] };
    case "reading_set": return { kind, passage: "", questions: [{ type: "true_false_ng", prompt: "", options: ["True", "False", "Not given"], answer: "" }] };
    case "word_practice": return { kind, word: "", translation_uz: "", translation_ru: "", example_sentence: "" };
    case "dictation": return { ...base, audio_url: "", answer: "", accepted_answers: [], hint: "" };
    case "spelling": return { kind, word: "", answer: "", accepted_answers: [], hint: "" };
    case "gap_fill": return { ...base, answer: "", accepted_answers: [], hint: "" };
    case "guided_writing": return { ...base, word_count: 30, reference_answer: "" };
    case "translation": return { ...base, direction: "EN→UZ", answer: "", accepted_answers: [] };
    case "reading_open": return { ...base, passage: "", reference_answer: "" };
    case "read_aloud": return { kind, passage: "", prompt: "", reference_answer: "" };
    case "paraphrase": return { kind, passage: "", prompt: "", reference_answer: "" };
    case "dialogue_completion": return { kind, passage: "", prompt: "", reference_answer: "" };
    case "picture_description": return { kind, image_url: "", prompt: "", instruction: "", reference_answer: "" };
    case "speak_sentence": return { ...base, word: "", reference_answer: "" };
    case "write_sentence": return { ...base, word: "", reference_answer: "" };
    default: return base;
  }
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
    if (q.kind === "spelling") {
      if (!String(q.word || "").trim()) return `${n}-mashq uchun so'z kiritilishi kerak.`;
      continue;
    }
    if (q.kind === "reading_set") {
      if (!String(q.passage || "").trim()) return `${n}-mashq uchun matn kiritilishi kerak.`;
      const rq = (q.questions || []).filter((x) => String(x?.prompt || "").trim() && String(x?.answer || "").trim());
      if (rq.length === 0) return `${n}-mashqda kamida bitta savol (matn + javob) bo'lishi kerak.`;
      continue;
    }
    if (q.kind === "passage_cloze") {
      const passage = String(q.passage || "");
      const gaps = (passage.match(/___/g) || []).length;
      const answers = (q.answers || []).filter((a) => String(a?.answer || "").trim());
      if (!passage.trim()) return `${n}-mashq uchun matn kiritilishi kerak.`;
      if (gaps === 0) return `${n}-mashq matnida kamida bitta ___ bo'sh joy bo'lishi kerak.`;
      if (answers.length !== gaps) return `${n}-mashqda bo'sh joylar soni (${gaps}) va javoblar soni (${answers.length}) mos kelmadi.`;
      continue;
    }
    if (q.kind === "read_aloud" || q.kind === "paraphrase" || q.kind === "dialogue_completion") {
      if (!String(q.passage || "").trim()) return `${n}-mashq uchun matn/dialog kiritilishi kerak.`;
      continue;
    }
    if (q.kind === "reading_open") {
      if (!String(q.passage || "").trim()) return `${n}-mashq uchun o'qish matni kiritilishi kerak.`;
      if (!String(q.prompt || "").trim()) return `${n}-mashq uchun savol kiritilishi kerak.`;
      continue;
    }
    if (q.kind === "picture_description") {
      if (!String(q.image_url || "").trim()) return `${n}-mashq uchun rasm yuklanishi kerak.`;
      continue;
    }
    if (meta.needsAudio && !String(q.audio_url || "").trim()) {
      return `${n}-mashq (${meta.label}) uchun audio fayl yuklanishi shart.`;
    }
    if (q.kind === "listening") {
      const opts = (q.options || []).map((o) => String(o || "").trim()).filter(Boolean);
      if (!String(q.prompt || "").trim()) return `${n}-mashqda savol matni bo'lishi kerak.`;
      if (opts.length < 2) return `${n}-mashqda kamida 2 ta variant bo'lishi kerak.`;
      if (new Set(opts).size !== opts.length) return `${n}-mashq variantlari takrorlangan.`;
      const idx = Number(q.correct_index ?? 0);
      if (!Number.isInteger(idx) || idx < 0 || idx >= opts.length) return `${n}-mashqda to'g'ri variant belgilanmagan.`;
      continue;
    }
    if (q.kind === "listening_tf") {
      if (!String(q.prompt || "").trim()) return `${n}-mashqda audio asosidagi savol matni bo'lishi kerak.`;
      continue;
    }
    if (q.kind === "listening_dictation" || q.kind === "listening_gap") {
      if (!String(q.prompt || "").trim()) return `${n}-mashqda student uchun ko'rsatma bo'lishi kerak.`;
      if (!String(q.answer || "").trim()) return `${n}-mashq uchun to'g'ri javob kiritilmagan.`;
      continue;
    }
    if (q.kind === "listening_open") {
      if (!String(q.prompt || "").trim()) return `${n}-mashqda audio asosidagi savol matni bo'lishi kerak.`;
      continue;
    }
    if (q.kind === "listening_order") {
      if (!String(q.prompt || "").trim()) return `${n}-mashqda ko'rsatma bo'lishi kerak.`;
      if (!String(q.answer || "").trim()) return `${n}-mashq uchun to'g'ri gap kiritilmagan.`;
      continue;
    }
    if (q.kind === "listening_set") {
      const subs = q.sub_questions || [];
      if (!String(q.prompt || "").trim()) return `${n}-mashqda ko'rsatma bo'lishi kerak.`;
      if (!subs.length) return `${n}-mashqda kamida bitta audio savol bo'lishi kerak.`;
      for (let subIndex = 0; subIndex < subs.length; subIndex++) {
        const sub = subs[subIndex];
        if (!String(sub.prompt || "").trim()) return `${n}-mashqning ${subIndex + 1}-savoli bo'sh.`;
        if (sub.type === "mcq" && (sub.options || []).filter((x) => String(x).trim()).length < 2) return `${n}-mashqning ${subIndex + 1}-savolida kamida 2 ta variant kerak.`;
        if (["gap", "dictation", "short", "order"].includes(String(sub.type || "")) && !String(sub.answer || "").trim()) return `${n}-mashqning ${subIndex + 1}-savolida to'g'ri javob bo'lishi kerak.`;
      }
      continue;
    }
    if (q.kind === "matching") {
      const pairs = (q.pairs || []).filter((p) => String(p.left || "").trim() && String(p.right || "").trim());
      if (pairs.length < 2) return `${n}-mashqda kamida 2 ta to'liq juftlik bo'lishi kerak.`;
      continue;
    }
    if (q.kind === "translation") {
      if (!String(q.prompt || "").trim()) return `${n}-mashq uchun tarjima qilinadigan matn kiritilishi kerak.`;
      if (!String(q.answer || "").trim()) return `${n}-mashq uchun to'g'ri tarjima kiritilishi kerak.`;
      continue;
    }
    if (!String(q.prompt || "").trim() && !String(q.word || "").trim() && !String(q.passage || "").trim()) {
      return `${n}-mashqda topshiriq matni yoki so'z bo'lishi kerak.`;
    }
    if (meta.check === "auto" && !["listening", "matching", "scrambled_sentence", "passage_cloze", "reading_set"].includes(q.kind)) {
      if (!String(q.answer || "").trim()) return `${n}-mashq uchun to'g'ri javob kiritilmagan.`;
    }
  }
  return null;
}

export type UploadFn = (file: File) => Promise<string | null>;

// ─── Yordamchi UI komponentlari ──────────────────────────────────────────────

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

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className={LABEL_CLS}>{label} {required && <span className="text-red-500">*</span>}</label>
      {children}
    </div>
  );
}

function FullField({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div className={SECTION_CLS}>
      <label className={LABEL_CLS}>{label} {required && <span className="text-red-500">*</span>}</label>
      {children}
    </div>
  );
}

// ─── Har bir kind uchun karta bloki ──────────────────────────────────────────

type PatchFn = (p: Partial<AiTestQuestion>) => void;
type UploadField = (field: "audio_url" | "image_url", file: File) => void;

function LevelField({ value, onChange }: { value?: string | null; onChange: (v: string) => void }) {
  return (
    <Field label="Daraja (ixtiyoriy)">
      <input value={String(value || "")} onChange={(e) => onChange(e.target.value)} className={INPUT_CLS} placeholder="A2 / B1" />
    </Field>
  );
}

function InstructionField({ value, onChange, placeholder }: { value?: string | null; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <FullField label="Ko'rsatma (ixtiyoriy)">
      <input value={String(value || "")} onChange={(e) => onChange(e.target.value)} className={INPUT_CLS} placeholder={placeholder || "Mashq ko'rsatmasi…"} />
    </FullField>
  );
}

function ReferenceAnswerField({ value, onChange }: { value?: string | null; onChange: (v: string) => void }) {
  return (
    <FullField label="Namuna javob (AI uchun yo'riqnoma, ixtiyoriy)">
      <textarea value={String(value || "")} onChange={(e) => onChange(e.target.value)} className={`${INPUT_CLS} min-h-[56px]`} placeholder="Namuna to'g'ri javob…" />
    </FullField>
  );
}

// speak_sentence / write_sentence
function SpeakWriteCard({ q, patch }: { q: AiTestQuestion; patch: PatchFn }) {
  return (
    <>
      <FullField label={q.kind === "speak_sentence" ? "Topshiriq (savol matni) *" : "Topshiriq (savol matni) *"} required>
        <textarea value={String(q.prompt || "")} onChange={(e) => patch({ prompt: e.target.value })} className={`${INPUT_CLS} min-h-[60px]`} placeholder={q.kind === "speak_sentence" ? "Make a sentence using the word below." : "Write a sentence using the word below."} />
      </FullField>
      <Field label="Ishlatilishi shart so'z">
        <input value={String(q.word || "")} onChange={(e) => patch({ word: e.target.value })} className={INPUT_CLS} placeholder="although" />
      </Field>
      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
      <ReferenceAnswerField value={q.reference_answer} onChange={(v) => patch({ reference_answer: v })} />
    </>
  );
}

// guided_writing
function GuidedWritingCard({ q, patch }: { q: AiTestQuestion; patch: PatchFn }) {
  return (
    <>
      <FullField label="Mavzu / topshiriq *" required>
        <textarea value={String(q.prompt || "")} onChange={(e) => patch({ prompt: e.target.value })} className={`${INPUT_CLS} min-h-[70px]`} placeholder="Write about your favourite holiday. Use past tense." />
      </FullField>
      <InstructionField value={q.instruction} onChange={(v) => patch({ instruction: v })} placeholder="Write at least 40 words." />
      <Field label="Minimal so'zlar soni">
        <input type="number" min={10} max={500} value={String(q.word_count ?? 30)} onChange={(e) => patch({ word_count: Number(e.target.value) || 30 })} className={INPUT_CLS} placeholder="30" />
      </Field>
      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
      <ReferenceAnswerField value={q.reference_answer} onChange={(v) => patch({ reference_answer: v })} />
    </>
  );
}

// translation
function TranslationCard({ q, patch }: { q: AiTestQuestion; patch: PatchFn }) {
  return (
    <>
      <FullField label="Tarjima qilinadigan matn *" required>
        <textarea value={String(q.prompt || "")} onChange={(e) => patch({ prompt: e.target.value })} className={`${INPUT_CLS} min-h-[70px]`} placeholder="She has been living in London for five years." />
      </FullField>
      <Field label="Tarjima yo'nalishi">
        <select value={String(q.direction || "EN→UZ")} onChange={(e) => patch({ direction: e.target.value })} className={INPUT_CLS}>
          <option value="EN→UZ">Inglizcha → O'zbekcha</option>
          <option value="EN→RU">Inglizcha → Ruscha</option>
          <option value="UZ→EN">O'zbekcha → Inglizcha</option>
          <option value="RU→EN">Ruscha → Inglizcha</option>
          <option value="RU→UZ">Ruscha → O'zbekcha</option>
          <option value="UZ→RU">O'zbekcha → Ruscha</option>
        </select>
      </Field>
      <Field label="To'g'ri tarjima *" required>
        <input value={String(q.answer || "")} onChange={(e) => patch({ answer: e.target.value })} className={INPUT_CLS} placeholder="U besh yildan beri Londonda yashaydi." />
      </Field>
      <Field label="Qabul qilinadigan boshqa tarjimalar">
        <input value={(q.accepted_answers || []).join(", ")} onChange={(e) => patch({ accepted_answers: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} className={INPUT_CLS} placeholder="vergul bilan ajratib yozing" />
      </Field>
      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
    </>
  );
}

// reading_open
function ReadingOpenCard({ q, patch }: { q: AiTestQuestion; patch: PatchFn }) {
  return (
    <>
      <FullField label="O'qish matni *" required>
        <textarea value={String(q.passage || "")} onChange={(e) => patch({ passage: e.target.value })} className={`${INPUT_CLS} min-h-[120px]`} placeholder="Matnni to'liq joylashtiring…" />
      </FullField>
      <FullField label="Savol *" required>
        <textarea value={String(q.prompt || "")} onChange={(e) => patch({ prompt: e.target.value })} className={`${INPUT_CLS} min-h-[56px]`} placeholder="What is the main idea of the text?" />
      </FullField>
      <InstructionField value={q.instruction} onChange={(v) => patch({ instruction: v })} />
      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
      <ReferenceAnswerField value={q.reference_answer} onChange={(v) => patch({ reference_answer: v })} />
    </>
  );
}

// read_aloud
function ReadAloudCard({ q, patch }: { q: AiTestQuestion; patch: PatchFn }) {
  return (
    <>
      <FullField label="O'qiladigan matn *" required>
        <textarea value={String(q.passage || "")} onChange={(e) => patch({ passage: e.target.value })} className={`${INPUT_CLS} min-h-[120px]`} placeholder="The quick brown fox jumps over the lazy dog. Read clearly and at a natural pace." />
      </FullField>
      <FullField label="Qo'shimcha ko'rsatma (ixtiyoriy)">
        <input value={String(q.prompt || "")} onChange={(e) => patch({ prompt: e.target.value })} className={INPUT_CLS} placeholder="Pay attention to stress and intonation." />
      </FullField>
      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
      <ReferenceAnswerField value={q.reference_answer} onChange={(v) => patch({ reference_answer: v })} />
    </>
  );
}

// paraphrase
function ParaphraseCard({ q, patch }: { q: AiTestQuestion; patch: PatchFn }) {
  return (
    <>
      <FullField label="Boshqacha aytilishi kerak bo'lgan gap *" required>
        <textarea value={String(q.passage || "")} onChange={(e) => patch({ passage: e.target.value })} className={`${INPUT_CLS} min-h-[70px]`} placeholder="Despite the rain, we decided to go for a walk." />
      </FullField>
      <FullField label="Topshiriq ko'rsatmasi">
        <input value={String(q.prompt || "")} onChange={(e) => patch({ prompt: e.target.value })} className={INPUT_CLS} placeholder="Rewrite the sentence using 'although'." />
      </FullField>
      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
      <ReferenceAnswerField value={q.reference_answer} onChange={(v) => patch({ reference_answer: v })} />
    </>
  );
}

// dialogue_completion
function DialogueCompletionCard({ q, patch }: { q: AiTestQuestion; patch: PatchFn }) {
  return (
    <>
      <FullField label="Dialog matni *" required>
        <textarea
          value={String(q.passage || "")}
          onChange={(e) => patch({ passage: e.target.value })}
          className={`${INPUT_CLS} min-h-[120px]`}
          placeholder={"A: Good morning! How are you?\nB: ___ [student fills this]\nA: That's great! What are you doing today?"}
        />
      </FullField>
      <p className="sm:col-span-2 -mt-1 text-[11px] font-semibold text-ink-400 dark:text-navy-400">
        ___ bilan student to'ldirishi kerak bo'lgan joyni belgilang (ixtiyoriy — AI o'zi topadi).
      </p>
      <FullField label="Ko'rsatma (ixtiyoriy)">
        <input value={String(q.prompt || "")} onChange={(e) => patch({ prompt: e.target.value })} className={INPUT_CLS} placeholder="Complete B's response in the dialogue." />
      </FullField>
      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
      <ReferenceAnswerField value={q.reference_answer} onChange={(v) => patch({ reference_answer: v })} />
    </>
  );
}

// picture_description
function PictureDescriptionCard({
  q, patch, uploading, onUpload,
}: { q: AiTestQuestion; patch: PatchFn; uploading: boolean; onUpload: UploadField }) {
  return (
    <>
      <div className={SECTION_CLS}>
        <AssetField
          label="Rasm *"
          value={q.image_url}
          accept="image/*"
          required
          uploading={uploading}
          onUpload={(file) => onUpload("image_url", file)}
          onClear={() => patch({ image_url: "" })}
        />
      </div>
      <FullField label="Ko'rsatma (ixtiyoriy)">
        <input value={String(q.prompt || "")} onChange={(e) => patch({ prompt: e.target.value })} className={INPUT_CLS} placeholder="Describe what you see in the picture." />
      </FullField>
      <FullField label="Qo'shimcha yo'riqnoma">
        <input value={String(q.instruction || "")} onChange={(e) => patch({ instruction: e.target.value })} className={INPUT_CLS} placeholder="Mention at least 3 objects. Speak for 30 seconds." />
      </FullField>
      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
      <ReferenceAnswerField value={q.reference_answer} onChange={(v) => patch({ reference_answer: v })} />
    </>
  );
}

// listening — audio ALOHIDA, savollar alohida
function ListeningCard({
  q, patch, uploading, onUpload,
}: { q: AiTestQuestion; patch: PatchFn; uploading: boolean; onUpload: UploadField }) {
  return (
    <>
      {/* Audio — bitta karta uchun, alohida saqlanadi */}
      <div className={SECTION_CLS}>
        <AssetField
          label="Audio fayl *"
          value={q.audio_url}
          accept="audio/*"
          required
          uploading={uploading}
          onUpload={(file) => onUpload("audio_url", file)}
          onClear={() => patch({ audio_url: "", needs_audio_upload: true })}
        />
      </div>

      {/* Savol matni */}
      <FullField label="Savol matni *" required>
        <textarea value={String(q.prompt || "")} onChange={(e) => patch({ prompt: e.target.value })} className={`${INPUT_CLS} min-h-[56px]`} placeholder="What is the woman's job?" />
      </FullField>

      {/* Variantlar */}
      <div className={SECTION_CLS}>
        <label className={LABEL_CLS}>
          Javob variantlari * <span className="font-semibold normal-case text-ink-400">(to'g'risini radio bilan belgilang)</span>
        </label>
        <div className="space-y-2">
          {(q.options || []).map((opt, oIndex) => (
            <div key={`opt-${oIndex}`} className="flex items-center gap-2">
              <input
                type="radio"
                name={`ai-correct-${q.prompt}`}
                checked={Number(q.correct_index ?? 0) === oIndex}
                onChange={() => patch({ correct_index: oIndex })}
                className="h-4 w-4 accent-cyan-500 shrink-0"
              />
              <input
                value={opt}
                onChange={(e) => {
                  const next = [...(q.options || [])];
                  next[oIndex] = e.target.value;
                  patch({ options: next });
                }}
                className={INPUT_CLS}
                placeholder={`${String.fromCharCode(65 + oIndex)}. Variant ${oIndex + 1}`}
              />
              {(q.options || []).length > 2 && (
                <button
                  type="button"
                  onClick={() => {
                    const next = (q.options || []).filter((_, i) => i !== oIndex);
                    patch({ options: next, correct_index: Math.min(Number(q.correct_index ?? 0), next.length - 1) });
                  }}
                  className="shrink-0 text-red-400 hover:text-red-600"
                >
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>
        {(q.options || []).length < 5 && (
          <button
            type="button"
            onClick={() => patch({ options: [...(q.options || []), ""] })}
            className="mt-2 rounded-xl border border-line bg-surface-soft px-3 py-1.5 text-xs font-black dark:border-white/10 dark:bg-white/5 dark:text-white"
          >
            + Variant
          </button>
        )}
        <p className="mt-1 text-[11px] font-semibold text-ink-400 dark:text-navy-400">
          💡 Bitta audio uchun bir nechta savol kerak bo'lsa — yangi "Tinglab tushunish" kartasi qo'shing va xuddi shu audio faylni qayta yuklang. Savollar alohida saqlanadi.
        </p>
      </div>

      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
    </>
  );
}

// dictation
function DictationCard({
  q, patch, uploading, onUpload,
}: { q: AiTestQuestion; patch: PatchFn; uploading: boolean; onUpload: UploadField }) {
  return (
    <>
      <div className={SECTION_CLS}>
        <AssetField
          label="Audio fayl *"
          value={q.audio_url}
          accept="audio/*"
          required
          uploading={uploading}
          onUpload={(file) => onUpload("audio_url", file)}
          onClear={() => patch({ audio_url: "", needs_audio_upload: true })}
        />
      </div>
      <FullField label="Studentga ko'rsatma *" required>
        <input value={String(q.prompt || "")} onChange={(e) => patch({ prompt: e.target.value })} className={INPUT_CLS} placeholder="Audioni tinglang va eshitganingizni yozing." />
      </FullField>
      <FullField label="Mavzu yoki hint (studentga ko'rsatiladi, ixtiyoriy)">
        <input value={String(q.hint || "")} onChange={(e) => patch({ hint: e.target.value })} className={INPUT_CLS} placeholder="Weather forecast audio — listen and write exactly what you hear." />
      </FullField>
      <FullField label="To'g'ri matn (diktant javob) *" required>
        <textarea value={String(q.answer || "")} onChange={(e) => patch({ answer: e.target.value })} className={`${INPUT_CLS} min-h-[70px]`} placeholder="Yesterday the weather was cold and rainy." />
      </FullField>
      <FullField label="Qabul qilinadigan boshqa variantlar">
        <input
          value={(q.accepted_answers || []).join(", ")}
          onChange={(e) => patch({ accepted_answers: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
          className={INPUT_CLS}
          placeholder="vergul bilan ajrating"
        />
      </FullField>
      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
    </>
  );
}

function ListeningTfCard({ q, patch, uploading, onUpload }: { q: AiTestQuestion; patch: PatchFn; uploading: boolean; onUpload: UploadField }) {
  const options = ["True", "False", "Not Given"];
  return (
    <>
      <div className={SECTION_CLS}><AssetField label="Audio fayl *" value={q.audio_url} accept="audio/*" required uploading={uploading} onUpload={(file) => onUpload("audio_url", file)} onClear={() => patch({ audio_url: "", needs_audio_upload: true })} /></div>
      <FullField label="Audio asosidagi gap yoki savol *" required><textarea value={String(q.prompt || "")} onChange={(e) => patch({ prompt: e.target.value })} className={`${INPUT_CLS} min-h-[56px]`} placeholder="The speaker says that the shop opens at 9 a.m." /></FullField>
      <div className={SECTION_CLS}>
        <label className={LABEL_CLS}>To'g'ri javob *</label>
        <div className="flex flex-wrap gap-2">{options.map((option, index) => <button key={option} type="button" onClick={() => patch({ correct_index: index })} className={`rounded-xl border-2 px-4 py-2 text-sm font-black ${Number(q.correct_index ?? 0) === index ? "border-cyan-500 bg-cyan-50 text-cyan-900 dark:bg-cyan-500/15 dark:text-cyan-100" : "border-line bg-surface-soft text-ink-600 dark:border-white/10 dark:bg-white/5 dark:text-navy-200"}`}>{option}</button>)}</div>
      </div>
      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
    </>
  );
}

function ListeningTextCard({ q, patch, uploading, onUpload, mode }: { q: AiTestQuestion; patch: PatchFn; uploading: boolean; onUpload: UploadField; mode: "dictation" | "open" | "gap" }) {
  const isOpen = mode === "open";
  return (
    <>
      <div className={SECTION_CLS}><AssetField label="Audio fayl *" value={q.audio_url} accept="audio/*" required uploading={uploading} onUpload={(file) => onUpload("audio_url", file)} onClear={() => patch({ audio_url: "", needs_audio_upload: true })} /></div>
      <FullField label="Studentga topshiriq *" required><textarea value={String(q.prompt || "")} onChange={(e) => patch({ prompt: e.target.value })} className={`${INPUT_CLS} min-h-[56px]`} placeholder={isOpen ? "Audioni tinglang. Nima uchun speaker kechikdi?" : mode === "gap" ? "Audioni tinglang va bo'sh joyni to'ldiring: She arrived ___." : "Audioni tinglang va eshitganingizni yozing."} /></FullField>
      {isOpen ? <ReferenceAnswerField value={q.reference_answer} onChange={(v) => patch({ reference_answer: v })} /> : <>
        <FullField label="To'g'ri javob *" required><input value={String(q.answer || "")} onChange={(e) => patch({ answer: e.target.value })} className={INPUT_CLS} placeholder="student yozishi kerak bo'lgan javob" /></FullField>
        <FullField label="Qabul qilinadigan boshqa javoblar"><input value={(q.accepted_answers || []).join(", ")} onChange={(e) => patch({ accepted_answers: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} className={INPUT_CLS} placeholder="vergul bilan ajrating" /></FullField>
      </>}
      {!isOpen && <FullField label="Hint (ixtiyoriy)"><input value={String(q.hint || "")} onChange={(e) => patch({ hint: e.target.value })} className={INPUT_CLS} placeholder="Studentga ko'rinadigan qisqa yo'riqnoma" /></FullField>}
      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
    </>
  );
}

function ListeningOrderCard({ q, patch, uploading, onUpload }: { q: AiTestQuestion; patch: PatchFn; uploading: boolean; onUpload: UploadField }) {
  return (
    <>
      <div className={SECTION_CLS}><AssetField label="Audio fayl *" value={q.audio_url} accept="audio/*" required uploading={uploading} onUpload={(file) => onUpload("audio_url", file)} onClear={() => patch({ audio_url: "", needs_audio_upload: true })} /></div>
      <ScrambledCard q={q} patch={patch} />
    </>
  );
}

function ListeningSetCard({ q, patch, uploading, onUpload }: { q: AiTestQuestion; patch: PatchFn; uploading: boolean; onUpload: UploadField }) {
  const subs = q.sub_questions || [];
  const patchSub = (index: number, value: NonNullable<AiTestQuestion["sub_questions"]>[number]) => {
    const next = [...subs]; next[index] = value; patch({ sub_questions: next });
  };
  return (
    <>
      <div className={SECTION_CLS}><AssetField label="Barcha savollar uchun audio *" value={q.audio_url} accept="audio/*" required uploading={uploading} onUpload={(file) => onUpload("audio_url", file)} onClear={() => patch({ audio_url: "", needs_audio_upload: true })} /></div>
      <FullField label="Studentga ko'rsatma *" required><input value={String(q.prompt || "")} onChange={(e) => patch({ prompt: e.target.value })} className={INPUT_CLS} placeholder="Audioni tinglang va barcha savollarga javob bering." /></FullField>
      <div className={SECTION_CLS}>
        <label className={LABEL_CLS}>Audio ostidagi savollar *</label>
        <div className="space-y-3">
          {subs.map((sub, index) => {
            const type = String(sub.type || "mcq");
            const options = sub.options || ["", ""];
            const needsChoice = type === "mcq";
            const needsAnswer = ["short", "gap", "dictation", "order"].includes(type);
            return <div key={index} className="rounded-xl border border-line p-3 dark:border-white/10">
              <div className="mb-2 flex gap-2"><strong className="pt-2 text-sm text-ink-500">{index + 1}.</strong><select value={type} onChange={(e) => patchSub(index, { ...sub, type: e.target.value, options: e.target.value === "mcq" ? options : undefined, correct_index: 0, answer: "", tokens: [] })} className="flex-1 rounded-lg border border-line bg-surface-soft px-2 py-1 text-sm font-bold dark:border-white/10 dark:bg-navy-950 dark:text-white"><option value="mcq">Tanlov</option><option value="tf">True / False / Not Given</option><option value="short">Qisqa javob</option><option value="gap">Bo'sh joy</option><option value="dictation">Diktant</option><option value="order">So'zlar tartibi</option><option value="open">Ochiq javob</option></select><button type="button" onClick={() => patch({ sub_questions: subs.filter((_, i) => i !== index) })} className="px-2 text-red-500">✕</button></div>
              <input value={String(sub.prompt || "")} onChange={(e) => patchSub(index, { ...sub, prompt: e.target.value })} className={`${INPUT_CLS} mb-2`} placeholder="Savol matni" />
              {needsChoice && <div className="space-y-1">{options.map((option, optionIndex) => <div key={optionIndex} className="flex gap-2"><input type="radio" checked={Number(sub.correct_index ?? 0) === optionIndex} onChange={() => patchSub(index, { ...sub, correct_index: optionIndex })} className="accent-cyan-500" /><input value={option} onChange={(e) => { const nextOptions = [...options]; nextOptions[optionIndex] = e.target.value; patchSub(index, { ...sub, options: nextOptions }); }} className={INPUT_CLS} placeholder={`${optionIndex + 1}-variant`} /></div>)}</div>}
              {type === "tf" && <select value={String(sub.correct_index ?? 0)} onChange={(e) => patchSub(index, { ...sub, correct_index: Number(e.target.value) })} className={INPUT_CLS}><option value="0">True</option><option value="1">False</option><option value="2">Not Given</option></select>}
              {needsAnswer && <input value={String(sub.answer || "")} onChange={(e) => patchSub(index, { ...sub, answer: e.target.value, tokens: type === "order" ? e.target.value.replace(/[.,!?;:]/g, "").split(/\s+/).filter(Boolean) : sub.tokens })} className={INPUT_CLS} placeholder={type === "order" ? "To'g'ri gap" : "To'g'ri javob"} />}
              {type === "open" && <input value={String(sub.reference_answer || "")} onChange={(e) => patchSub(index, { ...sub, reference_answer: e.target.value })} className={INPUT_CLS} placeholder="Namuna javob (ixtiyoriy)" />}
            </div>;
          })}
        </div>
        <button type="button" onClick={() => patch({ sub_questions: [...subs, { type: "mcq", prompt: "", options: ["", ""], correct_index: 0 }] })} className="mt-2 rounded-xl border border-line bg-surface-soft px-3 py-1.5 text-xs font-black dark:border-white/10 dark:bg-white/5 dark:text-white">+ Savol qo'shish</button>
      </div>
      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
    </>
  );
}

// spelling
function SpellingCard({ q, patch }: { q: AiTestQuestion; patch: PatchFn }) {
  const word = String(q.word || "");
  return (
    <>
      <Field label="So'z *" required>
        <input value={word} onChange={(e) => patch({ word: e.target.value, answer: e.target.value })} className={INPUT_CLS} placeholder="necessary" />
      </Field>
      <Field label="Ta'rif / hint (ixtiyoriy)">
        <input value={String(q.hint || "")} onChange={(e) => patch({ hint: e.target.value })} className={INPUT_CLS} placeholder="Something you need; not optional." />
      </Field>
      <FullField label="Qabul qilinadigan boshqa yozilishlar">
        <input
          value={(q.accepted_answers || []).join(", ")}
          onChange={(e) => patch({ accepted_answers: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
          className={INPUT_CLS}
          placeholder="Muqobil to'g'ri yozilishlar (vergul bilan)"
        />
      </FullField>
      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
      {word && (
        <div className="sm:col-span-2 rounded-xl bg-surface-soft px-3 py-2 text-xs font-semibold text-ink-500 dark:bg-white/5 dark:text-navy-300">
          Student bu so'zni eshitmasdan faqat ta'rifni ko'rib yozishi kerak bo'ladi.
          Javob: <span className="font-black text-navy-900 dark:text-white">{word}</span>
        </div>
      )}
    </>
  );
}

// matching
function MatchingCard({ q, patch }: { q: AiTestQuestion; patch: PatchFn }) {
  return (
    <>
      <FullField label="Ko'rsatma (ixtiyoriy)">
        <input value={String(q.prompt || "")} onChange={(e) => patch({ prompt: e.target.value })} className={INPUT_CLS} placeholder="Match the words to their definitions." />
      </FullField>
      <div className={SECTION_CLS}>
        <label className={LABEL_CLS}>Juftliklar * (kamida 2 ta)</label>
        <div className="space-y-2">
          {(q.pairs || []).map((pair, pIndex) => (
            <div key={`pair-${pIndex}`} className="flex items-center gap-2">
              <input
                value={pair.left}
                onChange={(e) => {
                  const next = [...(q.pairs || [])];
                  next[pIndex] = { ...next[pIndex], left: e.target.value };
                  patch({ pairs: next });
                }}
                className={INPUT_CLS}
                placeholder="brave"
              />
              <span className="shrink-0 font-black text-ink-400">→</span>
              <input
                value={pair.right}
                onChange={(e) => {
                  const next = [...(q.pairs || [])];
                  next[pIndex] = { ...next[pIndex], right: e.target.value };
                  patch({ pairs: next });
                }}
                className={INPUT_CLS}
                placeholder="not afraid"
              />
              {(q.pairs || []).length > 2 && (
                <button
                  type="button"
                  onClick={() => patch({ pairs: (q.pairs || []).filter((_, i) => i !== pIndex) })}
                  className="shrink-0 text-red-400 hover:text-red-600"
                >
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={() => patch({ pairs: [...(q.pairs || []), { left: "", right: "" }] })}
          className="mt-2 rounded-xl border border-line bg-surface-soft px-3 py-1.5 text-xs font-black dark:border-white/10 dark:bg-white/5 dark:text-white"
        >
          + Juftlik
        </button>
      </div>
      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
    </>
  );
}

// scrambled_sentence
function ScrambledCard({ q, patch }: { q: AiTestQuestion; patch: PatchFn }) {
  return (
    <>
      <FullField label="Ko'rsatma (ixtiyoriy)">
        <input value={String(q.prompt || "")} onChange={(e) => patch({ prompt: e.target.value })} className={INPUT_CLS} placeholder="Put the words in the correct order." />
      </FullField>
      <FullField label="To'g'ri gap *" required>
        <input
          value={String(q.answer || "")}
          onChange={(e) =>
            patch({
              answer: e.target.value,
              tokens: e.target.value.replace(/[.,!?;:]/g, "").split(/\s+/).filter(Boolean),
            })
          }
          className={INPUT_CLS}
          placeholder="I have never been to Paris."
        />
      </FullField>
      {(q.tokens || []).length > 0 && (
        <div className={SECTION_CLS}>
          <p className="mb-1 text-[11px] font-black uppercase tracking-wide text-ink-400 dark:text-navy-400">Tokenlar (avtomatik)</p>
          <div className="flex flex-wrap gap-1.5">
            {(q.tokens || []).map((token, tIndex) => (
              <span key={`tok-${tIndex}`} className="rounded-lg bg-cyan-50 px-2 py-0.5 text-xs font-bold text-cyan-800 dark:bg-cyan-500/15 dark:text-cyan-100">
                {token}
              </span>
            ))}
          </div>
        </div>
      )}
      <FullField label="Chalg'ituvchi so'zlar (vergul bilan, ixtiyoriy)">
        <input
          value={(q.distractors || []).join(", ")}
          onChange={(e) => patch({ distractors: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
          className={INPUT_CLS}
          placeholder="was, going, the"
        />
      </FullField>
      <p className="sm:col-span-2 -mt-1 text-[11px] font-semibold text-ink-400 dark:text-navy-400">
        Chalg'ituvchi so'zlar gapga kirmaydi — student ularni aralashgan holda ko'radi.
      </p>
      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
    </>
  );
}

// gap_fill
function GapFillCard({ q, patch }: { q: AiTestQuestion; patch: PatchFn }) {
  return (
    <>
      <FullField label="Gap (___ bilan) *" required>
        <textarea value={String(q.prompt || "")} onChange={(e) => patch({ prompt: e.target.value })} className={`${INPUT_CLS} min-h-[60px]`} placeholder="She ___ to school every day." />
      </FullField>
      <Field label="Qavs ichidagi hint (ixtiyoriy)">
        <input value={String(q.hint || "")} onChange={(e) => patch({ hint: e.target.value })} className={INPUT_CLS} placeholder="(go) — fe'l shaklini o'zgartiring" />
      </Field>
      <Field label="To'g'ri javob *" required>
        <input value={String(q.answer || "")} onChange={(e) => patch({ answer: e.target.value })} className={INPUT_CLS} placeholder="goes" />
      </Field>
      <FullField label="Qabul qilinadigan boshqa javoblar">
        <input
          value={(q.accepted_answers || []).join(", ")}
          onChange={(e) => patch({ accepted_answers: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
          className={INPUT_CLS}
          placeholder="vergul bilan ajrating"
        />
      </FullField>
      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
    </>
  );
}

// passage_cloze
function PassageClozeCard({ q, patch }: { q: AiTestQuestion; patch: PatchFn }) {
  const gaps = (String(q.passage || "").match(/___/g) || []).length;
  return (
    <>
      <FullField label="Ko'rsatma (ixtiyoriy)">
        <input value={String(q.instruction || "")} onChange={(e) => patch({ instruction: e.target.value })} className={INPUT_CLS} placeholder="Fe'llarni to'g'ri shaklda qo'ying." />
      </FullField>
      <FullField label="Matn * (har bo'sh joyni ___ bilan belgilang)" required>
        <textarea
          value={String(q.passage || "")}
          onChange={(e) => {
            const passage = e.target.value;
            const g = (passage.match(/___/g) || []).length;
            const cur = q.answers || [];
            const next = Array.from({ length: g }, (_, i) => cur[i] || { answer: "" });
            patch({ passage, answers: next });
          }}
          className={`${INPUT_CLS} min-h-[110px]`}
          placeholder={"Last Tuesday Lisa ___ from London to Madrid. She ___ up at 6 o'clock."}
        />
        <p className="mt-1 text-[11px] font-semibold text-ink-400 dark:text-navy-400">
          Bo'sh joylar: <span className="font-black text-navy-900 dark:text-white">{gaps}</span> ta
        </p>
      </FullField>
      {gaps > 0 && (
        <div className={SECTION_CLS}>
          <label className={LABEL_CLS}>Bo'sh joylar javoblari (tartib bo'yicha) *</label>
          <div className="space-y-1.5">
            {(q.answers || []).map((a, ai) => (
              <div key={ai} className="flex items-center gap-2">
                <span className="w-6 shrink-0 text-sm font-black text-ink-500">{ai + 1}.</span>
                <input
                  value={String(a?.answer || "")}
                  onChange={(e) => {
                    const next = [...(q.answers || [])];
                    next[ai] = { ...next[ai], answer: e.target.value };
                    patch({ answers: next });
                  }}
                  className={INPUT_CLS}
                  placeholder="to'g'ri so'z"
                />
              </div>
            ))}
          </div>
        </div>
      )}
      <FullField label="So'zlar banki (vergul bilan; javoblar avtomatik qo'shiladi)">
        <input
          value={(q.word_bank || []).join(", ")}
          onChange={(e) => patch({ word_bank: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
          className={INPUT_CLS}
          placeholder="fly, get, have, leave, drive"
        />
      </FullField>
    </>
  );
}

// reading_set
function ReadingSetCard({ q, patch }: { q: AiTestQuestion; patch: PatchFn }) {
  const TF_OPTIONS = ["True", "False", "Not given"];

  return (
    <>
      <FullField label="O'qish matni *" required>
        <textarea value={String(q.passage || "")} onChange={(e) => patch({ passage: e.target.value })} className={`${INPUT_CLS} min-h-[140px]`} placeholder="Matnni to'liq joylashtiring…" />
      </FullField>
      <div className={SECTION_CLS}>
        <label className={LABEL_CLS}>Savollar *</label>
        <div className="space-y-3">
          {(q.questions || []).map((rq, ri) => {
            const type = String(rq.type || "short");
            const isTfng = type === "true_false_ng";
            const isChoice = type === "choice";
            return (
              <div key={ri} className="rounded-xl border border-line p-3 dark:border-white/10">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="text-xs font-black text-ink-500">{ri + 1}.</span>
                  <select
                    value={type}
                    onChange={(e) => {
                      const next = [...(q.questions || [])];
                      const t = e.target.value;
                      next[ri] = {
                        ...next[ri],
                        type: t,
                        options: t === "true_false_ng" ? TF_OPTIONS : t === "choice" ? (next[ri].options || ["", "", "", ""]) : [],
                      };
                      patch({ questions: next });
                    }}
                    className="rounded-lg border border-line bg-surface-soft px-2 py-1 text-xs font-bold dark:border-white/10 dark:bg-navy-950 dark:text-white"
                  >
                    <option value="true_false_ng">True / False / Not given</option>
                    <option value="choice">Tanlov (multiple choice)</option>
                    <option value="synonym">Sinonim</option>
                    <option value="gap">Bo'sh joy</option>
                    <option value="who_said">Kim aytdi / qildi</option>
                    <option value="short">Qisqa javob</option>
                  </select>
                  <button
                    type="button"
                    onClick={() => patch({ questions: (q.questions || []).filter((_, i2) => i2 !== ri) })}
                    className="ml-auto text-sm font-black text-red-500 hover:text-red-600"
                  >
                    ✕
                  </button>
                </div>

                {/* Savol matni */}
                <input
                  value={String(rq.prompt || "")}
                  onChange={(e) => {
                    const next = [...(q.questions || [])];
                    next[ri] = { ...next[ri], prompt: e.target.value };
                    patch({ questions: next });
                  }}
                  className={`${INPUT_CLS} mb-2`}
                  placeholder="Savol matni…"
                />

                {/* True/False/Not given — 3 chip */}
                {isTfng && (
                  <div className="flex flex-wrap gap-2 mb-2">
                    {TF_OPTIONS.map((opt) => (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => {
                          const next = [...(q.questions || [])];
                          next[ri] = { ...next[ri], answer: opt };
                          patch({ questions: next });
                        }}
                        className={`rounded-xl px-3 py-1.5 text-sm font-black transition border-2 ${
                          rq.answer === opt
                            ? opt === "True"
                              ? "border-emerald-500 bg-emerald-50 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-100"
                              : opt === "False"
                              ? "border-red-400 bg-red-50 text-red-800 dark:bg-red-500/15 dark:text-red-100"
                              : "border-amber-400 bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-100"
                            : "border-line bg-surface-soft text-ink-600 dark:border-white/10 dark:bg-white/5 dark:text-navy-300"
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                )}

                {/* Multiple choice — 4 variant */}
                {isChoice && (
                  <div className="space-y-1.5 mb-2">
                    {(rq.options || ["", "", "", ""]).map((opt, oi) => (
                      <div key={oi} className="flex items-center gap-2">
                        <input
                          type="radio"
                          name={`rs-correct-${ri}`}
                          checked={rq.answer === opt && !!opt.trim()}
                          onChange={() => {
                            const next = [...(q.questions || [])];
                            next[ri] = { ...next[ri], answer: opt };
                            patch({ questions: next });
                          }}
                          className="h-4 w-4 accent-cyan-500 shrink-0"
                        />
                        <input
                          value={opt}
                          onChange={(e) => {
                            const next = [...(q.questions || [])];
                            const opts = [...(next[ri].options || ["", "", "", ""])];
                            opts[oi] = e.target.value;
                            const wasCorrect = next[ri].answer === opt;
                            next[ri] = { ...next[ri], options: opts, answer: wasCorrect ? e.target.value : next[ri].answer };
                            patch({ questions: next });
                          }}
                          className={INPUT_CLS}
                          placeholder={`${String.fromCharCode(65 + oi)}. Variant`}
                        />
                      </div>
                    ))}
                    <p className="text-[11px] text-ink-400 dark:text-navy-400">Radio bilan to'g'ri variantni belgilang.</p>
                  </div>
                )}

                {/* Qisqa javob (non-TF, non-choice) */}
                {!isTfng && !isChoice && (
                  <input
                    value={String(rq.answer || "")}
                    onChange={(e) => {
                      const next = [...(q.questions || [])];
                      next[ri] = { ...next[ri], answer: e.target.value };
                      patch({ questions: next });
                    }}
                    className={INPUT_CLS}
                    placeholder="To'g'ri javob"
                  />
                )}
              </div>
            );
          })}
        </div>
        <button
          type="button"
          onClick={() =>
            patch({
              questions: [
                ...(q.questions || []),
                { type: "short", prompt: "", answer: "", options: [] },
              ],
            })
          }
          className="mt-2 rounded-xl border border-line bg-surface-soft px-3 py-1.5 text-xs font-black dark:border-white/10 dark:bg-white/5 dark:text-white"
        >
          + Savol
        </button>
      </div>
    </>
  );
}

// word_practice
function WordPracticeCard({ q, patch }: { q: AiTestQuestion; patch: PatchFn }) {
  return (
    <>
      <Field label="So'z *" required>
        <input value={String(q.word || "")} onChange={(e) => patch({ word: e.target.value })} className={INPUT_CLS} placeholder="decide" />
      </Field>
      <LevelField value={q.level} onChange={(v) => patch({ level: v })} />
      <Field label="Tarjima — o'zbekcha">
        <input value={String(q.translation_uz ?? q.translation ?? "")} onChange={(e) => patch({ translation_uz: e.target.value })} className={INPUT_CLS} placeholder="qaror qilmoq" />
      </Field>
      <Field label="Tarjima — ruscha">
        <input value={String(q.translation_ru ?? q.meaning ?? "")} onChange={(e) => patch({ translation_ru: e.target.value })} className={INPUT_CLS} placeholder="решать" />
      </Field>
      <FullField label="Misol gap (ixtiyoriy)">
        <input value={String(q.example_sentence || "")} onChange={(e) => patch({ example_sentence: e.target.value })} className={INPUT_CLS} placeholder="I decided to study harder." />
      </FullField>
      <div className="sm:col-span-2 rounded-xl bg-violet-50 px-3 py-2 text-xs font-semibold text-violet-700 dark:bg-violet-500/10 dark:text-violet-200">
        🎲 Student bu so'zga yetganda tizim avtomatik ravishda: gapirish, yozish, imlo yoki tarjima — random biriga aylantiradi.
      </div>
    </>
  );
}

// ─── Asosiy muharrir ──────────────────────────────────────────────────────────

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
      {/* Header */}
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

      {/* Savollar */}
      {questions.map((q, index) => {
        const meta = AI_TEST_KIND_META[q.kind];
        if (!meta) return null;
        const patchQ = (p: Partial<AiTestQuestion>) => patch(index, p);
        const uploadQ = (field: "audio_url" | "image_url", file: File) => upload(index, field, file);
        const isUploading = (field: string) => uploadingIndex === `${index}-${field}`;

        return (
          <article
            key={`aiq-${index}`}
            className="rounded-2xl border border-line bg-white p-4 shadow-sm dark:border-white/10 dark:bg-navy-900/70"
          >
            {/* Karta sarlavhasi */}
            <header className="mb-3 flex flex-wrap items-center gap-2">
              <span className="text-lg">{meta.icon}</span>
              <strong className="font-black text-navy-900 dark:text-white">{index + 1}.</strong>
              <select
                value={q.kind}
                onChange={(e) => {
                  const nextKind = e.target.value as AiTestKind;
                  onChange(
                    questions.map((qq, i) =>
                      i === index
                        ? { ...emptyAiQuestion(nextKind), prompt: qq.prompt, word: qq.word, level: qq.level }
                        : qq
                    )
                  );
                }}
                className="rounded-lg border border-line bg-surface-soft px-2 py-1 text-sm font-bold text-navy-900 dark:border-white/10 dark:bg-navy-950 dark:text-white"
                title="Bu savol turini o'zgartirish"
              >
                {AI_TEST_KINDS.map((k) => (
                  <option key={k} value={k}>
                    {AI_TEST_KIND_META[k].icon} {AI_TEST_KIND_META[k].label}
                  </option>
                ))}
              </select>
              <span
                className={`rounded-full px-2.5 py-0.5 text-[11px] font-black ${
                  meta.check === "ai"
                    ? "bg-violet-50 text-violet-700 dark:bg-violet-500/15 dark:text-violet-100"
                    : "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-100"
                }`}
              >
                {meta.check === "ai" ? "🤖 AI tekshiradi" : "⚡ Avtomatik"}
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

            {/* Kind-specific maydonlar */}
            <div className="grid gap-3 sm:grid-cols-2">
              {(q.kind === "speak_sentence" || q.kind === "write_sentence") && (
                <SpeakWriteCard q={q} patch={patchQ} />
              )}
              {q.kind === "guided_writing" && <GuidedWritingCard q={q} patch={patchQ} />}
              {q.kind === "translation" && <TranslationCard q={q} patch={patchQ} />}
              {q.kind === "reading_open" && <ReadingOpenCard q={q} patch={patchQ} />}
              {q.kind === "read_aloud" && <ReadAloudCard q={q} patch={patchQ} />}
              {q.kind === "paraphrase" && <ParaphraseCard q={q} patch={patchQ} />}
              {q.kind === "dialogue_completion" && <DialogueCompletionCard q={q} patch={patchQ} />}
              {q.kind === "picture_description" && (
                <PictureDescriptionCard q={q} patch={patchQ} uploading={isUploading("image_url")} onUpload={uploadQ} />
              )}
              {q.kind === "listening" && (
                <ListeningCard q={q} patch={patchQ} uploading={isUploading("audio_url")} onUpload={uploadQ} />
              )}
              {q.kind === "dictation" && (
                <DictationCard q={q} patch={patchQ} uploading={isUploading("audio_url")} onUpload={uploadQ} />
              )}
              {q.kind === "listening_tf" && <ListeningTfCard q={q} patch={patchQ} uploading={isUploading("audio_url")} onUpload={uploadQ} />}
              {q.kind === "listening_dictation" && <ListeningTextCard q={q} patch={patchQ} mode="dictation" uploading={isUploading("audio_url")} onUpload={uploadQ} />}
              {q.kind === "listening_open" && <ListeningTextCard q={q} patch={patchQ} mode="open" uploading={isUploading("audio_url")} onUpload={uploadQ} />}
              {q.kind === "listening_gap" && <ListeningTextCard q={q} patch={patchQ} mode="gap" uploading={isUploading("audio_url")} onUpload={uploadQ} />}
              {q.kind === "listening_order" && <ListeningOrderCard q={q} patch={patchQ} uploading={isUploading("audio_url")} onUpload={uploadQ} />}
              {q.kind === "listening_set" && <ListeningSetCard q={q} patch={patchQ} uploading={isUploading("audio_url")} onUpload={uploadQ} />}
              {q.kind === "spelling" && <SpellingCard q={q} patch={patchQ} />}
              {q.kind === "matching" && <MatchingCard q={q} patch={patchQ} />}
              {q.kind === "scrambled_sentence" && <ScrambledCard q={q} patch={patchQ} />}
              {q.kind === "gap_fill" && <GapFillCard q={q} patch={patchQ} />}
              {q.kind === "passage_cloze" && <PassageClozeCard q={q} patch={patchQ} />}
              {q.kind === "reading_set" && <ReadingSetCard q={q} patch={patchQ} />}
              {q.kind === "word_practice" && <WordPracticeCard q={q} patch={patchQ} />}
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
