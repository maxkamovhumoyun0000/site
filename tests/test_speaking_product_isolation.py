"""Product isolation is enforced even for a modified client."""
import asyncio
import pytest
from fastapi import HTTPException

from backend import speaking_subscriptions as subscriptions


@pytest.mark.parametrize("product,other", [("english", "russian"), ("russian", "english")])
def test_standalone_account_cannot_use_other_products_subject(product, other):
    token = subscriptions.set_product_code(product)
    try:
        user = {"id": 1, "speaking_app_account": True}
        subscriptions.require_product_subject(user, product)
        with pytest.raises(HTTPException) as exc:
            subscriptions.require_product_subject(user, other)
        assert exc.value.status_code == 404
    finally:
        subscriptions.reset_product_code(token)


@pytest.mark.parametrize("account", [False, None])
def test_linked_student_and_staff_remain_cross_subject(account):
    token = subscriptions.set_product_code("english")
    try:
        subscriptions.require_product_subject({"speaking_app_account": account}, "russian")
    finally:
        subscriptions.reset_product_code(token)


def test_signed_product_wins_and_legacy_speaking_token_cannot_select_header():
    token = subscriptions.set_product_code("russian")
    try:
        subscriptions.bind_authenticated_product(None, True)
        assert subscriptions.current_product_code() == "english"
        subscriptions.bind_authenticated_product("russian", True)
        assert subscriptions.current_product_code() == "russian"
        subscriptions.bind_authenticated_product("english", True)
        assert subscriptions.current_product_code() == "english"
    finally:
        subscriptions.reset_product_code(token)


def test_legacy_student_product_cannot_be_switched_by_header():
    token = subscriptions.set_product_code("russian")
    try:
        subscriptions.bind_authenticated_product(None, False)
        assert subscriptions.current_product_code() == "english"
        subscriptions.require_product_subject({"speaking_app_account": False}, "russian")
    finally:
        subscriptions.reset_product_code(token)


@pytest.mark.parametrize("product,other", [("english", "russian"), ("russian", "english")])
def test_linked_student_paid_features_bind_subject_but_shared_features_do_not(monkeypatch, product, other):
    monkeypatch.setattr(subscriptions, "_student_linked", lambda user: True)
    token = subscriptions.set_product_code(product)
    try:
        user = {"id": 2, "speaking_app_account": False}
        subscriptions.require_product_subject(user, other)  # Student-included feature
        subscriptions.require_product_subject(user, product, paid_feature=True)
        with pytest.raises(HTTPException):
            subscriptions.require_product_subject(user, other, paid_feature=True)
    finally:
        subscriptions.reset_product_code(token)


@pytest.mark.parametrize("product,other", [("english", "russian"), ("russian", "english")])
def test_paid_plan_and_mock_exam_endpoints_reject_other_product(monkeypatch, product, other):
    from backend import speaking_exams, speaking_plans

    student = {"id": 2, "speaking_app_account": False}
    monkeypatch.setattr(subscriptions, "_student_linked", lambda user: True)
    monkeypatch.setattr(subscriptions, "require_feature", lambda *args: {"allowed": True})
    monkeypatch.setattr(speaking_plans, "_auth", lambda *args: (student, "student"))
    monkeypatch.setattr(speaking_plans, "ensure_tables", lambda: None)
    monkeypatch.setattr(speaking_exams, "_user", lambda *args: student)
    monkeypatch.setattr(speaking_exams, "ensure_tables", lambda: None)
    token = subscriptions.set_product_code(product)
    try:
        with pytest.raises(HTTPException) as plan_error:
            asyncio.run(speaking_plans.current_speaking_plan(subject=other, authorization="test"))
        assert plan_error.value.status_code == 404
        with pytest.raises(HTTPException) as exam_error:
            asyncio.run(speaking_exams.start_speaking_exam(
                speaking_exams.ExamStartRequest(subject=other, kind="mock"), authorization="test"
            ))
        assert exam_error.value.status_code == 404
    finally:
        subscriptions.reset_product_code(token)


def test_student_shared_learning_track_keeps_cross_subject_access():
    from backend import speaking_learning

    class Cursor:
        def execute(self, *_args):
            pass

        def fetchone(self):
            return {"subject": "russian"}

    token = subscriptions.set_product_code("english")
    try:
        speaking_learning._require_track_subject(
            Cursor(), 1, {"id": 2, "speaking_app_account": False}
        )
    finally:
        subscriptions.reset_product_code(token)


def test_active_plan_uses_separate_product_key(monkeypatch):
    class Cursor:
        def execute(self, sql, params):
            self.params = params

        def fetchone(self):
            return {"plan_code": "pro"} if self.params[1] == "english" else None

        def close(self):
            pass

    class Connection:
        def cursor(self):
            return Cursor()

        def close(self):
            pass

    monkeypatch.setattr(subscriptions, "ensure_tables", lambda: None)
    monkeypatch.setattr(subscriptions, "get_conn", Connection)
    assert subscriptions.active_plan(1, "english")["plan_code"] == "pro"
    assert subscriptions.active_plan(1, "russian") is None
