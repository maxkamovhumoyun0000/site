#!/usr/bin/env python3
"""Receive a raw email from Postfix and store it in the website inbox."""

from __future__ import annotations

import argparse
import hashlib
import html
import os
import re
import sys
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIL_ENV_PATH = Path("/etc/diamond-site-mail.env")
MAX_EMAIL_BYTES = 12 * 1024 * 1024
MAX_BODY_CHARS = 250_000


def _load_env_file(path: Path) -> None:
    try:
        if not path.exists() or not path.is_file():
            return
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        return


_load_env_file(MAIL_ENV_PATH)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:  # noqa: E402
    from db import _execute_ddl_candidates, get_conn  # type: ignore
except Exception:  # pragma: no cover - used by Postfix copy outside project tree
    import psycopg  # type: ignore
    from psycopg.rows import dict_row  # type: ignore

    def _execute_ddl_candidates(cur: Any, statements: list[str] | tuple[str, ...]) -> None:
        cur.execute(str(statements[0]).strip())

    def _to_pg(sql: str) -> str:
        return str(sql or "").replace("?", "%s")

    class _CompatCursor:
        def __init__(self, cur: Any):
            self.cur = cur

        def execute(self, sql: str, params: Any = None) -> Any:
            if params is None:
                return self.cur.execute(_to_pg(sql))
            return self.cur.execute(_to_pg(sql), params)

        def fetchone(self) -> Any:
            return self.cur.fetchone()

        def __getattr__(self, name: str) -> Any:
            return getattr(self.cur, name)

    class _CompatConn:
        def __init__(self, conn: Any):
            self.conn = conn

        def cursor(self) -> _CompatCursor:
            return _CompatCursor(self.conn.cursor())

        def commit(self) -> Any:
            return self.conn.commit()

        def close(self) -> Any:
            return self.conn.close()

    def get_conn() -> _CompatConn:
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            raise RuntimeError("DATABASE_URL is not configured for inbound email")
        return _CompatConn(psycopg.connect(url, row_factory=dict_row, connect_timeout=8))


