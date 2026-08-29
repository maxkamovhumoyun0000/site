"use client";

import React, { useState, useEffect } from "react";
import {
  Smartphone,
  CheckCircle2,
  XCircle,
  Clock,
  Send,
  RefreshCw,
  LogOut,
  Sliders,
  Bell,
  Sparkles,
  AlertTriangle,
  Calendar,
  Gift,
  CreditCard,
  MessageSquare,
  UserPlus,
  Zap,
  Info,
  ShieldCheck,
  History,
} from "lucide-react";

interface UserbotSettings {
  is_enabled: boolean;
  phone_number: string | null;
  account_name: string | null;
  is_authenticated: boolean;
  notify_absent: boolean;
  notify_late: boolean;
  notify_homework: boolean;
  notify_achievements: boolean;
  notify_payment_reminder: boolean;
  notify_overdue: boolean;
  notify_payment_receipt: boolean;
  notify_welcome: boolean;
  notify_lesson_cancelled: boolean;
  templates: Record<string, string>;
}

interface UserbotLog {
  id: number;
  recipient_phone: string;
  student_name: string;
  event_type: string;
  message_text: string;
  status: string;
  error_message?: string;
  created_at: string;
}

const TEMPLATE_META: Record<
  string,
  { label: string; icon: any; vars: string[]; defaultDesc: string }
> = {
  attendance_absent: {
    label: "Darsga kelmaganlik",
    icon: AlertTriangle,
    vars: ["{student_name}", "{group_name}", "{course_title}"],
    defaultDesc: "O'qituvchi 'bormadi' deb belgilaganda otasiga/onasiga yuboriladi.",
  },
  attendance_late: {
    label: "Darsga kechikib kelish (5 daqiqadan keyin)",
    icon: Clock,
    vars: ["{student_name}", "{group_name}"],
    defaultDesc: "5 daqiqadan keyin holat 'keldiga' o'zgartirilsa yuboriladi.",
  },
  lesson_cancelled: {
    label: "Dars qoldirilishi / Bayram e'loni",
    icon: Calendar,
    vars: ["{group_name}", "{reason}", "{date}"],
    defaultDesc: "Dars bekor qilinganda yoki admin bayram belgilaganda yuboriladi.",
  },
  homework_alert: {
    label: "Bajarilmagan vazifa / Past baho",
    icon: MessageSquare,
    vars: ["{student_name}", "{group_name}", "{reason}", "{score}"],
    defaultDesc: "Vazifa deadline o'tganda yoki o'qituvchi bajarmadi deya belgilasa.",
  },
  achievement_notice: {
    label: "Reyting & Yutuqlar (1-o'rin / Do'kon)",
    icon: Gift,
    vars: ["{student_name}", "{reason}", "{group_name}"],
    defaultDesc: "O'quvchi guruhda 1-o'rinni egallaganda yoki sovg'a xarid qilganda.",
  },
  payment_reminder: {
    label: "To'lov eslatmasi (3 kun oldin)",
    icon: Bell,
    vars: ["{student_name}", "{date}", "{amount}"],
    defaultDesc: "Oylik to'lov muddatiga 3 kun qolganda yuboriladi.",
  },
  overdue_alert: {
    label: "Qarzdorlik eslatmasi (Muddati o'tganda)",
    icon: CreditCard,
    vars: ["{student_name}", "{amount}"],
    defaultDesc: "To'lov muddati o'tganda avtomatik yuboriladi.",
  },
  payment_receipt: {
    label: "To'lov qabul qilindi (Chek)",
    icon: ShieldCheck,
    vars: ["{student_name}", "{amount}", "{date}"],
    defaultDesc: "Admin to'lovni kiritishi bilan chek va minnatdorchilik yuboriladi.",
  },
  welcome_message: {
    label: "Yangi o'quvchi xush kelibsiz xabari",
    icon: UserPlus,
    vars: ["{student_name}", "{group_name}", "{schedule}", "{start_time}", "{end_time}"],
    defaultDesc: "O'quvchi guruhga qo'shilganda dars jadvali va manzillar bilan yuboriladi.",
  },
};

