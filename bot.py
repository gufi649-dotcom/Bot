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

# --- НАСТРОЙКИ ---
API_TOKEN = '8309438145:AAFTjTJ9OHgn1tVjqLneqDLT3Q8odMrryLo'
GEMINI_API_KEY = 'AIzaSyAJngwLCzOjjqFe_EkxQctwm1QT-vZEbrc'
CHANNEL_ID = '@iPromt_AI'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
scheduler = AsyncIOScheduler()
posted_urls = set()

def escape_md(text):
    """Экранирование символов для Markdown V2"""
    for s in r'_*[]()~`>#+-=|{}.!':
        text = text.replace(s, f'\\{s}')
    return text

async def get_ai_generated_prompt(image_url):
    """Получение промпта от Gemini с отключенными фильтрами цензуры"""
    try:
        img_resp = requests.get(image_url, timeout=15)
        if img_resp.status_code != 200: return None
        base64_image = base64.b64encode(img_resp.content).decode('utf-8')
        
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Write a professional Midjourney AI art prompt based on this image. English only, no preamble, one paragraph."},
                    {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}
                ]
            }],
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        }
        
        r = requests.post(url, json=payload, timeout=25)
        res = r.json()
        
        if 'candidates' in res and len(res['candidates']) > 0:
            candidate = res['candidates'][0]
            if 'content' in candidate:
                return candidate['content']['parts'][0]['text'].strip()
        
        logger.error(f"Gemini rejection or empty response: {res.get('promptFeedback')}")
        return None
            
    except Exception as e:
        logger.error(f"Gemini Critical Error: {e}")
        return None

async def post_now():
    """Поиск картинок на Reddit и публикация"""
    logger.info("Starting Reddit sweep...")
    subs = ['Midjourney', 'AIArt', 'StableDiffusion', 'ImaginaryLandscapes']
    target_sub = random.choice(subs)
    url = f"https://www.reddit.com/r/{target_sub}/hot.json?limit=15"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0'}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            logger.error(f"Reddit error {r.status_code}")
            return False
            
        posts = r.json().get('data', {}).get('children', [])
        random.shuffle(posts)
        
        for post in posts:
            data = post.get('data', {})
            img_url = data.get('url', '')
            
            if any(img_url.lower().endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                if img_url not in posted_urls:
                    logger.info(f"Analyzing image: {img_url}")
                    prompt = await get_ai_generated_prompt(img_url)
                    
                    if prompt:
                        posted_urls.add(img_url)
                        clean_prompt = escape_md(prompt)
                        caption = f"🖼 *Visual AI Analysis* \(r/{target_sub}\)\n\n👤 *Prompt:* `{clean_prompt}`"
                        
                        photo = types.BufferedInputFile(requests.get(img_url).content, "image.jpg")
                        await bot.send_photo(CHANNEL_ID, photo, caption=caption)
                        logger.info("Successfully posted to Telegram!")
                        return True
        logger.warning("No suitable new images found.")
    except Exception as e:
        logger.error(f"Post task error: {e}")
    return False

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Bot is running and healthy!")

async def main():
    # 1. Запуск сервера для прохождения проверки портов Render
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Render compliance server started on port {port}")

    # 2. Очистка вебхуков и длинная пауза для удаления старых инстансов
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook cleared. Waiting 45 seconds to avoid Conflict error...")
    await asyncio.sleep(45)

    # 3. Запуск планировщика
    scheduler.add_job(post_now, 'interval', minutes=25)
    scheduler.start()
    
    # 4. Первый запуск и старт прослушивания
    asyncio.create_task(post_now())
    logger.info("Bot polling starting...")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Unexpected crash: {e}")