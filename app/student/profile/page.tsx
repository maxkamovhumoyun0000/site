"use client";
import { useEffect, useState } from "react";
import { BadgeChip } from "@/app/ui/badge-chip";

const TABS = [
  { id: "general", label: "👤 Umumiy" },
  { id: "certificates", label: "🎓 Sertifikatlarim" },
  { id: "badges", label: "🎖 Badge'larim" },
  { id: "security", label: "🔒 Xavfsizlik" },
];

export default function StudentProfilePage() {
  const [tab, setTab] = useState("general");
  const [profile, setProfile] = useState<any>(null);
  const [certificates, setCertificates] = useState<any[]>([]);
  const [badges, setBadges] = useState<any[]>([]);
  const [selectedBadge, setSelectedBadge] = useState<string | null>(null);
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  async function loadData() {
    setLoading(true);
    try {
      const [pRes, sRes] = await Promise.all([
        fetch("/api/student/portfolio").then((r) => r.json()).catch(() => ({})),
        fetch("/api/student/sessions").then((r) => r.json()).catch(() => ({ items: [] })),
      ]);
      setProfile(pRes.student || {});
      setCertificates(pRes.certificates || []);
      setBadges(pRes.badges || []);
      setSelectedBadge(pRes.selected_badge || null);
      setSessions(sRes.items || []);
    } finally {
      setLoading(false);
    }
  }

  async function selectBadge(badgeKey: string) {
    const next = selectedBadge === badgeKey ? null : badgeKey;
    setSelectedBadge(next);
    await fetch("/api/student/portfolio/badge", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ badge_key: next }),
    });
  }

  async function terminateSession(id: number) {
    await fetch(`/api/student/sessions/${id}`, { method: "DELETE" });
    setSessions((prev) => prev.filter((s) => s.id !== id));
  }

  useEffect(() => {
    loadData();
  }, []);

  return (
    <main className="min-h-screen p-6 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100">
      <div className="max-w-3xl mx-auto">
        {/* Header with avatar & selected badge */}
        <div className="flex items-center gap-4 p-6 mb-6 bg-gradient-to-r from-blue-500/10 via-purple-500/10 to-pink-500/10 rounded-2xl border border-gray-200 dark:border-gray-800">
          <div className="w-16 h-16 rounded-full bg-blue-600 text-white flex items-center justify-center text-2xl font-bold">
            {profile?.first_name?.[0] || "S"}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold">
                {profile?.first_name || "O'quvchi"} {profile?.last_name || ""}
              </h1>
              {selectedBadge && <BadgeChip badgeTitle={selectedBadge} size="md" />}
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {profile?.phone || profile?.username || "Diamond O'quvchi"}
            </p>
          </div>
        </div>

        {/* Tab switcher */}
        <div className="flex gap-2 mb-6 border-b border-gray-200 dark:border-gray-700 overflow-x-auto pb-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`pb-2.5 px-4 text-sm font-semibold transition border-b-2 whitespace-nowrap -mb-px ${
                tab === t.id
                  ? "border-blue-500 text-blue-600 dark:text-blue-400"
                  : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {loading ? (
          <p className="text-center py-16 text-gray-500">Yuklanmoqda...</p>
        ) : (
          <>
            {/* 1. Umumiy */}
            {tab === "general" && (
              <div className="bg-gray-50 dark:bg-gray-800/60 border border-gray-200 dark:border-gray-700 rounded-2xl p-6 space-y-4">
                <h2 className="text-lg font-bold">Shaxsiy ma'lumotlar</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                  <div className="p-3 bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700">
                    <span className="text-gray-500 dark:text-gray-400 block text-xs">Ism familiya</span>
                    <span className="font-semibold">{profile?.first_name} {profile?.last_name}</span>
                  </div>
                  <div className="p-3 bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700">
                    <span className="text-gray-500 dark:text-gray-400 block text-xs">Telefon</span>
                    <span className="font-semibold">{profile?.phone || "Kiritilmagan"}</span>
                  </div>
                  <div className="p-3 bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700">
                    <span className="text-gray-500 dark:text-gray-400 block text-xs">Tanlangan Badge</span>
                    <span className="font-semibold">{selectedBadge || "Tanlanmagan"}</span>
                  </div>
                  <div className="p-3 bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700">
                    <span className="text-gray-500 dark:text-gray-400 block text-xs">Jami sertifikatlar</span>
                    <span className="font-semibold">{certificates.length} ta</span>
                  </div>
                </div>
              </div>
            )}

            {/* 2. Sertifikatlarim */}
            {tab === "certificates" && (
              <div className="space-y-4">
                {certificates.length === 0 ? (
                  <div className="text-center py-16 bg-gray-50 dark:bg-gray-800/50 rounded-2xl border border-gray-200 dark:border-gray-700">
                    <span className="text-4xl block mb-2">🎓</span>
                    <p className="text-gray-500 dark:text-gray-400">Hozircha sertifikatlar mavjud emas.</p>
                    <p className="text-xs text-gray-400 mt-1">Track yoki kursni yakunlaganingizda yuklab olish va ulashish mumkin bo‘lgan sertifikat beriladi.</p>
                  </div>
                ) : (
                  certificates.map((c) => (
                    <div
                      key={c.id || c.certificate_id}
                      className="p-5 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl flex items-center justify-between shadow-sm"
                    >
                      <div>
                        <h3 className="font-bold text-lg text-gray-900 dark:text-white">{c.course_title || "Kurs yakunlangan"}</h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400">ID: {c.certificate_id} • {c.issued_at?.slice(0, 10)}</p>
                      </div>
                      <div className="flex gap-2">
                        <a
                          href={`/api/student/certificates/${c.certificate_id}/pdf`}
                          target="_blank"
                          rel="noreferrer"
                          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold transition"
                        >
                          📄 PDF
                        </a>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* 3. Badge'larim */}
            {tab === "badges" && (
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                  Badge ustiga bosib, uni ismingiz yonida (Telegram Premium kabi) ko'rsatish uchun tanlang:
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                  {[
                    { key: "streak_7", title: "🔥 7 Kunlik Streak", desc: "Ketma-ket 7 kun dars" },
                    { key: "streak_30", title: "⚡ 30 Kunlik Afsona", desc: "Ketma-ket 30 kun dars" },
                    { key: "arena_champion", title: "🏆 Arena Chempioni", desc: "10 marta arena g'olibi" },
                    { key: "first_test", title: "🎯 Ilk Sinov", desc: "Birinchi test topshirildi" },
                    { key: "perfect_score", title: "💎 100% Natija", desc: "Testda 100 ball" },
                    { key: "study_room_host", title: "👑 Study Room Lideri", desc: "5 ta xona yaratildi" },
                    { key: "bookworm", title: "📖 Kitobxon", desc: "5 ta kitob saqlandi" },
                  ].map((b) => {
                    const isUnlocked = badges.some((item) => (item.badge_key || item) === b.key);
                    const isSelected = selectedBadge === b.key;
                    return (
                      <div
                        key={b.key}
                        onClick={() => isUnlocked && selectBadge(b.key)}
                        className={`p-4 rounded-2xl border-2 transition text-center cursor-pointer ${
                          isSelected
                            ? "border-blue-500 bg-blue-50/50 dark:bg-blue-900/30 shadow-md ring-2 ring-blue-400/50"
                            : isUnlocked
                            ? "border-gray-200 dark:border-gray-700 hover:border-blue-300 bg-white dark:bg-gray-800"
                            : "border-gray-200 dark:border-gray-800 bg-gray-100/50 dark:bg-gray-900 opacity-40 cursor-not-allowed"
                        }`}
                      >
                        <div className="text-3xl mb-2">{b.title.split(" ")[0]}</div>
                        <h4 className="font-bold text-sm mb-1">{b.title.substring(2)}</h4>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">{b.desc}</p>
                        {isSelected ? (
                          <span className="inline-block px-2.5 py-0.5 text-[10px] font-bold bg-blue-600 text-white rounded-full">
                            ✓ Tanlangan
                          </span>
                        ) : isUnlocked ? (
                          <span className="inline-block px-2.5 py-0.5 text-[10px] font-medium bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400 rounded-full">
                            Ochiq
                          </span>
                        ) : (
                          <span className="inline-block px-2.5 py-0.5 text-[10px] font-medium bg-gray-200 dark:bg-gray-800 text-gray-500 rounded-full">
                            Qulflangan
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 4. Xavfsizlik */}
            {tab === "security" && (
              <div className="space-y-4">
                <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-2xl text-sm">
                  🛡️ Hisobingizga ulangan qurilmalar va sessiyalar ro'yxati. Notanish qurilmani ko'rsangiz darhol "Tugatish" tugmasini bosing.
                </div>
                {sessions.length === 0 ? (
                  <p className="text-center py-10 text-gray-500">Faol sessiyalar topilmadi</p>
                ) : (
                  sessions.map((s) => (
                    <div
                      key={s.id}
                      className="p-4 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl flex items-center justify-between"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-lg">{s.platform === "ios" ? "📱" : s.platform === "android" ? "🤖" : "💻"}</span>
                          <p className="font-semibold text-gray-900 dark:text-white text-sm">{s.device_name || "Qurilma"}</p>
                        </div>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          IP: {s.ip_address || "Noma'lum"} • Oxirgi faollik: {s.last_seen?.slice(0, 16) || "Hozir"}
                        </p>
                      </div>
                      <button
                        onClick={() => terminateSession(s.id)}
                        className="px-3 py-1.5 bg-red-100 dark:bg-red-900/30 hover:bg-red-200 text-red-600 rounded-xl text-xs font-semibold transition"
                      >
                        Tugatish
                      </button>
                    </div>
                  ))
                )}
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
