from pathlib import Path
import importlib.util
import unittest


SOURCE = (Path(__file__).resolve().parents[1] / "app" / "page.tsx").read_text(encoding="utf-8")
BACKEND = (Path(__file__).resolve().parents[1] / "backend" / "main.py").read_text(encoding="utf-8")
DEVELOPER_WORKSPACE = (Path(__file__).resolve().parents[1] / "app" / "ui" / "developer-workspace.tsx").read_text(encoding="utf-8")


class ThermalReceiptLayoutTests(unittest.TestCase):
    def test_xprinter_receipt_is_server_generated_and_compact(self) -> None:
        """The 56mm printer gets a server-created raw document, not browser HTML."""
        self.assertIn("page = doc.new_page(width=158.74", BACKEND)
        self.assertIn("def _receipt_escpos_document", BACKEND)
        self.assertNotIn("function receiptPrintHtml", SOURCE)
        self.assertIn("printReceiptWithLocalAgent", SOURCE)
        self.assertNotIn('"TO\'LOV TASDIQLANDI"', BACKEND)
        self.assertNotIn('"QAYTARISH TASDIQLANDI"', BACKEND)

    def test_every_receipt_output_is_uzbek_only(self) -> None:
        receipt_preview = BACKEND.split("def _receipt_escpos_document", 1)[1].split("def _receipt_print_document_payload", 1)[0]
        pdf_receipt = BACKEND.split("def _receipt_pdf_bytes", 1)[1].split('@app.get("/admin/receipts/', 1)[0]
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

    def test_thermal_receipt_uses_compact_font_for_totals_note_and_receipt_id(self) -> None:
        """Long totals and refund notes must stay inside the 56mm print width."""
        receipt_source = BACKEND.split("def _receipt_escpos_document", 1)[1].split("def _receipt_print_document_payload", 1)[0]
        self.assertIn("_RECEIPT_ESC_FONT_COMPACT", BACKEND)
        self.assertIn("_RECEIPT_ESC_FONT_NORMAL", BACKEND)
        self.assertIn("compact_width", receipt_source)
        self.assertIn("details[4:]", receipt_source)
        self.assertIn("job.extend(_RECEIPT_ESC_CUT)", receipt_source)

    def test_receipt_header_and_every_separator_use_the_small_receipt_font(self) -> None:
        """Header and rules must not wrap or look larger than payment-method/date rows."""
        receipt_source = BACKEND.split("def _receipt_escpos_document", 1)[1].split("def _receipt_print_document_payload", 1)[0]
        self.assertIn("separator = b\"-\" * compact_width", receipt_source)
        self.assertIn("_RECEIPT_ESC_ALIGN_CENTER + _RECEIPT_ESC_FONT_COMPACT", receipt_source)
        self.assertNotIn("_RECEIPT_ESC_ALIGN_CENTER + _RECEIPT_ESC_BOLD_ON", receipt_source)
        self.assertNotIn("b\"-\" * width", receipt_source)

    def test_receipt_shows_applied_discount_amount_on_thermal_and_pdf_outputs(self) -> None:
        """A non-zero saved monthly discount must be visible on both printable formats."""
        receipt_source = BACKEND.split("def _receipt_escpos_document", 1)[1].split("def _receipt_print_document_payload", 1)[0]
        pdf_source = BACKEND.split("def _receipt_pdf_bytes", 1)[1].split('@app.get("/admin/receipts/', 1)[0]
        snapshot_source = BACKEND.split("def _receipt_snapshot_from_transaction", 1)[1].split("def _refund_receipt_snapshot_from_rows", 1)[0]
        self.assertIn('("Chegirma", f"{_receipt_money(snapshot.get(\'discount_amount\'))} SO\'M")', receipt_source)
        self.assertIn('f"CHEGIRMA: {float(snapshot.get(\'discount_amount\') or 0):,.2f} so\'m"', pdf_source)
        self.assertIn("o.discount_amount", snapshot_source)
        self.assertIn("_receipt_discount_snapshot(tx)", snapshot_source)

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

    def test_agent_reports_paper_out_to_the_web_application(self) -> None:
        """The browser must be able to stop a receipt and warn staff before an empty-roll print."""
        agent_path = Path(__file__).resolve().parents[1] / "public" / "downloads" / "diamond-print-agent.py"
        spec = importlib.util.spec_from_file_location("diamond_print_agent_paper", agent_path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)

        self.assertEqual(module.paper_status_from_text("media-empty-error"), "paper_out")
        self.assertEqual(module.paper_status_from_text("printer XP58 is idle"), "ready")
        self.assertEqual(module.paper_status_from_text("printer disabled"), "unavailable")

        client = (Path(__file__).resolve().parents[1] / "app" / "ui" / "local-print-agent.ts").read_text(encoding="utf-8")
        self.assertIn("paper_status", client)
        self.assertIn("alertLocalPrinterPaperOut", client)


if __name__ == "__main__":
    unittest.main()
