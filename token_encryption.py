"""Authenticated encryption helpers for device tokens and local log records.

The server never writes the clear-text value of an FCM token to the database.
Keys can be supplied independently for each use case; in their absence a
domain-separated key is derived from the mandatory server JWT secret.  This
keeps existing deployments operational while avoiding a hard-coded key.
"""
from __future__ import annotations

import base64
import hashlib
import os
from collections.abc import Mapping

from cryptography.fernet import Fernet


ENCRYPTED_VALUE_PREFIX = "enc:v1:"


class TokenEncryptionConfigurationError(RuntimeError):
    """Raised when no server secret is available for authenticated encryption."""


class TokenCipher:
    """Small versioned Fernet wrapper used for sensitive server-side values."""

    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode("ascii"))
        except Exception as exc:
            raise TokenEncryptionConfigurationError("Invalid encryption key configuration") from exc

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        key_name: str = "PUSH_TOKEN_ENCRYPTION_KEY",
        derivation_context: str = "push-token",
    ) -> "TokenCipher":
        env = environment if environment is not None else os.environ
        configured_key = str(env.get(key_name) or "").strip()
        if configured_key:
            return cls(configured_key)

        jwt_secret = str(env.get("JWT_SECRET") or "").strip()
        if not jwt_secret or jwt_secret == "change-this-in-production":
            raise TokenEncryptionConfigurationError(
                f"{key_name} or a non-default JWT_SECRET must be configured",
            )
        # A domain-separated derived key prevents a log key and a push-token
        # key from being interchangeable while retaining backward-compatible
        # secure operation for deployments that already have JWT_SECRET.
        material = hashlib.sha256(
            f"diamond:{derivation_context}:v1:{jwt_secret}".encode("utf-8"),
        ).digest()
        return cls(base64.urlsafe_b64encode(material).decode("ascii"))

    def encrypt(self, value: str) -> str:
        text = str(value or "")
        if not text:
            return ""
        return ENCRYPTED_VALUE_PREFIX + self._fernet.encrypt(text.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        text = str(value or "")
        if not text:
            return ""
        if not text.startswith(ENCRYPTED_VALUE_PREFIX):
            # This branch is used only during the one-time migration of legacy
            # values; callers must write the returned value back encrypted.
            return text
        return self._fernet.decrypt(text[len(ENCRYPTED_VALUE_PREFIX):].encode("ascii")).decode("utf-8")
