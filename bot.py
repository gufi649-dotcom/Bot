import os
import asyncio
import logging
import random
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from google import genai

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", 10000))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# GEMINI (NEW SDK)
# =========================

genai_client = genai.Client(api_key=GEMINI_API_KEY)

# =========================
# TELEGRAM
# =========================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# =========================
# PROMPT TRENDS
# =========================

TRENDS = [
    "романтическая пара дома",
    "девушка в зеркальном селфи",
    "парень в мягком дневном свете",
    "домашняя фотосессия",
    "уютная сцена в спальне",
]

# =========================
# PROMPT GENERATOR
# =========================

async def generate_prompt():
    trend = random.choice(TRENDS)

    try:
        response = genai_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=f"""
Создай ультрареалистичный фото-промпт для Midjourney / Stable Diffusion.

Тема: {trend}

Обязательно:
— identity lock лица
— естественная кожа
— живая текстура
— cinematic lighting
— shallow depth of field
— фотореализм
— 8k
— мягкий дневной свет
— детальная композиция
— negative prompt в конце

Верни только готовый промпт.
"""
        )

        return response.text.strip()

    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return f"{trend}, ultra realistic, cinematic lighting, 8k, shallow depth of field"

# =========================
# KEYBOARD
# =========================

def prompt_keyboard(prompt):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Скопировать промпт",
                    switch_inline_query=prompt
                )
            ]
        ]
    )

# =========================
# POST FUNCTION
# =========================

async def post_now():
    logger.info("Создаю пост")

    prompt = await generate_prompt()

    caption = f"""
🔥 <b>Viral AI Prompt</b>

<code>{prompt}</code>

🚀 Используй в Midjourney / SD
"""

    try:
        await bot.send_message(
            CHANNEL_ID,
            caption,
            reply_markup=prompt_keyboard(prompt)
        )
        logger.info("Пост отправлен")

    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")

# =========================
# COMMAND
# =========================

@dp.message(F.text == "/post")
async def manual_post(message: Message):
    await post_now()
    await message.answer("Пост опубликован")

# =========================
# SCHEDULER
# =========================

async def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: asyncio.create_task(post_now()), "interval", minutes=30)
    scheduler.start()
    logger.info("Планировщик запущен")

# =========================
# HEALTH CHECK
# =========================

async def health(request):
    return web.Response(text="BOT IS RUNNING")

# =========================
# STARTUP
# =========================

async def on_startup(app):
    logger.info("Удаляем webhook...")
    await bot.delete_webhook(drop_pending_updates=True)

    await start_scheduler()
    asyncio.create_task(dp.start_polling(bot))

# =========================
# MAIN
# =========================

def main():
    app = web.Application()
    app.router.add_get("/", health)
    app.on_startup.append(on_startup)

    logger.info("Сервер запущен")
    web.run_app(app, port=PORT)

if __name__ == "__main__":
    main()