"use client";

import React, { useState, useEffect } from "react";
import { ModalPortal } from "./modal-portal";
import { useWebT } from "./web-i18n";

type GenericRow = any;

function parseSurveyAnswers(value: any): Record<string, any> {
  if (!value) return {};
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
    } catch {
      return {};
    }
  }
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function cleanRespondentName(resp: GenericRow): string {
  const siteName = `${String(resp.first_name || "").trim()} ${String(resp.last_name || "").trim()}`.trim();
  const candidates = [
    resp.respondent_name,
    resp.user_display,
    siteName,
    resp.tg_full_name,
    resp.tg_username ? `@${String(resp.tg_username).replace(/^@/, "")}` : "",
    resp.telegram_id ? `Telegram ID: ${resp.telegram_id}` : "",
  ];

  for (const candidate of candidates) {
    const text = String(candidate || "")
      .replace(/^👤\s*/, "")
      .replace(/^[-|—\s]+/, "")
      .trim();
    if (text) return text;
  }

  const uid = Number(resp.user_id || 0);
  return uid < 0 ? "Anonim foydalanuvchi" : uid > 0 ? `Foydalanuvchi #${uid}` : "Foydalanuvchi";
}

function respondentInitial(resp: GenericRow, name: string): string {
  const fromApi = String(resp.respondent_initial || "").trim();
  if (fromApi) return fromApi.slice(0, 2).toUpperCase();
  const match = String(name || "").match(/[\p{L}\p{N}]/u);
  return match ? match[0].toUpperCase() : "👤";
}

function formatSubmittedAt(value: any, compact = false): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Sana noma'lum";
  return compact
    ? date.toLocaleString("uz-UZ", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
    : date.toLocaleString();
}

function deviceLabel(value: any): string {
  const deviceInfo = typeof value === "string" ? value : "";
  if (!deviceInfo) return "Noma'lum qurilma";
  if (deviceInfo.includes("iPhone")) return "iPhone";
  if (deviceInfo.includes("iPad")) return "iPad";
  if (deviceInfo.includes("Android")) return "Android";
  if (deviceInfo.includes("Mac OS")) return "Mac";
  if (deviceInfo.includes("Windows")) return "Windows";
  return "Noma'lum";
}

