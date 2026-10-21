"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useWebT } from "./web-i18n";
import { LanguageIconButton, useTheme } from "./theme-provider";
import { LogoMark } from "./primitives";

type PublicTab = "home" | "courses" | "results" | "about" | "videos" | "articles";

const NAV_ITEMS = [
  { id: "videos", fallback: "Video darslar", href: "/videos" },
  { id: "results", fallback: "Natijalar", href: "/results" },
  { id: "courses", fallback: "Kurslar", href: "/courses" },
  { id: "about", fallback: "Biz haqimizda", href: "/about" },
] as const;

export function PublicNavbar({ activeTab }: { activeTab: PublicTab }) {
  const tt = useWebT();
  const { theme, toggle } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const updateScrollState = () => setScrolled(window.scrollY > 24);
    updateScrollState();
    window.addEventListener("scroll", updateScrollState, { passive: true });
    return () => window.removeEventListener("scroll", updateScrollState);
  }, []);

  return (
    <>
      <header className="public-pill-header fixed inset-x-0 top-0 z-[1000] px-3 pt-3 sm:px-4 sm:pt-4">
        <div className={`public-pill-header-backdrop ${scrolled ? "public-pill-header-backdrop--hidden" : ""}`} aria-hidden="true" />
        <div className="public-pill-navbar relative mx-auto flex h-14 max-w-[1600px] items-center justify-between gap-2 rounded-full px-3 shadow-lg sm:h-16 sm:px-5 lg:px-8">
          <Link href="/" className="flex shrink-0 items-center gap-2.5" aria-label="Diamond Education — Bosh sahifa">
            <LogoMark size="sm" />
            <span className="flex flex-col leading-none">
              <span className="text-sm font-black tracking-tight text-slate-900 sm:text-base">Diamond</span>
              <span className="mt-1 text-[8px] font-bold uppercase tracking-[0.16em] text-blue-700 sm:text-[9px]">Education</span>
            </span>
          </Link>

          <nav className="hidden min-w-0 flex-1 items-center justify-center gap-1 lg:flex" aria-label="Asosiy navigatsiya">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.id}
                href={item.href}
                aria-current={activeTab === item.id ? "page" : undefined}
                className={`whitespace-nowrap rounded-full px-2.5 py-2 text-[13px] font-medium transition-colors xl:px-3 xl:text-sm ${
                  activeTab === item.id
                    ? "text-[#4b2451]"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-950"
                }`}
              >
                {tt(`landing.nav.${item.id}`, item.fallback)}
              </Link>
            ))}
          </nav>

          <div className="flex shrink-0 items-center gap-1 sm:gap-2">
            <Link href="/login" className="hidden rounded-full px-3 py-2 text-sm font-semibold text-[#4b2451] hover:bg-slate-100 xl:inline-flex">
              {tt("common.login", "Kirish")}
            </Link>
            <a
              href="tel:+998977483634"
              className="hidden items-center gap-2 whitespace-nowrap rounded-full px-2 py-2 text-sm font-semibold text-[#38213e] transition-colors hover:bg-slate-100 xl:flex"
              aria-label="Qo'ng'iroq qilish: +998 97 748 36 34"
            >
              <PhoneIcon />
              <span>+998 97 748 36 34</span>
            </a>
            <a href="tel:+998977483634" className="flex h-10 w-10 items-center justify-center rounded-full text-[#38213e] hover:bg-slate-100 xl:hidden" aria-label="Qo'ng'iroq qilish">
              <PhoneIcon />
            </a>
            <LanguageIconButton className="!h-10 !rounded-full !border-0 !bg-transparent !px-2 !shadow-none hover:!bg-slate-100 dark:!bg-transparent dark:hover:!bg-slate-100" />
            <button
              type="button"
              onClick={toggle}
              className="flex h-10 w-10 items-center justify-center rounded-full text-[#32163a] transition-colors hover:bg-slate-100"
              aria-label={theme === "light" ? tt("theme.toggle.toDark", "Qorong'u rejimga o'tish") : tt("theme.toggle.toLight", "Yorug' rejimga o'tish")}
              title={theme === "light" ? tt("theme.toggle.toDark", "Qorong'u rejimga o'tish") : tt("theme.toggle.toLight", "Yorug' rejimga o'tish")}
            >
              {theme === "light" ? <MoonIcon /> : <SunIcon />}
            </button>
            <button
              type="button"
              className="flex h-10 w-10 items-center justify-center rounded-full text-slate-800 hover:bg-slate-100 lg:hidden"
              onClick={() => setMobileOpen((open) => !open)}
              aria-expanded={mobileOpen}
              aria-label={mobileOpen ? "Menyuni yopish" : "Menyuni ochish"}
            >
              {mobileOpen ? <CloseIcon /> : <MenuIcon />}
            </button>
          </div>
        </div>
      </header>

      {mobileOpen ? (
        <div className="fixed inset-0 z-[999] bg-slate-950/30 px-3 pt-[82px] backdrop-blur-sm lg:hidden" onClick={() => setMobileOpen(false)}>
          <nav className="mx-auto max-w-[1600px] rounded-3xl bg-white p-4 shadow-2xl" aria-label="Mobil navigatsiya" onClick={(event) => event.stopPropagation()}>
            <div className="grid gap-1">
              {NAV_ITEMS.map((item) => (
                <Link
                  key={item.id}
                  href={item.href}
                  aria-current={activeTab === item.id ? "page" : undefined}
                  onClick={() => setMobileOpen(false)}
                  className={`min-h-11 rounded-2xl px-4 py-3 text-sm font-semibold ${activeTab === item.id ? "bg-blue-50 text-blue-800" : "text-slate-700 hover:bg-slate-50"}`}
                >
                  {tt(`landing.nav.${item.id}`, item.fallback)}
                </Link>
              ))}
              <Link href="/login" onClick={() => setMobileOpen(false)} className="mt-2 min-h-11 rounded-2xl bg-blue-700 px-4 py-3 text-center text-sm font-bold text-white">
                {tt("common.login", "Kirish")}
              </Link>
              <a href="tel:+998977483634" className="min-h-11 rounded-2xl px-4 py-3 text-center text-sm font-semibold text-slate-700">
                +998 97 748 36 34
              </a>
            </div>
          </nav>
        </div>
      ) : null}
    </>
  );
}

function PhoneIcon() {
  return <svg className="h-[18px] w-[18px]" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6.62 10.79a15.05 15.05 0 006.59 6.59l2.2-2.2a1 1 0 011.01-.24c1.12.37 2.33.56 3.58.56a1 1 0 011 1V20a1 1 0 01-1 1C10.61 21 3 13.39 3 4a1 1 0 011-1h3.5a1 1 0 011 1c0 1.25.19 2.46.56 3.58a1 1 0 01-.25 1.01l-2.19 2.2z" /></svg>;
}

function MoonIcon() {
  return <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M20.1 15.5A8.5 8.5 0 018.5 3.9 8.5 8.5 0 1020.1 15.5z" /></svg>;
}

function SunIcon() {
  return <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path strokeLinecap="round" d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42" /></svg>;
}

function MenuIcon() {
  return <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path strokeLinecap="round" d="M4 7h16M4 12h16M4 17h16" /></svg>;
}

function CloseIcon() {
  return <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path strokeLinecap="round" d="m6 6 12 12M18 6 6 18" /></svg>;
}
