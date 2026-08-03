"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { PublicShell } from "../../public-shell";
import { fetchPublicVideo, recordPublicVideoView, recordPublicVideoLike, API_BASE, GenericRow } from "../../public-data";
import { useWebLocale, useWebT } from "../../ui/web-i18n";
import VideoComments from "../../ui/video-comments";

function formatViews(views: number | undefined | null, tt: ReturnType<typeof useWebT>) {
  const count = Number(views || 0);
  if (!count) return tt("videos.views.zero", "0 ko'rish");
  if (count >= 1000000) return `${(count / 1000000).toFixed(1)}${tt("videos.views.million", " mln ko'rish")}`;
  if (count >= 1000) return `${(count / 1000).toFixed(1)}${tt("videos.views.thousand", " ming ko'rish")}`;
  return `${count} ${tt("videos.views.plural", "ko'rish")}`;
}

function formatDate(dateStr: string | undefined | null, locale: "uz" | "ru" | "en") {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    const intlLocale = locale === "ru" ? "ru-RU" : locale === "en" ? "en-US" : "uz-UZ";
    return new Intl.DateTimeFormat(intlLocale, { day: "numeric", month: "short", year: "numeric" }).format(d);
  } catch {
    return dateStr;
  }
}

export default function VideoPlayerPage() {
  const params = useParams();
  const videoId = params?.videoId as string;
  const locale = useWebLocale();
  const tt = useWebT();

  const [video, setVideo] = useState<GenericRow | null>(null);
  const [related, setRelated] = useState<GenericRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  
  const [liked, setLiked] = useState(false);
  const [disliked, setDisliked] = useState(false);

  const [descExpanded, setDescExpanded] = useState(false);
  const [playerLoadError, setPlayerLoadError] = useState(false);

  useEffect(() => {
    if (!videoId) return;
    let active = true;
    try {
      const localLiked = localStorage.getItem(`video_${videoId}_liked`) === "true";
      const localDisliked = localStorage.getItem(`video_${videoId}_disliked`) === "true";
      window.setTimeout(() => {
        if (!active) return;
        setLiked(localLiked);
        setDisliked(localDisliked);
      }, 0);
    } catch {}

    return () => {
      active = false;
    };
  }, [videoId]);

  useEffect(() => {
    if (!videoId) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchPublicVideo(videoId);
        if (cancelled) return;
        setVideo(data.video);
        setRelated(data.related || []);

        // Increment view count
        recordPublicVideoView(videoId).catch(() => {});
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : tt("videos.loadError", "Video yuklanmadi"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();

    return () => {
      cancelled = true;
    };
  }, [tt, videoId]);

  const handleLike = async () => {
    if (!video) return;
    if (liked) {
      setLiked(false);
      try { localStorage.removeItem(`video_${video.id}_liked`); } catch {}
      setVideo({ ...video, like_count: Math.max(0, (video.like_count || 0) - 1) });
      recordPublicVideoLike(video.id, "unlike").catch(() => {});
    } else {
      setLiked(true);
      try { localStorage.setItem(`video_${video.id}_liked`, "true"); } catch {}
      if (disliked) {
        setDisliked(false);
        try { localStorage.removeItem(`video_${video.id}_disliked`); } catch {}
      }
      setVideo({ ...video, like_count: (video.like_count || 0) + 1 });
      recordPublicVideoLike(video.id, "like").catch(() => {});
    }
  };

  const handleDislike = () => {
    if (disliked) {
      setDisliked(false);
      try { localStorage.removeItem(`video_${video?.id}_disliked`); } catch {}
    } else {
      setDisliked(true);
      try { localStorage.setItem(`video_${video?.id}_disliked`, "true"); } catch {}
      if (liked) {
        setLiked(false);
        try { localStorage.removeItem(`video_${video?.id}_liked`); } catch {}
        if (video) {
          setVideo({ ...video, like_count: Math.max(0, (video.like_count || 0) - 1) });
          recordPublicVideoLike(video.id, "unlike").catch(() => {});
        }
      }
    }
  };

  if (loading) {
    return (
      <PublicShell activeTab="videos" kicker={tt("common.loading", "Yuklanmoqda...")} title="">
        <div className="flex items-center justify-center min-h-[50vh]">
          <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
        </div>
      </PublicShell>
    );
  }

  if (error || !video) {
    return (
      <PublicShell activeTab="videos" kicker={tt("common.error", "Xatolik")} title="">
        <div className="max-w-xl mx-auto py-24 text-center">
          <span className="text-6xl mb-6 opacity-30">⚠️</span>
          <h1 className="text-2xl font-black text-gray-900 dark:text-white mb-4">
            {error || tt("videos.notFound", "Video topilmadi")}
          </h1>
          <Link href="/videos" className="text-blue-600 font-bold hover:underline">
            ← {tt("videos.backToAll", "Barcha videolarga qaytish")}
          </Link>
        </div>
      </PublicShell>
    );
  }

  const isYouTube = video.video_url && (video.video_url.includes("youtube.com") || video.video_url.includes("youtu.be"));
  let embedUrl = video.video_url;
  if (isYouTube) {
    const match = video.video_url.match(/[?&]v=([^&]+)/) || video.video_url.match(/youtu\.be\/([^?]+)/);
    if (match && match[1]) {
      embedUrl = `https://www.youtube.com/embed/${match[1]}?autoplay=1&rel=0`;
    }
  } else if (video.video_url && video.video_url.startsWith("/")) {
    embedUrl = `${API_BASE}${video.video_url}`;
  }

  return (
    <PublicShell
      activeTab="videos"
      kicker={video.subject ? tt(`public.subject.${video.subject}`, String(video.subject)) : tt("videos.defaultTitle", "Video dars")}
      title={video.title || tt("videos.defaultTitle", "Video dars")}
      subtitle={video.description || ""}
    >
      <div className="w-full max-w-[1800px] mx-auto flex flex-col lg:flex-row gap-8 sm:px-6 lg:px-8 2xl:px-12">
        
        {/* Main Player Area */}
        <div className="flex-1">
          <div className="bg-black sm:rounded-2xl overflow-hidden shadow-2xl aspect-video w-full relative mb-6">
            {embedUrl ? (
              isYouTube ? (
              <iframe
                  src={embedUrl}
                  title={video.title || tt("videos.defaultTitle", "Video dars")}
                  className="absolute inset-0 w-full h-full border-0"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                  onError={() => setPlayerLoadError(true)}
                ></iframe>
              ) : (
                <video
                  src={embedUrl}
                  controls
                  autoPlay
                  className="absolute inset-0 w-full h-full"
                  poster={video.thumbnail_url ? (video.thumbnail_url.startsWith("/") ? `${API_BASE}${video.thumbnail_url}` : video.thumbnail_url) : undefined}
                  onError={() => setPlayerLoadError(true)}
                ></video>
              )
            ) : (
              <div className="absolute inset-0 flex items-center justify-center text-white/50 flex-col">
                <span className="text-4xl mb-2">🚫</span>
                <span>{tt("videos.notAvailable", "Video mavjud emas")}</span>
              </div>
            )}
          </div>

          {playerLoadError ? (
            <div className="rounded-xl border border-red-200 bg-red-50 text-red-600 px-4 py-3 text-sm font-semibold mb-6">
              {tt("videos.playerError", "Video player yuklanmadi. Qayta urinib ko'ring.")}
            </div>
          ) : null}

          <div className="px-4 sm:px-0">
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white mb-3 leading-tight">
              {video.title || tt("videos.defaultTitle", "Video dars")}
            </h1>
            
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
              {/* Channel / Author placeholder */}
              <div className="flex items-center justify-between sm:justify-start w-full sm:w-auto gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 font-black text-xl shrink-0">
                    D
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-900 dark:text-white text-sm">Diamond Education</h3>
                    <p className="text-xs text-gray-500">{tt("videos.officialChannel", "Rasmiy kanal")}</p>
                  </div>
                </div>

              </div>
              
              {/* Actions */}
              <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
                <div className="flex items-center bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 rounded-full transition-colors h-9">
                  <button onClick={handleLike} className={`flex items-center gap-1.5 px-4 h-full border-r border-gray-300 dark:border-gray-600 font-semibold text-sm ${liked ? "text-blue-600 dark:text-blue-400" : "text-gray-900 dark:text-white"}`}>
                    {liked ? (
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
                  {tt("common.share", "Ulashish")}
                </button>
              </div>
            </div>

            <div 
              className="bg-gray-200/50 hover:bg-gray-200 dark:bg-gray-800/60 dark:hover:bg-gray-800 rounded-xl p-3 sm:p-4 text-sm transition-colors cursor-pointer mt-2"
              onClick={() => setDescExpanded(!descExpanded)}
            >
              <div className="flex gap-2 font-bold text-gray-900 dark:text-white mb-1">
                <span>{formatViews((video.view_count || 0) + 1, tt)}</span>
                <span>•</span>
                <span>{formatDate(video.created_at, locale)}</span>
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

            {/* Comments Section */}
            <VideoComments videoId={videoId} />

          </div>
        </div>

        {/* Sidebar / Related */}
        <div className="w-full lg:w-[350px] xl:w-[400px] flex-shrink-0">
          <div className="flex flex-col gap-3">
            {related.length > 0 ? (
              related.map((item) => (
                <Link
                  key={item.id}
                  href={`/videos/${item.id}`}
                  className="group flex gap-2 sm:gap-3 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors p-1"
                >
                  <div className="w-40 sm:w-44 aspect-video rounded-lg overflow-hidden bg-gray-100 dark:bg-gray-700 flex-shrink-0 relative">
                    {item.thumbnail_url ? (
                      <img
                        src={String(item.thumbnail_url).startsWith("/") ? `${API_BASE}${item.thumbnail_url}` : String(item.thumbnail_url)}
                        alt={item.title || tt("videos.defaultTitle", "Video dars")}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                      />
                    ) : (
                      <div className="absolute inset-0 flex items-center justify-center opacity-30">▶️</div>
                    )}
                    <span className="absolute bottom-1 right-1 bg-black/80 text-white text-[10px] font-bold px-1.5 py-0.5 rounded shadow">
                      {item.duration || "0:00"}
                    </span>
                  </div>
                  <div className="flex flex-col py-0.5">
                    <h4 className="font-bold text-sm text-gray-900 dark:text-white line-clamp-2 leading-tight group-hover:text-blue-600 transition-colors">
                      {item.title || tt("videos.defaultTitle", "Video dars")}
                    </h4>
                    <span className="text-[13px] text-gray-500 dark:text-gray-400 mt-1">Diamond Education</span>
                    <span className="text-[12px] text-gray-500 dark:text-gray-400 mt-0.5">
                      {formatViews(item.view_count, tt)} • {formatDate(item.created_at, locale)}
                    </span>
                  </div>
                </Link>
              ))
            ) : null}
          </div>
        </div>
      </div>
    </PublicShell>
  );
}
