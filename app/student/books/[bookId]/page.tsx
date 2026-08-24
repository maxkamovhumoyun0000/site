"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { MobilePdfViewer } from "@/app/ui/mobile-pdf-viewer";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

function resolveMediaUrl(url?: string | null) {
  const raw = String(url || "").trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith("/")) return `${API_BASE}${raw}`;
  return `${API_BASE}/${raw}`;
}

type PurchaseInfo = {
  id: number;
  deadline_at?: string | null;
  status?: string;
  deadline_expired?: boolean;
  seconds_until_deadline?: number | null;
  can_take_test?: boolean;
  test_submitted?: boolean;
};

type BookItem = {
  id: number;
  title: string;
  description?: string;
  author?: string;
  category?: string;
  level?: string;
  cover_url?: string;
  pdf_url?: string;
  price?: number;
  deadline_days?: number;
  question_count?: number;
  purchase?: PurchaseInfo | null;
};

export default function StudentBookPage({ params }: { params: { bookId: string } }) {
  const router = useRouter();
  const routeParams = useParams<{ bookId?: string }>();
  const [book, setBook] = useState<BookItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // Test states
  const [testData, setTestData] = useState<any>(null);
  const [testResult, setTestResult] = useState<any>(null);
  const [testError, setTestError] = useState("");
  const resolvedBookIdRaw = String(params?.bookId || routeParams?.bookId || "").trim();
  const safeBookId = useMemo(() => {
    const raw = resolvedBookIdRaw;
    return /^\d+$/.test(raw) ? raw : "";
  }, [resolvedBookIdRaw]);
  const resolvedPdfUrl = useMemo(() => (safeBookId ? `${API_BASE}/student/books/${safeBookId}/pdf` : resolveMediaUrl(book?.pdf_url)), [book?.pdf_url, safeBookId]);

  function normalizeError(error: unknown) {
    const text = String(error instanceof Error ? error.message : "").trim();
    const lowered = text.toLowerCase();
    if (!text) return "Kitobni yuklab bo'lmadi.";
    if (lowered.includes("404") || lowered.includes("not found")) return "Kitob topilmadi yoki uni xarid qilmagansiz.";
    if (lowered.includes("422")) return "Kitob ochilmadi. Fayl yoki ID noto'g'ri.";
    if (lowered.includes("timeout")) return "So'rov vaqti tugadi. Qayta urinib ko'ring.";
    return text;
  }

  const fetchBook = useCallback(async () => {
    if (!safeBookId) {
      setBook(null);
      setError("Kitob identifikatori noto'g'ri.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch(`/student/books/${safeBookId}`);
      if (res?.item) setBook(res.item);
      else setError("Kitob topilmadi yoki uni xarid qilmagansiz.");
    } catch (e) {
      setError(normalizeError(e));
    }
    setLoading(false);
  }, [safeBookId]);

  const fetchTest = useCallback(async () => {
    if (!safeBookId) return;
    try {
      const res = await apiFetch(`/student/book/${safeBookId}/test`);
      if (res?.test) {
        setTestData(res.test);
        setTestResult(res.result || null);
        setTestError("");
      } else {
        setTestData(null);
      }
    } catch (e: any) {
      const message = String(e?.message || "");
      const lowered = message.toLowerCase();
      if (lowered.includes("not found") || lowered.includes("404") || lowered.includes("topilmadi") || lowered.includes("ma'lumot")) {
        setTestError("Test hali qo'shilmagan");
      } else {
        setTestError(message || "");
      }
      setTestData(null);
    }
  }, [safeBookId]);

  useEffect(() => {
    fetchBook().catch(() => null);
  }, [fetchBook]);

  useEffect(() => {
    if (book) {
      fetchTest().catch(() => null);
    }
  }, [book?.id, fetchTest]);

  function deriveBookFlags(bookItem: BookItem) {
    const purchase = bookItem.purchase || null;
    const status = String(purchase?.status || "").toLowerCase();
    const testSubmitted = Boolean(purchase?.test_submitted) || status === "test_passed" || status === "test_failed";
    // Deadline tizimi olib tashlandi: xariddan keyin test istalgan vaqtda ochiq.
    const purchased = Boolean(purchase) || Number(bookItem.price || 0) <= 0;
    if (!purchased) {
      return {
        purchased: false,
        expired: false,
        canTakeTest: false,
        testSubmitted: false,
        seconds: null as number | null,
      };
    }
    const canTakeTest = typeof purchase?.can_take_test === "boolean" ? purchase.can_take_test : !testSubmitted;
    return { purchased: true, expired: false, canTakeTest, testSubmitted, seconds: null as number | null };
  }

  const flags = book ? deriveBookFlags(book) : null;

  if (!loading && book && flags && resolvedPdfUrl) {
    return (
      <main className="fixed inset-0 z-[90] bg-slate-950">
        <div className="fixed right-3 top-3 z-[105] flex items-center gap-2">
              {testResult ? (
                <span className="rounded-xl border border-green-400/30 bg-green-500/20 px-3 py-2 text-xs font-black text-green-100 backdrop-blur">
                  Natija: {Number(testResult.correct_count ?? testResult.correct ?? testResult.score ?? 0)} / {Number(testResult.total_questions ?? testResult.total ?? (testData?.questions || []).length ?? 0)}
                </span>
              ) : testData ? (
                <button
                  type="button"
                  onClick={() => router.push(`/student/content-tests/book/${safeBookId}`)}
                  className="rounded-xl bg-cyan-500 px-4 py-2 text-xs font-black text-white shadow-premium hover:bg-cyan-600"
                >
              Testni ishlash
            </button>
          ) : null}
        </div>
        <MobilePdfViewer
          pdfUrl={resolvedPdfUrl}
          title={book.title || "Kitob"}
          authToken={localStorage.getItem("diamond_token") || ""}
          hideHeader
          className="h-[100dvh] min-h-[100dvh]"
          onBack={() => router.back()}
        />
      </main>
    );
  }

  return (
    <main className="flex min-h-screen flex-col bg-background relative selection:bg-cyan-500/30 selection:text-cyan-900 dark:selection:text-cyan-100">
      <div className="flex-1 overflow-y-auto w-full p-0">
        <div className="w-full relative flex flex-col min-h-[100dvh]">

          {error && (
            <div className="mx-4 mt-4 bg-red-50 text-red-500 px-6 py-4 rounded-2xl shadow-sm border border-red-100 dark:bg-red-500/10 dark:border-red-500/20 text-sm font-bold flex items-center gap-4 flex-shrink-0">
              <svg className="w-6 h-6 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              <span>{error}</span>
            </div>
          )}

          {notice && (
            <div className="mx-4 mt-4 bg-green-50 text-green-600 px-6 py-3 rounded-2xl shadow-sm border border-green-100 dark:bg-green-500/10 dark:border-green-500/20 text-sm font-bold flex items-center gap-3 flex-shrink-0">
              <span>{notice}</span>
              <button className="text-green-700 dark:text-green-400 hover:underline" onClick={() => setNotice("")}>✕</button>
            </div>
          )}

          {loading ? (
            <div className="m-4 bg-white dark:bg-navy-900/50 rounded-[2rem] p-16 shadow-premium border border-line dark:border-white/10 text-center flex flex-col items-center justify-center flex-1">
               <div className="w-12 h-12 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin mb-6" />
               <p className="text-ink-500 font-bold tracking-wide">Kitob yuklanmoqda...</p>
            </div>
          ) : book && flags ? (
            <div className="bg-white dark:bg-navy-900/50 shadow-premium border-y sm:border sm:border-line dark:sm:border-white/10 sm:rounded-[1.25rem] overflow-hidden animate-fade-in-up flex flex-col flex-1 min-h-[100dvh]">
              <div className="flex items-center justify-end gap-3 px-3 sm:px-4 py-3 border-b border-line dark:border-white/10 bg-surface-soft/90 dark:bg-navy-900/80 backdrop-blur-md flex-shrink-0">
                <div className="flex items-center gap-2">
                  {testResult ? (
                    <span className="bg-green-50 text-green-600 dark:bg-green-500/10 dark:text-green-400 px-3 py-2 rounded-xl text-[11px] sm:text-xs font-bold uppercase tracking-wider border border-green-100 dark:border-green-500/20 text-center">Natija: {testResult.score}/{testResult.total}</span>
                  ) : testData ? (
                    <button
                      onClick={() => router.push(`/student/content-tests/book/${safeBookId}`)}
                      className="px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all bg-gold-500 hover:bg-gold-600 text-white shadow-[0_0_15px_rgba(234,179,8,0.4)]"
                    >
                      Testni ishlash
                    </button>
                  ) : null}
                </div>
              </div>

              <div className="flex-1 bg-surface-soft dark:bg-navy-900 h-full flex flex-col relative overflow-hidden">
                {resolvedPdfUrl ? (
                  <div className="w-full flex-1 h-full min-h-[calc(100dvh-62px)] relative">
                    <MobilePdfViewer
                      pdfUrl={resolvedPdfUrl}
                      title={book.title || "Kitob"}
                      authToken={localStorage.getItem("diamond_token") || ""}
                      hideHeader
                      onBack={() => router.back()}
                    />
                  </div>
                ) : (
                  <div className="rounded-[1.5rem] border border-gold-200 bg-gold-50 text-gold-700 px-6 py-8 text-center font-bold flex-1 flex items-center justify-center m-4">
                    {resolvedPdfUrl ? "PDF faylini ochib bo'lmadi. Iltimos keyinroq qayta urinib ko'ring." : "Ushbu kitob uchun PDF URL biriktirilmagan."}
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </main>
  );
}
