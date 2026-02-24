import asyncio
import logging
import requests
import random
import os
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import CallbackQuery, Message
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- КОНФИГУРАЦИЯ ---
# Твой НОВЫЙ токен от BotFather
API_TOKEN = '8309438145:AAFTjTJ9OHgn1tVjqLneqDLT3Q8odMrryLo'
GEMINI_API_KEY = 'AIzaSyAJngwLCzOjjqFe_EkxQctwm1QT-vZEbrc'
CHANNEL_ID = '@iPromt_AI'

# Настройка Gemini с актуальной моделью
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
scheduler = AsyncIOScheduler()
posted_urls = set()

# --- ЛОГИКА АНАЛИЗА ИЗОБРАЖЕНИЯ ---
async def get_ai_generated_prompt(image_url):
    try:
        response = requests.get(image_url, timeout=15)
        if response.status_code != 200: return None
        
        image_parts = [{"mime_type": "image/jpeg", "data": response.content}]
        
        instruction = (
            "Analyze this image and write a professional, highly detailed AI art prompt for Stable Diffusion. "
            "Describe the subject, clothing, environment, lighting, and camera settings. "
            "Output ONLY the English prompt. No preamble."
        )
        
        # Генерация контента через Gemini
        ai_response = model.generate_content([instruction, image_parts[0]])
        return ai_response.text.strip()
    except Exception as e:
        logging.error(f"Gemini error: {e}")
        return None

def escape_md(text):
    # Очистка текста для Telegram MarkdownV2
    symbols = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for s in symbols: text = text.replace(s, f'\\{s}')
    return text

# --- ГЛАВНАЯ ФУНКЦИЯ ПОСТИНГА ---
async def post_now():
    subs = ['Midjourney', 'StableDiffusion', 'AIArt', 'DigitalArt']
    sub = random.choice(subs)
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit=30"
    headers = {'User-Agent': f'BananahBot/4.0_{random.randint(1,1000)}'}
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200: 
            logging.error(f"Reddit error: {r.status_code}")
            return False
        
        data = r.json().get('data', {}).get('children', [])
        random.shuffle(data)
        
        for post in data:
            p_data = post.get('data', {})
            img_url = p_data.get('url', '')
            
            # Ищем прямую ссылку на картинку
            if any(img_url.lower().endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                if img_url not in posted_urls:
                    logging.info(f"Analyzing image: {img_url}")
                    prompt = await get_ai_generated_prompt(img_url)
                    
                    if prompt:
                        posted_urls.add(img_url)
                        caption = (
                            f"🖼 *Visual AI Analysis*\n\n"
                            f"👤 *Detailed Prompt:* \n`{escape_md(prompt)}`\n\n"
                            f"✨ @iPromt\\_AI\n"
                            f"\\#ai \\#prompts \\#gemini"
                        )
                        
                        img_res = requests.get(img_url)
                        photo = types.BufferedInputFile(img_res.content, "art.jpg")
                        
                        # Кнопка копирования
                        kb = [[types.InlineKeyboardButton(text="📋 Скопировать промпт", callback_data="copy")]]
                        
                        await bot.send_photo(CHANNEL_ID, photo, caption=caption, 
                                             reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
                        logging.info("SUCCESS: Post sent to channel!")
                        return True
    except Exception as e:
        logging.error(f"Post error: {e}")
    return False

# --- ОБРАБОТЧИКИ СОБЫТИЙ ---

@dp.callback_query(F.data == "copy")
async def copy_p(call: CallbackQuery):
    try:
        t = call.message.caption
        p = t[t.find("`")+1:t.rfind("`")]
        await call.message.answer(f"Промпт для копирования:\n\n`{p}`")
        await call.answer()
    except:
        await call.answer("Ошибка копирования")

async def handle(request): return web.Response(text="Bananah-Vision is ACTIVE")

async def main():
    # Запуск веб-сервера для Render
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000))).start()

    # ЖЕСТКИЙ СБРОС: Убираем старые вебхуки и конфликты
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Webhook dropped. Starting bot...")

    # Интервал публикаций (каждые 20 минут)
    scheduler.
