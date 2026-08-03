"use client";

import React, { useEffect, useState } from "react";
import { useWebT } from "./web-i18n";

type AttendanceItem = {
  id: number;
  user_id: number;
  group_id: number;
  date: string;
  status: string;
  created_at: string;
  group_name?: string;
};

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number) {
  let day = new Date(year, month, 1).getDay();
  return day === 0 ? 6 : day - 1; // 0=Mon, 6=Sun
}

export function StudentAttendance() {
  const tt = useWebT();
  const [items, setItems] = useState<AttendanceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedGroupId, setSelectedGroupId] = useState<string>("all");

  async function requestJson<T>(path: string, options?: { token?: string | null; method?: string }): Promise<T> {
    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
    const headers: Record<string, string> = {};
    if (options?.token) headers["Authorization"] = `Bearer ${options.token}`;
    const res = await fetch(`${API_BASE}${path}`, {
      method: options?.method || "GET",
      headers,
    });
    if (!res.ok) {
      let errText = tt("errors.generic", "Xatolik");
      try { errText = (await res.json())?.detail || errText; } catch (e) {}
      throw new Error(errText);
    }
    return res.json();
  }

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const res = await requestJson<{ items: AttendanceItem[] }>("/student/attendance", {
          token: localStorage.getItem("diamond_token") || "",
        });
        if (mounted && res && res.items) {
          setItems(res.items);
        }
      } catch (err: any) {
        if (mounted) setError(err.message || tt("errors.occurred", "Xatolik yuz berdi"));
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => { mounted = false; };
  }, []);

  // 1. Get unique groups
  const groups = React.useMemo(() => {
    const map = new Map<number, string>();
    items.forEach(item => {
      if (item.group_id) {
        map.set(item.group_id, item.group_name || `Guruh #${item.group_id}`);
      }
    });
    return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
  }, [items]);

  // 2. Filter items by selected group
  const filteredItems = React.useMemo(() => {
    if (selectedGroupId === "all") return items;
    return items.filter(i => String(i.group_id) === selectedGroupId);
  }, [items, selectedGroupId]);

  // 3. Group by YYYY-MM
  const monthsData: Record<string, Record<number, AttendanceItem>> = {};
  filteredItems.forEach(item => {
    if (!item.date) return;
    const parts = item.date.split(" ")[0].split("-");
    if (parts.length >= 3) {
      const ym = `${parts[0]}-${parts[1]}`;
      const day = parseInt(parts[2], 10);
      if (!monthsData[ym]) monthsData[ym] = {};
      if (!monthsData[ym][day]) monthsData[ym][day] = item;
    }
  });

  const sortedMonths = Object.keys(monthsData).sort((a, b) => b.localeCompare(a));


  return (
    <div className="flex flex-col gap-6 animate-fade-in p-4 sm:p-6 md:p-8 max-w-5xl mx-auto">
      <div className="flex flex-col gap-2">
        {groups.length > 0 && (
          <div className="mt-4">
            <label className="text-xs font-bold text-ink-500 dark:text-navy-400 uppercase tracking-wider mb-2 block">Guruhni tanlang:</label>
            <select
              value={selectedGroupId}
              onChange={(e) => setSelectedGroupId(e.target.value)}
              className="w-full sm:max-w-xs px-4 py-3 rounded-xl border border-line dark:border-white/10 bg-white dark:bg-navy-900 text-navy-900 dark:text-white font-semibold outline-none focus:ring-2 focus:ring-cyan-500"
            >
              <option value="all">Barcha guruhlar</option>
              {groups.map(g => (
                <option key={g.id} value={String(g.id)}>{g.name}</option>
              ))}
            </select>
          </div>
        )}

        <div className="flex flex-wrap gap-4 mt-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-navy-900 dark:text-white"><div className="w-4 h-4 rounded bg-green-500"></div>{tt("status.keldi", "Keldi")}</div>
          <div className="flex items-center gap-2 text-xs font-semibold text-navy-900 dark:text-white"><div className="w-4 h-4 rounded bg-amber-400"></div>{tt("status.sababli", "Sababli")}</div>
          <div className="flex items-center gap-2 text-xs font-semibold text-navy-900 dark:text-white"><div className="w-4 h-4 rounded bg-red-500"></div>{tt("status.sababsiz", "Sababsiz")}</div>
          <div className="flex items-center gap-2 text-xs font-semibold text-navy-900 dark:text-white"><div className="w-4 h-4 rounded bg-red-900"></div>{tt("status.holiday", "Bayram")}</div>
        </div>
      </div>

      {error ? (
        <div className="p-4 rounded-xl bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400 border border-red-100 dark:border-red-500/20 text-sm font-semibold">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="flex justify-center py-20"><div className="w-10 h-10 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin" /></div>
      ) : (
        <div className="flex flex-col gap-8">
          {sortedMonths.length === 0 ? (
            <div className="p-8 text-center bg-white dark:bg-navy-900/50 rounded-2xl border border-line dark:border-white/5 text-ink-500 dark:text-navy-400 font-bold">
              {tt("common.no_data", "Ma'lumot topilmadi")}
            </div>
          ) : (
            sortedMonths.map(ym => {
              const [yStr, mStr] = ym.split("-");
              const year = parseInt(yStr, 10);
              const month = parseInt(mStr, 10) - 1;
              const daysInMonth = getDaysInMonth(year, month);
              const firstDay = getFirstDayOfMonth(year, month);
              const dayCells = [];
              for (let i = 0; i < firstDay; i++) {
                dayCells.push(<div key={`empty-${i}`} className="aspect-square opacity-0"></div>);
              }
              for (let d = 1; d <= daysInMonth; d++) {
                const item = monthsData[ym][d];
                let bgClass = "bg-surface-soft dark:bg-white/5 border border-line dark:border-white/10 text-ink-600 dark:text-navy-300"; // default empty
                if (item) {
                  const st = String(item.status || "").toLowerCase();
                  if (st === "present" || st === "keldi") bgClass = "bg-green-500 text-white font-bold shadow-md border-transparent";
                  else if (st === "excused" || st === "sababli") bgClass = "bg-amber-400 text-navy-900 font-bold shadow-md border-transparent";
                  else if (st === "holiday" || st === "bayram") bgClass = "bg-red-900 text-white font-bold shadow-md border-transparent";
                  else bgClass = "bg-red-500 text-white font-bold shadow-md border-transparent"; // absent
                }
                
                dayCells.push(
                  <div key={`day-${d}`} className={`aspect-square flex flex-col items-center justify-center rounded-xl text-sm transition-all hover:scale-105 ${bgClass}`} title={item ? item.group_name || "" : ""}>
                    <span>{d}</span>
                  </div>
                );
              }

              return (
                <div key={ym} className="bg-white dark:bg-[#0f172a] border border-line dark:border-white/10 rounded-2xl overflow-hidden shadow-premium p-6">
                  <h3 className="text-xl font-bold text-navy-900 dark:text-white mb-6 font-display">{ym}</h3>
                  <div className="grid grid-cols-7 gap-2 sm:gap-4 mb-2 text-center text-xs font-bold text-ink-500 dark:text-navy-400 uppercase">
                    <div>{tt("weekday.mo", "Du")}</div>
                    <div>{tt("weekday.tu", "Se")}</div>
                    <div>{tt("weekday.we", "Ch")}</div>
                    <div>{tt("weekday.th", "Pa")}</div>
                    <div>{tt("weekday.fr", "Ju")}</div>
                    <div>{tt("weekday.sa", "Sh")}</div>
                    <div>{tt("weekday.su", "Ya")}</div>
                  </div>
                  <div className="grid grid-cols-7 gap-2 sm:gap-4">
                    {dayCells}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
