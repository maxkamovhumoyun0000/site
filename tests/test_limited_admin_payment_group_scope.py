from __future__ import annotations

import backend.main as api


def test_limited_admin_payment_scope_follows_group_not_student_creator(monkeypatch) -> None:
    own_group = {"id": 20, "owner_admin_id": 222}
    other_group = {"id": 10, "owner_admin_id": 111}
    # The student was created by admin 111, but currently belongs to admin
    # 222's group. Payment access must follow that group assignment.
    monkeypatch.setattr(api, "_is_general_admin_scope", lambda _admin_id: False)
    monkeypatch.setattr(api, "get_user_by_id", lambda _user_id: {"id": 700, "login_type": 2, "owner_admin_id": 111})
    monkeypatch.setattr(api, "get_user_groups", lambda _user_id: [own_group])
    monkeypatch.setattr(api, "get_group", lambda group_id: own_group if group_id == 20 else other_group)
    monkeypatch.setattr(api, "_can_manage_group", lambda admin_id, group: admin_id == 222 and group.get("owner_admin_id") == 222)
    monkeypatch.setattr(api, "get_all_groups", lambda: [own_group, other_group])
    monkeypatch.setattr(api, "_scope_groups_for_admin", lambda _admin_id, groups: [g for g in groups if g["id"] == 20])

    assert api._student_in_manageable_payment_group(222, 700)
    assert api._student_in_manageable_payment_group(222, 700, 20)
    assert not api._student_in_manageable_payment_group(222, 700, 10)


def test_limited_admin_can_reach_removed_student_payment_for_scoped_group(monkeypatch) -> None:
    group = {"id": 20, "owner_admin_id": 222}

    class Cursor:
        def execute(self, *_args, **_kwargs):
            pass

        def fetchone(self):
            return {"1": 1}

    class Connection:
        def cursor(self):
            return Cursor()

        def close(self):
            pass

    monkeypatch.setattr(api, "_is_general_admin_scope", lambda _admin_id: False)
    monkeypatch.setattr(api, "get_user_by_id", lambda _user_id: {"id": 700, "login_type": 2, "owner_admin_id": 111})
    monkeypatch.setattr(api, "get_user_groups", lambda _user_id: [])
    monkeypatch.setattr(api, "get_group", lambda _group_id: group)
    monkeypatch.setattr(api, "_can_manage_group", lambda admin_id, candidate: admin_id == 222 and candidate == group)
    monkeypatch.setattr(api, "get_conn", Connection)

    assert api._student_in_manageable_payment_group(222, 700, 20)


def test_limited_payment_overview_drops_other_groups_and_unscoped_bonuses() -> None:
    filtered = api._payment_filter_overview_by_group_scope(
        {
            "current_month": {"ym": "2026-10"},
            "months": [
                {
                    "ym": "2026-10",
                    "items": [
                        {"group_id": 20, "final_amount": 100, "paid_amount": 50, "debt_amount": 50},
                        {"group_id": 10, "final_amount": 900, "paid_amount": 0, "debt_amount": 900},
                    ],
                }
            ],
            "transactions": [{"group_id": 20}, {"group_id": 10}],
            "refunds": [{"group_id": 10}],
            "bonus_history": [{"group_id": None}, {"group_id": 20}, {"group_id": 10}],
            "referral_status": {"status": "private-user-wide-state"},
            "referral_as_source": [{"user_id": 999}],
        },
        {20},
    )

    assert [item["group_id"] for item in filtered["months"][0]["items"]] == [20]
    assert filtered["months"][0]["total_final_amount"] == 100
    assert filtered["transactions"] == [{"group_id": 20}]
    assert filtered["refunds"] == []
    assert filtered["bonus_history"] == [{"group_id": 20}]
    assert filtered["referral_status"] is None
    assert filtered["referral_as_source"] == []
