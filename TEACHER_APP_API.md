# Diamond Teachers App — Backend API Reference

> This document lists every backend endpoint used by the **Diamond Teachers** mobile app
> (Flutter, iOS + Android). It was collected from `backend/main.py` so that the next time
> we need an endpoint we can find it here instead of grepping 46k lines.
>
> - **Base URL:** `https://diamond-education.uz/api/`
> - **Auth:** JWT bearer token — header `Authorization: Bearer <access_token>`
> - **Roles:** `login_type` 1,2 = student, 6 = accountless student. Teacher endpoints require
>   `TEACHER_STAFF_ROLES` (role `teacher` OR `support`). Payment status is `teacher`-only.
> - All line numbers refer to `backend/main.py` at the time of writing.

---

## 1. Auth & Session

| Method | Path | Body / Query | Response | Line |
|---|---|---|---|---|
| POST | `/auth/login` | `LoginRequest` | `TokenResponse` | 16348 |
| POST | `/auth/telegram` | `TelegramLoginRequest` | `TokenResponse` | 16409 |
| POST | `/auth/telegram/sync` | `TelegramSyncRequest` (Bearer) | `User` | 16429 |
| POST | `/auth/qr/generate` | — (Bearer, teacher/admin only) | `QrGenerateResponse` | 16473 |
| POST | `/auth/qr/consume` | `QrConsumeRequest` | `TokenResponse` | 16487 |
| POST | `/auth/logout` | — (Bearer) | `{message}` | 16532 |
| GET  | `/auth/me` | — (Bearer) | `User` | 16543 |
| PATCH| `/user/language` | `UserLanguageUpdateRequest` `{language: uz|ru|en}` | `{status,message}` | — |
| GET  | `/user/profile/avatar` | — (Bearer) | avatar | 30539 |
| POST | `/user/profile/avatar` | multipart file | `{url}` | 30547 |
| GET  | `/user/subscription-status` | — (Bearer) | `{subscribed}` | — |

**Request models**
```
LoginRequest      { login_id, password, device_id?, telegram_id?, init_data?, sync_bot_session=true }
QrConsumeRequest  { qr_token, device_id?, telegram_id?, init_data?, sync_bot_session=true }
QrGenerateResponse{ qr_token, qr_payload, expires_at, expires_in }
TokenResponse     { access_token, token_type, user }
```

**QR login flow (teacher side):** The teacher (already logged in on web/another device) calls
`POST /auth/qr/generate` → shows `qr_payload` as a QR code. A second device scans it and calls
`POST /auth/qr/consume { qr_token }` to receive a full `TokenResponse`. Students are **not** allowed
to generate QR (`403`). In the mobile app the login screen scans a QR shown on the web to log in.

---

## 2. Teacher Overview / Dashboard

| Method | Path | Notes | Line |
|---|---|---|---|
| GET | `/teacher/overview` | `{ user, payload }` — payload = `_build_teacher_payload` (groups, stats, students summary) | 27080 |
| GET | `/teacher/payments/status?ym=YYYY-MM&group_id=` | teacher-only. `{ ym, group_id, items[] }` item = `{user_id, student_name, group_id, group_name, ym, status, has_remaining_debt, is_accountless}` | 27101 |

---

## 3. Groups (Mening Guruhlarim)

| Method | Path | Body / Query | Response | Line |
|---|---|---|---|---|
| GET | `/teacher/groups` | `?subject=` | `{items:[group]}` | 27087 |
| GET | `/teacher/groups/{group_id}/members` | — | `{items:[user_light]}` (students only) | 27223 |
| GET | `/teacher/groups/{group_id}/available-students` | `?q=&limit=` | `{items:[user_light]}` | 27236 |
| PATCH | `/teacher/groups/{group_id}` | `GroupUpdateRequest` | `{message, group}` | 27281 |
| POST | `/teacher/groups/{group_id}/members/{student_id}` | — | membership payload | 27325 |
| DELETE | `/teacher/groups/{group_id}/members/{student_id}` | `?removed_at=` | membership payload | 27347 |

```
GroupUpdateRequest { name?, teacher_id?, level?, subject?, subject_id?, course_id?,
                     lesson_date?(MWF|TTS), lesson_start?, lesson_end?, tz?,
                     telegram_group_url?, pricing_type? }
group = { id, name, subject, level, teacher_name, lesson_date, lesson_start, lesson_end,
          student_count, telegram_group_url, ... }
```

