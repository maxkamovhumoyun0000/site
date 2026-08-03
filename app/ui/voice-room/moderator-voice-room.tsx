"use client";

import { useEffect, useState, useRef } from "react";
import cx from "clsx";
// Removed invalid import
import { useGlobalVoiceRoom } from "./GlobalVoiceRoomContext";
import { useWebT } from "../web-i18n";
import { useRouter } from "next/navigation";

const SUBJECT_MAP: Record<string, string> = {
  "english": "Ingliz tili",
  "russian": "Rus tili",
  "math": "Matematika",
  "English": "Ingliz tili",
  "Russian": "Rus tili",
  "Math": "Matematika"
};

export function ModeratorVoiceRoom({ role = "teacher" }: { role?: "teacher" | "admin" | "support" }) {
  const t = useWebT();
  const router = useRouter();
  const userSubjects: string[] = ["english", "russian"];

  const {
    state,
    errorMsg,
    isLoading,
    activeRooms,
    myRooms,
    mySessions,
    roomState,
    chatMessages,
    isMuted,
    myId,
    isOnStage,
    reactions,
    raisedHands,
    speakingPeers,
    createRoom,
    joinRoom,
    deleteRoom,
    requestStage,
    approveStage,
    rejectStage,
    leaveStage,
    leaveRoom,
    endRoom,
    sendChatMessage,
    sendReaction,
    toggleMute,
    setErrorMsg,
    isSpeakerphone,
    toggleSpeakerphone,
    demotePeer,
    kickPeer,
    forceMutePeer,
    makeCoHost,
    sendGift,
    topGifters,
    fetchTopGifters,
    activeGame,
    startGame,
    setIsMinimized
  } = useGlobalVoiceRoom();

  const [createSubject, setCreateSubject] = useState(userSubjects.length > 0 ? userSubjects[0] : "english");
  
  useEffect(() => {
    if (userSubjects.length > 0 && !userSubjects.includes(createSubject)) {
      setCreateSubject(userSubjects[0]);
    }
  }, [userSubjects, createSubject]);
  const [createName, setCreateName] = useState("");
  const [createTags, setCreateTags] = useState<string[]>([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [replyingTo, setReplyingTo] = useState<any>(null);
  const [showHandsModal, setShowHandsModal] = useState(false);
  const [showTopGiftersModal, setShowTopGiftersModal] = useState(false);
  const [selectedProfile, setSelectedProfile] = useState<string | null>(null);
  const [currentTab, setCurrentTab] = useState<"live" | "my_rooms" | "history">("live");
  const [activeSubTab, setActiveSubTab] = useState("all");
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [chatMessages]);

  const handleSendChat = (e: React.FormEvent) => {
    e.preventDefault();
    if (chatInput.trim()) {
      if (replyingTo) {
        sendChatMessage(chatInput, replyingTo.id, replyingTo.author, replyingTo.text);
        setReplyingTo(null);
      } else {
        sendChatMessage(chatInput);
      }
      setChatInput("");
    }
  };

  const handleCreateRoom = async () => {
    if (!createName.trim()) {
      setErrorMsg(t("voiceroom.roomName") + "!");
      return;
    }
    await createRoom(createName, createSubject, createTags);
    setShowCreateModal(false);
    setCreateName("");
    setCreateTags([]);
  };

  const handleEditRoomName = async (roomId: string, currentName: string) => {
    const newName = window.prompt(t("voiceroom.edit_name_prompt") || "Xona uchun yangi nom kiriting:", currentName);
    if (newName && newName.trim() !== "" && newName !== currentName) {
      try {
        const token = localStorage.getItem("auth_token") || "";
        const res = await fetch(`/api/voice-rooms/${roomId}/name`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
          },
          body: JSON.stringify({ name: newName })
        });
        if (res.ok) {
          window.location.reload();
        } else {
          setErrorMsg(t("voiceroom.editNameFailed") || "Xona nomini o'zgartirish amalga oshmadi");
        }
      } catch (e) {
        console.error(e);
        setErrorMsg(t("common.networkError") || "Tarmoq xatosi");
      }
    }
  };

  const formatDuration = (start: string, end?: string) => {
    if (!end) return "Davom etmoqda...";
    const s = new Date(start).getTime();
    const e = new Date(end).getTime();
    const diff = Math.floor((e - s) / 1000); // seconds
    if (diff < 60) return `${diff}s`;
    const m = Math.floor(diff / 60);
    const h = Math.floor(m / 60);
    if (h > 0) return `${h}h ${m % 60}m`;
    return `${m}m ${diff % 60}s`;
  };

  if (state === "lobby") {
    const subjects = ["all", ...userSubjects];
    const filteredActive = activeSubTab === "all" ? activeRooms : activeRooms.filter(r => r.subject === activeSubTab);

    return (
      <div className="flex-1 w-full h-full flex flex-col bg-slate-50 dark:bg-[#0a0f1c] relative overflow-hidden">
        
        {/* Top Header */}
        <div className="pt-6 pb-4 px-6 bg-white dark:bg-slate-900 shadow-sm border-b border-slate-200 dark:border-slate-800 flex items-center justify-between z-20">
           <button onClick={() => router.push('/dashboard')} className="text-slate-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
           </button>
           <h1 className="text-xl font-bold text-slate-800 dark:text-white">{t("voiceroom.title") || "Voice Rooms"}</h1>
           <div className="w-6"></div> {/* Spacer */}
        </div>

        {errorMsg && (
          <div className="z-20 m-4 bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400 p-3 rounded-xl text-center shadow-sm text-sm border border-red-200 dark:border-red-800/50">
            {errorMsg}
            <button onClick={() => setErrorMsg("")} className="ml-3 underline">Yopish</button>
          </div>
        )}

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto pb-24 custom-scrollbar z-10 relative">
          
          {currentTab === "live" && (
            <div className="p-4 sm:p-6 space-y-4">
              {/* Subject Tabs */}
              <div className="flex space-x-2 overflow-x-auto pb-2 custom-scrollbar">
                {subjects.map(subj => (
                  <button
                    key={subj}
                    onClick={() => setActiveSubTab(subj)}
                    className={cx(
                      "px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-all border",
                      activeSubTab === subj 
                        ? "bg-indigo-600 text-white border-indigo-600 shadow-md shadow-indigo-500/20" 
                        : "bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700"
                    )}
                  >
                    {subj === "all" ? "Barcha fanlar" : SUBJECT_MAP[subj] || subj}
                  </button>
                ))}
              </div>

              {filteredActive.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <div className="w-20 h-20 mb-4 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center">
                    <span className="text-4xl">🎧</span>
                  </div>
                  <p className="text-slate-500 dark:text-slate-400">{t("voiceroom.emptyRooms")}</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {filteredActive.map(room => (
                    <div key={room.room_id} onClick={() => joinRoom(room.room_id!)} className="bg-white dark:bg-slate-800/80 rounded-2xl p-4 shadow-sm border border-slate-100 dark:border-slate-700/50 cursor-pointer hover:shadow-md hover:border-indigo-500/30 transition-all flex items-start justify-between group">
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                           <span className="px-2 py-0.5 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded text-xs font-semibold uppercase tracking-wider">
                             {SUBJECT_MAP[room.subject] || room.subject}
                           </span>
                           <span className="flex items-center gap-1 text-slate-500 dark:text-slate-400 text-xs">
                             <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                             {room.listeners}
                           </span>
                        </div>
                        <h3 className="font-bold text-slate-800 dark:text-white group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">{room.name}</h3>
                        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{t("voiceroom.host")}: {room.host_name}</p>
                        {room.tags && room.tags.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {room.tags.map(tag => (
                              <span key={tag} className="px-2 py-0.5 bg-slate-100 dark:bg-slate-700/50 text-slate-500 dark:text-slate-400 rounded text-[10px] font-medium">
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="w-10 h-10 rounded-full bg-slate-100 dark:bg-slate-700 flex items-center justify-center group-hover:bg-indigo-50 dark:group-hover:bg-indigo-500/20 transition-colors">
                        <svg className="w-5 h-5 text-slate-400 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {currentTab === "my_rooms" && (
            <div className="p-4 sm:p-6 relative min-h-full">
              {myRooms.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <div className="w-20 h-20 mb-4 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center">
                    <span className="text-4xl">🏠</span>
                  </div>
                  <p className="text-slate-500 dark:text-slate-400">{t("voiceroom.emptyMyRooms")}</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {myRooms.map(room => {
                    const isActive = activeRooms.some(r => String(r.id) === String(room.id));
                    return (
                      <div key={room.id} className="bg-white dark:bg-slate-800 rounded-2xl p-4 shadow-sm border border-slate-100 dark:border-slate-700 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                        <div>
                           <h4 className="font-bold text-slate-800 dark:text-white text-lg">{room.name}</h4>
                           <span className="text-sm text-slate-500 dark:text-slate-400 mt-1 inline-block">{SUBJECT_MAP[room.subject] || room.subject}</span>
                           {room.tags && room.tags.length > 0 && (
                             <div className="flex flex-wrap gap-1 mt-2">
                               {room.tags.map(tag => (
                                 <span key={tag} className="px-2 py-0.5 bg-slate-100 dark:bg-slate-700/50 text-slate-500 dark:text-slate-400 rounded text-[10px] font-medium">
                                   {tag}
                                 </span>
                               ))}
                             </div>
                           )}
                        </div>
                        <div className="flex items-center gap-2 self-end sm:self-auto">
                          <button onClick={() => handleEditRoomName(room.id, room.name)} className="w-10 h-10 rounded-full flex items-center justify-center text-slate-400 hover:bg-indigo-50 hover:text-indigo-500 dark:hover:bg-indigo-500/10 transition-colors" title={t("voiceroom.editRoomName")}>
                             <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                          </button>
                          <button 
                            onClick={() => joinRoom(room.id)} 
                            className={cx(
                              "px-6 py-2.5 rounded-xl text-sm font-bold transition-all shadow-sm",
                              isActive 
                                ? "bg-emerald-500 text-white hover:bg-emerald-600 shadow-emerald-500/20" 
                                : "bg-indigo-600 text-white hover:bg-indigo-700 shadow-indigo-500/20"
                            )}
                          >
                            {isActive ? t("voiceroom.join") : "Start"}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* FAB for Create Room */}
              <button 
                onClick={() => setShowCreateModal(true)}
                className="fixed bottom-24 right-6 w-14 h-14 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full shadow-[0_8px_30px_rgb(79,70,229,0.3)] flex items-center justify-center transition-transform hover:scale-105 active:scale-95 z-30"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
              </button>
            </div>
          )}

          {currentTab === "history" && (
            <div className="p-4 sm:p-6">
              {mySessions.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <div className="w-20 h-20 mb-4 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center">
                    <span className="text-4xl">🕒</span>
                  </div>
                  <p className="text-slate-500 dark:text-slate-400">{t("voiceroom.emptyHistory")}</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {mySessions.map(session => (
                    <div key={session.id} className="bg-white dark:bg-slate-800 rounded-xl p-4 flex items-center justify-between border border-slate-100 dark:border-slate-700/50 shadow-sm">
                      <div>
                         <h4 className="font-bold text-slate-800 dark:text-white">{session.room_name}</h4>
                         <div className="flex items-center gap-2 mt-1 text-xs text-slate-500 dark:text-slate-400">
                            <span>{new Date(session.start_time).toLocaleDateString()}</span>
                            <span>•</span>
                            <span>{new Date(session.start_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                         </div>
                      </div>
                      <div className="text-right">
                         <div className="text-sm font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-500/10 px-3 py-1 rounded-lg">
                           {formatDuration(session.start_time, session.end_time)}
                         </div>
                         <div className="text-[10px] text-slate-400 mt-1 uppercase tracking-wider">{t("voiceroom.duration")}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

        </div>

        {/* Bottom Navigation Bar */}
        <div className="absolute bottom-0 w-full bg-white/90 dark:bg-slate-900/90 backdrop-blur-lg border-t border-slate-200 dark:border-slate-800 pb-safe z-30">
          <div className="flex justify-around items-center h-16 max-w-md mx-auto">
            <button 
              onClick={() => setCurrentTab("live")} 
              className={cx("flex flex-col items-center justify-center w-full h-full transition-colors", currentTab === "live" ? "text-indigo-600 dark:text-indigo-400" : "text-slate-400 hover:text-slate-600 dark:hover:text-slate-300")}
            >
              <svg className="w-6 h-6 mb-1" fill={currentTab === "live" ? "currentColor" : "none"} stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={currentTab === "live"?0:2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" /></svg>
              <span className="text-[10px] font-semibold">{t("voiceroom.nav.ongoing")}</span>
            </button>
            <button 
              onClick={() => setCurrentTab("my_rooms")} 
              className={cx("flex flex-col items-center justify-center w-full h-full transition-colors", currentTab === "my_rooms" ? "text-indigo-600 dark:text-indigo-400" : "text-slate-400 hover:text-slate-600 dark:hover:text-slate-300")}
            >
              <svg className="w-6 h-6 mb-1" fill={currentTab === "my_rooms" ? "currentColor" : "none"} stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={currentTab === "my_rooms"?0:2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>
              <span className="text-[10px] font-semibold">{t("voiceroom.nav.myRooms")}</span>
            </button>
            <button 
              onClick={() => setCurrentTab("history")} 
              className={cx("flex flex-col items-center justify-center w-full h-full transition-colors", currentTab === "history" ? "text-indigo-600 dark:text-indigo-400" : "text-slate-400 hover:text-slate-600 dark:hover:text-slate-300")}
            >
              <svg className="w-6 h-6 mb-1" fill={currentTab === "history" ? "currentColor" : "none"} stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={currentTab === "history"?0:2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              <span className="text-[10px] font-semibold">{t("voiceroom.nav.history")}</span>
            </button>
          </div>
        </div>

        {/* Create Room Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white dark:bg-slate-800 rounded-3xl w-full max-w-sm overflow-hidden shadow-2xl border border-slate-200 dark:border-slate-700 animate-in slide-in-from-bottom-4">
              <div className="p-6">
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-xl font-bold text-slate-800 dark:text-white">{t("voiceroom.createRoom")}</h2>
                  <button onClick={() => setShowCreateModal(false)} className="w-8 h-8 flex items-center justify-center rounded-full bg-slate-100 dark:bg-slate-700 text-slate-500 hover:text-slate-800 dark:hover:text-white transition-colors">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                  </button>
                </div>
                
                <div className="space-y-4 mb-6">
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">{t("voiceroom.roomName")}</label>
                    <input 
                      type="text" 
                      value={createName}
                      onChange={e => setCreateName(e.target.value)}
                      placeholder={t("voiceroom.name_placeholder") || "e.g. English Speaking Club"}
                      className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3.5 text-sm text-slate-800 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-all placeholder:text-slate-400"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">{t("voiceroom.roomSubject")}</label>
                    <select 
                      value={createSubject} 
                      onChange={e => setCreateSubject(e.target.value)}
                      className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3.5 text-sm text-slate-800 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-all appearance-none"
                    >
                      {(userSubjects.length > 0 ? userSubjects : ["English", "Russian"]).map(key => (
                        <option key={key} value={key}>{SUBJECT_MAP[key] || key}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">Teglar (Tags)</label>
                    <div className="flex flex-wrap gap-2">
                      {["Beginner", "IELTS", "Free Talk", "Grammar", "Vocabulary"].map(tag => (
                        <button
                          key={tag}
                          onClick={() => {
                            if (createTags.includes(tag)) setCreateTags(createTags.filter(t => t !== tag));
                            else if (createTags.length < 3) setCreateTags([...createTags, tag]);
                          }}
                          className={cx(
                            "px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors",
                            createTags.includes(tag) ? "bg-indigo-600 text-white border-indigo-600" : "bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700"
                          )}
                        >
                          {tag}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <button
                  disabled={isLoading}
                  onClick={handleCreateRoom}
                  className="w-full py-3.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl shadow-[0_8px_20px_rgba(79,70,229,0.25)] transition-all active:scale-[0.98] disabled:opacity-50"
                >
                  {isLoading ? "..." : t("voiceroom.createBtn")}
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    );
  }

  // Room State (Fullscreen inside web app)
  if (!roomState) return null;

  const isHost = roomState.hostId === myId;
  const stagePeers = roomState.stagePeers;
  const emptyStageSpots = Math.max(0, 4 - stagePeers.length);

  return (
    <div className="flex-1 w-full h-full flex flex-col bg-slate-950 relative overflow-hidden">
      
      {/* FLOATING REACTIONS ANIMATION */}
      <div className="pointer-events-none fixed inset-0 z-40 overflow-hidden">
        {reactions.map((r, i) => {
           // generate a consistent random path offset for each reaction
           const sway = Math.random() * 40 - 20; // -20px to 20px sway
           const startRight = 20 + Math.random() * 20; // start between 20px and 40px from right
           return (
             <div 
               key={r.id} 
               className="absolute text-4xl"
               style={{ 
                 bottom: '80px',
                 right: `${startRight}px`,
                 animation: `floatBubble 2.5s ease-in forwards`,
                 '--sway': `${sway}px`
               } as React.CSSProperties}
             >
               {r.emoji}
             </div>
           );
        })}
      </div>
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes floatBubble {
          0% { transform: translateY(0) translateX(0) scale(0.5); opacity: 0; }
          10% { transform: translateY(-20px) translateX(calc(var(--sway) * 0.2)) scale(1.2); opacity: 1; }
          50% { transform: translateY(-150px) translateX(var(--sway)) scale(1); opacity: 0.8; }
          100% { transform: translateY(-300px) translateX(calc(var(--sway) * -0.5)) scale(0.8); opacity: 0; }
        }
      `}} />

      {/* Room Header */}
      <div className="z-20 pt-6 pb-4 px-6 flex items-center justify-between bg-gradient-to-b from-slate-950 to-transparent">
        <button
          onClick={leaveRoom}
          className="w-10 h-10 rounded-full bg-slate-800/80 text-white flex items-center justify-center backdrop-blur-md border border-slate-700/50 hover:bg-slate-700 transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
        </button>
        <div className="text-center flex-1 mx-4">
          <div className="flex items-center justify-center gap-2">
            <h1 className="text-lg font-bold text-white leading-tight truncate">{activeRooms.find(r => r.room_id === roomState.roomId)?.name || "Room"}</h1>
            {isHost && (
              <button onClick={() => handleEditRoomName(roomState.roomId, activeRooms.find(r => r.room_id === roomState.roomId)?.name || "")} className="w-6 h-6 flex items-center justify-center text-slate-400 hover:text-indigo-400 transition-colors" title={t("voiceroom.editRoomName")}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
              </button>
            )}
          </div>
          <div className="flex items-center justify-center gap-1.5 mt-0.5">
             <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></span>
             <span className="text-xs font-medium text-slate-300">{roomState.listenersCount} {t("voiceroom.listeners").toLowerCase()}</span>
          </div>
        </div>
        
        <div className="flex items-center">
          {/* Top Gifters Button */}
          <button onClick={() => { fetchTopGifters(); setShowTopGiftersModal(true); }} className="relative w-10 h-10 mr-2 rounded-full bg-slate-800/80 text-yellow-500 hover:text-yellow-400 flex items-center justify-center backdrop-blur-md border border-slate-700/50 hover:bg-slate-700 transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" /></svg>
          </button>

          {/* HOST Actions */}
          {isHost ? (
            <>
              {/* Start Game Button */}
              {(!activeGame || !activeGame.active) && (
                <button onClick={() => startGame("anagram")} className="relative w-10 h-10 mr-2 rounded-full bg-purple-600/80 text-white hover:bg-purple-500 flex items-center justify-center backdrop-blur-md border border-purple-500/50 transition-colors" title={t("voiceroom.startGame") || "Start Game"}>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                </button>
              )}
              {/* Raised Hands Badge */}
              <button onClick={() => setShowHandsModal(true)} className="relative w-10 h-10 rounded-full bg-slate-800/80 text-slate-300 hover:text-white flex items-center justify-center backdrop-blur-md border border-slate-700/50 hover:bg-slate-700 transition-colors">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 11.5V14m0-2.5v-6a1.5 1.5 0 113 0m-3 6a1.5 1.5 0 00-3 0v2a7.5 7.5 0 0015 0v-5a1.5 1.5 0 00-3 0m-6-3V11m0-5.5v-1a1.5 1.5 0 013 0v1m0 0V11m0-5.5a1.5 1.5 0 013 0v3m0 0V11" /></svg>
              {raisedHands.length > 0 && (
                <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center border-2 border-slate-900 animate-bounce">
                  {raisedHands.length}
                </span>
              )}
              </button>
              {/* End Room Button */}
              <button onClick={endRoom} className="relative w-10 h-10 mr-2 rounded-full bg-red-600/80 text-white hover:bg-red-500 flex items-center justify-center backdrop-blur-md border border-red-500/50 transition-colors" title={t("voiceroom.closeRoom") || "End Room"}>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </>
          ) : (
            <div className="w-10"></div>
          )}
        </div>
      </div>

      <div className="z-10 flex-1 flex flex-col lg:flex-row overflow-hidden relative">
        
        {/* STAGE AREA */}
        <div className="flex-none lg:flex-1 max-h-[35vh] lg:max-h-none overflow-y-auto px-2 lg:px-8 py-4 custom-scrollbar">

          <div className="grid grid-cols-2 gap-4 max-w-lg mx-auto px-2 sm:px-4">
            {stagePeers.map(peerId => {
              const isMe = peerId === myId;
              const isHostPeer = peerId === roomState.hostId;
              const isSpeaking = speakingPeers.includes(peerId);

              const isGifter = topGifters.slice(0, 3).find(g => (isMe ? "You" : (roomState.peerInfo?.[peerId]?.name || "User")) === g.name || (g.name.includes("You")));
              
              let borderColor = "border-slate-800/80";
              if (isHostPeer) borderColor = "border-yellow-500";
              else if (roomState.coHosts?.includes(peerId)) borderColor = "border-blue-500";
              else if (isGifter) borderColor = "border-pink-500";

              let shadowClass = "shadow-lg";
              let scaleClass = "";
              if (isSpeaking) {
                 shadowClass = "shadow-[0_0_20px_rgba(16,185,129,0.5)]";
                 scaleClass = "scale-105";
                 if (borderColor === "border-slate-800/80") {
                   borderColor = "border-emerald-500";
                 }
              }

              return (
                <div 
                  key={peerId} 
                  onClick={() => setSelectedProfile(peerId)}
              className="flex flex-col items-center justify-center relative cursor-pointer group"
                >
                  <div className={cx(
                    "w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-slate-800 mb-2 flex items-center justify-center border-4 z-10 overflow-hidden relative transition-all duration-300 group-hover:scale-105",
                    borderColor, shadowClass, scaleClass
                  )}>
                    <img 
                      alt="Avatar"
                      src={roomState.peerInfo?.[peerId]?.avatar_url ? (roomState.peerInfo[peerId].avatar_url.startsWith('http') ? roomState.peerInfo[peerId].avatar_url : `/api${roomState.peerInfo[peerId].avatar_url.startsWith('/') ? '' : '/'}${roomState.peerInfo[peerId].avatar_url}`) : `https://api.dicebear.com/7.x/avataaars/svg?seed=${peerId}&backgroundColor=transparent`} 
                      className="w-full h-full object-cover relative z-10"
                      onError={(e) => { e.currentTarget.src = `https://api.dicebear.com/7.x/avataaars/svg?seed=${peerId}&backgroundColor=transparent` }}
                    />
                  </div>
                  
                  <div className="flex flex-col items-center mt-2 relative z-20">
                  <div className="font-bold text-[11px] sm:text-xs text-white truncate max-w-[90%] text-center">
                    {isMe ? (t("voiceroom.you") || "Siz") : (isHostPeer ? roomState.hostName : (roomState.peerInfo?.[peerId]?.name || (t("voiceroom.user") || "User")))}
                  </div>
                  <div className="text-[9px] text-slate-400 mt-0.5 uppercase tracking-wider font-medium">
                    {isHostPeer ? t("voiceroom.host") : (roomState.peerInfo?.[peerId]?.role || "Speaker")}
                  </div>
                </div>
                  
                  {/* Removed floating badges as per request */}
                </div>
              );
            })}
            
            {/* Empty Spots */}
            {Array.from({ length: emptyStageSpots }).map((_, i) => (
              <div key={i} className="flex flex-col items-center justify-center opacity-50">
                <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-slate-800/30 mb-2 flex items-center justify-center border-2 border-dashed border-slate-700/50">
                  <svg className="w-6 h-6 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
                </div>
                <span className="text-slate-500 font-medium text-xs">Empty</span>
              </div>
            ))}
          </div>
        </div>

        {/* CHAT AREA */}
        <div className="flex-1 lg:h-full lg:w-96 bg-slate-900/50 backdrop-blur-xl border-t lg:border-t-0 lg:border-l border-slate-800 flex flex-col min-h-0">
          <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
            {chatMessages.map(msg => {
              const isSystem = msg.author === "Tizim";
              const isMe = msg.author === myId; 
              return (
                <div key={msg.id} className={cx("animate-in fade-in flex flex-col", isMe ? "items-end" : "items-start")}>
                  {!isSystem && (
                    <div className={cx("flex items-baseline gap-2 mb-1 px-1", msg.is_admin ? "text-red-400" : "text-slate-400")}>
                      <span className="font-semibold text-[11px] text-current">{msg.author}</span>
                      {msg.is_admin && <span className="bg-red-600 text-white text-[9px] px-1.5 py-0.5 rounded shadow-sm shadow-red-500/20 uppercase font-black tracking-wider border border-red-400/50 animate-pulse">Admin</span>}
                      <button onClick={() => setReplyingTo(msg)} className="text-[10px] text-slate-500 hover:text-indigo-400 transition-colors uppercase font-bold tracking-wider">Reply</button>
                    </div>
                  )}
                  {isSystem ? (
                    <div className="w-full text-center my-2">
                       <span className="text-[11px] font-medium text-slate-400 bg-slate-800/80 px-3 py-1 rounded-full">{msg.text}</span>
                    </div>
                  ) : (
                    <div className={cx("px-3.5 py-2 rounded-2xl max-w-[85%] text-[13px] shadow-sm flex flex-col", isMe ? "bg-indigo-600 text-white rounded-br-sm" : (msg.is_admin ? "bg-red-950/40 text-red-100 border border-red-500/30 rounded-bl-sm shadow-[0_0_15px_rgba(220,38,38,0.15)]" : "bg-slate-800 text-slate-200 border border-slate-700/50 rounded-bl-sm"))}>
                      {msg.replyToText && (
                        <div className="mb-1.5 px-2 py-1 bg-black/20 rounded-lg border-l-2 border-indigo-400 text-[11px] opacity-80 line-clamp-2">
                          <span className="font-bold block mb-0.5">{msg.replyToAuthor}</span>
                          {msg.replyToText}
                        </div>
                      )}
                      {msg.text}
                    </div>
                  )}
                </div>
              );
            })}
            <div ref={chatEndRef} />
          </div>

          <div className="p-3 bg-slate-900/80 border-t border-slate-800 pb-safe flex flex-col gap-2">
            {replyingTo && (
               <div className="flex items-center justify-between px-3 py-2 bg-slate-800 rounded-xl text-xs text-slate-300 border-l-2 border-indigo-500">
                  <div className="flex-1 truncate pr-2">
                    <span className="font-bold text-indigo-400">{t("voiceroom.replying_to") || "Replying to"} {replyingTo.author}: </span>
                    <span className="opacity-80">{replyingTo.text}</span>
                  </div>
                  <button onClick={() => setReplyingTo(null)} className="text-slate-500 hover:text-white shrink-0">
                     <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                  </button>
               </div>
            )}
            <div className="flex flex-wrap sm:flex-nowrap items-center gap-1.5 w-full">
              <form onSubmit={handleSendChat} className="flex-1 flex gap-1.5">
                <input
                  type="text"
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  placeholder="Xabar..."
                  className="flex-1 min-w-0 bg-slate-950 border border-slate-800 rounded-full px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500/50 transition-all"
                />
                <button type="submit" disabled={!chatInput.trim()} className="w-7 h-7 flex-shrink-0 bg-indigo-600 text-white rounded-full flex items-center justify-center hover:bg-indigo-500 disabled:opacity-50 transition-colors">
                  <svg className="w-3.5 h-3.5 ml-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>
                </button>
              </form>
              
              {/* CHAT CONTROLS (MIC & REACTIONS) */}
              <div className="flex items-center gap-1 shrink-0 ml-auto">
                <button onClick={() => sendReaction("❤️")} className="w-7 h-7 shrink-0 rounded-full bg-slate-800 hover:bg-slate-700 flex items-center justify-center text-xs transition-transform active:scale-90">❤️</button>
                <button onClick={() => sendReaction("👏")} className="w-7 h-7 shrink-0 rounded-full bg-slate-800 hover:bg-slate-700 flex items-center justify-center text-xs transition-transform active:scale-90">👏</button>
                <button onClick={() => sendReaction("😂")} className="w-7 h-7 shrink-0 rounded-full bg-slate-800 hover:bg-slate-700 flex items-center justify-center text-xs transition-transform active:scale-90">😂</button>
                
                <div className="w-[1px] h-4 bg-slate-700 mx-0.5 shrink-0"></div>
                
                {isOnStage ? (
                  <>
                    <button onClick={toggleMute} className={cx("w-7 h-7 shrink-0 rounded-full flex items-center justify-center transition-all", isMuted ? "bg-red-500/20 text-red-500 hover:bg-red-500 hover:text-white" : "bg-emerald-500/20 text-emerald-500 hover:bg-emerald-500 hover:text-white")}>
                      {isMuted ? (
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11v2a7 7 0 01-14 0v-2M19 11L5 11M12 19v2m-3 0h6M12 3a3 3 0 00-3 3v5.5a3 3 0 006 0V6a3 3 0 00-3-3z" /></svg>
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" /></svg>
                      )}
                    </button>
                    <button onClick={toggleSpeakerphone} className={cx("w-7 h-7 shrink-0 rounded-full flex items-center justify-center transition-all ml-1", isSpeakerphone ? "bg-indigo-500/20 text-indigo-500 hover:bg-indigo-500 hover:text-white" : "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white")} title={isSpeakerphone ? "Dinamik (Loudspeaker)" : "Quloqchin (Earpiece)"}>
                      {isSpeakerphone ? (
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" /></svg>
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" /></svg>
                      )}
                    </button>
                    {!isHost && (
                      <button onClick={leaveStage} className="w-7 h-7 shrink-0 rounded-full bg-slate-800 text-slate-300 hover:bg-red-500/20 hover:text-red-500 flex items-center justify-center transition-all" title="Sahnadan tushish">
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
                      </button>
                    )}
                  </>
                ) : (
                  <button onClick={requestStage} className="w-7 h-7 shrink-0 bg-indigo-600 hover:bg-indigo-500 text-white rounded-full flex items-center justify-center transition-transform hover:scale-105">
                    <span className="text-xs">✋</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>

      </div>
      
      {/* HOST Raised Hands Modal */}
      {isHost && showHandsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 rounded-3xl w-full max-w-sm overflow-hidden shadow-2xl border border-slate-800 animate-in zoom-in-95">
            <div className="p-6">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <span>✋</span> {t("voiceroom.raised_hands") || "Raised Hands"}
                </h2>
                <button onClick={() => setShowHandsModal(false)} className="w-8 h-8 flex items-center justify-center rounded-full bg-slate-800 text-slate-400 hover:text-white transition-colors">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
              
              <div className="space-y-3 max-h-60 overflow-y-auto custom-scrollbar">
                {raisedHands.length === 0 ? (
                  <p className="text-center text-slate-500 py-4">Sahnaga chiqmoqchi bo'lganlar yo'q.</p>
                ) : (
                  raisedHands.map(hand => (
                    <div key={hand.id} className="flex items-center justify-between p-3 bg-slate-800 rounded-xl">
                      <span className="text-sm font-bold text-white">{hand.name}</span>
                      <div className="flex gap-2">
                        <button onClick={() => rejectStage(hand.id)} className="px-3 py-1.5 bg-slate-700 text-slate-300 rounded-lg text-xs font-bold hover:bg-slate-600">Rad etish</button>
                        <button onClick={() => approveStage(hand.id)} className="px-3 py-1.5 bg-emerald-500 text-white rounded-lg text-xs font-bold hover:bg-emerald-600">Ruxsat</button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TOP GIFTERS MODAL */}
      {showTopGiftersModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm animate-in fade-in duration-200" onClick={() => setShowTopGiftersModal(false)}>
          <div className="bg-gradient-to-b from-yellow-900/40 to-slate-900 rounded-3xl w-full max-w-sm overflow-hidden shadow-2xl border border-yellow-500/20 animate-in zoom-in-95" onClick={e => e.stopPropagation()}>
            <div className="p-6">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-bold text-yellow-500 flex items-center gap-2">
                  <span>🏆</span> Top Gifters
                </h2>
                <button onClick={() => setShowTopGiftersModal(false)} className="w-8 h-8 flex items-center justify-center rounded-full bg-slate-800 text-slate-400 hover:text-white transition-colors">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
              
              <div className="space-y-3 max-h-72 overflow-y-auto custom-scrollbar">
                {topGifters.length === 0 ? (
                  <p className="text-center text-slate-500 py-4">Hali hech kim sovg'a yubormadi.</p>
                ) : (
                  topGifters.map((gifter, index) => (
                    <div key={index} className="flex items-center justify-between p-3 bg-slate-800/50 rounded-xl border border-slate-700/50">
                      <div className="flex items-center gap-3">
                        <span className={cx(
                          "w-6 h-6 flex items-center justify-center rounded-full text-xs font-bold",
                          index === 0 ? "bg-yellow-500 text-yellow-950" :
                          index === 1 ? "bg-slate-300 text-slate-900" :
                          index === 2 ? "bg-amber-700 text-amber-100" :
                          "bg-slate-700 text-slate-300"
                        )}>
                          {index + 1}
                        </span>
                        <span className="text-sm font-bold text-white">{gifter.name}</span>
                      </div>
                      <span className="text-sm font-bold text-yellow-500">{gifter.amount} Dcoin</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}
      {/* USER PROFILE MODAL */}
      {selectedProfile && (
        <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center bg-slate-950/60 backdrop-blur-sm animate-in fade-in duration-200" onClick={() => setSelectedProfile(null)}>
          <div className="bg-slate-900 w-full sm:w-96 rounded-t-3xl sm:rounded-3xl p-6 sm:p-8 shadow-2xl border-t sm:border border-slate-800 animate-in slide-in-from-bottom sm:slide-in-from-bottom-0 sm:zoom-in-95" onClick={e => e.stopPropagation()}>
            <div className="w-12 h-1.5 bg-slate-800 rounded-full mx-auto mb-6 sm:hidden"></div>
            
            <div className="flex flex-col items-center">
              <div className="w-24 h-24 rounded-full bg-slate-800 mb-4 border-4 border-slate-700 overflow-hidden shadow-xl">
                <img 
                  alt="Avatar"
                  src={roomState.peerInfo?.[selectedProfile]?.avatar_url ? (roomState.peerInfo[selectedProfile].avatar_url.startsWith('http') ? roomState.peerInfo[selectedProfile].avatar_url : `/api${roomState.peerInfo[selectedProfile].avatar_url.startsWith('/') ? '' : '/'}${roomState.peerInfo[selectedProfile].avatar_url}`) : `https://api.dicebear.com/7.x/avataaars/svg?seed=${selectedProfile}&backgroundColor=transparent`} 
                  className="w-full h-full object-cover relative z-10"
                  onError={(e) => { e.currentTarget.src = `https://api.dicebear.com/7.x/avataaars/svg?seed=${selectedProfile}&backgroundColor=transparent` }}
                />
              </div>
              <div className="text-center">
                <h2 className="text-2xl font-bold text-white mb-1">
                {selectedProfile === myId ? "You" : (selectedProfile === roomState.hostId ? roomState.hostName : (roomState.peerInfo?.[selectedProfile]?.name || "User"))}
                </h2>
                <p className="text-slate-400 capitalize">{selectedProfile === roomState.hostId ? "Host" : (roomState.peerInfo?.[selectedProfile]?.role || "Speaker")}</p>
              </div>
              <div className="flex gap-2 mt-4 flex-wrap justify-center">
                <span className="px-2.5 py-1 rounded-lg bg-indigo-500/20 text-indigo-400 text-[10px] font-bold uppercase tracking-wider">Level 12</span>
                {selectedProfile === roomState.hostId && <span className="px-2.5 py-1 rounded-lg bg-yellow-500/20 text-yellow-500 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">Host</span>}
                {roomState.coHosts?.includes(selectedProfile) && <span className="px-2.5 py-1 rounded-lg bg-blue-500/20 text-blue-400 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">Co-Host</span>}
                {topGifters.slice(0, 3).find(g => ((selectedProfile === myId) ? "You" : (selectedProfile === roomState.hostId ? roomState.hostName : (roomState.peerInfo?.[selectedProfile]?.name || "User"))) === g.name || g.name.includes("You")) && <span className="px-2.5 py-1 rounded-lg bg-pink-500/20 text-pink-400 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">Top Gifter</span>}
              </div>

              {/* Actions */}
              <div className="w-full space-y-3">
                {selectedProfile !== myId && (
                  <div className="flex gap-2">
                    <button onClick={() => { sendGift(selectedProfile, "Diamond", 50); setSelectedProfile(null); }} className="flex-1 py-3.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-bold rounded-xl shadow-lg transition-all active:scale-95 flex items-center justify-center gap-2">
                      <span>💎</span> Send Gift (50)
                    </button>
                    <button onClick={() => { router.push(`/dashboard?chat=${selectedProfile}`); }} className="flex-1 py-3.5 bg-slate-800 hover:bg-slate-700 text-white font-bold rounded-xl shadow-lg transition-all active:scale-95 flex items-center justify-center gap-2">
                      <span>💬</span> Message
                    </button>
                  </div>
                )}
                
                {isHost && selectedProfile !== myId && selectedProfile !== roomState.hostId && (
                  <div className="grid grid-cols-2 gap-2 mt-4 pt-4 border-t border-slate-800">
                    {!roomState.coHosts?.includes(selectedProfile) && (
                      <button onClick={() => { makeCoHost(selectedProfile); setSelectedProfile(null); }} className="py-2.5 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 text-xs font-bold rounded-xl transition-colors">
                        Make Co-Host
                      </button>
                    )}
                    <button onClick={() => { forceMutePeer(selectedProfile); setSelectedProfile(null); }} className="py-2.5 bg-orange-500/10 text-orange-400 hover:bg-orange-500/20 text-xs font-bold rounded-xl transition-colors">
                      Force Mute
                    </button>
                    <button onClick={() => { demotePeer(selectedProfile); setSelectedProfile(null); }} className="py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold rounded-xl transition-colors">
                      Move to Listeners
                    </button>
                    <button onClick={() => { kickPeer(selectedProfile); setSelectedProfile(null); }} className="py-2.5 bg-red-500/10 text-red-400 hover:bg-red-500/20 text-xs font-bold rounded-xl transition-colors">
                      Kick from Room
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}


      {/* BACKGROUND DECORATION */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] rounded-full bg-indigo-600/10 blur-[120px] pointer-events-none -translate-y-1/2 translate-x-1/4"></div>
      <div className="absolute bottom-0 left-0 w-[500px] h-[500px] rounded-full bg-blue-600/10 blur-[120px] pointer-events-none translate-y-1/4 -translate-x-1/4"></div>
    </div>
  );
}
