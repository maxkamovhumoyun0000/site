"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useGlobalVoiceRoom } from "./voice-room/GlobalVoiceRoomContext";

type Row = Record<string, any>;

function normalizeMediaUrl(url?: string | null): string {
  if (!url) return "";
  const s = String(url).trim();
  if (s.startsWith("http://") || s.startsWith("https://") || s.startsWith("blob:") || s.startsWith("data:")) {
    return s;
  }
  if (s.startsWith("/")) return s;
  return `/${s}`;
}

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
  const [copiedCode, setCopiedCode] = useState(false);
  const [mobileTab, setMobileTab] = useState<"stage" | "chat">("stage");
  const [reactions, setReactions] = useState<{ id: string; emoji: string }[]>([]);

  const sendReaction = (emoji: string) => {
    const id = `${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    setReactions((prev) => [...prev, { id, emoji }]);
    setTimeout(() => {
      setReactions((prev) => prev.filter((r) => r.id !== id));
    }, 4000);
    if (roomId) {
      void apiFetch(`/student/study-rooms/${roomId}/messages`, {
        method: "POST",
        body: { body: emoji },
      }).catch(() => null);
    }
  };

  const handleCopyCode = async (textToCopy: string) => {
    try {
      await navigator.clipboard.writeText(textToCopy);
      setCopiedCode(true);
      setTimeout(() => setCopiedCode(false), 2000);
    } catch {
      // fallback
    }
  };

  // Live WebRTC voice room integration
  const {
    state: voiceState,
    roomState: voiceRoomState,
    isMuted: voiceMuted,
    speakingPeers,
    joinRoom: joinVoiceRoom,
    leaveRoom: leaveVoiceRoom,
    toggleMute: toggleVoiceMute,
    errorMsg: voiceContextError,
    setErrorMsg: setVoiceContextError,
  } = useGlobalVoiceRoom();

  const [voiceConnecting, setVoiceConnecting] = useState(false);
  const [voiceLocalError, setVoiceLocalError] = useState("");
  const activeVoiceRoomIdRef = useRef<string | null>(null);

  // File/image floating popup preview modal (qalqib chiquvchi oyna)
  const [previewFile, setPreviewFile] = useState<Row | null>(null);

  // Center Document Stage navigation (independent per user: hamma ozi xohlagandek o'tkaza olsin)
  const [activeMaterialIndex, setActiveMaterialIndex] = useState(0);

  // 10-second empty room auto-termination timer
  const [emptyCountdown, setEmptyCountdown] = useState<number | null>(null);
  const emptyTimerRef = useRef<NodeJS.Timeout | null>(null);

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

  // Empty room countdown: if 0 members remain, close after 10 seconds
  useEffect(() => {
    if (!roomId || !detail) return;
    const activeCount = Array.isArray(detail?.members) ? detail.members.length : 0;
    if (activeCount === 0) {
      if (!emptyTimerRef.current) {
        let count = 10;
        setEmptyCountdown(count);
        emptyTimerRef.current = setInterval(() => {
          count -= 1;
          setEmptyCountdown(count);
          if (count <= 0) {
            if (emptyTimerRef.current) clearInterval(emptyTimerRef.current);
            emptyTimerRef.current = null;
            void leaveOrClose();
          }
        }, 1000);
      }
    } else {
      if (emptyTimerRef.current) {
        clearInterval(emptyTimerRef.current);
        emptyTimerRef.current = null;
      }
      setEmptyCountdown(null);
    }
    return () => {
      if (emptyTimerRef.current) {
        clearInterval(emptyTimerRef.current);
        emptyTimerRef.current = null;
      }
    };
  }, [detail?.members, roomId]);

  const joinVoiceCall = useCallback(async () => {
    if (!roomId) return;
    setVoiceConnecting(true);
    setVoiceLocalError("");
    try {
      const res = await apiFetch(`/student/study-rooms/${roomId}/voice-room`, { method: "POST" });
      const voiceId = String(res?.room_id || "");
      if (voiceId) {
        activeVoiceRoomIdRef.current = voiceId;
        joinVoiceRoom(voiceId);
      } else {
        throw new Error("Ovozli xona identifikatori olinmadi");
      }
    } catch (err: any) {
      setVoiceLocalError(err instanceof Error ? err.message : "Ovozli xonaga ulanib bo'lmadi");
    } finally {
      setVoiceConnecting(false);
    }
  }, [roomId, apiFetch, joinVoiceRoom]);

  // Auto-connect live voice transmission inside study room when entering
  useEffect(() => {
    if (!roomId) {
      if (activeVoiceRoomIdRef.current) {
        leaveVoiceRoom();
        activeVoiceRoomIdRef.current = null;
      }
      return;
    }

    let isSubscribed = true;
    const initVoice = async () => {
      setVoiceConnecting(true);
      setVoiceLocalError("");
      try {
        const res = await apiFetch(`/student/study-rooms/${roomId}/voice-room`, { method: "POST" });
        if (!isSubscribed) return;
        const voiceId = String(res?.room_id || "");
        if (voiceId) {
          activeVoiceRoomIdRef.current = voiceId;
          joinVoiceRoom(voiceId);
        }
      } catch (err: any) {
        if (isSubscribed) {
          setVoiceLocalError(err instanceof Error ? err.message : "Ovozli xonaga ulanib bo'lmadi");
        }
      } finally {
        if (isSubscribed) setVoiceConnecting(false);
      }
    };

    initVoice().catch(() => null);

    return () => {
      isSubscribed = false;
      if (activeVoiceRoomIdRef.current) {
        leaveVoiceRoom();
        activeVoiceRoomIdRef.current = null;
      }
    };
  }, [roomId]); // eslint-disable-line react-hooks/exhaustive-deps

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
    const cleanCode = code.trim();
    if (!cleanCode) {
      setNotice("Iltimos, 6 xonali xona kodini kiriting");
      return;
    }
    if (cleanCode.length !== 6 || !/^\d{6}$/.test(cleanCode)) {
      setNotice("Xona kodi aynan 6 ta raqamdan iborat bo'lishi kerak (masalan: 123456)");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const joined = await apiFetch(`/student/study-rooms/join/${cleanCode}`, { method: "POST" });
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
      setActiveMaterialIndex(0);
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
    const isOwner = userId > 0 && owner === userId;
    if (isOwner) {
      if (!window.confirm("Study roomni yopishni tasdiqlaysizmi? Xonaga yuklangan barcha materiallar va fayllar butunlay o'chiriladi.")) {
        return;
      }
    }
    setBusy(true);
    setNotice("");
    if (activeVoiceRoomIdRef.current) {
      leaveVoiceRoom();
      activeVoiceRoomIdRef.current = null;
    }
    try {
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
  // NO ROOM SELECTED VIEW — VOICE ROOM STYLED LOBBY
  // ═════════════════════════════════════════════════════════════════════════════
  if (!roomId) {
    return (
      <section className="flex flex-1 flex-col p-4 sm:p-6 min-h-0 overflow-y-auto">
        <div className="w-full max-w-4xl mx-auto space-y-6 animate-fade-in my-auto">
          {/* Voice Room Header Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-5">
            <div className="flex items-center gap-3.5">
              <div className="grid h-12 w-12 place-items-center rounded-2xl bg-indigo-600 text-2xl text-white shadow-md shadow-indigo-500/20">
                🎧
              </div>
              <div>
                <h1 className="text-2xl sm:text-3xl font-black text-slate-800 dark:text-white tracking-tight">
                  Study Room
                </h1>
                <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-0.5">
                  4 kishilik interaktiv o'quv xonalari · Jonli ovoz, markaziy PDF/Kitob ko'rish va real vaqtda chat
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-indigo-50 dark:bg-indigo-500/10 px-3.5 py-1.5 text-xs font-bold text-indigo-600 dark:text-indigo-400 border border-indigo-200/50 dark:border-indigo-500/20 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>{myRooms.length} ta faol xona</span>
              </span>
            </div>
          </div>

          {/* Notice / Error Feedback */}
          {notice ? (
            <div className="flex items-center justify-between gap-3 rounded-2xl border border-rose-500/30 bg-rose-500/15 p-4 text-xs sm:text-sm font-bold text-rose-700 dark:text-rose-200 shadow-sm animate-shake">
              <div className="flex items-center gap-2.5">
                <span className="text-base">⚠️</span>
                <span>{notice}</span>
              </div>
              <button
                type="button"
                onClick={() => setNotice("")}
                className="grid h-6 w-6 place-items-center rounded-lg hover:bg-rose-500/20 text-rose-600 dark:text-rose-300 font-bold"
              >
                ✕
              </button>
            </div>
          ) : null}

          {/* 2-Column Action Cards in Voice Room Style */}
          <div className="grid gap-5 md:grid-cols-2">
            {/* Card 1: Yangi xona ochish */}
            <div className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm flex flex-col justify-between hover:border-indigo-500/30 transition">
              <div>
                <div className="flex items-center gap-3">
                  <div className="grid h-12 w-12 place-items-center rounded-2xl bg-indigo-50 dark:bg-indigo-500/10 text-2xl text-indigo-600 dark:text-indigo-400">
                    🚀
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-800 dark:text-white text-base">
                      Yangi xona ochish
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      O'zingiz yangi study room oching va kodini do'stlaringizga yuboring
                    </p>
                  </div>
                </div>

                <div className="mt-5">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block mb-1.5">
                    Xona nomi (ixtiyoriy)
                  </label>
                  <input
                    className="w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-4 py-3 text-sm font-medium text-slate-800 dark:text-white placeholder:text-slate-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    placeholder="Masalan: IELTS Reading yoki Matematika"
                  />
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  className="w-full py-3.5 rounded-xl text-sm font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-md shadow-indigo-500/20 transition flex items-center justify-center gap-2"
                  disabled={busy}
                  onClick={create}
                >
                  <span>{busy ? "Ochilmoqda..." : "✨ Yangi xona yaratish"}</span>
                </button>
              </div>
            </div>

            {/* Card 2: Kod bilan kirish */}
            <div className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm flex flex-col justify-between hover:border-indigo-500/30 transition">
              <div>
                <div className="flex items-center gap-3">
                  <div className="grid h-12 w-12 place-items-center rounded-2xl bg-indigo-50 dark:bg-indigo-500/10 text-2xl text-indigo-600 dark:text-indigo-400">
                    🔑
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-800 dark:text-white text-base">
                      Kod bilan kirish
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Do'stingiz bergan 6 xonali PIN-kodni kiritib xonaga qo'shiling
                    </p>
                  </div>
                </div>

                <form onSubmit={join} className="mt-5" id="join-room-form">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block mb-1.5">
                    6 xonali PIN-kod
                  </label>
                  <input
                    className="w-full text-center font-mono font-black text-2xl tracking-[0.35em] rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 py-3 text-slate-800 dark:text-white placeholder:tracking-normal placeholder:font-sans placeholder:text-sm placeholder:text-slate-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition"
                    inputMode="numeric"
                    maxLength={6}
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                    placeholder="000000"
                  />
                </form>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="submit"
                  form="join-room-form"
                  className="w-full py-3.5 rounded-xl text-sm font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-indigo-600 hover:text-white transition flex items-center justify-center gap-2"
                  disabled={busy || code.length !== 6}
                >
                  <span>{busy ? "Tekshirilmoqda..." : "Kirish →"}</span>
                </button>
              </div>
            </div>
          </div>

          {/* Mening faol xonalarim (Voice Room Card Style) */}
          {myRooms.length ? (
            <div className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/80 p-6 shadow-sm">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-4">
                Mening faol study roomlarim ({myRooms.length})
              </p>
              <div className="grid gap-3.5 sm:grid-cols-2">
                {myRooms.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => {
                      setRoom(item);
                      setCode(String(item.room_code || ""));
                    }}
                    className="group flex items-center justify-between rounded-2xl border border-slate-100 dark:border-slate-800 bg-slate-50/70 p-4 text-left transition hover:shadow-md hover:border-indigo-500/30 dark:bg-slate-800/60 cursor-pointer"
                  >
                    <div className="min-w-0 flex-1 pr-3">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="px-2 py-0.5 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded text-[10px] font-bold uppercase tracking-wider">
                          Study Room
                        </span>
                        <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 text-xs font-bold">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                          {item.member_count || 1}/4 a'zo
                        </span>
                      </div>
                      <p className="font-bold text-slate-800 dark:text-white truncate text-sm group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition">
                        {item.title || "Study-room"}
                      </p>
                      <div className="mt-1 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                        <span className="font-mono font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-500/10 px-2 py-0.5 rounded-md">
                          PIN: {item.room_code}
                        </span>
                      </div>
                    </div>
                    <div className="w-10 h-10 rounded-full bg-slate-200/70 dark:bg-slate-700 flex items-center justify-center group-hover:bg-indigo-600 group-hover:text-white transition">
                      <svg className="w-5 h-5 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M8 5v14l11-7z" />
                      </svg>
                    </div>
                  </div>
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
  const safeActiveMaterialIndex = Math.min(Math.max(0, activeMaterialIndex), Math.max(0, materials.length - 1));
  const currentMaterial = materials[safeActiveMaterialIndex] || null;
  const currentMaterialUrl = normalizeMediaUrl(currentMaterial?.file_url || currentMaterial?.url);
  const currentMaterialIsImage =
    Boolean(currentMaterialUrl) && (
      String(currentMaterial?.mime_type || "").startsWith("image/") ||
      /\.(jpg|jpeg|png|webp|gif|svg|bmp)(\?.*)?$/i.test(currentMaterialUrl)
    );
  const currentMaterialIsPdf =
    Boolean(currentMaterialUrl) && (
      String(currentMaterial?.mime_type || "") === "application/pdf" ||
      /\.pdf(\?.*)?$/i.test(currentMaterialUrl)
    );

  const isRoomOwner = userId > 0 && Number(detail?.room?.owner_id || room?.owner_id || 0) === userId;

  // ═════════════════════════════════════════════════════════════════════════════
  // ACTIVE STUDY ROOM VIEW — VOICE ROOM DESIGN SYSTEM
  // ═════════════════════════════════════════════════════════════════════════════
  return (
    <section className="relative flex min-h-0 flex-1 flex-col bg-slate-950 text-white overflow-hidden">
      {/* FLOATING REACTIONS ANIMATION */}
      <div className="pointer-events-none fixed inset-0 z-40 overflow-hidden">
        {reactions.map((r) => {
          const sway = Math.random() * 40 - 20;
          const startRight = 20 + Math.random() * 20;
          return (
            <div
              key={r.id}
              className="absolute text-4xl"
              style={{
                bottom: "80px",
                right: `${startRight}px`,
                animation: `floatBubble 4s ease-out forwards`,
                "--sway": `${sway}px`,
              } as React.CSSProperties}
            >
              {r.emoji}
            </div>
          );
        })}
      </div>
      <style
        dangerouslySetInnerHTML={{
          __html: `
        @keyframes floatBubble {
          0% { transform: translateY(0) translateX(0) scale(0.5); opacity: 0; }
          15% { transform: translateY(-30px) translateX(calc(var(--sway) * 0.3)) scale(1.1); opacity: 1; }
          60% { transform: translateY(-180px) translateX(var(--sway)) scale(1); opacity: 0.7; }
          100% { transform: translateY(-350px) translateX(calc(var(--sway) * -0.5)) scale(0.8); opacity: 0; }
        }
      `,
        }}
      />

      {/* Voice Room Top Header Bar */}
      <header className="z-20 px-4 py-3 bg-slate-900 border-b border-slate-800 flex items-center justify-between gap-3 shadow-sm">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={() => {
              if (activeVoiceRoomIdRef.current) {
                leaveVoiceRoom();
                activeVoiceRoomIdRef.current = null;
              }
              setRoom(null);
              setDetail(null);
              setMessages([]);
              loadMyRooms().catch(() => null);
            }}
            className="w-9 h-9 rounded-full bg-slate-800 text-slate-300 hover:text-white flex items-center justify-center border border-slate-700/70 hover:bg-slate-700 transition"
            title="Orqaga"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="font-bold text-white leading-tight truncate text-sm sm:text-base">
                {String(room?.title || "Study-room")}
              </h1>
              {isRoomOwner ? (
                <span className="rounded-md bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-bold text-amber-300 border border-amber-500/30">
                  👑 Egasi
                </span>
              ) : null}
            </div>
            <div className="flex items-center gap-2 mt-0.5 text-[11px] text-slate-400">
              <span className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>{members.length}/4 a'zo</span>
              </span>
              <span>·</span>
              <button
                type="button"
                onClick={() => handleCopyCode(String(detail?.room?.room_code || room?.room_code || code))}
                className="inline-flex items-center gap-1 font-mono font-bold text-indigo-400 hover:text-indigo-300"
                title="Kodni nusxalash"
              >
                <span>PIN: {String(detail?.room?.room_code || room?.room_code || code)}</span>
                <span>{copiedCode ? "✓" : "📋"}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Live Audio Indicator & Actions */}
        <div className="flex items-center gap-2">
          {voiceState === "room" ? (
            <div className="flex items-center gap-2 rounded-xl bg-emerald-500/10 px-2.5 py-1.5 border border-emerald-500/20">
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="text-[11px] font-bold text-emerald-300 hidden sm:inline">
                {speakingPeers.length > 0 ? "🗣️ Gapirmoqda..." : "Jonli ovoz faol"}
              </span>
              <button
                type="button"
                onClick={toggleVoiceMute}
                className={`rounded-lg px-2 py-1 text-xs font-bold transition ${
                  voiceMuted
                    ? "bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500 hover:text-white"
                    : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500 hover:text-white"
                }`}
                title={voiceMuted ? "Ovozni yoqish" : "Ovozni o'chirish (Mute)"}
              >
                {voiceMuted ? "🔇 Muted" : "🎙 Jonli"}
              </button>
            </div>
          ) : voiceConnecting ? (
            <div className="flex items-center gap-1.5 rounded-xl bg-indigo-500/10 px-2.5 py-1.5 border border-indigo-500/20 text-xs font-semibold text-indigo-300">
              <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent"></span>
              <span className="hidden sm:inline">Ulanmoqda...</span>
            </div>
          ) : (
            <button
              type="button"
              onClick={joinVoiceCall}
              className="rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-3 py-1.5 flex items-center gap-1.5 shadow-sm transition"
            >
              <span>🎙</span>
              <span>Ovozga ulanish</span>
            </button>
          )}

          <button
            className={`rounded-xl px-3 py-1.5 text-xs font-bold transition border ${
              isRoomOwner
                ? "border-red-500/30 bg-red-500/15 text-red-400 hover:bg-red-600 hover:text-white"
                : "border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white"
            }`}
            disabled={busy}
            onClick={leaveOrClose}
            title={isRoomOwner ? "Xonani yopish" : "Xonadan chiqish"}
          >
            {isRoomOwner ? "🔒 Yopish" : "🚪 Chiqish"}
          </button>
        </div>
      </header>

      {/* Auto-termination warning banner */}
      {emptyCountdown !== null ? (
        <div className="bg-red-500/20 border-b border-red-500/30 px-4 py-2 text-center text-xs font-bold text-red-300 animate-pulse">
          ⚠️ Xonada a'zolar qolmadi. Sessiya {emptyCountdown} soniyadan keyin avtomatik yopiladi!
        </div>
      ) : null}

      {(voiceLocalError || voiceContextError) ? (
        <div className="flex items-center justify-between bg-amber-500/20 px-4 py-2 text-xs font-medium text-amber-200 border-b border-amber-500/30">
          <span>⚠️ {voiceLocalError || voiceContextError}</span>
          <button
            type="button"
            onClick={() => {
              setVoiceLocalError("");
              setVoiceContextError("");
            }}
            className="text-amber-300 hover:text-white ml-2"
          >
            ✕
          </button>
        </div>
      ) : null}

      {/* Mobile Tab Switcher (Visible on small screens) */}
      <div className="lg:hidden flex border-b border-slate-800 bg-slate-900/90 px-3 py-2 gap-2 z-10">
        <button
          type="button"
          onClick={() => setMobileTab("stage")}
          className={`flex-1 py-1.5 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 ${
            mobileTab === "stage"
              ? "bg-indigo-600 text-white shadow-sm"
              : "bg-slate-800 text-slate-400 hover:text-slate-200"
          }`}
        >
          <span>📄 Sahna & Hujjat</span>
        </button>
        <button
          type="button"
          onClick={() => setMobileTab("chat")}
          className={`flex-1 py-1.5 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 ${
            mobileTab === "chat"
              ? "bg-indigo-600 text-white shadow-sm"
              : "bg-slate-800 text-slate-400 hover:text-slate-200"
          }`}
        >
          <span>💬 Guruh Chat</span>
          {messages.length > 0 ? (
            <span className="rounded-full bg-black/30 px-1.5 py-0.2 text-[10px]">
              {messages.length}
            </span>
          ) : null}
        </button>
      </div>

      {/* ═════════════════════════════════════════════════════════════════════════
          SPLIT LAYOUT: LEFT (STAGE & DOCUMENT READER) | RIGHT (CHAT & CONTROLS)
          ═════════════════════════════════════════════════════════════════════════ */}
      <div className="flex-1 min-h-0 flex flex-col lg:flex-row overflow-hidden">
        {/* ─── LEFT: VOICE STAGE & DOCUMENT READER ─── */}
        <div
          className={`flex-1 min-h-0 flex flex-col border-b lg:border-b-0 lg:border-r border-slate-800 bg-slate-950 ${
            mobileTab === "stage" ? "flex" : "hidden lg:flex"
          }`}
        >
          {/* Voice Room Stage Area (Avatars with Green Glow Ring) */}
          <div className="border-b border-slate-800 bg-slate-900/60 p-3 sm:p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Sahnadagi A'zolar ({members.length}/4)
              </span>
              {isRoomOwner ? (
                <button
                  className="text-xs font-bold text-indigo-400 hover:text-indigo-300 transition"
                  onClick={regenerateCode}
                  disabled={busy}
                >
                  Yangi PIN olish
                </button>
              ) : null}
            </div>

            <div className="grid grid-cols-4 gap-2 sm:gap-4 max-w-xl mx-auto">
              {members.map((m: Row) => {
                const isSpeaking =
                  speakingPeers.includes(String(m.user_id)) ||
                  (voiceState === "room" && speakingPeers.length > 0);
                const initials = (m.first_name?.[0] || m.login_id?.[0] || "U").toUpperCase();
                const isOwnerMember =
                  Number(m.user_id) === Number(detail?.room?.owner_id || room?.owner_id || 0);

                return (
                  <div key={m.user_id} className="flex flex-col items-center justify-center text-center">
                    <div
                      className={`relative w-12 h-12 sm:w-14 sm:h-14 rounded-full flex items-center justify-center text-sm font-black transition-all duration-200 border-2 ${
                        isSpeaking
                          ? "border-emerald-500 shadow-[0_0_20px_rgba(16,185,129,0.5)] scale-105 bg-slate-800"
                          : "border-slate-700 bg-slate-800"
                      }`}
                    >
                      <span className="text-white font-bold">{initials}</span>
                      {isOwnerMember ? (
                        <span className="absolute -top-1 -right-1 text-xs" title="Xona egasi">
                          👑
                        </span>
                      ) : null}
                      {isSpeaking ? (
                        <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-500 border-2 border-slate-900 animate-pulse" />
                      ) : null}
                    </div>
                    <span className="mt-1.5 text-xs font-bold text-slate-200 max-w-[80px] truncate">
                      {m.first_name || m.login_id}
                    </span>
                    <span className="text-[10px] text-slate-400">
                      {isSpeaking ? "🗣️ Ovozda" : "🎙 Tinglamoqda"}
                    </span>
                  </div>
                );
              })}

              {Array.from({ length: Math.max(0, 4 - members.length) }, (_, i) => (
                <div key={`empty-${i}`} className="flex flex-col items-center justify-center text-center">
                  <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-full border-2 border-dashed border-slate-800 flex items-center justify-center text-slate-600 text-xs">
                    +
                  </div>
                  <span className="mt-1.5 text-[11px] text-slate-600 font-medium">Bo'sh</span>
                </div>
              ))}
            </div>
          </div>

          {/* Central Live Document Reader Stage */}
          <div className="flex-1 min-h-0 flex flex-col">
            {/* Document Controls Toolbar */}
            <div className="flex items-center justify-between border-b border-slate-800 px-4 py-2.5 bg-slate-900/40">
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  disabled={safeActiveMaterialIndex <= 0}
                  onClick={() => setActiveMaterialIndex((prev) => Math.max(0, prev - 1))}
                  className="rounded-lg bg-slate-800 px-2.5 py-1 text-xs font-bold text-slate-300 hover:bg-slate-700 disabled:opacity-30"
                  title="Oldingi"
                >
                  ←
                </button>
                <button
                  type="button"
                  disabled={safeActiveMaterialIndex >= materials.length - 1}
                  onClick={() => setActiveMaterialIndex((prev) => Math.min(materials.length - 1, prev + 1))}
                  className="rounded-lg bg-slate-800 px-2.5 py-1 text-xs font-bold text-slate-300 hover:bg-slate-700 disabled:opacity-30"
                  title="Keyingi"
                >
                  →
                </button>
              </div>

              <div className="text-center px-2 min-w-0 flex-1">
                <span className="text-xs font-bold text-white truncate block">
                  {materials.length > 0
                    ? `Fayl ${safeActiveMaterialIndex + 1} / ${materials.length}: ${
                        currentMaterial?.title || currentMaterial?.file_name || "Material"
                      }`
                    : "Materiallar yuklanmagan"}
                </span>
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                <label className="cursor-pointer rounded-lg bg-indigo-600 hover:bg-indigo-700 px-2.5 py-1 text-xs font-bold text-white transition flex items-center gap-1">
                  <span>📎</span>
                  <span className="hidden sm:inline">Yuklash</span>
                  <input
                    type="file"
                    multiple
                    className="hidden"
                    accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt"
                    onChange={upload}
                  />
                </label>

                {currentMaterial ? (
                  <>
                    <button
                      type="button"
                      onClick={() => setPreviewFile(currentMaterial)}
                      className="rounded-lg bg-slate-800 hover:bg-slate-700 px-2 py-1 text-xs text-slate-300 font-bold"
                      title="To'liq ekranda ochish"
                    >
                      ⛶
                    </button>
                    <a
                      href={currentMaterialUrl}
                      target="_blank"
                      rel="noreferrer"
                      download
                      className="rounded-lg bg-slate-800 hover:bg-slate-700 px-2 py-1 text-xs text-slate-300 font-bold"
                      title="Yuklab olish"
                    >
                      ⬇
                    </a>
                  </>
                ) : null}
              </div>
            </div>

            {/* Document Viewer Stage */}
            <div className="flex-1 min-h-0 flex items-center justify-center p-3 overflow-auto bg-black/30">
              {currentMaterial ? (
                currentMaterialIsImage ? (
                  <div className="flex h-full w-full items-center justify-center p-2">
                    <img
                      src={currentMaterialUrl}
                      alt={currentMaterial.title || "Material"}
                      className="max-h-[55vh] max-w-full rounded-2xl object-contain shadow-2xl border border-slate-800"
                    />
                  </div>
                ) : currentMaterialIsPdf ? (
                  <iframe
                    src={currentMaterialUrl}
                    className="w-full h-full min-h-[450px] rounded-2xl border border-slate-800 shadow-md bg-white"
                    title="PDF Viewer"
                  />
                ) : (
                  <div className="p-6 text-center bg-slate-900 rounded-3xl border border-slate-800 max-w-md">
                    <span className="text-4xl block mb-2">📄</span>
                    <h4 className="font-bold text-sm text-white mb-1">
                      {currentMaterial.title || currentMaterial.file_name}
                    </h4>
                    <p className="text-xs text-slate-400 mb-4">
                      Ushbu hujjatni alohida oynada ochishingiz yoki yuklab olishingiz mumkin.
                    </p>
                    <div className="flex items-center justify-center gap-2">
                      <a
                        href={currentMaterialUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-xl bg-indigo-600 hover:bg-indigo-700 px-4 py-2 text-xs font-bold text-white shadow"
                      >
                        📄 Yangi oynada ochish
                      </a>
                    </div>
                  </div>
                )
              ) : (
                <div className="flex flex-col items-center justify-center p-8 text-center">
                  <div className="w-16 h-16 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center text-3xl mb-3">
                    📚
                  </div>
                  <h4 className="font-bold text-base text-white">Markaziy Materiallar Bo'limi</h4>
                  <p className="text-xs text-slate-400 max-w-sm mt-1 mb-4 leading-relaxed">
                    Darslik, PDF kitob yoki konspekt rasmlarini yuklang. Xonadagi barcha talabalar materialni mustaqil varaqlab o'rganadilar.
                  </p>
                  <label className="cursor-pointer rounded-xl bg-indigo-600 hover:bg-indigo-700 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-500/20 transition flex items-center gap-2">
                    <span>📎</span>
                    <span>Fayl yoki PDF yuklash</span>
                    <input
                      type="file"
                      multiple
                      className="hidden"
                      accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt"
                      onChange={upload}
                    />
                  </label>
                </div>
              )}
            </div>

            {/* Filmstrip Thumbnails Switcher */}
            {materials.length > 1 ? (
              <div className="border-t border-slate-800 px-3 py-2 bg-slate-900/60 flex items-center gap-2 overflow-x-auto">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 shrink-0">
                  Fayllar ({materials.length}):
                </span>
                <div className="flex gap-2">
                  {materials.map((file: Row, idx: number) => {
                    const isCur = idx === safeActiveMaterialIndex;
                    const fUrl = normalizeMediaUrl(file.file_url || file.url);
                    const isImg =
                      String(file.mime_type || "").startsWith("image/") ||
                      /\.(jpg|jpeg|png|webp|gif|svg|bmp)(\?.*)?$/i.test(fUrl);
                    return (
                      <button
                        key={file.id || idx}
                        type="button"
                        onClick={() => setActiveMaterialIndex(idx)}
                        className={`flex items-center gap-1.5 rounded-xl border px-2.5 py-1 text-xs font-bold transition shrink-0 ${
                          isCur
                            ? "border-indigo-500 bg-indigo-500/20 text-indigo-300"
                            : "border-slate-800 bg-slate-900 text-slate-400 hover:border-slate-700"
                        }`}
                      >
                        <span>{isImg ? "🖼️" : "📄"}</span>
                        <span className="max-w-28 truncate">{file.title || file.file_name || `Fayl #${idx + 1}`}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </div>
        </div>

        {/* ─── RIGHT: LIVE CHAT & VOICE-ROOM CONTROLS DOCK ─── */}
        <div
          className={`w-full lg:w-96 flex flex-col min-h-0 bg-slate-900 border-l border-slate-800 shadow-xl ${
            mobileTab === "chat" ? "flex" : "hidden lg:flex"
          }`}
        >
          {/* Chat Header */}
          <div className="border-b border-slate-800 px-4 py-3 bg-slate-900/90 flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
              Guruh Suhbat ({messages.length})
            </span>
            <span className="text-[11px] text-emerald-400 font-bold flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse inline-block" />
              <span>Jonli</span>
            </span>
          </div>

          {/* Messages Stream */}
          <div className="min-h-0 flex-1 overflow-y-auto space-y-3 p-3.5 custom-scrollbar">
            {messages.map((item) => {
              const isMe = userId > 0 && Number(item.user_id) === userId;
              const files = Array.isArray(item.attachments) ? item.attachments : [];
              return (
                <div key={item.id} className={`flex flex-col ${isMe ? "items-end" : "items-start"}`}>
                  <span className="text-[10px] text-slate-500 mb-1 px-1">
                    {item.first_name || item.login_id || "A'zo"} ·{" "}
                    {item.created_at ? new Date(item.created_at).toLocaleTimeString().slice(0, 5) : ""}
                  </span>

                  <div
                    className={`px-3.5 py-2 rounded-2xl max-w-[88%] text-[13px] shadow-sm ${
                      isMe
                        ? "bg-indigo-600 text-white rounded-br-sm"
                        : "bg-slate-800 text-slate-200 border border-slate-700/50 rounded-bl-sm"
                    }`}
                  >
                    <p className="whitespace-pre-wrap leading-relaxed">{item.body}</p>

                    {/* Attachment chips */}
                    {files.length > 0 ? (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {files.map((file: Row, index: number) => {
                          const attUrl = normalizeMediaUrl(file.url || file.file_url);
                          const isImageAtt =
                            String(file.mime_type || "").startsWith("image/") ||
                            /\.(jpg|jpeg|png|webp|gif|svg|bmp)(\?.*)?$/i.test(attUrl);
                          return (
                            <button
                              key={index}
                              type="button"
                              onClick={() => setPreviewFile(file)}
                              className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900/80 px-2 py-1 text-[11px] font-bold text-indigo-300 hover:border-indigo-400 transition"
                            >
                              <span>{isImageAtt ? "🖼️" : "📎"}</span>
                              <span className="max-w-32 truncate">{file.file_name || "Fayl"}</span>
                            </button>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                </div>
              );
            })}

            {!messages.length ? (
              <div className="py-12 text-center text-xs text-slate-500">
                Suhbat bo'sh. Birinchi xabarni yuboring yoki reaksiyalar bilan fikr bildiring.
              </div>
            ) : null}
          </div>

          {/* VOICE ROOM STYLE BOTTOM CONTROLS DOCK */}
          <div className="p-3 bg-slate-950 border-t border-slate-800 flex flex-col gap-2">
            {/* Quick Emoji Reactions & Attachment Toolbar */}
            <div className="flex items-center justify-between gap-1 px-1">
              <div className="flex items-center gap-1">
                {["❤️", "👏", "😂", "🔥", "💡"].map((emoji) => (
                  <button
                    key={emoji}
                    type="button"
                    onClick={() => sendReaction(emoji)}
                    className="w-7 h-7 rounded-full bg-slate-800 hover:bg-slate-700 text-xs flex items-center justify-center transition active:scale-90"
                    title={emoji}
                  >
                    {emoji}
                  </button>
                ))}
              </div>

              <label className="cursor-pointer rounded-full bg-slate-800 hover:bg-slate-700 w-7 h-7 flex items-center justify-center text-xs text-slate-300 transition" title="Fayl biriktirish">
                📎
                <input
                  type="file"
                  multiple
                  className="hidden"
                  accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt"
                  onChange={upload}
                />
              </label>
            </div>

            {/* Input Form with Send Button */}
            <form onSubmit={send} className="flex items-center gap-2">
              <input
                type="text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Xabar yozing..."
                className="flex-1 bg-slate-900 border border-slate-800 rounded-full px-4 py-2 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 transition"
              />
              <button
                type="submit"
                disabled={busy || (!text.trim() && !attachments.length)}
                className="w-8 h-8 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white flex items-center justify-center disabled:opacity-40 transition shadow-sm shrink-0"
              >
                <svg className="w-4 h-4 ml-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Floating Preview Modal */}
      {previewFile ? (() => {
        const previewUrl = normalizeMediaUrl(previewFile.file_url || previewFile.url);
        const previewIsImage =
          Boolean(previewUrl) && (
            String(previewFile.mime_type || "").startsWith("image/") ||
            /\.(jpg|jpeg|png|webp|gif|svg|bmp)(\?.*)?$/i.test(previewUrl)
          );
        return (
          <div className="fixed inset-0 z-[250] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm animate-fade-in">
            <div className="relative flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-3xl bg-slate-900 border border-slate-800 shadow-2xl">
              <div className="flex items-center justify-between border-b border-slate-800 p-4 bg-slate-900">
                <div className="min-w-0 flex-1 pr-4">
                  <h3 className="font-bold text-white truncate text-sm sm:text-base">
                    {previewFile.title || previewFile.file_name || "Material ko'rish"}
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <a
                    href={previewUrl}
                    target="_blank"
                    rel="noreferrer"
                    download
                    className="rounded-xl bg-indigo-600 hover:bg-indigo-700 px-3 py-1.5 text-xs font-bold text-white"
                  >
                    Yuklab olish ↗
                  </a>
                  <button
                    onClick={() => setPreviewFile(null)}
                    type="button"
                    className="grid h-8 w-8 place-items-center rounded-full text-slate-400 hover:bg-slate-800 hover:text-white transition"
                  >
                    ✕
                  </button>
                </div>
              </div>

              <div className="min-h-0 flex-1 overflow-auto p-4 flex items-center justify-center bg-black/30">
                {previewIsImage ? (
                  <img
                    src={previewUrl}
                    alt={previewFile.title || "Preview"}
                    className="max-h-[65vh] w-auto max-w-full rounded-xl object-contain shadow"
                  />
                ) : (
                  <iframe
                    src={previewUrl}
                    className="w-full h-[65vh] rounded-xl border-none shadow bg-white"
                    title="PDF Modal"
                  />
                )}
              </div>
            </div>
          </div>
        );
      })() : null}
    </section>
  );
}
