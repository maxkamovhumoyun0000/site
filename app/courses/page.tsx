"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { PublicShell } from "../public-shell";
import { PublicCourse, cutText, fetchPublicCourses, toAssetUrl, getCourseGroups } from "../public-data";
import { PublicListSkeleton } from "../public-skeletons";
import { SubjectCoursesGrid } from "../ui/subject-courses-grid";
import { useWebLocale, useWebT } from "../ui/web-i18n";

export default function CoursesPage() {
  const [items, setItems] = useState<PublicCourse[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const deferred = useDeferredValue(query);
  const [activeSubject, setActiveSubject] = useState("Barchasi");
  const tt = useWebT();
  const locale = useWebLocale();

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const rows = await fetchPublicCourses(300, locale);
        if (!cancelled) setItems(rows);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : tt("courses.page.loadError", "Kurslarni yuklab bo'lmadi"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [locale, tt]);

  const availableSubjects = useMemo(() => {
    const subs = new Set<string>();
    items.forEach(c => {
      const s = String(c.subject || "Boshqa fanlar").trim();
      if (s) subs.add(s);
    });
    return ["Barchasi", ...Array.from(subs).sort()];
  }, [items]);

  const filteredGroups = useMemo(() => {
    const key = deferred.trim().toLowerCase();
    let result = items;
    if (activeSubject !== "Barchasi") {
      result = result.filter(item => String(item.subject || "Boshqa fanlar").trim() === activeSubject);
    }
    if (key) {
      result = result.filter((item) => `${item.title || ""} ${item.description || ""} ${item.subject || ""}`.toLowerCase().includes(key));
    }
    return getCourseGroups(result);
  }, [items, deferred, activeSubject]);

  function subjectLabel(subject: string) {
    if (subject === "Barchasi") return tt("common.all", "Barchasi");
    return tt(`public.subject.${subject}`, subject);
  }

  return (
    <PublicShell
      activeTab="courses"
      kicker={tt("courses.page.kicker", "Ochiq kurslar")}
      title={tt("courses.page.title", "O'zingizga mos o'quv yo'nalishini tanlang")}
      subtitle={tt("courses.page.subtitle", "Eng yaxshi ustozlar bilan birga o'z kelajagingizni quring. Barcha kurslar xalqaro standartlarga moslashtirilgan.")}
    >
      <div className="max-w-2xl mx-auto mb-12 relative z-10">
        <div className="relative group">
          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
            <svg className="h-6 w-6 text-gray-400 group-focus-within:text-blue-500 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            className="w-full bg-white dark:bg-gray-800 text-gray-900 dark:text-white border-2 border-gray-200 dark:border-gray-700 rounded-2xl py-4 pl-12 pr-4 shadow-sm focus:outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 transition-all text-lg font-medium"
            placeholder={tt("courses.page.searchPlaceholder", "Kurs nomi yoki mavzu bo'yicha qidiring...")}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
      </div>

      {!loading && !error && availableSubjects.length > 1 ? (
        <div className="flex flex-wrap items-center justify-center gap-3 mb-12 relative z-10">
          {availableSubjects.map((sub) => (
            <button
              key={`sub-tab-${sub}`}
              onClick={() => setActiveSubject(sub)}
              className={`px-5 py-2.5 rounded-2xl text-sm font-bold transition-all duration-300 ${
                activeSubject === sub 
                  ? "bg-blue-600 text-white shadow-lg shadow-blue-600/30 -translate-y-0.5" 
                  : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 hover:border-gray-300 dark:hover:border-gray-600"
              }`}
            >
              {subjectLabel(sub)}
            </button>
          ))}
        </div>
      ) : null}

      {error ? (
        <div className="p-6 bg-red-50 border border-red-200 text-red-600 rounded-2xl mb-8 font-semibold">
          {error}
        </div>
      ) : null}
      
      {loading ? <PublicListSkeleton count={6} /> : null}
      
      {!loading && !error && !filteredGroups.length ? (
        <div className="w-full py-24 bg-white dark:bg-gray-800 rounded-3xl border border-gray-200 dark:border-gray-700 flex flex-col items-center justify-center text-center shadow-sm">
          <span className="text-6xl mb-6 opacity-30">📚</span>
          <p className="text-2xl font-black text-gray-400 dark:text-gray-500">{tt("courses.page.empty", "Kurslar topilmadi.")}</p>
        </div>
      ) : null}

      {!loading && filteredGroups.length ? (
        <div className="flex flex-col gap-8">
          {filteredGroups.map((group) => (
            <SubjectCoursesGrid key={`page-${group.id}`} group={group} />
          ))}
        </div>
      ) : null}
    </PublicShell>
  );
}
