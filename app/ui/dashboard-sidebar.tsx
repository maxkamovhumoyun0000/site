"use client";

import type { CSSProperties } from "react";
import { LogoMark } from "./primitives";
import { useWebT } from "./web-i18n";

type DashboardSidebarProps = {
  visibleSections: string[];
  currentSection: string;
  isMobileLayout: boolean;
  mobileDrawerOpen: boolean;
  desktopCollapsed?: boolean;
  setMobileDrawerOpen: (open: boolean) => void;
  onNavigate: (section: string) => void;
  onLogout: () => void;
  sectionLabel: (section: string) => string;
  notificationCount?: number;
};

function iconForSection(section: string) {
  return section.charAt(0).toUpperCase() || "N";
}

function SidebarDiamondWordmark({
  className = "sidebar-diamond-wordmark",
  primarySize = 16,
  secondarySize = 8,
}: {
  className?: string;
  primarySize?: number;
  secondarySize?: number;
}) {
  return (
    <strong className={className} style={{ display: "inline-flex", flexDirection: "column", lineHeight: 1.0, verticalAlign: "middle" }}>
      <span style={{ fontSize: `${primarySize}px`, fontWeight: 900, letterSpacing: "-0.02em", color: "var(--ev-logo-color, #000000)" }}>
        D<span style={{ position: "relative", display: "inline-block" }}>ı<svg viewBox="0 0 24 24" fill="currentColor" style={{ position: "absolute", top: "-0.1em", left: "50%", transform: "translateX(-50%)", width: "0.26em", height: "0.26em", color: "var(--ev-primary, #002DFF)" }}><path d="M12 2L3.5 12 12 22l8.5-10z" /></svg></span>amond
      </span>
      <span style={{ fontSize: `${secondarySize}px`, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.14em", color: "var(--ev-primary)", marginTop: "1px" }}>Education</span>
    </strong>
  );
}

export function orderSections(sections: string[]) {
  const sectionSet = new Set(sections);
  const roleOrder = sectionSet.has("grammar") && sectionSet.has("vocabulary")
    ? [
        "home", "grammar", "vocabulary", "daily-test", "gamified", "arena", "leaderboard", "dcoin",
        "videos", "books", "homework", "notes", "support", "chats", "notifications", "profile",
      ]
    : sectionSet.has("users") && sectionSet.has("reviews")
      ? [
          "home", "users", "groups", "family-groups", "payments", "purchases", "homework",
          "attendance", "holidays", "admin-callbacks",
          "videos", "books", "courses", "gifts", "reviews", "leaderboard",
          "generator", "results", "competitions-history", "broadcasts", "surveys",
          "domain-email", "dpoint-settings", "sms", "chats", "notifications", "profile",
        ]
      : sectionSet.has("performance") && sectionSet.has("homework")
        ? [
            "home", "groups", "attendance", "homework", "arena", "tests", "performance", "dcoin",
            "leaderboard", "generator", "videos", "books", "chats", "notifications", "profile",
          ]
        : sectionSet.has("bookings")
          ? [
              "home", "bookings", "attendance", "homework", "calendar", "schedule", "hours", "filial", "bonus", "settings",
              "leaderboard", "videos", "books", "chats", "notifications", "profile",
            ]
          : sections;
  return [
    ...roleOrder.filter((item) => sectionSet.has(item)),
    ...sections.filter((item) => !roleOrder.includes(item)),
  ];
}

function pickRoleBottomSections(orderedSections: string[]) {
  const has = (section: string) => orderedSections.includes(section);
  const fillFrom = (preferred: string[], used: Set<string>, count: number) => {
    const out: string[] = [];
    for (const item of preferred) {
      if (out.length >= count) break;
      if (!has(item) || used.has(item) || item === "profile") continue;
      used.add(item);
      out.push(item);
    }
    for (const item of orderedSections) {
      if (out.length >= count) break;
      if (!has(item) || used.has(item) || item === "profile") continue;
      used.add(item);
      out.push(item);
    }
    return out;
  };
  const complete = (leftPreferred: string[], rightPreferred: string[]) => {
    const used = new Set<string>();
    const left = fillFrom(leftPreferred, used, 2);
    if (has("home")) used.add("home");
    const right = fillFrom(rightPreferred, used, 1);
    if (has("chats")) used.add("chats");
    const fallback = fillFrom(orderedSections, used, 5);
    const items = [
      left[0] || fallback.shift(),
      left[1] || fallback.shift(),
      has("home") ? "home" : fallback.shift(),
      right[0] || fallback.shift(),
      has("chats") ? "chats" : fallback.shift(),
    ].filter(Boolean) as string[];
    return items.slice(0, 5);
  };

  if (has("grammar") && has("vocabulary") && has("chats")) {
    return complete(["vocabulary", "arena"], ["grammar", "leaderboard", "books"]);
  }
  if (has("performance") && has("homework")) {
    return complete(["groups", "attendance"], ["homework", "performance"]);
  }
  if (has("users") && has("reviews")) {
    return complete(["users", "payments"], ["groups", "generator"]);
  }
  if (has("bookings")) {
    return complete(["bookings", "attendance"], ["homework", "bonus"]);
  }
  return complete(orderedSections, orderedSections);
}

export function DashboardSidebar({
  visibleSections,
  currentSection,
  isMobileLayout,
  mobileDrawerOpen,
  desktopCollapsed = false,
  setMobileDrawerOpen,
  onNavigate,
  sectionLabel,
  notificationCount = 0,
}: DashboardSidebarProps) {
  const tt = useWebT();
  const orderedSections = orderSections(visibleSections);

  const mobileBottomSections = pickRoleBottomSections(orderedSections);

  const itemBase = "group flex min-h-[42px] w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left text-sm font-black transition-all outline-none";
  const itemActive = "border-cyan-400/55 bg-cyan-400/12 text-navy-950 shadow-sm dark:border-cyan-300/40 dark:bg-cyan-300/12 dark:text-white";
  const itemIdle = "border-transparent text-ink-600 hover:border-line hover:bg-white/65 hover:text-navy-950 dark:text-slate-300 dark:hover:border-white/10 dark:hover:bg-white/[0.06] dark:hover:text-white";
  const iconBase = "sidebar-nav-icon grid h-8 w-8 shrink-0 place-items-center rounded-full transition-all";
  const iconActive = "sidebar-nav-icon--active";
  const iconIdle = "sidebar-nav-icon--idle";

  function renderNavButtons(prefix = "") {
    const bottomSet = new Set(mobileBottomSections);
    return orderedSections
      .filter((item) => item !== "profile")
      .map((item, index) => {
        const active = currentSection === item;
        return (
          <button
            key={`${prefix}${item}`}
            className={`${itemBase} ${active ? itemActive : itemIdle}`}
            onClick={() => onNavigate(item)}
            aria-current={active ? "page" : undefined}
            title={sectionLabel(item)}
            style={{ "--item-delay": `${index * 28}ms` } as CSSProperties}
          >
            <span className={`${iconBase} ${active ? iconActive : iconIdle}`} aria-hidden="true">
              <span className="sidebar-nav-icon__letter">{iconForSection(item)}</span>
            </span>
            {!desktopCollapsed ? <span className="min-w-0 flex-1 truncate">{sectionLabel(item)}</span> : null}
            {item === "notifications" && notificationCount > 0 ? (
              <span className="ml-auto rounded-full bg-red-500 px-1.5 py-0.5 text-[10px] font-black text-white">
                {notificationCount > 99 ? "99+" : notificationCount}
              </span>
            ) : active ? (
              <span className="ml-auto h-2 w-2 rounded-full bg-cyan-400" />
            ) : null}
          </button>
        );
      });
  }

  return (
    <>
      {!isMobileLayout ? (
        <aside
          data-testid="desktop-sidebar"
          className={`sidebar sticky top-0 z-30 hidden h-screen flex-col border-r border-line bg-surface shadow-[12px_0_36px_rgba(15,23,42,0.06)] transition-all dark:border-white/10 dark:bg-navy-950 dark:shadow-none md:flex ${desktopCollapsed ? "w-20" : "w-72"}`}
        >
          <div className="flex min-h-24 items-center gap-3 border-b border-line px-4 dark:border-white/10">
            <LogoMark size={desktopCollapsed ? "sm" : "md"} />
            {!desktopCollapsed ? (
              <div className="min-w-0">
                <SidebarDiamondWordmark primarySize={16} secondarySize={8} />
                <span className="block truncate text-[11px] font-bold text-ink-500 dark:text-slate-400">{tt("common.menu", "Menyu")}</span>
              </div>
            ) : null}
          </div>

          <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4 scrollbar-hide" aria-label={tt("common.menu", "Menyu")}>
            {renderNavButtons("desk-")}
          </nav>


        </aside>
      ) : null}

      {isMobileLayout ? (
        <>
          <div
            className={`dashboard-mobile-drawer-overlay fixed inset-0 z-[80] bg-navy-900/60 backdrop-blur-sm transition-opacity ${mobileDrawerOpen ? "opacity-100" : "pointer-events-none opacity-0"}`}
            onClick={() => setMobileDrawerOpen(false)}
            aria-hidden={!mobileDrawerOpen}
          />
          <aside
            data-testid="mobile-drawer"
            className={`dashboard-mobile-drawer fixed inset-y-0 left-0 z-[90] flex w-72 max-w-[86vw] transform flex-col border-r border-line bg-surface shadow-2xl transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] dark:border-white/10 dark:bg-navy-950 ${mobileDrawerOpen ? "translate-x-0" : "-translate-x-full"}`}
            aria-hidden={!mobileDrawerOpen}
          >
            <div className="flex items-center justify-between border-b border-line px-4 py-4 dark:border-white/10">
              <div className="flex min-w-0 items-center gap-3">
                <LogoMark size="sm" />
                <SidebarDiamondWordmark primarySize={18} secondarySize={9} />
              </div>
              <button
                className="-mr-2 rounded-xl p-2 text-ink-500 hover:bg-surface-soft dark:text-slate-300 dark:hover:bg-white/10"
                onClick={() => setMobileDrawerOpen(false)}
                aria-label={tt("common.menu.close", "Menyuni yopish")}
              >
                X
              </button>
            </div>

            <div className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
              {renderNavButtons("mob-")}
            </div>


          </aside>

          <nav className={`bottom-nav-mobile ${mobileDrawerOpen ? "is-drawer-open" : ""} fixed bottom-0 left-0 right-0 z-40 flex min-h-[4rem] pt-1 items-center justify-around border-t border-line bg-surface/95 px-2 backdrop-blur-xl transition-all duration-200 dark:border-white/10 dark:bg-navy-950/95 md:hidden pb-safe-bottom`}>
              {mobileBottomSections.map((item) => (
                <button
                  key={`bot-nav-${item}`}
                  className={`bottom-nav-item ${item === "home" ? "home-center" : ""} flex h-full w-full flex-col items-center justify-center gap-1 transition-colors ${currentSection === item ? "active text-navy-700 dark:text-cyan-300" : "text-ink-500 hover:text-ink-700 dark:text-slate-400 dark:hover:text-slate-200"}`}
                  onClick={() => onNavigate(item)}
                  aria-current={currentSection === item ? "page" : undefined}
                  title={sectionLabel(item)}
                >
                  <span className={`sidebar-nav-icon sidebar-bottom-nav-icon flex h-8 w-8 items-center justify-center rounded-full ${currentSection === item ? "sidebar-nav-icon--active" : "sidebar-nav-icon--idle"}`}>
                    <span className="sidebar-nav-icon__letter">{iconForSection(item)}</span>
                  </span>
                  <span className="max-w-full truncate px-1 text-[10px] font-bold tracking-wide">{sectionLabel(item)}</span>
                </button>
              ))}
            </nav>
        </>
      ) : null}
    </>
  );
}
