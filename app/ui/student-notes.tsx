"use client";

import { useState, useEffect, useCallback } from "react";

type GenericRow = Record<string, unknown>;

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";

async function apiFetch(path: string, options?: RequestInit): Promise<GenericRow | null> {
  try {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") || "" : "";
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(options?.headers || {}) },
      ...options,
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function NoteCard({
  note,
  isTeacher,
  onDelete,
  onEdit,
}: {
  note: GenericRow;
  isTeacher: boolean;
  onDelete?: (id: number) => void;
  onEdit?: (note: GenericRow) => void;
}) {
  const id = Number(note.id || 0);
  const text = String(note.note || note.content || "");
  const createdAt = String(note.created_at || "").slice(0, 16).replace("T", " ");
  const teacherName = note.teacher_name
    ? String(note.teacher_name)
    : note.teacher_first_name
    ? `${String(note.teacher_first_name)} ${note.teacher_last_name ? String(note.teacher_last_name) : ""}`.trim()
    : null;

  const isPinned = Boolean(note.is_pinned);
  const tagColor = String(note.tag_color || "#6c63ff");
  const tag = String(note.tag || "");

  return (
    <article
      style={{
        position: "relative",
        background: "var(--surface-2,#16213e)",
        border: `1px solid ${isPinned ? tagColor + "66" : "var(--border-color,#2a2a3e)"}`,
        borderLeft: `4px solid ${tagColor}`,
        borderRadius: 14,
        padding: "16px 18px",
        transition: "box-shadow .2s, transform .2s",
        cursor: "default",
      }}
    >
      {/* Top row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8, marginBottom: 10 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          {isTeacher && (
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                background: "#6c63ff22",
                color: "#a78bfa",
                borderRadius: 8,
                padding: "2px 10px",
                letterSpacing: 0.5,
              }}
            >
              👨‍🏫 O'qituvchi
            </span>
          )}
          {!isTeacher && (
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                background: "#10b98122",
                color: "#10b981",
                borderRadius: 8,
                padding: "2px 10px",
              }}
            >
              📓 Shaxsiy
            </span>
          )}
          {isPinned && (
            <span style={{ fontSize: 11, background: "#f59e0b22", color: "#f59e0b", borderRadius: 8, padding: "2px 8px" }}>
              📌 Muhim
            </span>
          )}
          {tag && (
            <span
              style={{
                fontSize: 11,
                borderRadius: 8,
                padding: "2px 10px",
                background: tagColor + "22",
                color: tagColor,
                fontWeight: 600,
              }}
            >
              {tag}
            </span>
          )}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ fontSize: 11, opacity: 0.45, whiteSpace: "nowrap" }}>{createdAt}</span>
          {!isTeacher && onEdit && (
            <button
              onClick={() => onEdit(note)}
              style={{ background: "none", border: "none", cursor: "pointer", fontSize: 13, opacity: 0.7, color: "#3b82f6" }}
              title="Tahrirlash"
            >
              ✏️
            </button>
          )}
          {!isTeacher && onDelete && (
            <button
              onClick={() => onDelete(id)}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                fontSize: 14,
                opacity: 0.5,
                lineHeight: 1,
                padding: "2px 4px",
                borderRadius: 6,
                color: "#ef4444",
              }}
              title="O'chirish"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {/* Teacher name */}
      {teacherName && (
        <div style={{ fontSize: 12, opacity: 0.6, marginBottom: 6 }}>
          {teacherName}
        </div>
      )}

      {/* Text */}
      <p style={{ margin: 0, lineHeight: 1.65, whiteSpace: "pre-wrap", fontSize: 14 }}>{text}</p>
    </article>
  );
}


const TAG_OPTIONS = [
  { label: "Grammatika", color: "#6c63ff" },
  { label: "Lug'at", color: "#10b981" },
  { label: "Talaffuz", color: "#f59e0b" },
  { label: "Eslatma", color: "#a855f7" },
  { label: "Vazifa", color: "#ef4444" },
  { label: "Maqsad", color: "#3b82f6" },
];

export function StudentNotesPanel() {
  const [teacherNotes, setTeacherNotes] = useState<GenericRow[]>([]);
  const [myNotes, setMyNotes] = useState<GenericRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"teacher" | "mine">("teacher");
  const [addOpen, setAddOpen] = useState(false);
  const [editingNote, setEditingNote] = useState<GenericRow | null>(null);
  const [noteText, setNoteText] = useState("");
  const [selectedTag, setSelectedTag] = useState(TAG_OPTIONS[0]);
  const [isPinned, setIsPinned] = useState(false);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");
  const [filterTag, setFilterTag] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    const [tRes, mRes] = await Promise.all([
      apiFetch("/student/teacher-notes"),
      apiFetch("/student/notes/mine"),
    ]);
    setTeacherNotes((tRes?.items as GenericRow[]) || []);
    setMyNotes((mRes?.items as GenericRow[]) || []);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    if (!noteText.trim()) return;
    setSaving(true);
    if (editingNote) {
      await apiFetch(`/student/notes/${editingNote.id}`, {
        method: "PUT",
        body: JSON.stringify({ content: noteText.trim() }),
      });
    } else {
      await apiFetch("/student/notes", {
        method: "POST",
        body: JSON.stringify({ content: noteText.trim(), tag: selectedTag.label, tag_color: selectedTag.color, is_pinned: isPinned }),
      });
    }
    setNoteText("");
    setEditingNote(null);
    setAddOpen(false);
    setIsPinned(false);
    await load();
    setSaving(false);
  };

  const handleStartEdit = (n: GenericRow) => {
    setEditingNote(n);
    setNoteText(String(n.content || n.note || ""));
    setAddOpen(true);
  };

  const handleDelete = async (id: number) => {
    await apiFetch(`/student/notes/${id}`, { method: "DELETE" });
    setMyNotes((prev) => prev.filter((n) => Number(n.id) !== id));
  };


  const teacherFiltered = teacherNotes.filter((n) => {
    const text = String(n.note || n.content || "").toLowerCase();
    const tag = String(n.tag || "");
    return (
      (!search || text.includes(search.toLowerCase())) &&
      (!filterTag || tag === filterTag)
    );
  });

  const myFiltered = myNotes.filter((n) => {
    const text = String(n.note || n.content || "").toLowerCase();
    const tag = String(n.tag || "");
    return (
      (!search || text.includes(search.toLowerCase())) &&
      (!filterTag || tag === filterTag)
    );
  });

  const pinnedFirst = (arr: GenericRow[]) =>
    [...arr.filter((n) => n.is_pinned), ...arr.filter((n) => !n.is_pinned)];

  return (
    <div className="page-stack">
      <style>{`
        .note-tab { cursor:pointer; padding: 8px 20px; border-radius:20px; font-weight:600; font-size:13px; border:1px solid var(--border-color,#2a2a3e); transition:all .2s; background:transparent; color:inherit; }
        .note-tab.active { background: linear-gradient(135deg,#6c63ff,#a855f7); color:#fff; border-color:transparent; }
        .notes-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:14px; }
        .note-add-form { display:flex; flex-direction:column; gap:12px; }
        .note-add-form textarea { background:var(--surface-2,#16213e); border:1px solid var(--border-color,#2a2a3e); border-radius:10px; padding:12px; font-size:14px; color:inherit; resize:vertical; min-height:100px; outline:none; transition:border .2s; }
        .note-add-form textarea:focus { border-color:#6c63ff; }
      `}</style>

      {/* Header */}
      <section className="panel-card">
        <div className="row-between" style={{ flexWrap: "wrap", gap: 12 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>📓 My Notes</h2>
            <p style={{ margin: "4px 0 0", opacity: 0.6, fontSize: 14 }}>
              O'qituvchi eslatmalari va shaxsiy qaydlarim
            </p>
          </div>
          <button
            onClick={() => setAddOpen((v) => !v)}
            style={{
              padding: "9px 18px",
              borderRadius: 10,
              border: "none",
              background: "linear-gradient(135deg,#6c63ff,#a855f7)",
              color: "#fff",
              cursor: "pointer",
              fontWeight: 700,
              fontSize: 13,
            }}
          >
            {addOpen ? "✕ Yopish" : "+ Yangi not"}
          </button>
        </div>

        {/* Add Note Form */}
        {addOpen && (
          <div className="note-add-form" style={{ marginTop: 18, paddingTop: 18, borderTop: "1px solid var(--border-color,#2a2a3e)" }}>
            <textarea
              placeholder="Eslatmangizni yozing..."
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
            />
            {/* Tag selector */}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {TAG_OPTIONS.map((t) => (
                <button
                  key={t.label}
                  type="button"
                  onClick={() => setSelectedTag(t)}
                  style={{
                    padding: "4px 14px",
                    borderRadius: 20,
                    border: `2px solid ${t.color}`,
                    background: selectedTag.label === t.label ? t.color : "transparent",
                    color: selectedTag.label === t.label ? "#fff" : t.color,
                    cursor: "pointer",
                    fontSize: 12,
                    fontWeight: 600,
                    transition: "all .15s",
                  }}
                >
                  {t.label}
                </button>
              ))}
            </div>
            {/* Pinned toggle */}
            <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer", fontSize: 13 }}>
              <input
                type="checkbox"
                checked={isPinned}
                onChange={(e) => setIsPinned(e.target.checked)}
                style={{ width: 16, height: 16, accentColor: "#f59e0b" }}
              />
              📌 Muhim (pinned) sifatida belgilash
            </label>
            <div style={{ display: "flex", gap: 10 }}>
              <button
                onClick={handleSave}
                disabled={saving || !noteText.trim()}
                style={{
                  padding: "9px 20px",
                  borderRadius: 10,
                  border: "none",
                  background: "linear-gradient(135deg,#6c63ff,#a855f7)",
                  color: "#fff",
                  cursor: saving ? "not-allowed" : "pointer",
                  fontWeight: 700,
                  fontSize: 13,
                  opacity: saving || !noteText.trim() ? 0.6 : 1,
                }}
              >
                {saving ? "Saqlanmoqda..." : "💾 Saqlash"}
              </button>
              <button
                type="button"
                onClick={() => { setAddOpen(false); setNoteText(""); }}
                style={{
                  padding: "9px 16px",
                  borderRadius: 10,
                  border: "1px solid var(--border-color,#2a2a3e)",
                  background: "transparent",
                  color: "inherit",
                  cursor: "pointer",
                  fontSize: 13,
                }}
              >
                Bekor
              </button>
            </div>
          </div>
        )}
      </section>

      {/* Tabs + Search */}
      <section className="panel-card" style={{ paddingTop: 14, paddingBottom: 14 }}>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className={`note-tab${tab === "teacher" ? " active" : ""}`}
              onClick={() => setTab("teacher")}
            >
              👨‍🏫 O'qituvchi ({teacherNotes.length})
            </button>
            <button
              className={`note-tab${tab === "mine" ? " active" : ""}`}
              onClick={() => setTab("mine")}
            >
              📓 Mening notlarim ({myNotes.length})
            </button>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              type="search"
              placeholder="Qidirish..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                padding: "6px 14px",
                borderRadius: 8,
                border: "1px solid var(--border-color,#2a2a3e)",
                background: "var(--surface-2,#16213e)",
                color: "inherit",
                fontSize: 13,
                outline: "none",
                width: 160,
              }}
            />
            <select
              value={filterTag}
              onChange={(e) => setFilterTag(e.target.value)}
              style={{
                padding: "6px 10px",
                borderRadius: 8,
                border: "1px solid var(--border-color,#2a2a3e)",
                background: "var(--surface-2,#16213e)",
                color: "inherit",
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              <option value="">Barcha teglar</option>
              {TAG_OPTIONS.map((t) => (
                <option key={t.label} value={t.label}>{t.label}</option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {/* Content */}
      {loading ? (
        <section className="panel-card">
          <div style={{ textAlign: "center", padding: 48, opacity: 0.5 }}>⏳ Yuklanmoqda...</div>
        </section>
      ) : tab === "teacher" ? (
        teacherFiltered.length === 0 ? (
          <section className="panel-card">
            <div style={{ textAlign: "center", padding: 48 }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>📭</div>
              <p style={{ opacity: 0.6 }}>O'qituvchidan hech qanday eslatma yo'q</p>
            </div>
          </section>
        ) : (
          <div className="notes-grid">
            {pinnedFirst(teacherFiltered).map((note) => (
              <NoteCard key={String(note.id)} note={note} isTeacher={true} />
            ))}
          </div>
        )
      ) : (
        myFiltered.length === 0 ? (
          <section className="panel-card">
            <div style={{ textAlign: "center", padding: 48 }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>✍️</div>
              <p style={{ opacity: 0.6 }}>Hali hech qanday not qo'shmagansiz</p>
              <button
                onClick={() => setAddOpen(true)}
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
                + Birinchi notni qo'shish
              </button>
            </div>
          </section>
        ) : (
          <div className="notes-grid">
            {pinnedFirst(myFiltered).map((note) => (
              <NoteCard key={String(note.id)} note={note} isTeacher={false} onDelete={handleDelete} onEdit={handleStartEdit} />
            ))}

          </div>
        )
      )}

      {/* Stats bar */}
      {!loading && (
        <section className="panel-card" style={{ paddingTop: 12, paddingBottom: 12 }}>
          <div style={{ display: "flex", gap: 20, flexWrap: "wrap", fontSize: 13, opacity: 0.7 }}>
            <span>📌 Muhim: <strong>{[...teacherNotes, ...myNotes].filter((n) => n.is_pinned).length}</strong></span>
            <span>👨‍🏫 O'qituvchi: <strong>{teacherNotes.length}</strong></span>
            <span>📓 Shaxsiy: <strong>{myNotes.length}</strong></span>
            <span>📊 Jami: <strong>{teacherNotes.length + myNotes.length}</strong></span>
          </div>
        </section>
      )}
    </div>
  );
}
