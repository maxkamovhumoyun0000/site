import asyncio
import os
import aiohttp

async def main():
    token = os.getenv("ADMIN_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": 12345,
        "text": "test",
        "reply_markup": {
            "inline_keyboard": [
                [{"text": "Call", "url": "invalidurl"}]
            ]
        }
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
            print(data)

asyncio.run(main())
