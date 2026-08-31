export type Role = "student" | "teacher" | "admin" | "support";

export const ROLE_LABELS: Record<Role, string> = {
  student: "Talaba",
  teacher: "O'qituvchi",
  admin: "Admin",
  support: "Support Teacher",
};

export const SUBJECT_OPTIONS = ["English", "Russian", "Matematika", "Ona tili", "Tarix", "Arab tili"] as const;
export const DEFAULT_SUBJECT_SUGGESTIONS = [...SUBJECT_OPTIONS];

export const LESSON_DAY_OPTIONS = [
  { value: "MWF", label: "Mon, Wed, Fri" },
  { value: "TTS", label: "Tue, Thu, Sat" },
];

export const LESSON_TIME_OPTIONS = [
  "08:00", "08:30", "09:00", "09:30", "10:00", "10:30",
  "11:00", "11:30", "12:00", "12:30", "13:00", "13:30",
  "14:00", "14:30", "15:00", "15:30", "16:00", "16:30",
  "17:00", "17:30", "18:00", "18:30", "19:00", "19:30",
  "20:00", "20:30", "21:00", "21:30", "22:00",
];

export const SUPPORT_WEEKDAY_OPTIONS = [
  { value: 0, label: "Dush" },
  { value: 1, label: "Sesh" },
  { value: 2, label: "Chor" },
  { value: 3, label: "Pay" },
  { value: 4, label: "Juma" },
  { value: 5, label: "Shan" },
];

export const DEFAULT_SECTIONS: Record<Role, string[]> = {
  student: [
    "home",
    "grammar",
    "vocabulary",
    "videos",
    "books",
    "daily-test",
    "daily-test-process",
    "gamified",
    "vocabulary-process",
    "arena",
    "arena-boss",
    "duel-1v1",
    "duel-3v3",
    "duel-5v5",
    "voice-rooms",
    "chats",
    "notifications",
    "dcoin",
    "gifts",
    "homework",
    "support",
    "attendance",
    "notes",
    "profile",
  ],
  teacher: ["home", "chats", "groups", "substitutions", "attendance", "performance", "students", "analytics", "dcoin", "homework", "materials", "kpi", "leaderboard", "videos", "books", "voice-rooms", "profile"],
  admin: ["home", "chats", "users", "groups", "family-groups", "payments", "purchases", "userbot", "homework", "leaderboard", "kpi", "competitions-history", "attendance", "analytics", "holidays", "generator", "videos", "books", "grammar", "courses", "results", "broadcasts", "surveys", "reviews", "gifts", "domain-email", "dpoint-settings", "sms", "admin-callbacks", "voice-rooms", "profile"],
  support: ["home", "chats", "bookings", "calendar", "attendance", "homework", "settings", "bonus", "schedule", "hours", "filial", "broadcast", "leaderboard", "videos", "books", "voice-rooms", "profile"],
};

export const HIDDEN_SECTION_IDS = new Set([
  "daily-test-process",
  "vocabulary-process",
  "arena-boss",
  "duel-1v1",
  "duel-3v3",
  "duel-5v5",
]);

// Daily and teacher-run group arenas are retired. This protects against a
// stale section list returned by an older client or backend response.
export const RETIRED_SECTION_IDS = new Set(["arena-daily", "arena-group", "arena"]);

export const SECTION_ALIAS: Record<string, string> = {
  dashboard: "home",
  daily: "daily-test",
  "daily-process": "daily-test-process",
  gamified: "gamified",
  "gamified-tests": "gamified",
  "vocabulary-process": "vocabulary-process",
  learn: "grammar",
  "boss-arena": "arena-boss",
  duel1v1: "duel-1v1",
  duel3v3: "duel-3v3",
  duel5v5: "duel-5v5",
  home: "home",
  chat: "chats",
  diamondvoy: "chats",
  chats: "chats",
  holiday: "holidays",
  holidays: "holidays",
  sms: "sms",
  userbot: "userbot",
  competitions: "competitions-history",
};

export const SECTION_LABELS: Record<string, string> = {
  home: "Boshqaruv paneli",
  grammar: "Grammatika Darslari",
  vocabulary: "Lug'at",
  videos: "Video Darslar",
  books: "Kutubxona",
  "daily-test": "Kunlik Test",
  "daily-test-process": "Kunlik Test Jarayoni",
  gamified: "Gamified Testlar",
  "vocabulary-process": "Lug'at Test Jarayoni",
  arena: "Arena va Duel",
  "arena-boss": "Boss Arena",
  "duel-1v1": "Duel 1v1",
  "duel-3v3": "Duel 3v3",
  "duel-5v5": "Duel 5v5",
  chats: "Chats",
  leaderboard: "Reyting",
  dcoin: "D'Coins",
  gifts: "Sovgalar",
  homework: "Homework",
  support: "Support Darsi Bronlari",
  holidays: "Holidays",
  courses: "Kurslar",
  results: "Natijalar",
  profile: "Mening Profilim",
  users: "Foydalanuvchilar",
  groups: "Guruhlar",
  "family-groups": "Family Groups",
  payments: "To'lovlar",
  purchases: "Xaridlar",
  userbot: "📲 Telegram Userbot",
  broadcasts: "Yuborishlar",
  broadcast: "Broadcast",
  surveys: "So'rovnomalar",
  reviews: "Sharhlar",
  attendance: "Davomat",
  "group-attendance": "Guruh davomati",
  tests: "Testlar",
  generator: "AI Generator",
  "dpoint-settings": "D'point / D'coin qoidalari",
  "domain-email": "Domen Email",
  performance: "Talaba natijalari",
  students: "Mening O'quvchilarim",
  bookings: "Bronlar",
  calendar: "Kalendar",
  schedule: "Dars kunlari",
  hours: "Soatlar",
  filial: "Filial",
  settings: "Sozlamalar",
  bonus: "Bonus",
  sms: "SMS Yuborish",
  "competitions-history": "Musobaqalar Tarixi",
  "admin-callbacks": "Arizalar",
  substitutions: "Vaqtinchalik O'qituvchi",
  analytics: "Analitika",
  "voice-rooms": "Voiceroom",
  materials: "Materiallar Kutubxonasi",
  kpi: "Mening KPI",
  notes: "Mening Notlarim",
};
