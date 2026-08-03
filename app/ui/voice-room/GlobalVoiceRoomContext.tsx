"use client";

import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";
import { useWebT } from "../web-i18n";

export type VoiceRoomState = "lobby" | "room";

export interface VoiceRoomInfo {
  id: string; // from DB
  room_id?: string; // from Redis
  name: string;
  subject: string;
  tags?: string[];
  host_name?: string;
  listeners?: number;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  author: string;
  text: string;
  time: string;
  is_admin?: boolean;
  replyToId?: string;
  replyToAuthor?: string;
  replyToText?: string;
}

export interface VoiceRoomSession {
  id: string;
  room_id: string;
  room_name?: string;
  subject?: string;
  host_id: string;
  start_time: string;
  end_time?: string;
}

export interface RoomState {
  roomId: string;
  hostId: string;
  hostName: string;
  subject: string;
  stagePeers: string[];
  hiddenSpeakers?: string[];
  coHosts?: string[];
  listenersCount: number;
  peerInfo?: Record<string, { user_id: string; name: string; avatar_url: string; role?: string; }>;
}

export interface RaisedHand {
  id: string;
  name: string;
}

export interface GameState {
  active: boolean;
  word: string; // The scrambled word to display
  original_word?: string;
  time_left?: number;
}

export interface Reaction {
  id: string;
  emoji: string;
  peerId: string;
}

export interface GlobalVoiceRoomContextValue {
  state: VoiceRoomState;
  errorMsg: string;
  isLoading: boolean;
  activeRooms: VoiceRoomInfo[];
  myRooms: VoiceRoomInfo[];
  mySessions: VoiceRoomSession[];
  roomState: RoomState | null;
  chatMessages: ChatMessage[];
  isMuted: boolean;
  myId: string;
  isOnStage: boolean;
  reactions: Reaction[];
  raisedHands: RaisedHand[];
  speakingPeers: string[];
  createRoom: (name: string, subject: string, tags?: string[]) => Promise<void>;
  joinRoom: (roomId: string) => void;
  deleteRoom: (roomId: string) => Promise<void>;
  requestStage: () => void;
  approveStage: (peerId: string) => void;
  rejectStage: (peerId: string) => void;
  leaveStage: () => void;
  leaveRoom: () => void;
  endRoom: () => void;
  sendChatMessage: (text: string, replyToId?: string, replyToAuthor?: string, replyToText?: string) => void;
  sendReaction: (emoji: string) => void;
  toggleMute: () => void;
  setErrorMsg: (msg: string) => void;
  demotePeer: (peerId: string) => void;
  kickPeer: (peerId: string) => void;
  forceMutePeer: (peerId: string) => void;
  fetchRooms: () => Promise<void>;
  makeCoHost: (peerId: string) => void;
  sendGift: (targetId: string, giftName: string, amount: number) => void;
  topGifters: {name: string, amount: number}[];
  fetchTopGifters: () => void;
  activeGame: GameState | null;
  startGame: (type: string) => void;
  isMinimized: boolean;
  setIsMinimized: (val: boolean) => void;
  isAdmin: boolean;
  forceJoinStage: () => void;
  forceCloseRoom: () => void;
  toggleHiddenSpeaker: () => void;
  isHiddenSpeaker: boolean;
  isRecording: boolean;
  startRecording: () => void;
  stopRecordingAndUpload: (homeworkId: string) => Promise<void>;
  isSpeakerphone: boolean;
  toggleSpeakerphone: () => void;
}

const GlobalVoiceRoomContext = createContext<GlobalVoiceRoomContextValue | null>(null);

