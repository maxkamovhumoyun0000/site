"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export function StudentCompetitionRedirect({
  section,
  arenaMode,
  searchParams,
}: {
  section: string;
  arenaMode?: string;
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  const router = useRouter();

  useEffect(() => {
    const read = (key: string) => {
      const value = searchParams?.[key];
      return Array.isArray(value) ? String(value[0] || "") : String(value || "");
    };
    const params = new URLSearchParams();
    params.set("role", "student");
    params.set("section", section);
    const mode = String(read("arena_mode") || arenaMode || "").trim();
    const subject = String(read("subject") || "").trim();
    const autoJoin = String(read("auto_join") || "").trim();
    const sessionId = String(read("session_id") || "").trim();
    if (mode) params.set("arena_mode", mode);
    if (subject) params.set("subject", subject);
    if (autoJoin) params.set("auto_join", autoJoin);
    if (sessionId) params.set("session_id", sessionId);
    router.replace(`/?${params.toString()}`);
  }, [arenaMode, router, searchParams, section]);

  return (
    <main className="placement-page process-runtime-page">
      <section className="placement-card placement-runtime-card">
        <div className="panel-card text-center text-sm font-black text-navy-900 dark:text-white">
          Yuklanmoqda...
        </div>
      </section>
    </main>
  );
}
