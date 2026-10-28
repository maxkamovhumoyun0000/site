"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
const LEVELS = ["", "A1", "A2", "B1", "B2", "C1", "C2"];

type Subject = "english" | "russian";

type SpeakingVideo = {
  id: number;
  title: string;
  description: string;
  level: string;
  subject: Subject;
  thumbnail_url: string | null;
  duration: number;
  view_count: number;
  video_asset_id: number | null;
  is_published: boolean;
};

type CatalogVideo = {
  id: number;
  title: string;
  subject: Subject | "";
  level: string;
  thumbnail_url: string | null;
  duration: number;
  view_count: number;
};

type FormState = {
  title: string;
  description: string;
  subject: Subject;
  level: string;
  thumbnail_url: string;
  video_asset_id: number | null;
  duration: number;
  is_published: boolean;
};

const EMPTY_FORM: FormState = {
  title: "",
  description: "",
  subject: "english",
  level: "",
  thumbnail_url: "",
  video_asset_id: null,
  duration: 0,
  is_published: true,
};

interface AdminSpeakingVideosProps {
  apiFetch: (path: string, options?: { method?: string; body?: any; timeoutMs?: number; signal?: AbortSignal }) => Promise<any>;
}

function mediaUrl(raw: string | null | undefined) {
  const value = String(raw || "").trim();
  if (!value) return "";
  return value.startsWith("/") ? `${API_BASE}${value}` : value;
}

function formatDuration(seconds: number) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function errorText(error: unknown, fallback: string) {
  const message = error instanceof Error ? error.message : String(error || "");
  return message.trim() || fallback;
}

/** Reads the duration of a local video file in the browser. */
function readVideoDuration(file: File): Promise<number> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    const done = (value: number) => {
      URL.revokeObjectURL(url);
      resolve(Number.isFinite(value) ? Math.round(value) : 0);
    };
    video.onloadedmetadata = () => done(video.duration);
    video.onerror = () => done(0);
    video.src = url;
  });
}

