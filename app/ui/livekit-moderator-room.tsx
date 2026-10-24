"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { createPortal } from "react-dom";
import { useWebLocale } from "./web-i18n";

type ApiFetch = (path: string, options?: { method?: string; body?: unknown }) => Promise<unknown>;
type JoinPayload = { url: string; token: string; room_state?: RoomState; recording_status?: string };
type MediaRequest = { user_id: number; media_kind: string; display_name?: string | null };
type Hand = { user_id: number; display_name: string };
type ChatMessage = { id: number; display_name: string; is_moderator: boolean; text: string; created_at: string };
type RoomState = {
  topic?: string;
  primary_identity?: string | null;
  primary_source?: "camera" | "screen" | "board" | "auto" | null;
  announcement?: string | null;
  cue_card_title?: string | null;
  cue_card_prompts?: string[] | null;
  cue_card_started_at?: string | null;
  cue_card_duration_seconds?: number | null;
  cue_card_visible?: boolean;
  board_text?: string | null;
  board_visible?: boolean;
};
type Feed = { key: string; identity: string; name: string; participant: any; publication: any | null; source: "camera" | "screen"; local: boolean };

const COPY = {
  uz: {
    room: "Xona", connected: "Ulangan", connecting: "Moderator sifatida ulanmoqda…", live: "JONLI", attendees: "qatnashchi", raised: "qo‘l ko‘tardi", muteAll: "Barchani o‘chirish", end: "Darsni tugatish", leave: "Xonadan chiqish", participants: "Qatnashchilar", chat: "Live chat", primary: "ASOSIY SAHNA", setPrimary: "Asosiy qilish", camera: "Kamera", screen: "Ekran", waiting: "Video oqimi kutilmoqda", waitingHelp: "Kamera yoki ekran ulashilganda shu yerda ko‘rinadi.", stage: "Sahnada", microphone: "Mikrofon", mute: "O‘chirish", unmute: "Yoqish", camOn: "Kamera yoqilgan", camOff: "Kamera o‘chiq", share: "Ekran ulashish", stopShare: "Ulashishni to‘xtatish", cue: "Cue card", board: "Taxta", note: "E’lon", finish: "Tugatish", all: "Barchasi", hands: "Qo‘llar", speaking: "Gapiryapti", requests: "So‘rovlar", search: "Qatnashchini qidirish…", noPeople: "Qatnashchi topilmadi.", invite: "Gapirishga taklif", askUnmute: "Mikrofonni yoqishni so‘rash", remove: "Chiqarish", permission: "Media ruxsati", approve: "Ruxsat berish", deny: "Rad etish", pending: "Kutilayotgan so‘rov yo‘q.", pinned: "MUHIM E’LON", message: "Sinfga xabar yozing…", send: "Yuborish", lock: "Xonani qulflash", unlock: "Xonani ochish", fit: "To‘liq sig‘dirish", fullscreen: "To‘liq ekran", edit: "Tahrirlash", save: "Saqlash", cancel: "Bekor qilish", title: "Savol yoki cue card", prompts: "Yo‘naltiruvchi savollar (har biri yangi qatorda)", timer: "Timer", startTimer: "Timerni boshlash", resetTimer: "Timerni qayta boshlash", announcement: "Barcha qatnashchilarga e’lon", boardText: "Taxta matni", showBoard: "Taxtani ko‘rsatish", hideBoard: "Taxtani yashirish", endConfirm: "Darsni barcha qatnashchilar uchun tugatasizmi?", endHelp: "Bu amal barcha qurilmalarni live xonadan chiqaradi va dars jadvalidagi holatni tugallangan qiladi.", removeConfirm: "Qatnashchini xonadan chiqarasizmi?", muteAllConfirm: "Faol mikrofonlarni o‘chirasizmi?", audio: "Ovozni yoqish", device: "Qurilma", noMessages: "Hozircha xabar yo‘q.", statusError: "Amalni bajarib bo‘lmadi. Qayta urinib ko‘ring.", requestApproved: "Ruxsat berildi.", requestDenied: "So‘rov rad etildi.", invited: "Gapirish taklifi yuborildi.", asked: "Mikrofon so‘rovi yuborildi.", saved: "O‘zgarishlar barcha qatnashchilarga yuborildi.", mutedCount: "ta mikrofon o‘chirildi", noneToMute: "O‘chiriladigan faol mikrofon yo‘q.", presentation: "Taqdimot", status: "Aloqa", participant: "Qatnashchi", roomLocked: "Xona qulflangan", roomOpen: "Xona ochiq",
  },
  ru: {
    room: "Комната", connected: "Подключено", connecting: "Подключение модератора…", live: "ПРЯМОЙ ЭФИР", attendees: "участников", raised: "подняли руку", muteAll: "Отключить все", end: "Завершить урок", leave: "Выйти из комнаты", participants: "Участники", chat: "Чат эфира", primary: "ОСНОВНОЙ ЭКРАН", setPrimary: "Сделать основным", camera: "Камера", screen: "Экран", waiting: "Ожидание видео", waitingHelp: "Здесь появится камера или демонстрация экрана.", stage: "На экране", microphone: "Микрофон", mute: "Выключить", unmute: "Включить", camOn: "Камера включена", camOff: "Камера выключена", share: "Демонстрация экрана", stopShare: "Остановить показ", cue: "Карточка задания", board: "Доска", note: "Объявление", finish: "Завершить", all: "Все", hands: "Руки", speaking: "Говорят", requests: "Запросы", search: "Найти участника…", noPeople: "Участники не найдены.", invite: "Пригласить говорить", askUnmute: "Попросить включить микрофон", remove: "Удалить", permission: "Разрешение на медиа", approve: "Разрешить", deny: "Отклонить", pending: "Нет ожидающих запросов.", pinned: "ЗАКРЕПЛЕННОЕ ОБЪЯВЛЕНИЕ", message: "Написать сообщение классу…", send: "Отправить", lock: "Закрыть комнату", unlock: "Открыть комнату", fit: "Вместить целиком", fullscreen: "Полный экран", edit: "Изменить", save: "Сохранить", cancel: "Отмена", title: "Вопрос или карточка", prompts: "Подсказки (каждая с новой строки)", timer: "Таймер", startTimer: "Начать таймер", resetTimer: "Перезапустить таймер", announcement: "Объявление для всех участников", boardText: "Текст доски", showBoard: "Показать доску", hideBoard: "Скрыть доску", endConfirm: "Завершить урок для всех участников?", endHelp: "Все устройства выйдут из комнаты, а урок в расписании будет завершён.", removeConfirm: "Удалить участника из комнаты?", muteAllConfirm: "Отключить активные микрофоны?", audio: "Включить звук", device: "Устройство", noMessages: "Пока нет сообщений.", statusError: "Не удалось выполнить действие. Попробуйте ещё раз.", requestApproved: "Доступ разрешён.", requestDenied: "Запрос отклонён.", invited: "Приглашение говорить отправлено.", asked: "Запрос на включение микрофона отправлен.", saved: "Изменения отправлены всем участникам.", mutedCount: "микрофонов выключено", noneToMute: "Нет активных микрофонов.", presentation: "Презентация", status: "Связь", participant: "Участник", roomLocked: "Комната закрыта", roomOpen: "Комната открыта",
  },
  en: {
    room: "Room", connected: "Connected", connecting: "Connecting as moderator…", live: "LIVE", attendees: "attendees", raised: "raised", muteAll: "Mute All", end: "End Lesson", leave: "Leave room", participants: "Participants", chat: "Live Chat", primary: "PRIMARY STAGE", setPrimary: "Set as primary", camera: "Camera", screen: "Screen", waiting: "Waiting for video", waitingHelp: "A camera or shared screen will appear here.", stage: "On stage", microphone: "Microphone", mute: "Mute", unmute: "Unmute", camOn: "Cam On", camOff: "Cam Off", share: "Screen Sharing", stopShare: "Stop Sharing", cue: "Cue Card", board: "Board", note: "Broadcast Note", finish: "Finish", all: "All", hands: "Hands", speaking: "Speaking", requests: "Requests", search: "Search participants…", noPeople: "No participants found.", invite: "Invite to speak", askUnmute: "Ask to unmute", remove: "Remove", permission: "Media access", approve: "Approve", deny: "Deny", pending: "No pending requests.", pinned: "PINNED ANNOUNCEMENT", message: "Send a message to class…", send: "Send", lock: "Lock room", unlock: "Unlock room", fit: "Fit to screen", fullscreen: "Fullscreen", edit: "Edit", save: "Save", cancel: "Cancel", title: "Question or cue card", prompts: "Prompts (one per line)", timer: "Timer", startTimer: "Start timer", resetTimer: "Restart timer", announcement: "Announcement for all participants", boardText: "Board text", showBoard: "Show board", hideBoard: "Hide board", endConfirm: "End this lesson for everyone?", endHelp: "All devices will leave the live room and the scheduled lesson will be marked complete.", removeConfirm: "Remove this participant from the room?", muteAllConfirm: "Mute all active microphones?", audio: "Enable audio", device: "Device", noMessages: "No messages yet.", statusError: "Action failed. Please try again.", requestApproved: "Access approved.", requestDenied: "Request denied.", invited: "Invitation to speak sent.", asked: "Unmute request sent.", saved: "Changes sent to all participants.", mutedCount: "microphones muted", noneToMute: "No active microphones to mute.", presentation: "Presentation", status: "Connection", participant: "Participant", roomLocked: "Room locked", roomOpen: "Room open",
  },
} as const;

