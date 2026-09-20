"use client";

import { useEffect, useState, useCallback } from "react";
import { createPortal } from "react-dom";

export interface UnseenBadge {
  code: string;
  title: string;
  description: string;
  asset_url: string;
  earned_at?: string;
}

interface BadgeAwardModalProps {
  onNavigateToProfile?: () => void;
}

const I18N = {
  uz: {
    kicker: "🎉 YANGI YUTUQ!",
    title: "Tabriklaymiz! Siz yangi badge oldingiz!",
    subtitle: "Bilim va faolligingiz evaziga profilingizga yangi nishon qo‘shildi.",
    viewProfile: "Profilimga o‘tish",
    later: "Keyinroq",
    of: "dan",
  },
  ru: {
    kicker: "🎉 НОВОЕ ДОСТИЖЕНИЕ!",
    title: "Поздравляем! Вы получили новый бейдж!",
    subtitle: "За ваши знания и активность в ваш профиль добавлен новый знак отличия.",
    viewProfile: "Перейти в профиль",
    later: "Позже",
    of: "из",
  },
  en: {
    kicker: "🎉 NEW BADGE UNLOCKED!",
    title: "Congratulations! You earned a new badge!",
    subtitle: "A new honor has been added to your profile for your dedication and activity.",
    viewProfile: "Go to Profile",
    later: "Later",
    of: "of",
  },
};

