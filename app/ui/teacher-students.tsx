import { useState, useEffect } from "react";
import { useWebT } from "./web-i18n";
import { ModalPortal } from "./modal-portal";

export function TeacherStudents({ token, onApiCall }: { token: string; onApiCall: any }) {
  const tt = useWebT();
  const [students, setStudents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editingStudent, setEditingStudent] = useState<any | null>(null);
  const [saving, setSaving] = useState(false);

  const [resetPasswordInfo, setResetPasswordInfo] = useState<any>(null);
  const [resettingId, setResettingId] = useState<number | null>(null);

  const [notesStudent, setNotesStudent] = useState<any | null>(null);
  const [studentNotesList, setStudentNotesList] = useState<any[]>([]);
  const [loadingNotes, setLoadingNotes] = useState(false);
  const [newNoteText, setNewNoteText] = useState("");
  const [newNoteVisible, setNewNoteVisible] = useState(true);
  const [savingNote, setSavingNote] = useState(false);

  const handleOpenNotes = async (s: any) => {
    setNotesStudent(s);
    setLoadingNotes(true);
    try {
      const res = await onApiCall(`/teacher/students/${s.id}/notes`, undefined, "GET");
      setStudentNotesList(res?.items || []);
    } catch {
      setStudentNotesList([]);
    } finally {
      setLoadingNotes(false);
    }
  };

  const handleCreateNote = async () => {
    if (!newNoteText.trim() || !notesStudent) return;
    setSavingNote(true);
    try {
      await onApiCall(
        `/teacher/students/${notesStudent.id}/notes`,
        { note_text: newNoteText.trim(), is_visible: newNoteVisible },
        "POST",
        "Eslatma yaratildi"
      );
      setNewNoteText("");
      const res = await onApiCall(`/teacher/students/${notesStudent.id}/notes`, undefined, "GET");
      setStudentNotesList(res?.items || []);
    } catch (err: any) {
      alert("Xatolik: " + err.message);
    } finally {
      setSavingNote(false);
    }
  };

  const [editingNoteId, setEditingNoteId] = useState<number | null>(null);
  const [editNoteText, setEditNoteText] = useState("");
  const [editNoteVisible, setEditNoteVisible] = useState(true);

  const handleUpdateNote = async (noteId: number) => {
    if (!editNoteText.trim() || !notesStudent) return;
    try {
      await onApiCall(
        `/teacher/students/${notesStudent.id}/notes/${noteId}`,
        { note_text: editNoteText.trim(), is_visible: editNoteVisible },
        "PUT",
        "Eslatma tahrirlandi"
      );
      setEditingNoteId(null);
      const res = await onApiCall(`/teacher/students/${notesStudent.id}/notes`, undefined, "GET");
      setStudentNotesList(res?.items || []);
    } catch (err: any) {
      alert("Xatolik: " + err.message);
    }
  };

  const handleDeleteNote = async (noteId: number) => {
    if (!notesStudent) return;
    try {
      await onApiCall(
        `/teacher/students/${notesStudent.id}/notes/${noteId}`,
        undefined,
        "DELETE",
        "Eslatma o'chirildi"
      );
      setStudentNotesList((prev) => prev.filter((n) => n.id !== noteId));
    } catch (err: any) {
      alert("Xatolik: " + err.message);
    }
  };


  const copyText = async (txt: string) => {

    try {
      await navigator.clipboard.writeText(txt);
      alert(tt("common.copied", "Nusxalandi"));
    } catch {
      alert(tt("common.copyFailed", "Nusxalash imkoni bo'lmadi"));
    }
  };

  const loadStudents = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await onApiCall("/teacher/my-students", undefined, "GET");
      setStudents(data);
    } catch (err: any) {
      setError(err.message || "Xatolik yuz berdi");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStudents();
  }, [token]);

  const handleSave = async (e: any) => {
    e.preventDefault();
    setSaving(true);
    try {
      await onApiCall(
        `/teacher/my-students/${editingStudent.id}`,
        {
          first_name: editingStudent.first_name,
          last_name: editingStudent.last_name,
          phone: editingStudent.phone,
          parent_phone: editingStudent.parent_phone,
          subject: editingStudent.subject,
          level: editingStudent.level,
        },
        "PUT",
        "Ma'lumotlar saqlandi"
      );
      setEditingStudent(null);
      loadStudents();
    } catch (err: any) {
      alert("Xatolik: " + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleResetPassword = async (s: any) => {
    if (resettingId) return;
    setResettingId(s.id);
    try {
      const result = await onApiCall(
        `/teacher/my-students/${s.id}/reset-password`,
        {},
        "POST",
        "Parol tiklandi"
      );
      setResetPasswordInfo({
        userId: s.id,
        userName: `${s.first_name || ""} ${s.last_name || ""}`.trim() || "-",
        loginId: s.login_id || `#${s.id}`,
        password: result.password,
        qr_payload: result.qr_payload,
        qr_token: result.qr_token,
        qr_expires_at: result.qr_expires_at,
      });
    } catch (err: any) {
      alert("Xatolik: " + err.message);
    } finally {
      setResettingId(null);
    }
  };

  return (
    <div className="page-stack">
      <div className="row-between mb-4">
        <h2>{tt("students", "Mening O'quvchilarim")} ({students.length})</h2>
        {loading && <span className="chip">Yuklanmoqda...</span>}
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>{tt("common.name", "Ism")}</th>
              <th>{tt("common.phone", "Telefon")}</th>
              <th>{tt("common.level", "Daraja")}</th>
              <th>{tt("common.subject", "Fan")}</th>
              <th>{tt("common.actions", "Amallar")}</th>
            </tr>
          </thead>
          <tbody>
            {students.map((s: any, idx: number) => (
              <tr key={s.id}>
                <td className="text-ink-400 dark:text-navy-500 text-xs">{idx + 1}</td>
                <td className="font-semibold">{`${s.first_name || ""} ${s.last_name || ""}`.trim() || "-"}</td>
                <td className="text-sm text-ink-600 dark:text-navy-300">{s.phone || "-"}</td>
                <td>
                  <span className="chip">{s.level || "-"}</span>
                </td>
                <td className="text-sm text-ink-600 dark:text-navy-300">{s.subject || "-"}</td>
                <td>
                  <div className="button-grid inline">
                    <button
                      className="btn btn-soft small"
                      onClick={() => setEditingStudent({ ...s })}
                    >
                      {tt("common.edit", "Tahrirlash")}
                    </button>
                    <button
                      className="btn btn-soft small"
                      style={{ color: "#a78bfa" }}
                      onClick={() => handleOpenNotes(s)}
                    >
                      📝 {tt("teacher.notes", "Notes")}
                    </button>
                    <button
                      className="btn btn-soft small"
                      onClick={() => handleResetPassword(s)}
                      disabled={resettingId === s.id}
                    >
                      {resettingId === s.id ? "..." : tt("admin.users.action.resetPass", "Parol")}
                    </button>

                  </div>
                </td>
              </tr>
            ))}
            {students.length === 0 && !loading ? (
              <tr>
                <td colSpan={6} className="text-center py-8 text-sm text-ink-400 font-semibold">
                  O&apos;quvchi topilmadi
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {/* Edit Modal */}
      <ModalPortal open={Boolean(editingStudent)}>
        {editingStudent && (
          <div className="overlay-modal-backdrop" onClick={() => setEditingStudent(null)}>
            <article className="overlay-modal-card" onClick={(e) => e.stopPropagation()}>
              <h3 className="modal-title">Student tahrirlash</h3>
              <form onSubmit={handleSave} className="grid grid-1 gap-4">
                <label>
                  Ism
                  <input
                    required
                    value={editingStudent.first_name || ""}
                    onChange={(e) =>
                      setEditingStudent({ ...editingStudent, first_name: e.target.value })
                    }
                  />
                </label>
                <label>
                  Familiya
                  <input
                    value={editingStudent.last_name || ""}
                    onChange={(e) =>
                      setEditingStudent({ ...editingStudent, last_name: e.target.value })
                    }
                  />
                </label>
                <label>
                  Telefon
                  <input
                    required
                    value={editingStudent.phone || ""}
                    onChange={(e) =>
                      setEditingStudent({ ...editingStudent, phone: e.target.value })
                    }
                  />
                </label>
                <label>
                  Ota-ona telefoni
                  <input
                    value={editingStudent.parent_phone || ""}
                    onChange={(e) =>
                      setEditingStudent({ ...editingStudent, parent_phone: e.target.value })
                    }
                  />
                </label>
                <div className="flex gap-4">
                  <button type="submit" className="btn btn-primary flex-1" disabled={saving}>
                    {saving ? "Saqlanmoqda..." : "Saqlash"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-soft flex-1"
                    onClick={() => setEditingStudent(null)}
                  >
                    Bekor qilish
                  </button>
                </div>
              </form>
            </article>
          </div>
        )}
      </ModalPortal>

      {/* Reset Password Result Modal */}
      <ModalPortal open={Boolean(resetPasswordInfo)}>
        {resetPasswordInfo && (
          <div className="overlay-modal-backdrop" onClick={() => setResetPasswordInfo(null)}>
            <article
              className="overlay-modal-card admin-wide-modal"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="row-between gap-3 mb-4">
                <h3 className="font-bold text-lg text-green-600 dark:text-green-400 flex items-center gap-2">
                  🔑 {tt("admin.users.resetResult", "Parolni tiklash natijasi")}
                </h3>
                <button
                  className="btn btn-soft small"
                  type="button"
                  onClick={() => setResetPasswordInfo(null)}
                >
                  {tt("common.close", "Yopish")}
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div className="flex flex-col gap-1 p-4 bg-white dark:bg-navy-900/50 rounded-xl border border-green-200 dark:border-green-500/20">
                  <span className="text-xs font-bold text-ink-400 uppercase tracking-wider">
                    {tt("common.user", "Foydalanuvchi")}
                  </span>
                  <strong className="font-bold text-navy-900 dark:text-white">
                    {resetPasswordInfo.userName}
                  </strong>
                </div>
                <div className="flex flex-col gap-1 p-4 bg-white dark:bg-navy-900/50 rounded-xl border border-green-200 dark:border-green-500/20">
                  <span className="text-xs font-bold text-ink-400 uppercase tracking-wider">
                    {tt("common.loginId", "Login ID")}
                  </span>
                  <strong className="font-mono font-bold text-navy-900 dark:text-white">
                    {resetPasswordInfo.loginId}
                  </strong>
                </div>
                <div className="flex flex-col gap-1 p-4 bg-white dark:bg-navy-900/50 rounded-xl border border-green-200 dark:border-green-500/20">
                  <span className="text-xs font-bold text-ink-400 uppercase tracking-wider">
                    {tt("common.password", "Parol")}
                  </span>
                  <strong className="font-mono font-bold text-navy-900 dark:text-white text-lg">
                    {resetPasswordInfo.password}
                  </strong>
                </div>
              </div>
              {resetPasswordInfo.qr_payload && (
                <div className="flex flex-col md:flex-row gap-6 p-4 bg-surface-soft dark:bg-white/5 rounded-xl border border-line dark:border-white/10 mb-4">
                  <img
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=${encodeURIComponent(
                      String(resetPasswordInfo.qr_payload || "")
                    )}`}
                    alt="QR"
                    className="w-48 h-48 rounded-lg bg-white p-2 shrink-0 border border-line dark:border-white/10"
                  />
                  <div className="flex flex-col gap-2 justify-center">
                    <p className="text-sm font-medium text-ink-500 dark:text-navy-200">
                      Ushbu QR kodni ilova yoki veb-sayt orqali skanerlang.
                    </p>
                    <div className="kv">
                      <span>QR expires</span>
                      <strong>{new Date(resetPasswordInfo.qr_expires_at).toLocaleString()}</strong>
                    </div>
                    <div className="kv">
                      <span>QR token</span>
                      <strong>{resetPasswordInfo.qr_token}</strong>
                    </div>
                  </div>
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <button
                  className="px-5 py-2.5 text-sm font-bold text-white bg-green-500 hover:bg-green-600 rounded-xl transition-all"
                  onClick={() => copyText(resetPasswordInfo.password)}
                >
                  {tt("common.copyPassword", "Parolni nusxalash")}
                </button>
                <button
                  className="px-5 py-2.5 text-sm font-bold text-white bg-navy-700 hover:bg-navy-800 rounded-xl transition-all"
                  onClick={() =>
                    copyText(`${resetPasswordInfo.loginId} / ${resetPasswordInfo.password}`)
                  }
                >
                  {tt("common.copyLoginPassword", "Login va parolni nusxalash")}
                </button>
                <button
                  className="px-5 py-2.5 text-sm font-bold bg-surface-soft dark:bg-white/5 border border-line dark:border-white/10 text-ink-600 dark:text-navy-200 rounded-xl hover:border-red-400 hover:text-red-500 transition-all"
                  onClick={() => setResetPasswordInfo(null)}
                >
                  {tt("common.clear", "Tozalash")}
                </button>
              </div>
            </article>
          </div>
        )}
      </ModalPortal>

      {/* Student Notes Modal */}
      <ModalPortal open={Boolean(notesStudent)}>
        {notesStudent && (
          <div className="overlay-modal-backdrop" onClick={() => setNotesStudent(null)}>
            <article className="overlay-modal-card admin-wide-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 640 }}>
              <div className="row-between gap-3 mb-4">
                <div>
                  <h3 className="font-bold text-lg">📝 Student Eslatmalari</h3>
                  <p className="text-xs text-ink-500">{notesStudent.first_name} {notesStudent.last_name}</p>
                </div>
                <button className="btn btn-soft small" type="button" onClick={() => setNotesStudent(null)}>
                  ✕
                </button>
              </div>

              {/* Add Note Form */}
              <div className="p-4 bg-surface-soft dark:bg-white/5 rounded-xl border border-line dark:border-white/10 mb-4 flex flex-col gap-3">
                <textarea
                  className="w-full p-3 rounded-lg border border-line dark:border-white/10 bg-white dark:bg-navy-900 text-sm outline-none resize-none"
                  rows={3}
                  placeholder="Yangi izoh yozing (masalan: Grammatikaga ko'proq urg'u berish kerak)..."
                  value={newNoteText}
                  onChange={(e) => setNewNoteText(e.target.value)}
                />
                <div className="flex items-center justify-between gap-3">
                  <label className="flex items-center gap-2 text-xs font-semibold cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newNoteVisible}
                      onChange={(e) => setNewNoteVisible(e.target.checked)}
                      className="accent-primary"
                    />
                    Student o'zida ko'rishi mumkin (Visible)
                  </label>
                  <button
                    type="button"
                    className="btn btn-primary small"
                    disabled={savingNote || !newNoteText.trim()}
                    onClick={handleCreateNote}
                  >
                    {savingNote ? "Saqlanmoqda..." : "➕ Saqlash"}
                  </button>
                </div>
              </div>

              {/* Existing Notes List */}
              {loadingNotes ? (
                <p className="text-center py-6 text-sm text-ink-400">Yuklanmoqda...</p>
              ) : studentNotesList.length === 0 ? (
                <p className="text-center py-6 text-sm text-ink-400">Hali izoh biriktirilmagan.</p>
              ) : (
                <div className="flex flex-col gap-2 max-h-72 overflow-y-auto">
                  {studentNotesList.map((n: any) => (
                    <div
                      key={n.id}
                      className="p-3 rounded-xl border border-line dark:border-white/10 bg-white dark:bg-navy-900/60 flex flex-col gap-2"
                    >
                      {editingNoteId === n.id ? (
                        <div className="flex flex-col gap-2">
                          <textarea
                            className="w-full p-2 rounded-lg border border-line dark:border-white/10 bg-white dark:bg-navy-900 text-sm outline-none resize-none"
                            rows={2}
                            value={editNoteText}
                            onChange={(e) => setEditNoteText(e.target.value)}
                          />
                          <div className="flex items-center justify-between">
                            <label className="flex items-center gap-2 text-xs font-semibold">
                              <input
                                type="checkbox"
                                checked={editNoteVisible}
                                onChange={(e) => setEditNoteVisible(e.target.checked)}
                              />
                              Visible
                            </label>
                            <div className="flex gap-2">
                              <button
                                type="button"
                                className="btn btn-primary small"
                                onClick={() => handleUpdateNote(n.id)}
                              >
                                Saqlash
                              </button>
                              <button
                                type="button"
                                className="btn btn-soft small"
                                onClick={() => setEditingNoteId(null)}
                              >
                                Bekor qilish
                              </button>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1 text-sm">
                            <p className="whitespace-pre-wrap font-medium">{n.note_text}</p>
                            <div className="flex items-center gap-3 mt-2 text-[11px] opacity-60">
                              <span>{String(n.created_at || "").slice(0, 16)}</span>
                              {n.is_visible ? (
                                <span className="text-green-600 dark:text-green-400 font-bold">👁️ Ko'rinadigan</span>
                              ) : (
                                <span className="text-amber-600 dark:text-amber-400 font-bold">🔒 Maxfiy</span>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              className="text-blue-500 hover:text-blue-600 text-xs font-bold p-1"
                              onClick={() => {
                                setEditingNoteId(n.id);
                                setEditNoteText(n.note_text);
                                setEditNoteVisible(Boolean(n.is_visible));
                              }}
                            >
                              ✏️
                            </button>
                            <button
                              type="button"
                              className="text-red-500 hover:text-red-600 text-xs font-bold p-1"
                              onClick={() => handleDeleteNote(n.id)}
                            >
                              ✕
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}

                </div>
              )}
            </article>
          </div>
        )}
      </ModalPortal>
    </div>
  );
}

