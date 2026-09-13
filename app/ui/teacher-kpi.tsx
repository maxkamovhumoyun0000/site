"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useWebT } from "./web-i18n";

type GenericRow = Record<string, unknown>;

function CircleProgress({
  value,
  max = 100,
  label,
  size = 88,
  color = "#0284c7",
}: {
  value: number;
  max?: number;
  label: string;
  size?: number;
  color?: string;
}) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const r = (size - 14) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  return (
    <div className="flex flex-col items-center gap-1.5 sm:gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            className="stroke-slate-100 dark:stroke-white/10"
            strokeWidth={7}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth={7}
            strokeDasharray={`${dash} ${circ - dash}`}
            strokeLinecap="round"
            className="transition-all duration-1000 ease-out"
          />
        </svg>
        <div
          className="absolute inset-0 flex items-center justify-center text-xs sm:text-sm font-black tracking-tight"
          style={{ color }}
        >
          {Math.round(pct)}%
        </div>
      </div>
      <div className="text-[11px] sm:text-xs font-semibold text-ink-600 dark:text-navy-300 text-center max-w-[80px] sm:max-w-[84px] leading-tight">
        {label}
      </div>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const label =
    score >= 80
      ? "A+ A'lo natija"
      : score >= 55
      ? "B Yaxshi natija"
      : score >= 30
      ? "C O'rtacha natija"
      : "D Yaxshilash kerak";

  const badgeClass =
    score >= 80
      ? "bg-emerald-50 text-emerald-600 border-emerald-200/80 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/20"
      : score >= 55
      ? "bg-amber-50 text-amber-600 border-amber-200/80 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/20"
      : score >= 30
      ? "bg-sky-50 text-sky-600 border-sky-200/80 dark:bg-sky-500/10 dark:text-sky-400 dark:border-sky-500/20"
      : "bg-rose-50 text-rose-600 border-rose-200/80 dark:bg-rose-500/10 dark:text-rose-400 dark:border-rose-500/20";

  return (
    <div className={`inline-flex flex-col items-center justify-center gap-1.5 rounded-2xl border px-5 py-3.5 sm:px-8 sm:py-5 shadow-sm transition-all ${badgeClass}`}>
      <div className="text-3xl sm:text-4xl font-black leading-none font-display">
        {score.toFixed(1)}
      </div>
      <div className="text-[11px] sm:text-xs font-bold uppercase tracking-wider">{label}</div>
    </div>
  );
}

function LeaderboardRow({ item, idx }: { item: GenericRow; idx: number }) {
  const isSelf = Boolean(item.is_self);
  const rank = Number(item.rank_pos || idx + 1);
  const score = Number(item.kpi_score || 0);
  const name = isSelf
    ? "Siz"
    : `${String(item.first_name || "O'qituvchi")} ${String(item.last_name || "")}`.trim();
  const rankBadge =
    rank === 1 ? "🥇" : rank === 2 ? "🥈" : rank === 3 ? "🥉" : `#${rank}`;

  const scoreBadgeClass =
    score >= 80
      ? "bg-emerald-50 text-emerald-600 border-emerald-200/80 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/20"
      : score >= 55
      ? "bg-amber-50 text-amber-600 border-amber-200/80 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/20"
      : score >= 30
      ? "bg-sky-50 text-sky-600 border-sky-200/80 dark:bg-sky-500/10 dark:text-sky-400 dark:border-sky-500/20"
      : "bg-slate-50 text-slate-600 border-slate-200/80 dark:bg-slate-500/10 dark:text-slate-300 dark:border-slate-500/20";

  return (
    <div
      className={`flex items-center gap-3 p-3 sm:p-4 rounded-xl border transition-all ${
        isSelf
          ? "bg-sky-50/70 dark:bg-sky-500/10 border-sky-300 dark:border-sky-500/30 shadow-sm"
          : "bg-white dark:bg-white/[0.02] border-slate-200/70 dark:border-white/[0.06] hover:border-slate-300 dark:hover:border-white/10"
      }`}
    >
      <span className="text-lg sm:text-xl min-w-[34px] text-center font-black">
        {rankBadge}
      </span>
      <div className="min-w-0 flex-1 flex items-center gap-2">
        <span className={`text-sm sm:text-base font-bold truncate ${isSelf ? "text-sky-900 dark:text-cyan-200" : "text-navy-950 dark:text-white"}`}>
          {name}
        </span>
        {isSelf && (
          <span className="px-2 py-0.5 text-[10px] font-black uppercase tracking-wider rounded-md bg-sky-600 text-white shadow-xs">
            Siz
          </span>
        )}
      </div>
      <div className={`px-3 py-1 rounded-xl text-xs sm:text-sm font-black border ${scoreBadgeClass}`}>
        {score.toFixed(1)} ball
      </div>
    </div>
  );
}

