# Diamond Speaking Live Video media node

This directory prepares the **media plane** for Diamond Speaking live video.
It is deliberately separate from the current web/API server: the existing
server already owns TCP port 443 for `diamond-education.uz`, while dependable
WebRTC fallback needs TURN/TLS on TCP 443.

The application backend remains the authority for accounts, room creation and
short-lived join tokens.  LiveKit transports only encrypted audio/video/data;
no LiveKit secret is ever placed in Flutter, browser code or Git.

## Target topology

```
Speaking app -> https://diamond-education.uz/api/speaking/live-video/*
                         | short-lived, signed join token
                         v
                 wss://live.diamond-education.uz (dedicated media VM)
                         |
          LiveKit SFU + embedded TURN/TLS + Redis + Caddy
```

Use a dedicated public IPv4 media VM, not the current website VM.  It lets the
media node own TCP/UDP port 443 without interrupting the website and gives
TURN/TLS a reliable path from corporate Wi-Fi, VPNs and mobile networks.

## DNS required before starting anything

Create these records for the dedicated media VM public IP:

```text
live.diamond-education.uz.       A   <LIVEKIT_MEDIA_VM_IPV4>
turn.live.diamond-education.uz.  A   <LIVEKIT_MEDIA_VM_IPV4>
```

Do not point either name at `31.220.87.193` while the website Caddy owns its
TCP 443 port.

## Deployment package (do this only when deployment is authorized)

The official LiveKit generator creates the matched Caddy, Docker Compose,
Redis, LiveKit and systemd files.  Run it from the **dedicated media VM** only:

```bash
sudo install -d -m 700 /opt/livekit
sudo docker run --rm -it -v /opt/livekit:/output livekit/generate
```

During the generator prompts use:

- primary domain: `live.diamond-education.uz`
- TURN domain: `turn.live.diamond-education.uz`
- no ingress, egress or recording for the first release
- a generated high-entropy API key and secret

The generator produces `/opt/livekit` files and a `livekit-docker` systemd
service. Keep its generated `.env` at mode `0600`; it must never be committed.
Before starting the service, run the media preflight below.

## Backend configuration

On the existing Diamond API host, add these values to its protected `.env`.
They are server-only values; restart is required later for FastAPI to read them.

```ini
LIVEKIT_URL=wss://live.diamond-education.uz
LIVEKIT_INTERNAL_URL=https://live.diamond-education.uz
LIVEKIT_API_KEY=<generated-on-media-vm>
LIVEKIT_API_SECRET=<generated-on-media-vm>
```

`LIVEKIT_INTERNAL_URL` is intentionally HTTPS because the API host and media
VM are separate. The control API is authenticated with a 60-second server JWT.

## Capacity policy

The product room limit is 1,000 signed-in attendees. It is a stage/listener
room: the mobile UI subscribes to at most 12 visible cameras with 360p/20fps
camera capture. A room of 1,000 simultaneous camera publishers is a different
capacity target and must not be promised from one VM.

Start with at least 8 vCPU, 16 GiB RAM and a 1 Gbps public NIC, then load-test
with representative networks. For multiple heavy rooms or more than a small
speaker stage, move to a multi-node LiveKit/Redis topology before raising the
publisher limit.

## Preflight commands

On the media VM, after the official generator has produced `/opt/livekit`:

```bash
LIVEKIT_MEDIA_IP=<public-ip> bash scripts/livekit_preflight.sh media
```

On the API host, after its `.env` is updated:

```bash
bash scripts/livekit_preflight.sh backend
```

Only after both pass should the operator start `livekit-docker`, restart the
Diamond backend, then test Android and iOS on Wi-Fi and cellular networks.

## Required inbound ports on the media VM

| Port | Protocol | Purpose |
| --- | --- | --- |
| 80 | TCP | TLS certificate issuance |
| 443 | TCP and UDP | HTTPS/WebSocket and TURN/TLS fallback |
| 3478 | UDP | TURN/STUN |
| 7881 | TCP | ICE/TCP fallback |
| 50000-60000 | UDP | WebRTC media |

Do not expose LiveKit's port 7880 publicly; Caddy terminates the public HTTPS
and WebSocket traffic. Do not enable recording, ingress, SIP or egress unless a
separate feature specifically needs them.
