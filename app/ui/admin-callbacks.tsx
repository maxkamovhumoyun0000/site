"use client";

import { useEffect, useState, useCallback } from "react";
import { API_BASE } from "../public-data";
import { useWebT } from "./web-i18n";

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
  const tt = useWebT();
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
        <span>{tt("common.loading", "Yuklanmoqda...")}</span>
      </div>
    );
  }

  return (
    <div className="admin-callbacks-root admin-users-page">
      <div className="admin-page-header admin-callbacks-header">
        <h2 className="admin-callbacks-title">
          <span className="admin-callbacks-title-icon">📋</span>
          {tt("section.applications", "Arizalar")}
        </h2>
        <button className="admin-page-btn admin-callbacks-refresh" onClick={fetchCallbacks} title={tt("admin.callbacks.refresh", "Yangilash")}>
          ↻
        </button>
      </div>

      {items.length === 0 ? (
        <div className="admin-callbacks-empty">
          <div className="admin-callbacks-empty-icon">📭</div>
          <p>{tt("admin.callbacks.empty", "Hozircha ariza yo'q")}</p>
        </div>
      ) : (
        <>
          {pending.length > 0 && (
            <section className="admin-callbacks-section admin-table-card">
              <h3 className="admin-callbacks-section-title">
                <span className="admin-callbacks-dot pending" />
                {tt("admin.callbacks.pending", "Kutilmoqda")} ({pending.length})
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
            <section className="admin-callbacks-section admin-table-card">
              <h3 className="admin-callbacks-section-title">
                <span className="admin-callbacks-dot completed" />
                {tt("admin.callbacks.completed", "Ko'rib chiqilgan")} ({completed.length})
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
  const tt = useWebT();
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
        title={`${item.phone} ${tt("admin.callbacks.callTitle", "raqamiga qo'ng'iroq qilish")}`}
      >
        {isLoading ? `📡 ${tt("admin.callbacks.calling", "Ulanyapti...")}` : !isPending ? `✅ ${tt("admin.callbacks.done", "Qilindi")}` : `📞 ${tt("admin.callbacks.call", "Qo'ng'iroq")}`}
      </button>
    </div>
  );
}
