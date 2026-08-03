"use client";

import { useWebT } from "./web-i18n";
import { LanguageIconButton } from "./theme-provider";
import { useState, useEffect } from "react";
import Link from "next/link";
import { LogoMark } from "./primitives";
import dynamic from "next/dynamic";

// three.js (≈1.6 MB) faqat kerak bo'lganda yuklansin — main bundle dan chiqarildi
const LandingDiamond3D = dynamic(
  () => import("./landing-diamond-3d").then((m) => m.LandingDiamond3D),
  { ssr: false, loading: () => null }
);

/* ---- Nav items ---- */
const NAV_ITEMS = [
  { id: "courses",  label: "Kurslar", href: "/courses" },
  { id: "videos",   label: "Video darslar", href: "/videos" },
  { id: "results",  label: "Natijalar", href: "/results" },
  { id: "about",    label: "Biz haqimizda", href: "/about" },
] as const;

export function HeroSection() {
  const tt = useWebT();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [show3D, setShow3D] = useState(true);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <section className="relative min-h-[100svh] w-full bg-white dark:bg-[#07111f] font-sans flex flex-col transition-colors duration-300">
      {/* ── NAVBAR ────────────────────────────────────────── */}
      <header
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 border-b ${
          scrolled 
            ? "bg-white/90 dark:bg-[#0a1526]/90 backdrop-blur-md border-gray-200 dark:border-gray-800 py-3" 
            : "bg-transparent border-transparent py-5"
        }`}
      >
        <div className="w-full 2xl:px-8 mx-auto px-4 md:px-8 flex items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-3 relative z-20 group">
            <div className="w-10 h-10 md:w-12 md:h-12 rounded-xl flex items-center justify-center overflow-hidden shadow-lg group-hover:scale-105 transition-transform">
              <img src="/logo.jpg" alt="Diamond Education" className="object-cover w-full h-full" />
            </div>
            <span className="flex flex-col justify-center">
              <span className="text-lg md:text-xl font-black text-gray-900 dark:text-white leading-tight tracking-tight">
                Diamond
              </span>
              <span className="text-[10px] md:text-xs font-bold text-blue-600 uppercase tracking-widest leading-none">
                Education
              </span>
            </span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-8" aria-label="Asosiy navigatsiya">
            {NAV_ITEMS.map(item => (
              <Link
                key={`desk-${item.id}`}
                href={item.href}
                className="text-[15px] font-semibold text-gray-700 hover:text-blue-600 dark:text-gray-300 dark:hover:text-blue-400 transition-colors"
              >
                {tt(`landing.nav.${item.id}`, item.label)}
              </Link>
            ))}
          </nav>

          {/* Desktop right */}
          <div className="hidden md:flex items-center gap-6">
            <div className="flex flex-col items-end mr-2">
              <a href="tel:+998977483634" className="text-sm font-bold text-gray-900 hover:text-blue-600 dark:text-white transition-colors">+998 (97) 748-36-34</a>
              <a href="tel:+998977443634" className="text-[11px] font-bold text-gray-500 hover:text-gray-700 dark:text-gray-400 transition-colors">+998 (97) 744-36-34</a>
            </div>
            <LanguageIconButton />
            <Link 
              href="/login"
              className="px-6 py-2.5 bg-blue-600 text-white text-sm font-bold rounded-xl shadow-lg shadow-blue-600/30 hover:bg-blue-700 hover:shadow-blue-600/40 hover:-translate-y-0.5 transition-all"
            >
              {tt("common.login", "Kirish")}
            </Link>
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
      <div
        className={`fixed inset-0 z-40 bg-white dark:bg-[#07111f] transition-transform duration-300 ease-in-out ${mobileNavOpen ? "translate-x-0" : "translate-x-full"}`}
      >
        <div className="flex flex-col h-full pt-24 px-6 pb-8">
          <nav className="flex flex-col gap-6 text-2xl font-black">
            {NAV_ITEMS.map(item => (
              <Link
                key={`mob-${item.id}`}
                href={item.href}
                className="text-gray-900 dark:text-white"
                onClick={() => setMobileNavOpen(false)}
              >
                {tt(`landing.nav.${item.id}`, item.label)}
              </Link>
            ))}
          </nav>

          <div className="mt-auto flex flex-col gap-6">
            <div className="flex flex-col gap-2">
              <a href="tel:+998977483634" className="text-xl font-bold text-gray-900 dark:text-white">+998 (97) 748-36-34</a>
              <a href="tel:+998977443634" className="text-xl font-bold text-gray-500 dark:text-gray-400">+998 (97) 744-36-34</a>
            </div>
            <div className="flex items-center gap-4">
              <LanguageIconButton />
              <span className="text-sm font-semibold text-gray-500 dark:text-gray-400">Tilni o&apos;zgartirish</span>
            </div>
            <Link
              href="/login"
              className="w-full py-4 bg-blue-600 text-white text-center text-lg font-bold rounded-xl active:bg-blue-700 transition-colors"
            >
              {tt("common.login", "Kirish")}
            </Link>
          </div>
        </div>
      </div>

      {/* ── MAIN CONTENT ─────────────────────────────── */}
      <main className="flex-1 flex items-center justify-center pt-32 pb-16 px-4 md:px-8 relative overflow-hidden">
        {show3D && <LandingDiamond3D />}
        {/* Decorative background blurs */}
        <div className="absolute top-1/4 -left-64 w-[500px] h-[500px] bg-blue-400/20 dark:bg-blue-600/20 rounded-full blur-[120px] pointer-events-none" />
        <div className="absolute bottom-0 -right-32 w-[600px] h-[600px] bg-indigo-400/10 dark:bg-indigo-600/10 rounded-full blur-[120px] pointer-events-none" />

        <div className="w-full 2xl:px-8 mx-auto grid lg:grid-cols-2 gap-12 lg:gap-8 items-center z-10">
          
          {/* ── LEFT COLUMN ───────────────────────────────────── */}
          <div className="flex flex-col items-start max-w-2xl">


            <h1 className="text-4xl md:text-6xl lg:text-[72px] font-black leading-[1.05] tracking-tight text-gray-900 dark:text-white mb-6">
              {tt("landing.hero.title.line1", "Diamond Education")}
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-500">
                {tt("landing.hero.title.line2", "Yangiyo'l shaxridagi")}
              </span>
              <br />
              {tt("landing.hero.title.line3", "Yetakchi o'quv markazi")}
            </h1>

            <p className="text-lg md:text-xl text-gray-600 dark:text-gray-400 font-medium leading-relaxed mb-10 max-w-lg">
              {tt(
                "landing.hero.subtitle",
                "Talabalar, o'qituvchilar va ota-onalarni birlashtiruvchi yagona raqamli ekotizim. Aniq o'quv rejasi, real vaqt rejimidagi tahlillar va shaxsiy rivojlanish traektoriyasi.",
              )}
            </p>

            <div className="flex flex-col sm:flex-row items-center gap-4 w-full sm:w-auto">
              <Link
                href="/login"
                className="w-full sm:w-auto px-8 py-4 bg-blue-600 text-white text-base md:text-lg font-bold rounded-xl shadow-xl shadow-blue-600/30 hover:bg-blue-700 hover:shadow-blue-600/40 hover:-translate-y-1 transition-all flex items-center justify-center gap-2"
              >
                {tt("common.login", "Kirish")}
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M17 8l4 4m0 0l-4 4m4-4H3" /></svg>
              </Link>
              <Link 
                href="/results"
                className="w-full sm:w-auto px-8 py-4 bg-white dark:bg-gray-800 text-gray-900 dark:text-white border-2 border-gray-200 dark:border-gray-700 text-base md:text-lg font-bold rounded-xl hover:border-blue-600 dark:hover:border-blue-500 hover:text-blue-600 dark:hover:text-blue-400 hover:-translate-y-1 transition-all flex items-center justify-center"
              >
                {tt("landing.hero.resultsCta", "Natijalarimiz")}
              </Link>
            </div>
          </div>

          {/* ── RIGHT COLUMN — 3D Diamond ───────────────── */}
          <div 
            className="relative flex items-center justify-center lg:justify-end min-h-[300px] sm:min-h-[400px] lg:min-h-[600px] animate-fade-in [animation-delay:200ms] cursor-pointer"
            onClick={() => window.dispatchEvent(new CustomEvent("diamond_click"))}
          >
            <div className="relative w-full aspect-square max-w-[320px] sm:max-w-[400px] lg:max-w-[580px]">
               {/* Clickable area for the full-screen 3D Diamond */}
            </div>
          </div>
        </div>
      </main>
    </section>
  );
}
