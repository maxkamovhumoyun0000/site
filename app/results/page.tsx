"use client";

import { useEffect, useMemo, useState } from "react";
import { PublicShell } from "../public-shell";
import { PublicResult, fetchPublicResults } from "../public-data";
import { PublicListSkeleton } from "../public-skeletons";
import { NATIONAL_CERTIFICATE_SUBJECTS, ResultCard } from "../ui/result-card";
import { useWebT } from "../ui/web-i18n";

const RESULT_CATEGORY_META = [
  { type: "IELTS", titleKey: "results.category.ielts.title", subtitleKey: "results.category.ielts.subtitle", title: "IELTS", subtitle: "Xalqaro IELTS sertifikatlari va band natijalari." },
  { type: "CEFR", titleKey: "results.category.cefr.title", subtitleKey: "results.category.cefr.subtitle", title: "CEFR", subtitle: "CEFR bo'yicha tasdiqlangan natijalar." },
  { type: "Milliy Sertifikat", titleKey: "results.category.national.title", subtitleKey: "results.category.national.subtitle", title: "Milliy Sertifikat", subtitle: "Fanlar bo'yicha milliy sertifikat natijalari." },
  { type: "Rus tili", titleKey: "results.category.russian.title", subtitleKey: "results.category.russian.subtitle", title: "Rus tili", subtitle: "Rus tili bo'yicha talaba video natijalari." },
  { type: "Universitet", titleKey: "results.category.university.title", subtitleKey: "results.category.university.subtitle", title: "Universitet", subtitle: "Universitetga qabul va grant natijalari." },
];

const CEFR_RANK: Record<string, number> = { A1: 1, A2: 2, B1: 3, B2: 4, C1: 5, C2: 6 };

