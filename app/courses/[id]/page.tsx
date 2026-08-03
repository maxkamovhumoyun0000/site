"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { PublicShell } from "../../public-shell";
import { PublicCourse, fetchPublicCourses, toAssetUrl } from "../../public-data";
import { PublicDetailSkeleton } from "../../public-skeletons";
import { useWebLocale, useWebT } from "../../ui/web-i18n";

function formatPrice(priceText: string, freeLabel: string) {
  const trimmed = String(priceText || "").trim();
  if (!trimmed) return freeLabel;
  if (/^\d+$/.test(trimmed)) {
    const formatted = trimmed.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return `${formatted} UZS`;
  }
  if (trimmed.toLowerCase().includes("uzs") || trimmed.toLowerCase().includes("so'm") || trimmed.toLowerCase().includes("som")) {
    // Reformat existing numbers inside the string
    return trimmed.replace(/(\d+)/g, (m) =>
      m.length > 3 ? m.replace(/\B(?=(\d{3})+(?!\d))/g, ".") : m
    );
  }
  if (/\d/.test(trimmed)) {
    return `${trimmed.replace(/(\d+)/g, (m) => m.length > 3 ? m.replace(/\B(?=(\d{3})+(?!\d))/g, ".") : m)} UZS`;
  }
  return trimmed;
}

export default function CourseDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params?.id || 0);
  const [items, setItems] = useState<PublicCourse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const locale = useWebLocale();
  const tt = useWebT();

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const rows = await fetchPublicCourses(300, locale);
        if (!cancelled) setItems(rows);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : tt("courses.detail.loadError", "Kurs ma'lumotlarini yuklab bo'lmadi"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [locale, tt]);

  const item = useMemo(() => items.find((row) => Number(row.id) === id) || null, [items, id]);
  const localizedTitle = item ? String((item as any)[`title_${locale}`] || item.title || "").trim() : "";
  const localizedDescription = item ? String((item as any)[`description_${locale}`] || item.description || "").trim() : "";

  return (
    <PublicShell
      activeTab="courses"
      kicker={tt("courses.detail.kicker", "Kurs tafsiloti")}
      title={localizedTitle || tt("courses.detail.title", "Kurs ma'lumoti")}
      subtitle={tt("courses.detail.subtitle", "Kurs haqida batafsil ma'lumot.")}
      action={
        <Link className="px-6 py-2.5 bg-white dark:bg-gray-800 text-gray-900 dark:text-white border-2 border-gray-200 dark:border-gray-700 font-bold rounded-xl hover:border-blue-600 dark:hover:border-blue-500 hover:text-blue-600 dark:hover:text-blue-400 transition-colors flex items-center gap-2" href="/courses">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
          {tt("courses.detail.back", "Kurslarga qaytish")}
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
          <p className="text-2xl font-black text-gray-400 dark:text-gray-500 mb-6">{tt("courses.detail.notFound", "Kurs topilmadi yoki hali chop etilmagan.")}</p>
          <Link className="px-6 py-3 bg-blue-600 text-white font-bold rounded-xl shadow-lg hover:bg-blue-700 transition-colors" href="/courses">{tt("courses.detail.back", "Kurslarga qaytish")}</Link>
        </div>
      ) : null}

      {item ? (
        <div className="max-w-6xl mx-auto flex flex-col lg:flex-row items-start gap-8 md:gap-12 pb-16">
          <div className="w-full lg:w-1/2 rounded-[2rem] overflow-hidden bg-gray-100 dark:bg-gray-900 shadow-2xl border border-gray-100 dark:border-gray-800 aspect-square sticky top-8">
            {item.cover_image_url ? (
              <img
                className="w-full h-full object-cover"
                src={toAssetUrl(item.cover_image_url)}
                alt={localizedTitle || tt("courses.detail.title", "Kurs ma'lumoti")}
              />
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center text-gray-400 bg-gray-100 dark:bg-gray-800">
                <span className="text-6xl mb-4">📚</span>
                <span className="text-sm font-bold uppercase tracking-widest text-gray-400">{tt("courses.detail.noImage", "Rasm yo'q")}</span>
              </div>
            )}
          </div>

          <div className="w-full lg:w-1/2 bg-white dark:bg-gray-800 rounded-[2rem] p-8 md:p-10 shadow-xl border border-gray-100 dark:border-gray-700">
            <div className="flex flex-wrap items-center justify-between gap-4 mb-8 pb-8 border-b border-gray-100 dark:border-gray-700">
              <span className="px-4 py-1.5 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-bold uppercase tracking-wider rounded-lg text-sm">
                {item.status === "published" ? tt("common.active", "Faol") : (item.status || tt("common.active", "Faol"))}
              </span>
              <div className="flex items-center gap-2">
                <span className="px-5 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-black rounded-xl text-lg shadow-md">
                  {tt("courses.detail.groupPrice", "Guruh")}: {formatPrice(item.price_text || "", tt("courses.detail.free", "Bepul"))}
                </span>
                {(item as any).individual_price_text ? (
                  <span className="px-5 py-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white font-black rounded-xl text-lg shadow-md">
                    {tt("courses.detail.individualPrice", "Individual")}: {formatPrice((item as any).individual_price_text, tt("courses.detail.free", "Bepul"))}
                  </span>
                ) : null}
              </div>
            </div>

            <div className="flex flex-col gap-10">
              <div>
                <h1 className="text-3xl md:text-5xl font-black text-gray-900 dark:text-white tracking-tight mb-8">
                  {localizedTitle || tt("courses.detail.title", "Kurs ma'lumoti")}
                </h1>
                
                <div className="space-y-4">
                  <Link href="/login" className="block w-full py-4 bg-blue-600 text-white text-center text-lg font-bold rounded-xl hover:bg-blue-700 shadow-lg shadow-blue-600/30 hover:-translate-y-1 transition-all">
                    {tt("courses.detail.enroll", "Kursga yozilish")}
                  </Link>
                  <a href="tel:+998977483634" className="block w-full py-4 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white text-center text-lg font-bold rounded-xl hover:bg-gray-100 dark:hover:bg-gray-600 border border-gray-200 dark:border-gray-600 transition-colors">
                    {tt("courses.detail.contactAdmin", "Administrator bilan bog'lanish")}
                  </a>
                </div>
              </div>

              <div>
                <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4">{tt("courses.detail.about", "Kurs haqida")}</h3>
                <div className="prose prose-lg dark:prose-invert text-gray-600 dark:text-gray-400">
                  <p className="leading-relaxed whitespace-pre-wrap">
                    {localizedDescription || tt("public.results.noDescription", "Qo'shimcha tavsif kiritilmagan.")}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </PublicShell>
  );
}
