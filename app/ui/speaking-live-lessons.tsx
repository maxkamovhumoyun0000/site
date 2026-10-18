"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";
import { createPortal } from "react-dom";
import { useWebLocale } from "./web-i18n";
import { LiveKitModeratorRoom } from "./livekit-moderator-room";

type Lesson = {
  id: number;
  title: string;
  topic: string;
  subject: "english" | "russian" | string;
  moderator_name: string;
  audience_label: string;
  starts_at: string;
  ends_at: string;
  status: "scheduled" | "live" | "completed" | "cancelled" | string;
  auto_open_video_room: boolean;
  cancellation_reason: string;
  room_id: string;
  recording_url: string;
  recording_expires_at: string;
  recording_days_left: number;
  recording_expired: boolean;
  reminder_minutes: number[];
};
type LiveRoom = {
  id: string;
  title: string;
  status: string;
  participant_count?: number;
};
type Props = {
  apiFetch: (
    path: string,
    options?: { method?: string; body?: unknown },
  ) => Promise<unknown>;
};
type FormValue = {
  title: string;
  topic: string;
  subject: "english" | "russian";
  moderator_name: string;
  audience_label: string;
  starts_at: string;
  ends_at: string;
  auto_open_video_room: boolean;
  reminder_minutes: number[];
};

