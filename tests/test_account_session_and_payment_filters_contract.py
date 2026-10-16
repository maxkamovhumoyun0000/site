from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
DB = (ROOT / "db.py").read_text(encoding="utf-8")
PAYMENTS_PAGE = (ROOT / "app" / "page.tsx").read_text(encoding="utf-8")


def _section(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


class AccountSessionAndPaymentFiltersContractTests(unittest.TestCase):
    def test_privileged_password_resets_keep_existing_sessions(self) -> None:
        admin_reset = _section(
            BACKEND,
            '@app.post("/admin/users/{user_id}/reset-password", response_model=AdminPasswordResetResponse)',
            '@app.post("/admin/users/{user_id}/access")',
        )
        teacher_reset = _section(
            BACKEND,
            '@app.post("/teacher/my-students/{student_id}/reset-password")',
            '# ============================================================\n# TEACHER NOTES ENDPOINTS',
        )
        speaking_reset = _section(
            BACKEND,
            '@app.post("/admin/speaking-users/{user_id}/reset-password")',
            'def _speaking_link_code()',
        )
        for handler in (admin_reset, teacher_reset, speaking_reset):
            self.assertNotIn("_revoke_web_sessions", handler)
            self.assertNotIn("session_version=COALESCE", handler)

    def test_screenshot_demo_student_and_teacher_cannot_be_hard_deleted(self) -> None:
        deletion = _section(DB, "def hard_delete_user_profile", "def soft_delete_user_profile")
        self.assertIn("COALESCE(screenshot_demo, 0) AS screenshot_demo", deletion)
        self.assertIn("hard_delete_user_profile refused screenshot demo", deletion)
        inactive = _section(BACKEND, "def _find_inactive_students", '@app.get("/admin/students/inactive-preview")')
        self.assertIn("COALESCE(u.screenshot_demo, 0)=0", inactive)

    def test_unpaid_and_partial_filters_are_debt_based_after_due_date(self) -> None:
        dashboard = _section(BACKEND, '@app.get("/admin/payments/dashboard")', '@app.get("/admin/payments/students")')
        self.assertIn('is_unpaid = paid_amount <= 1e-9 and debt_amount > 1e-9', dashboard)
        self.assertIn('"status_lists"', dashboard)
        students = _section(BACKEND, '@app.get("/admin/payments/students")', '@app.get("/admin/payments/groups/{group_id}/students")')
        self.assertIn('COALESCE(sa.paid_amount, 0) <= 0.000000001', students)
        self.assertIn('COALESCE(sa.paid_amount, 0) > 0.000000001', students)
        self.assertIn('COALESCE(sa.debt_amount, 0) > 0.000000001', students)
        self.assertIn("status_lists: (dashboard.status_lists || {})", PAYMENTS_PAGE)


if __name__ == "__main__":
    unittest.main()
