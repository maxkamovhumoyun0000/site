"use client";

import { useState, useEffect, useCallback } from "react";
import { useWebT } from "./web-i18n";

type GenericRow = Record<string, unknown>;

function CircleProgress({
  value,
  max = 100,
  label,
  size = 96,
  color = "#6c63ff",
}: {
  value: number;
  max?: number;
  label: string;
  size?: number;
  color?: string;
}) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const r = (size - 12) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <div style={{ position: "relative", width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#ffffff15" strokeWidth={8} />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth={8}
            strokeDasharray={`${dash} ${circ - dash}`}
            strokeLinecap="round"
            style={{ transition: "stroke-dasharray 1s ease" }}
          />
        </svg>
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 14,
            fontWeight: 700,
            color,
          }}
        >
          {Math.round(pct)}%
        </div>
      </div>
      <div style={{ fontSize: 11, opacity: 0.65, textAlign: "center", maxWidth: 80 }}>{label}</div>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const clr =
    score >= 80 ? "#10b981" : score >= 55 ? "#f59e0b" : score >= 30 ? "#8b5cf6" : "#ef4444";
  const label =
    score >= 80 ? "A+ Excellent" : score >= 55 ? "B Good" : score >= 30 ? "C Fair" : "D Needs Work";
  return (
    <div
      style={{
        display: "inline-flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 4,
        background: clr + "18",
        border: `2px solid ${clr}55`,
        borderRadius: 16,
        padding: "16px 28px",
      }}
    >
      <div style={{ fontSize: 42, fontWeight: 900, color: clr, lineHeight: 1 }}>
        {score.toFixed(1)}
      </div>
      <div style={{ fontSize: 12, color: clr, fontWeight: 600 }}>{label}</div>
    </div>
  );
}

function LeaderboardRow({ item, idx }: { item: GenericRow; idx: number }) {
  const isSelf = Boolean(item.is_self);
  const rank = Number(item.rank_pos || idx + 1);
  const score = Number(item.kpi_score || 0);
  const name =
    isSelf
      ? "Siz"
      : `${String(item.first_name || "O'qituvchi")} ${String(item.last_name || "")}`.trim();
  const rankIcon = rank === 1 ? "🥇" : rank === 2 ? "🥈" : rank === 3 ? "🥉" : `#${rank}`;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "10px 14px",
        borderRadius: 10,
        background: isSelf ? "#6c63ff18" : "transparent",
        border: `1px solid ${isSelf ? "#6c63ff44" : "var(--border-color,#2a2a3e)"}`,
        marginBottom: 6,
        transition: "background .2s",
      }}
    >
      <span style={{ fontSize: 18, minWidth: 32, textAlign: "center" }}>{rankIcon}</span>
      <div style={{ flex: 1, fontWeight: isSelf ? 700 : 400 }}>{name}</div>
      <div
        style={{
          padding: "3px 12px",
          borderRadius: 20,
          background:
            score >= 80 ? "#10b98122" : score >= 55 ? "#f59e0b22" : "#6b728022",
          color: score >= 80 ? "#10b981" : score >= 55 ? "#f59e0b" : "#9ca3af",
          fontSize: 13,
          fontWeight: 700,
        }}
      >
        {score.toFixed(1)}
      </div>
    </div>
  );
}

