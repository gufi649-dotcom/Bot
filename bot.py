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

# --- CONFIG ---
API_TOKEN = '8309438145:AAFTjTJ9OHgn1tVjqLneqDLT3Q8odMrryLo'
GEMINI_API_KEY = 'AIzaSyAJngwLCzOjjqFe_EkxQctwm1QT-vZEbrc'
CHANNEL_ID = '@iPromt_AI'

# Use the explicitly full model path to bypass the 404
MODEL_NAME = "gemini-1.5-flash" 

client = genai.Client(api_key=GEMINI_API_KEY)
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
scheduler = AsyncIOScheduler()
posted_urls = set()

async def get_ai_generated_prompt(image_url):
    try:
        response = requests.get(image_url, timeout=10)
        if response.status_code != 200: return None
        
        # New SDK logic: explicitly using the model via the models.generate_content
        ai_res = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                genai_types.Part.from_bytes(data=response.content, mime_type="image/jpeg"),
                "Write a professional AI art prompt for this image. English only. No intro."
            ]
        )
        return ai_res.text.strip()
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
    headers = {'User-Agent': f'BananahBot/9.0_{random.randint(1,1000)}'}
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
                        caption = f"🖼 *Visual AI Analysis*\n\n👤 *Prompt:* `{escape_md(prompt)}`"
                        photo = types.BufferedInputFile(requests.get(img_url).content, "art.jpg")
                        await bot.send_photo(CHANNEL_ID, photo, caption=caption)
                        logging.info("Successfully posted!")
                        return True
    except Exception as e:
        logging.error(f"Reddit error: {e}")
    return False

async def handle(request):
    return web.Response(text="Bot Alive")

async def on_startup(app):
    # Wait 5 seconds to let Render finish the 'zero-downtime' transition
    # This prevents the "Conflict" error with the previous instance
    logging.info("Waiting for old instances to clear...")
    await asyncio.sleep(5)
    
    await bot.delete_webhook(drop_pending_updates=True)
    scheduler.add_job(post_now, 'interval', minutes=25)
    scheduler.start()
    
    asyncio.create_task(post_now())
    asyncio.create_task(dp.start_polling(bot, skip_updates=True))

async def create_app():
    app = web.Application()
    app.router.add_get('/', handle)
    app.on_startup.append(on_startup)
    return app

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    web.run_app(create_app(), host='0.0.0.0', port=port)
