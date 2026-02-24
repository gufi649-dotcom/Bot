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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY, transport='rest')

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
scheduler = AsyncIOScheduler()

def escape_md(text):
    for s in r'_*[]()~`>#+-=|{}.!':
        text = text.replace(s, f'\\{s}')
    return text

async def get_ai_generated_prompt(image_url):
    try:
        logger.info(f"Отправка в Gemini: {image_url}")
        response = requests.get(image_url, timeout=15)
        if response.status_code != 200: return None
        
        model = genai.GenerativeModel(model_name='models/gemini-1.5-flash')
        img_data = [{'mime_type': 'image/jpeg', 'data': response.content}]
        prompt_text = "Create a short Midjourney prompt for this image. English only."
        
        result = model.generate_content([prompt_text, img_data[0]])
        return result.text.strip() if result and result.text else None
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        return None

async def post_now():
    logger.info("=== ЗАПУСК ПРОВЕРКИ REDDIT ===")
    subs = ['Midjourney', 'AIArt', 'StableDiffusion']
    target_sub = random.choice(subs)
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        url = f"https://www.reddit.com/r/{target_sub}/hot.json?limit=10"
        r = requests.get(url, headers=headers, timeout=10)
        posts = r.json().get('data', {}).get('children', [])
        
        for post in posts:
            img_url = post['data'].get('url', '')
            if any(img_url.lower().endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                prompt = await get_ai_generated_prompt(img_url)
                if prompt:
                    caption = f"🖼 *Visual Analysis* \(r/{target_sub}\)\n\n👤 *Prompt:* `{escape_md(prompt)}`"
                    photo_resp = requests.get(img_url)
                    await bot.send_photo(CHANNEL_ID, types.BufferedInputFile(photo_resp.content, filename="img.jpg"), caption=caption)
                    logger.info("✅ УСПЕХ: Пост отправлен!")
                    return True
        logger.warning("❌ Картинки не найдены.")
    except Exception as e:
        logger.error(f"Ошибка постинга: {e}")
    return False

async def handle(request):
    return web.Response(text="Alive")

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000))).start()

    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем цикл публикаций
    scheduler.add_job(post_now, 'interval', minutes=25)
    scheduler.start()
    
    # ВАЖНО: Прямой запуск первой публикации
    logger.info("Бот запущен. Выполняю первый пост...")
    await post_now()
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())