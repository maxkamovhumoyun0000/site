"use client";

import React, { useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useWebT } from "./web-i18n";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
const VIDEO_LIST_CACHE_TTL_MS = 45_000;
const videoListCache = new Map<string, { payload: any; ts: number }>();

type VideoProgress = {
  watched_seconds: number;
  completed: boolean;
};

type VideoItem = {
  id: number;
  title: string;
  description?: string;
  author?: string;
  category?: string;
  level?: string;
  thumbnail_url?: string;
  duration?: number;
  view_count?: number;
  like_count?: number;
  subject?: string;
  created_at?: string;
  missing_original?: boolean;
  missing_message?: string;
  media_status?: string;
  progress?: VideoProgress | null;
};

export function StudentVideos({ apiFetch, user }: { apiFetch: (path: string, options?: any) => Promise<any>, user?: any }) {
  const tt = useWebT();
  const router = useRouter();
  const pageSize = 20;

  const subjects = React.useMemo<string[]>(() => {
    if (!user || !user.subjects || !Array.isArray(user.subjects)) return [];
    return Array.from(new Set<string>(user.subjects.map((s: any) => String(s || "").trim()).filter(Boolean)));
  }, [user]);

  const [selectedSubject, setSelectedSubject] = React.useState<string>("all");
  const [selectedLevel, setSelectedLevel] = React.useState<string>("all");
  
  const levels = ["Beginner", "A1", "A2", "B1", "B2", "C1", "C2"];

  // Check if there's already cached data so we don't show spinner on back-navigation
  const getInitialState = () => {
    const offset = 0; // page=1
    const cacheKey = `videos:${pageSize}:${offset}:${selectedSubject}:${selectedLevel}`;
    const cached = videoListCache.get(cacheKey);
    if (cached && Date.now() - cached.ts < VIDEO_LIST_CACHE_TTL_MS) {
      return {
        videos: (cached.payload?.items || []) as VideoItem[],
        hasMore: Boolean(cached.payload?.has_more),
        loading: false,
      };
    }
    return { videos: [] as VideoItem[], hasMore: false, loading: true };
  };

  const initial = React.useMemo(getInitialState, [selectedSubject, selectedLevel]);  
  const [videos, setVideos] = React.useState<VideoItem[]>(initial.videos);
  const [page, setPage] = React.useState(1);
  const [hasMore, setHasMore] = React.useState(initial.hasMore);
  const [loading, setLoading] = React.useState(initial.loading);
  const [error, setError] = React.useState("");
  const requestSeqRef = React.useRef(0);
  const abortRef = React.useRef<AbortController | null>(null);

  const fetchVideos = useCallback(async () => {
    const seq = requestSeqRef.current + 1;
    requestSeqRef.current = seq;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setError("");
    const offset = (Math.max(1, page) - 1) * pageSize;
    const subjQuery = selectedSubject && selectedSubject !== "all" ? `&subject=${encodeURIComponent(selectedSubject)}` : "";
    const lvlQuery = selectedLevel && selectedLevel !== "all" ? `&level=${encodeURIComponent(selectedLevel)}` : "";
    const cacheKey = `videos:${pageSize}:${offset}:${selectedSubject}:${selectedLevel}`;
    const cached = videoListCache.get(cacheKey);
    if (cached && Date.now() - cached.ts < VIDEO_LIST_CACHE_TTL_MS) {
      const res = cached.payload || {};
      setVideos(res.items || []);
      setHasMore(Boolean(res.has_more));
      setLoading(false);
    } else {
      setLoading(true);
    }
    try {
      const res = await apiFetch(`/student/videos?limit=${pageSize}&offset=${offset}${subjQuery}${lvlQuery}`, {
        signal: controller.signal,
        timeoutMs: 9000,
        retries: 1,
      });
      if (requestSeqRef.current !== seq || controller.signal.aborted) return;
      videoListCache.set(cacheKey, { payload: res || {}, ts: Date.now() });
      if (res && res.items) {
        setVideos(res.items);
        setHasMore(Boolean(res.has_more));
      }
    } catch (e) {
      if (requestSeqRef.current !== seq || controller.signal.aborted) return;
      if (!cached) setError(e instanceof Error ? e.message : tt("videos.loadError", "Videolarni yuklab bo'lmadi."));
    } finally {
      if (requestSeqRef.current === seq && !controller.signal.aborted) setLoading(false);
    }
  }, [apiFetch, page, selectedSubject, selectedLevel]);

  useEffect(() => {
    setPage(1);
  }, [selectedSubject, selectedLevel]);

  useEffect(() => {
    let mounted = true;
    const timer = window.setTimeout(() => {
      if (!mounted) return;
      fetchVideos().catch(() => null);
    }, 0);
    return () => {
      mounted = false;
      requestSeqRef.current += 1;
      abortRef.current?.abort();
      window.clearTimeout(timer);
    };
  }, [fetchVideos]);

  function mediaUrl(url?: string) {
    const raw = String(url || "").trim();
    if (!raw) return "";
    return raw.startsWith("/") ? `${API_BASE}${raw}` : raw;
  }

  function openVideo(video: VideoItem) {
    const videoId = Number(video?.id || (video as any)?.video_id || 0);
    if (!Number.isInteger(videoId) || videoId <= 0) {
      setError(tt("videos.unavailable", "Video vaqtincha mavjud emas. Iltimos qayta urinib ko'ring."));
      return;
    }
    router.push(`/student/videos/${videoId}`);
  }

  return (
    <div className="student-video-list flex flex-col gap-5 pb-12 animate-fade-in">
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

      {error ? <div className="rounded-xl bg-red-500/10 text-red-500 border border-red-500/20 px-4 py-3 font-semibold text-sm animate-fade-in">{error}</div> : null}

      {loading ? (
        <div className="flex justify-center py-20"><div className="w-12 h-12 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin"></div></div>
      ) : (
        <div className="student-video-grid grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
          {videos.length === 0 ? (
             <div className="col-span-full text-center py-16 text-ink-500 bg-surface-soft border border-line dark:bg-white/5 dark:border-white/10 rounded-[2rem] font-medium text-lg">{tt("videos.empty", "Hozircha videolar mavjud emas")}</div>
          ) : videos.map((v) => (
            <div key={v.id} onClick={() => openVideo(v)} className="group student-video-card media-library-card relative flex flex-col bg-white border border-line dark:bg-navy-900/40 dark:border-white/10 rounded-2xl shadow-premium overflow-hidden transition-all duration-300 hover:-translate-y-1 cursor-pointer">
              <div className="student-video-thumb relative aspect-square bg-surface-soft dark:bg-navy-900 overflow-hidden">
                {v.thumbnail_url ? (
                  <img src={mediaUrl(v.thumbnail_url)} alt={v.title} loading="lazy" decoding="async" className="student-video-thumb-img w-full h-full object-contain bg-white dark:bg-navy-950" />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-surface-soft to-line dark:from-navy-800 dark:to-navy-900">
                    <span className="text-3xl opacity-20">▶️</span>
                  </div>
                )}
                <div className="student-video-play-overlay absolute inset-0 bg-transparent transition-colors duration-300 group-hover:bg-navy-900/20 flex items-center justify-center">
                  <div className="w-10 h-10 bg-white/90 dark:bg-navy-900/90 rounded-full flex items-center justify-center shadow-xl transform scale-90 opacity-0 group-hover:opacity-100 group-hover:scale-100 transition-all duration-300">
                    <svg className="w-5 h-5 text-cyan-500 ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
                  </div>
                </div>
                <div className="absolute bottom-3 right-3 flex items-center gap-2">
                  {v.missing_original ? (
                    <div className="bg-amber-500/90 text-white text-[10px] font-bold px-2.5 py-1 rounded-full backdrop-blur-md shadow-lg">
                      {tt("videos.fileNotFound", "Fayl topilmadi")}
                    </div>
                  ) : null}
                  {Number(v.view_count || 0) > 0 && (
                    <div className="bg-navy-900/80 text-white text-[10px] font-bold px-2.5 py-1 rounded-full backdrop-blur-md shadow-lg flex items-center gap-1">
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                      {v.view_count}
                    </div>
                  )}
                  <div className="bg-navy-900/80 text-white text-[10px] font-bold px-2.5 py-1 rounded-full backdrop-blur-md shadow-lg flex items-center gap-1">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M2 21h4V9H2v12Zm20-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L13.17 1 6.59 7.59C6.22 7.95 6 8.45 6 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-2Z" /></svg>
                    {Number(v.like_count || 0)}
                  </div>
                  {Number(v.duration || 0) > 0 && (
                    <div className="bg-navy-900/80 text-white text-[10px] font-bold px-2.5 py-1 rounded-full backdrop-blur-md shadow-lg tracking-wider">
                      {Math.floor(Number(v.duration || 0) / 60)}:{(Number(v.duration || 0) % 60).toString().padStart(2, "0")}
                    </div>
                  )}
                </div>
              </div>
              <div className="student-video-card-body p-3 sm:p-4 flex-grow flex flex-col relative z-10 bg-white dark:bg-navy-900/80 border-t border-line dark:border-white/10 transition-transform duration-300">
                <div className="flex items-center gap-2 mb-2">
                  <span className="px-2 py-0.5 bg-cyan-50 text-cyan-700 dark:bg-cyan-500/10 dark:text-cyan-300 rounded-lg text-[10px] font-bold uppercase tracking-wider border border-cyan-100 dark:border-cyan-500/20">{v.level || "B1"}</span>
                  <span className="text-[11px] font-bold text-ink-600 dark:text-navy-300 truncate">{v.subject || v.category || "-"}</span>
                </div>
                <h3 className="font-display font-bold text-sm sm:text-base text-navy-900 dark:text-white mb-1 line-clamp-2 group-hover:text-cyan-500 transition-colors">{v.title}</h3>
                <p className="text-xs sm:text-sm font-medium text-ink-600 dark:text-navy-300 line-clamp-2 mb-3 flex-grow leading-relaxed">{v.description}</p>
                {v.missing_original ? (
                  <p className="mb-3 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-[11px] font-bold text-amber-800 dark:border-amber-400/30 dark:bg-amber-500/10 dark:text-amber-100">
                    {v.missing_message || tt("videos.originalNotFound", "Original video fayli topilmadi. Qayta yuklang.")}
                  </p>
                ) : null}
                {v.progress?.completed ? (
                  <div className="mt-2 mb-3">
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); router.push(`/student/content-tests/video/${v.id}`); }}
                      className="w-full rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-700 hover:to-cyan-600 text-white font-bold py-2.5 text-xs transition-all shadow-md hover:shadow-lg active:scale-95 flex items-center justify-center gap-2"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      {tt("student.video.test", "Video Testni Ishlash")}
                    </button>
                  </div>
                ) : null}

                <div className="mt-auto pt-3 border-t border-line dark:border-white/10">
                  <span className="text-xs font-bold text-ink-500 dark:text-navy-400 uppercase tracking-wider">
                    {tt("videos.views", "Ko'rishlar:")} {Number(v.view_count || 0).toLocaleString()}
                  </span>
                </div>
              </div>
            </div>
          ))}
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
    </div>
  );
}
