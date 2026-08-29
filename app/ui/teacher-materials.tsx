"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useWebT } from "./web-i18n";

type GenericRow = Record<string, unknown>;

const FILE_TYPE_ICONS: Record<string, string> = {
  pdf: "📄",
  image: "🖼️",
  video: "🎬",
  audio: "🎵",
  doc: "📝",
  other: "📎",
};

const FILE_TYPE_COLORS: Record<string, string> = {
  pdf: "#ef4444",
  image: "#8b5cf6",
  video: "#f59e0b",
  audio: "#10b981",
  doc: "#3b82f6",
  other: "#6b7280",
};

function formatFileSize(bytes: number): string {
  if (!bytes || bytes <= 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function MaterialCard({
  mat,
  isSelf,
  tt,
  groups,
  onEdit,
  onDelete,
  onSend,
}: {
  mat: GenericRow;
  isSelf: boolean;
  tt: (k: string, f?: string) => string;
  groups: GenericRow[];
  onEdit: (m: GenericRow) => void;
  onDelete: (m: GenericRow) => void;
  onSend: (m: GenericRow, groupId: number) => void;
}) {
  const [sendOpen, setSendOpen] = useState(false);
  const [sendGroupId, setSendGroupId] = useState<number>(0);
  const fileType = String(mat.file_type || "other");
  const icon = FILE_TYPE_ICONS[fileType] || "📎";
  const color = FILE_TYPE_COLORS[fileType] || "#6b7280";
  const isPublic = Boolean(mat.is_public);

  return (
    <div
      style={{
        background: "var(--card-bg, #1e1e2e)",
        border: "1px solid var(--border-color, #2a2a3e)",
        borderRadius: 14,
        padding: "18px 20px",
        display: "flex",
        flexDirection: "column",
        gap: 10,
        position: "relative",
        transition: "box-shadow .2s",
      }}
      className="material-card"
    >
      {/* Badge */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            style={{
              width: 40,
              height: 40,
              borderRadius: 10,
              background: color + "22",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 20,
              flexShrink: 0,
              border: `1.5px solid ${color}55`,
            }}
          >
            {icon}
          </span>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14, lineHeight: 1.3 }}>{String(mat.title || "")}</div>
            {mat.description ? (
              <div style={{ fontSize: 12, opacity: 0.6, marginTop: 2 }}>{String(mat.description).slice(0, 60)}</div>
            ) : null}
          </div>
        </div>
      </div>

      {/* Meta */}
      <div style={{ display: "flex", gap: 12, fontSize: 12, opacity: 0.55, flexWrap: "wrap" }}>
        {mat.subject ? <span>📚 {String(mat.subject)}</span> : null}
        {mat.file_size ? <span>{formatFileSize(Number(mat.file_size))}</span> : null}
        {typeof mat.download_count === "number" ? (
          <span>⬇ {mat.download_count}</span>
        ) : null}
        {mat.teacher_first_name ? (
          <span>
            👤 {String(mat.teacher_first_name)} {String(mat.teacher_last_name || "")}
          </span>
        ) : null}
      </div>

      {/* Actions */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4 }}>
        <a
          href={String(mat.file_url || "#")}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            padding: "6px 14px",
            borderRadius: 8,
            fontSize: 12,
            background: "var(--accent-gradient, linear-gradient(135deg,#6c63ff,#a855f7))",
            color: "#fff",
            textDecoration: "none",
            fontWeight: 600,
          }}
        >
          ⬇ Download
        </a>
        {isSelf ? (
          <>
            <button
              onClick={() => onEdit(mat)}
              style={{
                padding: "6px 12px",
                borderRadius: 8,
                fontSize: 12,
                border: "1px solid var(--border-color,#2a2a3e)",
                background: "transparent",
                cursor: "pointer",
                color: "inherit",
              }}
            >
              ✏️ Edit
            </button>
            <button
              onClick={() => setSendOpen((p) => !p)}
              style={{
                padding: "6px 12px",
                borderRadius: 8,
                fontSize: 12,
                border: "1px solid #10b98144",
                background: "#10b98111",
                cursor: "pointer",
                color: "#10b981",
              }}
            >
              📤 {tt("teacher.materials.send", "Send")}
            </button>
            <button
              onClick={() => onDelete(mat)}
              style={{
                padding: "6px 10px",
                borderRadius: 8,
                fontSize: 12,
                border: "1px solid #ef444444",
                background: "#ef444411",
                cursor: "pointer",
                color: "#ef4444",
              }}
            >
              🗑
            </button>
          </>
        ) : null}
      </div>

      {/* Send Modal */}
      {sendOpen && groups.length > 0 ? (
        <div
          style={{
            marginTop: 8,
            padding: "12px",
            borderRadius: 10,
            background: "var(--surface-2, #16213e)",
            border: "1px solid var(--border-color,#2a2a3e)",
          }}
        >
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
            {tt("teacher.materials.selectGroup", "Select group")}
          </div>
          <select
            value={sendGroupId}
            onChange={(e) => setSendGroupId(Number(e.target.value))}
            style={{
              width: "100%",
              padding: "7px 10px",
              borderRadius: 8,
              border: "1px solid var(--border-color,#2a2a3e)",
              background: "var(--card-bg,#1e1e2e)",
              color: "inherit",
              fontSize: 13,
              marginBottom: 8,
            }}
          >
            <option value={0}>— tanlang —</option>
            {groups.map((g) => (
              <option key={String(g.id)} value={Number(g.id)}>
                {String(g.name || g.title || g.id)}
              </option>
            ))}
          </select>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              disabled={!sendGroupId}
              onClick={() => {
                if (sendGroupId) {
                  onSend(mat, sendGroupId);
                  setSendOpen(false);
                }
              }}
              style={{
                padding: "7px 16px",
                borderRadius: 8,
                fontSize: 13,
                background: sendGroupId ? "linear-gradient(135deg,#6c63ff,#a855f7)" : "#444",
                color: "#fff",
                border: "none",
                cursor: sendGroupId ? "pointer" : "not-allowed",
                fontWeight: 600,
              }}
            >
              📤 Yuborish
            </button>
            <button
              onClick={() => setSendOpen(false)}
              style={{
                padding: "7px 12px",
                borderRadius: 8,
                fontSize: 13,
                border: "1px solid var(--border-color,#2a2a3e)",
                background: "transparent",
                cursor: "pointer",
                color: "inherit",
              }}
            >
              ✕
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function UploadModal({
  onClose,
  onSaved,
  onApiCall,
  editItem,
  subjects,
}: {
  onClose: () => void;
  onSaved: () => void;
  onApiCall: (path: string, payload?: GenericRow, method?: string) => Promise<GenericRow | null>;
  editItem: GenericRow | null;
  subjects: string[];
}) {
  const tt = useWebT();
  const [title, setTitle] = useState(String(editItem?.title || ""));
  const [description, setDescription] = useState(String(editItem?.description || ""));
  const [subject, setSubject] = useState(String(editItem?.subject || ""));
  const [fileUrl, setFileUrl] = useState(String(editItem?.file_url || ""));
  const [fileType, setFileType] = useState(String(editItem?.file_type || "other"));
  const [fileSize, setFileSize] = useState(Number(editItem?.file_size || 0));
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = useCallback(async (file: File) => {
    setUploading(true);
    setError("");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch("/api/teacher/upload/material", {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("diamond_token") || ""}` },
        body: formData,
      });
      const data = await res.json();
      if (data.url) {
        setFileUrl(data.url);
        setFileType(data.file_type || "other");
        setFileSize(data.file_size || 0);
        if (!title && data.original_name) setTitle(data.original_name.replace(/\.[^.]+$/, ""));
      } else {
        setError("Fayl yuklab bo'lmadi");
      }
    } catch {
      setError("Fayl yuklab bo'lmadi");
    }
    setUploading(false);
  }, [title]);

  const handleSave = async () => {
    if (!title.trim()) { setError("Nom kiritish majburiy"); return; }
    if (!fileUrl.trim() && !editItem) { setError("Fayl yuklanmagan"); return; }
    setSaving(true);
    setError("");
    const payload: GenericRow = { title, description, subject, is_public: true };
    if (fileUrl && !editItem) {
      Object.assign(payload, { file_url: fileUrl, file_type: fileType, file_size: fileSize });
    }
    let ok: GenericRow | null;
    if (editItem) {
      ok = await onApiCall(`/teacher/materials/${editItem.id}`, payload, "PATCH");
    } else {
      ok = await onApiCall("/teacher/materials", payload, "POST");
    }

    setSaving(false);
    if (ok) { onSaved(); onClose(); }
    else setError("Saqlashda xato");
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "#0009",
        zIndex: 9998,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
    >
      <div
        style={{
          background: "var(--card-bg,#1e1e2e)",
          borderRadius: 18,
          padding: 28,
          width: "100%",
          maxWidth: 520,
          boxShadow: "0 24px 60px #0006",
          border: "1px solid var(--border-color,#2a2a3e)",
        }}
      >
        <h3 style={{ margin: "0 0 20px", fontSize: 18, fontWeight: 700 }}>
          {editItem ? "✏️ Material tahrirlash" : tt("teacher.materials.add", "New Material")}
        </h3>

        {/* File upload area */}
        {!editItem && (
          <div
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const f = e.dataTransfer.files[0];
              if (f) handleFileSelect(f);
            }}
            style={{
              border: `2px dashed ${fileUrl ? "#10b981" : "var(--border-color,#2a2a3e)"}`,
              borderRadius: 12,
              padding: "24px",
              textAlign: "center",
              cursor: "pointer",
              marginBottom: 16,
              transition: "border .2s",
              background: fileUrl ? "#10b98111" : "transparent",
            }}
          >
            <input
              ref={fileRef}
              type="file"
              style={{ display: "none" }}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFileSelect(f);
              }}
            />
            {uploading ? (
              <div style={{ color: "#a78bfa" }}>⏳ Yuklanmoqda...</div>
            ) : fileUrl ? (
              <div style={{ color: "#10b981" }}>✅ Fayl yuklandi</div>
            ) : (
              <div style={{ opacity: 0.6, fontSize: 14 }}>
                📎 {tt("teacher.materials.uploadDrop", "Select file or drag here")}
              </div>
            )}
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div>
            <label style={{ fontSize: 12, opacity: 0.6, marginBottom: 4, display: "block" }}>
              {tt("teacher.materials.titleLabel", "Title")} *
            </label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Material nomi"
              style={{
                width: "100%",
                padding: "9px 12px",
                borderRadius: 9,
                border: "1px solid var(--border-color,#2a2a3e)",
                background: "var(--surface-2,#16213e)",
                color: "inherit",
                fontSize: 14,
                boxSizing: "border-box",
              }}
            />
          </div>
          <div>
            <label style={{ fontSize: 12, opacity: 0.6, marginBottom: 4, display: "block" }}>
              {tt("teacher.materials.descLabel", "Description")}
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              style={{
                width: "100%",
                padding: "9px 12px",
                borderRadius: 9,
                border: "1px solid var(--border-color,#2a2a3e)",
                background: "var(--surface-2,#16213e)",
                color: "inherit",
                fontSize: 14,
                resize: "vertical",
                boxSizing: "border-box",
              }}
            />
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 12, opacity: 0.6, marginBottom: 4, display: "block" }}>
                {tt("teacher.materials.subjectLabel", "Subject")}
              </label>
              <select
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                style={{
                  width: "100%",
                  padding: "9px 10px",
                  borderRadius: 9,
                  border: "1px solid var(--border-color,#2a2a3e)",
                  background: "var(--surface-2,#16213e)",
                  color: "inherit",
                  fontSize: 14,
                }}
              >
                <option value="">— Fan —</option>
                {subjects.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {error ? <p style={{ color: "#ef4444", fontSize: 13, marginTop: 10, marginBottom: 0 }}>{error}</p> : null}

        <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
          <button
            onClick={handleSave}
            disabled={saving || uploading}
            style={{
              flex: 1,
              padding: "10px",
              borderRadius: 10,
              border: "none",
              background: "linear-gradient(135deg,#6c63ff,#a855f7)",
              color: "#fff",
              fontWeight: 700,
              fontSize: 14,
              cursor: saving || uploading ? "not-allowed" : "pointer",
              opacity: saving || uploading ? 0.7 : 1,
            }}
          >
            {saving ? "Saqlanmoqda..." : tt("teacher.materials.saveBtn", "Save")}
          </button>
          <button
            onClick={onClose}
            style={{
              padding: "10px 18px",
              borderRadius: 10,
              border: "1px solid var(--border-color,#2a2a3e)",
              background: "transparent",
              cursor: "pointer",
              fontSize: 14,
              color: "inherit",
            }}
          >
            {tt("teacher.materials.cancelBtn", "Cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}

export function TeacherMaterialsPanel({
  onApiCall,
  groups,
}: {
  onApiCall: (path: string, payload?: GenericRow, method?: string, successText?: string) => Promise<GenericRow | null>;
  groups: GenericRow[];
}) {
  const tt = useWebT();
  const [items, setItems] = useState<GenericRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [myOnly, setMyOnly] = useState(false);
  const [subject, setSubject] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editItem, setEditItem] = useState<GenericRow | null>(null);
  const [selfId, setSelfId] = useState<number>(0);

  const SUBJECTS = ["English", "Russian", "Matematika", "Ona tili", "Tarix", "Arab tili"];

  const load = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (myOnly) params.set("my_only", "true");
    if (subject) params.set("subject", subject);
    params.set("limit", "80");
    const res = await onApiCall(`/teacher/materials?${params}`, undefined, "GET");
    setItems((res?.items as GenericRow[]) || []);
    setLoading(false);
  }, [myOnly, subject, onApiCall]);

  useEffect(() => {
    load();
    // Get self id
    try {
      const token = localStorage.getItem("diamond_token") || "";
      if (token) {
        const payload = JSON.parse(atob(token.split(".")[1]));
        setSelfId(Number(payload.user_id || payload.sub || 0));
      }
    } catch { /* ignore */ }
  }, [load]);

  const handleDelete = async (mat: GenericRow) => {
    if (!confirm(tt("teacher.materials.deleteConfirm", "Delete this material?"))) return;
    await onApiCall(`/teacher/materials/${mat.id}`, undefined, "DELETE", "O'chirildi");
    load();
  };

  const handleSend = async (mat: GenericRow, groupId: number) => {
    await onApiCall(`/teacher/materials/${mat.id}/send`, { group_id: groupId }, "POST", "Guruhga yuborildi ✅");
  };


  return (
    <div className="page-stack">
      <style>{`
        .material-card:hover { box-shadow: 0 8px 32px #6c63ff22; }
      `}</style>

      {/* Header */}
      <section className="panel-card">
        <div className="row-between" style={{ flexWrap: "wrap", gap: 12 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>
              📚 {tt("teacher.materials.title", "Materials Library")}
            </h2>
            <p style={{ margin: "4px 0 0", opacity: 0.6, fontSize: 14 }}>
              Materiallaringizni boshqaring va ulashing
            </p>
          </div>
          <button
            onClick={() => { setEditItem(null); setModalOpen(true); }}
            style={{
              padding: "10px 20px",
              borderRadius: 10,
              border: "none",
              background: "linear-gradient(135deg,#6c63ff,#a855f7)",
              color: "#fff",
              fontWeight: 700,
              fontSize: 14,
              cursor: "pointer",
            }}
          >
            + {tt("teacher.materials.add", "New Material")}
          </button>
        </div>

        {/* Filters */}
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 16 }}>
          <button
            onClick={() => setMyOnly(false)}
            style={{
              padding: "7px 16px",
              borderRadius: 20,
              border: "1px solid var(--border-color,#2a2a3e)",
              background: !myOnly ? "linear-gradient(135deg,#6c63ff,#a855f7)" : "transparent",
              color: !myOnly ? "#fff" : "inherit",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {tt("teacher.materials.filterAll", "All")}
          </button>
          <button
            onClick={() => setMyOnly(true)}
            style={{
              padding: "7px 16px",
              borderRadius: 20,
              border: "1px solid var(--border-color,#2a2a3e)",
              background: myOnly ? "linear-gradient(135deg,#6c63ff,#a855f7)" : "transparent",
              color: myOnly ? "#fff" : "inherit",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {tt("teacher.materials.filterMy", "My materials")}
          </button>
          <select
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            style={{
              padding: "7px 12px",
              borderRadius: 20,
              border: "1px solid var(--border-color,#2a2a3e)",
              background: "var(--card-bg,#1e1e2e)",
              color: "inherit",
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            <option value="">Barcha fanlar</option>
            {SUBJECTS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </section>

      {/* Grid */}
      <section className="panel-card">
        {loading ? (
          <div style={{ textAlign: "center", padding: 40, opacity: 0.5 }}>⏳ Yuklanmoqda...</div>
        ) : items.length === 0 ? (
          <div style={{ textAlign: "center", padding: 40, opacity: 0.5 }}>
            📭 {tt("teacher.materials.noItems", "No materials found")}
          </div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
              gap: 16,
            }}
          >
            {items.map((mat) => (
              <MaterialCard
                key={String(mat.id)}
                mat={mat}
                isSelf={Number(mat.teacher_id) === selfId}
                tt={tt}
                groups={groups}
                onEdit={(m) => { setEditItem(m); setModalOpen(true); }}
                onDelete={handleDelete}
                onSend={handleSend}
              />
            ))}
          </div>
        )}
      </section>

      {modalOpen ? (
        <UploadModal
          onClose={() => { setModalOpen(false); setEditItem(null); }}
          onSaved={load}
          onApiCall={onApiCall}
          editItem={editItem}
          subjects={SUBJECTS}
        />
      ) : null}
    </div>
  );
}
