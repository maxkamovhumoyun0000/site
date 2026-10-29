"use client";
import React, { useCallback, useEffect, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

type Subject = "english" | "russian";
type Status = "draft" | "published";

type WritingTask = {
  id: string;
  builtin?: boolean;
  subject: Subject;
  task_type: string;
  title: string;
  prompt: string;
  image_url: string | null;
  min_words: number;
  time_minutes: number;
  status?: Status;
  sample_answer?: string;
  submissions?: number;
  average_score?: number | null;
  updated_at?: string | null;
};

type FormState = {
  subject: Subject;
  task_type: string;
  title: string;
  prompt: string;
  image_url: string;
  min_words: number;
  time_minutes: number;
  sample_answer: string;
  status: Status;
};

interface AdminSpeakingWritingProps {
  apiFetch: (path: string, options?: { method?: string; body?: any; timeoutMs?: number; signal?: AbortSignal }) => Promise<any>;
}

const TYPE_LABELS: Record<string, string> = {
  task1_academic: "IELTS Task 1 Academic (grafik / jadval)",
  task1_general: "IELTS Task 1 General (xat)",
  task2: "IELTS Task 2 (esse)",
  ru_essay: "Rus tili — сочинение / эссе",
  ru_letter: "Rus tili — письмо",
};

const TYPES: Record<Subject, string[]> = {
  english: ["task1_academic", "task1_general", "task2"],
  russian: ["ru_essay", "ru_letter"],
};

const DEFAULTS: Record<string, { min_words: number; time_minutes: number }> = {
  task1_academic: { min_words: 150, time_minutes: 20 },
  task1_general: { min_words: 150, time_minutes: 20 },
  task2: { min_words: 250, time_minutes: 40 },
  ru_essay: { min_words: 150, time_minutes: 40 },
  ru_letter: { min_words: 100, time_minutes: 25 },
};

function emptyForm(subject: Subject): FormState {
  const taskType = TYPES[subject][subject === "english" ? 2 : 0];
  return {
    subject,
    task_type: taskType,
    title: "",
    prompt: "",
    image_url: "",
    min_words: DEFAULTS[taskType].min_words,
    time_minutes: DEFAULTS[taskType].time_minutes,
    sample_answer: "",
    status: "draft",
  };
}

function errorText(error: unknown, fallback: string) {
  const message = error instanceof Error ? error.message : String(error || "");
  return message.trim() || fallback;
}

function mediaUrl(raw: string | null | undefined) {
  const value = String(raw || "").trim();
  if (!value) return "";
  return value.startsWith("/") ? `${API_BASE}${value}` : value;
}

function uploadImage(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const body = new FormData();
    body.append("file", file);
    body.append("asset_type", "file");
    const token = localStorage.getItem("diamond_token") || "";
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/staff/speaking/upload/media`, true);
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.onload = () => {
      try {
        const payload = JSON.parse(xhr.responseText || "{}");
        const url = String(payload?.asset?.public_url || "").trim();
        if (xhr.status >= 200 && xhr.status < 300 && url) resolve(url);
        else reject(new Error(payload.detail || `Yuklash xatosi: ${xhr.status}`));
      } catch {
        reject(new Error(`Yuklash xatosi: ${xhr.status}`));
      }
    };
    xhr.onerror = () => reject(new Error("Tarmoq xatosi. Rasm yuklanmadi."));
    xhr.send(body);
  });
}

const inputClass =
  "mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm font-normal dark:border-slate-700 dark:bg-slate-800";

export function AdminSpeakingWriting({ apiFetch }: AdminSpeakingWritingProps) {
  const [subject, setSubject] = useState<Subject>("english");
  const [typeFilter, setTypeFilter] = useState("");
  const [items, setItems] = useState<WritingTask[]>([]);
  const [builtin, setBuiltin] = useState<WritingTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm("english"));
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generateType, setGenerateType] = useState("task2");
  const [generateTopic, setGenerateTopic] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch(`/staff/speaking/writing/tasks?subject=${subject}`);
      setItems(Array.isArray(data?.items) ? data.items : []);
      setBuiltin(Array.isArray(data?.builtin) ? data.builtin : []);
    } catch (e) {
      setError(errorText(e, "Topshiriqlarni yuklab bo'lmadi."));
    } finally {
      setLoading(false);
    }
  }, [apiFetch, subject]);

  useEffect(() => {
    void load();
    setGenerateType(TYPES[subject][subject === "english" ? 2 : 0]);
    setTypeFilter("");
  }, [load, subject]);

  const visible = useMemo(
    () => items.filter((item) => !typeFilter || item.task_type === typeFilter),
    [items, typeFilter],
  );

  function openNew() {
    setEditingId(null);
    setForm(emptyForm(subject));
    setFormOpen(true);
    setNotice("");
  }

  function openEdit(task: WritingTask) {
    setEditingId(task.id);
    setForm({
      subject: task.subject,
      task_type: task.task_type,
      title: task.title,
      prompt: task.prompt,
      image_url: task.image_url || "",
      min_words: task.min_words,
      time_minutes: task.time_minutes,
      sample_answer: task.sample_answer || "",
      status: task.status || "draft",
    });
    setFormOpen(true);
    setNotice("");
  }

  async function save() {
    if (form.prompt.trim().length < 10) {
      setError("Topshiriq matnini yozing.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const body = {
        subject: form.subject,
        task_type: form.task_type,
        title: form.title.trim(),
        prompt: form.prompt.trim(),
        image_url: form.image_url,
        min_words: form.min_words,
        time_minutes: form.time_minutes,
        sample_answer: form.sample_answer.trim(),
        status: form.status,
      };
      if (editingId) {
        await apiFetch(`/staff/speaking/writing/tasks/${editingId}`, { method: "PUT", body });
        setNotice("Topshiriq saqlandi.");
      } else {
        await apiFetch("/staff/speaking/writing/tasks", { method: "POST", body });
        setNotice("Topshiriq qo'shildi.");
      }
      setFormOpen(false);
      await load();
    } catch (e) {
      setError(errorText(e, "Saqlab bo'lmadi."));
    } finally {
      setSaving(false);
    }
  }

  async function togglePublished(task: WritingTask) {
    const next: Status = task.status === "published" ? "draft" : "published";
    try {
      await apiFetch(`/staff/speaking/writing/tasks/${task.id}`, { method: "PUT", body: { status: next } });
      setItems((prev) => prev.map((item) => (item.id === task.id ? { ...item, status: next } : item)));
    } catch (e) {
      setError(errorText(e, "Holatni o'zgartirib bo'lmadi."));
    }
  }

  async function remove(task: WritingTask) {
    if (!window.confirm(`"${task.title || task.prompt.slice(0, 40)}" o'chirilsinmi?`)) return;
    try {
      await apiFetch(`/staff/speaking/writing/tasks/${task.id}`, { method: "DELETE" });
      setItems((prev) => prev.filter((item) => item.id !== task.id));
    } catch (e) {
      setError(errorText(e, "O'chirib bo'lmadi."));
    }
  }

  async function generate() {
    setGenerating(true);
    setError("");
    setNotice("");
    try {
      const data = await apiFetch("/staff/speaking/writing/tasks/generate", {
        method: "POST",
        body: { subject, task_type: generateType, count: 3, topic: generateTopic.trim() },
        timeoutMs: 120000,
      });
      const created = Array.isArray(data?.items) ? data.items.length : 0;
      setNotice(`${created} ta yangi topshiriq qoralama sifatida qo'shildi. Tekshirib, nashr qiling.`);
      await load();
    } catch (e) {
      setError(errorText(e, "AI topshiriq yarata olmadi."));
    } finally {
      setGenerating(false);
    }
  }

  async function pickImage(file: File) {
    if (!/\.(jpg|jpeg|png|webp|gif)$/i.test(file.name)) {
      setError("Faqat JPG, PNG, WEBP yoki GIF rasm yuklang.");
      return;
    }
    setUploading(true);
    setError("");
    try {
      const url = await uploadImage(file);
      setForm((prev) => ({ ...prev, image_url: url }));
    } catch (e) {
      setError(errorText(e, "Rasm yuklanmadi."));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">Writing topshiriqlari</h2>
          <p className="text-sm text-slate-500">
            IELTS Writing (Task 1, Task 2) va rus tili yozma ishlari. O&apos;quvchilar matnni yozadi, AI ball va xatolarini ko&apos;rsatadi.
          </p>
        </div>
        <div className="flex gap-2">
          {(["english", "russian"] as Subject[]).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setSubject(value)}
              className={`rounded-xl px-4 py-2 text-sm font-semibold ${
                subject === value ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200"
              }`}
            >
              {value === "english" ? "Ingliz tili (IELTS)" : "Rus tili"}
            </button>
          ))}
        </div>
      </div>

      {error ? <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-200">{error}</div> : null}
      {notice ? <div className="rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-200">{notice}</div> : null}

      <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900 md:grid-cols-[1fr_1fr_auto]">
        <label className="text-sm font-semibold text-slate-700 dark:text-slate-200">
          AI bilan yaratish: turi
          <select value={generateType} onChange={(e) => setGenerateType(e.target.value)} className={inputClass}>
            {TYPES[subject].map((type) => <option key={type} value={type}>{TYPE_LABELS[type]}</option>)}
          </select>
        </label>
        <label className="text-sm font-semibold text-slate-700 dark:text-slate-200">
          Mavzu (ixtiyoriy)
          <input value={generateTopic} onChange={(e) => setGenerateTopic(e.target.value)} className={inputClass} placeholder="education, environment, technology..." />
        </label>
        <div className="flex items-end gap-2">
          <button type="button" onClick={generate} disabled={generating} className="rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {generating ? "Yaratilmoqda…" : "3 ta yaratish"}
          </button>
          <button type="button" onClick={openNew} className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white">
            + Qo&apos;lda qo&apos;shish
          </button>
        </div>
      </div>

      {formOpen ? (
        <div className="space-y-3 rounded-2xl border border-blue-200 bg-blue-50/40 p-4 dark:border-blue-900 dark:bg-blue-950/20">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Turi
              <select
                value={form.task_type}
                onChange={(e) => {
                  const type = e.target.value;
                  setForm((prev) => ({ ...prev, task_type: type, ...DEFAULTS[type] }));
                }}
                className={inputClass}
              >
                {TYPES[form.subject].map((type) => <option key={type} value={type}>{TYPE_LABELS[type]}</option>)}
              </select>
            </label>
            <label className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Sarlavha
              <input value={form.title} onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))} className={inputClass} />
            </label>
          </div>
          <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
            Topshiriq matni (jadvalni Markdown ko&apos;rinishida yozish mumkin)
            <textarea value={form.prompt} onChange={(e) => setForm((prev) => ({ ...prev, prompt: e.target.value }))} className={`${inputClass} min-h-[160px]`} />
          </label>
          {form.task_type === "task1_academic" ? (
            <div className="space-y-2">
              <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">Grafik / jadval / diagramma rasmi</span>
              <div className="flex flex-wrap items-center gap-3">
                {form.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={mediaUrl(form.image_url)} alt="" className="h-24 rounded-lg border border-slate-200 object-contain" />
                ) : null}
                <label className="cursor-pointer rounded-xl border border-dashed border-slate-300 px-4 py-2 text-sm font-semibold text-slate-600 dark:border-slate-600 dark:text-slate-300">
                  {uploading ? "Yuklanmoqda…" : form.image_url ? "Rasmni almashtirish" : "+ Rasm yuklash"}
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/gif"
                    className="hidden"
                    disabled={uploading}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) void pickImage(file);
                      e.target.value = "";
                    }}
                  />
                </label>
                {form.image_url ? (
                  <button type="button" onClick={() => setForm((prev) => ({ ...prev, image_url: "" }))} className="text-sm font-semibold text-red-600">
                    Olib tashlash
                  </button>
                ) : null}
              </div>
            </div>
          ) : null}
          <div className="grid gap-3 md:grid-cols-3">
            <label className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Minimal so&apos;zlar
              <input type="number" min={20} max={1000} value={form.min_words} onChange={(e) => setForm((prev) => ({ ...prev, min_words: Number(e.target.value) || 0 }))} className={inputClass} />
            </label>
            <label className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Vaqt (daqiqa)
              <input type="number" min={5} max={180} value={form.time_minutes} onChange={(e) => setForm((prev) => ({ ...prev, time_minutes: Number(e.target.value) || 0 }))} className={inputClass} />
            </label>
            <label className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Holati
              <select value={form.status} onChange={(e) => setForm((prev) => ({ ...prev, status: e.target.value as Status }))} className={inputClass}>
                <option value="draft">Qoralama</option>
                <option value="published">Nashr qilingan</option>
              </select>
            </label>
          </div>
          <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
            Namuna javob (ixtiyoriy, o&apos;quvchiga ko&apos;rsatilmaydi)
            <textarea value={form.sample_answer} onChange={(e) => setForm((prev) => ({ ...prev, sample_answer: e.target.value }))} className={`${inputClass} min-h-[100px]`} />
          </label>
          <div className="flex gap-2">
            <button type="button" onClick={save} disabled={saving} className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
              {saving ? "Saqlanmoqda…" : "Saqlash"}
            </button>
            <button type="button" onClick={() => setFormOpen(false)} className="rounded-xl bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-200">
              Bekor qilish
            </button>
          </div>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => setTypeFilter("")} className={`rounded-full px-3 py-1 text-xs font-semibold ${!typeFilter ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900" : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"}`}>
          Hammasi ({items.length})
        </button>
        {TYPES[subject].map((type) => (
          <button key={type} type="button" onClick={() => setTypeFilter(type)} className={`rounded-full px-3 py-1 text-xs font-semibold ${typeFilter === type ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900" : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"}`}>
            {TYPE_LABELS[type]}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-3" aria-hidden="true">
          {[0, 1, 2].map((index) => (
            <div key={index} className="skeleton-card p-4"><div className="skeleton-line title" /><div className="skeleton-line short" /></div>
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {visible.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500 dark:border-slate-700">
              Hali o&apos;z topshiriqlaringiz yo&apos;q. Ilovada quyidagi tayyor topshiriqlar ishlaydi.
            </div>
          ) : null}
          {visible.map((task) => (
            <div key={task.id} className="flex flex-wrap items-start gap-4 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
              {task.image_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={mediaUrl(task.image_url)} alt="" className="h-16 w-24 rounded-lg object-cover" />
              ) : null}
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-slate-900 dark:text-white">{task.title || TYPE_LABELS[task.task_type]}</span>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${task.status === "published" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                    {task.status === "published" ? "Nashr qilingan" : "Qoralama"}
                  </span>
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">{TYPE_LABELS[task.task_type]}</span>
                </div>
                <p className="mt-1 line-clamp-2 whitespace-pre-line text-sm text-slate-600 dark:text-slate-300">{task.prompt}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {task.min_words}+ so&apos;z · {task.time_minutes} daqiqa · {task.submissions || 0} ta javob
                  {task.average_score != null ? ` · o'rtacha ${task.average_score}` : ""}
                </p>
              </div>
              <div className="flex gap-2">
                <button type="button" onClick={() => togglePublished(task)} className="rounded-xl bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                  {task.status === "published" ? "Yashirish" : "Nashr qilish"}
                </button>
                <button type="button" onClick={() => openEdit(task)} className="rounded-xl bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 dark:bg-blue-950 dark:text-blue-200">
                  Tahrirlash
                </button>
                <button type="button" onClick={() => remove(task)} className="rounded-xl bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-600 dark:bg-red-950 dark:text-red-200">
                  O&apos;chirish
                </button>
              </div>
            </div>
          ))}
          {builtin.length > 0 ? (
            <details className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/60">
              <summary className="cursor-pointer text-sm font-semibold text-slate-700 dark:text-slate-200">
                Tayyor topshiriqlar ({builtin.length}) — har doim ilovada mavjud
              </summary>
              <ul className="mt-3 space-y-2">
                {builtin.map((task) => (
                  <li key={task.id} className="text-sm text-slate-600 dark:text-slate-300">
                    <span className="font-semibold">{task.title}</span> · {TYPE_LABELS[task.task_type]}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>
      )}
    </div>
  );
}
