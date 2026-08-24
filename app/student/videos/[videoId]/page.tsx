"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useWebT } from "@/app/ui/web-i18n";
import VideoComments from "@/app/ui/video-comments";

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

type VideoProgress = {
  watched_seconds: number;
  max_watched_seconds?: number;
  last_position_seconds?: number;
  duration_seconds?: number;
  completed: boolean;
};

type VideoItem = {
  id: number;
  title: string;
  description?: string;
  author?: string;
  category?: string;
  level?: string;
  subject?: string;
  thumbnail_url?: string;
  video_url?: string;
  duration?: number;
  view_count?: number;
  like_count?: number;
  liked_by_me?: boolean;
  progress?: VideoProgress | null;
};

export default function StudentVideoPage({ params }: { params: { videoId: string } }) {
  const router = useRouter();
  const routeParams = useParams<{ videoId?: string }>();
  const tt = useWebT();

  const [video, setVideo] = useState<VideoItem | null>(null);
  const [related, setRelated] = useState<VideoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [, setSavingProgress] = useState(false);
  const [playerLoadError, setPlayerLoadError] = useState(false);
  const [actualDuration, setActualDuration] = useState(0);
  const [likeBusy, setLikeBusy] = useState(false);
  const [disliked, setDisliked] = useState(false);
  const [fullscreenNotice, setFullscreenNotice] = useState("");
  const [isFullscreen, setIsFullscreen] = useState(false);
  
  const [descExpanded, setDescExpanded] = useState(false);
  const fullscreenToastTimerRef = useRef<number | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const progressSendRef = useRef<{ videoId: number; sentAtSec: number; sentAtMs: number }>({ videoId: 0, sentAtSec: -1, sentAtMs: 0 });
  const resumeAppliedRef = useRef<{ videoId: number; applied: boolean }>({ videoId: 0, applied: false });
  const maxWatchedTimeRef = useRef(0);
  const viewRegisteredRef = useRef<{ videoId: number; done: boolean }>({ videoId: 0, done: false });
  const resolvedVideoIdRaw = String(params?.videoId || routeParams?.videoId || "").trim();
  const safeVideoId = useMemo(() => (/^\d+$/.test(resolvedVideoIdRaw) ? resolvedVideoIdRaw : ""), [resolvedVideoIdRaw]);
  const resolvedVideoUrl = useMemo(() => resolveMediaUrl(video?.video_url), [video?.video_url]);
  const [refreshedSrc, setRefreshedSrc] = useState("");
  const videoSrc = refreshedSrc || resolvedVideoUrl;
  const retryRef = useRef(false);
  const lastTimeRef = useRef(0);
  const replayModeRef = useRef(false);
  
  // Test states
  const [testData, setTestData] = useState<any>(null);
  const [testResult, setTestResult] = useState<any>(null);
  const [testError, setTestError] = useState("");
  const testResultSummary = useMemo(() => {
    const raw = testResult || {};
    const correct = Number(raw.correct_count ?? raw.correct ?? raw.score ?? 0);
    const wrong = Number(raw.wrong_count ?? raw.wrong ?? 0);
    const skipped = Number(raw.skipped_count ?? raw.skipped ?? raw.unanswered ?? 0);
    const total = Number(raw.total_questions ?? raw.total ?? (testData?.questions || []).length ?? 0);
    const delta = Number(raw.dpoints_delta ?? 0);
    return { correct, wrong, skipped, total, delta };
  }, [testResult, testData]);

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
        // Telegram WebApp API availability differs across clients.
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

  async function openNativeFullscreen() {
    const element = videoRef.current as (HTMLVideoElement & {
      webkitEnterFullscreen?: () => void;
      webkitRequestFullscreen?: () => Promise<void> | void;
    }) | null;
    if (!element) return;
    setFullscreenNotice("");
    
    // Always use fake fullscreen in Telegram Mini Apps
    const isTelegramMiniApp = (typeof window !== "undefined" && (window as any).Telegram?.WebApp?.initData) || navigator.userAgent.includes("Telegram");
    if (isTelegramMiniApp) {
      setIsFullscreen(true);
      return;
    }

    try {
      const isAppleMobile = /iPad|iPhone|iPod/i.test(navigator.userAgent || "");
      if (isAppleMobile && element.webkitEnterFullscreen) {
        element.webkitEnterFullscreen();
        return;
      }
      if (element.requestFullscreen) {
        try {
          const promise = element.requestFullscreen();
          if (promise) await promise;
        } catch {
          setIsFullscreen(true);
        }
        return;
      }
      if (element.webkitEnterFullscreen) {
        element.webkitEnterFullscreen();
        return;
      }
      if (element.webkitRequestFullscreen) {
        try {
          const promise = element.webkitRequestFullscreen();
          if (promise) await promise;
        } catch {
          setIsFullscreen(true);
        }
        return;
      }
      setIsFullscreen(true);
    } catch {
      setIsFullscreen(true);
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
          // Native players may ignore programmatic seek while entering playback.
        }
      }
    }
    setFullscreenNotice("");
    registerViewIfReady().catch(() => null);
  }

  async function refreshVideoSrc() {
    if (retryRef.current) return;
    retryRef.current = true;
    try {
      const res = await apiFetch(`/student/videos/${safeVideoId}`);
      const freshUrl = resolveMediaUrl(res?.item?.video_url);
      if (freshUrl && freshUrl !== resolvedVideoUrl) {
        setRefreshedSrc(freshUrl);
        setPlayerLoadError(false);
      }
    } catch {
      // ignore
    }
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
      const res = await apiFetch(`/student/videos/${safeVideoId}`);
      if (res?.item) setVideo(res.item);
      else setError("Video topilmadi.");
      
      if (res?.related && Array.isArray(res.related)) {
        setRelated(res.related);
      } else {
        setRelated([]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Videoni yuklab bo'lmadi.");
    }
    setLoading(false);
  }, [safeVideoId]);

  useEffect(() => {
    fetchVideo().catch(() => null);
  }, [fetchVideo]);

  const fetchTest = useCallback(async () => {
    if (!safeVideoId) return;
    try {
      const res = await apiFetch(`/student/video/${safeVideoId}/test`);
      if (res?.test) {
        setTestData(res.test);
        setTestResult(res.result || null);
        setTestError("");
      } else {
        setTestData(null);
      }
    } catch (e: any) {
      const message = String(e?.message || "");
      const lowered = message.toLowerCase();
      if (message.includes("Videoni tugatgandan keyin") || lowered.includes("tomosha") || lowered.includes("yakun") || lowered.includes("completed")) {
        setTestError("Videoni tomosha qilgandan keyin test ochiladi");
      } else if (lowered.includes("not found") || lowered.includes("404") || lowered.includes("topilmadi") || lowered.includes("ma'lumot")) {
        setTestError("Test hali qo'shilmagan");
      } else {
        setTestError("");
      }
      setTestData(null);
    }
  }, [safeVideoId]);

  useEffect(() => {
    if (video) {
      fetchTest().catch(() => null);
    }
  }, [video?.id, video?.progress?.completed, fetchTest]);

  async function persistProgress(seconds: number, completed: boolean, force = false) {
    if (!video) return;
    const safeSec = Math.max(0, Math.round(seconds));
    const maxWatchedSec = Math.max(0, Math.round(Math.max(maxWatchedTimeRef.current || 0, completed ? safeSec : 0)));
    const sameVideo = progressSendRef.current.videoId === Number(video.id || 0);
    const nowMs = Date.now();
    if (!force && sameVideo && nowMs - Number(progressSendRef.current.sentAtMs || 0) < 12000 && !completed) return;
    
    progressSendRef.current = { videoId: Number(video.id || 0), sentAtSec: safeSec, sentAtMs: nowMs };
    if (force) {
      setSavingProgress(true);
    }
    try {
      const payload = await apiFetch(`/student/videos/${video.id}/progress`, {
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
      setVideo((prev) =>
        prev
          ? {
              ...prev,
              progress: nextProgress,
              view_count: Number(payload?.view_count ?? prev.view_count ?? 0),
            }
          : prev,
      );
    } catch (e) {
      console.error("Progress saqlanmadi", e);
    } finally {
      if (force) {
        setSavingProgress(false);
      }
    }
  }

  async function registerViewIfReady() {
    if (!video) return;
    const currentVideoId = Number(video.id || 0);
    if (viewRegisteredRef.current.videoId !== currentVideoId) {
      viewRegisteredRef.current = { videoId: currentVideoId, done: false };
    }
    if (viewRegisteredRef.current.done) return;
    viewRegisteredRef.current.done = true;
    try {
      const payload = await apiFetch(`/student/videos/${video.id}/view`, {
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
      setVideo((prev) =>
        prev
          ? {
              ...prev,
              progress: nextProgress || prev.progress,
              view_count: Number(payload?.view_count ?? prev.view_count ?? 0),
            }
          : prev,
      );
    } catch {
      // View counting is best-effort and must not interrupt playback.
    }
  }

  function onVideoTimeUpdate() {
    const element = videoRef.current;
    if (!element) return;

    const duration = Math.max(0, Number(video?.duration || element.duration || 0));
    const current = Number(element.currentTime || 0);
    const replayJumpToStart = duration > 0 && lastTimeRef.current >= duration - 1 && current <= 1;

    if (!element.seeking) {
      if (replayJumpToStart) {
        replayModeRef.current = true;
        lastTimeRef.current = current;
      } else if (current > lastTimeRef.current + 1.25) {
        element.currentTime = Math.max(0, lastTimeRef.current);
        return;
      } else if (replayModeRef.current) {
        lastTimeRef.current = current;
        if (current > 2) {
          replayModeRef.current = false;
        }
      } else {
        lastTimeRef.current = current;
      }
    }

    const completed = duration > 0 ? current >= duration - 1 : false;
    
    if (Number.isFinite(current) && !element.seeking) {
      maxWatchedTimeRef.current = Math.max(maxWatchedTimeRef.current, current);
    }
    
    registerViewIfReady().catch(() => null);
    persistProgress(current, completed, false);
  }

  function onSeeking() {
    const element = videoRef.current;
    if (!element) return;
    const current = Number(element.currentTime || 0);
    const duration = Math.max(0, Number(video?.duration || element.duration || 0));
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
    } else {
      lastTimeRef.current = current;
    }
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


  function onVideoEnded() {
    const element = videoRef.current;
    if (!element) return;
    const duration = Math.max(Number(video?.duration || 0), Number(element.duration || 0), Number(element.currentTime || 0));
    maxWatchedTimeRef.current = Math.max(maxWatchedTimeRef.current, duration);
    lastTimeRef.current = duration;
    replayModeRef.current = true;
    persistProgress(duration, true, true);
    if (video) {
      viewRegisteredRef.current = { videoId: Number(video.id || 0), done: false };
    }
  }

  function flushProgressOnPause() {
    const element = videoRef.current;
    if (!element) return;
    const duration = Math.max(0, Number(video?.duration || element.duration || 0));
    const current = Number(element.currentTime || 0);
    const completed = duration > 0 ? current >= duration - 1 : false;
    persistProgress(current, completed, true);
  }

  const formattedDuration = useMemo(() => {
    const total = Math.max(0, Math.round(Number(actualDuration || video?.duration || 0)));
    const minutes = Math.floor(total / 60);
    const seconds = total % 60;
    return `${minutes}:${String(seconds).padStart(2, "0")}`;
  }, [actualDuration, video?.duration]);

  async function toggleLike() {
    if (!video || likeBusy) return;
    setLikeBusy(true);
    const wasLiked = Boolean(video.liked_by_me);
    if (!wasLiked && disliked) setDisliked(false);
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
      const payload = await apiFetch(`/student/videos/${video.id}/like`, { method: "POST" });
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


  useEffect(() => {
    const onBeforeUnload = () => {
      const element = videoRef.current;
      if (!element || !video) return;
      const duration = Math.max(0, Number(video.duration || element.duration || 0));
      const current = Number(element.currentTime || 0);
      const completed = duration > 0 ? current >= duration - 1 : false;
      persistProgress(current, completed, true).catch(() => null);
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      onBeforeUnload();
      window.removeEventListener("beforeunload", onBeforeUnload);
    };
  }, [video]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <main className="video-detail-page flex min-h-screen flex-col bg-slate-50 text-slate-900 relative selection:bg-cyan-500/30 selection:text-cyan-900 dark:bg-slate-950 dark:text-slate-100 dark:selection:text-cyan-100">
      <div className="flex-1 overflow-y-auto w-full p-0 sm:p-4 lg:p-8">
        <div className="w-full max-w-[1800px] mx-auto space-y-6 relative 2xl:px-8">
          {error && (
            <div className="bg-red-50 text-red-500 px-6 py-4 rounded-2xl shadow-sm border border-red-100 dark:bg-red-500/10 dark:border-red-500/20 text-sm font-bold flex items-center gap-4 mx-4 lg:mx-0">
              <svg className="w-6 h-6 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              <span>{error}</span>
            </div>
          )}

          {loading ? (
            <div className="video-loading-card rounded-[2rem] bg-white p-16 shadow-premium border border-line text-center flex flex-col items-center justify-center min-h-[50vh] dark:border-slate-700 dark:bg-slate-900 mx-4 lg:mx-0">
               <div className="w-12 h-12 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin mb-6" />
               <p className="text-ink-500 dark:text-slate-200 font-bold tracking-wide">{tt("common.loading", "Video yuklanmoqda...")}</p>
            </div>
          ) : video ? (
            <div className="w-full flex flex-col lg:flex-row gap-6 px-0 sm:px-6 lg:px-0 pb-10">
              {/* Main Player Area */}
              <div className="flex-1 min-w-0">
                <div className={`${isFullscreen ? "fixed inset-0 z-[99999] !m-0 !rounded-none w-screen h-screen flex flex-col items-center justify-center bg-black" : "bg-black sm:rounded-2xl overflow-hidden sm:shadow-2xl aspect-video relative mb-3 sm:mb-6 w-full"}`}>
                  {resolvedVideoUrl ? (
                    <video
                      ref={videoRef}
                      src={videoSrc}
                      controls
                      controlsList="nodownload noplaybackrate"
                      disablePictureInPicture
                      autoPlay
                      playsInline
                      preload="auto"
                      className={`outline-none ${isFullscreen ? "w-full h-full max-h-screen object-contain" : "absolute inset-0 w-full h-full"}`}
                    onPlay={onPlaybackStarted}
                    onPlaying={onPlaybackStarted}
                    onRateChange={enforcePlaybackRate}
                    onTimeUpdate={onVideoTimeUpdate}
                    onSeeking={onSeeking}
                    onEnded={onVideoEnded}
                    onPause={flushProgressOnPause}
                    onLoadedMetadata={() => {
                      const duration = Number(videoRef.current?.duration || 0);
                      if (Number.isFinite(duration) && duration > 0) {
                        setActualDuration(Math.round(duration));
                      }
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
                      if (
                        videoRef.current &&
                        !video.progress?.completed &&
                        target > 0 &&
                        Number.isFinite(target) &&
                        !resumeAppliedRef.current.applied
                      ) {
                        lastTimeRef.current = Math.min(target, maxWatchedTimeRef.current);
                        videoRef.current.currentTime = lastTimeRef.current;
                        resumeAppliedRef.current.applied = true;
                      } else if (video.progress?.completed) {
                        replayModeRef.current = true;
                        lastTimeRef.current = 0;
                        resumeAppliedRef.current.applied = true;
                      }
                      setPlayerLoadError(false);
                    }}
                    onError={() => {
                      setPlayerLoadError(true);
                      refreshVideoSrc();
                    }}
                  />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center text-white/50 flex-col">
                    <span className="text-4xl mb-2">🚫</span>
                    <span>Video mavjud emas</span>
                  </div>
                )}
                <button
                  type="button"
                  aria-label={tt("video.fullscreen", "Fullscreen")}
                  title={tt("video.fullscreen", "Fullscreen")}
                  className="absolute bottom-3 right-3 grid h-10 w-10 place-items-center rounded-xl bg-black/70 text-white backdrop-blur transition hover:bg-black focus:outline-none focus:ring-2 focus:ring-cyan-300 z-10"
                  onClick={() => {
                    if (isFullscreen) setIsFullscreen(false);
                    else openNativeFullscreen();
                  }}
                >
                  {isFullscreen ? (
                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4h4M4 16v4h4M20 8V4h-4M20 16v4h-4" />
                    </svg>
                  ) : (
                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3M3 16v3a2 2 0 002 2h3m8 0h3a2 2 0 002-2v-3" />
                    </svg>
                  )}
                </button>
                {isFullscreen && (
                  <button
                    type="button"
                    className="absolute top-4 right-4 z-[100000] grid h-10 w-10 place-items-center rounded-full bg-black/60 text-white backdrop-blur transition hover:bg-black focus:outline-none"
                    onClick={() => setIsFullscreen(false)}
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
                <h1 className="text-lg sm:text-2xl font-bold text-gray-900 dark:text-white mb-2 leading-tight">
                  {video.title}
                </h1>
                
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
                  <div className="flex items-center justify-between sm:justify-start w-full sm:w-auto gap-3">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 font-black text-lg shrink-0">
                        D
                      </div>
                      <div>
                        <h3 className="font-bold text-gray-900 dark:text-white text-[15px]">Diamond Education</h3>
                        <p className="text-xs text-gray-500">{tt("videos.officialChannel", "Rasmiy kanal")}</p>
                      </div>
                    </div>

                  </div>
                  
                  <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0 no-scrollbar">
                    <div className="flex items-center bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 rounded-full transition-colors h-9 shrink-0">
                      <button onClick={toggleLike} className={`flex items-center gap-1.5 px-3 sm:px-4 h-full border-r border-gray-300 dark:border-gray-600 font-bold text-sm ${video.liked_by_me ? "text-blue-600 dark:text-blue-400" : "text-gray-900 dark:text-white"}`}>
                        {video.liked_by_me ? (
                          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>
                        ) : (
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>
                        )}
                        {video.like_count ? video.like_count : tt("videos.like", "Yoqdi")}
                      </button>
                      <button onClick={handleDislike} className={`flex items-center justify-center px-3 sm:px-4 h-full ${disliked ? "text-blue-600 dark:text-blue-400" : "text-gray-900 dark:text-white"}`}>
                        {disliked ? (
                          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-2"></path></svg>
                        ) : (
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-2"></path></svg>
                        )}
                      </button>
                    </div>
                    <button className="flex items-center gap-1.5 px-3 sm:px-4 h-9 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 rounded-full font-bold text-sm text-gray-900 dark:text-white transition-colors shrink-0">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
                      {tt("common.share", "Ulashish")}
                    </button>
                  </div>
                </div>

                <div 
                  className="bg-gray-200/50 hover:bg-gray-200 dark:bg-gray-800/60 dark:hover:bg-gray-800 rounded-xl p-3 sm:p-4 text-sm transition-colors cursor-pointer mt-2"
                  onClick={() => setDescExpanded(!descExpanded)}
                >
                  <div className="flex gap-2 font-bold text-gray-900 dark:text-white mb-1">
                    <span>{tt("videos.views", "{count} ko'rish", { count: String(video.view_count || 0) })}</span>
                    <span>•</span>
                    <span>{tt("videos.duration", "Davomiylik: {duration}", { duration: formattedDuration })}</span>
                  </div>
                  <div className={`prose dark:prose-invert max-w-none text-gray-800 dark:text-gray-200 ${descExpanded ? '' : 'line-clamp-2'}`}>
                    {video.description ? (
                      <p className="whitespace-pre-wrap leading-relaxed">{video.description}</p>
                    ) : (
                      <p className="italic opacity-70">{tt("videos.noDescription", "Tavsif kiritilmagan.")}</p>
                    )}
                  </div>
                  {video.description && video.description.length > 100 && (
                    <button className="font-bold mt-2 text-gray-900 dark:text-white">
                      {descExpanded ? tt("common.collapse", "Yig'ish") : tt("common.showMore", "Ko'proq")}
                    </button>
                  )}
                </div>

                {/* Video Test Section */}
                {testResult ? (
                  <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 dark:border-emerald-500/20 dark:bg-emerald-500/10 px-4 py-3 text-sm font-bold text-emerald-700 dark:text-emerald-300 flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span>✅ {tt("library.testSubmitted", "Test topshirilgan")}</span>
                    <span className="opacity-80">
                      {testResultSummary.correct}/{testResultSummary.total}
                      {testResultSummary.delta ? ` · +${testResultSummary.delta} D'Point` : ""}
                    </span>
                  </div>
                ) : testData ? (
                  <div className="mt-4 rounded-xl border border-cyan-200 bg-cyan-50 dark:border-cyan-500/20 dark:bg-cyan-500/10 px-4 py-3 flex flex-wrap items-center justify-between gap-3">
                    <div className="text-sm font-bold text-cyan-800 dark:text-cyan-200">
                      📝 {tt("video.testReady", "Video testi tayyor")} · {Number(testData?.question_count ?? (testData?.questions || []).length ?? 0)} {tt("test.questions", "savol")}
                    </div>
                    <button
                      type="button"
                      className="rounded-xl bg-cyan-500 hover:bg-cyan-600 text-white px-4 py-2 font-bold text-sm transition-colors"
                      onClick={() => router.push(`/student/content-tests/video/${safeVideoId}`)}
                    >
                      {tt("library.startTest", "Testni boshlash")}
                    </button>
                  </div>
                ) : testError && testError !== "Test hali qo'shilmagan" ? (
                  <div className="mt-4 rounded-xl border border-gray-200 bg-gray-50 dark:border-white/10 dark:bg-white/5 px-4 py-3 text-sm font-semibold text-gray-600 dark:text-gray-300 flex items-center gap-2">
                    <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
                    {testError}
                  </div>
                ) : null}



                {/* Comments Section */}
                <VideoComments videoId={safeVideoId} />

              </div>
              {/* End of Left Column */}
              </div>

              {/* Sidebar / Related Videos */}
              <div className="w-full lg:w-[350px] xl:w-[400px] flex-shrink-0 pt-2 lg:pt-0">
                {/* Section Header */}
                <div className="flex items-center gap-2 px-1 mb-3">
                  <svg className="w-4 h-4 text-blue-500" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M4 6h16M4 12h16M4 18h7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none"/>
                  </svg>
                  <h2 className="text-sm font-extrabold text-gray-900 dark:text-white tracking-wide uppercase">
                    {tt("videos.recommended", "Tavsiya etilgan videolar")}
                  </h2>
                </div>

                <div className="flex flex-col gap-1">
                  {related.length > 0 ? (
                    related.map((item) => {
                      const mins = Math.floor(Number(item.duration || 0) / 60);
                      const secs = (Number(item.duration || 0) % 60).toString().padStart(2, "0");
                      const hasDuration = Number(item.duration || 0) > 0;
                      const subjectLabel = item.subject || item.category || "";
                      return (
                        <a
                          key={item.id}
                          href={`/student/videos/${item.id}`}
                          className="group flex gap-3 rounded-xl hover:bg-gray-100 dark:hover:bg-white/5 transition-all duration-200 p-2 cursor-pointer"
                        >
                          {/* Thumbnail */}
                          <div className="w-[156px] min-w-[156px] aspect-video rounded-lg overflow-hidden bg-gray-200 dark:bg-gray-800 flex-shrink-0 relative shadow-sm">
                            {item.thumbnail_url ? (
                              <img
                                src={resolveMediaUrl(item.thumbnail_url)}
                                alt={item.title}
                                className="w-full h-full object-cover group-hover:scale-[1.04] transition-transform duration-300"
                              />
                            ) : (
                              <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-blue-500/20 to-purple-500/20">
                                <svg className="w-8 h-8 text-white/40" fill="currentColor" viewBox="0 0 24 24">
                                  <path d="M8 5v14l11-7z"/>
                                </svg>
                              </div>
                            )}
                            {/* Play overlay on hover */}
                            <div className="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                              <div className="w-9 h-9 rounded-full bg-white/90 flex items-center justify-center shadow-lg">
                                <svg className="w-4 h-4 text-gray-900 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                                  <path d="M8 5v14l11-7z"/>
                                </svg>
                              </div>
                            </div>
                            {hasDuration && (
                              <span className="absolute bottom-1.5 right-1.5 bg-black/85 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-md shadow">
                                {mins}:{secs}
                              </span>
                            )}
                            {item.progress?.completed && (
                              <span className="absolute top-1.5 left-1.5 bg-green-500 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-md">
                                ✓
                              </span>
                            )}
                          </div>

                          {/* Info */}
                          <div className="flex flex-col py-0.5 min-w-0 flex-1">
                            <h4 className="font-semibold text-[13px] text-gray-900 dark:text-white line-clamp-2 leading-snug group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                              {item.title}
                            </h4>
                            <span className="text-[12px] text-gray-500 dark:text-gray-400 mt-1 font-medium">Diamond Education</span>
                            <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                              <span className="text-[11px] text-gray-400 dark:text-gray-500">
                                {Number(item.view_count || 0).toLocaleString()} {tt("videos.viewsText", "ko'rish")}
                              </span>
                              {subjectLabel && (
                                <>
                                  <span className="text-[10px] text-gray-300 dark:text-gray-600">•</span>
                                  <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 uppercase tracking-wide">
                                    {subjectLabel}
                                  </span>
                                </>
                              )}
                            </div>
                          </div>
                        </a>
                      );
                    })
                  ) : (
                    <div className="flex flex-col items-center justify-center py-12 text-center gap-3">
                      <div className="w-14 h-14 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                        <svg className="w-7 h-7 text-gray-400" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z" />
                        </svg>
                      </div>
                      <p className="text-sm text-gray-500 dark:text-gray-400 font-medium">
                        {tt("videos.noRelated", "Sizning faningiz bo'yicha boshqa videolar hozircha yo'q")}
                      </p>
                    </div>
                  )}
                </div>
              </div>

            </div>
          ) : null}
        </div>
      </div>
    </main>
  );
}
