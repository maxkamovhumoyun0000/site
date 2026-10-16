"use client";

import { useCallback, useEffect, useState } from "react";

type LiveRoom = {
  id: string;
  title: string;
  subject: "english" | "russian" | string;
  host_user_id: number;
  status: "active" | "ending" | "ended" | string;
  participant_count?: number;
  max_participants?: number;
  created_at?: string;
  ended_at?: string | null;
};

type Props = {
  apiFetch: (path: string, options?: { method?: string; body?: unknown }) => Promise<unknown>;
  currentUserId: number;
};

function roomDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("uz-UZ");
}

export function SpeakingLiveManagement({ apiFetch, currentUserId }: Props) {
  const [rooms, setRooms] = useState<LiveRoom[]>([]);
  const [title, setTitle] = useState("IELTS Speaking Live Practice");
  const [subject, setSubject] = useState<"english" | "russian">("english");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [endingId, setEndingId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await apiFetch("/staff/speaking/live-video/rooms", { method: "GET" }) as { rooms?: LiveRoom[] };
      setRooms(Array.isArray(payload.rooms) ? payload.rooms : []);
    } catch (cause: any) {
      setError(cause?.message || "Live xonalarni yuklab bo‘lmadi.");
    } finally {
      setLoading(false);
    }
  }, [apiFetch]);

  useEffect(() => {
    void load();
  }, [load]);

  async function startRoom(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanTitle = title.trim();
    if (cleanTitle.length < 3) {
      setError("Xona nomi kamida 3 ta belgidan iborat bo‘lsin.");
      return;
    }
    setSaving(true);
    setMessage("");
    setError("");
    try {
      const payload = await apiFetch("/api/speaking/live-video/rooms", {
        method: "POST",
        body: { title: cleanTitle, subject },
      }) as { room?: LiveRoom };
      const room = payload.room;
      setMessage(room ? `Live xona ochildi: ${room.title}. Speaking ilovasida endi qatnashchilar xonani ko‘ra oladi.` : "Live xona ochildi.");
      await load();
    } catch (cause: any) {
      setError(cause?.message || "Live xonani ochib bo‘lmadi.");
    } finally {
      setSaving(false);
    }
  }

  async function endRoom(room: LiveRoom) {
    setEndingId(room.id);
    setMessage("");
    setError("");
    try {
      await apiFetch(`/api/speaking/live-video/rooms/${encodeURIComponent(room.id)}/end`, { method: "POST" });
      setMessage(`“${room.title}” live xonasi tugatildi.`);
      await load();
    } catch (cause: any) {
      setError(cause?.message || "Live xonani tugatib bo‘lmadi.");
    } finally {
      setEndingId("");
    }
  }

  const activeRooms = rooms.filter((room) => room.status === "active" || room.status === "ending");

  return (
    <section className="mx-auto w-full max-w-6xl space-y-5 px-3 py-5 pb-24 sm:px-6">
      <header className="rounded-3xl border border-cyan-400/25 bg-gradient-to-br from-cyan-500/10 via-white to-blue-500/10 p-6 shadow-sm dark:from-cyan-400/10 dark:via-navy-950 dark:to-blue-500/10">
        <span className="inline-flex rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-black uppercase tracking-wide text-cyan-700 dark:text-cyan-300">Diamond Speaking Live</span>
        <h1 className="mt-3 text-2xl font-black tracking-tight text-navy-950 dark:text-white">Live video boshqaruvi</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-600 dark:text-slate-300">Speaking ilovasi uchun jonli xona oching va o‘zingiz boshlagan live’ni xavfsiz tugating. Har bir xonada 1 000 tagacha qatnashchi bo‘lishi mumkin.</p>
      </header>

      {message ? <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm font-bold text-emerald-700 dark:text-emerald-300">✓ {message}</div> : null}
      {error ? <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm font-semibold text-red-700 dark:text-red-300">⚠ {error}</div> : null}

      <form onSubmit={startRoom} className="grid gap-3 rounded-2xl border border-line bg-surface p-5 shadow-sm md:grid-cols-[1fr_180px_auto] dark:border-white/10 dark:bg-navy-950">
        <label className="grid gap-1 text-sm font-bold text-navy-950 dark:text-white">
          Live xona nomi
          <input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={90} className="rounded-xl border border-line bg-white px-3 py-3 text-sm font-medium outline-none focus:border-cyan-500 dark:border-white/15 dark:bg-white/5 dark:text-white" />
        </label>
        <label className="grid gap-1 text-sm font-bold text-navy-950 dark:text-white">
          Fan
          <select value={subject} onChange={(event) => setSubject(event.target.value as "english" | "russian")} className="rounded-xl border border-line bg-white px-3 py-3 text-sm font-medium outline-none focus:border-cyan-500 dark:border-white/15 dark:bg-white/5 dark:text-white">
            <option value="english">English / IELTS</option>
            <option value="russian">Rus tili</option>
          </select>
        </label>
        <button type="submit" disabled={saving} className="self-end rounded-xl bg-cyan-600 px-5 py-3 text-sm font-black text-white transition hover:bg-cyan-500 disabled:opacity-60">{saving ? "Ochilmoqda…" : "Live boshlash"}</button>
      </form>

      <div className="overflow-hidden rounded-2xl border border-line bg-surface shadow-sm dark:border-white/10 dark:bg-navy-950">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4 dark:border-white/10">
          <div><h2 className="font-black text-navy-950 dark:text-white">Jonli xonalar</h2><p className="mt-0.5 text-xs text-ink-500 dark:text-slate-400">Aktiv: {activeRooms.length} ta</p></div>
          <button type="button" onClick={() => void load()} disabled={loading} className="rounded-xl border border-line px-4 py-2 text-sm font-black text-ink-700 transition hover:bg-surface-soft disabled:opacity-60 dark:border-white/15 dark:text-slate-200 dark:hover:bg-white/10">Yangilash</button>
        </div>
        {loading ? <div className="p-10 text-center text-sm text-ink-500 dark:text-slate-400">Yuklanmoqda…</div> : rooms.length === 0 ? <div className="p-10 text-center text-sm text-ink-500 dark:text-slate-400">Hozircha live video xonasi yo‘q.</div> : <div className="divide-y divide-line dark:divide-white/10">{rooms.map((room) => {
          const active = room.status === "active" || room.status === "ending";
          const ownRoom = Number(room.host_user_id) === currentUserId;
          return <article key={room.id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"><div><div className="flex flex-wrap items-center gap-2"><h3 className="font-black text-navy-950 dark:text-white">{room.title}</h3><span className={`rounded-full px-2.5 py-1 text-xs font-black ${active ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "bg-slate-500/10 text-slate-700 dark:text-slate-300"}`}>{active ? "Jonli" : "Tugagan"}</span>{ownRoom ? <span className="rounded-full bg-cyan-500/10 px-2.5 py-1 text-xs font-black text-cyan-700 dark:text-cyan-300">Sizning xonangiz</span> : null}</div><p className="mt-1 text-xs text-ink-500 dark:text-slate-400">{room.subject === "russian" ? "Rus tili" : "English / IELTS"} · {Number(room.participant_count || 0)} / {Number(room.max_participants || 1000)} qatnashchi · {roomDate(room.created_at)}</p></div>{active && ownRoom ? <button type="button" disabled={endingId === room.id} onClick={() => void endRoom(room)} className="rounded-xl bg-red-600 px-4 py-2.5 text-sm font-black text-white transition hover:bg-red-500 disabled:opacity-60">{endingId === room.id ? "Tugatilyapti…" : "Live’ni tugatish"}</button> : null}</article>;
        })}</div>}
      </div>
    </section>
  );
}

type SpeakingAdminIdentity = {
  id?: string | number;
  full_name?: string;
  login_id?: string;
  phone?: string | null;
  subjects?: string[];
};

type SpeakingAdminPersonalProps = {
  apiFetch: Props["apiFetch"];
  user: SpeakingAdminIdentity;
  onNavigate: (section: string) => void;
  profileMode?: boolean;
};

function SpeakingAdminPersonalPanel({
  apiFetch,
  user,
  onNavigate,
  profileMode = false,
}: SpeakingAdminPersonalProps) {
  const [rooms, setRooms] = useState<LiveRoom[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const userId = Number(user.id || 0);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await apiFetch("/staff/speaking/live-video/rooms", { method: "GET" }) as { rooms?: LiveRoom[] };
      setRooms(Array.isArray(payload.rooms) ? payload.rooms : []);
    } catch (cause: any) {
      setError(cause?.message || "Shaxsiy live ma’lumotlarini yuklab bo‘lmadi.");
    } finally {
      setLoading(false);
    }
  }, [apiFetch]);

  useEffect(() => {
    void load();
  }, [load]);

  const ownRooms = rooms.filter((room) => Number(room.host_user_id) === userId);
  const activeRooms = ownRooms.filter((room) => room.status === "active" || room.status === "ending");
  const participantTotal = ownRooms.reduce((total, room) => total + Number(room.participant_count || 0), 0);
  const title = profileMode ? "Speaking admin profili" : "Speaking admin bosh sahifasi";

  return (
    <section className="mx-auto w-full max-w-6xl space-y-5 px-3 py-5 pb-24 sm:px-6">
      <header className="rounded-3xl border border-cyan-400/25 bg-gradient-to-br from-cyan-500/10 via-white to-blue-500/10 p-6 shadow-sm dark:from-cyan-400/10 dark:via-navy-950 dark:to-blue-500/10">
        <span className="inline-flex rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-black uppercase tracking-wide text-cyan-700 dark:text-cyan-300">Diamond Speaking Admin</span>
        <h1 className="mt-3 text-2xl font-black tracking-tight text-navy-950 dark:text-white">{title}</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-600 dark:text-slate-300">Bu sahifa faqat sizning Speaking administrator akkauntingiz, xonalaringiz va Speaking App boshqaruvlaringizni ko‘rsatadi.</p>
      </header>

      {error ? <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm font-semibold text-red-700 dark:text-red-300">⚠ {error}</div> : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <article className="rounded-2xl border border-line bg-surface p-4 shadow-sm dark:border-white/10 dark:bg-navy-950"><p className="text-xs font-bold uppercase tracking-wide text-ink-500 dark:text-slate-400">Login ID</p><p className="mt-2 break-all text-lg font-black text-navy-950 dark:text-white">{user.login_id || "—"}</p></article>
        <article className="rounded-2xl border border-line bg-surface p-4 shadow-sm dark:border-white/10 dark:bg-navy-950"><p className="text-xs font-bold uppercase tracking-wide text-ink-500 dark:text-slate-400">Mening live xonalarim</p><p className="mt-2 text-2xl font-black text-cyan-700 dark:text-cyan-300">{loading ? "…" : ownRooms.length}</p></article>
        <article className="rounded-2xl border border-line bg-surface p-4 shadow-sm dark:border-white/10 dark:bg-navy-950"><p className="text-xs font-bold uppercase tracking-wide text-ink-500 dark:text-slate-400">Hozir jonli</p><p className="mt-2 text-2xl font-black text-emerald-700 dark:text-emerald-300">{loading ? "…" : activeRooms.length}</p></article>
        <article className="rounded-2xl border border-line bg-surface p-4 shadow-sm dark:border-white/10 dark:bg-navy-950"><p className="text-xs font-bold uppercase tracking-wide text-ink-500 dark:text-slate-400">Qatnashchilar</p><p className="mt-2 text-2xl font-black text-navy-950 dark:text-white">{loading ? "…" : participantTotal}</p></article>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.25fr_0.75fr]">
        <article className="rounded-2xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-navy-950">
          <h2 className="text-lg font-black text-navy-950 dark:text-white">Mening akkauntim</h2>
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2"><div><dt className="font-bold text-ink-500 dark:text-slate-400">Ism</dt><dd className="mt-1 font-black text-navy-950 dark:text-white">{user.full_name || "Speaking administrator"}</dd></div><div><dt className="font-bold text-ink-500 dark:text-slate-400">Telefon</dt><dd className="mt-1 font-black text-navy-950 dark:text-white">{user.phone || "—"}</dd></div><div><dt className="font-bold text-ink-500 dark:text-slate-400">Ruxsat</dt><dd className="mt-1 font-black text-emerald-700 dark:text-emerald-300">Speaking App boshqaruvi</dd></div><div><dt className="font-bold text-ink-500 dark:text-slate-400">Fanlar</dt><dd className="mt-1 font-black text-navy-950 dark:text-white">{Array.isArray(user.subjects) && user.subjects.length ? user.subjects.join(", ") : "English / Russian"}</dd></div></dl>
        </article>
        <article className="rounded-2xl border border-line bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-navy-950"><h2 className="text-lg font-black text-navy-950 dark:text-white">Tezkor amallar</h2><div className="mt-4 grid gap-2"><button type="button" onClick={() => onNavigate("speaking-live")} className="rounded-xl bg-cyan-600 px-4 py-3 text-left text-sm font-black text-white transition hover:bg-cyan-500">Live video boshqaruvi</button><button type="button" onClick={() => onNavigate("speaking-topics")} className="rounded-xl border border-line px-4 py-3 text-left text-sm font-black text-ink-700 transition hover:bg-surface-soft dark:border-white/15 dark:text-slate-200 dark:hover:bg-white/10">Mavzu va savollar</button><button type="button" onClick={() => onNavigate("speaking-users")} className="rounded-xl border border-line px-4 py-3 text-left text-sm font-black text-ink-700 transition hover:bg-surface-soft dark:border-white/15 dark:text-slate-200 dark:hover:bg-white/10">Speaking foydalanuvchilari</button><button type="button" onClick={() => void load()} className="rounded-xl border border-line px-4 py-3 text-left text-sm font-black text-ink-700 transition hover:bg-surface-soft dark:border-white/15 dark:text-slate-200 dark:hover:bg-white/10">Shaxsiy ma’lumotlarni yangilash</button></div></article>
      </div>
    </section>
  );
}

export function SpeakingAdminHome(props: Omit<SpeakingAdminPersonalProps, "profileMode">) {
  return <SpeakingAdminPersonalPanel {...props} />;
}

export function SpeakingAdminProfile(props: Omit<SpeakingAdminPersonalProps, "profileMode">) {
  return <SpeakingAdminPersonalPanel {...props} profileMode />;
}
