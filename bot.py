
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
API_TOKEN = '8309438145:AAEGBACLyLh2H_OyUk6ScDYpvNJU9_OaQyQ'
GEMINI_API_KEY = 'AIzaSyAJngwLCzOjjqFe_EkxQctwm1QT-vZEbrc'
CHANNEL_ID = '@iPromt_AI'

# Настройка Gemini AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
scheduler = AsyncIOScheduler()
posted_urls = set()

# --- ФУНКЦИЯ АНАЛИЗА ИЗОБРАЖЕНИЯ (VISION) ---
async def get_ai_generated_prompt(image_url):
    """Отправляет картинку в Gemini и получает готовый промпт."""
    try:
        response = requests.get(image_url, timeout=15)
        if response.status_code != 200: return None
        
        # Подготовка картинки для нейросети
        image_parts = [{"mime_type": "image/jpeg", "data": response.content}]
        
        # Промпт для самой нейросети (как ей описывать фото)
        prompt_instruction = (
            "Analyze this image and write a professional, highly detailed AI art prompt. "
            "Describe the subject, clothing, environment, lighting (e.g. cinematic, soft, rim lighting), "
            "camera lens (e.g. 85mm, f/1.8), and overall aesthetic. "
            "Output ONLY the English prompt. No introductions."
        )
        
        # Генерируем текст
        ai_response = model.generate_content([prompt_instruction, image_parts[0]])
        return ai_response.text.strip()
    except Exception as e:
        logging.error(f"Gemini error: {e}")
        return None

def translate_desc(text):
    """Делает краткое описание на русском для заголовка."""
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ru&dt=t&q={text[:120]}"
        res = requests.get(url).json()
        return res[0][0][0]
    except: return "AI Генерация"

def escape_md(text):
    """Экранирование символов для Telegram MarkdownV2."""
    symbols = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for s in symbols: text = text.replace(s, f'\\{s}')
    return text

# --- ОСНОВНАЯ ЛОГИКА ПОСТИНГА ---
async def post_now():
    # Сабреддиты, где больше всего крутых артов
    subreddits = ['AiGeminiPhotoPrompts', 'PromptHero', 'StableDiffusion', 'midjourney']
    sub = random.choice(subreddits)
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit=30"
    headers = {'User-agent': 'Bananah-Vision-Bot-v1'}
    
    try:
        response = requests.get(url, headers=headers).json()
        posts = response['data']['children']
        random.shuffle(posts)
        
        for post in posts:
            data = post['data']
            img_url = data.get('url', '')
            
            # Проверяем, что это картинка и мы её ещё не постили
            if data.get('post_hint') == 'image' and img_url not in posted_urls:
                # ИИ «смотрит» на фото и пишет промпт
                smart_prompt = await get_ai_generated_prompt(img_url)
                
                if smart_prompt:
                    posted_urls.add(img_url)
                    russian_info = translate_desc(smart_prompt)
                    
                    # Формируем красивый пост
                    caption = (
                        f"📝 *Описание:* {escape_md(russian_info)}\n\n"
                        f"👤 *Detailed Prompt:* \n`{escape_md(smart_prompt)}`\n\n"
                        f"✨ @iPromt\\_AI\n"
                        f"\\#ai \\#prompts \\#gemini"
                    )
                    
                    kb = [[types.InlineKeyboardButton(text="📋 Скопировать промпт", callback_data="copy")]]
                    
                    img_res = requests.get(img_url)
                    photo = types.BufferedInputFile(img_res.content, "art.jpg")
                    await bot.send_photo(CHANNEL_ID, photo, caption=caption, 
                                         reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
                    return True
    except Exception as e:
        logging.error(f"Post error: {e}")
    return False

# --- ОБРАБОТЧИКИ ---

@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    btn = [[types.KeyboardButton(text="🚀 Опубликовать сейчас")]]
    await message.answer("Бот-генератор готов!", reply_markup=types.ReplyKeyboardMarkup(keyboard=btn, resize_keyboard=True))

@dp.message(F.text == "🚀 Опубликовать сейчас")
async def manual_post(message: Message):
    await message.answer("🤖 ИИ анализирует новое изображение...")
    await post_now()

@dp.callback_query(F.data == "copy")
async def copy_prompt(callback: CallbackQuery):
    try:
        # Извлекаем текст промпта из блока с кодом
        text = callback.message.caption
        start = text.find("`") + 1
        end = text.rfind("`")
        prompt = text[start:end]
        await callback.message.answer(f"Промпт для копирования:\n\n`{prompt}`")
        await callback.answer()
    except:
        await callback.answer("Ошибка")

# --- ЗАПУСК ---
async def handle(request): return web.Response(text="Bananah-Vision-AI is running!")

async def main():
    # Web сервер для Render
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()

    # Постинг каждые 20 минут
    scheduler.add_job(post_now, 'interval', minutes=20)
    scheduler.start()
    
    await post_now() # Первый пост при запуске
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
