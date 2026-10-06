from __future__ import annotations

import pytest

import backend.main as api


@pytest.mark.asyncio
async def test_removing_group_member_queues_payment_recalculation(monkeypatch: pytest.MonkeyPatch) -> None:
    """A roster removal must return without doing payment work inline."""
    removed: list[tuple[int, int, str | None, bool]] = []
    queued: list[dict] = []

    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: {"id": 44, "login_type": 4})
    monkeypatch.setattr(api, "_require_role", lambda _user, _roles: "admin")
    monkeypatch.setattr(api, "_admin_ref_id", lambda _user: 44)
    monkeypatch.setattr(api, "get_group", lambda _group_id: {"id": 9, "owner_admin_id": 44})
    monkeypatch.setattr(api, "get_user_by_id", lambda _student_id: {"id": 7, "login_type": 1})
    monkeypatch.setattr(api, "_can_manage_group", lambda _admin_id, _group: True)
    monkeypatch.setattr(api, "_can_manage_user_globally", lambda _admin_id, _student: True)
    monkeypatch.setattr(
        api,
        "remove_user_from_group",
        lambda user_id, group_id, removed_at=None, is_mistake=False: removed.append(
            (user_id, group_id, removed_at, is_mistake)
        ),
    )
    monkeypatch.setattr(api, "_clear_user_media_caches", lambda _student_id: None)
    monkeypatch.setattr(
        api,
        "_payment_prewarm_user_month_obligations",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("payment work must not run inline")),
    )
    monkeypatch.setattr(
        api,
        "_payment_prewarm_users_month_async",
        lambda **kwargs: queued.append(kwargs),
    )
    monkeypatch.setattr(
        api,
        "_group_membership_change_payload",
        lambda group_id, student_id, message: {"group_id": group_id, "student_id": student_id, "message": message},
    )

    payload = await api.admin_remove_group_member(
        9,
        7,
        removed_at="2026-10-06",
        authorization="Bearer test",
    )

    assert payload["message"] == "Student removed from group"
    assert removed == [(7, 9, "2026-10-06", False)]
    assert queued == [
        {
            "user_ids": {7},
            "reason": "admin_remove_group_member",
        }
    ]
