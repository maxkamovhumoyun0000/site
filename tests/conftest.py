"""Process-wide pytest setup that must run before application imports."""

import asyncio


# Pyrogram's synchronous compatibility layer calls ``get_event_loop`` while
# test modules import the application. Python 3.12's loop policy may not
# create one implicitly, and pytest-asyncio can replace the policy during
# collection. Ensure a loop both at startup and immediately before every test
# module import.
def _ensure_import_loop() -> None:
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


_ensure_import_loop()


def pytest_pycollect_makemodule(module_path, parent):
    _ensure_import_loop()
    return None
