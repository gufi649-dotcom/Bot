import os
import logging
import asyncio
import random
from aiohttp import web, ClientSession
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.client.bot import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import google.generativeai as genai  # можно заменить на google.genai в будущем

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ⚡ Инициализация бота под aiogram 3.7+
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

app = web.Application()

# Тренды про людей и пары
TRENDS = [
    "парень",
    "девушка",
    "пара",
    "люди",
    "молодая девушка",
    "молодой парень",
    "романтическая пара",
    "группа людей",
    "друзья",
    "семья"
]

# Запасные изображения
FALLBACK_IMAGES = [
    "https://picsum.photos/1024/1024",
    "https://source.unsplash.com/1024x1024/?people",
    "https://source.unsplash.com/1024x1024/?portrait",
    "https://source.unsplash.com/1024x1024/?couple",
    "https://source.unsplash.com/1024x1024/?friends",
]


async def get_image():
    try:
        url = "https://meme-api.com/gimme/StableDiffusion"
        async with ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("url")
                else:
                    logger.warning(f"Reddit статус {resp.status}")
    except Exception as e:
        logger.error(f"Ошибка при получении изображения: {e}")

    logger.info("Используем резервное изображение")
    return random.choice(FALLBACK_IMAGES)


async def generate_prompt():
    trend = random.choice(TRENDS)
    try:
        response = model.generate_content(
            f"""
Создай ультрареалистичный AI промпт для Midjourney / Stable Diffusion по теме: {trend}.
Следуй этим инструкциям:

ВНЕШНОСТЬ:
- Использовать лицо с референса (identity lock)
- Сохранить форму глаз, губ, носа, пропорции, естественную асимметрию лица
- Молодая кожа, большие глаза, естественный блеск губ, живая текстура кожи
- Сохраняется исходная прическа

ОДЕЖДА И ДЕТАЛИ:
- Домашняя одежда или пижама, мягкая, струящаяся
- Акцент на руках или предметах (например, зажигалка, букет)
- Композиция: крупный план объекта на переднем плане, фон слегка размытый

СВЕТ И ЦВЕТ:
- Естественный свет или один источник (например, пламя, окно)
- Мягкий свет, драматичные тени, отражения в глазах
- Глубокие тени, контраст и подсветка объекта

КАМЕРА И СТИЛЬ:
- Close-up или крупный план
- Shallow depth of field, акцент на главном объекте
- Cinematic, фотореализм, 8k, высокая детализация
- Мягкое боке, эффект случайного красивого кадра

ПОЗА И КОМПОЗИЦИЯ:
- Передний план резкий, задний слегка размытый
- Акцент на объекте, центральная композиция
- Если есть отражения, лицо и тело слегка вне фокуса

НЕГАТИВНЫЙ:
- Изменение лица, пластик, мультяшность
- Лишние предметы и люди
- Резкий фон, пересвет, агрессивная ретушь
- Неестественные пропорции или деформации
- Лишние источники света

Верни только готовый промпт, без лишнего текста.
"""
        )
        return getattr(response, "text", "").strip() or f"{trend}, ultra realistic, cinematic lighting, 8k, shallow depth of field"
    except Exception as e:
        logger.error(f"Ошибка Gemini: {e}")
        return f"{trend}, ultra realistic, cinematic lighting, 8k, shallow depth of field"


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


async def post_now():
    logger.info("Создаю пост")

    image_url = await get_image()
    prompt = await generate_prompt()

    caption = f"""
🔥 <b>Viral AI Prompt</b>

<code>{prompt}</code>

🚀 Используй в Midjourney / SD
"""

    try:
        await bot.send_photo(
            CHANNEL_ID,
            photo=image_url,
            caption=caption,
            reply_markup=prompt_keyboard(prompt)
        )
        logger.info(f"Пост отправлен с промптом: {prompt[:50]}...")
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")


@dp.message(F.text == "/post")
async def manual_post(message: Message):
    await post_now()
    await message.answer("Пост опубликован")


async def scheduler():
    sched = AsyncIOScheduler()
    sched.add_job(lambda: asyncio.create_task(post_now()), "interval", minutes=30)
    sched.start()
    logger.info("Планировщик запущен")


async def handle(request):
    return web.Response(text="BOT WORKING")


async def on_startup(app):
    await scheduler()
    asyncio.create_task(dp.start_polling(bot))


if __name__ == "__main__":
    logger.info("Сервер запущен")
    app.on_startup.append(on_startup)
    web.run_app(app, port=int(os.getenv("PORT", 10000)))