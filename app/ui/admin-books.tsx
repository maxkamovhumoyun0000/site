"use client";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ModalPortal } from "./modal-portal";
import { SharedTestEditor, validateTestQuestions, TestQuestion } from "./shared-test-editor";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
const LIBRARY_LOAD_ERROR = "Kutubxona yuklanmadi. Qayta urinib ko‘ring.";

type BookItem = {
  id: number;
  title: string;
  subject?: string;
  description?: string;
  author?: string;
  category?: string;
  level?: string;
  cover_url?: string;
  pdf_url?: string;
  pdf_asset_id?: number | null;
  price?: number;
  deadline_days?: number;
  purchase_count?: number;
  read_count?: number;
  like_count?: number;
  created_at?: string;
  is_published?: boolean;
  question_count?: number;
};

type BookQuestion = {
  id: number;
  book_id: number;
  question: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_option: string;
  explanation?: string;
  order: number;
};

type BookFormState = {
  title: string;
  subject: string;
  description: string;
  author: string;
  category: string;
  level: string;
  cover_url: string;
  pdf_url: string;
  pdf_asset_id: number | null;
  price: string;
  deadline_days: string;
  is_published: boolean;
};

const EMPTY_BOOK_FORM: BookFormState = {
  title: "",
  subject: "English",
  description: "",
  author: "",
  category: "",
  level: "",
  cover_url: "",
  pdf_url: "",
  pdf_asset_id: null,
  price: "",
  deadline_days: "",
  is_published: true,
};

function BookCoverImage({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setFailed(false);
  }, [src]);
  if (!src || failed) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-slate-100 dark:bg-slate-900">
        <span className="text-xs font-black uppercase tracking-wider text-slate-400 dark:text-slate-500">Kitob</span>
      </div>
    );
  }
	  return <img src={src} alt={alt} loading="lazy" decoding="async" onError={() => setFailed(true)} className="w-full h-full object-contain bg-white dark:bg-slate-950" />;
}

