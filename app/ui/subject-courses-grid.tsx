"use client";

import { useState } from "react";
import { PublicCourseGroup, cutText, toAssetUrl } from "../public-data";
import { useWebT, useWebLocale } from "./web-i18n";

function formatPrice(priceText?: string | null): string {
  const trimmed = String(priceText || "").trim();
  if (!trimmed) return "";
  // Pure digits → format with dots: 389000 → 389.000 UZS
  if (/^\d+$/.test(trimmed)) {
    return trimmed.replace(/\B(?=(\d{3})+(?!\d))/g, ".") + " UZS";
  }
  // Already has currency label → just reformat digits inside
  const withDots = trimmed.replace(/(\d+)/g, (m) =>
    m.length > 3 ? m.replace(/\B(?=(\d{3})+(?!\d))/g, ".") : m
  );
  return withDots;
}

export function SubjectCoursesGrid({ group }: { group: PublicCourseGroup }) {
  const [expanded, setExpanded] = useState(false);
  const tt = useWebT();
  const locale = useWebLocale();

  const total = group.items.length;
  
  // We want to show a base limit of 10 items (2 rows of 5 on desktop).
  // On mobile (cols-2), it will naturally show 2 rows if limit is 4, but 
  // CSS can't easily restrict the DOM nodes per viewport without JS.
  // Using 10 as a safe default that fills 2 rows on desktop. 
  // Alternatively, we just slice the array based on state.
  const limit = expanded ? total : 10;
  const visibleItems = group.items.slice(0, limit);
  const hasMore = total > 10;

  if (total === 0) return null;

  return (
    <div className="bg-white dark:bg-gray-800/30 rounded-3xl p-6 md:p-8 border border-gray-100 dark:border-gray-700/50">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <h3 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-3">
          <span className="w-2 h-8 bg-blue-500 rounded-full"></span>
          {tt(`public.subject.${group.title}`, group.title)}
        </h3>
        <p className="text-sm font-semibold text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 px-3 py-1.5 rounded-xl">
          {total} {tt("landing.courses.courseCount", "ta kurs")}
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 md:gap-6">
        {visibleItems.map((course: any) => {
          const localizedTitle = course[`title_${locale}`] || course.title || "Kurs";
          const localizedDesc = course[`description_${locale}`] || course.description || "-";
          return (
          <a
            className="group flex flex-col bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-3xl overflow-hidden shadow-md hover:shadow-2xl transition-all duration-300 hover:-translate-y-2 cursor-pointer"
            href={`/courses/${course.id}`}
            key={`course-${course.id}`}
          >
            <div className="relative aspect-square overflow-hidden bg-gray-100 dark:bg-gray-900">
              {course.cover_image_url ? (
                <img
                  className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                  src={toAssetUrl(course.cover_image_url)}
                  alt={localizedTitle}
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-gray-800 dark:to-gray-900">
                  <span className="text-6xl opacity-20 transition-transform duration-700 group-hover:scale-110 group-hover:rotate-6">📚</span>
                </div>
              )}
              
              {/* Overlay gradient */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
            </div>
            
            <div className="p-4 flex-grow flex flex-col bg-white dark:bg-gray-800">
              <h3 className="text-base font-black text-gray-900 dark:text-white mb-1.5 line-clamp-2 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                {localizedTitle}
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2 mb-3 flex-grow leading-relaxed">
                {cutText(localizedDesc, 100)}
              </p>
              <div className="flex items-end justify-end mt-auto pt-2">
                <span className="w-7 h-7 rounded-full bg-blue-50 dark:bg-gray-700 flex items-center justify-center text-blue-600 dark:text-blue-400 group-hover:bg-blue-600 group-hover:text-white transition-colors shrink-0">
                  <svg className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
                </span>
              </div>
            </div>
          </a>
        )})}
      </div>

      {hasMore && !expanded && (
        <div className="mt-8 flex justify-center">
          <button
            onClick={() => setExpanded(true)}
            className="px-6 py-3 bg-white dark:bg-gray-800 border-2 border-gray-100 dark:border-gray-700 rounded-2xl shadow-sm text-sm font-bold text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 hover:border-blue-100 dark:hover:border-blue-900/50 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all active:scale-95"
          >
            {tt("landing.courses.showMore", "Yana ko'rsatish")} ↓
          </button>
        </div>
      )}
      
      {hasMore && expanded && (
        <div className="mt-8 flex justify-center">
          <button
            onClick={() => setExpanded(false)}
            className="px-6 py-3 bg-white dark:bg-gray-800 border-2 border-gray-100 dark:border-gray-700 rounded-2xl shadow-sm text-sm font-bold text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 hover:border-blue-100 dark:hover:border-blue-900/50 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all active:scale-95"
          >
            {tt("landing.courses.showLess", "Yopish")} ↑
          </button>
        </div>
      )}
    </div>
  );
}
