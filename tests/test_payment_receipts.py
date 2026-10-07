from __future__ import annotations

import backend.main as api
import pytest


def test_receipt_branch_snapshot_uses_existing_group_owner_relation(monkeypatch) -> None:
    monkeypatch.setattr(api, "LIMITED_ADMIN_CHAT_IDS", [901, 902])

    assert api._receipt_branch_snapshot({"owner_admin_id": 901}) == (901, "1-filial")
    assert api._receipt_branch_snapshot({"owner_admin_id": 902}) == (902, "2-filial")
    assert api._receipt_branch_snapshot({"owner_admin_id": 0}) == (None, "Diamond Education")


def test_receipt_public_payload_only_returns_immutable_snapshot() -> None:
    receipt = {
        "receipt_id": "PAY-42-01",
        "payment_transaction_id": 42,
        "status": "confirmed",
        "created_at": "2026-10-01T12:00:00+00:00",
        "snapshot_json": '{"student_name":"Ali","amount":500000}',
        # This private storage field must never become a public API field.
        "confirmed_by_admin_id": 999,
    }

    payload = api._receipt_public_payload(receipt)

    assert payload == {
        "receipt_id": "PAY-42-01",
        "payment_transaction_id": 42,
        "status": "confirmed",
        "created_at": "2026-10-01T12:00:00+00:00",
        "snapshot": {"student_name": "Ali", "amount": 500000},
    }


def test_receipt_financial_snapshot_preserves_partial_payment_and_remaining_balance() -> None:
    snapshot = api._receipt_financial_snapshot(
        {
            "amount": 100_000,
            "remaining_after": 400_000,
            "overpayment_after": 0,
            "status_after": api.PAYMENT_STATUS_PARTIAL,
        }
    )

    assert snapshot == {
        "amount": 100_000.0,
        "total_paid_amount": 100_000.0,
        "remaining_amount": 400_000.0,
        "overpayment_amount": 0.0,
        "payment_status": api.PAYMENT_STATUS_PARTIAL,
    }


def test_receipt_financial_snapshot_preserves_current_and_total_paid_amounts() -> None:
    snapshot = api._receipt_financial_snapshot(
        {
            "amount": 100_000,
            "paid_total_after": 300_000,
            "remaining_after": 200_000,
            "overpayment_after": 0,
            "status_after": api.PAYMENT_STATUS_PARTIAL,
        }
    )

    assert snapshot["amount"] == 100_000.0
    assert snapshot["total_paid_amount"] == 300_000.0
    assert snapshot["remaining_amount"] == 200_000.0


def test_refund_receipt_financial_snapshot_keeps_zero_total_paid() -> None:
    snapshot = api._receipt_financial_snapshot(
        {
            "amount": 100_000,
            "paid_total_after": 0,
            "remaining_after": 100_000,
            "overpayment_after": 0,
            "status_after": api.PAYMENT_STATUS_UNPAID,
        }
    )

    assert snapshot["total_paid_amount"] == 0.0


def test_payment_amount_cannot_exceed_the_outstanding_or_refundable_limit() -> None:
    assert api._payment_require_amount_within_limit(100_000, 100_000, field_name="Payment") == 100_000.0

    with pytest.raises(api.HTTPException, match="cannot exceed"):
        api._payment_require_amount_within_limit(100_000.01, 100_000, field_name="Payment")


def test_attendance_credit_is_not_carried_into_a_future_month_early(monkeypatch) -> None:
    monkeypatch.setattr(api, "_payment_ym_now", lambda: "2026-10")

    assert api._payment_carry_forward_is_due("2026-10") is True
    assert api._payment_carry_forward_is_due("2026-11") is False


