import { useEffect, useRef, useState, useCallback } from "react";

export type VoiceRoomState = "lobby" | "room";

export interface VoiceRoomInfo {
  id: string; // from DB
  room_id?: string; // from Redis
  name: string;
  subject: string;
  host_name?: string;
  listeners?: number;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  author: string;
  text: string;
  time: string;
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
  listenersCount: number;
}

export interface RaisedHand {
  id: string;
  name: string;
}

export interface Reaction {
  id: string;
  emoji: string;
  peerId: string;
}

interface UseVoiceRoomProps {
  role: "student" | "moderator";
  wsUrl: string;
}

export function useVoiceRoom({ role, wsUrl }: UseVoiceRoomProps) {
  const [state, setState] = useState<VoiceRoomState>("lobby");
  const [errorMsg, setErrorMsg] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  
  // Lobby state
  const [activeRooms, setActiveRooms] = useState<VoiceRoomInfo[]>([]);
  const [myRooms, setMyRooms] = useState<VoiceRoomInfo[]>([]);
  const [mySessions, setMySessions] = useState<VoiceRoomSession[]>([]);
  const [currentTab, setCurrentTab] = useState<"live" | "my_rooms" | "history">("live");
  
  // Room state
  const [roomState, setRoomState] = useState<RoomState | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [isMuted, setIsMuted] = useState(false);
  
  // Advanced Features State
  const [raisedHands, setRaisedHands] = useState<RaisedHand[]>([]);
  const [reactions, setReactions] = useState<Reaction[]>([]);
  const [speakingPeers, setSpeakingPeers] = useState<string[]>([]);
  
  // My state
  const [myId, setMyId] = useState<string>("");
  const myIdRef = useRef<string>("");
  const [isOnStage, setIsOnStage] = useState(false);
  
  // WebRTC
  const wsRef = useRef<WebSocket | null>(null);
  const pcsRef = useRef<Map<string, RTCPeerConnection>>(new Map());
  const localStreamRef = useRef<MediaStream | null>(null);
  const audioElementsRef = useRef<Map<string, HTMLAudioElement>>(new Map());
  
  // AudioContext for Speaking Indicators
  const audioContextRef = useRef<AudioContext | null>(null);
  const analysersRef = useRef<Map<string, AnalyserNode>>(new Map());
  const rafRef = useRef<number>(0);

  const getToken = () => typeof window !== "undefined" ? localStorage.getItem("diamond_token") : "";

  const fetchRooms = async () => {
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
  };

  useEffect(() => {
    if (state === "lobby") {
      fetchRooms();
      const interval = setInterval(fetchRooms, 10000);
      return () => clearInterval(interval);
    }
  }, [state]);

  const monitorAudioLevels = useCallback(() => {
    if (!audioContextRef.current) return;
    const currentlySpeaking: string[] = [];

    // Check local stream
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

    // Check remote streams
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
        } else if (msg.type === "room_state") {
          setRoomState({
            roomId: msg.room_id,
            hostId: msg.host_id,
            hostName: msg.host_name,
            subject: msg.subject,
            stagePeers: msg.stage_peers || [],
            listenersCount: msg.listeners_count
          });
          
          if (msg.stage_peers?.includes(myIdRef.current) && !localStreamRef.current) {
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

              msg.stage_peers.forEach((peerId: string) => {
                if (peerId !== myIdRef.current) {
                  setupWebRTC(peerId, true);
                }
              });
            }
          } else if (!msg.stage_peers?.includes(myIdRef.current) && localStreamRef.current) {
             // Demoted
             if (localStreamRef.current) {
                localStreamRef.current.getTracks().forEach((t) => t.stop());
                localStreamRef.current = null;
             }
             setIsOnStage(false);
             setIsMuted(false);
          }
        } else if (msg.type === "chat_message") {
          setChatMessages(prev => [...prev, {
            id: Math.random().toString(),
            author: msg.author,
            text: msg.text,
            time: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
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
             // Will be handled by room_state update, but we can proactively clean
             if (localStreamRef.current) {
                localStreamRef.current.getTracks().forEach((t) => t.stop());
                localStreamRef.current = null;
             }
             setIsOnStage(false);
          } else if (msg.data && msg.data.type === "kicked") {
             leaveRoom();
             setErrorMsg("Siz xonadan chetlatildingiz.");
          } else {
             await handleSignalingData(msg.from_id, msg.data);
          }
        } else if (msg.type === "reaction") {
          const reactionId = Math.random().toString();
          setReactions(prev => [...prev, { id: reactionId, emoji: msg.emoji, peerId: msg.peer_id }]);
          setTimeout(() => {
            setReactions(prev => prev.filter(r => r.id !== reactionId));
          }, 3000); // Remove after 3s
        } else if (msg.type === "peer_left" || msg.type === "stage_left") {
          removePeer(msg.peer_id);
          setRaisedHands(prev => prev.filter(h => h.id !== msg.peer_id));
        } else if (msg.type === "left_room" || msg.type === "room_closed") {
          if (msg.type === "room_closed") setErrorMsg("Xona yopildi.");
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
      setErrorMsg("Ulanishda xatolik yuz berdi. Iltimos qayta urinib ko'ring.");
    };

    ws.onclose = () => {
      wsRef.current = null;
    };
  }, [wsUrl]);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      cleanupWebRTC();
    };
  }, []);

  const startMedia = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      localStreamRef.current = stream;
      
      // Setup Local Audio Analyser
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      const source = audioContextRef.current.createMediaStreamSource(stream);
      const analyser = audioContextRef.current.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analysersRef.current.set("local", analyser);

      return true;
    } catch (e) {
      setErrorMsg("Mikrofonga ruxsat berilmadi. Iltimos brauzer sozlamalaridan mikrofonni yoqing.");
      return false;
    }
  };

  const createRoom = async (name: string, subject: string) => {
    setErrorMsg("");
    setIsLoading(true);
    try {
      const token = getToken();
      const res = await fetch("/api/voice-rooms/create", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { "Authorization": `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ name, subject })
      });
      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.detail || "Xatolik yuz berdi");
      } else {
        await fetchRooms(); // Refresh lists
        connectWebSocket(data.room_id);
      }
    } catch (e) {
      setErrorMsg("Tarmoq xatosi");
    } finally {
      setIsLoading(false);
    }
  };

  const joinRoom = (roomId: string) => {
    setErrorMsg("");
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
    wsRef.current?.send(JSON.stringify({ 
      action: "request_stage"
    }));
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
    cleanupWebRTC(); // They revert to listener
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

  const sendChatMessage = (text: string) => wsRef.current?.send(JSON.stringify({ action: "chat_message", text }));
  
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
    }

    pc.ontrack = (event) => {
      let audio = audioElementsRef.current.get(peerId);
      if (!audio) {
        audio = document.createElement("audio");
        audio.autoplay = true;
        audio.style.display = "none";
        document.body.appendChild(audio);
        audioElementsRef.current.set(peerId, audio);
      }
      audio.srcObject = event.streams[0];
      audio.play().catch(console.error);

      // Setup analyser for remote track
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      const stream = event.streams[0];
      // Note: createMediaStreamSource sometimes fails on empty remote tracks in Safari, but standard in Chrome.
      try {
        const source = audioContextRef.current.createMediaStreamSource(stream);
        const analyser = audioContextRef.current.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        analysersRef.current.set(peerId, analyser);
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

  // Moderator actions
  const demotePeer = (peerId: string) => {
     wsRef.current?.send(JSON.stringify({ action: "demote_peer", peer_id: peerId }));
  };
  const kickPeer = (peerId: string) => {
     wsRef.current?.send(JSON.stringify({ action: "kick_peer", peer_id: peerId }));
  };
  const forceMutePeer = (peerId: string) => {
     wsRef.current?.send(JSON.stringify({ action: "force_mute", target_id: peerId }));
  };

  return {
    state,
    errorMsg,
    isLoading,
    currentTab,
    setCurrentTab,
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
    sendChatMessage,
    sendReaction,
    toggleMute,
    setErrorMsg,
    demotePeer,
    kickPeer,
    forceMutePeer,
    fetchRooms
  };
}
