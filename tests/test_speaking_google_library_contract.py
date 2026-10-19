"""Guard the Speaking Google sign-in and authenticated Library contract."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")


class SpeakingGoogleLibraryContractTests(unittest.TestCase):
    def test_translation_route_uses_backend_path_after_proxy_strips_api(self) -> None:
        translation = (ROOT / "backend" / "speaking_translation.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('@router.post("/speaking/translate")', translation)
        self.assertNotIn('@router.post("/api/speaking/translate")', translation)

    def test_google_sign_in_verifies_id_token_and_uses_normal_session_limit(self) -> None:
        endpoint = SOURCE.split('async def speaking_google_login(', 1)[1].split(
            '@app.post("/auth/speaking-registration/start")', 1
        )[0]
        self.assertIn("google_id_token.verify_oauth2_token", endpoint)
        self.assertIn('claims.get("email_verified")', endpoint)
        self.assertIn('claims.get("sub")', endpoint)
        self.assertIn("speaking_google_identities", endpoint)
        self.assertIn("is_speaking_app_account", endpoint)
        self.assertIn("payload.first_name", endpoint)
        self.assertIn("payload.last_name", endpoint)
        self.assertIn("payload.phone", endpoint)
        self.assertIn('phone or None', endpoint)
        user_payload = SOURCE.split("def _build_user_payload(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('phone=u.get("phone")', user_payload)
        self.assertIn("_reserve_web_session_slot", endpoint)
        self.assertIn("_issue_web_session", endpoint)

    def test_unknown_google_user_gets_profile_prompt_then_speaking_account(self) -> None:
        endpoint = SOURCE.split("async def speaking_google_login(", 1)[1].split(
            '@app.post("/auth/speaking-registration/start")', 1
        )[0]
        self.assertIn('if (', endpoint)
        self.assertNotIn('payload.collect_profile and (', endpoint)
        self.assertIn('not str(payload.first_name or "").strip()', endpoint)
        self.assertIn('not str(payload.last_name or "").strip()', endpoint)
        self.assertIn('not str(payload.phone or "").strip()', endpoint)
        self.assertIn('or payload.age is None', endpoint)
        self.assertIn('or payload.gender is None', endpoint)
        self.assertIn('"code": "profile_required"', endpoint)
        self.assertIn('INSERT INTO users(login_id,password,first_name,last_name,phone,subject,login_type,blocked,access_enabled,pending_approval,public_signup,speaking_app_account,language,face_enrollment_required,proctoring_required)', endpoint)
        self.assertIn('speaking_account_contacts(user_id,email,age,gender,updated_at)', endpoint)

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
