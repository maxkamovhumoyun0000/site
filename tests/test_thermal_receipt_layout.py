from pathlib import Path
import unittest


SOURCE = (Path(__file__).resolve().parents[1] / "app" / "page.tsx").read_text(encoding="utf-8")


class ThermalReceiptLayoutTests(unittest.TestCase):
    def test_xprinter_receipt_uses_the_full_48mm_printable_area_without_status_or_duplicate_id(self) -> None:
        """XP-58IIL accepts 58mm rolls but can print only a 48mm-wide area."""
        self.assertTrue("@page{size:48mm auto;margin:0}" in SOURCE)
        self.assertTrue("body{width:48mm" in SOURCE)
        self.assertTrue(".receipt{box-sizing:border-box;width:48mm" in SOURCE)
        self.assertFalse('["Payment ID", snapshot.payment_id]' in SOURCE)
        self.assertFalse('"TO\'LOV TASDIQLANDI"' in SOURCE)
        self.assertFalse('"QAYTARISH TASDIQLANDI"' in SOURCE)


if __name__ == "__main__":
    unittest.main()
