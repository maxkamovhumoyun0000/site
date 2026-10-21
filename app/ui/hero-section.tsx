"use client";

import { useWebT } from "./web-i18n";
import { PublicNavbar } from "./public-navbar";
import Link from "next/link";
import dynamic from "next/dynamic";

// three.js (≈1.6 MB) faqat kerak bo'lganda yuklansin — main bundle dan chiqarildi
const LandingDiamond3D = dynamic(
  () => import("./landing-diamond-3d").then((m) => m.LandingDiamond3D),
  { ssr: false, loading: () => null }
);

export function HeroSection() {
  const tt = useWebT();

  return (
    <section className="public-landing-hero relative min-h-[100svh] w-full bg-white dark:bg-[#07111f] font-sans flex flex-col transition-colors duration-300">
      <PublicNavbar activeTab="home" />

      {/* ── MAIN CONTENT ─────────────────────────────── */}
      <main className="flex-1 flex items-center justify-center pt-32 pb-16 px-4 md:px-8 relative overflow-hidden">
        <LandingDiamond3D />
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
              <a
                href="/login"
                className="w-full sm:w-auto px-8 py-4 bg-blue-600 text-white text-base md:text-lg font-bold rounded-xl shadow-xl shadow-blue-600/30 hover:bg-blue-700 hover:shadow-blue-600/40 hover:-translate-y-1 transition-all flex items-center justify-center gap-2"
              >
                {tt("common.login", "Kirish")}
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M17 8l4 4m0 0l-4 4m4-4H3" /></svg>
              </a>
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
