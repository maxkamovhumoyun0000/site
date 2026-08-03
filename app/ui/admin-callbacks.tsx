"use client";

import { useEffect, useState, useCallback } from "react";
import { API_BASE } from "../public-data";

interface Callback {
  id: number;
  name: string;
  phone: string;
  subject: string;
  status: string;
  created_at: string;
}

function formatDate(dateStr: string) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleString("uz-UZ", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function AdminCallbacksPanel({ token }: { token: string }) {
  const [items, setItems] = useState<Callback[]>([]);
  const [loading, setLoading] = useState(true);
  const [callingId, setCallingId] = useState<number | null>(null);

  const fetchCallbacks = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/admin/callbacks`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setItems(data.items || []);
      }
    } catch (_) {
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchCallbacks();
  }, [fetchCallbacks]);

  const handleCall = async (item: Callback) => {
    // Immediately update in UI optimistically
    setCallingId(item.id);
    setItems((prev) =>
      prev.map((c) => (c.id === item.id ? { ...c, status: "completed" } : c))
    );

    // Update status in backend
    try {
      await fetch(`${API_BASE}/admin/callbacks/${item.id}/status?status=completed`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (_) {}

    // Open phone dialer
    const safe = item.phone.replace(/\s/g, "");
    window.location.href = `tel:${safe}`;

    setTimeout(() => setCallingId(null), 2000);
  };

  const pending = items.filter((c) => c.status === "pending");
  const completed = items.filter((c) => c.status !== "pending");

  if (loading) {
    return (
      <div className="admin-callbacks-loading">
        <div className="admin-callbacks-spinner" />
        <span>Yuklanmoqda...</span>
      </div>
    );
  }

  return (
    <div className="admin-callbacks-root">
      <div className="admin-callbacks-header">
        <h2 className="admin-callbacks-title">
          <span className="admin-callbacks-title-icon">📋</span>
          Arizalar
        </h2>
        <button className="admin-callbacks-refresh" onClick={fetchCallbacks} title="Yangilash">
          ↻
        </button>
      </div>

      {items.length === 0 ? (
        <div className="admin-callbacks-empty">
          <div className="admin-callbacks-empty-icon">📭</div>
          <p>Hozircha ariza yo'q</p>
        </div>
      ) : (
        <>
          {pending.length > 0 && (
            <section className="admin-callbacks-section">
              <h3 className="admin-callbacks-section-title">
                <span className="admin-callbacks-dot pending" />
                Kutilmoqda ({pending.length})
              </h3>
              <div className="admin-callbacks-list">
                {pending.map((item) => (
                  <CallbackCard
                    key={item.id}
                    item={item}
                    onCall={handleCall}
                    isLoading={callingId === item.id}
                  />
                ))}
              </div>
            </section>
          )}

          {completed.length > 0 && (
            <section className="admin-callbacks-section">
              <h3 className="admin-callbacks-section-title">
                <span className="admin-callbacks-dot completed" />
                Ko'rib chiqilgan ({completed.length})
              </h3>
              <div className="admin-callbacks-list">
                {completed.map((item) => (
                  <CallbackCard
                    key={item.id}
                    item={item}
                    onCall={handleCall}
                    isLoading={callingId === item.id}
                  />
                ))}
              </div>
            </section>
          )}
        </>
      )}

      <style>{`
        .admin-callbacks-root {
          max-width: 800px;
          margin: 0 auto;
          padding: 24px 16px 48px;
        }
        .admin-callbacks-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 28px;
        }
        .admin-callbacks-title {
          display: flex;
          align-items: center;
          gap: 10px;
          font-size: 22px;
          font-weight: 800;
          color: var(--ev-text, #0f172a);
          margin: 0;
        }
        .admin-callbacks-title-icon {
          font-size: 24px;
        }
        .admin-callbacks-refresh {
          width: 36px;
          height: 36px;
          border-radius: 10px;
          border: 1.5px solid var(--ev-border, #e2e8f0);
          background: var(--ev-surface, #fff);
          font-size: 18px;
          cursor: pointer;
          transition: all 0.15s;
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--ev-muted, #64748b);
        }
        .admin-callbacks-refresh:hover {
          background: var(--ev-surface-soft, #f8fafc);
          color: var(--ev-primary, #002dff);
        }
        .admin-callbacks-loading {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;
          padding: 64px 0;
          color: var(--ev-muted, #64748b);
          font-size: 14px;
        }
        .admin-callbacks-spinner {
          width: 36px;
          height: 36px;
          border: 3px solid var(--ev-border, #e2e8f0);
          border-top-color: var(--ev-primary, #002dff);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .admin-callbacks-empty {
          text-align: center;
          padding: 80px 0;
          color: var(--ev-muted, #64748b);
        }
        .admin-callbacks-empty-icon {
          font-size: 48px;
          margin-bottom: 12px;
        }
        .admin-callbacks-section {
          margin-bottom: 32px;
        }
        .admin-callbacks-section-title {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: var(--ev-muted, #64748b);
          margin: 0 0 14px;
        }
        .admin-callbacks-dot {
          width: 10px;
          height: 10px;
          border-radius: 50%;
          flex-shrink: 0;
        }
        .admin-callbacks-dot.pending {
          background: #ef4444;
          box-shadow: 0 0 0 3px rgba(239,68,68,0.2);
        }
        .admin-callbacks-dot.completed {
          background: #22c55e;
          box-shadow: 0 0 0 3px rgba(34,197,94,0.2);
        }
        .admin-callbacks-list {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        /* ── Card ── */
        .callback-card {
          display: flex;
          align-items: center;
          gap: 14px;
          padding: 14px 16px;
          border-radius: 14px;
          border: 1.5px solid var(--ev-border, #e2e8f0);
          background: var(--ev-surface, #fff);
          transition: box-shadow 0.15s, border-color 0.15s;
        }
        .callback-card:hover {
          box-shadow: 0 4px 16px rgba(0,0,0,0.07);
        }
        .callback-card.is-pending {
          border-color: rgba(239,68,68,0.3);
          background: rgba(239,68,68,0.02);
        }
        .callback-card.is-completed {
          opacity: 0.72;
        }
        .callback-status-badge {
          flex-shrink: 0;
          width: 14px;
          height: 14px;
          border-radius: 50%;
          border: 2px solid;
        }
        .callback-status-badge.pending {
          border-color: #ef4444;
          background: #ef4444;
          box-shadow: 0 0 0 3px rgba(239,68,68,0.25);
        }
        .callback-status-badge.completed {
          border-color: #22c55e;
          background: #22c55e;
          box-shadow: 0 0 0 3px rgba(34,197,94,0.2);
        }
        .callback-card-body {
          flex: 1;
          min-width: 0;
        }
        .callback-name {
          font-size: 15px;
          font-weight: 700;
          color: var(--ev-text, #0f172a);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          margin-bottom: 2px;
        }
        .callback-meta {
          display: flex;
          flex-wrap: wrap;
          gap: 6px 16px;
          font-size: 12.5px;
          color: var(--ev-muted, #64748b);
        }
        .callback-phone {
          font-weight: 600;
          color: var(--ev-primary, #002dff);
          font-family: monospace;
        }
        .callback-subject-chip {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          background: rgba(0,45,255,0.07);
          color: var(--ev-primary, #002dff);
          border-radius: 6px;
          padding: 1px 7px;
          font-size: 11px;
          font-weight: 700;
        }
        .callback-call-btn {
          flex-shrink: 0;
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 8px 16px;
          border-radius: 10px;
          border: none;
          background: #22c55e;
          color: #fff;
          font-size: 13px;
          font-weight: 700;
          cursor: pointer;
          transition: background 0.15s, transform 0.1s;
          white-space: nowrap;
        }
        .callback-call-btn:hover {
          background: #16a34a;
          transform: scale(1.03);
        }
        .callback-call-btn:active {
          transform: scale(0.97);
        }
        .callback-call-btn.loading {
          background: #86efac;
          cursor: default;
        }
        .callback-call-btn.done {
          background: #d1fae5;
          color: #15803d;
          cursor: default;
        }

        @media (max-width: 520px) {
          .callback-card {
            flex-direction: column;
            align-items: flex-start;
          }
          .callback-call-btn {
            width: 100%;
            justify-content: center;
          }
        }
        @media (prefers-color-scheme: dark) {
          .admin-callbacks-title { color: #f1f5f9; }
          .callback-card {
            background: rgba(255,255,255,0.04);
            border-color: rgba(255,255,255,0.08);
          }
          .callback-card.is-pending {
            background: rgba(239,68,68,0.05);
            border-color: rgba(239,68,68,0.25);
          }
          .callback-name { color: #f1f5f9; }
          .callback-phone { color: #93c5fd; }
          .callback-subject-chip {
            background: rgba(147,197,253,0.12);
            color: #93c5fd;
          }
        }
      `}</style>
    </div>
  );
}

function CallbackCard({
  item,
  onCall,
  isLoading,
}: {
  item: Callback;
  onCall: (item: Callback) => void;
  isLoading: boolean;
}) {
  const isPending = item.status === "pending";

  return (
    <div className={`callback-card ${isPending ? "is-pending" : "is-completed"}`}>
      <div className={`callback-status-badge ${isPending ? "pending" : "completed"}`} />

      <div className="callback-card-body">
        <div className="callback-name">{item.name || "—"}</div>
        <div className="callback-meta">
          <span className="callback-phone">{item.phone}</span>
          {item.subject && (
            <span className="callback-subject-chip">📚 {item.subject}</span>
          )}
          {item.created_at && (
            <span>{formatDate(item.created_at)}</span>
          )}
        </div>
      </div>

      <button
        className={`callback-call-btn ${isLoading ? "loading" : ""} ${!isPending ? "done" : ""}`}
        onClick={() => onCall(item)}
        disabled={isLoading}
        title={`${item.phone} raqamiga qo'ng'iroq qilish`}
      >
        {isLoading ? "📡 Ulanyapti..." : !isPending ? "✅ Qilindi" : "📞 Qo'ng'iroq"}
      </button>
    </div>
  );
}
