"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";

type Row = Record<string, any>;

export function StudyRoomChat({ apiFetch }: { apiFetch: (path: string, options?: any) => Promise<any> }) {
  const [code, setCode] = useState("");
  const [room, setRoom] = useState<Row | null>(null);
  const [detail, setDetail] = useState<Row | null>(null);
  const [messages, setMessages] = useState<Row[]>([]);
  const [text, setText] = useState("");
  const [materialTitle, setMaterialTitle] = useState("");
  const [attachments, setAttachments] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const roomId = Number(room?.id || detail?.room?.id || 0);

  const loadRoom = async (id = roomId) => {
    if (!id) return;
    const [nextDetail, nextMessages] = await Promise.all([
      apiFetch(`/student/study-rooms/${id}`),
      apiFetch(`/student/study-rooms/${id}/messages`),
    ]);
    setDetail(nextDetail || null);
    setRoom(nextDetail?.room || room);
    setMessages(nextMessages?.items || []);
  };

  useEffect(() => {
    if (!roomId) return;
    loadRoom().catch((error) => setNotice(error instanceof Error ? error.message : "Xona yuklanmadi"));
    const timer = window.setInterval(() => loadRoom().catch(() => null), 4000);
    return () => window.clearInterval(timer);
  }, [roomId]); // eslint-disable-line react-hooks/exhaustive-deps

  const create = async () => {
    setBusy(true); setNotice("");
    try {
      const created = await apiFetch("/student/study-rooms", { method: "POST", body: { title: "Study-room" } });
      setRoom(created); setCode(String(created.room_code || "")); await loadRoom(Number(created.id || 0));
      setNotice(`Xona yaratildi. Kod: ${created.room_code}`);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Xona yaratilmadi"); } finally { setBusy(false); }
  };

  const join = async (event: FormEvent) => {
    event.preventDefault(); if (code.length !== 6) return;
    setBusy(true); setNotice("");
    try {
      const joined = await apiFetch(`/student/study-rooms/join/${code}`, { method: "POST" });
      const next = joined.room || joined; setRoom(next); await loadRoom(Number(next.id || 0));
    } catch (error) { setNotice(error instanceof Error ? error.message : "Xonaga kirib bo‘lmadi"); } finally { setBusy(false); }
  };

  const send = async (event: FormEvent) => {
    event.preventDefault(); if (!roomId || (!text.trim() && !attachments.length)) return;
    setBusy(true);
    try {
      await apiFetch(`/student/study-rooms/${roomId}/messages`, { method: "POST", body: { body: text.trim() || "📎 Material", attachments } });
      setText(""); setAttachments([]); await loadRoom();
    } catch (error) { setNotice(error instanceof Error ? error.message : "Xabar yuborilmadi"); } finally { setBusy(false); }
  };

  const upload = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []).slice(0, Math.max(0, 5 - attachments.length));
    if (!files.length || !roomId) return;
    setBusy(true);
    try {
      const next: Row[] = [];
      for (const file of files) {
        const form = new FormData(); form.append("file", file);
        const result = await apiFetch("/community-chat/upload", { method: "POST", body: form });
        const item = { url: String(result?.url || result?.file_url || ""), file_name: file.name, mime_type: file.type || null };
        if (!item.url) continue;
        next.push(item);
        await apiFetch(`/student/study-rooms/${roomId}/materials`, { method: "POST", body: { title: materialTitle.trim() || file.name, file_url: item.url, mime_type: item.mime_type } });
      }
      setAttachments((current) => [...current, ...next].slice(0, 5));
      setMaterialTitle(""); await loadRoom();
    } catch (error) { setNotice(error instanceof Error ? error.message : "Fayl yuklanmadi"); } finally { setBusy(false); event.target.value = ""; }
  };

  const openVoice = async () => {
    if (!roomId) return;
    setBusy(true);
    try {
      const result = await apiFetch(`/student/study-rooms/${roomId}/voice-room`, { method: "POST" });
      window.location.assign(`/?role=student&section=voice-rooms&room_id=${encodeURIComponent(String(result.room_id || ""))}`);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Voice-room ochilmadi"); } finally { setBusy(false); }
  };

  if (!roomId) return <section className="flex flex-1 items-center justify-center p-5"><div className="premium-card w-full max-w-lg"><p className="text-xs font-black uppercase tracking-wide text-cyan-600">Study-room</p><h2 className="mt-2 text-2xl font-black">Do‘stlar bilan o‘qing</h2><p className="mt-2 text-sm text-ink-500 dark:text-navy-300">4 kishigacha. Xona kodi 6 xonali, chat va materiallar faqat a’zolarga ko‘rinadi.</p>{notice ? <p className="mt-3 text-sm font-semibold text-rose-600">{notice}</p> : null}<div className="mt-5 flex flex-wrap gap-3"><button className="btn btn-primary" disabled={busy} onClick={create}>Xona yaratish</button><form onSubmit={join} className="flex gap-2"><input className="w-32 rounded-xl border border-line bg-transparent px-3 text-sm dark:border-white/10" inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} placeholder="6 xonali kod" /><button className="btn btn-soft" disabled={busy || code.length !== 6}>Kirish</button></form></div></div></section>;

  const members = detail?.members || [];
  return <section className="flex min-h-0 flex-1 flex-col bg-white dark:bg-navy-950"><header className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3 dark:border-white/10"><div className="min-w-0 flex-1"><p className="font-black text-navy-900 dark:text-white">{String(room?.title || "Study-room")}</p><p className="text-xs text-ink-500 dark:text-navy-300">Kod: <strong>{String(room?.room_code || code)}</strong> · {members.length}/4 a’zo</p></div><button className="btn btn-soft text-xs" disabled={busy} onClick={openVoice}>🎙 Voice-room</button></header>{notice ? <p className="mx-4 mt-3 rounded-xl bg-rose-500/10 px-3 py-2 text-sm text-rose-700 dark:text-rose-200">{notice}</p> : null}<div className="min-h-0 flex-1 overflow-y-auto space-y-3 p-4">{messages.map((item) => <article key={item.id} className="rounded-2xl border border-line bg-surface-soft p-3 dark:border-white/10 dark:bg-white/5"><p className="text-xs font-black text-cyan-700 dark:text-cyan-300">{item.first_name || item.login_id || "Student"}</p><p className="mt-1 whitespace-pre-wrap text-sm">{item.body}</p>{Array.isArray(item.attachments) ? item.attachments.map((file: Row, index: number) => <a key={index} className="mt-2 block text-xs font-bold text-cyan-700 dark:text-cyan-300" href={file.url} target="_blank" rel="noreferrer">📎 {file.file_name || "Fayl"}</a>) : null}</article>)}{!messages.length ? <p className="py-10 text-center text-sm text-ink-500">Xona tayyor. Birinchi xabarni yuboring.</p> : null}</div><form onSubmit={send} className="border-t border-line p-3 dark:border-white/10"><div className="mb-2 flex items-center gap-2"><input value={materialTitle} onChange={(e) => setMaterialTitle(e.target.value)} className="min-w-0 flex-1 rounded-lg border border-line bg-transparent px-2 py-1 text-xs dark:border-white/10" placeholder="Material nomi (ixtiyoriy)" /><label className="btn btn-soft cursor-pointer text-xs">📎<input type="file" multiple className="hidden" onChange={upload} /></label><span className="text-xs text-ink-500">{attachments.length ? `${attachments.length} fayl tayyor` : ""}</span></div><div className="flex gap-2"><textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} className="min-w-0 flex-1 rounded-xl border border-line bg-transparent p-2 text-sm dark:border-white/10" placeholder="Guruhga yozing…" /><button className="btn btn-primary" disabled={busy}>Yuborish</button></div></form></section>;
}
