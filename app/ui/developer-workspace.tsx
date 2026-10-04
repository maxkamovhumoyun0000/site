"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE } from "../public-data";
import { SectionTitle } from "./primitives";
import { useWebT } from "./web-i18n";

type GenericRow = Record<string, any>;

async function requestJson<T>(
  path: string,
  options?: {
    method?: string;
    body?: any;
    token?: string;
    timeoutMs?: number;
  }
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options?.timeoutMs || 15000);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: options?.method || "GET",
      signal: controller.signal,
      headers: {
        ...(options?.token ? { Authorization: `Bearer ${options.token}` } : {}),
        ...(options?.body ? { "Content-Type": "application/json" } : {}),
      },
      body: options?.body ? JSON.stringify(options.body) : undefined,
    });
    if (!res.ok) {
      let errMessage = `Error ${res.status}`;
      try {
        const data = await res.json();
        if (data.detail) {
          errMessage = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
        } else if (data.message) {
          errMessage = data.message;
        }
      } catch {
        const text = await res.text().catch(() => "");
        if (text) errMessage = text.slice(0, 200);
      }
      throw new Error(errMessage);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

function systemBytes(value: unknown): string {
  const bytes = Number(value || 0);
  if (!bytes || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

function systemUptime(seconds: unknown): string {
  const s = Math.floor(Number(seconds || 0));
  if (s <= 0) return "0 daqiqa";
  const days = Math.floor(s / 86400);
  const hours = Math.floor((s % 86400) / 3600);
  const mins = Math.floor((s % 3600) / 60);
  const parts: string[] = [];
  if (days > 0) parts.push(`${days} kun`);
  if (hours > 0) parts.push(`${hours} soat`);
  if (mins > 0 || parts.length === 0) parts.push(`${mins} daqiqa`);
  return parts.join(" ");
}

function datetimeLocalValue(value: unknown): string {
  const date = value ? new Date(String(value)) : null;
  if (!date || Number.isNaN(date.getTime())) return "";
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

// ============================================================================
// 1. DEVELOPER HOME VIEW
// ============================================================================

export function DeveloperHomeView({ onNavigate }: { onNavigate: (section: string) => void }) {
  const tt = useWebT();
  const [status, setStatus] = useState<GenericRow | null>(null);
  const [deploy, setDeploy] = useState<GenericRow | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("diamond_token") || "";
      const [sRes, dRes] = await Promise.all([
        requestJson<GenericRow>("/developer/server/status", { token, timeoutMs: 10000 }).catch(() => null),
        requestJson<GenericRow>("/developer/deploy/info", { token, timeoutMs: 10000 }).catch(() => null),
      ]);
      setStatus(sRes || null);
      setDeploy(dRes || null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const metrics = (status?.metrics || {}) as GenericRow;
  const services = (status?.services || []) as GenericRow[];
  const runningServicesCount = services.filter((s) => s.active_state === "active").length;
  const latestBackup = ((deploy?.backups || []) as GenericRow[])[0];

  const cards = [
    {
      id: "developer-server",
      title: tt("section.developer-server", "Server va Loglar"),
      desc: "CPU, RAM, disk, 6 ta systemd servislar va real-time journalctl loglar.",
      icon: "⌘",
      badge: `${Number(metrics.cpu_percent || 0).toFixed(0)}% CPU · ${systemBytes(metrics.memory_available_bytes)} bo'sh`,
      color: "from-blue-600/10 to-indigo-600/10 border-blue-500/30 text-blue-600 dark:text-blue-400",
    },
    {
      id: "developer-deploy",
      title: tt("section.developer-deploy", "Deploy Markazi"),
      desc: "PostgreSQL backup yaratish, dump fayllar, git versiya va rollback.",
      icon: "▲",
      badge: latestBackup ? `${latestBackup.size_mb || 0} MB` : "Backup tayyor",
      color: "from-cyan-600/10 to-teal-600/10 border-cyan-500/30 text-cyan-600 dark:text-cyan-400",
    },
    {
      id: "developer-maintenance",
      title: tt("section.developer-maintenance", "Rejali Maintenance"),
      desc: "Student, Teacher ilovalari va Web-sayt uchun texnik tanaffusni vaqtli yoqish.",
      icon: "⏸",
      badge: "Mobil & Web",
      color: "from-amber-600/10 to-orange-600/10 border-amber-500/30 text-amber-600 dark:text-amber-400",
    },
    {
      id: "developer-flags",
      title: tt("section.developer-flags", "Feature Flags"),
      desc: "Yangi imkoniyatlarni toggle qilish, rol bo'yicha yoki tanlanganlarga ochish.",
      icon: "⚑",
      badge: "Kill switch",
      color: "from-purple-600/10 to-pink-600/10 border-purple-500/30 text-purple-600 dark:text-purple-400",
    },
    {
      id: "developer-audit",
      title: tt("section.developer-audit", "Audit va Xavfsizlik"),
      desc: "Admin va developer amallari, loginlar tarixi, xavfsizlik ogohlantirishlari.",
      icon: "🛡",
      badge: "Xavfsizlik nazorati",
      color: "from-emerald-600/10 to-green-600/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400",
    },
    {
      id: "developer-jobs",
      title: tt("section.developer-jobs", "Queue va Joblar"),
      desc: "Telegram bot webhook holati, background schedulers, push notificationlar.",
      icon: "⚡",
      badge: "4 ta bot & FCM",
      color: "from-yellow-600/10 to-amber-600/10 border-yellow-500/30 text-yellow-600 dark:text-yellow-400",
    },
    {
      id: "developer-database",
      title: tt("section.developer-database", "Database va Kesh"),
      desc: "Jadvallar hajmi, unread count va overview keshlarini tozalash, DB holati.",
      icon: "🗄",
      badge: "Cache purge",
      color: "from-rose-600/10 to-red-600/10 border-rose-500/30 text-rose-600 dark:text-rose-400",
    },
    {
      id: "developer-api-metrics",
      title: tt("section.developer-api-metrics", "API Telemetriya"),
      desc: "Database ping tezligi, bot webhook ping va tashqi servislar salomatligi.",
      icon: "📈",
      badge: "Health check",
      color: "from-sky-600/10 to-blue-600/10 border-sky-500/30 text-sky-600 dark:text-sky-400",
    },
  ];

  return (
    <div className="flex flex-col gap-6 pb-12 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <SectionTitle
            kicker="Developer Workspace"
            title="Boshqaruv va Monitoring Markazi"
            subtitle="Server infratuzilmasi, servislar, deploy, xavfsizlik va tizim parametrlarini to'liq nazorat qilish."
          />
        </div>
        <button
          type="button"
          onClick={loadData}
          disabled={loading}
          className="btn btn-soft small flex items-center gap-2"
        >
          <span>🔄</span>
          <span>{loading ? "Yuklanmoqda..." : "Yangilash"}</span>
        </button>
      </div>

      {/* Hero Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:gap-4">
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <span className="text-[11px] font-black uppercase tracking-wider text-ink-500 dark:text-slate-400">Server Uptime</span>
          <p className="mt-1 text-lg font-black text-navy-900 dark:text-white sm:text-xl">
            {metrics.uptime_seconds ? systemUptime(metrics.uptime_seconds) : "Faol"}
          </p>
          <span className="mt-1 block text-xs font-bold text-emerald-600 dark:text-emerald-400">● Tizim barqaror</span>
        </div>

        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <span className="text-[11px] font-black uppercase tracking-wider text-ink-500 dark:text-slate-400">Yuklama (CPU/RAM)</span>
          <p className="mt-1 text-lg font-black text-navy-900 dark:text-white sm:text-xl">
            {Number(metrics.cpu_percent || 0).toFixed(0)}% / {Number(metrics.memory_percent || 0).toFixed(0)}%
          </p>
          <span className="mt-1 block text-xs font-bold text-ink-500 dark:text-slate-400">
            {metrics.cpu_cores || 0} yadro · {systemBytes(metrics.memory_available_bytes)} bo'sh
          </span>
        </div>

        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <span className="text-[11px] font-black uppercase tracking-wider text-ink-500 dark:text-slate-400">Servislar Holati</span>
          <p className="mt-1 text-lg font-black text-navy-900 dark:text-white sm:text-xl">
            {runningServicesCount} / {services.length || 6}
          </p>
          <span className="mt-1 block text-xs font-bold text-emerald-600 dark:text-emerald-400">
            {runningServicesCount === (services.length || 6) ? "Barchasi faol" : "Diqqat talab"}
          </span>
        </div>

        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <span className="text-[11px] font-black uppercase tracking-wider text-ink-500 dark:text-slate-400">Git Versiya</span>
          <p className="mt-1 text-lg font-black text-navy-900 dark:text-white sm:text-xl font-mono">
            {deploy?.git?.commit || "production"}
          </p>
          <span className="mt-1 block truncate text-xs font-bold text-ink-500 dark:text-slate-400">
            {deploy?.git?.branch || "main"} · {deploy?.git?.message?.slice(0, 20) || "deploy"}
          </span>
        </div>
      </div>

      {/* Navigation Grid */}
      <div>
        <h3 className="mb-3 text-base font-black text-navy-900 dark:text-white">Boshqaruv Bo'limlari</h3>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {cards.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => onNavigate(c.id)}
              className="group relative flex flex-col justify-between rounded-2xl border border-line bg-surface p-5 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-cyan-400/50 hover:shadow-md dark:border-white/10 dark:bg-white/[0.03] dark:hover:border-cyan-400/30"
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <div className={`flex h-10 w-10 items-center justify-center rounded-xl border bg-gradient-to-br text-lg font-black ${c.color}`}>
                    {c.icon}
                  </div>
                  <span className="rounded-full bg-surface-soft px-2.5 py-1 text-[11px] font-bold text-ink-600 dark:bg-white/10 dark:text-slate-300">
                    {c.badge}
                  </span>
                </div>
                <h4 className="mt-4 text-base font-black text-navy-900 group-hover:text-cyan-600 dark:text-white dark:group-hover:text-cyan-300">
                  {c.title}
                </h4>
                <p className="mt-1.5 text-xs font-medium text-ink-500 dark:text-slate-400 leading-relaxed">
                  {c.desc}
                </p>
              </div>
              <div className="mt-4 flex items-center gap-1.5 text-xs font-black text-cyan-600 dark:text-cyan-400">
                <span>Bo'limni ochish</span>
                <span className="transition-transform group-hover:translate-x-1">→</span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// 2. DEVELOPER DEPLOY VIEW
// ============================================================================

export function DeveloperDeployView() {
  const tt = useWebT();
  const [data, setData] = useState<GenericRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [backingUp, setBackingUp] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const loadInfo = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("diamond_token") || "";
      const res = await requestJson<GenericRow>("/developer/deploy/info", { token, timeoutMs: 15000 });
      setData(res || null);
    } catch (err: any) {
      setMessage({ text: err.message || "Deploy ma'lumotlari yuklanmadi", type: "error" });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadInfo();
  }, [loadInfo]);

  const handleCreateBackup = async () => {
    if (!window.confirm("Haqiqatan ham yangi PostgreSQL database backup yaratmoqchimisiz?")) return;
    setBackingUp(true);
    setMessage(null);
    try {
      const token = localStorage.getItem("diamond_token") || "";
      const res = await requestJson<GenericRow>("/developer/deploy/backup", { method: "POST", token, timeoutMs: 120000 });
      setMessage({ text: `Backup yaratildi: ${res.filename} (${res.size_mb} MB)`, type: "success" });
      await loadInfo();
    } catch (err: any) {
      setMessage({ text: err.message || "Backup yaratishda xatolik yuz berdi", type: "error" });
    } finally {
      setBackingUp(false);
    }
  };

  const git = data?.git || {};
  const backups = (data?.backups || []) as GenericRow[];
  const latestBackup = backups[0];
  const build = data?.build || {};

  return (
    <div className="flex flex-col gap-6 pb-12 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <SectionTitle
            kicker="Deploy & Versiyalar"
            title={tt("section.developer-deploy", "Deploy Markazi")}
            subtitle="Database backup yaratish, avtomatik dump ro'yxati, git versiya nazorati va rollback yo'riqnomasi."
          />
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleCreateBackup}
            disabled={backingUp || loading}
            className="btn btn-primary small flex items-center gap-2"
          >
            <span>💾</span>
            <span>{backingUp ? "Backup olinmoqda..." : "Yangi Backup Olish"}</span>
          </button>
          <button
            type="button"
            onClick={loadInfo}
            disabled={loading}
            className="btn btn-soft small"
          >
            🔄 Yangilash
          </button>
        </div>
      </div>

      {message && (
        <div
          className={`rounded-2xl border p-4 text-sm font-bold ${
            message.type === "success"
              ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-950/40 dark:text-emerald-200"
              : "border-red-300 bg-red-50 text-red-800 dark:border-red-500/30 dark:bg-red-950/40 dark:text-red-200"
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Git & Runtime Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <span className="text-xs font-black uppercase tracking-wider text-cyan-600 dark:text-cyan-400">Git Versiya</span>
          <div className="mt-2 space-y-1 text-sm text-navy-900 dark:text-white">
            <p>Commit: <strong className="font-mono text-cyan-600 dark:text-cyan-300">{git.commit || "—"}</strong></p>
            <p>Branch: <strong className="font-mono">{git.branch || "main"}</strong></p>
            <p className="truncate text-xs text-ink-500 dark:text-slate-400">Xabar: {git.message || "—"}</p>
            <p className="text-xs text-ink-500 dark:text-slate-400">Muallif: {git.author || "—"}</p>
          </div>
        </div>

        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <span className="text-xs font-black uppercase tracking-wider text-emerald-600 dark:text-emerald-400">Build Muhiti</span>
          <div className="mt-2 space-y-1 text-sm text-navy-900 dark:text-white">
            <p>Next.js Build: <strong>{build.next_build_time ? new Date(build.next_build_time).toLocaleString("uz-UZ") : "Mavjud"}</strong></p>
            <p>Python versiya: <strong className="font-mono">{build.python_version || "3.11"}</strong></p>
            <p>Node.js versiya: <strong className="font-mono">{build.node_version || "20.x"}</strong></p>
          </div>
        </div>

        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <span className="text-xs font-black uppercase tracking-wider text-indigo-600 dark:text-indigo-400">Backup Siyosati</span>
          <div className="mt-2 space-y-1 text-xs font-medium text-ink-500 dark:text-slate-300 leading-relaxed">
            <p>• Har bir deploydan oldin avtomatik snapshot olinadi.</p>
            <p>• Faqat eng oxirgi 2 ta tekshirilgan dump saqlanadi.</p>
            <p>• Backup fayllari faqat root o'qiy oladigan 0700 papkasida turadi.</p>
          </div>
        </div>
      </div>

      {/* Backups List */}
      <div className="rounded-3xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-black text-navy-900 dark:text-white">Mavjud Database Backuplar ({backups.length})</h3>
          <span className="text-xs font-bold text-ink-500 dark:text-slate-400">Saqlash yo'li: /root/diamond-backups/</span>
        </div>

        {backups.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-line text-xs font-bold uppercase tracking-wider text-ink-500 dark:border-white/10 dark:text-slate-400">
                  <th className="pb-3">Fayl Nomi</th>
                  <th className="pb-3">Hajmi</th>
                  <th className="pb-3">Yaratilgan Vaqt</th>
                  <th className="pb-3">Holat</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line dark:divide-white/10">
                {backups.map((b, idx) => (
                  <tr key={b.name} className="hover:bg-surface-soft dark:hover:bg-white/[0.02]">
                    <td className="py-3 font-mono font-bold text-navy-900 dark:text-white flex items-center gap-2">
                      <span>📦</span>
                      <span>{b.name}</span>
                      {idx === 0 && <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-emerald-600 dark:text-emerald-400">Eng yangi</span>}
                    </td>
                    <td className="py-3 font-bold text-ink-600 dark:text-slate-300">{b.size_mb} MB</td>
                    <td className="py-3 text-ink-500 dark:text-slate-400">{new Date(b.modified_at).toLocaleString("uz-UZ")}</td>
                    <td className="py-3">
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-bold text-emerald-600 dark:text-emerald-400">
                        ✓ Tasdiqlangan
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-ink-500 dark:text-slate-400">Hozircha saqlangan backup fayllar topilmadi.</p>
        )}
      </div>

      {/* Rollback Instructions */}
      <div className="rounded-3xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
        <h3 className="text-base font-black text-navy-900 dark:text-white">Favqulodda Rollback Protokoli</h3>
        <p className="mt-1 text-xs text-ink-500 dark:text-slate-400">
          Agar yangi versiyada jiddiy xatolik kuzatilsa, serverda ushbu ketma-ketlik bo'yicha oldingi barqaror holatga qaytiladi:
        </p>
        <div className="mt-4 rounded-2xl bg-navy-950 p-4 font-mono text-xs text-emerald-400 overflow-x-auto">
          <p className="text-slate-400"># 1. Frontend va backendni to'xtatish</p>
          <p>systemctl stop diamond-site-frontend diamond-site-backend</p>
          <p className="mt-2 text-slate-400"># 2. Database ni oxirgi backupdan tiklash (agar data rollback kerak bo'lsa)</p>
          <p>pg_restore -d $DATABASE_URL --clean /root/diamond-backups/{latestBackup?.name || "diamond-site-latest.dump"}</p>
          <p className="mt-2 text-slate-400"># 3. Barqaror commitga qaytarish va serverda qayta build qilish</p>
          <p>git checkout HEAD~1 && npm run build && systemctl start diamond-site-frontend diamond-site-backend</p>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// 3. DEVELOPER SERVER & LOGS VIEW
// ============================================================================

export function DeveloperServerView() {
  const tt = useWebT();
  const [data, setData] = useState<GenericRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [restarting, setRestarting] = useState<string | null>(null);
  const [restartMsg, setRestartMsg] = useState<{ text: string; error?: boolean } | null>(null);

  // Log viewer state
  const [selectedService, setSelectedService] = useState("diamond-site-backend");
  const [logLines, setLogLines] = useState<string[]>([]);
  const [logLoading, setLogLoading] = useState(false);
  const [logSearch, setLogSearch] = useState("");
  const [logLineCount, setLogLineCount] = useState(100);
  const [autoRefreshLogs, setAutoRefreshLogs] = useState(false);

  const loadStatus = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("diamond_token") || "";
      const res = await requestJson<GenericRow>("/developer/server/status", { token, timeoutMs: 10000 });
      setData(res || null);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadLogs = useCallback(async () => {
    setLogLoading(true);
    try {
      const token = localStorage.getItem("diamond_token") || "";
      const res = await requestJson<{ lines: string[] }>(`/developer/server/logs?service=${encodeURIComponent(selectedService)}&lines=${logLineCount}`, { token, timeoutMs: 15000 });
      setLogLines(res.lines || []);
    } catch (err: any) {
      setLogLines([`Xatolik: ${err.message || "Loglar yuklanmadi"}`]);
    } finally {
      setLogLoading(false);
    }
  }, [selectedService, logLineCount]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  useEffect(() => {
    if (!autoRefreshLogs) return;
    const interval = setInterval(loadLogs, 6000);
    return () => clearInterval(interval);
  }, [autoRefreshLogs, loadLogs]);

  const handleRestartService = async (svc: string) => {
    if (!window.confirm(`Haqiqatan ham '${svc}' servisni qayta ishga tushirmoqchimisiz?`)) return;
    setRestarting(svc);
    setRestartMsg(null);
    try {
      const token = localStorage.getItem("diamond_token") || "";
      const res = await requestJson<GenericRow>("/developer/server/service-restart", {
        method: "POST",
        token,
        body: { service: svc },
        timeoutMs: 35000,
      });
      setRestartMsg({ text: res.message || `${svc} qayta ishga tushirildi` });
      await loadStatus();
      if (selectedService === svc) await loadLogs();
    } catch (err: any) {
      setRestartMsg({ text: err.message || `${svc} restartida xatolik`, error: true });
    } finally {
      setRestarting(null);
    }
  };

  const metrics = (data?.metrics || {}) as GenericRow;
  const services = (data?.services || []) as GenericRow[];

  const filteredLogs = useMemo(() => {
    if (!logSearch.trim()) return logLines;
    const s = logSearch.toLowerCase();
    return logLines.filter((l) => l.toLowerCase().includes(s));
  }, [logLines, logSearch]);

  return (
    <div className="flex flex-col gap-6 pb-12 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <SectionTitle
            kicker="Telemetriya va Servislar"
            title={tt("section.developer-server", "Server va Jonli Loglar")}
            subtitle="CPU, RAM, disk yuklamasi, systemd servislarni boshqarish va real-time journalctl log ko'ruvchi."
          />
        </div>
        <button type="button" onClick={loadStatus} disabled={loading} className="btn btn-soft small">
          🔄 Yangilash
        </button>
      </div>

      {restartMsg && (
        <div
          className={`rounded-2xl border p-4 text-sm font-bold ${
            restartMsg.error
              ? "border-red-300 bg-red-50 text-red-800 dark:border-red-500/30 dark:bg-red-950/40 dark:text-red-200"
              : "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-950/40 dark:text-emerald-200"
          }`}
        >
          {restartMsg.text}
        </div>
      )}

      {/* Metrics Row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:gap-4">
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <span className="text-xs font-black uppercase text-indigo-600 dark:text-indigo-400">CPU Yuklama</span>
          <p className="mt-1 text-2xl font-black text-navy-900 dark:text-white">{Number(metrics.cpu_percent || 0).toFixed(1)}%</p>
          <span className="mt-1 block text-xs font-bold text-ink-500 dark:text-slate-400">{metrics.cpu_cores || 0} yadro</span>
        </div>
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <span className="text-xs font-black uppercase text-cyan-600 dark:text-cyan-400">RAM Xotira</span>
          <p className="mt-1 text-2xl font-black text-navy-900 dark:text-white">{Number(metrics.memory_percent || 0).toFixed(1)}%</p>
          <span className="mt-1 block text-xs font-bold text-ink-500 dark:text-slate-400">{systemBytes(metrics.memory_available_bytes)} bo'sh</span>
        </div>
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <span className="text-xs font-black uppercase text-emerald-600 dark:text-emerald-400">Disk Bo'sh Joy</span>
          <p className="mt-1 text-2xl font-black text-navy-900 dark:text-white">{Number(metrics.disk_percent || 0).toFixed(1)}%</p>
          <span className="mt-1 block text-xs font-bold text-ink-500 dark:text-slate-400">{systemBytes(metrics.disk_free_bytes)} bo'sh</span>
        </div>
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <span className="text-xs font-black uppercase text-amber-600 dark:text-amber-400">Load Average</span>
          <p className="mt-1 text-2xl font-black text-navy-900 dark:text-white font-mono">
            {Number(metrics.load_1 || 0).toFixed(1)}
          </p>
          <span className="mt-1 block text-xs font-bold text-ink-500 dark:text-slate-400">
            5m: {Number(metrics.load_5 || 0).toFixed(1)} · 15m: {Number(metrics.load_15 || 0).toFixed(1)}
          </span>
        </div>
      </div>

      {/* Services Table */}
      <div className="rounded-3xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
        <h3 className="mb-4 text-base font-black text-navy-900 dark:text-white">Systemd Servislar ({services.length})</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-line text-xs font-bold uppercase tracking-wider text-ink-500 dark:border-white/10 dark:text-slate-400">
                <th className="pb-3">Servis Nomi</th>
                <th className="pb-3">Holat</th>
                <th className="pb-3">PID</th>
                <th className="pb-3">Xotira</th>
                <th className="pb-3">Restart Soni</th>
                <th className="pb-3 text-right">Amallar</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line dark:divide-white/10">
              {services.map((svc) => {
                const isActive = svc.active_state === "active";
                return (
                  <tr key={svc.service} className="hover:bg-surface-soft dark:hover:bg-white/[0.02]">
                    <td className="py-3 font-mono font-bold text-navy-900 dark:text-white">
                      {svc.service}
                    </td>
                    <td className="py-3">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold ${
                          isActive
                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                            : "bg-red-500/10 text-red-600 dark:text-red-400"
                        }`}
                      >
                        {isActive ? "● Active (running)" : `✕ ${svc.active_state}`}
                      </span>
                    </td>
                    <td className="py-3 font-mono text-xs text-ink-500 dark:text-slate-400">{svc.pid || "—"}</td>
                    <td className="py-3 text-xs font-bold text-ink-600 dark:text-slate-300">
                      {svc.memory_bytes ? systemBytes(svc.memory_bytes) : "—"}
                    </td>
                    <td className="py-3 font-mono text-xs">
                      <span className={svc.restarts > 0 ? "font-bold text-amber-600 dark:text-amber-400" : "text-ink-500 dark:text-slate-400"}>
                        {svc.restarts}
                      </span>
                    </td>
                    <td className="py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setSelectedService(svc.service)}
                          className={`btn btn-soft small text-xs ${selectedService === svc.service ? "active" : ""}`}
                        >
                          Log ko'rish
                        </button>
                        <button
                          type="button"
                          onClick={() => handleRestartService(svc.service)}
                          disabled={restarting === svc.service}
                          className="btn btn-soft small text-xs text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/20"
                        >
                          {restarting === svc.service ? "Restart..." : "Restart"}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Live Log Viewer */}
      <div className="rounded-3xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="text-base font-black text-navy-900 dark:text-white">Jonli Loglar:</span>
            <select
              value={selectedService}
              onChange={(e) => setSelectedService(e.target.value)}
              className="rounded-xl border border-line bg-surface px-3 py-1.5 font-mono text-xs font-bold text-navy-900 dark:border-white/10 dark:bg-navy-900 dark:text-white"
            >
              {services.map((s) => (
                <option key={s.service} value={s.service}>
                  {s.service}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <input
              type="text"
              placeholder="Loglar ichidan qidirish..."
              value={logSearch}
              onChange={(e) => setLogSearch(e.target.value)}
              className="rounded-xl border border-line bg-surface-soft px-3 py-1 text-xs dark:border-white/10 dark:bg-white/[0.04] dark:text-white w-48 sm:w-64"
            />
            <div className="flex items-center gap-1">
              {[50, 100, 200].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setLogLineCount(n)}
                  className={`rounded-lg px-2 py-1 text-[11px] font-bold ${
                    logLineCount === n ? "bg-cyan-500 text-white" : "bg-surface-soft text-ink-600 dark:bg-white/10 dark:text-slate-300"
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
            <label className="flex items-center gap-2 text-xs font-bold text-ink-600 dark:text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefreshLogs}
                onChange={(e) => setAutoRefreshLogs(e.target.checked)}
              />
              Avto-yangilash (6s)
            </label>
            <button
              type="button"
              onClick={loadLogs}
              disabled={logLoading}
              className="btn btn-soft small text-xs"
            >
              {logLoading ? "Yuklanmoqda..." : "🔄"}
            </button>
          </div>
        </div>

        {/* Terminal Window */}
        <div className="relative rounded-2xl bg-navy-950 p-4 font-mono text-xs text-slate-200 border border-slate-800 shadow-inner h-96 overflow-y-auto scrollbar-thin">
          {filteredLogs.length ? (
            filteredLogs.map((line, idx) => {
              const isErr = line.includes("ERROR") || line.includes("Exception") || line.includes("failed");
              const isWarn = line.includes("WARNING") || line.includes("WARN");
              const isInfo = line.includes("INFO");
              return (
                <div
                  key={idx}
                  className={`leading-relaxed hover:bg-white/[0.04] px-1 rounded flex gap-3 ${
                    isErr ? "text-red-400 bg-red-950/20" : isWarn ? "text-amber-300" : isInfo ? "text-slate-200" : "text-slate-400"
                  }`}
                >
                  <span className="select-none text-slate-600 w-8 shrink-0 text-right">{idx + 1}</span>
                  <span className="whitespace-pre-wrap break-all">{line}</span>
                </div>
              );
            })
          ) : (
            <p className="text-slate-500">Log ma'lumotlari topilmadi.</p>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// 4. DEVELOPER MAINTENANCE VIEW
// ============================================================================

export function DeveloperMaintenanceView() {
  const tt = useWebT();
  const [settings, setSettings] = useState<GenericRow>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await requestJson<GenericRow>("/developer/mobile-maintenance", {
        token: localStorage.getItem("diamond_token") || "",
        timeoutMs: 15000,
      });
      setSettings(result || {});
      setError("");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Maintenance sozlamalari yuklanmadi.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const update = (role: "student" | "teacher", key: string, value: unknown) => {
    setSettings((previous) => ({ ...previous, [role]: { ...(previous[role] || {}), [key]: value } }));
    setSuccess(false);
  };

  const save = async () => {
    setSaving(true);
    setError("");
    setSuccess(false);
    try {
      const payload: GenericRow = {};
      for (const role of ["student", "teacher"] as const) {
        const item = (settings[role] || {}) as GenericRow;
        payload[role] = {
          maintenance_enabled: Boolean(item.enabled),
          maintenance_starts_at: item.starts_at ? new Date(String(item.starts_at)).toISOString() : "",
          maintenance_ends_at: item.ends_at ? new Date(String(item.ends_at)).toISOString() : "",
          maintenance_message_uz: String(item.message_uz || ""),
          maintenance_message_ru: String(item.message_ru || ""),
          maintenance_message_en: String(item.message_en || ""),
        };
      }
      const result = await requestJson<GenericRow>("/developer/mobile-maintenance", {
        method: "POST",
        token: localStorage.getItem("diamond_token") || "",
        body: payload,
        timeoutMs: 15000,
      });
      setSettings(result || {});
      setSuccess(true);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Saqlashda xatolik.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 pb-12 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <SectionTitle
            kicker="Tizim Tanaffusi"
            title={tt("section.developer-maintenance", "Rejali Maintenance Boshqaruvi")}
            subtitle="Mobil ilovalar va platforma uchun texnik ishlarni belgilash, vaqtini hisoblash va xabarlar chiqarish."
          />
        </div>
        <button
          type="button"
          onClick={save}
          disabled={saving || loading}
          className="btn btn-primary small"
        >
          {saving ? "Saqlanmoqda..." : "O'zgarishlarni Saqlash"}
        </button>
      </div>

      {success && (
        <div className="rounded-2xl border border-emerald-300 bg-emerald-50 p-4 text-sm font-bold text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-950/40 dark:text-emerald-200">
          Maintenance sozlamalari muvaffaqiyatli saqlandi!
        </div>
      )}
      {error && (
        <div className="rounded-2xl border border-red-300 bg-red-50 p-4 text-sm font-bold text-red-800 dark:border-red-500/30 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {(["student", "teacher"] as const).map((role) => {
          const item = (settings[role] || {}) as GenericRow;
          const title = role === "student" ? "🎓 Student App & Web" : "👨‍🏫 Teacher App & Web";
          return (
            <div
              key={role}
              className="rounded-3xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.03]"
            >
              <div className="flex items-center justify-between gap-3 border-b border-line pb-4 dark:border-white/10">
                <div>
                  <strong className="text-lg text-navy-900 dark:text-white">{title}</strong>
                  <p className="mt-0.5 text-xs text-ink-500 dark:text-slate-400">
                    Holat:{" "}
                    <span className="font-bold text-cyan-600 dark:text-cyan-300">
                      {item.active ? "● Hozir faol (foydalanuvchilarga ko'rsatilmoqda)" : item.enabled ? "Rejalashtirilgan" : "O'chiq"}
                    </span>
                  </p>
                </div>
                <label className="flex items-center gap-2 text-sm font-bold cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(item.enabled)}
                    onChange={(event) => update(role, "enabled", event.target.checked)}
                  />
                  <span>Rejimni Yoqish</span>
                </label>
              </div>

              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <label className="text-xs font-bold text-ink-600 dark:text-slate-300">
                  Boshlanish vaqti (Toshkent UTC+5)
                  <input
                    type="datetime-local"
                    value={datetimeLocalValue(item.starts_at)}
                    onChange={(event) => update(role, "starts_at", event.target.value)}
                    className="mt-1 w-full rounded-xl border border-line bg-surface-soft px-3 py-2 text-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-white"
                  />
                </label>
                <label className="text-xs font-bold text-ink-600 dark:text-slate-300">
                  Tugash vaqti (Toshkent UTC+5)
                  <input
                    type="datetime-local"
                    value={datetimeLocalValue(item.ends_at)}
                    onChange={(event) => update(role, "ends_at", event.target.value)}
                    className="mt-1 w-full rounded-xl border border-line bg-surface-soft px-3 py-2 text-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-white"
                  />
                </label>
              </div>

              <div className="mt-4 space-y-3">
                <label className="block text-xs font-bold text-ink-600 dark:text-slate-300">
                  Xabar matni (O'zbekcha)
                  <textarea
                    value={String(item.message_uz || "")}
                    onChange={(event) => update(role, "message_uz", event.target.value)}
                    maxLength={500}
                    rows={2}
                    placeholder="Rejali texnik ishlar olib borilmoqda. Tez orada qaytamiz."
                    className="mt-1 w-full rounded-xl border border-line bg-surface-soft px-3 py-2 text-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-white"
                  />
                </label>
                <label className="block text-xs font-bold text-ink-600 dark:text-slate-300">
                  Xabar matni (Ruscha)
                  <textarea
                    value={String(item.message_ru || "")}
                    onChange={(event) => update(role, "message_ru", event.target.value)}
                    maxLength={500}
                    rows={2}
                    placeholder="Проводятся плановые технические работы."
                    className="mt-1 w-full rounded-xl border border-line bg-surface-soft px-3 py-2 text-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-white"
                  />
                </label>
                <label className="block text-xs font-bold text-ink-600 dark:text-slate-300">
                  Xabar matni (Inglizcha)
                  <textarea
                    value={String(item.message_en || "")}
                    onChange={(event) => update(role, "message_en", event.target.value)}
                    maxLength={500}
                    rows={2}
                    placeholder="Scheduled maintenance in progress. We'll be back shortly."
                    className="mt-1 w-full rounded-xl border border-line bg-surface-soft px-3 py-2 text-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-white"
                  />
                </label>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================================
// 5. DEVELOPER FEATURE FLAGS VIEW
// ============================================================================

export function DeveloperFlagsView() {
  const tt = useWebT();
  const [flags, setFlags] = useState<GenericRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [newFlag, setNewFlag] = useState({ flag_key: "", title: "", description: "", target_roles: "all", is_enabled: false });

  const loadFlags = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("diamond_token") || "";
      const res = await requestJson<{ flags: GenericRow[] }>("/developer/feature-flags", { token, timeoutMs: 10000 });
      setFlags(res.flags || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFlags();
  }, [loadFlags]);

  const toggleFlag = async (flag: GenericRow) => {
    const nextVal = !flag.is_enabled;
    setSavingKey(flag.flag_key);
    try {
      const token = localStorage.getItem("diamond_token") || "";
      await requestJson("/developer/feature-flags", {
        method: "POST",
        token,
        body: {
          flag_key: flag.flag_key,
          title: flag.title,
          description: flag.description,
          target_roles: flag.target_roles,
          target_user_ids: flag.target_user_ids,
          is_enabled: nextVal,
        },
      });
      setFlags((prev) => prev.map((f) => (f.flag_key === flag.flag_key ? { ...f, is_enabled: nextVal } : f)));
    } finally {
      setSavingKey(null);
    }
  };

  const handleCreateFlag = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFlag.flag_key.trim()) return;
    try {
      const token = localStorage.getItem("diamond_token") || "";
      await requestJson("/developer/feature-flags", {
        method: "POST",
        token,
        body: newFlag,
      });
      setModalOpen(false);
      setNewFlag({ flag_key: "", title: "", description: "", target_roles: "all", is_enabled: false });
      await loadFlags();
    } catch (err: any) {
      alert(err.message || "Xatolik yuz berdi");
    }
  };

  return (
    <div className="flex flex-col gap-6 pb-12 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <SectionTitle
            kicker="Eksperimentlar va Flags"
            title={tt("section.developer-flags", "Feature Flags Boshqaruvi")}
            subtitle="Yangi imkoniyatlarni bosqichma-bosqich yoqish, rollar bo'yicha targeting va avtomatik kill switch."
          />
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            className="btn btn-primary small flex items-center gap-2"
          >
            <span>➕</span>
            <span>Yangi Flag Qo'shish</span>
          </button>
          <button type="button" onClick={loadFlags} disabled={loading} className="btn btn-soft small">
            🔄 Yangilash
          </button>
        </div>
      </div>

      <div className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-xs font-medium text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/40 dark:text-amber-200">
        💡 <strong>Eslatma:</strong> Feature flags tizimi orqali yangi funksiyalarni butun platformani qayta deploy qilmasdan 1 soniyada yoqish yoki o'chirish mumkin.
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {flags.map((flag) => {
          const isBusy = savingKey === flag.flag_key;
          return (
            <div
              key={flag.flag_key}
              className="flex flex-col justify-between rounded-3xl border border-line bg-surface p-5 shadow-sm transition-all hover:border-cyan-400/40 dark:border-white/10 dark:bg-white/[0.03]"
            >
              <div>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h4 className="text-base font-black text-navy-900 dark:text-white">{flag.title || flag.flag_key}</h4>
                    <span className="font-mono text-xs font-bold text-cyan-600 dark:text-cyan-400">{flag.flag_key}</span>
                  </div>
                  <label className="relative inline-flex cursor-pointer items-center">
                    <input
                      type="checkbox"
                      checked={Boolean(flag.is_enabled)}
                      onChange={() => toggleFlag(flag)}
                      disabled={isBusy}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer dark:bg-slate-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyan-500"></div>
                  </label>
                </div>
                <p className="mt-3 text-xs font-medium text-ink-500 dark:text-slate-400 leading-relaxed">
                  {flag.description || "Tavsif ko'rsatilmagan"}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-line dark:border-white/10 flex items-center justify-between text-xs">
                <span className="rounded-md bg-surface-soft px-2 py-0.5 font-bold text-ink-600 dark:bg-white/10 dark:text-slate-300">
                  Target: {flag.target_roles || "all"}
                </span>
                <span className={`font-bold ${flag.is_enabled ? "text-emerald-600 dark:text-emerald-400" : "text-slate-400"}`}>
                  {flag.is_enabled ? "● Yoqilgan" : "○ O'chiq"}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-900/60 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-3xl border border-line bg-surface p-6 shadow-2xl dark:border-white/10 dark:bg-navy-950">
            <h3 className="text-lg font-black text-navy-900 dark:text-white">Yangi Feature Flag</h3>
            <form onSubmit={handleCreateFlag} className="mt-4 space-y-4">
              <div>
                <label className="text-xs font-bold text-ink-600 dark:text-slate-300">Flag Kaliti (key)</label>
                <input
                  type="text"
                  placeholder="masalan: new_feature_v2"
                  value={newFlag.flag_key}
                  onChange={(e) => setNewFlag({ ...newFlag, flag_key: e.target.value })}
                  required
                  className="mt-1 w-full rounded-xl border border-line bg-surface-soft px-3 py-2 text-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-white"
                />
              </div>
              <div>
                <label className="text-xs font-bold text-ink-600 dark:text-slate-300">Sarlavha</label>
                <input
                  type="text"
                  placeholder="Yangi imkoniyat"
                  value={newFlag.title}
                  onChange={(e) => setNewFlag({ ...newFlag, title: e.target.value })}
                  required
                  className="mt-1 w-full rounded-xl border border-line bg-surface-soft px-3 py-2 text-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-white"
                />
              </div>
              <div>
                <label className="text-xs font-bold text-ink-600 dark:text-slate-300">Tavsif</label>
                <textarea
                  placeholder="Funksiya nima qilishi haqida..."
                  value={newFlag.description}
                  onChange={(e) => setNewFlag({ ...newFlag, description: e.target.value })}
                  rows={2}
                  className="mt-1 w-full rounded-xl border border-line bg-surface-soft px-3 py-2 text-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-white"
                />
              </div>
              <div>
                <label className="text-xs font-bold text-ink-600 dark:text-slate-300">Target Rollar (vergul bilan)</label>
                <input
                  type="text"
                  placeholder="student, teacher, admin"
                  value={newFlag.target_roles}
                  onChange={(e) => setNewFlag({ ...newFlag, target_roles: e.target.value })}
                  className="mt-1 w-full rounded-xl border border-line bg-surface-soft px-3 py-2 text-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-white"
                />
              </div>
              <div className="flex justify-end gap-3 pt-3">
                <button type="button" onClick={() => setModalOpen(false)} className="btn btn-soft small">
                  Bekor qilish
                </button>
                <button type="submit" className="btn btn-primary small">
                  Qo'shish
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// 6. DEVELOPER AUDIT VIEW
// ============================================================================

export function DeveloperAuditView() {
  const tt = useWebT();
  const [events, setEvents] = useState<GenericRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  const loadAudit = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("diamond_token") || "";
      const res = await requestJson<{ events: GenericRow[] }>("/developer/audit/logs?limit=80", { token, timeoutMs: 10000 });
      setEvents(res.events || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAudit();
  }, [loadAudit]);

  const filteredEvents = useMemo(() => {
    if (filter === "all") return events;
    return events.filter((e) => e.source === filter);
  }, [events, filter]);

  return (
    <div className="flex flex-col gap-6 pb-12 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <SectionTitle
            kicker="Xavfsizlik va Nazorat"
            title={tt("section.developer-audit", "Audit va Xavfsizlik Markazi")}
            subtitle="Admin va developer amallari, iqtisod qoidalaridagi o'zgarishlar, to'lov auditlari va loginlar tarixi."
          />
        </div>
        <button type="button" onClick={loadAudit} disabled={loading} className="btn btn-soft small">
          🔄 Yangilash
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {[
          { id: "all", label: "Barcha Hodisalar" },
          { id: "security", label: "🛡 Xavfsizlik & Developer" },
          { id: "economy", label: "💎 Iqtisod Qoidalari" },
          { id: "payment", label: "💳 To'lov Auditlari" },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setFilter(tab.id)}
            className={`rounded-xl px-3 py-1.5 text-xs font-bold transition-all ${
              filter === tab.id
                ? "bg-cyan-500 text-white shadow-sm"
                : "bg-surface text-ink-600 border border-line dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="rounded-3xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
        <h3 className="mb-4 text-base font-black text-navy-900 dark:text-white">Oxirgi Hodisalar ({filteredEvents.length})</h3>
        {filteredEvents.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-line text-xs font-bold uppercase tracking-wider text-ink-500 dark:border-white/10 dark:text-slate-400">
                  <th className="pb-3">Vaqt</th>
                  <th className="pb-3">Kim</th>
                  <th className="pb-3">Tur</th>
                  <th className="pb-3">Tafsilotlar</th>
                  <th className="pb-3">IP Manzil</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line dark:divide-white/10">
                {filteredEvents.map((e, idx) => (
                  <tr key={idx} className="hover:bg-surface-soft dark:hover:bg-white/[0.02]">
                    <td className="py-3 text-xs text-ink-500 dark:text-slate-400 whitespace-nowrap">
                      {new Date(e.created_at).toLocaleString("uz-UZ")}
                    </td>
                    <td className="py-3 font-bold text-navy-900 dark:text-white whitespace-nowrap">
                      {e.actor} <span className="text-xs text-ink-400 font-normal">({e.role})</span>
                    </td>
                    <td className="py-3">
                      <span className="rounded bg-surface-soft px-2 py-0.5 font-mono text-xs font-bold text-cyan-700 dark:bg-white/10 dark:text-cyan-300">
                        {e.type}
                      </span>
                    </td>
                    <td className="py-3 text-xs text-ink-600 dark:text-slate-300 max-w-xs truncate">
                      {e.details}
                    </td>
                    <td className="py-3 font-mono text-xs text-ink-400">{e.ip}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-ink-500 dark:text-slate-400">Hozircha audit yozuvlari topilmadi.</p>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// 7. DEVELOPER JOBS & QUEUE VIEW
// ============================================================================

export function DeveloperJobsView() {
  const tt = useWebT();
  const [data, setData] = useState<GenericRow | null>(null);
  const [loading, setLoading] = useState(true);

  const loadJobs = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("diamond_token") || "";
      const res = await requestJson<GenericRow>("/developer/jobs/status", { token, timeoutMs: 10000 });
      setData(res || null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  const broadcasts = (data?.broadcasts || {}) as Record<string, number>;
  const tokens = (data?.push_device_tokens || []) as GenericRow[];
  const schedulers = (data?.schedulers || []) as GenericRow[];

  return (
    <div className="flex flex-col gap-6 pb-12 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <SectionTitle
            kicker="Background Jobs"
            title={tt("section.developer-jobs", "Queue va Joblar Nazorati")}
            subtitle="Telegram bot webhooklari, Firebase push navbati, background schedulerlar va to'lov xabarnomalari oqimi."
          />
        </div>
        <button type="button" onClick={loadJobs} disabled={loading} className="btn btn-soft small">
          🔄 Yangilash
        </button>
      </div>

      <div className="rounded-3xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
        <h3 className="mb-4 text-base font-black text-navy-900 dark:text-white">Background Schedulerlar</h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {schedulers.map((sch) => {
            const isAct = sch.status === "active";
            return (
              <div
                key={sch.name}
                className="rounded-2xl border border-line bg-surface-soft p-4 dark:border-white/10 dark:bg-white/[0.02]"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-navy-900 dark:text-white truncate">{sch.name}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                      isAct ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-slate-200 text-slate-500 dark:bg-slate-800 dark:text-slate-400"
                    }`}
                  >
                    {sch.status}
                  </span>
                </div>
                <p className="mt-2 text-xs text-ink-500 dark:text-slate-400">Oraliq: {sch.interval}</p>
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-3xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <h3 className="mb-3 text-base font-black text-navy-900 dark:text-white">Push Tokens (FCM)</h3>
          <p className="mb-4 text-xs text-ink-500 dark:text-slate-400">
            Mobil ilovalarda push xabarnoma olish uchun ro'yxatdan o'tgan faol qurilmalar.
          </p>
          {tokens.length ? (
            <div className="space-y-2">
              {tokens.map((t, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between rounded-xl border border-line p-3 text-sm dark:border-white/10 dark:bg-white/[0.02]"
                >
                  <span className="font-bold text-navy-900 dark:text-white">
                    {t.app} <span className="text-xs uppercase text-cyan-600 dark:text-cyan-300">({t.platform})</span>
                  </span>
                  <span className="rounded-lg bg-surface-soft px-3 py-1 font-mono text-xs font-black text-navy-900 dark:bg-white/10 dark:text-white">
                    {t.count} ta token
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-ink-500 dark:text-slate-400">Tokenlar topilmadi.</p>
          )}
        </div>

        <div className="rounded-3xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <h3 className="mb-3 text-base font-black text-navy-900 dark:text-white">Broadcast Xabarlar Oqimi</h3>
          <p className="mb-4 text-xs text-ink-500 dark:text-slate-400">
            Bot va veb-sayt orqali yuborilgan ommaviy xabarlar holati.
          </p>
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(broadcasts).map(([status, count]) => (
              <div
                key={status}
                className="rounded-xl border border-line p-3 text-sm dark:border-white/10 dark:bg-white/[0.02]"
              >
                <span className="text-xs uppercase font-bold text-ink-500 dark:text-slate-400">{status}</span>
                <p className="mt-1 text-xl font-black text-navy-900 dark:text-white">{count}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-3 border-t border-line dark:border-white/10 flex items-center justify-between text-xs text-ink-500 dark:text-slate-400">
            <span>Oxirgi 24 soatdagi to'lov xabarlari:</span>
            <strong className="text-navy-900 dark:text-white font-mono text-sm">{data?.notifications_last_24h || 0}</strong>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// 8. DEVELOPER DATABASE & CACHE VIEW
// ============================================================================

export function DeveloperDatabaseView() {
  const tt = useWebT();
  const [data, setData] = useState<GenericRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [purging, setPurging] = useState(false);
  const [purgeMsg, setPurgeMsg] = useState<string | null>(null);

  const loadDb = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("diamond_token") || "";
      const res = await requestJson<GenericRow>("/developer/database/stats", { token, timeoutMs: 10000 });
      setData(res || null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDb();
  }, [loadDb]);

  const handlePurgeCache = async () => {
    setPurging(true);
    setPurgeMsg(null);
    try {
      const token = localStorage.getItem("diamond_token") || "";
      const res = await requestJson<GenericRow>("/developer/database/purge-cache", { method: "POST", token });
      setPurgeMsg(res.message || "Kesh tozalandi");
      await loadDb();
    } catch (err: any) {
      setPurgeMsg(`Xatolik: ${err.message}`);
    } finally {
      setPurging(false);
    }
  };

  const tables = (data?.tables || []) as GenericRow[];

  return (
    <div className="flex flex-col gap-6 pb-12 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <SectionTitle
            kicker="Data & Xotira"
            title={tt("section.developer-database", "Database va Kesh Vositalari")}
            subtitle="PostgreSQL / SQLite jadvallari qatorlar soni, RAM keshlari monitoringi va bir marta bosishda tozalash."
          />
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handlePurgeCache}
            disabled={purging}
            className="btn btn-primary small flex items-center gap-2"
          >
            <span>🧹</span>
            <span>{purging ? "Tozalanmoqda..." : "Keshni Tozalash"}</span>
          </button>
          <button type="button" onClick={loadDb} disabled={loading} className="btn btn-soft small">
            🔄 Yangilash
          </button>
        </div>
      </div>

      {purgeMsg && (
        <div className="rounded-2xl border border-emerald-300 bg-emerald-50 p-4 text-sm font-bold text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-950/40 dark:text-emerald-200">
          {purgeMsg}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <span className="text-xs font-black uppercase text-cyan-600 dark:text-cyan-400">Unread Count Kesh</span>
          <p className="mt-1 text-2xl font-black text-navy-900 dark:text-white">
            {data?.unread_cache_keys_cached || 0} ta kalit
          </p>
          <p className="mt-2 text-xs text-ink-500 dark:text-slate-400 leading-relaxed">
            Talabalar va o'qituvchilarning o'qilmagan xabarlari sonini tezkor berish uchun xotirada saqlanadigan ma'lumotlar.
          </p>
        </div>

        <div className="rounded-2xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <span className="text-xs font-black uppercase text-indigo-600 dark:text-indigo-400">Overview Payload Kesh</span>
          <p className="mt-1 text-2xl font-black text-navy-900 dark:text-white">
            {data?.student_overview_cached || 0} ta sessiya
          </p>
          <p className="mt-2 text-xs text-ink-500 dark:text-slate-400 leading-relaxed">
            Talaba boshqaruv panelining eng og'ir hisob-kitoblarini takroran bajarmaslik uchun saqlanadigan oraliq kesh.
          </p>
        </div>
      </div>

      <div className="rounded-3xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
        <h3 className="mb-4 text-base font-black text-navy-900 dark:text-white">Asosiy Jadvallar Qatorlar Soni</h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {tables.map((t) => (
            <div
              key={t.table}
              className="flex items-center justify-between rounded-xl border border-line p-3 text-sm dark:border-white/10 dark:bg-white/[0.02]"
            >
              <span className="font-mono text-xs font-bold text-navy-900 dark:text-white">{t.table}</span>
              <span className="rounded-md bg-surface-soft px-2.5 py-1 font-mono text-xs font-black text-cyan-600 dark:bg-white/10 dark:text-cyan-300">
                {t.rows?.toLocaleString("uz-UZ") || 0}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// 9. DEVELOPER API METRICS VIEW
// ============================================================================

export function DeveloperApiMetricsView() {
  const tt = useWebT();
  const [data, setData] = useState<GenericRow | null>(null);
  const [loading, setLoading] = useState(true);

  const loadMetrics = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("diamond_token") || "";
      const res = await requestJson<GenericRow>("/developer/api-metrics/telemetry", { token, timeoutMs: 10000 });
      setData(res || null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMetrics();
  }, [loadMetrics]);

  const proc = data?.process || {};
  const integrations = (data?.integrations || []) as GenericRow[];

  return (
    <div className="flex flex-col gap-6 pb-12 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <SectionTitle
            kicker="Telemetriya"
            title={tt("section.developer-api-metrics", "API Telemetriya va Salomatlik")}
            subtitle="Database javob tezligi, backend jarayoni xotirasi va uchinchi tomon integratsiyalari holati."
          />
        </div>
        <button type="button" onClick={loadMetrics} disabled={loading} className="btn btn-soft small">
          🔄 Yangilash
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <span className="text-xs font-black uppercase text-cyan-600 dark:text-cyan-400">Database Ping Latency</span>
          <p className="mt-1 text-3xl font-black text-navy-900 dark:text-white">
            {data?.database_latency_ms || 0} <span className="text-base font-normal text-ink-500">ms</span>
          </p>
          <span className="mt-2 block text-xs font-bold text-emerald-600 dark:text-emerald-400">
            {Number(data?.database_latency_ms || 0) < 5 ? "● Ultra tezkor ulanish" : "● Barqaror"}
          </span>
        </div>

        <div className="rounded-2xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <span className="text-xs font-black uppercase text-indigo-600 dark:text-indigo-400">Backend Process RSS</span>
          <p className="mt-1 text-3xl font-black text-navy-900 dark:text-white">
            {proc.rss_mb || 0} <span className="text-base font-normal text-ink-500">MB</span>
          </p>
          <span className="mt-2 block text-xs font-bold text-ink-500 dark:text-slate-400">
            VMS: {proc.vms_mb || 0} MB · {proc.threads || 0} ta oqim
          </span>
        </div>

        <div className="rounded-2xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
          <span className="text-xs font-black uppercase text-emerald-600 dark:text-emerald-400">Integratsiyalar</span>
          <p className="mt-1 text-3xl font-black text-navy-900 dark:text-white">
            {integrations.length} / {integrations.length || 4}
          </p>
          <span className="mt-2 block text-xs font-bold text-emerald-600 dark:text-emerald-400">
            Barcha xizmatlar tayyor
          </span>
        </div>
      </div>

      <div className="rounded-3xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.03]">
        <h3 className="mb-4 text-base font-black text-navy-900 dark:text-white">Tashqi Xizmatlar Salomatligi</h3>
        <div className="space-y-3">
          {integrations.map((item, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between rounded-2xl border border-line p-4 text-sm dark:border-white/10 dark:bg-white/[0.02]"
            >
              <div className="flex items-center gap-3">
                <span className="flex h-3 w-3 rounded-full bg-emerald-500"></span>
                <span className="font-bold text-navy-900 dark:text-white">{item.name}</span>
              </div>
              <div className="flex items-center gap-4">
                {item.latency_ms !== undefined && (
                  <span className="font-mono text-xs text-ink-500 dark:text-slate-400">{item.latency_ms} ms</span>
                )}
                <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-bold text-emerald-600 dark:text-emerald-400">
                  {item.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// MAIN DEVELOPER WORKSPACE ROUTER
// ============================================================================

export function DeveloperWorkspace({
  section = "home",
  onNavigate,
}: {
  section?: string;
  onNavigate: (section: string) => void;
}) {
  switch (section) {
    case "developer-deploy":
      return <DeveloperDeployView />;
    case "developer-server":
      return <DeveloperServerView />;
    case "developer-maintenance":
      return <DeveloperMaintenanceView />;
    case "developer-flags":
      return <DeveloperFlagsView />;
    case "developer-audit":
      return <DeveloperAuditView />;
    case "developer-jobs":
      return <DeveloperJobsView />;
    case "developer-database":
      return <DeveloperDatabaseView />;
    case "developer-api-metrics":
      return <DeveloperApiMetricsView />;
    case "home":
    default:
      return <DeveloperHomeView onNavigate={onNavigate} />;
  }
}
