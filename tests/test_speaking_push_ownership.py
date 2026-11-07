"""Private FCM routing must not be reassigned using a device ID alone."""

from push_notifications import _speaking_competition_product, _speaking_product_matches, _speaking_token_update_allowed, speaking_push_route_product


def test_owner_can_rotate_a_token():
    assert _speaking_token_update_allowed(17, 17, "old-token", "new-token")


def test_other_user_or_anonymous_request_cannot_replace_a_bound_token():
    assert not _speaking_token_update_allowed(17, 23, "owner-token", "attacker-token")
    assert not _speaking_token_update_allowed(17, None, "owner-token", "attacker-token")


def test_same_installation_can_log_out_and_switch_accounts():
    assert _speaking_token_update_allowed(17, None, "owner-token", "owner-token")
    assert _speaking_token_update_allowed(17, 23, "owner-token", "owner-token")


def test_anonymous_registration_and_rotation_are_supported():
    assert _speaking_token_update_allowed(None, None, "old-token", "new-token")


def test_unreadable_token_cannot_prove_ownership():
    assert not _speaking_token_update_allowed(17, 23, "", "")


def test_product_targeting_excludes_unknown_and_other_language_devices():
    assert _speaking_product_matches("russian", "russian")
    assert not _speaking_product_matches("english", "russian")
    assert not _speaking_product_matches(None, "russian")
    assert _speaking_product_matches("english", None)
    assert _speaking_product_matches("russian", None)
    assert _speaking_product_matches(None, None)


def test_competition_subject_is_scoped_but_chat_remains_shared():
    assert _speaking_competition_product({"notification_type": "competition_waiting", "subject": "Russian"}) == "russian"
    assert _speaking_competition_product({"notification_type": "competition_waiting", "subject": "English"}) == "english"
    assert _speaking_competition_product({"notification_type": "chat", "subject": "Russian"}) is None
    assert _speaking_competition_product({"notification_type": "competition_waiting", "subject": "unknown"}) is None


def test_authenticated_product_overrides_untrusted_header():
    assert speaking_push_route_product(17, "russian", "english") == "russian"
    assert speaking_push_route_product(None, "english", "russian") == "russian"
    assert speaking_push_route_product(None, "english", "unknown") is None
    assert speaking_push_route_product(None, "english", "") is None