---

## 4. My Students (Mening o'quvchilarim)

| Method | Path | Body | Response | Line |
|---|---|---|---|---|
| GET | `/teacher/my-students` | — | `{items:[student]}` unique across groups | 46683 |
| PUT | `/teacher/my-students/{student_id}` | `{first_name,last_name,phone,parent_phone,subject,level}` | `{message}` | 46710 |
| POST | `/teacher/my-students/{student_id}/reset-password` | `{new_password}` | `{message}` | 46746 |

---

## 5. Attendance (Davomat)

| Method | Path | Body / Query | Response | Line |
|---|---|---|---|---|
| GET | `/teacher/attendance` | `?group_id=(req)&date=YYYY-MM-DD` | `{group_id,date,items:[{user_id,full_name,avatar_url,status}]}` | 27365 |
| GET | `/teacher/attendance/table` | `?group_id=(req)&month=YYYY-MM` | month grid payload | 27408 |
| POST | `/teacher/attendance/mark` | `AttendanceMarkRequest` | `{message,status,dpoints_delta,effect}` | 27424 |
| POST | `/teacher/attendance/bulk-mark` | `AttendanceBulkMarkRequest` | `{message,status,marked,changed,noops,total_dpoints_delta,effects[]}` | 27453 |

```
AttendanceMarkRequest     { group_id, user_id, date, status }
AttendanceBulkMarkRequest { group_id, date, status, user_ids[] }
status ∈ Keldi | Sababli | Sababsiz  (also accepts Present/Late/Absent + lowercase)
```

---

## 6. Lesson Exchange / Substitutions (Dars almashinuvi)

| Method | Path | Body | Response | Line |
|---|---|---|---|---|
| GET | `/teacher/substitutions/candidates` | `?subject=&q=` | `{items:[{id,full_name,role,subject,subjects,login_id}]}` — teachers/support eligible as substitutes | new, added during backend audit |
| GET | `/teacher/substitutions` | `?group_id=` | `{items:[assignment]}` active owned assignments | 27499 |
| POST | `/teacher/groups/{group_id}/substitutions` | `TemporaryAssignmentRequest` | `{message,assignment_id,assignment_ids[],created_count,skipped_existing,...}` | 27529 |
| DELETE | `/teacher/groups/{group_id}/substitutions/{temp_teacher_id}` | — | `{message,cancelled,released_slots}` | 27572 |

```
TemporaryAssignmentRequest { temp_teacher_id, lesson_date?, lesson_start?, lesson_end?,
                             upcoming_count?(1..60) }
```
- `upcoming_count` = how many upcoming lessons to hand over (the "nechta dars" value).
- The temporary teacher gains full management of that group (attendance, points, homework, arena)
  for the assigned slots via `_teacher_can_manage_group` (checks `temporary_group_assignments`).
- Admin equivalents: `GET/POST/DELETE /admin/groups/{group_id}/temporary-assignments` (40653+).

### Backend bugs found & fixed during the mobile app build (2026-07-17)
1. **Silent lockout when a group has no `lesson_start`/`lesson_end` configured** (`db.py`,
   `_temporary_assignment_access_bounds`). Groups can be created with null lesson times
   (`create_group` defaults both to `None`). Previously, if either time was missing, this function
   returned `None` unconditionally, which made `_temporary_assignment_accessible_now()` always
   return `False`. The result: `POST /teacher/groups/{id}/substitutions` would succeed (200, valid
   `assignment_id`), but the substitute teacher could never actually pass `_teacher_can_manage_group`
   — every attendance/homework/arena/D'Point call for that group returned a 403 with no indication
   why. **Fix**: fall back to a full-day access window (00:00–23:59 on `lesson_date`) when either
   time is missing, instead of refusing access outright.
2. **No conflict check across different substitutes for the same slot** (`backend/main.py`,
   `teacher_create_substitution`). The existing dedupe logic only checked
   `(owner_teacher_id, group_id, temp_teacher_id)` — so a *different* substitute could be assigned to
   an already-covered group+lesson_date with no warning, and both would then simultaneously pass
   `_teacher_can_manage_group`, risking duplicate/conflicting attendance or D'Point actions on the
   same lesson. **Fix**: added `get_active_temporary_assignments_for_group_slots()` in `db.py` and a
   pre-check in the endpoint that returns `409` naming the other substitute already covering that date.
