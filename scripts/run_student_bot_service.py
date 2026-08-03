import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from student_bot import run_student_bot

if __name__ == "__main__":
    asyncio.run(run_student_bot())