function symbol(name: string, size = 18) {
  // Inline icons do not depend on Google's icon font being reachable. A
  // blocked font used to expose ligature names ("mic_off", "groups", …) in
  // the moderator controls instead of drawing the icons.
  const shape = (() => {
    switch (name) {
      case "groups": return <><circle cx="9" cy="8" r="3"/><path d="M3 20v-1a6 6 0 0 1 12 0v1M17 5a3 3 0 0 1 0 6m1 3a5 5 0 0 1 3 5v1"/></>;
      case "volume_off": return <><path d="M11 5 6 9H3v6h3l5 4V5ZM17 9l5 6m0-6-5 6"/><path d="M2 2l20 20"/></>;
      case "volume_up": return <><path d="M11 5 6 9H3v6h3l5 4V5ZM15 9a5 5 0 0 1 0 6m3-9a9 9 0 0 1 0 12"/></>;
      case "call_end": return <path d="M4 13c4.7-3.4 11.3-3.4 16 0l1 3-4 2-2-3a12 12 0 0 0-6 0l-2 3-4-2 1-3Z"/>;
      case "close": return <path d="M5 5l14 14M19 5 5 19"/>;
      case "fit_screen": return <><path d="M8 3H4v4m12-4h4v4M4 17v4h4m12-4v4h-4"/><rect x="8" y="8" width="8" height="8" rx="1"/></>;
      case "fullscreen": return <path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>;
      case "article": return <><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></>;
      case "mic": return <><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0m-7 7v3m-4 0h8"/></>;
      case "mic_off": return <><path d="M9 7v5a3 3 0 0 0 5 2m1-5V6a3 3 0 0 0-5-2M5 11a7 7 0 0 0 12 5m2-5a7 7 0 0 1-1 4m-6 4v2m-4 0h8M3 3l18 18"/></>;
      case "videocam": return <><rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10 5-3v10l-5-3"/></>;
      case "videocam_off": return <><path d="M10 6h4a2 2 0 0 1 2 2v2l5-3v10l-3-2M16 17a2 2 0 0 1-2 1H5a2 2 0 0 1-2-2V8a2 2 0 0 1 1-2M3 3l18 18"/></>;
      case "screen_share": return <><rect x="3" y="4" width="18" height="14" rx="2"/><path d="M8 22h8m-4-4v4m-2-9 4-4m-3 0h3v3"/></>;
      case "stop_screen_share": return <><rect x="3" y="4" width="18" height="14" rx="2"/><path d="M8 22h8m-4-4v4M3 3l18 18"/></>;
      case "draw": return <><path d="m4 18 1-4L17 2l5 5-12 12-4 1-2-2Zm10-13 5 5M3 22h18"/></>;
      case "campaign": return <><path d="M3 10v4a2 2 0 0 0 2 2h3l2 5h3l-2-5h2l7 4V4l-7 4H5a2 2 0 0 0-2 2Z"/></>;
      case "power_settings_new": return <><path d="M12 2v10m-5-7a9 9 0 1 0 10 0"/></>;
      case "lock": return <><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></>;
      case "lock_open": return <><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M7 11V7a5 5 0 0 1 9-3"/></>;
      case "chat": return <path d="M4 4h16a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H8l-5 3V6a2 2 0 0 1 1-2Z"/>;
      case "send": return <><path d="m22 2-7 20-4-9-9-4 20-7ZM11 13 22 2"/></>;
      default: return <circle cx="12" cy="12" r="8"/>;
    }
  })();
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="inline-block shrink-0 align-middle">{shape}</svg>;
}

function publications(participant: any): any[] {
  return Array.from(participant?.trackPublications?.values?.() || []);
}

function moderator(participant: any): boolean {
  return String(participant?.identity || "").startsWith("speaking-admin-");
}

function feedSource(publication: any): "camera" | "screen" {
  return String(publication?.source || "").toLowerCase().includes("screen") ? "screen" : "camera";
}

function feedsFor(participants: any[]): Feed[] {
  const feeds: Feed[] = [];
  for (const participant of participants) {
    const identity = String(participant?.identity || "");
    const name = String(participant?.name || identity || "Participant");
    const videos = publications(participant).filter((item) => item.track?.kind === "video" && !item.isMuted);
    if (!videos.length) {
      feeds.push({ key: `${identity}:avatar`, identity, name, participant, publication: null, source: "camera", local: participant?.isLocal === true });
    } else {
      for (const publication of videos) feeds.push({ key: `${identity}:${publication.trackSid || publication.source}`, identity, name, participant, publication, source: feedSource(publication), local: participant?.isLocal === true });
    }
  }
  return feeds;
}

