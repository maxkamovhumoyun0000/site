"use client";

import React, { useState, useEffect } from "react";

type NotificationItem = {
  id: number;
  title: string;
  body: string;
  target_part?: number;
  target_topic_id?: number;
  recipient_count: number;
  status: string;
  created_at: string;
};

interface AdminSpeakingNotificationsProps {
  apiFetch: (path: string, options?: { method?: string; body?: any }) => Promise<any>;
}

export function AdminSpeakingNotifications({ apiFetch }: AdminSpeakingNotificationsProps) {
  const [title, setTitle] = useState<string>("");
  const [body, setBody] = useState<string>("");
  const [targetPart, setTargetPart] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [historyLoading, setHistoryLoading] = useState<boolean>(true);
  const [history, setHistory] = useState<NotificationItem[]>([]);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    loadHistory();
  }, []);

  async function loadHistory() {
    setHistoryLoading(true);
    try {
      const res = await apiFetch("/staff/speaking/notifications", { method: "GET" });
      if (res && res.items) {
        setHistory(res.items);
      }
    } catch (e: any) {
      console.error("Bildirishnomalar tarixini yuklashda xatolik:", e);
    } finally {
      setHistoryLoading(false);
    }
  }

  async function handleSend() {
    if (!title.trim() || !body.trim()) {
      alert("Iltimos, bildirishnoma sarlavhasi va matnini to'liq kiriting.");
      return;
    }

    if (!confirm("Haqiqatan ham barcha Speaking ilovasi foydalanuvchilariga bu xabarni yubormoqchimisiz?")) {
      return;
    }

    setLoading(true);
    setSuccessMessage(null);
    try {
      const res = await apiFetch("/staff/speaking/notifications/send", {
        method: "POST",
        body: {
          title: title.trim(),
          body: body.trim(),
          target_part: targetPart || undefined,
        },
      });

      if (res && res.success) {
        setSuccessMessage(res.message || "Bildirishnoma muvaffaqiyatli yuborildi!");
        setTitle("");
        setBody("");
        setTargetPart(null);
        await loadHistory();
      }
    } catch (e: any) {
      alert("Bildirishnoma yuborishda xatolik: " + (e?.message || String(e)));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 pb-20 animate-fade-in max-w-6xl mx-auto">
      {/* ─── HEADER BAR ─── */}
      <div className="bg-navy-900/60 dark:bg-[#0c143b]/80 backdrop-blur-md p-6 rounded-2xl border border-navy-700/40 shadow-xl">
        <div className="flex items-center gap-2 mb-1">
          <span className="px-2.5 py-0.5 text-xs font-black uppercase tracking-wider rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30">
            FCM Cloud Messaging
          </span>
          <span className="text-xs text-ink-400">· Real-time Push Service</span>
        </div>
        <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
          Speaking App Notification
        </h1>
        <p className="text-sm text-ink-300 mt-1">
          Diamond IELTS Speaking ilovasi o'rnatilgan barcha qurilmalarga (Android & iOS) tezkor tizimli bildirishnomalar yuborish va tarixni kuzatish.
        </p>
      </div>

      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm flex items-center justify-between">
          <span>✅ {successMessage}</span>
          <button type="button" onClick={() => setSuccessMessage(null)} className="text-emerald-400 hover:text-white">
            ✕
          </button>
        </div>
      )}

      {/* ─── TWO COLUMN COMPOSER & PREVIEW ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Composer Form */}
        <div className="lg:col-span-7 bg-navy-900/60 dark:bg-[#0c143b]/70 border border-navy-700/50 rounded-2xl p-6 shadow-xl space-y-5">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <span>📝</span>
            <span>Yangi Bildirishnoma Yozish</span>
          </h2>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-ink-300 mb-1.5">
              Bildirishnoma Sarlavhasi (Title):
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Masalan: 🎯 Yangi 2026 Predicted Part 2 Mavzulari Qo'shildi!"
              className="w-full px-4 py-3 rounded-xl bg-navy-950 border border-navy-700 text-white placeholder-ink-500 text-sm focus:border-cyan-400 outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-ink-300 mb-1.5">
              Xabar Matni (Message Body):
            </label>
            <textarea
              rows={4}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Masalan: Imtihonda eng ko'p tushishi kutilayotgan yangi mavzular va Band 8.5-9.0 namuna javoblari ilovaga yuklandi. Hoziroq mashq qiling!"
              className="w-full px-4 py-3 rounded-xl bg-navy-950 border border-navy-700 text-white placeholder-ink-500 text-sm focus:border-cyan-400 outline-none resize-none"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-ink-300 mb-1.5">
              Foydalanuvchini yo'naltirish (Ixtiyoriy Deep-link):
            </label>
            <select
              value={targetPart || ""}
              onChange={(e) => setTargetPart(e.target.value ? Number(e.target.value) : null)}
              className="w-full px-4 py-3 rounded-xl bg-navy-950 border border-navy-700 text-white text-sm focus:border-cyan-400 outline-none"
            >
              <option value="">Umumiy ilovani ochish (Bosh sahifa)</option>
              <option value="1">Part 1 (Introduction & Interview)</option>
              <option value="2">Part 2 (Cue Card / Long Turn)</option>
              <option value="3">Part 3 (Two-way Discussion)</option>
            </select>
          </div>

          <div className="pt-2">
            <button
              type="button"
              onClick={handleSend}
              disabled={loading}
              className="w-full py-3.5 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-extrabold text-sm shadow-xl shadow-blue-600/30 active:scale-[0.98] transition-all flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Bildirishnoma yuborilmoqda...</span>
                </>
              ) : (
                <>
                  <span>📲</span>
                  <span>Bildirishnomani Barcha Qurilmalarga Yuborish (Push)</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Right: Phone Notification Live Preview */}
        <div className="lg:col-span-5 bg-navy-900/40 dark:bg-[#0c143b]/50 border border-navy-700/40 rounded-2xl p-6 shadow-xl flex flex-col items-center justify-center">
          <span className="text-xs font-bold uppercase tracking-wider text-ink-400 mb-4 block">
            Jonli Smartfon Ko'rinishi (Live Preview)
          </span>

          <div className="w-full max-w-[320px] rounded-[36px] bg-slate-950 border-[6px] border-slate-800 p-4 shadow-2xl relative">
            {/* Dynamic island / notch */}
            <div className="w-24 h-4 bg-slate-800 rounded-full mx-auto mb-4" />

            {/* Notification Card */}
            <div className="bg-slate-900/90 border border-slate-700/60 rounded-2xl p-3 shadow-lg backdrop-blur-md space-y-1.5 transition-all">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-md bg-blue-600 text-[10px] text-white flex items-center justify-center font-black">
                    💎
                  </div>
                  <span className="text-[11px] font-bold text-slate-200">
                    DIAMOND IELTS SPEAKING
                  </span>
                </div>
                <span className="text-[10px] text-slate-400">hozir</span>
              </div>

              <h4 className="text-xs font-bold text-white leading-tight">
                {title.trim() || "Bildirishnoma sarlavhasi bu yerda chiqadi"}
              </h4>

              <p className="text-[11px] text-slate-300 leading-snug line-clamp-3">
                {body.trim() || "Xabar matni smartfon qulf ekranida va yuqori panelida shunday ko'rinadi..."}
              </p>
            </div>

            <div className="mt-8 text-center">
              <span className="text-[10px] text-slate-500">
                {targetPart ? `Ochilganda: Part ${targetPart} bo'limiga o'tadi` : "Ochilganda: Bosh sahifaga o'tadi"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ─── NOTIFICATION HISTORY TABLE ─── */}
      <div className="bg-navy-900/60 dark:bg-[#0c143b]/70 border border-navy-700/50 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <span>📜</span>
            <span>Yuborilgan Bildirishnomalar Tarixi</span>
          </h2>
          <button
            type="button"
            onClick={loadHistory}
            className="text-xs text-cyan-400 hover:text-cyan-300 font-bold"
          >
            Yangilash
          </button>
        </div>

        {historyLoading ? (
          <div className="py-8 text-center text-ink-400 text-xs">Tarix yuklanmoqda...</div>
        ) : history.length === 0 ? (
          <div className="py-8 text-center text-ink-400 text-xs">
            Hozircha yuborilgan bildirishnomalar mavjud emas.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-navy-800 text-ink-400 uppercase text-[10px] tracking-wider">
                  <th className="py-3 px-3">Sana & Vaqt</th>
                  <th className="py-3 px-3">Sarlavha</th>
                  <th className="py-3 px-3">Matn</th>
                  <th className="py-3 px-3">Nishon</th>
                  <th className="py-3 px-3">Qurilmalar</th>
                  <th className="py-3 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-800/60">
                {history.map((item) => (
                  <tr key={item.id} className="hover:bg-navy-800/30 transition-colors">
                    <td className="py-3 px-3 text-ink-400 whitespace-nowrap">
                      {item.created_at ? item.created_at.replace("T", " ").slice(0, 16) : "—"}
                    </td>
                    <td className="py-3 px-3 font-bold text-white max-w-[200px] truncate">
                      {item.title}
                    </td>
                    <td className="py-3 px-3 text-ink-300 max-w-[320px] truncate">
                      {item.body}
                    </td>
                    <td className="py-3 px-3 text-cyan-400 whitespace-nowrap">
                      {item.target_part ? `Part ${item.target_part}` : "Bosh sahifa"}
                    </td>
                    <td className="py-3 px-3 font-bold text-white whitespace-nowrap">
                      {item.recipient_count} ta
                    </td>
                    <td className="py-3 px-3">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-black uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                        {item.status || "SENT"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
