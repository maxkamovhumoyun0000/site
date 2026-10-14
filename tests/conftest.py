"""Process-wide pytest setup that must run before application imports."""

import asyncio


# Pyrogram's synchronous compatibility layer calls ``get_event_loop`` while
# modules are imported. Python 3.12 no longer creates one implicitly in this
# situation, so create a test-only loop before pytest imports the application.
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
