"use client";

import React, { useState, useEffect } from "react";

type GenericRow = any;

export function StudentSurveyScreen({
  user,
  surveyId,
  onFinish,
}: {
  user: any;
  surveyId: string;
  onFinish: () => void;
}) {
  const [survey, setSurvey] = useState<GenericRow | null>(null);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (typeof window !== "undefined" && !(window as any).Telegram?.WebApp) {
      const script = document.createElement("script");
      script.src = "https://telegram.org/js/telegram-web-app.js";
      script.integrity = "sha384-PyI6uk8O3pfRRl4+CaepaS++FqtEbco/HaV3jzdYl4y+U7HMQvn3gWVfKhjuzfzG";
      script.crossOrigin = "anonymous";
      script.async = true;
      document.head.appendChild(script);
    }
    loadSurvey();
  }, [surveyId]);


  async function loadSurvey() {
    setLoading(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("diamond_token") : null;
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`/api/survey/${surveyId}`, { headers });
      const data = await res.json();
      if (data.survey) {
        setSurvey(data.survey);
        if (data.has_responded) {
          setSubmitted(true);
        }
      } else {
        setError("So'rovnoma topilmadi yoki yopilgan");
      }
    } catch (e) {
      setError("Xatolik yuz berdi");
    }
    setLoading(false);
  }

  async function submitSurvey() {
    setLoading(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("diamond_token") : null;
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      let telegram_user = null;
      if (typeof window !== "undefined" && (window as any).Telegram?.WebApp?.initDataUnsafe?.user) {
        telegram_user = (window as any).Telegram.WebApp.initDataUnsafe.user;
      }

      const res = await fetch(`/api/survey/${surveyId}/submit`, {
        method: "POST",
        headers,
        body: JSON.stringify({ answers, telegram_user }),
      });
      if (res.ok) {
        setSubmitted(true);
      } else {
        const err = await res.json();
        setError(err.detail || "Xatolik yuz berdi");
      }
    } catch (e) {
      setError("Xatolik yuz berdi");
    }
    setLoading(false);
  }

  if (loading && !survey) {
    return <main className="min-h-screen bg-white p-8 text-center font-medium text-slate-700">Yuklanmoqda...</main>;
  }

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-white p-4">
        <div className="w-full max-w-[500px] mx-auto rounded-3xl border border-red-200 bg-white p-8 text-center shadow-xl shadow-slate-200/60">
          <div className="text-4xl mb-4">⚠️</div>
          <h2 className="text-xl font-bold text-red-700 mb-6">{error}</h2>
          <button 
            className="w-full rounded-xl border border-slate-200 bg-slate-50 px-6 py-3 font-bold text-slate-800 transition-all hover:bg-slate-100 active:scale-[0.98]"
            onClick={onFinish}
          >
            Asosiy sahifaga qaytish
          </button>
        </div>
      </main>
    );
  }

  if (submitted) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-white p-4">
        <div className="w-full max-w-[500px] mx-auto rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-xl shadow-slate-200/60">
          <div className="text-6xl mb-6">🎉</div>
          <h2 className="text-3xl font-black text-slate-900 mb-3">Rahmat!</h2>
          <p className="text-slate-600 mb-8">Sizning javoblaringiz muvaffaqiyatli qabul qilindi.</p>
          <button 
            className="w-full rounded-xl bg-indigo-600 px-6 py-3 font-bold text-white shadow-lg shadow-indigo-600/20 transition-all hover:bg-indigo-700 active:scale-[0.98]"
            onClick={onFinish}
          >
            Asosiy sahifaga o'tish →
          </button>
        </div>
      </main>
    );
  }

  if (!survey) return null;

  let questions: any[] = [];
  try {
    questions = JSON.parse(String(survey.questions_json || "[]"));
  } catch (e) {}

  const allAnswered = questions.every((q: any) => {
    const val = answers[q.id];
    if (Array.isArray(val)) return val.length > 0;
    if (typeof val === "number") return val > 0;
    return String(val || "").trim().length > 0;
  });

  const toggleCheckbox = (qId: string, opt: string) => {
    setAnswers((prev) => {
      const current: string[] = Array.isArray(prev[qId]) ? [...prev[qId]] : [];
      const idx = current.indexOf(opt);
      if (idx >= 0) {
        current.splice(idx, 1);
      } else {
        current.push(opt);
      }
      return { ...prev, [qId]: current };
    });
  };

  return (
    <main className="min-h-screen flex items-center justify-center bg-white p-4">
      <div className="w-full max-w-[680px] mx-auto">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-200/60 md:p-10">
          <div className="text-center mb-8">
            <span className="mb-4 inline-block rounded-full border border-indigo-100 bg-indigo-50 px-4 py-1.5 text-xs font-bold uppercase tracking-wider text-indigo-700">
              📝 So'rovnoma
            </span>
            <h1 className="mb-3 text-3xl font-black text-slate-900">{survey.title}</h1>
            {survey.description && <p className="text-slate-600">{survey.description}</p>}
          </div>

          <div className="flex flex-col gap-5 mb-8">
            {questions.map((q: any, i: number) => (
              <div key={q.id} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-5">
                <h3 className="mb-4 text-base font-bold text-slate-900">{i + 1}. {q.text}</h3>
                
                {q.type === "single_choice" ? (
                  <div className="flex flex-col gap-3">
                    {q.options.map((opt: string, oIdx: number) => (
                      <label key={oIdx} className={`flex cursor-pointer items-center gap-4 rounded-xl border p-4 transition-all ${answers[q.id] === opt ? "border-indigo-300 bg-indigo-50" : "border-slate-200 bg-white hover:bg-slate-50"}`}>
                        <input 
                          type="radio" 
                          name={`q_${q.id}`} 
                          value={opt}
                          checked={answers[q.id] === opt}
                          onChange={() => setAnswers(prev => ({ ...prev, [q.id]: opt }))}
                          className="h-5 w-5 border-slate-300 bg-white text-indigo-600 focus:ring-indigo-500"
                        />
                        <span className="text-sm font-medium text-slate-700">{opt}</span>
                      </label>
                    ))}
                  </div>
                ) : q.type === "multiple_choice" ? (
                  <div className="flex flex-col gap-3">
                    {q.options.map((opt: string, oIdx: number) => {
                      const isChecked = Array.isArray(answers[q.id]) && answers[q.id].includes(opt);
                      return (
                        <label key={oIdx} className={`flex cursor-pointer items-center gap-4 rounded-xl border p-4 transition-all ${isChecked ? "border-indigo-300 bg-indigo-50" : "border-slate-200 bg-white hover:bg-slate-50"}`}>
                          <input 
                            type="checkbox" 
                            name={`q_${q.id}`} 
                            value={opt}
                            checked={isChecked}
                            onChange={() => toggleCheckbox(q.id, opt)}
                            className="h-5 w-5 rounded border-slate-300 bg-white text-indigo-600 focus:ring-indigo-500"
                          />
                          <span className="text-sm font-medium text-slate-700">{opt}</span>
                        </label>
                      );
                    })}
                  </div>
                ) : q.type === "rating" ? (
                  <div className="flex items-center justify-center gap-3 py-2">
                    {[1, 2, 3, 4, 5].map((star) => {
                      const selected = (answers[q.id] || 0) >= star;
                      return (
                        <button
                          key={star}
                          type="button"
                          onClick={() => setAnswers(prev => ({ ...prev, [q.id]: star }))}
                          className={`text-3xl transition-transform hover:scale-125 active:scale-95 ${selected ? "text-amber-500" : "text-slate-300"}`}
                        >
                          ★
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <textarea 
                    className="min-h-[120px] w-full resize-y rounded-xl border border-slate-300 bg-white p-4 text-slate-900 outline-none transition-shadow placeholder:text-slate-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                    placeholder="Javobingizni shu yerga yozing..."
                    value={answers[q.id] || ""}
                    onChange={(e) => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                  />
                )}
              </div>
            ))}
          </div>

          <button 
            className="w-full rounded-xl bg-indigo-600 px-6 py-4 font-bold text-white shadow-lg shadow-indigo-600/20 transition-all hover:bg-indigo-700 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 disabled:transform-none"
            disabled={!allAnswered || loading}
            onClick={submitSurvey}
          >
            {loading ? "Yuborilmoqda..." : "Javoblarni Yuborish →"}
          </button>
        </div>
      </div>
    </main>
  );
}

