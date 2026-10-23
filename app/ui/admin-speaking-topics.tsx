"use client";

import React, { useState, useEffect } from "react";
import { ModalPortal } from "./modal-portal";

type VocabularyItem = {
  word: string;
  definition: string;
  example: string;
};

type SpeakingQuestion = {
  id: number;
  topic_id: number;
  part: number;
  subject?: string;
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
  subject?: string;
  title: string;
  status_badge: string;
  sort_order: number;
  created_at: string;
  question_count: number;
};

const TOPIC_STATUS_OPTIONS = ["COMMON", "PREDICTED", "HIGH FREQUENCY"] as const;

function normalizedTopicStatus(value?: string) {
  const status = (value || "").trim().toUpperCase();
  return TOPIC_STATUS_OPTIONS.includes(status as (typeof TOPIC_STATUS_OPTIONS)[number])
    ? status
    : "PREDICTED";
}

interface AdminSpeakingTopicsProps {
  apiFetch: (path: string, options?: { method?: string; body?: any; timeoutMs?: number; signal?: AbortSignal }) => Promise<any>;
}

export function AdminSpeakingTopics({ apiFetch }: AdminSpeakingTopicsProps) {
  const [activeSubject, setActiveSubject] = useState<"english" | "russian">("english");
  const [activePart, setActivePart] = useState<number>(1);
  const [topics, setTopics] = useState<SpeakingTopic[]>([]);
  const [questions, setQuestions] = useState<SpeakingQuestion[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [expandedTopicId, setExpandedTopicId] = useState<number | null>(null);

  // AI Modal State
  const [aiModalOpen, setAiModalOpen] = useState<boolean>(false);
  const [aiMode, setAiMode] = useState<"new_topic" | "existing_topic" | "batch_topics">("new_topic");
  const [aiTargetTopicId, setAiTargetTopicId] = useState<number | null>(null);
  const [aiTheme, setAiTheme] = useState<string>("");
  const [aiPart, setAiPart] = useState<number>(1);
  const [aiCount, setAiCount] = useState<number | "">("");
  const [aiTopicCount, setAiTopicCount] = useState<number | "">("");
  const [aiInstruction, setAiInstruction] = useState<string>("");
  const [aiLoading, setAiLoading] = useState<boolean>(false);
  const [aiProgress, setAiProgress] = useState<number>(0);
  const [aiProgressStage, setAiProgressStage] = useState<string>("");
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiGeneratedResult, setAiGeneratedResult] = useState<any | null>(null);
  const [catalogLoading, setCatalogLoading] = useState<boolean>(false);
  const [catalogProgress, setCatalogProgress] = useState<number>(0);
  const [catalogStage, setCatalogStage] = useState<string>("");
  const [catalogPart, setCatalogPart] = useState<number | null>(null);
  const [catalogBuilderOpen, setCatalogBuilderOpen] = useState<boolean>(false);
  const [customCatalogTopics, setCustomCatalogTopics] = useState<string>("");
  const [customCatalogPart, setCustomCatalogPart] = useState<number>(1);
  const [customQuestionTargetMode, setCustomQuestionTargetMode] = useState<"exact" | "range">("exact");
  const [customExactQuestionCount, setCustomExactQuestionCount] = useState<number>(15);
  const [customMinimumQuestionCount, setCustomMinimumQuestionCount] = useState<number>(4);
  const [customMaximumQuestionCount, setCustomMaximumQuestionCount] = useState<number>(10);
  const [customExistingOnly, setCustomExistingOnly] = useState<boolean>(false);
  const [customExistingQuestionCount, setCustomExistingQuestionCount] = useState<number>(0);

  // Manual Add Topic Modal
  const [newTopicModalOpen, setNewTopicModalOpen] = useState<boolean>(false);
  const [newTopicTitle, setNewTopicTitle] = useState<string>("");
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

  // Push Notification Modal State
  const [notifModalOpen, setNotifModalOpen] = useState<boolean>(false);
  const [notifTitle, setNotifTitle] = useState<string>("");
  const [notifBody, setNotifBody] = useState<string>("");
  const [notifPart, setNotifPart] = useState<number | null>(null);
  const [notifLoading, setNotifLoading] = useState<boolean>(false);

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

  async function handleSendNotif() {
    if (!notifTitle.trim() || !notifBody.trim()) {
      alert("Iltimos, bildirishnoma sarlavhasi va matnini to'liq kiriting.");
      return;
    }
    setNotifLoading(true);
    try {
      const res = await apiFetch("/staff/speaking/notifications/send", {
        method: "POST",
        body: {
          title: notifTitle.trim(),
          body: notifBody.trim(),
          target_part: notifPart || undefined,
        },
      });
      if (res && res.success) {
        alert("✅ Bildirishnoma Speaking app foydalanuvchilariga muvaffaqiyatli yuborildi!");
        setNotifModalOpen(false);
        setNotifTitle("");
        setNotifBody("");
        setNotifPart(null);
      }
    } catch (e: any) {
      alert("Bildirishnoma yuborishda xatolik: " + (e?.message || String(e)));
    } finally {
      setNotifLoading(false);
    }
  }

  const filteredTopics = topics.filter((t) => {
    const s = t.subject || "english";
    if (activeSubject === "russian") {
      return s === "russian";
    }
    return s === "english" && t.part === activePart;
  });
  const displayedCatalogPart = catalogPart || activePart;

  // Open AI modal for creating a new topic
  function openAiModalForNewTopic(part?: number) {
    setAiMode("new_topic");
    setAiPart(activeSubject === "russian" ? 1 : (part || activePart));
    setAiTargetTopicId(null);
    setAiCount("");
    setAiTopicCount("");
    setAiTheme("");
    setAiInstruction("");
    setAiGeneratedResult(null);
    setAiError(null);
    setAiModalOpen(true);
  }

  // Open AI modal targeting an existing topic
  function openAiModalForExistingTopic(topic: SpeakingTopic) {
    setAiMode("existing_topic");
    setAiPart(topic.part || 1);
    setAiTargetTopicId(topic.id);
    setAiTheme(topic.title);
    setAiCount("");
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
    const questionCount = Number(aiCount);
    if (!Number.isInteger(questionCount) || questionCount < 1 || questionCount > 10) {
      setAiError("Savollar sonini 1 dan 10 gacha kiriting (maksimum 10 ta).");
      return;
    }
    const topicCount = aiMode === "batch_topics" ? Number(aiTopicCount) : 1;
    if (aiMode === "batch_topics" && (!Number.isInteger(topicCount) || topicCount < 2 || topicCount > 5)) {
      setAiError("Mavzular sonini 2 dan 5 gacha kiriting (maksimum 5 ta).");
      return;
    }
    setAiLoading(true);
    setAiProgress(0);
    setAiProgressStage("AI generatsiyasi navbatga qo'yilmoqda...");
    setAiError(null);
    try {
      // Generation is a pollable backend job: the browser never has to keep
      // one long request open, and the percentage is based on completed work.
      const started = await apiFetch("/staff/speaking/ai-generate/jobs", {
        method: "POST",
        body: {
          theme: aiTheme.trim(),
          part: activeSubject === "russian" ? 1 : aiPart,
          subject: activeSubject,
          question_count: questionCount,
          topic_count: topicCount,
          existing_topic_id: aiMode === "existing_topic" ? aiTargetTopicId || undefined : undefined,
          custom_instruction: aiInstruction.trim() || undefined,
        },
        timeoutMs: 30000,
      });
      const jobId = Number(started?.job?.id);
      if (!Number.isInteger(jobId) || jobId < 1) {
        throw new Error("AI generatsiya vazifasi yaratilmadi.");
      }

      let res: any = null;
      // The backend may retry a slow provider and repair a truncated response.
      // This scales with requested work instead of cutting off a valid 5 × 10
      // batch at a fixed browser timeout.
      const deadline = Date.now() + Math.max(30 * 60_000, topicCount * questionCount * 5 * 60_000);
      while (Date.now() < deadline) {
        await new Promise((resolve) => window.setTimeout(resolve, 900));
        let statusResponse: any;
        try {
          statusResponse = await apiFetch(`/staff/speaking/ai-generate/jobs/${jobId}`, {
            method: "GET",
            timeoutMs: 30000,
          });
        } catch {
          // A transient network hiccup must not discard a server-side job.
          setAiProgressStage("Server bilan aloqa qayta tiklanmoqda...");
          continue;
        }
        const job = statusResponse?.job;
        const progress = Number(job?.progress_percent);
        setAiProgress(Number.isFinite(progress) ? Math.max(0, Math.min(100, progress)) : 0);
        setAiProgressStage(String(job?.stage || "AI savollarni yaratmoqda..."));

        if (job?.status === "completed") {
          res = job?.result_json;
          break;
        }
        if (job?.status === "failed") {
          throw new Error(String(job?.error_message || "AI generatsiyasi yakunlanmadi."));
        }
      }
      if (!res) {
        throw new Error("AI generatsiyasi kutish vaqtidan oshdi. Jarayon serverda davom etayotgan bo'lishi mumkin; qayta urinib ko'ring.");
      }

      if (res && (res.topics || res.questions || res.question_text)) {
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

  async function waitForCatalogCompletion(jobId: number, subjectLabel: string, targetTopics: number) {
    const deadline = Date.now() + 5 * 60 * 60_000;
    let completedJob: any = null;
    while (Date.now() < deadline) {
      await new Promise((resolve) => window.setTimeout(resolve, 1500));
      let statusResponse: any;
      try {
        statusResponse = await apiFetch(`/staff/speaking/ai-generate/jobs/${jobId}`, {
          method: "GET",
          timeoutMs: 30000,
        });
      } catch {
        setCatalogStage("Server bilan aloqa qayta tiklanmoqda...");
        continue;
      }
      const job = statusResponse?.job;
      const progress = Number(job?.progress_percent);
      setCatalogProgress(Number.isFinite(progress) ? Math.max(0, Math.min(100, progress)) : 0);
      setCatalogStage(String(job?.stage || `${subjectLabel} savollari tayyorlanmoqda...`));
      if (job?.status === "completed") {
        completedJob = job;
        break;
      }
      if (job?.status === "failed") {
        throw new Error(String(job?.error_message || `${subjectLabel} katalogi yakunlanmadi.`));
      }
    }
    if (!completedJob) {
      throw new Error("Katalog generatsiyasi hali davom etmoqda. Sahifani keyinroq yangilang — tayyor qismi saqlanib qoladi.");
    }
    const result = completedJob.result_json || {};
    const incomplete = Array.isArray(result.incomplete_topics) ? result.incomplete_topics.length : 0;
    const actualTargetTopics = Number(result.target_topics) || targetTopics;
    await loadData();
    alert(
      incomplete === 0
        ? `✅ ${subjectLabel} katalogi tayyor: ${result.topics_ready || actualTargetTopics} ta mavzu to'ldirildi.`
        : `⚠️ Katalog qisman tayyor: ${result.topics_ready || 0}/${actualTargetTopics} mavzu belgilangan savol soniga yetdi. Qayta bosilsa faqat yetishmayotgan savollar to'ldiriladi.`
    );
  }

  function openCatalogBuilder() {
    setCustomCatalogPart(activeSubject === "russian" ? 1 : activePart);
    setCustomExistingOnly(false);
    setCatalogBuilderOpen(true);
  }

  async function handleCatalogFill(subject: "english" | "russian", part?: number) {
    const isEnglishPart = subject === "english";
    const selectedPart = isEnglishPart ? part || activePart : null;
    const subjectLabel = isEnglishPart ? `English IELTS Part ${selectedPart}` : "Rus tili";
    const topicTarget = isEnglishPart ? 10 : 30;
    const accepted = window.confirm(
      `${subjectLabel} katalogi uchun ${topicTarget} ta mavzu yaratiladi yoki mavjud mos mavzular to'ldiriladi. ` +
      "Har birida 15 tagacha savol bo'ladi. Jarayon fon rejimida ishlaydi va bir necha vaqt olishi mumkin. Boshlaymizmi?"
    );
    if (!accepted) return;

    setCatalogLoading(true);
    setCatalogPart(selectedPart);
    setCatalogProgress(0);
    setCatalogStage("Vazifa navbatga qo'yilmoqda...");
    try {
      const path = isEnglishPart
        ? `/staff/speaking/english-catalog/jobs?part=${selectedPart}`
        : "/staff/speaking/russian-catalog/jobs";
      const started = await apiFetch(path, {
        method: "POST",
        timeoutMs: 30000,
      });
      const jobId = Number(started?.job?.id);
      if (!Number.isInteger(jobId) || jobId < 1) {
        throw new Error(`${subjectLabel} katalogi uchun vazifa yaratilmagan.`);
      }

      await waitForCatalogCompletion(jobId, subjectLabel, topicTarget);
    } catch (e: any) {
      alert(`${subjectLabel} katalogini to'ldirishda xatolik: ` + (e?.message || String(e)));
    } finally {
      setCatalogLoading(false);
      setCatalogPart(null);
    }
  }

  async function handleCustomCatalogFill() {
    const selectedPart = activeSubject === "russian" ? 1 : customCatalogPart;
    const topicTitles = customCatalogTopics
      .split(/\r?\n/)
      .map((title) => title.trim())
      .filter(Boolean);
    if (!customExistingOnly && topicTitles.length === 0) {
      alert("Kamida bitta topic kiriting. Har topicni yangi qatordan yozing.");
      return;
    }
    if (!customExistingOnly && topicTitles.length > 30) {
      alert("Bir jarayonda maksimum 30 ta topic kiritish mumkin.");
      return;
    }
    const minimum = customQuestionTargetMode === "exact"
      ? customExactQuestionCount
      : customMinimumQuestionCount;
    const maximum = customQuestionTargetMode === "exact"
      ? customExactQuestionCount
      : customMaximumQuestionCount;
    if (!Number.isInteger(minimum) || !Number.isInteger(maximum) || minimum < 1 || maximum > 30 || minimum > maximum) {
      alert("Savollar sonini to'g'ri kiriting: 1 dan 30 gacha, minimum maximumdan katta bo'lmasin.");
      return;
    }
    if (customExistingOnly && (!Number.isInteger(customExistingQuestionCount) || customExistingQuestionCount < 0 || customExistingQuestionCount > 30)) {
      alert("Mavjud savollar sonini 0 dan 30 gacha kiriting.");
      return;
    }
    const sourceText = customExistingOnly
      ? `Part ${selectedPart} ichida aynan ${customExistingQuestionCount} ta savolli mavjud topiclar topiladi`
      : `${topicTitles.length} ta kiritilgan topic ishlatiladi`;
    const targetText = minimum === maximum ? `${minimum} ta` : `${minimum}–${maximum} ta`;
    if (!window.confirm(`${sourceText}. Har topic yakunida ${targetText} savol bo'ladi. Boshlaymizmi?`)) return;

    const subjectLabel = activeSubject === "russian" ? "Rus tili" : `English IELTS Part ${selectedPart}`;
    setCatalogLoading(true);
    setCatalogPart(selectedPart);
    setCatalogProgress(0);
    setCatalogStage("Moslashuvchan katalog vazifasi navbatga qo'yilmoqda...");
    try {
      const started = await apiFetch("/staff/speaking/catalog/jobs", {
        method: "POST",
        timeoutMs: 30000,
        body: {
          subject: activeSubject,
          part: selectedPart,
          topics: customExistingOnly ? [] : topicTitles,
          question_target_mode: customQuestionTargetMode,
          exact_question_count: customQuestionTargetMode === "exact" ? customExactQuestionCount : undefined,
          minimum_question_count: customQuestionTargetMode === "range" ? customMinimumQuestionCount : undefined,
          maximum_question_count: customQuestionTargetMode === "range" ? customMaximumQuestionCount : undefined,
          existing_question_count: customExistingOnly ? customExistingQuestionCount : undefined,
        },
      });
      const jobId = Number(started?.job?.id);
      if (!Number.isInteger(jobId) || jobId < 1) {
        throw new Error("Moslashuvchan katalog vazifasi yaratilmadi.");
      }
      setCatalogBuilderOpen(false);
      await waitForCatalogCompletion(jobId, subjectLabel, customExistingOnly ? 30 : topicTitles.length);
    } catch (e: any) {
      alert(`${subjectLabel} katalogini to'ldirishda xatolik: ` + (e?.message || String(e)));
    } finally {
      setCatalogLoading(false);
      setCatalogPart(null);
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
          part: activeSubject === "russian" ? 1 : activePart,
          subject: activeSubject,
        },
        timeoutMs: 90000,
      });

      if (res) {
        const answer =
          res.sample_answer ||
          res.model_answer ||
          res.answer ||
          (res.questions && res.questions[0]?.sample_answer) ||
          "";
        if (answer) setQAnswer(answer);

        const bullets =
          res.cue_card_bullet_points ||
          (res.questions && res.questions[0]?.cue_card_bullet_points) ||
          [];
        if (Array.isArray(bullets) && bullets.length > 0) {
          setQBullets(bullets.join("\n"));
        }

        const vocabs =
          res.vocabulary ||
          res.words ||
          (res.questions && res.questions[0]?.vocabulary) ||
          [];
        if (Array.isArray(vocabs) && vocabs.length > 0) {
          setVocabList(vocabs);
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
      if (aiMode === "batch_topics") {
        const generatedTopics = Array.isArray(aiGeneratedResult.topics) ? aiGeneratedResult.topics : [];
        if (generatedTopics.length === 0) {
          throw new Error("Bir nechta mavzu uchun AI javobi topilmadi.");
        }
        const batchRes = await apiFetch("/staff/speaking/topics/batch", {
          method: "POST",
          body: {
            subject: activeSubject,
            topics: generatedTopics.map((topic: any) => ({
              part: activeSubject === "russian" ? 1 : aiPart,
              title: String(topic.topic_title || topic.title || "Mavzu").trim(),
              status_badge: normalizedTopicStatus(topic.status_badge),
              sort_order: 0,
              questions: (topic.questions || []).map((q: any) => ({
                question_text: String(q.question_text || q.question || q.prompt || "Savol").trim(),
                cue_card_bullet_points: activeSubject === "russian" ? [] : (q.cue_card_bullet_points || []),
                sample_answer: activeSubject === "russian" ? "" : String(q.sample_answer || q.model_answer || q.answer || "").trim(),
                vocabulary: q.vocabulary || [],
                sort_order: 0,
              })),
            })),
          },
        });
        const createdTopics = batchRes?.topics || [];
        if (createdTopics.length === 0) {
          throw new Error("Mavzular bazaga yozilmadi.");
        }
        alert(`✨ ${createdTopics.length} ta mavzu va savollari muvaffaqiyatli saqlandi!`);
        setAiModalOpen(false);
        setAiGeneratedResult(null);
        setAiTheme("");
        setAiInstruction("");
        setExpandedTopicId(createdTopics[0].id);
        await loadData();
        return;
      }

      let finalTopicId = aiTargetTopicId;

      if (aiMode === "new_topic" || !finalTopicId) {
        // 1. Create Topic
        const topicRes = await apiFetch("/staff/speaking/topics", {
          method: "POST",
          body: {
            part: activeSubject === "russian" ? 1 : aiPart,
            subject: activeSubject,
            title: aiGeneratedResult.topic_title || aiTheme.trim(),
            status_badge: normalizedTopicStatus(aiGeneratedResult.status_badge),
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
      const targetTopic = topics.find((t) => t.id === finalTopicId);
      const targetPart = activeSubject === "russian" ? 1 : (targetTopic?.part ?? aiPart);
      const questionsToSave = aiGeneratedResult.questions || [];
      for (const q of questionsToSave) {
        const ans = activeSubject === "russian" ? "" : (q.sample_answer || q.model_answer || q.answer || "Namuna javob").trim();
        const text = (q.question_text || q.question || q.prompt || "Savol").trim();
        await apiFetch(`/staff/speaking/topics/${finalTopicId}/questions`, {
          method: "POST",
          body: {
            part: targetPart,
            subject: activeSubject,
            question_text: text,
            cue_card_bullet_points: activeSubject === "russian" ? [] : (q.cue_card_bullet_points || []),
            ...(ans ? { sample_answer: ans } : {}),
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
          part: activeSubject === "russian" ? 1 : newTopicPart,
          subject: activeSubject,
          title: newTopicTitle.trim(),
          status_badge: "PREDICTED",
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
    if (!targetTopicId || !qText.trim()) {
      alert("Savol matnini kiriting.");
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
            cue_card_bullet_points: activeSubject === "russian" ? [] : bullets,
            ...(qAnswer.trim() ? { sample_answer: qAnswer.trim() } : {}),
            vocabulary: vocabList,
          },
        });
      } else {
        await apiFetch(`/staff/speaking/topics/${targetTopicId}/questions`, {
          method: "POST",
          body: {
            question_text: qText.trim(),
            cue_card_bullet_points: activeSubject === "russian" ? [] : bullets,
            ...(qAnswer.trim() ? { sample_answer: qAnswer.trim() } : {}),
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
            onClick={() => setNotifModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold text-sm shadow-md shadow-indigo-600/25 active:scale-95 transition-all"
          >
            <span>📢</span>
            <span>Bildirishnoma</span>
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

      {/* ─── SUBJECT SELECTOR (ENGLISH vs RUSSIAN) ─── */}
      <div className="flex items-center gap-2 p-1.5 bg-slate-100 dark:bg-slate-950 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-inner max-w-md transition-colors">
        <button
          type="button"
          onClick={() => setActiveSubject("english")}
          className={`flex-1 py-2.5 px-4 rounded-xl font-bold text-xs md:text-sm transition-all flex items-center justify-center gap-2 ${
            activeSubject === "english"
              ? "bg-gradient-to-r from-blue-600 to-cyan-600 text-white shadow-md shadow-blue-600/30"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200/60 dark:hover:bg-slate-900"
          }`}
        >
          <span>🇬🇧</span>
          <span>English (IELTS)</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveSubject("russian")}
          className={`flex-1 py-2.5 px-4 rounded-xl font-bold text-xs md:text-sm transition-all flex items-center justify-center gap-2 ${
            activeSubject === "russian"
              ? "bg-gradient-to-r from-rose-600 to-amber-600 text-white shadow-md shadow-rose-600/30"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200/60 dark:hover:bg-slate-900"
          }`}
        >
          <span>🇷🇺</span>
          <span>Русский язык</span>
        </button>
      </div>

      <section className={`rounded-3xl border p-5 md:p-6 shadow-sm ${
        activeSubject === "russian"
          ? "border-amber-300/70 dark:border-amber-700/60 bg-gradient-to-br from-amber-50 via-white to-orange-50 dark:from-amber-950/30 dark:via-slate-900 dark:to-orange-950/20"
          : "border-blue-300/70 dark:border-blue-700/60 bg-gradient-to-br from-blue-50 via-white to-cyan-50 dark:from-blue-950/30 dark:via-slate-900 dark:to-cyan-950/20"
      }`}>
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className={`flex items-center gap-2 font-extrabold ${activeSubject === "russian" ? "text-amber-800 dark:text-amber-200" : "text-blue-800 dark:text-blue-200"}`}>
                <span className="text-xl">{activeSubject === "russian" ? "🇷🇺" : "🇬🇧"}</span>
                <span>{activeSubject === "russian" ? "Rus tili katalogini avtomatik to‘ldirish" : "English IELTS katalogini avtomatik to‘ldirish"}</span>
              </div>
              <p className="mt-1.5 max-w-2xl text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                {activeSubject === "russian"
                  ? "AI 30 ta suhbat mavzusini yaratadi yoki mavjud mos mavzularni 15 tagacha takrorlanmaydigan savol bilan to‘ldiradi."
                  : `AI faqat hozir tanlangan Part ${displayedCatalogPart} uchun 10 ta mavzuni yaratadi yoki mavjud mos mavzularni to‘ldiradi; savollar, cue cardlar, Band 9 javoblar va vocabulary ham to‘liq yaratiladi.`}
                {" "}Mavjud topic hamda savollar avval tekshiriladi; sahifa yopilsa ham tayyor bo‘lgan material yo‘qolmaydi.
              </p>
            </div>
            <div className="flex shrink-0 flex-col gap-2 sm:flex-row">
              <button
                type="button"
                onClick={openCatalogBuilder}
                disabled={catalogLoading}
                className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-extrabold text-slate-700 shadow-sm transition-all hover:bg-slate-50 active:scale-95 disabled:cursor-wait disabled:opacity-70 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                ⚙️ Qo'lda sozlash
              </button>
              <button
                type="button"
                onClick={() => handleCatalogFill(activeSubject, activeSubject === "english" ? activePart : undefined)}
                disabled={catalogLoading}
                className={`rounded-xl px-5 py-3 text-sm font-extrabold text-white shadow-lg transition-all active:scale-95 disabled:cursor-wait disabled:opacity-70 ${
                  activeSubject === "russian"
                    ? "bg-gradient-to-r from-amber-500 to-orange-600 shadow-amber-500/25 hover:from-amber-400 hover:to-orange-500"
                    : "bg-gradient-to-r from-blue-600 to-cyan-600 shadow-blue-500/25 hover:from-blue-500 hover:to-cyan-500"
                }`}
              >
                {catalogLoading
                  ? `⏳ ${catalogProgress}% tayyorlanmoqda`
                  : activeSubject === "english"
                    ? `✨ Part ${activePart} uchun 10 mavzuni AI bilan to‘ldirish`
                    : "✨ 30 mavzuni AI bilan to‘ldirish"}
              </button>
            </div>
          </div>
          {catalogLoading && (
            <div className="mt-4 space-y-1.5">
              <div className={`h-2 overflow-hidden rounded-full ${activeSubject === "russian" ? "bg-amber-200/80 dark:bg-amber-950/80" : "bg-blue-200/80 dark:bg-blue-950/80"}`}>
                <div
                  className={`h-full rounded-full transition-all duration-500 ${activeSubject === "russian" ? "bg-gradient-to-r from-amber-500 to-orange-600" : "bg-gradient-to-r from-blue-600 to-cyan-600"}`}
                  data-csp-style={JSON.stringify({ width: `${catalogProgress}%` })}
                />
              </div>
              <p className={`text-[11px] font-medium ${activeSubject === "russian" ? "text-amber-800 dark:text-amber-200" : "text-blue-800 dark:text-blue-200"}`}>
                {catalogStage || "Savollar tayyorlanmoqda..."}
              </p>
            </div>
          )}
      </section>

      {/* ─── PART SEGMENTED SELECTOR (ONLY FOR ENGLISH IELTS) ─── */}
      {activeSubject === "english" && (
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
      )}

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
              {activeSubject === "russian"
                ? "Русский язык бўйича мавзулар ҳозирча йўқ"
                : `Part ${activePart} bo'yicha mavzular mavjud emas`}
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400 max-w-md mx-auto">
              {activeSubject === "russian"
                ? "Diamondvoy AI orqali bir tugma bilan rus tili so'zlashuv mavzulari va savollarini yarating."
                : "Diamondvoy AI orqali bir tugma bilan yangi IELTS Speaking mavzulari va Band 8.5–9.0 savollarini yarating."}
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
                          {q.sample_answer && (
                          <div className="bg-blue-50/60 dark:bg-blue-950/20 border border-blue-200/80 dark:border-blue-900/40 p-4 rounded-xl text-xs space-y-1.5">
                            <span className="font-bold text-blue-600 dark:text-blue-400 uppercase text-[10px] tracking-wider block">
                              Band 8.5–9.0 Model Answer:
                            </span>
                            <p className="text-slate-800 dark:text-slate-200 leading-relaxed italic">
                              {q.sample_answer}
                            </p>
                          </div>
                          )}

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
      <ModalPortal open={aiModalOpen}>
        <div className="fixed inset-0 z-[99999] flex items-center justify-center p-3 sm:p-5 bg-slate-950/70 backdrop-blur-md animate-fade-in">
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
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-1 bg-slate-100 dark:bg-slate-950 rounded-2xl border border-slate-200 dark:border-slate-800">
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
                      setAiMode("batch_topics");
                      setAiTargetTopicId(null);
                      setAiTopicCount("");
                    }}
                    className={`py-2.5 px-3 rounded-xl font-bold text-xs transition-all ${
                      aiMode === "batch_topics"
                        ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    🗂️ Bir Nechta Mavzu & Savollar
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
                      {topics
                        .filter((t) => (t.subject || "english") === activeSubject)
                        .map((t) => (
                          <option key={t.id} value={t.id}>
                            {activeSubject === "russian" ? t.title : `Part ${t.part} — ${t.title}`}
                          </option>
                        ))}
                    </select>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                    {aiMode === "batch_topics" ? "Mavzular yo'nalishi yoki kalit so'z (Theme):" : "Mavzu mavzusi yoki kalit so'z (Theme):"}
                  </label>
                  <input
                    type="text"
                    value={aiTheme}
                    onChange={(e) => setAiTheme(e.target.value)}
                    placeholder={
                      activeSubject === "russian"
                        ? "Masalan: Путешествия и страны, Профессия и карьера, Хобби, Технологии в нашей жизни"
                        : "Masalan: Artificial Intelligence, Traditional Festivals, Sustainable Energy, Daily Routines"
                    }
                    className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 text-sm focus:border-cyan-500 outline-none"
                  />
                </div>

                <div className={`grid grid-cols-1 ${activeSubject === "english" ? "sm:grid-cols-2" : ""} gap-4`}>
                  {activeSubject === "english" && (
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
                  )}

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                      {aiMode === "batch_topics" ? "Har bir mavzu uchun savollar soni:" : "Savollar soni:"}
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={10}
                      value={aiCount}
                      onChange={(e) => setAiCount(e.target.value === "" ? "" : Number(e.target.value))}
                      className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-sm focus:border-cyan-500 outline-none"
                    />
                    <p className="mt-1.5 text-[11px] text-slate-500 dark:text-slate-400">
                      Bu maksimum: 10 tanlansa ham 4–10 ta sifatli savol yetarli bo‘ladi.
                    </p>
                  </div>
                </div>

                {aiMode === "batch_topics" && (
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                      Mavzular soni:
                    </label>
                    <input
                      type="number"
                      min={2}
                      max={5}
                      value={aiTopicCount}
                      onChange={(e) => setAiTopicCount(e.target.value === "" ? "" : Number(e.target.value))}
                      className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-sm focus:border-cyan-500 outline-none"
                    />
                    <p className="mt-1.5 text-[11px] text-slate-500 dark:text-slate-400">
                      Maksimum 5 ta mavzu. Tasdiqlaganda barcha mavzu hamda savollar birga saqlanadi.
                    </p>
                  </div>
                )}

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
                      <span className="w-full flex flex-col gap-2 px-2">
                        <span className="flex items-center justify-center gap-2">
                          <span className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                          <span>Diamondvoy AI: {aiProgress}%</span>
                        </span>
                        <span className="h-1.5 w-full max-w-sm mx-auto overflow-hidden rounded-full bg-white/25">
                          <span className="block h-full rounded-full bg-white transition-all duration-500" data-csp-style={JSON.stringify({ width: `${aiProgress}%` })} />
                        </span>
                        <span className="text-[11px] font-medium text-white/85">{aiProgressStage || "AI savollarni yaratmoqda..."}</span>
                      </span>
                    ) : (
                      <>
                        <span className="text-base">✨</span>
                        <span>{aiMode === "batch_topics" ? "Mavzular va Savollarni Generatsiya Qilish" : "Mavzu va Savollarni Generatsiya Qilish"}</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            ) : (
              /* Preview of Generated Content */
              <div className="space-y-5">
                {aiMode === "batch_topics" ? (
                  <div className="p-5 bg-slate-50 dark:bg-slate-950 rounded-2xl border border-cyan-500/30 space-y-3">
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
                        Birgalikda saqlanadigan mavzular:
                      </span>
                      <h4 className="text-lg font-bold text-slate-900 dark:text-white">
                        {aiGeneratedResult.topics?.length || 0} ta mavzu · har birida {aiCount} ta savol
                      </h4>
                    </div>
                    {(aiGeneratedResult.topics || []).map((topic: any, index: number) => (
                      <div key={index} className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
                        <div className="flex items-center justify-between gap-3">
                          <span className="font-bold text-sm text-slate-900 dark:text-white">
                            #{index + 1} {topic.topic_title || topic.title || "Mavzu"}
                          </span>
                        </div>
                        <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">
                          {(topic.questions || []).length} ta savol tayyorlandi
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                <div className="p-5 bg-slate-50 dark:bg-slate-950 rounded-2xl border border-cyan-500/30 space-y-4">
                  <div className="border-b border-slate-200 dark:border-slate-800 pb-3">
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
                        {aiMode === "new_topic" ? "Yangi Mavzu Nomi:" : "Tanlangan Mavzu:"}
                      </span>
                      <h4 className="text-lg font-bold text-slate-900 dark:text-white">
                        {aiGeneratedResult.topic_title || aiTheme}
                      </h4>
                    </div>
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

                        {activeSubject !== "russian" && aiPart === 2 && q.cue_card_bullet_points && q.cue_card_bullet_points.length > 0 && (
                          <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-300 space-y-1">
                            <span className="font-bold text-cyan-600 dark:text-cyan-400 block text-[10px] uppercase">
                              You should say:
                            </span>
                            {q.cue_card_bullet_points.map((pt: string, pi: number) => (
                              <div key={pi}>• {pt}</div>
                            ))}
                          </div>
                        )}

                        {q.sample_answer && (
                        <div className="p-3 bg-blue-50/60 dark:bg-blue-950/20 border border-blue-200/80 dark:border-blue-900/30 rounded-lg text-slate-800 dark:text-slate-200 italic leading-relaxed">
                          <strong>{activeSubject === "russian" ? "Namunaviy javob (B2–C1):" : "Band 8.5–9.0 Namuna:"}</strong> {q.sample_answer}
                        </div>
                        )}

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
                )}

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
      </ModalPortal>

      {/* ─── MODAL: CONFIGURABLE CATALOGUE FILL ─── */}
      <ModalPortal open={catalogBuilderOpen}>
        <div className="fixed inset-0 z-[99999] flex items-center justify-center bg-slate-950/70 p-3 backdrop-blur-md animate-fade-in sm:p-5">
          <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-3xl border border-slate-200 bg-white p-6 text-slate-900 shadow-2xl dark:border-slate-800 dark:bg-slate-900 dark:text-white md:p-8">
            <div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-4 dark:border-slate-800">
              <div>
                <h3 className="text-lg font-extrabold">⚙️ Moslashuvchan katalog generatsiyasi</h3>
                <p className="mt-1 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
                  Topiclarni qo'lda kiriting yoki aynan belgilangan sonli savolga ega mavjud topiclarni topib to'ldiring. AI har bir topicdagi eski savollarni tekshiradi va takrorini qo'shmaydi.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setCatalogBuilderOpen(false)}
                className="text-xl text-slate-400 transition-colors hover:text-slate-800 dark:hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="mt-5 space-y-5">
              <div>
                <label className="mb-2 block text-xs font-extrabold text-slate-700 dark:text-slate-300">IELTS bo'limi (Part)</label>
                {activeSubject === "russian" ? (
                  <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm font-bold text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
                    🇷🇺 Rus tili uchun Part 1 ishlatiladi
                  </div>
                ) : (
                  <div className="grid grid-cols-3 gap-2">
                    {[1, 2, 3].map((part) => (
                      <button
                        key={part}
                        type="button"
                        onClick={() => setCustomCatalogPart(part)}
                        className={`rounded-xl border px-3 py-2.5 text-sm font-extrabold transition-all ${
                          customCatalogPart === part
                            ? "border-blue-600 bg-blue-600 text-white shadow-md shadow-blue-600/20"
                            : "border-slate-300 bg-slate-50 text-slate-700 hover:border-blue-400 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300"
                        }`}
                      >
                        Part {part}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
                <label className="flex cursor-pointer items-start gap-3">
                  <input
                    type="checkbox"
                    checked={customExistingOnly}
                    onChange={(e) => setCustomExistingOnly(e.target.checked)}
                    className="mt-0.5 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span>
                    <span className="block text-sm font-extrabold">Mavjud topiclarni savol soni bo'yicha topish</span>
                    <span className="mt-0.5 block text-xs text-slate-500 dark:text-slate-400">
                      Yoqilsa, qo'lda kiritilgan topiclar ishlatilmaydi: tanlangan Part ichidan aynan siz ko'rsatgan miqdorda savoli bor topiclar topiladi va to'ldiriladi. Bir ishda ko'pi bilan 30 tasi olinadi.
                    </span>
                  </span>
                </label>
                {customExistingOnly && (
                  <div className="mt-4">
                    <label className="mb-1.5 block text-xs font-bold text-slate-700 dark:text-slate-300">Topic hozir nechta savolga ega bo'lishi kerak?</label>
                    <input
                      type="number"
                      min={0}
                      max={30}
                      value={customExistingQuestionCount}
                      onChange={(e) => setCustomExistingQuestionCount(Number(e.target.value))}
                      className="w-full rounded-xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950"
                    />
                  </div>
                )}
              </div>

              {!customExistingOnly && (
                <div>
                  <label className="mb-1.5 block text-xs font-extrabold text-slate-700 dark:text-slate-300">
                    Topiclar (har biri yangi qatorda, maksimum 30 ta)
                  </label>
                  <textarea
                    rows={8}
                    value={customCatalogTopics}
                    onChange={(e) => setCustomCatalogTopics(e.target.value)}
                    placeholder={activeSubject === "russian"
                      ? "Путешествия и новые места\nРабота и карьера\nХобби и свободное время"
                      : "Travel and tourism\nTechnology in everyday life\nA person who influenced you"}
                    className="w-full resize-y rounded-xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950"
                  />
                  <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">
                    {customCatalogTopics.split(/\r?\n/).map((value) => value.trim()).filter(Boolean).length}/30 topic kiritildi.
                  </p>
                </div>
              )}

              <div>
                <label className="mb-2 block text-xs font-extrabold text-slate-700 dark:text-slate-300">Har topicdagi yakuniy savollar soni</label>
                <div className="grid grid-cols-2 gap-2">
                  {([
                    ["exact", "Aniq belgilangan miqdor"],
                    ["range", "Minimum–maximum oralig'i"],
                  ] as const).map(([mode, label]) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setCustomQuestionTargetMode(mode)}
                      className={`rounded-xl border px-3 py-2.5 text-xs font-extrabold transition-all ${
                        customQuestionTargetMode === mode
                          ? "border-blue-600 bg-blue-600 text-white"
                          : "border-slate-300 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {customQuestionTargetMode === "exact" ? (
                  <div className="mt-3">
                    <label className="mb-1.5 block text-xs font-bold text-slate-700 dark:text-slate-300">Aniq miqdor (1–30)</label>
                    <input
                      type="number"
                      min={1}
                      max={30}
                      value={customExactQuestionCount}
                      onChange={(e) => setCustomExactQuestionCount(Number(e.target.value))}
                      className="w-full rounded-xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950"
                    />
                  </div>
                ) : (
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1.5 block text-xs font-bold text-slate-700 dark:text-slate-300">Minimum (1–30)</label>
                      <input
                        type="number"
                        min={1}
                        max={30}
                        value={customMinimumQuestionCount}
                        onChange={(e) => setCustomMinimumQuestionCount(Number(e.target.value))}
                        className="w-full rounded-xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950"
                      />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-xs font-bold text-slate-700 dark:text-slate-300">Maximum (1–30)</label>
                      <input
                        type="number"
                        min={1}
                        max={30}
                        value={customMaximumQuestionCount}
                        onChange={(e) => setCustomMaximumQuestionCount(Number(e.target.value))}
                        className="w-full rounded-xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950"
                      />
                    </div>
                  </div>
                )}
                <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                  Minimum–maximum rejimida har topic uchun oraliqdagi turli yakuniy miqdor tanlanadi; hammasi bir xil ko'rinmaydi.
                </p>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-3 border-t border-slate-200 pt-4 dark:border-slate-800">
              <button
                type="button"
                onClick={() => setCatalogBuilderOpen(false)}
                className="px-4 py-2.5 text-sm text-slate-500 hover:text-slate-800 dark:hover:text-white"
              >
                Bekor qilish
              </button>
              <button
                type="button"
                onClick={handleCustomCatalogFill}
                className="rounded-xl bg-gradient-to-r from-blue-600 to-cyan-600 px-6 py-2.5 text-sm font-extrabold text-white shadow-md shadow-blue-600/25 transition-all active:scale-95 hover:from-blue-500 hover:to-cyan-500"
              >
                ✨ Katalogni boshlash
              </button>
            </div>
          </div>
        </div>
      </ModalPortal>

      {/* ─── MODAL: MANUAL ADD TOPIC ─── */}
      <ModalPortal open={newTopicModalOpen}>
        <div className="fixed inset-0 z-[99999] flex items-center justify-center p-3 sm:p-5 bg-slate-950/70 backdrop-blur-md animate-fade-in">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl max-w-lg w-full p-6 md:p-8 space-y-5 shadow-2xl text-slate-900 dark:text-white">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                {activeSubject === "russian" ? "Русский язык — Yangi Mavzu Qo'shish" : `Part ${newTopicPart} — Yangi Mavzu Qo'shish`}
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
                placeholder={activeSubject === "russian" ? "Masalan: Путешествия и страны" : "Masalan: Weather and Climate, Traditional Festivals"}
                className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-sm outline-none focus:border-cyan-500"
              />
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
      </ModalPortal>

      {/* ─── MODAL: MANUAL ADD / EDIT QUESTION ─── */}
      <ModalPortal open={newQuestionModalOpen}>
        <div className="fixed inset-0 z-[99999] flex items-center justify-center p-3 sm:p-5 bg-slate-950/70 backdrop-blur-md animate-fade-in">
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
                  {qAiAutoLoading
                    ? "AI to'ldirmoqda..."
                    : activeSubject === "russian"
                      ? "✨ AI orqali lug'atni to'ldirish"
                      : "✨ AI orqali namunaviy javob va lug'atni to'ldirish"}
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

            {activeSubject === "english" && activePart === 2 && (
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

            {activeSubject === "english" && (
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
            )}

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
      </ModalPortal>

      {/* ─── MODAL: PUSH NOTIFICATION ─── */}
      <ModalPortal open={notifModalOpen}>
        <div className="fixed inset-0 z-[99999] flex items-center justify-center p-3 sm:p-5 bg-slate-950/70 backdrop-blur-md animate-fade-in">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl max-w-lg w-full p-6 md:p-8 space-y-5 shadow-2xl text-slate-900 dark:text-white">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <div className="flex items-center gap-2.5">
                <span className="text-xl">📢</span>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                  Speaking App-ga Bildirishnoma (Push)
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setNotifModalOpen(false)}
                className="text-slate-400 hover:text-slate-700 dark:hover:text-white text-xl"
              >
                ✕
              </button>
            </div>

            <div className="p-3 rounded-2xl bg-blue-500/10 border border-blue-500/20 text-xs text-blue-700 dark:text-blue-300">
              Bu xabar Diamond Speaking ilovasini yuklab olgan barcha o'quvchilarga (FCM orqali) real-time bildirishnoma sifatida boradi.
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                Xabar Sarlavhasi (Title):
              </label>
              <input
                type="text"
                value={notifTitle}
                onChange={(e) => setNotifTitle(e.target.value)}
                placeholder="Masalan: 🔥 Yangi B2-C1 Rus tili mavzulari qo'shildi!"
                className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-sm outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                Xabar Matni (Body):
              </label>
              <textarea
                rows={3}
                value={notifBody}
                onChange={(e) => setNotifBody(e.target.value)}
                placeholder="Masalan: Ilovani yangilang yoki qayta yuklang va yangi speaking savollarini ko'rib chiqing..."
                className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white text-sm outline-none focus:border-blue-500 resize-none"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                Target Bo'lim (Ixtiyoriy):
              </label>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { label: "Barchasi", val: null },
                  { label: "Part 1", val: 1 },
                  { label: "Part 2", val: 2 },
                  { label: "Part 3", val: 3 },
                ].map((item) => (
                  <button
                    key={String(item.val)}
                    type="button"
                    onClick={() => setNotifPart(item.val)}
                    className={`py-2 text-xs font-bold rounded-xl border transition-all ${
                      notifPart === item.val
                        ? "bg-blue-600 text-white border-blue-600 shadow-md shadow-blue-600/20"
                        : "bg-slate-50 dark:bg-slate-950 border-slate-300 dark:border-slate-800 text-slate-700 dark:text-slate-300"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-3">
              <button
                type="button"
                onClick={() => setNotifModalOpen(false)}
                className="px-4 py-2.5 rounded-xl text-slate-500 hover:text-slate-800 dark:hover:text-white text-sm"
              >
                Bekor qilish
              </button>
              <button
                type="button"
                disabled={notifLoading}
                onClick={handleSendNotif}
                className="px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-sm shadow-md shadow-blue-600/25 disabled:opacity-50 active:scale-95 transition-all flex items-center gap-2"
              >
                {notifLoading ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Yuborilmoqda...
                  </>
                ) : (
                  <>
                    <span>🚀</span>
                    Yuborish
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </ModalPortal>
    </div>
  );
}