export function BadgeAwardModal({ onNavigateToProfile }: BadgeAwardModalProps) {
  const [mounted, setMounted] = useState(false);
  const [badges, setBadges] = useState<UnseenBadge[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [celebrationPulse, setCelebrationPulse] = useState(false);

  const localeRaw = typeof window !== "undefined" ? localStorage.getItem("diamond_locale") || "uz" : "uz";
  const locale = (["uz", "ru", "en"].includes(localeRaw) ? localeRaw : "uz") as "uz" | "ru" | "en";
  const t = I18N[locale] || I18N.uz;

  const getAuthToken = () => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem("diamond_token") || "";
  };

  const checkUnseenBadges = useCallback(async () => {
    const token = getAuthToken();
    if (!token) return;

    try {
      const res = await fetch("/api/student/badges/unseen", {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data?.has_new && Array.isArray(data?.unseen_badges) && data.unseen_badges.length > 0) {
        setBadges(data.unseen_badges);
        setCurrentIndex(0);
        setIsOpen(true);
        setCelebrationPulse(true);
      }
    } catch {
      // Ignore network errors during polling
    }
  }, []);

  const markBadgeSeen = async (badgeCodes?: string[]) => {
    const token = getAuthToken();
    if (!token) return;
    try {
      await fetch("/api/student/badges/mark-seen", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(badgeCodes ? { badge_codes: badgeCodes } : {}),
      });
    } catch {
      // Ignore
    }
  };

  useEffect(() => {
    setMounted(true);
    // Initial check after a short delay
    const initialTimer = setTimeout(() => {
      checkUnseenBadges();
    }, 1500);

    // Periodic check every 30 seconds
    const interval = setInterval(() => {
      checkUnseenBadges();
    }, 30000);

    // Check on window focus
    const onFocus = () => {
      checkUnseenBadges();
    };
    window.addEventListener("focus", onFocus);

    return () => {
      clearTimeout(initialTimer);
      clearInterval(interval);
      window.removeEventListener("focus", onFocus);
    };
  }, [checkUnseenBadges]);

  if (!mounted || !isOpen || badges.length === 0) return null;

  const currentBadge = badges[currentIndex];
  if (!currentBadge) return null;

  const handleNextOrClose = async () => {
    await markBadgeSeen([currentBadge.code]);
    if (currentIndex + 1 < badges.length) {
      setCurrentIndex((idx) => idx + 1);
    } else {
      setIsOpen(false);
      setBadges([]);
    }
  };

  const handleGoToProfile = async () => {
    const allCodes = badges.map((b) => b.code);
    await markBadgeSeen(allCodes);
    setIsOpen(false);
    setBadges([]);

    if (onNavigateToProfile) {
      onNavigateToProfile();
    } else if (typeof window !== "undefined") {
      window.location.assign("/?role=student&section=profile");
    }
  };

  const modalContent = (
    <div className="fixed inset-0 z-[500] flex items-center justify-center p-4 bg-navy-950/80 backdrop-blur-md animate-fade-in">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t.title}
        className="relative w-full max-w-md overflow-hidden rounded-3xl border border-amber-400/30 bg-gradient-to-b from-navy-900 via-slate-900 to-navy-950 p-6 text-center text-white shadow-2xl transition-all sm:p-8"
      >
        {/* Glow & flare animations */}
        <div className="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 h-64 w-64 rounded-full bg-gradient-to-br from-amber-400/30 via-yellow-500/20 to-transparent blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 left-1/2 -translate-x-1/2 h-64 w-64 rounded-full bg-gradient-to-tr from-cyan-400/20 via-blue-500/15 to-transparent blur-3xl" />

        {/* Floating confetti dots */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <span className="absolute top-6 left-8 text-amber-300 animate-bounce text-sm opacity-75">✨</span>
          <span className="absolute top-12 right-10 text-yellow-200 animate-pulse text-base opacity-80">⭐</span>
          <span className="absolute bottom-16 left-10 text-cyan-300 animate-ping text-xs opacity-60" style={{ animationDuration: "3s" }}>✦</span>
          <span className="absolute bottom-12 right-8 text-amber-400 animate-bounce text-sm opacity-75" style={{ animationDelay: "0.5s" }}>🌟</span>
        </div>

        {/* Counter if multiple */}
        {badges.length > 1 && (
          <div className="relative mb-2 inline-block rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-amber-300">
            {currentIndex + 1} {t.of} {badges.length}
          </div>
        )}

        {/* Kicker */}
        <p className="relative text-xs font-extrabold tracking-widest text-amber-400 uppercase">
          {t.kicker}
        </p>

        {/* Badge Artwork with ring glow */}
        <div className="relative mx-auto my-5 flex h-32 w-32 items-center justify-center">
          <div
            className={`absolute inset-0 rounded-full bg-gradient-to-tr from-amber-500/30 via-yellow-400/40 to-amber-300/20 blur-xl ${
              celebrationPulse ? "scale-110" : "scale-100"
            } transition-transform duration-700`}
          />
          <div className="relative flex h-28 w-28 items-center justify-center rounded-2xl border-2 border-amber-400/50 bg-gradient-to-b from-amber-400/15 via-white/5 to-black/30 p-2 shadow-inner">
            {currentBadge.asset_url ? (
              <img
                src={currentBadge.asset_url}
                alt={currentBadge.title}
                className="h-24 w-24 object-contain filter drop-shadow-[0_8px_16px_rgba(245,158,11,0.5)] transition-transform duration-500 hover:scale-110"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = "none";
                  const parent = (e.target as HTMLElement).parentElement;
                  if (parent) {
                    const fallback = document.createElement("span");
                    fallback.innerText = "🏅";
                    fallback.className = "text-5xl drop-shadow-md";
                    parent.appendChild(fallback);
                  }
                }}
              />
            ) : (
              <span className="text-5xl drop-shadow-md">🏅</span>
            )}
          </div>
        </div>

        {/* Headline */}
        <h2 className="relative text-xl sm:text-2xl font-black tracking-tight text-white">
          {t.title}
        </h2>

        {/* Badge Title */}
        <div className="relative mt-2 inline-block rounded-xl bg-amber-400/15 px-4 py-1.5 border border-amber-400/30">
          <span className="text-base sm:text-lg font-black text-amber-300">
            {currentBadge.title}
          </span>
        </div>

        {/* Badge Description */}
        <p className="relative mt-3 text-sm text-slate-300 leading-relaxed max-w-sm mx-auto">
          {currentBadge.description || t.subtitle}
        </p>

        {/* Action Buttons */}
        <div className="relative mt-6 flex flex-col gap-2.5 sm:flex-row sm:gap-3">
          <button
            type="button"
            onClick={handleGoToProfile}
            className="flex-1 rounded-xl bg-gradient-to-r from-amber-500 via-amber-400 to-yellow-500 px-5 py-3.5 text-sm font-black text-navy-950 shadow-lg shadow-amber-500/25 transition-all hover:scale-[1.02] hover:shadow-amber-500/40 active:scale-[0.98]"
          >
            👤 {t.viewProfile}
          </button>
          <button
            type="button"
            onClick={handleNextOrClose}
            className="rounded-xl border border-white/15 bg-white/5 px-4 py-3.5 text-sm font-semibold text-white/80 transition-all hover:bg-white/10 hover:text-white active:scale-[0.98]"
          >
            {currentIndex + 1 < badges.length ? "Keyingisi →" : t.later}
          </button>
        </div>
      </div>
    </div>
  );

  return typeof document !== "undefined" ? createPortal(modalContent, document.body) : null;
}
