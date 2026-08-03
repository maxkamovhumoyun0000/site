"use client";

import React, { useState, useEffect } from "react";
import { useWebT } from "./web-i18n";

export function AdminHomeworkPanel({ data, onApiCall }: any) {
  const tt = useWebT();
  const [teachers, setTeachers] = useState<any[]>([]);
  const [groups, setGroups] = useState<any[]>([]);
  
  const [teacherId, setTeacherId] = useState(0);
  const [groupId, setGroupId] = useState(0);
  
  const [homeworks, setHomeworks] = useState<any[]>([]);
  const [reports, setReports] = useState<Record<number, any>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    async function init() {
      try {
        const d = await onApiCall("/admin/users?role=teacher&limit=500", undefined, "GET");
        if (mounted && d && d.items) setTeachers(d.items);
      } catch (e) {}
      try {
        const d = await onApiCall("/admin/groups", undefined, "GET");
        if (mounted && d && d.items) setGroups(d.items);
      } catch (e) {}
    }
    init();
    return () => { mounted = false; };
  }, [onApiCall]);

  const filteredGroups = groups.filter(g => !teacherId || g.teacher_id === teacherId);

  async function loadHomeworksAndReports(gid: number) {
    if (!gid) {
      setHomeworks([]);
      setReports({});
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await onApiCall(`/admin/homework?group_id=${gid}`, undefined, "GET");
      if (res && res.items) {
        setHomeworks(res.items);
        const newReports: Record<number, any> = {};
        await Promise.all(res.items.map(async (hw: any) => {
          try {
            const rep = await onApiCall(`/admin/homework/${hw.id}/report`, undefined, "GET");
            if (rep && rep.items) {
              newReports[hw.id] = rep.items;
            }
          } catch(e) {}
        }));
        setReports(newReports);
      }
    } catch (err: any) {
      setError(err.message || tt("errors.generic", "Xatolik"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (groupId) {
      loadHomeworksAndReports(groupId);
    } else {
      setHomeworks([]);
      setReports({});
    }
  }, [groupId]);

  return (
    <div className="flex flex-col gap-6 p-4 max-w-6xl mx-auto animate-fade-in">
      <div className="flex flex-col md:flex-row gap-4 items-start md:items-end bg-white dark:bg-[#0f172a] p-6 rounded-2xl shadow-sm border border-line dark:border-white/10">
        <div className="flex-1 flex flex-col gap-2 w-full">
          <label className="text-sm font-bold text-ink-500">{tt("admin.teacher", "O'qituvchi")}</label>
          <select 
            className="w-full px-4 py-3 border border-line dark:border-white/10 rounded-xl bg-surface-soft dark:bg-[#0f172a] outline-none focus:border-cyan-500 font-semibold text-navy-900 dark:text-white" 
            value={teacherId} 
            onChange={e => {
              setTeacherId(parseInt(e.target.value));
              setGroupId(0);
            }}
          >
            <option value={0}>{tt("admin.teacher_select", "O'qituvchini tanlang")}</option>
            {teachers.map(t => <option key={t.id} value={t.id}>{t.full_name || `${t.first_name || ""} ${t.last_name || ""}`.trim() || `O'qituvchi #${t.id}`}</option>)}
          </select>
        </div>
        <div className="flex-1 flex flex-col gap-2 w-full">
          <label className="text-sm font-bold text-ink-500">{tt("admin.group", "Guruh")}</label>
          <select 
            className="w-full px-4 py-3 border border-line dark:border-white/10 rounded-xl bg-surface-soft dark:bg-[#0f172a] outline-none focus:border-cyan-500 font-semibold text-navy-900 dark:text-white" 
            value={groupId} 
            onChange={e => setGroupId(parseInt(e.target.value))}
            disabled={!teacherId}
          >
            <option value={0}>{tt("admin.group_select", "Guruhni tanlang")}</option>
            {filteredGroups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        </div>
      </div>

      {error ? <div className="text-red-500 font-bold bg-red-50 dark:bg-red-500/10 p-4 rounded-xl border border-red-100 dark:border-red-500/20">{error}</div> : null}

      {loading ? (
        <div className="flex justify-center p-10"><div className="w-10 h-10 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin"></div></div>
      ) : groupId ? (
        <div className="flex flex-col gap-6">
          {homeworks.length === 0 ? (
            <div className="bg-white dark:bg-[#0f172a] p-10 text-center rounded-2xl shadow-sm border border-line dark:border-white/10 font-bold text-ink-500">
              {tt("admin.no_homeworks", "Bu guruhda vazifalar topilmadi.")}
            </div>
          ) : (
            homeworks.map(hw => (
              <div key={hw.id} className="bg-white dark:bg-[#0f172a] border border-line dark:border-white/10 rounded-2xl overflow-hidden shadow-premium">
                <div className="p-4 sm:p-6 bg-surface-soft dark:bg-white/5 border-b border-line dark:border-white/10 flex justify-between items-center">
                  <div>
                    <h3 className="font-bold text-lg text-navy-900 dark:text-white">{hw.title}</h3>
                    <p className="text-sm text-ink-500">{tt("common.date", "Sana")}: {(hw.created_at || "").split("T")[0]}</p>
                  </div>
                </div>
                <div className="p-0 overflow-x-auto">
                  <table className="w-full text-left min-w-[500px]">
                    <thead>
                      <tr className="bg-surface-soft dark:bg-white/5 border-b border-line dark:border-white/10 text-xs font-bold text-ink-500 uppercase tracking-wider">
                        <th className="p-4">{tt("admin.student", "O'quvchi")}</th>
                        <th className="p-4">{tt("common.status", "Holat")}</th>
                        <th className="p-4">{tt("admin.submission_time", "Topshirgan vaqti")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line dark:divide-white/5">
                      {(reports[hw.id] || []).map((r: any) => {
                        const status = String(r.submission_status || "").toLowerCase();
                        const isDone = status === "done" || status === "completed";
                        return (
                          <tr key={r.student_id} className="hover:bg-surface-soft/50 dark:hover:bg-white/[0.02] transition-colors">
                            <td className="p-4 font-semibold text-sm text-navy-900 dark:text-white">{r.student_first_name} {r.student_last_name}</td>
                            <td className="p-4">
                              {r.submission_status ? (
                                <span className={`inline-block px-2.5 py-1 rounded-lg text-xs font-bold border ${isDone ? "bg-green-50 text-green-700 border-green-200 dark:bg-green-500/10 dark:text-green-400 dark:border-green-500/20" : "bg-red-50 text-red-700 border-red-200 dark:bg-red-500/10 dark:text-red-400 dark:border-red-500/20"}`}>
                                  {isDone ? tt("status.done", "Qildi") : tt("status.not_done", "Qilmadi")}
                                </span>
                              ) : <span className="inline-block px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/20">{tt("status.pending", "Kutilmoqda (Topshirmagan)")}</span>}
                            </td>
                            <td className="p-4 text-xs text-ink-500 font-medium">{(r.submission_updated_at || "").split(".")[0].replace("T", " ") || "-"}</td>
                          </tr>
                        );
                      })}
                      {(!reports[hw.id] || reports[hw.id].length === 0) && (
                        <tr><td colSpan={3} className="p-4 text-center text-sm text-ink-500">{tt("admin.no_students", "O'quvchilar yo'q")}</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        <div className="text-center p-10 text-ink-500 font-bold bg-white dark:bg-[#0f172a] rounded-2xl shadow-sm border border-line dark:border-white/10">
          {tt("admin.group_select", "Guruhni tanlang")}
        </div>
      )}
    </div>
  );
}
