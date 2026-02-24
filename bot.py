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

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
scheduler = AsyncIOScheduler()
posted_urls = set()

def escape_md(text):
    """Экранирование спецсимволов для Telegram Markdown V2"""
    for s in r'_*[]()~`>#+-=|{}.!':
        text = text.replace(s, f'\\{s}')
    return text

async def get_ai_generated_prompt(image_url):
    """Запрос к Gemini 1.5 Flash для анализа изображения"""
    try:
        # Скачиваем изображение
        img_resp = requests.get(image_url, timeout=15)
        if img_resp.status_code != 200:
            logger.error(f"Не удалось скачать фото: {img_resp.status_code}")
            return None
        
        base64_image = base64.b64encode(img_resp.content).decode('utf-8')
        
        # Используем v1beta для лучшей поддержки мультимодальности
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Analyze this image and write a detailed, artistic Midjourney prompt. English only, no intro, just the prompt text."},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64_image
                        }
                    }
                ]
            }],
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 800
            }
        }
        
        r = requests.post(url, json=payload, timeout=30)
        res = r.json()
        
        # Извлекаем текст из ответа
        if 'candidates' in res and len(res['candidates']) > 0:
            candidate = res['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content']:
                return candidate['content']['parts'][0].get('text', '').strip()
        
        logger.error(f"Ошибка Gemini (пустой ответ): {res}")
        return None
            
    except Exception as e:
        logger.error(f"Критическая ошибка Gemini: {e}")
        return None

async def post_now():
    """Основная задача: взять фото с Reddit, сделать промпт и отправить в канал"""
    logger.info("Начинаю поиск новых изображений на Reddit...")
    subs = ['Midjourney', 'AIArt', 'StableDiffusion', 'ImaginaryLandscapes', 'DigitalArt']
    target_sub = random.choice(subs)
    url = f"https://www.reddit.com/r/{target_sub}/hot.json?limit=15"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0'}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            logger.error(f"Reddit вернул ошибку: {r.status_code}")
            return False
            
        posts = r.json().get('data', {}).get('children', [])
        random.shuffle(posts) # Для разнообразия
        
        for post in posts:
            data = post.get('data', {})
            img_url = data.get('url', '')
            
            # Проверяем, что это прямая ссылка на картинку
            if any(img_url.lower().endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                if img_url not in posted_urls:
                    logger.info(f"Обработка изображения: {img_url}")
                    prompt = await get_ai_generated_prompt(img_url)
                    
                    if prompt:
                        posted_urls.add(img_url)
                        # Формируем сообщение
                        clean_prompt = escape_md(prompt)
                        caption = f"🖼 *Visual AI Analysis* \(r/{target_sub}\)\n\n👤 *Prompt:* `{clean_prompt}`"
                        
                        # Отправка фото в Telegram
                        photo_content = requests.get(img_url).content
                        photo = types.BufferedInputFile(photo_content, "image.jpg")
                        await bot.send_photo(CHANNEL_ID, photo, caption=caption)
                        logger.info("Успех! Пост опубликован в канале.")
                        return True
        logger.warning("Новых подходящих изображений не найдено.")
    except Exception as e:
        logger.error(f"Ошибка в цикле публикации: {e}")
    return False

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Bot is Live and Healthy")

async def main():
    # 1. Запуск мини-сервера для Render (чтобы не было ошибок порта)
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Сервер мониторинга запущен на порту {port}")

    # 2. Очистка старых обновлений и пауза
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Ожидание 45 секунд для очистки сессий...")
    await asyncio.sleep(45)

    # 3. Настройка планировщика (пост каждые 25 минут)
    scheduler.add_job(post_now, 'interval', minutes=25)
    scheduler.start()
    
    # 4. Моментальный запуск первого поста при старте
    asyncio.create_task(post_now())
    
    # 5. Запуск получения сообщений
    logger.info("Бот начинает опрос Telegram...")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"Бот упал с ошибкой: {e}")
