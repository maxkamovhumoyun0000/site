#!/usr/bin/env python3
"""Diamond Education local thermal-printer agent.

The agent is intentionally small and dependency-free.  It listens only on
127.0.0.1, accepts print jobs from the Diamond Education web application, and
sends ESC/POS bytes to the selected local printer.  It never exposes a network
port to other machines and it does not retain payment or student data.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import shutil
import subprocess
import sys
import textwrap
import unicodedata
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


HOST = "127.0.0.1"
PORT = 18765
LINE_WIDTH = 32  # 58mm / XP-58 class printer at normal font size.
MAX_BODY_BYTES = 16_384
DEFAULT_SETTINGS = {"paper_width_mm": 57.5, "side_padding_mm": 1.5, "line_width": LINE_WIDTH}
ALLOWED_ORIGINS = {
    "https://diamond-education.uz",
    "https://www.diamond-education.uz",
    "http://localhost:3000",
}
ESC_INIT = b"\x1b@\x1b\x74\x11"
ESC_ALIGN_LEFT = b"\x1ba\x00"
ESC_ALIGN_CENTER = b"\x1ba\x01"
ESC_BOLD_ON = b"\x1bE\x01"
ESC_BOLD_OFF = b"\x1bE\x00"
ESC_CUT = b"\x1dV\x00"


def default_settings_path() -> Path:
    configured = os.environ.get("DIAMOND_PRINT_AGENT_CONFIG", "").strip()
    if configured:
        return Path(configured)
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", ".")) / "DiamondEducation" / "PrintAgent" / "settings.json"
    return Path.home() / ".config" / "diamond-education" / "print-agent.json"


def validate_settings(raw: object) -> dict[str, float | int]:
    if not isinstance(raw, dict) or set(raw) - set(DEFAULT_SETTINGS):
        raise ValueError("invalid printer settings")
    try:
        paper_width = float(raw.get("paper_width_mm", DEFAULT_SETTINGS["paper_width_mm"]))
        side_padding = float(raw.get("side_padding_mm", DEFAULT_SETTINGS["side_padding_mm"]))
        line_width = int(raw.get("line_width", DEFAULT_SETTINGS["line_width"]))
    except (TypeError, ValueError) as exc:
        raise ValueError("printer settings must be numeric") from exc
    if not 48 <= paper_width <= 58 or not 0 <= side_padding <= 4 or not 24 <= line_width <= 42:
        raise ValueError("printer settings are outside the supported range")
    if side_padding * 2 >= paper_width:
        raise ValueError("side padding leaves no printable width")
    return {"paper_width_mm": round(paper_width, 2), "side_padding_mm": round(side_padding, 2), "line_width": line_width}


def load_settings(path: Path | None = None) -> dict[str, float | int]:
    target = path or default_settings_path()
    try:
        return validate_settings(json.loads(target.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return dict(DEFAULT_SETTINGS)
    except (OSError, ValueError, json.JSONDecodeError):
        # A corrupt local preference must never stop payment receipt printing.
        return dict(DEFAULT_SETTINGS)


def save_settings(raw: object, path: Path | None = None) -> dict[str, float | int]:
    settings = validate_settings(raw)
    target = path or default_settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    temporary.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)
    if os.name != "nt":
        target.chmod(0o600)
    return settings


def printable_columns(settings: dict[str, float | int]) -> int:
    """Keep the configured character width inside the selected roll and side inset."""
    physical_columns = int((float(settings["paper_width_mm"]) - 2 * float(settings["side_padding_mm"])) / 1.5)
    return max(24, min(int(settings["line_width"]), physical_columns))


def clean_text(value: object, *, limit: int) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = " ".join(text.split())
    if len(text) > limit:
        raise ValueError(f"field is longer than {limit} characters")
    return text


def validate_payload(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("JSON object expected")
    allowed = {"receipt_id", "title", "brand", "branch", "lines", "totals"}
    unexpected = set(raw) - allowed
    if unexpected:
        raise ValueError("unexpected field")
    receipt_id = clean_text(raw.get("receipt_id"), limit=96)
    if not receipt_id:
        raise ValueError("receipt_id is required")
    result: dict[str, Any] = {
        "receipt_id": receipt_id,
        "title": clean_text(raw.get("title") or "TO'LOV CHEKI", limit=120),
        "brand": clean_text(raw.get("brand") or "DIAMOND EDUCATION", limit=80),
        "branch": clean_text(raw.get("branch"), limit=120),
        "lines": [],
        "totals": [],
    }
    for key, maximum in (("lines", 18), ("totals", 4)):
        rows = raw.get(key, [])
        if not isinstance(rows, list) or len(rows) > maximum:
            raise ValueError(f"{key} has an invalid length")
        for row in rows:
            if not isinstance(row, dict) or set(row) - {"label", "value"}:
                raise ValueError(f"{key} row is invalid")
            label = clean_text(row.get("label"), limit=100)
            value = clean_text(row.get("value"), limit=180)
            if not label or not value:
                raise ValueError(f"{key} row needs label and value")
            result[key].append({"label": label, "value": value})
    return result


def display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1 for char in text)


def wrap_line(text: str, line_width: int = LINE_WIDTH) -> list[str]:
    # Payment data is Latin/Cyrillic in normal use.  textwrap preserves words
    # while the final slicing also gives a deterministic bound for long IDs.
    value = clean_text(text, limit=180)
    if not value:
        return [""]
    return textwrap.wrap(value, width=line_width, break_long_words=True, break_on_hyphens=False) or [""]


def receipt_lines(payload: dict[str, Any], settings: dict[str, float | int] | None = None) -> list[str]:
    line_width = printable_columns(validate_settings(settings or DEFAULT_SETTINGS))
    lines = [payload["brand"].upper(), payload["branch"], "-" * line_width, payload["title"].upper(), "-" * line_width]
    for row in payload["lines"]:
        lines.extend(wrap_line(row["label"], line_width))
        lines.extend(wrap_line(row["value"], line_width))
    if payload["totals"]:
        lines.append("-" * line_width)
        for row in payload["totals"]:
            lines.extend(wrap_line(row["label"], line_width))
            lines.extend(wrap_line(row["value"], line_width))
    lines.extend(["-" * line_width, f"CHEK ID: {payload['receipt_id']}"])
    return [line for line in lines if line]


def printable_line_lengths(payload: dict[str, Any]) -> list[int]:
    return [display_width(line) for line in receipt_lines(validate_payload(payload))]


def escpos_text(text: str) -> bytes:
    # CP866 is supported by common ESC/POS printers and keeps Russian labels
    # readable. Unsupported glyphs degrade safely instead of failing a receipt.
    return unicodedata.normalize("NFKC", text).encode("cp866", errors="replace")


def build_escpos_document(raw_payload: object, settings: dict[str, float | int] | None = None) -> bytes:
    payload = validate_payload(raw_payload)
    active_settings = validate_settings(settings or DEFAULT_SETTINGS)
    line_width = printable_columns(active_settings)
    job = bytearray(ESC_INIT)
    job.extend(ESC_ALIGN_CENTER + ESC_BOLD_ON)
    for line in wrap_line(payload["brand"].upper(), line_width):
        job.extend(escpos_text(line) + b"\n")
    job.extend(ESC_BOLD_OFF)
    if payload["branch"]:
        for line in wrap_line(payload["branch"], line_width):
            job.extend(escpos_text(line) + b"\n")
    job.extend(ESC_ALIGN_LEFT)
    for line in receipt_lines({**payload, "brand": "", "branch": ""}, active_settings)[2:]:
        job.extend(escpos_text(line) + b"\n")
    job.extend(b"\n\n\n" + ESC_CUT)
    return bytes(job)


def default_printer() -> str:
    if os.name == "nt":
        from ctypes import wintypes

        size = wintypes.DWORD(0)
        ctypes.windll.winspool.GetDefaultPrinterW(None, ctypes.byref(size))
        if not size.value:
            raise RuntimeError("Windows default printer is not configured")
        buffer = ctypes.create_unicode_buffer(size.value)
        if not ctypes.windll.winspool.GetDefaultPrinterW(buffer, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer.value
    return os.environ.get("DIAMOND_PRINTER", "").strip()


def print_windows(document: bytes, printer: str) -> None:
    from ctypes import wintypes

    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [("pDocName", wintypes.LPWSTR), ("pOutputFile", wintypes.LPWSTR), ("pDatatype", wintypes.LPWSTR)]

    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    handle = wintypes.HANDLE()
    if not winspool.OpenPrinterW(printer, ctypes.byref(handle), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        doc = DOC_INFO_1("Diamond Education receipt", None, "RAW")
        if not winspool.StartDocPrinterW(handle, 1, ctypes.byref(doc)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not winspool.StartPagePrinter(handle):
                raise ctypes.WinError(ctypes.get_last_error())
            written = wintypes.DWORD(0)
            buffer = ctypes.create_string_buffer(document)
            if not winspool.WritePrinter(handle, buffer, len(document), ctypes.byref(written)) or written.value != len(document):
                raise ctypes.WinError(ctypes.get_last_error())
            if not winspool.EndPagePrinter(handle):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            winspool.EndDocPrinter(handle)
    finally:
        winspool.ClosePrinter(handle)


def print_linux(document: bytes, printer: str) -> None:
    command = ["lp", "-o", "raw"]
    if printer:
        command.extend(["-d", printer])
    if not shutil.which("lp"):
        raise RuntimeError("CUPS 'lp' command was not found")
    completed = subprocess.run(command, input=document, check=False, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace").strip() or "printer rejected the job")


def send_to_printer(document: bytes, printer: str) -> str:
    selected = printer.strip() or default_printer()
    if os.name == "nt":
        if not selected:
            raise RuntimeError("Windows default printer is not configured")
        print_windows(document, selected)
        return selected
    print_linux(document, selected)
    return selected or "CUPS default"


class AgentHandler(BaseHTTPRequestHandler):
    server_version = "DiamondPrintAgent/1.0"

    def log_message(self, format: str, *args: object) -> None:
        # Do not log receipt content, student names, or payment values.
        print(f"[agent] {self.address_string()} {format % args}")

    def origin_is_allowed(self) -> bool:
        return not self.headers.get("Origin") or self.headers.get("Origin") in ALLOWED_ORIGINS

    def cors_headers(self) -> None:
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            if self.headers.get("Access-Control-Request-Private-Network") == "true":
                self.send_header("Access-Control-Allow-Private-Network", "true")

    def reply(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        if not self.origin_is_allowed():
            self.reply(HTTPStatus.FORBIDDEN, {"ok": False, "error": "origin is not allowed"})
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path not in {"/health", "/v1/settings"}:
            self.reply(HTTPStatus.NOT_FOUND, {"ok": False})
            return
        if not self.origin_is_allowed():
            self.reply(HTTPStatus.FORBIDDEN, {"ok": False, "error": "origin is not allowed"})
            return
        self.reply(HTTPStatus.OK, {
            "ok": True,
            "printer": self.server.printer or default_printer() or "CUPS default",
            "settings": self.server.settings,
        })

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in {"/v1/print", "/v1/settings"}:
            self.reply(HTTPStatus.NOT_FOUND, {"ok": False})
            return
        if not self.origin_is_allowed():
            self.reply(HTTPStatus.FORBIDDEN, {"ok": False, "error": "origin is not allowed"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY_BYTES:
                raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if self.path == "/v1/settings":
                self.server.settings = save_settings(payload, self.server.settings_path)
                self.reply(HTTPStatus.OK, {"ok": True, "settings": self.server.settings})
                return
            document = build_escpos_document(payload, self.server.settings)
            printer = send_to_printer(document, self.server.printer)
            self.reply(HTTPStatus.OK, {"ok": True, "printer": printer})
        except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
            self.reply(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        except Exception as exc:  # Printer errors must reach the website, not logs with receipt data.
            self.reply(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": str(exc)})


def main() -> int:
    parser = argparse.ArgumentParser(description="Diamond Education local receipt printer")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--printer", default=os.environ.get("DIAMOND_PRINTER", ""), help="Windows printer name or CUPS queue")
    parser.add_argument("--test", action="store_true", help="Print a short test receipt and exit")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    if args.test:
        sample = {"receipt_id": "TEST-LOCAL-PRINT", "title": "TEST CHEKI", "brand": "DIAMOND EDUCATION", "lines": [{"label": "Printer", "value": "Local agent ready"}], "totals": []}
        print(f"Test sent to: {send_to_printer(build_escpos_document(sample), args.printer)}")
        return 0
    httpd = ThreadingHTTPServer((HOST, args.port), AgentHandler)
    httpd.printer = args.printer.strip()
    httpd.settings_path = default_settings_path()
    httpd.settings = load_settings(httpd.settings_path)
    print(f"Diamond Print Agent ready on http://{HOST}:{args.port} (printer: {httpd.printer or 'default'})")
    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
