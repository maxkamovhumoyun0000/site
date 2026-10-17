"""Guard the Speaking Google sign-in and authenticated Library contract."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")


class SpeakingGoogleLibraryContractTests(unittest.TestCase):
    def test_google_sign_in_verifies_id_token_and_uses_normal_session_limit(self) -> None:
        endpoint = SOURCE.split('async def speaking_google_login(', 1)[1].split(
            '@app.post("/auth/speaking-registration/start")', 1
        )[0]
        self.assertIn("google_id_token.verify_oauth2_token", endpoint)
        self.assertIn('claims.get("email_verified")', endpoint)
        self.assertIn('claims.get("sub")', endpoint)
        self.assertIn("speaking_google_identities", endpoint)
        self.assertIn("is_speaking_app_account", endpoint)
        self.assertIn("_reserve_web_session_slot", endpoint)
        self.assertIn("_issue_web_session", endpoint)

    def test_guest_library_does_not_claim_a_purchase_or_expose_pdf_url(self) -> None:
        endpoint = SOURCE.split("async def user_get_books(", 1)[1].split(
            '@app.get("/student/books/{book_id}")', 1
        )[0]
        self.assertIn("if user is None:", endpoint)
        self.assertIn('item["pdf_url"] = None', endpoint)
        self.assertIn("purchases = {}", endpoint)


if __name__ == "__main__":
    unittest.main()
