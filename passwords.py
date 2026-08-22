"""Password hashing / verification shared by backend, bots and migration scripts.

Single source of truth for how user passwords are stored and checked.
Storage format is bcrypt (`$2b$...`); rows written before this module existed
may still contain legacy plaintext and are accepted by `verify_password`
so a gradual migration is possible (see scripts/migrate_passwords_to_bcrypt.py).

Uses the `bcrypt` library directly instead of passlib: the installed
passlib 1.7.4 is incompatible with bcrypt>=4.1 (its backend version probe
crashes), and no passlib feature beyond raw hash/verify is needed here.
"""
import logging
import secrets
import string

try:
    import bcrypt as _bcrypt
except ImportError:  # pragma: no cover - bcrypt is in requirements
    _bcrypt = None
    logging.getLogger("passwords").error("bcrypt library not installed; hashing disabled")

logger = logging.getLogger("passwords")

_BCRYPT_PREFIXES = ("$2b$", "$2a$", "$2y$", "$2c$")
_BCRYPT_MAX_PASSWORD_BYTES = 72  # bcrypt's inherent limit; new libs raise instead of truncating
_BCRYPT_ROUNDS = 12
_UPPER_DIGITS = string.ascii_uppercase + string.digits


def is_password_hash(stored) -> bool:
    """True if the stored value is already a bcrypt hash."""
    stored_clean = str(stored or "").strip()
    return stored_clean.startswith(_BCRYPT_PREFIXES)


def hash_password(plain) -> str:
    """Hash a plaintext password with bcrypt."""
    if _bcrypt is None:
        raise RuntimeError("bcrypt is not installed; cannot hash passwords")
    raw = str(plain or "").encode("utf-8")[:_BCRYPT_MAX_PASSWORD_BYTES]
    return _bcrypt.hashpw(raw, _bcrypt.gensalt(rounds=_BCRYPT_ROUNDS, prefix=b"2b")).decode("ascii")


def verify_password(incoming, stored) -> bool:
    """Check a submitted password against a stored value.

    - bcrypt hashes: constant-time bcrypt verify (also tries the uppercase
      form, because legacy passwords were generated uppercase and users may
      type them in lowercase).
    - legacy plaintext rows: constant-time, case-insensitive comparison.
    - empty incoming or empty stored: never valid.
    """
    incoming_clean = str(incoming or "").strip()
    stored_clean = str(stored or "").strip()
    if not incoming_clean or not stored_clean:
        return False
    if is_password_hash(stored_clean):
        if _bcrypt is None:
            return False
        raw = incoming_clean.encode("utf-8")[:_BCRYPT_MAX_PASSWORD_BYTES]
        try:
            if _bcrypt.checkpw(raw, stored_clean.encode("ascii")):
                return True
            upper = incoming_clean.upper()
            if upper != incoming_clean:
                return _bcrypt.checkpw(upper.encode("utf-8")[:_BCRYPT_MAX_PASSWORD_BYTES], stored_clean.encode("ascii"))
            return False
        except ValueError:
            # malformed stored hash
            logger.warning("malformed bcrypt hash rejected")
            return False
    return secrets.compare_digest(incoming_clean.upper(), stored_clean.upper())


def generate_password(length: int = 6, chars: str = _UPPER_DIGITS) -> str:
    """Cryptographically secure password generation (replaces random.choices)."""
    pool = str(chars or _UPPER_DIGITS)
    return "".join(secrets.choice(pool) for _ in range(max(1, int(length))))


def generate_otp(length: int = 6) -> str:
    """Cryptographically secure numeric OTP code."""
    return "".join(secrets.choice(string.digits) for _ in range(max(1, int(length))))