export function TeacherKpiPanel({
  onApiCall,
}: {
  onApiCall: (path: string, payload?: GenericRow, method?: string, successText?: string) => Promise<GenericRow | null>;
}) {
  const tt = useWebT();
  const [kpiData, setKpiData] = useState<GenericRow | null>(null);
  const [leaderboard, setLeaderboard] = useState<GenericRow[]>([]);
  const [rank, setRank] = useState<number | null>(null);
  const [totalTeachers, setTotalTeachers] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState<"my" | "leaderboard">("my");

  const load = useCallback(async () => {
    setLoading(true);
    const res = await onApiCall("/api/teacher/kpi/me", undefined, "GET");
    if (res) {
      setKpiData((res.kpi as GenericRow) || null);
      setRank(typeof res.rank === "number" ? res.rank : null);
      setTotalTeachers(Number(res.total_teachers || 0));
    }
    const lbRes = await onApiCall("/api/teacher/kpi/leaderboard?limit=30", undefined, "GET");
    setLeaderboard((lbRes?.items as GenericRow[]) || []);
    setLoading(false);
  }, [onApiCall]);

  useEffect(() => {
    load();
  }, [load]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await onApiCall("/api/teacher/kpi/refresh", {}, "POST", "KPI yangilandi ✅");
    await load();
    setRefreshing(false);
  };

  const kpi = kpiData || {};
  const score = Number(kpi.kpi_score || 0);
  const attRate = Math.round(Number(kpi.attendance_rate || 0) * 100);
  const hwRate = Math.round(Number(kpi.homework_review_rate || 0) * 100);
  const avgScore = Math.round(Number(kpi.avg_student_score || 0) * 100);
  const respSpeed = Math.round(Number(kpi.response_speed_score || 0) * 100);
  const groupCompl = Math.round(Number(kpi.group_completion_rate || 0) * 100);

  return (
    <div className="page-stack">
      <style>{`
        .kpi-tab { cursor:pointer; padding: 8px 20px; border-radius:20px; font-weight:600; font-size:13px; border:1px solid var(--border-color,#2a2a3e); transition:all .2s; }
        .kpi-tab.active { background: linear-gradient(135deg,#6c63ff,#a855f7); color:#fff; border-color:transparent; }
      `}</style>

      {/* Header */}
      <section className="panel-card">
        <div className="row-between" style={{ flexWrap: "wrap", gap: 12 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>
              📊 {tt("teacher.kpi.title", "My KPI")}
            </h2>
            <p style={{ margin: "4px 0 0", opacity: 0.6, fontSize: 14 }}>
              O'qituvchilik unumdorlik ko'rsatkichlari
            </p>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <button
              onClick={handleRefresh}
              disabled={refreshing || loading}
              style={{
                padding: "9px 18px",
                borderRadius: 10,
                border: "1px solid var(--border-color,#2a2a3e)",
                background: "transparent",
                color: "inherit",
                cursor: refreshing ? "not-allowed" : "pointer",
                fontSize: 13,
                fontWeight: 600,
                opacity: refreshing ? 0.5 : 1,
              }}
            >
              {refreshing ? "⏳ ..." : `🔄 ${tt("teacher.kpi.refresh", "Refresh")}`}
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
          <button
            className={`kpi-tab${tab === "my" ? " active" : ""}`}
            onClick={() => setTab("my")}
          >
            📊 {tt("teacher.kpi.title", "My KPI")}
          </button>
          <button
            className={`kpi-tab${tab === "leaderboard" ? " active" : ""}`}
            onClick={() => setTab("leaderboard")}
          >
            🏆 {tt("teacher.kpi.leaderboard", "Teacher Leaderboard")}
          </button>
        </div>
      </section>

      {loading ? (
        <section className="panel-card">
          <div style={{ textAlign: "center", padding: 48, opacity: 0.5 }}>⏳ Yuklanmoqda...</div>
        </section>
      ) : tab === "my" ? (
        <>
          {/* Main Score */}
          <section className="panel-card">
            {!kpiData ? (
              <div style={{ textAlign: "center", padding: 40, opacity: 0.5 }}>
                📭 {tt("teacher.kpi.noData", "KPI not yet calculated")}
                <br />
                <button
                  onClick={handleRefresh}
                  style={{
                    marginTop: 16,
                    padding: "10px 24px",
                    borderRadius: 10,
                    border: "none",
                    background: "linear-gradient(135deg,#6c63ff,#a855f7)",
                    color: "#fff",
                    cursor: "pointer",
                    fontWeight: 700,
                  }}
                >
                  🔄 Hisoblash
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "center" }}>
                {/* Score Badge */}
                <div>
                  <ScoreBadge score={score} />
                  {rank !== null ? (
                    <p style={{ margin: "8px 0 0", textAlign: "center", fontSize: 13, opacity: 0.7 }}>
                      {tt("teacher.kpi.youAreRank", "Ranked #{rank}", { rank })} &bull;{" "}
                      {tt("teacher.kpi.outOf", "out of {total} teachers", { total: totalTeachers })}
                    </p>
                  ) : null}
                </div>

                {/* Circle charts */}
                <div
                  style={{
                    display: "flex",
                    gap: 20,
                    flexWrap: "wrap",
                    flex: 1,
                    justifyContent: "center",
                  }}
                >
                  <CircleProgress
                    value={attRate}
                    label={tt("teacher.kpi.attendance", "Attendance")}
                    color="#6c63ff"
                  />
                  <CircleProgress
                    value={hwRate}
                    label={tt("teacher.kpi.hwReview", "HW Review")}
                    color="#10b981"
                  />
                  <CircleProgress
                    value={avgScore}
                    label={tt("teacher.kpi.avgScore", "Avg Score")}
                    color="#f59e0b"
                  />
                  <CircleProgress
                    value={respSpeed}
                    label={tt("teacher.kpi.responseSpeed", "Speed")}
                    color="#a855f7"
                  />
                  <CircleProgress
                    value={groupCompl}
                    label={tt("teacher.kpi.groupCompletion", "Group")}
                    color="#ef4444"
                  />
                </div>
              </div>
            )}
          </section>

          {/* Stats Grid */}
          {kpiData ? (
            <section className="panel-card">
              <h3 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 700 }}>📈 Batafsil statistika</h3>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
                  gap: 12,
                }}
              >
                {[
                  {
                    icon: "👥",
                    label: tt("teacher.kpi.totalStudents", "Students"),
                    val: Number(kpi.total_students || 0),
                    unit: "ta",
                  },
                  {
                    icon: "📚",
                    label: tt("teacher.kpi.totalGroups", "Groups"),
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
                    style={{
                      background: "var(--surface-2,#16213e)",
                      borderRadius: 12,
                      padding: "14px 16px",
                      border: "1px solid var(--border-color,#2a2a3e)",
                    }}
                  >
                    <div style={{ fontSize: 20, marginBottom: 6 }}>{item.icon}</div>
                    <div style={{ fontSize: 24, fontWeight: 800, lineHeight: 1 }}>
                      {item.val}
                      <span style={{ fontSize: 13, opacity: 0.6, fontWeight: 400 }}> {item.unit}</span>
                    </div>
                    <div style={{ fontSize: 12, opacity: 0.6, marginTop: 4 }}>{item.label}</div>
                  </div>
                ))}
              </div>

              {/* KPI Formula explanation */}
              <div
                style={{
                  marginTop: 20,
                  padding: "14px 16px",
                  background: "#6c63ff11",
                  borderRadius: 12,
                  border: "1px solid #6c63ff33",
                  fontSize: 13,
                }}
              >
                <strong>🧮 KPI Formula:</strong>
                <div style={{ marginTop: 8, opacity: 0.8, lineHeight: 1.8 }}>
                  Davomat × 30% + Homework tekshirish × 25% + O&rsquo;quvchilar ball × 20% + Tezlik × 15% + Guruh to&rsquo;liqlik × 10%
                </div>
              </div>
            </section>
          ) : null}
        </>
      ) : (
        /* Leaderboard tab */
        <section className="panel-card">
          <h3 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 700 }}>
            🏆 {tt("teacher.kpi.leaderboard", "Teacher Leaderboard")}
          </h3>
          {leaderboard.length === 0 ? (
            <div style={{ textAlign: "center", padding: 40, opacity: 0.5 }}>
              Reyting ma&rsquo;lumotlari yo&rsquo;q. Avval KPI ni hisoblang.
            </div>
          ) : (
            <div>
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
