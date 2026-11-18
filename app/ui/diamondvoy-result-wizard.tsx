"use client";

import React, { useEffect, useRef, useState } from "react";

type Draft = {
  step: "image" | "name" | "certificate" | "done";
  image_url?: string;
  image_analysis?: string;
  student_name?: string;
  result_type?: "IELTS" | "CEFR" | "Milliy Sertifikat" | "Boshqa sertifikat";
  subject?: string;
  score_text?: string;
  certificate_name?: string;
  description?: string;
  result_id?: number;
};

type ApiFetch = (path: string, options?: any) => Promise<any>;
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

export function DiamondvoyResultWizard({ chatId, wizardId, apiFetch }: { chatId: number; wizardId: string; apiFetch: ApiFetch }) {
  const path = `/chats/diamondvoy/${chatId}/result-wizards/${wizardId}`;
  const [state, setState] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const queue = useRef<Promise<void>>(Promise.resolve());
  const stateRef = useRef<Draft | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latest = (value: Draft) => { stateRef.current = value; setState(value); };

  useEffect(() => {
    let active = true;
    apiFetch(path).then((result: any) => {
      if (!active) return;
      let loaded: Draft = result.state;
      const pending = localStorage.getItem(`diamondvoy-result-draft:${wizardId}`);
      if (pending && loaded.step !== "image" && loaded.step !== "done") {
        try {
          const local = JSON.parse(pending) as Partial<Draft>;
          loaded = { ...loaded, ...local };
          saveDraft(loaded).catch(() => undefined);
        } catch { localStorage.removeItem(`diamondvoy-result-draft:${wizardId}`); }
      } else if (loaded.step === "done") localStorage.removeItem(`diamondvoy-result-draft:${wizardId}`);
      latest(loaded);
    })
      .catch((err: any) => { if (active) setError(err.message || "Wizard yuklanmadi"); });
    return () => { active = false; };
  }, [path, apiFetch]);

  function saveDraft(draft: Draft) {
    if (draft.step !== "name" && draft.step !== "certificate") return Promise.resolve();
    const body = { step: draft.step, student_name: draft.student_name || "", result_type: draft.result_type || "IELTS", subject: draft.subject || "", score_text: draft.score_text || "", certificate_name: draft.certificate_name || "" };
    queue.current = queue.current.catch(() => undefined).then(async () => {
      await apiFetch(`${path}/draft`, { method: "POST", body });
      const key = `diamondvoy-result-draft:${wizardId}`;
      if (localStorage.getItem(key) === JSON.stringify(body)) localStorage.removeItem(key);
    }).catch((err: any) => { setError(err.message || "Qoralama saqlanmadi"); throw err; });
    return queue.current;
  }

  function change(patch: Partial<Draft>) {
    const current = stateRef.current;
    if (!current) return;
    const next = { ...current, ...patch };
    latest(next);
    if (next.step === "name" || next.step === "certificate") localStorage.setItem(`diamondvoy-result-draft:${wizardId}`, JSON.stringify({ step: next.step, student_name: next.student_name || "", result_type: next.result_type || "IELTS", subject: next.subject || "", score_text: next.score_text || "", certificate_name: next.certificate_name || "" }));
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => { saveDraft(next).catch(() => undefined); }, 500);
  }

  async function upload(file: File) {
    setBusy(true); setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const token = localStorage.getItem("diamond_token") || "";
      const response = await fetch(`${apiBase}${path}/image`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Rasm yuklanmadi");
      latest(data.state);
    } catch (err: any) { setError(err.message || "Rasm yuklanmadi"); }
    finally { setBusy(false); }
  }

  async function next() {
    if (!stateRef.current) return;
    if ((stateRef.current.student_name || "").trim().split(/\s+/).filter(Boolean).length < 2) { setError("Ism va familiyani kiriting."); return; }
    setBusy(true); setError("");
    try {
      if (timer.current) clearTimeout(timer.current);
      const draft = { ...stateRef.current, step: "certificate" as const };
      localStorage.setItem(`diamondvoy-result-draft:${wizardId}`, JSON.stringify({ step: draft.step, student_name: draft.student_name || "", result_type: draft.result_type || "IELTS", subject: draft.subject || "", score_text: draft.score_text || "", certificate_name: draft.certificate_name || "" }));
      await saveDraft(draft);
      latest(draft);
    } catch {} finally { setBusy(false); }
  }

  async function publish() {
    if (!stateRef.current) return;
    const draft = stateRef.current;
    if (!(draft.subject || "").trim() || (draft.result_type === "Boshqa sertifikat" && !(draft.certificate_name || "").trim())) { setError("Fan va sertifikat nomini kiriting."); return; }
    setBusy(true); setError("");
    try {
      if (timer.current) clearTimeout(timer.current);
      await saveDraft(draft);
      const result = await apiFetch(`${path}/publish`, { method: "POST", body: { student_name: draft.student_name || "", result_type: draft.result_type || "IELTS", subject: draft.subject || "", score_text: draft.score_text || "", certificate_name: draft.certificate_name || "" }, timeoutMs: 90000 });
      localStorage.removeItem(`diamondvoy-result-draft:${wizardId}`);
      latest(result.state);
    } catch (err: any) { setError(err.message || "Natija joylanmadi"); }
    finally { setBusy(false); }
  }

  const input = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-navy-700 dark:bg-navy-950 dark:text-white";
  const button = "rounded-xl bg-blue-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-50";
  return <div className="space-y-4 rounded-2xl border-2 border-cyan-200 bg-white p-4 text-slate-900 shadow-sm dark:border-cyan-900 dark:bg-navy-900 dark:text-white">
    <h4 className="font-black">💎 Natija qo‘shish</h4>
    {!state && !error && <p className="text-sm">Yuklanmoqda…</p>}
    {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
    {state?.step === "image" && <label className="block text-sm font-semibold">Sertifikat rasmini yuklang
      <input className={input} type="file" accept="image/*" disabled={busy} onChange={(event) => { const file = event.target.files?.[0]; if (file) upload(file); }} />
      <span className="mt-1 block text-xs">Rasm WebP formatiga o‘tkaziladi va AI orqali tahlil qilinadi.</span>
    </label>}
    {busy && <p className="text-sm">Bajarilmoqda…</p>}
    {state?.step === "name" && <>
      {state.image_analysis && <p className="whitespace-pre-wrap rounded-xl bg-slate-100 p-3 text-sm dark:bg-navy-950">Rasmdan aniq ko‘ringan ma’lumotlar:{"\n"}{state.image_analysis}</p>}
      <label className="block text-sm font-semibold">O‘quvchining ism va familiyasi<input className={input} value={state.student_name || ""} onChange={(event) => change({ student_name: event.target.value })} /></label>
      <button type="button" className={button} disabled={busy} onClick={next}>Davom etish</button>
    </>}
    {state?.step === "certificate" && <>
      <label className="block text-sm font-semibold">Ism va familiya<input className={input} value={state.student_name || ""} onChange={(event) => change({ student_name: event.target.value })} /></label>
      <label className="block text-sm font-semibold">Sertifikat turi<select className={input} value={state.result_type || "IELTS"} onChange={(event) => change({ result_type: event.target.value as Draft["result_type"] })}><option>IELTS</option><option>CEFR</option><option>Milliy Sertifikat</option><option>Boshqa sertifikat</option></select></label>
      {state.result_type === "Boshqa sertifikat" && <label className="block text-sm font-semibold">Sertifikat nomi<input className={input} value={state.certificate_name || ""} onChange={(event) => change({ certificate_name: event.target.value })} /></label>}
      <label className="block text-sm font-semibold">Fan<input className={input} value={state.subject || ""} onChange={(event) => change({ subject: event.target.value })} placeholder="Masalan, ingliz tili yoki matematika" /></label>
      <label className="block text-sm font-semibold">Ball yoki daraja (ixtiyoriy)<input className={input} value={state.score_text || ""} onChange={(event) => change({ score_text: event.target.value })} /></label>
      <button type="button" className={button} disabled={busy} onClick={publish}>Natijani joylash</button>
    </>}
    {state?.step === "done" && <><p className="text-sm font-bold text-green-700">Natija joylandi.</p><p className="text-sm">{state.description}</p><a className="text-sm font-bold text-blue-600 underline" href={`/results/${state.result_id}`} target="_blank" rel="noreferrer">Natijani ko‘rish</a></>}
  </div>;
}
