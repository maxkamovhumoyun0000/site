import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from token_encryption import TokenCipher, TokenEncryptionConfigurationError

# Create logs directory if it doesn't exist
log_dir = Path("logs")

# Configure logging format
LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


class SensitiveDataFilter(logging.Filter):
    """Redact credentials and common PII before a record reaches any handler.

    This is deliberately a logging boundary, not a substitute for avoiding
    sensitive values in log calls.  It protects both application loggers and
    third-party loggers that propagate to the root logger.
    """

    _key_names = (
        r"password|passcode|passwd|authorization|bearer|access[_-]?token|refresh[_-]?token|"
        r"(?:fcm|push|device)[_-]?token|"
        r"session(?:[_-]?id|[_-]?token|[_-]?string)?|api[_-]?key|api[_-]?hash|secret|private[_-]?key|otp|"
        r"reset[_-]?token|cookie|agent[_-]?token|qr[_-]?token|init[_-]?data"
    )
    # key=value / key: value, and JSON/dict style "key": "value" / 'key': 'value'.
    _key_value = re.compile(
        r"(?i)([\"']?(?:" + _key_names + r")[\"']?)\s*([:=])\s*(\"[^\"]*\"|'[^']*'|[^\s,;}\]]+)",
    )
    _bearer = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
    # Telegram bot tokens, e.g. in api.telegram.org/bot<token>/sendMessage URLs.
    _telegram_bot_token = re.compile(r"(?<!\d)\d{6,12}:[A-Za-z0-9_-]{30,}")
    # Credentials embedded in connection URLs (postgresql://user:pass@host).
    _url_credentials = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^\s:/@]+):[^\s@/]+@")
    _phone = re.compile(r"(?<!\d)(\+?998)\d{7,12}(?!\d)")
    # Provider keys that may appear without a "key=" prefix (xAI, OpenAI,
    # Google/Firebase, Deepgram/LiveKit style), and signed JWTs.
    _provider_key = re.compile(
        r"\b(?:xai-[A-Za-z0-9]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|"
        r"gsk_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,})"
    )
    _jwt = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+")
    # Secrets in URL query strings, e.g. /voice-room-ws?token=... or ?key=...
    _query_secret = re.compile(r"(?i)([?&](?:token|access_token|key|api_key|sig|signature|code)=)[^&\s\"']+")
    # Exact values of secret environment variables, built lazily so values
    # loaded after import (dotenv/systemd) are covered too.
    _env_secret_re: re.Pattern[str] | None = None
    _env_secret_count = -1

    _env_size = -1

    @classmethod
    def _env_secrets(cls) -> re.Pattern[str] | None:
        # Rebuild only when the environment changes (cheap per-record check).
        if len(os.environ) == cls._env_size:
            return cls._env_secret_re
        cls._env_size = len(os.environ)
        names = re.compile(r"(?i)(KEY|SECRET|TOKEN|PASSWORD|PASSWD|DSN|DATABASE_URL|API_HASH|PRIVATE)")
        values = sorted(
            {
                str(value)
                for name, value in os.environ.items()
                if names.search(name) and len(str(value or "").strip()) >= 12
            },
            key=len,
            reverse=True,
        )
        if len(values) != cls._env_secret_count:
            cls._env_secret_count = len(values)
            cls._env_secret_re = re.compile("|".join(re.escape(value) for value in values)) if values else None
        return cls._env_secret_re

    @classmethod
    def redact(cls, value: object) -> str:
        text = str(value)
        env_re = cls._env_secrets()
        if env_re is not None:
            text = env_re.sub("[REDACTED_SECRET]", text)
        text = cls._bearer.sub("Bearer [REDACTED]", text)
        text = cls._jwt.sub("[REDACTED_JWT]", text)
        text = cls._provider_key.sub("[REDACTED_KEY]", text)
        text = cls._telegram_bot_token.sub("[REDACTED_BOT_TOKEN]", text)
        text = cls._url_credentials.sub(lambda match: f"{match.group(1)}:[REDACTED]@", text)
        text = cls._query_secret.sub(lambda match: f"{match.group(1)}[REDACTED]", text)
        text = cls._key_value.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", text)
        return cls._phone.sub(lambda match: f"{match.group(1)}***{match.group(0)[-3:]}", text)

    def filter(self, record: logging.LogRecord) -> bool:
        # Render first so %-format arguments cannot bypass the sanitizer.
        try:
            rendered = record.getMessage()
        except Exception:
            rendered = str(record.msg)
        record.msg = self.redact(rendered)
        record.args = ()
        # Format and redact tracebacks before the handler formatter can append
        # them. Exception messages often include request headers or payloads.
        if record.exc_info:
            try:
                record.exc_text = self.redact(logging.Formatter().formatException(record.exc_info))
                record.exc_info = None
            except Exception:
                record.exc_info = None
        return True


