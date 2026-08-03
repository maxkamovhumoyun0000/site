"use client";

import React, { useCallback, useEffect, useRef, useState, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useWebT } from "./web-i18n";
import VideoComments from "./video-comments";

function formatViews(views: number | undefined | null) {
  if (!views) return "0 views";
  if (views >= 1000000) return (views / 1000000).toFixed(1) + "M views";
  if (views >= 1000) return (views / 1000).toFixed(1) + "K views";
  return views.toString() + " views";
}

function formatDate(dateStr: string | undefined | null) {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    return new Intl.DateTimeFormat("en-US", { day: "numeric", month: "short", year: "numeric" }).format(d);
  } catch {
    return dateStr;
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

function resolveMediaUrl(url?: string | null) {
  const raw = String(url || "").trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith("/")) return `${API_BASE}${raw}`;
  return `${API_BASE}/${raw}`;
}

type VideoItem = {
  id: number;
  title: string;
  description?: string;
  author?: string;
  category?: string;
  level?: string;
  thumbnail_url?: string;
  video_url?: string;
  duration?: number;
  view_count?: number;
  like_count?: number;
  liked_by_me?: boolean;
  missing_original?: boolean;
  media_status?: string;
  missing_message?: string;
  progress?: {
    watched_seconds?: number;
    max_watched_seconds?: number;
    last_position_seconds?: number;
    duration_seconds?: number;
    completed?: boolean;
  } | null;
};

