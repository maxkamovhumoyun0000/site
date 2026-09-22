# Learning path, materials and homework integration

Reviewed 2026-09-22. Projects: `diamond-site`, Desktop `Diamond Teachers APP/diamond_teachers`, and Desktop `Diamond Students APP/diamond_students`.

## Teacher workflow

1. Open a learning-path module and choose **Kutubxona muharriri · Barcha mashq turlari**. In the Teacher app, this is available inside the manual test sheet after entering a title.
2. Use the same structured exercise editor as Materials and Homework. It supports nested questions, matching pairs, passages, accepted answers and media instead of requiring raw JSON.
3. Save the exercises to the module in one transaction. AI generation also saves its returned questions as a batch.
4. Use **Kutubxonaga nusxa saqlash** (library icon in the app) to create a private, reusable copy. The library's existing assignment flow attaches that copy to homework; the learning-path library picker can reuse it in another module.
5. Edit a supported library exercise with the same full editor. Basic legacy MCQ/true-false/fill-blank/word-order questions retain their existing editor.

Library copies and attached module questions are independent snapshots: editing one does not silently change previously assigned homework or another module.

## Existing exercise inventory

Web and Teacher-app catalog comparison confirms the same 24 library exercise kinds.

| Family | Library kinds | Required content |
| --- | --- | --- |
| Writing and speaking | `speak_sentence`, `write_sentence`, `guided_writing`, `translation`, `reading_open`, `read_aloud`, `paraphrase`, `dialogue_completion`, `picture_description` | Prompt/word, reference answer, passage or image as appropriate |
| Listening | `listening`, `dictation`, `listening_tf`, `listening_dictation`, `listening_open`, `listening_gap`, `listening_order`, `listening_set` | Audio plus choices, answers, tokens or nested questions |
| Vocabulary and structured practice | `spelling`, `matching`, `scrambled_sentence`, `gap_fill`, `passage_cloze`, `reading_set`, `word_practice` | Accepted spellings, pairs, tokens, blank answers, passages or vocabulary metadata |
| Legacy learning-path questions | `multiple_choice`, `true_false`, `fill_blank`, `word_order` | Existing basic editor and student controls |

Books, videos, homework content tests, AI-generated tests and teacher library nodes can all be selected as learning-path sources through the existing materials search/import routes.

## Corrected integration defects

- The Teacher app previously discarded the AI endpoint's generated draft. It now persists it and reports the actual saved count.
- Batch creation validates access and writes all questions in one transaction, appending after existing positions.
- Mobile lesson editing previously discarded rich fields and changed unrecognized question kinds into MCQ. Supported library kinds now open the shared editor; legacy editing retains unknown metadata.
- Library-to-path normalization preserves rich fields and accepted answers, handles false and indexed answers, and maps `questions` to `sub_questions` and `answers` to `blanks` for existing runners.
- Final exams previously selected only a few payload fields, losing passages, images and matching pairs. Full fields now survive. Reading/listening sets become individual exam questions; cloze questions use numbered blanks with separate expected answers.
- The legacy AI question bank is reused only when it can supply the requested types without dropping structured fields.
- Learning-path library browsing/import now respects the same owner/public/shared visibility as the materials library.
- Audio upload in the mobile shared editor now works without a library provider, including the homework wizard and learning paths.

## Platform review and validation

Both Flutter apps use `https://diamond-education.uz/api/`. Android manifests include internet and recording permissions; iOS plists include microphone, camera and photo-library usage descriptions. The same Dart source serves Android and iOS.

No local application builds were run. Static analysis was run sequentially at low CPU priority. Backend regression tests, Python compilation and the Next.js production build run on the server. Deployment follows `deploy.md`: verified database backup, changed-code-only rsync, service restarts, HTTP smoke tests and restart-count checks.

Physical-device microphone/file-picker/playback tests and signed Android/iOS releases are outside these static checks. The Teacher app source changes require a future mobile release; a website deployment does not update already installed app binaries. The Student app receives the corrected payloads from the deployed backend without source changes.

## Check results

- Student app: `dart analyze lib test` — no issues.
- Teacher app: `dart analyze lib test` — no issues after the final source edits.
- Web/Teacher library catalog: 24 kinds, identical sets.
- Server: 12 targeted learning-path/personalization regression tests passed. Existing dependency deprecation warnings remain.
- Both iOS property lists parse successfully; Android recording/internet permissions are present.
- Production database backup: `diamond-site-20260922-163858.dump`, 10,478,864 bytes. A pre-change code archive is also retained on the server.
