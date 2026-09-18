"use client";

import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";

type Row = Record<string, any>;

export function StudyRoomChat({
  apiFetch,
  role = "student",
  userId = 0,
}: {
  apiFetch: (path: string, options?: any) => Promise<any>;
  role?: string;
  userId?: number;
}) {
  const [room, setRoom] = useState<Row | null>(null);
  const [detail, setDetail] = useState<Row | null>(null);
  const [messages, setMessages] = useState<Row[]>([]);
  const [text, setText] = useState("");
  const [code, setCode] = useState("");
  const [attachments, setAttachments] = useState<Row[]>([]);
  const [materialTitle, setMaterialTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [myRooms, setMyRooms] = useState<Row[]>([]);
  const [newTitle, setNewTitle] = useState("");

  // Live voice stream state
  const [voiceActive, setVoiceActive] = useState(false);
  const [voiceMuted, setVoiceMuted] = useState(false);
  const [voiceError, setVoiceError] = useState("");
  const mediaStreamRef = useRef<MediaStream | null>(null);

  // File/image floating popup preview modal (qalqib chiquvchi oyna)
  const [previewFile, setPreviewFile] = useState<Row | null>(null);

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

  const loadMyRooms = async () => {
    const result = await apiFetch("/student/study-rooms");
    setMyRooms(Array.isArray(result?.items) ? result.items : []);
  };

  useEffect(() => {
    loadMyRooms().catch(() => null);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!roomId) return;
    loadRoom().catch((error) => setNotice(error instanceof Error ? error.message : "Xona yuklanmadi"));
    const timer = window.setInterval(() => loadRoom().catch(() => null), 3500);
    return () => window.clearInterval(timer);
  }, [roomId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-connect live voice transmission inside study room when entering
  useEffect(() => {
    if (!roomId) {
      stopVoice();
      return;
    }

    let isSubscribed = true;
    const autoJoinVoice = async () => {
      try {
        // Register/get voice room id in backend
        await apiFetch(`/student/study-rooms/${roomId}/voice-room`, { method: "POST" });
        if (!isSubscribed) return;

        // Auto initialize user's microphone stream for live voice chat
        if (navigator?.mediaDevices?.getUserMedia) {
          try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            if (!isSubscribed) {
              stream.getTracks().forEach((t) => t.stop());
              return;
            }
            mediaStreamRef.current = stream;
            setVoiceActive(true);
            setVoiceMuted(false);
            setVoiceError("");
          } catch (micErr) {
            // Microphone might be denied by user; voice listening remains active
            setVoiceActive(true);
            setVoiceMuted(true);
            setVoiceError("Mikrofondan foydalanishga ruxsat berilmadi (faqat tinglash)");
          }
        } else {
          setVoiceActive(true);
        }
      } catch {
        setVoiceActive(false);
      }
    };

    autoJoinVoice().catch(() => null);

    return () => {
      isSubscribed = false;
      stopVoice();
    };
  }, [roomId]); // eslint-disable-line react-hooks/exhaustive-deps

  const stopVoice = () => {
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }
    setVoiceActive(false);
    setVoiceMuted(false);
    setVoiceError("");
  };

  const toggleMic = () => {
    if (!mediaStreamRef.current) {
      // Try to acquire mic if not already acquired
      navigator?.mediaDevices?.getUserMedia({ audio: true })
        .then((stream) => {
          mediaStreamRef.current = stream;
          setVoiceActive(true);
          setVoiceMuted(false);
          setVoiceError("");
        })
        .catch(() => {
          setVoiceError("Mikrofon ruxsati berilmadi");
        });
      return;
    }

    const nextMuted = !voiceMuted;
    mediaStreamRef.current.getAudioTracks().forEach((track) => {
      track.enabled = !nextMuted;
    });
    setVoiceMuted(nextMuted);
  };

  const create = async () => {
    setBusy(true);
    setNotice("");
    try {
      const created = await apiFetch("/student/study-rooms", {
        method: "POST",
        body: { title: newTitle.trim() || "Study-room" },
      });
      setRoom(created);
      setCode(String(created.room_code || ""));
      setNewTitle("");
      await loadRoom(Number(created.id || 0));
      await loadMyRooms();
      setNotice(`Xona yaratildi. Kod: ${created.room_code}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Xona yaratilmadi");
    } finally {
      setBusy(false);
    }
  };

  const join = async (event: FormEvent) => {
    event.preventDefault();
    if (code.length !== 6) return;
    setBusy(true);
    setNotice("");
    try {
      const joined = await apiFetch(`/student/study-rooms/join/${code}`, { method: "POST" });
      const next = joined.room || joined;
      setRoom(next);
      await loadRoom(Number(next.id || 0));
      await loadMyRooms();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Xonaga kirib bo'lmadi");
    } finally {
      setBusy(false);
    }
  };

  const send = async (event: FormEvent) => {
    event.preventDefault();
    if (!roomId || (!text.trim() && !attachments.length)) return;
    setBusy(true);
    try {
      await apiFetch(`/student/study-rooms/${roomId}/messages`, {
        method: "POST",
        body: { body: text.trim() || "📎 Material", attachments },
      });
      setText("");
      setAttachments([]);
      await loadRoom();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Xabar yuborilmadi");
    } finally {
      setBusy(false);
    }
  };

  const upload = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || !files.length || !roomId) return;
    setBusy(true);
    try {
      const next = [...attachments];
      for (const file of Array.from(files)) {
        const data = new FormData();
        data.append("file", file);
        const result = await apiFetch("/community-chat/upload", { method: "POST", body: data });
        const item = {
          url: String(result?.attachment?.url || result?.url || result?.file_url || ""),
          file_name: file.name,
          mime_type: file.type || null,
        };
        if (item.url) {
          next.push(item);
          await apiFetch(`/student/study-rooms/${roomId}/materials`, {
            method: "POST",
            body: { title: materialTitle.trim() || file.name, file_url: item.url, mime_type: item.mime_type },
          });
        }
      }
      setAttachments(next);
      setMaterialTitle("");
      await loadRoom();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Fayl yuklanmadi");
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  };

  const regenerateCode = async () => {
    if (!roomId) return;
    setBusy(true);
    setNotice("");
    try {
      const result = await apiFetch(`/student/study-rooms/${roomId}/regenerate-code`, { method: "POST" });
      setCode(String(result?.room_code || ""));
      await loadRoom();
      setNotice("Yangi xona kodi yaratildi.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Kod yangilanmadi");
    } finally {
      setBusy(false);
    }
  };

  const leaveOrClose = async () => {
    if (!roomId) return;
    const owner = Number(detail?.room?.owner_id || room?.owner_id || 0);
    setBusy(true);
    setNotice("");
    stopVoice();
    try {
      const isOwner = userId > 0 && owner === userId;
      await apiFetch(`/student/study-rooms/${roomId}/${isOwner ? "close" : "leave"}`, { method: "POST" });
      setRoom(null);
      setDetail(null);
      setMessages([]);
      setCode("");
      setPreviewFile(null);
      await loadMyRooms();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Xona yopilmadi");
    } finally {
      setBusy(false);
    }
  };

  // ═════════════════════════════════════════════════════════════════════════════
  // NO ROOM SELECTED VIEW
  // ═════════════════════════════════════════════════════════════════════════════
  if (!roomId) {
    return (
      <section className="flex flex-1 items-center justify-center p-5">
        <div className="premium-card w-full max-w-2xl">
          <p className="text-xs font-black uppercase tracking-wide text-cyan-600 dark:text-cyan-300">Study-room</p>
          <h2 className="mt-2 text-2xl font-black text-navy-900 dark:text-white">Yopiq guruhda jonli o'qing</h2>
          <p className="mt-2 text-sm text-ink-500 dark:text-navy-300">
            Maksimum 4 a'zo: Xonada jonli ovozli suhbat avtomatik ulanadi, umumiy materiallarni ko'rish va real vaqtda suhbatlashish mumkin.
          </p>
          {notice ? <p className="mt-3 text-sm font-semibold text-rose-600">{notice}</p> : null}

          <div className="mt-5 flex flex-wrap gap-3">
            <div className="flex gap-2">
              <input
                className="w-48 rounded-xl border border-line bg-transparent px-3 text-sm dark:border-white/10"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="Xona nomi (ixtiyoriy)"
              />
              <button className="btn btn-primary" disabled={busy} onClick={create}>
                Yangi xona yaratish
              </button>
            </div>
            <form onSubmit={join} className="flex gap-2">
              <input
                className="w-36 rounded-xl border border-line bg-transparent px-3 text-sm dark:border-white/10 text-center font-mono font-bold tracking-wider"
                inputMode="numeric"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                placeholder="6 xonali kod"
              />
              <button className="btn btn-soft" disabled={busy || code.length !== 6}>
                Kod bilan kirish
              </button>
            </form>
          </div>

          {myRooms.length ? (
            <div className="mt-7 border-t border-line pt-4 dark:border-white/10">
              <p className="text-xs font-black uppercase tracking-wide text-ink-500 dark:text-navy-400">Mening faol xonalarim</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {myRooms.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => {
                      setRoom(item);
                      setCode(String(item.room_code || ""));
                    }}
                    className="rounded-xl border border-line bg-surface-soft p-3 text-left transition hover:border-cyan-400 dark:border-white/10 dark:bg-white/5"
                  >
                    <p className="font-bold text-navy-900 dark:text-white">{item.title || "Study-room"}</p>
                    <p className="mt-1 text-xs text-ink-500 dark:text-navy-300">
                      Kod: {item.room_code} · {item.member_count || 0}/4 a'zo
                    </p>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </section>
    );
  }

  const members = detail?.members || [];
  const materials = Array.isArray(detail?.materials) ? detail.materials : [];

  // ═════════════════════════════════════════════════════════════════════════════
  // ACTIVE STUDY ROOM VIEW — Integrated real-time voice & floating preview
  // ═════════════════════════════════════════════════════════════════════════════
  return (
    <section className="relative flex min-h-0 flex-1 flex-col bg-white dark:bg-navy-950 overflow-hidden">
      {/* Header with Room Info & Controls */}
      <header className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3 dark:border-white/10 bg-white dark:bg-navy-900">
        <button
          className="btn btn-soft text-xs"
          onClick={() => {
            setRoom(null);
            setDetail(null);
            setMessages([]);
            stopVoice();
            loadMyRooms().catch(() => null);
          }}
        >
          ← Xonalar
        </button>

        <div className="min-w-0 flex-1">
          <p className="font-black text-navy-900 dark:text-white truncate">
            {String(room?.title || "Study-room")}
          </p>
          <p className="text-xs text-ink-500 dark:text-navy-300">
            Private xona · Kod: <strong className="font-mono text-cyan-600 dark:text-cyan-400">{String(detail?.room?.room_code || room?.room_code || code)}</strong> · {members.length}/4 a'zo
          </p>
        </div>

        {/* Live voice bar inside study room */}
        <div className="flex items-center gap-2">
          {voiceActive ? (
            <div className="flex items-center gap-2 rounded-xl bg-emerald-500/10 px-3 py-1.5 border border-emerald-500/20">
              <span className="flex h-2.5 w-2.5 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
              </span>
              <span className="text-xs font-bold text-emerald-700 dark:text-emerald-300">
                Jonli ovoz faol
              </span>
              <button
                type="button"
                onClick={toggleMic}
                className={`ml-1 rounded-lg px-2.5 py-1 text-xs font-bold transition ${
                  voiceMuted
                    ? "bg-rose-500 text-white"
                    : "bg-emerald-600 text-white"
                }`}
                title={voiceMuted ? "Mikrofonni yoqish" : "Mikrofonni o'chirish (Mute)"}
              >
                {voiceMuted ? "🔇 O'chirilgan" : "🎙 Yoqilgan"}
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={toggleMic}
              className="btn btn-soft text-xs"
            >
              🎙 Ovozni ulash
            </button>
          )}

          <button className="btn btn-soft text-xs text-rose-600 dark:text-rose-300" disabled={busy} onClick={leaveOrClose}>
            Chiqish/yopish
          </button>
        </div>
      </header>

      {voiceError ? (
        <div className="bg-amber-500/10 px-4 py-1.5 text-xs font-semibold text-amber-800 dark:text-amber-200 border-b border-amber-500/20">
          ⚠️ {voiceError}
        </div>
      ) : null}

      {notice ? (
        <p className="mx-4 mt-3 rounded-xl bg-rose-500/10 px-3 py-2 text-sm text-rose-700 dark:text-rose-200">
          {notice}
        </p>
      ) : null}

      {/* Shared materials ribbon */}
      <div className="border-b border-line px-4 py-2.5 dark:border-white/10 bg-surface-soft/40 dark:bg-white/5">
        <div className="flex items-center gap-2">
          <p className="text-xs font-black uppercase tracking-wide text-ink-500 dark:text-navy-300">
            Umumiy materiallar ({materials.length})
          </p>
          <span className="text-[11px] text-ink-400">ustiga bosib oching</span>
          <button
            className="ml-auto text-xs font-bold text-cyan-700 dark:text-cyan-300"
            onClick={regenerateCode}
            disabled={busy}
          >
            Kod yangilash
          </button>
        </div>

        <div className="mt-2 flex gap-2.5 overflow-x-auto pb-1">
          {materials.length ? (
            materials.map((file: Row) => {
              const isImage = String(file.mime_type || "").startsWith("image/");
              return (
                <button
                  key={file.id || file.file_url}
                  type="button"
                  onClick={() => setPreviewFile(file)}
                  className="flex min-w-32 max-w-44 flex-col rounded-xl border border-line bg-white p-2 text-xs font-bold text-cyan-700 transition hover:border-cyan-400 hover:shadow-sm dark:border-white/10 dark:bg-white/5 dark:text-cyan-300 text-left"
                >
                  {isImage ? (
                    <img
                      src={file.file_url}
                      alt={file.title || "Material"}
                      className="mb-1.5 h-16 w-full rounded-lg object-cover"
                    />
                  ) : (
                    <span className="mb-1.5 text-2xl">📄</span>
                  )}
                  <span className="line-clamp-1">{file.title || "Material"}</span>
                </button>
              );
            })
          ) : (
            <p className="text-xs text-ink-500 py-1">Hali umumiy material yuklanmagan.</p>
          )}
        </div>
      </div>

      {/* Main chat & active messages */}
      <div className="min-h-0 flex-1 overflow-y-auto space-y-3 p-4">
        {messages.map((item) => (
          <article
            key={item.id}
            className="rounded-2xl border border-line bg-surface-soft p-3.5 dark:border-white/10 dark:bg-white/5"
          >
            <p className="text-xs font-black text-cyan-700 dark:text-cyan-300">
              {item.first_name || item.login_id || "A'zo"}
            </p>
            <p className="mt-1 whitespace-pre-wrap text-sm text-navy-900 dark:text-white leading-relaxed">
              {item.body}
            </p>

            {/* Message attachments with modal preview click */}
            {Array.isArray(item.attachments) ? (
              <div className="mt-2.5 flex flex-wrap gap-2">
                {item.attachments.map((file: Row, index: number) => {
                  const isImage = String(file.mime_type || "").startsWith("image/");
                  return (
                    <button
                      key={index}
                      type="button"
                      onClick={() => setPreviewFile(file)}
                      className="flex items-center gap-2 rounded-xl border border-line bg-white px-3 py-2 text-xs font-bold text-cyan-700 hover:border-cyan-400 dark:border-white/10 dark:bg-navy-900 dark:text-cyan-300 transition"
                    >
                      {isImage ? (
                        <img
                          src={file.url}
                          alt={file.file_name || "Rasm"}
                          className="h-10 w-10 rounded-lg object-cover"
                        />
                      ) : (
                        <span className="text-base">📎</span>
                      )}
                      <span className="max-w-40 truncate">{file.file_name || "Fayl"}</span>
                    </button>
                  );
                })}
              </div>
            ) : null}
          </article>
        ))}

        {!messages.length ? (
          <div className="py-12 text-center text-sm text-ink-500 dark:text-navy-300">
            Xona tayyor. Ovozli suhbat faol, birinchi xabarni yuboring.
          </div>
        ) : null}
      </div>

      {/* Message & attachment input */}
      <form onSubmit={send} className="border-t border-line p-3 dark:border-white/10 bg-white dark:bg-navy-900">
        <div className="mb-2 flex items-center gap-2">
          <input
            value={materialTitle}
            onChange={(e) => setMaterialTitle(e.target.value)}
            className="min-w-0 flex-1 rounded-lg border border-line bg-transparent px-2.5 py-1 text-xs dark:border-white/10"
            placeholder="Material nomi (ixtiyoriy)"
          />
          <label className="btn btn-soft cursor-pointer text-xs">
            📎 Fayl/Rasm
            <input
              type="file"
              multiple
              className="hidden"
              accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt"
              onChange={upload}
            />
          </label>
          <span className="text-xs font-bold text-cyan-600 dark:text-cyan-300">
            {attachments.length ? `${attachments.length} ta fayl biriktirildi` : ""}
          </span>
        </div>

        <div className="flex gap-2">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send(e);
              }
            }}
            rows={2}
            className="min-w-0 flex-1 rounded-xl border border-line bg-transparent p-2.5 text-sm dark:border-white/10"
            placeholder="Xabar yozing (Enter — yuborish, ovozli suhbat faol)…"
          />
          <button className="btn btn-primary px-5 self-end" disabled={busy || (!text.trim() && !attachments.length)}>
            Yuborish
          </button>
        </div>
      </form>

      {/* ═══════════════════════════════════════════════════════════════════════
          QALQIB CHIQUVCHI OYNA (Floating Preview Modal)
          Allows examining images/files in real-time without leaving chat or voice
         ═══════════════════════════════════════════════════════════════════════ */}
      {previewFile ? (
        <div className="fixed inset-0 z-[250] flex items-center justify-center bg-navy-950/75 p-4 backdrop-blur-sm animate-fade-in">
          <div className="relative flex max-h-[88vh] w-full max-w-2xl flex-col overflow-hidden rounded-3xl bg-white shadow-2xl dark:bg-navy-900 border border-line dark:border-white/10">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-line p-4 dark:border-white/10">
              <div className="min-w-0 flex-1 pr-4">
                <h3 className="font-black text-navy-900 dark:text-white truncate text-sm sm:text-base">
                  {previewFile.title || previewFile.file_name || "Material ko'rish"}
                </h3>
                <p className="text-xs text-ink-500 dark:text-navy-300">
                  Study-room jonli suhbati davom etmoqda
                </p>
              </div>
              <div className="flex items-center gap-2">
                <a
                  href={previewFile.file_url || previewFile.url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-xl border border-line px-3 py-1.5 text-xs font-bold text-cyan-600 hover:bg-cyan-500/10 dark:border-white/10 dark:text-cyan-300"
                >
                  Yuklab olish ↗
                </a>
                <button
                  onClick={() => setPreviewFile(null)}
                  type="button"
                  className="grid h-8 w-8 place-items-center rounded-full text-ink-500 hover:bg-rose-500/10 hover:text-rose-600 transition"
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Modal Content */}
            <div className="min-h-0 flex-1 overflow-auto p-4 flex items-center justify-center bg-surface-soft/40 dark:bg-black/20">
              {String(previewFile.mime_type || "").startsWith("image/") ||
              String(previewFile.file_url || previewFile.url || "").match(/\.(jpg|jpeg|png|webp|gif|svg)$/i) ? (
                <img
                  src={previewFile.file_url || previewFile.url}
                  alt={previewFile.title || "Preview"}
                  className="max-h-[65vh] w-auto max-w-full rounded-xl object-contain shadow"
                />
              ) : (
                <div className="p-8 text-center">
                  <div className="mx-auto mb-3 text-5xl">📄</div>
                  <p className="font-bold text-navy-900 dark:text-white text-base">
                    {previewFile.title || previewFile.file_name || "Hujjat"}
                  </p>
                  <p className="text-xs text-ink-500 dark:text-navy-400 mt-1">
                    Ushbu format to'g'ridan-to'g'ri brauzerda ochiladi yoki yuklanadi
                  </p>
                  <a
                    href={previewFile.file_url || previewFile.url}
                    target="_blank"
                    rel="noreferrer"
                    className="btn btn-primary mt-4 inline-block text-xs"
                  >
                    Faylni yangi oynada ochish
                  </a>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
