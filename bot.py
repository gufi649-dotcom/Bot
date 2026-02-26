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

# ====== НАСТРОЙКИ ======

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
scheduler = AsyncIOScheduler()

# ====== ГЕНЕРАЦИЯ ПРОМПТА ======

def generate_prompt():
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        response = model.generate_content(
            "Create a viral Midjourney prompt for AI art. "
            "Make it short, detailed, cinematic, trending."
        )

        return response.text.strip()

    except Exception as e:
        logger.error(f"Ошибка Gemini: {e}")
        return "cyberpunk futuristic city, neon lights, ultra detailed, 8k"

# ====== ПОЛУЧЕНИЕ КАРТИНКИ ======

def get_image():
    images = [
        "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee",
        "https://images.unsplash.com/photo-1518770660439-4636190af475",
        "https://images.unsplash.com/photo-1535223289827-42f1e9919769"
    ]
    return random.choice(images)

# ====== ПУБЛИКАЦИЯ ======

async def post_now():
    logger.info("Создаю пост")

    image = get_image()
    prompt = generate_prompt()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Copy Prompt",
                    url="https://t.me/share/url?text=" + prompt
                )
            ]
        ]
    )

    try:
        await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=image,
            caption=f"<b>🔥 AI Prompt</b>\n\n<code>{prompt}</code>",
            reply_markup=keyboard
        )

        logger.info("Пост опубликован")

    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")

# ====== СЕРВЕР ДЛЯ RENDER ======

async def handle(request):
    return web.Response(text="Bot running")

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

    scheduler.add_job(post_now, "interval", minutes=30)
    scheduler.start()

    logger.info("Планировщик запущен")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())