"use client";

/**
 * O'qituvchi materiallar kutubxonasi — cheksiz chuqurlikdagi papka daraxti.
 * Har bir tugun: 📁 papka, 📎 fayl yoki 🧪 test. Testlarni AI (skrinshotdan)
 * yoki qo'lda tuzish, boshqa o'qituvchilarga ulashish (view/assign/edit) va
 * o'quvchilarga homework qilib berish shu paneldan boshqariladi.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AiTestEditor,
  AiTestQuestion,
  validateAiQuestions,
} from "./ai-test-editor";

type Row = Record<string, unknown>;
type ApiCall = (path: string, payload?: Row, method?: string) => Promise<Row | null>;

type LibNode = {
  id: number;
  parent_id: number | null;
  owner_id: number;
  kind: "folder" | "file" | "test";
  title: string;
  description?: string | null;
  subject?: string | null;
  level?: string | null;
  file_url?: string | null;
  is_public?: boolean;
  visibility?: "owner" | "public" | "shared";
  permission?: "owner" | "edit" | "assign" | "view";
  payload?: { questions?: AiTestQuestion[]; reading_text?: string; notes?: string } | null;
  sort_order?: number;
};

const KIND_ICON: Record<string, string> = { folder: "📁", file: "📎", test: "🧪" };
const PERM_LABEL: Record<string, string> = {
  owner: "Egasi", edit: "Tahrir", assign: "Berish", view: "Ko'rish",
};

function canEdit(node: LibNode) {
  return node.permission === "owner" || node.permission === "edit";
}
function canAssign(node: LibNode) {
  return node.permission === "owner" || node.permission === "edit" || node.permission === "assign";
}

async function uploadLibraryAsset(file: File): Promise<string | null> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/teacher/library/upload", {
    method: "POST",
    headers: { Authorization: `Bearer ${localStorage.getItem("diamond_token") || ""}` },
    body: form,
  });
  const data = await res.json().catch(() => ({}));
  return (data && data.url) || null;
}

export function TeacherLibraryPanel({
  onApiCall,
  groups,
}: {
  onApiCall: ApiCall;
  groups: Row[];
}) {
  const [nodes, setNodes] = useState<LibNode[]>([]);
  const [myId, setMyId] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [editorNode, setEditorNode] = useState<LibNode | null>(null);
  const [creating, setCreating] = useState<{ parentId: number | null; kind: LibNode["kind"] } | null>(null);
  const [shareNode, setShareNode] = useState<LibNode | null>(null);
  const [assignNode, setAssignNode] = useState<LibNode | null>(null);
  const [importParent, setImportParent] = useState<number | null | undefined>(undefined);
  const [viewerNode, setViewerNode] = useState<LibNode | null>(null);
  const [convertNode, setConvertNode] = useState<LibNode | null>(null);
  const [banner, setBanner] = useState("");
  const loadedOnce = useRef(false);

  const load = useCallback(async (silent = false) => {
    // Sahifa miltillamasin: faqat birinchi yuklashda to'liq spinner ko'rsatamiz,
    // keyingi yangilanishlar fonda bo'ladi va daraxt joyida qoladi.
    if (!silent && !loadedOnce.current) setLoading(true);
    const data = await onApiCall("/teacher/library", undefined, "GET");
    if (data) {
      setNodes(((data.nodes as LibNode[]) || []).map((n) => ({ ...n, id: Number(n.id) })));
      setMyId(Number(data.my_id || 0));
    }
    loadedOnce.current = true;
    setLoading(false);
  }, [onApiCall]);

  useEffect(() => {
    load();
  }, [load]);

  const childrenOf = useMemo(() => {
    const map = new Map<number, LibNode[]>();
    for (const node of nodes) {
      const key = Number(node.parent_id || 0);
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(node);
    }
    for (const list of map.values()) {
      list.sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0) || a.id - b.id);
    }
    return map;
  }, [nodes]);

  const toggle = (id: number) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const doDelete = async (node: LibNode) => {
    if (!confirm(`"${node.title}" va ichidagi hamma narsa o'chiriladi. Davom etamizmi?`)) return;
    const ok = await onApiCall(`/teacher/library/${node.id}`, undefined, "DELETE");
    if (ok) {
      setBanner("O'chirildi");
      load(true);
    }
  };

  const renderNode = (node: LibNode, depth: number) => {
    const kids = childrenOf.get(node.id) || [];
    const isOpen = expanded.has(node.id);
    return (
      <div key={node.id}>
        <div
          className="group flex items-center gap-2 rounded-xl px-2 py-2 transition hover:bg-surface-soft dark:hover:bg-white/5"
          style={{ paddingLeft: depth * 20 + 8 }}
        >
          {node.kind === "folder" ? (
            <button
              type="button"
              onClick={() => toggle(node.id)}
              className="w-5 text-sm font-black text-ink-500 dark:text-navy-300"
            >
              {isOpen ? "▾" : "▸"}
            </button>
          ) : (
            <span className="w-5" />
          )}
          <span className="text-lg">{KIND_ICON[node.kind]}</span>
          {node.kind === "file" && node.file_url ? (
            <button
              type="button"
              onClick={() => setViewerNode(node)}
              className="font-bold text-navy-900 underline-offset-2 hover:underline dark:text-white"
              title="Saytda ochish"
            >
              {node.title}
            </button>
          ) : (
            <span className="font-bold text-navy-900 dark:text-white">{node.title}</span>
          )}
          {node.visibility === "shared" && (
            <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-black text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-100">
              Ulashilgan · {PERM_LABEL[node.permission || "view"]}
            </span>
          )}
          {node.visibility === "public" && node.owner_id !== myId && (
            <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-black text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-100">
              Ommaviy
            </span>
          )}
          {node.is_public && node.owner_id === myId && (
            <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-black text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-100">
              Ochiq
            </span>
          )}

          <div className="ml-auto flex items-center gap-1 opacity-0 transition group-hover:opacity-100">
            {node.kind === "folder" && canEdit(node) && (
              <>
                <IconBtn title="Papka qo'shish" onClick={() => setCreating({ parentId: node.id, kind: "folder" })}>📁+</IconBtn>
                <IconBtn title="Fayl qo'shish" onClick={() => setCreating({ parentId: node.id, kind: "file" })}>📎+</IconBtn>
                <IconBtn title="Test qo'shish" onClick={() => setCreating({ parentId: node.id, kind: "test" })}>🧪+</IconBtn>
                <IconBtn title="Fayldan AI import" onClick={() => setImportParent(node.id)}>🤖</IconBtn>
              </>
            )}
            {node.kind === "test" && (
              <IconBtn title="Testni ochish" onClick={() => setEditorNode(node)}>✏️</IconBtn>
            )}
            {node.kind === "file" && node.file_url && (
              <IconBtn title="Saytda ochish" onClick={() => setViewerNode(node)}>👁</IconBtn>
            )}
            {node.kind === "file" && node.file_url && canEdit(node) && (
              <IconBtn title="AI orqali testga aylantirish" onClick={() => setConvertNode(node)}>🤖</IconBtn>
            )}
            {node.kind !== "folder" && canEdit(node) && (
              <IconBtn title="Tahrirlash" onClick={() => setEditorNode(node)}>⚙️</IconBtn>
            )}
            {node.kind !== "folder" && canAssign(node) && (
              <IconBtn title="O'quvchilarga berish" onClick={() => setAssignNode(node)}>📤</IconBtn>
            )}
            {node.owner_id === myId && (
              <IconBtn title="Ulashish" onClick={() => setShareNode(node)}>👥</IconBtn>
            )}
            {node.owner_id === myId && (
              <IconBtn title="O'chirish" danger onClick={() => doDelete(node)}>🗑</IconBtn>
            )}
          </div>
        </div>
        {node.kind === "folder" && isOpen && kids.map((child) => renderNode(child, depth + 1))}
      </div>
    );
  };

  const roots = childrenOf.get(0) || [];

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center gap-3">
        <div>
          <h2 className="text-2xl font-black text-navy-900 dark:text-white">Materiallar kutubxonasi</h2>
          <p className="text-sm font-semibold text-ink-500 dark:text-navy-300">
            Papkalar ichida testlar tuzing, AI bilan fayldan import qiling, ulashing va o'quvchilarga bering.
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => setImportParent(null)}
            className="rounded-xl bg-violet-500 px-4 py-2 text-sm font-black text-white shadow-sm transition hover:bg-violet-600"
          >
            🤖 Fayldan import
          </button>
          <button
            type="button"
            onClick={() => setCreating({ parentId: null, kind: "folder" })}
            className="rounded-xl bg-cyan-500 px-4 py-2 text-sm font-black text-white shadow-sm transition hover:bg-cyan-600"
          >
            + Yangi papka
          </button>
        </div>
      </header>

      {banner && (
        <div className="rounded-xl bg-emerald-50 px-4 py-2 text-sm font-bold text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-100">
          {banner}
        </div>
      )}

      <div className="rounded-2xl border border-line bg-white p-3 shadow-sm dark:border-white/10 dark:bg-navy-900/70">
        {loading ? (
          <p className="p-6 text-center font-bold text-ink-400">Yuklanmoqda…</p>
        ) : roots.length === 0 ? (
          <p className="p-8 text-center font-bold text-ink-400 dark:text-navy-300">
            Kutubxona bo'sh. Birinchi papkani yarating yoki fayldan import qiling.
          </p>
        ) : (
          roots.map((node) => renderNode(node, 0))
        )}
      </div>

      {creating && (
        <CreateNodeModal
          parentId={creating.parentId}
          kind={creating.kind}
          onApiCall={onApiCall}
          onClose={() => setCreating(null)}
          onSaved={(created) => {
            setCreating(null);
            if (created?.kind === "test") setEditorNode(created);
            if (creating.parentId) setExpanded((p) => new Set(p).add(creating.parentId!));
            load(true);
          }}
        />
      )}

      {editorNode && (
        <TestEditorModal
          node={editorNode}
          onApiCall={onApiCall}
          onClose={() => setEditorNode(null)}
          onSaved={() => {
            setEditorNode(null);
            load(true);
          }}
        />
      )}

      {shareNode && (
        <ShareModal node={shareNode} onApiCall={onApiCall} onClose={() => setShareNode(null)} />
      )}

      {assignNode && (
        <AssignModal node={assignNode} groups={groups} onApiCall={onApiCall} onClose={() => setAssignNode(null)} onDone={() => { setAssignNode(null); setBanner("Vazifa berildi ✓"); }} />
      )}

      {importParent !== undefined && (
        <ImportModal
          parentId={importParent}
          onApiCall={onApiCall}
          onClose={() => setImportParent(undefined)}
          onImported={(node) => {
            setImportParent(undefined);
            setEditorNode(node);
            load(true);
          }}
        />
      )}

      {viewerNode && (
        <FileViewerModal node={viewerNode} onClose={() => setViewerNode(null)} />
      )}

      {convertNode && (
        <ImportModal
          parentId={convertNode.parent_id ?? null}
          presetFile={{ url: String(convertNode.file_url || ""), name: convertNode.title }}
          onApiCall={onApiCall}
          onClose={() => setConvertNode(null)}
          onImported={(node) => {
            setConvertNode(null);
            setEditorNode(node);
            load(true);
          }}
        />
      )}
    </section>
  );
}

function IconBtn({
  children, onClick, title, danger,
}: {
  children: React.ReactNode;
  onClick: () => void;
  title: string;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={`rounded-lg px-2 py-1 text-sm font-black transition ${
        danger
          ? "text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10"
          : "text-ink-600 hover:bg-line dark:text-navy-200 dark:hover:bg-white/10"
      }`}
    >
      {children}
    </button>
  );
}

function ModalShell({ title, children, onClose, wide }: { title: string; children: React.ReactNode; onClose: () => void; wide?: boolean }) {
  return (
    <div className="fixed inset-0 z-[9998] flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className={`max-h-[92vh] w-full overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl dark:bg-navy-900 ${wide ? "max-w-3xl" : "max-w-lg"}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-black text-navy-900 dark:text-white">{title}</h3>
          <button onClick={onClose} className="text-xl font-black text-ink-400 hover:text-ink-600">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

const FIELD = "w-full rounded-xl border border-line bg-surface-soft px-3.5 py-2.5 text-sm font-semibold text-navy-900 outline-none focus:ring-2 focus:ring-cyan-500 dark:border-white/10 dark:bg-navy-950 dark:text-white";

function CreateNodeModal({
  parentId, kind, onApiCall, onClose, onSaved,
}: {
  parentId: number | null;
  kind: LibNode["kind"];
  onApiCall: ApiCall;
  onClose: () => void;
  onSaved: (node: LibNode | null) => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [isPublic, setIsPublic] = useState(false);
  const [fileUrl, setFileUrl] = useState("");
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const label = kind === "folder" ? "papka" : kind === "file" ? "fayl" : "test";

  const save = async () => {
    if (!title.trim()) { setError("Nom majburiy"); return; }
    if (kind === "file" && !fileUrl) { setError("Avval fayl yuklang"); return; }
    setBusy(true);
    const payload: Row = {
      title, kind, parent_id: parentId, description, is_public: isPublic,
    };
    if (kind === "file") payload.file_url = fileUrl;
    if (kind === "test") payload.payload = { questions: [{ kind: "write_sentence", prompt: "Yangi mashq", reference_answer: "" }] };
    const res = await onApiCall("/teacher/library", payload, "POST");
    setBusy(false);
    if (res && res.item) onSaved(res.item as LibNode);
    else setError("Saqlashda xato");
  };

  return (
    <ModalShell title={`Yangi ${label}`} onClose={onClose}>
      <div className="space-y-3">
        <input className={FIELD} placeholder="Nom" value={title} onChange={(e) => setTitle(e.target.value)} />
        <textarea className={`${FIELD} min-h-[60px]`} placeholder="Izoh (ixtiyoriy)" value={description} onChange={(e) => setDescription(e.target.value)} />
        {kind === "file" && (
          <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-line bg-surface-soft px-3 py-4 text-sm font-bold dark:border-white/10 dark:bg-white/5">
            {uploading ? "Yuklanmoqda…" : fileUrl ? "Fayl yuklandi ✓ — almashtirish" : "+ Fayl yuklash (PDF, rasm, audio…)"}
            <input
              type="file"
              className="hidden"
              disabled={uploading}
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                setUploading(true);
                const url = await uploadLibraryAsset(file);
                if (url) { setFileUrl(url); if (!title) setTitle(file.name.replace(/\.[^.]+$/, "")); }
                setUploading(false);
              }}
            />
          </label>
        )}
        <label className="flex items-center gap-2 text-sm font-bold text-navy-900 dark:text-white">
          <input type="checkbox" checked={isPublic} onChange={(e) => setIsPublic(e.target.checked)} className="h-4 w-4 accent-cyan-500" />
          Barcha o'qituvchilarga ochiq (ommaviy)
        </label>
        {error && <p className="text-sm font-bold text-red-500">{error}</p>}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="rounded-xl border border-line px-4 py-2 font-bold dark:border-white/10 dark:text-white">Bekor</button>
          <button onClick={save} disabled={busy} className="rounded-xl bg-cyan-600 px-4 py-2 font-black text-white disabled:opacity-60">
            {busy ? "Saqlanmoqda…" : "Yaratish"}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}

function TestEditorModal({
  node, onApiCall, onClose, onSaved,
}: {
  node: LibNode;
  onApiCall: ApiCall;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [title, setTitle] = useState(node.title);
  const [isPublic, setIsPublic] = useState(Boolean(node.is_public));
  const [questions, setQuestions] = useState<AiTestQuestion[]>(node.payload?.questions || []);
  const [notes] = useState(node.payload?.notes || "");
  const [reading] = useState(node.payload?.reading_text || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const readOnly = !canEdit(node);

  const save = async () => {
    const problem = validateAiQuestions(questions);
    if (problem) { setError(problem); return; }
    setBusy(true);
    const res = await onApiCall(`/teacher/library/${node.id}`, {
      title,
      is_public: isPublic,
      payload: { questions, notes, reading_text: reading },
    }, "PATCH");
    setBusy(false);
    if (res) onSaved();
    else setError("Saqlashda xato");
  };

  return (
    <ModalShell title={node.kind === "test" ? "Test muharriri" : "Element sozlamalari"} onClose={onClose} wide>
      <div className="space-y-4">
        <input className={FIELD} value={title} onChange={(e) => setTitle(e.target.value)} disabled={readOnly} />
        <label className="flex items-center gap-2 text-sm font-bold text-navy-900 dark:text-white">
          <input type="checkbox" checked={isPublic} onChange={(e) => setIsPublic(e.target.checked)} disabled={readOnly} className="h-4 w-4 accent-cyan-500" />
          O'quvchilar ishlashi uchun ochiq
        </label>
        {reading && (
          <div className="rounded-xl bg-surface-soft p-3 text-sm dark:bg-white/5">
            <p className="mb-1 text-xs font-black uppercase text-ink-500">Matn</p>
            <p className="whitespace-pre-wrap text-navy-900 dark:text-white">{reading}</p>
          </div>
        )}
        {node.kind === "test" && (
          <AiTestEditor questions={questions} onChange={readOnly ? () => {} : setQuestions} onUploadAsset={uploadLibraryAsset} />
        )}
        {error && <p className="text-sm font-bold text-red-500">{error}</p>}
        {!readOnly && (
          <div className="flex justify-end gap-2">
            <button onClick={onClose} className="rounded-xl border border-line px-4 py-2 font-bold dark:border-white/10 dark:text-white">Bekor</button>
            <button onClick={save} disabled={busy} className="rounded-xl bg-cyan-600 px-4 py-2 font-black text-white disabled:opacity-60">
              {busy ? "Saqlanmoqda…" : "Saqlash"}
            </button>
          </div>
        )}
      </div>
    </ModalShell>
  );
}

function ShareModal({ node, onApiCall, onClose }: { node: LibNode; onApiCall: ApiCall; onClose: () => void }) {
  const [teachers, setTeachers] = useState<Row[]>([]);
  const [shares, setShares] = useState<Row[]>([]);
  const [selected, setSelected] = useState(0);
  // Har bir huquqni alohida galochka bilan yoqamiz. Tahrir → berish + ko'rishni,
  // berish → ko'rishni o'z ichiga oladi (huquqlar bosqichma-bosqich).
  const [canView, setCanView] = useState(true);
  const [canAssignPerm, setCanAssignPerm] = useState(false);
  const [canEditPerm, setCanEditPerm] = useState(false);
  const [busy, setBusy] = useState(false);

  const effectivePermission = canEditPerm ? "edit" : canAssignPerm ? "assign" : "view";

  const load = useCallback(async () => {
    const data = await onApiCall(`/teacher/library/${node.id}/shares`, undefined, "GET");
    if (data) { setTeachers((data.teachers as Row[]) || []); setShares((data.shares as Row[]) || []); }
  }, [node.id, onApiCall]);

  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!selected) return;
    setBusy(true);
    await onApiCall(`/teacher/library/${node.id}/share`, { teacher_id: selected, permission: effectivePermission }, "POST");
    setBusy(false);
    setSelected(0);
    setCanAssignPerm(false);
    setCanEditPerm(false);
    load();
  };

  const remove = async (teacherId: number) => {
    await onApiCall(`/teacher/library/${node.id}/share/${teacherId}`, undefined, "DELETE");
    load();
  };

  return (
    <ModalShell title={`"${node.title}" ni ulashish`} onClose={onClose}>
      <div className="space-y-3">
        <p className="text-xs font-semibold text-ink-500 dark:text-navy-300">
          Ulashilgan huquq ichki papka/testlarga ham tarqaladi. <b>Ko'rish</b> — faqat ko'radi; <b>Berish</b> — o'quvchilarga bera oladi; <b>Tahrir</b> — o'zgartira oladi.
        </p>
        <div className="flex flex-wrap items-end gap-2">
          <select className={`${FIELD} flex-1`} value={selected} onChange={(e) => setSelected(Number(e.target.value))}>
            <option value={0}>O'qituvchini tanlang…</option>
            {teachers.map((t) => (
              <option key={String(t.id)} value={Number(t.id)}>
                {String(t.first_name || "")} {String(t.last_name || "")} ({String(t.login_id || "")})
              </option>
            ))}
          </select>
          <button onClick={add} disabled={busy || !selected} className="rounded-xl bg-cyan-600 px-4 py-2.5 font-black text-white disabled:opacity-60">
            Ulashish
          </button>
        </div>
        <div className="flex flex-wrap gap-4 rounded-xl bg-surface-soft px-3 py-2.5 dark:bg-white/5">
          <label className="flex items-center gap-2 text-sm font-bold text-navy-900 dark:text-white">
            <input type="checkbox" checked disabled className="h-4 w-4 accent-cyan-500 opacity-60" />
            Ko'rish
          </label>
          <label className="flex items-center gap-2 text-sm font-bold text-navy-900 dark:text-white">
            <input
              type="checkbox"
              checked={canAssignPerm || canEditPerm}
              disabled={canEditPerm}
              onChange={(e) => setCanAssignPerm(e.target.checked)}
              className="h-4 w-4 accent-cyan-500"
            />
            Berish (o'quvchilarga)
          </label>
          <label className="flex items-center gap-2 text-sm font-bold text-navy-900 dark:text-white">
            <input
              type="checkbox"
              checked={canEditPerm}
              onChange={(e) => {
                setCanEditPerm(e.target.checked);
                if (e.target.checked) setCanAssignPerm(true);
              }}
              className="h-4 w-4 accent-cyan-500"
            />
            Tahrirlash
          </label>
        </div>
        <div className="space-y-2">
          {shares.length === 0 && <p className="text-sm font-semibold text-ink-400">Hali hech kimga ulashilmagan.</p>}
          {shares.map((s) => (
            <div key={String(s.teacher_id)} className="flex items-center gap-2 rounded-xl bg-surface-soft px-3 py-2 dark:bg-white/5">
              <span className="font-bold text-navy-900 dark:text-white">
                {String(s.teacher_first_name || "")} {String(s.teacher_last_name || "")}
              </span>
              <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-black text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-100">
                {PERM_LABEL[String(s.permission || "view")]}
              </span>
              <button onClick={() => remove(Number(s.teacher_id))} className="ml-auto text-sm font-black text-red-500">Bekor</button>
            </div>
          ))}
        </div>
      </div>
    </ModalShell>
  );
}

function AssignModal({
  node, groups, onApiCall, onClose, onDone,
}: {
  node: LibNode;
  groups: Row[];
  onApiCall: ApiCall;
  onClose: () => void;
  onDone: () => void;
}) {
  const [groupId, setGroupId] = useState(0);
  const [due, setDue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const assign = async () => {
    if (!groupId) { setError("Guruh tanlang"); return; }
    setBusy(true);
    const res = await onApiCall(`/teacher/library/${node.id}/assign`, {
      group_id: groupId,
      due_at: due ? `${due} 23:59:00` : null,
    }, "POST");
    setBusy(false);
    if (res) onDone();
    else setError("Vazifa berilmadi");
  };

  return (
    <ModalShell title={`"${node.title}" ni o'quvchilarga berish`} onClose={onClose}>
      <div className="space-y-3">
        <select className={FIELD} value={groupId} onChange={(e) => setGroupId(Number(e.target.value))}>
          <option value={0}>Guruhni tanlang…</option>
          {groups.map((g) => (
            <option key={String(g.id)} value={Number(g.id)}>{String(g.name || g.title || `Guruh ${g.id}`)}</option>
          ))}
        </select>
        <label className="block text-sm font-bold text-navy-900 dark:text-white">
          Muddat (ixtiyoriy)
          <input type="date" className={`${FIELD} mt-1`} value={due} onChange={(e) => setDue(e.target.value)} />
        </label>
        {error && <p className="text-sm font-bold text-red-500">{error}</p>}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="rounded-xl border border-line px-4 py-2 font-bold dark:border-white/10 dark:text-white">Bekor</button>
          <button onClick={assign} disabled={busy} className="rounded-xl bg-cyan-600 px-4 py-2 font-black text-white disabled:opacity-60">
            {busy ? "Berilmoqda…" : "Homework qilib berish"}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}

function ImportModal({
  parentId, onApiCall, onClose, onImported, presetFile,
}: {
  parentId: number | null;
  onApiCall: ApiCall;
  onClose: () => void;
  onImported: (node: LibNode) => void;
  presetFile?: { url: string; name: string };
}) {
  const [files, setFiles] = useState<{ url: string; name: string }[]>(
    presetFile && presetFile.url ? [presetFile] : []
  );
  const [subject, setSubject] = useState("English");
  const [level, setLevel] = useState("");
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{
    title: string; questions: AiTestQuestion[]; level?: string | null; reading_text?: string; notes?: string;
    needs_audio_upload?: { index: number; kind: string; prompt: string }[];
  } | null>(null);
  const [title, setTitle] = useState("");
  const [questions, setQuestions] = useState<AiTestQuestion[]>([]);
  const [saving, setSaving] = useState(false);

  const isImage = (name: string) => /\.(png|jpe?g|webp|gif|bmp|avif)$/i.test(name);

  const runImport = async () => {
    if (files.length === 0) { setError("Kamida bitta fayl yuklang"); return; }
    setProcessing(true);
    setError("");
    const res = await onApiCall("/teacher/library/ai/import-screenshot", {
      file_urls: files.map((f) => f.url), subject, level: level || null, node_id: parentId,
    }, "POST");
    setProcessing(false);
    if (res && res.questions) {
      setResult(res as never);
      setTitle(String(res.title || "Yangi mavzu"));
      setQuestions((res.questions as AiTestQuestion[]) || []);
    } else {
      setError("AI mashqlarni topa olmadi. Aniqroq material yuboring.");
    }
  };

  const saveAsTest = async () => {
    const problem = validateAiQuestions(questions);
    if (problem) { setError(problem); return; }
    setSaving(true);
    const res = await onApiCall("/teacher/library", {
      title,
      kind: "test",
      parent_id: parentId,
      subject,
      level: result?.level || level || null,
      is_public: false,
      payload: { questions, reading_text: result?.reading_text || "", notes: result?.notes || "" },
    }, "POST");
    setSaving(false);
    if (res && res.item) onImported(res.item as LibNode);
    else setError("Saqlashda xato");
  };

  return (
    <ModalShell title="Fayldan AI import" onClose={onClose} wide>
      {!result ? (
        <div className="space-y-3">
          <p className="text-sm font-semibold text-ink-500 dark:text-navy-300">
            Rasm (PNG, JPG…), PDF, DOC/DOCX yoki TXT fayl yuklang — AI matn va mashqlarni
            tayyor test holatiga keltiradi. Listening mashqlari topilsa, audio faylni keyin o'zingiz yuklaysiz.
          </p>
          <div className="flex flex-wrap gap-3">
            <select className={FIELD + " w-40"} value={subject} onChange={(e) => setSubject(e.target.value)}>
              <option>English</option>
              <option>Russian</option>
            </select>
            <input className={FIELD + " w-32"} placeholder="Daraja (A2…)" value={level} onChange={(e) => setLevel(e.target.value)} />
          </div>
          <div className="flex flex-wrap gap-2">
            {files.map((f, i) => (
              <div key={i} className="relative">
                {isImage(f.name) ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={`/api${f.url}`} alt="" className="h-24 w-24 rounded-lg object-cover" />
                ) : (
                  <div className="flex h-24 w-24 flex-col items-center justify-center gap-1 rounded-lg border border-line bg-surface-soft px-1 text-center dark:border-white/10 dark:bg-white/5">
                    <span className="text-2xl">📄</span>
                    <span className="line-clamp-2 text-[10px] font-bold text-ink-600 dark:text-navy-200">{f.name}</span>
                  </div>
                )}
                <button
                  onClick={() => setFiles((p) => p.filter((_, idx) => idx !== i))}
                  className="absolute -right-2 -top-2 rounded-full bg-red-500 px-2 text-xs font-black text-white"
                >
                  ✕
                </button>
              </div>
            ))}
            {files.length < 5 && (
              <label className="flex h-24 w-24 cursor-pointer items-center justify-center rounded-lg border border-dashed border-line bg-surface-soft text-3xl font-black text-ink-400 dark:border-white/10 dark:bg-white/5">
                {uploading ? "…" : "+"}
                <input
                  type="file"
                  accept="image/*,.pdf,.doc,.docx,.txt,.rtf,.md"
                  className="hidden"
                  disabled={uploading}
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    setUploading(true);
                    const url = await uploadLibraryAsset(file);
                    if (url) setFiles((p) => [...p, { url, name: file.name }]);
                    setUploading(false);
                    e.target.value = "";
                  }}
                />
              </label>
            )}
          </div>
          {error && <p className="text-sm font-bold text-red-500">{error}</p>}
          <div className="flex justify-end gap-2">
            <button onClick={onClose} className="rounded-xl border border-line px-4 py-2 font-bold dark:border-white/10 dark:text-white">Bekor</button>
            <button
              onClick={runImport}
              disabled={processing || files.length === 0}
              className="rounded-xl bg-violet-600 px-4 py-2 font-black text-white disabled:opacity-60"
            >
              {processing ? "AI tahlil qilmoqda…" : "🤖 Import qilish"}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <input className={FIELD} value={title} onChange={(e) => setTitle(e.target.value)} />
          {result.needs_audio_upload && result.needs_audio_upload.length > 0 && (
            <div className="rounded-xl bg-amber-50 px-4 py-2 text-sm font-bold text-amber-800 dark:bg-amber-500/10 dark:text-amber-100">
              ⚠ {result.needs_audio_upload.length} ta tinglash mashqi topildi — quyida audio yuklang.
            </div>
          )}
          {result.reading_text && (
            <div className="rounded-xl bg-surface-soft p-3 text-sm dark:bg-white/5">
              <p className="mb-1 text-xs font-black uppercase text-ink-500">AI ajratgan matn</p>
              <p className="whitespace-pre-wrap text-navy-900 dark:text-white">{result.reading_text}</p>
            </div>
          )}
          <AiTestEditor questions={questions} onChange={setQuestions} onUploadAsset={uploadLibraryAsset} title="Import qilingan mashqlar (tahrirlash mumkin)" />
          {error && <p className="text-sm font-bold text-red-500">{error}</p>}
          <div className="flex justify-end gap-2">
            <button onClick={() => setResult(null)} className="rounded-xl border border-line px-4 py-2 font-bold dark:border-white/10 dark:text-white">Orqaga</button>
            <button onClick={saveAsTest} disabled={saving} className="rounded-xl bg-cyan-600 px-4 py-2 font-black text-white disabled:opacity-60">
              {saving ? "Saqlanmoqda…" : "Test sifatida saqlash"}
            </button>
          </div>
        </div>
      )}
    </ModalShell>
  );
}

/**
 * Faylni saytning o'zida ochadigan qalqib chiquvchi viewer:
 *  - rasm (png/jpg/webp…) → <img>
 *  - PDF → brauzer ichki PDF ko'rgichi (<iframe>)
 *  - DOC/DOCX/PPT/XLS → Microsoft Office Online ko'rgichi (embed)
 *  - TXT/MD → matn ko'rinishida
 * Fayllar `https://diamond-education.uz/api/homework/files/...` da ochiq
 * xizmat qilinadi, shu bois Office viewer ham ularni o'qiy oladi.
 */