function VideoFeed({ feed, large = false, refreshKey = 0 }: { feed: Feed | null; large?: boolean; refreshKey?: number }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const track = feed?.publication?.track;
    const container = host.current;
    if (!track || !container) return;
    const video = track.attach() as HTMLVideoElement;
    video.autoplay = true;
    video.playsInline = true;
    video.muted = feed?.local === true;
    video.style.width = "100%";
    video.style.height = "100%";
    video.style.objectFit = "contain";
    video.style.background = "#070d1b";
    container.appendChild(video);
    return () => { track.detach(video); video.remove(); };
  }, [feed?.key, feed?.publication?.track, feed?.local, refreshKey]);
  const initials = (feed?.name || "?").split(/[\s·]+/).filter(Boolean).slice(0, 2).map((item) => item[0]?.toUpperCase()).join("");
  return <div ref={host} className="relative flex h-full w-full items-center justify-center overflow-hidden bg-[#070d1b]">
    {!feed?.publication?.track && <div className="flex flex-col items-center gap-2 text-white"><span className={`grid place-items-center rounded-full border border-[#3549d5] bg-[#11205a] font-bold ${large ? "h-24 w-24 text-3xl" : "h-14 w-14 text-lg"}`}>{initials || "?"}</span><span className="max-w-[90%] truncate text-center text-xs font-semibold">{feed?.name || "—"}</span></div>}
  </div>;
}

function RemoteAudio({ participants, refreshKey }: { participants: any[]; refreshKey: number }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const container = host.current;
    if (!container) return;
    const attached: Array<{ track: any; element: HTMLElement }> = [];
    for (const participant of participants) {
      if (participant?.isLocal) continue;
      for (const publication of publications(participant)) {
        if (publication.track?.kind !== "audio" || publication.isMuted) continue;
        const audio = publication.track.attach() as HTMLAudioElement;
        audio.autoplay = true;
        audio.className = "hidden";
        container.appendChild(audio);
        void audio.play().catch(() => undefined);
        attached.push({ track: publication.track, element: audio });
      }
    }
    return () => { for (const item of attached) { item.track.detach(item.element); item.element.remove(); } };
  }, [participants, refreshKey]);
  return <div ref={host} className="hidden" aria-hidden="true" />;
}

function parseRoomState(raw: unknown): RoomState {
  try {
    const value = typeof raw === "string" ? JSON.parse(raw) : raw;
    return value && typeof value === "object" && !Array.isArray(value) ? value as RoomState : {};
  } catch { return {}; }
}

function messageTime(value: string, locale: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleTimeString(locale === "ru" ? "ru-RU" : locale === "en" ? "en-US" : "uz-UZ", { hour: "2-digit", minute: "2-digit" });
}