3. **No teacher-accessible endpoint to look up substitute candidates.** The web UI's substitute picker
   only worked because the candidate list (`temporary_teacher_candidates`) happened to be embedded
   inside the large `/teacher/overview` boot payload. There was no lightweight, purpose-built,
   teacher-role-accessible search endpoint — `/admin/teachers/search` exists but is `admin`-only.
   **Fix**: added `GET /teacher/substitutions/candidates?subject=&q=` reusing the existing
   `_teacher_temp_candidate_rows_for_subject()` helper.

---

## 7. Homework (Uy vazifalari) + Wizard

| Method | Path | Body / Query | Response | Line |
|---|---|---|---|---|
| GET | `/teacher/homework` | — | `{items:[homework + test_* fields]}` | 26717 |
| POST | `/teacher/homework` | `HomeworkCreateRequest` | `{message,item,target_type,audience_count,group_id,student_id}` | 26574 |
| PATCH | `/teacher/homework/{homework_id}` | `HomeworkCreateRequest` | `{message,item}` | 26668 |
| POST | `/teacher/homework/{homework_id}/review` | `HomeworkReviewRequest` | review result | 26947 |
| GET | `/teacher/homework/groups` | `?subject=&query=&limit=` | `{items:[group_light],total,limit}` | 26743 |
| GET | `/teacher/homework/groups/{group_id}/voiceroom-preview` | — | `{items:[voiceroom_group]}` random pairs | 26784 |
| GET | `/teacher/homework/{homework_id}/report` | — | submissions report | 45762 |
| POST | `/homework/upload-image` | multipart | `{url}` | 30468 |
| POST | `/homework/upload-voice` | multipart | `{url}` | 30493 |
| POST | `/homework/upload-file` | multipart | `{url}` | 30505 |
| POST | `/teacher/upload/media` | multipart | `{url}` | 30175 |

```
HomeworkCreateRequest { student_id?, group_id?, title, description?, due_at?, image_url?,
                        homework_kind?(list|test|both), requires_upload?, requires_test?,
                        requires_voice_message?, requires_file?, is_voiceroom?,
                        voiceroom_groups?[], dcoin_effect=0, dpoint_effect? }
HomeworkReviewRequest { student_id?, status(done|not_done), dcoin_delta=0, dpoint_delta?, review_note? }
```
Homework "wizard" (in Diamondvoy chat) — see section 9.

---

## 8. Homework Test Builder (per content)

| Method | Path | Notes | Line |
|---|---|---|---|
| GET | `/teacher/{content_type}/{content_id}/test` | fetch attached test | 45719 |
| POST | `/teacher/{content_type}/{content_id}/test` | create/replace test | 45724 |

`content_type` = `homework` etc.

---

## 9. Chats (Diamondvoy + Taklif/Shikoyat) + Homework Wizard

| Method | Path | Notes | Line |
|---|---|---|---|
| GET | `/chats/contacts` | contact list (ai + feedback threads) | 17694 |
| GET | `/chats/{thread_id}/messages` | thread messages | 17752 |
| POST | `/chats/{thread_id}/messages` | send message | 17766 |
| POST | `/chats/{thread_id}/read` | mark read | 17779 |
| GET | `/chats/unread-count` | badge | 17792 |
| POST | `/chats/upload-image` | multipart | 16890 |
| POST | `/chats/feedback` | create feedback (Taklif va Shikoyat) | 19335 |
| GET | `/chats/diamondvoy` | list AI chats | 18049 |
| POST | `/chats/diamondvoy` | new AI chat | 18064 |
| GET | `/chats/diamondvoy/{chat_id}/messages` | messages | 18102 |
| POST | `/chats/diamondvoy/{chat_id}/messages/stream` | streamed reply (SSE/chunked) | 18119 |
| POST | `/chats/diamondvoy/{chat_id}/regenerate` | regenerate last | 18133 |
| DELETE | `/chats/diamondvoy/{chat_id}` | delete chat | 18091 |
| POST | `/chats/diamondvoy/{chat_id}/pin` | pin | 18079 |

