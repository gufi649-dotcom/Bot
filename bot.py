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

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

# Принудительная настройка Gemini на REST-транспорт (для стабильности в облаке)
genai.configure(api_key=GEMINI_API_KEY, transport='rest')

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
scheduler = AsyncIOScheduler()

def escape_md(text):
    """Экранирование спецсимволов для Telegram Markdown V2"""
    for s in r'_*[]()~`>#+-=|{}.!':
        text = text.replace(s, f'\\{s}')
    return text

async def get_ai_generated_prompt(image_url):
    """Анализ изображения через Gemini"""
    try:
        logger.info(f"-> Запрос к Gemini для: {image_url}")
        response = requests.get(image_url, timeout=15)
        if response.status_code != 200:
            logger.error(f"Не удалось скачать картинку для Gemini. Код: {response.status_code}")
            return None
        
        # Указываем модель явно с полным путем
        model = genai.GenerativeModel(model_name='models/gemini-1.5-flash')
        
        img_data = [{'mime_type': 'image/jpeg', 'data': response.content}]
        prompt_text = "Create a short, artistic Midjourney prompt based on this image. One sentence only. English."
        
        result = model.generate_content([prompt_text, img_data[0]])
        
        if result and result.text:
            return result.text.strip()
        return None
    except Exception as e:
        logger.error(f"Ошибка Gemini SDK: {e}")
        return None

async def post_now():
    """Процесс поиска и публикации контента"""
    logger.info("=== START REDDIT SWEEP ===")
    subs = ['Midjourney', 'AIArt', 'StableDiffusion', 'ImaginaryLandscapes']
    target_sub = random.choice(subs)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        logger.info(f"Шаг 1: Проверка r/{target_sub}...")
        url = f"https://www.reddit.com/r/{target_sub}/hot.json?limit=15"
        r = requests.get(url, headers=headers, timeout=15)
        
        if r.status_code != 200:
            logger.warning(f"Reddit отклонил запрос. Код: {r.status_code}. Проверь User-Agent.")
            return False

        posts = r.json().get('data', {}).get('children', [])
        logger.info(f"Шаг 2: Найдено постов: {len(posts)}")
        
        random.shuffle(posts)
        
        for post in posts:
            pdata = post['data']
            img_url = pdata.get('url', '')
            
            # Проверяем, что это прямая ссылка на картинку
            if any(img_url.lower().endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                logger.info(f"Шаг 3: Найдена картинка: {img_url}")
                
                prompt = await get_ai_generated_prompt(img_url)
                if prompt:
                    logger.info(f"Шаг 4: Промпт готов: {prompt[:30]}...")
                    
                    # Экранируем текст для MarkdownV2
                    safe_prompt = escape_md(prompt)
                    safe_sub = escape_md(target_sub)
                    caption = f"🖼 *Visual AI Analysis* \(r/{safe_sub}\)\n\n👤 *Prompt:* `{safe_prompt}`"
                    
                    photo_resp = requests.get(img_url)
                    photo = types.BufferedInputFile(photo_resp.content, filename="image.jpg")
                    
                    # Отправка в канал
                    await bot.send_photo(CHANNEL_ID, photo, caption=caption)
                    logger.info("=== УСПЕХ: Пост отправлен! ===")
                    return True
                else:
                    logger.warning("Gemini не смог обработать это изображение. Пробую следующее...")
        
        logger.warning("Подходящих изображений не найдено во всем списке.")
    except Exception as e:
        logger.error(f"Ошибка в post_now: {e}")
    return False

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def main():
    # Запуск сервера
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Веб-сервер запущен на порту {port}")

    # Очистка старых сессий Telegram
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Ожидание 60 секунд (сброс старых подключений)...")
    await asyncio.sleep(60)

    # Настройка планировщика
    scheduler.add_job(post_now, 'interval', minutes=25)
    scheduler.start()
    
    # Первый запуск сразу
    asyncio.create_task(post_now())
    
    logger.info("Бот запущен и готов к работе!")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
