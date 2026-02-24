import asyncio
import logging
import requests
import random
import os
import base64
import sys
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

async def get_ai_generated_prompt(image_url):
    try:
        img_resp = requests.get(image_url, timeout=15)
        if img_resp.status_code != 200: return None
        
        base64_image = base64.b64encode(img_resp.content).decode('utf-8')
        
        # Переход на СТАБИЛЬНУЮ версию v1 и ПРЯМОЙ путь к модели
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Create a detailed AI art prompt for this. English only, no quotes, no intro."},
                    {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}
                ]
            }]
        }
        
        r = requests.post(url, json=payload, timeout=25)
        res_json = r.json()
        
        if 'candidates' in res_json:
            return res_json['candidates'][0]['content']['parts'][0]['text'].strip()
        
        logging.error(f"Gemini API Error: {res_json}")
        return None
    except Exception as e:
        logging.error(f"Gemini Exception: {e}")
        return None

def escape_md(text):
    for s in r'_*[]()~`>#+-=|{}.!':
        text = text.replace(s, f'\\{s}')
    return text

async def post_now():
    subs = ['Midjourney', 'AIArt', 'StableDiffusion']
    url = f"https://www.reddit.com/r/{random.choice(subs)}/hot.json?limit=15"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        data_json = r.json()
        posts = data_json.get('data', {}).get('children', [])
        random.shuffle(posts)
        
        for post in posts:
            img_url = post.get('data', {}).get('url', '')
            if any(img_url.lower().endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                if img_url not in posted_urls:
                    prompt = await get_ai_generated_prompt(img_url)
                    if prompt:
                        posted_urls.add(img_url)
                        caption = f"🖼 *Visual AI Analysis*\n\n👤 *Prompt:* `{escape_md(prompt)}`"
                        photo = types.BufferedInputFile(requests.get(img_url).content, "image.jpg")
                        await bot.send_photo(CHANNEL_ID, photo, caption=caption)
                        logging.info("SUCCESSFUL POST")
                        return True
    except Exception as e:
        logging.error(f"Post error: {e}")
    return False

async def handle(request):
    return web.Response(text="Bot Status: OK")

async def on_startup(app):
    logging.info("Startup sequence initiated...")
    
    # 1. Даем Render время на переключение
    await asyncio.sleep(15) 
    
    # 2. Очистка вебхука
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logging.warning(f"Webhook delete failed: {e}")

    scheduler.add_job(post_now, 'interval', minutes=25)
    scheduler.start()
    
    asyncio.create_task(post_now())
    
    # 3. Запуск с автоматическим выходом при конфликте
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        if "Conflict" in str(e):
            logging.error("CRITICAL CONFLICT: Restarting...")
            sys.exit(1) # Render перезапустит контейнер автоматически

async def create_app():
    app = web.Application()
    app.router.add_get('/', handle)
    app.on_startup.append(on_startup)
    return app

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    web.run_app(create_app(), host='0.0.0.0', port=port)
 