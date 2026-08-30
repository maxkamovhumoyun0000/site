"use client";

import React, { useState, useEffect } from "react";

// Clean SVG Icon Components
const SmartphoneIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
  </svg>
);

const CheckCircleIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const XCircleIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const ClockIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const SendIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
  </svg>
);

const RefreshIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
  </svg>
);

const LogOutIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
  </svg>
);

const SlidersIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
  </svg>
);

const BellIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
  </svg>
);

const AlertTriangleIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
  </svg>
);

const CalendarIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
  </svg>
);

const GiftIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V6a2 2 0 10-2 2h2zm0 0d17 11v8a2 2 0 01-2 2H5a2 2 0 01-2-2v-8a2 2 0 012-2h14a2 2 0 012 2z" />
  </svg>
);

const CreditCardIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
  </svg>
);

const MessageSquareIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
  </svg>
);

const UserPlusIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
  </svg>
);

const ZapIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
  </svg>
);

const InfoIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const ShieldCheckIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
  </svg>
);

const HistoryIcon = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

interface UserbotSettings {
  is_enabled: boolean;
  phone_number: string | null;
  account_name: string | null;
  is_authenticated: boolean;
  api_id?: number | null;
  api_hash?: string | null;
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
    icon: AlertTriangleIcon,
    vars: ["{student_name}", "{group_name}", "{course_title}"],
    defaultDesc: "O'qituvchi 'bormadi' deb belgilaganda otasiga/onasiga yuboriladi.",
  },
  attendance_late: {
    label: "Darsga kechikib kelish (5 daqiqadan keyin)",
    icon: ClockIcon,
    vars: ["{student_name}", "{group_name}"],
    defaultDesc: "5 daqiqadan keyin holat 'keldiga' o'zgartirilsa yuboriladi.",
  },
  lesson_cancelled: {
    label: "Dars qoldirilishi / Bayram e'loni",
    icon: CalendarIcon,
    vars: ["{group_name}", "{reason}", "{date}"],
    defaultDesc: "Dars bekor qilinganda yoki admin bayram belgilaganda yuboriladi.",
  },
  homework_alert: {
    label: "Bajarilmagan vazifa / Past baho",
    icon: MessageSquareIcon,
    vars: ["{student_name}", "{group_name}", "{reason}", "{score}"],
    defaultDesc: "Vazifa deadline o'tganda yoki o'qituvchi bajarmadi deya belgilasa.",
  },
  achievement_notice: {
    label: "Reyting & Yutuqlar (1-o'rin / Do'kon)",
    icon: GiftIcon,
    vars: ["{student_name}", "{reason}", "{group_name}"],
    defaultDesc: "O'quvchi guruhda 1-o'rinni egallaganda yoki sovg'a xarid qilganda.",
  },
  payment_reminder: {
    label: "To'lov eslatmasi (Darsga 3 kun qolganda)",
    icon: ShieldCheckIcon,
    vars: ["{student_name}", "{amount}", "{date}"],
    defaultDesc: "To'lov muddati tugashidan 3 kun oldin avtomatik yuboriladi.",
  },
  overdue_alert: {
    label: "Muddati o'tgan to'lov ogohlantirishi",
    icon: AlertTriangleIcon,
    vars: ["{student_name}", "{amount}", "{days}"],
    defaultDesc: "To'lov muddati 1 kun o'tib ketganda ota-onaga yuboriladi.",
  },
  payment_receipt: {
    label: "To'lov qabul qilindi kvitansiyasi",
    icon: CheckCircleIcon,
    vars: ["{student_name}", "{amount}", "{receipt_no}"],
    defaultDesc: "Kassaga to'lov tushganda rasmiy kvitansiya sifatida yuboriladi.",
  },
  welcome_message: {
    label: "Yangi o'quvchi xush kelibsiz xabari",
    icon: UserPlusIcon,
    vars: ["{student_name}", "{group_name}", "{schedule}", "{start_time}", "{end_time}"],
    defaultDesc: "O'quvchi guruhga qo'shilganda dars jadvali va manzillar bilan yuboriladi.",
  },
};

