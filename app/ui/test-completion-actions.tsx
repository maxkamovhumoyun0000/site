"use client";

import { useMemo, useState } from "react";

export type TestReviewItem = {
  prompt: string;
  selected_answer?: unknown;
  correct_answer?: unknown;
  options?: unknown[];
  is_correct?: boolean;
  explanation?: string;
  question_type?: string;
  passage?: string;
};

type TestContext = {
  title: string;
  subject?: string;
  questions: TestReviewItem[];
};

const CONTEXT_KEY = "diamondvoy:test-review-context:v1";

function display(value: unknown, fallback = "O‘tkazilgan") {
  if (value === null || value === undefined || value === "") return fallback;
  if (Array.isArray(value)) return value.map((item) => display(item, "")).filter(Boolean).join(" · ") || fallback;
  if (typeof value === "object") return Object.entries(value as Record<string, unknown>).map(([key, item]) => `${key}: ${display(item, "")}`).join(" · ") || fallback;
  return String(value);
}

/** A single completion action set shared by every student test result screen. */
export function TestCompletionActions({
  testTitle,
  subject,
  review,
  className = "",
}: {
  testTitle: string;
  subject?: string;
  review: TestReviewItem[];
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const items = useMemo(
    () => (Array.isArray(review) ? review.filter((item) => String(item?.prompt || "").trim()) : []),
    [review],
  );

  const openDiamondvoy = () => {
    if (!items.length || typeof window === "undefined") return;
    const context: TestContext = {
      title: testTitle,
      subject: String(subject || ""),
      // Keep browser storage bounded while retaining every normal test (20–30 questions).
      questions: items.slice(0, 40).map((item) => ({
        prompt: String(item.prompt || "").slice(0, 5000),
        selected_answer: item.selected_answer,
        correct_answer: item.correct_answer,
        options: Array.isArray(item.options) ? item.options.slice(0, 12) : [],
        is_correct: Boolean(item.is_correct),
        explanation: String(item.explanation || "").slice(0, 2000),
        question_type: String(item.question_type || ""),
        passage: String(item.passage || "").slice(0, 5000),
      })),
    };
    window.sessionStorage.setItem(CONTEXT_KEY, JSON.stringify(context));
    window.location.assign("/?role=student&section=chats&pane=diamondvoy");
  };

  if (!items.length) return null;
  return <>
    <div className={`flex flex-col items-center justify-center gap-2 sm:flex-row ${className}`}>
      <button type="button" onClick={() => setOpen(true)} className="rounded-2xl border border-indigo-200 bg-indigo-50 px-5 py-3 text-sm font-black text-indigo-700 transition hover:-translate-y-0.5 hover:bg-indigo-100 dark:border-indigo-400/30 dark:bg-indigo-500/15 dark:text-indigo-200 dark:hover:bg-indigo-500/25">
        📋 Javoblarimni ko‘rish
      </button>
      <button type="button" onClick={openDiamondvoy} className="rounded-2xl bg-cyan-500 px-5 py-3 text-sm font-black text-white shadow-lg shadow-cyan-500/20 transition hover:-translate-y-0.5 hover:bg-cyan-600 dark:text-navy-950">
        💎 Diamondvoy bilan tahlil qilish
      </button>
    </div>

    {open ? <div className="fixed inset-0 z-[100] flex items-end justify-center p-0 sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label="Test javoblari">
      <button type="button" aria-label="Yopish" className="absolute inset-0 bg-black/55 backdrop-blur-sm" onClick={() => setOpen(false)} />
      <section className="relative flex max-h-[90dvh] w-full max-w-2xl flex-col overflow-hidden rounded-t-[2rem] border border-line bg-white shadow-2xl dark:border-white/10 dark:bg-navy-950 sm:rounded-[2rem]">
        <header className="flex items-start justify-between gap-4 border-b border-line px-5 py-4 dark:border-white/10">
          <div><h2 className="text-lg font-black text-navy-900 dark:text-white">Javoblarim</h2><p className="mt-0.5 text-xs font-semibold text-ink-500 dark:text-navy-300">{testTitle} · {items.length} ta savol</p></div>
          <button type="button" onClick={() => setOpen(false)} className="grid h-9 w-9 place-items-center rounded-xl bg-surface-soft text-lg font-black text-ink-600 transition hover:bg-line dark:bg-white/10 dark:text-white">×</button>
        </header>
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {items.map((item, index) => {
            const skipped = item.selected_answer === null || item.selected_answer === undefined || item.selected_answer === "";
            const correct = Boolean(item.is_correct);
            return <article key={`${index}-${item.prompt}`} className={`rounded-2xl border p-4 text-left ${skipped ? "border-line bg-surface-soft/70 dark:border-white/10 dark:bg-white/[.03]" : correct ? "border-emerald-200 bg-emerald-50/70 dark:border-emerald-400/30 dark:bg-emerald-500/[.07]" : "border-rose-200 bg-rose-50/70 dark:border-rose-400/30 dark:bg-rose-500/[.07]"}`}>
              <p className="text-[11px] font-black uppercase tracking-wide text-ink-500 dark:text-navy-300">Savol {index + 1} · {skipped ? "O‘tkazilgan" : correct ? "To‘g‘ri" : "Noto‘g‘ri"}</p>
              {item.passage ? <p className="mt-2 whitespace-pre-line rounded-xl bg-white/60 p-3 text-xs leading-5 text-ink-600 dark:bg-black/10 dark:text-navy-200">{display(item.passage, "")}</p> : null}
              <p className="mt-2 whitespace-pre-line text-sm font-bold leading-6 text-navy-900 dark:text-white">{display(item.prompt, "")}</p>
              <dl className="mt-3 grid gap-2 text-sm"><div className="rounded-xl bg-white/75 px-3 py-2 dark:bg-black/10"><dt className="text-[10px] font-black uppercase tracking-wide text-ink-500 dark:text-navy-300">Sizning javobingiz</dt><dd className="mt-0.5 font-bold text-navy-900 dark:text-white">{display(item.selected_answer)}</dd></div><div className="rounded-xl bg-emerald-500/10 px-3 py-2"><dt className="text-[10px] font-black uppercase tracking-wide text-emerald-700 dark:text-emerald-300">To‘g‘ri javob</dt><dd className="mt-0.5 font-bold text-emerald-900 dark:text-emerald-100">{display(item.correct_answer, "—")}</dd></div></dl>
              {item.explanation ? <p className="mt-3 text-xs leading-5 text-ink-600 dark:text-navy-200">{display(item.explanation, "")}</p> : null}
            </article>;
          })}
        </div>
        <footer className="border-t border-line p-3 dark:border-white/10"><button type="button" onClick={openDiamondvoy} className="w-full rounded-xl bg-cyan-500 px-4 py-3 text-sm font-black text-white dark:text-navy-950">💎 Shu testni Diamondvoy bilan tahlil qilish</button></footer>
      </section>
    </div> : null}
  </>;
}

export const diamondvoyTestContextKey = CONTEXT_KEY;
