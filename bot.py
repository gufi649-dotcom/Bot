import os
import asyncio
import logging
import random
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from google import genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", 10000))

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

genai_client = genai.Client(api_key=GEMINI_API_KEY)

TRENDS = [
    "девушка портрет",
    "парень портрет",
    "люди lifestyle",
    "пара романтика",
    "фото девушки дома",
    "парень у окна",
    "люди в городе",
    "девушка зеркало селфи",
    "пара уютная атмосфера",
]

async def generate_prompt():
    trend = random.choice(TRENDS)

    prompt_text = f"""
Создай ультрареалистичный AI prompt для генерации фотографии.
Тема: {trend}

Опиши:
— внешность
— позу
— одежду
— свет
— камеру
— атмосферу
— негативный промпт

Сделай максимально детально.
"""

    try:
        response = genai_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt_text
        )

        return response.text

    except Exception as e:
        logger.error(e)
        return trend


async def post():
    prompt = await generate_prompt()

    text = f"""
🔥 AI PROMPT

<code>{prompt}</code>
"""

    await bot.send_message(CHANNEL_ID, text)


@dp.message(F.text == "/start")
async def start(message: Message):
    await message.answer("Бот работает")


@dp.message(F.text == "/post")
async def manual_post(message: Message):
    await post()
    await message.answer("Пост отправлен")


async def scheduler_start():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: asyncio.create_task(post()), "interval", minutes=30)
    scheduler.start()
    logger.info("Scheduler started")


async def health(request):
    return web.Response(text="OK")


async def start_bot(app):
    logger.info("Удаляем webhook")

    await bot.delete_webhook(drop_pending_updates=True)

    await scheduler_start()

    asyncio.create_task(dp.start_polling(bot))


def main():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_head("/", health)
    app.on_startup.append(start_bot)

    logger.info("Server started")

    web.run_app(app, port=PORT)


if __name__ == "__main__":
    main()