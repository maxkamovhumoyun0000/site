"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ModalPortal } from "./modal-portal";
import { useWebT } from "./web-i18n";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
const LIBRARY_LOAD_ERROR = "Kutubxona yuklanmadi. Qayta urinib ko‘ring.";
const BOOK_LIST_CACHE_TTL_MS = 6_000;
const bookListCache = new Map<string, { payload: any; ts: number }>();

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
  purchase_count?: number;
  purchase?: PurchaseInfo | null;
};

function BookCoverImage({ src, alt, className = "" }: { src: string; alt: string; className?: string }) {
  const tt = useWebT();
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setFailed(false);
  }, [src]);
  if (!src || failed) {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-surface-soft to-line dark:from-navy-800 dark:to-navy-900">
        <span className="text-xs font-black uppercase tracking-wider text-ink-400 dark:text-navy-400">{tt("library.book", "Kitob")}</span>
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
      className={`w-full h-full object-contain bg-white dark:bg-navy-950 ${className}`}
    />
  );
}

export function StudentBooks({ apiFetch, user }: { apiFetch: (path: string, options?: any) => Promise<any>, user?: any }) {
  const tt = useWebT();
  const router = useRouter();
  const pageSize = 20;
  const [books, setBooks] = useState<BookItem[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [wallet, setWallet] = useState(0);
  const [buyingBookId, setBuyingBookId] = useState<number | null>(null);
  const [purchaseCandidate, setPurchaseCandidate] = useState<BookItem | null>(null);
  const [nowTs, setNowTs] = useState(() => Date.now());
  
  const subjects = useMemo<string[]>(() => {
    if (!user || !user.subjects || !Array.isArray(user.subjects)) return [];
    return Array.from(new Set<string>(user.subjects.map((s: any) => String(s || "").trim()).filter(Boolean)));
  }, [user]);
  
  const [selectedSubject, setSelectedSubject] = useState<string>("all");
  const [selectedLevel, setSelectedLevel] = useState<string>("all");
  const levels = ["Beginner", "A1", "A2", "B1", "B2", "C1", "C2"];

  const apiFetchRef = useRef(apiFetch);
  const booksRequestSeqRef = useRef(0);
  const booksAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    apiFetchRef.current = apiFetch;
  }, [apiFetch]);

  const fetchBooks = useCallback(async () => {
    const requestSeq = booksRequestSeqRef.current + 1;
    booksRequestSeqRef.current = requestSeq;
    booksAbortRef.current?.abort();
    const controller = new AbortController();
    booksAbortRef.current = controller;
    setError("");
    const offset = (Math.max(1, page) - 1) * pageSize;
    const subjQuery = selectedSubject && selectedSubject !== "all" ? `&subject=${encodeURIComponent(selectedSubject)}` : "";
    const lvlQuery = selectedLevel && selectedLevel !== "all" ? `&level=${encodeURIComponent(selectedLevel)}` : "";
    const cacheKey = `books:${pageSize}:${offset}:${selectedSubject}:${selectedLevel}`;
    const cached = bookListCache.get(cacheKey);
    if (cached && Date.now() - cached.ts < BOOK_LIST_CACHE_TTL_MS) {
      const res = cached.payload || {};
      setBooks(res.items || []);
      setHasMore(Boolean(res.has_more));
      if (typeof res?.dcoin_balance === "number") setWallet(res.dcoin_balance);
      setLoading(false);
    } else {
      setLoading(true);
    }
    try {
      const res = await apiFetchRef.current(`/student/books?limit=${pageSize}&offset=${offset}${subjQuery}${lvlQuery}`, {
        signal: controller.signal,
        timeoutMs: 9000,
        retries: 1,
      });
      if (booksRequestSeqRef.current !== requestSeq || controller.signal.aborted) return;
      bookListCache.set(cacheKey, { payload: res || {}, ts: Date.now() });
      if (res && res.items) {
        setBooks(res.items);
        setHasMore(Boolean(res.has_more));
      }
      if (typeof res?.dcoin_balance === "number") {
        setWallet(res.dcoin_balance);
      }
    } catch (e) {
      if (booksRequestSeqRef.current !== requestSeq || controller.signal.aborted) return;
      if (!cached) setError(tt("library.loadError", LIBRARY_LOAD_ERROR));
    } finally {
      if (booksRequestSeqRef.current === requestSeq && !controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, [page, selectedSubject, selectedLevel]);

  useEffect(() => {
    setPage(1);
  }, [selectedSubject, selectedLevel]);

  useEffect(() => {
    let mounted = true;
    const timer = window.setTimeout(() => {
      if (!mounted) return;
      fetchBooks().catch(() => null);
    }, 0);
    return () => {
      mounted = false;
      booksRequestSeqRef.current += 1;
      booksAbortRef.current?.abort();
      window.clearTimeout(timer);
    };
  }, [fetchBooks]);

  useEffect(() => {
    const timer = window.setInterval(() => setNowTs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  function mediaUrl(url?: string | null) {
    const raw = String(url || "").trim();
    if (!raw) return "";
    return raw.startsWith("/") ? `${API_BASE}${raw}` : raw;
  }

  function secondsLeft(deadlineAt?: string | null) {
    const raw = String(deadlineAt || "").trim();
    if (!raw) return null;
    const ts = Date.parse(raw);
    if (!Number.isFinite(ts)) return null;
    return Math.floor((ts - nowTs) / 1000);
  }

  function formatCountdown(seconds: number | null) {
    if (seconds === null) return tt("library.noDeadline", "No deadline");
    const sec = Math.max(0, seconds);
    const days = Math.floor(sec / 86400);
    const hours = Math.floor((sec % 86400) / 3600);
    const mins = Math.floor((sec % 3600) / 60);
    if (days > 0) return `${days} ${tt("library.day", "kun")} ${hours} ${tt("library.hour", "soat")}`;
    if (hours > 0) return `${hours} ${tt("library.hour", "soat")} ${mins} ${tt("library.minute", "daqiqa")}`;
    return `${mins} ${tt("library.minute", "daqiqa")}`;
  }

  function deriveBookFlags(book: BookItem) {
    const purchase = book.purchase || null;
    if (!purchase) {
      return {
        purchased: false,
        expired: false,
        canTakeTest: false,
        testSubmitted: false,
        seconds: null as number | null,
      };
    }
    const seconds = secondsLeft(purchase.deadline_at);
    const expired = seconds !== null ? seconds <= 0 : Boolean(purchase.deadline_expired);
    const status = String(purchase.status || "").toLowerCase();
    const testSubmitted = Boolean(purchase.test_submitted) || status === "test_passed" || status === "test_failed";
    const canTakeTest = expired && !testSubmitted;
    return { purchased: true, expired, canTakeTest, testSubmitted, seconds };
  }

  async function buyBook(book: BookItem) {
    if (buyingBookId) return;
    setBuyingBookId(book.id);
    setError("");
    setNotice("");
    try {
      const payload = await apiFetch(`/student/books/${book.id}/buy`, { method: "POST" });
      if (typeof payload?.dcoin_balance === "number") {
        setWallet(payload.dcoin_balance);
      }
      setNotice(String(payload?.message || tt("library.purchased", "Kitob xarid qilindi.")));
      await fetchBooks();
      setPurchaseCandidate(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : tt("library.purchaseFailed", "Xarid amalga oshmadi."));
    } finally {
      setBuyingBookId(null);
    }
  }

  async function startTest(book: BookItem) {
    router.push(`/student/content-tests/book/${book.id}`);
  }

  const purchasedCount = useMemo(
    () => books.filter((book) => Boolean(book.purchase)).length,
    [books],
  );

  function openBookReader(book: BookItem) {
    const bookId = Number(book?.id || (book as any)?.book_id || 0);
    if (!Number.isInteger(bookId) || bookId <= 0) {
      setError(tt("library.unavailable", "Kitob vaqtincha mavjud emas. Iltimos qayta urinib ko'ring."));
      return;
    }
    router.push(`/student/books/${bookId}`);
  }

  function openBookInfo(book: BookItem) {
    setPurchaseCandidate(book);
  }

  function handleBookCardKey(event: React.KeyboardEvent<HTMLElement>, book: BookItem) {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    openBookInfo(book);
  }

  return (
    <div className="flex flex-col gap-8 pb-12 animate-fade-in">
      <div className="media-filter-panel">
        <label className="media-filter-control">
          <span>{tt("common.subject", "Fan")}</span>
          <select
            value={selectedSubject}
            onChange={(e) => setSelectedSubject(e.target.value)}
            className="media-filter-select"
          >
            <option value="all">{tt("videos.all_subjects", "Barcha fanlar")}</option>
            {subjects.map((subj) => (
              <option key={subj} value={subj}>{subj}</option>
            ))}
          </select>
        </label>

        <label className="media-filter-control">
          <span>{tt("student.grammar.level", "Level")}</span>
          <select
            value={selectedLevel}
            onChange={(e) => setSelectedLevel(e.target.value)}
            className="media-filter-select"
          >
            <option value="all">{tt("videos.all_levels", "Barcha darajalar")}</option>
            {levels.map((lvl) => (
              <option key={lvl} value={lvl}>{lvl}</option>
            ))}
          </select>
        </label>
      </div>

      {notice ? <div className="rounded-xl bg-green-500/10 text-green-500 border border-green-500/20 px-4 py-3 font-semibold text-sm animate-fade-in">{notice}</div> : null}
      {error ? (
        <div className="rounded-xl bg-red-500/10 text-red-500 border border-red-500/20 px-4 py-3 font-semibold text-sm animate-fade-in flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <span>{error}</span>
          <button
            type="button"
            onClick={fetchBooks}
            className="rounded-lg border border-red-500/30 px-3 py-2 text-xs font-bold text-red-600 dark:text-red-300 hover:bg-red-500/10"
          >
            {tt("library.retry", "Qayta urinish")}
          </button>
        </div>
      ) : null}

      {loading ? (
        <div className="flex justify-center py-20"><div className="w-12 h-12 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin"></div></div>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
          {books.length === 0 ? (
             <div className="col-span-full text-center py-16 text-ink-500 bg-surface-soft border border-line dark:bg-white/5 dark:border-white/10 rounded-[2rem] font-medium text-lg">{tt("library.empty", "Hozircha kitoblar mavjud emas")}</div>
          ) : books.map((b) => {
            const flags = deriveBookFlags(b);
            return (
              <article
                key={b.id}
                className="group media-library-card library-book-card relative flex flex-col bg-white border border-line dark:bg-navy-900/40 dark:border-white/10 rounded-2xl shadow-premium overflow-hidden transition-all duration-300 hover:-translate-y-1"
                role="button"
                tabIndex={0}
                onClick={() => openBookInfo(b)}
                onKeyDown={(event) => handleBookCardKey(event, b)}
                title={b.title}
              >
                <div
                  className="relative aspect-[3/4] bg-surface-soft dark:bg-navy-900 overflow-hidden text-left"
                >
                  <BookCoverImage key={`student-book-cover-${b.id}-${b.cover_url || ""}`} src={mediaUrl(b.cover_url)} alt={b.title} className="transition-transform duration-700 group-hover:scale-105" />
                  <div className="absolute top-3 right-3 flex flex-col gap-2 items-end">
                    {flags.purchased ? (
                      <div className="bg-green-500/90 backdrop-blur-md text-white text-[10px] font-bold px-2.5 py-1 rounded-full uppercase tracking-wider shadow-lg">
                        {tt("library.alreadyPurchased", "Xarid qilingan")}
                      </div>
                    ) : null}

                  </div>
	                </div>
	                <div className="p-3 sm:p-4 flex-grow flex flex-col relative z-10 bg-white dark:bg-navy-900/80 backdrop-blur-sm -mt-4 rounded-t-2xl border-t border-line dark:border-white/10 transition-transform duration-300">
	                  <div className="flex items-center gap-2 mb-2">
	                    {b.level ? <span className="px-2 py-0.5 bg-cyan-50 text-cyan-700 dark:bg-cyan-500/10 dark:text-cyan-300 rounded-lg text-[10px] font-bold uppercase tracking-wider border border-cyan-100 dark:border-cyan-500/20">{b.level}</span> : null}
	                    {b.category ? <span className="library-card-meta text-[11px] font-bold text-ink-600 dark:text-navy-300">{b.category}</span> : null}
	                  </div>
                  <h3 className="library-card-title font-display font-bold text-sm sm:text-base text-navy-900 dark:text-white mb-1 group-hover:text-cyan-500 transition-colors">{b.title}</h3>
                  <p className="library-card-meta text-xs font-medium text-ink-600 dark:text-navy-300 mb-2">{b.author}</p>
                  <p className="library-card-description text-xs sm:text-sm text-ink-600 dark:text-navy-300 mb-3 flex-grow leading-relaxed">{b.description}</p>
                  
                  {flags.purchased ? (
                    <div className={`mb-3 text-[11px] font-bold rounded-xl px-3 py-2 border ${
                      flags.canTakeTest
                        ? "bg-gold-50 border-gold-200 text-gold-700 dark:bg-gold-500/10 dark:text-gold-400 dark:border-gold-500/30"
                        : "bg-surface-soft border-line text-ink-500 dark:bg-navy-800 dark:border-white/10 dark:text-navy-300"
                    }`}>
                      {flags.testSubmitted
                        ? tt("library.testSubmitted", "✅ Test topshirilgan")
                        : flags.canTakeTest
                          ? tt("library.testReady", "⏳ Deadline tugadi. Testni boshlang.")
                          : `${tt("library.deadline", "⏳ Deadline:")} ${formatCountdown(flags.seconds)}`}
                    </div>
                  ) : null}
                  
                  <div className="mt-auto pt-3 border-t border-line dark:border-white/10 flex items-center justify-between gap-2">
                    {!flags.purchased ? (
                      <div className="font-black text-sm sm:text-base text-navy-900 dark:text-white library-card-meta">
                          {Number(b.price || 0) > 0 ? `${Number(b.price || 0)} D\u0027coin` : tt("library.free", "Tekin")}
                      </div>
                    ) : (
                      <div className="min-w-0 flex-1">
                        <span className="library-card-meta block text-xs font-bold text-ink-500 dark:text-navy-300">
                          {flags.testSubmitted ? tt("library.testSubmittedLabel", "Test topshirilgan") : flags.canTakeTest ? tt("library.testReadyLabel", "Test vaqti keldi") : tt("library.canRead", "O'qish mumkin")}
                        </span>
                      </div>
                    )}
                    {flags.canTakeTest ? (
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            startTest(b).catch(() => null);
                          }}
                          className="bg-gold-500 hover:bg-gold-600 text-white px-3 py-2 rounded-xl font-bold transition-all text-xs sm:text-sm shadow-[0_0_15px_rgba(234,179,8,0.3)]"
                        >
                          {tt("contentTest.test", "Test")}
                        </button>
                    ) : null}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
      <div className="list-pagination-row">
        <button className="pagination-btn" type="button" disabled={page <= 1 || loading} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>
          {tt("common.prev", "Oldingi")}
        </button>
        <span className="pagination-page">{tt("common.page", "Sahifa")} {page}</span>
        <button className="pagination-btn" type="button" disabled={!hasMore || loading} onClick={() => setPage((prev) => prev + 1)}>
          {tt("common.next", "Keyingi")}
        </button>
      </div>
      <ModalPortal open={Boolean(purchaseCandidate)}>
      {purchaseCandidate ? (() => {
        const modalFlags = deriveBookFlags(purchaseCandidate);
        const canBuy = !modalFlags.purchased && Number(purchaseCandidate.price || 0) <= wallet;
        return (
        <div className="overlay-modal-backdrop book-purchase-backdrop" onClick={() => setPurchaseCandidate(null)}>
          <div className="overlay-modal-card book-purchase-modal" onClick={(event) => event.stopPropagation()}>
            <div className="row-between gap-3">
              <h3 className="text-lg font-bold text-navy-900 dark:text-white">{purchaseCandidate.title}</h3>
              <button className="modal-icon-close" type="button" onClick={() => setPurchaseCandidate(null)} aria-label={tt("common.close", "Yopish")}>
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M6 6l12 12M18 6L6 18" />
                </svg>
              </button>
            </div>
            {purchaseCandidate.cover_url ? (
              <img key={`purchase-cover-${purchaseCandidate.id}-${purchaseCandidate.cover_url || ""}`} src={mediaUrl(purchaseCandidate.cover_url)} alt={purchaseCandidate.title} loading="lazy" decoding="async" className="book-purchase-cover" />
            ) : null}
            {purchaseCandidate.description ? (
              <p className="text-sm text-ink-600 dark:text-navy-300">{purchaseCandidate.description}</p>
            ) : null}
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="rounded-xl bg-surface-soft dark:bg-white/5 p-3">
                <p className="text-xs text-ink-500 dark:text-navy-400">{tt("common.price", "Narx")}</p>
                <p className="font-bold text-navy-900 dark:text-white">{Number(purchaseCandidate.price || 0)} D&apos;coin</p>
              </div>
              <div className="rounded-xl bg-surface-soft dark:bg-white/5 p-3">
                <p className="text-xs text-ink-500 dark:text-navy-400">{tt("library.duration", "Muddat")}</p>
                <p className="font-bold text-navy-900 dark:text-white">{Number(purchaseCandidate.deadline_days || 0) > 0 ? `${Number(purchaseCandidate.deadline_days || 0)} ${tt("library.day", "kun")}` : "—"}</p>
              </div>
            </div>
            {!modalFlags.purchased && Number(purchaseCandidate.price || 0) > wallet ? (
              <p className="text-sm font-semibold text-red-600 dark:text-red-300">{tt("library.notEnoughDcoin", "D'coin yetarli emas.")}</p>
            ) : null}
            <div className="flex flex-wrap justify-end gap-2">
              {modalFlags.purchased ? (
                <>
                  <button className="btn btn-soft" type="button" onClick={() => openBookReader(purchaseCandidate)}>
                    {tt("library.read", "O'qish")}
                  </button>
                  {modalFlags.canTakeTest ? (
                    <button
                      className="btn btn-primary"
                      type="button"
                      onClick={() => {
                        setPurchaseCandidate(null);
                        startTest(purchaseCandidate).catch(() => null);
                      }}
                    >
                      {tt("library.startTest", "Testni boshlash")}
                    </button>
                  ) : null}
                </>
              ) : (
                <button
                  className="btn btn-primary"
                  disabled={buyingBookId === purchaseCandidate.id || !canBuy}
                  onClick={() => buyBook(purchaseCandidate)}
                >
                  {buyingBookId === purchaseCandidate.id ? tt("common.loading", "Yuklanmoqda...") : tt("library.confirmBuy", "Tasdiqlab xarid qilish")}
                </button>
              )}
            </div>
          </div>
        </div>
        );
      })() : null}
      </ModalPortal>
    </div>
  );
}