class EncryptedRotatingFileHandler(RotatingFileHandler):
    """Stores development log records as independent authenticated ciphertexts."""

    def __init__(self, filename: Path, cipher: TokenCipher, **kwargs: object) -> None:
        self._cipher = cipher
        super().__init__(filename, **kwargs)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            self.acquire()
            if self.shouldRollover(record):
                self.doRollover()
            self.stream.write(self._cipher.encrypt(message) + "\n")
            self.flush()
        except Exception:
            self.handleError(record)
        finally:
            self.release()

def setup_logging():
    """Configure redacted, production-safe application logging.

    Production writes to stdout only, so the platform's protected log service
    controls retention and encryption-at-rest. Local file logging is opt-in
    for development and uses small, mode-0600 rotating files.
    """
    root = logging.getLogger()
    if getattr(root, "_diamond_logging_configured", False):
        return logging.getLogger(__name__)
    production = os.getenv("DIAMOND_ENV", "").strip().lower() == "production"
    level = logging.INFO if production else logging.DEBUG
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    sanitizer = SensitiveDataFilter()
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.addFilter(sanitizer)
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(console)

    if not production and os.getenv("DIAMOND_FILE_LOGGING", "").strip().lower() in {"1", "true", "yes"}:
        log_dir.mkdir(mode=0o700, exist_ok=True)
        try:
            log_cipher = TokenCipher.from_environment(
                key_name="LOG_ENCRYPTION_KEY",
                derivation_context="application-log",
            )
        except TokenEncryptionConfigurationError as exc:
            raise RuntimeError("Encrypted file logging requires LOG_ENCRYPTION_KEY or JWT_SECRET") from exc
        file_handler = EncryptedRotatingFileHandler(
            log_dir / "bot.log",
            cipher=log_cipher,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(sanitizer)
        root.addHandler(file_handler)
        try:
            os.chmod(log_dir / "bot.log", 0o600)
        except OSError:
            pass

    logging.getLogger('aiogram').setLevel(logging.INFO)
    logging.getLogger('aiogram.event').setLevel(logging.INFO)
    # uvicorn installs its own non-propagating handlers, so its records never
    # reach the root filter (WebSocket lines include ?token=<JWT>). A logger
    # level filter runs before any of that logger's handlers.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "aiohttp.access", "httpx", "telethon", "pyrogram"):
        third_party = logging.getLogger(name)
        if not any(isinstance(item, SensitiveDataFilter) for item in third_party.filters):
            third_party.addFilter(sanitizer)
    # Client libraries log full request URLs (Telegram bot URLs carry the
    # bot token) at INFO/DEBUG; keep them at WARNING outside debugging.
    for name in ("httpx", "httpcore", "urllib3", "aiohttp.client"):
        logging.getLogger(name).setLevel(logging.WARNING)
    root._diamond_logging_configured = True  # type: ignore[attr-defined]
    return logging.getLogger(__name__)


def safe_error_text(error: object, limit: int = 300) -> str:
    """Exception text that is safe to show to a user or chat (redacted, short)."""
    text = SensitiveDataFilter.redact(str(error or "")).strip()
    return (text[:limit].rstrip() + "…") if len(text) > limit else text

def get_logger(name: str):
    """Get a specific logger with proper configuration"""
    return logging.getLogger(name)

# Initialize logging when module is imported
main_logger = setup_logging()
