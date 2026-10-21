"use client";

import { type ReactNode } from "react";
import { useWebT } from "./ui/web-i18n";
import { PublicNavbar } from "./ui/public-navbar";
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

  return (
    <main className="public-page-shell min-h-screen bg-gray-50 dark:bg-[#07111f] font-sans flex flex-col transition-colors duration-300">
      <PublicNavbar activeTab={activeTab} />

      {/* Main Content Area */}
      <section className="public-page-hero pt-32 pb-12 px-4 md:px-8 bg-white dark:bg-[#0a1526] border-b border-gray-100 dark:border-gray-800">
        <div className="container mx-auto max-w-5xl text-center">
          <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300 text-sm font-bold mb-4 uppercase tracking-wider">
            {kicker}
          </span>
          <h1 className="text-3xl md:text-5xl lg:text-6xl font-black text-gray-900 dark:text-white tracking-tight mb-4">{title}</h1>
          {subtitle ? <p className="text-lg md:text-xl text-gray-500 dark:text-gray-400 max-w-2xl mx-auto">{subtitle}</p> : null}
          {action ? <div className="mt-8 flex justify-center">{action}</div> : null}
        </div>
      </section>

      <section className="public-page-content flex-1 py-12 px-4 md:px-8 bg-gray-50 dark:bg-[#07111f]">
        <div className="w-full 2xl:px-8 mx-auto">
          {children}
        </div>
      </section>

      {/* Footer */}
      <PublicFooter />
    </main>
  );
}
