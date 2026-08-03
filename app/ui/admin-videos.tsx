"use client";
import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ModalPortal } from "./modal-portal";
import { SharedTestEditor, validateTestQuestions, TestQuestion } from "./shared-test-editor";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

type VideoItem = {
  id: number;
  title: string;
  subject?: string;
  description?: string;
  author?: string;
  category?: string;
  level?: string;
  thumbnail_url?: string;
  video_url?: string;
  video_asset_id?: number | null;
  duration?: number;
  view_count?: number;
  like_count?: number;
  created_at?: string;
  is_published?: boolean;
  missing_original?: boolean;
  missing_message?: string;
  media_status?: string;
  teacher_id?: number | null;
  support_teacher_ids?: string | null;
};

type VideoFormState = {
  title: string;
  subject: string;
  description: string;
  author: string;
  category: string;
  level: string;
  thumbnail_url: string;
  video_url: string;
  video_asset_id: number | null;
  duration: string;
  is_published: boolean;
  teacher_id: number | null;
  support_teacher_ids: string;
};

const EMPTY_FORM: VideoFormState = {
  title: "",
  subject: "English",
  description: "",
  author: "",
  category: "",
  level: "",
  thumbnail_url: "",
  video_url: "",
  video_asset_id: null,
  duration: "0",
  is_published: true,
  teacher_id: null,
  support_teacher_ids: "",
};

