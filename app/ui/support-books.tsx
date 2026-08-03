"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
const LIBRARY_LOAD_ERROR = "Kutubxona yuklanmadi. Qayta urinib ko‘ring.";

type BookItem = {
  id: number;
  title: string;
  description?: string;
  subject?: string;
  author?: string;
  category?: string;
  level?: string;
  cover_url?: string;
};

function BookCoverImage({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-surface-soft dark:bg-navy-900">
        <span className="text-xs font-black uppercase tracking-wider text-ink-400 dark:text-navy-400">Kitob</span>
      </div>
    );
  }
  return <img src={src} alt={alt} loading="lazy" decoding="async" onError={() => setFailed(true)} className="w-full h-full object-contain bg-white dark:bg-navy-950" />;
}

export function SupportBooks({ apiFetch }: { apiFetch: (path: string, options?: any) => Promise<any> }) {
  const router = useRouter();
  const [items, setItems] = useState<BookItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [subjectFilter, setSubjectFilter] = useState("all");
  const apiFetchRef = useRef(apiFetch);
  const booksRequestSeqRef = useRef(0);

  useEffect(() => {
    apiFetchRef.current = apiFetch;
  }, [apiFetch]);

  const load = useCallback(async () => {
    const requestSeq = booksRequestSeqRef.current + 1;
    booksRequestSeqRef.current = requestSeq;
    setLoading(true);
    setError("");
    try {
      const res = await apiFetchRef.current("/support/books");
      if (booksRequestSeqRef.current !== requestSeq) return;
      setItems(Array.isArray(res?.items) ? res.items : []);
    } catch (e) {
      if (booksRequestSeqRef.current !== requestSeq) return;
      setError(LIBRARY_LOAD_ERROR);
    } finally {
      if (booksRequestSeqRef.current === requestSeq) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    const timer = window.setTimeout(() => {
      if (!mounted) return;
      load().catch(() => null);
    }, 0);
    return () => {
      mounted = false;
      booksRequestSeqRef.current += 1;
      window.clearTimeout(timer);
    };
  }, [load]);

  function mediaUrl(url?: string) {
    const raw = String(url || "").trim();
    if (!raw) return "";
    return raw.startsWith("/") ? `${API_BASE}${raw}` : raw;
  }

  function openBookDetail(book: BookItem) {
    const bookId = Number(book?.id || (book as any)?.book_id || 0);
    if (!Number.isInteger(bookId) || bookId <= 0) {
      setError("Kitob identifikatori topilmadi.");
      return;
    }
    router.push(`/support/books/${bookId}`);
  }

  if (loading) return <div className="py-10 text-center text-ink-500">Loading...</div>;
  const subjectOptions = Array.from(new Set(items.map((item) => String(item.subject || "").trim()).filter(Boolean)));
  const filtered = items.filter((item) => subjectFilter === "all" || String(item.subject || "").trim() === subjectFilter);

  return (
    <div className="space-y-4">
      {error ? (
        <div className="rounded-xl bg-red-50 text-red-700 border border-red-200 px-4 py-2 text-sm flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <span>{error}</span>
          <button type="button" onClick={load} className="rounded-lg border border-red-200 px-3 py-2 text-xs font-bold hover:bg-red-100">
            Qayta urinish
          </button>
        </div>
      ) : null}
      <div className="rounded-2xl border border-line bg-white p-3 dark:border-white/10 dark:bg-white/5">
        <select
          value={subjectFilter}
          onChange={(event) => setSubjectFilter(event.target.value)}
          className="w-full max-w-xs rounded-xl border border-line bg-white px-4 py-2.5 text-sm font-semibold text-navy-900 outline-none focus:ring-2 focus:ring-cyan-500/30 dark:border-white/10 dark:bg-navy-900 dark:text-white"
        >
          <option value="all">Barcha fanlar</option>
          {subjectOptions.map((subject) => (
            <option key={`support-book-subject-${subject}`} value={subject}>{subject}</option>
          ))}
        </select>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:gap-4">
        {filtered.map((b) => (
          <button
            key={b.id}
            type="button"
            onClick={() => openBookDetail(b)}
            className="media-library-card text-left rounded-2xl border border-line dark:border-white/10 bg-white dark:bg-navy-900/40 overflow-hidden"
          >
            <div className="aspect-[3/4] bg-surface-soft dark:bg-navy-900 overflow-hidden">
              <BookCoverImage src={mediaUrl(b.cover_url)} alt={b.title} />
            </div>
            <div className="p-3">
              <h3 className="text-sm sm:text-base font-bold text-navy-900 dark:text-white line-clamp-2">{b.title}</h3>
              <p className="text-xs text-ink-600 dark:text-navy-300 mt-1 line-clamp-2">{b.description || "-"}</p>
              <div className="mt-2 text-[11px] text-ink-500 dark:text-navy-300">
                {[b.subject, b.author, b.level, b.category].map((item) => String(item || "").trim()).filter(Boolean).join(" · ") || "-"}
              </div>
            </div>
          </button>
        ))}
        {!filtered.length ? <div className="col-span-2 rounded-2xl border border-dashed border-line p-8 text-center text-sm font-semibold text-ink-500 dark:border-white/10 dark:text-navy-300">Kitoblar topilmadi</div> : null}
      </div>
    </div>
  );
}
