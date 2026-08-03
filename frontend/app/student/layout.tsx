"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function StudentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading, isAuthenticated, logout } = useAuth();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [user, isLoading, isAuthenticated, router]);

  useEffect(() => {
    if (!menuOpen) {
      document.body.style.overflow = "";
      return;
    }
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [menuOpen]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center diamond-gradient">
        <div className="w-8 h-8 border-3 border-[hsl(var(--primary))/0.24] border-t-[hsl(var(--primary))] rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return null;
  }

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <div className="min-h-screen bg-[hsl(var(--background))]">
      <div
        className={`fixed inset-0 z-30 bg-black/40 transition-opacity ${menuOpen ? "opacity-100" : "pointer-events-none opacity-0"}`}
        onClick={() => setMenuOpen(false)}
        aria-hidden={!menuOpen}
      />

      <aside
        className={`fixed left-0 top-0 z-40 h-screen w-72 premium-gradient border-r border-[hsl(var(--border))] transition-transform duration-300 ${menuOpen ? "translate-x-0" : "-translate-x-full"}`}
        aria-hidden={!menuOpen}
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between p-4 border-b border-[hsl(var(--border))]">
            <strong className="text-[hsl(var(--foreground))]">Menu</strong>
            <button type="button" className="btn btn-soft small" onClick={() => setMenuOpen(false)}>
              Yopish
            </button>
          </div>
          <nav className="p-4 space-y-2">
            <Link
              href="/student"
              className="block rounded-lg border border-[hsl(var(--border))] px-4 py-3 text-sm text-[hsl(var(--foreground))] hover:bg-[hsl(var(--primary))/0.08]"
              onClick={() => setMenuOpen(false)}
            >
              Dashboard
            </Link>
          </nav>
          <div className="mt-auto p-4 border-t border-[hsl(var(--border))]">
            <button
              onClick={async () => {
                await handleLogout();
                setMenuOpen(false);
              }}
              className="w-full btn btn-soft"
            >
              Chiqish
            </button>
          </div>
        </div>
      </aside>

      <nav className="premium-gradient shadow-lg border-b border-[hsl(var(--border))]">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="btn btn-soft small"
                onClick={() => setMenuOpen(true)}
                aria-label="Open menu"
                title="Open menu"
              >
                ☰
              </button>
              <Link href="/student" className="flex items-center gap-2 font-serif font-bold text-xl text-[hsl(var(--foreground))]">
                <div className="w-8 h-8 rounded gold-gradient flex items-center justify-center">
                  <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                  </svg>
                </div>
                Diamond Education
              </Link>
            </div>
            <div className="flex items-center gap-6">
              <Link href="/student" className="text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition">
                Dashboard
              </Link>
              <button
                onClick={handleLogout}
                className="text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition"
              >
                Chiqish
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {children}
      </main>
    </div>
  );
}