export function AdminVideos({
  apiFetch,
  rolePrefix = "admin",
  canUploadVideos = false,
  canManageVideoTests = false,
}: {
  apiFetch: (path: string, options?: any) => Promise<any>;
  rolePrefix?: "admin" | "teacher";
  canUploadVideos?: boolean;
  canManageVideoTests?: boolean;
}) {
  const router = useRouter();
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [uploadingVideoFile, setUploadingVideoFile] = useState(false);
  const [videoUploadProgress, setVideoUploadProgress] = useState(0);
  const [selectedVideoFileName, setSelectedVideoFileName] = useState("");
  const [uploadingThumbFile, setUploadingThumbFile] = useState(false);
  const [selectedThumbFileName, setSelectedThumbFileName] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState<VideoFormState>(EMPTY_FORM);
  const [subjectFilter, setSubjectFilter] = useState("all");
  const [levelFilter, setLevelFilter] = useState("all");
  const [teachers, setTeachers] = useState<any[]>([]);
  const [fetchingTeachers, setFetchingTeachers] = useState(false);

  // Test editor state
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [testVideoId, setTestVideoId] = useState<number | null>(null);
  const [testVideoTitle, setTestVideoTitle] = useState("");
  const [testQuestions, setTestQuestions] = useState<TestQuestion[]>([]);
  const [testBusy, setTestBusy] = useState(false);
  const apiPrefix = rolePrefix === "admin" ? "/admin" : "/teacher";
  const canManageVideos = rolePrefix === "admin";
  const canManageTests = rolePrefix === "admin" || Boolean(canManageVideoTests);

  function mediaUrl(url?: string) {
    const raw = String(url || "").trim();
    if (!raw) return "";
    return raw.startsWith("/") ? `${API_BASE}${raw}` : raw;
  }

  function emitToast(message: string) {
    if (typeof window === "undefined") return;
    const text = String(message || "").trim();
    if (!text) return;
    window.dispatchEvent(new CustomEvent("diamond:toast", { detail: { message: text } }));
  }

  function normalizeUploadError(error: unknown, fallback: string) {
    const raw = error instanceof Error ? error.message : fallback;
    const text = String(raw || "").trim();
    const lowered = text.toLowerCase();
    if (!text) return fallback;
    if (lowered.includes("413") || lowered.includes("juda katta") || lowered.includes("too large")) {
      return "Fayl hajmi juda katta";
    }
    if (lowered.includes("422") || lowered.includes("format") || lowered.includes("type")) {
      return "Fayl turi noto'g'ri";
    }
    if (lowered.includes("timeout")) {
      return "So'rov vaqti tugadi. Qayta urinib ko'ring.";
    }
    if (lowered.includes("not found")) {
      return "Video topilmadi";
    }
    if (lowered.includes("could not register media asset") || lowered.includes("internal server error")) {
      return "Video yuklanmadi. Qayta urinib ko'ring.";
    }
    if (lowered.includes("<html")) {
      return fallback;
    }
    return text;
  }

  useEffect(() => {
    if (error) emitToast(error);
     
  }, [error]);

  useEffect(() => {
    if (notice) emitToast(notice);
     
  }, [notice]);

  const fetchVideos = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch(rolePrefix === "admin" ? "/admin/videos" : "/teacher/videos");
      if (res && res.items) setVideos(res.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Videolarni yuklab bo'lmadi");
    }
    setLoading(false);
  }, [apiFetch, rolePrefix]);

  useEffect(() => {
    let mounted = true;
    const timer = window.setTimeout(() => {
      if (!mounted) return;
      fetchVideos().catch(() => null);
      if (rolePrefix === "admin") {
        setFetchingTeachers(true);
        apiFetch("/admin/teachers/search")
          .then((res) => { if (mounted && res?.items) setTeachers(res.items); })
          .catch(() => null)
          .finally(() => { if (mounted) setFetchingTeachers(false); });
      }
    }, 0);
    return () => {
      mounted = false;
      window.clearTimeout(timer);
    };
  }, []); // run once on mount; avoid re-trigger on apiFetch identity changes from parent re-renders

  const filtered = videos.filter((video) => {
    const text = `${video.title || ""} ${video.author || ""} ${video.category || ""} ${video.subject || ""} ${video.level || ""}`.toLowerCase();
    const matchesQuery = text.includes(query.trim().toLowerCase());
    const matchesSubject = subjectFilter === "all" || String(video.subject || "").trim() === subjectFilter;
    const matchesLevel = levelFilter === "all" || String(video.level || "").trim() === levelFilter;
    return matchesQuery && matchesSubject && matchesLevel;
  });
  const subjectOptions = Array.from(new Set(videos.map((video) => String(video.subject || "").trim()).filter(Boolean)));
  const levelOptions = Array.from(new Set(videos.map((video) => String(video.level || "").trim()).filter(Boolean)));

  function openVideoDetail(video: VideoItem) {
    const videoId = Number(video?.id || (video as any)?.video_id || 0);
    if (!Number.isInteger(videoId) || videoId <= 0) {
      setError("Video identifikatori topilmadi.");
      return;
    }
    router.push(`/${rolePrefix}/videos/${videoId}`);
  }

  function toFormState(video?: VideoItem | null): VideoFormState {
    if (!video) return { ...EMPTY_FORM };
    return {
      title: String(video.title || ""),
      subject: String(video.subject || "English"),
      description: String(video.description || ""),
      author: String(video.author || ""),
      category: String(video.category || ""),
      level: String(video.level || ""),
      thumbnail_url: String(video.thumbnail_url || ""),
      video_url: String(video.video_url || ""),
      video_asset_id: Number(video.video_asset_id || 0) || null,
      duration: String(Number(video.duration || 0)),
      is_published: Boolean(video.is_published),
      teacher_id: video.teacher_id || null,
      support_teacher_ids: video.support_teacher_ids || "",
    };
  }

  function openCreateModal() {
    setEditingId(null);
    setForm(toFormState(null));
    setSelectedVideoFileName("");
    setSelectedThumbFileName("");
    setShowModal(true);
    setNotice("");
    setError("");
  }

  function openEditModal(video: VideoItem) {
    setEditingId(Number(video.id || 0));
    setForm(toFormState(video));
    setSelectedVideoFileName("");
    setSelectedThumbFileName("");
    setShowModal(true);
    setNotice("");
    setError("");
  }

  function closeModal() {
    if (saving) return;
    setShowModal(false);
  }

  async function openTestModal(video: VideoItem) {
    const vid = Number(video.id || 0);
    setTestVideoId(vid);
    setTestVideoTitle(video.title || "");
    setTestQuestions([]);
    setTestModalOpen(true);
    setError("");
    setNotice("");
    setTestBusy(true);
    try {
      const res = await apiFetch(`/content-tests/video/${vid}`);
      if (res?.test?.questions) {
        setTestQuestions(res.test.questions);
      }
    } catch (e) {
      // It's okay if not found
    } finally {
      setTestBusy(false);
    }
  }

  async function saveTestQuestions() {
    if (!testVideoId) return;
    const validationError = validateTestQuestions(testQuestions);
    if (validationError) {
      setError(validationError);
      return;
    }
    setTestBusy(true);
    setError("");
    try {
      await apiFetch(`/content-tests/video/${testVideoId}`, {
        method: "POST",
        body: { questions: testQuestions }
      });
      setNotice("");
      emitToast("Test saqlandi.");
      setTestModalOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Testni saqlab bo'lmadi.");
    } finally {
      setTestBusy(false);
    }
  }

  function handleFormChange<K extends keyof VideoFormState>(field: K, value: VideoFormState[K]) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function saveVideo() {
    const title = form.title.trim();
    if (title.length < 2) {
      setError("Video sarlavhasi kamida 2 ta belgidan iborat bo'lishi kerak.");
      return;
    }
    if (form.video_url.trim().length < 5 && !form.video_asset_id) {
      setError("Video URL kiriting yoki video fayl yuklang.");
      return;
    }
    if (!form.thumbnail_url.trim()) {
      setError("Thumbnail yuklash majburiy.");
      return;
    }
    if (rolePrefix === "admin" && !form.teacher_id) {
      setError("O'qituvchini tanlash majburiy.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const body = {
        title,
        subject: form.subject.trim(),
        description: form.description.trim(),
        author: form.author.trim(),
        category: "",
        level: "",
        thumbnail_url: form.thumbnail_url.trim(),
        video_url: form.video_url.trim(),
        video_asset_id: form.video_asset_id || null,
        duration: Math.max(0, Number(form.duration || 0)),
        is_published: true,
        teacher_id: form.teacher_id,
        support_teacher_ids: form.support_teacher_ids,
      };
      if (editingId) {
        await apiFetch(`/admin/videos/${editingId}`, { method: "PUT", body });
        setNotice("Video yangilandi.");
      } else {
        await apiFetch(`${apiPrefix}/videos`, { method: "POST", body });
        setNotice("Video yaratildi.");
      }
      setShowModal(false);
      await fetchVideos();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Saqlashda xatolik yuz berdi.");
    } finally {
      setSaving(false);
    }
  }

  async function uploadVideoFile(file: File) {
    if (!file) return;
    const isVideoByType = String(file.type || "").toLowerCase().startsWith("video/");
    const isVideoByExt = /\.(mp4|mov|mkv|webm|m4v)$/i.test(String(file.name || ""));
    if (!isVideoByType && !isVideoByExt) {
      setError("Fayl turi noto'g'ri");
      return;
    }
    const maxBytes = 2000 * 1024 * 1024;
    if (Number(file.size || 0) > maxBytes) {
      setError("Fayl hajmi juda katta");
      return;
    }
    setUploadingVideoFile(true);
    setVideoUploadProgress(0);
    setError("");
    setNotice("");
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("asset_type", "video");
      if (editingId) {
        body.append("target", "video");
        body.append("entity_id", String(editingId));
      }
      
      const token = localStorage.getItem("diamond_token") || "";
      const url = `${API_BASE}${apiPrefix}/upload/media`;
      
      const res = await new Promise<any>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", url, true);
        if (token) {
          xhr.setRequestHeader("Authorization", `Bearer ${token}`);
        }
        
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            const percent = Math.round((event.loaded / event.total) * 100);
            setVideoUploadProgress(percent);
          }
        };
        
        xhr.onload = () => {
          try {
            if (xhr.status >= 200 && xhr.status < 300) {
              resolve(JSON.parse(xhr.responseText));
            } else {
              const errResp = JSON.parse(xhr.responseText);
              reject(new Error(errResp.detail || errResp.message || `Yuklash xatosi: ${xhr.status}`));
            }
          } catch (e) {
            reject(new Error(`Yuklash xatosi: ${xhr.status}`));
          }
        };
        
        xhr.onerror = () => reject(new Error("Tarmoq xatosi. Video yuklanmadi."));
        xhr.send(body);
      });
      
      const assetId = Number(res?.asset?.id || 0) || null;
      const streamUrl = String(res?.asset?.stream_url || "").trim();
      if (!assetId || !streamUrl) {
        throw new Error("Video yuklanmadi. Qayta urinib ko'ring.");
      }
      setForm((prev) => ({
        ...prev,
        video_asset_id: assetId,
        video_url: prev.video_url.trim() || streamUrl || prev.video_url,
      }));
      if (editingId) {
        await fetchVideos();
      }
      setNotice("Video fayli yuklandi.");
      setSelectedVideoFileName(file.name || "");
    } catch (e) {
      setError(normalizeUploadError(e, "Video yuklanmadi. Qayta urinib ko'ring."));
    } finally {
      setUploadingVideoFile(false);
    }
  }

  async function uploadThumbnailFile(file: File) {
    if (!file) return;
    const lower = String(file.name || "").toLowerCase();
    const byType = String(file.type || "").toLowerCase().startsWith("image/");
    const byExt = /\.(jpg|jpeg|png|webp)$/i.test(lower);
    if (!byType && !byExt) {
      setError("Fayl turi noto'g'ri");
      return;
    }
    const maxBytes = 6 * 1024 * 1024;
    if (Number(file.size || 0) > maxBytes) {
      setError("Fayl hajmi juda katta");
      return;
    }
    setUploadingThumbFile(true);
    setError("");
    setNotice("");
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("asset_type", "image");
      const res = await apiFetch(`${apiPrefix}/upload/media`, {
        method: "POST",
        body,
        timeoutMs: 120000,
      });
      const imageUrl = String(res?.asset?.public_url || res?.asset?.stream_url || "").trim();
      if (!imageUrl) {
        throw new Error("Rasm yuklanmadi. Qayta urinib ko'ring.");
      }
      setForm((prev) => ({ ...prev, thumbnail_url: imageUrl }));
      setNotice("Thumbnail yuklandi.");
      setSelectedThumbFileName(file.name || "");
    } catch (e) {
      setError(normalizeUploadError(e, "Rasm yuklanmadi. Qayta urinib ko'ring."));
    } finally {
      setUploadingThumbFile(false);
    }
  }

  async function deleteVideo(video: VideoItem) {
    if (!confirm(`"${video.title}" videosini o'chirmoqchimisiz?`)) return;
    setError("");
    try {
      await apiFetch(`/admin/videos/${video.id}`, { method: "DELETE" });
      setNotice("Video o'chirildi.");
      setVideos((prev) => prev.filter((item) => Number(item.id || 0) !== Number(video.id || 0)));
      fetchVideos().catch(() => null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Video o'chirilmadi.");
    }
  }

  async function togglePublish(video: VideoItem) {
    setError("");
    try {
      await apiFetch(`/admin/videos/${video.id}`, {
        method: "PUT",
        body: { is_published: !Boolean(video.is_published) },
      });
      setNotice(Boolean(video.is_published) ? "Video qoralamaga o'tkazildi." : "Video nashr qilindi.");
      await fetchVideos();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Holatni yangilab bo'lmadi.");
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex justify-between items-center bg-white dark:bg-slate-800 p-6 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700">
        <div>
          <h2 className="text-2xl font-bold text-slate-800 dark:text-white">Video Darslar</h2>
          <p className="text-slate-500 dark:text-slate-400 mt-1">{rolePrefix === "admin" ? "Platformadagi barcha video darslarni boshqarish" : "Fanlaringiz bo'yicha video darslarni ko'rish"}</p>
        </div>
        {canManageVideos ? (
          <button onClick={openCreateModal} className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-xl font-medium transition-colors shadow-sm shadow-blue-500/30 flex items-center gap-2">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
            Yangi Video
          </button>
        ) : null}
      </div>
      <div className="bg-white dark:bg-slate-800 p-4 rounded-2xl border border-slate-200 dark:border-slate-700 flex flex-col md:flex-row md:items-center gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Video qidirish..."
          className="w-full md:max-w-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-2.5 text-sm text-slate-700 dark:text-slate-200 outline-none focus:ring-2 focus:ring-blue-500/30"
        />
        <div className="flex gap-2 w-full md:w-auto">
          <select
            value={subjectFilter}
            onChange={(event) => setSubjectFilter(event.target.value)}
            className="w-full md:w-48 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-2.5 text-sm text-slate-700 dark:text-slate-200 outline-none focus:ring-2 focus:ring-blue-500/30"
          >
            <option value="all">Barcha fanlar</option>
            {subjectOptions.map((subject) => (
              <option key={`video-subject-${subject}`} value={subject}>{subject}</option>
            ))}
          </select>
          <select
            value={levelFilter}
            onChange={(event) => setLevelFilter(event.target.value)}
            className="w-full md:w-48 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-2.5 text-sm text-slate-700 dark:text-slate-200 outline-none focus:ring-2 focus:ring-blue-500/30"
          >
            <option value="all">Barcha darajalar</option>
            {levelOptions.map((level) => (
              <option key={`video-level-${level}`} value={level}>{level}</option>
            ))}
          </select>
        </div>
        <div className="text-xs text-slate-500 dark:text-slate-400">
          Jami: <span className="font-semibold text-slate-700 dark:text-slate-200">{videos.length}</span>, Filtrlangan:{" "}
          <span className="font-semibold text-slate-700 dark:text-slate-200">{filtered.length}</span>
        </div>
      </div>
      {notice ? <div className="rounded-xl bg-green-50 text-green-700 border border-green-200 px-4 py-2 text-sm">{notice}</div> : null}
      {error ? <div className="rounded-xl bg-red-50 text-red-700 border border-red-200 px-4 py-2 text-sm">{error}</div> : null}

      {loading ? (
        <div className="flex justify-center py-12"><div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div></div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-8 text-center text-slate-500">Videolar topilmadi</div>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
          {filtered.map((v) => (
            <article key={v.id} className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden shadow-sm">
              <button
                type="button"
                className="w-full text-left"
                onClick={() => openVideoDetail(v)}
              >
                <div className="aspect-square bg-slate-100 dark:bg-slate-900 overflow-hidden">
                  {v.thumbnail_url ? <img src={mediaUrl(v.thumbnail_url)} alt={v.title} loading="lazy" decoding="async" className="w-full h-full object-contain bg-white dark:bg-slate-950" /> : null}
                </div>
                <div className="p-3 space-y-2">
                  <h3 className="text-sm sm:text-base font-bold text-slate-800 dark:text-white line-clamp-2">{v.title}</h3>
                  <p className="text-xs text-slate-500 line-clamp-2">{v.description || "-"}</p>
                  {v.missing_original ? (
                    <p className="rounded-lg border border-amber-300 bg-amber-50 px-2 py-1 text-[11px] font-bold text-amber-800 dark:border-amber-400/30 dark:bg-amber-500/10 dark:text-amber-100">
                      {v.missing_message || "Original video fayli topilmadi. Qayta yuklang."}
                    </p>
                  ) : null}
                  <div className="flex items-center justify-between gap-2 text-[11px]">
                    <span className="px-2 py-1 bg-slate-100 dark:bg-slate-700 rounded-md text-slate-700 dark:text-slate-200 font-semibold">{v.level || "B1"}</span>
                    <span className="px-2 py-1 bg-cyan-50 dark:bg-cyan-500/10 rounded-md text-cyan-700 dark:text-cyan-200 font-semibold">{v.subject || "-"}</span>
                    <span className="text-slate-600 dark:text-slate-300">
                      {Number(v.duration || 0) > 0 ? `${Math.floor(Number(v.duration || 0) / 60)}:${String(Number(v.duration || 0) % 60).padStart(2, "0")}` : "—"}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                    <span>Ko'rishlar: {Number(v.view_count || 0)}</span>
                    <span>Like: {Number(v.like_count || 0)}</span>
                    {v.created_at ? <span>{new Date(String(v.created_at)).toLocaleDateString()}</span> : null}
                  </div>
                </div>
              </button>
              {rolePrefix === "admin" || canManageTests ? (
                <div className="px-3 pb-3 flex flex-wrap items-center gap-2">
                  {rolePrefix === "admin" ? (
                    <button onClick={() => openEditModal(v)} className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 font-medium text-xs">Tahrirlash</button>
                  ) : null}
                  {canManageTests ? (
                    <button onClick={() => openTestModal(v)} className="text-cyan-600 hover:text-cyan-800 dark:text-cyan-400 dark:hover:text-cyan-300 font-medium text-xs">Testlar</button>
                  ) : null}
                  {rolePrefix === "admin" ? (
                    <button onClick={() => deleteVideo(v)} className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300 font-medium text-xs">O&apos;chirish</button>
                  ) : null}
                </div>
              ) : null}
            </article>
          ))}
        </div>
      )}
      <ModalPortal open={showModal || testModalOpen}>
      {showModal ? (
        <div className="overlay-modal-backdrop" onClick={closeModal}>
          <div className="overlay-modal-card admin-wide-modal" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-slate-800 dark:text-white">{editingId ? "Videoni tahrirlash" : "Yangi video qo&apos;shish"}</h3>
              <button onClick={closeModal} className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200">X</button>
            </div>
            {error ? <div className="rounded-xl bg-red-50 text-red-700 border border-red-200 px-4 py-2 text-sm">{error}</div> : null}
            <div className="grid sm:grid-cols-2 gap-3">
              <input value={form.title} onChange={(e) => handleFormChange("title", e.target.value)} placeholder="Sarlavha *" className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-2.5 text-sm" />
	              <select value={form.subject} onChange={(e) => handleFormChange("subject", e.target.value)} className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-2.5 text-sm">
	                <option value="English">English</option>
	                <option value="Russian">Russian</option>
	                <option value="Arabic">Arabic</option>
	                <option value="Matematika">Matematika</option>
	                <option value="Tarix">Tarix</option>
	                <option value="Ona tili">Ona tili</option>
	                <option value="Arab tili">Arab tili</option>
	              </select>
	              <select value={form.level} onChange={(e) => handleFormChange("level", e.target.value)} className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-2.5 text-sm">
	                <option value="">Darajani tanlang</option>
	                <option value="Beginner">Beginner</option>
	                <option value="A1">A1</option>
	                <option value="A2">A2</option>
	                <option value="B1">B1</option>
	                <option value="B2">B2</option>
	                <option value="C1">C1</option>
	                <option value="C2">C2</option>
	              </select>
                {rolePrefix === "admin" ? (
                  <>
                    <select value={form.teacher_id || ""} onChange={(e) => handleFormChange("teacher_id", e.target.value ? Number(e.target.value) : null)} className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-2.5 text-sm">
                      <option value="">O'qituvchi tanlang *</option>
                      {teachers.map(t => (
                        <option key={`t-${t.id}`} value={t.id}>{t.full_name || `O'qituvchi #${t.id}`} {t.subjects?.length ? `(${t.subjects.join(", ")})` : ""}</option>
                      ))}
                    </select>
                    <input value={form.support_teacher_ids} onChange={(e) => handleFormChange("support_teacher_ids", e.target.value)} placeholder="Qo'shimcha o'qituvchilar (ID larni vergul bilan ajrating)" className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-2.5 text-sm" />
                  </>
                ) : null}
	              <input value={form.author} onChange={(e) => handleFormChange("author", e.target.value)} placeholder="Muallif" className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-2.5 text-sm" />
              <label className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-3 text-sm sm:col-span-2 flex items-center justify-between gap-3 cursor-pointer">
                <span className="font-medium text-slate-700 dark:text-slate-300 truncate">
                  {uploadingVideoFile ? `Video yuklanmoqda... ${videoUploadProgress}%` : selectedVideoFileName || "Video fayl yuklash (MP4 va boshqalar)"}
                </span>
                <input
                  type="file"
                  accept="video/*,.mov,.mp4"
                  className="hidden"
                  disabled={uploadingVideoFile || saving}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) {
                      setSelectedVideoFileName(file.name || "");
                      uploadVideoFile(file).catch(() => null);
                    }
                    event.currentTarget.value = "";
                  }}
                />
                <span className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold whitespace-nowrap">
                  Fayl tanlash
                </span>
              </label>
              {form.video_asset_id ? (
                <div className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 sm:col-span-2">
                  Ulangan media asset: #{form.video_asset_id}
                </div>
              ) : null}
              <input value={form.video_url} onChange={(e) => handleFormChange("video_url", e.target.value)} placeholder="Video URL *" className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-2.5 text-sm sm:col-span-2" />
              <label className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-3 text-sm sm:col-span-2 flex items-center justify-between gap-3 cursor-pointer">
                <span className="font-medium text-slate-700 dark:text-slate-300 truncate">
                  {uploadingThumbFile ? "Thumbnail yuklanmoqda..." : selectedThumbFileName || "Thumbnail yuklash (JPG/PNG/WEBP) *"}
                </span>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  className="hidden"
                  disabled={uploadingThumbFile || saving}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) {
                      setSelectedThumbFileName(file.name || "");
                      uploadThumbnailFile(file).catch(() => null);
                    }
                    event.currentTarget.value = "";
                  }}
                />
                <span className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold whitespace-nowrap">
                  Fayl tanlash
                </span>
              </label>
              <input value={form.thumbnail_url} onChange={(e) => handleFormChange("thumbnail_url", e.target.value)} placeholder="Thumbnail URL *" className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-2.5 text-sm sm:col-span-2" />
              {form.thumbnail_url.trim() ? (
                <div className="sm:col-span-2 rounded-xl border border-slate-200 dark:border-slate-700 p-2 bg-slate-50 dark:bg-slate-900">
                  <img
                    src={mediaUrl(form.thumbnail_url)}
                    alt="thumbnail preview"
                    className="w-full aspect-square max-h-64 object-contain rounded-lg bg-white dark:bg-slate-950"
                    onError={() => setError("Rasm yuklanmadi. Qayta urinib ko'ring.")}
                  />
                </div>
              ) : null}
	              <textarea value={form.description} onChange={(e) => handleFormChange("description", e.target.value)} placeholder="Qisqacha tavsif" rows={4} className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-2.5 text-sm sm:col-span-2 resize-none" />
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={closeModal} disabled={saving} className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200 text-sm">Bekor qilish</button>
              <button onClick={() => saveVideo()} disabled={saving} className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium">
                {saving ? "Saqlanmoqda..." : editingId ? "Yangilash" : "Saqlash"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {testModalOpen ? (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4 overflow-y-auto" onClick={() => !testBusy && setTestModalOpen(false)}>
          <div className="bg-white dark:bg-slate-900 w-full max-w-4xl rounded-2xl shadow-xl flex flex-col my-8 border border-slate-200 dark:border-slate-800" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-slate-50 dark:bg-slate-800/50 rounded-t-2xl">
              <h3 className="text-xl font-bold text-slate-800 dark:text-white">Test Tahrirlash: {testVideoTitle}</h3>
              <button onClick={() => !testBusy && setTestModalOpen(false)} disabled={testBusy} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">X</button>
            </div>
            
            <div className="p-6 overflow-y-auto max-h-[70vh]">
              {error ? <div className="mb-4 rounded-xl bg-red-50 text-red-700 border border-red-200 px-4 py-3 text-sm font-medium">{error}</div> : null}
              {testBusy && testQuestions.length === 0 ? (
                <div className="flex justify-center py-12"><div className="w-8 h-8 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin"></div></div>
              ) : (
                <SharedTestEditor questions={testQuestions} onChange={setTestQuestions} title="Video Test Savollari" />
              )}
            </div>

            <div className="p-6 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 rounded-b-2xl flex justify-end gap-3">
              <button onClick={() => setTestModalOpen(false)} disabled={testBusy} className="px-5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200 text-sm font-semibold hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">Bekor qilish</button>
              <button onClick={saveTestQuestions} disabled={testBusy} className="px-5 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-white text-sm font-bold shadow-sm shadow-cyan-500/30 transition-all">
                {testBusy ? "Saqlanmoqda..." : "Testni saqlash"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
      </ModalPortal>
    </div>
  );
}
