import asyncio
import logging
import random
import os
import requests
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- ПОЛУЧАЕМ ПЕРЕМЕННЫЕ ИЗ RENDER ---
API_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not API_TOKEN:
    raise ValueError("BOT_TOKEN не найден в Environment Variables")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)

dp = Dispatcher()
scheduler = AsyncIOScheduler()


async def get_ai_prompt(image_url):
    try:
        response = requests.get(image_url, timeout=15)
        if response.status_code != 200:
            return None

        model = genai.GenerativeModel("gemini-1.5-flash")

        result = model.generate_content([
            "Create short Midjourney prompt",
            {
                "mime_type": "image/jpeg",
                "data": response.content
            }
        ])

        return result.text
    except Exception as e:
        logger.error(e)
        return None


async def post_now():
    logger.info("Проверка Reddit")

    subs = ["Midjourney", "AIArt", "StableDiffusion"]
    sub = random.choice(subs)

    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        url = f"https://www.reddit.com/r/{sub}/hot.json?limit=10"
        r = requests.get(url, headers=headers, timeout=10)

        posts = r.json()["data"]["children"]

        for post in posts:
            img = post["data"].get("url")

            if img and img.endswith((".jpg", ".png", ".jpeg")):
                prompt = await get_ai_prompt(img)

                if prompt:
                    await bot.send_photo(
                        CHANNEL_ID,
                        img,
                        caption=f"Prompt:\n{prompt}"
                    )
                    return
    except Exception as e:
        logger.error(e)


async def handle(request):
    return web.Response(text="Bot is running")


async def main():
    # web server для Render
    app = web.Application()
    app.router.add_get("/", handle)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    await bot.delete_webhook(drop_pending_updates=True)

    scheduler.add_job(post_now, "interval", minutes=25)
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())