**Homework wizard (teacher) — inside a Diamondvoy chat:**
| Method | Path | Line |
|---|---|---|
| POST | `/chats/diamondvoy/{chat_id}/homework/start` | 18206 |
| GET | `/chats/diamondvoy/{chat_id}/homework/state` | 18268 |
| POST | `/chats/diamondvoy/{chat_id}/homework/action` | 18275 |
| POST | `/chats/diamondvoy/{chat_id}/homework/generate-test` | 18385 |
| POST | `/chats/diamondvoy/{chat_id}/homework/modify-test` | 18417 |
| POST | `/chats/diamondvoy/{chat_id}/homework/parse-test` | 18451 |
| POST | `/chats/diamondvoy/{chat_id}/homework/send` | 18487 |

**Add-students wizard (teacher, via chat):** `/chats/diamondvoy/{chat_id}/add-students/{start|select-type|upload-xlsx|confirm|reset|state}` (18829+).

---

## 10. Group Arena (Guruh Arena) + Settings

| Method | Path | Body | Response | Line |
|---|---|---|---|---|
| GET | `/teacher/arena/groups/{group_id}/status` | — | `{group_id,session,snapshot,answers}` | 28504 |
| GET | `/teacher/arena/groups/{group_id}/leaderboard` | — | `{group_id,session,leaderboard[]}` | 28522 |
| GET | `/teacher/arena/groups/{group_id}/prepared` | — | `{group_id,items[],total}` ready sessions | 28953 |
| POST | `/teacher/arena/groups/{group_id}/prepare` | `TeacherArenaStartRequest` (manual) | `{message,session_id,session}` | 28966 |
| POST | `/teacher/arena/groups/{group_id}/generate` | `TeacherArenaGenerationRequest` | generator job `{job_id,status,...}` | 29001 |
| POST | `/teacher/arena/groups/{group_id}/start` | `TeacherArenaStartRequest` | `{message,session}` | 29068 |
| POST | `/teacher/arena/groups/{group_id}/finish` | — | `{message,session_id,result,snapshot}` | 29038 |

```
TeacherArenaStartRequest      { session_id?, question_count(5..30), question_source(ai|manual|bank),
                                difficulty(Easy|Medium|Hard), questions?[] }
TeacherArenaGenerationRequest { question_count(5..30), difficulty }
```
- Requires today's attendance to be marked before `start` (`attendance_ready`).

---

## 11. D'Point / D'Coin + Student Performance + Ratings

| Method | Path | Body | Response | Line |
|---|---|---|---|---|
| GET | `/teacher/economy/students` (alias `/teacher/dcoin/students`) | — | `{items:[{student,subjects,subject_levels,balances,balance_total,dpoints_total,tests_*,rules}]}` | 27024 |
| GET | `/teacher/student-performance/{student_id}` | — | `{student,subject_levels,monthly,tests,dcoin_by_subject,dcoin_total,dpoints_total,lesson_window_active}` | 28376 |
| POST | `/teacher/students/{student_id}/dpoint-adjust` (alias `/dcoin-adjust`) | `TeacherDcoinAdjustRequest` | `{message,student_id,subject,amount,dpoints_total,balance_total,balances,rules}` | 28438 |
| GET | `/leaderboard` | `?limit=` | `{items:[leaderboard_item]}` | 43829 |
| GET | `/leaderboard/groups/{group_id}` | — | group leaderboard | 43839 |
| GET | `/dcoin/balance` | — | balance | 43844 |
| GET | `/dcoin/transactions` | — | tx history | 43923 |

```
TeacherDcoinAdjustRequest { amount, subject?, reason? }
  reason required (>=3 chars). amount: +1..+500 (bonus) or -1..-500 (penalty), not 0.
  24h manual limit enforced (rules.daily_remaining).
```

---

## 12. Video Lessons (Video darslar)