def test_refund_receipt_snapshot_is_derived_from_the_persisted_refund_and_source_payment() -> None:
    snapshot = api._refund_receipt_snapshot_from_rows(
        {
            "id": 17,
            "transaction_id": 42,
            "user_id": 5,
            "group_id": 8,
            "amount": 100_000,
            "paid_total_after": 300_000,
            "debt_after": 400_000,
            "overpayment_after": 0,
            "status_after": api.PAYMENT_STATUS_PARTIAL,
            "refund_type": "partial",
            "note": "Dars bekor qilindi",
            "refunded_by_admin_name": "Main Admin",
            "created_at": "2026-10-02T12:44:46+05:00",
        },
        {
            "payment_method": "cash",
            "is_advance": 0,
            "student_name": "Ali Valiyev",
            "group_name": "IELTS-901",
            "subject_name": "IELTS",
            "course_title": "IELTS",
            "teacher_name": "Azizbek Karimov",
            "owner_admin_id": 901,
        },
    )

    assert snapshot["receipt_kind"] == "refund"
    assert snapshot["amount"] == 100_000.0
    assert snapshot["total_paid_amount"] == 300_000.0
    assert snapshot["remaining_amount"] == 400_000.0
    assert snapshot["payment_type"] == "refund_partial"
    assert snapshot["refund_note"] == "Dars bekor qilindi"
    assert snapshot["payment_id"] == "REF-17"
    assert snapshot["confirmed_by_name"] == "Main Admin"


def test_web_sessions_default_to_thirty_days_to_prevent_daily_logout() -> None:
    assert api.WEB_SESSION_TOKEN_TTL_HOURS == 720
    assert api.WEB_SESSION_TOKEN_TTL_HOURS == api.MOBILE_SESSION_TOKEN_TTL_HOURS


def test_group_specific_pricing_override_replaces_only_that_students_group_price(monkeypatch) -> None:
    """A student's negotiated group fee must not become a global group fee."""
    monkeypatch.setattr(
        api,
        "_get_student_group_pricing_override",
        lambda _user_id, _group_id: {"mode": "fixed_price", "price_amount": 450_000},
        raising=False,
    )
    monkeypatch.setattr(api, "_payment_lesson_dates_for_group_month", lambda _group, _ym: [object()] * 12)
    monkeypatch.setattr(api, "_payment_active_lesson_dates", lambda *_args: [object()] * 12)
    monkeypatch.setattr(api, "_attendance_excused_lesson_dates", lambda *_args: set())

    result = api._calculate_monthly_payment_for_student_group(
        17,
        23,
        "2026-10",
        student_row={"id": 17, "free_access": 0},
        group_row={"id": 23, "name": "IELTS", "monthly_fee_text": "600000"},
        discount_info={"discount_type": "none", "discount_percent": 0},
    )

    assert result["original_price"] == 450_000
    assert result["final_payable_amount"] == 450_000
    assert result["pricing_override_mode"] == "fixed_price"


def test_group_specific_percent_discount_is_applied_to_one_students_group(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "_get_student_group_pricing_override",
        lambda _user_id, _group_id: {"mode": "discount_percent", "discount_percent": 100},
        raising=False,
    )
    monkeypatch.setattr(api, "_payment_lesson_dates_for_group_month", lambda _group, _ym: [object()] * 12)
    monkeypatch.setattr(api, "_payment_active_lesson_dates", lambda *_args: [object()] * 12)
    monkeypatch.setattr(api, "_attendance_excused_lesson_dates", lambda *_args: set())

    result = api._calculate_monthly_payment_for_student_group(
        17,
        23,
        "2026-10",
        student_row={"id": 17, "free_access": 0},
        group_row={"id": 23, "name": "IELTS", "monthly_fee_text": "600000"},
        discount_info={"discount_type": "none", "discount_percent": 0},
    )

    assert result["discount_type"] == "student_group_override"
    assert result["discount_percent"] == 100
    assert result["final_payable_amount"] == 0


def test_mini_group_freezes_payment_when_only_one_student_remains(monkeypatch) -> None:
    """A one-student mini group must never fall back to the 2-person price."""
    monkeypatch.setattr(
        api,
        "_get_course_by_id",
        lambda _course_id: {
            "id": 71,
            "price_text": "1000000",
            "mini_group_2_price_text": "700000",
            "mini_group_3_price_text": "600000",
            "mini_group_4_price_text": "500000",
        },
    )
    monkeypatch.setattr(api, "get_group_users", lambda _group_id: [{"id": 17, "login_type": 2}])
    monkeypatch.setattr(api, "_get_student_group_pricing_override", lambda *_args: None)
    monkeypatch.setattr(api, "_payment_lesson_dates_for_group_month", lambda _group, _ym: [object()] * 12)
    monkeypatch.setattr(api, "_payment_active_lesson_dates", lambda *_args: [object()] * 12)
    monkeypatch.setattr(api, "_attendance_excused_lesson_dates", lambda *_args: set())

    result = api._calculate_monthly_payment_for_student_group(
        17,
        23,
        "2026-10",
        student_row={"id": 17, "free_access": 0},
        group_row={"id": 23, "course_id": 71, "pricing_type": "mini_group", "mini_group_action_required": 1},
        discount_info={"discount_type": "none", "discount_percent": 0},
    )

    assert result["course_price"] == 0
    assert result["course_price_source"] == "mini_group_frozen"


