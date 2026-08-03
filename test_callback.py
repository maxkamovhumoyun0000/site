import asyncio
from backend.main import _send_telegram_text
import os
from dotenv import load_dotenv

load_dotenv()
admin_token = os.getenv("ADMIN_BOT_TOKEN")
chat_id = "5130327830"
message = "Test message"
button_url = "https://example.com"

async def test():
    print(f"Token: {admin_token}")
    res = await _send_telegram_text(
        admin_token, chat_id, message,
        button_text="Qo'ng'iroq qilish",
        button_url=button_url,
        parse_mode="HTML"
    )
    print(f"Result: {res}")

asyncio.run(test())