function firstNumeric(value?: string | null) {
  const raw = String(value || "").replace(",", ".");
  const match = raw.match(/\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : 0;
}

function dateRank(item: PublicResult) {
  const raw = String(item.exam_date || item.updated_at || item.created_at || "");
  const stamp = Date.parse(raw);
  return Number.isFinite(stamp) ? stamp : 0;
}

function resultRankValue(item: PublicResult) {
  const type = String(item.result_type || "").trim();
  if (type === "IELTS") return firstNumeric(item.score_text);
  if (type === "CEFR") return firstNumeric(item.score_text) || CEFR_RANK[String(item.score_text || "").trim().toUpperCase()] || 0;
  if (type === "Milliy Sertifikat") return firstNumeric(item.score_text);
  return 0;
}

function sortResultsByRank(rows: PublicResult[]) {
  return [...rows].sort((a, b) => {
    const rankDiff = resultRankValue(b) - resultRankValue(a);
    if (rankDiff) return rankDiff;
    const dateDiff = dateRank(b) - dateRank(a);
    if (dateDiff) return dateDiff;
    return Number(b.id || 0) - Number(a.id || 0);
  });
}

function useResponsiveCols() {
  const [cols, setCols] = useState(5);
  useEffect(() => {
    const check = () => {
      const w = window.innerWidth;
      if (w >= 1536) setCols(5);
      else if (w >= 1280) setCols(4);
      else if (w >= 768) setCols(3);
      else setCols(2);
    };
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);
  return cols;
}

function ResultsCategoryBlock({
  title,
  subtitle,
  items,
}: {
  title: string;
  subtitle?: string;
  items: PublicResult[];
}) {
  const tt = useWebT();
  const [visibleRows, setVisibleRows] = useState(2);
  const cols = useResponsiveCols();
  
  const visibleItems = items.slice(0, visibleRows * cols);
  const hasMore = visibleItems.length < items.length;

  return (
    <section className="mb-20">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <h2 className="text-3xl md:text-4xl font-black text-gray-900 dark:text-white mb-2">{title}</h2>
          {subtitle && <p className="text-gray-500 dark:text-gray-400">{subtitle}</p>}
        </div>
      </div>
      
      {items.length ? (
        <>
          <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
            {visibleItems.map((item) => (
              <ResultCard item={item} key={`result-card-${title}-${item.id}`} />
            ))}
          </div>
          {hasMore && (
            <div className="mt-8 flex justify-center">
              <button 
                onClick={() => setVisibleRows(r => r + 2)} 
                className="px-6 py-3 bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-900 dark:text-white rounded-xl font-bold transition-colors"
              >
                {tt("common.showMore", "Yana ko'rsatish")}
              </button>
            </div>
          )}
        </>
      ) : (
        <div className="w-full py-16 bg-gray-50 dark:bg-gray-800/50 rounded-3xl border border-gray-200 dark:border-gray-700 flex flex-col items-center justify-center text-center px-4">
          <span className="text-4xl mb-4 opacity-50">🔍</span>
          <p className="text-lg font-bold text-gray-400 dark:text-gray-500">{tt("results.category.empty", "Bu kategoriya bo'yicha natijalar topilmadi.")}</p>
        </div>
      )}
    </section>
  );
}

function NationalGroupBlock({ group }: { group: { subject: string; items: PublicResult[] } }) {
  const tt = useWebT();
  const [visibleRows, setVisibleRows] = useState(2);
  const cols = useResponsiveCols();
  
  const visibleItems = group.items.slice(0, visibleRows * cols);
  const hasMore = visibleItems.length < group.items.length;

  return (
    <div className="bg-white dark:bg-gray-800/30 rounded-3xl p-6 md:p-8 border border-gray-100 dark:border-gray-700/50">
      <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-6 flex items-center gap-3">
        <span className="w-2 h-8 bg-blue-500 rounded-full"></span>
        {tt(`public.subject.${group.subject}`, group.subject)}
      </h3>
      {group.items.length ? (
        <>
          <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
            {visibleItems.map((item) => (
              <ResultCard item={item} key={`national-${group.subject}-${item.id}`} />
            ))}
          </div>
          {hasMore && (
            <div className="mt-8 flex justify-center">
              <button 
                onClick={() => setVisibleRows(r => r + 2)} 
                className="px-6 py-3 bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-900 dark:text-white rounded-xl font-bold transition-colors"
              >
                {tt("common.showMore", "Yana ko'rsatish")}
              </button>
            </div>
          )}
        </>
      ) : (
        <p className="text-gray-400 font-medium">{tt("results.subject.empty", "Bu fan bo'yicha natijalar topilmadi.")}</p>
      )}
    </div>
  );
}

export default function ResultsPage() {
  const tt = useWebT();
  const [items, setItems] = useState<PublicResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const rows = await fetchPublicResults();
        if (!cancelled) setItems(rows);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : tt("results.page.loadError", "Natijalarni yuklab bo'lmadi"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [tt]);

  const filtered = items;

  const grouped = useMemo(() => {
    return RESULT_CATEGORY_META
      .map((category) => ({
        ...category,
        items: sortResultsByRank(filtered.filter((item) => String(item.result_type || "").trim() === category.type)),
      }))
      .filter((category) => category.items.length > 0);
  }, [filtered]);

  const nationalGroups = useMemo(() => {
    const national = grouped.find((category) => category.type === "Milliy Sertifikat")?.items || [];
    const known = NATIONAL_CERTIFICATE_SUBJECTS.map((subject) => ({
      subject,
      items: sortResultsByRank(national.filter((item) => String(item.subject || "").trim() === subject)),
    }));
    const otherItems = national.filter((item) => {
      const subject = String(item.subject || "").trim();
      return !subject || !NATIONAL_CERTIFICATE_SUBJECTS.includes(subject as any);
    });
    const groups = otherItems.length ? [...known, { subject: "Boshqa fanlar", items: sortResultsByRank(otherItems) }] : known;
    return groups.filter((group) => group.items.length > 0);
  }, [grouped]);

  return (
    <PublicShell
      activeTab="results"
      kicker={tt("results.page.kicker", "Talaba natijalari")}
      title={tt("results.page.title", "Tasdiqlangan yutuqlar")}
      subtitle={tt("results.page.subtitle", "O'quv markazimiz talabalarining barcha yutuqlari va muvaffaqiyat hikoyalari bilan tanishing.")}
    >
      {error ? (
        <div className="p-6 bg-red-50 border border-red-200 text-red-600 rounded-2xl mb-8 font-semibold">
          {error}
        </div>
      ) : null}
      
      {loading ? <PublicListSkeleton count={8} /> : null}
      
      {!loading && !error && !filtered.length ? (
        <div className="w-full py-24 bg-white dark:bg-gray-800 rounded-3xl border border-gray-200 dark:border-gray-700 flex flex-col items-center justify-center text-center shadow-sm">
          <span className="text-6xl mb-6 opacity-30">🏆</span>
          <p className="text-2xl font-black text-gray-400 dark:text-gray-500">{tt("results.page.empty", "Ochiq natijalar topilmadi.")}</p>
        </div>
      ) : null}

      {!loading && filtered.length ? (
        <div className="flex flex-col gap-8 md:gap-16">
          {grouped.map((category) => (
            category.type === "Milliy Sertifikat" ? (
              <section className="mb-20" key={category.type}>
                <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
                  <div>
                    <h2 className="text-3xl md:text-4xl font-black text-gray-900 dark:text-white mb-2">{tt(category.titleKey, category.title)}</h2>
                  </div>
                </div>

                <div className="flex flex-col gap-12">
                  {nationalGroups.map((group) => (
                    <NationalGroupBlock key={`national-${group.subject}`} group={group} />
                  ))}
                </div>
              </section>
            ) : (
              <ResultsCategoryBlock
                key={category.type}
                title={tt(category.titleKey, category.title)}
                subtitle={tt(category.subtitleKey, category.subtitle)}
                items={category.items}
              />
            )
          ))}
        </div>
      ) : null}
    </PublicShell>
  );
}
