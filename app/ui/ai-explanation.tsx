"use client";

import { useState } from "react";

interface AiExplanationProps {
  question: string;
  options?: string[];
  selected?: string;
  correct?: string;
  subject?: string;
}

export function AiExplanation({ question, options, selected, correct, subject }: AiExplanationProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [explanation, setExplanation] = useState<string | null>(null);

  async function fetchExplanation() {
    if (explanation) { setOpen(o => !o); return; }
    setOpen(true);
    setLoading(true);
    try {
      const res = await fetch("/api/ai/explain-answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, options, selected, correct, subject }),
      });
      const data = await res.json();
      setExplanation(data.explanation || "Tushuntirish topilmadi.");
    } catch {
      setExplanation("Tushuntirish olishda xato yuz berdi.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-3">
      <button
        onClick={fetchExplanation}
        className="text-sm text-blue-600 dark:text-blue-400 underline underline-offset-2 hover:opacity-80 transition"
      >
        💡 Nima uchun?
      </button>
      {open && (
        <div className="mt-2 p-3 rounded-xl bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 text-sm text-gray-800 dark:text-gray-200">
          {loading ? (
            <span className="animate-pulse">AI tushuntiryapti...</span>
          ) : (
            <p>{explanation}</p>
          )}
        </div>
      )}
    </div>
  );
}
