"use client";

import { FormEvent, useState } from "react";
import { storeBrowserSessionToken } from "@/lib/auth-session";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

type AuthResult = {
  access_token?: string;
  user?: Record<string, unknown>;
};

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(String(payload?.detail || "So‘rovni bajarib bo‘lmadi."));
  }
  return payload as T;
}

export default function SpeakingAccountPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [subjects, setSubjects] = useState<string[]>(["English"]);
  const [verificationId, setVerificationId] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [issuedLoginId, setIssuedLoginId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function complete(result: AuthResult) {
    const token = String(result.access_token || "");
    storeBrowserSessionToken(token);
    if (result.user) localStorage.setItem("diamond_user", JSON.stringify(result.user));
    window.location.assign("/?role=speaking_user");
  }

  async function submitLogin(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await postJson<AuthResult>("/auth/login", { login_id: loginId.trim(), password });
      complete(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Kirish amalga oshmadi.");
    } finally {
      setBusy(false);
    }
  }

  async function startRegistration(event: FormEvent) {
    event.preventDefault();
    if (password.length < 8) {
      setError("Parol kamida 8 belgidan iborat bo‘lishi kerak.");
      return;
    }
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await postJson<{ verification_id: string; login_id: string; message?: string }>("/auth/speaking-registration/start", {
        login_id: loginId.trim() || null,
        password,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim(),
        phone: phone.trim() || null,
        language: "uz",
        subjects,
      });
      setVerificationId(String(result.verification_id || ""));
      setIssuedLoginId(String(result.login_id || ""));
      setMessage(String(result.message || "Tasdiqlash kodi emailingizga yuborildi. Spam papkasini ham tekshiring."));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Ro‘yxatdan o‘tish boshlanmadi.");
    } finally {
      setBusy(false);
    }
  }

  async function verifyRegistration(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      const result = await postJson<AuthResult>("/auth/speaking-registration/verify", {
        verification_id: verificationId,
        code: verificationCode.trim(),
      });
      complete(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Kod tasdiqlanmadi.");
    } finally {
      setBusy(false);
    }
  }

  const toggleSubject = (subject: string) => {
    setSubjects((current) => {
      const next = current.includes(subject) ? current.filter((item) => item !== subject) : [...current, subject];
      return next.length ? next : [subject];
    });
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-[#06175d] via-[#0b2ba5] to-[#061032] px-4 py-10 text-white">
      <section className="mx-auto w-full max-w-xl rounded-[2rem] border border-white/20 bg-white/10 p-6 shadow-2xl backdrop-blur-xl sm:p-9">
        <p className="text-xs font-black uppercase tracking-[0.2em] text-cyan-200">Diamond Education</p>
        <h1 className="mt-2 text-3xl font-black">Diamond Speaking</h1>
        <p className="mt-2 text-sm leading-6 text-blue-100">Bitta tasdiqlangan akkaunt sayt va mobil ilovada ishlaydi.</p>

        <div className="mt-6 grid grid-cols-2 rounded-2xl bg-navy-950/50 p-1 text-sm font-bold">
          <button type="button" className={`rounded-xl px-3 py-2.5 transition ${mode === "login" ? "bg-cyan-400 text-navy-950" : "text-blue-100"}`} onClick={() => { setMode("login"); setError(""); }}>
            Kirish
          </button>
          <button type="button" className={`rounded-xl px-3 py-2.5 transition ${mode === "register" ? "bg-cyan-400 text-navy-950" : "text-blue-100"}`} onClick={() => { setMode("register"); setError(""); }}>
            Akkaunt ochish
          </button>
        </div>

        {error ? <p className="mt-5 rounded-xl border border-red-300/30 bg-red-500/20 p-3 text-sm font-semibold text-red-100">{error}</p> : null}
        {message ? <p className="mt-5 rounded-xl border border-cyan-300/30 bg-cyan-500/15 p-3 text-sm font-semibold text-cyan-50">{message}</p> : null}

        {mode === "login" ? (
          <form className="mt-6 space-y-4" onSubmit={submitLogin}>
            <label className="block text-sm font-bold text-cyan-100">Login ID
              <input className="mt-2 w-full rounded-xl border border-white/20 bg-navy-950/50 px-4 py-3 text-white outline-none focus:border-cyan-300" value={loginId} onChange={(event) => setLoginId(event.target.value)} autoComplete="username" required />
            </label>
            <label className="block text-sm font-bold text-cyan-100">Parol
              <input className="mt-2 w-full rounded-xl border border-white/20 bg-navy-950/50 px-4 py-3 text-white outline-none focus:border-cyan-300" value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" required />
            </label>
            <button className="w-full rounded-xl bg-cyan-400 px-4 py-3 font-black text-navy-950 transition hover:bg-cyan-300 disabled:opacity-60" disabled={busy} type="submit">{busy ? "Tekshirilmoqda..." : "Kirish"}</button>
          </form>
        ) : verificationId ? (
          <form className="mt-6 space-y-4" onSubmit={verifyRegistration}>
            <p className="rounded-xl bg-white/10 p-3 text-sm text-blue-100">Sizning Login ID’ingiz: <strong className="font-mono text-cyan-200">@{issuedLoginId}</strong></p>
            <label className="block text-sm font-bold text-cyan-100">Emailga yuborilgan 6 xonali kod
              <input className="mt-2 w-full rounded-xl border border-white/20 bg-navy-950/50 px-4 py-3 text-center font-mono tracking-[0.4em] text-white outline-none focus:border-cyan-300" value={verificationCode} onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" required />
            </label>
            <button className="w-full rounded-xl bg-cyan-400 px-4 py-3 font-black text-navy-950 transition hover:bg-cyan-300 disabled:opacity-60" disabled={busy || verificationCode.length !== 6} type="submit">{busy ? "Tasdiqlanmoqda..." : "Kod bilan tasdiqlash"}</button>
            <button type="button" className="w-full text-sm font-bold text-cyan-200 underline" onClick={() => { setVerificationId(""); setVerificationCode(""); setMessage(""); }}>Yangi kod so‘rash</button>
          </form>
        ) : (
          <form className="mt-6 space-y-4" onSubmit={startRegistration}>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block text-sm font-bold text-cyan-100">Ism<input className="mt-2 w-full rounded-xl border border-white/20 bg-navy-950/50 px-4 py-3 text-white outline-none focus:border-cyan-300" value={firstName} onChange={(event) => setFirstName(event.target.value)} autoComplete="given-name" required /></label>
              <label className="block text-sm font-bold text-cyan-100">Familiya<input className="mt-2 w-full rounded-xl border border-white/20 bg-navy-950/50 px-4 py-3 text-white outline-none focus:border-cyan-300" value={lastName} onChange={(event) => setLastName(event.target.value)} autoComplete="family-name" /></label>
            </div>
            <label className="block text-sm font-bold text-cyan-100">Email<input className="mt-2 w-full rounded-xl border border-white/20 bg-navy-950/50 px-4 py-3 text-white outline-none focus:border-cyan-300" value={email} onChange={(event) => setEmail(event.target.value)} type="email" autoComplete="email" required /></label>
            <label className="block text-sm font-bold text-cyan-100">Telefon (ixtiyoriy)<input className="mt-2 w-full rounded-xl border border-white/20 bg-navy-950/50 px-4 py-3 text-white outline-none focus:border-cyan-300" value={phone} onChange={(event) => setPhone(event.target.value)} type="tel" autoComplete="tel" /></label>
            <label className="block text-sm font-bold text-cyan-100">Login ID (ixtiyoriy)<input className="mt-2 w-full rounded-xl border border-white/20 bg-navy-950/50 px-4 py-3 text-white outline-none focus:border-cyan-300" value={loginId} onChange={(event) => setLoginId(event.target.value)} autoComplete="username" placeholder="Bo‘sh qoldirsangiz tizim yaratadi" /></label>
            <label className="block text-sm font-bold text-cyan-100">Parol (kamida 8 belgi)<input className="mt-2 w-full rounded-xl border border-white/20 bg-navy-950/50 px-4 py-3 text-white outline-none focus:border-cyan-300" value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="new-password" required minLength={8} /></label>
            <fieldset className="rounded-xl border border-white/15 p-3"><legend className="px-1 text-sm font-bold text-cyan-100">Fanlar</legend>{["English", "Russian"].map((subject) => <label className="mr-4 inline-flex items-center gap-2 text-sm" key={subject}><input type="checkbox" checked={subjects.includes(subject)} onChange={() => toggleSubject(subject)} />{subject === "English" ? "IELTS / English" : "Rus tili"}</label>)}</fieldset>
            <button className="w-full rounded-xl bg-cyan-400 px-4 py-3 font-black text-navy-950 transition hover:bg-cyan-300 disabled:opacity-60" disabled={busy} type="submit">{busy ? "Kod yuborilmoqda..." : "Tasdiqlash kodini yuborish"}</button>
          </form>
        )}

        <a className="mt-6 block text-center text-sm font-bold text-cyan-200 underline" href="/login">Diamond Education boshqa akkaunti bilan kirish</a>
      </section>
    </main>
  );
}