export default function AdminUserbot() {
  const [settings, setSettings] = useState<UserbotSettings | null>(null);
  const [logs, setLogs] = useState<UserbotLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<"modules" | "logs">("modules");

  // Login Modal state
  const [loginModalOpen, setLoginModalOpen] = useState(false);
  const [loginStep, setLoginStep] = useState<"phone" | "code">("phone");
  const [phoneInput, setPhoneInput] = useState("");
  const [codeInput, setCodeInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");
  const [phoneCodeHash, setPhoneCodeHash] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");

  // Test Message Modal state
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [testPhone, setTestPhone] = useState("");
  const [testMessage, setTestMessage] = useState("");
  const [testSending, setTestSending] = useState(false);
  const [testStatus, setTestStatus] = useState("");

  const getHeaders = () => {
    const token = localStorage.getItem("token") || "";
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    };
  };

  const fetchSettings = async () => {
    try {
      const res = await fetch("/admin/userbot/settings", { headers: getHeaders() });
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
      }
    } catch (e) {
      console.error("Failed to fetch userbot settings", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchLogs = async () => {
    try {
      const res = await fetch("/admin/userbot/logs?limit=50", { headers: getHeaders() });
      if (res.ok) {
        const data = await res.json();
        setLogs(data.logs || []);
      }
    } catch (e) {
      console.error("Failed to fetch userbot logs", e);
    }
  };

  useEffect(() => {
    fetchSettings();
    fetchLogs();
  }, []);

  const handleToggle = (key: keyof UserbotSettings) => {
    if (!settings) return;
    setSettings({
      ...settings,
      [key]: !settings[key],
    });
  };

  const handleTemplateChange = (key: string, value: string) => {
    if (!settings) return;
    setSettings({
      ...settings,
      templates: {
        ...settings.templates,
        [key]: value,
      },
    });
  };

  const handleSaveSettings = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      const res = await fetch("/admin/userbot/settings", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify(settings),
      });
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
        alert("Sozlamalar va shablonlar muvaffaqiyatli saqlandi!");
      } else {
        alert("Xatolik yuz berdi");
      }
    } catch (e) {
      console.error(e);
      alert("Saqlashda xatolik");
    } finally {
      setSaving(false);
    }
  };

  const handleSendCode = async () => {
    if (!phoneInput.trim()) {
      setLoginError("Telefon raqamini kiriting (+998...)");
      return;
    }
    setLoginLoading(true);
    setLoginError("");
    try {
      const res = await fetch("/admin/userbot/send-code", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ phone_number: phoneInput.trim() }),
      });
      const data = await res.json();
      if (res.ok) {
        setPhoneCodeHash(data.phone_code_hash);
        setLoginStep("code");
      } else {
        setLoginError(data.detail || "SMS kod yuborishda xatolik");
      }
    } catch (e: any) {
      setLoginError(e.message || "Ulanish xatosi");
    } finally {
      setLoginLoading(false);
    }
  };

  const handleVerifyCode = async () => {
    if (!codeInput.trim()) {
      setLoginError("Telegram SMS kodini kiriting");
      return;
    }
    setLoginLoading(true);
    setLoginError("");
    try {
      const res = await fetch("/admin/userbot/verify-code", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          phone_number: phoneInput.trim(),
          phone_code_hash: phoneCodeHash,
          phone_code: codeInput.trim(),
          password: passwordInput.trim() || undefined,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setLoginModalOpen(false);
        fetchSettings();
        alert("Telegram Userbot akkaunti muvaffaqiyatli ulandi! ✅");
      } else {
        setLoginError(data.detail || "Kodni tasdiqlashda xatolik");
      }
    } catch (e: any) {
      setLoginError(e.message || "Xatolik yuz berdi");
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = async () => {
    if (!confirm("Haqiqatan ham Userbot akkauntini uzmoqchimisiz?")) return;
    try {
      const res = await fetch("/admin/userbot/logout", {
        method: "POST",
        headers: getHeaders(),
      });
      if (res.ok) {
        fetchSettings();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSendTest = async () => {
    if (!testPhone.trim() || !testMessage.trim()) return;
    setTestSending(true);
    setTestStatus("");
    try {
      const res = await fetch("/admin/userbot/test-send", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          phone_number: testPhone.trim(),
          message: testMessage.trim(),
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setTestStatus("✅ Xabar muvaffaqiyatli navbatga qo'shildi!");
        setTimeout(() => {
          setTestModalOpen(false);
          fetchLogs();
        }, 1500);
      } else {
        setTestStatus(`❌ Xatolik: ${data.detail}`);
      }
    } catch (e: any) {
      setTestStatus(`❌ Xatolik: ${e.message}`);
    } finally {
      setTestSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin mr-2" />
        Userbot sozlamalari yuklanmoqda...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 border border-indigo-500/20 text-white flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-xl">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-indigo-600/30 rounded-xl border border-indigo-400/30 text-indigo-300">
            <Smartphone className="w-8 h-8" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold">Telegram Userbot Bildirishnoma Tizimi</h2>
              {settings?.is_authenticated ? (
                <span className="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                  Ulangan: {settings.account_name || settings.phone_number}
                </span>
              ) : (
                <span className="px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-rose-400"></span>
                  Ulanmagan
                </span>
              )}
            </div>
            <p className="text-sm text-slate-300 mt-1">
              O'quv markazi rasmiy Telegram profilidan ota-onalar shaxsiyiga (botga start bosish shart emas) avtomatik xabar yuborish.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto">
          {settings?.is_authenticated ? (
            <>
              <button
                onClick={() => setTestModalOpen(true)}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition flex items-center gap-2 shadow-lg shadow-indigo-600/20"
              >
                <Send className="w-4 h-4" />
                Test Xabar Yuborish
              </button>
              <button
                onClick={handleLogout}
                className="px-4 py-2 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 font-medium text-sm transition flex items-center gap-2 border border-rose-500/30"
              >
                <LogOut className="w-4 h-4" />
                Uzish
              </button>
            </>
          ) : (
            <button
              onClick={() => {
                setLoginStep("phone");
                setLoginError("");
                setLoginModalOpen(true);
              }}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-semibold text-sm transition flex items-center gap-2 shadow-lg shadow-emerald-500/20"
            >
              <Zap className="w-4 h-4" />
              Telegram Akkauntni Ulash
            </button>
          )}
        </div>
      </div>

      {/* Main Switcher & Save Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-4 rounded-xl bg-slate-900/60 border border-slate-800 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setActiveTab("modules")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition flex items-center gap-2 ${
              activeTab === "modules"
                ? "bg-indigo-600 text-white"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
            }`}
          >
            <Sliders className="w-4 h-4" />
            Bildirishnoma Modullari & Shablonlar
          </button>
          <button
            onClick={() => {
              setActiveTab("logs");
              fetchLogs();
            }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition flex items-center gap-2 ${
              activeTab === "logs"
                ? "bg-indigo-600 text-white"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
            }`}
          >
            <History className="w-4 h-4" />
            Yuborilgan Xabarlar Tarixi ({logs.length})
          </button>
        </div>

        {activeTab === "modules" && (
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <span className="text-sm font-medium text-slate-300">Tizim holati:</span>
              <input
                type="checkbox"
                checked={settings?.is_enabled ?? true}
                onChange={() => handleToggle("is_enabled")}
                className="w-5 h-5 accent-indigo-600 rounded cursor-pointer"
              />
              <span className={`text-xs font-semibold ${settings?.is_enabled ? "text-emerald-400" : "text-slate-500"}`}>
                {settings?.is_enabled ? "Yoqilgan" : "O'chirilgan"}
              </span>
            </label>

            <button
              onClick={handleSaveSettings}
              disabled={saving}
              className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-medium text-sm transition flex items-center gap-2 shadow-md shadow-emerald-600/20"
            >
              {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
              Sozlamalarni Saqlash
            </button>
          </div>
        )}
      </div>

      {/* TAB 1: MODULES & TEMPLATES */}
      {activeTab === "modules" && settings && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {Object.entries(TEMPLATE_META).map(([key, meta]) => {
            const Icon = meta.icon;
            const toggleKey = `notify_${key.replace("attendance_absent", "absent").replace("attendance_late", "late").replace("lesson_cancelled", "lesson_cancelled")}` as keyof UserbotSettings;
            const isEnabled = Boolean(settings[toggleKey] ?? true);
            const templateText = settings.templates?.[key] || "";

            return (
              <div
                key={key}
                className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 hover:border-indigo-500/30 transition flex flex-col justify-between space-y-4"
              >
                <div>
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                        <Icon className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-slate-100 text-sm">{meta.label}</h3>
                        <p className="text-xs text-slate-400 mt-0.5">{meta.defaultDesc}</p>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={isEnabled}
                      onChange={() => handleToggle(toggleKey)}
                      className="w-5 h-5 accent-indigo-600 rounded cursor-pointer"
                    />
                  </div>

                  {/* Variables Helper */}
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    <span className="text-[11px] text-slate-400 flex items-center gap-1">
                      <Info className="w-3 h-3" /> O'zgaruvchilar:
                    </span>
                    {meta.vars.map((v) => (
                      <button
                        key={v}
                        type="button"
                        onClick={() => handleTemplateChange(key, templateText + ` ${v}`)}
                        className="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-800 text-indigo-300 hover:bg-indigo-900/50 border border-slate-700 transition"
                      >
                        {v}
                      </button>
                    ))}
                  </div>

                  {/* Textarea */}
                  <textarea
                    rows={4}
                    value={templateText}
                    onChange={(e) => handleTemplateChange(key, e.target.value)}
                    placeholder="Xabar matni..."
                    className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 focus:border-indigo-500 focus:outline-none text-slate-200 text-xs font-mono leading-relaxed resize-y"
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* TAB 2: LOGS TABLE */}
      {activeTab === "logs" && (
        <div className="rounded-2xl bg-slate-900/80 border border-slate-800 overflow-hidden">
          <div className="p-4 border-b border-slate-800 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <History className="w-4 h-4 text-indigo-400" />
              Telegram Userbot Orqali Yuborilgan So'nggi Xabarlar
            </h3>
            <button
              onClick={fetchLogs}
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Yangilash
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 font-medium">
                <tr>
                  <th className="p-3">Sana</th>
                  <th className="p-3">O'quvchi</th>
                  <th className="p-3">Ota-ona Tel</th>
                  <th className="p-3">Hodisa Tu`ri</th>
                  <th className="p-3">Xabar Matni</th>
                  <th className="p-3">Holat</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {logs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-slate-500">
                      Hozircha yuborilgan xabarlar mavjud emas
                    </td>
                  </tr>
                ) : (
                  logs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-800/40 transition">
                      <td className="p-3 text-slate-400 font-mono text-[11px] whitespace-nowrap">
                        {log.created_at}
                      </td>
                      <td className="p-3 font-semibold text-slate-200">{log.student_name || "—"}</td>
                      <td className="p-3 font-mono text-indigo-300">{log.recipient_phone}</td>
                      <td className="p-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                          {log.event_type}
                        </span>
                      </td>
                      <td className="p-3 max-w-xs truncate text-slate-300" title={log.message_text}>
                        {log.message_text}
                      </td>
                      <td className="p-3">
                        {log.status === "sent" ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1 w-fit">
                            <CheckCircle2 className="w-3 h-3" /> Yuborildi
                          </span>
                        ) : log.status === "failed" ? (
                          <span
                            className="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center gap-1 w-fit"
                            title={log.error_message}
                          >
                            <XCircle className="w-3 h-3" /> {log.error_message || "Xato"}
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1 w-fit">
                            <Clock className="w-3 h-3" /> Navbatda
                          </span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* LOGIN MODAL */}
      {loginModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-md p-6 rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl text-white space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold flex items-center gap-2">
                <Smartphone className="w-5 h-5 text-indigo-400" />
                Telegram Akkauntini Ulash (Pyrogram)
              </h3>
              <button
                onClick={() => setLoginModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            {loginError && (
              <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                {loginError}
              </div>
            )}

            {loginStep === "phone" ? (
              <div className="space-y-4">
                <p className="text-xs text-slate-300">
                  O'quv markazi Telegram profiliga ulangan telefon raqamini kiriting. Telegram SMS kodi shu raqam Telegram ilovasiga yuboriladi.
                </p>
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Telefon Raqami:</label>
                  <input
                    type="text"
                    value={phoneInput}
                    onChange={(e) => setPhoneInput(e.target.value)}
                    placeholder="+998901234567"
                    className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 focus:border-indigo-500 focus:outline-none text-sm font-mono"
                  />
                </div>

                <button
                  onClick={handleSendCode}
                  disabled={loginLoading}
                  className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition flex items-center justify-center gap-2"
                >
                  {loginLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : "SMS Kod Yuborish"}
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <p className="text-xs text-slate-300">
                  Telegram ilovangizga kelgan 5 xonali tasdiqlash kodini kiriting:
                </p>
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Telegram SMS Kodi:</label>
                  <input
                    type="text"
                    value={codeInput}
                    onChange={(e) => setCodeInput(e.target.value)}
                    placeholder="12345"
                    className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 focus:border-indigo-500 focus:outline-none text-sm font-mono text-center tracking-widest text-lg font-bold"
                  />
                </div>

                <div>
                  <label className="text-xs text-slate-400 block mb-1">
                    2-Bosqichli Parol (2FA Password, agar bo'lsa):
                  </label>
                  <input
                    type="password"
                    value={passwordInput}
                    onChange={(e) => setPasswordInput(e.target.value)}
                    placeholder="Ixtiyoriy Cloud Password"
                    className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 focus:border-indigo-500 focus:outline-none text-sm"
                  />
                </div>

                <button
                  onClick={handleVerifyCode}
                  disabled={loginLoading}
                  className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm transition flex items-center justify-center gap-2"
                >
                  {loginLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : "Tasdiqlash & Ulash"}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TEST MESSAGE MODAL */}
      {testModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-md p-6 rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl text-white space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold flex items-center gap-2">
                <Send className="w-5 h-5 text-indigo-400" />
                Test Telegram Xabari Yuborish
              </h3>
              <button onClick={() => setTestModalOpen(false)} className="text-slate-400 hover:text-white">
                ✕
              </button>
            </div>

            {testStatus && (
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-indigo-300">
                {testStatus}
              </div>
            )}

            <div>
              <label className="text-xs text-slate-400 block mb-1">Ota-ona / Qabul qiluvchi tel:</label>
              <input
                type="text"
                value={testPhone}
                onChange={(e) => setTestPhone(e.target.value)}
                placeholder="+998901234567"
                className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 focus:border-indigo-500 focus:outline-none text-sm font-mono"
              />
            </div>

            <div>
              <label className="text-xs text-slate-400 block mb-1">Xabar matni:</label>
              <textarea
                rows={3}
                value={testMessage}
                onChange={(e) => setTestMessage(e.target.value)}
                placeholder="Salom, bu test xabari..."
                className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 focus:border-indigo-500 focus:outline-none text-xs font-mono"
              />
            </div>

            <button
              onClick={handleSendTest}
              disabled={testSending}
              className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition flex items-center justify-center gap-2"
            >
              {testSending ? <RefreshCw className="w-4 h-4 animate-spin" /> : "Navbatga Qo'shish & Yuborish"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
