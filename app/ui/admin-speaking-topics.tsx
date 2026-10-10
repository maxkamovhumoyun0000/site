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
  apiFetch: (path: string, options?: { method?: string; body?: any; timeoutMs?: number; signal?: AbortSignal }) => Promise<any>;
}

export function AdminSpeakingTopics({ apiFetch }: AdminSpeakingTopicsProps) {
  const [activePart, setActivePart] = useState<number>(1);
  const [topics, setTopics] = useState<SpeakingTopic[]>([]);
  const [questions, setQuestions] = useState<SpeakingQuestion[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [expandedTopicId, setExpandedTopicId] = useState<number | null>(null);

  // AI Modal State
  const [aiModalOpen, setAiModalOpen] = useState<boolean>(false);
  const [aiMode, setAiMode] = useState<"new_topic" | "existing_topic">("new_topic");
  const [aiTargetTopicId, setAiTargetTopicId] = useState<number | null>(null);
  const [aiTheme, setAiTheme] = useState<string>("");
  const [aiPart, setAiPart] = useState<number>(1);
  const [aiCount, setAiCount] = useState<number>(2);
  const [aiInstruction, setAiInstruction] = useState<string>("");
  const [aiLoading, setAiLoading] = useState<boolean>(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiGeneratedResult, setAiGeneratedResult] = useState<any | null>(null);

  // Manual Add Topic Modal
  const [newTopicModalOpen, setNewTopicModalOpen] = useState<boolean>(false);
  const [newTopicTitle, setNewTopicTitle] = useState<string>("");
  const [newTopicBadge, setNewTopicBadge] = useState<string>("PREDICTED");
  const [newTopicPart, setNewTopicPart] = useState<number>(1);

  // Manual Add / Edit Question Modal
  const [newQuestionModalOpen, setNewQuestionModalOpen] = useState<boolean>(false);
  const [targetTopicId, setTargetTopicId] = useState<number | null>(null);
  const [editingQuestionId, setEditingQuestionId] = useState<number | null>(null);
  const [qText, setQText] = useState<string>("");
  const [qAnswer, setQAnswer] = useState<string>("");
  const [qBullets, setQBullets] = useState<string>("");
  const [qVocabWord, setQVocabWord] = useState<string>("");
  const [qVocabDef, setQVocabDef] = useState<string>("");
  const [qVocabEx, setQVocabEx] = useState<string>("");
  const [vocabList, setVocabList] = useState<VocabularyItem[]>([]);
  const [qAiAutoLoading, setQAiAutoLoading] = useState<boolean>(false);

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

  // Open AI modal for creating a new topic
  function openAiModalForNewTopic(part?: number) {
    setAiMode("new_topic");
    setAiPart(part || activePart);
    setAiTargetTopicId(null);
    setAiTheme("");
    setAiInstruction("");
    setAiGeneratedResult(null);
    setAiError(null);
    setAiModalOpen(true);
  }

  // Open AI modal targeting an existing topic
  function openAiModalForExistingTopic(topic: SpeakingTopic) {
    setAiMode("existing_topic");
    setAiPart(topic.part);
    setAiTargetTopicId(topic.id);
    setAiTheme(topic.title);
    setAiInstruction("");
    setAiGeneratedResult(null);
    setAiError(null);
    setAiModalOpen(true);
  }

  // Trigger AI Generator
  async function handleAiGenerate() {
    if (!aiTheme.trim()) {
      setAiError("Iltimos, mavzu nomini yoki kalit so'zni kiriting.");
      return;
    }
    setAiLoading(true);
    setAiError(null);
    try {
      const res = await apiFetch("/staff/speaking/ai-generate", {
        method: "POST",
        body: {
          theme: aiTheme.trim(),
          part: aiPart,
          question_count: aiCount,
          custom_instruction: aiInstruction.trim() || undefined,
        },
        timeoutMs: 90000,
      });

      if (res && (res.questions || res.question_text)) {
        // If single question returned format to list
        if (!res.questions && res.question_text) {
          setAiGeneratedResult({
            topic_title: aiTheme.trim(),
            status_badge: "PREDICTED",
            questions: [res],
          });
        } else {
          setAiGeneratedResult(res);
        }
      } else {
        throw new Error("AI javob formati kutilganidek emas.");
      }
    } catch (e: any) {
      setAiError("Diamondvoy AI generatsiyasida xatolik: " + (e?.message || String(e)));
    } finally {
      setAiLoading(false);
    }
  }

  // Auto-fill a question form using AI
  async function handleAutoFillQuestionWithAi() {
    if (!qText.trim()) {
      alert("Avval savol matnini kiriting, shunda AI namunaviy javob va lug'atlarni tayyorlab beradi.");
      return;
    }
    setQAiAutoLoading(true);
    try {
      const res = await apiFetch("/staff/speaking/ai-generate", {
        method: "POST",
        body: {
          question_text: qText.trim(),
          part: activePart,
        },
        timeoutMs: 90000,
      });

      if (res) {
        if (res.sample_answer) setQAnswer(res.sample_answer);
        if (res.cue_card_bullet_points && Array.isArray(res.cue_card_bullet_points)) {
          setQBullets(res.cue_card_bullet_points.join("\n"));
        }
        if (res.vocabulary && Array.isArray(res.vocabulary)) {
          setVocabList(res.vocabulary);
        }
      }
    } catch (e: any) {
      alert("AI bilan to'ldirishda xatolik: " + (e?.message || String(e)));
    } finally {
      setQAiAutoLoading(false);
    }
  }

  // Save AI Generated Topic & Questions to Database
  async function handleSaveAiResult() {
    if (!aiGeneratedResult) return;
    setAiLoading(true);
    setAiError(null);
    try {
      let finalTopicId = aiTargetTopicId;

      if (aiMode === "new_topic" || !finalTopicId) {
        // 1. Create Topic
        const topicRes = await apiFetch("/staff/speaking/topics", {
          method: "POST",
          body: {
            part: aiPart,
            title: aiGeneratedResult.topic_title || aiTheme.trim(),
            status_badge: aiGeneratedResult.status_badge || "PREDICTED",
            sort_order: 0,
          },
        });

        const createdTopic = topicRes?.topic;
        if (!createdTopic || !createdTopic.id) {
          throw new Error("Mavzu yaratilmadi.");
        }
        finalTopicId = createdTopic.id;
      }

      // 2. Add Questions
      const questionsToSave = aiGeneratedResult.questions || [];
      for (const q of questionsToSave) {
        await apiFetch(`/staff/speaking/topics/${finalTopicId}/questions`, {
          method: "POST",
          body: {
            part: aiPart,
            question_text: q.question_text || "",
            cue_card_bullet_points: q.cue_card_bullet_points || [],
            sample_answer: q.sample_answer || "",
            vocabulary: q.vocabulary || [],
            sort_order: 0,
          },
        });
      }

      alert("✨ Muvaffaqiyatli saqlandi!");
      setAiModalOpen(false);
      setAiGeneratedResult(null);
      setAiTheme("");
      setAiInstruction("");
      if (finalTopicId) setExpandedTopicId(finalTopicId);
      await loadData();
    } catch (e: any) {
      setAiError("Saqlashda xatolik yuz berdi: " + (e?.message || String(e)));
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
      const res = await apiFetch("/staff/speaking/topics", {
        method: "POST",
        body: {
          part: newTopicPart,
          title: newTopicTitle.trim(),
          status_badge: newTopicBadge.trim() || "PREDICTED",
        },
      });
      setNewTopicModalOpen(false);
      setNewTopicTitle("");
      if (res?.topic?.id) setExpandedTopicId(res.topic.id);
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

  // Open Question Modal
  function openAddQuestionModal(topicId: number) {
    setTargetTopicId(topicId);
    setEditingQuestionId(null);
    setQText("");
    setQAnswer("");
    setQBullets("");
    setVocabList([]);
    setNewQuestionModalOpen(true);
  }

  function openEditQuestionModal(q: SpeakingQuestion) {
    setTargetTopicId(q.topic_id);
    setEditingQuestionId(q.id);
    setQText(q.question_text || "");
    setQAnswer(q.sample_answer || "");
    setQBullets((q.cue_card_bullet_points || []).join("\n"));
    setVocabList(q.vocabulary || []);
    setNewQuestionModalOpen(true);
  }

  // Manual Add or Edit Question
  async function handleSaveQuestion() {
    if (!targetTopicId || !qText.trim() || !qAnswer.trim()) {
      alert("Savol matni va namunaviy javobni kiriting.");
      return;
    }
    try {
      const bullets = qBullets
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);

      if (editingQuestionId) {
        await apiFetch(`/staff/speaking/questions/${editingQuestionId}`, {
          method: "PATCH",
          body: {
            question_text: qText.trim(),
            cue_card_bullet_points: bullets,
            sample_answer: qAnswer.trim(),
            vocabulary: vocabList,
          },
        });
      } else {
        await apiFetch(`/staff/speaking/topics/${targetTopicId}/questions`, {
          method: "POST",
          body: {
            part: activePart,
            question_text: qText.trim(),
            cue_card_bullet_points: bullets,
            sample_answer: qAnswer.trim(),
            vocabulary: vocabList,
          },
        });
      }

      setNewQuestionModalOpen(false);
      setEditingQuestionId(null);
      setQText("");
      setQAnswer("");
      setQBullets("");
      setVocabList([]);
      await loadData();
    } catch (e: any) {
      alert("Savolni saqlashda xatolik: " + (e?.message || String(e)));
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

  function removeVocabItem(index: number) {
    setVocabList(vocabList.filter((_, i) => i !== index));
  }

  return (
    <div className="w-full max-w-7xl mx-auto px-3 sm:px-6 py-6 flex flex-col gap-6 pb-24 animate-fade-in">
      {/* ─── HEADER BAR ─── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-5 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md p-6 rounded-3xl border border-slate-200/80 dark:border-slate-800 shadow-sm dark:shadow-xl transition-colors">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-3 py-0.5 text-xs font-black uppercase tracking-wider rounded-full bg-cyan-500/15 text-cyan-600 dark:text-cyan-400 border border-cyan-500/30">
              Diamond IELTS Speaking
            </span>
            <span className="text-xs text-slate-500 dark:text-slate-400">· Admin Content Manager</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
            Speaking Mavzular & Savollar Boshqaruvi
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1 max-w-3xl">
            IELTS Speaking ilovasi uchun Part 1, Part 2 va Part 3 mavzularini boshqarish, savollar, cue cardlar va Band 8.5–9.0 namuna javoblarini qo‘shish hamda Diamondvoy AI yordamida tezkor generatsiya qilish.
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <button
            type="button"
            onClick={() => openAiModalForNewTopic()}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold text-sm shadow-lg shadow-cyan-500/25 active:scale-95 transition-all"
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
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-white border border-slate-300 dark:border-slate-700 font-bold text-sm shadow-sm active:scale-95 transition-all"
          >
            <span>➕</span>
            <span>Yangi mavzu</span>
          </button>

          <button
            type="button"
            onClick={loadData}
            title="Ma'lumotlarni yangilash"
            className="p-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 border border-slate-300 dark:border-slate-700 active:scale-95 transition-all"
          >
            🔄
          </button>
        </div>
      </div>

      {/* ─── PART SEGMENTED SELECTOR ─── */}
      <div className="flex items-center gap-2 p-1.5 bg-slate-100 dark:bg-slate-950 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-inner max-w-lg transition-colors">
        {[
          { part: 1, label: "Part 1", desc: "Introduction & Interview" },
          { part: 2, label: "Part 2", desc: "Cue Cards / Long Turn" },
          { part: 3, label: "Part 3", desc: "Two-way Discussion" },
        ].map((item) => (
          <button
            key={item.part}
            type="button"
            onClick={() => setActivePart(item.part)}
            className={`flex-1 py-2.5 px-3 rounded-xl font-bold text-xs md:text-sm transition-all flex flex-col items-center ${
              activePart === item.part
                ? "bg-gradient-to-r from-blue-600 to-cyan-600 text-white shadow-md shadow-blue-600/30"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200/60 dark:hover:bg-slate-900"
            }`}
          >
            <span>{item.label}</span>
            <span className="text-[10px] opacity-80 font-normal hidden sm:inline">{item.desc}</span>
          </button>
        ))}
      </div>

      {/* ─── TOPICS LIST / CATALOG ─── */}
      {loading ? (
        <div className="p-16 text-center text-slate-500 dark:text-slate-400 bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="w-9 h-9 border-3 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm font-semibold">Mavzular va savollar yuklanmoqda...</p>
        </div>
      ) : filteredTopics.length === 0 ? (
        <div className="p-16 text-center bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-cyan-500/10 text-cyan-500 flex items-center justify-center text-3xl mx-auto">
            🗣️
          </div>
          <div>
            <p className="text-lg font-bold text-slate-900 dark:text-white mb-1">
              Part {activePart} bo'yicha mavzular mavjud emas
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400 max-w-md mx-auto">
              Diamondvoy AI orqali bir tugma bilan yangi IELTS Speaking mavzulari va Band 8.5–9.0 savollarini yarating.
            </p>
          </div>
          <button
            type="button"
            onClick={() => openAiModalForNewTopic()}
            className="px-5 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-sm shadow-lg shadow-cyan-600/25 transition-all inline-flex items-center gap-2"
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
                className="bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 hover:border-cyan-500/50 dark:hover:border-cyan-500/40 rounded-2xl shadow-sm dark:shadow-lg transition-all overflow-hidden"
              >
                {/* Topic Header Row */}
                <div
                  className="p-4 md:p-5 flex items-center justify-between gap-4 cursor-pointer select-none"
                  onClick={() => setExpandedTopicId(isExpanded ? null : topic.id)}
                >
                  <div className="flex items-center gap-3.5 min-w-0">
                    <span className="w-9 h-9 rounded-xl bg-blue-500/10 text-blue-600 dark:text-cyan-400 border border-blue-500/25 font-black text-xs flex items-center justify-center shrink-0">
                      #{String(index + 1).padStart(2, "0")}
                    </span>

                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="text-base md:text-lg font-bold text-slate-900 dark:text-white truncate">
                          {topic.title}
                        </h3>
                        <span className="px-2.5 py-0.5 text-[10px] font-black uppercase tracking-wider rounded-md bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30">
                          {topic.status_badge || "PREDICTED"}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                        {topicQuestions.length} ta savol va Band 9 namuna javoblar
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        openAiModalForExistingTopic(topic);
                      }}
                      className="px-3 py-1.5 rounded-lg bg-cyan-50 dark:bg-cyan-950/40 hover:bg-cyan-100 dark:hover:bg-cyan-900/50 text-xs font-bold text-cyan-700 dark:text-cyan-300 border border-cyan-200 dark:border-cyan-800/60 transition-all flex items-center gap-1 shadow-sm"
                      title="Ushbu mavzuga AI orqali yangi savollar qo'shish"
                    >
                      <span>✨</span>
                      <span className="hidden sm:inline">AI Savol</span>
                    </button>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        openAddQuestionModal(topic.id);
                      }}
                      className="px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-xs font-bold text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-700 transition-all flex items-center gap-1"
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
                      className="p-1.5 rounded-lg text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/40 border border-transparent hover:border-rose-300 dark:hover:border-rose-800/50 transition-all"
                      title="Mavzuni o'chirish"
                    >
                      🗑️
                    </button>

                    <span className="text-slate-400 dark:text-slate-500 ml-1 transform transition-transform duration-200 text-xs">
                      {isExpanded ? "▲" : "▼"}
                    </span>
                  </div>
                </div>

                {/* Expanded Questions Area */}
                {isExpanded && (
                  <div className="p-4 md:p-6 bg-slate-50/70 dark:bg-slate-950/60 border-t border-slate-200/90 dark:border-slate-800/80 space-y-4">
                    {topicQuestions.length === 0 ? (
                      <div className="text-center py-8 text-slate-500 dark:text-slate-400 text-xs">
                        Bu mavzuda hozircha savollar yo'q. Yuqoridagi "AI Savol" yoki "Savol qo'shish" tugmasini bosing.
                      </div>
                    ) : (
                      topicQuestions.map((q, qIndex) => (
                        <div
                          key={q.id}
                          className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-4 md:p-5 space-y-3.5 shadow-sm relative group"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex items-start gap-2.5">
                              <span className="w-6 h-6 rounded-lg bg-cyan-500/15 text-cyan-700 dark:text-cyan-300 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                                #{qIndex + 1}
                              </span>
                              <h4 className="text-sm md:text-base font-bold text-slate-900 dark:text-white leading-snug">
                                {q.question_text}
                              </h4>
                            </div>

                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => openEditQuestionModal(q)}
                                className="text-xs px-2.5 py-1 rounded-md text-blue-600 dark:text-cyan-300 hover:bg-blue-50 dark:hover:bg-slate-800 transition-colors font-medium"
                              >
                                Tahrirlash
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDeleteQuestion(q.id)}
                                className="text-xs px-2.5 py-1 rounded-md text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors font-medium"
                              >
                                O'chirish
                              </button>
                            </div>
                          </div>

                          {/* Cue Card Bullet Points (Part 2) */}
                          {topic.part === 2 && q.cue_card_bullet_points && q.cue_card_bullet_points.length > 0 && (
                            <div className="bg-slate-50 dark:bg-slate-950/70 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 text-xs text-slate-700 dark:text-slate-300 space-y-1.5">
                              <span className="font-bold text-cyan-600 dark:text-cyan-400 uppercase text-[10px] tracking-wider block">
                                You should say:
                              </span>
                              {q.cue_card_bullet_points.map((pt, i) => (
                                <div key={i} className="flex items-center gap-2">
                                  <span className="text-cyan-500 font-bold">•</span>
                                  <span>{pt}</span>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Band 8-9 Model Answer */}
                          <div className="bg-blue-50/60 dark:bg-blue-950/20 border border-blue-200/80 dark:border-blue-900/40 p-4 rounded-xl text-xs space-y-1.5">
                            <span className="font-bold text-blue-600 dark:text-blue-400 uppercase text-[10px] tracking-wider block">
                              Band 8.5–9.0 Model Answer:
                            </span>
                            <p className="text-slate-800 dark:text-slate-200 leading-relaxed italic">
                              {q.sample_answer}
                            </p>
                          </div>

                          {/* Vocabulary items */}
                          {q.vocabulary && q.vocabulary.length > 0 && (
                            <div className="space-y-1.5 pt-1">
                              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
                                Band 9 Lexical Resource / Vocabulary:
                              </span>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                {q.vocabulary.map((v, vi) => (
                                  <div
                                    key={vi}
                                    className="bg-slate-50 dark:bg-slate-950 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 text-xs"
                                  >
                                    <span className="font-bold text-cyan-600 dark:text-cyan-300">{v.word}</span>:{" "}
                                    <span className="text-slate-700 dark:text-slate-300">{v.definition}</span>
                                    {v.example && (
                                      <p className="text-[11px] text-slate-500 dark:text-slate-400 italic mt-0.5">
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-950/60 dark:bg-slate-950/80 backdrop-blur-sm animate-fade-in">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl max-w-4xl w-full p-6 md:p-8 space-y-6 shadow-2xl overflow-y-auto max-h-[92vh] text-slate-900 dark:text-white">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-cyan-500/15 text-cyan-500 flex items-center justify-center text-xl">
                  ✨
                </div>
                <div>
                  <h3 className="text-xl font-extrabold text-slate-900 dark:text-white">
                    Diamondvoy AI Speaking Generator
                  </h3>
                  <p className="text-xs text-cyan-600 dark:text-cyan-400">
                    IELTS Examiner darajasidagi savollar, namuna javoblar va Band 9 lug'atlar
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setAiModalOpen(false)}
                className="text-slate-400 hover:text-slate-700 dark:hover:text-white text-2xl"
              >
                ✕
              </button>
            </div>

            {aiError && (
              <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-700 dark:text-rose-300 text-xs flex items-center justify-between">
                <span>⚠️ {aiError}</span>
                <button type="button" onClick={() => setAiError(null)} className="text-rose-500 hover:underline">
                  Yopish
                </button>
              </div>
            )}

            {!aiGeneratedResult ? (
              <div className="space-y-5">
                {/* Mode Selector */}
                <div className="grid grid-cols-2 gap-3 p-1 bg-slate-100 dark:bg-slate-950 rounded-2xl border border-slate-200 dark:border-slate-800">
                  <button
                    type="button"
                    onClick={() => {
                      setAiMode("new_topic");
                      setAiTargetTopicId(null);
                    }}
                    className={`py-2.5 px-3 rounded-xl font-bold text-xs transition-all ${
                      aiMode === "new_topic"
                        ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    ✨ Yangi Mavzu & Savollar Ochish
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setAiMode("existing_topic");
                      if (!aiTargetTopicId && filteredTopics.length > 0) {
                        setAiTargetTopicId(filteredTopics[0].id);
                        setAiTheme(filteredTopics[0].title);
                      }
                    }}
                    className={`py-2.5 px-3 rounded-xl font-bold text-xs transition-all ${
                      aiMode === "existing_topic"
                        ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    📂 Mavjud Mavzuga Savollar Qo'shish
                  </button>
                </div>

                {/* If Existing Topic Mode */}
                {aiMode === "existing_topic" && (
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                      Qaysi mavzuga savol qo'shilsin:
                    </label>
                    <select
                      value={aiTargetTopicId || ""}
                      onChange={(e) => {
                        const tid = Number(e.target.value);
                        setAiTargetTopicId(tid);
                        const sel = topics.find((t) => t.id === tid);
                        if (sel) {
                          setAiTheme(sel.title);
                          setAiPart(sel.part);
                        }
                      }}
                      className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-sm focus:border-cyan-500 outline-none"
                    >
                      {topics.map((t) => (
                        <option key={t.id} value={t.id}>
                          Part {t.part} — {t.title}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                    Mavzu mavzusi yoki kalit so'z (Theme):
                  </label>
                  <input
                    type="text"
                    value={aiTheme}
                    onChange={(e) => setAiTheme(e.target.value)}
                    placeholder="Masalan: Artificial Intelligence, Traditional Festivals, Sustainable Energy, Daily Routines"
                    className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 text-sm focus:border-cyan-500 outline-none"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                      IELTS Bo'limi (Part):
                    </label>
                    <select
                      value={aiPart}
                      disabled={aiMode === "existing_topic"}
                      onChange={(e) => setAiPart(Number(e.target.value))}
                      className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-sm focus:border-cyan-500 outline-none disabled:opacity-60"
                    >
                      <option value={1}>Part 1 (Introduction & Interview)</option>
                      <option value={2}>Part 2 (Cue Card / Long Turn)</option>
                      <option value={3}>Part 3 (Two-way Discussion)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                      Savollar soni:
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={5}
                      value={aiCount}
                      onChange={(e) => setAiCount(Number(e.target.value))}
                      className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-sm focus:border-cyan-500 outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                    Maxsus ko'rsatma (Ixtiyoriy):
                  </label>
                  <input
                    type="text"
                    value={aiInstruction}
                    onChange={(e) => setAiInstruction(e.target.value)}
                    placeholder="Masalan: C1/C2 academic collocations, idiomatic expressions"
                    className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 text-sm focus:border-cyan-500 outline-none"
                  />
                </div>

                <div className="pt-2">
                  <button
                    type="button"
                    onClick={handleAiGenerate}
                    disabled={aiLoading}
                    className="w-full py-4 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold text-sm shadow-xl shadow-cyan-500/25 active:scale-[0.98] transition-all flex items-center justify-center gap-2"
                  >
                    {aiLoading ? (
                      <>
                        <span className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        <span>Diamondvoy AI savollarni yaratmoqda... (10–25s)</span>
                      </>
                    ) : (
                      <>
                        <span className="text-base">✨</span>
                        <span>Mavzu va Savollarni Generatsiya Qilish</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            ) : (
              /* Preview of Generated Content */
              <div className="space-y-5">
                <div className="p-5 bg-slate-50 dark:bg-slate-950 rounded-2xl border border-cyan-500/30 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
                        {aiMode === "new_topic" ? "Yangi Mavzu Nomi:" : "Tanlangan Mavzu:"}
                      </span>
                      <h4 className="text-lg font-bold text-slate-900 dark:text-white">
                        {aiGeneratedResult.topic_title || aiTheme}
                      </h4>
                    </div>
                    <span className="px-3 py-1 text-xs font-black uppercase rounded-lg bg-cyan-500/20 text-cyan-600 dark:text-cyan-300 border border-cyan-500/30">
                      {aiGeneratedResult.status_badge || "PREDICTED"}
                    </span>
                  </div>

                  <div className="space-y-4 pt-1">
                    {(aiGeneratedResult.questions || []).map((q: any, i: number) => (
                      <div
                        key={i}
                        className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 text-xs space-y-2.5 shadow-sm"
                      >
                        <p className="font-bold text-slate-900 dark:text-white text-sm">
                          #{i + 1} {q.question_text}
                        </p>

                        {aiPart === 2 && q.cue_card_bullet_points && q.cue_card_bullet_points.length > 0 && (
                          <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-300 space-y-1">
                            <span className="font-bold text-cyan-600 dark:text-cyan-400 block text-[10px] uppercase">
                              You should say:
                            </span>
                            {q.cue_card_bullet_points.map((pt: string, pi: number) => (
                              <div key={pi}>• {pt}</div>
                            ))}
                          </div>
                        )}

                        <div className="p-3 bg-blue-50/60 dark:bg-blue-950/20 border border-blue-200/80 dark:border-blue-900/30 rounded-lg text-slate-800 dark:text-slate-200 italic leading-relaxed">
                          <strong>Band 8.5–9.0 Namuna:</strong> {q.sample_answer}
                        </div>

                        {q.vocabulary && q.vocabulary.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 pt-1">
                            {q.vocabulary.map((v: any, vi: number) => (
                              <span
                                key={vi}
                                className="px-2 py-0.5 bg-slate-100 dark:bg-slate-950 text-cyan-700 dark:text-cyan-300 rounded border border-slate-200 dark:border-slate-800 text-[11px]"
                              >
                                <strong>{v.word}</strong>: {v.definition}
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
                    className="flex-1 py-3.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-sm shadow-lg shadow-emerald-600/30 active:scale-95 transition-all flex items-center justify-center gap-2"
                  >
                    {aiLoading ? "Bazaga saqlanmoqda..." : "✅ Tasdiqlash va Bazaga Saqlash"}
                  </button>

                  <button
                    type="button"
                    onClick={() => setAiGeneratedResult(null)}
                    disabled={aiLoading}
                    className="px-5 py-3.5 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-bold text-sm border border-slate-300 dark:border-slate-700 transition-all"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-950/60 dark:bg-slate-950/80 backdrop-blur-sm animate-fade-in">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl max-w-lg w-full p-6 md:p-8 space-y-5 shadow-2xl text-slate-900 dark:text-white">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                Part {newTopicPart} — Yangi Mavzu Qo'shish
              </h3>
              <button
                type="button"
                onClick={() => setNewTopicModalOpen(false)}
                className="text-slate-400 hover:text-slate-700 dark:hover:text-white text-xl"
              >
                ✕
              </button>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                Mavzu Nomi (Topic Title):
              </label>
              <input
                type="text"
                value={newTopicTitle}
                onChange={(e) => setNewTopicTitle(e.target.value)}
                placeholder="Masalan: Weather and Climate, Traditional Festivals"
                className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-sm outline-none focus:border-cyan-500"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                Status Badge:
              </label>
              <select
                value={newTopicBadge}
                onChange={(e) => setNewTopicBadge(e.target.value)}
                className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-sm outline-none focus:border-cyan-500"
              >
                <option value="PREDICTED">PREDICTED</option>
                <option value="HIGH FREQUENCY">HIGH FREQUENCY</option>
                <option value="COMMON">COMMON</option>
              </select>
            </div>

            <div className="flex justify-end gap-3 pt-3">
              <button
                type="button"
                onClick={() => setNewTopicModalOpen(false)}
                className="px-4 py-2.5 rounded-xl text-slate-500 hover:text-slate-800 dark:hover:text-white text-sm"
              >
                Bekor qilish
              </button>
              <button
                type="button"
                onClick={handleAddTopic}
                className="px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-sm shadow-md shadow-blue-600/25 active:scale-95 transition-all"
              >
                Mavzuni yaratish
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL: MANUAL ADD / EDIT QUESTION ─── */}
      {newQuestionModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-950/60 dark:bg-slate-950/80 backdrop-blur-sm animate-fade-in">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl max-w-3xl w-full p-6 md:p-8 space-y-5 shadow-2xl max-h-[92vh] overflow-y-auto text-slate-900 dark:text-white">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                {editingQuestionId ? "Savolni Tahrirlash" : "Mavzuga Yangi Savol Qo'shish"}
              </h3>
              <button
                type="button"
                onClick={() => setNewQuestionModalOpen(false)}
                className="text-slate-400 hover:text-slate-700 dark:hover:text-white text-xl"
              >
                ✕
              </button>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                  Savol matni (Prompt):
                </label>
                <button
                  type="button"
                  onClick={handleAutoFillQuestionWithAi}
                  disabled={qAiAutoLoading}
                  className="text-xs font-bold text-cyan-600 dark:text-cyan-400 hover:underline flex items-center gap-1 disabled:opacity-50"
                >
                  {qAiAutoLoading ? "AI to'ldirmoqda..." : "✨ AI orqali namunaviy javob va lug'atni to'ldirish"}
                </button>
              </div>
              <input
                type="text"
                value={qText}
                onChange={(e) => setQText(e.target.value)}
                placeholder="Savol matnini kiriting"
                className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-sm outline-none focus:border-cyan-500"
              />
            </div>

            {activePart === 2 && (
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                  Cue Card Bullet Points (har biri yangi qatorda):
                </label>
                <textarea
                  rows={3}
                  value={qBullets}
                  onChange={(e) => setQBullets(e.target.value)}
                  placeholder="Where you went&#10;Who accompanied you&#10;What happened along the way"
                  className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-sm outline-none focus:border-cyan-500"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                Band 8.5–9.0 Namunaviy Javob (Model Answer):
              </label>
              <textarea
                rows={4}
                value={qAnswer}
                onChange={(e) => setQAnswer(e.target.value)}
                placeholder="Model answer with rich lexical resource and natural discourse markers..."
                className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-sm outline-none focus:border-cyan-500"
              />
            </div>

            {/* Vocab sub-form */}
            <div className="p-4 bg-slate-50 dark:bg-slate-950 rounded-2xl border border-slate-200 dark:border-slate-800 space-y-3">
              <span className="text-xs font-bold text-cyan-600 dark:text-cyan-400 block">
                Band 9 Lug'at / Collocations qo'shish:
              </span>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
                <input
                  type="text"
                  placeholder="So'z / ibora"
                  value={qVocabWord}
                  onChange={(e) => setQVocabWord(e.target.value)}
                  className="px-3 py-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs text-slate-900 dark:text-white outline-none"
                />
                <input
                  type="text"
                  placeholder="Ma'nosi"
                  value={qVocabDef}
                  onChange={(e) => setQVocabDef(e.target.value)}
                  className="px-3 py-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs text-slate-900 dark:text-white outline-none"
                />
                <input
                  type="text"
                  placeholder="Misol jumla (ixtiyoriy)"
                  value={qVocabEx}
                  onChange={(e) => setQVocabEx(e.target.value)}
                  className="px-3 py-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs text-slate-900 dark:text-white outline-none"
                />
              </div>
              <button
                type="button"
                onClick={addVocabItem}
                className="px-3 py-1.5 bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-cyan-700 dark:text-cyan-300 rounded-xl text-xs font-bold"
              >
                + Lug'at qo'shish
              </button>

              {vocabList.length > 0 && (
                <div className="flex flex-wrap gap-2 pt-2">
                  {vocabList.map((v, i) => (
                    <span
                      key={i}
                      className="px-2.5 py-1 bg-white dark:bg-slate-900 text-cyan-700 dark:text-cyan-300 border border-slate-200 dark:border-slate-800 rounded-lg text-xs flex items-center gap-1.5"
                    >
                      <strong>{v.word}</strong>: {v.definition}
                      <button
                        type="button"
                        onClick={() => removeVocabItem(i)}
                        className="text-slate-400 hover:text-rose-500 ml-1"
                      >
                        ✕
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-3 pt-3">
              <button
                type="button"
                onClick={() => setNewQuestionModalOpen(false)}
                className="px-4 py-2.5 rounded-xl text-slate-500 hover:text-slate-800 dark:hover:text-white text-sm"
              >
                Bekor qilish
              </button>
              <button
                type="button"
                onClick={handleSaveQuestion}
                className="px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-sm shadow-md shadow-blue-600/25 active:scale-95 transition-all"
              >
                {editingQuestionId ? "O'zgarishlarni saqlash" : "Savolni saqlash"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
