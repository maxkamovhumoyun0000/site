"""Small offline checks for the reversible student subscription switch."""
import ast
import asyncio
import logging
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_function(path, name, namespace):
    tree = ast.parse((ROOT / path).read_text())
    node = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    node.decorator_list = []
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, node], type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)
    return namespace[name]


class StudentBotSwitchTest(unittest.TestCase):
    def test_backend_flag_can_disable_and_reenable(self):
        for enabled in (False, True):
            fake = types.ModuleType("config")
            fake.FORCE_SUBSCRIBE = enabled
            fake.FORCE_SUBSCRIBE_CHANNEL_ID = -123
            fake.FORCE_SUBSCRIBE_CHANNEL_URL = "https://t.me/example"
            fake.STUDENT_BOT_TOKEN = "not-a-real-token"
            with patch.dict(sys.modules, {"config": fake}):
                fn = load_function("backend/main.py", "_student_channel_membership_config", {})
                self.assertEqual(fn()[0], enabled)

    def test_disabled_bot_never_calls_telegram(self):
        class Bot:
            async def get_chat_member(self, *_args):
                raise AssertionError("Telegram must not be called when disabled")
        fn = load_function("force_subscribe.py", "is_user_subscribed", {
            "FORCE_SUBSCRIBE": False,
            "FORCE_SUBSCRIBE_CHANNEL_ID": -123,
            "logger": logging.getLogger("test"),
        })
        self.assertIs(asyncio.run(fn(Bot(), 42)), True)

    def test_release_does_not_restart_disabled_bots(self):
        script = (ROOT / "scripts/activate_production_release.sh").read_text()
        services = script.split("BACKEND_SERVICES=(", 1)[1].split(")", 1)[0]
        for bot in ("student", "teacher", "support"):
            self.assertNotIn(f"diamond-site-{bot}-bot", services)


if __name__ == "__main__":
    unittest.main()
