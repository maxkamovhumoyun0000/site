"use client";

import React from "react";
import { useWebT } from "./web-i18n";

export type TestQuestion = {
  question: string;
  options: string[];
  correct: string;
  explanation: string;
  time_limit_sec?: number | string;
};

export type SharedTestEditorProps = {
  questions: TestQuestion[];
  onChange: (questions: TestQuestion[]) => void;
  title?: string;
};

export function SharedTestEditor({ questions, onChange, title = "Test Savollari" }: SharedTestEditorProps) {
  const tt = useWebT();
  const addQuestion = () => {
    onChange([
      ...questions,
      { question: "", options: ["", ""], correct: "", explanation: "", time_limit_sec: 30 },
    ]);
  };

  const removeQuestion = (index: number) => {
    onChange(questions.filter((_, i) => i !== index));
  };

  const updateQuestion = (index: number, patch: Partial<TestQuestion>) => {
    onChange(
      questions.map((q, i) => {
        if (i === index) return { ...q, ...patch };
        return q;
      })
    );
  };

  const addOption = (qIndex: number) => {
    const q = questions[qIndex];
    if (!q) return;
    updateQuestion(qIndex, { options: [...q.options, ""] });
  };

  const removeOption = (qIndex: number, oIndex: number) => {
    const q = questions[qIndex];
    if (!q || q.options.length <= 2) return; // min 2 options
    const removedOption = q.options[oIndex];
    const newOptions = q.options.filter((_, i) => i !== oIndex);
    // If correct answer was the removed option, clear correct answer
    const newCorrect = q.correct === removedOption ? "" : q.correct;
    updateQuestion(qIndex, { options: newOptions, correct: newCorrect });
  };

  const updateOption = (qIndex: number, oIndex: number, value: string) => {
    const q = questions[qIndex];
    if (!q) return;
    const oldVal = q.options[oIndex];
    const newOptions = [...q.options];
    newOptions[oIndex] = value;
    // update correct answer if it was matching the old option
    const newCorrect = q.correct === oldVal ? value : q.correct;
    updateQuestion(qIndex, { options: newOptions, correct: newCorrect });
  };

  return (
    <div className="shared-test-editor space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-black text-navy-900 dark:text-white">{title}</h3>
        <button
          type="button"
          onClick={addQuestion}
          className="rounded-xl bg-cyan-500 px-4 py-2 text-sm font-black text-white hover:bg-cyan-600 transition-colors shadow-sm"
        >
          {tt("contentTest.addQuestion", "Savol qo'shish")}
        </button>
      </div>

      {questions.map((q, qIndex) => (
        <article
          key={`q-${qIndex}`}
          className="shared-test-question rounded-2xl border border-line bg-white p-5 shadow-sm dark:border-white/10 dark:bg-navy-900/70"
        >
          <div className="mb-4 flex items-center justify-between gap-4">
            <strong className="text-lg font-black text-navy-900 dark:text-white">
              {tt("contentTest.question", "Savol")} {qIndex + 1}
            </strong>
            <label className="ml-auto flex items-center gap-2 text-xs font-bold text-ink-600 dark:text-navy-200">
              <span>{tt("contentTest.questionSeconds", "Sekund")}</span>
              <input
                type="number"
                min={10}
                max={300}
                step={5}
                value={q.time_limit_sec ?? 30}
                onChange={(e) => updateQuestion(qIndex, { time_limit_sec: e.target.value })}
                className="w-20 rounded-lg border border-line bg-surface-soft px-2 py-1.5 text-sm font-black text-navy-900 outline-none focus:ring-2 focus:ring-cyan-500 dark:border-white/10 dark:bg-navy-950 dark:text-white"
                aria-label={tt("contentTest.questionSeconds", "Sekund")}
              />
            </label>
            <button
              type="button"
              onClick={() => removeQuestion(qIndex)}
              className="rounded-lg bg-red-50 p-2 text-red-500 hover:bg-red-100 dark:bg-red-500/10 dark:hover:bg-red-500/20 transition-colors"
              title={tt("common.delete", "O'chirish")}
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-bold text-ink-600 dark:text-navy-200">
                {tt("contentTest.questionText", "Savol matni")} *
              </label>
              <textarea
                value={q.question}
                onChange={(e) => updateQuestion(qIndex, { question: e.target.value })}
                className="w-full min-h-[80px] rounded-xl border border-line bg-surface-soft px-4 py-3 text-sm font-semibold text-navy-900 outline-none focus:ring-2 focus:ring-cyan-500 dark:border-white/10 dark:bg-navy-950 dark:text-white transition-all"
                placeholder={tt("contentTest.questionPlaceholder", "Savolni kiriting...")}
              />
            </div>

            <div className="space-y-3">
              <label className="block text-sm font-bold text-ink-600 dark:text-navy-200">
                {tt("contentTest.options", "Variantlar")} * ({tt("contentTest.minTwoOptions", "kamida 2 ta")})
              </label>
              {q.options.map((opt, oIndex) => (
                <div key={`o-${qIndex}-${oIndex}`} className="shared-test-option-row flex items-center gap-3">
                  <input
                    type="radio"
                    name={`correct-${qIndex}`}
                    checked={q.correct === opt && opt !== ""}
                    onChange={() => updateQuestion(qIndex, { correct: opt })}
                    className="h-5 w-5 cursor-pointer accent-cyan-500"
                    title={tt("contentTest.correctAnswer", "To'g'ri javobni belgilash")}
                  />
                  <input
                    type="text"
                    value={opt}
                    onChange={(e) => updateOption(qIndex, oIndex, e.target.value)}
                    className={`flex-1 rounded-xl border px-4 py-2.5 text-sm font-semibold outline-none transition-all ${
                      q.correct === opt && opt !== ""
                        ? "border-green-400 bg-green-50 text-green-900 dark:border-green-500/50 dark:bg-green-500/10 dark:text-green-100"
                        : "border-line bg-surface-soft text-navy-900 focus:ring-2 focus:ring-cyan-500 dark:border-white/10 dark:bg-navy-950 dark:text-white"
                    }`}
                    placeholder={`${tt("contentTest.option", "Variant")} ${oIndex + 1}`}
                  />
                  {q.options.length > 2 && (
                    <button
                      type="button"
                      onClick={() => removeOption(qIndex, oIndex)}
                      className="text-red-400 hover:text-red-600 dark:hover:text-red-300 p-2"
                      title={tt("contentTest.deleteOption", "Variantni o'chirish")}
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={() => addOption(qIndex)}
                className="mt-2 inline-flex items-center gap-2 rounded-xl border border-line bg-surface-soft px-4 py-2 text-sm font-bold text-navy-900 hover:bg-line dark:border-white/10 dark:bg-white/5 dark:text-white dark:hover:bg-white/10 transition-colors"
              >
                + {tt("contentTest.addOption", "Variant qo'shish")}
              </button>
            </div>

            <div>
              <label className="mb-1 block text-sm font-bold text-ink-600 dark:text-navy-200">
                {tt("contentTest.explanation", "Izoh")} ({tt("common.optional", "ixtiyoriy")})
              </label>
              <input
                type="text"
                value={q.explanation}
                onChange={(e) => updateQuestion(qIndex, { explanation: e.target.value })}
                className="w-full rounded-xl border border-line bg-surface-soft px-4 py-2.5 text-sm font-semibold text-navy-900 outline-none focus:ring-2 focus:ring-cyan-500 dark:border-white/10 dark:bg-navy-950 dark:text-white transition-all"
                placeholder={tt("contentTest.explanationPlaceholder", "To'g'ri javob uchun qisqacha izoh")}
              />
            </div>
          </div>
        </article>
      ))}

      {questions.length === 0 && (
        <div className="rounded-2xl border border-dashed border-line bg-surface-soft/50 p-8 text-center dark:border-white/10 dark:bg-white/[0.02]">
          <p className="font-bold text-ink-500 dark:text-navy-300">
            {tt("contentTest.empty", "Hozircha savollar yo'q. Yangi savol qo'shing.")}
          </p>
        </div>
      )}
    </div>
  );
}

export function validateTestQuestions(questions: TestQuestion[]): string | null {
  if (questions.length === 0) return "Kamida bitta savol qo'shilishi shart.";
  for (let i = 0; i < questions.length; i++) {
    const q = questions[i];
    if (!q.question.trim()) return `${i + 1}-savol matni bo'sh bo'lishi mumkin emas.`;
    if (q.options.length < 2) return `${i + 1}-savolda kamida 2 ta variant bo'lishi kerak.`;
    if (q.options.some((opt) => !opt.trim())) return `${i + 1}-savol variantlari orasida bo'sh qator bor.`;
    if (!q.correct || !q.correct.trim() || !q.options.includes(q.correct)) {
      return `${i + 1}-savol uchun to'g'ri javob belgilanmagan yoki yaroqsiz.`;
    }
    const seconds = Number(q.time_limit_sec || 30);
    if (!Number.isFinite(seconds) || seconds < 10 || seconds > 300) {
      return `${i + 1}-savol vaqti 10 va 300 sekund oralig'ida bo'lishi kerak.`;
    }
    const uniqueOptions = new Set(q.options.map((o) => o.trim()));
    if (uniqueOptions.size !== q.options.length) {
      return `${i + 1}-savol variantlari orasida bir xillari bor.`;
    }
  }
  return null;
}
