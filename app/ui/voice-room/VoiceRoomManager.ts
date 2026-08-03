export class VoiceRoomManager {
  private ws: WebSocket | null = null;
  private peerConnections: Map<string, RTCPeerConnection> = new Map();
  private localStream: MediaStream | null = null;
  
  public onStateChange: (state: "idle" | "waiting" | "matched" | "connected" | "error") => void = () => {};
  public onRemoteStream: (peerId: string, stream: MediaStream) => void = () => {};
  public onPeerDisconnected: (peerId: string) => void = () => {};
  public onError: (err: string) => void = () => {};

  public roomId: string | null = null;
  public myPeerId: string | null = null;

  constructor(private url: string, private subject: string, private role: string = "student") {}

  public async start() {
    try {
      this.localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      
      this.ws = new WebSocket(this.url);
      
      this.ws.onopen = () => {
        this.ws?.send(JSON.stringify({ action: "join_queue", subject: this.subject, role: this.role }));
        this.onStateChange("waiting");
      };

      this.ws.onmessage = async (event) => {
        try {
          const msg = JSON.parse(event.data);
          
          if (msg.type === "waiting") {
            this.onStateChange("waiting");
          } else if (msg.type === "room_joined") {
            this.roomId = msg.room_id;
            this.myPeerId = msg.peer_id;
            this.onStateChange("matched");
            
            // Connect to existing peers in the room
            for (const peerId of msg.peers) {
              await this.createPeerConnection(peerId, true);
            }
          } else if (msg.type === "peer_joined") {
            // A new peer joined, wait for their offer
            await this.createPeerConnection(msg.peer_id, false);
          } else if (msg.type === "signal") {
            await this.handleSignal(msg.from_peer_id, msg.signal_data);
          } else if (msg.type === "peer_disconnected") {
            this.removePeer(msg.peer_id);
            if (this.peerConnections.size === 0 && this.role === "student") {
              // If everyone left and I'm a student, end it or wait. We will just end it for simplicity.
              // Actually, we'll let the UI handle it via onPeerDisconnected.
            }
          } else if (msg.type === "error") {
            this.onError(msg.message);
          }
        } catch (err) {
          console.error("WS parse error", err);
        }
      };

      this.ws.onerror = (e) => {
        this.onError("WebSocket error");
        this.cleanup();
      };

      this.ws.onclose = () => {
        this.cleanup();
      };
      
    } catch (err: any) {
      this.onError(err.message || "Microphone access denied");
    }
  }

  public async joinSpecificRoom(roomId: string) {
    try {
      this.localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      this.ws = new WebSocket(this.url);
      this.ws.onopen = () => {
        this.ws?.send(JSON.stringify({ action: "join_room", room_id: roomId, role: this.role }));
        this.onStateChange("waiting");
      };
      // Reuse onmessage from start(), but refactored:
      this.attachWsListeners();
    } catch (err: any) {
      this.onError(err.message || "Microphone access denied");
    }
  }

  private attachWsListeners() {
    if (!this.ws) return;
    this.ws.onmessage = async (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "waiting") {
          this.onStateChange("waiting");
        } else if (msg.type === "room_joined") {
          this.roomId = msg.room_id;
          this.myPeerId = msg.peer_id;
          this.onStateChange("matched");
          for (const peerId of msg.peers) {
            await this.createPeerConnection(peerId, true);
          }
        } else if (msg.type === "peer_joined") {
          await this.createPeerConnection(msg.peer_id, false);
        } else if (msg.type === "signal") {
          await this.handleSignal(msg.from_peer_id, msg.signal_data);
        } else if (msg.type === "peer_disconnected") {
          this.removePeer(msg.peer_id);
        } else if (msg.type === "error") {
          this.onError(msg.message);
        }
      } catch (err) {
        console.error("WS parse error", err);
      }
    };
    this.ws.onerror = (e) => {
      this.onError("WebSocket error");
      this.cleanup();
    };
    this.ws.onclose = () => {
      this.cleanup();
    };
  }

  private async createPeerConnection(peerId: string, isCaller: boolean) {
    const pc = new RTCPeerConnection({
      iceServers: [
        { urls: "stun:stun.l.google.com:19302" },
        { urls: "stun:stun1.l.google.com:19302" },
      ]
    });
    this.peerConnections.set(peerId, pc);

    if (this.localStream) {
      this.localStream.getTracks().forEach(track => {
        if (this.localStream) {
          pc.addTrack(track, this.localStream);
        }
      });
    }

    pc.ontrack = (event) => {
      this.onRemoteStream(peerId, event.streams[0]);
      this.onStateChange("connected");
    };

    pc.onicecandidate = (event) => {
      if (event.candidate && this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({
          action: "signal",
          target_peer_id: peerId,
          signal_data: { ice: event.candidate }
        }));
      }
    };

    if (isCaller) {
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      this.ws?.send(JSON.stringify({
        action: "signal",
        target_peer_id: peerId,
        signal_data: { sdp: pc.localDescription }
      }));
    }
  }

  private async handleSignal(peerId: string, data: any) {
    let pc = this.peerConnections.get(peerId);
    if (!pc) {
      console.warn("Received signal for unknown peer", peerId);
      return;
    }
    
    if (data.sdp) {
      await pc.setRemoteDescription(new RTCSessionDescription(data.sdp));
      if (data.sdp.type === "offer") {
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        this.ws?.send(JSON.stringify({
          action: "signal",
          target_peer_id: peerId,
          signal_data: { sdp: pc.localDescription }
        }));
      }
    } else if (data.ice) {
      try {
        await pc.addIceCandidate(new RTCIceCandidate(data.ice));
      } catch (e) {
        console.error("Error adding ice candidate", e);
      }
    }
  }

  private removePeer(peerId: string) {
    const pc = this.peerConnections.get(peerId);
    if (pc) {
      pc.close();
      this.peerConnections.delete(peerId);
    }
    this.onPeerDisconnected(peerId);
  }

  public setMuted(muted: boolean) {
    if (this.localStream) {
      this.localStream.getAudioTracks().forEach(track => {
        track.enabled = !muted;
      });
    }
  }

  public cleanup() {
    this.onStateChange("idle");
    if (this.localStream) {
      this.localStream.getTracks().forEach(track => track.stop());
      this.localStream = null;
    }
    this.peerConnections.forEach(pc => pc.close());
    this.peerConnections.clear();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
