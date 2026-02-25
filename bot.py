import asyncio
import logging
import random
import os
import aiohttp
import google.generativeai as genai
from aiogram import Bot, types
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
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY не найден в Environment Variables")
if not CHANNEL_ID:
    raise ValueError("CHANNEL_ID не найден в Environment Variables")

# Если CHANNEL_ID это числовой ID канала, преобразуем в int
try:
    CHANNEL_ID = int(CHANNEL_ID)
except ValueError:
    pass  # Если это @username, оставляем как строку

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройка Gemini API
genai.configure(api_key=GEMINI_API_KEY)

bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)

scheduler = AsyncIOScheduler()


async def get_ai_prompt(image_url):
    """Генерирует короткий prompt для Midjourney через Gemini API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url, timeout=15) as response:
                if response.status != 200:
                    logger.warning(f"Не удалось скачать изображение: {image_url}")
                    return None
                img_bytes = await response.read()

        model = genai.GenerativeModel("gemini-1.5-flash")
        result = model.generate_content([
            "Create short Midjourney prompt",
            {"mime_type": "image/jpeg", "data": img_bytes}
        ])
        return result.text
    except Exception as e:
        logger.error(f"Ошибка get_ai_prompt: {e}")
        return None


async def post_now():
    """Берёт случайный пост с Reddit и публикует его в канал"""
    logger.info("Запуск задачи post_now")

    subs = ["Midjourney", "AIArt", "StableDiffusion"]
    sub = random.choice(subs)
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        url = f"https://www.reddit.com/r/{sub}/hot.json?limit=10"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as r:
                if r.status != 200:
                    logger.warning(f"Reddit вернул статус {r.status}")
                    return
                data = await r.json()

        posts = data.get("data", {}).get("children", [])
        for post in posts:
            img = post["data"].get("url")
            if img and img.endswith((".jpg", ".png", ".jpeg")):
                logger.info(f"Найдена картинка: {img}")
                prompt = await get_ai_prompt(img)
                if prompt:
                    try:
                        await bot.send_photo(
                            CHANNEL_ID,
                            img,
                            caption=f"Prompt:\n{prompt}"
                        )
                        logger.info("Сообщение успешно отправлено")
                        return
                    except Exception as e:
                        logger.error(f"Ошибка отправки в Telegram: {e}")
    except Exception as e:
        logger.error(f"Ошибка post_now: {e}")


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
    logger.info(f"Web server запущен на порту {port}")

    # Удаляем webhook, если был
    await bot.delete_webhook(drop_pending_updates=True)

    # APScheduler для периодической публикации
    scheduler.add_job(lambda: asyncio.create_task(post_now()), "interval", minutes=25)
    scheduler.start()
    logger.info("Scheduler запущен")

    # Держим цикл живым
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())