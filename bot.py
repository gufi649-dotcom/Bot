import asyncio
import logging
import requests
import random
import os
from google import genai
from google.genai import types as genai_types
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8309438145:AAFTjTJ9OHgn1tVjqLneqDLT3Q8odMrryLo'
GEMINI_API_KEY = 'AIzaSyAJngwLCzOjjqFe_EkxQctwm1QT-vZEbrc'
CHANNEL_ID = '@iPromt_AI'

# Принудительно используем стабильную версию API v1
client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1'})

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
scheduler = AsyncIOScheduler()
posted_urls = set()

# --- ЛОГИКА ---
async def get_ai_generated_prompt(image_url):
    try:
        response = requests.get(image_url, timeout=10)
        if response.status_code != 200: return None
        
        ai_res = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=[
                "Write a highly detailed professional AI art prompt for this image. Output ONLY the English text.",
                genai_types.Part.from_bytes(data=response.content, mime_type="image/jpeg")
            ]
        )
        return ai_res.text.strip()
    except Exception as e:
        logging.error(f"Gemini API Error: {e}")
        return None

def escape_md(text):
    for s in r'_*[]()~`>#+-=|{}.!':
        text = text.replace(s, f'\\{s}')
    return text

async def post_now():
    subs = ['Midjourney', 'StableDiffusion', 'AIArt', 'DigitalArt']
    url = f"https://www.reddit.com/r/{random.choice(subs)}/hot.json?limit=15"
    headers = {'User-Agent': f'BananahBot/8.0_{random.randint(1,1000)}'}
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json().get('data', {}).get('children', [])
        random.shuffle(data)
        
        for post in data:
            img_url = post.get('data', {}).get('url', '')
            if any(img_url.lower().endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                if img_url not in posted_urls:
                    prompt = await get_ai_generated_prompt(img_url)
                    if prompt:
                        posted_urls.add(img_url)
                        caption = (
                            f"🖼 *Visual AI Analysis*\n\n"
                            f"👤 *Prompt:* `{escape_md(prompt)}`"
                        )
                        photo_req = requests.get(img_url)
                        photo = types.BufferedInputFile(photo_req.content, "art.jpg")
                        await bot.send_photo(CHANNEL_ID, photo, caption=caption)
                        logging.info("SUCCESS: Post sent!")
                        return True
    except Exception as e:
        logging.error(f"Reddit Loop Error: {e}")
    return False

# --- WEB SERVER & STARTUP ---
async def handle(request):
    return web.Response(text="Bot is operational")

async def on_startup(app):
    # Удалили проблемный get_session()
    # Просто сбрасываем вебхук и запускаем процессы
    await bot.delete_webhook(drop_pending_updates=True)
    
    scheduler.add_job(post_now, 'interval', minutes=25)
    scheduler.start()
    
    # Запуск задач в фоне
    asyncio.create_task(post_now())
    asyncio.create_task(dp.start_polling(bot, skip_updates=True))
    logging.info("Bot started successfully!")

async def create_app():
    app = web.Application()
    app.router.add_get('/', handle)
    app.on_startup.append(on_startup)
    return app

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    web.run_app(create_app(), host='0.0.0.0', port=port)
