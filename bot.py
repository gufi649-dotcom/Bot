import asyncio
import logging
import os
import random
import requests
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = Bot(token=BOT_TOKEN)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash-latest")

# темы постов
topics = [
    "cinematic cyberpunk city",
    "realistic space station",
    "future robot design",
    "fantasy castle at sunset",
    "alien planet landscape",
    "dark sci-fi warrior",
    "ultra realistic dragon",
]

# резервные изображения
backup_images = [
    "https://images.unsplash.com/photo-1518779578993-ec3579fee39f",
    "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee",
    "https://images.unsplash.com/photo-1520975916090-3105956dac38",
]


def get_image():
    try:
        topic = random.choice(topics)
        url = f"https://source.unsplash.com/1600x900/?{topic}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return url
    except:
        pass

    return random.choice(backup_images)


def generate_prompt():
    try:
        response = model.generate_content(
            "Create a viral AI image prompt for Midjourney. Make it short and powerful."
        )
        return response.text
    except Exception as e:
        logging.warning("Gemini ошибка")
        return "Ultra realistic cinematic lighting, 8k, masterpiece"


async def post():
    logging.info("Публикация поста")

    image = get_image()
    prompt = generate_prompt()

    text = f"""
🔥 AI PROMPT

`{prompt}`

#ai #midjourney #prompt
"""

    try:
        await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=image,
            caption=text,
            parse_mode="Markdown"
        )
        logging.info("Пост опубликован")

    except Exception as e:
        logging.error(f"Ошибка отправки: {e}")


async def main():
    scheduler = AsyncIOScheduler()

    scheduler.add_job(post, "interval", minutes=20)
    scheduler.start()

    await post()

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())