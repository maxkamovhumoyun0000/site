"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { MobilePdfViewer } from "@/app/ui/mobile-pdf-viewer";
import { EpubViewer, isEpubUrl } from "@/app/ui/epub-viewer";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

function resolveMediaUrl(url?: string | null) {
  const raw = String(url || "").trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith("/")) return `${API_BASE}${raw}`;
  return `${API_BASE}/${raw}`;
}

type BookItem = {
  id: number;
  title: string;
  description?: string;
  author?: string;
  category?: string;
  level?: string;
  cover_url?: string;
  pdf_url?: string;
  question_count?: number;
  price?: number;
};

export function RoleBookDetailPage({ role, bookId }: { role: "admin" | "teacher" | "support"; bookId: string }) {
  const router = useRouter();
  const params = useParams<{ bookId?: string }>();
  const [book, setBook] = useState<BookItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const resolvedBookIdRaw = String(bookId || params?.bookId || "").trim();
  const safeBookId = useMemo(() => {
    const raw = resolvedBookIdRaw;
    return /^\d+$/.test(raw) ? raw : "";
  }, [resolvedBookIdRaw]);
  const resolvedPdfUrl = useMemo(() => (safeBookId ? `${API_BASE}/${role}/books/${safeBookId}/pdf` : resolveMediaUrl(book?.pdf_url)), [book?.pdf_url, role, safeBookId]);

  function normalizeError(error: unknown) {
    const text = String(error instanceof Error ? error.message : "").trim();
    const lowered = text.toLowerCase();
    if (!text) return "Kitobni yuklab bo'lmadi.";
    if (lowered.includes("404") || lowered.includes("not found")) return "Kitob topilmadi.";
    if (lowered.includes("timeout")) return "So'rov vaqti tugadi. Qayta urinib ko'ring.";
    if (lowered.includes("403")) return "Sizda bu kitobni ko'rish huquqi yo'q.";
    if (lowered.includes("422")) return "Kitob ochilmadi. Fayl yoki ID noto'g'ri.";
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
      const res = await apiFetch(`/${role}/books/${safeBookId}`);
      if (res?.item) setBook(res.item);
      else setError("Kitob topilmadi.");
    } catch (e) {
      setError(normalizeError(e));
    }
    setLoading(false);
  }, [role, safeBookId]);

  useEffect(() => {
    fetchBook().catch(() => null);
  }, [fetchBook]);

  return (
    !loading && book && resolvedPdfUrl ? (
      <main className="fixed inset-0 z-[90] bg-slate-950">
        {isEpubUrl(resolvedPdfUrl) ? (
          <EpubViewer
            epubUrl={resolvedPdfUrl}
            title={book.title || "Kitob"}
            authToken={localStorage.getItem("diamond_token") || ""}
            className="h-[100dvh] min-h-[100dvh]"
            onBack={() => router.back()}
          />
        ) : (
          <MobilePdfViewer
            pdfUrl={resolvedPdfUrl}
            title={book.title || "Kitob"}
            authToken={localStorage.getItem("diamond_token") || ""}
            hideHeader
            className="h-[100dvh] min-h-[100dvh]"
            onBack={() => router.back()}
          />
        )}
      </main>
    ) : (
    <main className="flex min-h-screen flex-col bg-background relative">
      <div className="flex-1 overflow-y-auto w-full p-4 sm:p-6 lg:p-8">
        <div className="max-w-6xl mx-auto space-y-6 relative flex flex-col min-h-[calc(100dvh-120px)]">
          {error ? (
            <div className="bg-red-50 text-red-700 px-6 py-4 rounded-2xl border border-red-200 dark:bg-red-500/10 dark:border-red-500/20 text-sm font-bold">{error}</div>
          ) : null}

          {loading ? (
            <div className="bg-white dark:bg-navy-900/50 rounded-[2rem] p-16 border border-line dark:border-white/10 text-center flex flex-col items-center justify-center flex-1">
              <div className="w-12 h-12 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin mb-6" />
              <p className="text-ink-600 dark:text-navy-300 font-bold tracking-wide">Kitob yuklanmoqda...</p>
            </div>
          ) : book ? (
            <div className="bg-white dark:bg-navy-900/50 rounded-[2rem] border border-line dark:border-white/10 overflow-hidden flex flex-col flex-1">
              <div className="flex flex-col md:flex-row md:items-center justify-between p-6 border-b border-line dark:border-white/10 bg-surface-soft dark:bg-navy-900/50 gap-4">
                <div className="min-w-0 pr-4">
                  <h1 className="text-xl sm:text-2xl font-display font-black text-navy-900 dark:text-white truncate tracking-tight">{book.title}</h1>
                  <p className="text-sm font-bold text-ink-600 dark:text-navy-300 mt-1 uppercase tracking-wider">{book.author || "Diamond Education"} <span className="mx-2 opacity-50">|</span> <span className="text-cyan-700 dark:text-cyan-300">{book.level || "B1"}</span></p>
                </div>
                <div className="text-xs font-bold uppercase tracking-wider px-3 py-2 rounded-xl bg-cyan-100 text-cyan-900 dark:bg-cyan-500/20 dark:text-cyan-200 border border-cyan-200 dark:border-cyan-500/30">{role}</div>
              </div>

              <div className="p-4 sm:p-6 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div className="rounded-xl border border-line dark:border-white/10 p-4 bg-surface-soft dark:bg-white/5">
                  <p className="text-xs uppercase font-bold text-ink-500 dark:text-navy-300">Toifa</p>
                  <p className="font-semibold text-navy-900 dark:text-white mt-1">{book.category || "-"}</p>
                </div>
                <div className="rounded-xl border border-line dark:border-white/10 p-4 bg-surface-soft dark:bg-white/5">
                  <p className="text-xs uppercase font-bold text-ink-500 dark:text-navy-300">Savollar</p>
                  <p className="font-semibold text-navy-900 dark:text-white mt-1">{Number(book.question_count || 0)}</p>
                </div>
              </div>

              <div className="flex-1 bg-surface-soft dark:bg-navy-900 p-4 sm:p-6 h-full flex flex-col relative overflow-hidden">
                {resolvedPdfUrl ? (
                  <div className="w-full flex-1 h-full rounded-2xl border border-line dark:border-white/10 overflow-hidden">
                    {isEpubUrl(resolvedPdfUrl) ? (
                      <EpubViewer
                        epubUrl={resolvedPdfUrl}
                        title={book.title || "Kitob"}
                        authToken={localStorage.getItem("diamond_token") || ""}
                        onBack={() => router.back()}
                        className="h-full"
                      />
                    ) : (
                      <MobilePdfViewer
                        pdfUrl={resolvedPdfUrl}
                        title={book.title || "Kitob"}
                        authToken={localStorage.getItem("diamond_token") || ""}
                        hideHeader
                        onBack={() => router.back()}
                      />
                    )}
                  </div>
                ) : (
                  <div className="rounded-[1.25rem] border border-gold-200 bg-gold-50 text-gold-800 px-6 py-8 text-center font-bold flex-1 flex items-center justify-center">
                    {resolvedPdfUrl ? "PDF faylini ochib bo'lmadi. Iltimos keyinroq qayta urinib ko'ring." : "Ushbu kitob uchun PDF URL biriktirilmagan."}
                  </div>
                )}
              </div>

              {book.description ? (
                <div className="px-6 pb-6">
                  <div className="rounded-xl border border-line dark:border-white/10 p-4 bg-surface-soft dark:bg-white/5">
                    <h3 className="text-sm font-bold text-navy-900 dark:text-white uppercase tracking-wider mb-2">Tavsif</h3>
                    <p className="text-sm text-ink-700 dark:text-navy-200 whitespace-pre-line leading-relaxed">{book.description}</p>
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </main>
    )
  );
}
