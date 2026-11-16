"use client";

import { useEffect, useState } from "react";

export function DiamondVoyAppVersionWizard({
  apiFetch,
  onSuccess,
  endpoint = "/admin/app-version-settings",
}: {
  apiFetch: (path: string, options?: any) => Promise<any>;
  onSuccess?: () => void;
  endpoint?: string;
}) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  const [studentVersion, setStudentVersion] = useState("1.0.0");
  const [studentBuild, setStudentBuild] = useState("1");
  const [studentStoreUrl, setStudentStoreUrl] = useState("");
  const [studentIosStoreUrl, setStudentIosStoreUrl] = useState("");

  const [teacherVersion, setTeacherVersion] = useState("1.0.0");
  const [teacherBuild, setTeacherBuild] = useState("1");
  const [teacherStoreUrl, setTeacherStoreUrl] = useState("");
  const [teacherIosStoreUrl, setTeacherIosStoreUrl] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    apiFetch(endpoint)
      .then((res: any) => {
        if (!active) return;
        if (res?.student) {
          setStudentVersion(res.student.min_version || "1.0.0");
          setStudentBuild(String(res.student.min_build || "1"));
          setStudentStoreUrl(res.student.store_url || "");
          setStudentIosStoreUrl(res.student.ios_store_url || "");
        }
        if (res?.teacher) {
          setTeacherVersion(res.teacher.min_version || "1.0.0");
          setTeacherBuild(String(res.teacher.min_build || "1"));
          setTeacherStoreUrl(res.teacher.store_url || "");
          setTeacherIosStoreUrl(res.teacher.ios_store_url || "");
        }
      })
      .catch((err: any) => {
        if (active) setError(err.message || "Versiyalarni yuklab bo'lmadi");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [apiFetch, endpoint]);

  async function handleSave() {
    setSaving(true);
    setError("");
    setSuccessMsg("");
    try {
      await apiFetch(endpoint, {
        method: "POST",
        body: {
          student: {
            min_version: studentVersion.trim(),
            min_build: parseInt(studentBuild, 10) || 1,
            store_url: studentStoreUrl.trim(),
            ios_store_url: studentIosStoreUrl.trim(),
          },
          teacher: {
            min_version: teacherVersion.trim(),
            min_build: parseInt(teacherBuild, 10) || 1,
            store_url: teacherStoreUrl.trim(),
            ios_store_url: teacherIosStoreUrl.trim(),
          },
        },
      });
      setSuccessMsg("✅ Versiyalar muvaffaqiyatli saqlandi va kuchga kirdi!");
      if (onSuccess) onSuccess();
    } catch (err: any) {
      setError(err.message || "Saqlashda xatolik yuz berdi");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="p-4 text-center text-sm text-ink-500">Versiya sozlamalari yuklanmoqda...</div>;
  }

  return (
    <div className="w-full max-w-xl border border-blue-200 dark:border-blue-800/50 rounded-2xl bg-white dark:bg-[#1A2332] shadow-lg overflow-hidden flex flex-col">
      <div className="px-4 py-3 bg-blue-50 dark:bg-blue-900/20 border-b border-blue-100 dark:border-blue-800/30 flex justify-between items-center">
        <h4 className="font-bold text-blue-800 dark:text-blue-300">
          🚀 Mobil Ilovalar Versiyasi (Force Update)
        </h4>
        <span className="text-[11px] text-blue-700 dark:text-blue-300">Build raqami tekshirilmaydi</span>
      </div>

      <div className="p-4 space-y-4 text-sm">
        {error && <div className="text-red-500 font-medium bg-red-50 dark:bg-red-900/20 rounded-xl px-3 py-2">{error}</div>}
        {successMsg && <div className="text-green-600 dark:text-green-400 font-bold bg-green-50 dark:bg-green-900/20 rounded-xl px-3 py-2">{successMsg}</div>}

        {/* Student App */}
        <div className="space-y-2 border-b border-line dark:border-white/10 pb-3">
          <h5 className="font-bold text-ink-800 dark:text-slate-200 flex items-center gap-2">
            📱 Diamond Students App
          </h5>
          <div className="grid grid-cols-1 gap-2">
            <div>
              <label className="block text-xs font-semibold mb-1 text-ink-600 dark:text-slate-400">Minimal Versiya</label>
              <input
                type="text"
                value={studentVersion}
                onChange={(e) => setStudentVersion(e.target.value)}
                placeholder="1.0.0"
                className="w-full px-3 py-1.5 border border-line dark:border-white/10 rounded-xl bg-transparent text-sm font-mono"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold mb-1 text-ink-600 dark:text-slate-400">Google Play URL</label>
            <input
              type="text"
              value={studentStoreUrl}
              onChange={(e) => setStudentStoreUrl(e.target.value)}
              placeholder="https://play.google.com/store/apps/details?id=..."
              className="w-full px-3 py-1.5 border border-line dark:border-white/10 rounded-xl bg-transparent text-xs font-mono"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold mb-1 text-ink-600 dark:text-slate-400">App Store URL</label>
            <input
              type="text"
              value={studentIosStoreUrl}
              onChange={(e) => setStudentIosStoreUrl(e.target.value)}
              placeholder="https://apps.apple.com/app/..."
              className="w-full px-3 py-1.5 border border-line dark:border-white/10 rounded-xl bg-transparent text-xs font-mono"
            />
          </div>
        </div>

        {/* Teacher App */}
        <div className="space-y-2 pb-2">
          <h5 className="font-bold text-ink-800 dark:text-slate-200 flex items-center gap-2">
            👨‍🏫 Diamond Teachers App
          </h5>
          <div className="grid grid-cols-1 gap-2">
            <div>
              <label className="block text-xs font-semibold mb-1 text-ink-600 dark:text-slate-400">Minimal Versiya</label>
              <input
                type="text"
                value={teacherVersion}
                onChange={(e) => setTeacherVersion(e.target.value)}
                placeholder="1.0.0"
                className="w-full px-3 py-1.5 border border-line dark:border-white/10 rounded-xl bg-transparent text-sm font-mono"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold mb-1 text-ink-600 dark:text-slate-400">Google Play URL</label>
            <input
              type="text"
              value={teacherStoreUrl}
              onChange={(e) => setTeacherStoreUrl(e.target.value)}
              placeholder="https://play.google.com/store/apps/details?id=..."
              className="w-full px-3 py-1.5 border border-line dark:border-white/10 rounded-xl bg-transparent text-xs font-mono"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold mb-1 text-ink-600 dark:text-slate-400">App Store URL</label>
            <input
              type="text"
              value={teacherIosStoreUrl}
              onChange={(e) => setTeacherIosStoreUrl(e.target.value)}
              placeholder="https://apps.apple.com/app/..."
              className="w-full px-3 py-1.5 border border-line dark:border-white/10 rounded-xl bg-transparent text-xs font-mono"
            />
          </div>
        </div>

        <button
          disabled={saving}
          onClick={handleSave}
          className="w-full px-4 py-2.5 bg-[#1429F2] hover:bg-blue-700 text-white font-bold rounded-xl disabled:opacity-50 transition-colors shadow-md text-sm cursor-pointer"
        >
          {saving ? "Saqlanmoqda..." : "💾 Versiyalarni Saqlash"}
        </button>
      </div>
    </div>
  );
}
