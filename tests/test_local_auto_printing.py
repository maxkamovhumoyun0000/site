from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "app" / "page.tsx").read_text(encoding="utf-8")
NAVIGATION = (ROOT / "app" / "ui" / "navigation-config.ts").read_text(encoding="utf-8")


class LocalAutomaticPrintingTests(unittest.TestCase):
    def test_confirmed_payment_and_refund_try_the_local_agent_before_browser_fallback(self) -> None:
        self.assertIn('import { printReceiptWithLocalAgent } from "./ui/local-print-agent"', PAGE)
        self.assertIn("const localPrint = await printReceiptWithLocalAgent(receipt);", PAGE)
        self.assertIn("if (localPrint.printed)", PAGE)
        self.assertIn("await printReceipt(receipt, autoPrintWindow);", PAGE)

    def test_developer_has_a_dedicated_downloads_page(self) -> None:
        self.assertIn('"local-print-agent"', NAVIGATION)
        self.assertIn('section === "local-print-agent"', PAGE)
        self.assertIn('/downloads/install-diamond-print-agent-windows.ps1', PAGE)
        self.assertIn('/downloads/LOCAL_PRINT_AGENT_README.md', PAGE)


if __name__ == "__main__":
    unittest.main()