export function RoleVideoDetailPage({ role, videoId }: { role: "admin" | "teacher" | "support"; videoId: string }) {
  const router = useRouter();
  const params = useParams<{ videoId?: string }>();
  const [video, setVideo] = useState<VideoItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [playerLoadError, setPlayerLoadError] = useState(false);
  const [fullscreenNotice, setFullscreenNotice] = useState("");
  const [isSimulatedFullscreen, setIsSimulatedFullscreen] = useState(false);
  const fullscreenToastTimerRef = useRef<number | null>(null);
  const [actualDuration, setActualDuration] = useState(0);
  const [likeBusy, setLikeBusy] = useState(false);
  const [refreshedSrc, setRefreshedSrc] = useState("");
  const [disliked, setDisliked] = useState(false);
  const [descExpanded, setDescExpanded] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const progressSendRef = useRef<{ videoId: number; sentAtSec: number; sentAtMs: number }>({ videoId: 0, sentAtSec: -1, sentAtMs: 0 });
  const resumeAppliedRef = useRef<{ videoId: number; applied: boolean }>({ videoId: 0, applied: false });
  const maxWatchedTimeRef = useRef(0);
  const lastTimeRef = useRef(0);
  const viewRegisteredRef = useRef<{ videoId: number; done: boolean }>({ videoId: 0, done: false });
  const replayModeRef = useRef(false);
  const retryRef = useRef(false);
  const resolvedVideoIdRaw = String(videoId || params?.videoId || "").trim();
  const safeVideoId = /^\d+$/.test(resolvedVideoIdRaw) ? resolvedVideoIdRaw : "";

  const videoSrc = refreshedSrc || resolveMediaUrl(video?.video_url);

  const formattedDuration = useMemo(() => {
    const total = Math.max(0, Math.round(Number(actualDuration || video?.duration || 0)));
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
  }, [actualDuration, video?.duration]);

  useEffect(() => {
    const webApp = (window as any)?.Telegram?.WebApp;
    const backButton = webApp?.BackButton;
    if (!backButton) return;
    const handleBack = () => router.back();
    try {
      backButton.show();
      backButton.onClick(handleBack);
    } catch {
      return;
    }
    return () => {
      try {
        backButton.offClick(handleBack);
        backButton.hide();
      } catch {
        // Telegram clients do not all expose the same BackButton API surface.
      }
    };
  }, [router]);

  useEffect(() => {
    return () => {
      if (fullscreenToastTimerRef.current) {
        window.clearTimeout(fullscreenToastTimerRef.current);
      }
    };
  }, []);

  function showFullscreenToast(message: string) {
    setFullscreenNotice(message);
    if (fullscreenToastTimerRef.current) {
      window.clearTimeout(fullscreenToastTimerRef.current);
    }
    fullscreenToastTimerRef.current = window.setTimeout(() => setFullscreenNotice(""), 3200);
  }

  async function toggleLike() {
    if (!video || likeBusy) return;
    setLikeBusy(true);
    const wasLiked = Boolean(video.liked_by_me);
    setVideo((prev) =>
      prev
        ? {
            ...prev,
            liked_by_me: !wasLiked,
            like_count: Math.max(0, Number(prev.like_count || 0) + (wasLiked ? -1 : 1)),
          }
        : prev,
    );
    try {
      const payload = await apiFetch(`/${role}/videos/${safeVideoId}/like`, { method: "POST" });
      setVideo((prev) =>
        prev
          ? {
              ...prev,
              liked_by_me: Boolean(payload?.liked),
              like_count: Number(payload?.like_count ?? prev.like_count ?? 0),
            }
          : prev,
      );
    } catch {
      setVideo((prev) =>
        prev
          ? {
              ...prev,
              liked_by_me: wasLiked,
              like_count: Math.max(0, Number(prev.like_count || 0) + (wasLiked ? 1 : -1)),
            }
          : prev,
      );
    } finally {
      setLikeBusy(false);
    }
  }

  async function persistProgress(seconds: number, completed: boolean, force = false) {
    if (!video || role === "admin") return;
    const safeSec = Math.max(0, Math.round(seconds));
    const maxWatchedSec = Math.max(0, Math.round(Math.max(maxWatchedTimeRef.current || 0, completed ? safeSec : 0)));
    const sameVideo = progressSendRef.current.videoId === Number(video.id || 0);
    const nowMs = Date.now();
    if (!force && sameVideo && nowMs - Number(progressSendRef.current.sentAtMs || 0) < 12000 && !completed) return;
    progressSendRef.current = { videoId: Number(video.id || 0), sentAtSec: safeSec, sentAtMs: nowMs };
    try {
      const payload = await apiFetch(`/${role}/videos/${video.id}/progress`, {
        method: "POST",
        body: {
          watched_seconds: safeSec,
          max_watched_seconds: maxWatchedSec,
          completed,
          duration: Math.round(actualDuration || Number(video.duration || 0) || 0),
        },
      });
      const nextProgress = payload?.progress || { watched_seconds: maxWatchedSec, last_position_seconds: safeSec, max_watched_seconds: maxWatchedSec, completed };
      const returnedMax = Number(nextProgress?.max_watched_seconds ?? nextProgress?.watched_seconds ?? maxWatchedSec);
      if (Number.isFinite(returnedMax)) {
        maxWatchedTimeRef.current = Math.max(maxWatchedTimeRef.current, returnedMax);
      }
      setVideo((prev) => prev ? { ...prev, progress: nextProgress, view_count: Number(payload?.view_count ?? prev.view_count ?? 0) } : prev);
    } catch {
      // Progress is best-effort and should not interrupt viewing.
    }
  }

  async function registerViewIfReady() {
    if (!video || role === "admin") return;
    const currentVideoId = Number(video.id || 0);
    if (viewRegisteredRef.current.videoId !== currentVideoId) {
      viewRegisteredRef.current = { videoId: currentVideoId, done: false };
    }
    if (viewRegisteredRef.current.done) return;
    viewRegisteredRef.current.done = true;
    try {
      const payload = await apiFetch(`/${role}/videos/${video.id}/view`, {
        method: "POST",
        body: {
          watched_seconds: Math.max(1, Math.round(videoRef.current?.currentTime || maxWatchedTimeRef.current || 1)),
          max_watched_seconds: Math.max(1, Math.round(maxWatchedTimeRef.current || videoRef.current?.currentTime || 1)),
          completed: false,
          duration: Math.round(actualDuration || Number(video.duration || 0) || 0),
        },
      });
      const nextProgress = payload?.progress;
      if (nextProgress) {
        const returnedMax = Number(nextProgress?.max_watched_seconds ?? nextProgress?.watched_seconds ?? maxWatchedTimeRef.current);
        if (Number.isFinite(returnedMax)) {
          maxWatchedTimeRef.current = Math.max(maxWatchedTimeRef.current, returnedMax);
        }
      }
      setVideo((prev) => prev ? { ...prev, progress: nextProgress || prev.progress, view_count: Number(payload?.view_count ?? prev.view_count ?? 0) } : prev);
    } catch {
      // View counting is best-effort and should not interrupt playback.
    }
  }

  function flushProgress(force = false) {
    const element = videoRef.current;
    if (!element || !video || role === "admin") return;
    const duration = Math.max(0, Number(actualDuration || video.duration || element.duration || 0));
    const current = Number(element.currentTime || 0);
    const completed = duration > 0 ? current >= duration - 1 : false;
    persistProgress(current, completed, force).catch(() => null);
  }

  async function openFullscreenVideo() {
    const element = videoRef.current as (HTMLVideoElement & {
      webkitEnterFullscreen?: () => void;
      webkitRequestFullscreen?: () => Promise<void> | void;
    }) | null;
    if (!element) return;
    setFullscreenNotice("");
    try {
      const isAppleMobile = /iPad|iPhone|iPod/i.test(navigator.userAgent || "");
      const isTg = Boolean((window as any)?.Telegram?.WebApp?.initData);
      
      if (isTg) {
        setIsSimulatedFullscreen(true);
        return;
      }

      if (isAppleMobile && element.webkitEnterFullscreen) {
        element.webkitEnterFullscreen();
      } else if (element.requestFullscreen) {
        try {
          const promise = element.requestFullscreen();
          if (promise) await promise;
        } catch {
          setIsSimulatedFullscreen(true);
        }
      } else if (element.webkitEnterFullscreen) {
        element.webkitEnterFullscreen();
      } else if (element.webkitRequestFullscreen) {
        try {
          const promise = element.webkitRequestFullscreen();
          if (promise) await promise;
        } catch {
          setIsSimulatedFullscreen(true);
        }
      } else {
        setIsSimulatedFullscreen(true);
      }
    } catch {
      setIsSimulatedFullscreen(true);
    }
  }

  function onPlaybackStarted() {
    const element = videoRef.current;
    if (element) {
      const duration = Math.max(0, Number(actualDuration || video?.duration || element.duration || 0));
      if (duration > 0 && (element.ended || element.currentTime >= duration - 0.35)) {
        replayModeRef.current = true;
        lastTimeRef.current = 0;
        try {
          element.currentTime = 0;
        } catch {
          // Native player may ignore programmatic seek while entering playback.
        }
      }
    }
    setFullscreenNotice("");
    registerViewIfReady().catch(() => null);
  }

  function enforcePlaybackRate() {
    const element = videoRef.current;
    if (!element) return;
    if (element.playbackRate !== 1) {
      element.playbackRate = 1;
    }
    if (element.defaultPlaybackRate !== 1) {
      element.defaultPlaybackRate = 1;
    }
  }

  async function refreshVideoSrc() {
    if (retryRef.current) return;
    retryRef.current = true;
    try {
      const res = await apiFetch(`/${role}/videos/${safeVideoId}`);
      const freshUrl = resolveMediaUrl(res?.item?.video_url);
      if (freshUrl && freshUrl !== resolveMediaUrl(video?.video_url)) {
        setRefreshedSrc(freshUrl);
        setPlayerLoadError(false);
      }
    } catch {
      // ignore
    }
  }

  function normalizeError(error: unknown) {
    const text = String(error instanceof Error ? error.message : "").trim();
    const lowered = text.toLowerCase();
    if (!text) return "Videoni yuklab bo'lmadi.";
    if (lowered.includes("404") || lowered.includes("not found")) return "Video topilmadi.";
    if (lowered.includes("timeout")) return "So'rov vaqti tugadi. Qayta urinib ko'ring.";
    if (lowered.includes("403")) return "Sizda bu videoni ko'rish huquqi yo'q.";
    if (lowered.includes("422")) return "Video ochilmadi. Fayl yoki ID noto'g'ri.";
    return text;
  }

  const fetchVideo = useCallback(async () => {
    if (!safeVideoId) {
      setVideo(null);
      setError("Video identifikatori noto'g'ri.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    setPlayerLoadError(false);
    try {
      const res = await apiFetch(`/${role}/videos/${safeVideoId}`);
      if (res?.item) setVideo(res.item);
      else setError("Video topilmadi.");
    } catch (e) {
      setError(normalizeError(e));
    }
    setLoading(false);
  }, [role, safeVideoId]);

  useEffect(() => {
    maxWatchedTimeRef.current = Math.max(
      0,
      Number(video?.progress?.max_watched_seconds || 0),
      Number(video?.progress?.watched_seconds || 0),
    );
    fetchVideo().catch(() => null);
  }, [fetchVideo]);

  const handleDislike = () => {
    if (disliked) {
      setDisliked(false);
    } else {
      setDisliked(true);
      if (video?.liked_by_me) {
        toggleLike();
      }
    }
  };

  return (
    <main className="video-detail-page flex min-h-screen flex-col bg-slate-50 text-slate-900 relative dark:bg-slate-950 dark:text-slate-100">
      <div className="flex-1 overflow-y-auto w-full pt-4 sm:pt-6 pb-12">
        <div className="w-full max-w-[1800px] mx-auto flex flex-col lg:flex-row gap-8 sm:px-6 lg:px-8 2xl:px-12">
          
          {/* Main Player Area */}
          <div className="flex-1 relative">
          {error ? (
            <div className="bg-red-50 text-red-500 px-6 py-4 rounded-2xl shadow-sm border border-red-100 dark:bg-red-500/10 dark:border-red-500/20 text-sm font-bold flex items-center gap-4">
              <svg className="w-6 h-6 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              <span>{error}</span>
            </div>
          ) : null}

          {loading ? (
            <div className="video-loading-card rounded-[2rem] bg-white p-16 shadow-premium border border-line text-center flex flex-col items-center justify-center min-h-[50vh] dark:border-slate-700 dark:bg-slate-900">
               <div className="w-12 h-12 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin mb-6" />
               <p className="text-ink-500 dark:text-slate-200 font-bold tracking-wide">Video yuklanmoqda...</p>
            </div>
          ) : video ? (
            <>
              <div className={`bg-black overflow-hidden relative mb-6 ${isSimulatedFullscreen ? "fixed inset-0 z-[99999] !m-0 !rounded-none w-screen h-screen flex flex-col items-center justify-center" : "sm:rounded-2xl shadow-2xl aspect-video w-full"}`}>
                {video.missing_original ? (
                  <div className="absolute inset-0 flex items-center justify-center flex-col p-6 text-center text-amber-500 bg-amber-500/10">
                    <span className="text-4xl mb-2">⚠️</span>
                    <span className="font-bold">{video.missing_message || "Original video fayli topilmadi."}</span>
                  </div>
                ) : video.video_url ? (
                    <video
                      ref={videoRef}
                      src={videoSrc}
                      controls
                      controlsList="nodownload noplaybackrate"
                      disablePictureInPicture
                      playsInline
                      preload="metadata"
                      className={`outline-none ${isSimulatedFullscreen ? "w-full h-full max-h-screen object-contain" : "w-full aspect-video"}`}
                      onPlay={onPlaybackStarted}
                      onPlaying={onPlaybackStarted}
                      onRateChange={enforcePlaybackRate}
                      onTimeUpdate={() => {
                        const element = videoRef.current;
                        if (!element) return;
                        const current = Number(element.currentTime || 0);
                        const duration = Math.max(0, Number(actualDuration || video?.duration || element.duration || 0));
                        const replayJumpToStart = duration > 0 && lastTimeRef.current >= duration - 1 && current <= 1;
                        if (role !== "admin" && !element.seeking) {
                          if (replayJumpToStart) {
                            replayModeRef.current = true;
                            lastTimeRef.current = current;
                          } else if (current > lastTimeRef.current + 1.25) {
                            element.currentTime = Math.max(0, lastTimeRef.current);
                            return;
                          } else {
                            lastTimeRef.current = current;
                          }
                        }
                        if (Number.isFinite(current) && !element.seeking) {
                          maxWatchedTimeRef.current = Math.max(maxWatchedTimeRef.current, current);
                        }
                        if (replayModeRef.current && current > 2) {
                          replayModeRef.current = false;
                        }
                        flushProgress(false);
                      }}
                      onSeeking={() => {
                        const element = videoRef.current;
                        if (!element || role === "admin") return;
                        const current = Number(element.currentTime || 0);
                        const duration = Math.max(0, Number(actualDuration || video?.duration || element.duration || 0));
                        if (duration > 0 && lastTimeRef.current >= duration - 1 && current <= 1) {
                          replayModeRef.current = true;
                          lastTimeRef.current = current;
                          return;
                        }
                        if (current <= lastTimeRef.current + 0.75) {
                          lastTimeRef.current = Math.max(0, current);
                          return;
                        }
                        const allowed = Math.max(0, Number(lastTimeRef.current || 0));
                        if (current > allowed + 1.25) {
                          element.currentTime = allowed;
                        }
                      }}
                      onPause={() => flushProgress(true)}
                      onEnded={() => {
                        const duration = Math.max(Number(actualDuration || 0), Number(videoRef.current?.duration || 0), Number(videoRef.current?.currentTime || 0));
                        maxWatchedTimeRef.current = Math.max(maxWatchedTimeRef.current, duration);
                        lastTimeRef.current = duration;
                        replayModeRef.current = true;
                        persistProgress(duration, true, true).catch(() => null);
                        viewRegisteredRef.current = { videoId: Number(video.id || 0), done: false };
                      }}
                      onLoadedMetadata={() => {
                        const duration = Number(videoRef.current?.duration || 0);
                        if (Number.isFinite(duration) && duration > 0) setActualDuration(Math.round(duration));
                        enforcePlaybackRate();
                        const target = Number(video.progress?.last_position_seconds ?? video.progress?.watched_seconds ?? 0);
                        const maxWatched = Math.max(
                          Number(video.progress?.max_watched_seconds || 0),
                          Number(video.progress?.watched_seconds || 0),
                          Number(target || 0),
                        );
                        if (Number.isFinite(maxWatched)) {
                          maxWatchedTimeRef.current = Math.max(maxWatchedTimeRef.current, maxWatched);
                        }
                        const currentVideoId = Number(video.id || 0);
                        if (resumeAppliedRef.current.videoId !== currentVideoId) {
                          resumeAppliedRef.current = { videoId: currentVideoId, applied: false };
                        }
                        if (videoRef.current && !video.progress?.completed && target > 0 && Number.isFinite(target) && !resumeAppliedRef.current.applied) {
                          videoRef.current.currentTime = Math.min(target, maxWatchedTimeRef.current);
                          lastTimeRef.current = Math.min(target, maxWatchedTimeRef.current);
                          resumeAppliedRef.current.applied = true;
                        } else if (video.progress?.completed) {
                          replayModeRef.current = true;
                          lastTimeRef.current = 0;
                          resumeAppliedRef.current.applied = true;
                        }
                        setPlayerLoadError(false);
                      }}
                      onError={() => { setPlayerLoadError(true); refreshVideoSrc(); }}
                    />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center text-white/50 flex-col">
                    <span className="text-4xl mb-2">🚫</span>
                    <span>Video mavjud emas</span>
                  </div>
                )}
                <button
                  type="button"
                  className="absolute bottom-3 right-3 grid h-10 w-10 place-items-center rounded-xl bg-black/70 text-white backdrop-blur transition hover:bg-black focus:outline-none focus:ring-2 focus:ring-cyan-300"
                  aria-label="Fullscreen"
                  title="Fullscreen"
                  onClick={openFullscreenVideo}
                >
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3M3 16v3a2 2 0 002 2h3m8 0h3a2 2 0 002-2v-3" />
                  </svg>
                </button>
                {isSimulatedFullscreen && (
                  <button
                    type="button"
                    className="absolute top-4 right-4 z-[100000] grid h-10 w-10 place-items-center rounded-full bg-black/60 text-white backdrop-blur transition hover:bg-black focus:outline-none"
                    onClick={() => setIsSimulatedFullscreen(false)}
                    aria-label="Chiqish"
                  >
                    ✕
                  </button>
                )}
              </div>

              {fullscreenNotice ? <div className="video-toast" role="status">{fullscreenNotice}</div> : null}
              {playerLoadError ? (
                <div className="rounded-xl border border-red-200 bg-red-50 text-red-600 px-4 py-3 text-sm font-semibold mb-6">
                  Video player yuklanmadi. Qayta urinib ko'ring.
                </div>
              ) : null}

              <div className="px-4 sm:px-0">
                <h1 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white mb-3 leading-tight">
                  {video.title}
                </h1>
                
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 font-black text-xl shrink-0">
                      D
                    </div>
                    <div>
                      <h3 className="font-bold text-gray-900 dark:text-white text-sm">Diamond Education</h3>
                      <p className="text-xs text-gray-500">Official Channel</p>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
                    <div className="flex items-center bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 rounded-full transition-colors h-9">
                      <button onClick={toggleLike} className={`flex items-center gap-1.5 px-4 h-full border-r border-gray-300 dark:border-gray-600 font-semibold text-sm ${video.liked_by_me ? "text-blue-600 dark:text-blue-400" : "text-gray-900 dark:text-white"}`}>
                        {video.liked_by_me ? (
                          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>
                        ) : (
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>
                        )}
                        {video.like_count ? video.like_count : ""}
                      </button>
                      <button onClick={handleDislike} className={`flex items-center justify-center px-4 h-full ${disliked ? "text-blue-600 dark:text-blue-400" : "text-gray-900 dark:text-white"}`}>
                        {disliked ? (
                          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-2"></path></svg>
                        ) : (
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-2"></path></svg>
                        )}
                      </button>
                    </div>
                    <button className="flex items-center gap-1.5 px-4 h-9 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 rounded-full font-semibold text-sm text-gray-900 dark:text-white transition-colors">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
                      Share
                    </button>
                  </div>
                </div>

                <div 
                  className="bg-gray-200/50 hover:bg-gray-200 dark:bg-gray-800/60 dark:hover:bg-gray-800 rounded-xl p-3 sm:p-4 text-sm transition-colors cursor-pointer mt-2"
                  onClick={() => setDescExpanded(!descExpanded)}
                >
                  <div className="flex gap-2 font-bold text-gray-900 dark:text-white mb-1">
                    <span>{formatViews(video.view_count)}</span>
                    <span>•</span>
                    <span>Davomiylik: {formattedDuration}</span>
                  </div>
                  <div className={`prose dark:prose-invert max-w-none text-gray-800 dark:text-gray-200 ${descExpanded ? '' : 'line-clamp-2'}`}>
                    {video.description ? (
                      <p className="whitespace-pre-wrap leading-relaxed">{video.description}</p>
                    ) : (
                      <p className="italic opacity-70">Tavsif kiritilmagan.</p>
                    )}
                  </div>
                  {video.description && video.description.length > 100 && (
                    <button className="font-bold mt-2 text-gray-900 dark:text-white">
                      {descExpanded ? "Yig'ish" : "Ko'proq"}
                    </button>
                  )}
                </div>

                {/* Comments Section */}
                <VideoComments videoId={safeVideoId} />

              </div>
            </>
          ) : null}
          </div>
          
          {/* Sidebar Area for consistency */}
          <div className="w-full lg:w-[350px] xl:w-[400px] flex-shrink-0"></div>
        </div>
      </div>
    </main>
  );
}
