"use client";

import React, { useState, useEffect } from "react";

type VocabularyItem = {
  word: string;
  definition: string;
  example: string;
};

type SpeakingQuestion = {
  id: number;
  topic_id: number;
  part: number;
  question_text: string;
  cue_card_bullet_points?: string[];
  sample_answer: string;
  examiner_tip?: string;
  vocabulary?: VocabularyItem[];
  sort_order: number;
};

type SpeakingTopic = {
  id: number;
  part: number;
  title: string;
  status_badge: string;
  sort_order: number;
  created_at: string;
  question_count: number;
};

interface AdminSpeakingTopicsProps {
  apiFetch: (path: string, options?: { method?: string; body?: any }) => Promise<any>;
}

export function AdminSpeakingTopics({ apiFetch }: AdminSpeakingTopicsProps) {
  const [activePart, setActivePart] = useState<number>(1);
  const [topics, setTopics] = useState<SpeakingTopic[]>([]);
  const [questions, setQuestions] = useState<SpeakingQuestion[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [expandedTopicId, setExpandedTopicId] = useState<number | null>(null);

  // AI Modal State
  const [aiModalOpen, setAiModalOpen] = useState<boolean>(false);
  const [aiTheme, setAiTheme] = useState<string>("");
  const [aiPart, setAiPart] = useState<number>(1);
  const [aiCount, setAiCount] = useState<number>(2);
  const [aiInstruction, setAiInstruction] = useState<string>("");
  const [aiLoading, setAiLoading] = useState<boolean>(false);
  const [aiGeneratedResult, setAiGeneratedResult] = useState<any | null>(null);

  // Manual Add Topic Modal
  const [newTopicModalOpen, setNewTopicModalOpen] = useState<boolean>(false);
  const [newTopicTitle, setNewTopicTitle] = useState<string>("");
  const [newTopicBadge, setNewTopicBadge] = useState<string>("PREDICTED");
  const [newTopicPart, setNewTopicPart] = useState<number>(1);

  // Manual Add Question Modal
  const [newQuestionModalOpen, setNewQuestionModalOpen] = useState<boolean>(false);
  const [targetTopicId, setTargetTopicId] = useState<number | null>(null);
  const [qText, setQText] = useState<string>("");
  const [qAnswer, setQAnswer] = useState<string>("");
  const [qBullets, setQBullets] = useState<string>("");
  const [qTip, setQTip] = useState<string>("");
  const [qVocabWord, setQVocabWord] = useState<string>("");
  const [qVocabDef, setQVocabDef] = useState<string>("");
  const [qVocabEx, setQVocabEx] = useState<string>("");
  const [vocabList, setVocabList] = useState<VocabularyItem[]>([]);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const res = await apiFetch("/staff/speaking/topics", { method: "GET" });
      if (res && res.topics) {
        setTopics(res.topics);
        setQuestions(res.questions || []);
      }
    } catch (e: any) {
      alert("Mavzularni yuklashda xatolik: " + (e?.message || String(e)));
    } finally {
      setLoading(false);
    }
  }

  const filteredTopics = topics.filter((t) => t.part === activePart);

  // Trigger AI Generator
  async function handleAiGenerate() {
    if (!aiTheme.trim()) {
      alert("Iltimos, mavzu nomini yoki kalit so'zni kiriting.");
      return;
    }
    setAiLoading(true);
    try {
      const res = await apiFetch("/staff/speaking/ai-generate", {
        method: "POST",
        body: {
          theme: aiTheme.trim(),
          part: aiPart,
          question_count: aiCount,
          custom_instruction: aiInstruction.trim() || undefined,
        },
      });
      setAiGeneratedResult(res);
    } catch (e: any) {
      alert("Diamondvoy AI generatsiyasida xatolik: " + (e?.message || String(e)));
    } finally {
      setAiLoading(false);
    }
  }

  // Save AI Generated Topic & Questions to Database
  async function handleSaveAiResult() {
    if (!aiGeneratedResult) return;
    setAiLoading(true);
    try {
      // 1. Create Topic
      const topicRes = await apiFetch("/staff/speaking/topics", {
        method: "POST",
        body: {
          part: aiPart,
          title: aiGeneratedResult.topic_title || aiTheme,
          status_badge: aiGeneratedResult.status_badge || "2026 PREDICTED",
          sort_order: 0,
        },
      });

      const createdTopic = topicRes?.topic;
      if (!createdTopic || !createdTopic.id) {
        throw new Error("Mavzu yaratilmadi.");
      }

      // 2. Add Questions
      const questionsToSave = aiGeneratedResult.questions || [];
      for (const q of questionsToSave) {
        await apiFetch(`/staff/speaking/topics/${createdTopic.id}/questions`, {
          method: "POST",
          body: {
            part: aiPart,
            question_text: q.question_text || "",
            cue_card_bullet_points: q.cue_card_bullet_points || [],
            sample_answer: q.sample_answer || "",
            examiner_tip: q.examiner_tip || "",
            vocabulary: q.vocabulary || [],
            sort_order: 0,
          },
        });
      }

      alert("✨ Yangi mavzu va savollar muvaffaqiyatli saqlandi!");
      setAiModalOpen(false);
      setAiGeneratedResult(null);
      setAiTheme("");
      setAiInstruction("");
      await loadData();
    } catch (e: any) {
      alert("Saqlashda xatolik yuz berdi: " + (e?.message || String(e)));
    } finally {
      setAiLoading(false);
    }
  }

  // Manual Add Topic
  async function handleAddTopic() {
    if (!newTopicTitle.trim()) {
      alert("Mavzu nomini kiriting");
      return;
    }
    try {
      await apiFetch("/staff/speaking/topics", {
        method: "POST",
        body: {
          part: newTopicPart,
          title: newTopicTitle.trim(),
          status_badge: newTopicBadge.trim(),
        },
      });
      setNewTopicModalOpen(false);
      setNewTopicTitle("");
      await loadData();
    } catch (e: any) {
      alert("Xatolik: " + (e?.message || String(e)));
    }
  }

  // Delete Topic
  async function handleDeleteTopic(topicId: number) {
    if (!confirm("Haqiqatan ham bu mavzuni va uning barcha savollarini o'chirmoqchimisiz?")) return;
    try {
      await apiFetch(`/staff/speaking/topics/${topicId}`, { method: "DELETE" });
      await loadData();
    } catch (e: any) {
      alert("O'chirishda xatolik: " + (e?.message || String(e)));
    }
  }

  // Manual Add Question
  async function handleAddQuestion() {
    if (!targetTopicId || !qText.trim() || !qAnswer.trim()) {
      alert("Savol matni va namunaviy javobni kiriting.");
      return;
    }
    try {
      const bullets = qBullets
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);

      await apiFetch(`/staff/speaking/topics/${targetTopicId}/questions`, {
        method: "POST",
        body: {
          part: activePart,
          question_text: qText.trim(),
          cue_card_bullet_points: bullets,
          sample_answer: qAnswer.trim(),
          examiner_tip: qTip.trim() || undefined,
          vocabulary: vocabList,
        },
      });

      setNewQuestionModalOpen(false);
      setQText("");
      setQAnswer("");
      setQBullets("");
      setQTip("");
      setVocabList([]);
      await loadData();
    } catch (e: any) {
      alert("Savol qo'shishda xatolik: " + (e?.message || String(e)));
    }
  }

  // Delete Question
  async function handleDeleteQuestion(qId: number) {
    if (!confirm("Savolni o'chirmoqchimisiz?")) return;
    try {
      await apiFetch(`/staff/speaking/questions/${qId}`, { method: "DELETE" });
      await loadData();
    } catch (e: any) {
      alert("O'chirishda xatolik: " + (e?.message || String(e)));
    }
  }

  function addVocabItem() {
    if (!qVocabWord.trim() || !qVocabDef.trim()) {
      alert("Lug'at so'zi va uning ma'nosini kiriting");
      return;
    }
    setVocabList([
      ...vocabList,
      {
        word: qVocabWord.trim(),
        definition: qVocabDef.trim(),
        example: qVocabEx.trim(),
      },
    ]);
    setQVocabWord("");
    setQVocabDef("");
    setQVocabEx("");
  }

  return (
    <div className="flex flex-col gap-6 pb-20 animate-fade-in max-w-6xl mx-auto">
      {/* ─── HEADER BAR ─── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-navy-900/60 dark:bg-[#0c143b]/80 backdrop-blur-md p-6 rounded-2xl border border-navy-700/40 shadow-xl">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 text-xs font-black uppercase tracking-wider rounded-full bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
              Diamond IELTS Speaking
            </span>
            <span className="text-xs text-ink-400">· 2026 Exam Engine</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
            Speaking App Mavzular & Savollar
          </h1>
          <p className="text-sm text-ink-300 mt-1">
            IELTS Speaking ilovasi uchun Part 1, Part 2 va Part 3 mavzularini boshqarish, savollar va Band 8-9 javoblarini qo‘shish hamda AI orqali generatsiya qilish.
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <button
            type="button"
            onClick={() => {
              setAiPart(activePart);
              setAiModalOpen(true);
            }}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold text-sm shadow-lg shadow-cyan-500/20 active:scale-95 transition-all"
          >
            <span className="text-base">✨</span>
            <span>AI orqali yaratish</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setNewTopicPart(activePart);
              setNewTopicModalOpen(true);
            }}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-navy-800 hover:bg-navy-700 text-white border border-navy-600 font-bold text-sm shadow-md active:scale-95 transition-all"
          >
            <span>➕</span>
            <span>Yangi mavzu</span>
          </button>

          <button
            type="button"
            onClick={loadData}
            title="Yangilash"
            className="p-2.5 rounded-xl bg-navy-800/80 hover:bg-navy-700 text-ink-300 hover:text-white border border-navy-700 active:scale-95 transition-all"
          >
            🔄
          </button>
        </div>
      </div>

      {/* ─── PART SEGMENTED SELECTOR ─── */}
      <div className="flex items-center gap-2 p-1.5 bg-navy-950/70 rounded-2xl border border-navy-800/70 shadow-inner max-w-md">
        {[
          { part: 1, label: "Part 1", desc: "Introduction" },
          { part: 2, label: "Part 2", desc: "Cue Cards" },
          { part: 3, label: "Part 3", desc: "Discussion" },
        ].map((item) => (
          <button
            key={item.part}
            type="button"
            onClick={() => setActivePart(item.part)}
            className={`flex-1 py-2.5 px-3 rounded-xl font-bold text-xs md:text-sm transition-all flex flex-col items-center ${
              activePart === item.part
                ? "bg-gradient-to-r from-blue-600 to-cyan-600 text-white shadow-md shadow-blue-600/30"
                : "text-ink-400 hover:text-white hover:bg-navy-900/40"
            }`}
          >
            <span>{item.label}</span>
            <span className="text-[10px] opacity-75 font-normal">{item.desc}</span>
          </button>
        ))}
      </div>

      {/* ─── TOPICS LIST / TABLE ─── */}
      {loading ? (
        <div className="p-12 text-center text-ink-400 bg-navy-900/30 rounded-2xl border border-navy-800/50">
          <div className="w-8 h-8 border-3 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          Mavzular yuklanmoqda...
        </div>
      ) : filteredTopics.length === 0 ? (
        <div className="p-12 text-center bg-navy-900/30 rounded-2xl border border-navy-800/50">
          <p className="text-lg font-bold text-white mb-2">Bu bo'limda hozircha mavzular yo'q</p>
          <p className="text-sm text-ink-400 mb-5">
            Diamondvoy AI orqali bir tugma bilan yangi IELTS Speaking mavzulari va savollarini yarating.
          </p>
          <button
            type="button"
            onClick={() => {
              setAiPart(activePart);
              setAiModalOpen(true);
            }}
            className="px-5 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-sm shadow-lg shadow-cyan-600/20 transition-all inline-flex items-center gap-2"
          >
            <span>✨</span>
            <span>AI orqali mavzu yaratish</span>
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredTopics.map((topic, index) => {
            const isExpanded = expandedTopicId === topic.id;
            const topicQuestions = questions.filter((q) => q.topic_id === topic.id);

            return (
              <div
                key={topic.id}
                className="bg-navy-900/60 dark:bg-[#0c143b]/70 border border-navy-700/50 hover:border-cyan-500/40 rounded-2xl transition-all shadow-lg overflow-hidden"
              >
                {/* Topic Header Row */}
                <div
                  className="p-4 md:p-5 flex items-center justify-between gap-4 cursor-pointer select-none"
                  onClick={() => setExpandedTopicId(isExpanded ? null : topic.id)}
                >
                  <div className="flex items-center gap-3.5 min-w-0">
                    <span className="w-8 h-8 rounded-lg bg-blue-600/20 text-cyan-400 border border-blue-500/30 font-black text-xs flex items-center justify-center shrink-0">
                      #{String(index + 1).padStart(2, "0")}
                    </span>

                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="text-base md:text-lg font-bold text-white truncate">
                          {topic.title}
                        </h3>
                        <span className="px-2 py-0.5 text-[10px] font-black uppercase tracking-wider rounded-md bg-amber-500/20 text-amber-300 border border-amber-500/30">
                          {topic.status_badge || "2026 PREDICTED"}
                        </span>
                      </div>
                      <p className="text-xs text-ink-400 mt-0.5">
                        {topicQuestions.length} ta savol va namuna javoblar
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setTargetTopicId(topic.id);
                        setNewQuestionModalOpen(true);
                      }}
                      className="px-3 py-1.5 rounded-lg bg-navy-800 hover:bg-navy-700 text-xs font-bold text-cyan-300 border border-navy-600 transition-all flex items-center gap-1"
                    >
                      <span>➕</span>
                      <span className="hidden sm:inline">Savol qo'shish</span>
                    </button>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteTopic(topic.id);
                      }}
                      className="p-1.5 rounded-lg text-rose-400 hover:bg-rose-950/40 border border-transparent hover:border-rose-800/50 transition-all"
                      title="Mavzuni o'chirish"
                    >
                      🗑️
                    </button>

                    <span className="text-ink-400 ml-1 transform transition-transform duration-200">
                      {isExpanded ? "▲" : "▼"}
                    </span>
                  </div>
                </div>

                {/* Expanded Questions Area */}
                {isExpanded && (
                  <div className="p-4 md:p-5 bg-navy-950/50 border-t border-navy-800/80 space-y-4">
                    {topicQuestions.length === 0 ? (
                      <div className="text-center py-6 text-ink-400 text-xs">
                        Bu mavzuda hozircha savollar yo'q. Yuqoridagi "Savol qo'shish" tugmasini bosing.
                      </div>
                    ) : (
                      topicQuestions.map((q, qIndex) => (
                        <div
                          key={q.id}
                          className="bg-navy-900/80 border border-navy-700/60 rounded-xl p-4 space-y-3 relative group"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex items-start gap-2.5">
                              <span className="w-5 h-5 rounded-full bg-cyan-600/20 text-cyan-300 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                                {qIndex + 1}
                              </span>
                              <h4 className="text-sm font-bold text-white leading-snug">
                                {q.question_text}
                              </h4>
                            </div>

                            <button
                              type="button"
                              onClick={() => handleDeleteQuestion(q.id)}
                              className="text-xs text-rose-400 hover:text-rose-300 opacity-60 group-hover:opacity-100 transition-opacity"
                              title="Savolni o'chirish"
                            >
                              O'chirish
                            </button>
                          </div>

                          {/* Cue Card Bullet Points (Part 2) */}
                          {q.cue_card_bullet_points && q.cue_card_bullet_points.length > 0 && (
                            <div className="bg-navy-950/70 p-3 rounded-lg border border-navy-800 text-xs text-ink-300 space-y-1">
                              <span className="font-bold text-cyan-400 uppercase text-[10px] tracking-wider block">
                                You should say:
                              </span>
                              {q.cue_card_bullet_points.map((pt, i) => (
                                <div key={i} className="flex items-center gap-1.5">
                                  <span className="text-cyan-400">•</span>
                                  <span>{pt}</span>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Band 8-9 Model Answer */}
                          <div className="bg-blue-950/20 border border-blue-900/40 p-3 rounded-lg text-xs space-y-1">
                            <span className="font-bold text-blue-400 uppercase text-[10px] tracking-wider block">
                              Band 8.5–9.0 Model Answer:
                            </span>
                            <p className="text-ink-200 leading-relaxed italic">{q.sample_answer}</p>
                          </div>

                          {/* Examiner Tip */}
                          {q.examiner_tip && (
                            <div className="text-[11px] text-amber-300 bg-amber-950/20 border border-amber-800/30 p-2.5 rounded-lg flex items-start gap-1.5">
                              <span>💡</span>
                              <span>
                                <strong>Examiner Tip:</strong> {q.examiner_tip}
                              </span>
                            </div>
                          )}

                          {/* Vocabulary items */}
                          {q.vocabulary && q.vocabulary.length > 0 && (
                            <div className="space-y-1.5 pt-1">
                              <span className="text-[10px] font-bold uppercase tracking-wider text-ink-400 block">
                                Band 9 Lexical Resource / Vocabulary:
                              </span>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                {q.vocabulary.map((v, vi) => (
                                  <div
                                    key={vi}
                                    className="bg-navy-950/60 p-2 rounded-lg border border-navy-800 text-xs"
                                  >
                                    <span className="font-bold text-cyan-300">{v.word}</span>:{" "}
                                    <span className="text-ink-300">{v.definition}</span>
                                    {v.example && (
                                      <p className="text-[11px] text-ink-400 italic mt-0.5">
                                        "{v.example}"
                                      </p>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ─── MODAL: AI GENERATOR (DIAMONDVOY) ─── */}
      {aiModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
          <div className="bg-navy-900 dark:bg-[#0c143b] border border-cyan-500/40 rounded-3xl max-w-2xl w-full p-6 md:p-8 space-y-6 shadow-2xl overflow-y-auto max-h-[90vh]">
            <div className="flex items-center justify-between border-b border-navy-800 pb-4">
              <div className="flex items-center gap-2.5">
                <span className="text-2xl">✨</span>
                <div>
                  <h3 className="text-xl font-extrabold text-white">Diamondvoy AI Speaking Generator</h3>
                  <p className="text-xs text-cyan-400">Learning Path kabi to'liq avtomatik IELTS savollar va javoblar</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setAiModalOpen(false)}
                className="text-ink-400 hover:text-white text-xl"
              >
                ✕
              </button>
            </div>

            {!aiGeneratedResult ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-ink-300 mb-1.5">
                    Mavzu mavzusi yoki kalit so'z (Theme):
                  </label>
                  <input
                    type="text"
                    value={aiTheme}
                    onChange={(e) => setAiTheme(e.target.value)}
                    placeholder="Masalan: Artificial Intelligence, Traditional Festivals, Environmental Protection"
                    className="w-full px-4 py-3 rounded-xl bg-navy-950 border border-navy-700 text-white placeholder-ink-500 text-sm focus:border-cyan-400 outline-none"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-ink-300 mb-1.5">
                      IELTS Bo'limi (Part):
                    </label>
                    <select
                      value={aiPart}
                      onChange={(e) => setAiPart(Number(e.target.value))}
                      className="w-full px-4 py-3 rounded-xl bg-navy-950 border border-navy-700 text-white text-sm focus:border-cyan-400 outline-none"
                    >
                      <option value={1}>Part 1 (Introduction)</option>
                      <option value={2}>Part 2 (Cue Card)</option>
                      <option value={3}>Part 3 (Discussion)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-ink-300 mb-1.5">
                      Savollar soni:
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={5}
                      value={aiCount}
                      onChange={(e) => setAiCount(Number(e.target.value))}
                      className="w-full px-4 py-3 rounded-xl bg-navy-950 border border-navy-700 text-white text-sm focus:border-cyan-400 outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-ink-300 mb-1.5">
                    Maxsus ko'rsatma (Ixtiyoriy):
                  </label>
                  <input
                    type="text"
                    value={aiInstruction}
                    onChange={(e) => setAiInstruction(e.target.value)}
                    placeholder="Masalan: Focus on academic collocations and predicted exam trends"
                    className="w-full px-4 py-3 rounded-xl bg-navy-950 border border-navy-700 text-white placeholder-ink-500 text-sm focus:border-cyan-400 outline-none"
                  />
                </div>

                <div className="pt-2">
                  <button
                    type="button"
                    onClick={handleAiGenerate}
                    disabled={aiLoading}
                    className="w-full py-3.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold text-sm shadow-xl shadow-cyan-500/20 active:scale-[0.98] transition-all flex items-center justify-center gap-2"
                  >
                    {aiLoading ? (
                      <>
                        <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        <span>Diamondvoy AI generatsiya qilmoqda...</span>
                      </>
                    ) : (
                      <>
                        <span>✨</span>
                        <span>Mavzu va Savollarni Generatsiya Qilish</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            ) : (
              /* Preview of Generated Content */
              <div className="space-y-4">
                <div className="p-4 bg-navy-950 rounded-2xl border border-cyan-500/30 space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-lg font-bold text-white">
                      {aiGeneratedResult.topic_title || aiTheme}
                    </h4>
                    <span className="px-2.5 py-0.5 text-xs font-black uppercase rounded-md bg-cyan-500/20 text-cyan-300">
                      {aiGeneratedResult.status_badge || "PREDICTED"}
                    </span>
                  </div>

                  <div className="space-y-3 pt-2">
                    {(aiGeneratedResult.questions || []).map((q: any, i: number) => (
                      <div key={i} className="p-3 bg-navy-900 rounded-xl border border-navy-700 text-xs space-y-2">
                        <p className="font-bold text-white">
                          #{i + 1} {q.question_text}
                        </p>
                        <p className="text-ink-300 italic">{q.sample_answer}</p>
                        {q.vocabulary && q.vocabulary.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 pt-1">
                            {q.vocabulary.map((v: any, vi: number) => (
                              <span
                                key={vi}
                                className="px-2 py-0.5 bg-navy-950 text-cyan-300 rounded border border-navy-800 text-[10px]"
                              >
                                {v.word}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-3 pt-2">
                  <button
                    type="button"
                    onClick={handleSaveAiResult}
                    disabled={aiLoading}
                    className="flex-1 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-sm shadow-lg shadow-emerald-600/30 active:scale-95 transition-all flex items-center justify-center gap-2"
                  >
                    {aiLoading ? "Saqlanmoqda..." : "✅ Tasdiqlash va Bazaga Saqlash"}
                  </button>

                  <button
                    type="button"
                    onClick={() => setAiGeneratedResult(null)}
                    disabled={aiLoading}
                    className="px-4 py-3 rounded-xl bg-navy-800 hover:bg-navy-700 text-ink-300 font-bold text-sm border border-navy-700 transition-all"
                  >
                    Qaytadan generatsiya
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── MODAL: MANUAL ADD TOPIC ─── */}
      {newTopicModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
          <div className="bg-navy-900 border border-navy-700 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-lg font-bold text-white">Yangi Mavzu Qo'shish</h3>
            <div>
              <label className="block text-xs font-bold text-ink-300 mb-1">Mavzu Nomi:</label>
              <input
                type="text"
                value={newTopicTitle}
                onChange={(e) => setNewTopicTitle(e.target.value)}
                placeholder="Masalan: Weather and Seasons"
                className="w-full px-3 py-2.5 rounded-xl bg-navy-950 border border-navy-700 text-white text-sm outline-none focus:border-cyan-400"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-ink-300 mb-1">Status Badge:</label>
              <select
                value={newTopicBadge}
                onChange={(e) => setNewTopicBadge(e.target.value)}
                className="w-full px-3 py-2.5 rounded-xl bg-navy-950 border border-navy-700 text-white text-sm outline-none"
              >
                <option value="PREDICTED">PREDICTED</option>
                <option value="HIGH FREQUENCY">HIGH FREQUENCY</option>
                <option value="COMMON">COMMON</option>
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setNewTopicModalOpen(false)}
                className="px-4 py-2 rounded-xl text-ink-400 hover:text-white text-sm"
              >
                Bekor qilish
              </button>
              <button
                type="button"
                onClick={handleAddTopic}
                className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-sm"
              >
                Qo'shish
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL: MANUAL ADD QUESTION ─── */}
      {newQuestionModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
          <div className="bg-navy-900 border border-navy-700 rounded-2xl max-w-xl w-full p-6 space-y-4 shadow-2xl max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-bold text-white">Mavzuga Yangi Savol Qo'shish</h3>

            <div>
              <label className="block text-xs font-bold text-ink-300 mb-1">Savol matni (Prompt):</label>
              <input
                type="text"
                value={qText}
                onChange={(e) => setQText(e.target.value)}
                placeholder="Savol matnini kiriting"
                className="w-full px-3 py-2.5 rounded-xl bg-navy-950 border border-navy-700 text-white text-sm outline-none focus:border-cyan-400"
              />
            </div>

            {activePart === 2 && (
              <div>
                <label className="block text-xs font-bold text-ink-300 mb-1">
                  Cue Card Bullet Points (har biri yangi qatorda):
                </label>
                <textarea
                  rows={3}
                  value={qBullets}
                  onChange={(e) => setQBullets(e.target.value)}
                  placeholder="Where you went&#10;Who accompanied you&#10;What happened"
                  className="w-full px-3 py-2.5 rounded-xl bg-navy-950 border border-navy-700 text-white text-sm outline-none"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-bold text-ink-300 mb-1">Band 8-9 Namunaviy Javob:</label>
              <textarea
                rows={4}
                value={qAnswer}
                onChange={(e) => setQAnswer(e.target.value)}
                placeholder="Model answer with rich vocabulary and fluency..."
                className="w-full px-3 py-2.5 rounded-xl bg-navy-950 border border-navy-700 text-white text-sm outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-ink-300 mb-1">Examiner Maslahati (Tip):</label>
              <input
                type="text"
                value={qTip}
                onChange={(e) => setQTip(e.target.value)}
                placeholder="Masalan: Extend your answer with contrasting examples."
                className="w-full px-3 py-2.5 rounded-xl bg-navy-950 border border-navy-700 text-white text-sm outline-none"
              />
            </div>

            {/* Vocab sub-form */}
            <div className="p-3 bg-navy-950 rounded-xl border border-navy-800 space-y-2">
              <span className="text-xs font-bold text-cyan-400 block">Band 9 Lug'at qo'shish:</span>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                <input
                  type="text"
                  placeholder="So'z / ibora"
                  value={qVocabWord}
                  onChange={(e) => setQVocabWord(e.target.value)}
                  className="px-2.5 py-1.5 rounded-lg bg-navy-900 border border-navy-700 text-xs text-white"
                />
                <input
                  type="text"
                  placeholder="Ma'nosi"
                  value={qVocabDef}
                  onChange={(e) => setQVocabDef(e.target.value)}
                  className="px-2.5 py-1.5 rounded-lg bg-navy-900 border border-navy-700 text-xs text-white"
                />
                <input
                  type="text"
                  placeholder="Misol (ixtiyoriy)"
                  value={qVocabEx}
                  onChange={(e) => setQVocabEx(e.target.value)}
                  className="px-2.5 py-1.5 rounded-lg bg-navy-900 border border-navy-700 text-xs text-white"
                />
              </div>
              <button
                type="button"
                onClick={addVocabItem}
                className="px-3 py-1 bg-navy-800 hover:bg-navy-700 text-cyan-300 rounded text-xs font-bold"
              >
                + Lug'at qo'shish
              </button>

              {vocabList.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {vocabList.map((v, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 bg-navy-900 text-cyan-300 border border-navy-700 rounded text-[11px]"
                    >
                      {v.word}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setNewQuestionModalOpen(false)}
                className="px-4 py-2 rounded-xl text-ink-400 hover:text-white text-sm"
              >
                Bekor qilish
              </button>
              <button
                type="button"
                onClick={handleAddQuestion}
                className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-sm"
              >
                Saqlash
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
