"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { StudentBookTest } from "@/app/ui/student-book-test";

type ContentRouteType = "book" | "video" | "homework";

// Yangi (AI/avtomatik) test turlari — bular topilsa taymersiz AI runner'ga
// yo'naltiramiz (eski MCQ runner ularni bo'sh/blank ko'rsatardi).
const AI_TEST_KINDS = new Set([
  "speak_sentence", "write_sentence", "guided_writing", "translation",
  "reading_open", "read_aloud", "paraphrase", "dialogue_completion",
  "picture_description", "listening", "dictation", "spelling",
  "matching", "scrambled_sentence", "gap_fill", "word_practice", "passage_cloze", "reading_set",
]);

function normalizeContentType(value?: string): ContentRouteType | "" {
  const raw = String(value || "").trim().toLowerCase();
  if (raw === "book" || raw === "books") return "book";
  if (raw === "video" || raw === "videos") return "video";
  if (raw === "homework" || raw === "homeworks") return "homework";
  return "";
}

function fallbackTitle(contentType: ContentRouteType, contentId: number) {
  if (contentType === "video") return `Video Test #${contentId}`;
  if (contentType === "homework") return `Homework Test #${contentId}`;
  return `Kitob Test #${contentId}`;
}

export default function StudentContentTestPage() {
  const router = useRouter();
  const params = useParams<{ contentType?: string; contentId?: string }>();
  const contentType = normalizeContentType(params?.contentType);
  const contentId = useMemo(() => {
    const raw = String(params?.contentId || "").trim();
    return /^\d+$/.test(raw) ? Number(raw) : 0;
  }, [params?.contentId]);
  const [test, setTest] = useState<any | null>(null);
  const [result, setResult] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!contentType || !contentId) {
      setError("Test manzili noto'g'ri.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const payload = await apiFetch(`/student/content-tests/${contentType}/${contentId}`, {
        timeoutMs: 12000,
        retries: 0,
      });
      const loadedTest = payload?.test || null;
      // Homework testi yangi turlardan iborat bo'lsa — taymersiz AI runner'ga.
      const qs = (loadedTest?.questions || []) as Array<{ kind?: string }>;
      if (contentType === "homework" && qs.some((q) => AI_TEST_KINDS.has(String(q?.kind || "")))) {
        router.replace(`/student/ai-tests/homework/${contentId}`);
        return;
      }
      setTest(loadedTest);
      setResult(payload?.result || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Testni ochib bo'lmadi.");
    } finally {
      setLoading(false);
    }
  }, [contentType, contentId, router]);

  useEffect(() => {
    load().catch(() => null);
  }, [load]);

  if (loading) {
    return (
      <main className="min-h-[100dvh] bg-slate-50 p-4 text-slate-900 dark:bg-slate-950 dark:text-white">
        <div className="mx-auto grid min-h-[80dvh] max-w-xl place-items-center">
          <div className="rounded-3xl border border-slate-200 bg-white px-6 py-5 text-sm font-black shadow-premium backdrop-blur dark:border-white/10 dark:bg-white/10">
            Test yuklanmoqda...
          </div>
        </div>
      </main>
    );
  }

  if (error || !contentType || !contentId || !test) {
    return (
      <main className="min-h-[100dvh] bg-slate-50 p-4 text-slate-900 dark:bg-slate-950 dark:text-white">
        <div className="mx-auto flex min-h-[80dvh] max-w-xl flex-col items-center justify-center gap-4 text-center">
          <div className="rounded-3xl border border-red-200 bg-red-50 px-5 py-4 text-sm font-bold text-red-700 dark:border-red-400/20 dark:bg-red-500/10 dark:text-red-100">
            {error || "Test hali qo'shilmagan."}
          </div>
          <button className="rounded-2xl bg-cyan-500 px-5 py-3 text-sm font-black text-white" onClick={() => router.back()}>
            Ortga qaytish
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-[100dvh] bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-white">
      <StudentBookTest
        bookTitle={String(test.title || fallbackTitle(contentType, contentId))}
        contentType={contentType}
        contentId={contentId}
        questions={test.questions || []}
        initialResult={result}
        autoSubmitWhenAllAnswered
        onSubmit={async (answers, proctoringSessionId) => {
          const payload = await apiFetch(`/student/content-tests/${contentType}/${contentId}/submit`, {
            method: "POST",
            body: { answers, proctoring_session_id: proctoringSessionId },
            timeoutMs: 15000,
            retries: 0,
          });
          return payload?.result || payload;
        }}
        onExit={() => router.back()}
      />
    </main>
  );
}