interface AdminUserbotProps {
  apiFetch?: (path: string, options?: { method?: "GET" | "POST" | "PATCH" | "DELETE"; body?: any }) => Promise<any>;
}

export default function AdminUserbot({ apiFetch }: AdminUserbotProps = {}) {
  const [settings, setSettings] = useState<UserbotSettings | null>(null);
  const [logs, setLogs] = useState<UserbotLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<"modules" | "logs" | "version">("modules");
  const [versionSettings, setVersionSettings] = useState({
    min_student_version: "1.0.0",
    min_student_build: 1,
    student_play_store_url: "https://play.google.com/store/apps/details?id=com.diamond.students",
    student_app_store_url: "https://apps.apple.com/app/id6742398571",
    min_teacher_version: "1.0.0",
    min_teacher_build: 1,
    teacher_play_store_url: "https://play.google.com/store/apps/details?id=com.diamond.teachers",
    teacher_app_store_url: "https://apps.apple.com/app/id6742398571",
  });
  const [savingVersion, setSavingVersion] = useState(false);

  // Login Modal state
  const [loginModalOpen, setLoginModalOpen] = useState(false);
  const [loginStep, setLoginStep] = useState<"phone" | "code">("phone");
  const [apiIdInput, setApiIdInput] = useState("");
  const [apiHashInput, setApiHashInput] = useState("");
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
    const token = localStorage.getItem("diamond_token") || localStorage.getItem("token") || "";
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    };
  };

  const doFetch = async (endpoint: string, options?: { method?: "GET" | "POST" | "PATCH" | "DELETE"; body?: any }) => {
    const cleanPath = endpoint.startsWith("/api") ? endpoint.substring(4) : endpoint;
    if (apiFetch) {
      return await apiFetch(cleanPath, options);
    }
    const apiPath = `/api${cleanPath}`;
    const res = await fetch(apiPath, {
      method: options?.method || "GET",
      headers: getHeaders(),
      ...(options?.body ? { body: JSON.stringify(options.body) } : {}),
    });
    const text = await res.text().catch(() => "");
    if (!res.ok) {
      let detail = "";
      try {
        const parsed = JSON.parse(text);
        detail = parsed?.detail || parsed?.message || text;
      } catch {
        detail = text;
      }
      throw new Error(detail || `HTTP Error ${res.status}`);
    }
    try {
      return JSON.parse(text);
    } catch {
      throw new Error("Serverdan noto'g'ri javob keldi (JSON emas)");
    }
  };

  const fetchSettings = async () => {
    try {
      const data = await doFetch("/api/admin/userbot/settings");
      if (data) {
        setSettings(data);
        if (data.api_id) setApiIdInput(String(data.api_id));
        if (data.api_hash) setApiHashInput(data.api_hash);
      }
    } catch (e) {
      console.error("Failed to fetch userbot settings", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchLogs = async () => {
    try {
      const data = await doFetch("/api/admin/userbot/logs");
      if (Array.isArray(data)) setLogs(data);
    } catch (e) {
      console.error("Failed to fetch userbot logs", e);
    }
  };

  const fetchVersionSettings = async () => {
    try {
      const data = await doFetch("/api/admin/app-version-settings");
      if (data) setVersionSettings(data);
    } catch (e) {
      console.error("Failed to fetch app version settings", e);
    }
  };

  const handleSaveVersionSettings = async () => {
    setSavingVersion(true);
    try {
      const data = await doFetch("/api/admin/app-version-settings", {
        method: "POST",
        body: versionSettings,
      });
      if (data) {
        setVersionSettings(data);
        alert("Ilova versiyalari va Force Update sozlamalari saqlandi! ✅");
      }
    } catch (e: any) {
      alert(e.message || "Saqlashda xatolik");
    } finally {
      setSavingVersion(false);
    }
  };

  useEffect(() => {
    fetchSettings();
    fetchLogs();
    fetchVersionSettings();
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
      const data = await doFetch("/api/admin/userbot/settings", {
        method: "POST",
        body: settings,
      });
      if (data) {
        setSettings(data);
        alert("Sozlamalar va shablonlar muvaffaqiyatli saqlandi!");
      }
    } catch (e: any) {
      console.error(e);
      alert(e.message || "Saqlashda xatolik");
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
      const data = await doFetch("/api/admin/userbot/send-code", {
        method: "POST",
        body: {
          phone_number: phoneInput.trim(),
          api_id: apiIdInput.trim() ? parseInt(apiIdInput.trim(), 10) : undefined,
          api_hash: apiHashInput.trim() || undefined,
        },
      });
      if (data?.phone_code_hash) {
        setPhoneCodeHash(data.phone_code_hash);
        setLoginStep("code");
      } else {
        setLoginError(data?.detail || "SMS kod yuborishda xatolik");
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
      const data = await doFetch("/api/admin/userbot/verify-code", {
        method: "POST",
        body: {
          phone_number: phoneInput.trim(),
          phone_code_hash: phoneCodeHash,
          code: codeInput.trim(),
          phone_code: codeInput.trim(),
          password: passwordInput.trim() || undefined,
        },
      });
      if (data?.success || data?.ok) {
        setLoginModalOpen(false);
        fetchSettings();
        alert("Telegram Userbot akkaunti muvaffaqiyatli ulandi! ✅");
      } else {
        setLoginError(data?.detail || "Kodni tasdiqlashda xatolik");
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
      await doFetch("/api/admin/userbot/logout", { method: "POST" });
      fetchSettings();
    } catch (e) {
      console.error(e);
    }
  };

  const handleSendTest = async () => {
    if (!testPhone.trim() || !testMessage.trim()) return;
    setTestSending(true);
    setTestStatus("");
    try {
      const data = await doFetch("/api/admin/userbot/test-send", {
        method: "POST",
        body: {
          phone_number: testPhone.trim(),
          message: testMessage.trim(),
        },
      });
      if (data?.success) {
        setTestStatus("✅ Xabar muvaffaqiyatli navbatga qo'shildi!");
        setTimeout(() => {
          setTestModalOpen(false);
          fetchLogs();
        }, 1500);
      } else {
        setTestStatus(`❌ Xatolik: ${data?.detail || "Yuborib bo'lmadi"}`);
      }
    } catch (e: any) {
      setTestStatus(`❌ Xatolik: ${e.message}`);
    } finally {
      setTestSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-slate-500 dark:text-slate-400">
        <RefreshIcon className="w-6 h-6 animate-spin mr-2" />
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
            <SmartphoneIcon className="w-8 h-8" />
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
                <SendIcon className="w-4 h-4" />
                Test Xabar Yuborish
              </button>
              <button
                onClick={handleLogout}
                className="px-4 py-2 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 font-medium text-sm transition flex items-center gap-2 border border-rose-500/30"
              >
                <LogOutIcon className="w-4 h-4" />
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
              <ZapIcon className="w-4 h-4" />
              Telegram Akkauntni Ulash
            </button>
          )}
        </div>
      </div>

      {/* Main Switcher & Save Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-4 rounded-xl bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 shadow-sm backdrop-blur-md">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setActiveTab("modules")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition flex items-center gap-2 ${
              activeTab === "modules"
                ? "bg-indigo-600 text-white"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
            }`}
          >
            <SlidersIcon className="w-4 h-4" />
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
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
            }`}
          >
            <HistoryIcon className="w-4 h-4" />
            Yuborilgan Xabarlar Tarixi ({logs.length})
          </button>
          <button
            onClick={() => {
              setActiveTab("version");
              fetchVersionSettings();
            }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition flex items-center gap-2 ${
              activeTab === "version"
                ? "bg-indigo-600 text-white"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
            }`}
          >
            <ZapIcon className="w-4 h-4" />
            Mobil Ilovalar Versiyasi (Force Update)
          </button>
        </div>

        {activeTab === "modules" && (
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Tizim holati:</span>
              <input
                type="checkbox"
                checked={settings?.is_enabled ?? true}
                onChange={() => handleToggle("is_enabled")}
                className="w-5 h-5 accent-indigo-600 rounded cursor-pointer"
              />
              <span className={`text-xs font-semibold ${settings?.is_enabled ? "text-emerald-600 dark:text-emerald-400" : "text-slate-400 dark:text-slate-500"}`}>
                {settings?.is_enabled ? "Yoqilgan" : "O'chirilgan"}
              </span>
            </label>

            <button
              onClick={handleSaveSettings}
              disabled={saving}
              className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-medium text-sm transition flex items-center gap-2 shadow-md shadow-emerald-600/20"
            >
              {saving ? <RefreshIcon className="w-4 h-4 animate-spin" /> : <CheckCircleIcon className="w-4 h-4" />}
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
                className="p-5 rounded-2xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 hover:border-indigo-500/30 transition flex flex-col justify-between space-y-4 shadow-sm"
              >
                <div>
                  <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3 mb-3">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
                        <Icon className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-slate-900 dark:text-slate-100 text-sm">{meta.label}</h3>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{meta.defaultDesc}</p>
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
                    <span className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1">
                      <InfoIcon className="w-3 h-3" /> O'zgaruvchilar:
                    </span>
                    {meta.vars.map((v) => (
                      <button
                        key={v}
                        type="button"
                        onClick={() => handleTemplateChange(key, templateText + ` ${v}`)}
                        className="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-100 dark:bg-slate-800 text-indigo-600 dark:text-indigo-300 hover:bg-indigo-50 dark:hover:bg-indigo-900/50 border border-slate-200 dark:border-slate-700 transition"
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
                    className="w-full p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 focus:border-indigo-500 focus:outline-none text-slate-800 dark:text-slate-200 text-xs font-mono leading-relaxed resize-y placeholder-slate-400 dark:placeholder-slate-600"
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* TAB 2: LOGS TABLE */}
      {activeTab === "logs" && (
        <div className="rounded-2xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm">
          <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-200 flex items-center gap-2">
              <HistoryIcon className="w-4 h-4 text-indigo-500 dark:text-indigo-400" />
              Telegram Userbot Orqali Yuborilgan So'nggi Xabarlar
            </h3>
            <button
              onClick={fetchLogs}
              className="px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-medium transition flex items-center gap-1.5"
            >
              <RefreshIcon className="w-3.5 h-3.5" />
              Yangilash
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700 dark:text-slate-300">
              <thead className="bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 font-medium">
                <tr>
                  <th className="p-3">Sana</th>
                  <th className="p-3">O'quvchi</th>
                  <th className="p-3">Ota-ona Tel</th>
                  <th className="p-3">Hodisa Turi</th>
                  <th className="p-3">Xabar Matni</th>
                  <th className="p-3">Holat</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800/60">
                {logs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-slate-400 dark:text-slate-500">
                      Hozircha yuborilgan xabarlar mavjud emas
                    </td>
                  </tr>
                ) : (
                  logs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition">
                      <td className="p-3 text-slate-500 dark:text-slate-400 font-mono text-[11px] whitespace-nowrap">
                        {log.created_at}
                      </td>
                      <td className="p-3 font-semibold text-slate-900 dark:text-slate-200">{log.student_name || "—"}</td>
                      <td className="p-3 font-mono text-indigo-600 dark:text-indigo-300">{log.recipient_phone}</td>
                      <td className="p-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-500/10 text-indigo-600 dark:text-indigo-300 border border-indigo-500/20">
                          {log.event_type}
                        </span>
                      </td>
                      <td className="p-3 max-w-xs truncate text-slate-700 dark:text-slate-300" title={log.message_text}>
                        {log.message_text}
                      </td>
                      <td className="p-3">
                        {log.status === "sent" ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30 flex items-center gap-1 w-fit">
                            <CheckCircleIcon className="w-3 h-3" /> Yuborildi
                          </span>
                        ) : log.status === "failed" ? (
                          <span
                            className="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/20 text-rose-700 dark:text-rose-300 border border-rose-500/30 flex items-center gap-1 w-fit"
                            title={log.error_message}
                          >
                            <XCircleIcon className="w-3 h-3" /> {log.error_message || "Xato"}
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-500/30 flex items-center gap-1 w-fit">
                            <ClockIcon className="w-3 h-3" /> Navbatda
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

      {/* TAB 3: APP VERSION CONTROL & FORCE UPDATE */}
      {activeTab === "version" && (
        <div className="space-y-6">
          <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-4">
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <SmartphoneIcon className="w-5 h-5 text-indigo-500" />
                  Mobil Ilovalar Versiyasini Boshqarish & Majburiy Yangilash (Force Update)
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  App Store va Google Play'ga yangi versiya chiqarganingizda minimally qaysi versiyadan past bo'lgan foydalanuvchilarga "Yangilash" ekranini chiqarishni belgilaysiz.
                </p>
              </div>
              <button
                onClick={handleSaveVersionSettings}
                disabled={savingVersion}
                className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-sm transition flex items-center gap-2 shadow-md shadow-emerald-600/20"
              >
                {savingVersion ? <RefreshIcon className="w-4 h-4 animate-spin" /> : <CheckCircleIcon className="w-4 h-4" />}
                Versiya Sozlamalarini Saqlash
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* STUDENT APP SETTINGS */}
              <div className="p-5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-4">
                <div className="flex items-center gap-2 pb-2 border-b border-slate-200 dark:border-slate-800">
                  <span className="p-2 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 font-bold text-xs">🎓 STUDENT APP</span>
                  <h4 className="font-bold text-sm text-slate-900 dark:text-slate-100">O'quvchilar Ilovasi</h4>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-600 dark:text-slate-400 block mb-1 font-medium">Eng Kam Versiya (Min Version):</label>
                    <input
                      type="text"
                      value={versionSettings.min_student_version}
                      onChange={(e) => setVersionSettings({ ...versionSettings, min_student_version: e.target.value })}
                      placeholder="2.0.0"
                      className="w-full p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-900 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-600 dark:text-slate-400 block mb-1 font-medium">Eng Kam Build Kodi (Build Number):</label>
                    <input
                      type="number"
                      value={versionSettings.min_student_build}
                      onChange={(e) => setVersionSettings({ ...versionSettings, min_student_build: parseInt(e.target.value, 10) || 1 })}
                      placeholder="1"
                      className="w-full p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-900 dark:text-slate-100"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs text-slate-600 dark:text-slate-400 block mb-1 font-medium">Google Play Store Havolasi (Android):</label>
                  <input
                    type="text"
                    value={versionSettings.student_play_store_url}
                    onChange={(e) => setVersionSettings({ ...versionSettings, student_play_store_url: e.target.value })}
                    placeholder="https://play.google.com/store/apps/details?id=..."
                    className="w-full p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-900 dark:text-slate-100"
                  />
                </div>

                <div>
                  <label className="text-xs text-slate-600 dark:text-slate-400 block mb-1 font-medium">Apple App Store Havolasi (iOS):</label>
                  <input
                    type="text"
                    value={versionSettings.student_app_store_url}
                    onChange={(e) => setVersionSettings({ ...versionSettings, student_app_store_url: e.target.value })}
                    placeholder="https://apps.apple.com/app/id..."
                    className="w-full p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-900 dark:text-slate-100"
                  />
                </div>
              </div>

              {/* TEACHER APP SETTINGS */}
              <div className="p-5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-4">
                <div className="flex items-center gap-2 pb-2 border-b border-slate-200 dark:border-slate-800">
                  <span className="p-2 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold text-xs">👨‍🏫 TEACHER APP</span>
                  <h4 className="font-bold text-sm text-slate-900 dark:text-slate-100">O'qituvchilar Ilovasi</h4>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-600 dark:text-slate-400 block mb-1 font-medium">Eng Kam Versiya (Min Version):</label>
                    <input
                      type="text"
                      value={versionSettings.min_teacher_version}
                      onChange={(e) => setVersionSettings({ ...versionSettings, min_teacher_version: e.target.value })}
                      placeholder="1.0.0"
                      className="w-full p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-900 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-600 dark:text-slate-400 block mb-1 font-medium">Eng Kam Build Kodi (Build Number):</label>
                    <input
                      type="number"
                      value={versionSettings.min_teacher_build}
                      onChange={(e) => setVersionSettings({ ...versionSettings, min_teacher_build: parseInt(e.target.value, 10) || 1 })}
                      placeholder="1"
                      className="w-full p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-900 dark:text-slate-100"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs text-slate-600 dark:text-slate-400 block mb-1 font-medium">Google Play Store Havolasi (Android):</label>
                  <input
                    type="text"
                    value={versionSettings.teacher_play_store_url}
                    onChange={(e) => setVersionSettings({ ...versionSettings, teacher_play_store_url: e.target.value })}
                    placeholder="https://play.google.com/store/apps/details?id=..."
                    className="w-full p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-900 dark:text-slate-100"
                  />
                </div>

                <div>
                  <label className="text-xs text-slate-600 dark:text-slate-400 block mb-1 font-medium">Apple App Store Havolasi (iOS):</label>
                  <input
                    type="text"
                    value={versionSettings.teacher_app_store_url}
                    onChange={(e) => setVersionSettings({ ...versionSettings, teacher_app_store_url: e.target.value })}
                    placeholder="https://apps.apple.com/app/id..."
                    className="w-full p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-900 dark:text-slate-100"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* LOGIN MODAL */}
      {loginModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 dark:bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-md p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl text-slate-900 dark:text-white space-y-5">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <h3 className="text-base font-bold flex items-center gap-2 text-slate-900 dark:text-white">
                <SmartphoneIcon className="w-5 h-5 text-indigo-500 dark:text-indigo-400" />
                Telegram Akkauntini Ulash (Pyrogram)
              </h3>
              <button
                onClick={() => setLoginModalOpen(false)}
                className="text-slate-400 hover:text-slate-700 dark:hover:text-white"
              >
                ✕
              </button>
            </div>

            {loginError && (
              <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2">
                <AlertTriangleIcon className="w-4 h-4 flex-shrink-0" />
                {loginError}
              </div>
            )}

            {loginStep === "phone" ? (
              <div className="space-y-4">
                <div className="p-3 rounded-xl bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 text-xs text-indigo-900 dark:text-indigo-200 space-y-1">
                  <p className="font-semibold flex items-center gap-1.5">
                    <InfoIcon className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                    my.telegram.org Kalitlari:
                  </p>
                  <p>
                    Telegram xavfsizlik talablariga ko'ra profil ulash uchun <a href="https://my.telegram.org" target="_blank" rel="noreferrer" className="underline font-semibold text-indigo-600 dark:text-indigo-400">my.telegram.org</a> saytidan bepul olingan <b>API ID</b> va <b>API Hash</b> kiritilishi lozim.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-600 dark:text-slate-400 block mb-1">API ID:</label>
                    <input
                      type="text"
                      value={apiIdInput}
                      onChange={(e) => setApiIdInput(e.target.value)}
                      placeholder="masalan: 28194821"
                      className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 focus:border-indigo-500 focus:outline-none text-xs font-mono text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-600"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-600 dark:text-slate-400 block mb-1">API Hash:</label>
                    <input
                      type="text"
                      value={apiHashInput}
                      onChange={(e) => setApiHashInput(e.target.value)}
                      placeholder="masalan: e3f8921a48..."
                      className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 focus:border-indigo-500 focus:outline-none text-xs font-mono text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-600"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs text-slate-600 dark:text-slate-400 block mb-1">Telefon Raqami:</label>
                  <input
                    type="text"
                    value={phoneInput}
                    onChange={(e) => setPhoneInput(e.target.value)}
                    placeholder="+998901234567 yoki +447529599103"
                    className="w-full p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 focus:border-indigo-500 focus:outline-none text-sm font-mono text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-600"
                  />
                </div>

                <button
                  onClick={handleSendCode}
                  disabled={loginLoading}
                  className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition flex items-center justify-center gap-2 shadow-md shadow-indigo-600/20"
                >
                  {loginLoading ? <RefreshIcon className="w-4 h-4 animate-spin" /> : "SMS Kod Yuborish"}
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <p className="text-xs text-slate-600 dark:text-slate-300">
                  Telegram ilovangizga kelgan 5 xonali tasdiqlash kodini kiriting:
                </p>
                <div>
                  <label className="text-xs text-slate-600 dark:text-slate-400 block mb-1">Telegram SMS Kodi:</label>
                  <input
                    type="text"
                    value={codeInput}
                    onChange={(e) => setCodeInput(e.target.value)}
                    placeholder="12345"
                    className="w-full p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 focus:border-indigo-500 focus:outline-none text-sm font-mono text-center tracking-widest text-lg font-bold text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-600"
                  />
                </div>

                <div>
                  <label className="text-xs text-slate-600 dark:text-slate-400 block mb-1">
                    2-Bosqichli Parol (2FA Password, agar bo'lsa):
                  </label>
                  <input
                    type="password"
                    value={passwordInput}
                    onChange={(e) => setPasswordInput(e.target.value)}
                    placeholder="Ixtiyoriy Cloud Password"
                    className="w-full p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 focus:border-indigo-500 focus:outline-none text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-600"
                  />
                </div>

                <button
                  onClick={handleVerifyCode}
                  disabled={loginLoading}
                  className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm transition flex items-center justify-center gap-2 shadow-md shadow-emerald-600/20"
                >
                  {loginLoading ? <RefreshIcon className="w-4 h-4 animate-spin" /> : "Tasdiqlash & Ulash"}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TEST MESSAGE MODAL */}
      {testModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 dark:bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-md p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl text-slate-900 dark:text-white space-y-4">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <h3 className="text-base font-bold flex items-center gap-2 text-slate-900 dark:text-white">
                <SendIcon className="w-5 h-5 text-indigo-500 dark:text-indigo-400" />
                Test Telegram Xabari Yuborish
              </h3>
              <button onClick={() => setTestModalOpen(false)} className="text-slate-400 hover:text-slate-700 dark:hover:text-white">
                ✕
              </button>
            </div>

            {testStatus && (
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono text-indigo-600 dark:text-indigo-300">
                {testStatus}
              </div>
            )}

            <div>
              <label className="text-xs text-slate-600 dark:text-slate-400 block mb-1">Ota-ona / Qabul qiluvchi tel:</label>
              <input
                type="text"
                value={testPhone}
                onChange={(e) => setTestPhone(e.target.value)}
                placeholder="+998901234567"
                className="w-full p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 focus:border-indigo-500 focus:outline-none text-sm font-mono text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-600"
              />
            </div>

            <div>
              <label className="text-xs text-slate-600 dark:text-slate-400 block mb-1">Xabar matni:</label>
              <textarea
                rows={3}
                value={testMessage}
                onChange={(e) => setTestMessage(e.target.value)}
                placeholder="Salom, bu test xabari..."
                className="w-full p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 focus:border-indigo-500 focus:outline-none text-xs font-mono text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-600"
              />
            </div>

            <button
              onClick={handleSendTest}
              disabled={testSending}
              className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition flex items-center justify-center gap-2 shadow-md shadow-indigo-600/20"
            >
              {testSending ? <RefreshIcon className="w-4 h-4 animate-spin" /> : "Navbatga Qo'shish & Yuborish"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