function uploadWithProgress(file: File, assetType: "video" | "file", onProgress: (percent: number) => void): Promise<any> {
  return new Promise((resolve, reject) => {
    const body = new FormData();
    body.append("file", file);
    body.append("asset_type", assetType);
    const token = localStorage.getItem("diamond_token") || "";
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/staff/speaking/upload/media`, true);
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      try {
        const payload = JSON.parse(xhr.responseText || "{}");
        if (xhr.status >= 200 && xhr.status < 300) resolve(payload);
        else reject(new Error(payload.detail || `Yuklash xatosi: ${xhr.status}`));
      } catch {
        reject(new Error(`Yuklash xatosi: ${xhr.status}`));
      }
    };
    xhr.onerror = () => reject(new Error("Tarmoq xatosi. Fayl yuklanmadi."));
    xhr.send(body);
  });
}

function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-hidden="true">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton-card flex items-center gap-4 p-3">
          <div className="skeleton-media h-16 w-28 shrink-0 rounded-lg" />
          <div className="flex-1 space-y-2">
            <div className="skeleton-line title" />
            <div className="skeleton-line short" />
          </div>
        </div>
      ))}
    </div>
  );
}

function Thumb({ url, title }: { url: string | null; title: string }) {
  const src = mediaUrl(url);
  return src ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={title} className="h-16 w-28 shrink-0 rounded-lg object-cover" />
  ) : (
    <div className="flex h-16 w-28 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-xs text-blue-600">Video</div>
  );
}

export function AdminSpeakingVideos({ apiFetch }: AdminSpeakingVideosProps) {
  const [tab, setTab] = useState<"own" | "picks">("own");
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<SpeakingVideo[]>([]);
  const [catalog, setCatalog] = useState<CatalogVideo[]>([]);
  const [pickIds, setPickIds] = useState<number[]>([]);
  const [savedPickIds, setSavedPickIds] = useState<number[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [editingId, setEditingId] = useState<number | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [videoProgress, setVideoProgress] = useState<number | null>(null);
  const [thumbUploading, setThumbUploading] = useState(false);
  const [videoFileName, setVideoFileName] = useState("");

  const [search, setSearch] = useState("");
  const [subjectFilter, setSubjectFilter] = useState<"" | Subject>("");
  const [savingPicks, setSavingPicks] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/staff/speaking/videos", { method: "GET" });
      setItems(Array.isArray(res?.items) ? res.items : []);
      setCatalog(Array.isArray(res?.catalog) ? res.catalog : []);
      const picks = Array.isArray(res?.pick_ids) ? res.pick_ids.map(Number) : [];
      setPickIds(picks);
      setSavedPickIds(picks);
    } catch (e) {
      setError(errorText(e, "Videolarni yuklab bo'lmadi."));
    } finally {
      setLoading(false);
    }
  }, [apiFetch]);

  useEffect(() => {
    load();
  }, [load]);

  function openCreate() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setVideoFileName("");
    setVideoProgress(null);
    setFormOpen(true);
  }

  function openEdit(video: SpeakingVideo) {
    setEditingId(video.id);
    setForm({
      title: video.title,
      description: video.description || "",
      subject: video.subject === "russian" ? "russian" : "english",
      level: video.level || "",
      thumbnail_url: video.thumbnail_url || "",
      video_asset_id: video.video_asset_id,
      duration: video.duration || 0,
      is_published: Boolean(video.is_published),
    });
    setVideoFileName("");
    setVideoProgress(null);
    setFormOpen(true);
  }

  async function handleVideoFile(file: File | undefined) {
    if (!file) return;
    if (!/^video\//i.test(file.type) && !/\.(mp4|mov|mkv|webm|m4v)$/i.test(file.name)) {
      setError("Fayl turi noto'g'ri. Video fayl tanlang.");
      return;
    }
    if (file.size > 2000 * 1024 * 1024) {
      setError("Video hajmi 2000 MB dan oshmasin.");
      return;
    }
    setError("");
    setVideoProgress(0);
    try {
      const [duration, res] = await Promise.all([
        readVideoDuration(file),
        uploadWithProgress(file, "video", setVideoProgress),
      ]);
      const assetId = Number(res?.asset?.id || 0) || null;
      if (!assetId) throw new Error("Video yuklanmadi. Qayta urinib ko'ring.");
      setForm((prev) => ({ ...prev, video_asset_id: assetId, duration: duration || prev.duration }));
      setVideoFileName(file.name);
      setNotice("Video fayli yuklandi.");
    } catch (e) {
      setError(errorText(e, "Video yuklanmadi."));
    } finally {
      setVideoProgress(null);
    }
  }

  async function handleThumbFile(file: File | undefined) {
    if (!file) return;
    if (!/\.(jpg|jpeg|png|webp)$/i.test(file.name)) {
      setError("Faqat JPG, PNG yoki WEBP rasm yuklang.");
      return;
    }
    setError("");
    setThumbUploading(true);
    try {
      const res = await uploadWithProgress(file, "file", () => undefined);
      const url = String(res?.asset?.public_url || "").trim();
      if (!url) throw new Error("Rasm yuklanmadi.");
      setForm((prev) => ({ ...prev, thumbnail_url: url }));
    } catch (e) {
      setError(errorText(e, "Rasm yuklanmadi."));
    } finally {
      setThumbUploading(false);
    }
  }

  async function saveForm() {
    if (form.title.trim().length < 2) {
      setError("Video nomini kiriting.");
      return;
    }
    if (!form.video_asset_id) {
      setError("Avval video faylni yuklang.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const body = {
        title: form.title.trim(),
        description: form.description.trim(),
        subject: form.subject,
        level: form.level,
        thumbnail_url: form.thumbnail_url,
        video_asset_id: form.video_asset_id,
        duration: Math.max(0, Math.round(form.duration || 0)),
        is_published: form.is_published,
      };
      if (editingId) {
        await apiFetch(`/staff/speaking/videos/${editingId}`, { method: "PUT", body });
        setNotice("Video saqlandi.");
      } else {
        await apiFetch("/staff/speaking/videos", { method: "POST", body });
        setNotice("Video qo'shildi.");
      }
      setFormOpen(false);
      await load();
    } catch (e) {
      setError(errorText(e, "Videoni saqlab bo'lmadi."));
    } finally {
      setSaving(false);
    }
  }

  async function togglePublished(video: SpeakingVideo) {
    try {
      await apiFetch(`/staff/speaking/videos/${video.id}`, { method: "PUT", body: { is_published: !video.is_published } });
      setItems((prev) => prev.map((item) => (item.id === video.id ? { ...item, is_published: !video.is_published } : item)));
    } catch (e) {
      setError(errorText(e, "Holatni o'zgartirib bo'lmadi."));
    }
  }

  async function removeVideo(video: SpeakingVideo) {
    if (!confirm(`"${video.title}" videosini o'chirmoqchimisiz?`)) return;
    try {
      await apiFetch(`/staff/speaking/videos/${video.id}`, { method: "DELETE" });
      setItems((prev) => prev.filter((item) => item.id !== video.id));
      setNotice("Video o'chirildi.");
    } catch (e) {
      setError(errorText(e, "Videoni o'chirib bo'lmadi."));
    }
  }

  async function move(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= items.length) return;
    const next = [...items];
    [next[index], next[target]] = [next[target], next[index]];
    setItems(next);
    try {
      await Promise.all(
        next.map((item, position) =>
          apiFetch(`/staff/speaking/videos/${item.id}`, { method: "PUT", body: { sort_order: position + 1 } }),
        ),
      );
    } catch (e) {
      setError(errorText(e, "Tartibni saqlab bo'lmadi."));
      await load();
    }
  }

  const catalogById = useMemo(() => new Map(catalog.map((video) => [video.id, video])), [catalog]);
  const filteredCatalog = useMemo(() => {
    const query = search.trim().toLowerCase();
    return catalog.filter(
      (video) =>
        (!subjectFilter || video.subject === subjectFilter || !video.subject) &&
        (!query || video.title.toLowerCase().includes(query)),
    );
  }, [catalog, search, subjectFilter]);
  const picksChanged = pickIds.join(",") !== savedPickIds.join(",");

  function togglePick(id: number) {
    setPickIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  }

  function movePick(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= pickIds.length) return;
    const next = [...pickIds];
    [next[index], next[target]] = [next[target], next[index]];
    setPickIds(next);
  }

  async function savePicks() {
    setSavingPicks(true);
    setError("");
    try {
      const res = await apiFetch("/staff/speaking/videos/picks", { method: "PUT", body: { video_ids: pickIds } });
      const saved = Array.isArray(res?.pick_ids) ? res.pick_ids.map(Number) : pickIds;
      setPickIds(saved);
      setSavedPickIds(saved);
      setNotice("Tanlangan videolar saqlandi.");
    } catch (e) {
      setError(errorText(e, "Tanlovni saqlab bo'lmadi."));
    } finally {
      setSavingPicks(false);
    }
  }

  const subjectLabel = (subject: string) => (subject === "russian" ? "Rus tili" : subject === "english" ? "Ingliz tili" : "Umumiy");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">Video darslar</h2>
          <p className="text-sm text-slate-500">Speaking ilovasidagi &quot;Video darslar&quot; sahifasi uchun videolar.</p>
        </div>
        {tab === "own" ? (
          <button type="button" onClick={openCreate} className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700">
            + Yangi video
          </button>
        ) : (
          <button
            type="button"
            onClick={savePicks}
            disabled={!picksChanged || savingPicks}
            className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {savingPicks ? "Saqlanmoqda..." : "Tanlovni saqlash"}
          </button>
        )}
      </div>

      <div className="flex gap-2 border-b border-slate-200 dark:border-slate-700">
        {([
          ["own", `Speaking videolari (${items.length})`],
          ["picks", `Student app videolaridan tanlash (${pickIds.length})`],
        ] as const).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-semibold ${
              tab === key ? "border-blue-600 text-blue-600" : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {error ? (
        <div className="flex items-start justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <span>{error}</span>
          <button type="button" onClick={() => setError("")} className="font-semibold">
            ×
          </button>
        </div>
      ) : null}
      {notice ? (
        <div className="flex items-start justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          <span>{notice}</span>
          <button type="button" onClick={() => setNotice("")} className="font-semibold">
            ×
          </button>
        </div>
      ) : null}

      {loading ? (
        <ListSkeleton />
      ) : tab === "own" ? (
        items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">
            Hali Speaking uchun video qo&apos;shilmagan. &quot;+ Yangi video&quot; tugmasini bosing.
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((video, index) => (
              <div key={video.id} className="flex flex-wrap items-center gap-4 rounded-2xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                <Thumb url={video.thumbnail_url} title={video.title} />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-semibold text-slate-900 dark:text-white">{video.title}</div>
                  <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
                    <span className="rounded-full bg-blue-50 px-2 py-0.5 text-blue-700">{subjectLabel(video.subject)}</span>
                    {video.level ? <span className="rounded-full bg-slate-100 px-2 py-0.5">{video.level}</span> : null}
                    <span>{formatDuration(video.duration)}</span>
                    <span>{video.view_count} marta ko&apos;rilgan</span>
                  </div>
                </div>
                <label className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                  <input type="checkbox" checked={video.is_published} onChange={() => togglePublished(video)} />
                  {video.is_published ? "Chop etilgan" : "Qoralama"}
                </label>
                <div className="flex gap-1">
                  <button type="button" onClick={() => move(index, -1)} disabled={index === 0} className="rounded-lg border px-2 py-1 text-xs disabled:opacity-40">
                    ↑
                  </button>
                  <button
                    type="button"
                    onClick={() => move(index, 1)}
                    disabled={index === items.length - 1}
                    className="rounded-lg border px-2 py-1 text-xs disabled:opacity-40"
                  >
                    ↓
                  </button>
                  <button type="button" onClick={() => openEdit(video)} className="rounded-lg border px-3 py-1 text-xs font-semibold">
                    Tahrirlash
                  </button>
                  <button type="button" onClick={() => removeVideo(video)} className="rounded-lg border border-red-200 px-3 py-1 text-xs font-semibold text-red-600">
                    O&apos;chirish
                  </button>
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        <div className="space-y-5">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
            <div className="mb-3 text-sm font-semibold text-slate-800 dark:text-slate-100">Speaking ilovasida ko&apos;rinadigan tartib</div>
            {pickIds.length === 0 ? (
              <div className="text-sm text-slate-500">Hali video tanlanmagan. Pastdagi ro&apos;yxatdan belgilang.</div>
            ) : (
              <div className="space-y-2">
                {pickIds.map((id, index) => {
                  const video = catalogById.get(id);
                  return (
                    <div key={id} className="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-2 dark:bg-slate-800">
                      <span className="w-6 text-xs font-bold text-slate-400">{index + 1}</span>
                      <span className="flex-1 truncate text-sm">{video?.title || `Video #${id}`}</span>
                      <button type="button" onClick={() => movePick(index, -1)} disabled={index === 0} className="rounded-lg border px-2 py-1 text-xs disabled:opacity-40">
                        ↑
                      </button>
                      <button
                        type="button"
                        onClick={() => movePick(index, 1)}
                        disabled={index === pickIds.length - 1}
                        className="rounded-lg border px-2 py-1 text-xs disabled:opacity-40"
                      >
                        ↓
                      </button>
                      <button type="button" onClick={() => togglePick(id)} className="rounded-lg border border-red-200 px-2 py-1 text-xs text-red-600">
                        Olib tashlash
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-3">
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Video nomi bo'yicha qidirish..."
              className="min-w-[220px] flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
            />
            <select
              value={subjectFilter}
              onChange={(event) => setSubjectFilter(event.target.value as "" | Subject)}
              className="rounded-xl border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
            >
              <option value="">Barcha fanlar</option>
              <option value="english">Ingliz tili</option>
              <option value="russian">Rus tili</option>
            </select>
          </div>

          {filteredCatalog.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">Video topilmadi.</div>
          ) : (
            <div className="space-y-2">
              {filteredCatalog.map((video) => (
                <label
                  key={video.id}
                  className={`flex cursor-pointer items-center gap-4 rounded-2xl border p-3 ${
                    pickIds.includes(video.id) ? "border-blue-500 bg-blue-50/60 dark:bg-blue-950/30" : "border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900"
                  }`}
                >
                  <input type="checkbox" checked={pickIds.includes(video.id)} onChange={() => togglePick(video.id)} />
                  <Thumb url={video.thumbnail_url} title={video.title} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold">{video.title}</div>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
                      <span>{subjectLabel(video.subject)}</span>
                      {video.level ? <span>{video.level}</span> : null}
                      <span>{formatDuration(video.duration)}</span>
                      <span>{video.view_count} ko&apos;rish</span>
                    </div>
                  </div>
                </label>
              ))}
            </div>
          )}
        </div>
      )}

      {formOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true">
          <div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-2xl bg-white p-6 shadow-xl dark:bg-slate-900">
            <h3 className="mb-4 text-lg font-bold">{editingId ? "Videoni tahrirlash" : "Yangi Speaking video"}</h3>
            <div className="space-y-4">
              <label className="block text-sm font-semibold">
                Nomi *
                <input
                  value={form.title}
                  onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
                  className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 font-normal dark:border-slate-700 dark:bg-slate-800"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-sm font-semibold">
                  Fan
                  <select
                    value={form.subject}
                    onChange={(event) => setForm((prev) => ({ ...prev, subject: event.target.value as Subject }))}
                    className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 font-normal dark:border-slate-700 dark:bg-slate-800"
                  >
                    <option value="english">Ingliz tili</option>
                    <option value="russian">Rus tili</option>
                  </select>
                </label>
                <label className="block text-sm font-semibold">
                  Daraja
                  <select
                    value={form.level}
                    onChange={(event) => setForm((prev) => ({ ...prev, level: event.target.value }))}
                    className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 font-normal dark:border-slate-700 dark:bg-slate-800"
                  >
                    {LEVELS.map((level) => (
                      <option key={level || "none"} value={level}>
                        {level || "Ko'rsatilmagan"}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="block text-sm font-semibold">
                Tavsif
                <textarea
                  value={form.description}
                  onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
                  rows={3}
                  className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 font-normal dark:border-slate-700 dark:bg-slate-800"
                />
              </label>
              <div className="text-sm">
                <div className="font-semibold">Video fayl *</div>
                <input
                  type="file"
                  accept="video/*,.mp4,.mov,.mkv,.webm,.m4v"
                  disabled={videoProgress !== null}
                  onChange={(event) => handleVideoFile(event.target.files?.[0])}
                  className="mt-1 block w-full text-sm"
                />
                {videoProgress !== null ? (
                  <div className="mt-2 flex items-center gap-3">
                    <progress value={videoProgress} max={100} className="h-2 flex-1" />
                    <span className="text-xs font-semibold">{videoProgress}%</span>
                  </div>
                ) : form.video_asset_id ? (
                  <div className="mt-1 text-xs text-emerald-600">
                    Video yuklangan{videoFileName ? `: ${videoFileName}` : ""} · {formatDuration(form.duration)}
                  </div>
                ) : null}
              </div>
              <div className="text-sm">
                <div className="font-semibold">Muqova rasmi</div>
                <div className="mt-1 flex items-center gap-3">
                  <Thumb url={form.thumbnail_url} title="Muqova" />
                  <input
                    type="file"
                    accept=".jpg,.jpeg,.png,.webp"
                    disabled={thumbUploading}
                    onChange={(event) => handleThumbFile(event.target.files?.[0])}
                    className="block w-full text-sm"
                  />
                </div>
                {thumbUploading ? <div className="mt-1 text-xs text-slate-500">Rasm yuklanmoqda...</div> : null}
              </div>
              <label className="flex items-center gap-2 text-sm font-semibold">
                <input
                  type="checkbox"
                  checked={form.is_published}
                  onChange={(event) => setForm((prev) => ({ ...prev, is_published: event.target.checked }))}
                />
                Speaking ilovasida ko&apos;rsatish
              </label>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button type="button" onClick={() => setFormOpen(false)} className="rounded-xl border px-4 py-2 text-sm font-semibold">
                Bekor qilish
              </button>
              <button
                type="button"
                onClick={saveForm}
                disabled={saving || videoProgress !== null || thumbUploading}
                className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {saving ? "Saqlanmoqda..." : "Saqlash"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
