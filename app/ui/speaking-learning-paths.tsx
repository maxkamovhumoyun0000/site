"use client";

import { useEffect, useState } from "react";
import { useWebT } from "./web-i18n";

type ApiFetch = (path: string, options?: { method?: string; body?: any }) => Promise<any>;
type Item = { id: number; title: string; description?: string; subject?: string; is_published?: boolean; cover_key?: string };

const QUESTION_TYPES = [
  "multiple_choice", "true_false", "short_answer", "fill_blank", "gap_fill", "word_order", "matching",
  "translation", "spelling", "write_sentence", "guided_writing", "paraphrase", "dialogue_completion",
  "reading_open", "listening_open", "listening_tf", "listening_gap", "listening_dictation", "dictation",
  "passage_cloze", "picture_description", "speak_sentence", "speaking_repeat", "speaking_response",
  "read_aloud", "reading_set", "listening_set", "multiple_choice_set", "word_practice",
];

const fieldClass = "w-full rounded-lg border bg-white p-2 text-navy-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white";

export function SpeakingLearningPaths({ apiFetch }: { apiFetch: ApiFetch }) {
  const t = useWebT();
  const [tracks, setTracks] = useState<Item[]>([]);
  const [modules, setModules] = useState<Item[]>([]);
  const [questions, setQuestions] = useState<any[]>([]);
  const [trackId, setTrackId] = useState<number | null>(null);
  const [moduleId, setModuleId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [moduleTitle, setModuleTitle] = useState("");
  const [moduleCover, setModuleCover] = useState("star");
  const [subject, setSubject] = useState("english");
  const [prompt, setPrompt] = useState("");
  const [kind, setKind] = useState("multiple_choice");
  const [answer, setAnswer] = useState("");
  const [options, setOptions] = useState("");
  const [dataJson, setDataJson] = useState("{}");
  const [explanation, setExplanation] = useState("");
  const [editingQuestionId, setEditingQuestionId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const loadTracks = async () => {
    const response = await apiFetch("/staff/speaking-learning/tracks");
    setTracks(response?.items || []);
  };
  const loadModules = async (id: number) => {
    setTrackId(id); setModuleId(null); setQuestions([]);
    const response = await apiFetch(`/staff/speaking-learning/tracks/${id}/modules`);
    setModules(response?.items || []);
  };
  const loadQuestions = async (id: number) => {
    setModuleId(id); resetQuestionForm();
    const response = await apiFetch(`/staff/speaking-learning/modules/${id}/questions`);
    setQuestions(response?.items || []);
  };
  useEffect(() => {
    let active = true;
    apiFetch("/staff/speaking-learning/tracks")
      .then((response) => { if (active) setTracks(response?.items || []); })
      .catch(() => { if (active) setError(t("speakingLearning.loadFailed")); });
    return () => { active = false; };
  }, [apiFetch, t]);

  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await action(); }
    catch (cause: any) { setError(cause?.message || t("speakingLearning.saveFailed")); }
    finally { setBusy(false); }
  };

  function resetQuestionForm() {
    setEditingQuestionId(null); setPrompt(""); setAnswer(""); setOptions(""); setDataJson("{}"); setExplanation(""); setKind("multiple_choice");
  }
  function startEditingQuestion(question: any) {
    setEditingQuestionId(question.id);
    setPrompt(String(question.prompt || ""));
    setKind(String(question.question_type || "multiple_choice"));
    setOptions(Array.isArray(question.options) ? question.options.map((item: any) => typeof item === "string" ? item : JSON.stringify(item)).join("\n") : "");
    setAnswer(question.answer === undefined ? "" : JSON.stringify(question.answer));
    setDataJson(JSON.stringify(question.data || {}, null, 2));
    setExplanation(String(question.explanation || ""));
  }
  const editTrack = (item: Item) => {
    const nextTitle = window.prompt(t("speakingLearning.trackName"), item.title);
    if (nextTitle === null || !nextTitle.trim()) return;
    const nextDescription = window.prompt(t("speakingLearning.description"), item.description || "");
    if (nextDescription === null) return;
    void run(async () => {
      await apiFetch(`/staff/speaking-learning/tracks/${item.id}`, { method: "PATCH", body: { title: nextTitle.trim(), description: nextDescription.trim(), subject: item.subject || "english" } });
      await loadTracks();
    });
  };
  const editModule = (item: Item) => {
    const nextTitle = window.prompt(t("speakingLearning.moduleName"), item.title);
    if (nextTitle === null || !nextTitle.trim()) return;
    const nextDescription = window.prompt(t("speakingLearning.description"), item.description || "");
    if (nextDescription === null) return;
    void run(async () => {
      await apiFetch(`/staff/speaking-learning/modules/${item.id}`, { method: "PATCH", body: { title: nextTitle.trim(), description: nextDescription.trim(), cover_key: item.cover_key || "star" } });
      if (trackId) await loadModules(trackId);
    });
  };
  const submitQuestion = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!moduleId) return;
    void run(async () => {
      const parsedOptions = options.split("\n").map((value) => value.trim()).filter(Boolean);
      let parsedData: any;
      let parsedAnswer: any;
      try { parsedData = JSON.parse(dataJson || "{}"); }
      catch { throw new Error(t("speakingLearning.invalidDataJson")); }
      try { parsedAnswer = answer.trim() === "" ? null : JSON.parse(answer); }
      catch { parsedAnswer = answer.trim(); }
      if (kind === "true_false" || kind === "listening_tf") {
        parsedAnswer = answer.toLowerCase() === "true" || answer === "1";
      }
      if (kind === "multiple_choice" && (!parsedOptions.includes(String(parsedAnswer).replace(/^\"|\"$/g, "")) || parsedOptions.length < 2)) {
        throw new Error(t("speakingLearning.choiceValidation"));
      }
      const body = { prompt: prompt.trim(), question_type: kind, options: parsedOptions, answer: parsedAnswer, data: parsedData, explanation: explanation.trim() };
      if (editingQuestionId) await apiFetch(`/staff/speaking-learning/questions/${editingQuestionId}`, { method: "PATCH", body });
      else await apiFetch(`/staff/speaking-learning/modules/${moduleId}/questions`, { method: "POST", body });
      resetQuestionForm();
      await loadQuestions(moduleId);
    });
  };

  return <main className="mx-auto max-w-7xl space-y-5 p-4 md:p-6">
    <header className="premium-card p-5 sm:p-7">
      <p className="text-xs font-black uppercase tracking-[.18em] text-cyan-600 dark:text-cyan-300">Diamond Speaking</p>
      <h1 className="mt-1 text-2xl font-black text-navy-900 dark:text-white">{t("speakingLearning.title")}</h1>
      <p className="mt-1 text-sm text-ink-600 dark:text-navy-300">{t("speakingLearning.subtitle")}</p>
    </header>
    {error && <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-3 text-red-700 dark:bg-red-500/10 dark:text-red-200">{error}</div>}
    <section className="grid gap-4 xl:grid-cols-3">
      <div className="premium-card p-4">
        <h2 className="mb-3 font-semibold">{t("speakingLearning.tracks")}</h2>
        <form className="mb-4 space-y-2" onSubmit={(event) => { event.preventDefault(); void run(async () => { await apiFetch("/staff/speaking-learning/tracks", { method: "POST", body: { title, subject, is_published: false } }); setTitle(""); await loadTracks(); }); }}>
          <input className={fieldClass} placeholder={t("speakingLearning.newTrack")} value={title} onChange={(event) => setTitle(event.target.value)} required />
          <select className={fieldClass} value={subject} onChange={(event) => setSubject(event.target.value)}><option value="english">English / IELTS</option><option value="russian">Русский</option></select>
          <button className="rounded-lg bg-blue-600 px-3 py-2 text-white disabled:opacity-50" disabled={busy}>{t("speakingLearning.createTrack")}</button>
        </form>
        <div className="space-y-2">{tracks.map((item) => <div key={item.id} className={`rounded-lg border p-3 dark:border-slate-700 ${trackId === item.id ? "border-blue-500 bg-blue-50 dark:bg-blue-500/10" : ""}`}>
          <button onClick={() => void loadModules(item.id)} className="w-full text-left"><span className="font-medium">{item.title}</span><small className="block opacity-60">{item.subject} · {item.is_published ? t("speakingLearning.published") : t("speakingLearning.draft")}</small></button>
          <div className="mt-2 flex flex-wrap gap-4 text-sm">
            <button disabled={busy} className="text-blue-700 dark:text-cyan-300" onClick={() => void run(async () => { await apiFetch(`/staff/speaking-learning/tracks/${item.id}/publish`, { method: "POST", body: { is_published: !item.is_published } }); await loadTracks(); })}>{item.is_published ? t("speakingLearning.unpublish") : t("speakingLearning.publish")}</button>
            <button disabled={busy} className="text-blue-700 dark:text-cyan-300" onClick={() => editTrack(item)}>{t("common.edit")}</button>
            <button disabled={busy} className="text-red-700 dark:text-red-300" onClick={() => { if (confirm(t("speakingLearning.deleteTrackConfirm", { title: item.title }))) void run(async () => { await apiFetch(`/staff/speaking-learning/tracks/${item.id}`, { method: "DELETE" }); if (trackId === item.id) { setTrackId(null); setModules([]); setQuestions([]); } await loadTracks(); }); }}>{t("common.delete")}</button>
          </div>
        </div>)}</div>
      </div>
      <div className="premium-card p-4">
        <h2 className="mb-3 font-semibold">{t("speakingLearning.modules")}</h2>
        {trackId && <form className="mb-4 space-y-2" onSubmit={(event) => { event.preventDefault(); void run(async () => { await apiFetch(`/staff/speaking-learning/tracks/${trackId}/modules`, { method: "POST", body: { title: moduleTitle, cover_key: moduleCover } }); setModuleTitle(""); setModuleCover("star"); await loadModules(trackId); }); }}>
          <input className={`min-w-0 ${fieldClass}`} placeholder={t("speakingLearning.moduleName")} value={moduleTitle} onChange={(event) => setModuleTitle(event.target.value)} required />
          <select aria-label={t("speakingLearning.moduleCover")} className={fieldClass} value={moduleCover} onChange={(event) => setModuleCover(event.target.value)}>
            {["dolphin", "chest", "jellyfish", "ship", "star", "trophy"].map((cover) => <option key={cover} value={cover}>{t(`speakingLearning.cover.${cover}`)}</option>)}
          </select>
          <button disabled={busy} className="rounded-lg bg-blue-600 px-3 text-white">+</button>
        </form>}
        <div className="space-y-2">{modules.map((item) => <div key={item.id} className="flex items-center gap-2 rounded-lg border p-3 dark:border-slate-700">
          <button onClick={() => void loadQuestions(item.id)} className={`flex-1 text-left ${moduleId === item.id ? "font-semibold text-blue-700 dark:text-cyan-300" : ""}`}>{item.title}</button>
          <button disabled={busy} className="text-sm text-blue-700 dark:text-cyan-300" onClick={() => editModule(item)}>{t("common.edit")}</button>
          <button disabled={busy} aria-label={t("common.delete")} className="text-sm text-red-700 dark:text-red-300" onClick={() => { if (confirm(t("speakingLearning.deleteModuleConfirm", { title: item.title }))) void run(async () => { await apiFetch(`/staff/speaking-learning/modules/${item.id}`, { method: "DELETE" }); if (moduleId === item.id) { setModuleId(null); setQuestions([]); } if (trackId) await loadModules(trackId); }); }}>×</button>
        </div>)}</div>
      </div>
      <div className="premium-card p-4">
        <h2 className="mb-3 font-semibold">{t("speakingLearning.questions")}</h2>
        {moduleId && <form className="mb-4 space-y-2" onSubmit={submitQuestion}>
          <select className={fieldClass} value={kind} onChange={(event) => { setKind(event.target.value); setAnswer(""); }}>
            {QUESTION_TYPES.map((type) => <option key={type} value={type}>{t(`speakingLearning.type.${type}`)}</option>)}
          </select>
          <textarea className={fieldClass} placeholder={t("speakingLearning.prompt")} value={prompt} onChange={(event) => setPrompt(event.target.value)} required />
          {(kind === "multiple_choice" || kind === "multiple_choice_set") && <textarea className={fieldClass} placeholder={t("speakingLearning.optionsHint")} value={options} onChange={(event) => setOptions(event.target.value)} />}
          <textarea className={fieldClass} placeholder={kind === "true_false" || kind === "listening_tf" ? t("speakingLearning.booleanAnswer") : t("speakingLearning.answerJsonHint")} value={answer} onChange={(event) => setAnswer(event.target.value)} required={kind !== "matching"} />
          <textarea className={`${fieldClass} font-mono text-xs`} rows={5} placeholder={t("speakingLearning.dataJsonHint")} value={dataJson} onChange={(event) => setDataJson(event.target.value)} />
          <textarea className={fieldClass} placeholder={t("speakingLearning.explanationOptional")} value={explanation} onChange={(event) => setExplanation(event.target.value)} />
          <div className="flex gap-2">
            <button className="rounded-lg bg-blue-600 px-3 py-2 text-white" disabled={busy}>{editingQuestionId ? t("speakingLearning.saveQuestion") : t("speakingLearning.addQuestion")}</button>
            {editingQuestionId && <button type="button" className="rounded-lg border px-3 py-2" onClick={resetQuestionForm}>{t("common.cancel")}</button>}
          </div>
        </form>}
        <ol className="list-decimal space-y-2 pl-5">{questions.map((question) => <li key={question.id} className="pl-1">
          {question.prompt}<small className="ml-2 opacity-60">{t(`speakingLearning.type.${question.question_type}`)}</small>
          <div className="mt-1 flex gap-3"><button type="button" className="text-sm text-blue-700 dark:text-cyan-300" onClick={() => startEditingQuestion(question)}>{t("common.edit")}</button><button type="button" disabled={busy} className="text-sm text-red-700 dark:text-red-300" onClick={() => { if (confirm(t("speakingLearning.deleteQuestionConfirm"))) void run(async () => { await apiFetch(`/staff/speaking-learning/questions/${question.id}`, { method: "DELETE" }); if (moduleId) await loadQuestions(moduleId); }); }}>{t("common.delete")}</button></div>
        </li>)}</ol>
      </div>
    </section>
  </main>;
}
