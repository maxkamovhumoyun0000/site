"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { resolveLocale, useWebT } from "./web-i18n";
import { SharedTestEditor } from "./shared-test-editor";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
const DIAMONDVOY_AVATAR = "/diamondvoy-avatar.jpg";
const DIAMONDVOY_THINKING_VIDEO = "/diamondvoy-thinking.mp4";
let diamondvoyThinkingAudioUnlocked = false;

function unlockDiamondvoyThinkingAudio() {
  diamondvoyThinkingAudioUnlocked = true;
}

function playDiamondvoyThinkingVideo(video: HTMLVideoElement | null) {
  if (!video) return;
  try {
    video.volume = 1;
    video.muted = !diamondvoyThinkingAudioUnlocked;
    const playPromise = video.play();
    if (playPromise && typeof playPromise.catch === "function") {
      playPromise.catch(() => {
        video.muted = true;
        video.play().catch(() => null);
      });
    }
  } catch {
    try {
      video.muted = true;
      video.play().catch(() => null);
    } catch {
      // Browser denied playback; the chat stream still continues.
    }
  }
}

const MAX_IMAGES = 3;
const MAX_IMAGE_SIZE = 10 * 1024 * 1024;
const IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

type ActivePane = "diamondvoy" | "feedback" | null;

type ChatAttachment = {
  id?: number;
  url: string;
  mime_type?: string | null;
  size_bytes?: number;
};

type DiamondvoyChat = {
  id: number;
  title: string;
  last_message_preview?: string | null;
  updated_at?: string | null;
  created_at?: string | null;
  expires_at?: string | null;
  pinned_at?: string | null;
  pinned?: boolean;
};

type DiamondvoyMessage = {
  id: number;
  role: "user" | "assistant" | "system";
  content: string;
  created_at?: string | null;
  attachments: ChatAttachment[];
  streaming?: boolean;
  failed?: boolean;
  retryMessage?: string;
  retryImages?: string[];
};

type FeedbackMessage = {
  id: number;
  sender_user_id: number;
  sender_role: string;
  text: string;
  is_anonymous_choice: boolean;
  created_at?: string | null;
  attachments: ChatAttachment[];
};

type FeedbackThread = {
  id: number;
  user_id: number;
  status: string;
  updated_at?: string | null;
  created_at?: string | null;
  user?: {
    id: number;
    full_name?: string;
    role?: string;
    group?: string | null;
    dcoin_balance?: number | null;
    dpoint_balance?: number | null;
    avatar_url?: string | null;
    login_id?: string | null;
  };
};

type FeedbackDetail = {
  thread: FeedbackThread;
  messages: FeedbackMessage[];
};

type FeedbackThreadSummary = {
  id: number;
  thread_id: number;
  user_id: number;
  user_name: string;
  role: string;
  status: string;
  last_message_preview?: string | null;
  updated_at?: string | null;
};

type UploadPreview = {
  url: string;
  preview: string;
  name: string;
};

type PreviewMedia = {
  type: "image" | "video";
  src: string;
  title: string;
} | null;

function cx(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

function apiUrl(pathOrUrl: string) {
  const raw = String(pathOrUrl || "");
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw) || raw.startsWith("data:") || raw.startsWith("blob:")) return raw;
  if (raw.startsWith("/")) return `${API_BASE}${raw}`;
  return `${API_BASE}/${raw}`;
}

function formatWhen(raw?: string | null) {
  if (!raw) return "";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return String(raw);
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

function chatTimeValue(raw?: string | null) {
  const value = raw ? new Date(raw).getTime() : 0;
  return Number.isFinite(value) ? value : 0;
}

function sortDiamondvoyChats(chats: DiamondvoyChat[]) {
  return [...chats].sort((a, b) => {
    const pinnedDelta = Number(Boolean(b.pinned_at || b.pinned)) - Number(Boolean(a.pinned_at || a.pinned));
    if (pinnedDelta) return pinnedDelta;
    const pinTimeDelta = chatTimeValue(b.pinned_at) - chatTimeValue(a.pinned_at);
    if (pinTimeDelta) return pinTimeDelta;
    const updateDelta =
      chatTimeValue(b.updated_at || b.created_at) - chatTimeValue(a.updated_at || a.created_at);
    if (updateDelta) return updateDelta;
    return b.id - a.id;
  });
}

function normalizeChat(raw: any): DiamondvoyChat | null {
  const id = Number(raw?.id || raw?.chat_id || 0);
  if (!id) return null;
  return {
    id,
    title: String(raw?.title || "").trim() || "Yangi chat",
    last_message_preview: raw?.last_message_preview || null,
    updated_at: raw?.updated_at || null,
    created_at: raw?.created_at || null,
    expires_at: raw?.expires_at || null,
    pinned_at: raw?.pinned_at || null,
    pinned: Boolean(raw?.pinned || raw?.pinned_at),
  };
}

function normalizeAttachments(raw: any): ChatAttachment[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => ({
      id: Number(item?.id || 0) || undefined,
      url: String(item?.url || item?.file_url || "").trim(),
      mime_type: item?.mime_type || null,
      size_bytes: Number(item?.size_bytes || 0) || 0,
    }))
    .filter((item) => item.url);
}

function normalizeAiMessage(raw: any, fallbackId: number): DiamondvoyMessage {
  const role = String(raw?.role || "assistant").toLowerCase();
  return {
    id: Number(raw?.id || fallbackId) || fallbackId,
    role: role === "user" ? "user" : role === "system" ? "system" : "assistant",
    content: String(raw?.content || raw?.text || ""),
    created_at: raw?.created_at || null,
    attachments: normalizeAttachments(raw?.attachments),
  };
}

function normalizeFeedbackMessage(raw: any): FeedbackMessage {
  return {
    id: Number(raw?.id || 0),
    sender_user_id: Number(raw?.sender_user_id || 0),
    sender_role: String(raw?.sender_role || ""),
    text: String(raw?.text || raw?.message_text || ""),
    is_anonymous_choice: Boolean(raw?.is_anonymous_choice),
    created_at: raw?.created_at || null,
    attachments: normalizeAttachments(raw?.attachments),
  };
}

function parseError(err: unknown, fallback: string) {
  const message = String(err instanceof Error ? err.message : err || "").trim();
  if (!message) return fallback;
  try {
    const parsed = JSON.parse(message) as { detail?: string };
    return String(parsed?.detail || fallback);
  } catch {
    return message;
  }
}

async function consumeSse(
  response: Response,
  handlers: {
    onThinking?: () => void;
    onDelta?: (content: string) => void;
    onDone?: (content: string, meta?: { chat_title?: string }) => void;
  },
) {
  if (!response.ok) {
    const raw = await response.text().catch(() => "");
    try {
      const parsed = JSON.parse(raw || "{}") as { detail?: string };
      throw new Error(parsed?.detail || raw || "Stream failed");
    } catch {
      throw new Error(raw || "Stream failed");
    }
  }
  if (!response.body) return "";
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let finalText = "";

  const process = (block: string) => {
    let eventType = "";
    let data = "";
    for (const line of block.replace(/\r/g, "").split("\n")) {
      if (line.startsWith("event:")) eventType = line.slice(6).trim();
      if (line.startsWith("data:")) data += line.slice(5).trim();
    }
    if (!eventType) return false;
    if (eventType === "status") {
      handlers.onThinking?.();
      return false;
    }
    if (eventType === "error") {
      try {
        const parsed = JSON.parse(data || "{}") as { message?: string };
        throw new Error(parsed?.message || "Stream failed");
      } catch (err) {
        throw err instanceof Error ? err : new Error("Stream failed");
      }
    }
    if (eventType === "delta") {
      const parsed = JSON.parse(data || "{}") as { content?: string; delta?: string };
      finalText = typeof parsed.content === "string" ? parsed.content : `${finalText}${parsed.delta || ""}`;
      handlers.onDelta?.(finalText);
      return false;
    }
    if (eventType === "done") {
      const parsed = JSON.parse(data || "{}") as { content?: string; chat_title?: string };
      finalText = String(parsed.content || finalText || "");
      handlers.onDone?.(finalText, { chat_title: parsed.chat_title });
      return true;
    }
    return false;
  };

  while (true) {
    const chunk = await reader.read();
    if (chunk.done) break;
    buffer += decoder.decode(chunk.value, { stream: true }).replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    let sep = buffer.indexOf("\n\n");
    while (sep !== -1) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      if (process(block)) return finalText;
      sep = buffer.indexOf("\n\n");
    }
  }
  if (buffer.trim()) process(buffer.trim());
  handlers.onDone?.(finalText);
  return finalText;
}

