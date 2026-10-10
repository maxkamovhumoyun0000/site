from __future__ import annotations

import unittest
from cryptography.fernet import Fernet, InvalidToken

from logging_config import SensitiveDataFilter
from token_encryption import TokenCipher, TokenEncryptionConfigurationError


class SpeakingTokenSecurityTests(unittest.TestCase):
    def test_fcm_token_is_encrypted_and_authenticated(self) -> None:
        cipher = TokenCipher(Fernet.generate_key().decode("ascii"))
        token = "fcm-registration-token-which-must-not-be-stored-in-plain-text"

        encrypted = cipher.encrypt(token)

        self.assertTrue(encrypted.startswith("enc:v1:"))
        self.assertNotIn(token, encrypted)
        self.assertEqual(cipher.decrypt(encrypted), token)

        tampered = encrypted[:-1] + ("A" if encrypted[-1] != "A" else "B")
        with self.assertRaises(InvalidToken):
            cipher.decrypt(tampered)

    def test_token_cipher_rejects_missing_or_invalid_key(self) -> None:
        with self.assertRaises(TokenEncryptionConfigurationError):
            TokenCipher.from_environment({})
        with self.assertRaises(TokenEncryptionConfigurationError):
            TokenCipher("not-a-fernet-key")

    def test_log_filter_redacts_push_tokens(self) -> None:
        message = 'push_token="fcm-registration-token-which-must-not-be-logged"'

        redacted = SensitiveDataFilter.redact(message)

        self.assertNotIn("fcm-registration-token-which-must-not-be-logged", redacted)
        self.assertIn("push_token=[REDACTED]", redacted)
