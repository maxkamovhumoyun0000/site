from __future__ import annotations

from push_notifications import _is_dead_fcm_token_error


class FcmError(Exception):
    def __init__(self, message: str, code: str = "") -> None:
        super().__init__(message)
        self.code = code


def test_legacy_not_registered_message_is_pruned() -> None:
    assert _is_dead_fcm_token_error(FcmError("NotRegistered"))


def test_modern_unregistered_code_is_pruned() -> None:
    assert _is_dead_fcm_token_error(
        FcmError(
            "Requested entity was not found",
            code="messaging/registration-token-not-registered",
        )
    )


def test_invalid_argument_payload_error_does_not_prune_token() -> None:
    assert not _is_dead_fcm_token_error(
        FcmError("Invalid payload field: title", code="invalid-argument")
    )


def test_invalid_registration_token_is_pruned() -> None:
    assert _is_dead_fcm_token_error(
        FcmError("The registration token is not valid", code="invalid-argument")
    )
