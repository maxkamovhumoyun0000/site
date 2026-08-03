"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { PublicShell } from "../public-shell";
import { fetchPublicVideos, API_BASE, GenericRow } from "../public-data";
import { PublicListSkeleton } from "../public-skeletons";
import { useWebT } from "../ui/web-i18n";

function formatViews(views: number | undefined | null, tt: any) {
  if (!views) return tt("videos.views.zero", "0 ko'rish");
  if (views >= 1000000) return (views / 1000000).toFixed(1) + tt("videos.views.million", " mln ko'rish");
  if (views >= 1000) return (views / 1000).toFixed(1) + tt("videos.views.thousand", " ming ko'rish");
  return views.toString() + " " + tt("videos.views.plural", "ko'rish");
}

function VideoCard({ video, onVideoClick }: { video: GenericRow; onVideoClick?: () => void }) {
  const tt = useWebT();
  const subject = String(video.subject || "").trim();
  const subjectLabel = subject ? tt(`public.subject.${subject}`, subject) : tt("common.general", "Umumiy");
  return (
    <div
      className="group relative flex flex-col bg-white border border-line rounded-2xl shadow-premium overflow-hidden transition-all duration-300 hover:-translate-y-1 cursor-pointer w-full"
      onClick={(e) => {
        if (onVideoClick) {
          e.preventDefault();
          onVideoClick();
        }
      }}
    >
      <div className="relative aspect-video bg-surface-soft overflow-hidden">
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/40 backdrop-blur-[2px]">
          <svg className="w-10 h-10 text-white drop-shadow-md" fill="currentColor" viewBox="0 0 24 24"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/></svg>
        </div>
        {video.thumbnail_url ? (
          <img
            src={String(video.thumbnail_url).startsWith("/") ? `${API_BASE}${video.thumbnail_url}` : String(video.thumbnail_url)}
            alt={video.title || tt("videos.defaultTitle", "Video dars")}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-surface-soft to-line">
            <span className="text-3xl opacity-20">▶️</span>
          </div>
        )}
        <div className="absolute inset-0 flex items-center justify-center bg-black/10 group-hover:bg-black/30 transition-colors">
          <span className="w-12 h-12 flex items-center justify-center bg-white/30 backdrop-blur-md rounded-full shadow-lg text-white border border-white/50 group-hover:scale-110 transition-transform">
            <svg className="w-5 h-5 ml-1" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
          </span>
        </div>
        <span className="absolute bottom-2 right-2 bg-black/70 text-white text-[10px] font-bold px-2 py-0.5 rounded">
          {video.duration || "0:00"}
        </span>
        <span className="absolute bottom-2 left-2 bg-cyan-500/90 text-white text-[10px] font-bold px-2 py-0.5 rounded backdrop-blur-md">
          {subjectLabel}
        </span>
      </div>
      <div className="p-3 sm:p-4 flex-grow flex flex-col bg-white">
        <h3 className="font-display font-bold text-sm sm:text-base text-navy-900 mb-1 line-clamp-2 group-hover:text-cyan-500 transition-colors">
          {video.title || tt("videos.defaultTitle", "Video dars")}
        </h3>
        <p className="text-xs sm:text-sm font-medium text-ink-600 line-clamp-2 mb-2 flex-grow leading-relaxed">
          {video.description || "—"}
        </p>
        <div className="mt-auto flex items-center justify-between text-xs font-semibold text-gray-500">
          <span>{formatViews(video.view_count, tt)}</span>
        </div>
      </div>
    </div>
  );
}

function VideosCategoryBlock({
  title,
  subtitle,
  items,
  onVideoClick,
}: {
  title: string;
  subtitle?: string;
  items: GenericRow[];
  onVideoClick?: () => void;
}) {
  const tt = useWebT();
  const [visibleRows, setVisibleRows] = useState(2);
  // Default to 4 columns on large screens
  const cols = 4;
  
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
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-6">
            {visibleItems.map((item, idx) => (
              <VideoCard video={item} key={`video-${item.id || idx}`} onVideoClick={onVideoClick} />
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
          <span className="text-4xl mb-4 opacity-50">▶️</span>
          <p className="text-lg font-bold text-gray-400 dark:text-gray-500">{tt("videos.emptyCategory", "Bu kategoriya bo'yicha videolar topilmadi.")}</p>
        </div>
      )}
    </section>
  );
}

