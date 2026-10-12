"use client";

import { useCallback, useEffect, useState } from "react";

type SpeakingUser = {
  id: number;
  full_name: string;
  login_id: string;
  role: string;
  subjects: string[];
  blocked: boolean;
  access_enabled: boolean;
  speaking_account_state?: "active" | "inactive";
  created_at?: string | null;
};

type AdminSpeakingUsersProps = {
  apiFetch: (path: string, options?: { method?: string; body?: unknown; timeoutMs?: number }) => Promise<unknown>;
};

/**
 * Dedicated account directory for the standalone Diamond Speaking app.
 * These accounts deliberately never appear in the regular admin users screen.
 */
export function AdminSpeakingUsers({ apiFetch }: AdminSpeakingUsersProps) {
  const [items, setItems] = useState<SpeakingUser[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (search = "") => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ speaking_only: "true", limit: "250" });
      if (search.trim()) params.set("q", search.trim());
      const response = await apiFetch(`/admin/users?${params.toString()}`, { method: "GET" }) as {
        items?: SpeakingUser[];
        total?: number;
      };
      setItems(Array.isArray(response?.items) ? response.items : []);
      setTotal(Number(response?.total || 0));
    } catch (cause: any) {
      setError(cause?.message || "Speaking App foydalanuvchilarini yuklab bo‘lmadi.");
    } finally {
      setLoading(false);
    }
  }, [apiFetch]);

  useEffect(() => {
    void load("");
  }, [load]);

  function submitSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void load(query);
  }

  return (
    <section className="mx-auto w-full max-w-7xl space-y-5 px-3 py-5 pb-24 sm:px-6">
      <header className="rounded-3xl border border-cyan-400/25 bg-gradient-to-br from-cyan-500/10 via-white to-blue-500/10 p-6 shadow-sm dark:from-cyan-400/10 dark:via-navy-950 dark:to-blue-500/10">
        <span className="inline-flex rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-black uppercase tracking-wide text-cyan-700 dark:text-cyan-300">Diamond Speaking</span>
        <h1 className="mt-3 text-2xl font-black tracking-tight text-navy-950 dark:text-white">Speaking App foydalanuvchilari</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-600 dark:text-slate-300">
          Bu alohida ro‘yxat faqat Diamond Speaking ilovasida ochilgan akkauntlarni ko‘rsatadi. Ular umumiy foydalanuvchilar sahifasiga qo‘shilmaydi va tasdiqlash kutmaydi.
        </p>
      </header>

      <form onSubmit={submitSearch} className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4 shadow-sm sm:flex-row dark:border-white/10 dark:bg-navy-950">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Ism yoki login bo‘yicha qidirish"
          className="min-w-0 flex-1 rounded-xl border border-line bg-white px-4 py-3 text-sm font-medium text-navy-950 outline-none placeholder:text-ink-400 focus:border-cyan-500 dark:border-white/15 dark:bg-white/5 dark:text-white"
        />
        <button type="submit" className="rounded-xl bg-cyan-600 px-5 py-3 text-sm font-black text-white transition hover:bg-cyan-500" disabled={loading}>
          Qidirish
        </button>
        <button type="button" onClick={() => void load(query)} className="rounded-xl border border-line px-5 py-3 text-sm font-black text-ink-700 transition hover:bg-surface-soft dark:border-white/15 dark:text-slate-200 dark:hover:bg-white/10" disabled={loading}>
          Yangilash
        </button>
      </form>

      {error ? <p role="alert" className="rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm font-semibold text-red-700 dark:text-red-300">{error}</p> : null}

      <div className="overflow-hidden rounded-2xl border border-line bg-surface shadow-sm dark:border-white/10 dark:bg-navy-950">
        <div className="flex items-center justify-between border-b border-line px-5 py-4 dark:border-white/10">
          <h2 className="font-black text-navy-950 dark:text-white">Akkauntlar</h2>
          <span className="rounded-full bg-cyan-500/10 px-3 py-1 text-xs font-black text-cyan-700 dark:text-cyan-300">{total} ta</span>
        </div>
        {loading ? <div className="p-8 text-center text-sm text-ink-500 dark:text-slate-400">Yuklanmoqda…</div> : items.length === 0 ? (
          <div className="p-8 text-center text-sm text-ink-500 dark:text-slate-400">Hozircha Speaking App akkaunti yo‘q.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-surface-soft text-xs uppercase tracking-wide text-ink-500 dark:bg-white/[0.04] dark:text-slate-400">
                <tr><th className="px-5 py-3">Foydalanuvchi</th><th className="px-5 py-3">Login</th><th className="px-5 py-3">Fanlar</th><th className="px-5 py-3">Holat</th><th className="px-5 py-3">Ochilgan</th></tr>
              </thead>
              <tbody className="divide-y divide-line dark:divide-white/10">
                {items.map((item) => (
                  <tr key={item.id} className="text-ink-700 dark:text-slate-200">
                    <td className="px-5 py-4 font-black text-navy-950 dark:text-white">{item.full_name || "Speaking learner"}</td>
                    <td className="px-5 py-4 font-mono text-xs">{item.login_id}</td>
                    <td className="px-5 py-4">{item.subjects?.join(", ") || "English, Russian"}</td>
                    <td className="px-5 py-4"><span className={`rounded-full px-2.5 py-1 text-xs font-black ${item.speaking_account_state === "inactive" ? "bg-slate-500/10 text-slate-700 dark:text-slate-300" : item.blocked || !item.access_enabled ? "bg-red-500/10 text-red-700 dark:text-red-300" : "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"}`}>{item.speaking_account_state === "inactive" ? "O‘chirilgan (saqlangan)" : item.blocked || !item.access_enabled ? "Cheklangan" : "Faol"}</span></td>
                    <td className="px-5 py-4 whitespace-nowrap text-xs">{item.created_at ? new Date(item.created_at).toLocaleDateString("uz-UZ") : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
