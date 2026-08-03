export type GrammarFallbackPayload = {
  topicId?: string;
  title?: string;
  subject?: string;
  level?: string;
  questionCount?: number;
};

export type GrammarResolvedContent = {
  title: string;
  rule: string;
  questionsPreview: Array<{ prompt: string; options: string[] }>;
};

type GrammarRuleEntry = {
  id?: string;
  subject: "English" | "Russian";
  levels: string[];
  title: string;
  keywords: string[];
  rule: string;
  questionsPreview: Array<{ prompt: string; options: string[] }>;
};

const ENGLISH_RULES: GrammarRuleEntry[] = [
  {
    subject: "English",
    levels: ["A1", "A2"],
    title: "Present Simple",
    keywords: ["present simple", "simple present"],
    rule: "Present Simple odat, fakt va jadval bo'yicha doimiy holatlar uchun ishlatiladi. Tuzilishi: I/You/We/They + V1, He/She/It + V1+s/es. Inkor: do/does not + V1. So'roq: Do/Does + ega + V1?",
    questionsPreview: [
      { prompt: "She ___ to school every day.", options: ["go", "goes", "going", "gone"] },
      { prompt: "___ they play football on Sundays?", options: ["Do", "Does", "Did", "Are"] },
    ],
  },
  {
    subject: "English",
    levels: ["A1", "A2"],
    title: "Present Continuous",
    keywords: ["present continuous", "present progressive"],
    rule: "Present Continuous hozir ayni paytda davom etayotgan harakat uchun ishlatiladi. Tuzilishi: am/is/are + V-ing. Signal so'zlar: now, at the moment, currently.",
    questionsPreview: [
      { prompt: "I ___ a book now.", options: ["read", "am reading", "reads", "reading"] },
      { prompt: "They ___ TV at the moment.", options: ["watch", "watched", "are watching", "watches"] },
    ],
  },
  {
    subject: "English",
    levels: ["A1", "A2", "B1"],
    title: "Past Simple",
    keywords: ["past simple", "simple past"],
    rule: "Past Simple o'tgan zamondagi tugallangan harakatni bildiradi. Regular fe'llar -ed qo'shimchasi oladi, irregular fe'llar 2-shaklga o'tadi. Inkor: did not + V1. So'roq: Did + ega + V1?",
    questionsPreview: [
      { prompt: "We ___ to Samarkand last year.", options: ["go", "went", "gone", "going"] },
      { prompt: "He did not ___ the task.", options: ["finished", "finish", "finishes", "to finish"] },
    ],
  },
  {
    subject: "English",
    levels: ["A2", "B1"],
    title: "Future Simple",
    keywords: ["future simple", "will"],
    rule: "Future Simple kelajakdagi reja yoki qarorni bildiradi. Tuzilishi: will + V1. Inkor: will not (won't) + V1. So'roq: Will + ega + V1?",
    questionsPreview: [
      { prompt: "I ___ call you tonight.", options: ["will", "am", "did", "have"] },
      { prompt: "___ she come tomorrow?", options: ["Does", "Will", "Is", "Did"] },
    ],
  },
  {
    subject: "English",
    levels: ["B1", "B2"],
    title: "Present Perfect",
    keywords: ["present perfect", "have has", "since", "for"],
    rule: "Present Perfect o'tmishda boshlangan va hozirga aloqasi bo'lgan harakat uchun. Tuzilishi: have/has + V3. Signal so'zlar: already, yet, just, since, for.",
    questionsPreview: [
      { prompt: "She ___ her homework already.", options: ["did", "has done", "does", "is doing"] },
      { prompt: "They have lived here ___ 2020.", options: ["for", "since", "at", "in"] },
    ],
  },
  {
    subject: "English",
    levels: ["B1", "B2"],
    title: "Modal Verbs",
    keywords: ["modal", "can", "must", "should", "might"],
    rule: "Modal fe'llar (can, must, should, may, might)dan keyin fe'lning asosiy shakli (V1) keladi. Modal fe'llar majburiyat, imkoniyat, maslahat va ehtimolni bildiradi.",
    questionsPreview: [
      { prompt: "You ___ wear a seatbelt.", options: ["must", "must to", "are", "can to"] },
      { prompt: "He ___ be at home, I'm not sure.", options: ["might", "must", "can", "should"] },
    ],
  },
  {
    subject: "English",
    levels: ["B1", "B2", "C1"],
    title: "Passive Voice",
    keywords: ["passive", "voice"],
    rule: "Passive Voice'da e'tibor harakat bajaruvchisiga emas, obyektga qaratiladi. Tuzilishi: be (zamonga mos) + V3. Masalan: The letter was written yesterday.",
    questionsPreview: [
      { prompt: "The room ___ every day.", options: ["cleans", "is cleaned", "cleaned", "was clean"] },
      { prompt: "The project ___ last week.", options: ["finished", "was finished", "is finish", "has finishing"] },
    ],
  },
  {
    subject: "English",
    levels: ["B1", "B2", "C1"],
    title: "Conditionals",
    keywords: ["conditional", "if clause", "if"],
    rule: "Conditionals: Zero (if + present, present), First (if + present, will + V1), Second (if + past simple, would + V1), Third (if + past perfect, would have + V3).",
    questionsPreview: [
      { prompt: "If it rains, we ___ at home.", options: ["stay", "will stay", "stayed", "would stay"] },
      { prompt: "If I were you, I ___ this course.", options: ["take", "will take", "would take", "took"] },
    ],
  },
  {
    subject: "English",
    levels: ["A1", "A2", "B1"],
    title: "Articles",
    keywords: ["article", "a an the"],
    rule: "A/an noaniq birlik otlar uchun, the esa aniq yoki oldindan ma'lum narsalar uchun ishlatiladi. Uncountable yoki umumiy ma'noda article ishlatilmasligi mumkin.",
    questionsPreview: [
      { prompt: "I saw ___ elephant at the zoo.", options: ["a", "an", "the", "-"] },
      { prompt: "___ sun rises in the east.", options: ["A", "An", "The", "-"] },
    ],
  },
];