const emptyForm = (): FormValue => ({
  title: "",
  topic: "",
  subject: "english",
  moderator_name: "",
  audience_label: "Barcha Speaking foydalanuvchilari",
  starts_at: "",
  ends_at: "",
  auto_open_video_room: true,
  reminder_minutes: [1440, 60, 15],
});
const ROOM_TEXT = {
  uz: {
    label: "Live video xonasi avtomatik ochilsin",
    hint: "Dars boshlanishidan 5 daqiqa oldin xona qatnashchilar uchun ochiladi.",
  },
  en: {
    label: "Open the live video room automatically",
    hint: "The room opens to participants 5 minutes before the lesson starts.",
  },
  ru: {
    label: "Автоматически открыть live-видеокомнату",
    hint: "Комната откроется участникам за 5 минут до начала занятия.",
  },
} as const;
const TEXT = {
  uz: {
    title: "Live darslar jadvali",
    subtitle:
      "Speaking ilovasidagi jonli video darslarni rejalashtiring, boshqaring va yozuvlarini kuzating.",
    today: "Bugungi darslar",
    upcoming: "Kelgusi darslar",
    live: "Jonli efirdagilar",
    recordings: "Yozuvlar holati",
    cancelled: "Bekor qilinganlar",
    month: "Oy",
    week: "Hafta",
    day: "Kun",
    list: "Jadval ro‘yxati",
    all: "Barchasi",
    english: "English / IELTS",
    russian: "Rus tili",
    subject: "Fan / til",
    status: "Holat",
    recording: "Yozuv holati",
    clear: "Filtrlarni tozalash",
    name: "Dars nomi va mavzu",
    audience: "Auditoriya",
    time: "Boshlanish va tugash",
    moderator: "Moderator",
    participants: "Qatnashchilar",
    recordingCol: "30 kunlik yozuv",
    actions: "Amallar",
    planned: "Rejalashtirilgan",
    onair: "Jonli efirda",
    complete: "Tugallangan",
    cancel: "Bekor qilingan",
    noRecording: "Yozuv mavjud emas",
    expired: "Muddati tugagan",
    play: "Yozuvni ko‘rish",
    enter: "Live video xonasiga kirish",
    start: "Live boshlash",
    end: "Live’ni tugatish",
    notify: "Xabar yuborish",
    edit: "Tahrirlash",
    reopen: "Qayta ochish",
    history: "O‘zgarishlar tarixi",
    export: "Eksport (CSV)",
    create: "Dars rejalashtirish",
    refresh: "Yangilash",
    empty: "Tanlangan davrda dars yo‘q.",
    loading: "Yuklanmoqda…",
    error: "Darslar jadvalini yuklab bo‘lmadi.",
    save: "Saqlash",
    close: "Yopish",
    lessonTitle: "Dars nomi",
    topic: "Dars mavzusi",
    audienceLabel: "Auditoriya / guruh",
    moderatorName: "Moderator nomi",
    starts: "Boshlanish vaqti",
    ends: "Tugash vaqti",
    reminders: "Eslatmalar",
    timeZone: "Toshkent vaqti (UTC+5)",
    minute24: "24 soat oldin",
    minute1: "1 soat oldin",
    minute15: "15 daqiqa oldin",
    createTitle: "Yangi Live dars rejalashtirish",
    editTitle: "Live darsni tahrirlash",
    recordingUrl: "Yozuvning HTTPS havolasi",
    addRecording: "Yozuv havolasini biriktirish",
    reason: "Bekor qilish sababi",
    changed: "Jadval yangilandi",
    noDevices:
      "Bildirishnoma navbatga qo‘yildi; qurilmalarga yetkazilganini hisobotdan tekshiring.",
    saved: "O‘zgarishlar saqlandi.",
    sent: "Bildirishnoma yuborildi.",
    none: "Hozircha ma’lumot yo‘q.",
    reminder24: "24 soat",
    reminder1: "1 soat",
    reminder15: "15 daqiqa",
    count: "ta dars",
    range: "Ko‘rsatilmoqda",
    total: "jami",
    previous: "Oldingi",
    next: "Keyingi",
    allStatus: "Barcha holatlar",
    allRecording: "Barcha yozuvlar",
    recordingAvailable: "Yozuvi mavjud",
    dateToday: "Bugun",
    recent: "Oxirgi 30 kun",
  },
  en: {
    title: "Live lesson schedule",
    subtitle:
      "Schedule and manage live video lessons for the Speaking app and track their recordings.",
    today: "Today's lessons",
    upcoming: "Upcoming lessons",
    live: "Live now",
    recordings: "Recording status",
    cancelled: "Cancelled",
    month: "Month",
    week: "Week",
    day: "Day",
    list: "Schedule list",
    all: "All",
    english: "English / IELTS",
    russian: "Russian",
    subject: "Subject / language",
    status: "Status",
    recording: "Recording",
    clear: "Clear filters",
    name: "Lesson and topic",
    audience: "Audience",
    time: "Start and end",
    moderator: "Moderator",
    participants: "Participants",
    recordingCol: "30-day recording",
    actions: "Actions",
    planned: "Scheduled",
    onair: "Live",
    complete: "Completed",
    cancel: "Cancelled",
    noRecording: "No recording",
    expired: "Expired",
    play: "Watch recording",
    enter: "Enter live video room",
    start: "Start live",
    end: "End live",
    notify: "Send notice",
    edit: "Edit",
    reopen: "Reopen",
    history: "Change history",
    export: "Export (CSV)",
    create: "Schedule a lesson",
    refresh: "Refresh",
    empty: "No lessons in this period.",
    loading: "Loading…",
    error: "Could not load the lesson schedule.",
    save: "Save",
    close: "Close",
    lessonTitle: "Lesson title",
    topic: "Lesson topic",
    audienceLabel: "Audience / group",
    moderatorName: "Moderator name",
    starts: "Starts at",
    ends: "Ends at",
    reminders: "Reminders",
    timeZone: "Tashkent time (UTC+5)",
    minute24: "24 hours before",
    minute1: "1 hour before",
    minute15: "15 minutes before",
    createTitle: "Schedule a live lesson",
    editTitle: "Edit live lesson",
    recordingUrl: "Recording HTTPS link",
    addRecording: "Attach recording link",
    reason: "Cancellation reason",
    changed: "Schedule updated",
    noDevices: "Notice queued; check delivery status in history.",
    saved: "Changes saved.",
    sent: "Notice sent.",
    none: "No information yet.",
    reminder24: "24 hours",
    reminder1: "1 hour",
    reminder15: "15 min",
    count: "lessons",
    range: "Showing",
    total: "total",
    previous: "Previous",
    next: "Next",
    allStatus: "All statuses",
    allRecording: "All recordings",
    recordingAvailable: "Recording available",
    dateToday: "Today",
    recent: "Last 30 days",
  },
  ru: {
    title: "Расписание live-уроков",
    subtitle:
      "Планируйте и управляйте live-видеоуроками Speaking и отслеживайте записи.",
    today: "Уроки сегодня",
    upcoming: "Предстоящие уроки",
    live: "Сейчас в эфире",
    recordings: "Состояние записей",
    cancelled: "Отменено",
    month: "Месяц",
    week: "Неделя",
    day: "День",
    list: "Список уроков",
    all: "Все",
    english: "English / IELTS",
    russian: "Русский язык",
    subject: "Предмет / язык",
    status: "Статус",
    recording: "Запись",
    clear: "Сбросить фильтры",
    name: "Урок и тема",
    audience: "Аудитория",
    time: "Начало и конец",
    moderator: "Модератор",
    participants: "Участники",
    recordingCol: "Запись на 30 дней",
    actions: "Действия",
    planned: "Запланирован",
    onair: "В эфире",
    complete: "Завершён",
    cancel: "Отменён",
    noRecording: "Записи нет",
    expired: "Срок истёк",
    play: "Смотреть запись",
    enter: "Войти в live-видеокомнату",
    start: "Начать эфир",
    end: "Завершить эфир",
    notify: "Отправить уведомление",
    edit: "Изменить",
    reopen: "Возобновить",
    history: "История изменений",
    export: "Экспорт (CSV)",
    create: "Запланировать урок",
    refresh: "Обновить",
    empty: "В этом периоде уроков нет.",
    loading: "Загрузка…",
    error: "Не удалось загрузить расписание.",
    save: "Сохранить",
    close: "Закрыть",
    lessonTitle: "Название урока",
    topic: "Тема урока",
    audienceLabel: "Аудитория / группа",
    moderatorName: "Имя модератора",
    starts: "Начало",
    ends: "Окончание",
    reminders: "Напоминания",
    timeZone: "Время Ташкента (UTC+5)",
    minute24: "За 24 часа",
    minute1: "За 1 час",
    minute15: "За 15 минут",
    createTitle: "Запланировать live-урок",
    editTitle: "Изменить live-урок",
    recordingUrl: "HTTPS-ссылка на запись",
    addRecording: "Добавить ссылку на запись",
    reason: "Причина отмены",
    changed: "Расписание обновлено",
    noDevices:
      "Уведомление поставлено в очередь; доставку проверьте в истории.",
    saved: "Изменения сохранены.",
    sent: "Уведомление отправлено.",
    none: "Пока нет данных.",
    reminder24: "24 часа",
    reminder1: "1 час",
    reminder15: "15 минут",
    count: "уроков",
    range: "Показано",
    total: "всего",
    previous: "Назад",
    next: "Далее",
    allStatus: "Все статусы",
    allRecording: "Все записи",
    recordingAvailable: "Запись доступна",
    dateToday: "Сегодня",
    recent: "Последние 30 дней",
  },
} as const;

