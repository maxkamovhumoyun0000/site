"use client";

import { useEffect, useState } from "react";
import { useWebT } from "./web-i18n";
import { SectionTitle } from "./primitives";

export function AdminCompetitions() {
  const tt = useWebT();
  const [mode, setMode] = useState("arena-boss");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [selectedSession, setSelectedSession] = useState<any>(null);
  const [sessionResults, setSessionResults] = useState<any[]>([]);
  const [resultsLoading, setResultsLoading] = useState(false);

  const fetchHistory = async (currentMode: string, currentPage: number) => {
    setLoading(true);
    try {
      const token = localStorage.getItem("diamond_token");
      const res = await fetch(`/api/admin/competitions/history?mode=${currentMode}&page=${currentPage}&limit=20`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const json = await res.json();
        setData(json);
      } else {
        console.error("Failed to fetch history");
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory(mode, page);
  }, [mode, page]);

  const fetchResults = async (session: any) => {
    setSelectedSession(session);
    setResultsLoading(true);
    try {
      const token = localStorage.getItem("diamond_token");
      const res = await fetch(`/api/admin/competitions/${session.id}/results?mode=${mode}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const json = await res.json();
        setSessionResults(json.participants || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setResultsLoading(false);
    }
  };

  const closeResults = () => {
    setSelectedSession(null);
    setSessionResults([]);
  };

  return (
    <div className="space-y-6">
      <SectionTitle
        kicker="Natijalar"
        title="Musobaqalar Tarixi"
        subtitle="Boss Arena va duellar natijalarini kuzatib boring."
      />

      {/* TABS */}
      <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
        {[
          { id: "arena-boss", label: "Boss Arena" },
          { id: "duel", label: "Duellar" }
        ].map(m => (
          <button
            key={m.id}
            onClick={() => { setMode(m.id); setPage(1); }}
            className={`whitespace-nowrap px-4 py-2 rounded-xl text-sm font-bold transition-colors ${
              mode === m.id
                ? "bg-navy-900 text-white dark:bg-cyan-500 dark:text-navy-950"
                : "bg-surface text-ink-600 hover:bg-surface-soft border border-line dark:border-white/10 dark:text-slate-300 dark:bg-navy-900/50"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* TABLE */}
      <div className="rounded-2xl border border-line bg-surface overflow-hidden dark:border-white/10 dark:bg-navy-900/50">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-line bg-surface-soft text-ink-500 dark:border-white/10 dark:bg-navy-950/50 dark:text-slate-400">
                <th className="px-4 py-3 font-semibold">ID</th>
                <th className="px-4 py-3 font-semibold">Fan/Mode</th>
                <th className="px-4 py-3 font-semibold">Sana</th>
                <th className="px-4 py-3 font-semibold text-center">Ishtirokchilar</th>
                <th className="px-4 py-3 font-semibold text-right">Amal</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-ink-500 dark:text-slate-400">Yuklanmoqda...</td>
                </tr>
              ) : data?.items?.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-ink-500 dark:text-slate-400">Ma'lumot topilmadi.</td>
                </tr>
              ) : (
                data?.items?.map((item: any) => (
                  <tr key={item.id} className="border-b border-line last:border-0 hover:bg-surface-soft/50 dark:border-white/10 dark:hover:bg-white/5 transition-colors">
                    <td className="px-4 py-3 font-medium text-navy-900 dark:text-white">
                      #{item.id}
                    </td>
                    <td className="px-4 py-3 text-ink-600 dark:text-slate-300">
                      {item.subject || item.level || "-"}
                    </td>
                    <td className="px-4 py-3 text-ink-500 dark:text-slate-400">
                      {item.created_at ? new Date(item.created_at + 'Z').toLocaleString('ru-RU') : "-"}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="inline-flex items-center justify-center min-w-[2rem] rounded-full bg-cyan-100 px-2 py-0.5 text-xs font-bold text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300">
                        {item.participants_count || 0}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => fetchResults(item)}
                        className="text-cyan-600 font-bold hover:underline dark:text-cyan-400"
                      >
                        Ko'rish
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        
        {/* Pagination */}
        {data?.total > 20 && (
          <div className="flex items-center justify-between border-t border-line px-4 py-3 dark:border-white/10">
            <span className="text-sm text-ink-500 dark:text-slate-400">
              Jami: {data.total}
            </span>
            <div className="flex gap-1">
              <button
                disabled={page <= 1}
                onClick={() => setPage(p => p - 1)}
                className="px-3 py-1.5 rounded-lg border border-line text-sm font-medium hover:bg-surface-soft disabled:opacity-50 dark:border-white/10 dark:hover:bg-white/5"
              >
                Orqaga
              </button>
              <button
                disabled={page * 20 >= data.total}
                onClick={() => setPage(p => p + 1)}
                className="px-3 py-1.5 rounded-lg border border-line text-sm font-medium hover:bg-surface-soft disabled:opacity-50 dark:border-white/10 dark:hover:bg-white/5"
              >
                Keyingi
              </button>
            </div>
          </div>
        )}
      </div>

      {/* MODAL */}
      {selectedSession && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-navy-950/60 p-4 backdrop-blur-sm">
          <div className="w-full max-w-3xl max-h-[90vh] overflow-hidden rounded-2xl bg-surface shadow-2xl dark:bg-navy-900 flex flex-col">
            <div className="flex items-center justify-between border-b border-line px-6 py-4 dark:border-white/10">
              <h3 className="text-lg font-black text-navy-900 dark:text-white">
                Natijalar: #{selectedSession.id}
              </h3>
              <button onClick={closeResults} className="text-ink-500 hover:text-ink-700 dark:text-slate-400 dark:hover:text-white text-xl leading-none">
                &times;
              </button>
            </div>
            
            <div className="overflow-y-auto p-6 flex-1">
              {resultsLoading ? (
                <div className="text-center py-8 text-ink-500">Yuklanmoqda...</div>
              ) : sessionResults.length === 0 ? (
                <div className="text-center py-8 text-ink-500">Ishtirokchilar topilmadi.</div>
              ) : (
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-line bg-surface-soft text-ink-500 dark:border-white/10 dark:bg-navy-950/50">
                      <th className="px-4 py-2">O'quvchi</th>
                      <th className="px-4 py-2 text-center text-green-600">To'g'ri</th>
                      <th className="px-4 py-2 text-center text-red-600">Xato</th>
                      <th className="px-4 py-2 text-center text-yellow-600">Tashlab ketilgan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sessionResults.map((r, i) => (
                      <tr key={i} className="border-b border-line last:border-0 hover:bg-surface-soft/30 dark:border-white/10">
                        <td className="px-4 py-3 font-medium text-navy-900 dark:text-white">
                          {r.first_name} {r.last_name}
                          {r.login_id && <span className="block text-[11px] text-ink-500 font-normal">@{r.login_id}</span>}
                        </td>
                        <td className="px-4 py-3 text-center font-bold text-green-600 dark:text-green-400">
                          {r.correct_count || 0}
                        </td>
                        <td className="px-4 py-3 text-center font-bold text-red-600 dark:text-red-400">
                          {r.wrong_count || 0}
                        </td>
                        <td className="px-4 py-3 text-center font-bold text-yellow-600 dark:text-yellow-400">
                          {r.skipped_count || 0}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
