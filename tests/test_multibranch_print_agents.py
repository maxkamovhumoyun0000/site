from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
AGENT = (ROOT / "public" / "downloads" / "diamond-print-agent.py").read_text(encoding="utf-8")
WORKSPACE = (ROOT / "app" / "ui" / "developer-workspace.tsx").read_text(encoding="utf-8")


class MultiBranchPrintAgentTests(unittest.TestCase):
    def test_each_branch_station_can_enroll_and_report_without_a_developer_browser_token(self) -> None:
        self.assertIn("CREATE TABLE IF NOT EXISTS developer_print_agents", BACKEND)
        self.assertIn('@app.post("/developer/print-agents/enroll")', BACKEND)
        self.assertIn('@app.post("/developer/print-agents/heartbeat")', BACKEND)
        self.assertIn("_verify_print_agent_token", BACKEND)
        self.assertIn("hashlib.sha256", BACKEND)
        self.assertIn("last_seen_at", BACKEND)

    def test_local_agent_keeps_station_credentials_private_and_sends_a_heartbeat(self) -> None:
        self.assertIn("agent_id", AGENT)
        self.assertIn("agent_token", AGENT)
        self.assertIn("def sanitized_settings", AGENT)
        self.assertIn("def report_agent_heartbeat", AGENT)
        self.assertIn("agent heartbeat", AGENT)
        health_block = AGENT.split("def do_GET", 1)[1].split("def do_POST", 1)[0]
        self.assertNotIn('"agent_token"', health_block)

    def test_developer_can_enroll_this_computer_and_monitor_all_branch_agents(self) -> None:
        self.assertIn("Filial printerlari", WORKSPACE)
        self.assertIn("Ushbu kompyuterni ulash", WORKSPACE)
        self.assertIn("/developer/print-agents", WORKSPACE)
        self.assertIn("branch_name", WORKSPACE)
        self.assertIn("station_name", WORKSPACE)


if __name__ == "__main__":
    unittest.main()
