"use client";

import { useEffect, useState, type RefObject } from "react";

/**
 * Plays an adaptive HLS stream in a <video> when one is available.
 *
 * Safari/iOS play HLS natively; other browsers use hls.js, loaded lazily so
 * pages without video do not download it. If there is no HLS URL, the
 * browser cannot play it, or the stream fails fatally, the returned `src` is
 * the progressive MP4 URL instead.
 *
 * Use the returned `src` as the <video> `src` attribute: it is the HLS URL
 * for native playback, the MP4 URL as fallback, or undefined while hls.js
 * drives the element through Media Source Extensions.
 */
export function useHlsSource(
  videoRef: RefObject<HTMLVideoElement | null>,
  hlsUrl: string | null | undefined,
  mp4Url: string | null | undefined,
): { src: string | undefined; usingHls: boolean } {
  const [failedHlsUrl, setFailedHlsUrl] = useState("");
  const [mseActive, setMseActive] = useState(false);
  const [nativeHls, setNativeHls] = useState(false);
  const hls = String(hlsUrl || "").trim();
  const mp4 = String(mp4Url || "").trim();
  const wantHls = Boolean(hls) && failedHlsUrl !== hls;

  useEffect(() => {
    const element = videoRef.current;
    setMseActive(false);
    setNativeHls(false);
    if (!element || !wantHls) return;
    if (element.canPlayType("application/vnd.apple.mpegurl")) {
      setNativeHls(true);
      return;
    }
    let destroyed = false;
    let instance: { destroy: () => void } | null = null;
    import("hls.js")
      .then(({ default: Hls }) => {
        if (destroyed) return;
        if (!Hls.isSupported()) {
          setFailedHlsUrl(hls);
          return;
        }
        const player = new Hls({ maxBufferLength: 30, backBufferLength: 30, startLevel: -1 });
        instance = player;
        player.on(Hls.Events.ERROR, (_event, data) => {
          if (data?.fatal) {
            player.destroy();
            instance = null;
            setMseActive(false);
            setFailedHlsUrl(hls);
          }
        });
        player.loadSource(hls);
        player.attachMedia(element);
        setMseActive(true);
      })
      .catch(() => {
        if (!destroyed) setFailedHlsUrl(hls);
      });
    return () => {
      destroyed = true;
      instance?.destroy();
      instance = null;
    };
  }, [videoRef, hls, wantHls]);

  // While HLS is wanted the MP4 is never set: hls.js owns the element's
  // source, and React removing a `src` attribute later would detach it.
  if (wantHls) return { src: nativeHls ? hls : undefined, usingHls: mseActive || nativeHls };
  return { src: mp4 || undefined, usingHls: false };
}
