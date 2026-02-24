import asyncio
import logging
import random
import os
import requests
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- НАСТРОЙКИ ---
API_TOKEN = '8309438145:AAFTjTJ9OHgn1tVjqLneqDLT3Q8odMrryLo'
GEMINI_API_KEY = 'AIzaSyAJngwLCzOjjqFe_EkxQctwm1QT-vZEbrc'
CHANNEL_ID = '@iPromt_AI'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
scheduler = AsyncIOScheduler()

def escape_md(text):
    """Экранирование символов для Markdown V2"""
    for s in r'_*[]()~`>#+-=|{}.!':
        text = text.replace(s, f'\\{s}')
    return text

async def get_ai_generated_prompt(image_url):
    """Получение промпта через официальный SDK Google"""
    try:
        response = requests.get(image_url, timeout=15)
        if response.status_code != 200:
            return None
        
        img_data = [{'mime_type': 'image/jpeg', 'data': response.content}]
        prompt_text = "Write a one-sentence Midjourney artistic prompt for this image. English only, no intros."
        
        result = model.generate_content([prompt_text, img_data[0]])
        if result and result.text:
            return result.text.strip()
        return None
    except Exception as e:
        logger.error(f"Gemini SDK Error: {e}")
        return None

async def post_now():
    """Основная логика публикации"""
    logger.info("Reddit Sweep Started...")
    subs = ['Midjourney', 'AIArt', 'StableDiffusion', 'ImaginaryLandscapes']
    target_sub = random.choice(subs)
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        r = requests.get(f"https://www.reddit.com/r/{target_sub}/hot.json?limit=15", headers=headers, timeout=15)
        posts = r.json().get('data', {}).get('children', [])
        random.shuffle(posts)
        
        for post in posts:
            img_url = post['data'].get('url', '')
            if any(img_url.lower().endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                prompt = await get_ai_generated_prompt(img_url)
                if prompt:
                    caption = f"🖼 *Visual AI Analysis* \(r/{target_sub}\)\n\n👤 *Prompt:* `{escape_md(prompt)}`"
                    photo_resp = requests.get(img_url)
                    photo = types.BufferedInputFile(photo_resp.content, filename="image.jpg")
                    await bot.send_photo(CHANNEL_ID, photo, caption=caption)
                    logger.info("SUCCESS: Post sent to Telegram!")
                    return True
        logger.warning("No new images found.")
    except Exception as e:
        logger.error(f"Post error: {e}")
    return False

# --- WEB SERVER (Для Render) ---
async def handle(request):
    return web.Response(text="Bot is Live")

async def main():
    # 1. Запуск веб-сервера для порта 10000
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Port {port} bound successfully.")

    # 2. Очистка вебхука
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook cleared. Waiting 30s...")
    await asyncio.sleep(30)

    # 3. Настройка планировщика (раз в 25 минут)
    scheduler.add_job(post_now, 'interval', minutes=25)
    scheduler.start()
    
    # 4. Первый запуск
    asyncio.create_task(post_now())
    
    # 5. Старт поллинга
    logger.info("Starting polling...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")