import asyncio
import logging
import os
import random
import requests
import google.generativeai as genai

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler


# ================= НАСТРОЙКИ =================

API_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not API_TOKEN:
    raise ValueError("BOT_TOKEN не найден")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
scheduler = AsyncIOScheduler()


# ================= ГЕНЕРАЦИЯ ПРОМПТА =================

def generate_prompt():
    try:
        model = genai.GenerativeModel("gemini-pro")

        response = model.generate_content(
            "Create a short viral Midjourney prompt for futuristic AI art. "
            "Make it detailed, cinematic, trending on ArtStation."
        )

        return response.text.strip()

    except Exception as e:
        logger.error(f"Ошибка Gemini: {e}")
        return "futuristic cyberpunk city, cinematic lighting, ultra detailed, 8k"


# ================= REDDIT =================

def get_image_from_reddit():
    subs = ["Midjourney", "AIArt", "StableDiffusion"]
    sub = random.choice(subs)

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        url = f"https://old.reddit.com/r/{sub}/top.json?t=day&limit=20"
        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code != 200:
            logger.warning(f"Reddit статус {r.status_code}")
            return None

        posts = r.json()["data"]["children"]

        for post in posts:
            img = post["data"].get("url")
            if img and img.endswith((".jpg", ".png", ".jpeg")):
                return img

    except Exception as e:
        logger.error(f"Ошибка Reddit: {e}")

    return None


# ================= ПУБЛИКАЦИЯ =================

async def post_now():
    logger.info("Создаю новый пост")

    image_url = get_image_from_reddit()

    if not image_url:
        logger.info("Используем резервное изображение")
        image_url = "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee"

    prompt = generate_prompt()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Copy Prompt",
                    switch_inline_query=prompt
                )
            ]
        ]
    )

    try:
        await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=image_url,
            caption=f"<b>🔥 AI Prompt</b>\n\n<code>{prompt}</code>",
            reply_markup=keyboard
        )

        logger.info("Пост опубликован")

    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")


# ================= WEB SERVER ДЛЯ RENDER =================

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

    await post_now()  # пост сразу после запуска

    scheduler.add_job(post_now, "interval", minutes=60)
    scheduler.start()

    logger.info("Планировщик запущен")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())