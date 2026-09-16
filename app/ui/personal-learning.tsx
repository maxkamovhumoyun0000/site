"use client";

import { FormEvent, useEffect, useState } from "react";

type Row = Record<string, any>;

export function PersonalLearningPanel({ apiFetch, role }: { apiFetch: (path: string, options?: any) => Promise<any>; role: "student" | "teacher" | "support" }) {
  const student = role === "student";
  const prefix = student ? "/student" : "/staff";
  const [plan, setPlan] = useState<Row | null>(null);
  const [mistakes, setMistakes] = useState<Row[]>([]);
  const [bookmarks, setBookmarks] = useState<Row[]>([]);
  const [summary, setSummary] = useState<Row>({ week_seconds: 0, sessions: 0 });
  const [reminders, setReminders] = useState<Row>({ enabled: true, quiet_start: "", quiet_end: "" });
  const [insights, setInsights] = useState<Row[]>([]);
  const [roomCode, setRoomCode] = useState("");
  const [room, setRoom] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const load = async () => {
    try {
      const requests: Promise<any>[] = [apiFetch(`${prefix}/bookmarks`), apiFetch(`${prefix}/pomodoro/summary`), apiFetch(`${prefix}/reminder-preferences`)];
      if (student) requests.push(apiFetch("/student/personal-plan"), apiFetch("/student/mistake-notebook"));
      else requests.push(apiFetch("/teacher/student-insights"));
      const response = await Promise.all(requests);
      setBookmarks(response[0]?.items || []); setSummary(response[1] || {}); setReminders(response[2] || {});
      if (student) { setPlan(response[3] || null); setMistakes(response[4]?.items || []); }
      else setInsights(response[3]?.items || []);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Ma’lumot yuklanmadi"); }
  };
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const savePomodoro = async (mode: "work" | "short_break" | "long_break", seconds: number) => {
    setBusy(true); try { await apiFetch(`${prefix}/pomodoro/sessions`, { method: "POST", body: { mode, planned_seconds: seconds, completed_seconds: seconds, completed: true } }); setNotice("Pomodoro sessiyasi saqlandi"); await load(); } catch (error) { setNotice(error instanceof Error ? error.message : "Saqlanmadi"); } finally { setBusy(false); }
  };
  const saveReminders = async () => { setBusy(true); try { await apiFetch(`${prefix}/reminder-preferences`, { method: "PUT", body: { enabled: Boolean(reminders.enabled), quiet_start: reminders.quiet_start || null, quiet_end: reminders.quiet_end || null, settings: { channels: ["push", "telegram", "in_app"] } } }); setNotice("Reminder sozlamalari saqlandi"); } catch (error) { setNotice(error instanceof Error ? error.message : "Saqlanmadi"); } finally { setBusy(false); } };
  const createRoom = async () => { setBusy(true); try { const created = await apiFetch("/student/study-rooms", { method: "POST", body: { title: "Study-room" } }); setRoom(created); setNotice(`Xona kodi: ${created.room_code}`); } catch (error) { setNotice(error instanceof Error ? error.message : "Xona yaratilmagan"); } finally { setBusy(false); } };
  const joinRoom = async (event: FormEvent) => { event.preventDefault(); if (!roomCode.trim()) return; setBusy(true); try { const joined = await apiFetch(`/student/study-rooms/join/${encodeURIComponent(roomCode.trim())}`, { method: "POST" }); setRoom(joined.room || joined); setNotice("Study-roomga kirdingiz"); } catch (error) { setNotice(error instanceof Error ? error.message : "Xonaga kirib bo‘lmadi"); } finally { setBusy(false); } };

  return <div className="flex flex-col gap-5 pb-10 animate-fade-in">
    <section className="relative overflow-hidden rounded-3xl border border-cyan-500/20 bg-gradient-to-br from-navy-950 to-indigo-800 p-5 text-white shadow-premium sm:p-7"><div className="absolute -right-16 -top-16 h-48 w-48 rounded-full bg-cyan-400/20 blur-3xl" /><p className="relative text-xs font-black uppercase tracking-[.18em] text-cyan-200">Diamondvoy · {student ? "Personal learning" : "Ish vositalari"}</p><h2 className="relative mt-2 text-2xl font-black">{student ? "Siz uchun bugungi o‘quv reja" : "Diqqat va boshqaruv markazi"}</h2><p className="relative mt-2 max-w-2xl text-sm text-white/75">{student ? String(plan?.summary || "Rejangiz shakllanmoqda.") : "Pomodoro, eslatmalar, saqlangan materiallar va student insightlari."}</p></section>
    {notice ? <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-sm font-semibold text-cyan-800 dark:text-cyan-100">{notice}</div> : null}
    {student ? <section className="grid gap-4 lg:grid-cols-2"><article className="premium-card"><h3 className="text-lg font-black">Bugungi vazifalar</h3><div className="mt-4 space-y-2">{(plan?.tasks || []).length ? plan?.tasks.map((task: Row) => <a key={task.id} href={task.target_url || "#"} className="block rounded-xl border border-line p-3 text-sm font-bold transition hover:border-cyan-400 dark:border-white/10">{task.title}</a>) : <p className="text-sm text-ink-500 dark:text-navy-300">Bugun uchun vazifa yo‘q.</p>}</div></article><article className="premium-card"><div className="flex items-center justify-between gap-3"><h3 className="text-lg font-black">Xatolar daftari</h3><span className="rounded-full bg-rose-500/10 px-2 py-1 text-xs font-black text-rose-600">{mistakes.length}</span></div><div className="mt-4 space-y-2">{mistakes.slice(0, 4).map((item) => <div key={item.id} className="rounded-xl border border-line p-3 text-sm dark:border-white/10"><strong>{item.topic_key || item.subject || "Mashq"}</strong><p className="mt-1 line-clamp-2 text-ink-500 dark:text-navy-300">{item.prompt}</p></div>)}{!mistakes.length ? <p className="text-sm text-ink-500 dark:text-navy-300">Qayta ishlanadigan xato yo‘q.</p> : null}</div></article></section> : <section className="premium-card"><h3 className="text-lg font-black">Studentlar qiynalayotgan mavzular</h3><div className="mt-4 grid gap-2 sm:grid-cols-2">{insights.slice(0, 10).map((item, index) => <div key={`${item.user_id}-${index}`} className="rounded-xl border border-line p-3 text-sm dark:border-white/10"><strong>{item.first_name || item.login_id}</strong><p className="text-ink-500 dark:text-navy-300">{item.subject || "Fan"} · {item.topic_key || "Mavzu"} · {item.mistakes || 0} xato</p></div>)}{!insights.length ? <p className="text-sm text-ink-500">Hozircha xato insightlari yo‘q.</p> : null}</div></section>}
    <section className="grid gap-4 lg:grid-cols-3"><article className="premium-card"><h3 className="text-lg font-black">Pomodoro</h3><p className="mt-1 text-sm text-ink-500 dark:text-navy-300">Haftada {Math.round(Number(summary.week_seconds || 0) / 60)} daqiqa · {summary.sessions || 0} sessiya</p><div className="mt-4 grid grid-cols-3 gap-2"><button disabled={busy} onClick={() => savePomodoro("work", 25 * 60)} className="btn btn-primary text-xs">25 min</button><button disabled={busy} onClick={() => savePomodoro("short_break", 5 * 60)} className="btn btn-soft text-xs">5 min</button><button disabled={busy} onClick={() => savePomodoro("long_break", 15 * 60)} className="btn btn-soft text-xs">15 min</button></div></article><article className="premium-card"><h3 className="text-lg font-black">Smart reminder</h3><label className="mt-3 flex items-center gap-2 text-sm font-semibold"><input type="checkbox" checked={Boolean(reminders.enabled)} onChange={(e) => setReminders({ ...reminders, enabled: e.target.checked })} /> Push, Telegram va ilova ichida</label><div className="mt-3 flex gap-2"><input className="min-w-0 rounded-lg border border-line bg-transparent px-2 py-1 text-sm dark:border-white/10" type="time" value={reminders.quiet_start || ""} onChange={(e) => setReminders({ ...reminders, quiet_start: e.target.value })} /><input className="min-w-0 rounded-lg border border-line bg-transparent px-2 py-1 text-sm dark:border-white/10" type="time" value={reminders.quiet_end || ""} onChange={(e) => setReminders({ ...reminders, quiet_end: e.target.value })} /></div><button disabled={busy} onClick={saveReminders} className="btn btn-soft mt-3 text-xs">Saqlash</button></article><article className="premium-card"><h3 className="text-lg font-black">Saqlanganlar</h3><div className="mt-3 max-h-32 space-y-2 overflow-auto">{bookmarks.map((item) => <div key={item.id} className="rounded-lg bg-surface-soft px-3 py-2 text-sm dark:bg-white/5">{item.title || item.content_type} {item.position_value ? `· ${item.position_value}` : ""}</div>)}{!bookmarks.length ? <p className="text-sm text-ink-500">Bookmark yo‘q.</p> : null}</div></article></section>
    {student ? <section className="premium-card"><h3 className="text-lg font-black">Study-room</h3><p className="mt-1 text-sm text-ink-500 dark:text-navy-300">4 kishigacha do‘stlaringiz bilan chat, material va birgalikdagi mashq.</p><div className="mt-4 flex flex-wrap gap-2"><button disabled={busy} onClick={createRoom} className="btn btn-primary">Xona yaratish</button><form onSubmit={joinRoom} className="flex gap-2"><input value={roomCode} maxLength={6} onChange={(e) => setRoomCode(e.target.value.replace(/\D/g, ""))} className="w-28 rounded-xl border border-line bg-transparent px-3 text-sm dark:border-white/10" placeholder="6 xonali kod" /><button disabled={busy} className="btn btn-soft">Kirish</button></form></div>{room ? <div className="mt-3 rounded-xl border border-cyan-500/20 bg-cyan-500/10 p-3 text-sm font-bold">{room.title || "Study-room"} · kod: {room.room_code || roomCode} · maksimum 4 student</div> : null}</section> : null}
  </div>;
}
