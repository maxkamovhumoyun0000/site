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
    return <div className="p-8 text-center text-white font-medium">Yuklanmoqda...</div>;
  }

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center p-4" style={{ background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)" }}>
        <div className="w-full max-w-[500px] mx-auto bg-white/5 backdrop-blur-xl border border-red-500/30 rounded-3xl p-8 text-center shadow-2xl">
          <div className="text-4xl mb-4">⚠️</div>
          <h2 className="text-xl font-bold text-red-400 mb-6">{error}</h2>
          <button 
            className="w-full py-3 px-6 rounded-xl font-bold text-white transition-all transform hover:scale-[1.02] active:scale-[0.98]" 
            style={{ background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.2)" }}
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
      <main className="min-h-screen flex items-center justify-center p-4" style={{ background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)" }}>
        <div className="w-full max-w-[500px] mx-auto bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-8 text-center shadow-2xl">
          <div className="text-6xl mb-6">🎉</div>
          <h2 className="text-3xl font-black text-white mb-3">Rahmat!</h2>
          <p className="text-slate-400 mb-8">Sizning javoblaringiz muvaffaqiyatli qabul qilindi.</p>
          <button 
            className="w-full py-3 px-6 rounded-xl font-bold text-white transition-all transform hover:scale-[1.02] active:scale-[0.98]" 
            style={{ background: "linear-gradient(to right, #4f46e5, #6366f1)", boxShadow: "0 4px 14px 0 rgba(99, 102, 241, 0.39)" }}
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
    <main className="min-h-screen flex items-center justify-center p-4" style={{ background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)" }}>
      <div className="w-full max-w-[680px] mx-auto">
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-6 md:p-10 shadow-2xl">
          <div className="text-center mb-8">
            <span className="inline-block px-4 py-1.5 rounded-full text-xs font-bold tracking-wider uppercase mb-4" style={{ background: "rgba(99,102,241,0.2)", color: "#818cf8", border: "1px solid rgba(99,102,241,0.4)" }}>
              📝 So'rovnoma
            </span>
            <h1 className="text-3xl font-black text-white mb-3">{survey.title}</h1>
            {survey.description && <p className="text-slate-400">{survey.description}</p>}
          </div>

          <div className="flex flex-col gap-5 mb-8">
            {questions.map((q: any, i: number) => (
              <div key={q.id} className="p-5 rounded-2xl" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)" }}>
                <h3 className="text-base font-bold text-white mb-4">{i + 1}. {q.text}</h3>
                
                {q.type === "single_choice" ? (
                  <div className="flex flex-col gap-3">
                    {q.options.map((opt: string, oIdx: number) => (
                      <label key={oIdx} className="flex items-center gap-4 p-4 border rounded-xl cursor-pointer transition-all hover:bg-white/5" style={{ background: answers[q.id] === opt ? "rgba(99,102,241,0.2)" : "transparent", border: `1px solid ${answers[q.id] === opt ? "rgba(99,102,241,0.5)" : "rgba(255,255,255,0.1)"}` }}>
                        <input 
                          type="radio" 
                          name={`q_${q.id}`} 
                          value={opt}
                          checked={answers[q.id] === opt}
                          onChange={() => setAnswers(prev => ({ ...prev, [q.id]: opt }))}
                          className="w-5 h-5 text-indigo-500 bg-transparent border-white/20 focus:ring-indigo-500"
                        />
                        <span className="text-sm font-medium" style={{ color: answers[q.id] === opt ? "#fff" : "#cbd5e1" }}>{opt}</span>
                      </label>
                    ))}
                  </div>
                ) : q.type === "multiple_choice" ? (
                  <div className="flex flex-col gap-3">
                    {q.options.map((opt: string, oIdx: number) => {
                      const isChecked = Array.isArray(answers[q.id]) && answers[q.id].includes(opt);
                      return (
                        <label key={oIdx} className="flex items-center gap-4 p-4 border rounded-xl cursor-pointer transition-all hover:bg-white/5" style={{ background: isChecked ? "rgba(99,102,241,0.2)" : "transparent", border: `1px solid ${isChecked ? "rgba(99,102,241,0.5)" : "rgba(255,255,255,0.1)"}` }}>
                          <input 
                            type="checkbox" 
                            name={`q_${q.id}`} 
                            value={opt}
                            checked={isChecked}
                            onChange={() => toggleCheckbox(q.id, opt)}
                            className="w-5 h-5 text-indigo-500 bg-transparent border-white/20 rounded focus:ring-indigo-500"
                          />
                          <span className="text-sm font-medium" style={{ color: isChecked ? "#fff" : "#cbd5e1" }}>{opt}</span>
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
                          className="text-3xl transition-transform hover:scale-125 active:scale-95"
                          style={{ color: selected ? "#f59e0b" : "#475569" }}
                        >
                          ★
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <textarea 
                    className="w-full p-4 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-shadow min-h-[120px] resize-y"
                    placeholder="Javobingizni shu yerga yozing..."
                    value={answers[q.id] || ""}
                    onChange={(e) => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                  />
                )}
              </div>
            ))}
          </div>

          <button 
            className="w-full py-4 px-6 rounded-xl font-bold text-white transition-all transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none disabled:transform-none" 
            style={{ background: "linear-gradient(to right, #4f46e5, #6366f1)", boxShadow: "0 4px 14px 0 rgba(99, 102, 241, 0.39)" }}
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

