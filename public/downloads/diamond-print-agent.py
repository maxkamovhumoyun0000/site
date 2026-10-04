#!/usr/bin/env python3
"""Diamond Education local thermal-printer agent.

The agent is intentionally small and dependency-free.  It listens only on
127.0.0.1, accepts print jobs from the Diamond Education web application, and
sends ESC/POS bytes to the selected local printer.  It never exposes a network
port to other machines and it does not retain payment or student data.
"""

from __future__ import annotations

import argparse
import base64
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


HOST = "127.0.0.1"
PORT = 18765
LINE_WIDTH = 35  # 56mm XP-58IIL driver page at normal font size.
MAX_BODY_BYTES = 16_384
DEFAULT_SETTINGS = {
    "paper_width_mm": 56.0,
    "side_padding_mm": 1.5,
    "line_width": LINE_WIDTH,
    "agent_id": "",
    "agent_token": "",
    "branch_name": "",
    "station_name": "",
    "server_url": "https://diamond-education.uz/api",
}
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
ESC_FONT_COMPACT = b"\x1bM\x01"
ESC_FONT_NORMAL = b"\x1bM\x00"
# ESC J 144 feeds about 18 mm so a test receipt also exits the XP-58IIL mouth.
ESC_EJECT_BEFORE_CUT = b"\x1bJ\x90"
# GS V B n asks compatible cutters to cut after exactly n additional lines.
# Match the server document: feed four default vertical-motion units
# (4 × 0.125 mm = 0.5 mm) before cutting, without a driver-sized page tail.
ESC_CUT = b"\x1dV\x42\x04"
THERMAL_PRINTER_PATTERN = re.compile(r"(?:xp[-_ ]?58|xprinter|thermal|receipt|pos[-_ ]?58|58mm|tm[-_ ]?t)", re.IGNORECASE)
PAPER_OUT_MARKERS = (
    "media-empty", "media empty", "out of paper", "paper out", "paper-empty", "paper empty", "no paper",
)
UNAVAILABLE_MARKERS = ("disabled", "stopped", "offline", "unavailable", "not accepting")
PAPER_OUT_MESSAGE = "Printerda qog'oz tugagan. Rulonni almashtiring va qayta urinib ko'ring."


def default_settings_path() -> Path:
    configured = os.environ.get("DIAMOND_PRINT_AGENT_CONFIG", "").strip()
    if configured:
        return Path(configured)
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", ".")) / "DiamondEducation" / "PrintAgent" / "settings.json"
    return Path.home() / ".config" / "diamond-education" / "print-agent.json"


def validate_settings(raw: object) -> dict[str, float | int | str]:
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
    result: dict[str, float | int | str] = {
        "paper_width_mm": round(paper_width, 2), "side_padding_mm": round(side_padding, 2), "line_width": line_width,
    }
    for key, limit in (("agent_id", 80), ("agent_token", 160), ("branch_name", 100), ("station_name", 100)):
        value = " ".join(str(raw.get(key, "")).strip().split())
        if len(value) > limit:
            raise ValueError(f"{key} is too long")
        result[key] = value
    server_url = str(raw.get("server_url", DEFAULT_SETTINGS["server_url"])).strip().rstrip("/")
    if server_url and not re.match(r"^https://[^/]+(?:/[^?#]*)?$|^http://(?:127\.0\.0\.1|localhost)(?::\d+)?(?:/[^?#]*)?$", server_url):
        raise ValueError("server_url must be HTTPS")
    result["server_url"] = server_url
    return result


def load_settings(path: Path | None = None) -> dict[str, float | int | str]:
    target = path or default_settings_path()
    try:
        stored = validate_settings(json.loads(target.read_text(encoding="utf-8")))
        # Earlier agent builds used 57.5mm / 36 columns.  Migrate only that
        # untouched legacy default; a deliberately saved custom size remains.
        if (stored.get("paper_width_mm"), stored.get("side_padding_mm"), stored.get("line_width")) == (57.5, 1.5, 36):
            stored.update({"paper_width_mm": 56.0, "line_width": LINE_WIDTH})
            temporary = target.with_suffix(f"{target.suffix}.tmp")
            temporary.write_text(json.dumps(stored, ensure_ascii=False), encoding="utf-8")
            temporary.replace(target)
            if os.name != "nt":
                target.chmod(0o600)
        return stored
    except FileNotFoundError:
        return dict(DEFAULT_SETTINGS)
    except (OSError, ValueError, json.JSONDecodeError):
        # A corrupt local preference must never stop payment receipt printing.
        return dict(DEFAULT_SETTINGS)