export function LiveKitModeratorRoom({ roomId, title, apiFetch, onClose, onRoomEnded }: {
  roomId: string; title: string; apiFetch: ApiFetch; onClose: () => void; onRoomEnded: () => void;
}) {
  const locale = useWebLocale();
  const lang = locale === "ru" || locale === "en" ? locale : "uz";
  const c = COPY[lang];
  const roomRef = useRef<any>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const [portalReady, setPortalReady] = useState(false);
  const [sessionId] = useState(() => globalThis.crypto?.randomUUID?.().replaceAll("-", "").slice(0, 24) || `${Date.now()}${Math.random().toString(36).slice(2, 10)}`);
  const [deviceName] = useState(() => {
    if (typeof navigator === "undefined") return "Browser";
    const ua = navigator.userAgent;
    const platform = /Android/i.test(ua) ? "Android" : /iPhone|iPad/i.test(ua) ? "iPhone" : /Windows/i.test(ua) ? "Windows" : /Macintosh|Mac OS/i.test(ua) ? "Mac" : "Browser";
    const browser = /Edg\//i.test(ua) ? "Edge" : /Firefox\//i.test(ua) ? "Firefox" : /Chrome\//i.test(ua) ? "Chrome" : /Safari\//i.test(ua) ? "Safari" : "Browser";
    return `${platform} · ${browser}`;
  });
  const [room, setRoom] = useState<any>(null);
  const [participants, setParticipants] = useState<any[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [connecting, setConnecting] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState<"chat" | "participants">("chat");
  const [filter, setFilter] = useState<"all" | "hand" | "speaking" | "requests">("all");
  const [search, setSearch] = useState("");
  const [mediaRequests, setMediaRequests] = useState<MediaRequest[]>([]);
  const [hands, setHands] = useState<Hand[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [roomState, setRoomState] = useState<RoomState>({});
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceMenu, setDeviceMenu] = useState<"audioinput" | "videoinput" | "audiooutput" | null>(null);
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [modal, setModal] = useState<"end" | "cue" | "board" | "announcement" | null>(null);
  const [cueTitle, setCueTitle] = useState("");
  const [cuePrompts, setCuePrompts] = useState("");
  const [boardText, setBoardText] = useState("");
  const [announcementText, setAnnouncementText] = useState("");
  const [wideStage, setWideStage] = useState(true);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const id = window.setTimeout(() => setPortalReady(true), 0);
    return () => window.clearTimeout(id);
  }, []);

  const refreshParticipants = useCallback(() => {
    const current = roomRef.current;
    if (!current) return;
    setParticipants([current.localParticipant, ...current.remoteParticipants.values()]);
    setRefreshKey((value) => value + 1);
    setAudioEnabled(Boolean(current.canPlaybackAudio));
  }, []);

  const loadMessages = useCallback(async () => {
    try {
      const data = await apiFetch(`/api/speaking/live-video/rooms/${encodeURIComponent(roomId)}/messages`, { method: "GET" }) as { messages?: ChatMessage[] };
      if (Array.isArray(data.messages)) setMessages((previous) => {
        const byId = new Map<number, ChatMessage>(previous.map((item) => [item.id, item]));
        for (const item of data.messages || []) byId.set(item.id, item);
        return [...byId.values()].sort((a, b) => a.id - b.id).slice(-100);
      });
    } catch { /* Live video remains usable during a short chat outage. */ }
  }, [apiFetch, roomId]);

  const loadHands = useCallback(async () => {
    try {
      const data = await apiFetch(`/staff/speaking/live-video/rooms/${encodeURIComponent(roomId)}/hands`, { method: "GET" }) as { hands?: Hand[] };
      setHands(Array.isArray(data.hands) ? data.hands : []);
    } catch { /* Retry with the next refresh. */ }
  }, [apiFetch, roomId]);

  const loadState = useCallback(async () => {
    try {
      const data = await apiFetch(`/api/speaking/live-video/rooms/${encodeURIComponent(roomId)}/session-state`, { method: "GET" }) as { state?: RoomState };
      setRoomState(parseRoomState(data.state));
    } catch { /* LiveKit metadata continues to drive the stage. */ }
  }, [apiFetch, roomId]);

  const refreshRequests = useCallback(async () => {
    try {
      const data = await apiFetch(`/staff/speaking/live-video/rooms/${encodeURIComponent(roomId)}/media-permissions`, { method: "GET" }) as { requests?: MediaRequest[] };
      setMediaRequests(Array.isArray(data.requests) ? data.requests : []);
    } catch { /* Media requests retry automatically. */ }
  }, [apiFetch, roomId]);

  const refreshDevices = useCallback(async () => {
    const found = await navigator.mediaDevices?.enumerateDevices().catch(() => []) || [];
    setDevices(found);
  }, []);

  useEffect(() => {
    let disposed = false;
    let liveRoom: any = null;
    const connect = async () => {
      try {
        setConnecting(true);
        setError("");
        const payload = await apiFetch(`/staff/speaking/live-video/rooms/${encodeURIComponent(roomId)}/moderator-token`, { method: "POST", body: { session_id: sessionId, device_name: deviceName } }) as JoinPayload;
        if (!payload?.url || !payload?.token) throw new Error(c.statusError);
        const { Room, RoomEvent } = await import("livekit-client");
        liveRoom = new Room({ adaptiveStream: true, dynacast: true });
        roomRef.current = liveRoom;
        const refresh = () => { if (!disposed) { setRoom(liveRoom); refreshParticipants(); } };
        for (const event of [RoomEvent.Connected, RoomEvent.ParticipantConnected, RoomEvent.ParticipantDisconnected, RoomEvent.TrackSubscribed, RoomEvent.TrackUnsubscribed, RoomEvent.TrackMuted, RoomEvent.TrackUnmuted, RoomEvent.LocalTrackPublished, RoomEvent.LocalTrackUnpublished, RoomEvent.AudioPlaybackStatusChanged]) liveRoom.on(event, refresh);
        liveRoom.on(RoomEvent.Disconnected, () => {
          if (!disposed) { setRoom(null); setParticipants([]); setError(c.statusError); }
        });
        liveRoom.on(RoomEvent.RoomMetadataChanged, (metadata: string) => { if (!disposed) setRoomState(parseRoomState(metadata)); });
        liveRoom.on(RoomEvent.DataReceived, (data: Uint8Array, _participant: any, _kind: any, topic: string) => {
          if (disposed || topic !== "diamond.speaking.live") return;
          try {
            const event = JSON.parse(new TextDecoder().decode(data));
            if (event?.type === "chat" && Number(event.id) > 0) setMessages((prev) => prev.some((item) => item.id === Number(event.id)) ? prev : [...prev, event].slice(-100));
            if (event?.type === "hand") void loadHands();
            if (event?.type === "reaction" && typeof event.emoji === "string") setNotice(event.emoji);
          } catch { /* Ignore unknown room packets. */ }
        });
        await liveRoom.connect(payload.url, payload.token);
        if (disposed) { await liveRoom.disconnect(); return; }
        if (payload.recording_status === "failed") setError(lang === "ru" ? "Запись урока не началась. Проверьте службу записи." : lang === "en" ? "Lesson recording did not start. Check the recording service." : "Dars yozuvi boshlanmadi. Yozuv xizmatini tekshiring.");
        setRoom(liveRoom);
        setRoomState(parseRoomState(liveRoom.metadata || payload.room_state));
        refreshParticipants();
        void loadMessages();
        void loadHands();
        void loadState();
        void refreshDevices();
      } catch (cause) {
        if (!disposed) setError(cause instanceof Error ? cause.message : c.statusError);
      } finally { if (!disposed) setConnecting(false); }
    };
    void Promise.resolve().then(connect);
    return () => {
      disposed = true;
      roomRef.current = null;
      if (liveRoom) void liveRoom.disconnect();
      void apiFetch(`/api/speaking/live-video/rooms/${encodeURIComponent(roomId)}/leave`, { method: "POST" }).catch(() => undefined);
    };
    // The callbacks are stable and belong to this room's connection lifetime.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roomId, sessionId, deviceName, apiFetch]);

  useEffect(() => {
    const firstRequest = window.setTimeout(() => void refreshRequests(), 0);
    const requests = window.setInterval(() => void refreshRequests(), 3000);
    const state = window.setInterval(() => { void loadMessages(); void loadHands(); void loadState(); }, 15000);
    const heartbeat = window.setInterval(() => {
      if (roomRef.current) void apiFetch(`/api/speaking/live-video/rooms/${encodeURIComponent(roomId)}/heartbeat`, { method: "POST" }).catch(() => undefined);
    }, 30000);
    const clock = window.setInterval(() => setTick(Date.now()), 1000);
    return () => { window.clearTimeout(firstRequest); window.clearInterval(requests); window.clearInterval(state); window.clearInterval(heartbeat); window.clearInterval(clock); };
  }, [refreshRequests, loadMessages, loadHands, loadState, apiFetch, roomId]);

  async function updateState(changes: Partial<RoomState>) {
    setBusy("state"); setError("");
    try {
      const result = await apiFetch(`/staff/speaking/live-video/rooms/${encodeURIComponent(roomId)}/session-state`, { method: "PATCH", body: changes }) as { state?: RoomState };
      setRoomState(parseRoomState(result.state));
      setNotice(c.saved);
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : c.statusError);
      return false;
    } finally { setBusy(""); }
  }

  async function toggleMedia(kind: "microphone" | "camera" | "screen") {
    const local = roomRef.current?.localParticipant;
    if (!local) return;
    setBusy(kind); setError("");
    try {
      if (kind === "microphone") await local.setMicrophoneEnabled(!local.isMicrophoneEnabled);
      else if (kind === "camera") await local.setCameraEnabled(!local.isCameraEnabled);
      else await local.setScreenShareEnabled(!local.isScreenShareEnabled);
      refreshParticipants();
      void refreshDevices();
    } catch (cause) { setError(cause instanceof Error ? cause.message : c.statusError); }
    finally { setBusy(""); }
  }

  async function changeDevice(kind: "audioinput" | "videoinput" | "audiooutput", id: string) {
    if (!roomRef.current) return;
    setBusy("device"); setError("");
    try { await roomRef.current.switchActiveDevice(kind, id); setDeviceMenu(null); setNotice(c.connected); }
    catch (cause) { setError(cause instanceof Error ? cause.message : c.statusError); }
    finally { setBusy(""); }
  }

  async function enableAudio() {
    if (!roomRef.current) return;
    setBusy("audio"); setError("");
    try { await roomRef.current.startAudio(); setAudioEnabled(true); }
    catch (cause) { setError(cause instanceof Error ? cause.message : c.statusError); }
    finally { setBusy(""); }
  }

  async function decide(request: MediaRequest, approved: boolean) {
    setBusy(`request:${request.user_id}`); setError("");
    try {
      await apiFetch(`/staff/speaking/live-video/rooms/${encodeURIComponent(roomId)}/media-permissions/decide`, { method: "POST", body: { user_id: request.user_id, media_kind: request.media_kind, approved } });
      await refreshRequests();
      setNotice(approved ? c.requestApproved : c.requestDenied);
    } catch (cause) { setError(cause instanceof Error ? cause.message : c.statusError); }
    finally { setBusy(""); }
  }

  async function muteTrack(identity: string, trackSid: string) {
    setBusy(identity); setError("");
    try {
      await apiFetch(`/staff/speaking/live-video/rooms/${encodeURIComponent(roomId)}/tracks/mute`, { method: "POST", body: { identity, track_sid: trackSid, muted: true } });
      const learnerId = Number(identity.replace(/^speaking-/, ""));
      if (Number.isSafeInteger(learnerId) && learnerId > 0) {
        await apiFetch(`/staff/speaking/live-video/rooms/${encodeURIComponent(roomId)}/media-permissions/decide`, { method: "POST", body: { user_id: learnerId, media_kind: "microphone", approved: false } });
      }
      refreshParticipants();
    } catch (cause) { setError(cause instanceof Error ? cause.message : c.statusError); }
    finally { setBusy(""); }
  }

  async function muteAll() {
    if (!window.confirm(c.muteAllConfirm)) return;
    const tracks = participants.filter((person) => !person.isLocal && !moderator(person)).flatMap((person) => publications(person).filter((publication) => publication.track?.kind === "audio" && !publication.isMuted).map((publication) => ({ identity: String(person.identity), trackSid: String(publication.trackSid) })));
    if (!tracks.length) { setNotice(c.noneToMute); return; }
    setBusy("mute-all"); setError("");
    let success = 0;
    for (let index = 0; index < tracks.length; index += 8) {
      const results = await Promise.allSettled(tracks.slice(index, index + 8).map((track) => apiFetch(`/staff/speaking/live-video/rooms/${encodeURIComponent(roomId)}/tracks/mute`, { method: "POST", body: { identity: track.identity, track_sid: track.trackSid, muted: true } })));
      success += results.filter((result) => result.status === "fulfilled").length;
    }
    setNotice(`${success} ${c.mutedCount}`);
    if (success < tracks.length) setError(c.statusError);
    setBusy("");
  }

  async function directAction(action: "invite-to-speak" | "ask-to-unmute", identity: string) {
    setBusy(identity); setError("");
    try {
      await apiFetch(`/staff/speaking/live-video/rooms/${encodeURIComponent(roomId)}/${action}`, { method: "POST", body: { identity } });
      setNotice(action === "invite-to-speak" ? c.invited : c.asked);
      if (action === "invite-to-speak") void loadHands();
    } catch (cause) { setError(cause instanceof Error ? cause.message : c.statusError); }
    finally { setBusy(""); }
  }

  async function removeParticipant(identity: string) {
    if (!window.confirm(c.removeConfirm)) return;
    setBusy(identity); setError("");
    try { await apiFetch(`/staff/speaking/live-video/rooms/${encodeURIComponent(roomId)}/participants/remove`, { method: "POST", body: { identity } }); refreshParticipants(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : c.statusError); }
    finally { setBusy(""); }
  }

  async function sendChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = chatInput.trim();
    if (!text) return;
    setBusy("chat"); setError("");
    try {
      const result = await apiFetch(`/api/speaking/live-video/rooms/${encodeURIComponent(roomId)}/messages`, { method: "POST", body: { text } }) as { message?: ChatMessage };
      if (result.message) setMessages((previous) => previous.some((item) => item.id === result.message!.id) ? previous : [...previous, result.message!].slice(-100));
      setChatInput("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : c.statusError); }
    finally { setBusy(""); }
  }

  async function react(emoji: string) {
    try {
      await roomRef.current?.localParticipant.publishData(new TextEncoder().encode(JSON.stringify({ type: "reaction", emoji })), { reliable: false, topic: "diamond.speaking.live" });
      setNotice(emoji);
    } catch (cause) { setError(cause instanceof Error ? cause.message : c.statusError); }
  }

  async function endLive() {
    setBusy("end"); setError("");
    try {
      await apiFetch(`/api/speaking/live-video/rooms/${encodeURIComponent(roomId)}/end`, { method: "POST" });
      await roomRef.current?.disconnect();
      onRoomEnded();
    } catch (cause) { setError(cause instanceof Error ? cause.message : c.statusError); }
    finally { setBusy(""); setModal(null); }
  }

  async function leave() {
    setBusy("leave");
    try { await roomRef.current?.disconnect(); } finally { onClose(); }
  }

  async function toggleFullscreen() {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await stageRef.current?.requestFullscreen?.();
  }

  const feeds = useMemo(() => feedsFor(participants), [participants]);
  const videoFeeds = feeds.filter((feed) => feed.publication?.track);
  const defaultFeed = [...videoFeeds].sort((left, right) => {
    const priority = (feed: Feed) => moderator(feed.participant) ? feed.source === "screen" ? 0 : 1 : feed.source === "screen" ? 2 : 3;
    return priority(left) - priority(right);
  })[0] || null;
  const selectedFeed = videoFeeds.find((feed) => feed.identity === roomState.primary_identity && feed.source === roomState.primary_source) || defaultFeed;
  const showingBoard = roomState.board_visible === true && roomState.primary_source === "board";
  const secondaryFeeds = feeds.filter((feed) => feed.key !== selectedFeed?.key).slice(0, 9);
  const shownPeople = participants.filter((person) => {
    const identity = String(person.identity || "");
    const name = String(person.name || identity).toLowerCase();
    const hand = hands.some((item) => identity === `speaking-${item.user_id}`);
    return name.includes(search.toLowerCase()) && (filter === "all" || filter === "hand" && hand || filter === "speaking" && person.isSpeaking || filter === "requests" && mediaRequests.some((item) => identity === `speaking-${item.user_id}`));
  });
  const local = room?.localParticipant;
  const timerDuration = Math.max(0, Number(roomState.cue_card_duration_seconds || 0));
  const timerStart = roomState.cue_card_started_at ? new Date(roomState.cue_card_started_at).getTime() : NaN;
  const timerRemaining = Number.isNaN(timerStart) ? timerDuration : Math.max(0, timerDuration - Math.floor(((tick || timerStart) - timerStart) / 1000));
  const timerLabel = `${Math.floor(timerRemaining / 60).toString().padStart(2, "0")}:${(timerRemaining % 60).toString().padStart(2, "0")}`;
  const labelClass = "rounded-xl border border-[#E6EBF5] bg-white px-3 py-2 text-xs font-bold text-[#17233C] transition hover:bg-[#E9EEFF] disabled:opacity-45";
  const mainButton = "rounded-xl bg-[#1736E8] px-3 py-2 text-xs font-bold text-white transition hover:bg-[#1029B9] disabled:opacity-45";

  if (!portalReady) return null;
  return createPortal(
    <div className="fixed inset-0 z-[2147483000] flex h-[100dvh] w-screen flex-col overflow-hidden bg-[#F6F8FD] text-[#0F1B34]" role="dialog" aria-modal="true" aria-label={title} data-csp-style={JSON.stringify({ fontFamily: "ui-sans-serif, system-ui, sans-serif" })}>
      <header className="flex min-h-16 shrink-0 flex-wrap items-center gap-3 border-b border-[#E6EBF5] bg-white px-4 py-2 shadow-sm lg:flex-nowrap">
        <div className="flex shrink-0 items-center gap-2 text-[11px] font-semibold text-[#68758D]"><span className="h-1.5 w-1.5 rounded-full bg-[#98A4BA]" />{c.room} #{roomId.slice(-6)} <span className="text-[#A5AFBF]">·</span><span className={room ? "font-bold text-[#13A879]" : "font-bold text-[#E8A33D]"}>● {room ? c.connected : c.connecting}</span></div>
        <span className="hidden h-8 w-px bg-[#E6EBF5] lg:block" />
        <h1 className="min-w-0 flex-1 truncate text-base font-extrabold tracking-tight">{title}</h1>
        <button type="button" onClick={() => { setTab("participants"); setFilter("hand"); }} className="rounded-xl border border-[#E8A33D]/30 bg-[#E8A33D]/10 px-3 py-2 text-xs font-bold">{hands.length} {c.raised}</button>
        <span className="rounded-xl bg-[#F1F3FF] px-3 py-2 text-xs font-bold">{symbol("groups", 16)} {participants.length} {c.attendees}</span>
        <button type="button" disabled={!room || !!busy} onClick={() => void muteAll()} className={labelClass}>{symbol("volume_off", 16)} {c.muteAll}</button>
        <button type="button" onClick={() => setModal("end")} className="rounded-xl bg-[#DC5261] px-3 py-2 text-xs font-bold text-white hover:bg-[#C83D4D]">{symbol("call_end", 16)} {c.end}</button>
        <button type="button" onClick={() => void leave()} title={c.leave} className="rounded-xl border border-[#E6EBF5] p-2 hover:bg-[#F1F3FF]">{symbol("close", 18)}</button>
      </header>

      {error && <div role="alert" className="mx-4 mt-2 rounded-xl border border-[#DC5261]/30 bg-[#FFF1F2] px-4 py-2 text-xs font-semibold text-[#A72D3C]">{error}</div>}
      {notice && <button type="button" onClick={() => setNotice("")} className="mx-4 mt-2 self-start rounded-xl bg-[#E9EEFF] px-4 py-2 text-xs font-bold text-[#1736E8]">{notice} ×</button>}
      <RemoteAudio participants={participants} refreshKey={refreshKey} />

      <main className="flex min-h-0 flex-1 flex-col gap-3 p-3 lg:flex-row lg:gap-4 lg:p-4">
        <section className="flex min-h-0 min-w-0 flex-1 flex-col gap-3">
          <div ref={stageRef} className={`relative min-h-[260px] flex-1 overflow-hidden rounded-[20px] border border-[#253454] bg-[#070d1b] shadow-[0_6px_16px_rgba(15,27,52,.16)] ${wideStage ? "" : "lg:mx-auto lg:max-w-[1080px] lg:w-full"}`}>
            {showingBoard ? <div className="flex h-full w-full flex-col justify-center gap-5 overflow-auto bg-gradient-to-br from-[#121c38] to-[#091023] p-7 text-white"><button type="button" onClick={() => { setBoardText(roomState.board_text || ""); setModal("board"); }} className="self-start rounded-lg bg-[#1736E8] px-3 py-1 text-xs font-bold">{c.board} · {c.edit}</button><h2 className="text-2xl font-extrabold">{roomState.topic || title}</h2><p className="whitespace-pre-wrap text-lg leading-relaxed">{roomState.board_text}</p></div> : selectedFeed ? <VideoFeed feed={selectedFeed} large refreshKey={refreshKey} /> : <div className="grid h-full place-items-center p-6 text-center text-white"><div><div className="mb-3 text-5xl">◇</div><h2 className="text-lg font-bold">{connecting ? c.connecting : c.waiting}</h2><p className="mt-2 text-xs text-slate-300">{c.waitingHelp}</p></div></div>}
            <div className="pointer-events-none absolute left-3 top-3 flex max-w-[65%] items-center gap-2 text-[11px] font-bold text-white"><span className="rounded-md bg-[#1736E8] px-2.5 py-1">● {c.primary}</span><span className="truncate rounded-md bg-black/55 px-2.5 py-1">{showingBoard ? c.board : selectedFeed ? `${selectedFeed.name} · ${selectedFeed.source === "screen" ? c.screen : c.camera}` : c.waiting}</span></div>
            <div className="absolute right-3 top-3 flex gap-1.5"><span className="rounded-md bg-black/50 px-2 py-1 text-[11px] font-semibold text-[#13A879]">{c.live}</span><button type="button" title={c.fit} onClick={() => setWideStage((value) => !value)} className="rounded-md bg-black/55 p-1.5 text-white hover:bg-black/75">{symbol("fit_screen", 18)}</button><button type="button" title={c.fullscreen} onClick={() => void toggleFullscreen()} className="rounded-md bg-black/55 p-1.5 text-white hover:bg-black/75">{symbol("fullscreen", 18)}</button></div>
            {roomState.cue_card_visible && !showingBoard && <div className="absolute bottom-3 left-3 max-h-[45%] w-[min(330px,70%)] overflow-auto rounded-2xl border border-[#E6EBF5] bg-white/95 p-3 text-[#0F1B34] shadow-xl"><div className="flex items-center justify-between gap-2 border-b border-[#E6EBF5] pb-2 text-xs font-bold"><span>{symbol("article", 16)} {c.cue}</span><span className="rounded-md bg-[#FFF3E4] px-2 py-1 text-[#C07A13]">{timerLabel}</span></div><p className="mt-2 text-xs font-bold text-[#1736E8]">{roomState.cue_card_title || roomState.topic || title}</p>{(roomState.cue_card_prompts || []).length > 0 && <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px] text-[#68758D]">{(roomState.cue_card_prompts || []).map((prompt, index) => <li key={index}>{prompt}</li>)}</ul>}<div className="mt-2 flex gap-2"><button type="button" onClick={() => void updateState({ cue_card_started_at: new Date().toISOString(), cue_card_duration_seconds: timerDuration || 120 })} className="text-[11px] font-bold text-[#1736E8]">{timerStart ? c.resetTimer : c.startTimer}</button><button type="button" onClick={() => { setCueTitle(roomState.cue_card_title || ""); setCuePrompts((roomState.cue_card_prompts || []).join("\n")); setModal("cue"); }} className="text-[11px] font-bold text-[#68758D]">{c.edit}</button></div></div>}
          </div>

          <div className="flex shrink-0 gap-2 overflow-x-auto pb-1">
            {secondaryFeeds.length ? secondaryFeeds.map((feed) => <article key={feed.key} className="group relative w-44 shrink-0 overflow-hidden rounded-2xl border border-[#E6EBF5] bg-white p-1.5 shadow-sm sm:w-52"><div className="relative aspect-video overflow-hidden rounded-xl"><VideoFeed feed={feed} refreshKey={refreshKey} /><span className="absolute left-1.5 top-1.5 rounded bg-black/70 px-1.5 py-0.5 text-[10px] font-semibold text-white">{feed.source === "screen" ? c.screen : moderator(feed.participant) ? c.camera : c.participant}</span><button type="button" onClick={() => void updateState({ primary_identity: feed.identity, primary_source: feed.source, board_visible: false })} className="absolute right-1.5 top-1.5 rounded bg-[#1736E8] px-1.5 py-1 text-[10px] font-bold text-white opacity-100 transition sm:opacity-0 sm:group-hover:opacity-100 sm:focus:opacity-100">{c.setPrimary}</button></div><div className="flex items-center justify-between gap-1 px-1 pt-1.5 text-[11px]"><span className="min-w-0 truncate font-bold">{feed.name}</span><span className={feed.participant?.isSpeaking ? "text-[#13A879]" : "text-[#94A0B5]"}>{feed.participant?.isSpeaking ? "●" : "○"}</span></div></article>) : <div className="rounded-2xl border border-[#E6EBF5] bg-white px-4 py-3 text-xs text-[#68758D]">{c.waitingHelp}</div>}
          </div>

          <nav aria-label="Moderator controls" className="flex shrink-0 flex-wrap items-center justify-center gap-1.5 rounded-2xl border border-[#E6EBF5] bg-white p-2 shadow-sm">
            <button type="button" disabled={!room || !!busy} onClick={() => void toggleMedia("microphone")} className={local?.isMicrophoneEnabled ? mainButton : labelClass}>{symbol(local?.isMicrophoneEnabled ? "mic" : "mic_off")} {local?.isMicrophoneEnabled ? c.mute : c.unmute}</button>
            <button type="button" onClick={() => { void refreshDevices(); setDeviceMenu(deviceMenu === "audioinput" ? null : "audioinput"); }} title={c.microphone} className={labelClass}>⌄</button>
            <button type="button" disabled={!room || !!busy} onClick={() => void toggleMedia("camera")} className={local?.isCameraEnabled ? mainButton : labelClass}>{symbol(local?.isCameraEnabled ? "videocam" : "videocam_off")} {local?.isCameraEnabled ? c.camOn : c.camOff}</button>
            <button type="button" onClick={() => { void refreshDevices(); setDeviceMenu(deviceMenu === "videoinput" ? null : "videoinput"); }} title={c.camera} className={labelClass}>⌄</button>
            <button type="button" disabled={!room || !!busy} onClick={() => void toggleMedia("screen")} className={local?.isScreenShareEnabled ? mainButton : labelClass}>{symbol(local?.isScreenShareEnabled ? "stop_screen_share" : "screen_share")} {local?.isScreenShareEnabled ? c.stopShare : c.share}</button>
            <button type="button" onClick={() => { if (!roomState.cue_card_title && !roomState.cue_card_visible) { setCueTitle(""); setCuePrompts(""); setModal("cue"); } else void updateState({ cue_card_visible: !roomState.cue_card_visible }); }} className={roomState.cue_card_visible ? mainButton : labelClass}>{symbol("article")} {c.cue}</button>
            <button type="button" onClick={() => roomState.board_text ? void updateState({ board_visible: !showingBoard, primary_source: showingBoard ? "auto" : "board" }) : (setBoardText(""), setModal("board"))} className={showingBoard ? mainButton : labelClass}>{symbol("draw")} {c.board}</button>
            <button type="button" onClick={() => { setAnnouncementText(roomState.announcement || ""); setModal("announcement"); }} className={labelClass}>{symbol("campaign")} {c.note}</button>
            <button type="button" onClick={() => setModal("end")} className="rounded-xl bg-[#DC5261]/10 px-3 py-2 text-xs font-bold text-[#C73E4F] hover:bg-[#DC5261]/20">{symbol("power_settings_new")} {c.finish}</button>
          </nav>
          {deviceMenu && <div className="flex flex-wrap gap-2 rounded-xl border border-[#E6EBF5] bg-white p-2 text-xs"><strong className="self-center px-2">{c.device}</strong>{devices.filter((item) => item.kind === deviceMenu).map((item) => <button type="button" key={item.deviceId} onClick={() => void changeDevice(deviceMenu, item.deviceId)} className={labelClass}>{item.label || `${c.device} ${item.deviceId.slice(0, 6)}`}</button>)}{deviceMenu === "audioinput" && <button type="button" onClick={() => { setDeviceMenu("audiooutput"); void refreshDevices(); }} className={labelClass}>{c.audio} →</button>}{!devices.some((item) => item.kind === deviceMenu) && <span className="self-center text-[#68758D]">{c.noPeople}</span>}</div>}
          {!audioEnabled && <button type="button" onClick={() => void enableAudio()} className={mainButton}>{symbol("volume_up")} {c.audio}</button>}
        </section>

        <aside className="flex min-h-[300px] shrink-0 flex-col overflow-hidden rounded-[20px] border border-[#E6EBF5] bg-white shadow-sm lg:w-[360px] xl:w-[380px]">
          <div className="grid grid-cols-2 gap-1 bg-[#F1F3FF] p-2"><button type="button" onClick={() => setTab("participants")} className={`rounded-lg px-2 py-2 text-xs font-bold ${tab === "participants" ? "bg-white text-[#1736E8] shadow-sm" : "text-[#68758D]"}`}>{symbol("groups", 16)} {c.participants} ({participants.length})</button><button type="button" onClick={() => setTab("chat")} className={`rounded-lg px-2 py-2 text-xs font-bold ${tab === "chat" ? "bg-white text-[#1736E8] shadow-sm" : "text-[#68758D]"}`}>{symbol("chat", 16)} {c.chat}</button></div>
          {tab === "participants" ? <div className="flex min-h-0 flex-1 flex-col"><div className="space-y-2 border-b border-[#E6EBF5] p-3"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={c.search} className="w-full rounded-xl border border-[#E6EBF5] bg-[#F6F8FD] px-3 py-2 text-xs outline-none focus:border-[#1736E8]" /><div className="flex gap-1 overflow-x-auto">{(["all", "hand", "speaking", "requests"] as const).map((item) => <button type="button" key={item} onClick={() => setFilter(item)} className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${filter === item ? "bg-[#1736E8] text-white" : "bg-[#F1F3FF] text-[#68758D]"}`}>{item === "all" ? c.all : item === "hand" ? `${c.hands} (${hands.length})` : item === "speaking" ? c.speaking : `${c.requests} (${mediaRequests.length})`}</button>)}</div></div><div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">{shownPeople.length ? shownPeople.map((person) => { const identity = String(person.identity || ""); const name = String(person.name || identity); const raised = hands.some((hand) => identity === `speaking-${hand.user_id}`); const audio = publications(person).find((item) => item.track?.kind === "audio" && !item.isMuted); return <article key={identity} className="rounded-xl border border-[#E6EBF5] bg-[#FBFCFF] p-2.5"><div className="flex items-center gap-2"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#E9EEFF] text-xs font-bold text-[#1736E8]">{name.slice(0, 1).toUpperCase()}</span><div className="min-w-0 flex-1"><p className="truncate text-xs font-bold">{name}</p><p className="text-[10px] text-[#68758D]">{moderator(person) ? "Moderator" : raised ? `✋ ${c.hands}` : person.isSpeaking ? c.speaking : c.participant}</p></div><span className="text-[#68758D]">{symbol(audio ? "mic" : "mic_off", 16)}</span></div>{!person.isLocal && !moderator(person) && <div className="mt-2 flex flex-wrap gap-1"><button type="button" disabled={!!busy} onClick={() => void directAction("invite-to-speak", identity)} className={mainButton}>{c.invite}</button><button type="button" disabled={!!busy} onClick={() => audio ? void muteTrack(identity, String(audio.trackSid)) : void directAction("ask-to-unmute", identity)} className={labelClass}>{audio ? c.mute : c.askUnmute}</button><button type="button" disabled={!!busy} onClick={() => void removeParticipant(identity)} className="rounded-lg px-2 py-1 text-[11px] font-bold text-[#DC5261] hover:bg-red-50">{c.remove}</button></div>}</article>; }) : <p className="p-4 text-center text-xs text-[#68758D]">{c.noPeople}</p>}{mediaRequests.length > 0 && <div className="space-y-2 border-t border-[#E6EBF5] pt-3"><h3 className="text-xs font-bold">{c.permission} ({mediaRequests.length})</h3>{mediaRequests.map((request) => <article key={`${request.user_id}:${request.media_kind}`} className="rounded-xl bg-[#E9EEFF] p-2"><p className="text-xs font-bold">{request.display_name || `${c.participant} ${request.user_id}`} · {request.media_kind === "camera" ? c.camera : request.media_kind === "screen_share" ? c.screen : c.microphone}</p><div className="mt-2 flex gap-2"><button type="button" disabled={!!busy} onClick={() => void decide(request, true)} className={mainButton}>{c.approve}</button><button type="button" disabled={!!busy} onClick={() => void decide(request, false)} className={labelClass}>{c.deny}</button></div></article>)}</div>}</div></div> : <div className="flex min-h-0 flex-1 flex-col">{roomState.announcement && <div className="border-b border-[#CCD7FF] bg-[#E9EEFF] p-3"><div className="text-[10px] font-extrabold tracking-wide text-[#1736E8]">{c.pinned}</div><p className="mt-1 whitespace-pre-wrap text-xs leading-relaxed">{roomState.announcement}</p></div>}<div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">{messages.length ? messages.map((item) => <article key={item.id} className="flex gap-2"><span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full text-[10px] font-bold ${item.is_moderator ? "bg-[#1736E8] text-white" : "bg-[#E9EEFF] text-[#1736E8]"}`}>{item.display_name.slice(0, 1).toUpperCase()}</span><div className="min-w-0"><div className="flex items-center gap-1.5"><span className={`truncate text-[11px] font-bold ${item.is_moderator ? "text-[#1736E8]" : "text-[#0F1B34]"}`}>{item.display_name}</span><span className="text-[10px] text-[#94A0B5]">{messageTime(item.created_at, lang)}</span></div><p className={`mt-1 whitespace-pre-wrap break-words rounded-xl px-2.5 py-2 text-xs ${item.is_moderator ? "bg-[#1736E8] text-white" : "bg-[#F1F3FF] text-[#0F1B34]"}`}>{item.text}</p></div></article>) : <p className="p-4 text-center text-xs text-[#68758D]">{c.noMessages}</p>}</div><div className="border-t border-[#E6EBF5] p-2.5"><div className="mb-2 flex gap-1">{["👏", "🔥", "💎", "👍", "🎯"].map((emoji) => <button type="button" key={emoji} onClick={() => void react(emoji)} className="rounded-lg bg-[#F1F3FF] px-2 py-1 text-sm hover:bg-[#E9EEFF]">{emoji}</button>)}</div><form onSubmit={sendChat} className="flex gap-2"><input value={chatInput} onChange={(event) => setChatInput(event.target.value)} maxLength={500} placeholder={c.message} className="min-w-0 flex-1 rounded-xl border border-[#E6EBF5] bg-[#F6F8FD] px-3 py-2 text-xs outline-none focus:border-[#1736E8]" /><button type="submit" disabled={!chatInput.trim() || busy === "chat"} title={c.send} className={mainButton}>{symbol("send", 18)}</button></form></div></div>}
        </aside>
      </main>

      {modal && <div className="fixed inset-0 z-[2147483001] grid place-items-center bg-[#071127]/60 p-4" role="dialog" aria-modal="true"><div className="w-full max-w-lg rounded-3xl border border-[#E6EBF5] bg-white p-5 shadow-2xl"><h2 className="text-lg font-extrabold">{modal === "end" ? c.endConfirm : modal === "cue" ? c.cue : modal === "board" ? c.board : c.announcement}</h2>{modal === "end" ? <p className="mt-2 text-sm text-[#68758D]">{c.endHelp}</p> : modal === "cue" ? <div className="mt-3 space-y-3"><label className="block text-xs font-bold">{c.title}<input value={cueTitle} onChange={(event) => setCueTitle(event.target.value)} maxLength={240} className="mt-1 w-full rounded-xl border border-[#E6EBF5] p-2.5 text-sm" /></label><label className="block text-xs font-bold">{c.prompts}<textarea value={cuePrompts} onChange={(event) => setCuePrompts(event.target.value)} rows={5} className="mt-1 w-full rounded-xl border border-[#E6EBF5] p-2.5 text-sm" /></label></div> : <textarea value={modal === "board" ? boardText : announcementText} onChange={(event) => modal === "board" ? setBoardText(event.target.value) : setAnnouncementText(event.target.value)} maxLength={modal === "board" ? 4000 : 500} rows={5} className="mt-3 w-full rounded-xl border border-[#E6EBF5] p-2.5 text-sm" placeholder={modal === "board" ? c.boardText : c.announcement} />}<div className="mt-4 flex justify-end gap-2"><button type="button" onClick={() => setModal(null)} className={labelClass}>{c.cancel}</button><button type="button" disabled={!!busy} onClick={() => { if (modal === "end") void endLive(); else if (modal === "cue") void updateState({ cue_card_title: cueTitle.trim(), cue_card_prompts: cuePrompts.split("\n").map((item) => item.trim()).filter(Boolean).slice(0, 5), cue_card_visible: true, cue_card_duration_seconds: 120 }).then((ok) => { if (ok) setModal(null); }); else if (modal === "board") void updateState({ board_text: boardText.trim(), board_visible: true, primary_source: "board" }).then((ok) => { if (ok) setModal(null); }); else void updateState({ announcement: announcementText.trim() }).then((ok) => { if (ok) setModal(null); }); }} className={modal === "end" ? "rounded-xl bg-[#DC5261] px-4 py-2 text-xs font-bold text-white" : mainButton}>{modal === "end" ? c.end : c.save}</button></div></div></div>}
    </div>, document.body,
  );
}
