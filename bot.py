import asyncio
import logging
import requests
import random
import os
import base64
import sys

# Срочная проверка импортов при запуске
try:
    from aiogram import Bot, Dispatcher, types
    from aiogram.enums import ParseMode
    from aiogram.client.default import DefaultBotProperties
    from aiohttp import web
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8309438145:AAFTjTJ9OHgn1tVjqLneqDLT3Q8odMrryLo'
GEMINI_API_KEY = 'AIzaSyAJngwLCzOjjqFe_EkxQctwm1QT-vZEbrc'
CHANNEL_ID = '@iPromt_AI'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
scheduler = AsyncIOScheduler()
posted_urls = set()

def escape_md(text):
    for s in r'_*[]()~`>#+-=|{}.!':
        text = text.replace(s, f'\\{s}')
    return text

async def get_ai_generated_prompt(image_url):
    try:
        img_resp = requests.get(image_url, timeout=15)
        if img_resp.status_code != 200: return None
        base64_image = base64.b64encode(img_resp.content).decode('utf-8')
        
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [
                {"text": "Create a detailed Midjourney prompt for this image. English only, no intro."},
                {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}
            ]}]
        }
        r = requests.post(url, json=payload, timeout=25)
        res = r.json()
        return res['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        logging.error(f"Gemini fail: {e}")
        return None

async def post_now():
    subs = ['Midjourney', 'AIArt', 'StableDiffusion']
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0'}
    try:
        r = requests.get(f"https://www.reddit.com/r/{random.choice(subs)}/hot.json", headers=headers, timeout=15)
        posts = r.json().get('data', {}).get('children', [])
        for post in posts:
            img_url = post['data'].get('url', '')
            if img_url.lower().endswith(('.jpg', '.jpeg', '.png')) and img_url not in posted_urls:
                prompt = await get_ai_generated_prompt(img_url)
                if prompt:
                    posted_urls.add(img_url)
                    caption = f"🖼 *Visual AI Analysis*\n\n👤 *Prompt:* `{escape_md(prompt)}`"
                    await bot.send_photo(CHANNEL_ID, img_url, caption=caption)
                    logging.info("SUCCESS: Posted to channel")
                    return True
    except Exception as e:
        logging.error(f"Reddit error: {e}")
    return False

# --- ПРИВЯЗКА ПОРТА ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Bot Status: Active")

async def main():
    # Запускаем веб-сервер первым, чтобы Render был доволен
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    logging.info(f"Web server on port {port}")

    # Очищаем вебхуки и ждем, пока старый инстанс Render умрет
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Waiting 45s for environment cleanup...")
    await asyncio.sleep(45)

    scheduler.add_job(post_now, 'interval', minutes=25)
    scheduler.start()
    
    asyncio.create_task(post_now())
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"CRITICAL RUNTIME ERROR: {e}")
