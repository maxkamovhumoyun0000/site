"use client";

import React, { useEffect, useRef, useState } from "react";

type PdfApi = {
  GlobalWorkerOptions: { workerSrc: string };
  TextLayer: new (args: { textContentSource: unknown; container: HTMLDivElement; viewport: unknown }) => {
    render: () => Promise<void>;
    cancel?: () => void;
  };
  getDocument: (src: unknown) => { promise: Promise<any> };
};

type MobilePdfViewerProps = {
  pdfUrl: string;
  title?: string;
  className?: string;
  authToken?: string;
  hideHeader?: boolean;
  onBack?: () => void;
};

type PdfPageViewProps = {
  pdfDoc: any;
  pdfApi: PdfApi;
  pageNumber: number;
  zoom: number;
  containerWidth: number;
  scrollRoot: HTMLDivElement | null;
};

const PDF_WORKER_SRC = "/pdfjs/pdf.worker.min.mjs";
const MIN_ZOOM = 0.75;
const MAX_ZOOM = 2.5;
const PAN_SENSITIVITY = 1.85;

function touchDistance(touches: React.TouchList | TouchList) {
  if (touches.length < 2) return 0;
  const a = touches[0];
  const b = touches[1];
  return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
}

function clampZoom(value: number) {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value));
}

function pdfReaderStorageKey(pdfUrl: string, title: string) {
  const raw = `${String(pdfUrl || "").trim()}::${String(title || "").trim()}`;
  let hash = 0;
  for (let index = 0; index < raw.length; index += 1) {
    hash = (hash * 31 + raw.charCodeAt(index)) | 0;
  }
  return `diamond_pdf_last_page:${Math.abs(hash)}`;
}

function PdfPageView({ pdfDoc, pdfApi, pageNumber, zoom, containerWidth, scrollRoot }: PdfPageViewProps) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const textLayerRef = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(pageNumber <= 2);
  const [rendering, setRendering] = useState(false);
  const [renderedOnce, setRenderedOnce] = useState(false);
  const [size, setSize] = useState({ width: Math.max(320, containerWidth || 360), height: Math.round((containerWidth || 360) * 1.35) });

  useEffect(() => {
    const node = wrapRef.current;
    if (!node || visible) return;
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) setVisible(true);
      },
      { root: scrollRoot, rootMargin: "1200px 0px", threshold: 0.01 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [scrollRoot, visible]);

  useEffect(() => {
    let cancelled = false;
    let renderTask: any = null;
    let textLayer: any = null;

    async function renderPage() {
      if (!visible || !pdfDoc || !canvasRef.current || !textLayerRef.current || !wrapRef.current || containerWidth <= 0) return;
      setRendering(true);
      try {
        const canvas = canvasRef.current;
        const textLayerEl = textLayerRef.current;
        const wrap = wrapRef.current;
        textLayerEl.replaceChildren();

        const pageProxy = await pdfDoc.getPage(pageNumber);
        if (cancelled) return;
        const initialViewport = pageProxy.getViewport({ scale: 1 });
        const fitScale = Math.max(0.5, containerWidth / Math.max(1, initialViewport.width));
        const viewport = pageProxy.getViewport({ scale: fitScale * zoom });
        const width = Math.floor(viewport.width);
        const height = Math.floor(viewport.height);
        const outputScale = Math.min(3, Math.max(1, window.devicePixelRatio || 1));

        setSize({ width, height });
        wrap.style.width = `${width}px`;
        wrap.style.height = `${height}px`;
        textLayerEl.style.width = `${width}px`;
        textLayerEl.style.height = `${height}px`;
        canvas.width = Math.floor(width * outputScale);
        canvas.height = Math.floor(height * outputScale);
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;

        const ctx = canvas.getContext("2d", { alpha: false });
        if (!ctx) throw new Error("canvas context unavailable");
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        renderTask = pageProxy.render({
          canvasContext: ctx,
          viewport,
          transform: outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : undefined,
        });
        await renderTask.promise;
        if (cancelled) return;

        const textContent = await pageProxy.getTextContent();
        if (cancelled) return;
        textLayer = new pdfApi.TextLayer({
          textContentSource: textContent,
          container: textLayerEl,
          viewport,
        });
        await textLayer.render();
        if (!cancelled) setRenderedOnce(true);
      } finally {
        if (!cancelled) setRendering(false);
      }
    }

    renderPage().catch(() => {
      if (!cancelled) setRendering(false);
    });
    return () => {
      cancelled = true;
      try {
        renderTask?.cancel?.();
      } catch {
        // no-op
      }
      try {
        textLayer?.cancel?.();
      } catch {
        // no-op
      }
    };
  }, [containerWidth, pdfApi, pdfDoc, pageNumber, visible, zoom]);

  return (
    <div
      ref={wrapRef}
      data-pdf-page={pageNumber}
      className="relative mx-auto bg-white shadow-lg"
      style={{ width: size.width, height: size.height }}
    >
      <canvas ref={canvasRef} className="absolute inset-0 bg-white pointer-events-none" />
      <div ref={textLayerRef} className="textLayer absolute inset-0" />
      {!visible || (rendering && !renderedOnce) ? (
        <div className="absolute inset-0 grid place-items-center bg-slate-950/10 text-xs font-bold text-white">
          Sahifa yuklanmoqda...
        </div>
      ) : null}
    </div>
  );
}

