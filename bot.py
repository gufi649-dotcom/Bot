import asyncio
import logging
import random
import os
import aiohttp
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================= НАСТРОЙКИ =================

API_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
)

dp = Dispatcher()
scheduler = AsyncIOScheduler()

# ================= UTILS =================

def escape_md(text):
    for s in r'_*[]()~`>#+-=|{}.!':
        text = text.replace(s, f'\\{s}')
    return text


async def download_image(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.read()
    return None


# ================= GEMINI =================

async def get_ai_generated_prompt(image_bytes):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        response = model.generate_content([
            "Create a short Midjourney prompt for this image. English only.",
            {
                "mime_type": "image/jpeg",
                "data": image_bytes
            }
        ])

        if response and response.text:
            return response.text.strip()

    except Exception as e:
        logger.error(f"Gemini error: {e}")

    return None


# ================= REDDIT =================

async def fetch_reddit_posts(sub):
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit=15&raw_json=1"

    headers = {
        "User-Agent": "telegram-bot:ipromt:v1.0"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as r:
            if r.status != 200:
                logger.error(f"Reddit error: {r.status}")
                return []

            data = await r.json()
            return data.get("data", {}).get("children", [])


# ================= POST =================

async def post_now():
    logger.info("=== ПРОВЕРКА REDDIT ===")

    subs = ["Midjourney", "AIArt", "StableDiffusion"]
    sub = random.choice(subs)

    posts = await fetch_reddit_posts(sub)

    for post in posts:
        img_url = post["data"].get("url", "")

        if not img_url.endswith((".jpg", ".png", ".jpeg")):
            continue

        image_bytes = await download_image(img_url)
        if not image_bytes:
            continue

        prompt = await get_ai_generated_prompt(image_bytes)
        if not prompt:
            continue

        caption = (
            f"🖼 *Visual Analysis* \\(r/{sub}\\)\n\n"
            f"👤 *Prompt:* `{escape_md(prompt)}`"
        )

        await bot.send_photo(
            CHANNEL_ID,
            types.BufferedInputFile(image_bytes, filename="image.jpg"),
            caption=caption
        )

        logger.info("ПОСТ ОТПРАВЛЕН")
        return

    logger.warning("Картинки не найдены")


# ================= SERVER =================

async def handle(request):
    return web.Response(text="Bot is running")


# ================= MAIN =================

async def main():
    app = web.Application()
    app.router.add_get("/", handle)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(
        runner,
        "0.0.0.0",
        int(os.environ.get("PORT", 10000))
    ).start()

    # Убираем webhook
    await bot.delete_webhook(drop_pending_updates=True)

    # Планировщик
    scheduler.add_job(post_now, "interval", minutes=25)
    scheduler.start()

    logger.info("Бот запущен")

    # Первый пост
    await post_now()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())