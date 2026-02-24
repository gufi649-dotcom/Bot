import asyncio
import logging
import requests
import random
import os
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- CONFIG ---
API_TOKEN = '8309438145:AAFTjTJ9OHgn1tVjqLneqDLT3Q8odMrryLo'
GEMINI_API_KEY = 'AIzaSyAJngwLCzOjjqFe_EkxQctwm1QT-vZEbrc'
CHANNEL_ID = '@iPromt_AI'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
scheduler = AsyncIOScheduler()
posted_urls = set()

# --- ПРЯМОЙ ЗАПРОС К GEMINI (БЕЗ SDK) ---
async def get_ai_generated_prompt(image_url):
    try:
        # 1. Качаем картинку
        img_data = requests.get(image_url, timeout=10).content
        import base64
        base64_image = base64.b64encode(img_data).decode('utf-8')

        # 2. Формируем запрос к API v1 (стабильный путь)
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Write a professional AI art prompt for this image. English only. No preamble."},
                    {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}
                ]
            }]
        }
        
        r = requests.post(url, json=payload, timeout=20)
        res_json = r.json()
        
        # Извлекаем текст
        prompt = res_json['candidates'][0]['content']['parts'][0]['text']
        return prompt.strip()
    except Exception as e:
        logging.error(f"Gemini direct error: {e}")
        return None

def escape_md(text):
    for s in r'_*[]()~`>#+-=|{}.!':
        text = text.replace(s, f'\\{s}')
    return text

async def post_now():
    subs = ['Midjourney', 'StableDiffusion', 'AIArt']
    url = f"https://www.reddit.com/r/{random.choice(subs)}/hot.json?limit=10"
    headers = {'User-Agent': f'BananahBot/11.0_{random.randint(1,999)}'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        posts = r.json().get('data', {}).get('children', [])
        random.shuffle(posts)
        for post in posts:
            img_url = post.get('data', {}).get('url', '')
            if any(img_url.lower().endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                if img_url not in posted_urls:
                    prompt = await get_ai_generated_prompt(img_url)
                    if prompt:
                        posted_urls.add(img_url)
                        caption = f"🖼 *Visual AI Analysis*\n\n👤 *Prompt:* `{escape_md(prompt)}`"
                        photo = types.BufferedInputFile(requests.get(img_url).content, "art.jpg")
                        await bot.send_photo(CHANNEL_ID, photo, caption=caption)
                        logging.info("!!! POSTED SUCCESSFULLY !!!")
                        return True
    except Exception as e:
        logging.error(f"Reddit error: {e}")
    return False

# --- WEB SERVER ---
async def handle(request):
    return web.Response(text="Service Active")

async def on_startup(app):
    logging.info("Starting up... waiting for old instances to die.")
    await asyncio.sleep(15) # Увеличили паузу для Render
    
    await bot.delete_webhook(drop_pending_updates=True)
    
    scheduler.add_job(post_now, 'interval', minutes=25)
    scheduler.start()
    
    asyncio.create_task(post_now())
    # skip_updates=True игнорирует сообщения, накопленные во время "конфликта"
    asyncio.create_task(dp.start_polling(bot, skip_updates=True))

async def create_app():
    app = web.Application()
    app.router.add_get('/', handle)
    app.on_startup.append(on_startup)
    return app

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    web.run_app(create_app(), host='0.0.0.0', port=port)