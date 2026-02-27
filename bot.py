import asyncio
import os
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
import google.generativeai as genai

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro")

SYSTEM_PROMPT = """
You are an elite AI Prompt Analyzer used by professional photography studios.

Analyze the image with maximum precision and produce a studio-level prompt.

OUTPUT:

1. ULTRA DETAILED PROMPT
2. COMPOSITION
3. SUBJECT ANALYSIS
4. FACE MICRO DETAILS
5. HAIR STRUCTURE
6. CLOTHING
7. LIGHTING BLUEPRINT
8. ENVIRONMENT
9. CAMERA SIMULATION
10. GENERATION SETTINGS
"""

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "Отправь фотографию — я сделаю профессиональный prompt-анализ."
    )


async def download_file(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.read()


@dp.message(lambda message: message.photo)
async def analyze_photo(message: types.Message):
    await message.answer("Анализирую изображение...")

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)

    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
    image_bytes = await download_file(file_url)

    try:
        response = model.generate_content([
            SYSTEM_PROMPT,
            {
                "mime_type": "image/jpeg",
                "data": image_bytes
            }
        ])

        result = response.text

        for i in range(0, len(result), 4000):
            await message.answer(result[i:i+4000])

    except Exception as e:
        await message.answer(f"Ошибка анализа: {e}")


async def main():
    print("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())