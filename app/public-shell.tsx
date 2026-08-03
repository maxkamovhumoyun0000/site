"use client";

import { type ReactNode, useState, useEffect } from "react";
import { useWebT } from "./ui/web-i18n";
import { LanguageIconButton } from "./ui/theme-provider";
import { LogoMark } from "./ui/primitives";
import { PublicFooter } from "./ui/public-footer";

type PublicTab = "home" | "courses" | "results" | "articles" | "about" | "videos";

export function PublicShell({
  activeTab,
  kicker,
  title,
  subtitle,
  action,
  children,
}: {
  activeTab: PublicTab;
  kicker: string;
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  const tt = useWebT();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-[#07111f] font-sans flex flex-col transition-colors duration-300">
      {/* ── NAVBAR ────────────────────────────────────────── */}
      <header
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 border-b ${
          scrolled 
            ? "bg-white/90 dark:bg-[#0a1526]/90 backdrop-blur-md border-gray-200 dark:border-gray-800 py-3" 
            : "bg-white dark:bg-[#0a1526] border-gray-200 dark:border-gray-800 py-3"
        }`}
      >
        <div className="w-full 2xl:px-8 mx-auto px-4 md:px-8 flex items-center justify-between">
          {/* Logo */}
          <a href="/" className="flex items-center gap-3 relative z-20 group">
            <div className="group-hover:scale-105 transition-transform">
              <LogoMark size="sm" />
            </div>
            <span className="flex flex-col justify-center">
              <span className="text-lg md:text-xl font-black text-gray-900 dark:text-white leading-tight tracking-tight">
                Diamond
              </span>
              <span className="text-[10px] md:text-xs font-bold text-blue-600 uppercase tracking-widest leading-none">
                Education
              </span>
            </span>
          </a>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-8" aria-label="Asosiy navigatsiya">
            <a href="/courses" className={`text-[15px] font-semibold transition-colors ${activeTab === 'courses' ? 'text-blue-600' : 'text-gray-700 hover:text-blue-600 dark:text-gray-300 dark:hover:text-blue-400'}`}>
              {tt("landing.nav.courses", "Kurslar")}
            </a>
            <a href="/videos" className={`text-[15px] font-semibold transition-colors ${activeTab === 'videos' ? 'text-blue-600' : 'text-gray-700 hover:text-blue-600 dark:text-gray-300 dark:hover:text-blue-400'}`}>
              {tt("landing.nav.videos", "Video darslar")}
            </a>
            <a href="/results" className={`text-[15px] font-semibold transition-colors ${activeTab === 'results' ? 'text-blue-600' : 'text-gray-700 hover:text-blue-600 dark:text-gray-300 dark:hover:text-blue-400'}`}>
              {tt("landing.nav.results", "Natijalar")}
            </a>
            <a href="/about" className={`text-[15px] font-semibold transition-colors ${activeTab === 'about' ? 'text-blue-600' : 'text-gray-700 hover:text-blue-600 dark:text-gray-300 dark:hover:text-blue-400'}`}>
              {tt("landing.nav.about", "Biz haqimizda")}
            </a>
          </nav>

          {/* Desktop right */}
          <div className="hidden md:flex items-center gap-6">
            <LanguageIconButton />
            <a 
              href="/login"
              className="px-6 py-2.5 bg-blue-600 text-white text-sm font-bold rounded-xl shadow-lg shadow-blue-600/30 hover:bg-blue-700 hover:-translate-y-0.5 transition-all"
            >
              {tt("common.login", "Kirish")}
            </a>
          </div>

          {/* Mobile hamburger */}
          <button 
            className="md:hidden relative z-20 w-10 h-10 flex flex-col items-center justify-center gap-1.5 text-gray-900 dark:text-white bg-gray-100 dark:bg-gray-800 rounded-lg"
            onClick={() => setMobileNavOpen(!mobileNavOpen)}
            aria-label="Toggle menu"
          >
            <span className={`w-5 h-0.5 bg-current transition-all ${mobileNavOpen ? 'rotate-45 translate-y-2' : ''}`} />
            <span className={`w-5 h-0.5 bg-current transition-all ${mobileNavOpen ? 'opacity-0' : ''}`} />
            <span className={`w-5 h-0.5 bg-current transition-all ${mobileNavOpen ? '-rotate-45 -translate-y-2' : ''}`} />
          </button>
        </div>
      </header>

      {/* ── MOBILE DRAWER ─────────────────────────────────── */}
      <div className={`fixed inset-0 z-40 bg-white dark:bg-[#07111f] transition-transform duration-300 ease-in-out md:hidden ${mobileNavOpen ? "translate-x-0" : "translate-x-full"}`}>
        <div className="flex flex-col h-full pt-24 px-6 pb-8">
          <nav className="flex flex-col gap-6 text-2xl font-black">
            <a href="/courses" className={activeTab === 'courses' ? "text-blue-600" : "text-gray-900 dark:text-white"} onClick={() => setMobileNavOpen(false)}>
              {tt("landing.nav.courses", "Kurslar")}
            </a>
            <a href="/videos" className={activeTab === 'videos' ? "text-blue-600" : "text-gray-900 dark:text-white"} onClick={() => setMobileNavOpen(false)}>
              {tt("landing.nav.videos", "Video darslar")}
            </a>
            <a href="/results" className={activeTab === 'results' ? "text-blue-600" : "text-gray-900 dark:text-white"} onClick={() => setMobileNavOpen(false)}>
              {tt("landing.nav.results", "Natijalar")}
            </a>
            <a href="/about" className={activeTab === 'about' ? "text-blue-600" : "text-gray-900 dark:text-white"} onClick={() => setMobileNavOpen(false)}>
              {tt("landing.nav.about", "Biz haqimizda")}
            </a>
          </nav>
          <div className="mt-auto flex flex-col gap-6">
            <LanguageIconButton />
            <a href="/login" className="w-full py-4 bg-blue-600 text-white text-center text-lg font-bold rounded-xl active:bg-blue-700 transition-colors">
              {tt("common.login", "Kirish")}
            </a>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <section className="pt-32 pb-12 px-4 md:px-8 bg-white dark:bg-[#0a1526] border-b border-gray-100 dark:border-gray-800">
        <div className="container mx-auto max-w-5xl text-center">
          <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300 text-sm font-bold mb-4 uppercase tracking-wider">
            {kicker}
          </span>
          <h1 className="text-3xl md:text-5xl lg:text-6xl font-black text-gray-900 dark:text-white tracking-tight mb-4">{title}</h1>
          {subtitle ? <p className="text-lg md:text-xl text-gray-500 dark:text-gray-400 max-w-2xl mx-auto">{subtitle}</p> : null}
          {action ? <div className="mt-8 flex justify-center">{action}</div> : null}
        </div>
      </section>

      <section className="flex-1 py-12 px-4 md:px-8 bg-gray-50 dark:bg-[#07111f]">
        <div className="w-full 2xl:px-8 mx-auto">
          {children}
        </div>
      </section>

      {/* Footer */}
      <PublicFooter />
    </main>
  );
}
