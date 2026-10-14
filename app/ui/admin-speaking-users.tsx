"use client";

import { useCallback, useEffect, useState } from "react";

type SpeakingUser = {
  id: number;
  full_name: string;
  first_name?: string;
  last_name?: string;
  login_id: string;
  email?: string;
  phone?: string;
  role: string;
  subjects: string[];
  blocked: boolean;
  access_enabled: boolean;
  speaking_account_state?: "active" | "inactive";
  created_at?: string | null;
  last_login_at?: string | null;
};

type AdminSpeakingUsersProps = {
  apiFetch: (path: string, options?: { method?: string; body?: unknown; timeoutMs?: number }) => Promise<unknown>;
};

export function AdminSpeakingUsers({ apiFetch }: AdminSpeakingUsersProps) {
  const [items, setItems] = useState<SpeakingUser[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Modals state
  const [editingUser, setEditingUser] = useState<SpeakingUser | null>(null);
  const [passwordUser, setPasswordUser] = useState<SpeakingUser | null>(null);

  // Edit form state
  const [editFirstName, setEditFirstName] = useState("");
  const [editLastName, setEditLastName] = useState("");
  const [editLoginId, setEditLoginId] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editSubjects, setEditSubjects] = useState<string[]>([]);
  const [editBlocked, setEditBlocked] = useState(false);
  const [editAccessEnabled, setEditAccessEnabled] = useState(true);
  const [savingEdit, setSavingEdit] = useState(false);

  // Password reset state
  const [newPassword, setNewPassword] = useState("");
  const [savingPassword, setSavingPassword] = useState(false);

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

  function openEditModal(user: SpeakingUser) {
    setEditingUser(user);
    setEditFirstName(user.first_name || user.full_name?.split(" ")[0] || "");
    setEditLastName(user.last_name || user.full_name?.split(" ").slice(1).join(" ") || "");
    setEditLoginId(user.login_id || "");
    setEditEmail(user.email || "");
    setEditSubjects(Array.isArray(user.subjects) ? [...user.subjects] : ["English"]);
    setEditBlocked(Boolean(user.blocked));
    setEditAccessEnabled(user.access_enabled !== false);
  }

  async function handleSaveEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editingUser) return;
    setSavingEdit(true);
    setError("");
    try {
      await apiFetch(`/admin/speaking-users/${editingUser.id}`, {
        method: "PATCH",
        body: {
          first_name: editFirstName.trim(),
          last_name: editLastName.trim(),
          login_id: editLoginId.trim(),
          email: editEmail.trim(),
          subjects: editSubjects.length ? editSubjects : ["English"],
          blocked: editBlocked,
          access_enabled: editAccessEnabled,
        },
      });
      setSuccessMsg(`Foydalanuvchi (${editLoginId}) ma’lumotlari muvaffaqiyatli saqlandi.`);
      setTimeout(() => setSuccessMsg(""), 4000);
      setEditingUser(null);
      void load(query);
    } catch (err: any) {
      setError(err?.message || "O‘zgarishlarni saqlab bo‘lmadi.");
    } finally {
      setSavingEdit(false);
    }
  }

  function openPasswordModal(user: SpeakingUser) {
    setPasswordUser(user);
    setNewPassword("");
  }

  function generateRandomPassword() {
    const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789";
    let pwd = "";
    for (let i = 0; i < 10; i++) {
      pwd += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    setNewPassword(pwd);
  }

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();
    if (!passwordUser || !newPassword.trim()) return;
    setSavingPassword(true);
    setError("");
    try {
      await apiFetch(`/admin/speaking-users/${passwordUser.id}/reset-password`, {
        method: "POST",
        body: { new_password: newPassword.trim() },
      });
      setSuccessMsg(`Foydalanuvchi (${passwordUser.login_id}) paroli muvaffaqiyatli yangilandi.`);
      setTimeout(() => setSuccessMsg(""), 4000);
      setPasswordUser(null);
    } catch (err: any) {
      setError(err?.message || "Parolni yangilab bo‘lmadi.");
    } finally {
      setSavingPassword(false);
    }
  }

  function toggleSubject(sub: string) {
    setEditSubjects((prev) =>
      prev.includes(sub) ? prev.filter((s) => s !== sub) : [...prev, sub]
    );
  }

  return (
    <section className="mx-auto w-full max-w-7xl space-y-5 px-3 py-5 pb-24 sm:px-6">
      {/* Header Banner */}
      <header className="rounded-3xl border border-cyan-400/25 bg-gradient-to-br from-cyan-500/10 via-white to-blue-500/10 p-6 shadow-sm dark:from-cyan-400/10 dark:via-navy-950 dark:to-blue-500/10">
        <span className="inline-flex rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-black uppercase tracking-wide text-cyan-700 dark:text-cyan-300">
          Diamond Speaking
        </span>
        <h1 className="mt-3 text-2xl font-black tracking-tight text-navy-950 dark:text-white">
          Speaking App foydalanuvchilari
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-600 dark:text-slate-300">
          Ushbu sahifada Speaking ilovasida ro‘yxatdan o‘tgan barcha o‘quvchilar ro‘yxati, ularning tanlagan fanlari,
          Login ID va parollarini boshqarish, tahrirlash hamda holatini kuzatish mumkin.
        </p>
      </header>

      {/* Notifications */}
      {successMsg ? (
        <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm font-bold text-emerald-700 dark:text-emerald-300">
          ✅ {successMsg}
        </div>
      ) : null}

      {error ? (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm font-semibold text-red-700 dark:text-red-300">
          ⚠️ {error}
        </div>
      ) : null}

      {/* Search and Filters */}
      <form onSubmit={submitSearch} className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4 shadow-sm sm:flex-row dark:border-white/10 dark:bg-navy-950">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Ism, login yoki email bo‘yicha qidirish"
          className="min-w-0 flex-1 rounded-xl border border-line bg-white px-4 py-3 text-sm font-medium text-navy-950 outline-none placeholder:text-ink-400 focus:border-cyan-500 dark:border-white/15 dark:bg-white/5 dark:text-white"
        />
        <button
          type="submit"
          className="rounded-xl bg-cyan-600 px-5 py-3 text-sm font-black text-white transition hover:bg-cyan-500"
          disabled={loading}
        >
          Qidirish
        </button>
        <button
          type="button"
          onClick={() => void load(query)}
          className="rounded-xl border border-line px-5 py-3 text-sm font-black text-ink-700 transition hover:bg-surface-soft dark:border-white/15 dark:text-slate-200 dark:hover:bg-white/10"
          disabled={loading}
        >
          Yangilash
        </button>
      </form>

      {/* Users Table */}
      <div className="overflow-hidden rounded-2xl border border-line bg-surface shadow-sm dark:border-white/10 dark:bg-navy-950">
        <div className="flex items-center justify-between border-b border-line px-5 py-4 dark:border-white/10">
          <h2 className="font-black text-navy-950 dark:text-white">Foydalanuvchilar ro‘yxati</h2>
          <span className="rounded-full bg-cyan-500/10 px-3 py-1 text-xs font-black text-cyan-700 dark:text-cyan-300">
            {total} ta o‘quvchi
          </span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-sm font-medium text-ink-500 dark:text-slate-400">Yuklanmoqda…</div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center text-sm text-ink-500 dark:text-slate-400">
            Hozircha Speaking App akkaunti topilmadi.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-surface-soft text-xs uppercase tracking-wide text-ink-500 dark:bg-white/[0.04] dark:text-slate-400">
                <tr>
                  <th className="px-5 py-3">O‘quvchi</th>
                  <th className="px-5 py-3">Login ID</th>
                  <th className="px-5 py-3">Email / Aloqa</th>
                  <th className="px-5 py-3">Fanlar</th>
                  <th className="px-5 py-3">Holat</th>
                  <th className="px-5 py-3">Ro‘yxatdan o‘tgan</th>
                  <th className="px-5 py-3 text-right">Amallar</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line dark:divide-white/10">
                {items.map((item) => {
                  const subs = item.subjects || ["English"];
                  const isBlocked = item.blocked || !item.access_enabled;
                  const isDeleted = item.speaking_account_state === "inactive";

                  return (
                    <tr key={item.id} className="text-ink-700 transition hover:bg-surface-soft/60 dark:text-slate-200 dark:hover:bg-white/[0.02]">
                      <td className="px-5 py-4">
                        <div className="font-black text-navy-950 dark:text-white">
                          {item.full_name || "Speaking o‘quvchi"}
                        </div>
                        <div className="text-xs text-ink-500 dark:text-slate-400">ID: #{item.id}</div>
                      </td>
                      <td className="px-5 py-4">
                        <span className="rounded-lg bg-blue-500/10 px-2.5 py-1 font-mono text-xs font-bold text-blue-700 dark:bg-blue-400/10 dark:text-blue-300">
                          {item.login_id}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-xs">
                        {item.email ? <div className="font-medium text-navy-950 dark:text-slate-200">{item.email}</div> : null}
                        {item.phone ? <div className="text-ink-500 dark:text-slate-400">{item.phone}</div> : null}
                        {!item.email && !item.phone ? <span className="text-slate-400">—</span> : null}
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex flex-wrap gap-1">
                          {subs.map((s) => (
                            <span
                              key={s}
                              className={`rounded-md px-2 py-0.5 text-xs font-bold ${
                                s.toLowerCase().includes("rus")
                                  ? "bg-cyan-500/10 text-cyan-700 dark:bg-cyan-400/15 dark:text-cyan-300"
                                  : "bg-blue-500/10 text-blue-700 dark:bg-blue-400/15 dark:text-blue-300"
                              }`}
                            >
                              {s.toLowerCase().includes("rus") ? "🇷🇺 Rus tili" : "🇬🇧 IELTS"}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-black ${
                            isDeleted
                              ? "bg-slate-500/10 text-slate-700 dark:text-slate-300"
                              : isBlocked
                              ? "bg-red-500/10 text-red-700 dark:text-red-300"
                              : "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                          }`}
                        >
                          <span className={`h-1.5 w-1.5 rounded-full ${isDeleted ? "bg-slate-500" : isBlocked ? "bg-red-500" : "bg-emerald-500"}`} />
                          {isDeleted ? "O‘chirilgan" : isBlocked ? "Cheklangan" : "Faol"}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-5 py-4 text-xs text-ink-500 dark:text-slate-400">
                        {item.created_at ? new Date(item.created_at).toLocaleDateString("uz-UZ") : "—"}
                      </td>
                      <td className="whitespace-nowrap px-5 py-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() => openEditModal(item)}
                            className="rounded-lg border border-line px-3 py-1.5 text-xs font-bold text-navy-950 transition hover:bg-surface-soft dark:border-white/15 dark:text-white dark:hover:bg-white/10"
                            title="Tahrirlash va ko‘rish"
                          >
                            Tahrirlash
                          </button>
                          <button
                            type="button"
                            onClick={() => openPasswordModal(item)}
                            className="rounded-lg bg-blue-600/10 px-3 py-1.5 text-xs font-bold text-blue-700 transition hover:bg-blue-600/20 dark:bg-blue-400/15 dark:text-blue-300 dark:hover:bg-blue-400/25"
                            title="Parolni yangilash"
                          >
                            Parol
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Edit User Modal */}
      {editingUser ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-3xl border border-line bg-surface p-6 shadow-2xl dark:border-white/15 dark:bg-navy-950">
            <div className="flex items-center justify-between border-b border-line pb-4 dark:border-white/10">
              <div>
                <h3 className="text-lg font-black text-navy-950 dark:text-white">O‘quvchi ma’lumotlarini tahrirlash</h3>
                <p className="text-xs text-ink-500 dark:text-slate-400">ID: #{editingUser.id}</p>
              </div>
              <button
                type="button"
                onClick={() => setEditingUser(null)}
                className="rounded-xl p-1.5 text-ink-500 hover:bg-surface-soft dark:text-slate-400 dark:hover:bg-white/10"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveEdit} className="mt-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-ink-600 dark:text-slate-300">Ism</label>
                  <input
                    value={editFirstName}
                    onChange={(e) => setEditFirstName(e.target.value)}
                    required
                    className="mt-1 w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm font-medium text-navy-950 outline-none focus:border-cyan-500 dark:border-white/15 dark:bg-white/5 dark:text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-ink-600 dark:text-slate-300">Familiya</label>
                  <input
                    value={editLastName}
                    onChange={(e) => setEditLastName(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm font-medium text-navy-950 outline-none focus:border-cyan-500 dark:border-white/15 dark:bg-white/5 dark:text-white"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-ink-600 dark:text-slate-300">Login ID</label>
                <input
                  value={editLoginId}
                  onChange={(e) => setEditLoginId(e.target.value)}
                  required
                  className="mt-1 w-full rounded-xl border border-line bg-white px-3 py-2.5 font-mono text-sm font-medium text-navy-950 outline-none focus:border-cyan-500 dark:border-white/15 dark:bg-white/5 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-ink-600 dark:text-slate-300">Email</label>
                <input
                  type="email"
                  value={editEmail}
                  onChange={(e) => setEditEmail(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm font-medium text-navy-950 outline-none focus:border-cyan-500 dark:border-white/15 dark:bg-white/5 dark:text-white"
                />
              </div>

              {/* Fanlar */}
              <div>
                <label className="block text-xs font-bold text-ink-600 dark:text-slate-300">O‘rganiladigan fanlar</label>
                <div className="mt-2 flex gap-3">
                  <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-line px-3 py-2 text-xs font-bold dark:border-white/15">
                    <input
                      type="checkbox"
                      checked={editSubjects.includes("English")}
                      onChange={() => toggleSubject("English")}
                      className="rounded"
                    />
                    🇬🇧 IELTS (Ingliz tili)
                  </label>
                  <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-line px-3 py-2 text-xs font-bold dark:border-white/15">
                    <input
                      type="checkbox"
                      checked={editSubjects.includes("Russian")}
                      onChange={() => toggleSubject("Russian")}
                      className="rounded"
                    />
                    🇷🇺 Rus tili
                  </label>
                </div>
              </div>

              {/* Holatlar */}
              <div className="rounded-xl border border-line p-3 dark:border-white/15">
                <label className="flex cursor-pointer items-center justify-between text-xs font-bold text-navy-950 dark:text-white">
                  <span>Akkaunt bloklangan</span>
                  <input
                    type="checkbox"
                    checked={editBlocked}
                    onChange={(e) => setEditBlocked(e.target.checked)}
                    className="h-4 w-4 rounded"
                  />
                </label>
                <div className="my-2 border-t border-line dark:border-white/10" />
                <label className="flex cursor-pointer items-center justify-between text-xs font-bold text-navy-950 dark:text-white">
                  <span>Kirish ruxsati (Access Enabled)</span>
                  <input
                    type="checkbox"
                    checked={editAccessEnabled}
                    onChange={(e) => setEditAccessEnabled(e.target.checked)}
                    className="h-4 w-4 rounded"
                  />
                </label>
              </div>

              <div className="mt-6 flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingUser(null)}
                  className="rounded-xl border border-line px-4 py-2.5 text-xs font-bold text-ink-700 transition hover:bg-surface-soft dark:border-white/15 dark:text-slate-300"
                >
                  Bekor qilish
                </button>
                <button
                  type="submit"
                  disabled={savingEdit}
                  className="rounded-xl bg-cyan-600 px-5 py-2.5 text-xs font-black text-white transition hover:bg-cyan-500 disabled:opacity-50"
                >
                  {savingEdit ? "Saqlanmoqda…" : "Saqlash"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {/* Reset Password Modal */}
      {passwordUser ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-3xl border border-line bg-surface p-6 shadow-2xl dark:border-white/15 dark:bg-navy-950">
            <div className="flex items-center justify-between border-b border-line pb-4 dark:border-white/10">
              <div>
                <h3 className="text-lg font-black text-navy-950 dark:text-white">Parolni yangilash</h3>
                <p className="text-xs text-ink-500 dark:text-slate-400">Login: {passwordUser.login_id}</p>
              </div>
              <button
                type="button"
                onClick={() => setPasswordUser(null)}
                className="rounded-xl p-1.5 text-ink-500 hover:bg-surface-soft dark:text-slate-400 dark:hover:bg-white/10"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleResetPassword} className="mt-5 space-y-4">
              <div>
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-bold text-ink-600 dark:text-slate-300">Yangi parol</label>
                  <button
                    type="button"
                    onClick={generateRandomPassword}
                    className="text-xs font-bold text-cyan-600 hover:underline dark:text-cyan-400"
                  >
                    🎲 Tasodifiy parol
                  </button>
                </div>
                <input
                  type="text"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Kamida 6 belgi"
                  required
                  className="mt-1 w-full rounded-xl border border-line bg-white px-3 py-2.5 font-mono text-sm font-medium text-navy-950 outline-none focus:border-cyan-500 dark:border-white/15 dark:bg-white/5 dark:text-white"
                />
              </div>

              <p className="text-xs text-ink-500 dark:text-slate-400">
                Parol yangilanganda foydalanuvchining barcha eski qurilmadagi sessiyalari bekor qilinadi.
              </p>

              <div className="mt-6 flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setPasswordUser(null)}
                  className="rounded-xl border border-line px-4 py-2.5 text-xs font-bold text-ink-700 transition hover:bg-surface-soft dark:border-white/15 dark:text-slate-300"
                >
                  Bekor qilish
                </button>
                <button
                  type="submit"
                  disabled={savingPassword || !newPassword.trim()}
                  className="rounded-xl bg-blue-600 px-5 py-2.5 text-xs font-black text-white transition hover:bg-blue-500 disabled:opacity-50"
                >
                  {savingPassword ? "Saqlanmoqda…" : "Parolni o‘rnatish"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </section>
  );
}
