import asyncio
import logging
import random
import os
import requests
import google.generativeai as genai
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

API_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)

dp = Dispatcher()
scheduler = AsyncIOScheduler()


# запасные промпты если AI не ответил
fallback_prompts = [
    "ultra realistic cyberpunk girl, neon lights, cinematic lighting, 8k",
    "futuristic city at night, rain, neon reflections, ultra detailed",
    "AI anime girl portrait, soft lighting, masterpiece, 4k",
    "space traveler, cinematic shot, volumetric light, hyper realistic",
    "cyberpunk samurai, glowing armor, epic composition"
]


async def get_ai_prompt(image_url):
    try:
        response = requests.get(image_url, timeout=15)
        if response.status_code != 200:
            return random.choice(fallback_prompts)

        model = genai.GenerativeModel("gemini-1.5-flash-latest")

        result = model.generate_content([
            "Write a short Midjourney prompt describing this image.",
            {
                "mime_type": "image/jpeg",
                "data": response.content
            }
        ])

        if result.text:
            return result.text.strip()

    except Exception as e:
        logger.error(e)

    return random.choice(fallback_prompts)


async def get_reddit_image():
    subs = ["Midjourney", "AIArt", "StableDiffusion"]

    headers = {
        "User-Agent": "Mozilla/5.0 (TelegramBot)"
    }

    for sub in subs:
        try:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=10"
            r = requests.get(url, headers=headers, timeout=10)

            if r.status_code != 200:
                continue

            posts = r.json()["data"]["children"]

            for post in posts:
                img = post["data"].get("url")

                if img and img.endswith((".jpg", ".png", ".jpeg")):
                    return img

        except:
            pass

    # если Reddit не дал картинку
    return random.choice([
        "https://images.unsplash.com/photo-1677442136019-21780ecad995",
        "https://images.unsplash.com/photo-1682687982501-1e58ab814714"
    ])


async def post_now():
    logger.info("Создаю новый пост")

    image = await get_reddit_image()
    prompt = await get_ai_prompt(image)

    caption = f"""
🔥 AI IMAGE PROMPT

`{prompt}`

Use this prompt in Midjourney / Leonardo / SDXL
"""

    try:
        await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=image,
            caption=caption
        )
        logger.info("Пост опубликован")

    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")


async def handle(request):
    return web.Response(text="Bot is running")


async def main():
    app = web.Application()
    app.router.add_get("/", handle)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info("Сервер запущен")

    await bot.delete_webhook(drop_pending_updates=True)

    await post_now()

    scheduler.add_job(post_now, "interval", hours=3)
    scheduler.start()

    logger.info("Планировщик запущен")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())