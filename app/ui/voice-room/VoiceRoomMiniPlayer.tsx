"use client";

import React from "react";
import cx from "clsx";
import { useGlobalVoiceRoom } from "./GlobalVoiceRoomContext";
import { usePathname, useRouter } from "next/navigation";
import { useWebT } from "../web-i18n";

export function VoiceRoomMiniPlayer() {
  const { state, roomState, isMinimized, setIsMinimized, leaveRoom, isMuted, toggleMute, speakingPeers } = useGlobalVoiceRoom();
  const pathname = usePathname();
  const router = useRouter();
  const t = useWebT();

  // If not in a room, do not render
  if (state !== "room" || !roomState) return null;

  // Determine if we should show the mini player automatically:
  // If we are NOT on /voice-rooms, we should force minimize state to true.
  // Actually, we can just render the mini player if pathname !== "/voice-rooms" OR isMinimized === true.
  const isVoiceRoomPage = pathname.startsWith("/voice-rooms");
  const shouldShow = !isVoiceRoomPage || isMinimized;

  if (!shouldShow) return null;

  const isSpeaking = speakingPeers.length > 0;

  return (
    <div className="fixed bottom-20 right-4 z-50 animate-in slide-in-from-bottom-8 fade-in duration-300">
      <div className="bg-slate-900/90 backdrop-blur-xl border border-slate-700/50 shadow-2xl p-3 rounded-2xl w-64 flex flex-col gap-2">
        
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 flex-1 cursor-pointer" onClick={() => router.push("/voice-rooms")}>
            <div className={cx(
              "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300",
              isSpeaking ? "bg-emerald-500 text-white animate-pulse shadow-[0_0_15px_rgba(16,185,129,0.5)]" : "bg-indigo-600 text-white"
            )}>
              {isSpeaking ? "🎙️" : "🎧"}
            </div>
            <div className="flex-1 min-w-0">
               <h4 className="text-white font-bold text-xs truncate">{roomState.subject.toUpperCase()}</h4>
               <p className="text-slate-400 text-[10px] truncate">{roomState.listenersCount} {t("voiceroom.listeners")?.toLowerCase() || "tinglovchi"}</p>
            </div>
          </div>
          <button onClick={leaveRoom} className="w-8 h-8 rounded-full bg-slate-800 text-slate-400 hover:text-red-500 hover:bg-red-500/10 flex items-center justify-center transition-colors">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2 mt-1">
           <button onClick={toggleMute} className={cx("w-full py-1.5 rounded-lg flex items-center justify-center transition-colors font-bold text-xs gap-2", isMuted ? "bg-red-500/20 text-red-500" : "bg-indigo-500/20 text-indigo-400")}>
             {isMuted ? (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.907L5.586 15z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" /></svg>
                  {t("voiceroom.mute") || "Mikrofon o'chiq"}
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" /></svg>
                  {t("voiceroom.unmute") || "Mikrofon yoniq"}
                </>
              )}
           </button>
        </div>

      </div>
    </div>
  );
}