export function GlobalVoiceRoomProvider({ children }: { children: React.ReactNode }) {
  const t = useWebT();
  const [state, setState] = useState<VoiceRoomState>("lobby");
  const [errorMsg, setErrorMsg] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  
  // Lobby state
  const [activeRooms, setActiveRooms] = useState<VoiceRoomInfo[]>([]);
  const [myRooms, setMyRooms] = useState<VoiceRoomInfo[]>([]);
  const [mySessions, setMySessions] = useState<VoiceRoomSession[]>([]);
  
  // Room state
  const [roomState, setRoomState] = useState<RoomState | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [isMuted, setIsMuted] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  
  // Advanced Features State
  const [raisedHands, setRaisedHands] = useState<RaisedHand[]>([]);
  const [reactions, setReactions] = useState<Reaction[]>([]);
  const [speakingPeers, setSpeakingPeers] = useState<string[]>([]);
  const [topGifters, setTopGifters] = useState<{name: string, amount: number}[]>([]);
  const [activeGame, setActiveGame] = useState<GameState | null>(null);
  
  // My state
  const [myId, setMyId] = useState<string>("");
  const myIdRef = useRef<string>("");
  const [isOnStage, setIsOnStage] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [isHiddenSpeaker, setIsHiddenSpeaker] = useState(false);
  const [isSpeakerphone, setIsSpeakerphone] = useState(true); // Default to true (boosted)
  
  // WebRTC
  const wsRef = useRef<WebSocket | null>(null);
  const pcsRef = useRef<Map<string, RTCPeerConnection>>(new Map());
  const localStreamRef = useRef<MediaStream | null>(null);
  const audioElementsRef = useRef<Map<string, HTMLAudioElement>>(new Map());
  
  // AudioContext for Speaking Indicators
  const audioContextRef = useRef<AudioContext | null>(null);
  const analysersRef = useRef<Map<string, AnalyserNode>>(new Map());
  const gainNodesRef = useRef<Map<string, GainNode>>(new Map());
  const rafRef = useRef<number>(0);
  
  // Recording
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<BlobPart[]>([]);
  const mixDestinationRef = useRef<MediaStreamAudioDestinationNode | null>(null);

  const getToken = () => typeof window !== "undefined" ? localStorage.getItem("diamond_token") : "";
  const wsUrl = typeof window !== "undefined" ? `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/api/voice-room-ws` : "";

  const fetchRooms = useCallback(async () => {
    try {
      const token = getToken();
      const headers = token ? { "Authorization": `Bearer ${token}` } : {};
      
      const [activeRes, myRes, sessionsRes] = await Promise.all([
        fetch("/api/voice-rooms/active", { headers }),
        token ? fetch("/api/voice-rooms/my", { headers }) : Promise.resolve({ ok: true, json: () => ({ rooms: [] }) }),
        token ? fetch("/api/voice-rooms/sessions/my", { headers }) : Promise.resolve({ ok: true, json: () => ({ sessions: [] }) })
      ]);
      
      if (activeRes.ok) {
        const data = await activeRes.json();
        setActiveRooms(data.rooms || []);
      }
      if (myRes && myRes.ok) {
        const data = await myRes.json();
        setMyRooms(data.rooms || []);
      }
      if (sessionsRes && sessionsRes.ok) {
        const data = await sessionsRes.json();
        setMySessions(data.sessions || []);
      }
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    if (state === "lobby") {
      fetchRooms();
      const interval = setInterval(fetchRooms, 10000);
      return () => clearInterval(interval);
    }
  }, [state, fetchRooms]);

  const monitorAudioLevels = useCallback(() => {
    if (!audioContextRef.current) return;
    const currentlySpeaking: string[] = [];

    if (localStreamRef.current && !isMuted) {
      const analyser = analysersRef.current.get("local");
      if (analyser) {
        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(dataArray);
        const sum = dataArray.reduce((a, b) => a + b, 0);
        if (sum > 500) {
          currentlySpeaking.push(myIdRef.current);
        }
      }
    }

    analysersRef.current.forEach((analyser, peerId) => {
      if (peerId === "local") return;
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(dataArray);
      const sum = dataArray.reduce((a, b) => a + b, 0);
      if (sum > 500) {
        currentlySpeaking.push(peerId);
      }
    });

    setSpeakingPeers(currentlySpeaking);
    rafRef.current = requestAnimationFrame(monitorAudioLevels);
  }, [isMuted]);

  useEffect(() => {
    if (state === "room") {
      rafRef.current = requestAnimationFrame(monitorAudioLevels);
    } else {
      cancelAnimationFrame(rafRef.current);
    }
    return () => cancelAnimationFrame(rafRef.current);
  }, [state, monitorAudioLevels]);

  const cleanupWebRTC = () => {
    pcsRef.current.forEach(pc => pc.close());
    pcsRef.current.clear();
    
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((t) => t.stop());
      localStreamRef.current = null;
    }
    audioElementsRef.current.forEach(audio => {
      audio.srcObject = null;
      audio.remove();
    });
    audioElementsRef.current.clear();
    
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    analysersRef.current.clear();
    cancelAnimationFrame(rafRef.current);
    
    setIsOnStage(false);
    setIsMuted(false);
    setRaisedHands([]);
    setSpeakingPeers([]);
    setIsMinimized(false);
    
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
    mixDestinationRef.current = null;
  };

  const forceLocalMute = () => {
    if (localStreamRef.current) {
      const audioTrack = localStreamRef.current.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = false;
        setIsMuted(true);
      }
    }
  };

  const startMedia = async () => {
    try {
      const isAndroid = typeof navigator !== "undefined" && /android/i.test(navigator.userAgent);
      // We must use echoCancellation to prevent screeching feedback loops!
      // But we try to pass echoCancellationType: 'browser' to see if Chrome will use software AEC and keep Media Volume.
      const audioConstraints = isAndroid ? { 
        echoCancellation: true, 
        echoCancellationType: 'browser',
        noiseSuppression: true, 
        autoGainControl: true 
      } as any : true;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });
      localStreamRef.current = stream;
      
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      const source = audioContextRef.current.createMediaStreamSource(stream);
      const analyser = audioContextRef.current.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analysersRef.current.set("local", analyser);

      if (mixDestinationRef.current) {
        analyser.connect(mixDestinationRef.current);
      }

      return true;
    } catch (e) {
      setErrorMsg(t("voiceroom.mic_denied") || "Mikrofonga ruxsat berilmadi. Iltimos ruxsat bering.");
      return false;
    }
  };

  const connectWebSocket = useCallback((roomId: string) => {
    if (wsRef.current) return;
    const token = getToken();
    const urlWithToken = `${wsUrl}?token=${token || ""}`;
    const ws = new WebSocket(urlWithToken);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ action: "join_room", room_id: roomId }));
    };

    ws.onmessage = async (event) => {
      try {
        const msg = JSON.parse(event.data);
        
        if (msg.type === "room_joined") {
          setState("room");
          setMyId(msg.my_id);
          myIdRef.current = msg.my_id;
          setIsAdmin(msg.is_admin || false);
        } else if (msg.type === "room_state") {
          setRoomState({
            roomId: msg.room_id,
            hostId: msg.host_id,
            hostName: msg.host_name,
            subject: msg.subject,
            stagePeers: msg.stage_peers || [],
            hiddenSpeakers: msg.hidden_speakers || [],
            coHosts: msg.co_hosts || [],
            listenersCount: msg.listeners_count,
            peerInfo: msg.peer_info || {}
          });
          
          const isNowHidden = msg.hidden_speakers?.includes(myIdRef.current) || false;
          setIsHiddenSpeaker(isNowHidden);
          
          if ((msg.stage_peers?.includes(myIdRef.current) || isNowHidden) && !localStreamRef.current) {
            setIsOnStage(true);
            const mediaOk = await startMedia();
            if (mediaOk) {
              pcsRef.current.forEach(async (pc, peerId) => {
                if (localStreamRef.current) {
                  let hasTrack = false;
                  pc.getSenders().forEach(sender => {
                    if (sender.track) hasTrack = true;
                  });
                  if (!hasTrack) {
                    localStreamRef.current.getTracks().forEach((track) => {
                      pc.addTrack(track, localStreamRef.current!);
                    });
                    try {
                      const offer = await pc.createOffer();
                      await pc.setLocalDescription(offer);
                      wsRef.current?.send(JSON.stringify({
                        action: "webrtc_signal",
                        target_id: peerId,
                        data: { type: "offer", offer }
                      }));
                    } catch (e) {
                      console.error("Renegotiation failed", e);
                    }
                  }
                }
              });

              const connectTo = [...(msg.stage_peers || []), ...(msg.hidden_speakers || [])];
              connectTo.forEach(pid => {
                if (pid !== myIdRef.current) {
                  setupWebRTC(pid, true);
                }
              });
            }
          } else if (!(msg.stage_peers?.includes(myIdRef.current) || isNowHidden)) {
             if (localStreamRef.current) {
                localStreamRef.current.getTracks().forEach((t) => t.stop());
                localStreamRef.current = null;
             }
             setIsOnStage(false);
             setIsMuted(false);
             
             // Connect to stage peers and hidden speakers as a listener
             const connectTo = [...(msg.stage_peers || []), ...(msg.hidden_speakers || [])];
             connectTo.forEach((peerId: string) => {
                if (peerId !== myIdRef.current && !pcsRef.current.has(peerId)) {
                   setupWebRTC(peerId, true);
                }
             });
          }
        } else if (msg.type === "chat_message") {
          setChatMessages(prev => [...prev, {
            id: Math.random().toString(),
            author: msg.author,
            text: msg.text,
            time: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}),
            replyToId: msg.replyToId,
            replyToAuthor: msg.replyToAuthor,
            replyToText: msg.replyToText
          }]);
        } else if (msg.type === "webrtc_signal") {
          if (msg.data && msg.data.type === "stage_request") {
             setRaisedHands(prev => {
                if (prev.find(h => h.id === msg.from_id)) return prev;
                return [...prev, { id: msg.from_id, name: msg.data.peer_name }];
             });
          } else if (msg.data && msg.data.type === "force_mute") {
             forceLocalMute();
          } else if (msg.data && msg.data.type === "demoted") {
             if (localStreamRef.current) {
                localStreamRef.current.getTracks().forEach((t) => t.stop());
                localStreamRef.current = null;
             }
             setIsOnStage(false);
          } else if (msg.data && msg.data.type === "kicked") {
             leaveRoom();
             setErrorMsg(t("voiceroom.kicked") || "Siz xonadan chetlatildingiz.");
          } else if (msg.data && msg.data.type === "gift") {
             setChatMessages(prev => [...prev, {
                id: Math.random().toString(),
                author: "Tizim",
                text: `🎁 ${msg.data.senderName} yubordi: ${msg.data.giftName} (${msg.data.amount} Dcoin)`,
                time: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
             }]);
             // Show floating animation
             const reactionId = Math.random().toString();
             setReactions(prev => [...prev, { id: reactionId, emoji: "🎁", peerId: "system" }]);
             setTimeout(() => {
               setReactions(prev => prev.filter(r => r.id !== reactionId));
             }, 3000);
          } else {
             await handleSignalingData(msg.from_id, msg.data);
          }
        } else if (msg.type === "reaction") {
          const reactionId = Math.random().toString();
          setReactions(prev => [...prev, { id: reactionId, emoji: msg.emoji, peerId: msg.peer_id }]);
          setTimeout(() => {
            setReactions(prev => prev.filter(r => r.id !== reactionId));
          }, 3000);
        } else if (msg.type === "peer_left" || msg.type === "stage_left") {
          removePeer(msg.peer_id);
          setRaisedHands(prev => prev.filter(h => h.id !== msg.peer_id));
        } else if (msg.type === "top_gifters_list") {
          setTopGifters(msg.gifters || []);
        } else if (msg.type === "game_state") {
          setActiveGame(msg.game);
        } else if (msg.type === "game_ended") {
          setActiveGame(null);
        } else if (msg.type === "left_room" || msg.type === "room_closed") {
          if (msg.type === "room_closed") setErrorMsg(t("voiceroom.closed_alert") || "Xona yopildi.");
          setState("lobby");
          setRoomState(null);
          setChatMessages([]);
          cleanupWebRTC();
          wsRef.current = null;
        } else if (msg.type === "error") {
          setErrorMsg(msg.message);
        }
      } catch (err) {
        console.error("WS message error", err);
      }
    };

    ws.onerror = () => {
      setErrorMsg(t("voiceroom.connection_error") || "Ulanishda xatolik yuz berdi. Iltimos qayta urinib ko'ring.");
    };

    ws.onclose = () => {
      wsRef.current = null;
    };
  }, [wsUrl]);

  const removePeer = (peerId: string) => {
    const pc = pcsRef.current.get(peerId);
    if (pc) {
      pc.close();
      pcsRef.current.delete(peerId);
    }
    const audio = audioElementsRef.current.get(peerId);
    if (audio) {
      audio.srcObject = null;
      audio.remove();
      audioElementsRef.current.delete(peerId);
    }
    analysersRef.current.delete(peerId);
  };

  const setupWebRTC = async (peerId: string, isInitiator: boolean) => {
    if (pcsRef.current.has(peerId)) return;

    const pc = new RTCPeerConnection({
      iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
    });
    pcsRef.current.set(peerId, pc);

    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => {
        pc.addTrack(track, localStreamRef.current!);
      });
    } else {
      pc.addTransceiver("audio", { direction: "recvonly" });
    }

    pc.ontrack = (event) => {
      let audio = audioElementsRef.current.get(peerId);
      if (!audio) {
        audio = document.createElement("audio");
        audio.autoplay = true;
        audio.setAttribute("playsinline", "true");
        audio.style.display = "none";
        document.body.appendChild(audio);
        audioElementsRef.current.set(peerId, audio);
      }
      const isAndroid = typeof navigator !== "undefined" && /android/i.test(navigator.userAgent);
      
      // On Android, HTML audio element plays through Earpiece during WebRTC calls due to MODE_IN_COMMUNICATION.
      // We mute it so we don't hear the earpiece, but we MUST keep srcObject and play() to feed the Web Audio API.
      audio.srcObject = event.streams[0];
      audio.muted = isAndroid;
      
      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise.catch(e => {
           console.error("Audio autoplay failed:", e);
           // Fallback: Try to play on first user interaction if blocked
           const resumeAudio = () => {
             audio?.play().catch(console.error);
             document.removeEventListener('click', resumeAudio);
             document.removeEventListener('touchstart', resumeAudio);
           };
           document.addEventListener('click', resumeAudio);
           document.addEventListener('touchstart', resumeAudio);
        });
      }

      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      if (audioContextRef.current.state === "suspended") {
        audioContextRef.current.resume().catch(console.error);
      }

      try {
        const stream = event.streams[0];
        const source = audioContextRef.current.createMediaStreamSource(stream);
        const gainNode = audioContextRef.current.createGain();
        gainNode.gain.value = isSpeakerphone ? 4.0 : 1.0;
        gainNodesRef.current.set(peerId, gainNode);
        source.connect(gainNode);
        
        const analyser = audioContextRef.current.createAnalyser();
        analyser.fftSize = 256;
        gainNode.connect(analyser);
        analysersRef.current.set(peerId, analyser);
        
        // Route to AudioContext destination on Android to force output through the Loudspeaker
        if (isAndroid) {
          analyser.connect(audioContextRef.current.destination);
        }
        
        if (mixDestinationRef.current) {
          analyser.connect(mixDestinationRef.current);
        }
      } catch (e) {
        console.warn("Could not create analyser for remote stream", e);
      }
    };

    pc.onicecandidate = (event) => {
      if (event.candidate && wsRef.current) {
        wsRef.current.send(JSON.stringify({
          action: "webrtc_signal",
          target_id: peerId,
          data: { type: "candidate", candidate: event.candidate }
        }));
      }
    };

    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "disconnected" || pc.connectionState === "failed") {
        removePeer(peerId);
      }
    };

    if (isInitiator) {
      try {
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        wsRef.current?.send(JSON.stringify({
          action: "webrtc_signal",
          target_id: peerId,
          data: { type: "offer", offer }
        }));
      } catch (e) {
        console.error("Error creating offer", e);
      }
    }
  };

  const handleSignalingData = async (fromId: string, data: any) => {
    let pc = pcsRef.current.get(fromId);
    if (!pc) {
      await setupWebRTC(fromId, false);
      pc = pcsRef.current.get(fromId);
    }
    if (!pc) return;

    if (data.type === "offer") {
      await pc.setRemoteDescription(new RTCSessionDescription(data.offer));
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      wsRef.current?.send(JSON.stringify({
        action: "webrtc_signal",
        target_id: fromId,
        data: { type: "answer", answer }
      }));
    } else if (data.type === "answer") {
      await pc.setRemoteDescription(new RTCSessionDescription(data.answer));
    } else if (data.type === "candidate") {
      await pc.addIceCandidate(new RTCIceCandidate(data.candidate));
    }
  };

  const createRoom = async (name: string, subject: string, tags?: string[]) => {
    setErrorMsg("");
    // Unlock AudioContext on user gesture
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
    }
    if (audioContextRef.current.state === "suspended") {
      audioContextRef.current.resume().catch(console.error);
    }
    setIsLoading(true);
    try {
      const token = getToken();
      const res = await fetch("/api/voice-rooms/create", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { "Authorization": `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ name, subject, tags: tags || [] })
      });
      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.detail || t("common.error") || "Xatolik yuz berdi");
      } else {
        await fetchRooms();
        connectWebSocket(data.room_id);
      }
    } catch (e) {
      setErrorMsg(t("common.networkError") || "Tarmoq xatosi");
    } finally {
      setIsLoading(false);
    }
  };

  const joinRoom = (roomId: string) => {
    setErrorMsg("");
    // Unlock AudioContext on user gesture
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
    }
    if (audioContextRef.current.state === "suspended") {
      audioContextRef.current.resume().catch(console.error);
    }
    
    setRoomState(null);
    connectWebSocket(roomId);
  };

  const deleteRoom = async (roomId: string) => {
    try {
      const token = getToken();
      await fetch(`/api/voice-rooms/${roomId}`, {
        method: "DELETE",
        headers: {
          ...(token ? { "Authorization": `Bearer ${token}` } : {})
        }
      });
      fetchRooms();
    } catch (e) {
      console.error(e);
    }
  };

  const requestStage = () => {
    wsRef.current?.send(JSON.stringify({ action: "request_stage" }));
  };
  
  const forceJoinStage = () => {
    wsRef.current?.send(JSON.stringify({ action: "force_join_stage" }));
  };
  
  const forceCloseRoom = () => {
    wsRef.current?.send(JSON.stringify({ action: "force_close_room" }));
  };
  
  const toggleHiddenSpeaker = () => {
    wsRef.current?.send(JSON.stringify({ action: "toggle_hidden_speaker" }));
  };
  
  const approveStage = (peerId: string) => {
    wsRef.current?.send(JSON.stringify({ action: "approve_stage", peer_id: peerId }));
    setRaisedHands(prev => prev.filter(h => h.id !== peerId));
  };

  const rejectStage = (peerId: string) => {
    setRaisedHands(prev => prev.filter(h => h.id !== peerId));
  };

  const leaveStage = () => {
    wsRef.current?.send(JSON.stringify({ action: "leave_stage" }));
    cleanupWebRTC();
  };

  const leaveRoom = () => {
    wsRef.current?.send(JSON.stringify({ action: "leave_room" }));
    cleanupWebRTC();
    if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
    }
    setState("lobby");
    setRoomState(null);
  };

  const endRoom = () => {
    wsRef.current?.send(JSON.stringify({ action: "end_room" }));
    cleanupWebRTC();
    if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
    }
    setState("lobby");
    setRoomState(null);
  };

  const sendChatMessage = (text: string, replyToId?: string, replyToAuthor?: string, replyToText?: string) => wsRef.current?.send(JSON.stringify({ 
    action: "chat_message", 
    text,
    replyToId,
    replyToAuthor,
    replyToText 
  }));
  
  const sendReaction = (emoji: string) => wsRef.current?.send(JSON.stringify({ action: "reaction", emoji }));

  const toggleMute = () => {
    if (localStreamRef.current) {
      const audioTrack = localStreamRef.current.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
        setIsMuted(!audioTrack.enabled);
      }
    }
  };

  const demotePeer = (peerId: string) => {
     wsRef.current?.send(JSON.stringify({ action: "demote_peer", peer_id: peerId }));
  };
  const kickPeer = (peerId: string) => {
     wsRef.current?.send(JSON.stringify({ action: "kick_peer", peer_id: peerId }));
  };
  const toggleSpeakerphone = () => {
    const newVal = !isSpeakerphone;
    setIsSpeakerphone(newVal);
    
    // Apply gain boost
    gainNodesRef.current.forEach(gainNode => {
       gainNode.gain.value = newVal ? 4.0 : 1.0;
    });
    
    // Apply sink ID if supported
    audioElementsRef.current.forEach(audio => {
       if (typeof (audio as any).setSinkId === "function") {
         navigator.mediaDevices.enumerateDevices().then(devices => {
           if (newVal) {
             const speaker = devices.find(d => d.kind === "audiooutput" && (d.label.toLowerCase().includes("speaker") || d.deviceId.toLowerCase().includes("speaker")));
             if (speaker) (audio as any).setSinkId(speaker.deviceId).catch(console.error);
             else (audio as any).setSinkId("default").catch(console.error);
           } else {
             const earpiece = devices.find(d => d.kind === "audiooutput" && d.label.toLowerCase().includes("earpiece"));
             if (earpiece) (audio as any).setSinkId(earpiece.deviceId).catch(console.error);
           }
         });
       }
    });
  };

  const forceMutePeer = (peerId: string) => {
     wsRef.current?.send(JSON.stringify({ action: "force_mute", target_id: peerId }));
  };
  const makeCoHost = (peerId: string) => {
     wsRef.current?.send(JSON.stringify({ action: "make_cohost", target_id: peerId }));
  };
  const sendGift = (targetId: string, giftName: string, amount: number) => {
     wsRef.current?.send(JSON.stringify({ action: "gift_broadcast", target_id: targetId, giftName, amount }));
  };

  const fetchTopGifters = () => {
     wsRef.current?.send(JSON.stringify({ action: "get_top_gifters" }));
  };

  const startGame = (type: string) => {
     wsRef.current?.send(JSON.stringify({ action: "start_game", type }));
  };

  const startRecording = useCallback(() => {
    if (!audioContextRef.current) return;
    try {
      const dest = audioContextRef.current.createMediaStreamDestination();
      mixDestinationRef.current = dest;
      
      analysersRef.current.forEach(analyser => {
        analyser.connect(dest);
      });
      
      const recorder = new MediaRecorder(dest.stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = recorder;
      recordedChunksRef.current = [];
      
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordedChunksRef.current.push(e.data);
      };
      
      recorder.start(1000);
      setIsRecording(true);
    } catch (e) {
      console.error("Recording failed", e);
      setErrorMsg(t("voiceroom.record_error") || "Ovoz yozib olishda xatolik yuz berdi. Brauzeringiz qo'llab-quvvatlamasligi mumkin.");
    }
  }, []);

  const stopRecordingAndUpload = async (homeworkId: string) => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      
      await new Promise(r => setTimeout(r, 500));
      
      if (recordedChunksRef.current.length === 0) {
        setErrorMsg(t("voiceroom.no_audio_recorded") || "Hech qanday ovoz yozilmadi.");
        return;
      }
      
      const blob = new Blob(recordedChunksRef.current, { type: "audio/webm" });
      const file = new File([blob], `voiceroom_${Date.now()}.webm`, { type: "audio/webm" });
      
      try {
        const formData = new FormData();
        formData.append("file", file);
        
        const token = getToken();
        const uploadRes = await fetch("/homework/upload-voice", {
          method: "POST",
          headers: { "Authorization": `Bearer ${token}` },
          body: formData
        });
        const uploadData = await uploadRes.json();
        
        if (uploadData.url) {
           const res = await fetch(`/student/homework/${homeworkId}/submit-voiceroom`, {
             method: "POST",
             headers: { 
               "Authorization": `Bearer ${token}`,
               "Content-Type": "application/json"
             },
             body: JSON.stringify({ recorded_audio_url: uploadData.url })
           });
           
           if (!res.ok) {
             const data = await res.json();
             throw new Error(data.detail || "Submission failed");
           }
           setErrorMsg("✓ " + (t("voiceroom.hw_submitted_alert") || "Homework muvaffaqiyatli topshirildi va yozuv yuborildi!"));
        } else {
           throw new Error("No URL returned from upload");
        }
      } catch (e: any) {
        console.error(e);
        setErrorMsg((t("voiceroom.record_upload_error") || "Yozuvni yuklashda xatolik yuz berdi: ") + e.message);
      }
    }
  };

  return (
    <GlobalVoiceRoomContext.Provider
      value={{
        state, errorMsg, isLoading, activeRooms, myRooms, mySessions, roomState,
        chatMessages, isMuted, myId, isOnStage, reactions, raisedHands, speakingPeers,
        createRoom, joinRoom, deleteRoom, requestStage, approveStage, rejectStage,
        leaveStage, leaveRoom, endRoom, sendChatMessage, sendReaction, toggleMute, setErrorMsg,
        demotePeer, kickPeer, forceMutePeer, fetchRooms, makeCoHost, sendGift,
        topGifters, fetchTopGifters,
        activeGame, startGame,
        isMinimized, setIsMinimized,
        isAdmin, forceJoinStage, forceCloseRoom, toggleHiddenSpeaker, isHiddenSpeaker,
        isRecording, startRecording, stopRecordingAndUpload,
        isSpeakerphone, toggleSpeakerphone
      }}
    >
      {children}
    </GlobalVoiceRoomContext.Provider>
  );
}

export function useGlobalVoiceRoom() {
  const context = useContext(GlobalVoiceRoomContext);
  if (!context) {
    throw new Error("useGlobalVoiceRoom must be used within GlobalVoiceRoomProvider");
  }
  return context;
}
