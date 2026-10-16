# Diamond Speaking: self-hosted live video

The existing VoiceRoom is an audio peer-to-peer mesh.  It remains unchanged.
`Live video` is a separate LiveKit SFU room type, which lets a room accept up
to 1,000 authenticated users without asking every device to upload a stream to
every other device.

## Before enabling it

1. Provision a **dedicated public media VM/IP** for LiveKit. Do not put it on
   the current web VM: the website Caddy already owns TCP 443, while reliable
   TURN/TLS must own TCP 443 for restrictive networks.
2. Add DNS `A` records: `live.diamond-education.uz` and
   `turn.live.diamond-education.uz` → the dedicated media VM public IP.
3. Generate the official LiveKit Docker Compose/Caddy/Redis package on that
   VM. It owns its own ports and does not replace the website Caddy or coturn.
4. Open media-VM firewall/provider ports: `80/tcp`, `443/tcp+udp`,
   `3478/udp`, `7881/tcp`, and `50000-60000/udp`.
5. Create a high-entropy LiveKit API key and secret, then set these server-only
   variables in the backend service environment:

   ```ini
   LIVEKIT_URL=wss://live.diamond-education.uz
LIVEKIT_INTERNAL_URL=https://live.diamond-education.uz
   LIVEKIT_API_KEY=...
   LIVEKIT_API_SECRET=...
   ```

No value above belongs in the mobile app, git, or a browser response.  The
backend issues each signed join token for only ten minutes.

## Capacity and privacy

- The application and LiveKit RoomService enforce at most 1,000 active
  signed-in participants per room.
- The Flutter client enables LiveKit `adaptiveStream` and `dynacast`; it draws
  a stage of at most 12 camera tiles instead of subscribing to 1,000
  full-resolution streams.
- Camera publishing is off by default. A participant chooses to turn it on.
- No video recording, egress, or permanent media storage is configured.
- Start with 360p camera publishing and monitor CPU, packet loss and egress.
  A 1,000-person room must be operated as a stage/listener room: only a small
  active-speaker set should publish video at the same time. A single 11 GiB VM
  is not a safe capacity guarantee for 1,000 simultaneous camera publishers;
  load-test and scale the SFU before enabling that mode.

## Generated LiveKit configuration

Use the official generator rather than manually mixing the website Caddy with
the LiveKit media edge. It produces a matched Caddy, Docker Compose, Redis,
LiveKit configuration and systemd service. The pinned media-server image should
be `livekit/livekit-server:v1.13.10` or a later reviewed patch release.

The deployment contract is documented in
[`ops/livekit/README.md`](../../ops/livekit/README.md), and the read-only
preflight script refuses to start or alter any service.

Validate from an authenticated test account: create a room, join from Android
and iOS, enable microphone, then enable camera.  Verify camera permission,
leave/end behavior, 1,000-seat refusal, and that a normal VoiceRoom still
works. Test from a mobile network and a second Wi-Fi network before announcing
the feature.
