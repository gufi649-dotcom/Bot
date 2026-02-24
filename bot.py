import asyncio
import logging
import requests
import random
import os
import urllib.parse
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import CallbackQuery, Message
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8309438145:AAEGBACLyLh2H_OyUk6ScDYpvNJU9_OaQyQ'
CHANNEL_ID = '@iPromt_AI'
# Увеличил количество постов до 100 в день
POSTS_PER_DAY = 100 
INTERVAL_SECONDS = (24 * 60 * 60) // POSTS_PER_DAY 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
scheduler = AsyncIOScheduler()
posted_urls = set()

# --- ФУНКЦИЯ ПЕРЕВОДА ---
def translate_to_russian(text):
    if not text: return "Генерация"
    try:
        clean_text = text.split(',')[0].split('--')[0][:100]
        base_url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ru&dt=t&q="
        response = requests.get(base_url + urllib.parse.quote(clean_text), timeout=5)
        if response.status_code == 200:
            return response.json()[0][0][0]
    except: pass
    return "AI Промпт"

# --- ОБРАБОТКА КОМАНД И КНОПОК ---

# Команда /start для админа, чтобы появилась кнопка принудительного поста
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    kb = [[types.KeyboardButton(text="🚀 Опубликовать сейчас")]]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Бот запущен. Нажмите кнопку ниже для мгновенной публикации промпта.", reply_markup=keyboard)

# Кнопка мгновенной публикации
@dp.message(F.text == "🚀 Опубликовать сейчас")
async def manual_post(message: Message):
    await message.answer("⏳ Ищу качественный промпт...")
    success = await post_now()
    if success:
        await message.answer("✅ Пост опубликован!")
    else:
        await message.answer("❌ Не удалось найти подходящий промпт, попробуйте еще раз через минуту.")

# Кнопка копирования под постом
@dp.callback_query(F.data == "copy_prompt")
async def process_copy_prompt(callback: CallbackQuery):
    text = callback.message.caption or ""
    try:
        start = text.find("`") + 1
        end = text.rfind("`")
        if start > 0 and end > start:
            prompt_text = text[start:end]
            await callback.message.answer(f"📋 *Промпт для копирования:* \n\n`{prompt_text}`")
        await callback.answer()
    except:
        await callback.answer("Ошибка копирования")

# --- ПОИСК И ФИЛЬТРАЦИЯ ---

def is_technical_prompt(text):
    """Отсеивает болтовню, оставляя только технические промпты."""
    t = text.lower()
    # Если это вопрос или крик о помощи - в топку
    if any(x in t for x in ['?', 'help', 'how to', 'why', 'anyone', 'problem', 'error']):
        return False
    # Промпты часто содержат параметры или ключевые слова качества
    signals = ['--', '8k', 'realistic', 'detailed', 'masterpiece', 'trending', 'sharp', 'lighting', 'v 6', 'v 5']
    return any(s in t for s in signals) or (',' in t and len(t) > 60)

def get_ai_content():
    subreddits = ['StableDiffusion', 'midjourney', 'PromptHero', 'AiGeminiPhotoPrompts']
    sub = random.choice(subreddits)
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit=100"
    headers = {'User-agent': 'AI-Prompt-Pro-v21'}
    
    try:
        response = requests.get(url, headers=headers).json()
        posts = response['data']['children']
        random.shuffle(posts)
        
        for post in posts:
            data = post['data']
            if data.get('post_hint') != 'image': continue
            
            img_url = data.get('url', '')
            title = data.get('title', '')
            body = data.get('selftext', '')
            full_text = body if len(body) > 40 else title

            # Проверка: это реально промпт?
            if not is_technical_prompt(full_text): continue
            
            if img_url not in posted_urls:
                posted_urls.add(img_url)
                is_car = any(x in full_text.lower() for x in ['car', 'auto', 'vehicle'])
                return img_url, full_text, is_car
    except: pass
    return None, None, None

def escape_md(text):
    symbols = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for s in symbols: text = text.replace(s, f'\\{s}')
    return text

async def post_now():
    image_url, prompt, is_car = get_ai_content()
    if not image_url: return False
    
    try:
        russian_desc = translate_to_russian(prompt)
        clean_prompt = escape_md(prompt[:850])
        clean_ru = escape_md(russian_desc)
        
        icon = "🏎️" if is_car else "👤"
        caption = (
            f"📝 *Описание:* {clean_ru}\n\n"
            f"{icon} *Detailed Prompt:* \n`{clean_prompt}`\n\n"
            f"✨ @iPromt\\_AI\n"
            f"\\#ai \\#prompts " + ("\\#cars" if is_car else "\\#portrait")
        )
        
        kb = [
            [types.InlineKeyboardButton(text="🔥 Подписаться", url="https://t.me/iPromt_AI")],
            [types.InlineKeyboardButton(text="📋 Скопировать промпт", callback_data="copy_prompt")]
        ]
        
        res = requests.get(image_url, timeout=15)
        if res.status_code == 200:
            photo = types.BufferedInputFile(res.content, filename="art.jpg")
            await bot.send_photo(CHANNEL_ID, photo, caption=caption, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
            return True
    except Exception as e:
        logging.error(f"Post error: {e}")
    return False

# --- СЕРВЕР И ЗАПУСК ---

async def handle(request):
    return web.Response(text="Prompt Bot is Active!")

async def main():
    # Запуск веб-сервера для Render
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()

    # Запуск планировщика
    scheduler.add_job(post_now, 'interval', seconds=INTERVAL_SECONDS)
    scheduler.start()
    
    # Сразу один пост при запуске
    await post_now()
    
    # Запуск прослушивания кнопок
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
