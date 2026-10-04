from pathlib import Path
import unittest


SOURCE = (Path(__file__).resolve().parents[1] / "app" / "page.tsx").read_text(encoding="utf-8")


class ThermalReceiptLayoutTests(unittest.TestCase):
    def test_xprinter_receipt_uses_the_full_48mm_printable_area_without_status_or_duplicate_id(self) -> None:
        """XP-58IIL accepts 58mm rolls but can print only a 48mm-wide area."""
        self.assertIn("@page{size:48mm auto;margin:1.5mm 0}", SOURCE)
        self.assertIn("body{width:48mm", SOURCE)
        self.assertIn(".receipt{box-sizing:border-box;width:45mm", SOURCE)
        self.assertNotIn('["Payment ID", snapshot.payment_id]', SOURCE)
        self.assertNotIn('"TO\'LOV TASDIQLANDI"', SOURCE)
        self.assertNotIn('"QAYTARISH TASDIQLANDI"', SOURCE)


if __name__ == "__main__":
    unittest.main()