def save_settings(raw: object, path: Path | None = None) -> dict[str, float | int | str]:
    target = path or default_settings_path()
    if not isinstance(raw, dict):
        raise ValueError("invalid printer settings")
    existing = load_settings(target)
    settings = validate_settings({**existing, **raw})
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    temporary.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)
    if os.name != "nt":
        target.chmod(0o600)
    return settings


def printable_columns(settings: dict[str, float | int | str]) -> int:
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


def decode_print_document(raw: object) -> bytes:
    """Accept only a server-generated, ready-to-spool ESC/POS document."""
    if not isinstance(raw, dict) or set(raw) - {"receipt_id", "document_base64"}:
        raise ValueError("server print document is invalid")
    encoded = clean_text(raw.get("document_base64"), limit=MAX_BODY_BYTES)
    try:
        document = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValueError("server print document is invalid") from exc
    if not 8 <= len(document) <= MAX_BODY_BYTES or not document.startswith(ESC_INIT) or not document.endswith(ESC_CUT):
        raise ValueError("server print document is invalid")
    return document


def legacy_plain_text_document(document: bytes) -> bytes:
    """Keep formatting and eject controls, but remove unsupported cutter bytes.

    Some USB receipt mechanisms visibly print the cutter bytes from ``GS V B
    04`` as ``42 04``.  They can still understand the common compact-font and
    alignment controls, which must be retained so this receipt matches the
    primary XP-58IIL.  The server remains responsible for rendering and its
    ESC J eject distance is retained, so the footer margin matches the primary
    printer.  Only the unsupported raw cutter command is removed.
    """
    rendered = bytearray()
    cursor = 0
    while cursor < len(document):
        current = document[cursor]
        if current == 0x1B:  # ESC: retain formatting and the standard eject feed.
            command = document[cursor + 1] if cursor + 1 < len(document) else None
            if command == ord("@"):
                rendered.extend(document[cursor:cursor + 2])
                cursor += 2
                continue
            if command in (ord("t"), ord("a"), ord("E"), ord("M"), ord("J")) and cursor + 2 < len(document):
                rendered.extend(document[cursor:cursor + 3])
                cursor += 3
                continue
            cursor += 3 if cursor + 2 < len(document) else 2
            continue
        if current == 0x1D and document[cursor + 1:cursor + 3] == b"VB":  # GS V B n cut.
            cursor += 4
            continue
        if current in (0x0A, 0x0D, 0x09) or current >= 0x20:
            rendered.append(current)
        cursor += 1
    return bytes(rendered).rstrip(b"\r\n")


def sanitized_settings(settings: dict[str, float | int | str]) -> dict[str, float | int | str | bool]:
    return {
        key: settings[key]
        for key in ("paper_width_mm", "side_padding_mm", "line_width", "agent_id", "branch_name", "station_name")
    } | {"registered": bool(settings.get("agent_id") and settings.get("agent_token"))}


def linux_printer_inventory() -> tuple[list[str], str]:
    """Read CUPS queues and its default without relying on desktop settings."""
    if not shutil.which("lpstat"):
        raise RuntimeError("CUPS client topilmadi; avval Linux installerini ishga tushiring")
    queues = subprocess.run(["lpstat", "-p"], check=False, capture_output=True, text=True)
    if queues.returncode != 0:
        raise RuntimeError(queues.stderr.strip() or "CUPS printer ro'yxatini o'qib bo'lmadi")
    names = [match.group(1) for line in queues.stdout.splitlines() if (match := re.match(r"^printer\s+(\S+)", line))]
    default = subprocess.run(["lpstat", "-d"], check=False, capture_output=True, text=True)
    default_match = re.search(r":\s*(\S+)\s*$", default.stdout)
    return names, default_match.group(1) if default_match else ""


def choose_thermal_printer(printers: list[str], default: str) -> str:
    """Prefer a receipt queue and never silently send a receipt to a random A4 printer."""
    names = [str(name).strip() for name in printers if str(name).strip()]
    thermal = [name for name in names if THERMAL_PRINTER_PATTERN.search(name)]
    if len(thermal) == 1:
        return thermal[0]
    if len(thermal) > 1 and default in thermal:
        return default
    if len(names) == 1:
        return names[0]
    if default and default in names and not thermal:
        return default
    if not names:
        raise RuntimeError("CUPS printer topilmadi; printerni Linux sozlamalarida qo'shing")
    raise RuntimeError("Termal printerni aniqlab bo'lmadi; DIAMOND_PRINTER bilan queue nomini belgilang")


def choose_linux_printer(printers: list[str], default: str) -> str:
    """Compatibility wrapper for Linux-specific tests and diagnostics."""
    return choose_thermal_printer(printers, default)