export function AdminSurveysPanel({
  onAdminCall,
}: {
  onAdminCall: (path: string, payload?: any, method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE", successText?: string) => Promise<any>;
}) {
  const pt = useWebT();
  const [surveys, setSurveys] = useState<GenericRow[]>([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [questions, setQuestions] = useState<{ id: string; text: string; type: "single_choice" | "multiple_choice" | "text" | "rating"; options: string[] }[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedSurvey, setSelectedSurvey] = useState<GenericRow | null>(null);
  const [surveyResults, setSurveyResults] = useState<{ survey: GenericRow; responses: GenericRow[] } | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<GenericRow | null>(null); // survey row to delete
  const [deleting, setDeleting] = useState(false);
  const [editingSurveyId, setEditingSurveyId] = useState<number | null>(null);
  const [selectedResponse, setSelectedResponse] = useState<GenericRow | null>(null);
  useEffect(() => {
    loadSurveys();
  }, []);

  async function loadSurveys() {
    setLoading(true);
    const res = await onAdminCall("/admin/surveys", undefined, "GET");
    if (res && res.items) {
      setSurveys(res.items);
    }
    setLoading(false);
  }

  function openCreateModal() {
    setEditingSurveyId(null);
    setTitle("");
    setDescription("");
    setQuestions([
      { id: Date.now().toString(), text: "", type: "single_choice", options: ["", ""] }
    ]);
    setShowCreateModal(true);
  }

  function openEditModal(row: GenericRow) {
    setEditingSurveyId(row.id);
    setTitle(row.title);
    setDescription(row.description || "");
    
    let parsedQs = [];
    try {
      parsedQs = JSON.parse(row.questions_json);
    } catch(e) {}
    if (!parsedQs || parsedQs.length === 0) {
      parsedQs = [{ id: Date.now().toString(), text: "", type: "single_choice", options: ["", ""] }];
    }
    
    // Ensure all questions have string options arrays to avoid mapping errors
    parsedQs = parsedQs.map((q: any) => ({
      ...q,
      options: Array.isArray(q.options) ? q.options : ["", ""]
    }));
    
    setQuestions(parsedQs);
    setShowCreateModal(true);
  }

  function addQuestion() {
    setQuestions((prev) => [
      ...prev,
      { id: Date.now().toString(), text: "", type: "single_choice", options: ["", ""] }
    ]);
  }

  function updateQuestion(idx: number, patch: any) {
    setQuestions((prev) => prev.map((q, i) => i === idx ? { ...q, ...patch } : q));
  }
  
  function removeQuestion(idx: number) {
    setQuestions((prev) => prev.filter((_, i) => i !== idx));
  }

  async function createSurvey() {
    if (!title.trim()) {
      alert(pt("survey.error.titleRequired", "So'rovnoma sarlavhasini kiriting!"));
      return;
    }
    if (questions.length === 0) {
      alert(pt("survey.error.questionRequired", "Kamida bitta savol kiritilishi shart!"));
      return;
    }
    for (let i = 0; i < questions.length; i++) {
      if (!questions[i].text.trim()) {
        alert(`${i + 1}-savol matni bo'sh bo'lmasligi kerak!`);
        return;
      }
    }

    setLoading(true);
    const payload = {
      title,
      description,
      questions
    };
    
    const isEditing = editingSurveyId !== null;
    const url = isEditing ? `/admin/surveys/${editingSurveyId}` : "/admin/surveys";
    const method = isEditing ? "PUT" : "POST";
    const msg = isEditing 
      ? pt("survey.updatedSuccess", "So'rovnoma muvaffaqiyatli yangilandi") 
      : pt("survey.createdSuccess", "So'rovnoma muvaffaqiyatli yaratildi");
      
    const res = await onAdminCall(url, payload, method, msg);
    if (res && res.survey_id) {
      setTitle("");
      setDescription("");
      setQuestions([]);
      setEditingSurveyId(null);
      setShowCreateModal(false);
      loadSurveys();
    }
    setLoading(false);
  }
  
  async function loadResults(surveyId: number) {
    setSurveyResults(null);
    const res = await onAdminCall(`/admin/surveys/${surveyId}/results`, undefined, "GET");
    if (res && res.survey) {
      setSelectedSurvey(res.survey);
      setSurveyResults(res);
    }
  }

  async function deleteSurvey(row: GenericRow) {
    setDeleting(true);
    const res = await onAdminCall(`/admin/surveys/${row.id}`, undefined, "DELETE", `"${row.title}" so'rovnomasi o'chirildi`);
    setDeleting(false);
    setDeleteConfirm(null);
    if (res !== null && res !== undefined) {
      loadSurveys();
    }
  }

  return (
    <div className="page-stack">
      {/* Header section with Create Button */}
      <section className="panel-card flex items-center justify-between gap-4">
        <div>
          <h3 className="m-0 text-xl font-bold flex items-center gap-2">
            📝 {pt("survey.manageTitle", "So'rovnomalar Boshqaruvi")}
          </h3>
          <p className="text-sm text-ink-500 m-0 mt-1">
            {pt("survey.manageDesc", "Talabalar va Telegram foydalanuvchilari uchun so'rovnomalar yaratish va natijalarni tahlil qilish")}
          </p>
        </div>
        <button className="btn btn-primary flex items-center gap-2 whitespace-nowrap" onClick={openCreateModal}>
          <span>+</span> {pt("survey.createButtonNew", "Yangi So'rovnoma Yaratish")}
        </button>
      </section>

      {/* CREATE SURVEY POPUP MODAL */}
      <ModalPortal open={showCreateModal}>
        <div
          className="survey-modal-backdrop fixed inset-0 z-[2147483000] bg-black/70 backdrop-blur-sm animate-fadeIn flex items-center justify-center p-3 sm:p-6"
          role="dialog"
          aria-modal="true"
          onClick={(e) => { if (e.target === e.currentTarget) setShowCreateModal(false); }}
        >
          <div className="survey-modal-card bg-surface panel-card w-full max-w-3xl flex flex-col shadow-2xl border border-line rounded-2xl overflow-hidden p-0">
            {/* Modal Header */}
            <div className="row-between p-4 sm:p-5 bg-surface border-b border-line shrink-0">
              <div className="flex items-center gap-3">
                <span className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-500 flex items-center justify-center text-xl font-bold border border-indigo-500/20 shrink-0">
                  📝
                </span>
                <div>
                  <h3 className="m-0 text-base sm:text-lg font-bold">
                    {editingSurveyId ? "So'rovnomani Tahrirlash" : pt("survey.createTitle", "Yangi So'rovnoma Yaratish")}
                  </h3>
                  <p className="text-xs text-ink-500 m-0">{pt("survey.createSubtitle", "Savollar ketma-ketligini va variantlarini belgilang")}</p>
                </div>
              </div>
              <button 
                className="w-8 h-8 rounded-lg bg-body hover:bg-line text-ink-500 hover:text-ink flex items-center justify-center transition-colors text-base font-bold shrink-0" 
                onClick={() => setShowCreateModal(false)}
              >
                ✕
              </button>
            </div>
            
            {/* Modal Body */}
            <div className="survey-modal-scroll p-4 sm:p-6 flex-1 overflow-y-auto touch-pan-y overscroll-contain flex flex-col gap-5 sm:gap-6 min-h-0">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                <label className="flex flex-col gap-1.5 font-semibold text-sm">
                  {pt("survey.titleLabel", "So'rovnoma Sarlavhasi")} *
                  <input 
                    className="input-field"
                    value={title} 
                    onChange={(e) => setTitle(e.target.value)} 
                    placeholder={pt("survey.titlePlaceholder", "Masalan: Kurs sifati bo'yicha fikringiz")} 
                  />
                </label>
                <label className="flex flex-col gap-1.5 font-semibold text-sm">
                  {pt("survey.descLabel", "Tavsif (Ixtiyoriy)")}
                  <textarea 
                    className="input-field whitespace-pre-wrap"
                    rows={1}
                    value={description} 
                    onChange={(e) => setDescription(e.target.value)} 
                    placeholder={pt("survey.descPlaceholder", "Qisqacha mazmuni va maqsadi")} 
                  />
                </label>
              </div>

              <div className="flex items-center justify-between border-b border-line pb-2">
                <h4 className="m-0 text-sm sm:text-base font-bold text-ink flex items-center gap-2">
                  ❓ {pt("survey.questionsListTitle", "Savollar Ro'yxati")} ({questions.length})
                </h4>
                <button className="btn btn-soft small flex items-center gap-1 text-xs" onClick={addQuestion}>
                  + {pt("survey.addQuestion", "Savol qo'shish")}
                </button>
              </div>

              <div className="flex flex-col gap-4">
                {questions.map((q, qIndex) => (
                  <div key={q.id} className="p-3 sm:p-4 rounded-xl border border-line bg-body/50 flex flex-col gap-3 relative">
                    <div className="flex items-center justify-between border-b border-line/60 pb-2">
                      <span className="text-xs font-bold uppercase tracking-wider px-2.5 py-1 rounded-md bg-indigo-500/10 text-indigo-500 border border-indigo-500/20">
                        {qIndex + 1}-Savol
                      </span>
                      {questions.length > 1 && (
                        <button 
                          className="btn btn-soft small text-red-500 hover:bg-red-500/10 px-2 py-0.5 text-xs font-bold" 
                          onClick={() => removeQuestion(qIndex)}
                        >
                          ✕ {pt("common.delete", "O'chirish")}
                        </button>
                      )}
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                      <label className="flex flex-col gap-1 text-xs font-semibold text-ink-500">
                        {pt("survey.questionText", "Savol Matni")}
                        <textarea 
                          className="input-field whitespace-pre-wrap leading-relaxed"
                          rows={2}
                          value={q.text} 
                          onChange={(e) => updateQuestion(qIndex, { text: e.target.value })} 
                          placeholder={`${qIndex + 1}-savol matnini yozing (yangi qator uchun Enter)...`}
                        />
                      </label>
                      <label className="flex flex-col gap-1 text-xs font-semibold text-ink-500">
                        {pt("survey.questionType", "Savol Turi")}
                        <select 
                          className="input-field"
                          value={q.type} 
                          onChange={(e) => updateQuestion(qIndex, { type: e.target.value })}
                        >
                          <option value="single_choice">🔘 {pt("survey.typeSingleChoice", "Bitta tanlov (Radio)")}</option>
                          <option value="multiple_choice">☑️ {pt("survey.typeMultipleChoice", "Bir nechta tanlov (Checkbox)")}</option>
                          <option value="text">✍️ {pt("survey.typeText", "Yozma javob (Textarea)")}</option>
                          <option value="rating">⭐ {pt("survey.typeRating", "Baho / Reyting (1-5 Yulduz)")}</option>
                        </select>
                      </label>
                    </div>


                    {(q.type === "single_choice" || q.type === "multiple_choice") && (
                      <div className="mt-2 pl-3 border-l-2 border-indigo-500/40 flex flex-col gap-2">
                        <p className="text-xs font-bold text-ink-500 uppercase tracking-wider mb-1">
                          {pt("survey.optionsLabel", "Variantlar:")}
                        </p>
                        {q.options.map((opt, oIndex) => (
                          <div key={oIndex} className="flex items-center gap-2">
                            <input 
                              className="input-field text-sm py-1.5"
                              value={opt} 
                              onChange={(e) => {
                                const newOpts = [...q.options];
                                newOpts[oIndex] = e.target.value;
                                updateQuestion(qIndex, { options: newOpts });
                              }} 
                              placeholder={`${pt("survey.optionPrefix", "Variant")} ${oIndex + 1}`}
                            />
                            {q.options.length > 1 && (
                              <button 
                                className="w-8 h-8 rounded-lg bg-line hover:bg-red-500/10 hover:text-red-500 flex items-center justify-center text-xs font-bold transition-colors" 
                                onClick={() => {
                                  const newOpts = q.options.filter((_, i) => i !== oIndex);
                                  updateQuestion(qIndex, { options: newOpts });
                                }}
                              >
                                ✕
                              </button>
                            )}
                          </div>
                        ))}
                        <button 
                          className="btn btn-soft small self-start mt-1 text-xs" 
                          onClick={() => updateQuestion(qIndex, { options: [...q.options, ""] })}
                        >
                          + {pt("survey.addOption", "Variant qo'shish")}
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="survey-modal-footer p-4 bg-surface border-t border-line row-between shrink-0">
              <button className="btn btn-soft" onClick={() => setShowCreateModal(false)}>
                {pt("common.cancel", "Bekor qilish")}
              </button>
              <button className="btn btn-primary" onClick={createSurvey} disabled={loading}>
                {loading ? pt("common.saving", "Saqlanmoqda...") : editingSurveyId ? "O'zgarishlarni Saqlash" : pt("survey.createButton", "So'rovnomani Saqlash va Yaratish")}
              </button>
            </div>
          </div>
        </div>
      </ModalPortal>

      {/* RESULTS MODAL */}
      <ModalPortal open={Boolean(selectedSurvey && surveyResults)}>
        {selectedSurvey && surveyResults && (
          <div
            className="survey-modal-backdrop fixed inset-0 z-[2147483000] bg-black/60 backdrop-blur-sm animate-fadeIn flex items-center justify-center p-3 sm:p-6"
            role="dialog"
            aria-modal="true"
            onClick={(e) => { if (e.target === e.currentTarget) { setSelectedSurvey(null); setSurveyResults(null); setSelectedResponse(null); } }}
          >
            <div className="survey-modal-card bg-surface panel-card w-full max-w-4xl flex flex-col shadow-2xl border border-line rounded-2xl overflow-hidden p-0">
              <div className="row-between p-4 sm:p-5 bg-surface border-b border-line shrink-0">
                <div className="flex items-center gap-3">
                  {selectedResponse && (
                    <button 
                      className="btn btn-soft small p-2" 
                      onClick={() => setSelectedResponse(null)}
                      title="Orqaga"
                    >
                      ⬅️
                    </button>
                  )}
                  <div>
                    <h3 className="m-0 text-base sm:text-lg font-bold">
                      {selectedResponse ? "Javoblar tafsiloti" : `${pt("survey.resultsTitle", "Natijalar")}: ${selectedSurvey.title}`}
                    </h3>
                    <p className="text-xs text-ink-500 m-0 mt-0.5">
                      {selectedResponse 
                        ? cleanRespondentName(selectedResponse)
                        : pt("survey.responsesCount", "{count} ta javob qabul qilindi", { count: surveyResults.responses.length })
                      }
                    </p>
                  </div>
                </div>
                <button className="btn btn-soft" onClick={() => { setSelectedSurvey(null); setSurveyResults(null); setSelectedResponse(null); }}>
                  {pt("common.close", "Yopish")}
                </button>
              </div>
              
              <div className="survey-modal-scroll p-4 sm:p-6 flex-1 overflow-y-auto touch-pan-y overscroll-contain flex flex-col gap-4 min-h-0 bg-body/30">
                {!selectedResponse ? (
                  /* LIST VIEW */
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                    {surveyResults.responses.map((resp, i) => {
                      const answers = parseSurveyAnswers(resp.answers_json);
                      const respondentName = cleanRespondentName(resp);
                      const initial = respondentInitial(resp, respondentName);
                      const deviceName = deviceLabel(answers.__device_info__);
                      const respondentMeta = String(resp.respondent_meta || "").trim();

                      return (
                        <div 
                          key={resp.id || i} 
                          className="p-4 border border-line rounded-xl bg-surface hover:border-indigo-500/50 hover:shadow-md cursor-pointer transition-all flex flex-col gap-3 group relative"
                          onClick={() => setSelectedResponse(resp)}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-center gap-3 overflow-hidden">
                              <span className="w-10 h-10 rounded-full bg-indigo-500/10 text-indigo-500 flex items-center justify-center font-bold shrink-0">
                                {initial}
                              </span>
                              <div className="truncate">
                                <h4 className="m-0 text-sm font-bold truncate group-hover:text-indigo-600 transition-colors">
                                  {respondentName}
                                </h4>
                                <p className="text-xs text-ink-500 m-0 truncate mt-0.5 flex items-center gap-1.5">
                                  <span>📅 {formatSubmittedAt(resp.submitted_at, true)}</span>
                                </p>
                                {respondentMeta ? <p className="text-[11px] text-ink-500 m-0 truncate mt-0.5">{respondentMeta}</p> : null}
                              </div>
                            </div>
                            <button className="btn btn-primary small shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                              Ko'rish
                            </button>
                          </div>
                          <div className="flex flex-wrap gap-2 mt-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded bg-body text-ink-500 border border-line flex items-center gap-1">
                              📱 {deviceName}
                            </span>
                            {resp.telegram_id && (
                              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded bg-blue-500/10 text-blue-600 border border-blue-500/20 flex items-center gap-1">
                                💬 Telegram
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                    {surveyResults.responses.length === 0 && (
                      <div className="col-span-full flex flex-col items-center justify-center py-16 text-ink-500 bg-surface rounded-2xl border border-line border-dashed">
                        <span className="text-4xl mb-3 opacity-50">📭</span>
                        <p>{pt("survey.noResponses", "Hozircha hech kim javob bermagan")}</p>
                      </div>
                    )}
                  </div>
                ) : (
                  /* DETAIL VIEW */
                  <div className="flex flex-col gap-5 max-w-3xl mx-auto w-full animate-fadeIn">
                    <div className="bg-surface p-5 rounded-xl border border-line flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
                      <div className="flex items-center gap-4">
                        <span className="w-12 h-12 rounded-full bg-indigo-500/10 text-indigo-500 flex items-center justify-center font-bold text-xl shrink-0">
                          {respondentInitial(selectedResponse, cleanRespondentName(selectedResponse))}
                        </span>
                        <div>
                          <h4 className="m-0 text-base font-bold">
                            {cleanRespondentName(selectedResponse)}
                          </h4>
                          <p className="text-xs text-ink-500 m-0 mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                            <span>📅 {formatSubmittedAt(selectedResponse.submitted_at)}</span>
                            <span>📱 {String(parseSurveyAnswers(selectedResponse.answers_json).__device_info__ || "Noma'lum qurilma")}</span>
                          </p>
                          {String(selectedResponse.respondent_meta || "").trim() ? (
                            <p className="text-xs text-ink-500 m-0 mt-1">{selectedResponse.respondent_meta}</p>
                          ) : null}
                        </div>
                      </div>
                      {selectedResponse.telegram_id && (
                        <a 
                          href={selectedResponse.tg_username ? `https://t.me/${selectedResponse.tg_username}` : `tg://user?id=${selectedResponse.telegram_id}`} 
                          target="_blank" 
                          rel="noreferrer"
                          className="btn btn-soft small text-xs font-bold flex items-center gap-2 whitespace-nowrap bg-[#0088cc]/10 text-[#0088cc] border-[#0088cc]/20 hover:bg-[#0088cc]/20"
                        >
                          💬 Telegram Profili
                        </a>
                      )}
                    </div>
                    
                    <div className="flex flex-col gap-3">
                      <h4 className="text-sm font-bold text-ink-500 uppercase tracking-wider mb-2 ml-1">Javoblar:</h4>
                      {(() => {
                        const answers = parseSurveyAnswers(selectedResponse.answers_json);
                        let questions = selectedSurvey.questions_json || [];
                        if (typeof questions === "string") {
                          try { questions = JSON.parse(questions); } catch(e) { questions = []; }
                        } else if (!Array.isArray(questions)) {
                          questions = [];
                        }

                        // Filter out metadata
                        const answerEntries = Object.entries(answers).filter(([k]) => !k.startsWith('__'));
                        if (answerEntries.length === 0) {
                          return (
                            <div className="bg-surface p-4 rounded-xl border border-line text-sm text-ink-500">
                              Javoblar topilmadi.
                            </div>
                          );
                        }

                        return answerEntries.map(([qId, ans], idx) => {
                          const qObj = questions.find((q: any) => String(q.id) === String(qId));
                          let displayAns = "";
                          if (Array.isArray(ans)) {
                            displayAns = ans.join(", ");
                          } else if (qObj?.type === "rating" || typeof ans === "number") {
                            const num = Number(ans) || 0;
                            displayAns = "⭐".repeat(num) + ` (${num}/5)`;
                          } else {
                            displayAns = String(ans);
                          }
                          return (
                            <div key={qId} className="bg-surface p-4 rounded-xl border border-line shadow-sm relative overflow-hidden">
                              <div className="absolute top-0 left-0 bottom-0 w-1 bg-indigo-500/50"></div>
                              <p className="text-sm text-ink-600 mb-2 font-semibold flex gap-2">
                                <span className="opacity-50">{idx + 1}.</span> 
                                <span className="whitespace-pre-wrap">{qObj ? qObj.text : qId}</span>
                              </p>
                              <div className="bg-body/50 p-3 rounded-lg border border-line/60">
                                <p className="font-bold text-sm text-ink whitespace-pre-wrap">{displayAns}</p>
                              </div>
                            </div>
                          );
                        });
                      })()}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </ModalPortal>

      {/* DELETE CONFIRM MODAL */}
      {deleteConfirm && (
        <div
          className="fixed inset-0 z-[200] bg-black/70 backdrop-blur-sm animate-fadeIn"
          style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "16px" }}
        >
          <div className="bg-surface border border-line rounded-2xl shadow-2xl w-full max-w-sm p-6 flex flex-col gap-5">
            <div className="flex flex-col items-center gap-3 text-center">
              <span className="w-14 h-14 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-3xl">🗑️</span>
              <h3 className="m-0 text-base font-bold">So'rovnomani o'chirish</h3>
              <p className="text-sm text-ink-500 m-0">
                <span className="font-semibold text-ink">«{deleteConfirm.title}»</span> so'rovnomasi va unga tegishli barcha javoblar butunlay o'chiriladi.
              </p>
              <p className="text-xs text-red-500 font-medium bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2 w-full">
                ⚠️ Bu amalni qaytarib bo'lmaydi!
              </p>
            </div>
            <div className="flex gap-3">
              <button
                className="btn btn-soft flex-1"
                onClick={() => setDeleteConfirm(null)}
                disabled={deleting}
              >
                Bekor qilish
              </button>
              <button
                className="btn flex-1 font-bold"
                style={{ background: "var(--color-error, #ef4444)", color: "#fff", opacity: deleting ? 0.6 : 1 }}
                onClick={() => deleteSurvey(deleteConfirm)}
                disabled={deleting}
              >
                {deleting ? "O'chirilmoqda..." : "Ha, o'chirish"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* SURVEYS LIST TABLE */}
      <section className="panel-card">
        <h3 className="text-base font-bold mb-3">{pt("survey.historyTitle", "Mavjud So'rovnomalar Ro'yxati")}</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>{pt("survey.colTitle", "Sarlavha")}</th>
                <th>{pt("survey.colDate", "Yaratilgan sana")}</th>
                <th>{pt("survey.colLink", "Telegram Link")}</th>
                <th className="text-right">Amallar</th>
              </tr>
            </thead>
            <tbody>
              {surveys.map(row => (
                <tr key={row.id}>
                  <td className="font-bold text-xs">#{row.id}</td>
                  <td className="font-semibold">{row.title}</td>
                  <td className="text-xs text-ink-500">{new Date(row.created_at).toLocaleString()}</td>
                  <td>
                    <button 
                      className="btn btn-soft small text-xs flex items-center gap-1" 
                      onClick={() => {
                        const link = `https://diamond-education.uz/?startapp=survey_${row.id}`;
                        navigator.clipboard.writeText(link);
                        alert(`${pt("survey.copiedMsg", "Havola nusxalandi:")} ${link}\n${pt("survey.broadcastHint", "Buni Broadcast orqali yuborishingiz mumkin.")}`);
                      }}
                    >
                      📋 {pt("survey.copyLink", "Linkni nusxalash")}
                    </button>
                  </td>
                  <td className="text-right flex items-center justify-end gap-2">
                    <button 
                      className="btn btn-primary small px-3 text-base" 
                      onClick={() => loadResults(Number(row.id))}
                      title={pt("survey.viewResults", "Natijalar")}
                    >
                      📊
                    </button>
                    <button
                      className="btn btn-soft small px-3 text-base"
                      onClick={() => openEditModal(row)}
                      title="Tahrirlash"
                    >
                      ✏️
                    </button>
                    <button
                      className="btn btn-soft small px-3 text-base"
                      style={{ color: "var(--color-error, #ef4444)", borderColor: "rgba(239,68,68,0.25)" }}
                      onClick={() => setDeleteConfirm(row)}
                      title="O'chirish"
                    >
                      🗑️
                    </button>
                  </td>
                </tr>
              ))}
              {surveys.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center py-8 text-ink-500">{pt("survey.noSurveys", "Hozircha so'rovnomalar mavjud emas")}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
