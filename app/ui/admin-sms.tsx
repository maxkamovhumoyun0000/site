"use client";

import React, { useState, useRef } from "react";
import { useWebT } from "./web-i18n";

export function AdminSms({
  apiFetch,
}: {
  apiFetch: (path: string, options?: any) => Promise<any>;
}) {
  const tt = useWebT();
  const [phone, setPhone] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phone || !message) {
      setError(tt("admin.sms.error.empty", "Raqam va matnni kiriting"));
      return;
    }
    setError("");
    setSuccess("");
    setLoading(true);

    try {
      await apiFetch("/admin/sms/send", {
        method: "POST",
        body: { phone_number: phone, message },
      });
      setSuccess(tt("admin.sms.success", "SMS muvaffaqiyatli yuborildi!"));
      setPhone("");
      setMessage("");
    } catch (err) {
      setError(err instanceof Error ? err.message : tt("admin.sms.error.generic", "Xatolik yuz berdi"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 pb-10">
      <section className="panel-card max-w-xl mx-auto w-full">
        <div className="row-between">
          <div>
            <h3>{tt("admin.sms.title", "SMS Yuborish")}</h3>
            <p className="text-sm text-ink-600 dark:text-navy-300">
              {tt("admin.sms.subtitle", "Foydalanuvchiga to'g'ridan-to'g'ri SMS yuboring")}
            </p>
          </div>
        </div>
        
        {error ? (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
            {error}
          </div>
        ) : null}

        {success ? (
          <div className="mt-4 rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm font-semibold text-green-700 dark:border-green-500/20 dark:bg-green-500/10 dark:text-green-300">
            {success}
          </div>
        ) : null}

        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-bold text-navy-900 dark:text-white">
              {tt("admin.sms.phone", "Telefon raqami (masalan 998901234567)")}
            </label>
            <input
              type="text"
              className="text-input"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="998901234567"
              disabled={loading}
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-sm font-bold text-navy-900 dark:text-white">
              {tt("admin.sms.message", "SMS Matni")}
            </label>
            <textarea
              className="text-input resize-none h-32"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={tt("admin.sms.messagePlaceholder", "Xabar matnini kiriting...")}
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary mt-2"
            disabled={loading}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white" />
                {tt("common.sending", "Yuborilmoqda...")}
              </span>
            ) : (
              tt("admin.sms.sendBtn", "SMS Yuborish")
            )}
          </button>
        </form>
      </section>
    </div>
  );
}
