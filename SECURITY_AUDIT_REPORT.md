# Diamond Education security audit — 2026-10-01

Scope inspected: the Next.js website/admin panel, FastAPI backend and payment
flow, PostgreSQL access code, the Student and Teacher Flutter applications in
the Desktop workspace, local storage, transport configuration, source-tracked
secrets, and application logging.

## Critical

No source-tracked private credential or TLS verification bypass was found in
the inspected code. This does not prove that secrets have not appeared in Git
history; production credentials must be rotated immediately if an external
secret-scanning service reports an exposure.

## High

### Mobile PII and FCM credentials persisted in plaintext preferences

- Found in: `Diamond Students APP/diamond_students` and `Diamond Teachers
  APP/diamond_teachers`, `lib/core/storage/local_storage.dart`.
- Risk: cached authenticated profile data and the last registered FCM token
  were stored with `SharedPreferences`; a profile may include personal data and
  an FCM token is a device credential.
- Fixed: both values now use `flutter_secure_storage` (Android encrypted
  preferences/Keystore and iOS Keychain). Existing plaintext keys are removed
  as soon as an app writes or clears the upgraded values. Bootstrap was made
  asynchronous so it reads the encrypted snapshot before first render.

### Persisted server logs were verbose and did not have a redaction boundary

- Found in: `logging_config.py`.
- Risk: DEBUG-level stdout plus persistent `logs/bot.log` and `errors.log`
  could retain exception details containing credentials or personal data.
- Fixed: production now emits INFO-level, centrally redacted stdout logs only.
  A root logging filter masks authorization values, passwords, token-like
  fields, common secret fields and Uzbek phone numbers. Development file logs
  are explicit opt-in, rotated, and owner-readable only.
- Manual action: configure the platform/journald or external logging provider
  with encrypted-at-rest storage, access control, and the business-approved
  retention policy. Do not re-enable production file logging.

### Receipts previously had no immutable, server-authorized document model

- Found in: payment confirmation flow in `backend/main.py` and the Admin
  payment history UI.
- Risk: no receipt snapshot, idempotency boundary, receipt-specific audit
  trail, or server-side receipt authorization existed.
- Fixed: a server-side `payment_receipts` model is created transactionally with
  payment confirmation. It has a unique transaction key and immutable JSON
  snapshot. Receipt reads, PDF generation and print-audit requests enforce the
  existing `_can_manage_group` Limited Admin scope. There are no client-facing
  receipt update/delete routes.
- Note: a receipt opened for a payment created before this deployment is
  backfilled once from the currently available historical payment/group data,
  then frozen. New receipts always capture the confirmation-time snapshot.

## Medium

### HTTPS relied on deployment convention instead of application enforcement

- Found in: FastAPI had CORS restrictions but no external plaintext request
  guard.
- Fixed: the backend denies non-loopback plaintext requests when
  `DIAMOND_ENV=production` (or `ENFORCE_HTTPS=true`). It accepts trusted
  reverse-proxy TLS termination only with `X-Forwarded-Proto: https`.
- Manual action: ensure Nginx forwards that header and redirects public HTTP
  to HTTPS. The direct backend port must remain private/firewalled.

### Missing browser hardening headers

- Found in: `next.config.ts`.
- Fixed: added CSP, frame, MIME-sniffing, referrer and permissions-policy
  headers; disabled production browser source maps and the `X-Powered-By`
  header. The CSP retains narrowly documented inline/eval compatibility needed
  by the existing client runtime; it should be tightened after inline assets
  are removed.

## Low

### Mobile error output could reach production device logs

- Found in: both Flutter apps' push service exception handlers.
- Fixed: diagnostic output is now gated by `kDebugMode` and logs only exception
  type, not exception content that may include a request or token.

## Verified existing controls

- Student and Teacher APIs use the HTTPS production base URL and send bearer
  credentials in authorization headers, not query parameters.
- Neither mobile client contains a certificate-validation bypass or master
  encryption key.
- Both mobile apps already used secure storage for the primary JWT.
- The backend uses parameterized database queries through its PostgreSQL
  compatibility layer.

## Required operational follow-up

1. Keep `DIAMOND_ENV=production` and verify the reverse proxy sends
   `X-Forwarded-Proto: https`.
2. Confirm PostgreSQL volumes and centralized log storage use provider/disk
   encryption with restricted service accounts; rotate credentials on any
   suspected historical exposure.
3. Define separate retention schedules for debug, security, payment and audit
   records. This repository deliberately does not automatically delete
   financial/audit history.
4. Run device-level regression tests for login, token refresh/logout, push
   registration, payments and receipt view/PDF/print before publishing the two
   mobile app updates.