export function MobilePdfViewer({
  pdfUrl,
  title = "PDF",
  className = "",
  authToken = "",
  hideHeader = false,
  onBack,
}: MobilePdfViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const touchStateRef = useRef({
    pinchDistance: 0,
    pinchZoom: 1,
    pinchLastZoom: 1,
    panX: 0,
    panY: 0,
    panning: false,
  });
  const mousePanRef = useRef({ active: false, x: 0, y: 0 });
  const zoomFrameRef = useRef<number | null>(null);
  const restoreAppliedRef = useRef(false);
  const scrollSaveFrameRef = useRef<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pdfDoc, setPdfDoc] = useState<any>(null);
  const [pdfApi, setPdfApi] = useState<PdfApi | null>(null);
  const [pageCount, setPageCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [renderZoom, setRenderZoom] = useState(1);
  const [liveZoom, setLiveZoom] = useState(1);
  const [containerWidth, setContainerWidth] = useState(360);
  const [scrollRoot, setScrollRoot] = useState<HTMLDivElement | null>(null);

  useEffect(() => {
    const webApp = (window as any)?.Telegram?.WebApp;
    const backButton = webApp?.BackButton;
    const handleBack = () => onBack?.();
    if (webApp) {
      try {
        webApp.expand?.();
        if (typeof webApp.disableVerticalSwipes === "function") webApp.disableVerticalSwipes();
        if (backButton && onBack) {
          backButton.show?.();
          backButton.onClick?.(handleBack);
        }
      } catch {
        // Telegram WebView methods are best-effort only.
      }
    }
    return () => {
      if (webApp) {
        try {
          if (backButton && onBack) {
            backButton.offClick?.(handleBack);
            backButton.hide?.();
          }
          if (typeof webApp.enableVerticalSwipes === "function") webApp.enableVerticalSwipes();
        } catch {
          // no-op
        }
      }
    };
  }, [onBack]);

  useEffect(() => {
    const updateWidth = () => {
      const width = Math.max(320, Math.floor(containerRef.current?.clientWidth || window.innerWidth || 360));
      setContainerWidth(width);
    };
    updateWidth();
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(updateWidth) : null;
    if (observer && containerRef.current) observer.observe(containerRef.current);
    window.addEventListener("resize", updateWidth);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", updateWidth);
    };
  }, []);

  useEffect(() => {
    setScrollRoot(scrollRef.current);
  }, []);

  useEffect(() => {
    restoreAppliedRef.current = false;
  }, [pdfUrl, title]);

  useEffect(() => {
    if (!pdfDoc || !scrollRoot || pageCount <= 0 || restoreAppliedRef.current) return;
    restoreAppliedRef.current = true;
    let savedPage = 0;
    try {
      const raw = window.localStorage.getItem(pdfReaderStorageKey(pdfUrl, title));
      const parsed = raw ? JSON.parse(raw) : null;
      savedPage = Math.max(1, Math.min(pageCount, Number(parsed?.page || 0)));
    } catch {
      savedPage = 0;
    }
    if (!savedPage || savedPage <= 1) return;
    setCurrentPage(savedPage);
    requestAnimationFrame(() => {
      const target = scrollRoot.querySelector(`[data-pdf-page="${savedPage}"]`) as HTMLElement | null;
      if (target) {
        scrollRoot.scrollTo({ top: Math.max(0, target.offsetTop - 4), left: 0, behavior: "auto" });
      }
    });
  }, [pageCount, pdfDoc, pdfUrl, scrollRoot, title]);

  useEffect(() => {
    let cancelled = false;
    let mountedDoc: any = null;

    async function loadPdf() {
      if (!pdfUrl) {
        setError("PDF topilmadi yoki sizda ruxsat yo'q.");
        setLoading(false);
        return;
      }
      setLoading(true);
      setError("");
      setPdfDoc(null);
      setPdfApi(null);
      setPageCount(0);
      setCurrentPage(1);
      setRenderZoom(1);
      setLiveZoom(1);
      try {
        const mod = (await import("pdfjs-dist/legacy/build/pdf.mjs")) as unknown as PdfApi;
        mod.GlobalWorkerOptions.workerSrc = PDF_WORKER_SRC;
        const headers: Record<string, string> = { Accept: "application/pdf,*/*" };
        const token = String(authToken || "").trim();
        if (token) headers.Authorization = `Bearer ${token}`;
        const doc = await mod.getDocument({
          url: pdfUrl,
          httpHeaders: headers,
          withCredentials: true,
          disableAutoFetch: false,
          disableRange: false,
          disableStream: false,
        }).promise;
        if (cancelled) return;
        mountedDoc = doc;
        setPdfApi(mod);
        setPdfDoc(doc);
        setPageCount(Number(doc.numPages || 0));
      } catch (err) {
        if (cancelled) return;
        const msg = String(err instanceof Error ? err.message : "").trim().toLowerCase();
        if (msg.includes("password")) setError("Ushbu PDF himoyalangan.");
        else if (msg.includes("403") || msg.includes("unauthorized")) setError("PDF topilmadi yoki sizda ruxsat yo'q.");
        else if (msg.includes("404")) setError("PDF fayli topilmadi.");
        else setError("PDF yuklanmadi. Qayta urinib ko'ring.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadPdf().catch(() => null);
    return () => {
      cancelled = true;
      try {
        mountedDoc?.destroy?.();
      } catch {
        // no-op
      }
      if (zoomFrameRef.current !== null) {
        window.cancelAnimationFrame(zoomFrameRef.current);
        zoomFrameRef.current = null;
      }
      if (scrollSaveFrameRef.current !== null) {
        window.cancelAnimationFrame(scrollSaveFrameRef.current);
        scrollSaveFrameRef.current = null;
      }
    };
  }, [pdfUrl, authToken]);

  function saveCurrentPageFromScroll() {
    const scrollEl = scrollRef.current;
    if (!scrollEl || pageCount <= 0) return;
    if (scrollSaveFrameRef.current !== null) window.cancelAnimationFrame(scrollSaveFrameRef.current);
    scrollSaveFrameRef.current = window.requestAnimationFrame(() => {
      scrollSaveFrameRef.current = null;
      const rootRect = scrollEl.getBoundingClientRect();
      const probeY = rootRect.top + rootRect.height * 0.42;
      const nodes = Array.from(scrollEl.querySelectorAll<HTMLElement>("[data-pdf-page]"));
      let bestPage = 1;
      let bestDistance = Number.POSITIVE_INFINITY;
      for (const node of nodes) {
        const rect = node.getBoundingClientRect();
        const pageNumber = Number(node.dataset.pdfPage || 0);
        if (!pageNumber) continue;
        let distance = 0;
        if (rect.bottom < probeY) distance = probeY - rect.bottom;
        else if (rect.top > probeY) distance = rect.top - probeY;
        if (distance < bestDistance) {
          bestDistance = distance;
          bestPage = pageNumber;
        }
        if (rect.top > rootRect.bottom) break;
      }
      setCurrentPage(bestPage);
      try {
        window.localStorage.setItem(
          pdfReaderStorageKey(pdfUrl, title),
          JSON.stringify({ page: bestPage, updated_at: Date.now() }),
        );
      } catch {
        // Storage can be unavailable in strict webviews.
      }
    });
  }

  return (
    <div ref={containerRef} className={`relative flex h-full min-h-[100dvh] flex-col bg-slate-950 ${className}`}>
      {!hideHeader ? (
        <div className="sticky top-0 z-20 border-b border-white/10 bg-slate-900/95 px-3 py-2 text-white backdrop-blur-md">
          <strong className="block truncate text-xs sm:text-sm">{title}</strong>
        </div>
      ) : null}

      {loading ? (
        <div className="flex flex-1 items-center justify-center px-4 text-center text-sm font-semibold text-slate-200">
          Kitob yuklanmoqda...
        </div>
      ) : error ? (
        <div className="flex flex-1 items-center justify-center px-4 text-center">
          <p className="max-w-sm text-sm font-semibold text-red-200">{error}</p>
        </div>
      ) : (
        <>
        {pageCount > 0 ? (
          <div className="pointer-events-none absolute left-1/2 top-3 z-30 -translate-x-1/2 rounded-full border border-white/15 bg-slate-950/75 px-3 py-1 text-xs font-black text-white shadow-lg backdrop-blur-md">
            {currentPage} / {pageCount}
          </div>
        ) : null}
        <div
          ref={scrollRef}
          className={`flex-1 overflow-auto bg-slate-950 p-0 ${liveZoom > 1 ? "select-none cursor-grab active:cursor-grabbing" : ""}`}
          style={{
            touchAction: liveZoom > 1 ? "none" : "pan-y",
            WebkitOverflowScrolling: "touch",
            overscrollBehavior: "contain",
          }}
          onTouchStart={(e) => {
            if (e.touches.length >= 2) {
              touchStateRef.current.pinchDistance = touchDistance(e.touches);
              touchStateRef.current.pinchZoom = liveZoom;
              touchStateRef.current.pinchLastZoom = liveZoom;
              touchStateRef.current.panning = false;
              return;
            }
            const touch = e.touches[0];
            if (!touch || liveZoom <= 1) return;
            touchStateRef.current.panX = touch.clientX;
            touchStateRef.current.panY = touch.clientY;
            touchStateRef.current.panning = true;
          }}
          onTouchMove={(e) => {
            const scrollEl = scrollRef.current;
            if (!scrollEl) return;
            if (e.touches.length === 1 && liveZoom > 1 && touchStateRef.current.panning) {
              const touch = e.touches[0];
              if (!touch) return;
              e.preventDefault();
              const dx = touch.clientX - touchStateRef.current.panX;
              const dy = touch.clientY - touchStateRef.current.panY;
              scrollEl.scrollLeft -= dx * PAN_SENSITIVITY;
              scrollEl.scrollTop -= dy * PAN_SENSITIVITY;
              touchStateRef.current.panX = touch.clientX;
              touchStateRef.current.panY = touch.clientY;
              return;
            }
            if (e.touches.length < 2) return;
            const startDistance = touchStateRef.current.pinchDistance || touchDistance(e.touches);
            if (!startDistance) return;
            e.preventDefault();
            const nextZoom = clampZoom(touchStateRef.current.pinchZoom * (touchDistance(e.touches) / startDistance));
            const prevZoom = touchStateRef.current.pinchLastZoom || liveZoom || 1;
            const ratio = nextZoom / prevZoom;
            const rect = scrollEl.getBoundingClientRect();
            const centerX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
            const centerY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
            const localX = centerX - rect.left;
            const localY = centerY - rect.top;
            if (zoomFrameRef.current !== null) window.cancelAnimationFrame(zoomFrameRef.current);
            zoomFrameRef.current = window.requestAnimationFrame(() => {
              setLiveZoom(Number(nextZoom.toFixed(2)));
              requestAnimationFrame(() => {
                scrollEl.scrollLeft = (scrollEl.scrollLeft + localX) * ratio - localX;
                scrollEl.scrollTop = (scrollEl.scrollTop + localY) * ratio - localY;
              });
              touchStateRef.current.pinchLastZoom = nextZoom;
              zoomFrameRef.current = null;
            });
          }}
          onTouchEnd={(e) => {
            if (e.touches.length > 0) return;
            touchStateRef.current.pinchDistance = 0;
            touchStateRef.current.pinchZoom = liveZoom;
            touchStateRef.current.pinchLastZoom = liveZoom;
            touchStateRef.current.panning = false;
          }}
          onMouseDown={(e) => {
            if (liveZoom <= 1 || e.button !== 0) return;
            e.preventDefault();
            mousePanRef.current = { active: true, x: e.clientX, y: e.clientY };
          }}
          onMouseMove={(e) => {
            if (!mousePanRef.current.active || liveZoom <= 1 || !scrollRef.current) return;
            e.preventDefault();
            const dx = e.clientX - mousePanRef.current.x;
            const dy = e.clientY - mousePanRef.current.y;
            scrollRef.current.scrollLeft -= dx * PAN_SENSITIVITY;
            scrollRef.current.scrollTop -= dy * PAN_SENSITIVITY;
            mousePanRef.current.x = e.clientX;
            mousePanRef.current.y = e.clientY;
          }}
          onMouseUp={() => {
            mousePanRef.current.active = false;
          }}
          onMouseLeave={() => {
            mousePanRef.current.active = false;
          }}
          onScroll={saveCurrentPageFromScroll}
        >
          <div
            className="flex min-h-full flex-col gap-2"
            style={{ zoom: liveZoom / renderZoom } as React.CSSProperties}
          >
            {pdfDoc && pdfApi
              ? Array.from({ length: pageCount }, (_, index) => (
                  <PdfPageView
                    key={index + 1}
                    pdfDoc={pdfDoc}
                    pdfApi={pdfApi}
                    pageNumber={index + 1}
                    zoom={renderZoom}
                    containerWidth={containerWidth}
                    scrollRoot={scrollRoot}
                  />
                ))
              : null}
          </div>
        </div>
        </>
      )}
    </div>
  );
}
