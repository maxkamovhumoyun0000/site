"use client";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { PublicShell } from "../../public-shell";
import { PublicResult, fetchPublicResults, formatPublicDate, toAssetUrl } from "../../public-data";
import { PublicDetailSkeleton } from "../../public-skeletons";
import { getResultPrimaryMedia, getResultVideoUrl, isResultVideoUrl, resultMetricLabel, resultSubjectLabel } from "../../ui/result-card";
import { useWebLocale, useWebT } from "../../ui/web-i18n";

function uniqMedia(values: Array<string | null | undefined>) {
  return Array.from(new Set(values.map((value) => String(value || "").trim()).filter(Boolean)));
}

function formatGrantPercent(value: unknown) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "";
  return `${Number.isInteger(numeric) ? numeric.toFixed(0) : numeric.toFixed(1)}%`;
}

export default function ResultDetailPage() {
  const locale = useWebLocale();
  const tt = useWebT();
  const params = useParams<{ id: string }>();
  const id = Number(params?.id || 0);
  const [items, setItems] = useState<PublicResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeMediaIndex, setActiveMediaIndex] = useState(0);
  const [previewOpen, setPreviewOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const rows = await fetchPublicResults();
        if (!cancelled) setItems(rows);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : tt("public.results.detailLoadError", "Natija tafsilotlarini yuklab bo'lmadi"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [tt]);

  const item = useMemo(() => items.find((row) => Number(row.id) === id) || null, [items, id]);
  const primaryMedia = useMemo(() => {
    const vUrl = getResultVideoUrl(item || {});
    return vUrl || getResultPrimaryMedia(item || {});
  }, [item]);
  const galleryMedia = useMemo(() => {
    return uniqMedia([primaryMedia, ...((item?.media || []) as string[])]);
  }, [item, primaryMedia]);
  const safeActiveMediaIndex = galleryMedia.length ? Math.min(activeMediaIndex, galleryMedia.length - 1) : 0;
  const activeMedia = galleryMedia[safeActiveMediaIndex] || primaryMedia;
  const activeMediaIsVideo = useMemo(() => isResultVideoUrl(activeMedia), [activeMedia]);
  
  const metric = useMemo(() => resultMetricLabel(item || {}), [item]);
  const subject = useMemo(() => resultSubjectLabel(item || {}), [item]);
  const type = String(item?.result_type || "").trim();
  const isUniversity = type === "Universitet";
  const localizedSubject = subject ? tt(`public.subject.${subject}`, subject) : "";
  const localizedMetric = useMemo(() => {
    const score = String(item?.score_text || "").trim();
    if (type === "IELTS") return `IELTS: ${score || "-"}`;
    if (type === "CEFR") return `CEFR: ${score || "-"}`;
    if (type === "Milliy Sertifikat") return `${tt("admin.results.type.Milliy Sertifikat", "Milliy Sertifikat")}: ${score || "-"}`;
    if (type === "Rus tili") return tt("admin.results.studentVideo", "Talaba videosi");
    return metric;
  }, [item, metric, tt, type]);
  const displayDate = useMemo(() => {
    return formatPublicDate(String(item?.exam_date || item?.updated_at || item?.created_at || ""), locale);
  }, [item, locale]);
  const detailRows = useMemo(() => {
    if (!item) return [];
    const rows: Array<{ label: string; value?: string | null }> = [
      { label: tt("common.student", "Talaba"), value: item.student_name },
      { label: tt("common.type", "Turi"), value: tt(`admin.results.type.${item.result_type || ""}`, item.result_type || tt("public.results.result", "Natija")) },
      { label: tt("common.date", "Sana"), value: displayDate },
    ];
    if (type === "Milliy Sertifikat") rows.push({ label: tt("common.subject", "Fan"), value: localizedSubject || item.subject });
    if (type === "IELTS") rows.push({ label: tt("admin.results.band", "Band"), value: item.score_text });
    if (type === "CEFR" || type === "Milliy Sertifikat") rows.push({ label: tt("admin.results.score", "Ball"), value: item.score_text });
    if (isUniversity) {
      rows.push(
        { label: tt("admin.results.universityName", "Universitet nomi"), value: item.university_name },
        {
          label: tt("admin.results.universityScope", "Universitet turi"),
          value: String(item.university_scope || "").trim() === "local"
            ? tt("admin.results.scope.local", "Local universitet")
            : tt("admin.results.scope.foreign", "Chet el universiteti"),
        },
        { label: tt("admin.results.universityCountry", "Davlat"), value: item.university_country },
        { label: tt("admin.results.universityCity", "Shahar"), value: item.university_city },
        { label: tt("admin.results.grantPercent", "Grant foizi"), value: formatGrantPercent(item.grant_percent) || tt("public.results.notEntered", "Kiritilmagan") },
      );
    }
    return rows.filter((row) => String(row.value || "").trim());
  }, [displayDate, item, isUniversity, localizedSubject, tt, type]);

  function goToMedia(direction: -1 | 1) {
    if (galleryMedia.length <= 1) return;
    setActiveMediaIndex((current) => (Math.min(current, galleryMedia.length - 1) + direction + galleryMedia.length) % galleryMedia.length);
  }

  return (
    <PublicShell
      activeTab="results"
      kicker={tt("public.results.detailKicker", "Natija tafsiloti")}
      title={item?.student_name || tt("public.results.detailTitle", "Natija tafsiloti")}
      subtitle={tt("public.results.detailSubtitle", "Talabaning erishgan yutug'i haqida batafsil ma'lumot.")}
      action={
        <Link className="px-6 py-2.5 bg-white dark:bg-gray-800 text-gray-900 dark:text-white border-2 border-gray-200 dark:border-gray-700 font-bold rounded-xl hover:border-blue-600 dark:hover:border-blue-500 hover:text-blue-600 dark:hover:text-blue-400 transition-colors flex items-center gap-2" href="/results">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
          {tt("public.results.back", "Natijalarga qaytish")}
        </Link>
      }
    >
      {error ? (
        <div className="p-6 bg-red-50 border border-red-200 text-red-600 rounded-2xl mb-8 font-semibold">
          {error}
        </div>
      ) : null}
      
      {loading ? <PublicDetailSkeleton /> : null}

      {!loading && !error && !item ? (
        <div className="w-full py-24 bg-white dark:bg-gray-800 rounded-3xl border border-gray-200 dark:border-gray-700 flex flex-col items-center justify-center text-center shadow-sm">
          <span className="text-6xl mb-6 opacity-30">🔍</span>
          <p className="text-2xl font-black text-gray-400 dark:text-gray-500 mb-6">{tt("public.results.notFound", "Natija topilmadi yoki chop etilmagan.")}</p>
          <Link className="px-6 py-3 bg-blue-600 text-white font-bold rounded-xl shadow-lg hover:bg-blue-700 transition-colors" href="/results">{tt("public.results.back", "Natijalarga qaytish")}</Link>
        </div>
      ) : null}

      {item ? (
        <div className="max-w-6xl mx-auto flex flex-col gap-8 md:gap-12 pb-16">
          <div className="flex flex-col lg:flex-row items-start gap-8 md:gap-12">
            {/* Main Media Section */}
            <div className="w-full lg:w-1/2">
              <div className="rounded-[1.5rem] md:rounded-[2rem] overflow-hidden shadow-2xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900">
                <div className="relative bg-gray-50 dark:bg-gray-950">
                  {activeMedia ? (
                    activeMediaIsVideo ? (
                      <video
                        className="w-full h-auto max-h-[58svh] lg:max-h-[calc(100svh-8rem)] block bg-black object-contain"
                        src={toAssetUrl(activeMedia)}
                        controls
                        playsInline
                        preload="metadata"
                      />
                    ) : (
                      <button
                        type="button"
                        className="block w-full cursor-zoom-in bg-white dark:bg-gray-950"
                        onClick={() => setPreviewOpen(true)}
                        aria-label={tt("public.results.openImage", "Rasmni kattalashtirib ochish")}
                      >
                        <img
                          className="w-full max-h-[58svh] lg:max-h-[calc(100svh-8rem)] object-contain block"
                          src={toAssetUrl(activeMedia)}
                          alt={item.student_name || tt("public.results.result", "Natija")}
                        />
                      </button>
                    )
                  ) : (
                    <div className="w-full aspect-[3/4] flex flex-col items-center justify-center text-gray-400 bg-gray-100 dark:bg-gray-800">
                      <span className="text-sm font-bold uppercase tracking-widest text-gray-400">{tt("public.results.noMedia", "Media yo'q")}</span>
                    </div>
                  )}

                  {galleryMedia.length > 1 ? (
                    <>
                      <button
                        type="button"
                        className="absolute left-3 top-1/2 -translate-y-1/2 h-10 w-10 rounded-full bg-white/90 text-gray-900 shadow-lg flex items-center justify-center hover:bg-white transition-colors"
                        onClick={() => goToMedia(-1)}
                        aria-label={tt("public.results.prevMedia", "Oldingi rasm")}
                      >
                        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7" /></svg>
                      </button>
                      <button
                        type="button"
                        className="absolute right-3 top-1/2 -translate-y-1/2 h-10 w-10 rounded-full bg-white/90 text-gray-900 shadow-lg flex items-center justify-center hover:bg-white transition-colors"
                        onClick={() => goToMedia(1)}
                        aria-label={tt("public.results.nextMedia", "Keyingi rasm")}
                      >
                        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" /></svg>
                      </button>
                      <div className="absolute bottom-3 left-0 right-0 flex justify-center gap-1.5 pointer-events-none">
                        {galleryMedia.map((entry, idx) => (
                          <span
                            key={`result-dot-${entry}-${idx}`}
                            className={`h-1.5 rounded-full transition-all ${idx === safeActiveMediaIndex ? "w-5 bg-blue-600" : "w-1.5 bg-white/80 shadow"}`}
                          />
                        ))}
                      </div>
                    </>
                  ) : null}
                </div>

                {galleryMedia.length > 1 ? (
                  <div className="flex gap-2 overflow-x-auto p-3 bg-white dark:bg-gray-900 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
                    {galleryMedia.map((entry, idx) => {
                      const isVideo = isResultVideoUrl(entry);
                      const active = idx === safeActiveMediaIndex;
                      return (
                        <button
                          type="button"
                          key={`result-thumb-${entry}-${idx}`}
                          className={`relative h-16 w-12 md:h-20 md:w-16 shrink-0 rounded-xl border-2 overflow-hidden bg-gray-100 dark:bg-gray-800 transition-colors ${active ? "border-blue-600" : "border-transparent hover:border-gray-300"}`}
                          onClick={() => setActiveMediaIndex(idx)}
                          aria-label={tt("public.results.mediaNumber", "Media {number}", { number: idx + 1 })}
                        >
                          {isVideo ? (
                            <video className="h-full w-full object-cover" src={`${toAssetUrl(entry)}#t=0.001`} muted playsInline preload="metadata" />
                          ) : (
                            <img className="h-full w-full object-cover" src={toAssetUrl(entry)} alt={`${item.student_name || tt("public.results.result", "Natija")} ${idx + 1}`} loading="lazy" />
                          )}
                        </button>
                      );
                    })}
                  </div>
                ) : null}
              </div>
          </div>

            {/* Details Card */}
          <div className="w-full lg:w-1/2 flex flex-col gap-8">
            <div className="bg-white dark:bg-gray-800 rounded-[2rem] p-8 md:p-10 shadow-xl border border-gray-100 dark:border-gray-700">
            {!isUniversity ? (
              <div className="flex flex-wrap items-center justify-between gap-4 mb-8 pb-8 border-b border-gray-100 dark:border-gray-700">
                <div className="flex items-center gap-3">
                  <span className="px-4 py-1.5 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-bold uppercase tracking-wider rounded-lg text-sm">
                    {tt(`admin.results.type.${item.result_type || ""}`, item.result_type || tt("public.results.result", "Natija"))}
                  </span>
                  {subject ? (
                    <span className="px-4 py-1.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-bold rounded-lg text-sm">
                      {localizedSubject || subject}
                    </span>
                  ) : null}
                </div>
                <div className="flex items-center gap-2 text-gray-500 font-medium">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                  {displayDate}
                </div>
              </div>
            ) : null}

            <div className="flex flex-col gap-10">
              <div>
                <h1 className="text-4xl md:text-5xl font-black text-gray-900 dark:text-white tracking-tight mb-4">
                  {item.student_name || tt("common.student", "Talaba")}
                </h1>
                
                {!isUniversity ? (
                  <div className="mt-8 p-6 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-2xl border border-blue-100 dark:border-blue-800/30">
                    <p className="text-sm font-bold text-blue-600 dark:text-blue-400 uppercase tracking-widest mb-2">{tt("public.results.overallResult", "Umumiy natija")}</p>
                    <p className="text-4xl font-black text-gray-900 dark:text-white">{localizedMetric}</p>
                  </div>
                ) : null}
              </div>

              <div>
                <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4">{tt("public.results.details", "Tafsilotlar")}</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-8">
                  {detailRows.map((row) => (
                    <div key={row.label} className="rounded-2xl border border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/60 p-4">
                      <p className="text-xs font-black uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-1">{row.label}</p>
                      <p className="text-base font-bold text-gray-900 dark:text-white">{row.value}</p>
                    </div>
                  ))}
                </div>
                <p className="text-gray-600 dark:text-gray-400 leading-relaxed text-lg mb-8">
                  {item.description || tt("public.results.noDescription", "Qo'shimcha tavsif kiritilmagan.")}
                </p>
              </div>
            </div>
          </div>
          </div>
          </div>
        </div>
      ) : null}
      {previewOpen && activeMedia && !activeMediaIsVideo ? (
        <div className="fixed inset-0 z-[9999] bg-black/90 p-4 md:p-8 flex items-center justify-center" onClick={() => setPreviewOpen(false)}>
          <button
            type="button"
            className="absolute right-4 top-4 h-11 w-11 rounded-full bg-white/10 text-white flex items-center justify-center hover:bg-white/20 transition-colors"
            onClick={() => setPreviewOpen(false)}
            aria-label={tt("common.close", "Yopish")}
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
          <img
            className="max-h-full max-w-full object-contain"
            src={toAssetUrl(activeMedia)}
            alt={item?.student_name || tt("public.results.result", "Natija")}
            onClick={(event) => event.stopPropagation()}
          />
        </div>
      ) : null}
    </PublicShell>
  );
}