| Method | Path | Body / Query | Line |
|---|---|---|---|
| GET | `/teacher/videos` | `?subject=&level=` | 44174 |
| GET | `/teacher/videos/{video_id}` | — | 44283 |
| POST | `/teacher/videos` | create video | 44045 |
| POST | `/teacher/videos/{video_id}/progress` | watch progress | 44388 |
| POST | `/teacher/videos/{video_id}/view` | +1 view | 44401 |
| POST | `/teacher/videos/{video_id}/like` | like | 44586 |
| GET | `/public/videos` / `/public/videos/{id}` | public list/detail | 29641 |
| POST | `/public/videos/{id}/comments` | comment | 29791 |
| POST | `/public/videos/comments/{comment_id}/vote` | vote | 29836 |

---

## 13. Library (Kutubxona)

| Method | Path | Body / Query | Line |
|---|---|---|---|
| GET | `/teacher/books` | `?subject=&level=` | 44681 / 45024 |
| GET | `/teacher/books/{book_id}` | — | 44727 / 45120 |
| GET | `/teacher/books/{book_id}/pdf` | pdf stream | 44733 |
| POST | `/teacher/books/{book_id}/external-open-link` | open-link | 44747 |
| POST | `/teacher/books` | create book | 44757 |

---

## 14. Support Requests (teacher-side booking approvals)

| Method | Path | Body | Line |
|---|---|---|---|
| GET | `/teacher/support-requests` | — | 28321 |
| POST | `/teacher/support-requests/{booking_id}/status` | `TeacherBookingDecisionRequest {status,date?,time?,branch?,note?}` | 28331 |

---

## 15. Notifications

| Method | Path | Notes | Line |
|---|---|---|---|
| GET | `/notifications` | `?limit=` → `{items:[notification],unread_count}` | 29254 |
| GET | `/notifications/unread-count` | badge | 29270 |
| POST | `/notifications/{notification_id}/read` | mark one | 29277 |
| POST | `/notifications/read-all` | mark all | 29302 |
| GET | `/teacher/notifications` | teacher-scoped feed | 29242 |

```
NotificationItem { id, title, body, type, read, created_at, data?, button_text?, button_url?, target_screen? }
```

---

## 16. Voice Rooms (Voiceroom)

| Method | Path | Body | Line |
|---|---|---|---|
| GET | `/voice-rooms/active` | — | 45990 |
| GET | `/voice-rooms/my` | — | 45930 |
| GET | `/voice-rooms/sessions/my` | — | 45953 |
| POST | `/voice-rooms/create` | `VoiceRoomCreateRequest {name,subject,tags?}` | 45884 |
| PUT | `/voice-rooms/{room_id}/name` | `{name}` | 46636 |
| DELETE | `/voice-rooms/{room_id}` | — | 45974 |

---

## 17. AI Generator (Teacher)

| Method | Path | Body | Line |
|---|---|---|---|
| GET | `/teacher/generator/stock` | — | 27605 |
| GET | `/teacher/generator/history` | — | 27679 |
| POST | `/teacher/generator/job` | `GeneratorJobRequest {kind, subject, level, count}` | 28115 |
| GET | `/teacher/generator/jobs/{job_id}` | — | 28130 |
| POST | `/teacher/generator/jobs/{job_id}/cancel` | — | 28149 |
| POST | `/teacher/generator/vocabulary` | `TeacherAiGenerationRequest` | 28168 |
| POST | `/teacher/generator/daily-tests` | `TeacherAiGenerationRequest` | 28182 |
| POST | `/teacher/generator/arena` | `TeacherAiGenerationRequest` | 28230 |
| POST | `/teacher/generator/bulk` | `BulkAiGenerationRequest` | 28304 |
| GET | `/teacher/tests/history` | `?days=` | 27597 |
| POST | `/teacher/tests/upload` | manual upload | 27617 |

---

## Notes for the Flutter app
- Always send `Authorization: Bearer <token>` (except `/auth/login`, `/auth/qr/consume`).
- On HTTP 401 → clear token and route back to Login (mirrors student app `unauthorizedEvent`).
- `_teacher_can_manage_group` allows both the owner teacher AND an active temporary (substitute)
  teacher, so the same teacher endpoints work for the substitute during the lesson-exchange window.
- Subjects are normalized server-side; common values: `English`, `Russian`, etc.
- Levels: `BEGINNER, ELEMENTARY, PRE-INTERMEDIATE, INTERMEDIATE, UPPER-INTERMEDIATE, ADVANCED`
  (also `A1..C1`).
