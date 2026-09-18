# Learning Paths — Duolingo uslubidagi o‘quv treklar

## Capability

Teacher yoki support teacher o‘z faniga tegishli **Track → Module → Lesson**
yo‘lini yaratadi va guruh/studentga tayinlaydi. Student trekni ketma-ket
o‘taydi: bitta trackdagi ochiq modulning darslari tugallanganda keyingi modul,
track tugallanganda esa keyingi track ochiladi. Materiallar kutubxonasi,
homework va qo‘lda/AI orqali yaratilgan mashqlar bitta modulda xavfsiz
birlashtiriladi.

## Fixed product rules

- Track ichida bir nechta dumaloq modul; modul ichida bir yoki bir nechta
  mavzu/dars bo‘ladi. Bir nechta mavzu bo‘lsa, cover atrofidagi segmentlar
  mavzu soni va yakunlanganlikni ko‘rsatadi.
- Navbatdagi modul faqat oldingi modulning required lessonlari bajarilganda
  ochiladi. Keyingi tracklar ochilmaguncha xira/locked ko‘rinadi.
- Teacher har lesson uchun vaqt limiti (sekund), passing score, urinishlar
  soni va qayta topshirish siyosatini beradi. Vaqt 0 bo‘lsa timer yo‘q.
- Mavjud kutubxona/homework savollari nusxalanmaydi: source reference va
  source version bilan bog‘lanadi. O‘chirilgan source studentning tugallangan
  attempt tarixini buzmaydi.
- Yangi savollar yoki AI savollar draft holatida ko‘rib chiqiladi; teacher
  publish qilmaguncha studentga chiqmaydi.
- Published track tarkibi keyingi o‘quvchi uchun versiyalanadi. Student
  boshlagan versiya keyinchalik teacher tahriri bilan o‘zgarmaydi.
- Teacher faqat o‘z fani/guruhiga yozishi mumkin; admin barcha tracklarni
  ko‘ra oladi va moderatsiya qila oladi.

## Surfaces

### Student web / Student Flutter

- Sidebar: `Learning Path` / `O‘quv yo‘lim`.
- Track xaritasi: vertikal Duolingo-style path, locked/xira track va modul,
  module cover, segment-ring, progress va keyingi tavsiya.
- Modul oynasi: lessonlar, kutubxona/homework/manually-created/AI source
  belgilari, vaqt va passing shartlari.
- Test player: single/multiple choice, matching, order-the-words,
  fill-the-gap, translation, short written answer, dictation/audio,
  image-based va teacher-created custom question. Natija umumiy test
  history va mistake notebookga yoziladi.
- Track tugashi: sertifikat ekraniga va PDF downloadga olib boradi.

### Teacher / Support Teacher web va Teacher Flutter

- `Learning Paths` manager: draft, published, archived tracklar; guruh yoki
  individual studentga tayinlash; progress/weak-topic analytics.
- Track builder: track nomi, fan, cover, rang, tartib, prerequisit va
  certificate settings.
- Module builder: dumaloq cover, bir nechta mavzu, segment/ring tartibi,
  lessonlar, vaqt sekundlari, passing rule va preview.
- Lesson builder: material library search, homework test, existing test,
  manual question editor yoki Diamondvoy AI generator. AI chiqishini
  teacher edit/approve qiladi.
- Certificate editor: template, static text, dynamic tokens, font/size/color,
  x/y/w/h joylashuvi, live preview, test-PDF va issue/withdraw controls.

## Visual asset catalogue

All images are 3240×3240 transparent PNG, so they can be resized to the
same circular module surface without quality loss. The teacher can choose
any cover; suggested defaults are:

| Asset | Suggested semantic |
| --- | --- |
| `telegram (1).png` | Boshlanish / Star |
| `telegram (5).png` | Practice chest / Reward |
| `telegram (4).png` | Discovery / Reading |
| `telegram (3).png` | Deep practice / Challenge |
| `telegram (2).png` | Journey / Track checkpoint |
| `telegram (6).png` | Final / Trophy |

The provided `Sertifikat.svg` and `Sertifikat (1).svg` are the English and
Russian certificate base templates (1123×794). Their base artwork must stay
unchanged; the editor stores an overlay layer rather than modifying SVG paths.
Teacher chooses the template explicitly, with subject-language as the default:
English → English, Russian → Russian. Student full name, issue date, unique
certificate id and opaque share-download URL are generated server-side. QR is
intentionally not part of this certificate flow.

## Data contract

- `learning_tracks`: owner, subject, title, cover, status, order, rules,
  certificate template/settings/version.
- `learning_track_assignments`: track version, group/student target,
  starts_at, due_at, access status.
- `learning_modules`: track, order, cover, theme topics, unlock/passing rules.
- `learning_lessons`: module, source kind/id/version, manual payload,
  duration_seconds, attempts, score rule.
- `learning_progress`: student + assignment + version, module/lesson state,
  best score, attempts, unlocked timestamps.
- `learning_question_snapshots`: immutable payload used by a started attempt.
- `certificate_templates`, `certificate_template_layers`,
  `learning_certificate_issues`: template editor state, audit and revocation.

All source-to-lesson adapters return the same `QuestionPayload` shape. This
is the compatibility boundary that lets library and homework gaps be repaired
without changing their old clients.

## State transitions

`draft → published → archived` for track versions.

`locked → unlocked → in_progress → passed` for modules; a module can become
`needs_review` only if a teacher manually requires review. A learner’s passed
module never re-locks due to a later teacher edit.

`pending → eligible → issued → revoked` for certificate issuance. Automatic
issuance is optional per track; teacher can always manually issue an eligible
certificate. Revoked share tokens immediately fail download validation.

## Safety and quality

- AI generated questions require teacher approval and duplicate/empty prompt,
  invalid answers and multiple-correct-answer validation before publish.
- Manual text answer uses teacher-defined normalisation/rubric; it is never
  auto-marked correct when the answer key is empty.
- Student cannot alter progress, clock or certificate payload. Timer is
  server-authoritative on submit.
- Assignment/group access is checked on every reader and submit endpoint.
- Track analytics feed the existing personal plan and mistake notebook, while
  arena/duel remain separate competition modes.

## Non-goals for the first release

- Replacing existing daily, arena, duel or homework screens.
- Letting AI publish a full track without teacher review.
- Giving students the ability to change certificate layers or issue dates.
- Retroactively changing an already issued certificate’s text/share identity.

## Recommended release order

1. Shared question adapter and validation for library/homework/manual tests.
2. Track/module/lesson schema, assignments, teacher web builder and student
   web path.
3. Student/teacher Flutter views using the same APIs.
4. AI draft generator, analytics and personalization integration.
5. SVG certificate layer editor, PDF/share download and manual/automatic
   issuance.

## Decisions still needed

- Does a lesson unlock at any completion, or only at a minimum score? Default:
  completion plus 70% passing score, editable by teacher.
- Do students get unlimited retries? Default: unlimited practice, but the
  teacher can set a cap for formal assignments.
- Should an assigned track have a deadline? Default: optional deadline;
  after it passes the student can still view/revise but teacher sees late.
