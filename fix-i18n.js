const fs = require('fs');

const FILE_PATH = '/home/xumoyun-maxkamov/Desktop/diamond-site/app/ui/web-i18n.tsx';
let content = fs.readFileSync(FILE_PATH, 'utf8');

const additions = {
  uz: `
    "landing.nav.videos": "Video darslar",
    "landing.videos.kicker": "Bepul Video Darslar",
    "landing.videos.pageTitle": "Platformamizdagi Video Darslar",
    "landing.videos.pageSubtitle": "Tajribali mentorlar tomonidan maxsus tayyorlangan video darsliklar va onlayn materiallar bilan ta'lim oling.",
    "videos.tabs.all": "Barcha Videolar",
    "videos.tabs.english": "Ingliz Tili",
    "videos.tabs.russian": "Rus Tili",
    "videos.categories.english.title": "Ingliz Tili Darslari",
    "videos.categories.english.subtitle": "General English, IELTS va grammatika bo'yicha video darslar",
    "videos.categories.russian.title": "Rus Tili Darslari",
    "videos.categories.russian.subtitle": "Rus tilida muloqot va grammatika qoidalari",
    "videos.notAvailable": "Video mavjud emas",
    "videos.playerError": "Video player yuklanmadi. Qayta urinib ko'ring.",
    "videos.officialChannel": "Rasmiy kanal",
    "videos.subscribe": "Obuna bo'lish",
    "videos.like": "Yoqdi",
`,
  ru: `
    "landing.nav.videos": "Видео уроки",
    "landing.videos.kicker": "Бесплатные видео уроки",
    "landing.videos.pageTitle": "Видео уроки на нашей платформе",
    "landing.videos.pageSubtitle": "Обучайтесь по специально подготовленным видеоматериалам от опытных менторов.",
    "videos.tabs.all": "Все видео",
    "videos.tabs.english": "Английский язык",
    "videos.tabs.russian": "Русский язык",
    "videos.categories.english.title": "Уроки английского языка",
    "videos.categories.english.subtitle": "Видео уроки по General English, IELTS и грамматике",
    "videos.categories.russian.title": "Уроки русского языка",
    "videos.categories.russian.subtitle": "Грамматика и общение на русском языке",
    "videos.notAvailable": "Видео недоступно",
    "videos.playerError": "Не удалось загрузить видео плеер. Попробуйте снова.",
    "videos.officialChannel": "Официальный канал",
    "videos.subscribe": "Подписаться",
    "videos.like": "Нравится",
`,
  en: `
    "landing.nav.videos": "Video lessons",
    "landing.videos.kicker": "Free Video Lessons",
    "landing.videos.pageTitle": "Video Lessons on our platform",
    "landing.videos.pageSubtitle": "Learn with specially prepared video materials from experienced mentors.",
    "videos.tabs.all": "All Videos",
    "videos.tabs.english": "English",
    "videos.tabs.russian": "Russian",
    "videos.categories.english.title": "English Lessons",
    "videos.categories.english.subtitle": "Video lessons for General English, IELTS and grammar",
    "videos.categories.russian.title": "Russian Lessons",
    "videos.categories.russian.subtitle": "Russian grammar and communication",
    "videos.notAvailable": "Video not available",
    "videos.playerError": "Video player failed to load. Please try again.",
    "videos.officialChannel": "Official channel",
    "videos.subscribe": "Subscribe",
    "videos.like": "Like",
`
};

for (const lang of ['uz', 'ru', 'en']) {
  const regex = new RegExp('(\\\\b' + lang + '\\\\s*:\\\\s*\\{)');
  content = content.replace(regex, '$1' + additions[lang]);
}

fs.writeFileSync(FILE_PATH, content);
console.log("Updated i18n file.");