function DiamondvoyAvatar({
  thinking,
  onPreview,
  thinkingLabel = "Diamondvoy is Thinking",
  profileLabel = "Diamondvoy",
}: {
  thinking?: boolean;
  onPreview?: (media: NonNullable<PreviewMedia>) => void;
  thinkingLabel?: string;
  profileLabel?: string;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  useEffect(() => {
    if (!videoRef.current) return;
    const video = videoRef.current;
    if (!thinking) {
      video.pause();
      video.currentTime = 0;
      return;
    }
    video.currentTime = 0;
    video.load();
    playDiamondvoyThinkingVideo(video);
    return () => {
      video.pause();
    };
  }, [thinking]);

  return (
    <button
      type="button"
      onClick={() =>
        onPreview?.({
          type: thinking ? "video" : "image",
          src: thinking ? DIAMONDVOY_THINKING_VIDEO : DIAMONDVOY_AVATAR,
          title: thinking ? thinkingLabel : profileLabel,
        })
      }
      className="diamondvoy-avatar-button w-10 h-10 rounded-xl overflow-hidden border border-line dark:border-white/15 bg-surface-soft dark:bg-white/5 shrink-0"
      aria-label={thinking ? thinkingLabel : profileLabel}
    >
      {thinking ? (
        <video
          ref={videoRef}
          src={DIAMONDVOY_THINKING_VIDEO}
          className="diamondvoy-thinking-video w-full h-full object-cover"
          autoPlay
          loop
          muted={!diamondvoyThinkingAudioUnlocked}
          playsInline
          preload="auto"
          disablePictureInPicture
          onCanPlay={() => playDiamondvoyThinkingVideo(videoRef.current)}
        />
      ) : (
        <img src={DIAMONDVOY_AVATAR} alt={profileLabel} className="w-full h-full object-cover" loading="lazy" />
      )}
    </button>
  );
}

function DiamondVoyHomeworkWizard({
  chatId,
  apiFetch,
  onSuccess,
}: {
  chatId: number;
  apiFetch: (path: string, options?: any) => Promise<any>;
  onSuccess: () => void;
}) {
  const tt = useWebT();
  const [state, setState] = useState<any>(null);
  const [targets, setTargets] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [selTarget, setSelTarget] = useState("");
  const [contentTypes, setContentTypes] = useState<string[]>([]);
  const [deadline, setDeadline] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [manualTest, setManualTest] = useState<any[]>([]);
  
  // AI Gen fields
  const [testMode, setTestMode] = useState<"ai" | "manual" | null>(null);
  const [topic, setTopic] = useState("");
  const [qCount, setQCount] = useState("5");
  const [modifyInstruction, setModifyInstruction] = useState("");
  const [rawTestText, setRawTestText] = useState("");
  useEffect(() => {
    let active = true;
    setLoading(true);
    apiFetch(`/chats/diamondvoy/${chatId}/homework/start`, { method: "POST" })
      .then((res) => {
        if (!active) return;
        setState(res.state);
        setTargets(res.targets || []);
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message || "Failed to start wizard");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [chatId, apiFetch]);

  async function handleAction(action: string, payload: any = {}) {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch(`/chats/diamondvoy/${chatId}/homework/${action}`, {
        method: "POST",
        body: { action, ...payload },
      });
      if (action === "send") {
        onSuccess();
      } else {
        setState(res.state);
        if (action === "parse-test" && res.state.manual_test) {
          setManualTest(res.state.manual_test);
        }
      }
    } catch (err: any) {
      setError(err.message || "Error performing action");
    } finally {
      setLoading(false);
    }
  }

  if (loading && !state) {
    return <div className="p-4 text-center text-sm text-ink-500">Loading wizard...</div>;
  }

  if (!state) {
    return <div className="p-4 text-center text-sm text-red-500">{error || "Wizard failed"}</div>;
  }

  return (
    <div className="w-[320px] sm:w-[400px] border border-cyan-200 dark:border-cyan-800/50 rounded-2xl bg-white dark:bg-[#1A2332] shadow-lg overflow-hidden flex flex-col">
      <div className="px-4 py-3 bg-cyan-50 dark:bg-cyan-900/20 border-b border-cyan-100 dark:border-cyan-800/30 flex justify-between items-center">
        <h4 className="font-bold text-cyan-800 dark:text-cyan-300">
          {tt("chat.wizard.title", "Uy vazifasi berish")}
        </h4>
      </div>
      <div className="p-4 space-y-4 text-sm">
        {error && <div className="text-red-500 font-medium">{error}</div>}
        
        {state.step === "target" && (
          <div className="space-y-2">
            <label className="block font-medium">{tt("chat.wizard.selectTarget", "Guruh yoki o'quvchini tanlang")}</label>
            <select
              value={selTarget}
              onChange={(e) => setSelTarget(e.target.value)}
              className="w-full px-3 py-2 border border-line dark:border-white/10 rounded-xl bg-transparent"
            >
              <option value="">-- Tanlang --</option>
              {targets.map((t, idx) => (
                <option key={idx} value={JSON.stringify(t)}>
                  {t.type === "group" ? `Guruh: ${t.name}` : `O'quvchi: ${t.name} (${t.label})`}
                </option>
              ))}
            </select>
            <button
              disabled={!selTarget || loading}
              onClick={() => {
                const t = JSON.parse(selTarget);
                handleAction("action", {
                  action: "select_target",
                  target_group_id: t.type === "group" ? t.id : null,
                  target_student_id: t.type === "student" ? t.id : null,
                  target_booking_id: t.type === "student" ? t.booking_id : null,
                });
              }}
              className="mt-2 w-full px-4 py-2 bg-cyan-500 text-white font-bold rounded-xl disabled:opacity-50"
            >
              {tt("chat.wizard.next", "Keyingisi")}
            </button>
          </div>
        )}

        {state.step === "content_types" && (
          <div className="space-y-3">
            <label className="block font-medium">{tt("chat.wizard.contentTypes", "Vazifa turlarini belgilang")}</label>
            <div className="flex flex-col gap-2">
              {["text", "image", "file", "voice", "voiceroom", "test"].map((ct) => (
                <label key={ct} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={contentTypes.includes(ct)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        if (ct === "voiceroom") {
                          setContentTypes(["voiceroom"]);
                        } else {
                          setContentTypes([...contentTypes.filter((x) => x !== "voiceroom"), ct]);
                        }
                      } else {
                        setContentTypes(contentTypes.filter((x) => x !== ct));
                      }
                    }}
                    className="w-4 h-4 rounded text-cyan-500"
                  />
                  <span>{ct.replace("_", " ").toUpperCase()}</span>
                </label>
              ))}
            </div>
            <button
              disabled={contentTypes.length === 0 || loading}
              onClick={() => handleAction("action", { action: "set_content_types", content_types: contentTypes })}
              className="w-full px-4 py-2 bg-cyan-500 text-white font-bold rounded-xl disabled:opacity-50"
            >
              {tt("chat.wizard.next", "Keyingisi")}
            </button>
          </div>
        )}

        {state.step === "details" && (
          <div className="space-y-3">
            <div>
              <label className="block font-medium mb-1">{tt("chat.wizard.homeworkTitle", "Sarlavha")}</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Uy vazifasi nomi"
                className="w-full px-3 py-2 border border-line dark:border-white/10 rounded-xl bg-transparent"
              />
            </div>
            <div>
              <label className="block font-medium mb-1">{tt("chat.wizard.deadline", "Muddat")}</label>
              <input
                type="datetime-local"
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
                className="w-full px-3 py-2 border border-line dark:border-white/10 rounded-xl bg-transparent"
              />
            </div>
            <div>
              <label className="block font-medium mb-1">{tt("chat.wizard.desc", "Tavsif")}</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-line dark:border-white/10 rounded-xl bg-transparent"
              />
            </div>
            <button
              disabled={!deadline || !title.trim() || !description.trim() || loading}
              onClick={() => handleAction("action", { action: "set_details", deadline_iso: new Date(deadline).toISOString(), title, description })}
              className="w-full px-4 py-2 bg-cyan-500 text-white font-bold rounded-xl disabled:opacity-50"
            >
              {tt("chat.wizard.next", "Keyingisi")}
            </button>
          </div>
        )}

        {state.step === "test" && (
          <div className="space-y-3">
            {!testMode && (
              <div className="space-y-3 text-center">
                <p className="font-medium">Testni qanday yaratmoqchisiz?</p>
                <div className="flex flex-col gap-2">
                  <button onClick={() => setTestMode("manual")} className="w-full px-4 py-2 border border-cyan-500 text-cyan-600 dark:text-cyan-400 font-bold rounded-xl">O'zim kiritaman</button>
                  <button onClick={() => setTestMode("ai")} className="w-full px-4 py-2 bg-purple-500 text-white font-bold rounded-xl">AI orqali yaratish</button>
                </div>
              </div>
            )}

            {testMode === "ai" && (
              <div className="space-y-3">
                {state.manual_test && state.manual_test.length > 0 ? (
                  <div className="space-y-3">
                    <div className="max-h-[300px] overflow-y-auto bg-surface-soft dark:bg-white/5 p-3 rounded-xl text-xs space-y-4 border border-line dark:border-white/10">
                      {state.manual_test.map((q: any, i: number) => (
                        <div key={i} className="mb-2">
                          <div className="font-semibold text-sm"><strong>{i+1}.</strong> {q.question}</div>
                          <div className="ml-2 mt-1 space-y-1">
                            {q.options?.map((opt: string, optIdx: number) => (
                              <div key={optIdx} className={optIdx === q.correct_option_index ? "text-green-600 dark:text-green-400 font-bold bg-green-500/10 px-2 py-0.5 rounded" : "text-ink-600 dark:text-slate-300 px-2 py-0.5"}>
                                {String.fromCharCode(65 + optIdx)}) {opt}
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                    <div>
                      <input type="text" value={modifyInstruction} onChange={(e) => setModifyInstruction(e.target.value)} placeholder="Nimasini o'zgartiramiz? (Masalan: osonroq qiling)" className="w-full px-3 py-2 border rounded-xl bg-transparent border-line dark:border-white/10 text-sm" />
                    </div>
                    <div className="flex gap-2">
                      <button disabled={!modifyInstruction.trim() || loading} onClick={() => { handleAction("modify-test", { instruction: modifyInstruction }); setModifyInstruction(""); }} className="flex-1 px-4 py-2 bg-yellow-500 text-white font-bold rounded-xl disabled:opacity-50 text-sm">O'zgartirish</button>
                      <button disabled={loading} onClick={() => handleAction("action", { action: "accept_ai_test", manual_test: state.manual_test })} className="flex-1 px-4 py-2 bg-green-500 text-white font-bold rounded-xl disabled:opacity-50 text-sm">Davom etish</button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <label className="block font-medium">Mavzu</label>
                    <input type="text" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Masalan: Past Simple" className="w-full px-3 py-2 border rounded-xl bg-transparent border-line dark:border-white/10" />
                    <label className="block font-medium mt-2">Savollar soni</label>
                    <input type="number" value={qCount} onChange={(e) => setQCount(e.target.value)} className="w-full px-3 py-2 border rounded-xl bg-transparent border-line dark:border-white/10" />
                    <button
                      disabled={!topic.trim() || loading}
                      onClick={() => handleAction("generate-test", { topic, question_count: Number(qCount) })}
                      className="mt-2 w-full px-4 py-2 bg-purple-500 text-white font-bold rounded-xl disabled:opacity-50"
                    >
                      {tt("chat.wizard.generateTest", "Test yaratish")}
                    </button>
                  </div>
                )}
              </div>
            )}

            {testMode === "manual" && (
              <div className="space-y-3">
                {manualTest && manualTest.length > 0 ? (
                  <div className="space-y-2">
                    <SharedTestEditor questions={manualTest} onChange={setManualTest} />
                    <button
                      disabled={loading}
                      onClick={() => handleAction("action", { action: "set_manual_test", manual_test: manualTest })}
                      className="w-full px-4 py-2 bg-cyan-500 text-white font-bold rounded-xl disabled:opacity-50"
                    >
                      {tt("chat.wizard.next", "Keyingisi")}
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <label className="block font-medium">Tayyor testni shu yerga tashlang (Pasting)</label>
                    <textarea 
                      value={rawTestText}
                      onChange={(e) => setRawTestText(e.target.value)}
                      rows={6}
                      placeholder="Masalan:&#10;1. 2+2 nechchi?&#10;A) 3&#10;B) 4&#10;C) 5&#10;D) 6"
                      className="w-full px-3 py-2 border rounded-xl bg-transparent border-line dark:border-white/10 text-sm"
                    />
                    <button
                      disabled={!rawTestText.trim() || loading}
                      onClick={() => handleAction("parse-test", { raw_test_text: rawTestText })}
                      className="w-full px-4 py-2 bg-purple-500 text-white font-bold rounded-xl disabled:opacity-50"
                    >
                      AI orqali ajratib olish
                    </button>
                    <button
                      disabled={loading}
                      onClick={() => setManualTest([{ question: "", options: ["", "", "", ""], correct_option_index: 0 }])}
                      className="w-full px-4 py-2 border border-line dark:border-white/10 text-ink-900 font-medium rounded-xl text-sm"
                    >
                      O'zim qo'lda kiritaman
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {state.step === "preview" && (
          <div className="space-y-3">
            <h5 className="font-bold text-center">Preview</h5>
            <div className="bg-surface-soft dark:bg-white/5 p-3 rounded-xl border border-line dark:border-white/10 text-xs space-y-1">
              <p><strong>Target:</strong> {state.target_type === "group" ? `Group #${state.target_id}` : `Student #${state.target_id}`}</p>
              <p><strong>Deadline:</strong> {new Date(state.deadline_iso).toLocaleString()}</p>
              <p><strong>Content:</strong> {state.content_types?.join(", ")}</p>
              <p><strong>Desc:</strong> {state.description}</p>
              {state.manual_test && <p><strong>Test Questions:</strong> {state.manual_test.length}</p>}
            </div>
            {state.voiceroom_groups && state.voiceroom_groups.length > 0 && (
              <div className="space-y-2">
                <h6 className="font-bold text-xs text-center">VoiceRoom Pairings</h6>
                <div className="max-h-[150px] overflow-y-auto space-y-1">
                  {state.voiceroom_groups.map((vg: any, idx: number) => (
                    <div key={idx} className="bg-white/5 p-2 rounded border border-white/10 text-xs">
                      {vg.student1_name} + {vg.student2_name || "(None)"} {vg.student3_name ? ` + ${vg.student3_name}` : ""}
                    </div>
                  ))}
                </div>
                <button
                  disabled={loading}
                  onClick={() => handleAction("action", { action: "randomise_voiceroom" })}
                  className="w-full px-3 py-1.5 border border-cyan-500 text-cyan-500 font-bold rounded-lg disabled:opacity-50 text-xs"
                >
                  Randomise Pairs
                </button>
              </div>
            )}
            <button
              disabled={loading}
              onClick={() => handleAction("send")}
              className="w-full px-4 py-2 bg-green-500 text-white font-bold rounded-xl disabled:opacity-50"
            >
              {tt("chat.wizard.send", "Vazifani yuborish")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Admin: Add Students from XLSX Wizard ────────────────────────────────────
type AddStudentsWizardState = {
  step: "select_type" | "upload" | "preview" | "done";
  account_type: "student" | "accountless" | null;
  parent_phone?: string | null;
  free_access?: boolean;
  subject?: string;
  group_id?: number;
  joined_at?: string | null;
  students: { first_name: string; last_name: string; phone: string; parent_phone?: string | null }[];
  created: any[];
  errors: string[];
};

function DiamondVoyAddStudentsWizard({
  chatId,
  apiFetch,
  onSuccess,
}: {
  chatId: number;
  apiFetch: (path: string, options?: any) => Promise<any>;
  onSuccess: () => void;
}) {
  const [state, setState] = useState<AddStudentsWizardState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ created: any[]; failed: any[] } | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    apiFetch(`/chats/diamondvoy/${chatId}/add-students/state`)
      .then((res: any) => { 
        if (active) {
          if (res.state?.step && res.state.step !== "done") {
            setState(res.state);
          } else {
            // Start fresh
            apiFetch(`/chats/diamondvoy/${chatId}/add-students/start`, { method: "POST" })
              .then((r: any) => { if (active) setState(r.state); })
              .catch((err: any) => { if (active) setError(err.message || "Wizard ishga tushmadi"); });
          }
        }
      })
      .catch((err: any) => { if (active) setError(err.message || "Wizard holati yuklanmadi"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [chatId, apiFetch]);

  // selectType is handled by WizardTypeStep sub-component
  // which calls /add-students/select-type with all extra fields

  async function uploadFile(file: File) {
    setLoading(true); setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const token = typeof window !== "undefined" ? localStorage.getItem("diamond_token") : null;
      const resp = await fetch(
        `${API_BASE}/chats/diamondvoy/${chatId}/add-students/upload-xlsx`,
        { method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, body: formData },
      );
      if (!resp.ok) {
        const errBody = await resp.json().catch(() => ({}));
        throw new Error(errBody?.detail || "Fayl yuklanmadi");
      }
      const res = await resp.json();
      setState(res.state);
    } catch (err: any) { setError(err.message || "Xatolik"); }
    finally { setLoading(false); }
  }

  async function confirm() {
    setLoading(true); setError("");
    try {
      const res = await apiFetch(`/chats/diamondvoy/${chatId}/add-students/confirm`, { method: "POST" });
      setState(res.state);
      setResult({ created: res.created || [], failed: res.failed || [] });
      onSuccess();
    } catch (err: any) { setError(err.message || "Xatolik"); }
    finally { setLoading(false); }
  }

  async function reset() {
    setLoading(true); setError(""); setResult(null);
    try {
      const res = await apiFetch(`/chats/diamondvoy/${chatId}/add-students/start`, { method: "POST" });
      setState(res.state);
    } catch { setState(null); }
    finally { setLoading(false); }
  }

  if (loading && !state) return <div className="p-4 text-center text-sm text-ink-500">Yuklanmoqda...</div>;
  if (!state)            return <div className="p-4 text-center text-sm text-red-500">{error || "Wizard yuklanmadi"}</div>;

  const typeLabel = state.account_type === "accountless" ? "Hisob raqamsiz" : "Hisob bilan";
  const createActionText = state.account_type === "accountless"
    ? `✅ ${state.students.length} ta student qo'shish`
    : `✅ ${state.students.length} ta hisob yaratish`;
  const doneText = state.account_type === "accountless"
    ? `${result?.created.length || 0} ta student ro'yxatga olindi!`
    : `${result?.created.length || 0} ta hisob yaratildi!`;

  return (
    <div className="w-full border border-emerald-200 dark:border-emerald-800/50 rounded-2xl bg-white dark:bg-[#1A2332] shadow-lg overflow-hidden flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 bg-emerald-50 dark:bg-emerald-900/20 border-b border-emerald-100 dark:border-emerald-800/30 flex justify-between items-center">
        <h4 className="font-bold text-emerald-800 dark:text-emerald-300">👥 Yangi o'quvchilar qo'shish</h4>
        <div className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
          {state.step === "select_type" && "1/3 - Tur tanlash"}
          {state.step === "upload"      && "2/3 - Fayl yuklash"}
          {state.step === "preview"     && "3/3 - Tasdiqlash"}
          {state.step === "done"        && "✅ Yakunlandi"}
        </div>
      </div>

      <div className="p-4 space-y-4 text-sm">
        {error && <div className="text-red-500 font-medium bg-red-50 dark:bg-red-900/20 rounded-xl px-3 py-2">{error}</div>}

        {/* ── Step 1: Select type + extra fields ───────────────────── */}
        {state.step === "select_type" && (
          <WizardTypeStep
            chatId={chatId}
            apiFetch={apiFetch}
            loading={loading}
            onDone={(newState) => setState(newState)}
            setLoading={setLoading}
            setError={setError}
          />
        )}

        {/* ── Step 2: Upload xlsx ─────────────────────────────── */}
        {state.step === "upload" && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-1.5 text-xs bg-emerald-50 dark:bg-emerald-900/20 rounded-lg px-3 py-2">
              <span className="font-bold text-emerald-700 dark:text-emerald-300">{typeLabel}</span>
            </div>
            <p className="text-ink-600 dark:text-slate-300">Excel yoki Word faylini (.xlsx, .docx) yuklang:</p>
            <div
              className="bg-surface-soft dark:bg-white/5 rounded-xl border-2 border-dashed border-line dark:border-white/15 p-5 text-center cursor-pointer hover:border-emerald-400 dark:hover:border-emerald-600 transition-colors group"
              onClick={() => !loading && fileInputRef.current?.click()}
            >
              <div className="text-3xl mb-2 group-hover:scale-110 transition-transform">📊</div>
              <p className="text-xs text-ink-500 dark:text-slate-400 mb-1">Ustunlar: <strong>Ism/Familiya | 1-telefon student | 2-telefon ota-ona</strong></p>
              <p className="text-[11px] text-ink-400 dark:text-slate-500 mb-3">Sarlavha bo'lsa ham, bo'lmasa ham avtomatik ajratiladi</p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.docx"
                className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadFile(f); e.target.value = ""; }}
              />
              <button
                disabled={loading}
                onClick={(ev) => { ev.stopPropagation(); fileInputRef.current?.click(); }}
                className="px-5 py-2 bg-emerald-500 text-white font-bold rounded-xl disabled:opacity-50 hover:bg-emerald-600 transition-colors text-sm"
              >
                {loading ? "Yuklanmoqda..." : "📂 Fayl tanlash"}
              </button>
            </div>
            <button onClick={reset} className="text-xs text-ink-400 underline">← Orqaga</button>
          </div>
        )}

        {/* ── Step 3: Preview table ───────────────────────────── */}
        {state.step === "preview" && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-1.5 text-xs bg-emerald-50 dark:bg-emerald-900/20 rounded-lg px-3 py-2">
              <span className="font-bold text-emerald-700 dark:text-emerald-300">{typeLabel}</span>
              <span className="text-emerald-400">·</span>
              <span className="font-bold">{state.students.length}</span>
              <span className="text-ink-500">ta o'quvchi topildi</span>
            </div>
            {state.errors.length > 0 && (
              <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700/30 rounded-xl px-3 py-2 text-xs text-amber-700 dark:text-amber-300 space-y-0.5">
                <p className="font-bold mb-1">⚠️ {state.errors.length} ta xatolik:</p>
                {state.errors.slice(0, 5).map((e, i) => <p key={i}>{e}</p>)}
                {state.errors.length > 5 && <p className="opacity-60">...va yana {state.errors.length - 5} ta</p>}
              </div>
            )}
            {state.students.length > 0 && (
              <div className="max-h-[240px] overflow-y-auto rounded-xl border border-line dark:border-white/10 bg-surface-soft dark:bg-white/5">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-surface-soft dark:bg-navy-900 border-b border-line dark:border-white/10">
                    <tr>
                      <th className="px-3 py-2 text-left text-ink-400 font-semibold">#</th>
                      <th className="px-3 py-2 text-left font-semibold">Ism</th>
                      <th className="px-3 py-2 text-left font-semibold">Familiya</th>
                      <th className="px-3 py-2 text-left font-semibold">Telefon</th>
                      <th className="px-3 py-2 text-left font-semibold">Ota-ona</th>
                    </tr>
                  </thead>
                  <tbody>
                    {state.students.map((st, i) => (
                      <tr key={i} className="border-t border-line dark:border-white/5 hover:bg-white/40 dark:hover:bg-white/5 transition-colors">
                        <td className="px-3 py-1.5 text-ink-400">{i + 1}</td>
                        <td className="px-3 py-1.5 font-medium">{st.first_name}</td>
                        <td className="px-3 py-1.5">{st.last_name}</td>
                        <td className="px-3 py-1.5 font-mono text-[11px] text-ink-500">{st.phone}</td>
                        <td className="px-3 py-1.5 font-mono text-[11px] text-ink-500">{st.parent_phone || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="flex gap-2">
              <button onClick={reset} disabled={loading}
                className="flex-1 px-4 py-2 border border-line dark:border-white/15 rounded-xl text-ink-700 dark:text-white font-medium disabled:opacity-50 hover:bg-surface-soft transition-colors text-sm">
                ← Orqaga
              </button>
              <button onClick={confirm} disabled={loading || state.students.length === 0}
                className="flex-[2] px-4 py-2 bg-emerald-500 text-white font-bold rounded-xl disabled:opacity-50 hover:bg-emerald-600 transition-colors text-sm">
                {loading ? "Yaratilmoqda..." : createActionText}
              </button>
            </div>
          </div>
        )}

        {/* Step 4 – Done / result */}
        {state.step === "done" && result && (
          <div className="space-y-3">
            <div className="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-700/30 rounded-xl px-4 py-3 text-center">
              <div className="text-2xl mb-1">🎉</div>
              <p className="font-bold text-emerald-700 dark:text-emerald-300 text-base">{doneText}</p>
              {result.failed.length > 0 && (
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">{result.failed.length} ta xatolik bor</p>
              )}
            </div>
            {/* Created list with login/password for student type */}
            {result.created.length > 0 && result.created[0]?.login_id && (
              <div className="max-h-[200px] overflow-y-auto bg-surface-soft dark:bg-white/5 rounded-xl border border-line dark:border-white/10">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-surface-soft dark:bg-navy-900 border-b border-line dark:border-white/10">
                    <tr>
                      <th className="px-3 py-2 text-left">Ism Familiya</th>
                      <th className="px-3 py-2 text-left">Login</th>
                      <th className="px-3 py-2 text-left">Parol</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.created.slice(0, 100).map((u: any, i: number) => (
                      <tr key={i} className="border-t border-line dark:border-white/5">
                        <td className="px-3 py-1.5">{u.first_name} {u.last_name}</td>
                        <td className="px-3 py-1.5 font-mono">{u.login_id}</td>
                        <td className="px-3 py-1.5 font-mono">{u.password}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {result.failed.length > 0 && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/30 rounded-xl px-3 py-2 text-xs text-red-700 dark:text-red-300 space-y-0.5">
                <p className="font-bold">❌ Xatoliklar:</p>
                {result.failed.slice(0, 5).map((f: any, i: number) => (
                  <p key={i}>{f.first_name} {f.last_name}: {f.error}</p>
                ))}
              </div>
            )}
            <button onClick={reset} className="w-full px-4 py-2 border border-line dark:border-white/15 rounded-xl text-ink-700 dark:text-white font-medium hover:bg-surface-soft dark:hover:bg-white/5 transition-colors">
              + Yana qo'shish
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function WizardTypeStep({
  chatId, apiFetch, loading, onDone, setLoading, setError,
}: {
  chatId: number;
  apiFetch: (path: string, options?: any) => Promise<any>;
  loading: boolean;
  onDone: (state: AddStudentsWizardState) => void;
  setLoading: (v: boolean) => void;
  setError: (v: string) => void;
}) {
  async function selectType(type: "student" | "accountless", extra?: { parent_phone?: string; free_access?: boolean; subject?: string }) {
    setLoading(true); setError("");
    try {
      const res = await apiFetch(`/chats/diamondvoy/${chatId}/add-students/select-type`, {
        method: "POST",
        body: { account_type: type, ...(extra || {}) },
      });
      onDone(res.state);
    } catch (err: any) { setError(err.message || "Xatolik"); }
    finally { setLoading(false); }
  }

  return (
    <div className="space-y-3">
      <p className="text-ink-600 dark:text-slate-300">Qo'shmoqchi bo'lgan o'quvchilar turi:</p>
      <div className="flex flex-col gap-2">
        <button disabled={loading} onClick={() => selectType("student")}
          className="w-full px-4 py-3 rounded-xl border-2 border-emerald-400 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300 font-bold hover:bg-emerald-100 dark:hover:bg-emerald-800/30 transition-colors text-left flex items-center gap-3">
          <span className="text-xl">🔑</span>
          <div>
            <div className="font-bold">Mavjud student (hisob bilan)</div>
            <div className="text-xs font-normal opacity-70">Login va parol yaratiladi</div>
          </div>
        </button>
        <button disabled={loading} onClick={() => selectType("accountless")}
          className="w-full px-4 py-3 rounded-xl border-2 border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-slate-800/30 text-slate-700 dark:text-slate-300 font-bold hover:bg-slate-100 dark:hover:bg-slate-700/30 transition-colors text-left flex items-center gap-3">
          <span className="text-xl">👤</span>
          <div>
            <div className="font-bold">Hisob raqamsiz student</div>
            <div className="text-xs font-normal opacity-70">Faqat ro'yxatga olish, kirish yo'q</div>
          </div>
        </button>
      </div>
    </div>
  );
}

function DiamondVoyAppVersionWizard({
  apiFetch,
  onSuccess,
}: {
  apiFetch: (path: string, options?: any) => Promise<any>;
  onSuccess?: () => void;
}) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  const [studentVersion, setStudentVersion] = useState("1.0.0");
  const [studentBuild, setStudentBuild] = useState("1");
  const [studentStoreUrl, setStudentStoreUrl] = useState("");
  const [studentIosStoreUrl, setStudentIosStoreUrl] = useState("");

  const [teacherVersion, setTeacherVersion] = useState("1.0.0");
  const [teacherBuild, setTeacherBuild] = useState("1");
  const [teacherStoreUrl, setTeacherStoreUrl] = useState("");
  const [teacherIosStoreUrl, setTeacherIosStoreUrl] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    apiFetch("/admin/app-version-settings")
      .then((res: any) => {
        if (!active) return;
        if (res?.student) {
          setStudentVersion(res.student.min_version || "1.0.0");
          setStudentBuild(String(res.student.min_build || "1"));
          setStudentStoreUrl(res.student.store_url || "");
          setStudentIosStoreUrl(res.student.ios_store_url || "");
        }
        if (res?.teacher) {
          setTeacherVersion(res.teacher.min_version || "1.0.0");
          setTeacherBuild(String(res.teacher.min_build || "1"));
          setTeacherStoreUrl(res.teacher.store_url || "");
          setTeacherIosStoreUrl(res.teacher.ios_store_url || "");
        }
      })
      .catch((err: any) => {
        if (active) setError(err.message || "Versiyalarni yuklab bo'lmadi");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [apiFetch]);

  async function handleSave() {
    setSaving(true);
    setError("");
    setSuccessMsg("");
    try {
      await apiFetch("/admin/app-version-settings", {
        method: "POST",
        body: {
          student: {
            min_version: studentVersion.trim(),
            min_build: parseInt(studentBuild, 10) || 1,
            store_url: studentStoreUrl.trim(),
            ios_store_url: studentIosStoreUrl.trim(),
          },
          teacher: {
            min_version: teacherVersion.trim(),
            min_build: parseInt(teacherBuild, 10) || 1,
            store_url: teacherStoreUrl.trim(),
            ios_store_url: teacherIosStoreUrl.trim(),
          },
        },
      });
      setSuccessMsg("✅ Versiyalar muvaffaqiyatli saqlandi va kuchga kirdi!");
      if (onSuccess) onSuccess();
    } catch (err: any) {
      setError(err.message || "Saqlashda xatolik yuz berdi");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="p-4 text-center text-sm text-ink-500">Versiya sozlamalari yuklanmoqda...</div>;
  }

  return (
    <div className="w-full max-w-xl border border-purple-200 dark:border-purple-800/50 rounded-2xl bg-white dark:bg-[#1A2332] shadow-lg overflow-hidden flex flex-col">
      <div className="px-4 py-3 bg-purple-50 dark:bg-purple-900/20 border-b border-purple-100 dark:border-purple-800/30 flex justify-between items-center">
        <h4 className="font-bold text-purple-800 dark:text-purple-300">
          🚀 Mobil Ilovalar Versiyasi (Force Update)
        </h4>
      </div>

      <div className="p-4 space-y-4 text-sm">
        {error && <div className="text-red-500 font-medium bg-red-50 dark:bg-red-900/20 rounded-xl px-3 py-2">{error}</div>}
        {successMsg && <div className="text-green-600 dark:text-green-400 font-bold bg-green-50 dark:bg-green-900/20 rounded-xl px-3 py-2">{successMsg}</div>}

        {/* Student App */}
        <div className="space-y-2 border-b border-line dark:border-white/10 pb-3">
          <h5 className="font-bold text-ink-800 dark:text-slate-200 flex items-center gap-2">
            📱 Diamond Students App
          </h5>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs font-semibold mb-1 text-ink-600 dark:text-slate-400">Minimal Versiya</label>
              <input
                type="text"
                value={studentVersion}
                onChange={(e) => setStudentVersion(e.target.value)}
                placeholder="1.0.0"
                className="w-full px-3 py-1.5 border border-line dark:border-white/10 rounded-xl bg-transparent text-sm font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold mb-1 text-ink-600 dark:text-slate-400">Minimal Build</label>
              <input
                type="number"
                value={studentBuild}
                onChange={(e) => setStudentBuild(e.target.value)}
                placeholder="1"
                className="w-full px-3 py-1.5 border border-line dark:border-white/10 rounded-xl bg-transparent text-sm font-mono"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold mb-1 text-ink-600 dark:text-slate-400">Google Play URL</label>
            <input
              type="text"
              value={studentStoreUrl}
              onChange={(e) => setStudentStoreUrl(e.target.value)}
              placeholder="https://play.google.com/store/apps/details?id=..."
              className="w-full px-3 py-1.5 border border-line dark:border-white/10 rounded-xl bg-transparent text-xs font-mono"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold mb-1 text-ink-600 dark:text-slate-400">App Store URL</label>
            <input
              type="text"
              value={studentIosStoreUrl}
              onChange={(e) => setStudentIosStoreUrl(e.target.value)}
              placeholder="https://apps.apple.com/app/..."
              className="w-full px-3 py-1.5 border border-line dark:border-white/10 rounded-xl bg-transparent text-xs font-mono"
            />
          </div>
        </div>

        {/* Teacher App */}
        <div className="space-y-2 pb-2">
          <h5 className="font-bold text-ink-800 dark:text-slate-200 flex items-center gap-2">
            👨‍🏫 Diamond Teachers App
          </h5>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs font-semibold mb-1 text-ink-600 dark:text-slate-400">Minimal Versiya</label>
              <input
                type="text"
                value={teacherVersion}
                onChange={(e) => setTeacherVersion(e.target.value)}
                placeholder="1.0.0"
                className="w-full px-3 py-1.5 border border-line dark:border-white/10 rounded-xl bg-transparent text-sm font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold mb-1 text-ink-600 dark:text-slate-400">Minimal Build</label>
              <input
                type="number"
                value={teacherBuild}
                onChange={(e) => setTeacherBuild(e.target.value)}
                placeholder="1"
                className="w-full px-3 py-1.5 border border-line dark:border-white/10 rounded-xl bg-transparent text-sm font-mono"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold mb-1 text-ink-600 dark:text-slate-400">Google Play URL</label>
            <input
              type="text"
              value={teacherStoreUrl}
              onChange={(e) => setTeacherStoreUrl(e.target.value)}
              placeholder="https://play.google.com/store/apps/details?id=..."
              className="w-full px-3 py-1.5 border border-line dark:border-white/10 rounded-xl bg-transparent text-xs font-mono"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold mb-1 text-ink-600 dark:text-slate-400">App Store URL</label>
            <input
              type="text"
              value={teacherIosStoreUrl}
              onChange={(e) => setTeacherIosStoreUrl(e.target.value)}
              placeholder="https://apps.apple.com/app/..."
              className="w-full px-3 py-1.5 border border-line dark:border-white/10 rounded-xl bg-transparent text-xs font-mono"
            />
          </div>
        </div>

        <button
          disabled={saving}
          onClick={handleSave}
          className="w-full px-4 py-2.5 bg-purple-600 hover:bg-purple-700 text-white font-bold rounded-xl disabled:opacity-50 transition-colors shadow-md text-sm cursor-pointer"
        >
          {saving ? "Saqlanmoqda..." : "💾 Versiyalarni Saqlash"}
        </button>
      </div>
    </div>
  );
}

export function UniversalChat({
  apiFetch,
  userId,
  userRole,
}: {
  apiFetch: (path: string, options?: any) => Promise<any>;
  userId: number;
  userRole: string;
}) {
  const tt = useWebT();
  const role = String(userRole || "").toLowerCase();
  const isAdmin = role === "admin";
  const canRegenerate = ["admin", "teacher", "support"].includes(role);

  const [activePane, setActivePane] = useState<ActivePane>(null);
  const [aiChats, setAiChats] = useState<DiamondvoyChat[]>([]);
  const [activeChatId, setActiveChatId] = useState<number | null>(null);
  const [aiMessages, setAiMessages] = useState<DiamondvoyMessage[]>([]);
  const [feedbackDetail, setFeedbackDetail] = useState<FeedbackDetail | null>(null);
  const [adminThreads, setAdminThreads] = useState<FeedbackThreadSummary[]>([]);
  const [activeFeedbackThreadId, setActiveFeedbackThreadId] = useState<number | null>(null);
  const [adminFeedbackDetail, setAdminFeedbackDetail] = useState<FeedbackDetail | null>(null);

  const [input, setInput] = useState("");
  const [replyInput, setReplyInput] = useState("");
  const [anonymous, setAnonymous] = useState(true);
  const [images, setImages] = useState<UploadPreview[]>([]);
  const [uploading, setUploading] = useState(false);
  const [sending, setSending] = useState(false);
  const [creatingChat, setCreatingChat] = useState(false);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingBody, setLoadingBody] = useState(false);
  const [error, setError] = useState("");
  const [adminStatusFilter, setAdminStatusFilter] = useState("");
  const [adminSearch, setAdminSearch] = useState("");
  const [dpointAmount, setDpointAmount] = useState("");
  const [dpointReason, setDpointReason] = useState("");
  const [previewMedia, setPreviewMedia] = useState<PreviewMedia>(null);
  const [chatActionId, setChatActionId] = useState<number | null>(null);
  const [visibleTimeId, setVisibleTimeId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const chatsLoadingRef = useRef(false);
  const chatsLoadedRef = useRef(false);
  const creatingChatRef = useRef(false);
  const messagesLoadSeqRef = useRef(0);
  const messageCacheRef = useRef<Map<number, DiamondvoyMessage[]>>(new Map());
  const aiScrollRef = useRef<HTMLDivElement | null>(null);
  const feedbackScrollRef = useRef<HTMLDivElement | null>(null);
  const adminScrollRef = useRef<HTMLDivElement | null>(null);
  const pinnedToBottomRef = useRef(true);
  const chatLongPressTimerRef = useRef<number | null>(null);
  const longPressedChatRef = useRef<number | null>(null);
  const msgLongPressTimerRef = useRef<number | null>(null);
  const activeChat = useMemo(() => aiChats.find((chat) => chat.id === activeChatId) || null, [aiChats, activeChatId]);

  const scrollToBottom = useCallback((force = false) => {
    const node =
      activePane === "diamondvoy"
        ? aiScrollRef.current
        : activePane === "feedback" && isAdmin
          ? adminScrollRef.current
          : feedbackScrollRef.current;
    if (!node) return;
    if (!force && !pinnedToBottomRef.current) return;
    requestAnimationFrame(() => {
      node.scrollTop = node.scrollHeight;
    });
  }, [activePane, isAdmin]);

  const loadDiamondvoyChats = useCallback(async () => {
    if (chatsLoadingRef.current) return;
    chatsLoadingRef.current = true;
    setLoadingList(!chatsLoadedRef.current);
    try {
      const payload = await apiFetch("/chats/diamondvoy?limit=30");
      const rows = Array.isArray(payload?.items) ? payload.items : [];
      setAiChats(sortDiamondvoyChats(rows.map(normalizeChat).filter(Boolean) as DiamondvoyChat[]));
      chatsLoadedRef.current = true;
      setError("");
    } catch (err) {
      setError(parseError(err, tt("chat.error.loadList", "Chatlar ro'yxatini yuklab bo'lmadi.")));
    } finally {
      chatsLoadingRef.current = false;
      setLoadingList(false);
    }
  }, [apiFetch, tt]);

  const loadAiMessages = useCallback(
    async (chatId: number) => {
      if (!chatId) return;
      const cached = messageCacheRef.current.get(chatId);
      const seq = messagesLoadSeqRef.current + 1;
      messagesLoadSeqRef.current = seq;
      if (cached) {
        setAiMessages(cached);
        scrollToBottom(true);
      }
      setLoadingBody(!cached);
      try {
        const payload = await apiFetch(`/chats/diamondvoy/${chatId}/messages?limit=160`);
        if (messagesLoadSeqRef.current !== seq) return;
        const rows = Array.isArray(payload?.items) ? payload.items : [];
        const normalized = rows.map((row: any, index: number) => normalizeAiMessage(row, index + 1));
        messageCacheRef.current.set(chatId, normalized);
        setAiMessages(normalized);
        setError("");
        scrollToBottom(true);
      } catch (err) {
        if (messagesLoadSeqRef.current === seq) {
          setError(parseError(err, tt("chat.error.loadMessages", "Suhbat xabarlarini yuklab bo'lmadi.")));
        }
      } finally {
        if (messagesLoadSeqRef.current === seq) setLoadingBody(false);
      }
    },
    [apiFetch, scrollToBottom, tt],
  );

  const loadOwnFeedback = useCallback(async () => {
    setLoadingBody(true);
    try {
      const payload = await apiFetch("/feedback/thread");
      setFeedbackDetail({
        thread: payload?.thread,
        messages: (Array.isArray(payload?.messages) ? payload.messages : []).map(normalizeFeedbackMessage),
      });
      setError("");
      scrollToBottom(true);
    } catch (err) {
      setError(parseError(err, tt("chat.feedback.error.submit", "Taklif yuklanmadi. Qayta urinib ko'ring.")));
    } finally {
      setLoadingBody(false);
    }
  }, [apiFetch, scrollToBottom]);

  const loadAdminThreads = useCallback(async () => {
    if (!isAdmin) return;
    setLoadingBody(true);
    try {
      const params = new URLSearchParams();
      if (adminStatusFilter) params.set("status", adminStatusFilter);
      if (adminSearch.trim()) params.set("search", adminSearch.trim());
      params.set("limit", "80");
      const payload = await apiFetch(`/feedback/threads?${params.toString()}`);
      const rows = Array.isArray(payload?.items) ? payload.items : [];
      setAdminThreads(rows as FeedbackThreadSummary[]);
      setError("");
    } catch (err) {
      setError(parseError(err, tt("chat.feedback.error.loadAdmin", "Takliflar ro'yxatini yuklab bo'lmadi.")));
    } finally {
      setLoadingBody(false);
    }
  }, [apiFetch, adminSearch, adminStatusFilter, isAdmin]);

  const loadAdminThreadDetail = useCallback(
    async (threadId: number) => {
      setLoadingBody(true);
      try {
        const payload = await apiFetch(`/feedback/threads/${threadId}`);
        setAdminFeedbackDetail({
          thread: payload?.thread,
          messages: (Array.isArray(payload?.messages) ? payload.messages : []).map(normalizeFeedbackMessage),
        });
        setActiveFeedbackThreadId(threadId);
        setError("");
        scrollToBottom(true);
      } catch (err) {
      setError(parseError(err, tt("chat.error.loadMessages", "Suhbat xabarlarini yuklab bo'lmadi.")));
      } finally {
        setLoadingBody(false);
      }
    },
    [apiFetch, scrollToBottom],
  );

  useEffect(() => {
    loadDiamondvoyChats().catch(() => null);
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission().catch(() => null);
    }
    return () => {
      streamAbortRef.current?.abort();
      clearChatLongPressTimer();
      if (msgLongPressTimerRef.current) window.clearTimeout(msgLongPressTimerRef.current);
    };
  }, [loadDiamondvoyChats]);

  useEffect(() => {
    if (activePane === "diamondvoy" && activeChatId) {
      loadAiMessages(activeChatId).catch(() => null);
    }
  }, [activeChatId, activePane, loadAiMessages]);

  useEffect(() => {
    if (activePane !== "feedback") return;
    if (isAdmin) {
      loadAdminThreads().catch(() => null);
    } else {
      loadOwnFeedback().catch(() => null);
    }
  }, [activePane, isAdmin, loadAdminThreads, loadOwnFeedback]);

  useEffect(() => {
    if (!isAdmin || activePane !== "feedback") return;
    const timer = window.setTimeout(() => {
      loadAdminThreads().catch(() => null);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [adminSearch, adminStatusFilter, activePane, isAdmin, loadAdminThreads]);

  useEffect(() => {
    scrollToBottom(false);
  }, [aiMessages, feedbackDetail?.messages, adminFeedbackDetail?.messages, scrollToBottom]);

  function openDiamondvoy(chatId: number) {
    setChatActionId(null);
    setActivePane("diamondvoy");
    setActiveChatId(chatId);
    const cached = messageCacheRef.current.get(chatId);
    if (cached) setAiMessages(cached);
    setError("");
    setInput("");
    setImages([]);
  }

  async function createDiamondvoyChat() {
    if (creatingChatRef.current) return;
    creatingChatRef.current = true;
    setCreatingChat(true);
    setError("");
    try {
      const payload = await apiFetch("/chats/diamondvoy", { method: "POST", body: { title: tt("chat.new", "Yangi chat") } });
      const chat = normalizeChat(payload?.chat);
      if (!chat) throw new Error("Chat yaratilmadi");
      setAiChats((prev) => sortDiamondvoyChats([chat, ...prev.filter((item) => item.id !== chat.id)]));
      setActivePane("diamondvoy");
      setActiveChatId(chat.id);
      setAiMessages([]);
      messageCacheRef.current.set(chat.id, []);
    } catch (err) {
      setError(parseError(err, tt("chat.error.create", "Yangi chat yaratib bo'lmadi.")));
    } finally {
      creatingChatRef.current = false;
      setCreatingChat(false);
    }
  }

  async function handleFiles(files: FileList | null) {
    const selected = Array.from(files || []);
    if (!selected.length) return;
    if (images.length + selected.length > MAX_IMAGES) {
      setError(tt("chat.error.maxImages", "Bir xabarda 3 tagacha rasm yuborish mumkin"));
      return;
    }
    setUploading(true);
    setError("");
    try {
      const uploaded: UploadPreview[] = [];
      for (const file of selected) {
        if (!IMAGE_TYPES.has(file.type)) throw new Error(tt("chat.error.imageType", "Rasm turi noto'g'ri"));
        if (file.size > MAX_IMAGE_SIZE) throw new Error(tt("chat.error.imageSize", "Rasm hajmi juda katta"));
        const form = new FormData();
        form.append("file", file);
        const payload = await apiFetch("/chats/upload-image", { method: "POST", body: form });
        const url = String(payload?.url || "");
        if (!url) throw new Error(tt("chat.error.imageUpload", "Rasm yuklanmadi. Qayta urinib ko'ring."));
        uploaded.push({ url, preview: URL.createObjectURL(file), name: file.name });
      }
      setImages((prev) => [...prev, ...uploaded].slice(0, MAX_IMAGES));
    } catch (err) {
      setError(parseError(err, tt("chat.error.imageUpload", "Rasm yuklanmadi. Qayta urinib ko'ring.")));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function clearComposerImages() {
    images.forEach((image) => {
      if (image.preview.startsWith("blob:")) URL.revokeObjectURL(image.preview);
    });
    setImages([]);
  }

  function clearChatLongPressTimer() {
    if (chatLongPressTimerRef.current) {
      window.clearTimeout(chatLongPressTimerRef.current);
      chatLongPressTimerRef.current = null;
    }
  }

  function startChatLongPress(chatId: number) {
    clearChatLongPressTimer();
    longPressedChatRef.current = null;
    chatLongPressTimerRef.current = window.setTimeout(() => {
      longPressedChatRef.current = chatId;
      setChatActionId(chatId);
    }, 2000);
  }

  async function toggleDiamondvoyPin(chat: DiamondvoyChat) {
    const nextPinned = !Boolean(chat.pinned_at || chat.pinned);
    setChatActionId(null);
    const optimisticPinnedAt = nextPinned ? new Date().toISOString() : null;
    setAiChats((prev) =>
      sortDiamondvoyChats(
        prev.map((item) =>
          item.id === chat.id ? { ...item, pinned: nextPinned, pinned_at: optimisticPinnedAt } : item,
        ),
      ),
    );
    try {
      const payload = await apiFetch(`/chats/diamondvoy/${chat.id}/pin`, {
        method: "POST",
        body: { pinned: nextPinned },
      });
      const updated = normalizeChat(payload?.chat);
      if (updated) {
        setAiChats((prev) =>
          sortDiamondvoyChats(prev.map((item) => (item.id === updated.id ? { ...item, ...updated } : item))),
        );
      }
    } catch (err) {
      setError(parseError(err, tt("chat.error.update", "Chatni yangilab bo'lmadi.")));
      loadDiamondvoyChats().catch(() => null);
    }
  }

  async function deleteDiamondvoyChat(chat: DiamondvoyChat) {
    setChatActionId(null);
    setAiChats((prev) => prev.filter((item) => item.id !== chat.id));
    messageCacheRef.current.delete(chat.id);
    if (activeChatId === chat.id) {
      setActiveChatId(null);
      setAiMessages([]);
      setActivePane(null);
    }
    try {
      await apiFetch(`/chats/diamondvoy/${chat.id}`, { method: "DELETE" });
    } catch (err) {
      setError(parseError(err, tt("chat.error.delete", "Chatni o'chirib bo'lmadi.")));
      loadDiamondvoyChats().catch(() => null);
    }
  }

  async function sendDiamondvoyMessage(retryText?: string, retryImages?: string[]) {
    if (sending) return;
    unlockDiamondvoyThinkingAudio();
    let chatId = activeChatId;
    const text = retryText ?? input.trim();
    const imageUrls = retryImages ?? images.map((item) => item.url);
    const previews = retryImages
      ? retryImages.map((url, index) => ({ url, preview: apiUrl(url), name: `image-${index + 1}` }))
      : images;
    if (!text && imageUrls.length === 0) return;
    setSending(true);
    setError("");
    try {
      if (!chatId) {
        const created = await apiFetch("/chats/diamondvoy", { method: "POST", body: { title: tt("chat.new", "Yangi chat") } });
        const chat = normalizeChat(created?.chat);
        if (!chat) throw new Error("Chat yaratilmadi");
        chatId = chat.id;
        setAiChats((prev) => sortDiamondvoyChats([chat, ...prev.filter((item) => item.id !== chat.id)]));
        setActivePane("diamondvoy");
        setActiveChatId(chat.id);
      }
      const now = new Date().toISOString();
      const userTemp = Date.now();
      const assistantTemp = userTemp + 1;
      const resolvedChatId = Number(chatId || 0);
      setInput("");
      clearComposerImages();
      setAiMessages((prev) => {
        const next: DiamondvoyMessage[] = [
          ...prev,
          {
          id: userTemp,
          role: "user",
          content: text,
          attachments: previews.map((item) => ({ url: item.url })),
          created_at: now,
          },
          {
          id: assistantTemp,
          role: "assistant",
          content: "",
          attachments: [],
          created_at: now,
          streaming: true,
          },
        ];
        if (resolvedChatId) messageCacheRef.current.set(resolvedChatId, next);
        return next;
      });
      scrollToBottom(true);

      const token = localStorage.getItem("diamond_token") || "";
      const language = resolveLocale(localStorage.getItem("diamond_locale"));
      const controller = new AbortController();
      streamAbortRef.current = controller;
      let latestTitle = "";
      const response = await fetch(apiUrl(`/chats/diamondvoy/${chatId}/messages/stream`), {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          "X-Language": language,
        },
        body: JSON.stringify({ message: text, image_urls: imageUrls }),
        signal: controller.signal,
      });
      const finalText = await consumeSse(response, {
        onThinking: () => {
          setAiMessages((prev) => {
            const next = prev.map((msg) => (msg.id === assistantTemp ? { ...msg, streaming: true } : msg));
            if (resolvedChatId) messageCacheRef.current.set(resolvedChatId, next);
            return next;
          });
        },
        onDelta: (content) => {
          setAiMessages((prev) => {
            const next = prev.map((msg) => (msg.id === assistantTemp ? { ...msg, content, streaming: true } : msg));
            if (resolvedChatId) messageCacheRef.current.set(resolvedChatId, next);
            return next;
          });
        },
        onDone: (content, meta) => {
          latestTitle = String(meta?.chat_title || "");
          setAiMessages((prev) => {
            const next = prev.map((msg) => (msg.id === assistantTemp ? { ...msg, content, streaming: false } : msg));
            if (resolvedChatId) messageCacheRef.current.set(resolvedChatId, next);
            return next;
          });
        },
      });
      setAiChats((prev) =>
        sortDiamondvoyChats(
          prev.map((chat) =>
            chat.id === chatId
              ? {
                  ...chat,
                  title: latestTitle || chat.title || tt("chat.new", "Yangi chat"),
                  last_message_preview: finalText.slice(0, 140),
                  updated_at: new Date().toISOString(),
                }
              : chat,
          ),
        ),
      );
    } catch (err) {
      const message = parseError(err, tt("chat.error.stream", "Javob olishda xatolik yuz berdi. Qayta urinib ko'ring."));
      setError(message);
      setAiMessages((prev) =>
        prev.map((msg, index) =>
          index === prev.length - 1 && msg.role === "assistant" && msg.streaming
            ? { ...msg, content: message, streaming: false, failed: true, retryMessage: text, retryImages: imageUrls }
            : msg,
        ),
      );
    } finally {
      setSending(false);
      streamAbortRef.current = null;
    }
  }

  async function regenerateLastAnswer() {
    if (!canRegenerate || !activeChatId || sending) return;
    unlockDiamondvoyThinkingAudio();
    const regenChatId = activeChatId;
    const assistantTemp = Date.now();
    setSending(true);
    setAiMessages((prev) => [
      ...prev,
      { id: assistantTemp, role: "assistant", content: "", attachments: [], created_at: new Date().toISOString(), streaming: true },
    ]);
    try {
      const token = localStorage.getItem("diamond_token") || "";
      const response = await fetch(apiUrl(`/chats/diamondvoy/${regenChatId}/regenerate`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: "{}",
      });
      await consumeSse(response, {
        onDelta: (content) => setAiMessages((prev) => {
          const next = prev.map((msg) => (msg.id === assistantTemp ? { ...msg, content, streaming: true } : msg));
          messageCacheRef.current.set(regenChatId, next);
          return next;
        }),
        onDone: (content) => setAiMessages((prev) => {
          const next = prev.map((msg) => (msg.id === assistantTemp ? { ...msg, content, streaming: false } : msg));
          messageCacheRef.current.set(regenChatId, next);
          return next;
        }),
      });
    } catch (err) {
      const message = parseError(err, tt("chat.error.stream", "Javob olishda xatolik yuz berdi. Qayta urinib ko'ring."));
      setError(message);
      setAiMessages((prev) => prev.map((msg) => (msg.id === assistantTemp ? { ...msg, content: message, streaming: false } : msg)));
    } finally {
      setSending(false);
    }
  }

  async function sendFeedbackMessage() {
    if (sending || isAdmin) return;
    const text = input.trim();
    const imageUrls = images.map((item) => item.url);
    if (!text && imageUrls.length === 0) return;
    setSending(true);
    setError("");
    try {
      const payload = await apiFetch("/feedback/thread/messages", {
        method: "POST",
        body: { message: text, is_anonymous: anonymous, image_urls: imageUrls },
      });
      setFeedbackDetail({
        thread: payload?.thread,
        messages: (Array.isArray(payload?.messages) ? payload.messages : []).map(normalizeFeedbackMessage),
      });
      setInput("");
      clearComposerImages();
      scrollToBottom(true);
    } catch (err) {
      setError(parseError(err, tt("chat.feedback.error.submit", "Taklif yuborilmadi. Qayta urinib ko'ring.")));
    } finally {
      setSending(false);
    }
  }

  async function sendAdminReply() {
    if (!activeFeedbackThreadId || !replyInput.trim()) return;
    setSending(true);
    setError("");
    try {
      const payload = await apiFetch(`/feedback/threads/${activeFeedbackThreadId}/reply`, {
        method: "POST",
        body: { message: replyInput.trim() },
      });
      setAdminFeedbackDetail({
        thread: payload?.thread,
        messages: (Array.isArray(payload?.messages) ? payload.messages : []).map(normalizeFeedbackMessage),
      });
      setReplyInput("");
      loadAdminThreads().catch(() => null);
    } catch (err) {
      setError(parseError(err, tt("chat.error.send", "Xabar yuborilmadi.")));
    } finally {
      setSending(false);
    }
  }

  async function updateFeedbackStatus(status: string) {
    if (!activeFeedbackThreadId) return;
    setError("");
    try {
      const payload = await apiFetch(`/feedback/threads/${activeFeedbackThreadId}/status`, {
        method: "POST",
        body: { status },
      });
      setAdminFeedbackDetail({
        thread: payload?.thread,
        messages: (Array.isArray(payload?.messages) ? payload.messages : []).map(normalizeFeedbackMessage),
      });
      loadAdminThreads().catch(() => null);
    } catch (err) {
      setError(parseError(err, tt("chat.error.status", "Status saqlanmadi. Qayta urinib ko'ring.")));
    }
  }

  async function applyDpoint(action: "reward" | "penalty") {
    if (!activeFeedbackThreadId) return;
    const amount = Math.abs(Number(dpointAmount));
    if (!Number.isFinite(amount) || amount <= 0 || !dpointReason.trim()) {
      setError(tt("chat.feedback.error.amountRequired", "D'point miqdorini kiriting."));
      return;
    }
    setSending(true);
    try {
      await apiFetch(`/feedback/threads/${activeFeedbackThreadId}/${action}`, {
        method: "POST",
        body: { amount, reason: dpointReason.trim() },
      });
      setDpointAmount("");
      setDpointReason("");
      await loadAdminThreadDetail(activeFeedbackThreadId);
    } catch (err) {
      setError(parseError(err, tt("chat.feedback.error.adjust", "D'point o'zgarishini saqlab bo'lmadi.")));
    } finally {
      setSending(false);
    }
  }

  const mobileShowingList = !activePane;

  const Sidebar = (
    <aside className={cx("universal-chat-sidebar w-full lg:w-[330px] lg:border-r border-line dark:border-white/10 bg-surface-soft dark:bg-navy-900/70 flex flex-col min-h-0", mobileShowingList ? "flex" : "hidden lg:flex")}>
      <div className="px-4 py-3 border-b border-line dark:border-white/10 flex items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-black text-navy-900 dark:text-white">{tt("section.chats", "Chats")}</h2>
          <p className="text-[11px] text-ink-500 dark:text-navy-300">Diamondvoy · Taklif & Shikoyat</p>
        </div>
        <button
          type="button"
          onClick={() => createDiamondvoyChat().catch(() => null)}
          disabled={loadingList || creatingChat}
          className="px-3 py-2 rounded-lg bg-cyan-500 text-white text-xs font-bold hover:bg-cyan-600 disabled:opacity-60"
        >
          + {tt("chat.new", "Yangi chat")}
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        <button
          type="button"
          onClick={() => {
            setActivePane("feedback");
            setActiveChatId(null);
            setInput("");
            clearComposerImages();
          }}
          className={cx(
            "w-full text-left rounded-lg border px-3 py-3 transition",
            activePane === "feedback"
              ? "bg-cyan-100 dark:bg-cyan-500/15 border-cyan-300 dark:border-cyan-400/50"
              : "bg-white dark:bg-white/5 border-line dark:border-white/10 hover:border-cyan-300",
          )}
        >
          <p className="font-black text-sm text-navy-900 dark:text-white">{tt("chat.feedback.title", "Taklif & Shikoyat")}</p>
          <p className="text-xs text-ink-600 dark:text-navy-300 mt-1">{isAdmin ? tt("chat.feedback.adminReview", "Admin review") : tt("chat.feedback.subtitle", "Anonim yoki anonimmas xabar yuborish")}</p>
        </button>

        <div className="pt-2">
          <div className="px-1 pb-2 text-[11px] font-bold uppercase text-ink-500 dark:text-navy-300">Diamondvoy</div>
          {aiChats.length === 0 ? (
            <div className="px-3 py-4 rounded-lg border border-dashed border-line dark:border-white/10 text-xs text-ink-500 dark:text-navy-300">
              {loadingList ? tt("common.loading", "Yuklanmoqda...") : tt("chat.ai.empty", "Hozircha chat yo'q")}
            </div>
          ) : (
            <div className="space-y-2">
              {aiChats.map((chat) => (
                <div key={chat.id} className="relative">
                  <button
                    type="button"
                    onPointerDown={() => startChatLongPress(chat.id)}
                    onPointerUp={clearChatLongPressTimer}
                    onPointerLeave={clearChatLongPressTimer}
                    onPointerCancel={clearChatLongPressTimer}
                    onContextMenu={(event) => {
                      event.preventDefault();
                      setChatActionId(chat.id);
                    }}
                    onClick={() => {
                      if (longPressedChatRef.current === chat.id) {
                        longPressedChatRef.current = null;
                        return;
                      }
                      openDiamondvoy(chat.id);
                    }}
                    className={cx(
                      "w-full text-left rounded-lg border px-3 py-3 transition",
                      activePane === "diamondvoy" && activeChatId === chat.id
                        ? "bg-cyan-100 dark:bg-cyan-500/15 border-cyan-300 dark:border-cyan-400/50"
                        : "bg-white dark:bg-white/5 border-line dark:border-white/10 hover:border-cyan-300",
                    )}
                  >
                    <div className="flex items-center gap-2">
                      {chat.pinned_at || chat.pinned ? <span className="text-xs" aria-label={tt("chat.pinned", "Qadalgan")}>📌</span> : null}
                      <p className="min-w-0 flex-1 text-sm font-black text-navy-900 dark:text-white line-clamp-1">{chat.title === "Yangi chat" ? tt("chat.new", "Yangi chat") : chat.title}</p>
                    </div>
                    <p className="text-xs text-ink-600 dark:text-navy-300 mt-1 line-clamp-2">{chat.last_message_preview || tt("chat.new", "Yangi chat")}</p>
                    <p className="text-[11px] text-ink-400 dark:text-navy-400 mt-2">{formatWhen(chat.updated_at || chat.created_at)}</p>
                  </button>
                  {chatActionId === chat.id ? (
                    <div className="mt-1 grid grid-cols-2 gap-1 rounded-lg border border-line dark:border-white/10 bg-white dark:bg-navy-950 p-1 shadow-premium">
                      <button
                        type="button"
                        onClick={() => toggleDiamondvoyPin(chat).catch(() => null)}
                        className="rounded-md px-2 py-2 text-xs font-bold text-navy-900 hover:bg-surface-soft dark:text-white dark:hover:bg-white/10"
                      >
                        {chat.pinned_at || chat.pinned ? tt("chat.unpin", "Qadashni olib tashlash") : tt("chat.pin", "Qadash")}
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteDiamondvoyChat(chat).catch(() => null)}
                        className="rounded-md px-2 py-2 text-xs font-bold text-red-600 hover:bg-red-50 dark:text-red-200 dark:hover:bg-red-500/15"
                      >
                        {tt("common.delete", "O'chirish")}
                      </button>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </aside>
  );

  function renderChatText(text: string) {
    if (!text) return null;
    const parts = text.split(/\[btn\](.*?)\[\/btn\]/g);
    return (
      <div className="whitespace-pre-wrap break-words text-sm leading-6 space-y-1">
        {parts.map((part, index) => {
          if (index % 2 === 1) {
            return (
              <button
                key={index}
                type="button"
                onClick={() => {
                  setInput(part);
                  setTimeout(() => {
                    sendDiamondvoyMessage(part).catch(() => null);
                  }, 50);
                }}
                className="inline-block mt-1 mr-2 px-3 py-1.5 rounded-lg bg-cyan-100 dark:bg-cyan-500/20 text-cyan-700 dark:text-cyan-300 font-semibold border border-cyan-200 dark:border-cyan-500/30 hover:bg-cyan-200 dark:hover:bg-cyan-500/30 transition-colors"
              >
                {part}
              </button>
            );
          }
          return <span key={index}>{part}</span>;
        })}
      </div>
    );
  }

  function renderAttachments(items: ChatAttachment[]) {
    if (!items.length) return null;
    return (
      <div className="mt-2 grid grid-cols-2 sm:grid-cols-3 gap-2">
        {items.map((item, index) => (
          <button
            key={`${item.url}-${index}`}
            type="button"
            onClick={() => setPreviewMedia({ type: "image", src: apiUrl(item.url), title: tt("chat.image", "Rasm") })}
            className="block rounded-lg overflow-hidden border border-line dark:border-white/10 bg-black/5 text-left"
          >
            <img src={apiUrl(item.url)} alt="chat attachment" className="w-full h-24 object-cover" loading="lazy" />
          </button>
        ))}
      </div>
    );
  }

  const ComposerImages = (
    <>
      {images.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-2">
          {images.map((image) => (
            <div key={image.preview} className="relative w-20 h-20 shrink-0 rounded-lg overflow-hidden border border-line dark:border-white/15">
              <img src={image.preview} alt={image.name} className="w-full h-full object-cover" />
              <button
                type="button"
                onClick={() => setImages((prev) => prev.filter((item) => item.preview !== image.preview))}
                className="absolute top-1 right-1 w-6 h-6 rounded-full bg-black/70 text-white text-xs"
              >
                x
              </button>
            </div>
          ))}
        </div>
      )}
    </>
  );

  const DiamondvoyPane = (
    <section className={cx("flex-1 min-w-0 min-h-0 flex-col bg-white dark:bg-navy-950", activePane === "diamondvoy" ? "flex" : "hidden lg:flex")}>
      <div className="px-3 sm:px-5 py-3 border-b border-line dark:border-white/10 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <button type="button" onClick={() => setActivePane(null)} className="lg:hidden p-2 rounded-lg border border-line dark:border-white/15 text-ink-700 dark:text-white">‹</button>
          <DiamondvoyAvatar onPreview={setPreviewMedia} thinkingLabel={tt("chat.ai.thinking", "Diamondvoy o'ylayapti")} profileLabel={tt("chat.ai.title", "Diamondvoy")} />
          <div className="min-w-0">
            <h3 className="font-black text-navy-900 dark:text-white truncate">{activeChat?.title === "Yangi chat" ? tt("chat.new", "Yangi chat") : activeChat?.title || "Diamondvoy"}</h3>
            <p className="text-xs text-ink-500 dark:text-navy-300">{tt("chat.retention", "7 kun saqlanadi")}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {canRegenerate && (
            <button type="button" onClick={() => regenerateLastAnswer().catch(() => null)} disabled={sending || !activeChatId} className="px-3 py-2 rounded-lg border border-line dark:border-white/15 text-xs font-bold text-ink-700 dark:text-white disabled:opacity-50">
              {tt("chat.regenerate", "Qayta javob ber")}
            </button>
          )}
          <button type="button" onClick={() => loadAiMessages(activeChatId || 0).catch(() => null)} disabled={!activeChatId || loadingBody} className="px-3 py-2 rounded-lg border border-line dark:border-white/15 text-xs font-bold text-ink-700 dark:text-white disabled:opacity-50">
            ↻
          </button>
        </div>
      </div>

      <div
        ref={aiScrollRef}
        onScroll={(event) => {
          const node = event.currentTarget;
          pinnedToBottomRef.current = node.scrollHeight - node.scrollTop - node.clientHeight < 120;
        }}
        className="flex-1 min-h-0 overflow-y-auto px-3 sm:px-6 py-4 space-y-4"
      >
        {!activeChatId ? (
          <div className="h-full grid place-items-center text-center text-ink-500 dark:text-navy-300">
            <button type="button" onClick={() => createDiamondvoyChat().catch(() => null)} className="px-4 py-3 rounded-lg bg-cyan-500 text-white font-bold">
              + {tt("chat.new", "Yangi chat")}
            </button>
          </div>
        ) : loadingBody && aiMessages.length === 0 ? (
          <div className="text-sm text-ink-500 dark:text-navy-300">{tt("common.loading", "Yuklanmoqda...")}</div>
        ) : aiMessages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-ink-400 dark:text-slate-400 h-full">
            <DiamondvoyAvatar profileLabel="Diamondvoy" />
            <h3 className="mt-4 text-xl font-black text-ink-600 dark:text-slate-200">Diamondvoy</h3>
            <p className="mt-2 text-sm max-w-sm">
              {tt("chat.ai.emptyMessage", "Savollaringizni yozing yoki rasm/fayl yuklang. Diamondvoy yordam berishga tayyor.")}
            </p>
            {canRegenerate && (userRole === "teacher" || userRole === "support") && (
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                <button
                  className="px-4 py-2 rounded-xl bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300 text-sm font-bold border border-cyan-200 dark:border-cyan-800/50 hover:bg-cyan-200 dark:hover:bg-cyan-800 transition-colors"
                  onClick={() => {
                    setInput("Uy vazifasi berish");
                    setTimeout(() => sendDiamondvoyMessage("Uy vazifasi berish").catch(() => null), 50);
                  }}
                >
                  📝 Uy vazifasi berish
                </button>
              </div>
            )}
            {isAdmin && (
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                <button
                  className="px-4 py-2 rounded-xl bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 text-sm font-bold border border-emerald-200 dark:border-emerald-800/50 hover:bg-emerald-200 dark:hover:bg-emerald-800 transition-colors"
                  onClick={() => {
                    setInput("Yangi o'quvchilar qo'shish");
                    setTimeout(() => sendDiamondvoyMessage("Yangi o'quvchilar qo'shish").catch(() => null), 50);
                  }}
                >
                  👥 Yangi o'quvchilar qo'shish
                </button>
                <button
                  className="px-4 py-2 rounded-xl bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300 text-sm font-bold border border-purple-200 dark:border-purple-800/50 hover:bg-purple-200 dark:hover:bg-purple-800 transition-colors"
                  onClick={() => {
                    setInput("Mobil ilovalar versiyasi");
                    setTimeout(() => sendDiamondvoyMessage("Mobil ilovalar versiyasi").catch(() => null), 50);
                  }}
                >
                  🚀 Mobil Ilovalar Versiyasi
                </button>
              </div>
            )}
          </div>
        ) : (
          aiMessages.map((message) => {
            const mine = message.role === "user";
            const isWizardTrigger = typeof message.content === 'string' && message.content.includes('"wizard_trigger"');
            return (
              <div key={message.id} className={cx("flex gap-3", mine ? "justify-end" : "justify-start", isWizardTrigger ? "w-full" : "")}>
                {!mine && <DiamondvoyAvatar thinking={message.streaming && !message.content} onPreview={setPreviewMedia} thinkingLabel={tt("chat.ai.thinking", "Diamondvoy o'ylayapti")} profileLabel={tt("chat.ai.title", "Diamondvoy")} />}
                <div 
                  className={cx(
                    isWizardTrigger ? "w-full max-w-[95%] sm:max-w-[85%]" : "max-w-[88%] sm:max-w-[72%] rounded-2xl px-4 py-3 border select-none", 
                    mine ? "bg-cyan-500 text-white border-cyan-500" : isWizardTrigger ? "" : "bg-surface-soft dark:bg-white/5 text-navy-900 dark:text-white border-line dark:border-white/10"
                  )}
                  onPointerDown={() => {
                    msgLongPressTimerRef.current = window.setTimeout(() => setVisibleTimeId(`ai-${message.id}`), 400);
                  }}
                  onPointerUp={() => {
                    if (msgLongPressTimerRef.current) window.clearTimeout(msgLongPressTimerRef.current);
                    setTimeout(() => setVisibleTimeId(null), 2000);
                  }}
                  onPointerCancel={() => {
                    if (msgLongPressTimerRef.current) window.clearTimeout(msgLongPressTimerRef.current);
                  }}
                >
                  {message.streaming && !message.content ? (
                    <div className="flex items-center gap-2 text-sm font-semibold">
                      <span>{tt("chat.ai.thinking", "Diamondvoy o'ylayapti")}</span>
                      <span className="inline-flex gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce" />
                        <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce [animation-delay:120ms]" />
                        <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce [animation-delay:240ms]" />
                      </span>
                    </div>
                  ) : (() => {
                    try {
                      const parsed = JSON.parse(message.content);
                      if (parsed.type === "wizard_trigger" && parsed.wizard === "homework") {
                        return <DiamondVoyHomeworkWizard chatId={activeChatId!} apiFetch={apiFetch} onSuccess={() => {
                          loadAiMessages(activeChatId!).catch(() => null);
                        }} />;
                      }
                      if (parsed.type === "wizard_trigger" && parsed.wizard === "add_students") {
                        return <DiamondVoyAddStudentsWizard chatId={activeChatId!} apiFetch={apiFetch} onSuccess={() => {
                          loadAiMessages(activeChatId!).catch(() => null);
                        }} />;
                      }
                      if (parsed.type === "wizard_trigger" && parsed.wizard === "app_version") {
                        return <DiamondVoyAppVersionWizard apiFetch={apiFetch} onSuccess={() => {
                          loadAiMessages(activeChatId!).catch(() => null);
                        }} />;
                      }
                    } catch {}
                    return renderChatText(message.content);
                  })()}
                  {renderAttachments(message.attachments)}
                  <div className={cx("mt-2 flex items-center gap-2 text-[11px] transition-opacity", mine ? "text-white/80" : "text-ink-500 dark:text-navy-300", visibleTimeId === `ai-${message.id}` ? "opacity-100" : "opacity-0 h-0 overflow-hidden")}>
                    <span>{formatWhen(message.created_at)}</span>
                    {!!message.content && (
                      <button type="button" onClick={() => navigator.clipboard?.writeText(message.content).catch(() => null)} className="underline underline-offset-2">
                        {tt("chat.copy", "Nusxalash")}
                      </button>
                    )}
                    {message.failed && (
                      <button type="button" onClick={() => sendDiamondvoyMessage(message.retryMessage, message.retryImages).catch(() => null)} className="font-bold underline underline-offset-2">
                        {tt("chat.retry", "Qayta urinish")}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          sendDiamondvoyMessage().catch(() => null);
        }}
        className="border-t border-line dark:border-white/10 bg-white dark:bg-navy-950 px-3 sm:px-5 py-3 pb-[calc(env(safe-area-inset-bottom)+12px)]"
      >
        {ComposerImages}
        <div className="flex items-end gap-2">
          <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp" multiple className="hidden" onChange={(event) => handleFiles(event.target.files).catch(() => null)} />
          <button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploading || images.length >= MAX_IMAGES} className="w-11 h-11 rounded-lg border border-line dark:border-white/15 text-ink-700 dark:text-white disabled:opacity-50">
            +
          </button>
          <textarea value={input} onChange={(event) => setInput(event.target.value)} rows={1} placeholder={tt("chat.inputPlaceholder", "Xabar yozing...")} className="flex-1 max-h-32 resize-none rounded-lg border border-line dark:border-white/15 bg-white dark:bg-white/5 px-3 py-3 text-sm text-navy-900 dark:text-white outline-none focus:border-cyan-400" />
          <button type="submit" disabled={sending || uploading || (!input.trim() && images.length === 0)} className="px-4 h-11 rounded-lg bg-cyan-500 text-white font-bold disabled:opacity-50">
            {sending ? "..." : tt("chat.send", "Yuborish")}
          </button>
        </div>
      </form>
    </section>
  );

  const UserFeedbackPane = (
    <section className={cx("flex-1 min-w-0 min-h-0 flex-col bg-white dark:bg-navy-950", activePane === "feedback" && !isAdmin ? "flex" : "hidden")}>
      <div className="px-3 sm:px-5 py-3 border-b border-line dark:border-white/10 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <button type="button" onClick={() => setActivePane(null)} className="lg:hidden p-2 rounded-lg border border-line dark:border-white/15 text-ink-700 dark:text-white">‹</button>
          <div>
            <h3 className="font-black text-navy-900 dark:text-white">{tt("chat.feedback.title", "Taklif & Shikoyat")}</h3>
            <p className="text-xs text-ink-500 dark:text-navy-300">{feedbackDetail?.thread?.status || tt("feedback.status.new", "Yangi")}</p>
          </div>
        </div>
        <button type="button" onClick={() => loadOwnFeedback().catch(() => null)} className="px-3 py-2 rounded-lg border border-line dark:border-white/15 text-xs font-bold text-ink-700 dark:text-white">↻</button>
      </div>
      <div ref={feedbackScrollRef} className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 space-y-3">
        {(feedbackDetail?.messages || []).map((message) => {
          const mine = message.sender_user_id === Number(userId);
          return (
            <div key={message.id} className={cx("flex", mine ? "justify-end" : "justify-start")}>
              <div 
                className={cx("max-w-[88%] sm:max-w-[72%] rounded-2xl px-4 py-3 border select-none", mine ? "bg-cyan-500 text-white border-cyan-500" : "bg-surface-soft dark:bg-white/5 text-navy-900 dark:text-white border-line dark:border-white/10")}
                onPointerDown={() => {
                  msgLongPressTimerRef.current = window.setTimeout(() => setVisibleTimeId(`fb-${message.id}`), 400);
                }}
                onPointerUp={() => {
                  if (msgLongPressTimerRef.current) window.clearTimeout(msgLongPressTimerRef.current);
                  setTimeout(() => setVisibleTimeId(null), 2000);
                }}
                onPointerCancel={() => {
                  if (msgLongPressTimerRef.current) window.clearTimeout(msgLongPressTimerRef.current);
                }}
              >
                <div className="whitespace-pre-wrap break-words text-sm leading-6">{message.text}</div>
                {renderAttachments(message.attachments)}
                <p className={cx("mt-2 text-[11px] opacity-75 transition-opacity", visibleTimeId === `fb-${message.id}` ? "opacity-100" : "opacity-0 h-0 overflow-hidden")}>{message.sender_role === "admin" ? "Admin" : message.is_anonymous_choice ? tt("chat.feedback.anonymous", "Anonim") : tt("chat.feedback.nonAnonymous", "Anonimmas")} · {formatWhen(message.created_at)}</p>
              </div>
            </div>
          );
        })}
        {!feedbackDetail?.messages?.length && <div className="text-sm text-ink-500 dark:text-navy-300">{tt("chat.feedback.emptyUser", "Taklif yoki shikoyatingizni yuboring.")}</div>}
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          sendFeedbackMessage().catch(() => null);
        }}
        className="border-t border-line dark:border-white/10 bg-white dark:bg-navy-950 px-3 sm:px-5 py-3 pb-[calc(env(safe-area-inset-bottom)+12px)]"
      >
        {ComposerImages}
        <div className="flex gap-2 pb-2">
          <button type="button" onClick={() => setAnonymous(true)} className={cx("px-3 py-2 rounded-lg border text-xs font-bold", anonymous ? "bg-cyan-500 text-white border-cyan-500" : "border-line dark:border-white/15 text-ink-700 dark:text-white")}>{tt("chat.feedback.anonymous", "Anonim")}</button>
          <button type="button" onClick={() => setAnonymous(false)} className={cx("px-3 py-2 rounded-lg border text-xs font-bold", !anonymous ? "bg-cyan-500 text-white border-cyan-500" : "border-line dark:border-white/15 text-ink-700 dark:text-white")}>{tt("chat.feedback.nonAnonymous", "Anonimmas")}</button>
        </div>
        <div className="flex items-end gap-2">
          <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp" multiple className="hidden" onChange={(event) => handleFiles(event.target.files).catch(() => null)} />
          <button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploading || images.length >= MAX_IMAGES} className="w-11 h-11 rounded-lg border border-line dark:border-white/15 text-ink-700 dark:text-white disabled:opacity-50">+</button>
          <textarea value={input} onChange={(event) => setInput(event.target.value)} rows={1} placeholder={tt("chat.feedback.input", "Taklif yoki shikoyatingizni yozing...")} className="flex-1 max-h-32 resize-none rounded-lg border border-line dark:border-white/15 bg-white dark:bg-white/5 px-3 py-3 text-sm text-navy-900 dark:text-white outline-none focus:border-cyan-400" />
          <button type="submit" disabled={sending || uploading || (!input.trim() && images.length === 0)} className="px-4 h-11 rounded-lg bg-cyan-500 text-white font-bold disabled:opacity-50">{tt("chat.send", "Yuborish")}</button>
        </div>
      </form>
    </section>
  );

  const AdminFeedbackPane = (
    <section className={cx("universal-admin-feedback-pane flex-1 min-w-0 min-h-0 bg-white dark:bg-navy-950", activePane === "feedback" && isAdmin ? "flex" : "hidden")}>
      <div className={cx("universal-admin-feedback-list w-full md:w-[320px] xl:w-[360px] border-r border-line dark:border-white/10 flex-col min-h-0", activeFeedbackThreadId ? "hidden md:flex" : "flex")}>
        <div className="px-3 py-3 border-b border-line dark:border-white/10 space-y-2">
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => setActivePane(null)} className="lg:hidden p-2 rounded-lg border border-line dark:border-white/15 text-ink-700 dark:text-white">‹</button>
            <h3 className="font-black text-navy-900 dark:text-white">Taklif & Shikoyat</h3>
          </div>
          <input value={adminSearch} onChange={(event) => setAdminSearch(event.target.value)} placeholder="Ism familya qidirish" className="w-full rounded-lg border border-line dark:border-white/15 bg-white dark:bg-white/5 px-3 py-2 text-sm text-navy-900 dark:text-white" />
          <select value={adminStatusFilter} onChange={(event) => setAdminStatusFilter(event.target.value)} className="w-full rounded-lg border border-line dark:border-white/15 bg-white dark:bg-navy-900 px-3 py-2 text-sm text-navy-900 dark:text-white">
            <option value="">Hammasi</option>
            <option value="Yangi">{tt("feedback.status.new", "Yangi")}</option>
            <option value="Ko‘rilmoqda">{tt("feedback.status.reviewing", "Ko'rilmoqda")}</option>
            <option value="Hal qilindi">{tt("feedback.status.resolved", "Hal qilindi")}</option>
          </select>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {adminThreads.map((thread) => (
            <button key={thread.id} type="button" onClick={() => loadAdminThreadDetail(thread.id).catch(() => null)} className="universal-feedback-thread-button w-full text-left rounded-lg border border-line dark:border-white/10 bg-white dark:bg-white/5 px-3 py-3 hover:border-cyan-300">
              <div className="flex items-center justify-between gap-2">
                <p className="font-black text-sm text-navy-900 dark:text-white truncate">{thread.user_name}</p>
                <span className="text-[11px] px-2 py-1 rounded-full bg-cyan-100 dark:bg-cyan-500/15 text-cyan-700 dark:text-cyan-200">{thread.status}</span>
              </div>
              <p className="text-xs text-ink-500 dark:text-navy-300 mt-1">{thread.role}</p>
              <p className="text-xs text-ink-600 dark:text-navy-300 mt-2 line-clamp-2">{thread.last_message_preview || "-"}</p>
            </button>
          ))}
          {!adminThreads.length && <div className="text-sm text-ink-500 dark:text-navy-300">{loadingBody ? tt("common.loading", "Yuklanmoqda...") : tt("chat.feedback.emptyAdmin", "Taklif yo'q")}</div>}
        </div>
      </div>

      <div className={cx("universal-admin-feedback-detail flex-1 min-w-0 min-h-0 flex-col", activeFeedbackThreadId ? "flex" : "hidden md:flex")}>
        {!adminFeedbackDetail ? (
          <div className="h-full grid place-items-center text-sm text-ink-500 dark:text-navy-300">{tt("chat.selectChat", "Chatni tanlang")}</div>
        ) : (
          <>
            <div className="universal-feedback-header px-3 sm:px-5 py-3 border-b border-line dark:border-white/10 flex items-center justify-between gap-3">
              <div className="universal-feedback-header-main flex items-center gap-3 min-w-0">
                <button type="button" onClick={() => setActiveFeedbackThreadId(null)} className="md:hidden p-2 rounded-lg border border-line dark:border-white/15 text-ink-700 dark:text-white">‹</button>
                {adminFeedbackDetail.thread.user?.avatar_url ? (
                  <button
                    type="button"
                    onClick={() =>
                      setPreviewMedia({
                        type: "image",
                        src: apiUrl(adminFeedbackDetail.thread.user?.avatar_url || ""),
                        title: adminFeedbackDetail.thread.user?.full_name || "Profile",
                      })
                    }
                    className="w-10 h-10 rounded-xl overflow-hidden"
                  >
                    <img src={apiUrl(adminFeedbackDetail.thread.user.avatar_url)} alt="" className="w-full h-full object-cover" />
                  </button>
                ) : (
                  <div className="w-10 h-10 rounded-xl bg-cyan-100 dark:bg-cyan-500/15" />
                )}
                <div className="min-w-0">
                  <h3 className="font-black text-navy-900 dark:text-white truncate">{adminFeedbackDetail.thread.user?.full_name}</h3>
                  <p className="text-xs text-ink-500 dark:text-navy-300 truncate">
                    {adminFeedbackDetail.thread.user?.role} · {adminFeedbackDetail.thread.user?.group || tt("group.none", "Guruh yo'q")} · D'point {adminFeedbackDetail.thread.user?.dpoint_balance ?? "-"} · D'coin {adminFeedbackDetail.thread.user?.dcoin_balance ?? "-"}
                  </p>
                </div>
              </div>
              <select value={adminFeedbackDetail.thread.status} onChange={(event) => updateFeedbackStatus(event.target.value).catch(() => null)} className="universal-feedback-status rounded-lg border border-line dark:border-white/15 bg-white dark:bg-navy-900 px-3 py-2 text-sm text-navy-900 dark:text-white">
                <option value="Yangi">{tt("feedback.status.new", "Yangi")}</option>
                <option value="Ko‘rilmoqda">{tt("feedback.status.reviewing", "Ko'rilmoqda")}</option>
                <option value="Hal qilindi">{tt("feedback.status.resolved", "Hal qilindi")}</option>
              </select>
            </div>
            <div ref={adminScrollRef} className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 space-y-3">
              {adminFeedbackDetail.messages.map((message) => {
                const mine = message.sender_user_id === Number(userId);
                return (
                  <div key={message.id} className={cx("flex", mine ? "justify-end" : "justify-start")}>
                    <div className={cx("universal-feedback-message max-w-[88%] sm:max-w-[72%] rounded-2xl px-4 py-3 border", mine ? "bg-cyan-500 text-white border-cyan-500" : "bg-surface-soft dark:bg-white/5 text-navy-900 dark:text-white border-line dark:border-white/10")}>
                      <div className="whitespace-pre-wrap break-words text-sm leading-6">{message.text}</div>
                      {renderAttachments(message.attachments)}
                      <p className="mt-2 text-[11px] opacity-75">{message.sender_role} · {message.is_anonymous_choice ? tt("chat.feedback.anonymous", "Anonim") : tt("chat.feedback.nonAnonymous", "Anonimmas")} · {formatWhen(message.created_at)}</p>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="border-t border-line dark:border-white/10 bg-white dark:bg-navy-950 px-3 sm:px-5 py-3 pb-[calc(env(safe-area-inset-bottom)+12px)] space-y-3">
              <div className="universal-admin-feedback-controls grid grid-cols-1 sm:grid-cols-[120px_1fr_auto_auto] gap-2">
                <input value={dpointAmount} onChange={(event) => setDpointAmount(event.target.value)} placeholder="D'point" type="number" className="rounded-lg border border-line dark:border-white/15 bg-white dark:bg-white/5 px-3 py-2 text-sm text-navy-900 dark:text-white" />
                <input value={dpointReason} onChange={(event) => setDpointReason(event.target.value)} placeholder={tt("duel.reason", "Sabab")} className="rounded-lg border border-line dark:border-white/15 bg-white dark:bg-white/5 px-3 py-2 text-sm text-navy-900 dark:text-white" />
                <button type="button" onClick={() => applyDpoint("reward").catch(() => null)} className="px-3 py-2 rounded-lg bg-emerald-500 text-white text-sm font-bold">{tt("chat.feedback.reward", "Mukofot")}</button>
                <button type="button" onClick={() => applyDpoint("penalty").catch(() => null)} className="px-3 py-2 rounded-lg bg-rose-500 text-white text-sm font-bold">{tt("chat.feedback.penalty", "Jarima")}</button>
              </div>
              <form onSubmit={(event) => { event.preventDefault(); sendAdminReply().catch(() => null); }} className="universal-admin-reply-form flex items-end gap-2">
                <textarea value={replyInput} onChange={(event) => setReplyInput(event.target.value)} rows={1} placeholder={tt("chat.feedback.adminReply", "Admin javobi...")} className="flex-1 max-h-32 resize-none rounded-lg border border-line dark:border-white/15 bg-white dark:bg-white/5 px-3 py-3 text-sm text-navy-900 dark:text-white outline-none focus:border-cyan-400" />
                <button type="submit" disabled={sending || !replyInput.trim()} className="px-4 h-11 rounded-lg bg-cyan-500 text-white font-bold disabled:opacity-50">{tt("chat.send", "Yuborish")}</button>
              </form>
            </div>
          </>
        )}
      </div>
    </section>
  );

  return (
    <div className="universal-chat-root fixed inset-0 z-[60] flex bg-white dark:bg-navy-950 text-navy-900 dark:text-white overflow-hidden" style={{ height: "var(--tg-viewport-height, 100dvh)" }}>
      {Sidebar}
      {DiamondvoyPane}
      {UserFeedbackPane}
      {AdminFeedbackPane}
      {!activePane && <div className="hidden sm:grid flex-1 place-items-center text-center text-ink-500 dark:text-navy-300">{tt("chat.choosePane", "Diamondvoy yoki Taklif & Shikoyat tanlang")}</div>}
      {previewMedia && (
        <div
          className="fixed inset-0 z-[90] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setPreviewMedia(null)}
        >
          <div
            className="relative w-full max-w-4xl max-h-[88dvh] rounded-2xl bg-white dark:bg-navy-950 border border-white/20 shadow-2xl overflow-hidden"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-line dark:border-white/10">
              <p className="font-black text-navy-900 dark:text-white truncate">{previewMedia.title}</p>
              <button
                type="button"
                onClick={() => setPreviewMedia(null)}
                className="w-9 h-9 rounded-lg border border-line dark:border-white/15 text-navy-900 dark:text-white font-black"
              >
                x
              </button>
            </div>
            <div className="bg-black flex items-center justify-center max-h-[78dvh]">
              {previewMedia.type === "video" ? (
                <video src={previewMedia.src} className="max-w-full max-h-[78dvh]" controls autoPlay playsInline />
              ) : (
                <img src={previewMedia.src} alt={previewMedia.title} className="max-w-full max-h-[78dvh] object-contain" />
              )}
            </div>
          </div>
        </div>
      )}
      {error && (
        <div className="absolute left-3 right-3 sm:left-auto sm:right-5 bottom-4 sm:max-w-md rounded-lg border border-rose-200 dark:border-rose-400/30 bg-rose-50 dark:bg-rose-500/15 px-4 py-3 text-sm text-rose-700 dark:text-rose-100 shadow-soft">
          <div className="flex items-start justify-between gap-3">
            <span>{error}</span>
            <button type="button" onClick={() => setError("")} className="font-black">x</button>
          </div>
        </div>
      )}
    </div>
  );
}
