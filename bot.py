import asyncio
import logging
import requests
import random
import os
import base64
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

# Initialize Bot with a specific session to avoid conflicts
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
scheduler = AsyncIOScheduler()
posted_urls = set()

async def get_ai_generated_prompt(image_url):
    try:
        img_data = requests.get(image_url, timeout=10).content
        base64_image = base64.b64encode(img_data).decode('utf-8')
        
        # Standard V1 URL
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Write a professional AI art prompt for this image. English only, no preamble."},
                    {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}
                ]
            }]
        }
        
        r = requests.post(url, json=payload, timeout=20)
        res_json = r.json()
        
        if 'candidates' in res_json:
            return res_json['candidates'][0]['content']['parts'][0]['text'].strip()
        return None
    except Exception as e:
        logging.error(f"Gemini Error: {e}")
        return None

def escape_md(text):
    for s in r'_*[]()~`>#+-=|{}.!':
        text = text.replace(s, f'\\{s}')
    return text

async def post_now():
    subs = ['Midjourney', 'StableDiffusion', 'AIArt']
    url = f"https://www.reddit.com/r/{random.choice(subs)}/hot.json?limit=10"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        posts = r.json().get('data', {}).get('children', [])
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
                        return True
    except Exception as e:
        logging.error(f"Reddit/Telegram Error: {e}")
    return False

# --- WEB SERVER (Fixes Render Port Timeout) ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000)))
    await site.start()
    logging.info("Web server started on port " + os.environ.get("PORT", "10000"))

async def main():
    # 1. Start the dummy web server for Render
    await start_webserver()
    
    # 2. Kill any old Telegram connections
    logging.info("Clearing Telegram Webhooks...")
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(2) # Give Telegram a breather
    
    # 3. Setup Scheduler
    scheduler.add_job(post_now, 'interval', minutes=25)
    scheduler.start()
    
    # 4. Initial Run
    asyncio.create_task(post_now())
    
    # 5. Start Polling
    logging.info("Starting Bot Polling...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
