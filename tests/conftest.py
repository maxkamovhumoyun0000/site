"""Process-wide pytest setup that must run before application imports."""

import asyncio


# Pyrogram installs uvloop when it is available, then calls ``get_event_loop``
# while modules are imported. Python 3.12's uvloop policy does not implicitly
# create a loop, so configure that same policy and install a test-only loop
# before pytest imports the application.
try:
    import uvloop
except ImportError:
    uvloop = None

if uvloop is not None:
    uvloop.install()

asyncio.set_event_loop(asyncio.new_event_loop())
