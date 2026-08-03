"use client";

import { useMemo, useState } from "react";
import { LogoMark } from "./primitives";
import { LanguageIconButton } from "./theme-provider";
import { useWebT } from "./web-i18n";

const NAV_ITEMS = [
  { id: "courses", label: "Kurslar" },
  { id: "results", label: "Natijalar" },
  { id: "videos", label: "Video darslar" },
] as const;

export function LandingNavbar({ onNavigate }: { onNavigate: (id: string) => void }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const tt = useWebT();
  const navItems = useMemo(() => NAV_ITEMS, []);

  function goToSection(id: string) {
    onNavigate(id);
    setMobileNavOpen(false);
  }

  return (
    <>
      <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-4 py-3 border-b md:px-8 border-white/20 bg-navy-900/80 backdrop-blur-lg shadow-premium">
        <a
          className="flex items-center gap-3 no-underline transition-transform hover:scale-105"
          href="#top"
          onClick={(event) => {
            event.preventDefault();
            if (window.matchMedia("(max-width: 767px)").matches) {
              setMobileNavOpen(true);
            } else {
              goToSection("top");
            }
          }}
        >
          <LogoMark size="sm" />
          <span className="hidden text-xl font-black text-white md:block font-display tracking-tight">
            Diamond<span className="text-cyan-400">Edu</span>
          </span>
        </a>

        <nav className="items-center hidden gap-6 md:flex">
          {navItems.map((item) => (
            <a
              key={`desktop-${item.id}`}
              className="text-sm font-bold text-white/90 hover:text-white hover:underline underline-offset-4 transition-all"
              href={`#${item.id}`}
              onClick={(event) => {
                event.preventDefault();
                goToSection(item.id);
              }}
            >
              <span>{tt(`landing.nav.${item.id}`, item.label)}</span>
            </a>
          ))}
          <div className="hero-quick-controls">
            <LanguageIconButton />
          </div>
          <a className="px-5 py-2 text-sm font-bold text-navy-900 transition-transform bg-white rounded-xl hover:bg-cyan-50 hover:scale-105 hover:shadow-premium-hover" href="/login">
            {tt("common.login", "Kirish")}
          </a>
        </nav>

      </header>

      {/* Mobile Menu Overlay */}
      <div 
        className={`fixed inset-0 z-40 bg-navy-900/40 backdrop-blur-sm transition-opacity duration-300 md:hidden ${mobileNavOpen ? "opacity-100" : "opacity-0 pointer-events-none"}`} 
        onClick={() => setMobileNavOpen(false)}
      />

      <aside className={`fixed top-0 right-0 z-50 w-64 h-full pt-20 pb-6 px-6 bg-navy-900 border-l border-white/10 shadow-2xl flex flex-col gap-6 transform transition-transform duration-300 ease-in-out md:hidden ${mobileNavOpen ? "translate-x-0" : "translate-x-full"}`}>
        <div className="flex flex-col gap-4">
          {navItems.map((item) => (
            <a
              key={`mobile-${item.id}`}
              className="text-lg font-bold text-white/90 hover:text-white"
              href={`#${item.id}`}
              onClick={(event) => {
                event.preventDefault();
                goToSection(item.id);
              }}
            >
              <span>{tt(`landing.nav.${item.id}`, item.label)}</span>
            </a>
          ))}
        </div>
        
        <div className="mt-auto flex flex-col gap-3">
          <div className="hero-quick-controls justify-center">
            <LanguageIconButton />
          </div>
          <a className="w-full px-4 py-3 text-center text-sm font-bold text-navy-900 bg-white rounded-xl shadow-premium" href="/login">
            {tt("common.login", "Kirish")}
          </a>
        </div>
      </aside>
    </>
  );
}
