# Diamond Site - Loyiha Strukturasi va Qisqacha Dokumentatsiya

Ushbu hujjat loyihaning asosiy fayllari va ularning vazifalari haqida ma'lumot beradi. Keyinchalik qidirish jarayonlarini tezlashtirish va kodni oson tushunish maqsadida yaratildi.

## Backend (API va Ma'lumotlar bazasi)

1. **`backend/main.py`**
   - Asosiy FastAPI server fayli. Barcha API marshrutlari (endpoints) shu yerda joylashgan.
   - **Guruhlar boshqaruvi (`/admin/groups`, `/groups`)**: Guruh yaratish, tahrirlash, o'quvchilarni qo'shish/o'chirish.
   - **Kurslar bilan bog'lanish**: Guruhni ochganda unga kurs biriktiriladi (`course_id`).
   - **Narxlash (`pricing_type`) mantiqi**: Guruh to'lovi guruh yoki individual ekanligini bildiradi. `main.py` da `pricing_type` ga qarab `monthly_fee_text` uchun `price_text` (guruh) yoki `individual_price_text` (individual) olinadi. 
   - **To'lovlar**: `_payment_generate_due_invoice_for_student` funksiyasi ham `pricing_type` dan foydalanib to'g'ri narxda schyot yaratadi.
   - **Xavfsizlik / Validatsiya**: O'quvchilarni guruhga qo'shishda `joined_at` (sana) kiritilishi majburiy qilingan (bo'lmasa HTTP 400 qaytadi).

2. **`db.py`**
   - Ma'lumotlar bazasi (SQLite yoki PostgreSQL) ulanishlari, jadvallar yaratish (schema) va CRUD operatsiyalarini o'z ichiga oladi.
   - **`create_group`**: Guruh yaratish funksiyasi. `pricing_type`, `course_id` kabi maydonlarni `groups` jadvaliga yozadi.
   - **Migratsiyalar**: Jadvalga yangi ustun qo'shish kerak bo'lganda (`pricing_type`, `telegram_group_url` va h.k.) `ensure_group_extra_subjects_schema()` kabi funksiyalar bilan tekshirilib qo'shiladi.
   - **Jadvallar**: `groups`, `test_results`, `attendance`, `web_courses` va boshqalar.

## Frontend (Next.js - UI)

1. **Voice Room (Ovozli Xona)**
   - **`app/ui/voice-room/GlobalVoiceRoomContext.tsx`**: Ovozli xonaning markaziy holati va logikasi (WebRTC streamlari).
     - *Echo Cancellation (Aks sado bekor qilish)*: `echoCancellationType: 'browser'` orqali boshqariladi.
     - *Audio Routing & Boost (Dinamik)*: Telefonda ovoz balandroq (dinamikda) chiqishi uchun `AudioContext` va `GainNode` (x4 balandlik) ishlatilgan. Shuningdek media streamlarni to'g'ri ulash uchun logika bor.
   - **`app/ui/voice-room/student-voice-room.tsx` & `moderator-voice-room.tsx`**: Ovozli xonaning ko'rinishi. 4 ta foydalanuvchiga moslangan `grid-cols-2` orqali dizayn qilingan.

2. **Guruhlar va O'quvchilar UI**
   - **`app/page.tsx`** (yoki o'quvchilarni guruhga qo'shadigan boshqa modal/sahifalar): O'quvchini guruhga qo'shayotganda "Qo'shilgan sana" (`joined_at`) kiritilmagan bo'lsa, xatolik beruvchi (Toast xabarnomasi) validatsiya UI tomonida qilingan.

## Muhim terminlar

- **`pricing_type`**: `group` yoki `individual` qiymatini qabul qiladi. Bu guruh o'ziga biriktirilgan kursning qaysi narxini (umumiy kurs narxi yoki individual dars narxi) ishlatishini belgilaydi.
- **`joined_at`**: O'quvchi guruhga qachon qo'shilganligi sanasi. To'lovlar yoki davomat shu sanaga qarab to'g'ri hisoblanadi.

## So'nggi o'zgarishlar va tuzatishlar

- **Guruh ma'lumotlarini yangilash API (PATCH)**: `db.py` dagi `update_group_course_details` funksiyasiga yangi qo'shilgan `telegram_group_url` va `pricing_type` argumentlari etishmayotganligi sababli guruhni saqlashda xatolik ("Serverda xatolik yuz berdi") chiqayotgan edi. Ushbu argumentlar funksiyaga va tegishli SQL so'roviga qo'shilib, tuzatildi.
- **Dinamik narx ko'rsatish**: Guruh yaratish va tahrirlash oynalarida "To'lov turi" qismida shunchaki "Guruh narxi" yozuvi o'rniga, tanlangan kursning aynan joriy narxi ko'rinishi (masalan, "Guruh narxi (400 000 UZS)") ta'minlandi. Buning uchun `app/page.tsx` faylidagi dropdown `activeCourse` ma'lumotlaridan foydalangan holda dinamik tarzda yangilanadigan qilindi.

- **Voice Room sheriklarining ismlari**: O'quvchi uy vazifasi panelida ovozli xonaga kirish oynasida (popup) sheriklarning ismi o'rniga "Student 1", "Student 2" deb chiqib qolish xatosi tuzatildi. Buning sababi, `web_homework_voiceroom_groups` jadvalida ismlar emas, faqat foydalanuvchi ID lari saqlanardi. Shuning uchun ma'lumot olish so'rovlari (`db.py` va `backend/main.py` dagi so'rovlar) `users` jadvali bilan `LEFT JOIN` qilinib, to'g'ri ismlar olinishi ta'minlandi.
- **Admin Voice Room boshqaruvi**: Adminlar (moderatorlar) ovozli xonaga (Voice Room) kirganda endi sahnaga chiqish uchun ruxsat so'rashi kerak bo'lmaydi. Ular xonaga kirishi bilan avtomatik tarzda sahnaga qo'shiladi va mikrofonlari yoqiq holatda bo'ladi. Ular to'g'ridan-to'g'ri mikrofonni o'chirib-yoqishlari va sahnani boshqarishlari mumkin. (`backend/main.py` da `my_role == "admin"` uchun sahnaga avto-qo'shish mantig'i qo'shildi). Adminlarning xonadagi ishtiroki qolganlarga ko'rinmasligi (Arvoh / Ghost rejimi avtomatik yoqilishi) ham qo'shildi.

### UI va Dizayn Yaxshilanishlari:
- **Voice Room Sahna (Stage) o'zgarishi** (`app/ui/voice-room/student-voice-room.tsx`): Ovozli xonada qatnashchilar (speakerlar) sahnada 2x2 shaklida emas, balki bir qatorda 4x1 (`grid-cols-4`) bo'lib chiqishi ta'minlandi va mobil qurilmalarga moslashtirildi. 
- **Reaksiya animatsiyalari** (`app/ui/voice-room/student-voice-room.tsx`): Reaksiya emojilari tez uchib o'tmasligi va sakramasligi uchun `@keyframes floatBubble` ichida CSS animatsiyasi tezligi `4s` (avvalgi `2.5s`) ga uzaytirildi va `ease-out` bilan silliq ishlashi ta'minlandi.
- **iOS va Mobil brauzerlarda menyu ko'rinishi** (`app/ui/voice-room/student-voice-room.tsx`): Mobil qurilmalarda Voice Room sahifasiga kirilganda, pastki navigatsiya paneli teginilgandan keyingina ko'rinadigan xato tuzatildi. Bosh konteynerga `h-[100dvh]` balandlik, pastki menyuga esa `fixed bottom-0` xususiyatlari qo'shildi.

### Homework Voice Room Avtomatizatsiyasi
- **Avtomatik Yozib olish (Auto-Recording)** (`app/ui/voice-room/student-voice-room.tsx`): Foydalanuvchilar kirishi bilan `useEffect` kodi `roomState.stagePeers.length >= 2` ni tekshiradi va avtomatik tarzda `startRecording()` ni ishga tushiradi. Oldingi manual "Yozishni boshlash" tugmasi o'rniga dinamik indikator ko'rsatiladi.
- **Avtomatik Topshirish (Auto-Submit)** (`app/ui/voice-room/student-voice-room.tsx`): Suhbat yakunlanib o'quvchi xonadan chiqqanida to'g'ridan-to'g'ri chiqib ketmaydi. `handleLeaveRoom` funksiyasi chaqirilib, avval `stopRecordingAndUpload(hwId)` ishga tushadi, ekranda aylanuvchi oyna ("Vazifa topshirilmoqda...") chiqadi va audio yuklangach lobbiga qaytaradi.
- **BeforeUnload Ogohlantirishi** (`app/ui/voice-room/student-voice-room.tsx`): Agar o'quvchi xonadan chiqish tugmasi o'rniga brauzerni yopib yubormoqchi bo'lsa, `window.addEventListener("beforeunload", ...)` orqali "Hali audio topshirilmadi" ogohlantirishi (Confirm Modal) chiqishi joriy qilindi.
- **Baza (Database) tuzatishlari** (`db.py` va `backend/main.py`):
  - `db.py` -> `upsert_homework_submission()`: O'quvchi avval kirib chiqqani sababli "pending" statusida qator mavjud bo'lsa, avvalgi kod uni yangilamas edi (shunchaki `existing` ni qaytarib yuborardi). Endi u yerda mavjud bo'lsa `UPDATE web_homework_submissions SET status=?, voice_message_url=? ...` orqali to'g'ridan to'g'ri yangilanadigan qilib to'g'rilandi.
  - `backend/main.py` -> `student_submit_voiceroom_homework()` (API endpoint: `/student/homework/{homework_id}/submit-voiceroom`): Guruh talabalarini DB dan olayotganda lug'at (dictionary) ustidan noto'g'ri iteratsiya sababli ID lar olinmayotgan edi. `vg.values()` orqali faqat raqamli ID lar filtrlanishi va hamma qatnashuvchilar uchun `upsert_homework_submission` chaqirilishi ta'minlandi.

### Admin Anonim So'rovnomalar (Anonymous Surveys)
- **Tizim vazifasi**: Adminlar Google Forms ga o'xshash anonim so'rovnomalar tayyorlab, ularni Telegram bot (Broadcast) orqali yubora olishadi. Talabalar uni MiniApp da yechadilar, admin esa panelda kim qaysi savolga qanday javob berganini aniq ko'radi.
- **Backend (API + Baza)**: Fayl: `backend/main.py`
  - `web_surveys` (so'rovnomalar) va `web_survey_responses` (javoblar) jadvallari mavjud.
  - `/admin/surveys` (GET, POST): So'rovnomalar ro'yxatini olish va yangi yaratish.
  - `/admin/surveys/{survey_id}/results` (GET): So'rovnoma bo'yicha barcha javoblarni tortish. (Xatoliklarning oldini olish maqsadida bu yerda sanalar string ga o'girilib yuboriladi).
  - `/survey/{survey_id}` (GET, POST): Talabalar so'rovnomani to'ldirishi va uning ma'lumotlarini yuklashi (frontend MiniApp orqali ishlatadi).
- **Frontend (UI)**:
  - **`app/ui/admin-surveys.tsx`**: Admin panelda so'rovnoma yaratish, tuzilgan so'rovnomalar ro'yxatini ko'rish, "Linkni nusxalash" va "Natijalar"ni ko'rish qismi. Bu yerda so'nggi yangilanishlarga ko'ra: havola nusxalaganda avtomatik ravishda `.com` o'rniga `.uz` domeni (`https://diamond-education.uz/?startapp=survey_{id}`) nusxalanadi va natijalar panelidagi noto'g'ri `JSON.parse` sababli yuzaga keladigan xatolik (UI Crash) to'liq to'g'irlangan (qator: 170-190 atrofida).
  - **`app/ui/student-survey.tsx`**: Talabalar uchun Telegram MiniApp oynasi. 
  - **`app/page.tsx`** (qator: 21200 atrofida): So'rovnoma havolasi (`?startapp=survey_{id}`) Telegram botdan oddiy brauzer orqali ochilganda ham to'g'ri URL parametrlarini tutib olib (URLSearchParams), to'g'ridan to'g'ri `student-survey.tsx` ni ko'rsatadi.

### Universal Ommaviy Xabarlar (Broadcast System)
- **Tizim vazifasi**: Adminlar va O'qituvchilar Web Panel orqali Telegram botdan o'quvchilar va boshqalarga ommaviy xabar yuborishi mumkin. Tugma matni va havolasini ham qo'sha oladi (masalan, so'rovnoma linki).
- **Backend (API)**: Fayl: `backend/main.py`
  - `BroadcastCreateRequest` (qator: 1761): API ga keluvchi so'rov modeli. Unda `button_type` (auto, regular, webapp) maydoni mavjud.
  - `/admin/broadcasts` (GET, POST - qator: 40050 atrofida): Xabarni bazaga (status='queued') qo'shadi. POST so'rovda admin tanlagan tugma turi (`button_type`) asinxron `_run_broadcast_job` ga uzatiladi.
  - `_run_broadcast_job` (qator: 2994): Xabarni fonga navbatga qo'yadi va yuborishni amalga oshiradi. U har bir foydalanuvchiga Telegram limitidan o'tmaslik uchun `_send_telegram_text` ni chaqiradi. Shuningdek DB dagi holatni (sent, failed, skipped count) yangilab boradi.
  - `_send_telegram_text` (qator: 2811): Barcha Telegram API orqali xat jo'natishlar uchun javobgar funksiya. Bu funksiyada `button_web_app` qabul qilinib, "Tugma turi" bo'yicha to'g'ri Inline Keyboard (`url` yoki `web_app: {url}`) yaratiladi. Agar "Avtomatik" tanlansa, domen tekshirilib (`diamond-education.uz` yoki `?startapp=`), u Web App hisoblanadi.
- **Frontend (UI)**:
  - **`app/ui/admin-broadcasts.tsx`**: Admin panelda ommaviy xabar yuborish interfeysi (state va UI). Yaqinda qo'shilgan **"Tugma turi"** (Avtomatik, Oddiy havola, Telegram Mini App) selektori orqali (qator: 98 atrofida) ma'lumot backend ga jo'natiladi.
  - O'sha fayldagi `AdminBroadcastsPanel` jadvali `/admin/broadcasts` GET so'roviga tayanib, jonli tarzda Xabarlar tarixini ko'rsatib boradi. Avval bu jadval eski koddagi takrorlangan va ishlamaydigan qism bo'lib qolib ketgan edi va to'liq almashtirildi.
- **Telegram Bot Python qismi**: Fayl: `broadcast_system.py`
  - Xabarlar tizimining eski asinxron scripti. U yerdagi `_create_inline_keyboard` ham `.uz` domenidagi havolalarni avto Web App ga aylantirish logikasiga ega qilib to'g'irlangan.
### Multi-language Support (Ko'p tilli qo'llab-quvvatlash)
- **Kurslar sahifasida va Karuselida**: `app/courses/page.tsx` dagi (va uning tarkibidagi `app/ui/subject-courses-grid.tsx`) hamda `app/page.tsx` dagi `LandingCoursesCarousel` komponentlarida kurs ma'lumotlari (`title` va `description`) faqat bitta (default) tilda ko'rsatilayotgan edi. Endilikda `useWebLocale()` ishlatilib, api-dan qaytgan `title_uz`, `title_ru`, `title_en` kabi maydonlar UI da foydalanuvchining joriy tiliga asosan dinamik ravishda (`course[\`title_${locale}\`] || course.title`) tanlanishi ta'minlandi. Bu o'zgarish orqali UI da tilni o'zgartirganda sahifani qayta yuklamasdan ham zudlik bilan kurs ma'lumotlari tegishli tilda chiqadi.
### Ishlash Tezligini Oshirish (Performance Optimization)
- **Dashboard Ma'lumotlari Sekin Yuklanishi (Dashboard Lag Fix)**: 
  - **Muammo**: Admin va talabalar dashboardida statistikani (`get_student_monthly_stats`) ko'rsatishda sahifalar qotib qolishi kuzatilgan. Buning asosiy sababi jadvallarda (xususan `test_history`, `grammar_attempts`, `diamond_history`) to'g'ri indekslar mavjud emasligi va to'liq jadval bo'ylab qidiruv (Full Table Scan) amalga oshirilgani bo'lgan.
  - **Yechim (Funksiyalar va fayllar)**: 
    - `backend/main.py`: `_ensure_admin_perf_indexes` funksiyasi ichida nafaqat student, balki **Teacher (O'qituvchi)** va **Support (Qo'llab-quvvatlash)** dashboardlarini tezlashtirish maqsadida qo'shimcha indekslar qo'shildi: `web_homework_submissions(status)`, `daily_test_attempts(status, test_date, user_id)` va hokazo. Ushbu indekslar `_daily_test_history_for_student_ids` (teacher dashboard) va uy vazifasi statistikalari uchun Full Table Scan oldini oladi.
    - `db.py`: Yuqoridagi indekslarni yaratish tezroq ishlashi uchun to'g'ridan-to'g'ri `get_student_monthly_stats`, `support_dashboard_metrics`, hamda boshqa ma'lumot qidiradigan SQL funksiyalar chaqiriladigan joyga ta'sir qildi. Barcha rollar (student, teacher, support) endi dashboardda qotishlarsiz ishlaydi.
- **Frontend Dashboard Keshlash (Instant Load / Zero-Second Load)**:
  - **Muammo**: O'quvchilar, o'qituvchilar, support va admin sahifaga kirganda ma'lumotlar serverdan kelgunicha "kutish (spinner)" aylanishiga to'g'ri kelardi.
  - **Yechim (Fayl: `app/page.tsx`)**:
    - **O'quvchi (Student)** roliga `/student/overview?scope=dashboard` API so'rovi qo'shilgan va uning natijasi `localStorage` (`diamond_app_state_cache_{id}`) da saqlanadi. Dastur ochilishi bilan UI shu keshdan o'zini tiklaydi va yangi ma'lumot kelganda fonga (background) yangilanadi.
    - **Admin va O'qituvchi (Teacher)** rollarining asosiy ekranlari (`/admin/analytics`, `/teacher/analytics`) alohida state-larga ega. Ular ham endi `localStorage` (`diamond_admin_analytics_cache` va `diamond_teacher_analytics_cache`) orqali xuddi shunday instant-load qilinadi.
    - **Qo'llab-quvvatlash (Support)** dashboard statistikasi `appState.support.metrics` ichidan, ya'ni `boot` payload orqali olinadi. O'quvchilarda `boot` da statistika bo'lmagani uchun uni kesh qilish to'xtatib qo'yilgan edi. Endi `app/page.tsx` dagi (20360, 20455-qatorlar atrofida) shartlar o'zgartirilib, admin/teacher/support kabi roldagilar uchun `boot` holati keshlanadigan qilindi va support dashboard ham darhol ochiladigan bo'ldi.

### Admin Panel O'zgarishlari
- **Admin Foydalanuvchilar Ro'yxati (Admin Users Panel)**:
  - **Fayl**: `app/page.tsx`
  - **Holat**: Admin foydalanuvchilar ro'yxatidagi (users list) bitta sahifadagi foydalanuvchilar soni (pagination limit) oldin 40 ta etib belgilangan edi.
  - **Yechim**: Foydalanuvchilarni qulayroq izlash uchun `/admin/users` API chaqirig'idagi `params.set("limit", "40")` kod `100` ga o'zgartirildi.
  - **Pagination UI**: `userPageSize` lokal o'zgaruvchisi ham `40` dan `100` ga o'zgartirildi. Frontend jadvalining pasida sahifalash (pagination) vizual qismi joylashgan bo'lib, ushbu kod o'zgarishi sahifalanish raqamlarini to'g'ri hisoblab (100 tadan) pagination logikasini avtomatik moslashtiradi.
- **Broadcast Xabarlar Tarixi (Broadcast History)**:
  - `backend/main.py` da `/admin/broadcasts` API orqali keladigan xabarlar tarixida faqatgina haqiqiy broadcastlar ko'rinadigan qilindi. Endi o'quvchilar tomonidan yuborilgan "Taklif va Shikoyat" xabarlari (Taklifni ochish) aralashib ketmaydi.
- **So'rovnomalar Natijasi Xatoligi (Survey Results Error)**:
  - "Natijalarni ko'rish" bosilganda serverda (API `500 Error`) yuzaga kelayotgan xatolik to'g'irlandi. (Bunga sabab `users` jadvalidan mavjud bo'lmagan `full_name` ustunini qidirayotgani edi).
  - So'rovnoma natijalari sahifada pastga tushib ketmasdan, endi chiroyli markaziy **Popup (Modal) Oyna** orqali ko'rsatilishi ta'minlandi (`app/ui/admin-surveys.tsx`).

### Bot O'zgarishlari
- **Oylik Mavsum Xabarlarini O'chirish (Monthly Season Leaderboard)**:
  - `student_bot.py` da o'quvchilarga har oyning oxirida (soat 20:00 da) avtomatik tarzda jo'natiladigan `"🏆 2026-06 — Russian D'coin season leaderboard (Top-10)"` va unga qo'shilib ketadigan yakuniy oylik statistika xabarlari (season_end_scheduler) to'liq o'chirib tashlandi. Bu vazifa (task) tizimdan to'liq uzib qo'yildi.

### Public Landing va Natijalar Sahifasi O'zgarishlari
- **Landing hero ichidagi review olib tashlandi**:
  - **Fayl**: `app/ui/hero-section.tsx`
  - Hero section endi `testimonial` prop qabul qilmaydi va hero ichida review card chiqarmaydi. Ichki navigatsiya linklari `next/link` orqali ishlaydi.
  - Hero birinchi CTA tugmasi `/login` ga boradigan i18n `common.login` matniga almashtirilgan. Ikkinchi CTA `landing.hero.resultsCta` orqali tarjima qilinadi.
- **Reviewlar FAQ oldiga ko'chirildi**:
  - **Fayl**: `app/page.tsx`
  - `PublicLandingScreen` ichida `/reviews/public` dan kelgan reviewlar endi video darslar carouselidan keyin, FAQ sectionidan oldin kichik cardli carousel sifatida chiqadi.
  - Shu joyni topish uchun `REVIEWS` commentini, `LandingReviewsCarousel` komponentini yoki `landing-reviews-carousel-*` klasslarini qidirish mumkin.
  - Faqat nomi bor o'quvchi reviewlari ko'rsatiladi; bo'sh nom yoki `Diamond User` fallbackli reviewlar landingda chiqarilmaydi.
  - Review section matnlari `landing.reviews.*` i18n kalitlariga bog'langan.
- **Landing va natijalar kartalarida universitet rasmlari gallery kabi ishlaydi**:
  - **Fayl**: `app/ui/result-card.tsx`
  - `getResultAllMedia()` universitetga bir nechta rasm yuklanganda ularni kartada horizontal snap slider sifatida ko'rsatadi.
  - Kartadagi media bloki `aspect-[3/4]` bilan barqaror o'lchamda turadi, shuning uchun rasm balandligi har xil bo'lsa ham layout sakramaydi.
  - Universitet natijalari kartalarida screenshotdagi dublikat `Grant` va `Universitet` pill-lari yashirilgan; to'liq ma'lumot faqat detail sahifada chiqadi.
- **Natija tafsiloti Uzum-style galleryga o'tkazildi**:
  - **Fayl**: `app/results/[id]/page.tsx`
  - Natija ochilganda asosiy media chap tomonda sticky gallery sifatida turadi. Barcha `image_url` va `media` elementlari bitta `galleryMedia` ro'yxatiga yig'iladi.
  - Pastda alohida "Qo'shimcha Media" grid endi yo'q; rasm/video almashish thumbnail carousel, chap/o'ng tugmalar va dot indikatorlar orqali qilinadi.
  - Rasm bosilganda fullscreen preview ochiladi.
  - Mobil ekranda asosiy rasm `sticky top-20` bilan joyida qoladi va pastdagi tafsilotlarni scroll qilganda rasm birga oqib ketmasligi uchun max balandlik `58svh` bilan cheklangan.
- **Universitet natijasi tafsilotlari to'liq chiqariladi**:
  - **Fayl**: `app/results/[id]/page.tsx`
  - `detailRows` ichida admin kiritadigan asosiy maydonlar ko'rsatiladi: talaba, natija turi, sana, universitet nomi, universitet turi, davlat, shahar, grant foizi va tavsif.
  - Universitet detail sahifasida yuqoridagi type/university chip qatori va alohida "Umumiy natija" grant boxi yashirilgan, chunki shu ma'lumotlar detail gridda bor.
  - Sana ko'rsatishda `exam_date` bo'sh kelsa `updated_at` yoki `created_at` fallback ishlatiladi, shuning uchun admin sana kiritgan yoki eski natijada vaqt maydoni bor bo'lsa `-` chiqmaydi.
  - Detail sahifasidagi matnlar `public.results.*`, `admin.results.*`, `common.*` i18n kalitlariga bog'langan.
  - Admin tarafdagi kiritish formasi hali ham `app/page.tsx` ichidagi `AdminResultsPanel` komponentida turadi (`universityName`, `universityScope`, `universityCountry`, `universityCity`, `grantPercent`, `examDate`, `description`, `mediaUrls` state-lari).

### Public Sahifalar i18n Tuzatishlari
- **Kurslar sahifasi**:
  - **Fayl**: `app/courses/page.tsx`
  - Header `kicker/title/subtitle`, qidiruv placeholderi, empty state va fan filterlari i18n qilindi.
  - Fan nomlari `public.subject.*` kalitlari orqali chiqadi.
  - Kurs group title tarjimasi `app/ui/subject-courses-grid.tsx` ichida `tt(\`public.subject.${group.title}\`)` orqali ishlaydi.
- **Kurs detail sahifasi**:
  - **Fayl**: `app/courses/[id]/page.tsx`
  - Kurs nomi va tavsifi joriy tilga qarab `title_uz/title_ru/title_en` va `description_uz/description_ru/description_en` maydonlaridan olinadi.
  - Back button, status, narx labeli, enroll/contact tugmalari, empty/error/no-image holatlari `courses.detail.*`, `courses.page.loadError`, `common.*` kalitlari orqali tarjima qilinadi.
- **Video darslar sahifasi**:
  - **Fayl**: `app/videos/page.tsx`
  - Video card subject badge `public.subject.*` orqali tarjima qilinadi.
  - Fallback video title `videos.defaultTitle`, view counter textlari `videos.views.*`, kategoriya empty state `videos.emptyCategory` orqali tarjima qilinadi.
- **Video detail sahifasi**:
  - **Fayl**: `app/videos/[videoId]/page.tsx`
  - Back link, default title, subject kicker, no-video/player-error matnlari, show-more/share va related video view/date matnlari `videos.*`, `common.*`, `public.subject.*` orqali tarjima qilinadi.
  - View counter `formatViews(..., tt)` bilan `videos.views.zero/million/thousand/plural` kalitlarini ishlatadi; sana `useWebLocale()` orqali `uz-UZ`, `ru-RU`, `en-US` formatlariga mos chiqadi.
- **Natijalar sahifasi**:
  - **Fayl**: `app/results/page.tsx`
  - Header matnlari `results.page.*`, category title/subtitle `results.category.*`, empty state `results.category.empty` / `results.subject.empty` orqali tarjima qilinadi.
  - Milliy Sertifikat fan subcategory titlelari ham `public.subject.*` orqali tarjima qilinadi.
  - Result card ichidagi `Fan`, `Milliy Sertifikat`, `Talaba videosi`, media fallback va sana fallback `app/ui/result-card.tsx` ichida i18n va `exam_date || updated_at || created_at` bilan ishlaydi.
- **Natija detail va card sanalari**:
  - **Fayllar**: `app/results/[id]/page.tsx`, `app/ui/result-card.tsx`, `app/public-data.ts`
  - `formatPublicDate(value, locale)` endi locale qabul qiladi va public natija kartalari/detail sahifasidagi sanalar `uz/ru/en` bo'yicha formatlanadi.
  - Natija detail sahifasidagi error, result fallback, umumiy natija, detail grid label/value matnlari `public.results.*`, `admin.results.*`, `common.*` orqali tarjima qilinadi.
- **Biz haqimizda sahifasi**:
  - **Fayl**: `app/about/page.tsx`
  - Sahifa headerida ishlatiladigan `about.kicker`, `about.title`, `about.subtitle` kalitlari uch tilga to'ldirildi.
- **Translation katalogi**:
  - **Fayl**: `app/ui/web-i18n.tsx`
  - Qo'shilgan asosiy kalitlar: `courses.page.*`, `courses.detail.*`, `results.page.*`, `results.category.*`, `public.results.*`, `public.subject.*`, `videos.views.*`, `videos.defaultTitle`, `videos.backToAll`, `common.share`, `common.collapse`, `about.kicker`, `about.title`, `common.all`, `common.showMore`, `landing.courses.courseCount/showMore/showLess`.

*(Ushbu fayl loyiha ehtiyojlariga qarab keyinchalik to'ldirib borilishi mumkin.)*

### O'qituvchilar uchun "Mening studentlarim" Sahifasi
- **Vazifasi**: O'qituvchilar o'z guruhlaridagi talabalar ro'yxatini ko'rishi, ularning shaxsiy ma'lumotlarini tahrirlashi hamda parollarini tiklashi mumkin bo'lgan maxsus sahifa qo'shildi.
- **Frontend (UI)**: 
  - `app/ui/navigation-config.ts`: O'qituvchi menyusiga `students` ("Mening O'quvchilarim") bo'limi qo'shildi.
  - `app/ui/teacher-students.tsx`: Yangi komponent yaratilib, talabalar jadvali, "Tahrirlash" va "Parol tiklash" modal oynalari bilan ta'minlandi.
  - `app/page.tsx`: O'qituvchilar paneliga ushbu komponent ulandi.
- **Backend (API)**: `backend/main.py`
  - `/teacher/my-students` (GET): O'qituvchiga biriktirilgan guruhlardagi barcha talabalarni noyob (unique) holda qaytaradi.
  - `/teacher/my-students/{student_id}` (PUT): Talaba ma'lumotlarini (ism, familiya, telefon, ota-ona telefoni, fan, daraja) yangilaydi (SQL sintaksisi `?` dan PostgreSQL `%s` ga moslandi).
  - `/teacher/my-students/{student_id}/reset-password` (POST): Talabaning parolini yangilaydi va `password_used=0` qilib belgilaydi.

### Admin To'lovlar Sahifasi (Payments)
- **O'zgarish**: Admin to'lovlar panelidagi (`app/page.tsx` ichidagi) "Sozlamalar" ("To'lov sozlamalari") tugmasi va unga tegishli modal oyna, shuningdek "To'lov usullari" qo'shish/tahrirlash imkoniyatlari butunlay olib tashlandi.
- **i18n**: `app/ui/web-i18n.tsx` dagi `admin.payments.settings`, `admin.payments.paymentMethods` va unga bog'liq barcha tarjima kalitlari o'chirildi.

### Boshqa Tuzatishlar (Bot va Davomat)
- **Davomat tizimi**: `login_type = 6` (Accountless) bo'lgan o'quvchilarni davomat ro'yxatida to'g'ri ko'rsatish ta'minlandi.
- **Kunlik Test (Daily Test) Xabarnomalari**: `student_bot.py` orqali talabalarga keladigan avtomatlashtirilgan "Daily Test" xabarnomalari optimallashtirildi va endilikda faqat English va Russian fanlari o'quvchilari uchun filtrlangan holda jo'natiladi.


### Diamond Teachers Mobile App (Flutter, iOS + Android)
- **Teacher API reference**: barcha o'qituvchi (teacher) endpointlari alohida hujjatga yig'ildi: **`TEACHER_APP_API.md`** (loyiha root'ida). U yerda auth+QR, dashboard, guruhlar, davomat, dars almashinuvi (substitutions), uy vazifalari + wizard, chatlar (Diamondvoy + Taklif/Shikoyat), Group Arena, D'Point/D'Coin, o'quvchi natijalari, reyting, video darslar, kutubxona, voiceroom, notifications va profil endpointlari method/path/body/response va `backend/main.py` qator raqamlari bilan berilgan.
- **Mobil ilova joylashuvi**: `/home/xumoyun-maxkamov/Desktop/Diamond Teachers APP IOS` (Flutter loyihasi `diamond_teachers/`).
- **Base URL**: `https://diamond-education.uz/api/`, JWT bearer token bilan.
- **Dizayn**: student Android app (`DiamondEducationStudentPlatform`) uslubiga yaqin — asosiy rang `#1429F2` (royal blue), dark/light mode, uz/ru/en tillari.
