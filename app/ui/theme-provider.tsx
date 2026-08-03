"use client";

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { useWebLocale, useWebT } from "./web-i18n";

type Theme = "light" | "dark";

const ThemeContext = createContext<{ theme: Theme; toggle: () => void }>({
  theme: "light",
  toggle: () => {},
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const token = typeof window !== "undefined" && localStorage.getItem("diamond_token");
    const saved = localStorage.getItem("diamond_theme") as Theme | null;
    const savedLocale = localStorage.getItem("diamond_locale") || "uz";
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    // Lock to light if not logged in (landing/login page)
    const initial = !token ? "light" : (saved || (prefersDark ? "dark" : "light"));
    setTheme(initial);
    document.documentElement.setAttribute("data-theme", initial);
    document.documentElement.lang = savedLocale;
  }, []);

  const toggle = useCallback(() => {
    const token = typeof window !== "undefined" && localStorage.getItem("diamond_token");
    if (!token) return; // Disable theme toggling on landing/login page
    setTheme((prev) => {
      const next = prev === "light" ? "dark" : "light";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("diamond_theme", next);
      return next;
    });
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}

export function ThemeToggleButton() {
  const { theme, toggle } = useTheme();
  const tt = useWebT();
  const nextTitle = theme === "light"
    ? tt("theme.toggle.toDark", "Qorong'u rejimga o'tish")
    : tt("theme.toggle.toLight", "Yorug' rejimga o'tish");
  return (
    <button
      className="theme-toggle"
      onClick={toggle}
      aria-label={nextTitle}
      title={nextTitle}
    >
      <span className="toggle-thumb" />
      <span className="toggle-icon">☀️</span>
      <span className="toggle-icon">🌙</span>
    </button>
  );
}

const LANGUAGE_ORDER = ["uz", "ru", "en"] as const;

export function LanguageIconButton({ className = "" }: { className?: string }) {
  const locale = useWebLocale();
  const tt = useWebT();
  const currentIndex = Math.max(0, LANGUAGE_ORDER.indexOf(locale));
  const current = LANGUAGE_ORDER[currentIndex] || "uz";
  const nextTitle = `${tt("common.language", "Til")}: ${current.toUpperCase()}`;

  function cycleLanguage() {
    const next = LANGUAGE_ORDER[(currentIndex + 1) % LANGUAGE_ORDER.length] || "uz";
    if (typeof window === "undefined") return;
    localStorage.setItem("diamond_locale", next);
    document.documentElement.lang = next;
    window.dispatchEvent(new CustomEvent("diamond:locale-change", { detail: { locale: next } }));
  }

  return (
    <button
      type="button"
      className={`flex items-center justify-center gap-1.5 h-10 px-3.5 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-blue-600 dark:hover:text-blue-400 transition-colors shadow-sm ${className}`}
      onClick={cycleLanguage}
      aria-label={nextTitle}
      title={nextTitle}
    >
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <strong className="text-[13px] font-bold tracking-wide uppercase">{current}</strong>
    </button>
  );
}
