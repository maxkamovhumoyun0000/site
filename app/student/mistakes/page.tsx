"use client";
import { useEffect, useState } from "react";

export default function MistakesPage() {
  const [due, setDue] = useState<any[]>([]);
  const [all, setAll] = useState<any[]>([]);
  const [current, setCurrent] = useState<any>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const [dueRes, allRes] = await Promise.all([
      fetch("/api/student/mistakes/due").then(r => r.json()),
      fetch("/api/student/mistakes").then(r => r.json()),
    ]);
    setDue(dueRes.items || []);
    setAll(allRes.items || []);
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  function startQuiz(item: any) { setCurrent(item); setSelected(null); setResult(null); }

  async function answer(opt: string) {
    if (selected) return;
    setSelected(opt);
    const correct = opt === current.correct_answer;
    setResult(correct);
    await fetch(`/api/student/mistakes/${current.id}/answer`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ correct }),
    });
    setTimeout(() => { setCurrent(null); load(); }, 1500);
  }

  const opts: string[] = current ? (JSON.parse(current.options_json || "[]") || []) : [];

  if (current) return (
    <main className="min-h-screen p-6 bg-white dark:bg-gray-900 flex items-center justify-center">
      <div className="max-w-xl w-full bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-6">
        <p className="text-sm text-blue-600 dark:text-blue-400 font-medium mb-3">Xatolar daftari — Qayta tekshirish</p>
        <p className="text-lg font-semibold text-gray-900 dark:text-white mb-6">{current.prompt}</p>
        <div className="space-y-2">
          {opts.map((o: string) => {
            const isCorrect = o === current.correct_answer;
            const isSelected = o === selected;
            let cls = "w-full text-left p-3 rounded-xl border-2 transition font-medium ";
            if (!selected) cls += "border-gray-200 dark:border-gray-600 hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 text-gray-800 dark:text-gray-200";
            else if (isCorrect) cls += "border-green-500 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400";
            else if (isSelected) cls += "border-red-500 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400";
            else cls += "border-gray-200 dark:border-gray-600 text-gray-400 dark:text-gray-500";
            return <button key={o} className={cls} onClick={() => answer(o)}>{o}</button>;
          })}
        </div>
        {result !== null && (
          <p className={`mt-4 text-center font-semibold text-lg ${result ? "text-green-600" : "text-red-600"}`}>
            {result ? "✓ To'g'ri!" : "✗ Xato"}
          </p>
        )}
      </div>
    </main>
  );

  return (
    <main className="min-h-screen p-6 bg-white dark:bg-gray-900">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">📒 Xatolar Daftari</h1>
        {loading ? <p className="text-center text-gray-500 dark:text-gray-400 py-12">Yuklanmoqda...</p> : (
          <>
            {due.length > 0 && (
              <section className="mb-8">
                <h2 className="text-lg font-semibold text-gray-800 dark:text-white mb-3">🔔 Bugun ko'rish kerak ({due.length})</h2>
                <div className="space-y-2">
                  {due.map((item: any) => (
                    <div key={item.id} className="flex items-center justify-between p-4 bg-orange-50 dark:bg-orange-900/10 border border-orange-200 dark:border-orange-800 rounded-xl">
                      <p className="text-gray-800 dark:text-gray-200 text-sm flex-1 mr-4 line-clamp-2">{item.prompt}</p>
                      <button onClick={() => startQuiz(item)} className="px-4 py-1.5 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-sm font-medium transition flex-shrink-0">Boshlash</button>
                    </div>
                  ))}
                </div>
              </section>
            )}
            <section>
              <h2 className="text-lg font-semibold text-gray-800 dark:text-white mb-3">📚 Barcha xatolar ({all.length})</h2>
              {all.length === 0 ? (
                <p className="text-center text-gray-500 dark:text-gray-400 py-8">Hozircha xato yo'q 🎉</p>
              ) : (
                <div className="space-y-2">
                  {all.map((item: any) => (
                    <div key={item.id} className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl">
                      <div className="flex-1 mr-4">
                        <p className="text-sm text-gray-800 dark:text-gray-200 line-clamp-1">{item.prompt}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">{item.subject} • Streak: {item.correct_streak}</p>
                      </div>
                      <button onClick={() => startQuiz(item)} className="px-3 py-1 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-lg text-xs font-medium transition">Tekshir</button>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </main>
  );
}
