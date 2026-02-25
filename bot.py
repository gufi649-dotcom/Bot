import asyncio
import logging
import random
import os
import aiohttp
import google.generativeai as genai
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

API_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)

scheduler = AsyncIOScheduler()

HEADERS = {
    "User-Agent": "telegram-bot/1.0"
}

subs = [
    "StableDiffusion",
    "midjourney",
    "AIArt",
    "ArtificialInteligence"
]

fallback_images = [
    "https://picsum.photos/1024",
    "https://picsum.photos/seed/ai/1024",
    "https://picsum.photos/seed/art/1024"
]

async def get_image_from_reddit():
    random.shuffle(subs)

    for sub in subs:
        try:
            url = f"https://old.reddit.com/r/{sub}/hot.json?limit=30"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=HEADERS, timeout=15) as r:
                    if r.status != 200:
                        logger.warning(f"Reddit ошибка {r.status}")
                        continue

                    data = await r.json()
                    posts = data["data"]["children"]
                    random.shuffle(posts)

                    for post in posts:
                        img = post["data"].get("url")
                        if img and img.endswith((".jpg", ".png", ".jpeg")):
                            return img

        except Exception as e:
            logger.error(f"Reddit ошибка: {e}")

    return None


async def generate_prompt(image_url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                img = await resp.read()

        model = genai.GenerativeModel("gemini-1.5-flash")

        result = model.generate_content([
            "Create short Midjourney prompt",
            {
                "mime_type": "image/jpeg",
                "data": img
            }
        ])

        return result.text

    except Exception as e:
        logger.error(e)
        return "AI generated artwork"


async def post_now():
    try:
        logger.info("Начинаю публикацию")

        img = await get_image_from_reddit()

        if not img:
            logger.info("Используем резервное изображение")
            img = random.choice(fallback_images)

        prompt = await generate_prompt(img)

        await bot.send_photo(
            CHANNEL_ID,
            img,
            caption=f"✨ AI Prompt\n\n{prompt}"
        )

        logger.info("Пост отправлен")

    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")


async def healthcheck(request):
    return web.Response(text="Bot running")


async def main():
    app = web.Application()
    app.router.add_get("/", healthcheck)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info("Сервер запущен")

    await bot.delete_webhook(drop_pending_updates=True)

    # первый пост сразу
    await post_now()

    # каждые 10 минут
    scheduler.add_job(post_now, "interval", minutes=10)
    scheduler.start()

    logger.info("Планировщик запущен")

    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())