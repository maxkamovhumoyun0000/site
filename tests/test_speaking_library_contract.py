"""Guard Speaking Library and registration contracts."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")


class SpeakingLibraryContractTests(unittest.TestCase):
    def test_translation_route_uses_backend_path_after_proxy_strips_api(self) -> None:
        translation = (ROOT / "backend" / "speaking_translation.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('@router.post("/speaking/translate")', translation)
        self.assertNotIn('@router.post("/api/speaking/translate")', translation)

    def test_speaking_registration_requires_and_persists_age_and_gender(self) -> None:
        request = SOURCE.split("class SpeakingRegistrationRequest(", 1)[1].split(
            "class SpeakingRegistrationVerificationRequest(", 1
        )[0]
        self.assertIn('age: int = Field(ge=5, le=120)', request)
        self.assertIn('gender: Literal["male", "female", "prefer_not_to_say"]', request)
        endpoint = SOURCE.split("async def start_speaking_registration(", 1)[1].split(
            '@app.post("/auth/speaking-registration/verify"', 1
        )[0]
        self.assertIn('"age": payload.age', endpoint)
        self.assertIn('"gender": payload.gender', endpoint)

    def test_speaking_accounts_are_exempt_from_school_initial_password_binding(self) -> None:
        helper = SOURCE.split("def _bind_initial_student_password_device(", 1)[1].split(
            "def ", 1
        )[0]
        self.assertIn("is_speaking_app_account(user.get(\"speaking_app_account\"))", helper)

    def test_guest_library_does_not_claim_a_purchase_or_expose_pdf_url(self) -> None:
        endpoint = SOURCE.split("async def user_get_books(", 1)[1].split(
            '@app.get("/student/books/{book_id}")', 1
        )[0]
        self.assertIn("if user is None:", endpoint)
        self.assertIn('item["pdf_url"] = None', endpoint)
        self.assertIn("purchases = {}", endpoint)


if __name__ == "__main__":
    unittest.main()