export function TeacherKpiPanel({
  onApiCall,
  adminMode = false,
}: {
  onApiCall: (path: string, payload?: GenericRow, method?: string, successText?: string) => Promise<GenericRow | null>;
  adminMode?: boolean;
}) {
  const tt = useWebT();
  const [kpiData, setKpiData] = useState<GenericRow | null>(null);
  const [leaderboard, setLeaderboard] = useState<GenericRow[]>([]);
  const [rank, setRank] = useState<number | null>(null);
  const [totalTeachers, setTotalTeachers] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const onApiCallRef = useRef(onApiCall);
  onApiCallRef.current = onApiCall;
  const initialLoadDoneRef = useRef(false);

  const load = useCallback(async (silent = false) => {
    if (!silent && !initialLoadDoneRef.current) {
      setLoading(true);
    }
    try {
      if (adminMode) {
        const res = await onApiCallRef.current("/admin/teacher-kpi?limit=200", undefined, "GET");
        const items = (res?.items as GenericRow[]) || [];
        setLeaderboard(items);
        setTotalTeachers(Number(res?.total || items.length));
        setKpiData(null);
        setRank(null);
      } else {
        const res = await onApiCallRef.current("/teacher/kpi/me", undefined, "GET");
        if (res) {
          setKpiData((res.kpi as GenericRow) || null);
          setRank(typeof res.rank === "number" ? res.rank : null);
          setTotalTeachers(Number(res.total_teachers || 0));
        }
        const lbRes = await onApiCallRef.current("/teacher/kpi/leaderboard?limit=30", undefined, "GET");
        setLeaderboard((lbRes?.items as GenericRow[]) || []);
      }
    } catch {
      // Quietly ignore background poll errors to avoid disrupting UX
    } finally {
      initialLoadDoneRef.current = true;
      setLoading(false);
    }
  }, [adminMode]);

  useEffect(() => {
    // Initial fetch
    load(false);

    // Silent background auto-refresh every 30 seconds
    const interval = window.setInterval(() => {
      load(true);
    }, 30000);

    return () => {
      window.clearInterval(interval);
    };
  }, [load]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      if (!adminMode) {
        await onApiCallRef.current("/teacher/kpi/refresh", {}, "POST");
      }
      await load(true);
    } finally {
      setRefreshing(false);
    }
  };

  const kpi = kpiData || {};
  const score = Number(kpi.kpi_score || 0);
  const attRate = Math.round(Number(kpi.attendance_rate || 0) * 100);
  const hwRate = Math.round(Number(kpi.homework_review_rate || 0) * 100);
  const avgScore = Math.round(Number(kpi.avg_student_score || 0) * 100);
  const respSpeed = Math.round(Number(kpi.response_speed_score || 0) * 100);
  const groupCompl = Math.round(Number(kpi.group_completion_rate || 0) * 100);

  if (adminMode) {
    return (
      <div className="admin-groups-page">
        <div className="admin-page-header">
          <div>
            <h2>📊 O'qituvchilar KPI</h2>
            <p>Barcha o'qituvchilarning unumdorlik ko'rsatkichlari va reytingi</p>
          </div>
          <button
            className="admin-btn-action"
            onClick={handleRefresh}
            disabled={refreshing || loading}
          >
            {refreshing ? "⏳ ..." : `🔄 ${tt("teacher.kpi.refresh", "Yangilash")}`}
          </button>
        </div>

        {loading && !initialLoadDoneRef.current ? (
          <div className="admin-table-card p-12 text-center text-sm font-semibold text-ink-500 dark:text-navy-400">
            ⏳ Yuklanmoqda...
          </div>
        ) : (
          <section className="bg-white dark:bg-white/[0.03] border border-slate-200/80 dark:border-white/10 rounded-2xl p-5 sm:p-7 shadow-sm">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h3 className="text-base sm:text-lg font-bold text-navy-950 dark:text-white">
                  🏆 O'qituvchilar reytingi
                </h3>
                <p className="text-xs text-ink-500 dark:text-navy-400 mt-0.5">
                  Eng yuqori unumdorlikka ega o'qituvchilar ro'yxati
                </p>
              </div>
              <span className="admin-dash-panel-badge">{leaderboard.length} o'qituvchi</span>
            </div>

            {leaderboard.length === 0 ? (
              <div className="text-center py-12 text-sm font-semibold text-ink-500 dark:text-navy-400">
                Reyting ma&rsquo;lumotlari yo&rsquo;q.
              </div>
            ) : (
              <div className="flex flex-col gap-2.5">
                {leaderboard.map((item, idx) => (
                  <LeaderboardRow key={String(item.teacher_id || idx)} item={item} idx={idx} />
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    );
  }

  return (
    <div className="admin-groups-page">
      {/* 1. Main KPI Indicators Hero Card */}
      <section className="bg-white dark:bg-white/[0.03] border border-slate-200/80 dark:border-white/10 rounded-2xl p-5 sm:p-7 shadow-sm">
        {loading && !initialLoadDoneRef.current ? (
          <div className="text-center py-10 text-sm font-semibold text-ink-500 dark:text-navy-400">
            ⏳ Yuklanmoqda...
          </div>
        ) : !kpiData ? (
          <div className="text-center py-8 sm:py-10">
            <p className="text-sm font-semibold text-ink-500 dark:text-navy-400 mb-4">
              📭 {tt("teacher.kpi.noData", "KPI ma'lumotlari hali hisoblanmagan")}
            </p>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-sm font-bold shadow-md hover:opacity-90 transition-opacity"
            >
              {refreshing ? "⏳ Hisoblanmoqda..." : "🔄 Hisoblash"}
            </button>
          </div>
        ) : (
          <div className="flex flex-col lg:flex-row gap-6 lg:gap-10 items-center justify-between">
            {/* Score Badge */}
            <div className="flex flex-col items-center text-center">
              <ScoreBadge score={score} />
              {rank !== null ? (
                <div className="mt-3 inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 dark:bg-white/10 text-xs font-bold text-ink-700 dark:text-navy-200">
                  <span>🏆</span>
                  <span>
                    {tt("teacher.kpi.youAreRank", "{rank}-o'rinda", { rank })} &bull;{" "}
                    {tt("teacher.kpi.outOf", "{total} o'qituvchidan", { total: totalTeachers })}
                  </span>
                </div>
              ) : null}
            </div>

            {/* Circle charts with logo colors (Emerald, Cyan, Blue, Amber, Rose) */}
            <div className="flex flex-wrap items-center justify-center gap-3.5 sm:gap-6 flex-1">
              <CircleProgress
                value={attRate}
                label={tt("teacher.kpi.attendance", "Davomat foizi")}
                color="#10b981"
              />
              <CircleProgress
                value={hwRate}
                label={tt("teacher.kpi.hwReview", "Homework tekshirish")}
                color="#0284c7"
              />
              <CircleProgress
                value={avgScore}
                label={tt("teacher.kpi.avgScore", "O'quvchilar balli")}
                color="#f59e0b"
              />
              <CircleProgress
                value={respSpeed}
                label={tt("teacher.kpi.responseSpeed", "Javob tezligi")}
                color="#06b6d4"
              />
              <CircleProgress
                value={groupCompl}
                label={tt("teacher.kpi.groupCompletion", "Guruh to'liqligi")}
                color="#f43f5e"
              />
            </div>
          </div>
        )}
      </section>

      {/* 2. Detailed Statistics (Batafsil statistika) */}
      {kpiData ? (
        <section className="bg-white dark:bg-white/[0.03] border border-slate-200/80 dark:border-white/10 rounded-2xl p-5 sm:p-7 shadow-sm">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-base sm:text-lg font-bold text-navy-950 dark:text-white">
              📈 Batafsil statistika
            </h3>
            <span className="admin-dash-panel-badge">6 ta ko'rsatkich</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 sm:gap-4">
            {[
              {
                icon: "👥",
                label: tt("teacher.kpi.totalStudents", "Jami o'quvchilar"),
                val: Number(kpi.total_students || 0),
                unit: "ta",
              },
              {
                icon: "📚",
                label: tt("teacher.kpi.totalGroups", "Guruhlar"),
                val: Number(kpi.groups_count || 0),
                unit: "ta",
              },
              {
                icon: "📝",
                label: "Jami homework",
                val: Number(kpi.total_homeworks || 0),
                unit: "ta",
              },
              {
                icon: "✅",
                label: "Tekshirilgan",
                val: Number(kpi.reviewed_homeworks || 0),
                unit: "ta",
              },
              {
                icon: "📊",
                label: "Davomat foizi",
                val: attRate,
                unit: "%",
              },
              {
                icon: "⚡",
                label: "Tezlik ball",
                val: respSpeed,
                unit: "%",
              },
            ].map((item) => (
              <div
                key={item.label}
                className="p-3.5 sm:p-4 rounded-2xl bg-slate-50/70 dark:bg-white/[0.03] border border-slate-200/70 dark:border-white/[0.06] hover:border-slate-300 dark:hover:border-white/15 transition-all flex flex-col justify-between"
              >
                <div className="text-2xl mb-2">{item.icon}</div>
                <div>
                  <div className="text-xl sm:text-2xl font-black text-navy-950 dark:text-white leading-none">
                    {item.val}
                    <span className="text-xs font-semibold text-ink-500 dark:text-navy-400 ml-1">{item.unit}</span>
                  </div>
                  <div className="text-xs font-semibold text-ink-600 dark:text-navy-300 mt-1.5 leading-snug">
                    {item.label}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* KPI Formula Banner */}
          <div className="mt-6 p-4 sm:p-5 bg-sky-50/60 dark:bg-sky-500/10 border border-sky-100 dark:border-sky-500/20 rounded-2xl">
            <div className="flex items-center gap-2 text-sm font-bold text-sky-950 dark:text-cyan-200 mb-2">
              <span>🧮</span>
              <span>KPI Hisoblash Formulasi:</span>
            </div>
            <div className="flex flex-wrap gap-1.5 sm:gap-2 text-xs font-semibold">
              <span className="px-2.5 py-1 rounded-lg bg-emerald-100/80 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-300">
                Davomat × 30%
              </span>
              <span className="text-ink-400 dark:text-white/40 self-center">+</span>
              <span className="px-2.5 py-1 rounded-lg bg-blue-100/80 text-blue-800 dark:bg-blue-500/20 dark:text-blue-300">
                Homework tekshirish × 25%
              </span>
              <span className="text-ink-400 dark:text-white/40 self-center">+</span>
              <span className="px-2.5 py-1 rounded-lg bg-amber-100/80 text-amber-800 dark:bg-amber-500/20 dark:text-amber-300">
                O'quvchilar ball × 20%
              </span>
              <span className="text-ink-400 dark:text-white/40 self-center">+</span>
              <span className="px-2.5 py-1 rounded-lg bg-cyan-100/80 text-cyan-800 dark:bg-cyan-500/20 dark:text-cyan-300">
                Javob tezligi × 15%
              </span>
              <span className="text-ink-400 dark:text-white/40 self-center">+</span>
              <span className="px-2.5 py-1 rounded-lg bg-rose-100/80 text-rose-800 dark:bg-rose-500/20 dark:text-rose-300">
                Guruh to'liqlik × 10%
              </span>
            </div>
          </div>
        </section>
      ) : null}

      {/* 3. Reyting (O'qituvchilar reytingi) directly UNDER Batafsil statistika */}
      <section className="bg-white dark:bg-white/[0.03] border border-slate-200/80 dark:border-white/10 rounded-2xl p-5 sm:p-7 shadow-sm">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="text-base sm:text-lg font-bold text-navy-950 dark:text-white">
              🏆 {tt("teacher.kpi.leaderboard", "O'qituvchilar reytingi")}
            </h3>
            <p className="text-xs text-ink-500 dark:text-navy-400 mt-0.5">
              Eng yuqori unumdorlikka ega o'qituvchilar ro'yxati
            </p>
          </div>
          <span className="admin-dash-panel-badge">{leaderboard.length} o'qituvchi</span>
        </div>

        {leaderboard.length === 0 ? (
          <div className="text-center py-12 text-sm font-semibold text-ink-500 dark:text-navy-400">
            Reyting ma&rsquo;lumotlari yo&rsquo;q. Avval KPI ni hisoblang.
          </div>
        ) : (
          <div className="flex flex-col gap-2.5">
            {leaderboard.map((item, idx) => (
              <LeaderboardRow key={String(item.teacher_id || idx)} item={item} idx={idx} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