function FileViewerModal({ node, onClose }: { node: LibNode; onClose: () => void }) {
  const rel = String(node.file_url || "");
  const proxied = rel.startsWith("/") ? `/api${rel}` : rel;
  const absolute =
    rel.startsWith("http")
      ? rel
      : `https://diamond-education.uz/api${rel.startsWith("/") ? rel : `/${rel}`}`;
  const ext = (rel.split(".").pop() || "").toLowerCase();
  const [text, setText] = useState<string>("");
  const [textLoading, setTextLoading] = useState(false);

  const isImage = ["png", "jpg", "jpeg", "webp", "gif", "bmp", "avif"].includes(ext);
  const isPdf = ext === "pdf";
  const isOffice = ["doc", "docx", "ppt", "pptx", "xls", "xlsx"].includes(ext);
  const isText = ["txt", "md", "csv", "log", "rtf"].includes(ext);

  useEffect(() => {
    if (!isText) return;
    setTextLoading(true);
    fetch(proxied, { headers: { Authorization: `Bearer ${localStorage.getItem("diamond_token") || ""}` } })
      .then((r) => r.text())
      .then((t) => setText(t))
      .catch(() => setText("Faylni o'qib bo'lmadi."))
      .finally(() => setTextLoading(false));
  }, [proxied, isText]);

  return (
    <div className="fixed inset-0 z-[9998] flex items-center justify-center bg-black/70 p-3" onClick={onClose}>
      <div
        className="flex h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl dark:bg-navy-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-line px-5 py-3 dark:border-white/10">
          <h3 className="truncate text-base font-black text-navy-900 dark:text-white">{node.title}</h3>
          <div className="flex items-center gap-2">
            <a
              href={proxied}
              download
              className="rounded-lg border border-line px-3 py-1.5 text-xs font-black text-navy-900 hover:bg-surface-soft dark:border-white/10 dark:text-white"
            >
              Yuklab olish
            </a>
            <button onClick={onClose} className="text-xl font-black text-ink-400 hover:text-ink-600">✕</button>
          </div>
        </div>
        <div className="flex-1 overflow-auto bg-surface-soft dark:bg-navy-950">
          {isImage && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={proxied} alt={node.title} className="mx-auto max-h-full w-auto object-contain" />
          )}
          {isPdf && (
            <iframe src={proxied} title={node.title} className="h-full w-full" />
          )}
          {isOffice && (
            <iframe
              src={`https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(absolute)}`}
              title={node.title}
              className="h-full w-full"
            />
          )}
          {isText && (
            <pre className="whitespace-pre-wrap p-5 text-sm text-navy-900 dark:text-white">
              {textLoading ? "Yuklanmoqda…" : text}
            </pre>
          )}
          {!isImage && !isPdf && !isOffice && !isText && (
            <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
              <span className="text-5xl">📎</span>
              <p className="font-bold text-ink-500 dark:text-navy-300">
                Bu fayl turini brauzerda ko'rsatib bo'lmadi. Yuklab olib oching.
              </p>
              <a
                href={proxied}
                download
                className="rounded-xl bg-cyan-600 px-5 py-2.5 font-black text-white"
              >
                Yuklab olish
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
