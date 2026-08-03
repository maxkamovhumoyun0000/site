"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

type VideoItem = {
  id: number;
  title: string;
  description?: string;
  subject?: string;
  category?: string;
  level?: string;
  thumbnail_url?: string;
  duration?: number;
};

export function SupportVideos({ apiFetch }: { apiFetch: (path: string, options?: any) => Promise<any> }) {
  const router = useRouter();
  const [items, setItems] = useState<VideoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [subjectFilter, setSubjectFilter] = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/support/videos");
      setItems(Array.isArray(res?.items) ? res.items : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Videolarni yuklab bo'lmadi");
    }
    setLoading(false);
  }, [apiFetch]);

  useEffect(() => {
    let mounted = true;
    const timer = window.setTimeout(() => {
      if (!mounted) return;
      load().catch(() => null);
    }, 0);
    return () => {
      mounted = false;
      window.clearTimeout(timer);
    };
  }, [load]);

  function mediaUrl(url?: string) {
    const raw = String(url || "").trim();
    if (!raw) return "";
    return raw.startsWith("/") ? `${API_BASE}${raw}` : raw;
  }

  function openVideoDetail(video: VideoItem) {
    const videoId = Number(video?.id || (video as any)?.video_id || 0);
    if (!Number.isInteger(videoId) || videoId <= 0) {
      setError("Video identifikatori topilmadi.");
      return;
    }
    router.push(`/support/videos/${videoId}`);
  }

  if (loading) return <div className="py-10 text-center text-ink-500">Loading...</div>;
  const subjectOptions = Array.from(new Set(items.map((item) => String(item.subject || "").trim()).filter(Boolean)));
  const filtered = items.filter((item) => subjectFilter === "all" || String(item.subject || "").trim() === subjectFilter);

  return (
    <div className="space-y-4">
      {error ? <div className="rounded-xl bg-red-50 text-red-700 border border-red-200 px-4 py-2 text-sm">{error}</div> : null}
      <div className="rounded-2xl border border-line bg-white p-3 dark:border-white/10 dark:bg-white/5">
        <select
          value={subjectFilter}
          onChange={(event) => setSubjectFilter(event.target.value)}
          className="w-full max-w-xs rounded-xl border border-line bg-white px-4 py-2.5 text-sm font-semibold text-navy-900 outline-none focus:ring-2 focus:ring-cyan-500/30 dark:border-white/10 dark:bg-navy-900 dark:text-white"
        >
          <option value="all">Barcha fanlar</option>
          {subjectOptions.map((subject) => (
            <option key={`support-video-subject-${subject}`} value={subject}>{subject}</option>
          ))}
        </select>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:gap-4">
        {filtered.map((v) => (
          <button
            key={v.id}
            type="button"
            onClick={() => openVideoDetail(v)}
            className="media-library-card text-left rounded-2xl border border-line dark:border-white/10 bg-white dark:bg-navy-900/40 overflow-hidden"
          >
            <div className="aspect-square bg-surface-soft dark:bg-navy-900 overflow-hidden">
              {v.thumbnail_url ? <img src={mediaUrl(v.thumbnail_url)} alt={v.title} loading="lazy" decoding="async" className="w-full h-full object-contain bg-white dark:bg-navy-950" /> : null}
            </div>
            <div className="p-3">
              <h3 className="text-sm sm:text-base font-bold text-navy-900 dark:text-white line-clamp-2">{v.title}</h3>
              <p className="text-xs text-ink-600 dark:text-navy-300 mt-1 line-clamp-2">{v.description || "-"}</p>
              <div className="mt-2 text-[11px] text-ink-500 dark:text-navy-300">{v.subject || "-"} · {v.level || "B1"} · {v.category || "-"} · {Math.floor(Number(v.duration || 0) / 60)}:{String(Number(v.duration || 0) % 60).padStart(2, "0")}</div>
            </div>
          </button>
        ))}
        {!filtered.length ? <div className="col-span-2 rounded-2xl border border-dashed border-line p-8 text-center text-sm font-semibold text-ink-500 dark:border-white/10 dark:text-navy-300">Videolar topilmadi</div> : null}
      </div>
    </div>
  );
}