const RUSSIAN_RULES: GrammarRuleEntry[] = [
  {
    subject: "Russian",
    levels: ["A1", "A2"],
    title: "Russian Basics",
    keywords: ["russian", "alphabet", "basics", "основ", "грамматик"],
    rule: "Rus tili A1 asoslari: ot jinslari (мужской/женский/средний), shaxs olmoshlari (я, ты, он/она, мы, вы, они), hozirgi zamon fe'l tuslanishi va oddiy gap tartibi.",
    questionsPreview: [
      { prompt: "Выберите местоимение 1-го лица ед. числа.", options: ["ты", "я", "мы", "они"] },
      { prompt: "Он ___ студент.", options: ["есть", "это", "был", "будет"] },
    ],
  },
];

const ALL_RULES = [...ENGLISH_RULES, ...RUSSIAN_RULES];

function norm(value: string) {
  return String(value || "").trim().toLowerCase();
}

export function resolveGrammarContent(input: GrammarFallbackPayload): GrammarResolvedContent | null {
  const subject = norm(input.subject || "English");
  const level = norm(input.level || "A1");
  const title = norm(input.title || "");
  const topicId = norm(input.topicId || "");

  const byId = ALL_RULES.find((entry) => entry.id && norm(entry.id) === topicId);
  if (byId) {
    return {
      title: byId.title,
      rule: byId.rule,
      questionsPreview: byId.questionsPreview,
    };
  }

  const scoped = ALL_RULES.filter((entry) => norm(entry.subject) === subject && entry.levels.map(norm).includes(level));
  const byKeyword = scoped.find((entry) => entry.keywords.some((keyword) => title.includes(norm(keyword))));
  if (byKeyword) {
    return {
      title: byKeyword.title,
      rule: byKeyword.rule,
      questionsPreview: byKeyword.questionsPreview,
    };
  }

  const firstBySubjectLevel = scoped[0];
  if (firstBySubjectLevel) {
    return {
      title: firstBySubjectLevel.title,
      rule: firstBySubjectLevel.rule,
      questionsPreview: firstBySubjectLevel.questionsPreview,
    };
  }

  return null;
}
