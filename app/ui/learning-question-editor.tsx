"use client";

import { useState } from "react";
import { AiTestEditor, AI_TEST_KIND_META, validateAiQuestions, type AiTestQuestion, type AiTestKind, type UploadFn } from "./ai-test-editor";

export function libraryQuestionDraft(payload: Record<string, any>): AiTestQuestion | null {
  const kind = String(payload.kind || payload.test_type || "") as AiTestKind;
  if (!AI_TEST_KIND_META[kind]) return null;
  const { question, correct_answer, test_type, check, input, ...rest } = payload;
  const options = Array.isArray(rest.options) ? rest.options : [];
  return {
    ...rest, kind,
    prompt: rest.prompt ?? question ?? "",
    answer: rest.answer ?? correct_answer ?? "",
    reference_answer: rest.reference_answer ?? correct_answer ?? "",
    correct_index: rest.correct_index ?? Math.max(0, options.indexOf(correct_answer)),
    accepted_answers: rest.accepted_answers ?? rest.acceptable_answers ?? [],
  };
}

export function LearningQuestionEditor({ initialTitle, initialQuestions, editing, upload, onSave, onSaveToLibrary, onClose }: {
  initialTitle: string;
  initialQuestions: AiTestQuestion[];
  editing: boolean;
  upload: UploadFn;
  onSave: (title: string, questions: AiTestQuestion[]) => Promise<void>;
  onSaveToLibrary: (title: string, questions: AiTestQuestion[]) => Promise<void>;
  onClose: () => void;
}) {
  const [title, setTitle] = useState(initialTitle);
  const [questions, setQuestions] = useState(initialQuestions);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const save = async (toLibrary = false) => {
    const problem = !title.trim() ? "Test nomini kiriting." : title.trim().length > 160 ? "Test nomi 160 belgidan oshmasin." : editing && questions.length !== 1 ? "Tahrirlashda bitta mashq saqlanishi kerak." : validateAiQuestions(questions);
    if (problem) { setError(problem); return; }
    setBusy(true);
    setError("");
    try {
      if (toLibrary) { await onSaveToLibrary(title.trim(), questions); setCopied(true); }
      else { await onSave(title.trim(), questions); onClose(); }
    }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setBusy(false); }
  };
  return <div className="fixed inset-0 z-[250] flex items-center justify-center bg-black/60 p-3" role="dialog" aria-modal="true" aria-label="Test muharriri">
    <div className="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-2xl bg-white p-5 dark:bg-slate-950">
      <h3 className="text-lg font-bold">Test muharriri</h3>
      <p className="my-2 text-sm text-slate-500">Kutubxona va uy vazifalari bilan bir xil mashq turlari.</p>
      <fieldset disabled={busy} className="space-y-4">
        <input aria-label="Test nomi" maxLength={160} className="w-full rounded-xl border p-3 dark:bg-slate-900" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Test nomi" />
        <AiTestEditor questions={questions} onChange={setQuestions} onUploadAsset={upload} />
        {error && <p role="alert" className="text-red-500">{error}</p>}
        {copied && <p role="status" className="text-emerald-600">Kutubxonaga shaxsiy nusxa saqlandi. Uni uy vazifasiga yoki boshqa modulga biriktirishingiz mumkin.</p>}
        <div className="flex justify-end gap-3">
          <button type="button" disabled={copied} onClick={() => void save(true)}>Kutubxonaga nusxa saqlash</button>
          <button type="button" onClick={onClose}>Bekor qilish</button>
          <button type="button" onClick={() => void save()} className="rounded-xl bg-cyan-600 px-4 py-2 font-bold text-white">{busy ? "Saqlanmoqda…" : "Saqlash"}</button>
        </div>
      </fieldset>
    </div>
  </div>;
}