export function AdminBooks({
  apiFetch,
  rolePrefix = "admin",
  canUploadBooks = false,
  canManageBookTests = false,
}: {
  apiFetch: (path: string, options?: any) => Promise<any>;
  rolePrefix?: "admin" | "teacher" | "support";
  canUploadBooks?: boolean;
  canManageBookTests?: boolean;
}) {
  const router = useRouter();
  const [books, setBooks] = useState<BookItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [showBookModal, setShowBookModal] = useState(false);
  const [bookSaving, setBookSaving] = useState(false);
  const [uploadingBookPdf, setUploadingBookPdf] = useState(false);
  const [selectedBookPdfName, setSelectedBookPdfName] = useState("");
  const [uploadingBookCover, setUploadingBookCover] = useState(false);
  const [selectedBookCoverName, setSelectedBookCoverName] = useState("");
  const [editingBookId, setEditingBookId] = useState<number | null>(null);
  const [bookForm, setBookForm] = useState<BookFormState>(EMPTY_BOOK_FORM);
  const [selectedBookId, setSelectedBookId] = useState<number | null>(null);
  
  // Test editor state
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [testBookId, setTestBookId] = useState<number | null>(null);
  const [testBookTitle, setTestBookTitle] = useState("");
  const [testQuestions, setTestQuestions] = useState<TestQuestion[]>([]);
  const [testBusy, setTestBusy] = useState(false);
  
  const [subjectFilter, setSubjectFilter] = useState("all");
  const apiFetchRef = useRef(apiFetch);
  const booksRequestSeqRef = useRef(0);
  const apiPrefix = rolePrefix === "admin" ? "/admin" : rolePrefix === "support" ? "/support" : "/teacher";
  const canManageBooks = rolePrefix === "admin" || Boolean(canUploadBooks);
  const canEditBooks = rolePrefix === "admin";
  const canManageTests = rolePrefix === "admin" || Boolean(canManageBookTests);

  useEffect(() => {
    apiFetchRef.current = apiFetch;
  }, [apiFetch]);

  function mediaUrl(url?: string) {
    const raw = String(url || "").trim();
    if (!raw) return "";
    return raw.startsWith("/") ? `${API_BASE}${raw}` : raw;
  }

  function emitToast(message: string) {
    if (typeof window === "undefined") return;
    const text = String(message || "").trim();
    if (!text) return;
    window.dispatchEvent(new CustomEvent("diamond:toast", { detail: { message: text } }));
  }

  function normalizeUploadError(error: unknown, fallback: string) {
    const raw = error instanceof Error ? error.message : fallback;
    const text = String(raw || "").trim();
    const lowered = text.toLowerCase();
    if (!text) return fallback;
    if (lowered.includes("413") || lowered.includes("juda katta") || lowered.includes("too large")) {
      return "Fayl hajmi juda katta";
    }
    if (lowered.includes("422") || lowered.includes("format") || lowered.includes("type")) {
      return "Fayl turi noto'g'ri";
    }
    if (lowered.includes("timeout")) {
      return "So'rov vaqti tugadi. Qayta urinib ko'ring.";
    }
    if (lowered.includes("not found")) {
      return "Kitob topilmadi";
    }
    if (lowered.includes("could not register media asset") || lowered.includes("internal server error")) {
      return "Kitob yuklanmadi. Qayta urinib ko'ring.";
    }
    if (lowered.includes("<html")) {
      return fallback;
    }
    return text;
  }

  useEffect(() => {
    if (error) emitToast(error);
     
  }, [error]);

  useEffect(() => {
    if (notice) emitToast(notice);
     
  }, [notice]);

  const fetchBooks = useCallback(async () => {
    const requestSeq = booksRequestSeqRef.current + 1;
    booksRequestSeqRef.current = requestSeq;
    setLoading(true);
    setError("");
    try {
      const res = await apiFetchRef.current(`${apiPrefix}/books`);
      if (booksRequestSeqRef.current !== requestSeq) return;
      const items = (res && res.items) ? res.items : [];
      setBooks(items);
      if (items.length) {
        setSelectedBookId((prev) => prev || Number(items[0].id || 0));
      }
    } catch (e) {
      if (booksRequestSeqRef.current !== requestSeq) return;
      setError(LIBRARY_LOAD_ERROR);
    } finally {
      if (booksRequestSeqRef.current === requestSeq) {
        setLoading(false);
      }
    }
  }, [apiPrefix]);

  useEffect(() => {
    let mounted = true;
    const timer = window.setTimeout(() => {
      if (!mounted) return;
      fetchBooks().catch(() => null);
    }, 0);
    return () => {
      mounted = false;
      booksRequestSeqRef.current += 1;
      window.clearTimeout(timer);
    };
  }, [fetchBooks]);

  // Removed old loadQuestions, replaced with openTestModal

  const filtered = books.filter((book) => {
    const text = `${book.title || ""} ${book.author || ""} ${book.category || ""} ${book.subject || ""}`.toLowerCase();
    const matchesQuery = text.includes(query.trim().toLowerCase());
    const matchesSubject = subjectFilter === "all" || String(book.subject || "").trim() === subjectFilter;
    return matchesQuery && matchesSubject;
  });
  const subjectOptions = Array.from(new Set(books.map((book) => String(book.subject || "").trim()).filter(Boolean)));

  const selectedBook = books.find((book) => Number(book.id || 0) === Number(selectedBookId || 0)) || null;

  function openBookDetail(book: BookItem) {
    // Check both `id` and `book_id` for compatibility with different API response shapes
    const bookId = Number(book?.id || (book as any)?.book_id || 0);
    if (!Number.isInteger(bookId) || bookId <= 0) {
      setError("Kitob sahifasini ochib bo\'lmadi \u2014 kitobni qayta yuklang.");
      return;
    }
    router.push(`/${rolePrefix}/books/${bookId}`);
  }

  function toBookFormState(book?: BookItem | null): BookFormState {
    if (!book) return { ...EMPTY_BOOK_FORM };
    return {
      title: String(book.title || ""),
      subject: String(book.subject || "English"),
      description: String(book.description || ""),
      author: String(book.author || ""),
      category: String(book.category || ""),
      level: String(book.level || ""),
      cover_url: String(book.cover_url || ""),
      pdf_url: String(book.pdf_url || ""),
      pdf_asset_id: Number(book.pdf_asset_id || 0) || null,
      price: (book.price ?? null) === null ? "" : String(Number(book.price || 0)),
      deadline_days: (book.deadline_days ?? null) === null ? "" : String(Number(book.deadline_days || 7)),
      is_published: Boolean(book.is_published),
    };
  }

  // toQuestionFormState removed

  function openCreateBookModal() {
    setEditingBookId(null);
    setBookForm(toBookFormState(null));
    setSelectedBookCoverName("");
    setSelectedBookPdfName("");
    setShowBookModal(true);
    setNotice("");
    setError("");
  }

  function openEditBookModal(book: BookItem) {
    setEditingBookId(Number(book.id || 0));
    setBookForm(toBookFormState(book));
    setSelectedBookCoverName("");
    setSelectedBookPdfName("");
    setShowBookModal(true);
    setNotice("");
    setError("");
  }

  async function saveBook() {
    const title = bookForm.title.trim();
    if (title.length < 2) {
      setError("Kitob nomi kamida 2 ta belgidan iborat bo'lishi kerak.");
      return;
    }
    if (!bookForm.cover_url.trim()) {
      setError("Thumbnail yuklash majburiy.");
      return;
    }
    setBookSaving(true);
    setError("");
    try {
      const body = {
        title,
        subject: bookForm.subject.trim(),
        description: bookForm.description.trim(),
        author: bookForm.author.trim(),
        category: "",
        level: "",
        cover_url: bookForm.cover_url.trim(),
        pdf_url: bookForm.pdf_url.trim(),
        pdf_asset_id: bookForm.pdf_asset_id || null,
        price: String(bookForm.price || "").trim() === "" ? null : Math.max(0, Number(bookForm.price || 0)),
        deadline_days: String(bookForm.deadline_days || "").trim() === "" ? null : Math.max(1, Number(bookForm.deadline_days || 7)),
        is_published: true,
      };
      if (editingBookId) {
        await apiFetch(`/admin/books/${editingBookId}`, { method: "PUT", body });
        emitToast("Kitob yangilandi.");
      } else {
        await apiFetch(`${apiPrefix}/books`, { method: "POST", body });
        emitToast("Kitob yaratildi.");
      }
      setShowBookModal(false);
      await fetchBooks();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Kitobni saqlab bo'lmadi.");
    } finally {
      setBookSaving(false);
    }
  }

  async function uploadPdfFile(file: File) {
    if (!file) return;
    const mime = String(file.type || "").toLowerCase();
    const name = String(file.name || "").toLowerCase();
    const isPdf = mime === "application/pdf" || /\.pdf$/.test(name);
    const isEpub = mime === "application/epub+zip" || /\.epub$/.test(name);
    if (!isPdf && !isEpub) {
      setError("Fayl turi noto'g'ri (PDF yoki EPUB bo'lishi kerak)");
      return;
    }
    const maxBytes = 80 * 1024 * 1024;
    if (Number(file.size || 0) > maxBytes) {
      setError("Fayl hajmi juda katta (max 80 MB)");
      return;
    }
    setUploadingBookPdf(true);
    setError("");
    setNotice("");
    try {
      const body = new FormData();
      body.append("file", file);
      // Backend PDF endpoint qabul qiladi — epub ham shu yo'l orqali yuklanadi
      body.append("asset_type", "pdf");
      if (editingBookId) {
        body.append("target", "book");
        body.append("entity_id", String(editingBookId));
      }
      const res = await apiFetch(`${apiPrefix}/upload/media`, {
        method: "POST",
        body,
      });
      const assetId = Number(res?.asset?.id || 0) || null;
      const streamUrl = String(res?.asset?.stream_url || "").trim();
      if (!assetId || !streamUrl) {
        throw new Error("Fayl yuklanmadi. Qayta urinib ko'ring.");
      }
      setBookForm((prev) => ({
        ...prev,
        pdf_asset_id: assetId,
        pdf_url: prev.pdf_url.trim() || streamUrl || prev.pdf_url,
      }));
      if (editingBookId) {
        await fetchBooks();
      }
      setNotice(`${isEpub ? "ePub" : "PDF"} fayl yuklandi.`);
      setSelectedBookPdfName(file.name || "");
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : "";
      const isTypeErr = errMsg.toLowerCase().includes("422") ||
                        errMsg.toLowerCase().includes("format") ||
                        errMsg.toLowerCase().includes("type") ||
                        errMsg.toLowerCase().includes("unsupported");
      if (isEpub && isTypeErr) {
        setError("Backend ePub yuklashni qo'llab-quvvatlamaydi. ePub kitob URL manzilini 'PDF URL' maydoniga qo'lda kiriting.");
      } else {
        setError(normalizeUploadError(e, "Fayl yuklanmadi. Qayta urinib ko'ring."));
      }
    } finally {
      setUploadingBookPdf(false);
    }
  }

  async function uploadBookCoverFile(file: File) {
    if (!file) return;
    const isImageByType = String(file.type || "").toLowerCase().startsWith("image/");
    const isImageByExt = /\.(jpg|jpeg|png|webp)$/i.test(String(file.name || ""));
    if (!isImageByType && !isImageByExt) {
      setError("Fayl turi noto'g'ri");
      return;
    }
    const maxBytes = 6 * 1024 * 1024;
    if (Number(file.size || 0) > maxBytes) {
      setError("Fayl hajmi juda katta");
      return;
    }
    setUploadingBookCover(true);
    setError("");
    setNotice("");
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("asset_type", "image");
      const res = await apiFetch(`${apiPrefix}/upload/media`, {
        method: "POST",
        body,
      });
      const imageUrl = String(res?.asset?.public_url || res?.asset?.stream_url || "").trim();
      if (!imageUrl) {
        throw new Error("Rasm yuklanmadi. Qayta urinib ko'ring.");
      }
      setBookForm((prev) => ({
        ...prev,
        cover_url: imageUrl,
      }));
      setNotice("Thumbnail yuklandi.");
      setSelectedBookCoverName(file.name || "");
    } catch (e) {
      setError(normalizeUploadError(e, "Rasm yuklanmadi. Qayta urinib ko'ring."));
    } finally {
      setUploadingBookCover(false);
    }
  }

  async function deleteBook(book: BookItem) {
    if (!confirm(`"${book.title}" kitobini o'chirmoqchimisiz?`)) return;
    setError("");
    try {
      await apiFetch(`/admin/books/${book.id}`, { method: "DELETE" });
      setNotice("Kitob o'chirildi.");
      setBooks((prev) => prev.filter((item) => Number(item.id || 0) !== Number(book.id || 0)));
      if (Number(selectedBookId || 0) === Number(book.id || 0)) {
        setSelectedBookId(null);
      }
      fetchBooks().catch(() => null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Kitobni o'chirib bo'lmadi.");
    }
  }

  async function togglePublish(book: BookItem) {
    setError("");
    try {
      await apiFetch(`/admin/books/${book.id}`, { method: "PUT", body: { is_published: !Boolean(book.is_published) } });
      setNotice(Boolean(book.is_published) ? "Kitob qoralamaga o'tkazildi." : "Kitob nashr qilindi.");
      await fetchBooks();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Holatni yangilab bo'lmadi.");
    }
  }

  async function openTestModal(book: BookItem) {
    const bid = Number(book.id || 0);
    setTestBookId(bid);
    setTestBookTitle(book.title || "");
    setTestQuestions([]);
    setTestModalOpen(true);
    setError("");
    setNotice("");
    setTestBusy(true);
    try {
      const res = await apiFetch(`/content-tests/book/${bid}`);
      if (res?.test?.questions) {
        setTestQuestions(res.test.questions);
      }
    } catch (e) {
      // It's okay if not found
    } finally {
      setTestBusy(false);
    }
  }

  async function saveTestQuestions() {
    if (!testBookId) return;
    const validationError = validateTestQuestions(testQuestions);
    if (validationError) {
      setError(validationError);
      return;
    }
    setTestBusy(true);
    setError("");
    try {
      await apiFetch(`/content-tests/book/${testBookId}`, {
        method: "POST",
        body: { questions: testQuestions }
      });
      setNotice("");
      emitToast("Test saqlandi.");
      setTestModalOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Testni saqlab bo'lmadi.");
    } finally {
      setTestBusy(false);
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex justify-between items-center bg-white dark:bg-slate-800 p-6 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700">
        <div>
          <h2 className="text-2xl font-bold text-slate-800 dark:text-white">Kutubxona Boshqaruvi</h2>
          <p className="text-slate-500 dark:text-slate-400 mt-1">{rolePrefix === "admin" ? "Platformadagi barcha elektron kitoblarni boshqarish" : canManageBooks ? "Ruxsat berilgan kitoblarni yuklash va o'qish" : "Fanlaringiz bo'yicha elektron kitoblarni o'qish"}</p>
        </div>
        {canManageBooks ? (
          <button onClick={openCreateBookModal} className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-xl font-medium transition-colors shadow-sm shadow-blue-500/30 flex items-center gap-2">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
            Yangi Kitob
          </button>
        ) : null}
      </div>
      <div className="bg-white dark:bg-slate-800 p-4 rounded-2xl border border-slate-200 dark:border-slate-700 flex flex-col md:flex-row md:items-center gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Kitob qidirish..."
          className="w-full md:max-w-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-2.5 text-sm text-slate-700 dark:text-slate-200 outline-none focus:ring-2 focus:ring-blue-500/30"
        />
        <select
          value={subjectFilter}
          onChange={(event) => setSubjectFilter(event.target.value)}
          className="w-full md:w-48 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-2.5 text-sm text-slate-700 dark:text-slate-200 outline-none focus:ring-2 focus:ring-blue-500/30"
        >
          <option value="all">Barcha fanlar</option>
          {subjectOptions.map((subject) => (
            <option key={`book-subject-${subject}`} value={subject}>{subject}</option>
          ))}
        </select>
        <div className="text-xs text-slate-500 dark:text-slate-400">
          Jami: <span className="font-semibold text-slate-700 dark:text-slate-200">{books.length}</span>, Filtrlangan:{" "}
          <span className="font-semibold text-slate-700 dark:text-slate-200">{filtered.length}</span>
        </div>
      </div>
      {notice ? <div className="rounded-xl bg-green-50 text-green-700 border border-green-200 px-4 py-2 text-sm">{notice}</div> : null}
      {error ? (
        <div className="rounded-xl bg-red-50 text-red-700 border border-red-200 px-4 py-2 text-sm flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <span>{error}</span>
          <button type="button" onClick={fetchBooks} className="rounded-lg border border-red-200 px-3 py-2 text-xs font-bold hover:bg-red-100">
            Qayta urinish
          </button>
        </div>
      ) : null}

      {loading ? (
        <div className="flex justify-center py-12"><div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div></div>
      ) : (
        <div className="grid lg:grid-cols-5 gap-6">
          <div className="lg:col-span-5">
            {filtered.length === 0 ? (
              <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-8 text-center text-slate-500">Kitoblar topilmadi</div>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
                {filtered.map((b) => (
                  <article
                    key={b.id}
                    className={`media-library-card rounded-2xl border bg-white dark:bg-slate-800 shadow-sm overflow-hidden ${Number(selectedBookId || 0) === Number(b.id || 0) ? "border-blue-400 dark:border-blue-500" : "border-slate-200 dark:border-slate-700"}`}
                  >
                    <button
                      type="button"
                      className="w-full text-left"
                      onClick={() => rolePrefix === "admin" ? setSelectedBookId(Number(b.id || 0)) : openBookDetail(b)}
                    >
                      <div className="aspect-[3/4] bg-slate-100 dark:bg-slate-900 overflow-hidden">
                        <BookCoverImage key={`book-cover-${b.id}-${b.cover_url || ""}`} src={mediaUrl(b.cover_url)} alt={b.title} />
                      </div>
                      <div className="p-3 space-y-2">
                        <h3 className="text-sm sm:text-base font-bold text-slate-800 dark:text-white line-clamp-2">{b.title}</h3>
                        <p className="text-xs text-slate-500 truncate">{b.author || "-"}</p>
	                        <div className="flex items-center justify-between gap-2 text-[11px]">
	                          {b.level ? <span className="px-2 py-1 bg-slate-100 dark:bg-slate-700 rounded-md text-slate-700 dark:text-slate-200 font-semibold">{b.level}</span> : null}
	                          <span className="px-2 py-1 bg-cyan-50 dark:bg-cyan-500/10 rounded-md text-cyan-700 dark:text-cyan-200 font-semibold">{b.subject || "-"}</span>
	                          <span className="font-semibold text-slate-700 dark:text-slate-200">{Number(b.price || 0) > 0 ? `${Number(b.price || 0)} D'coin` : "Tekin"}</span>
	                        </div>
                        <div className="flex items-center gap-3 text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                          <span>Sotib olingan: {Number(b.purchase_count || 0)}</span>
                          {Number(b.read_count || 0) > 0 ? <span>O'qilgan: {Number(b.read_count || 0)}</span> : null}
                          {Number(b.like_count || 0) > 0 ? <span>Like: {Number(b.like_count || 0)}</span> : null}
                        </div>
                      </div>
                    </button>
                    <div className="px-3 pb-3 flex flex-wrap items-center gap-2">
                      <button onClick={() => openBookDetail(b)} className="text-cyan-700 hover:text-cyan-900 dark:text-cyan-300 font-medium text-xs">Ochish</button>
                      {canEditBooks ? (
                        <>
                          <button onClick={() => openEditBookModal(b)} className="text-blue-600 hover:text-blue-800 dark:text-blue-400 font-medium text-xs">Tahrirlash</button>
                          <button onClick={() => deleteBook(b)} className="text-red-600 hover:text-red-800 dark:text-red-400 font-medium text-xs">O&apos;chirish</button>
                        </>
                      ) : null}
                      {canManageTests ? (
                        <button onClick={() => openTestModal(b)} className="text-cyan-600 hover:text-cyan-800 dark:text-cyan-400 font-medium text-xs">Testlar</button>
                      ) : null}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
      <ModalPortal open={showBookModal}>
      {showBookModal ? (
        <div className="overlay-modal-backdrop" onClick={() => !bookSaving && setShowBookModal(false)}>
          <div className="overlay-modal-card admin-wide-modal" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-slate-800 dark:text-white">{editingBookId ? "Kitobni tahrirlash" : "Yangi kitob qo'shish"}</h3>
              <button onClick={() => !bookSaving && setShowBookModal(false)} className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200">X</button>
            </div>
            <div className="grid sm:grid-cols-2 gap-3">
              <input value={bookForm.title} onChange={(e) => setBookForm((prev) => ({ ...prev, title: e.target.value }))} placeholder="Sarlavha *" className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-2.5 text-sm" />
	              <select value={bookForm.subject} onChange={(e) => setBookForm((prev) => ({ ...prev, subject: e.target.value }))} className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-2.5 text-sm">
	                <option value="English">English</option>
	                <option value="Russian">Russian</option>
	                <option value="Matematika">Matematika</option>
	                <option value="Tarix">Tarix</option>
	                <option value="Ona tili">Ona tili</option>
	                <option value="Arab tili">Arab tili</option>
	              </select>
	              <input value={bookForm.author} onChange={(e) => setBookForm((prev) => ({ ...prev, author: e.target.value }))} placeholder="Muallif" className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-2.5 text-sm" />
	              <label className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-3 text-sm sm:col-span-2 flex items-center justify-between gap-3 cursor-pointer">
                <span className="font-medium text-slate-700 dark:text-slate-300 truncate">
                  {uploadingBookCover ? "Thumbnail yuklanmoqda..." : selectedBookCoverName || "Thumbnail yuklash (JPG/PNG/WEBP) *"}
                </span>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  className="hidden"
                  disabled={uploadingBookCover || bookSaving}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) {
                      setSelectedBookCoverName(file.name || "");
                      uploadBookCoverFile(file).catch(() => null);
                    }
                    event.currentTarget.value = "";
                  }}
                />
                <span className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold whitespace-nowrap">
                  Fayl tanlash
                </span>
              </label>
              <input value={bookForm.cover_url} onChange={(e) => setBookForm((prev) => ({ ...prev, cover_url: e.target.value }))} placeholder="Cover URL *" className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-2.5 text-sm sm:col-span-2" />
              {bookForm.cover_url.trim() ? (
                <div className="sm:col-span-2 rounded-xl border border-slate-200 dark:border-slate-700 p-2 bg-slate-50 dark:bg-slate-900">
	                  <img
	                    src={mediaUrl(bookForm.cover_url)}
	                    alt="book cover preview"
	                    className="w-full max-h-64 object-contain rounded-lg bg-white dark:bg-slate-950"
	                    onError={() => setError("Rasm yuklanmadi. Qayta urinib ko'ring.")}
	                  />
                </div>
              ) : null}
              <label className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-3 text-sm sm:col-span-2 flex items-center justify-between gap-3 cursor-pointer">
                <span className="font-medium text-slate-700 dark:text-slate-300 truncate">
                  {uploadingBookPdf ? "Fayl yuklanmoqda..." : selectedBookPdfName || "Kitob faylini yuklash (PDF yoki ePub)"}
                </span>
                <input
                  type="file"
                  accept="application/pdf,.pdf,application/epub+zip,.epub"
                  className="hidden"
                  disabled={uploadingBookPdf || bookSaving}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) {
                      setSelectedBookPdfName(file.name || "");
                      uploadPdfFile(file).catch(() => null);
                    }
                    event.currentTarget.value = "";
                  }}
                />
                <span className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold whitespace-nowrap">
                  Fayl tanlash
                </span>
              </label>
              {bookForm.pdf_asset_id ? (
                <div className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 sm:col-span-2">
                  Ulangan media asset: #{bookForm.pdf_asset_id}
                </div>
              ) : null}
	              <input value={bookForm.pdf_url} onChange={(e) => setBookForm((prev) => ({ ...prev, pdf_url: e.target.value }))} placeholder="PDF yoki ePub URL (masalan: https://...book.epub)" className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-2.5 text-sm sm:col-span-2" />
	              <input type="number" min={0} value={bookForm.price} onChange={(e) => setBookForm((prev) => ({ ...prev, price: e.target.value }))} placeholder="Narx (D'coin)" className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-2.5 text-sm" />
	              <input type="number" min={1} value={bookForm.deadline_days} onChange={(e) => setBookForm((prev) => ({ ...prev, deadline_days: e.target.value }))} placeholder="Deadline (kun)" className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-2.5 text-sm" />
	              <textarea value={bookForm.description} onChange={(e) => setBookForm((prev) => ({ ...prev, description: e.target.value }))} placeholder="Tavsif" rows={4} className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-2.5 text-sm sm:col-span-2 resize-none" />
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => !bookSaving && setShowBookModal(false)} disabled={bookSaving} className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200 text-sm">Bekor qilish</button>
              <button onClick={() => saveBook()} disabled={bookSaving} className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium">
                {bookSaving ? "Kitob yuklanmoqda..." : editingBookId ? "Yangilash" : "Saqlash"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
      </ModalPortal>
      <ModalPortal open={testModalOpen}>
      {testModalOpen ? (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4 overflow-y-auto" onClick={() => !testBusy && setTestModalOpen(false)}>
          <div className="bg-white dark:bg-slate-900 w-full max-w-4xl rounded-2xl shadow-xl flex flex-col my-8 border border-slate-200 dark:border-slate-800" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-slate-50 dark:bg-slate-800/50 rounded-t-2xl">
              <h3 className="text-xl font-bold text-slate-800 dark:text-white">Test Tahrirlash: {testBookTitle}</h3>
              <button onClick={() => !testBusy && setTestModalOpen(false)} disabled={testBusy} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">X</button>
            </div>
            
            <div className="p-6 overflow-y-auto max-h-[70vh]">
              {error ? <div className="mb-4 rounded-xl bg-red-50 text-red-700 border border-red-200 px-4 py-3 text-sm font-medium">{error}</div> : null}
              {testBusy && testQuestions.length === 0 ? (
                <div className="flex justify-center py-12"><div className="w-8 h-8 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin"></div></div>
              ) : (
                <SharedTestEditor questions={testQuestions} onChange={setTestQuestions} title="Kitob Test Savollari" />
              )}
            </div>

            <div className="p-6 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 rounded-b-2xl flex justify-end gap-3">
              <button onClick={() => setTestModalOpen(false)} disabled={testBusy} className="px-5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200 text-sm font-semibold hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">Bekor qilish</button>
              <button onClick={saveTestQuestions} disabled={testBusy} className="px-5 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-white text-sm font-bold shadow-sm shadow-cyan-500/30 transition-all">
                {testBusy ? "Saqlanmoqda..." : "Testni saqlash"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
      </ModalPortal>
    </div>
  );
}
