import asyncio
import sys
import os

sys.path.append(os.path.abspath("."))
import main

async def test():
    try:
        main._user_row_from_bearer = lambda auth: {"id": 1, "login_type": 1, "login_id": "test", "role": "student"}
        res = await main.user_get_video_detail(video_id=1, authorization="Bearer dummy")
        print("Success:", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test())
