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

    _key_value = re.compile(
        r"(?i)(password|passcode|authorization|bearer|access[_-]?token|refresh[_-]?token|"
        r"(?:fcm|push|device)[_-]?token|"
        r"session(?:[_-]?id|[_-]?token)?|api[_-]?key|secret|private[_-]?key|otp|"
        r"reset[_-]?token|cookie)\s*([:=])\s*([^\s,;}\]]+)",
    )
    _bearer = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
    _phone = re.compile(r"(?<!\d)(\+?998)\d{7,12}(?!\d)")

    @classmethod
    def redact(cls, value: object) -> str:
        text = str(value)
        text = cls._bearer.sub("Bearer [REDACTED]", text)
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
    root._diamond_logging_configured = True  # type: ignore[attr-defined]
    return logging.getLogger(__name__)

def get_logger(name: str):
    """Get a specific logger with proper configuration"""
    return logging.getLogger(name)

# Initialize logging when module is imported
main_logger = setup_logging()
