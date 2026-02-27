import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
import google.generativeai as genai
import aiohttp

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"

PORT = int(os.getenv("PORT", 10000))

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

SYSTEM_PROMPT = """
You are an elite AI Prompt Analyzer used by professional photography studios.
Analyze image with maximum precision.
Return ultra detailed prompt and scene breakdown.
"""


@dp.message()
async def handle_message(message: types.Message):
    if not message.photo:
        await message.answer("Отправь фотографию.")
        return

    await message.answer("Анализирую изображение...")

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)

    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"

    async with aiohttp.ClientSession() as session:
        async with session.get(file_url) as resp:
            image_bytes = await resp.read()

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


async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
    print("Webhook установлен:", WEBHOOK_URL)


async def on_shutdown(app):
    await bot.delete_webhook()


def main():
    app = web.Application()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path=WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)

    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()