def windows_printer_inventory() -> tuple[list[str], str]:
    """Enumerate local/network queues through Winspool without external tools."""
    from ctypes import wintypes

    class PRINTER_INFO_4W(ctypes.Structure):
        _fields_ = [("pPrinterName", wintypes.LPWSTR), ("pServerName", wintypes.LPWSTR), ("Attributes", wintypes.DWORD)]

    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    needed = wintypes.DWORD(0)
    returned = wintypes.DWORD(0)
    flags = 0x00000002 | 0x00000004  # PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS
    winspool.EnumPrintersW(flags, None, 4, None, 0, ctypes.byref(needed), ctypes.byref(returned))
    if not needed.value:
        return [], ""
    buffer = (ctypes.c_byte * needed.value)()
    if not winspool.EnumPrintersW(flags, None, 4, buffer, needed.value, ctypes.byref(needed), ctypes.byref(returned)):
        raise ctypes.WinError(ctypes.get_last_error())
    records = ctypes.cast(buffer, ctypes.POINTER(PRINTER_INFO_4W))
    names = [records[index].pPrinterName for index in range(returned.value) if records[index].pPrinterName]
    size = wintypes.DWORD(0)
    winspool.GetDefaultPrinterW(None, ctypes.byref(size))
    if not size.value:
        return names, ""
    default = ctypes.create_unicode_buffer(size.value)
    if not winspool.GetDefaultPrinterW(default, ctypes.byref(size)):
        return names, ""
    return names, default.value


def default_printer() -> str:
    if os.name == "nt":
        configured = os.environ.get("DIAMOND_PRINTER", "").strip()
        if configured:
            return configured
        printers, default = windows_printer_inventory()
        return choose_thermal_printer(printers, default)
    configured = os.environ.get("DIAMOND_PRINTER", "").strip()
    if configured:
        return configured
    printers, default = linux_printer_inventory()
    return choose_linux_printer(printers, default)


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


def send_to_printer(document: bytes, printer: str, *, plain_text: bool = False) -> str:
    selected = printer.strip() or default_printer()
    if plain_text:
        document = legacy_plain_text_document(document)
    if os.name == "nt":
        if not selected:
            raise RuntimeError("Windows default printer is not configured")
        print_windows(document, selected)
        return selected
    print_linux(document, selected)
    return selected


def detected_printer_name(configured: str) -> tuple[str, str]:
    try:
        return configured or default_printer(), ""
    except RuntimeError as exc:
        return "", str(exc)


def paper_status_from_text(value: object) -> str:
    """Classify only explicit driver/CUPS state; unknown never pretends the roll is present."""
    text = " ".join(str(value or "").lower().replace("_", "-").split())
    if any(marker in text for marker in PAPER_OUT_MARKERS):
        return "paper_out"
    if any(marker in text for marker in UNAVAILABLE_MARKERS):
        return "unavailable"
    if any(marker in text for marker in (" is idle", " ready", " enabled", "printing")):
        return "ready"
    return "unknown"


def printer_paper_status(printer: str) -> tuple[str, str]:
    """Return a conservative paper state without sending or retaining a receipt.

    CUPS exposes media-empty for drivers that implement it. Many Windows USB
    drivers do not expose a consumable state to raw spooler clients, so the
    caller keeps that result as unknown and also classifies print errors.
    """
    if not printer:
        return "unavailable", "Termal printer topilmadi."
    if os.name == "nt":
        return "unknown", "Windows drayveri qog'oz holatini bermadi; chop etish xatosi kuzatiladi."
    if not shutil.which("lpstat"):
        return "unknown", "CUPS qog'oz holatini o'qib bo'lmadi."
    completed = subprocess.run(["lpstat", "-l", "-p", printer], check=False, capture_output=True, text=True)
    details = f"{completed.stdout}\n{completed.stderr}"
    state = paper_status_from_text(details)
    if state == "paper_out":
        return state, PAPER_OUT_MESSAGE
    if completed.returncode != 0 or state == "unavailable":
        return "unavailable", (completed.stderr.strip() or "Printer tayyor emas.")
    if state == "ready":
        return state, ""
    return "unknown", "Printer drayveri qog'oz holatini aniq bermadi."


class PrinterPaperOutError(RuntimeError):
    """A distinct error lets the website avoid opening an incorrect PDF fallback."""