export default function VideosPage() {
  const tt = useWebT();
  const [items, setItems] = useState<GenericRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const rows = await fetchPublicVideos(300);
        if (!cancelled) setItems(rows);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : tt("videos.loadError", "Videolarni yuklab bo'lmadi"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [tt]);

  const englishVideos = useMemo(() => {
    return items.filter(v => ["English", "General English", "IELTS", "CEFR"].includes(String(v.subject || "").trim()) || !v.subject);
  }, [items]);

  const russianVideos = useMemo(() => {
    return items.filter(v => ["Rus tili", "Russian", "Russian Track"].includes(String(v.subject || "").trim()));
  }, [items]);

  const [activeTab, setActiveTab] = useState<"all" | "english" | "russian">("all");
  const [videoLockPopup, setVideoLockPopup] = useState(false);

  return (
    <PublicShell
      activeTab="videos"
      kicker={tt("landing.videos.kicker", "Bepul Video Darslar")}
      title={tt("landing.videos.pageTitle", "Platformamizdagi Video Darslar")}
      subtitle={tt("landing.videos.pageSubtitle", "Tajribali mentorlar tomonidan maxsus tayyorlangan video darsliklar va onlayn materiallar bilan ta'lim oling.")}
    >
      {error ? (
        <div className="p-6 bg-red-50 border border-red-200 text-red-600 rounded-2xl mb-8 font-semibold">
          {error}
        </div>
      ) : null}
      
      <div className="flex items-center gap-2 mb-12 bg-gray-100/50 dark:bg-gray-800/50 p-1.5 rounded-xl w-fit">
        <button 
          onClick={() => setActiveTab("all")}
          className={`px-6 py-2.5 rounded-lg text-sm font-bold transition-all ${activeTab === "all" ? "bg-white dark:bg-gray-700 shadow-sm text-blue-600 dark:text-blue-400" : "text-gray-500 hover:text-gray-900 dark:hover:text-white"}`}
        >
          {tt("videos.tabs.all", "Barcha Videolar")}
        </button>
        <button 
          onClick={() => setActiveTab("english")}
          className={`px-6 py-2.5 rounded-lg text-sm font-bold transition-all ${activeTab === "english" ? "bg-white dark:bg-gray-700 shadow-sm text-blue-600 dark:text-blue-400" : "text-gray-500 hover:text-gray-900 dark:hover:text-white"}`}
        >
          {tt("videos.tabs.english", "Ingliz Tili")}
        </button>
        <button 
          onClick={() => setActiveTab("russian")}
          className={`px-6 py-2.5 rounded-lg text-sm font-bold transition-all ${activeTab === "russian" ? "bg-white dark:bg-gray-700 shadow-sm text-blue-600 dark:text-blue-400" : "text-gray-500 hover:text-gray-900 dark:hover:text-white"}`}
        >
          {tt("videos.tabs.russian", "Rus Tili")}
        </button>
      </div>

      {loading ? <PublicListSkeleton count={8} /> : null}
      
      {!loading && !error && !items.length ? (
        <div className="w-full py-24 bg-white dark:bg-gray-800 rounded-3xl border border-gray-200 dark:border-gray-700 flex flex-col items-center justify-center text-center shadow-sm">
          <span className="text-6xl mb-6 opacity-30">▶️</span>
          <p className="text-2xl font-black text-gray-400 dark:text-gray-500">{tt("videos.empty", "Video darslar topilmadi.")}</p>
        </div>
      ) : null}

      {!loading && items.length ? (
        <div className="flex flex-col gap-8">
          {(activeTab === "all" || activeTab === "english") && (englishVideos.length > 0 || activeTab === "english") ? (
            <VideosCategoryBlock
              title={tt("videos.categories.english.title", "Ingliz Tili Darslari")}
              subtitle={tt("videos.categories.english.subtitle", "General English, IELTS va grammatika bo'yicha video darslar")}
              items={englishVideos}
              onVideoClick={() => setVideoLockPopup(true)}
            />
          ) : null}
          {(activeTab === "all" || activeTab === "russian") && (russianVideos.length > 0 || activeTab === "russian") ? (
            <VideosCategoryBlock
              title={tt("videos.categories.russian.title", "Rus Tili Darslari")}
              subtitle={tt("videos.categories.russian.subtitle", "Rus tilida muloqot va grammatika qoidalari")}
              items={russianVideos}
              onVideoClick={() => setVideoLockPopup(true)}
            />
          ) : null}
        </div>
      ) : null}

      {/* ── VIDEO LOCK POPUP ───────────────────────────────────────── */}
      {videoLockPopup && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-navy-900 rounded-2xl shadow-2xl max-w-md w-full p-6 text-center animate-in fade-in zoom-in-95 relative">
            <button 
              onClick={() => setVideoLockPopup(false)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 24 24">
                <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/>
              </svg>
            </div>
            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
              {tt("landing.videos.lockTitle", "Yopiq kontent")}
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              {tt("landing.videos.lockMessage", "Bizning o'quv markazimizda tahsil oling va bepul video darslar hamda ko'plab qo'shimcha o'quv materiallariga ega bo'ling.")}
            </p>
            <div className="flex justify-center">
              <Link
                href="/#courses"
                onClick={() => {
                  setVideoLockPopup(false);
                }}
                className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl shadow-lg shadow-blue-600/20 transition-all hover:-translate-y-0.5 active:translate-y-0 flex items-center gap-2"
              >
                <span>{tt("landing.videos.lockAction", "Kurslarni ko'rish")}</span>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              </Link>
            </div>
          </div>
        </div>
      )}
    </PublicShell>
  );
}
