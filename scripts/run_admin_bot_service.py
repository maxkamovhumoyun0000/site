import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admin_bot import run_admin_bot

if __name__ == "__main__":
    asyncio.run(run_admin_bot())
