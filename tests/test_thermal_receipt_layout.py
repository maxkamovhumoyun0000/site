from pathlib import Path
import unittest


SOURCE = (Path(__file__).resolve().parents[1] / "app" / "page.tsx").read_text(encoding="utf-8")
BACKEND = (Path(__file__).resolve().parents[1] / "backend" / "main.py").read_text(encoding="utf-8")


class ThermalReceiptLayoutTests(unittest.TestCase):
    def test_xprinter_receipt_is_compact_uzbek_only_with_a_small_side_inset(self) -> None:
        """The 58mm roll has no application margin, only a compact content inset."""
        receipt_source = SOURCE.split("function receiptPrintHtml", 1)[1].split("type ApiUser", 1)[0]
        self.assertTrue("@page{size:48mm auto;margin:0}" in SOURCE)
        self.assertTrue("body{width:48mm" in SOURCE)
        self.assertTrue(".receipt{box-sizing:border-box;width:48mm" in SOURCE)
        self.assertIn("padding:0 1.5mm", receipt_source)
        self.assertIn("font:9.5px/1.16", receipt_source)
        self.assertNotIn("Ученик", receipt_source)
        self.assertNotIn("ТЕКУЩИЙ", receipt_source)
        self.assertFalse('["Payment ID", snapshot.payment_id]' in SOURCE)
        self.assertFalse('"TO\'LOV TASDIQLANDI"' in SOURCE)
        self.assertFalse('"QAYTARISH TASDIQLANDI"' in SOURCE)

    def test_every_receipt_output_is_uzbek_only(self) -> None:
        receipt_preview = SOURCE.split("receiptPreview", 1)[1].split("<section className=\"panel-card", 1)[0]
        pdf_receipt = BACKEND.split("def _receipt_pdf", 1)[1].split("@app", 1)[0]
        for forbidden in ("ЧЕК", "Ученик", "Группа", "Курс", "Преподаватель", "ТЕКУЩИЙ", "ВОЗВРАТ", "ОСТАТОК", "ID чека"):
            self.assertNotIn(forbidden, receipt_preview)
            self.assertNotIn(forbidden, pdf_receipt)


if __name__ == "__main__":
    unittest.main()
