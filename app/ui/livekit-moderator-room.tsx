"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

type ApiFetch = (path: string, options?: { method?: string; body?: unknown }) => Promise<unknown>;
type JoinPayload = { url: string; token: string; room?: { title?: string } };

function mediaPublications(participant: any) {
  return Array.from(participant.trackPublications?.values?.() || []) as any[];
}

function ModeratorParticipantTile({
  participant,
  local,
  refreshKey,
  onMuteTrack,
  onRemove,
}: {
  participant: any;
  local: boolean;
  refreshKey: number;
  onMuteTrack?: (identity: string, trackSid: string, muted: boolean) => void;
  onRemove?: (identity: string) => void;
}) {
  const mediaRef = useRef<HTMLDivElement>(null);
  const publications = mediaPublications(participant);

  useEffect(() => {
    const container = mediaRef.current;
    if (!container) return;
    const attached: Array<{ track: any; element: HTMLElement }> = [];
    for (const publication of publications) {
      const track = publication.track;
      if (!track || (participant.isLocal && track.kind === "audio")) continue;
      const element = track.attach() as HTMLElement;
      if (track.kind === "video") {
        const video = element as HTMLVideoElement;
        video.autoplay = true;
        video.playsInline = true;
        video.muted = participant.isLocal === true;
        video.className = "h-full max-h-[34rem] min-h-48 w-full rounded-xl bg-black object-contain";
      } else {
        const audio = element as HTMLAudioElement;
        audio.autoplay = true;
        audio.controls = false;
        audio.className = "hidden";
      }
      container.appendChild(element);
      attached.push({ track, element });
    }
    return () => {
      for (const { track, element } of attached) {
        track.detach(element);
        element.remove();
      }
    };
  }, [participant, refreshKey]);

  const identity = String(participant.identity || "");
  const visibleTracks = publications.filter((publication) => publication.kind === "audio" || publication.kind === "video");
  const hasVideo = visibleTracks.some((publication) => publication.kind === "video" && !publication.isMuted);

  return (
    <article className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900 shadow-xl">
      <div ref={mediaRef} className={`relative grid min-h-48 place-items-center gap-1 bg-black p-1 ${hasVideo ? "" : "aspect-video"}`}>
        {!hasVideo ? <div className="absolute inset-0 grid place-items-center text-center text-white"><div><div className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-cyan-800 text-xl font-black">{String(participant.name || identity || "?").slice(0, 1).toUpperCase()}</div><p className="mt-3 max-w-48 truncate text-sm font-bold">{participant.name || identity}</p></div></div> : null}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 p-3 text-white">
        <div className="min-w-0"><p className="truncate text-sm font-bold">{participant.name || identity}{local ? " · Siz (moderator)" : ""}</p><p className="text-xs text-slate-400">{visibleTracks.length ? `${visibleTracks.filter((item) => !item.isMuted).length} media oqimi faol` : "Kamera/mikrofon o‘chiq"}</p></div>
        {!local && onMuteTrack && onRemove ? <div className="flex gap-2">
          {visibleTracks.map((publication) => <button key={publication.trackSid} type="button" onClick={() => onMuteTrack(identity, String(publication.trackSid), !publication.isMuted)} className="rounded-lg border border-white/15 px-2.5 py-1.5 text-xs font-bold hover:bg-white/10">{publication.kind === "audio" ? (publication.isMuted ? "Ovozni yoqish" : "Ovozni o‘chirish") : (publication.isMuted ? "Kamerani yoqish" : "Kamerani o‘chirish")}</button>)}
          <button type="button" onClick={() => onRemove(identity)} className="rounded-lg bg-red-600 px-2.5 py-1.5 text-xs font-bold hover:bg-red-500">Xonadan chiqarish</button>
        </div> : null}
      </div>
    </article>
  );
}

export function LiveKitModeratorRoom({
  roomId,
  title,
  apiFetch,
  onClose,
  onRoomEnded,
}: {
  roomId: string;
  title: string;
  apiFetch: ApiFetch;
  onClose: () => void;
  onRoomEnded: () => void;
}) {
  const roomRef = useRef<any>(null);
  const [room, setRoom] = useState<any>(null);
  const [participants, setParticipants] = useState<any[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [connecting, setConnecting] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [portalReady, setPortalReady] = useState(false);

  useEffect(() => {
    setPortalReady(true);
  }, []);

  const refreshParticipants = useCallback(() => {
    const current = roomRef.current;
    if (!current) return;
    setParticipants([current.localParticipant, ...current.remoteParticipants.values()]);
    setRefreshKey((value) => value + 1);
  }, []);

  useEffect(() => {
    let disposed = false;
    let createdRoom: any = null;
    const connect = async () => {
      try {
        setConnecting(true);
        setError("");
        const payload = await apiFetch(`/staff/speaking/live-video/rooms/${encodeURIComponent(roomId)}/moderator-token`, { method: "POST" }) as JoinPayload;
        if (!payload?.url || !payload?.token) throw new Error("Moderator ulanish tokeni olinmadi.");
        const { Room, RoomEvent } = await import("livekit-client");
        createdRoom = new Room({ adaptiveStream: true, dynacast: true });
        roomRef.current = createdRoom;
        const refresh = () => {
          if (!disposed) {
            setRoom(createdRoom);
            setParticipants([createdRoom!.localParticipant, ...createdRoom!.remoteParticipants.values()]);
            setRefreshKey((value) => value + 1);
          }
        };
        for (const event of [RoomEvent.Connected, RoomEvent.Disconnected, RoomEvent.ParticipantConnected, RoomEvent.ParticipantDisconnected, RoomEvent.TrackSubscribed, RoomEvent.TrackUnsubscribed, RoomEvent.TrackMuted, RoomEvent.TrackUnmuted, RoomEvent.LocalTrackPublished, RoomEvent.LocalTrackUnpublished]) {
          createdRoom.on(event as any, refresh as any);
        }
        await createdRoom.connect(payload.url, payload.token);
        if (disposed) {
          await createdRoom.disconnect();
          return;
        }
        setRoom(createdRoom);
        setParticipants([createdRoom.localParticipant, ...createdRoom.remoteParticipants.values()]);
        setRefreshKey((value) => value + 1);
      } catch (cause) {
        if (!disposed) setError(cause instanceof Error ? cause.message : "Live xonaga ulanishda xatolik yuz berdi.");
      } finally {
        if (!disposed) setConnecting(false);
      }
    };
    void connect();
    return () => {
      disposed = true;
      roomRef.current = null;
      if (createdRoom) void createdRoom.disconnect();
      void apiFetch(`/api/speaking/live-video/rooms/${encodeURIComponent(roomId)}/leave`, { method: "POST" }).catch(() => undefined);
    };
  }, [apiFetch, roomId]);

  async function toggleMedia(kind: "microphone" | "camera" | "screen") {
    if (!room) return;
    setBusy(kind);
    setError("");
    try {
      if (kind === "microphone") await room.localParticipant.setMicrophoneEnabled(!room.localParticipant.isMicrophoneEnabled);
      else if (kind === "camera") await room.localParticipant.setCameraEnabled(!room.localParticipant.isCameraEnabled);
      else await room.localParticipant.setScreenShareEnabled(!room.localParticipant.isScreenShareEnabled);
      refreshParticipants();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Qurilma ruxsati olinmadi.");
    } finally {
      setBusy("");
    }
  }

  async function moderate(action: "remove" | "mute", identity: string, trackSid?: string, muted?: boolean) {
    setBusy(identity);
    setError("");
    try {
      if (action === "remove") {
        await apiFetch(`/staff/speaking/live-video/rooms/${encodeURIComponent(roomId)}/participants/remove`, { method: "POST", body: { identity } });
      } else {
        await apiFetch(`/staff/speaking/live-video/rooms/${encodeURIComponent(roomId)}/tracks/mute`, { method: "POST", body: { identity, track_sid: trackSid, muted } });
      }
      window.setTimeout(refreshParticipants, 400);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Moderator amali bajarilmadi.");
    } finally {
      setBusy("");
    }
  }

  async function leaveRoom() {
    setBusy("leave");
    await room?.disconnect();
    void apiFetch(`/api/speaking/live-video/rooms/${encodeURIComponent(roomId)}/leave`, { method: "POST" }).catch(() => undefined);
    onClose();
  }

  async function endLive() {
    if (!window.confirm("Live’ni hamma qatnashchi uchun tugatmoqchimisiz?")) return;
    setBusy("end");
    try {
      await apiFetch(`/api/speaking/live-video/rooms/${encodeURIComponent(roomId)}/end`, { method: "POST" });
      await room?.disconnect();
      onRoomEnded();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Live’ni tugatishda xatolik.");
      setBusy("");
    }
  }

  const local = room?.localParticipant;

  if (!portalReady) return null;

  return createPortal(
    <div className="fixed inset-0 z-[2147483000] h-[100dvh] w-screen overflow-y-auto overscroll-contain bg-slate-950 text-white" role="dialog" aria-modal="true" aria-label="Live video moderator">
      <header className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-slate-950/95 px-4 py-3 backdrop-blur sm:px-6">
        <div className="min-w-0"><p className="text-xs font-black uppercase tracking-wider text-cyan-300">Diamond Speaking · Moderator</p><h1 className="truncate text-lg font-black">{title}</h1></div>
        <div className="flex flex-wrap gap-2">
          <button type="button" disabled={!room || !!busy} onClick={() => void toggleMedia("microphone")} className="rounded-xl border border-white/15 px-3 py-2 text-sm font-bold hover:bg-white/10 disabled:opacity-50">{local?.isMicrophoneEnabled ? "Mikrofonni o‘chirish" : "Mikrofonni yoqish"}</button>
          <button type="button" disabled={!room || !!busy} onClick={() => void toggleMedia("camera")} className="rounded-xl border border-white/15 px-3 py-2 text-sm font-bold hover:bg-white/10 disabled:opacity-50">{local?.isCameraEnabled ? "Kamerani o‘chirish" : "Kamerani yoqish"}</button>
          <button type="button" disabled={!room || !!busy} onClick={() => void toggleMedia("screen")} className="rounded-xl border border-cyan-300/40 px-3 py-2 text-sm font-bold text-cyan-100 hover:bg-cyan-400/10 disabled:opacity-50">{local?.isScreenShareEnabled ? "Ekran ulashishni to‘xtatish" : "Ekran ulashish"}</button>
          <button type="button" disabled={!!busy} onClick={() => void leaveRoom()} className="rounded-xl bg-slate-700 px-3 py-2 text-sm font-bold hover:bg-slate-600 disabled:opacity-50">{room ? "Xonadan chiqish" : "Yopish"}</button>
          <button type="button" disabled={!!busy} onClick={() => void endLive()} className="rounded-xl bg-red-600 px-3 py-2 text-sm font-bold hover:bg-red-500 disabled:opacity-50">Live’ni tugatish</button>
        </div>
      </header>
      <main className="mx-auto max-w-[1600px] space-y-4 p-4 sm:p-6">
        {connecting ? <div className="rounded-2xl border border-white/10 bg-white/5 p-8 text-center">Moderator sifatida ulanmoqda…</div> : null}
        {error ? <div role="alert" className="rounded-xl border border-red-400/40 bg-red-950/70 p-3 text-sm text-red-100">{error}</div> : null}
        {!connecting && !error && participants.length <= 1 ? <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">Xona ochiq. Qatnashchilar Speaking ilovasidagi Live video bo‘limidan qo‘shilganda shu yerda ko‘rinadi.</div> : null}
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {participants.map((participant) => <ModeratorParticipantTile key={participant.identity} participant={participant} local={participant.isLocal === true} refreshKey={refreshKey} onMuteTrack={(identity, trackSid, muted) => void moderate("mute", identity, trackSid, muted)} onRemove={(identity) => void moderate("remove", identity)} />)}
        </section>
      </main>
    </div>,
    document.body,
  );
}