function localDate(
  value: string,
  locale: string,
  options: Intl.DateTimeFormatOptions = {},
) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : new Intl.DateTimeFormat(locale, {
        timeZone: "Asia/Tashkent",
        ...options,
      }).format(date);
}
function dateInput(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return shifted.toISOString().slice(0, 16);
}
function toIso(value: string) {
  return new Date(value).toISOString();
}
export function SpeakingLiveLessons({ apiFetch }: Props) {
  const locale = useWebLocale();
  const lang = (
    locale === "ru" || locale === "en" ? locale : "uz"
  ) as keyof typeof TEXT;
  const t = TEXT[lang];
  const roomText = ROOM_TEXT[lang];
  function statusLabel(status: Lesson["status"]) {
    if (status === "live") return t.onair;
    if (status === "completed") return t.complete;
    if (status === "cancelled") return t.cancel;
    return t.planned;
  }
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [rooms, setRooms] = useState<LiveRoom[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [view, setView] = useState<"month" | "week" | "day" | "list">("month");
  const [anchor, setAnchor] = useState(() => new Date());
  const [subjectFilter, setSubjectFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [recordingFilter, setRecordingFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [form, setForm] = useState<FormValue>(emptyForm());
  const [editing, setEditing] = useState<Lesson | null>(null);
  const [modal, setModal] = useState<"form" | "recording" | "history" | null>(
    null,
  );
  const [recordingLesson, setRecordingLesson] = useState<Lesson | null>(null);
  const [recordingUrl, setRecordingUrl] = useState("");
  const [history, setHistory] = useState<
    Array<{
      action: string;
      details: Record<string, unknown>;
      created_at: string;
    }>
  >([]);
  const [menu, setMenu] = useState<number | null>(null);
  const [moderatingRoom, setModeratingRoom] = useState<LiveRoom | null>(null);

  useEffect(() => {
    if (!modal) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setModal(null);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [modal]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [schedule, active] = await Promise.all([
        apiFetch("/staff/speaking/live-lessons", { method: "GET" }) as Promise<{
          lessons?: Lesson[];
        }>,
        apiFetch("/staff/speaking/live-video/rooms", { method: "GET" }).catch(
          () => ({ rooms: [] }),
        ) as Promise<{ rooms?: LiveRoom[] }>,
      ]);
      setLessons(Array.isArray(schedule.lessons) ? schedule.lessons : []);
      setRooms(Array.isArray(active.rooms) ? active.rooms : []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t.error);
    } finally {
      setLoading(false);
    }
  }, [apiFetch, t.error]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const activeRooms = rooms.filter(
    (room) => room.status === "active" || room.status === "ending",
  );
  const periodRows = useMemo(
    () =>
      lessons.filter((lesson) => {
        const date = new Date(lesson.starts_at);
        if (Number.isNaN(date.getTime())) return false;
        if (view === "list") return true;
        if (view === "month")
          return (
            date.getFullYear() === anchor.getFullYear() &&
            date.getMonth() === anchor.getMonth()
          );
        if (view === "day")
          return date.toDateString() === anchor.toDateString();
        const start = new Date(anchor);
        start.setDate(anchor.getDate() - ((anchor.getDay() + 6) % 7));
        start.setHours(0, 0, 0, 0);
        const end = new Date(start);
        end.setDate(start.getDate() + 7);
        return date >= start && date < end;
      }),
    [lessons, view, anchor],
  );
  const filtered = periodRows
    .filter((lesson) => {
      if (subjectFilter !== "all" && lesson.subject !== subjectFilter)
        return false;
      if (statusFilter !== "all" && lesson.status !== statusFilter)
        return false;
      if (recordingFilter === "available" && !lesson.recording_url)
        return false;
      if (recordingFilter === "expired" && !lesson.recording_expired)
        return false;
      if (
        recordingFilter === "missing" &&
        (lesson.recording_url || lesson.status !== "completed")
      )
        return false;
      const needle = query.trim().toLocaleLowerCase();
      return (
        !needle ||
        `${lesson.title} ${lesson.topic} ${lesson.moderator_name} ${lesson.audience_label}`
          .toLocaleLowerCase()
          .includes(needle)
      );
    })
    .sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  const pageSize = 8;
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const visible = filtered.slice(page * pageSize, (page + 1) * pageSize);
  const todayKey = new Date().toDateString();
  const todayCount = lessons.filter(
    (lesson) =>
      new Date(lesson.starts_at).toDateString() === todayKey &&
      lesson.status !== "cancelled",
  ).length;
  const upcomingCount = lessons.filter(
    (lesson) =>
      lesson.status === "scheduled" && new Date(lesson.starts_at) >= new Date(),
  ).length;
  const recordingCount = lessons.filter((lesson) =>
    Boolean(lesson.recording_url),
  ).length;
  const cancelledCount = lessons.filter(
    (lesson) => lesson.status === "cancelled",
  ).length;

  function shiftPeriod(direction: number) {
    setAnchor((current) => {
      const next = new Date(current);
      if (view === "month") next.setMonth(next.getMonth() + direction);
      else if (view === "week") next.setDate(next.getDate() + direction * 7);
      else next.setDate(next.getDate() + direction);
      return next;
    });
    setPage(0);
  }
  function periodTitle() {
    if (view === "month")
      return new Intl.DateTimeFormat(locale, {
        month: "long",
        year: "numeric",
      }).format(anchor);
    if (view === "day")
      return localDate(anchor.toISOString(), locale, { dateStyle: "full" });
    const start = new Date(anchor);
    start.setDate(anchor.getDate() - ((anchor.getDay() + 6) % 7));
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    return `${localDate(start.toISOString(), locale, { day: "numeric", month: "short" })} – ${localDate(end.toISOString(), locale, { day: "numeric", month: "short", year: "numeric" })}`;
  }
  function openCreate() {
    setEditing(null);
    setForm(emptyForm());
    setModal("form");
  }
  function openEdit(lesson: Lesson) {
    setEditing(lesson);
    setForm({
      title: lesson.title,
      topic: lesson.topic,
      subject: lesson.subject === "russian" ? "russian" : "english",
      moderator_name: lesson.moderator_name,
      audience_label: lesson.audience_label,
      starts_at: dateInput(lesson.starts_at),
      ends_at: dateInput(lesson.ends_at),
      auto_open_video_room: lesson.auto_open_video_room !== false,
      reminder_minutes: lesson.reminder_minutes || [1440, 60, 15],
    });
    setModal("form");
  }
  async function saveLesson(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("save");
    setError("");
    setNotice("");
    try {
      const body = {
        ...form,
        starts_at: toIso(form.starts_at),
        ends_at: toIso(form.ends_at),
      };
      await apiFetch(
        editing
          ? `/staff/speaking/live-lessons/${editing.id}`
          : "/staff/speaking/live-lessons",
        { method: editing ? "PATCH" : "POST", body },
      );
      setModal(null);
      setNotice(t.saved);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t.error);
    } finally {
      setBusy("");
    }
  }
  async function action(
    id: number,
    name: string,
    path: string,
    body?: unknown,
  ) {
    setBusy(`${id}:${name}`);
    setError("");
    setNotice("");
    try {
      const result = (await apiFetch(
        `/staff/speaking/live-lessons/${id}/${path}`,
        { method: "POST", body },
      )) as { sent_count?: number };
      if (name === "notify")
        setNotice(Number(result.sent_count || 0) > 0 ? t.sent : t.noDevices);
      else setNotice(t.saved);
      if (name === "complete") setModeratingRoom(null);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t.error);
    } finally {
      setBusy("");
      setMenu(null);
    }
  }
  async function beginLive(lesson: Lesson) {
    setBusy(`${lesson.id}:start`);
    setError("");
    try {
      const result = (await apiFetch(
        `/staff/speaking/live-lessons/${lesson.id}/start`,
        { method: "POST" },
      )) as { room_id?: string; lesson?: Lesson };
      const roomId = result.room_id || result.lesson?.room_id;
      if (!roomId) throw new Error("Live room ID was not returned.");
      setModeratingRoom({ id: roomId, title: lesson.title, status: "active" });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t.error);
    } finally {
      setBusy("");
    }
  }
  async function cancelLesson(lesson: Lesson) {
    const reason = window.prompt(t.reason, lesson.cancellation_reason || "");
    if (reason === null) return;
    await action(lesson.id, "cancel", "cancel", { reason });
  }
  async function showHistory(lesson: Lesson) {
    setRecordingLesson(lesson);
    setModal("history");
    setHistory([]);
    try {
      const result = (await apiFetch(
        `/staff/speaking/live-lessons/${lesson.id}/history`,
        { method: "GET" },
      )) as { items?: typeof history };
      setHistory(Array.isArray(result.items) ? result.items : []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t.error);
    }
  }
  async function attachRecording(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!recordingLesson) return;
    await action(recordingLesson.id, "recording", "recording", {
      recording_url: recordingUrl,
    });
    setModal(null);
    setRecordingUrl("");
  }
  function exportCsv() {
    const rows = [
      [
        "title",
        "topic",
        "subject",
        "audience",
        "moderator",
        "starts_at",
        "ends_at",
        "status",
        "recording_url",
      ],
      ...filtered.map((lesson) => [
        lesson.title,
        lesson.topic,
        lesson.subject,
        lesson.audience_label,
        lesson.moderator_name,
        lesson.starts_at,
        lesson.ends_at,
        lesson.status,
        lesson.recording_url,
      ]),
    ];
    const csv = rows
      .map((row) =>
        row
          .map((value) => `"${String(value || "").replaceAll('"', '""')}"`)
          .join(","),
      )
      .join("\r\n");
    const url = URL.createObjectURL(
      new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "speaking-live-lessons.csv";
    link.click();
    URL.revokeObjectURL(url);
  }
  function dateLabel(lesson: Lesson) {
    return `${localDate(lesson.starts_at, locale, { weekday: "short", day: "numeric", month: "short" })} · ${localDate(lesson.starts_at, locale, { hour: "2-digit", minute: "2-digit" })}–${localDate(lesson.ends_at, locale, { hour: "2-digit", minute: "2-digit" })}`;
  }

  return (
    <section className="mx-auto w-full max-w-[1400px] space-y-5 px-3 py-5 pb-24 sm:px-6">
      <header className="flex flex-col justify-between gap-4 pb-1 md:flex-row md:items-end">
        <div>
          <span className="inline-flex rounded-full border border-primary/20 bg-brand-primary-tint px-3 py-1 text-xs font-black uppercase tracking-wide text-primary">
            Diamond Speaking Live
          </span>
          <h1 className="mt-3 text-2xl font-black tracking-tight text-on-surface">
            {t.title}
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-text-secondary-light">
            {t.subtitle}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => void showHistory(lessons[0])}
            disabled={!lessons.length}
            className="rounded-xl border border-border-subtle-light bg-surface-card-light px-3.5 py-2.5 text-sm font-bold text-on-surface disabled:opacity-50"
          >
            ◷ {t.history}
          </button>
          <button
            onClick={exportCsv}
            className="rounded-xl border border-border-subtle-light bg-surface-card-light px-3.5 py-2.5 text-sm font-bold text-on-surface"
          >
            ⇩ {t.export}
          </button>
          <button
            onClick={openCreate}
            className="rounded-xl bg-[#1736E8] px-4 py-2.5 text-sm font-black text-white shadow-md transition-colors hover:bg-[#1029B9] active:bg-[#0D238F] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1736E8] focus-visible:ring-offset-2"
          >
            ＋ {t.create}
          </button>
        </div>
      </header>
      {notice ? (
        <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm font-semibold text-emerald-700">
          ✓ {notice}
        </div>
      ) : null}
      {error ? (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-3 text-sm font-semibold text-red-700">
          ⚠ {error}
        </div>
      ) : null}
      <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {[
          [t.today, `${todayCount} ${t.count}`, "calendar_today"],
          [t.upcoming, `${upcomingCount}`, "upcoming"],
          [t.live, `${activeRooms.length}`, "sensors"],
          [t.recordings, `${recordingCount}`, "video_library"],
          [t.cancelled, `${cancelledCount}`, "event_busy"],
        ].map(([label, value, icon], index) => (
          <article
            key={label}
            className={`rounded-2xl border border-border-subtle-light bg-white p-4 shadow-sm ${index === 2 && activeRooms.length ? "ring-1 ring-primary/20" : ""}`}
          >
            <div className="flex items-center justify-between text-xs font-bold text-text-secondary-light">
              <span>{label}</span>
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-primary-tint text-primary">
                {icon === "sensors"
                  ? "●"
                  : icon === "calendar_today"
                    ? "▦"
                    : icon === "upcoming"
                      ? "◷"
                      : icon === "video_library"
                        ? "▷"
                        : "×"}
              </span>
            </div>
            <div className="mt-3 text-xl font-extrabold text-on-surface">
              {value}
            </div>
            {index === 2 ? (
              <p className="mt-1 text-[11px] text-text-secondary-light">
                {activeRooms.reduce(
                  (sum, room) => sum + Number(room.participant_count || 0),
                  0,
                )}{" "}
                {t.participants.toLocaleLowerCase()}
              </p>
            ) : null}
          </article>
        ))}
      </section>
      <section className="grid grid-cols-1 items-center gap-4 rounded-2xl border border-border-subtle-light bg-white p-3 shadow-sm xl:grid-cols-[minmax(330px,auto)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <div className="flex gap-1 rounded-xl border border-border-subtle-light bg-surface-canvas-light p-1">
            {(["month", "week", "day", "list"] as const).map((key) => (
              <button
                key={key}
                onClick={() => {
                  setView(key);
                  setPage(0);
                }}
                className={`rounded-lg px-3 py-1.5 text-xs font-bold ${view === key ? "bg-white text-primary shadow-sm" : "text-text-secondary-light"}`}
              >
                {t[key]}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2 rounded-xl border border-border-subtle-light bg-surface-canvas-light px-2 py-1.5 text-sm font-bold text-on-surface">
            <button
              aria-label={t.previous}
              onClick={() => shiftPeriod(-1)}
              className="rounded px-2 py-1 hover:bg-white"
            >
              ‹
            </button>
            <span>{periodTitle()}</span>
            <button
              aria-label={t.next}
              onClick={() => shiftPeriod(1)}
              className="rounded px-2 py-1 hover:bg-white"
            >
              ›
            </button>
          </div>
        </div>
        <div className="grid min-w-0 grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-[minmax(150px,1.35fr)_minmax(125px,1fr)_minmax(125px,1fr)_minmax(135px,1.1fr)_auto]">
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(0);
            }}
            placeholder={t.name}
            className="col-span-2 min-w-0 rounded-xl border border-border-subtle-light bg-surface-canvas-light px-3 py-2 text-xs outline-none focus:border-primary sm:col-span-1"
          />
          <select
            value={subjectFilter}
            onChange={(event) => setSubjectFilter(event.target.value)}
            aria-label={t.subject}
            className="min-w-0 rounded-xl border border-border-subtle-light bg-surface-canvas-light px-3 py-2 text-xs"
          >
            <option value="all">
              {t.subject}: {t.all}
            </option>
            <option value="english">{t.english}</option>
            <option value="russian">{t.russian}</option>
          </select>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            aria-label={t.status}
            className="min-w-0 rounded-xl border border-border-subtle-light bg-surface-canvas-light px-3 py-2 text-xs"
          >
            <option value="all">{t.allStatus}</option>
            <option value="live">{t.onair}</option>
            <option value="scheduled">{t.planned}</option>
            <option value="completed">{t.complete}</option>
            <option value="cancelled">{t.cancel}</option>
          </select>
          <select
            value={recordingFilter}
            onChange={(event) => setRecordingFilter(event.target.value)}
            aria-label={t.recording}
            className="min-w-0 rounded-xl border border-border-subtle-light bg-surface-canvas-light px-3 py-2 text-xs"
          >
            <option value="all">{t.allRecording}</option>
            <option value="available">{t.recordingAvailable}</option>
            <option value="missing">{t.noRecording}</option>
          </select>
          <button
            title={t.clear}
            onClick={() => {
              setSubjectFilter("all");
              setStatusFilter("all");
              setRecordingFilter("all");
              setQuery("");
              setPage(0);
            }}
            className="justify-self-start rounded-xl border border-border-subtle-light px-3 py-2 text-sm text-text-secondary-light xl:justify-self-center"
          >
            ⟲
          </button>
        </div>
      </section>
      <section className="overflow-hidden rounded-2xl border border-border-subtle-light bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1180px] border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-border-subtle-light bg-surface-canvas-light text-[11px] font-extrabold uppercase tracking-wide text-text-secondary-light">
                {[
                  t.name,
                  t.audience,
                  t.time,
                  t.moderator,
                  t.participants,
                  t.recordingCol,
                  t.status,
                  t.actions,
                ].map((label) => (
                  <th key={label} className="px-4 py-4">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle-light">
              {loading ? (
                <tr>
                  <td
                    colSpan={8}
                    className="p-10 text-center text-sm text-text-secondary-light"
                  >
                    {t.loading}
                  </td>
                </tr>
              ) : visible.length === 0 ? (
                <tr>
                  <td
                    colSpan={8}
                    className="p-10 text-center text-sm text-text-secondary-light"
                  >
                    {t.empty}
                  </td>
                </tr>
              ) : (
                visible.map((lesson) => {
                  const room = rooms.find((item) => item.id === lesson.room_id);
                  const active =
                    lesson.status === "live" || room?.status === "active";
                  return (
                    <tr
                      key={lesson.id}
                      className={
                        active
                          ? "bg-blue-50/30"
                          : "hover:bg-surface-canvas-light/60"
                      }
                    >
                      <td className="px-4 py-4">
                        <div className="font-bold text-on-surface">
                          {lesson.title}
                        </div>
                        <div className="mt-1 text-text-secondary-light">
                          {lesson.topic || "—"}
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <span className="rounded-lg bg-brand-primary-tint px-2 py-1 font-bold text-primary">
                          {lesson.audience_label || "—"}
                        </span>
                        <div className="mt-1 text-text-secondary-light">
                          {lesson.subject === "russian" ? t.russian : t.english}
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-4 py-4 font-semibold text-on-surface">
                        {dateLabel(lesson)}
                      </td>
                      <td className="px-4 py-4">
                        {lesson.moderator_name || "—"}
                      </td>
                      <td className="px-4 py-4">
                        {room
                          ? `${Number(room.participant_count || 0)} / 1 000`
                          : "—"}
                      </td>
                      <td className="px-4 py-4">
                        {lesson.recording_url ? (
                          lesson.recording_days_left > 0 ? (
                            <button
                              onClick={() =>
                                window.open(
                                  lesson.recording_url,
                                  "_blank",
                                  "noopener,noreferrer",
                                )
                              }
                              className="font-bold text-emerald-700"
                            >
                              ▷ {lesson.recording_days_left}{" "}
                              {lang === "en"
                                ? "days left"
                                : lang === "ru"
                                  ? "дн. осталось"
                                  : "kun qoldi"}
                            </button>
                          ) : (
                            <span className="text-text-secondary-light">
                              {t.expired}
                            </span>
                          )
                        ) : (
                          <button
                            disabled={
                              lesson.status === "scheduled" ||
                              lesson.status === "cancelled"
                            }
                            onClick={() => {
                              setRecordingLesson(lesson);
                              setRecordingUrl("");
                              setModal("recording");
                            }}
                            className="font-semibold text-primary disabled:text-text-muted-light"
                          >
                            {lesson.status === "completed" || active
                              ? t.addRecording
                              : t.noRecording}
                          </button>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        <span
                          className={`rounded-full px-2.5 py-1 font-bold ${lesson.status === "live" ? "bg-emerald-50 text-emerald-700" : lesson.status === "cancelled" ? "bg-red-50 text-red-700" : "bg-surface-canvas-light text-text-secondary-light"}`}
                        >
                          {statusLabel(lesson.status)}
                        </span>
                        {lesson.cancellation_reason ? (
                          <div className="mt-1 max-w-36 text-red-600">
                            {lesson.cancellation_reason}
                          </div>
                        ) : null}
                      </td>
                      <td className="whitespace-nowrap px-4 py-4 text-right">
                        <div className="relative flex items-center justify-end gap-1">
                          {lesson.status === "scheduled" || active ? (
                            <button
                              disabled={Boolean(busy)}
                              onClick={() =>
                                active
                                  ? setModeratingRoom({
                                      id: lesson.room_id,
                                      title: lesson.title,
                                      status: "active",
                                    })
                                  : void beginLive(lesson)
                              }
                              className="rounded-lg bg-[#1736E8] px-3 py-2 font-bold text-white transition-colors hover:bg-[#1029B9] active:bg-[#0D238F] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1736E8] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {busy === `${lesson.id}:start`
                                ? "…"
                                : active
                                  ? t.enter
                                  : t.start}
                            </button>
                          ) : null}
                          {active ? (
                            <button
                              disabled={Boolean(busy)}
                              onClick={() =>
                                void action(lesson.id, "complete", "complete")
                              }
                              className="rounded-lg border border-red-200 px-2 py-2 font-bold text-red-600"
                            >
                              {t.end}
                            </button>
                          ) : null}
                          <button
                            disabled={Boolean(busy)}
                            title={t.notify}
                            onClick={() =>
                              void action(lesson.id, "notify", "notify")
                            }
                            className="rounded-lg border border-border-subtle-light px-2.5 py-2 text-primary"
                          >
                            ↗
                          </button>
                          <button
                            onClick={() => openEdit(lesson)}
                            disabled={
                              lesson.status === "completed" ||
                              lesson.status === "cancelled"
                            }
                            className="rounded-lg border border-border-subtle-light px-2.5 py-2 font-bold text-on-surface disabled:opacity-40"
                          >
                            {t.edit}
                          </button>
                          <button
                            onClick={() =>
                              setMenu(menu === lesson.id ? null : lesson.id)
                            }
                            className="rounded-lg border border-border-subtle-light px-2.5 py-2"
                          >
                            ⋮
                          </button>
                          {menu === lesson.id ? (
                            <div className="absolute right-0 top-10 z-20 grid min-w-44 gap-1 rounded-xl border border-border-subtle-light bg-white p-1.5 shadow-xl">
                              {lesson.status === "cancelled" ? (
                                <button
                                  onClick={() =>
                                    void action(lesson.id, "reopen", "reopen")
                                  }
                                  className="rounded-lg px-3 py-2 text-left hover:bg-surface-canvas-light"
                                >
                                  {t.reopen}
                                </button>
                              ) : lesson.status === "scheduled" || active ? (
                                <button
                                  onClick={() => void cancelLesson(lesson)}
                                  className="rounded-lg px-3 py-2 text-left text-red-600 hover:bg-red-50"
                                >
                                  {t.cancel}
                                </button>
                              ) : null}
                              <button
                                onClick={() => void showHistory(lesson)}
                                className="rounded-lg px-3 py-2 text-left hover:bg-surface-canvas-light"
                              >
                                {t.history}
                              </button>
                              {lesson.status === "completed" || active ? (
                                <button
                                  onClick={() => {
                                    setRecordingLesson(lesson);
                                    setRecordingUrl(lesson.recording_url || "");
                                    setModal("recording");
                                    setMenu(null);
                                  }}
                                  className="rounded-lg px-3 py-2 text-left hover:bg-surface-canvas-light"
                                >
                                  {t.addRecording}
                                </button>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
        <div className="flex flex-col justify-between gap-3 border-t border-border-subtle-light bg-surface-canvas-light/60 px-5 py-4 text-xs text-text-secondary-light sm:flex-row sm:items-center">
          <span>
            {t.range}: {filtered.length ? page * pageSize + 1 : 0}–
            {Math.min((page + 1) * pageSize, filtered.length)} / {t.total}{" "}
            {filtered.length} {t.count}
          </span>
          <div className="flex items-center gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage(Math.max(0, page - 1))}
              className="rounded-xl border border-border-subtle-light bg-white px-3 py-2 disabled:opacity-40"
            >
              {t.previous}
            </button>
            <span>
              {page + 1} / {pageCount}
            </span>
            <button
              disabled={page + 1 >= pageCount}
              onClick={() => setPage(Math.min(pageCount - 1, page + 1))}
              className="rounded-xl border border-border-subtle-light bg-white px-3 py-2 disabled:opacity-40"
            >
              {t.next}
            </button>
            <button
              onClick={() => void load()}
              className="rounded-xl border border-border-subtle-light bg-white px-3 py-2"
            >
              ↻ {t.refresh}
            </button>
          </div>
        </div>
      </section>
      {modal && typeof document !== "undefined"
        ? createPortal(<div
          className="fixed inset-0 z-[10000] flex items-center justify-center bg-slate-950/45 p-3 backdrop-blur-sm sm:p-4"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setModal(null);
          }}
          role="presentation"
        >
          <div
            className="flex max-h-[92dvh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-border-subtle-light bg-white shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="speaking-live-lesson-dialog-title"
          >
            <div className="flex shrink-0 items-center justify-between border-b border-border-subtle-light bg-surface-canvas-light/50 px-5 py-4">
              <div>
                <h2 id="speaking-live-lesson-dialog-title" className="font-extrabold text-on-surface">
                  {modal === "form"
                    ? editing
                      ? t.editTitle
                      : t.createTitle
                    : modal === "recording"
                      ? t.addRecording
                      : t.history}
                </h2>
                <p className="mt-1 text-xs text-text-secondary-light">
                  {modal === "form" ? t.timeZone : recordingLesson?.title}
                </p>
              </div>
              <button
                onClick={() => setModal(null)}
                className="rounded-lg px-3 py-2 text-text-secondary-light"
              >
                ✕ {t.close}
              </button>
            </div>
            {modal === "form" ? (
              <form
                onSubmit={saveLesson}
                className="flex min-h-0 flex-1 flex-col overflow-hidden"
              >
                <div className="grid min-h-0 flex-1 gap-4 overflow-y-auto p-5 sm:grid-cols-2">
                <label className="grid gap-1.5 text-xs font-bold text-on-surface sm:col-span-2">
                  {t.lessonTitle} *
                  <input
                    required
                    minLength={3}
                    maxLength={140}
                    value={form.title}
                    onChange={(event) =>
                      setForm({ ...form, title: event.target.value })
                    }
                    className="rounded-xl border border-border-subtle-light bg-surface-canvas-light px-3 py-2.5 text-sm"
                  />
                </label>
                <label className="grid gap-1.5 text-xs font-bold text-on-surface sm:col-span-2">
                  {t.topic}
                  <input
                    maxLength={240}
                    value={form.topic}
                    onChange={(event) =>
                      setForm({ ...form, topic: event.target.value })
                    }
                    className="rounded-xl border border-border-subtle-light bg-surface-canvas-light px-3 py-2.5 text-sm"
                  />
                </label>
                <label className="grid gap-1.5 text-xs font-bold text-on-surface">
                  {t.subject}
                  <select
                    value={form.subject}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        subject: event.target.value as FormValue["subject"],
                      })
                    }
                    className="rounded-xl border border-border-subtle-light bg-surface-canvas-light px-3 py-2.5 text-sm"
                  >
                    <option value="english">{t.english}</option>
                    <option value="russian">{t.russian}</option>
                  </select>
                </label>
                <label className="grid gap-1.5 text-xs font-bold text-on-surface">
                  {t.moderatorName}
                  <input
                    maxLength={100}
                    value={form.moderator_name}
                    onChange={(event) =>
                      setForm({ ...form, moderator_name: event.target.value })
                    }
                    className="rounded-xl border border-border-subtle-light bg-surface-canvas-light px-3 py-2.5 text-sm"
                  />
                </label>
                <label className="grid gap-1.5 text-xs font-bold text-on-surface sm:col-span-2">
                  {t.audienceLabel}
                  <input
                    maxLength={160}
                    value={form.audience_label}
                    onChange={(event) =>
                      setForm({ ...form, audience_label: event.target.value })
                    }
                    className="rounded-xl border border-border-subtle-light bg-surface-canvas-light px-3 py-2.5 text-sm"
                  />
                </label>
                <label className="grid gap-1.5 text-xs font-bold text-on-surface">
                  {t.starts} · {t.timeZone}
                  <input
                    required
                    type="datetime-local"
                    value={form.starts_at}
                    onChange={(event) =>
                      setForm({ ...form, starts_at: event.target.value })
                    }
                    className="rounded-xl border border-border-subtle-light bg-surface-canvas-light px-3 py-2.5 text-sm"
                  />
                </label>
                <label className="grid gap-1.5 text-xs font-bold text-on-surface">
                  {t.ends}
                  <input
                    required
                    type="datetime-local"
                    value={form.ends_at}
                    onChange={(event) =>
                      setForm({ ...form, ends_at: event.target.value })
                    }
                    className="rounded-xl border border-border-subtle-light bg-surface-canvas-light px-3 py-2.5 text-sm"
                  />
                </label>
                <label className="flex items-center justify-between gap-3 rounded-xl border border-border-subtle-light bg-surface-canvas-light p-3.5 sm:col-span-2">
                  <span className="flex items-center gap-2">
                    <span className="text-lg text-primary" aria-hidden="true">
                      ◉
                    </span>
                    <span>
                      <span className="block text-xs font-bold text-on-surface">
                        {roomText.label}
                      </span>
                      <span className="mt-0.5 block text-[11px] font-normal text-text-secondary-light">
                        {roomText.hint}
                      </span>
                    </span>
                  </span>
                  <input
                    type="checkbox"
                    checked={form.auto_open_video_room}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        auto_open_video_room: event.target.checked,
                      })
                    }
                    aria-label={roomText.label}
                  />
                </label>
                <fieldset className="grid gap-2 text-xs text-on-surface sm:col-span-2">
                  <legend className="mb-1 font-bold">{t.reminders}</legend>
                  {[
                    [1440, t.minute24],
                    [60, t.minute1],
                    [15, t.minute15],
                  ].map(([mins, label]) => (
                    <label key={mins} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={form.reminder_minutes.includes(Number(mins))}
                        onChange={(event) =>
                          setForm({
                            ...form,
                            reminder_minutes: event.target.checked
                              ? [...form.reminder_minutes, Number(mins)]
                              : form.reminder_minutes.filter(
                                  (item) => item !== Number(mins),
                                ),
                          })
                        }
                      />
                      {label}
                    </label>
                  ))}
                </fieldset>
                </div>
                <div className="flex shrink-0 justify-end border-t border-border-subtle-light bg-white px-5 py-4">
                  <button
                    disabled={busy === "save"}
                    type="submit"
                    className="rounded-xl bg-[#1736E8] px-5 py-2.5 text-sm font-bold text-white transition-colors hover:bg-[#1029B9] active:bg-[#0D238F] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1736E8] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {busy === "save" ? "…" : t.save}
                  </button>
                </div>
              </form>
            ) : modal === "recording" ? (
              <form onSubmit={attachRecording} className="grid min-h-0 gap-4 overflow-y-auto p-5">
                <label className="grid gap-2 text-sm font-bold text-on-surface">
                  {t.recordingUrl}
                  <input
                    required
                    type="url"
                    pattern="https://.*"
                    value={recordingUrl}
                    onChange={(event) => setRecordingUrl(event.target.value)}
                    placeholder="https://…"
                    className="rounded-xl border border-border-subtle-light bg-surface-canvas-light px-3 py-2.5 text-sm font-normal"
                  />
                </label>
                <p className="text-xs text-text-secondary-light">
                  {t.recent}: yozuv dars tugaganidan keyin 30 kun davomida ochiq
                  bo‘ladi.
                </p>
                <div className="flex justify-end">
                  <button
                    disabled={Boolean(busy)}
                    className="rounded-xl bg-[#1736E8] px-5 py-2.5 text-sm font-bold text-white transition-colors hover:bg-[#1029B9] active:bg-[#0D238F] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1736E8] focus-visible:ring-offset-2"
                  >
                    {t.save}
                  </button>
                </div>
              </form>
            ) : (
              <div className="min-h-0 overflow-y-auto p-5">
                {history.length ? (
                  <ol className="space-y-3">
                    {history.map((item, index) => (
                      <li
                        key={`${item.created_at}-${index}`}
                        className="rounded-xl border border-border-subtle-light bg-surface-canvas-light p-3"
                      >
                        <div className="flex justify-between gap-3 text-sm font-bold text-on-surface">
                          <span>{item.action}</span>
                          <time className="text-xs font-normal text-text-secondary-light">
                            {localDate(item.created_at, locale, {
                              dateStyle: "medium",
                              timeStyle: "short",
                            })}
                          </time>
                        </div>
                        <pre className="mt-2 whitespace-pre-wrap text-xs text-text-secondary-light">
                          {JSON.stringify(item.details || {}, null, 2)}
                        </pre>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="text-sm text-text-secondary-light">{t.none}</p>
                )}
              </div>
            )}
          </div>
        </div>, document.body)
        : null}
      {moderatingRoom ? (
        <LiveKitModeratorRoom
          roomId={moderatingRoom.id}
          title={moderatingRoom.title}
          apiFetch={apiFetch}
          onClose={() => setModeratingRoom(null)}
          onRoomEnded={() => {
            const lesson = lessons.find(
              (item) => item.room_id === moderatingRoom.id,
            );
            setModeratingRoom(null);
            if (lesson) void action(lesson.id, "complete", "complete");
            else void load();
          }}
        />
      ) : null}
    </section>
  );
}
