from pathlib import Path
import importlib.util
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

    def test_payment_confirmation_retries_use_an_idempotency_key(self) -> None:
        """A retry must replay one payment, while a later equal payment remains valid."""
        self.assertIn("idempotency_key: str | None", BACKEND)
        self.assertIn("ux_payment_tx_idempotency_key", BACKEND)
        self.assertIn("if not idempotency_key:", BACKEND)
        self.assertIn("paymentConfirmRequestRef", SOURCE)
        self.assertIn("idempotency_key: requestKey", SOURCE)

    def test_developer_printer_guide_has_copy_paste_commands_for_the_new_agent(self) -> None:
        self.assertIn("Windows buyrug‘ini nusxalash", DEVELOPER_WORKSPACE)
        self.assertIn("Linux buyrug‘ini nusxalash", DEVELOPER_WORKSPACE)
        self.assertIn("Driver buyrug‘ini nusxalash", DEVELOPER_WORKSPACE)
        self.assertIn("Server chekni yaratadi", DEVELOPER_WORKSPACE)

    def test_linux_agent_selects_thermal_printer_without_a_default_queue(self) -> None:
        agent_path = Path(__file__).resolve().parents[1] / "public" / "downloads" / "diamond-print-agent.py"
        spec = importlib.util.spec_from_file_location("diamond_print_agent", agent_path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)

        self.assertEqual(module.choose_linux_printer(["Office_A4", "XP-58IIL"], "Office_A4"), "XP-58IIL")
        self.assertEqual(module.choose_linux_printer(["Receipt_USB"], ""), "Receipt_USB")
        with self.assertRaisesRegex(RuntimeError, "DIAMOND_PRINTER"):
            module.choose_linux_printer(["Office_A4", "Warehouse_A4"], "")

        installer = (agent_path.parent / "install-diamond-print-agent-linux.sh").read_text(encoding="utf-8")
        self.assertIn("systemctl --user enable --now diamond-print-agent.service", installer)
        self.assertIn("diamond-print-agent.py", installer)


if __name__ == "__main__":
    unittest.main()
