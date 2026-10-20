"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import Script from "next/script";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
const DEVICE_ID_KEY = "diamond_device_id";
const TELEGRAM_BOT_SYNC_PREF_PREFIX = "diamond_tg_bot_sync_pref_";
const TELEGRAM_MANUAL_LOGOUT_PREFIX = "diamond_tg_manual_logout_";
const LOGIN_REQUEST_TIMEOUT_MS = 30000;
const TELEGRAM_AUTO_LOGIN_TIMEOUT_MS = 15000;
const SPEAKING_GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_SPEAKING_GOOGLE_CLIENT_ID
  || "956229422440-mrk4gdhhapnp594gmnlnij2d8m39p9us.apps.googleusercontent.com";

type GoogleCredentialResponse = { credential?: string };
type GoogleSession = { session_id?: string; device_model?: string; last_seen_at?: string; created_at?: string };

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (options: { client_id: string; callback: (response: GoogleCredentialResponse) => void }) => void;
          renderButton: (element: HTMLElement, options: Record<string, unknown>) => void;
        };
      };
    };
  }
}

type TelegramWebApp = {
  initData?: string;
  initDataUnsafe?: {
    user?: {
      id?: number;
    };
  };
  ready?: () => void;
  expand?: () => void;
};

function getOrCreateDeviceId() {
  if (typeof window === "undefined") return "";
  const existing = localStorage.getItem(DEVICE_ID_KEY);
  if (existing) return existing;
  const next = `dev_${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
  localStorage.setItem(DEVICE_ID_KEY, next);
  return next;
}

function getTelegramMiniAppAuthPayload() {
  if (typeof window === "undefined") return null;
  const webApp = (window as Window & { Telegram?: { WebApp?: TelegramWebApp } }).Telegram?.WebApp;
  if (!webApp) return null;
  try {
    webApp.ready?.();
  } catch {
    // noop
  }
  const telegramId = Number(webApp.initDataUnsafe?.user?.id || 0);
  const initData = String(webApp.initData || "").trim();
  if (telegramId > 0 && initData) {
    return { telegram_id: telegramId, init_data: initData };
  }
  return null;
}

function resolveTelegramBotSyncPreference(telegramId: number) {
  if (typeof window === "undefined" || !telegramId) return true;
  const key = `${TELEGRAM_BOT_SYNC_PREF_PREFIX}${telegramId}`;
  const stored = localStorage.getItem(key);
  if (stored === "0") return false;
  localStorage.setItem(key, "1");
  return true;
}

function getTelegramMiniAppSyncPayload() {
  const payload = getTelegramMiniAppAuthPayload();
  if (!payload) return {};
  return {
    ...payload,
    sync_bot_session: resolveTelegramBotSyncPreference(Number(payload.telegram_id || 0)),
  };
}

function isTelegramAutoLoginSuppressed(telegramId: number) {
  if (typeof window === "undefined" || !telegramId) return false;
  try {
    return sessionStorage.getItem(`${TELEGRAM_MANUAL_LOGOUT_PREFIX}${telegramId}`) === "1";
  } catch {
    return false;
  }
}

function clearTelegramAutoLoginSuppression(telegramId: number) {
  if (typeof window === "undefined" || !telegramId) return;
  try {
    sessionStorage.removeItem(`${TELEGRAM_MANUAL_LOGOUT_PREFIX}${telegramId}`);
  } catch {
    // no-op
  }
}

export default function LoginPage() {
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [qrBusy, setQrBusy] = useState(false);
  const [qrError, setQrError] = useState("");
  const [scannerActive, setScannerActive] = useState(false);
  const [scannerSupported, setScannerSupported] = useState(false);
  const [scannerMessage, setScannerMessage] = useState("");
  const [scannerPermissionError, setScannerPermissionError] = useState("");
  const [cameraReady, setCameraReady] = useState(false);
  const [showQrPanel, setShowQrPanel] = useState(false);
  const [telegramAutoChecking, setTelegramAutoChecking] = useState(false);
  const [googleScriptReady, setGoogleScriptReady] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [googleProfileRequired, setGoogleProfileRequired] = useState(false);
  const [googleProfileError, setGoogleProfileError] = useState("");
  const [pendingGoogleToken, setPendingGoogleToken] = useState("");
  const [googleProfile, setGoogleProfile] = useState({ firstName: "", lastName: "", phone: "", age: "", gender: "prefer_not_to_say" });
  const [googleSessions, setGoogleSessions] = useState<GoogleSession[]>([]);
  const [selectedGoogleSessions, setSelectedGoogleSessions] = useState<string[]>([]);
  const googleButtonRef = useRef<HTMLDivElement | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const lastScannedValueRef = useRef("");
  const scanSubmittingRef = useRef(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setScannerSupported(typeof window !== "undefined" && "BarcodeDetector" in window);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    const reason = new URLSearchParams(window.location.search).get("reason");
    if (reason === "account_blocked") {
      const locale = String(localStorage.getItem("diamond_locale") || "uz").toLowerCase();
      setError(locale.startsWith("ru") ? "Ваш аккаунт заблокирован. Обратитесь к администратору." : locale.startsWith("en") ? "Your account is blocked. Please contact the administrator." : "Akkauntingiz bloklangan. Administratorga murojaat qiling.");
    } else if (reason === "session_expired") {
      const locale = String(localStorage.getItem("diamond_locale") || "uz").toLowerCase();
      setError(locale.startsWith("ru") ? "Сессия завершена или аккаунт удалён. Войдите снова." : locale.startsWith("en") ? "Your session ended or the account was removed. Please log in again." : "Sessiya tugadi yoki akkaunt o‘chirilgan. Qayta kiring.");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function checkToken() {
      const token = localStorage.getItem("diamond_token");
      if (!token) return;
      const telegramAuthPayload = getTelegramMiniAppAuthPayload();
      try {
        const response = await fetch(`${API_BASE}/auth/me`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (!response.ok) {
          if (response.status === 401 || response.status === 404) {
            localStorage.removeItem("diamond_token");
            const locale = String(localStorage.getItem("diamond_locale") || "uz").toLowerCase();
            setError(locale.startsWith("ru") ? "Сессия завершена или аккаунт удалён. Войдите снова." : locale.startsWith("en") ? "Your session ended or the account was removed. Please log in again." : "Sessiya tugadi yoki akkaunt o‘chirilgan. Qayta kiring.");
          } else if (response.status === 403) {
            const body = await response.json().catch(() => ({}));
            if (String(body?.detail || "").toLowerCase().includes("account is blocked")) {
              localStorage.removeItem("diamond_token");
              const locale = String(localStorage.getItem("diamond_locale") || "uz").toLowerCase();
              setError(locale.startsWith("ru") ? "Ваш аккаунт заблокирован. Обратитесь к администратору." : locale.startsWith("en") ? "Your account is blocked. Please contact the administrator." : "Akkauntingiz bloklangan. Administratorga murojaat qiling.");
            }
          }
          return;
        }
        const me = await response.json().catch(() => ({} as Record<string, unknown>));
        if (telegramAuthPayload) {
          const meTelegramId = Number((me as any)?.telegram_id || 0);
          if (!meTelegramId || meTelegramId !== Number(telegramAuthPayload.telegram_id || 0)) {
            localStorage.removeItem("diamond_token");
            return;
          }
        }
        if (!cancelled) window.location.replace("/");
      } catch {
        // ignore and keep login form
      }
    }
    checkToken();
    return () => {
      cancelled = true;
    };
  }, []);

  const completeLogin = useCallback((token: string) => {
    const telegramAuthPayload = getTelegramMiniAppAuthPayload();
    if (telegramAuthPayload) clearTelegramAutoLoginSuppression(Number(telegramAuthPayload.telegram_id || 0));
    localStorage.setItem("diamond_token", token);
    window.location.replace("/");
  }, []);

  const exchangeGoogleToken = useCallback(async (
    idToken: string,
    profile?: { first_name: string; last_name: string; phone: string; age: number; gender: string },
    revokeSessionIds: string[] = [],
  ) => {
    setGoogleBusy(true);
    setGoogleProfileError("");
    setError("");
    try {
      const response = await fetch(`${API_BASE}/auth/speaking-google`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id_token: idToken,
          device_id: getOrCreateDeviceId(),
          device_model: typeof navigator === "undefined" ? "Web browser" : navigator.userAgent.slice(0, 120),
          revoke_session_ids: revokeSessionIds,
          ...(profile || {}),
        }),
      });
      const body = await response.json().catch(() => ({}));
      const detail = body?.detail;
      if (response.status === 428 && detail?.code === "profile_required") {
        setPendingGoogleToken(idToken);
        setGoogleProfileRequired(true);
        setGoogleSessions([]);
        return;
      }
      if (response.status === 409 && detail?.code === "session_limit") {
        const sessions = Array.isArray(detail.sessions) ? detail.sessions as GoogleSession[] : [];
        setGoogleSessions(sessions);
        setSelectedGoogleSessions([]);
        setPendingGoogleToken(idToken);
        setGoogleProfileRequired(false);
        setGoogleProfileError(String(detail.message || "Avvalgi qurilmalardan sessiyani tanlab yakunlang."));
        return;
      }
      if (!response.ok) {
        const message = typeof detail === "string" ? detail : "Google orqali kirib bo‘lmadi. Qayta urinib ko‘ring.";
        throw new Error(message);
      }
      const token = String(body?.access_token || "");
      if (!token) throw new Error("Serverdan sessiya tokeni olinmadi. Qayta urinib ko‘ring.");
      completeLogin(token);
    } catch (err) {
      setGoogleProfileError(err instanceof Error ? err.message : "Google orqali kirishda xatolik yuz berdi.");
      setError(err instanceof Error ? err.message : "Google orqali kirishda xatolik yuz berdi.");
    } finally {
      setGoogleBusy(false);
    }
  }, [completeLogin]);

  useEffect(() => {
    const element = googleButtonRef.current;
    const google = window.google;
    if (!googleScriptReady || !element || !google) return;
    google.accounts.id.initialize({
      client_id: SPEAKING_GOOGLE_CLIENT_ID,
      callback: (response) => {
        const credential = String(response?.credential || "").trim();
        if (!credential) {
          setError("Google hisobidan tasdiqlash tokeni olinmadi. Qayta urinib ko‘ring.");
          return;
        }
        void exchangeGoogleToken(credential);
      },
    });
    element.replaceChildren();
    google.accounts.id.renderButton(element, {
      type: "standard", theme: "outline", size: "large", shape: "pill",
      text: "continue_with", logo_alignment: "left", width: Math.min(element.clientWidth || 340, 360),
    });
  }, [googleScriptReady, exchangeGoogleToken]);

  async function submitGoogleProfile(event: FormEvent) {
    event.preventDefault();
    if (!pendingGoogleToken || googleBusy) return;
    const age = Number(googleProfile.age);
    if (!googleProfile.firstName.trim() || !googleProfile.lastName.trim() || !googleProfile.phone.trim() || !Number.isInteger(age) || age < 5 || age > 120) {
      setGoogleProfileError("Ism, familiya, telefon va 5–120 oralig‘idagi yoshni to‘ldiring.");
      return;
    }
    await exchangeGoogleToken(pendingGoogleToken, {
      first_name: googleProfile.firstName.trim(),
      last_name: googleProfile.lastName.trim(),
      phone: googleProfile.phone.trim(),
      age,
      gender: googleProfile.gender,
    }, selectedGoogleSessions);
  }

  useEffect(() => {
    let cancelled = false;
    async function tryTelegramAutoLogin() {
      const telegramAuthPayload = getTelegramMiniAppAuthPayload();
      if (!telegramAuthPayload) return;
      if (isTelegramAutoLoginSuppressed(Number(telegramAuthPayload.telegram_id || 0))) return;
      setTelegramAutoChecking(true);
      try {
        const deviceId = getOrCreateDeviceId();
        const controller = new AbortController();
        const timeout = window.setTimeout(() => controller.abort(), TELEGRAM_AUTO_LOGIN_TIMEOUT_MS);
        const syncBotSession = resolveTelegramBotSyncPreference(Number(telegramAuthPayload.telegram_id || 0));
        let response: Response;
        try {
          response = await fetch(`${API_BASE}/auth/telegram`, {
            method: "POST",
            signal: controller.signal,
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              ...telegramAuthPayload,
              device_id: deviceId || null,
              sync_bot_session: syncBotSession,
            }),
          });
        } finally {
          window.clearTimeout(timeout);
        }
        const body = await response.json().catch(() => ({}));
        if (!response.ok) {
          if (response.status === 403 && String(body?.detail || "").toLowerCase().includes("account is blocked")) {
            const locale = String(localStorage.getItem("diamond_locale") || "uz").toLowerCase();
            setError(locale.startsWith("ru") ? "Ваш аккаунт заблокирован. Обратитесь к администратору." : locale.startsWith("en") ? "Your account is blocked. Please contact the administrator." : "Akkauntingiz bloklangan. Administratorga murojaat qiling.");
          }
          return;
        }
        const token = String(body.access_token || "");
        if (!token) return;
        if (!cancelled) completeLogin(token);
      } catch {
        // silent fallback to manual login
      } finally {
        if (!cancelled) setTelegramAutoChecking(false);
      }
    }
    tryTelegramAutoLogin().catch(() => null);
    return () => {
      cancelled = true;
    };
  }, [completeLogin]);

  const consumeQrLogin = useCallback(async (rawQrToken: string) => {
    const raw = String(rawQrToken || "").trim();
    if (!raw) {
      setQrError("QR code aniqlanmadi");
      return;
    }
    if (scanSubmittingRef.current) return;
    scanSubmittingRef.current = true;
    setQrBusy(true);
    setQrError("");
    setError("");
    try {
      const deviceId = getOrCreateDeviceId();
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), LOGIN_REQUEST_TIMEOUT_MS);
      let response: Response;
      try {
        response = await fetch(`${API_BASE}/auth/qr/consume`, {
          method: "POST",
          signal: controller.signal,
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            qr_token: raw,
            device_id: deviceId || null,
            ...getTelegramMiniAppSyncPayload(),
          }),
        });
      } finally {
        window.clearTimeout(timeout);
      }
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = String(body.detail || "").toLowerCase();
        if (detail.includes("expired")) throw new Error("QR code muddati tugagan");
        if (detail.includes("invalid")) throw new Error("QR code aniqlanmadi");
        throw new Error("Qayta urinib ko'ring");
      }
      const token = String(body.access_token || "");
      if (!token) throw new Error("Token qaytmadi");
      completeLogin(token);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setQrError("Qayta urinib ko'ring");
      } else if (err instanceof TypeError) {
        setQrError("Ulanishda xatolik. Qayta urinib ko'ring.");
      } else {
        setQrError(err instanceof Error ? err.message : "Qayta urinib ko'ring");
      }
    } finally {
      setQrBusy(false);
      scanSubmittingRef.current = false;
    }
  }, [completeLogin]);

  useEffect(() => {
    let mounted = true;
    let rafId = 0;
    let stream: MediaStream | null = null;
    const DetectorCtor = typeof window !== "undefined" ? (window as any).BarcodeDetector : null;
    const detector = DetectorCtor ? new DetectorCtor({ formats: ["qr_code"] }) : null;

    async function stopScanner() {
      if (rafId) {
        window.cancelAnimationFrame(rafId);
        rafId = 0;
      }
      if (videoRef.current) {
        videoRef.current.pause();
        videoRef.current.srcObject = null;
      }
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
        stream = null;
      }
      if (mounted) {
        setCameraReady(false);
      }
    }

    async function startScanner() {
      const videoEl = videoRef.current;
      const canvasEl = canvasRef.current;
      if (!scannerActive || !videoEl || !canvasEl || !detector) {
        await stopScanner();
        return;
      }
      try {
        setScannerPermissionError("");
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: "environment" },
          },
          audio: false,
        });
        if (!mounted) return;
        videoEl.srcObject = stream;
        await videoEl.play();
        setCameraReady(true);
      } catch (err) {
        if (!mounted) return;
        setScannerPermissionError("Kamera ruxsati kerak");
        setScannerActive(false);
        await stopScanner();
        return;
      }

      const ctx = canvasEl.getContext("2d");
      if (!ctx) return;

      const loop = async () => {
        if (!mounted || !scannerActive || !videoEl || !canvasEl) return;
        const width = videoEl.videoWidth || 0;
        const height = videoEl.videoHeight || 0;
        if (width > 0 && height > 0) {
          canvasEl.width = width;
          canvasEl.height = height;
          ctx.drawImage(videoEl, 0, 0, width, height);
          try {
            const detected = await detector.detect(canvasEl);
            const firstValue = String(detected?.[0]?.rawValue || "").trim();
            if (firstValue && firstValue !== lastScannedValueRef.current) {
              lastScannedValueRef.current = firstValue;
              setScannerMessage("QR code aniqlanmoqda...");
              consumeQrLogin(firstValue).catch(() => null);
              setScannerActive(false);
              await stopScanner();
              return;
            }
          } catch {
            // Ignore intermittent decode errors while scanning frames.
          }
        }
        rafId = window.requestAnimationFrame(loop);
      };
      rafId = window.requestAnimationFrame(loop);
    }

    startScanner().catch(() => null);
    return () => {
      mounted = false;
      stopScanner().catch(() => null);
    };
  }, [scannerActive, consumeQrLogin]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const deviceId = getOrCreateDeviceId();
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), LOGIN_REQUEST_TIMEOUT_MS);
      let response: Response;
      try {
        response = await fetch(`${API_BASE}/auth/login`, {
          method: "POST",
          signal: controller.signal,
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            login_id: loginId,
            password,
            device_id: deviceId || null,
            ...getTelegramMiniAppSyncPayload(),
          }),
        });
      } finally {
        window.clearTimeout(timeout);
      }
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = String(body.detail || "Kirish amalga oshmadi");
        if (response.status === 403 && detail.toLowerCase().includes("account is blocked")) {
          const locale = String(localStorage.getItem("diamond_locale") || "uz").toLowerCase();
          throw new Error(locale.startsWith("ru") ? "Ваш аккаунт заблокирован. Обратитесь к администратору." : locale.startsWith("en") ? "Your account is blocked. Please contact the administrator." : "Akkauntingiz bloklangan. Administratorga murojaat qiling.");
        }
        throw new Error(detail);
      }
      const token = String(body.access_token || "");
      if (!token) throw new Error("Token qaytmadi");
      completeLogin(token);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setError("So'rov vaqti tugadi. Iltimos, qayta urinib ko'ring.");
      } else if (err instanceof TypeError) {
        setError("Tarmoq xatosi. Internet aloqasini tekshiring.");
      } else {
        setError(err instanceof Error ? err.message : "Kirish amalga oshmadi");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-brand-shell flex items-center justify-center min-h-[100svh] px-4 py-12 bg-navy-900 relative overflow-hidden">
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onReady={() => setGoogleScriptReady(true)}
        onError={() => setError("Google kirish xizmati yuklanmadi. Tarmoqni tekshirib qayta urinib ko‘ring.")}
      />
      {/* Dynamic Backgrounds matching Hero */}
      <div className="absolute inset-0 pointer-events-none opacity-20 bg-[url('data:image/svg+xml,%3Csvg viewBox=\'0 0 200 200\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noiseFilter\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.65\' numOctaves=\'3\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noiseFilter)\'/%3E%3C/svg%3E')]" />
      <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] rounded-full bg-cyan-600/30 blur-[140px] pointer-events-none animate-pulse" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-sky-500/20 blur-[120px] pointer-events-none" />

      <section className="relative w-full max-w-[420px] p-8 md:p-10 bg-white/10 backdrop-blur-2xl border border-white/20 rounded-[2.5rem] shadow-[0_0_60px_rgba(34,211,238,0.15)] flex flex-col items-center animate-fade-in z-10 transition-transform duration-500 hover:scale-[1.01]">
        <h1 className="mb-8 text-3xl font-black text-white font-display tracking-tight text-center drop-shadow-lg">Tizimga kirish</h1>
        
        <form className="flex flex-col w-full gap-5" onSubmit={submit}>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-bold text-cyan-100 ml-1">Login ID</label>
            <input 
              className="w-full px-5 py-4 text-white bg-navy-950/50 border border-white/20 rounded-2xl outline-none focus:border-cyan-400 focus:bg-navy-900/80 focus:ring-2 focus:ring-cyan-400/50 transition-all placeholder:text-white/40 font-medium shadow-inner"
              value={loginId} 
              onChange={(event) => setLoginId(event.target.value)} 
              autoComplete="username" 
              placeholder="Masalan: D12345"
              required 
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-bold text-cyan-100 ml-1">Parol</label>
            <input 
              className="w-full px-5 py-4 text-white bg-navy-950/50 border border-white/20 rounded-2xl outline-none focus:border-cyan-400 focus:bg-navy-900/80 focus:ring-2 focus:ring-cyan-400/50 transition-all placeholder:text-white/40 font-medium shadow-inner"
              value={password} 
              onChange={(event) => setPassword(event.target.value)} 
              type="password" 
              autoComplete="current-password" 
              placeholder="••••••••"
              required 
            />
          </div>
          
          {error && (
            <div className="px-4 py-3 text-sm font-semibold text-red-200 border border-red-500/30 bg-red-500/20 rounded-xl flex items-center gap-2 animate-shake">
              <span>⚠️</span> {error}
            </div>
          )}
          
          <button 
            className="w-full px-6 py-4 mt-4 text-lg font-bold text-navy-900 bg-cyan-400 rounded-2xl hover:bg-cyan-300 hover:-translate-y-1 transition-all shadow-[0_0_20px_rgba(34,211,238,0.4)] disabled:opacity-70 disabled:hover:translate-y-0 disabled:cursor-not-allowed" 
            type="submit" 
            disabled={loading}
          >
            {loading ? "Tekshirilmoqda..." : "Kirish"}
          </button>
        </form>

        <div className="flex items-center w-full gap-4 my-8 opacity-60">
          <div className="flex-1 h-px bg-cyan-200/20" />
          <span className="text-xs font-bold text-cyan-100 uppercase tracking-widest">yoki</span>
          <div className="flex-1 h-px bg-cyan-200/20" />
        </div>

        <div className="w-full flex flex-col items-center gap-2">
          <div ref={googleButtonRef} className="min-h-[44px] w-full flex justify-center" />
          {googleBusy ? <p role="status" className="text-xs font-semibold text-cyan-100">Google hisobi tekshirilmoqda...</p> : null}
          <p className="text-[11px] text-cyan-100/70 text-center">Google orqali faqat Diamond Speaking hisobiga kirasiz.</p>
        </div>

        {telegramAutoChecking && (
          <div className="w-full px-4 py-3 mb-4 text-sm font-semibold text-cyan-100 border border-cyan-400/40 bg-cyan-500/20 rounded-xl text-center">
            Telegram orqali avtomatik kirish tekshirilmoqda...
          </div>
        )}

        <section className="flex flex-col w-full gap-4 p-5 bg-navy-950/40 border border-white/10 rounded-3xl shadow-inner">
          <button
            className="w-full px-4 py-3 text-sm font-bold text-cyan-100 border border-cyan-400/30 bg-white/5 rounded-xl hover:bg-white/10 hover:border-cyan-400/50 transition-all shadow-sm"
            type="button"
            onClick={() => {
              if (!scannerSupported) {
                setQrError("Kamera ruxsati kerak");
                return;
              }
              setShowQrPanel(true);
              setScannerPermissionError("");
              setScannerMessage("");
              setQrError("");
              lastScannedValueRef.current = "";
              setScannerActive(true);
            }}
          >
            QR code orqali kirish
          </button>
          {!scannerSupported ? (
            <div className="px-4 py-3 text-xs font-semibold text-orange-200 bg-orange-500/20 border border-orange-500/30 rounded-xl">
              QR scanner bu brauzerda qo&apos;llab-quvvatlanmaydi.
            </div>
          ) : null}
        </section>
      </section>

      {showQrPanel ? (
        <section className="fixed inset-0 z-[200] bg-black">
          <div className="absolute inset-0">
            <video ref={videoRef} className="w-full h-full object-cover" playsInline muted autoPlay />
            <canvas ref={canvasRef} style={{ display: "none" }} />
          </div>
          <div className="absolute inset-x-0 top-0 px-4 py-4 flex items-center justify-between bg-gradient-to-b from-black/75 to-transparent">
            <span className="text-white text-sm font-semibold">{cameraReady ? "QR tekshirilmoqda..." : "Kamera tayyorlanmoqda..."}</span>
            <button
              type="button"
              className="px-3 py-2 rounded-lg bg-white/20 text-white text-sm font-semibold"
              onClick={() => {
                setScannerActive(false);
                setShowQrPanel(false);
              }}
            >
              Yopish
            </button>
          </div>
          <div className="absolute inset-x-0 bottom-0 px-4 pb-6 pt-4 bg-gradient-to-t from-black/80 to-transparent space-y-2">
            {scannerPermissionError ? <div className="px-3 py-2 rounded-lg bg-red-500/30 text-red-100 text-sm font-semibold">{scannerPermissionError}</div> : null}
            {qrError ? <div className="px-3 py-2 rounded-lg bg-red-500/30 text-red-100 text-sm font-semibold">{qrError}</div> : null}
            {scannerMessage ? <div className="px-3 py-2 rounded-lg bg-cyan-500/30 text-cyan-100 text-sm font-semibold">{scannerMessage}</div> : null}
            {qrBusy ? <div className="px-3 py-2 rounded-lg bg-cyan-500/30 text-cyan-100 text-sm font-semibold">QR tekshirilmoqda...</div> : null}
          </div>
        </section>
      ) : null}

      {googleProfileRequired || googleSessions.length > 0 ? (
        <div className="fixed inset-0 z-[220] flex items-center justify-center bg-slate-950/70 px-4 py-6 backdrop-blur-sm">
          <section className="w-full max-w-md max-h-[90svh] overflow-y-auto rounded-3xl border border-white/20 bg-white p-6 text-slate-900 shadow-2xl">
            {googleProfileRequired ? (
              <form className="space-y-4" onSubmit={submitGoogleProfile}>
                <div>
                  <h2 className="text-xl font-extrabold">Speaking profilingizni to‘ldiring</h2>
                  <p className="mt-1 text-sm text-slate-600">Yangi Google hisob uchun ro‘yxatdan o‘tishni yakunlang.</p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <label className="text-sm font-semibold">Ism<input required maxLength={80} autoComplete="given-name" className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-3" value={googleProfile.firstName} onChange={(event) => setGoogleProfile((v) => ({ ...v, firstName: event.target.value }))} /></label>
                  <label className="text-sm font-semibold">Familiya<input required maxLength={80} autoComplete="family-name" className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-3" value={googleProfile.lastName} onChange={(event) => setGoogleProfile((v) => ({ ...v, lastName: event.target.value }))} /></label>
                </div>
                <label className="block text-sm font-semibold">Telefon<input required type="tel" autoComplete="tel" maxLength={32} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-3" value={googleProfile.phone} onChange={(event) => setGoogleProfile((v) => ({ ...v, phone: event.target.value }))} /></label>
                <div className="grid grid-cols-2 gap-3">
                  <label className="text-sm font-semibold">Yosh<input required type="number" min={5} max={120} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-3" value={googleProfile.age} onChange={(event) => setGoogleProfile((v) => ({ ...v, age: event.target.value }))} /></label>
                  <label className="text-sm font-semibold">Jins<select className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-3" value={googleProfile.gender} onChange={(event) => setGoogleProfile((v) => ({ ...v, gender: event.target.value }))}><option value="prefer_not_to_say">Ko‘rsatmaslik</option><option value="female">Ayol</option><option value="male">Erkak</option></select></label>
                </div>
                {googleProfileError ? <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm font-medium text-red-700">{googleProfileError}</p> : null}
                <div className="flex justify-end gap-2 pt-1">
                  <button type="button" className="rounded-xl border border-slate-200 px-4 py-2.5 font-semibold" onClick={() => { setGoogleProfileRequired(false); setPendingGoogleToken(""); setGoogleProfileError(""); }}>Bekor qilish</button>
                  <button type="submit" disabled={googleBusy} className="rounded-xl bg-blue-700 px-5 py-2.5 font-bold text-white disabled:opacity-60">{googleBusy ? "Tekshirilmoqda..." : "Davom etish"}</button>
                </div>
              </form>
            ) : (
              <div className="space-y-4">
                <div>
                  <h2 className="text-xl font-extrabold">Faol qurilmalar limiti</h2>
                  <p className="mt-1 text-sm text-slate-600">Davom etish uchun hisobingizdan chiqariladigan eski qurilmani tanlang.</p>
                </div>
                <div className="space-y-2">
                  {googleSessions.map((session) => {
                    const id = String(session.session_id || "");
                    if (!id) return null;
                    const checked = selectedGoogleSessions.includes(id);
                    return <label key={id} className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 p-3"><input type="checkbox" checked={checked} onChange={(event) => setSelectedGoogleSessions((current) => event.target.checked ? [...current, id] : current.filter((value) => value !== id))} /><span><span className="block font-semibold">{session.device_model || "Noma’lum qurilma"}</span><span className="text-xs text-slate-500">{session.last_seen_at || session.created_at || "Faol sessiya"}</span></span></label>;
                  })}
                </div>
                {googleProfileError ? <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm font-medium text-red-700">{googleProfileError}</p> : null}
                <div className="flex justify-end gap-2">
                  <button type="button" className="rounded-xl border border-slate-200 px-4 py-2.5 font-semibold" onClick={() => { setGoogleSessions([]); setPendingGoogleToken(""); setGoogleProfileError(""); }}>Bekor qilish</button>
                  <button type="button" disabled={googleBusy || !selectedGoogleSessions.length} className="rounded-xl bg-blue-700 px-5 py-2.5 font-bold text-white disabled:opacity-50" onClick={() => pendingGoogleToken && void exchangeGoogleToken(pendingGoogleToken, undefined, selectedGoogleSessions)}>{googleBusy ? "Tekshirilmoqda..." : "Tanlanganlarni chiqarish va kirish"}</button>
                </div>
              </div>
            )}
          </section>
        </div>
      ) : null}
    </main>
  );
}