def _ensure_schema() -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS inbound_emails (
                    id BIGSERIAL PRIMARY KEY,
                    recipient TEXT NOT NULL,
                    sender TEXT,
                    subject TEXT,
                    text_body TEXT,
                    html_body_sanitized TEXT,
                    message_id TEXT UNIQUE,
                    has_attachments INTEGER DEFAULT 0,
                    attachment_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'unread',
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS inbound_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient TEXT NOT NULL,
                    sender TEXT,
                    subject TEXT,
                    text_body TEXT,
                    html_body_sanitized TEXT,
                    message_id TEXT UNIQUE,
                    has_attachments INTEGER DEFAULT 0,
                    attachment_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'unread',
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        for sql in (
            "CREATE INDEX IF NOT EXISTS idx_inbound_emails_received ON inbound_emails(received_at DESC, id DESC)",
            "CREATE INDEX IF NOT EXISTS idx_inbound_emails_status_received ON inbound_emails(status, received_at DESC, id DESC)",
            "CREATE INDEX IF NOT EXISTS idx_inbound_emails_recipient_received ON inbound_emails(recipient, received_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_inbound_emails_message_id ON inbound_emails(message_id)",
        ):
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


def _decode_part(part: Any) -> str:
    try:
        payload = part.get_payload(decode=True)
    except Exception:
        payload = None
    if payload is None:
        try:
            value = part.get_content()
            return str(value or "")
        except Exception:
            return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except Exception:
        return payload.decode("utf-8", errors="replace")


def _sanitize_html(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"(?is)<(script|style|iframe|object|embed|form|meta|link)[^>]*>.*?</\1>", "", text)
    text = re.sub(r"(?is)<(script|style|iframe|object|embed|form|meta|link)[^>]*/?>", "", text)
    text = re.sub(r"(?i)\son\w+\s*=\s*(['\"]).*?\1", "", text)
    text = re.sub(r"(?i)\s(href|src)\s*=\s*(['\"])\s*javascript:.*?\2", r" \1=\"#\"", text)
    return text[:MAX_BODY_CHARS]


def _first_address(*values: str) -> str:
    addresses = getaddresses([value for value in values if value])
    if not addresses:
        return ""
    name, address = addresses[0]
    return address or name or ""


def _received_at(message: Any) -> str:
    raw = str(message.get("Date") or "").strip()
    if raw:
        try:
            parsed = parsedate_to_datetime(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except Exception:
            pass
    return datetime.now(timezone.utc).isoformat()


def _extract_bodies(message: Any) -> tuple[str, str, int]:
    text_parts: list[str] = []
    html_parts: list[str] = []
    attachment_count = 0
    if message.is_multipart():
        for part in message.walk():
            if part.is_multipart():
                continue
            disposition = str(part.get_content_disposition() or "").lower()
            ctype = str(part.get_content_type() or "").lower()
            filename = str(part.get_filename() or "").strip()
            if disposition == "attachment" or filename:
                attachment_count += 1
                continue
            body = _decode_part(part)
            if ctype == "text/plain":
                text_parts.append(body)
            elif ctype == "text/html":
                html_parts.append(body)
    else:
        ctype = str(message.get_content_type() or "").lower()
        body = _decode_part(message)
        if ctype == "text/html":
            html_parts.append(body)
        else:
            text_parts.append(body)
    text_body = "\n\n".join(part.strip() for part in text_parts if part.strip())[:MAX_BODY_CHARS]
    html_body = _sanitize_html("\n\n".join(part for part in html_parts if part.strip()))
    return text_body, html_body, attachment_count


def save_email(raw: bytes, recipient: str = "", sender: str = "") -> int:
    if len(raw) > MAX_EMAIL_BYTES:
        raise ValueError("email too large")
    message = BytesParser(policy=policy.default).parsebytes(raw)
    subject = str(message.get("Subject") or "").strip()[:1000]
    message_id = str(message.get("Message-ID") or "").strip()[:500]
    if not message_id:
        message_id = f"local-{hashlib.sha256(raw).hexdigest()}"
    clean_recipient = (
        recipient
        or _first_address(str(message.get("X-Original-To") or ""), str(message.get("Delivered-To") or ""), str(message.get("To") or ""))
        or "unknown@diamond-education.uz"
    )[:500]
    clean_sender = (sender or _first_address(str(message.get("From") or ""), str(message.get("Return-Path") or "")))[:500]
    text_body, html_body, attachment_count = _extract_bodies(message)
    _ensure_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM inbound_emails WHERE message_id=? LIMIT 1", (message_id,))
        existing = cur.fetchone()
        if existing:
            return int(existing.get("id") if hasattr(existing, "get") else existing[0])
        cur.execute(
            """
            INSERT INTO inbound_emails (
                recipient, sender, subject, text_body, html_body_sanitized, message_id,
                has_attachments, attachment_count, status, received_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'unread', ?, CURRENT_TIMESTAMP)
            """,
            (
                clean_recipient,
                clean_sender,
                subject,
                text_body,
                html_body,
                message_id,
                1 if attachment_count > 0 else 0,
                int(attachment_count),
                _received_at(message),
            ),
        )
        conn.commit()
        cur.execute("SELECT id FROM inbound_emails WHERE message_id=? LIMIT 1", (message_id,))
        row = cur.fetchone()
        email_id = int(row.get("id") if hasattr(row, "get") else row[0])
        
        # Send Telegram notification to admins
        try:
            bot_token = os.environ.get("ADMIN_BOT_TOKEN")
            if bot_token:
                cur.execute("SELECT tg_id FROM users WHERE role='admin' AND tg_id IS NOT NULL")
                admins = cur.fetchall()
                if admins:
                    import urllib.request
                    import json
                    for a in admins:
                        tg_id = str(a.get("tg_id") if hasattr(a, "get") else a[0]).strip()
                        if tg_id:
                            msg = f"🔔 *Yangi domen email!*\n\n*Kimdan:* {clean_sender}\n*Kimga:* {clean_recipient}\n*Mavzu:* {subject}"
                            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                            data = json.dumps({"chat_id": tg_id, "text": msg, "parse_mode": "Markdown"}).encode("utf-8")
                            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                            try:
                                urllib.request.urlopen(req, timeout=5)
                            except Exception:
                                pass
        except Exception:
            pass

        return email_id
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Store inbound diamond-education.uz email in DB")
    parser.add_argument("--recipient", default="")
    parser.add_argument("--sender", default="")
    args = parser.parse_args()
    raw = sys.stdin.buffer.read(MAX_EMAIL_BYTES + 1)
    try:
        email_id = save_email(raw, recipient=args.recipient, sender=args.sender)
        print(f"stored inbound email id={email_id}", file=sys.stderr)
        return 0
    except Exception as exc:
        print(f"inbound email ingest failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 75


if __name__ == "__main__":
    raise SystemExit(main())
