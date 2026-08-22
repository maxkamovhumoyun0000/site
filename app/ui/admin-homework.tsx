"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useWebT } from "./web-i18n";

/* ─────────────────────────── helpers ─────────────────────────── */
function fmtDate(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(iso.replace(" ", "T"));
  if (isNaN(d.getTime())) return iso.split("T")[0] || iso;
  return d.toLocaleString("uz-UZ", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}
function fmtDay(iso: string | null | undefined) {
  if (!iso) return "—";
  return iso.split("T")[0].split(" ")[0] || iso;
}

/* ─────────────────────────── types ───────────────────────────── */
type Hw = {
  id: number; title: string; description?: string; subject?: string;
  group_id?: number; group_name?: string; teacher_name?: string;
  created_at?: string; due_date?: string; due_at?: string;
  homework_kind?: string; requires_file?: boolean; requires_voice_message?: boolean;
  is_voiceroom?: boolean;
};
type StudentRow = {
  student_id: number; student_first_name?: string; student_last_name?: string;
  submission_status?: string; submission_created_at?: string;
  submission_updated_at?: string; uploaded?: boolean;
  student_note?: string; test_available?: boolean; test_completed?: boolean;
  test_correct_count?: number; test_total_questions?: number;
  test_dpoints_delta?: number; reviewed_at?: string;
  review_dpoint_delta?: number; review_note?: string;
  deadline_missed?: boolean;
};
type Filter = "all" | "done" | "not_done" | "pending";
type SortMode = "last_submission" | "created_at" | "title";

/* ─────────────────────────── main ────────────────────────────── */
export function AdminHomeworkPanel({ data, onApiCall }: any) {
  const tt = useWebT();

  /* filters */
  const [teacherId, setTeacherId] = useState(0);
  const [groupId, setGroupId] = useState(0);

  /* data */
  const [teachers, setTeachers] = useState<any[]>([]);
  const [groups, setGroups] = useState<any[]>([]);
  const [homeworks, setHomeworks] = useState<Hw[]>([]);
  const [reports, setReports] = useState<Record<number, StudentRow[]>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  /* UI state */
  const [sortMode, setSortMode] = useState<SortMode>("last_submission");
  const [statusFilter, setStatusFilter] = useState<Filter>("all");
  const [expandedHw, setExpandedHw] = useState<number | null>(null);

  /* init */
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const d = await onApiCall("/admin/users?role=teacher&limit=500", undefined, "GET");
        if (mounted && d?.items) setTeachers(d.items);
      } catch {}
      try {
        const d = await onApiCall("/admin/groups", undefined, "GET");
        if (mounted && d?.items) setGroups(d.items);
      } catch {}
    })();
    return () => { mounted = false; };
  }, [onApiCall]);

  const filteredGroups = groups.filter(g => !teacherId || g.teacher_id === teacherId);

  /* load */
  const load = useCallback(async (gid: number) => {
    if (!gid) { setHomeworks([]); setReports({}); return; }
    setLoading(true); setError("");
    try {
      const res = await onApiCall(`/admin/homework?group_id=${gid}`, undefined, "GET");
      const hws: Hw[] = res?.items || [];
      setHomeworks(hws);
      const newReports: Record<number, StudentRow[]> = {};
      await Promise.all(hws.map(async (hw) => {
        try {
          const rep = await onApiCall(`/admin/homework/${hw.id}/report`, undefined, "GET");
          if (rep?.items) newReports[hw.id] = rep.items;
        } catch {}
      }));
      setReports(newReports);
    } catch (err: any) {
      setError(err.message || "Xatolik");
    } finally {
      setLoading(false);
    }
  }, [onApiCall]);

  useEffect(() => {
    if (groupId) load(groupId);
    else { setHomeworks([]); setReports({}); }
  }, [groupId, load]);

  /* sort */
  function lastActivity(hw: Hw): string {
    const rows = reports[hw.id] || [];
    const times = rows.map(r => r.submission_updated_at || r.submission_created_at || "").filter(Boolean);
    return times.sort().reverse()[0] || hw.created_at || "";
  }

  const sorted = [...homeworks].sort((a, b) => {
    if (sortMode === "last_submission") return lastActivity(b).localeCompare(lastActivity(a));
    if (sortMode === "created_at") return (b.created_at || "").localeCompare(a.created_at || "");
    return a.title.localeCompare(b.title);
  });

  /* status helpers */
  function rowStatus(r: StudentRow): "done" | "not_done" | "pending" {
    const s = String(r.submission_status || "").toLowerCase();
    if (s === "done" || s === "completed" || s === "reviewed") return "done";
    if (s === "not_done" || s === "missed" || r.deadline_missed) return "not_done";
    if (s === "submitted") return "done"; // submitted counts as done for filter
    return "pending";
  }

  function hwMatchesFilter(hw: Hw): boolean {
    if (statusFilter === "all") return true;
    const rows = reports[hw.id] || [];
    return rows.some(r => rowStatus(r) === statusFilter);
  }

  const filtered = sorted.filter(hwMatchesFilter);

  /* summary counts */
  function counts(hwId: number) {
    const rows = reports[hwId] || [];
    const done = rows.filter(r => rowStatus(r) === "done").length;
    const notDone = rows.filter(r => rowStatus(r) === "not_done").length;
    const pending = rows.filter(r => rowStatus(r) === "pending").length;
    return { done, notDone, pending, total: rows.length };
  }

  /* kind label */
  function kindLabel(hw: Hw) {
    if (hw.is_voiceroom) return "🎙 Voiceroom";
    if (hw.homework_kind === "test") return "📝 Test";
    if (hw.requires_file) return "📎 Fayl";
    if (hw.requires_voice_message) return "🎤 Ovoz";
    return "📄 Oddiy";
  }

  return (
    <div className="flex flex-col gap-6 p-4 max-w-6xl mx-auto animate-fade-in">
      {/* ── Filters ── */}
      <div className="bg-white dark:bg-[#0f172a] p-6 rounded-2xl shadow-sm border border-line dark:border-white/10 flex flex-col gap-4">
        <div className="flex flex-col md:flex-row gap-4">
          {/* Teacher */}
          <div className="flex-1 flex flex-col gap-1.5">
            <label className="text-xs font-bold text-ink-500 uppercase tracking-wider">{tt("admin.teacher", "O'qituvchi")}</label>
            <select
              className="w-full px-4 py-3 border border-line dark:border-white/10 rounded-xl bg-surface-soft dark:bg-[#0f172a] outline-none focus:border-cyan-500 font-semibold text-navy-900 dark:text-white"
              value={teacherId}
              onChange={e => { setTeacherId(parseInt(e.target.value)); setGroupId(0); }}
            >
              <option value={0}>{tt("admin.teacher_select", "O'qituvchini tanlang")}</option>
              {teachers.map(t => (
                <option key={t.id} value={t.id}>
                  {t.full_name || `${t.first_name || ""} ${t.last_name || ""}`.trim() || `O'qituvchi #${t.id}`}
                </option>
              ))}
            </select>
          </div>

          {/* Group */}
          <div className="flex-1 flex flex-col gap-1.5">
            <label className="text-xs font-bold text-ink-500 uppercase tracking-wider">{tt("admin.group", "Guruh")}</label>
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

        {/* Sort + Status filter row */}
        {groupId > 0 && !loading && (
          <div className="flex flex-wrap gap-3 items-center border-t border-line dark:border-white/10 pt-4">
            {/* Sort */}
            <div className="flex items-center gap-2 mr-2">
              <span className="text-xs font-bold text-ink-500">{tt("admin.sort", "Saralash")}:</span>
              {(["last_submission", "created_at", "title"] as SortMode[]).map(m => (
                <button
                  key={m}
                  onClick={() => setSortMode(m)}
                  className={`px-3 py-1 rounded-lg text-xs font-bold border transition-colors ${sortMode === m
                    ? "bg-cyan-500 text-white border-cyan-500"
                    : "border-line dark:border-white/10 text-ink-500 hover:border-cyan-300"
                  }`}
                >
                  {m === "last_submission" ? tt("admin.sort_last", "So'nggi topshirish") :
                   m === "created_at" ? tt("admin.sort_date", "Berilgan sana") :
                   tt("admin.sort_title", "Nomi")}
                </button>
              ))}
            </div>

            {/* Status filter */}
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-ink-500">{tt("common.status", "Status")}:</span>
              {([
                { id: "all", label: tt("common.all", "Hammasi"), cls: "bg-slate-500" },
                { id: "done", label: tt("status.done", "Qildi"), cls: "bg-green-500" },
                { id: "not_done", label: tt("status.not_done", "Qilmadi"), cls: "bg-red-500" },
                { id: "pending", label: tt("status.pending", "Kutilmoqda"), cls: "bg-amber-500" },
              ] as const).map(f => (
                <button
                  key={f.id}
                  onClick={() => setStatusFilter(f.id)}
                  className={`px-3 py-1 rounded-lg text-xs font-bold border transition-colors ${
                    statusFilter === f.id
                      ? `${f.cls} text-white border-transparent`
                      : "border-line dark:border-white/10 text-ink-500 hover:border-slate-300"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Error ── */}
      {error && (
        <div className="text-red-500 font-bold bg-red-50 dark:bg-red-500/10 p-4 rounded-xl border border-red-100 dark:border-red-500/20">
          {error}
        </div>
      )}

      {/* ── Loading ── */}
      {loading && (
        <div className="flex justify-center p-10">
          <div className="w-10 h-10 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {/* ── Content ── */}
      {!loading && groupId > 0 && (
        <div className="flex flex-col gap-4">
          {filtered.length === 0 ? (
            <div className="bg-white dark:bg-[#0f172a] p-10 text-center rounded-2xl shadow-sm border border-line dark:border-white/10 font-bold text-ink-500">
              {tt("admin.no_homeworks", "Bu guruhda vazifalar topilmadi.")}
            </div>
          ) : filtered.map(hw => {
            const c = counts(hw.id);
            const isExpanded = expandedHw === hw.id;
            const rows = reports[hw.id] || [];
            const deadline = hw.due_date || hw.due_at || "";

            // Apply per-student status filter inside expanded view
            const visibleRows = statusFilter === "all"
              ? rows
              : rows.filter(r => rowStatus(r) === statusFilter);

            return (
              <div key={hw.id} className="bg-white dark:bg-[#0f172a] border border-line dark:border-white/10 rounded-2xl overflow-hidden shadow-sm">

                {/* ── Homework header ── */}
                <button
                  className="w-full text-left p-4 sm:p-5 bg-surface-soft dark:bg-white/[0.03] hover:bg-surface-soft/80 dark:hover:bg-white/[0.05] transition-colors"
                  onClick={() => setExpandedHw(isExpanded ? null : hw.id)}
                >
                  <div className="flex flex-wrap gap-3 items-start justify-between">
                    {/* Left: title + meta */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-bold px-2 py-0.5 rounded-md bg-cyan-50 text-cyan-700 dark:bg-cyan-500/10 dark:text-cyan-300 border border-cyan-200 dark:border-cyan-500/20">
                          {kindLabel(hw)}
                        </span>
                        <h3 className="font-bold text-base text-navy-900 dark:text-white truncate">{hw.title}</h3>
                      </div>

                      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-ink-500">
                        <span>📅 {tt("common.date", "Berildi")}: <strong>{fmtDay(hw.created_at)}</strong></span>
                        {deadline && (
                          <span>⏳ {tt("homework.deadline", "Deadline")}: <strong className="text-red-500">{fmtDay(deadline)}</strong></span>
                        )}
                        {hw.teacher_name && <span>👤 {hw.teacher_name}</span>}
                        {hw.subject && <span>📚 {hw.subject}</span>}
                      </div>

                      {hw.description && (
                        <p className="mt-1.5 text-xs text-ink-500 line-clamp-2">{hw.description}</p>
                      )}

                      {/* Requirements badges */}
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {hw.requires_file && (
                          <span className="text-[11px] px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-500/20 font-medium">
                            📎 Fayl talab qilinadi
                          </span>
                        )}
                        {hw.requires_voice_message && (
                          <span className="text-[11px] px-2 py-0.5 rounded bg-purple-50 dark:bg-purple-500/10 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-500/20 font-medium">
                            🎤 Ovoz talab qilinadi
                          </span>
                        )}
                        {hw.is_voiceroom && (
                          <span className="text-[11px] px-2 py-0.5 rounded bg-teal-50 dark:bg-teal-500/10 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-500/20 font-medium">
                            🎙 Voiceroom vazifasi
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Right: counters + chevron */}
                    <div className="flex items-center gap-3 shrink-0">
                      <div className="flex gap-2 text-xs font-bold">
                        <span className="px-2.5 py-1 rounded-lg bg-green-50 text-green-700 dark:bg-green-500/10 dark:text-green-400 border border-green-200 dark:border-green-500/20">
                          ✓ {c.done}
                        </span>
                        <span className="px-2.5 py-1 rounded-lg bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-400 border border-red-200 dark:border-red-500/20">
                          ✕ {c.notDone}
                        </span>
                        <span className="px-2.5 py-1 rounded-lg bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400 border border-amber-200 dark:border-amber-500/20">
                          ⏳ {c.pending}
                        </span>
                        <span className="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-600 dark:bg-white/5 dark:text-slate-400 border border-slate-200 dark:border-white/10">
                          👥 {c.total}
                        </span>
                      </div>
                      <svg
                        className={`w-4 h-4 text-ink-500 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                        fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </div>
                </button>

                {/* ── Expanded: student table ── */}
                {isExpanded && (
                  <div className="overflow-x-auto border-t border-line dark:border-white/10">
                    <table className="w-full text-left min-w-[620px]">
                      <thead>
                        <tr className="bg-surface-soft dark:bg-white/[0.03] border-b border-line dark:border-white/10 text-xs font-bold text-ink-500 uppercase tracking-wider">
                          <th className="px-4 py-3">{tt("admin.student", "O'quvchi")}</th>
                          <th className="px-4 py-3">{tt("common.status", "Status")}</th>
                          <th className="px-4 py-3">{tt("admin.submission_time", "Topshirgan vaqt")}</th>
                          <th className="px-4 py-3">{tt("homework.noteLabel", "Izoh / Test")}</th>
                          <th className="px-4 py-3">{tt("homework.reviewNote", "Baholash")}</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-line dark:divide-white/[0.05]">
                        {visibleRows.length === 0 && (
                          <tr>
                            <td colSpan={5} className="px-4 py-6 text-center text-sm text-ink-500 font-medium">
                              {tt("admin.no_students", "O'quvchilar yo'q")}
                            </td>
                          </tr>
                        )}
                        {visibleRows.map((r) => {
                          const st = rowStatus(r);
                          return (
                            <tr key={r.student_id} className="hover:bg-surface-soft/40 dark:hover:bg-white/[0.02] transition-colors">
                              {/* Name */}
                              <td className="px-4 py-3 font-semibold text-sm text-navy-900 dark:text-white whitespace-nowrap">
                                {r.student_first_name} {r.student_last_name}
                              </td>

                              {/* Status badge */}
                              <td className="px-4 py-3">
                                {st === "done" ? (
                                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-green-50 text-green-700 border border-green-200 dark:bg-green-500/10 dark:text-green-400 dark:border-green-500/20">
                                    ✓ {tt("status.done", "Qildi")}
                                    {r.uploaded && " 📎"}
                                  </span>
                                ) : st === "not_done" ? (
                                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-red-50 text-red-700 border border-red-200 dark:bg-red-500/10 dark:text-red-400 dark:border-red-500/20">
                                    ✕ {tt("status.not_done", "Qilmadi")}
                                    {r.deadline_missed && " ⏰"}
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/20">
                                    ⏳ {tt("status.pending", "Topshirmagan")}
                                  </span>
                                )}
                              </td>

                              {/* Submission time */}
                              <td className="px-4 py-3 text-xs text-ink-500 font-medium whitespace-nowrap">
                                {fmtDate(r.submission_updated_at || r.submission_created_at)}
                              </td>

                              {/* Note / test */}
                              <td className="px-4 py-3 text-xs text-ink-500 max-w-[220px]">
                                {r.student_note && (
                                  <p className="truncate italic">"{r.student_note}"</p>
                                )}
                                {r.test_available && (
                                  <span className={`inline-block mt-1 px-1.5 py-0.5 rounded text-[11px] font-bold ${
                                    r.test_completed
                                      ? "bg-green-50 text-green-700 dark:bg-green-500/10 dark:text-green-400"
                                      : "bg-slate-100 text-slate-500 dark:bg-white/5"
                                  }`}>
                                    {r.test_completed
                                      ? `Test: ${r.test_correct_count}/${r.test_total_questions} (+${(r.test_dpoints_delta ?? 0).toFixed(1)} D'p)`
                                      : "Test: qilinmagan"}
                                  </span>
                                )}
                              </td>

                              {/* Review */}
                              <td className="px-4 py-3 text-xs text-ink-500 max-w-[180px]">
                                {r.reviewed_at ? (
                                  <div>
                                    <span className={`font-bold ${(r.review_dpoint_delta ?? 0) >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                                      {(r.review_dpoint_delta ?? 0) >= 0 ? "+" : ""}{(r.review_dpoint_delta ?? 0).toFixed(1)} D'p
                                    </span>
                                    {r.review_note && (
                                      <p className="truncate text-ink-500 mt-0.5">"{r.review_note}"</p>
                                    )}
                                    <p className="text-[10px] text-ink-400 mt-0.5">{fmtDate(r.reviewed_at)}</p>
                                  </div>
                                ) : (
                                  <span className="text-ink-400">—</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Placeholder ── */}
      {!loading && !groupId && (
        <div className="text-center p-12 text-ink-500 font-bold bg-white dark:bg-[#0f172a] rounded-2xl shadow-sm border border-line dark:border-white/10">
          <div className="text-4xl mb-3">📚</div>
          <p>{tt("admin.group_select", "Guruhni tanlang")}</p>
        </div>
      )}
    </div>
  );
}
