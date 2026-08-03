"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface EpubViewerProps {
  epubUrl: string;
  title?: string;
  authToken?: string;
  onBack?: () => void;
  className?: string;
}

export function EpubViewer({ epubUrl, title, authToken, onBack, className = "" }: EpubViewerProps) {
  const viewerRef = useRef<HTMLDivElement>(null);
  const bookRef = useRef<any>(null);
  const renditionRef = useRef<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState(0);
  const [currentCfi, setCurrentCfi] = useState("");
  const [canPrev, setCanPrev] = useState(false);
  const [canNext, setCanNext] = useState(true);
  const [fontSize, setFontSize] = useState(100);

  const destroy = useCallback(() => {
    try { renditionRef.current?.destroy(); } catch { /* ignore */ }
    try { bookRef.current?.destroy(); } catch { /* ignore */ }
    renditionRef.current = null;
    bookRef.current = null;
  }, []);

  useEffect(() => {
    if (!epubUrl || !viewerRef.current) return;
    let cancelled = false;

    async function init() {
      setLoading(true);
      setError("");
      setProgress(0);
      setCanPrev(false);
      setCanNext(true);
      destroy();

      try {
        // Fetch with auth token
        const headers: Record<string, string> = {};
        if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
        const res = await fetch(epubUrl, { headers });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const buffer = await res.arrayBuffer();
        if (cancelled) return;

        // Dynamic import to avoid SSR issues
        const { default: Epub } = await import("epubjs");
        if (cancelled) return;

        const book = Epub(buffer);
        bookRef.current = book;

        await book.ready;
        if (cancelled) return;

        const rendition = book.renderTo(viewerRef.current!, {
          width: "100%",
          height: "100%",
          flow: "paginated",
          spread: "none",
        });
        renditionRef.current = rendition;

        // Apply default theme
        rendition.themes.register("light", {
          body: { background: "#fafafa", color: "#1a1a1a", fontFamily: "Georgia, serif", lineHeight: "1.8" },
        });
        rendition.themes.register("dark", {
          body: { background: "#1a1a2e", color: "#e2e8f0", fontFamily: "Georgia, serif", lineHeight: "1.8" },
        });
        const isDark = document.documentElement.classList.contains("dark");
        rendition.themes.select(isDark ? "dark" : "light");
        rendition.themes.fontSize(`${fontSize}%`);

        rendition.on("relocated", (location: any) => {
          const pct = book.locations?.percentageFromCfi?.(location.start.cfi) || 0;
          setProgress(Math.round(pct * 100));
          setCurrentCfi(location.start.cfi);
          setCanPrev(!location.atStart);
          setCanNext(!location.atEnd);
        });

        // Generate locations for progress tracking (async, non-blocking)
        book.locations.generate(1600).catch(() => null);

        await rendition.display();
        if (cancelled) return;
        setLoading(false);
      } catch (e) {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : "ePub fayl yuklanmadi";
        setError(msg.includes("403") ? "Sizda bu kitobni o'qish huquqi yo'q." :
                 msg.includes("404") ? "ePub fayl topilmadi." : msg);
        setLoading(false);
      }
    }

    init().catch(() => null);

    return () => {
      cancelled = true;
      destroy();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [epubUrl, authToken]);

  const prev = useCallback(() => renditionRef.current?.prev().catch(() => null), []);
  const next = useCallback(() => renditionRef.current?.next().catch(() => null), []);

  const changeFontSize = useCallback((delta: number) => {
    const newSize = Math.min(200, Math.max(60, fontSize + delta));
    setFontSize(newSize);
    renditionRef.current?.themes.fontSize(`${newSize}%`);
  }, [fontSize]);

  // Keyboard navigation
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowLeft" || e.key === "ArrowUp") prev();
      if (e.key === "ArrowRight" || e.key === "ArrowDown") next();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [prev, next]);

  return (
    <div className={`flex flex-col bg-slate-950 text-white ${className}`} style={{ height: "100dvh" }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-slate-900 border-b border-slate-800 shrink-0 gap-3">
        {onBack && (
          <button
            onClick={onBack}
            className="flex items-center gap-2 text-slate-300 hover:text-white transition-colors font-semibold text-sm"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            <span className="hidden sm:inline">Orqaga</span>
          </button>
        )}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-bold truncate text-white">{title || "Kitob"}</p>
          <div className="flex items-center gap-2 mt-1">
            <div className="flex-1 h-1 bg-slate-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-cyan-500 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="text-[11px] text-slate-400 font-mono shrink-0">{progress}%</span>
          </div>
        </div>
        {/* Font size controls */}
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => changeFontSize(-10)}
            className="w-8 h-8 flex items-center justify-center rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors text-lg font-bold"
            title="Shriftni kichraytirish"
          >
            A-
          </button>
          <button
            onClick={() => changeFontSize(10)}
            className="w-8 h-8 flex items-center justify-center rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors text-xl font-bold"
            title="Shriftni kattalashtirish"
          >
            A+
          </button>
        </div>
      </div>

      {/* Reader area */}
      <div className="flex flex-1 min-h-0 relative">
        {/* Prev button */}
        <button
          onClick={prev}
          disabled={!canPrev || loading}
          className="hidden sm:flex absolute left-0 top-0 bottom-0 w-14 z-10 items-center justify-center text-slate-600 hover:text-slate-200 hover:bg-slate-800/40 disabled:opacity-20 transition-all"
          title="Oldingi sahifa"
        >
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>

        {/* Epub container */}
        <div className="flex-1 min-w-0 relative overflow-hidden bg-[#fafafa] dark:bg-[#1a1a2e]" style={{ margin: "0 3.5rem" }}>
          {loading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950 z-20 gap-4">
              <div className="w-10 h-10 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin" />
              <p className="text-slate-400 font-semibold text-sm">ePub yuklanmoqda...</p>
            </div>
          )}
          {error && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950 z-20 gap-4 p-8 text-center">
              <span className="text-5xl">📚</span>
              <p className="text-red-400 font-bold">{error}</p>
              {onBack && (
                <button onClick={onBack} className="mt-2 px-5 py-2 bg-cyan-600 rounded-xl text-white font-bold text-sm hover:bg-cyan-700">
                  Orqaga qaytish
                </button>
              )}
            </div>
          )}
          <div ref={viewerRef} className="w-full h-full" />
        </div>

        {/* Next button */}
        <button
          onClick={next}
          disabled={!canNext || loading}
          className="hidden sm:flex absolute right-0 top-0 bottom-0 w-14 z-10 items-center justify-center text-slate-600 hover:text-slate-200 hover:bg-slate-800/40 disabled:opacity-20 transition-all"
          title="Keyingi sahifa"
        >
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      {/* Bottom navigation (mobile) */}
      <div className="flex sm:hidden items-center justify-between px-4 py-3 bg-slate-900 border-t border-slate-800 shrink-0">
        <button
          onClick={prev}
          disabled={!canPrev || loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 disabled:opacity-30 text-slate-200 font-semibold text-sm"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Oldingi
        </button>
        <span className="text-slate-400 text-xs font-mono">{progress}%</span>
        <button
          onClick={next}
          disabled={!canNext || loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 disabled:opacity-30 text-slate-200 font-semibold text-sm"
        >
          Keyingi
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>
  );
}

/** URL epub faylmi yoki yo'qligini tekshiradi */
export function isEpubUrl(url?: string | null): boolean {
  return /\.epub(\?|$)/i.test(String(url || "").trim());
}