def test_frozen_mini_group_ignores_student_specific_price_override(monkeypatch) -> None:
    """A negotiated price must not bypass the mandatory mini-group freeze."""
    monkeypatch.setattr(api, "_get_course_by_id", lambda _course_id: {"id": 71, "mini_group_2_price_text": "700000"})
    monkeypatch.setattr(api, "get_group_users", lambda _group_id: [{"id": 17, "login_type": 2}])
    monkeypatch.setattr(api, "_get_student_group_pricing_override", lambda *_args: {"mode": "fixed_price", "price_amount": 900_000})
    monkeypatch.setattr(api, "_payment_lesson_dates_for_group_month", lambda _group, _ym: [object()] * 12)
    monkeypatch.setattr(api, "_payment_active_lesson_dates", lambda *_args: [object()] * 12)
    monkeypatch.setattr(api, "_attendance_excused_lesson_dates", lambda *_args: set())

    result = api._calculate_monthly_payment_for_student_group(
        17, 23, "2026-10",
        student_row={"id": 17, "free_access": 0},
        group_row={"id": 23, "course_id": 71, "pricing_type": "mini_group", "mini_group_action_required": 1},
        discount_info={"discount_type": "none", "discount_percent": 0},
    )

    assert result["course_price"] == 0
    assert result["final_payable_amount"] == 0
    assert result["pricing_override_mode"] is None


def test_mini_group_uses_current_three_student_price(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "_get_course_by_id",
        lambda _course_id: {
            "id": 71,
            "price_text": "1000000",
            "mini_group_2_price_text": "700000",
            "mini_group_3_price_text": "600000",
            "mini_group_4_price_text": "500000",
        },
    )
    monkeypatch.setattr(
        api,
        "get_group_users",
        lambda _group_id: [
            {"id": 17, "login_type": 2},
            {"id": 18, "login_type": 2},
            {"id": 19, "login_type": 2},
        ],
    )
    monkeypatch.setattr(api, "_get_student_group_pricing_override", lambda *_args: None)
    monkeypatch.setattr(api, "_payment_lesson_dates_for_group_month", lambda _group, _ym: [object()] * 12)
    monkeypatch.setattr(api, "_payment_active_lesson_dates", lambda *_args: [object()] * 12)
    monkeypatch.setattr(api, "_attendance_excused_lesson_dates", lambda *_args: set())

    result = api._calculate_monthly_payment_for_student_group(
        17,
        23,
        "2026-10",
        student_row={"id": 17, "free_access": 0},
        group_row={"id": 23, "course_id": 71, "pricing_type": "mini_group"},
        discount_info={"discount_type": "none", "discount_percent": 0},
    )

    assert result["course_price"] == 600_000
    assert result["course_price_source"] == "mini_group_3"


def test_receipt_pdf_is_rendered_from_server_snapshot() -> None:
    pdf = api._receipt_pdf_bytes(
        {
            "receipt_id": "PAY-42-01",
            "snapshot": {
                "brand": "DIAMOND EDUCATION",
                "branch_name": "1-filial",
                "student_name": "Ali Valiyev",
                "group_name": "IELTS-901",
                "subject_name": "IELTS",
                "teachers": ["Azizbek Karimov"],
                "amount": 500000,
                "payment_method": "cash",
                "payment_type": "monthly",
                "confirmed_by_name": "Admin",
                "confirmed_at": "2026-10-01T18:35:00+05:00",
                "payment_id": "PAY-42",
            },
        }
    )

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 500

    import fitz

    document = fitz.open(stream=pdf, filetype="pdf")
    pdf_text = "\n".join(page.get_text() for page in document)
    document.close()
    assert "JAMI TO'LANGAN" in pdf_text
    assert "Receipt ID" in pdf_text
    assert "Payment ID" not in pdf_text
    assert "TO'LOV TASDIQLANDI" not in pdf_text
