import importlib.util
import unittest
from pathlib import Path


AGENT_PATH = Path(__file__).resolve().parents[1] / "public" / "downloads" / "diamond-print-agent.py"


def load_agent():
    spec = importlib.util.spec_from_file_location("diamond_print_agent", AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("print agent module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LocalPrintAgentTests(unittest.TestCase):
    def test_receipt_is_rendered_as_a_bounded_58mm_escpos_job(self):
        agent = load_agent()
        payload = {
            "receipt_id": "PAY-12-01",
            "title": "TO'LOV CHEKI / ЧЕК ОПЛАТЫ",
            "brand": "DIAMOND EDUCATION",
            "lines": [{"label": "O'quvchi / Ученик", "value": "Rushana Xayitboyevna"}],
            "totals": [{"label": "JORIY TO'LOV / ТЕКУЩИЙ ПЛАТЁЖ", "value": "100 000 SO'M"}],
        }

        document = agent.build_escpos_document(payload)

        self.assertTrue(document.startswith(agent.ESC_INIT))
        self.assertIn(b"DIAMOND EDUCATION", document)
        self.assertIn(b"PAY-12-01", document)
        self.assertTrue(document.endswith(agent.ESC_CUT))
        self.assertLessEqual(max(agent.printable_line_lengths(payload)), agent.LINE_WIDTH)

    def test_rejects_unknown_fields_and_oversized_receipts(self):
        agent = load_agent()

        with self.assertRaises(ValueError):
            agent.validate_payload({"receipt_id": "PAY-1", "unexpected": "field"})
        with self.assertRaises(ValueError):
            agent.validate_payload({"receipt_id": "PAY-1", "brand": "x" * 401})


if __name__ == "__main__":
    unittest.main()
