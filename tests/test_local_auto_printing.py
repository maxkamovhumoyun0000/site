from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "app" / "page.tsx").read_text(encoding="utf-8")
NAVIGATION = (ROOT / "app" / "ui" / "navigation-config.ts").read_text(encoding="utf-8")
NEXT_CONFIG = (ROOT / "next.config.ts").read_text(encoding="utf-8")


class LocalAutomaticPrintingTests(unittest.TestCase):
    def test_confirmed_payment_and_refund_try_the_local_agent_before_browser_fallback(self) -> None:
        self.assertIn('from "./ui/local-print-agent"', PAGE)
        self.assertIn("printReceiptWithLocalAgent", PAGE)
        self.assertIn("const localPrint = await printReceiptWithLocalAgent(receipt);", PAGE)
        self.assertIn("if (localPrint.printed)", PAGE)
        self.assertIn("await printReceipt(receipt, autoPrintWindow);", PAGE)

    def test_developer_has_a_dedicated_downloads_page(self) -> None:
        self.assertIn('"local-print-agent"', NAVIGATION)
        self.assertIn('section === "local-print-agent"', PAGE)
        self.assertIn('/downloads/install-diamond-print-agent-windows.ps1', PAGE)
        self.assertIn('/downloads/LOCAL_PRINT_AGENT_README.md', PAGE)

    def test_developer_can_test_print_and_save_local_paper_settings(self) -> None:
        self.assertIn("printLocalAgentTestReceipt", PAGE)
        self.assertIn("saveLocalPrintAgentSettings", PAGE)
        self.assertIn("paper_width_mm", PAGE)

    def test_csp_allows_only_the_loopback_print_agent_connection(self) -> None:
        self.assertIn("http://127.0.0.1:18765", NEXT_CONFIG)


if __name__ == "__main__":
    unittest.main()