def report_agent_heartbeat(settings: dict[str, float | int | str], printer_name: str) -> bool:
    """Send an agent heartbeat containing only station health, never receipt data."""
    agent_id = str(settings.get("agent_id") or "").strip()
    agent_token = str(settings.get("agent_token") or "").strip()
    server_url = str(settings.get("server_url") or "").strip().rstrip("/")
    if not agent_id or not agent_token or not server_url:
        return False
    body = json.dumps({
        "agent_id": agent_id,
        "printer_name": printer_name,
        "platform": sys.platform,
        "settings": sanitized_settings(settings),
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{server_url}/developer/print-agents/heartbeat",
        data=body,
        headers={"Content-Type": "application/json", "X-Diamond-Print-Agent": agent_token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return 200 <= int(response.status) < 300
    except (OSError, urllib.error.URLError, urllib.error.HTTPError):
        return False


def agent_heartbeat_loop(server: ThreadingHTTPServer) -> None:
    while not server.heartbeat_stop.wait(60):
        printer_name, _ = detected_printer_name(server.printer)
        report_agent_heartbeat(server.settings, printer_name)


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
        printer, printer_error = detected_printer_name(self.server.printer)
        paper_status, paper_message = (
            ("unavailable", printer_error or "Termal printer topilmadi.")
            if printer_error else printer_paper_status(printer)
        )
        self.reply(HTTPStatus.OK, {
            "ok": True,
            "printer": printer,
            "printer_error": printer_error,
            "paper_status": paper_status,
            "paper_message": paper_message,
            "settings": sanitized_settings(self.server.settings),
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
                printer_name, _ = detected_printer_name(self.server.printer)
                threading.Thread(target=report_agent_heartbeat, args=(self.server.settings, printer_name), daemon=True).start()
                self.reply(HTTPStatus.OK, {"ok": True, "settings": sanitized_settings(self.server.settings)})
                return
            printer, printer_error = detected_printer_name(self.server.printer)
            if printer_error:
                raise RuntimeError(printer_error)
            paper_status, paper_message = printer_paper_status(printer)
            if paper_status == "paper_out":
                raise PrinterPaperOutError(paper_message)
            document = decode_print_document(payload)
            printer = send_to_printer(document, printer, plain_text=self.server.plain_text)
            self.reply(HTTPStatus.OK, {"ok": True, "printer": printer, "paper_status": paper_status, "paper_message": paper_message})
        except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
            self.reply(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        except PrinterPaperOutError as exc:
            self.reply(HTTPStatus.CONFLICT, {"ok": False, "error": str(exc), "paper_status": "paper_out", "paper_message": str(exc)})
        except Exception as exc:  # Printer errors must reach the website, not logs with receipt data.
            paper_status = paper_status_from_text(exc)
            paper_message = PAPER_OUT_MESSAGE if paper_status == "paper_out" else ""
            self.reply(HTTPStatus.SERVICE_UNAVAILABLE, {
                "ok": False,
                "error": paper_message or str(exc),
                "paper_status": paper_status,
                "paper_message": paper_message,
            })


def main() -> int:
    parser = argparse.ArgumentParser(description="Diamond Education local receipt printer")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--printer", default=os.environ.get("DIAMOND_PRINTER", ""), help="Windows printer name or CUPS queue")
    parser.add_argument("--plain-text", action="store_true", help="Legacy printer mode: remove ESC/POS cut/feed controls")
    parser.add_argument("--test", action="store_true", help="Print a short test receipt and exit")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    if args.test:
        separator = b"-" * LINE_WIDTH
        diagnostic = (
            ESC_INIT + ESC_ALIGN_CENTER + ESC_FONT_COMPACT + b"DIAMOND EDUCATION\n"
            + ESC_ALIGN_LEFT + separator + b"\n"
            + b"TEST CHEK\nJoriy to'lov: 15 000 SO'M\nJami to'langan: 15 000 SO'M\nQoldiq: 0 SO'M\n"
            + separator + b"\nChek ID: TEST\n" + ESC_FONT_NORMAL + ESC_EJECT_BEFORE_CUT + ESC_CUT
        )
        print(f"Test sent to: {send_to_printer(diagnostic, args.printer, plain_text=args.plain_text)}")
        return 0
    httpd = ThreadingHTTPServer((HOST, args.port), AgentHandler)
    httpd.printer = args.printer.strip()
    httpd.plain_text = args.plain_text
    httpd.settings_path = default_settings_path()
    httpd.settings = load_settings(httpd.settings_path)
    httpd.heartbeat_stop = threading.Event()
    printer_name, _ = detected_printer_name(httpd.printer)
    report_agent_heartbeat(httpd.settings, printer_name)
    threading.Thread(target=agent_heartbeat_loop, args=(httpd,), name="agent heartbeat", daemon=True).start()
    print(f"Diamond Print Agent ready on http://{HOST}:{args.port} (printer: {httpd.printer or 'default'})")
    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.heartbeat_stop.set()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
