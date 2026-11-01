"""Regression contracts for Speaking Writing admin tasks and feedback."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class SpeakingWritingAdminContractTests(unittest.TestCase):
  def test_speaking_admin_can_attach_images_to_english_task_one_variants(self):
    admin_ui = _read("app/ui/admin-speaking-writing.tsx")
    self.assertIn('form.subject === "english" && form.task_type.startsWith("task1")', admin_ui)
    self.assertIn('image_url: form.image_url', admin_ui)


  def test_admin_can_create_both_english_task_one_and_task_two_questions(self):
    admin_ui = _read("app/ui/admin-speaking-writing.tsx")
    backend = _read("backend/speaking_writing.py")
    self.assertIn('english: ["task1_academic", "task1_general", "task2"]', admin_ui)
    self.assertIn('"english": ("task1_academic", "task1_general", "task2")', backend)
    self.assertIn('@router.post("/staff/speaking/writing/tasks")', backend)


  def test_improved_version_is_not_generated_or_returned_for_writing_feedback(self):
    backend = _read("backend/speaking_writing.py")
    flutter_result = _read(
        "/home/xumoyun-maxkamov/Desktop/Diamond Speaking Questions/lib/features/writing/writing_result_page.dart"
    )
    flutter_api = _read(
        "/home/xumoyun-maxkamov/Desktop/Diamond Speaking Questions/lib/features/writing/writing_api.dart"
    )
    self.assertNotIn('"improved_version":', backend)
    self.assertIn('result.pop("improved_version", None)', backend)
    self.assertNotIn("improved_version", flutter_result)
    self.assertNotIn("improvedVersion", flutter_api)


if __name__ == "__main__":
    unittest.main()

