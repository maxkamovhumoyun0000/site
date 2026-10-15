# Diamond Speaking: self-hosted live video

The existing VoiceRoom is an audio peer-to-peer mesh.  It remains unchanged.
`Live video` is a separate LiveKit SFU room type, which lets a room accept up
to 1,000 authenticated users without asking every device to upload a stream to
every other device.

## Before enabling it

1. Add DNS `A` records: `live.diamond-education.uz` and
   `turn.live.diamond-education.uz` → the current Diamond server public IP.
2. Install the LiveKit media service on the same server.  Do **not** replace
   the existing Caddy or coturn service: Caddy continues to own HTTPS for the
   website and coturn continues to own `3478`.
3. Proxy `https://live.diamond-education.uz` to LiveKit's local `7880` port
   in the existing Caddy configuration.
4. Open only these additional firewall/provider ports:
   - `7881/tcp` for TCP WebRTC fallback;
   - `50000-51000/udp` for WebRTC media.
   - `5349/tcp` and `5349/udp` for TURN/TLS on restrictive networks.
5. Create a high-entropy LiveKit API key and secret, then set these server-only
   variables in the backend service environment:

   ```ini
   LIVEKIT_URL=wss://live.diamond-education.uz
   LIVEKIT_INTERNAL_URL=http://127.0.0.1:7880
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

## Caddy fragment

Add this **as an additional site block** to the existing Caddy configuration;
do not overwrite the Diamond Education site block:

```caddy
live.diamond-education.uz {
    reverse_proxy 127.0.0.1:7880
}
```

## LiveKit server configuration

Use a fixed, reviewed image/version and create a configuration equivalent to:

```yaml
port: 7880
log_level: info
rtc:
  tcp_port: 7881
  port_range_start: 50000
  port_range_end: 51000
  use_external_ip: true
turn:
  enabled: true
  domain: turn.live.diamond-education.uz
  tls_port: 5349
keys:
  <LIVEKIT_API_KEY>: <LIVEKIT_API_SECRET>
```

Validate from an authenticated test account: create a room, join from Android
and iOS, enable microphone, then enable camera.  Verify camera permission,
leave/end behavior, 1,000-seat refusal, and that a normal VoiceRoom still
works. Test from a mobile network and a second Wi-Fi network before announcing
the feature.
