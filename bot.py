import asyncio
import logging
import requests
import random
import os
import urllib.parse
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import CallbackQuery
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8309438145:AAEGBACLyLh2H_OyUk6ScDYpvNJU9_OaQyQ'
CHANNEL_ID = '@iPromt_AI'
POSTS_PER_DAY = 50 
INTERVAL_SECONDS = (24 * 60 * 60) // POSTS_PER_DAY 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
scheduler = AsyncIOScheduler()
posted_urls = set()

# --- ФУНКЦИЯ ПЕРЕВОДА ---
def translate_to_russian(text):
    if not text or len(text) < 5: return "Эстетичный AI арт"
    try:
        short_text = (text[:150] + '...') if len(text) > 150 else text
        base_url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ru&dt=t&q="
        response = requests.get(base_url + urllib.parse.quote(short_text), timeout=5)
        if response.status_code == 200:
            return response.json()[0][0][0]
    except: pass
    return "Детализированный AI промт"

# --- ОБРАБОТЧИК КНОПКИ КОПИРОВАНИЯ ---
@dp.callback_query(F.data == "copy_prompt")
async def process_copy_prompt(callback: CallbackQuery):
    # Извлекаем текст промта из сообщения (он находится между кавычками в блоке кода)
    text = callback.message.caption or callback.message.text
    try:
        # Ищем текст внутри моноширинного шрифта (промт)
        start = text.find("`") + 1
        end = text.rfind("`")
        prompt_text = text[start:end]
        
        await callback.message.answer(f"Текст промта (нажми, чтобы скопировать):\n\n`{prompt_text}`")
        await callback.answer("Промт отправлен ниже!")
    except:
        await callback.answer("Ошибка при копировании", show_alert=True)

# --- WEB SERVER ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Bot is Live and Fixed!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- ПОИСК КОНТЕНТА ---
def get_ai_content():
    subreddits = ['AiGeminiPhotoPrompts', 'PromptHero', 'lexica', 'civitai', 'StableDiffusion', 'AI_Car_Design']
    sub = random.choice(subreddits)
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit=100"
    headers = {'User-agent': 'AI-Mega-Bot-Fixed-v18'}
    
    people_keys = ['woman', 'girl', 'man', 'portrait', 'model', 'human', 'face', 'lady']
    car_keys = ['car', 'supercar', 'vehicle', 'auto', 'porsche', 'ferrari', 'lamborghini']
    news_keys = ['released', 'update', 'version', 'download', 'github', 'article', 'software']

    try:
        response = requests.get(url, headers=headers).json()
        posts = response['data']['children']
        random.shuffle(posts)
        
        for post in posts:
            data = post['data']
            if data.get('post_hint') != 'image': continue
                
            img_url = data.get('url', '')
            title = data.get('title', '')
            body_text = data.get('selftext', '')
            full_prompt = body_text if len(body_text) > len(title) else title
            low_prompt = full_prompt.lower()
            
            if any(n in low_prompt for n in news_keys): continue

            if any(img_url.endswith(ext) for ext in ['.jpg', '.png', '.jpeg']) and len(full_prompt) > 35:
                if img_url not in posted_urls:
                    is_p = any(k in low_prompt for k in people_keys)
                    is_c = any(k in low_prompt for k in car_keys)
                    if (is_p or is_c) and not any(b in low_prompt for b in ['cat', 'dog', 'animal']):
                        posted_urls.add(img_url)
                        return img_url, full_prompt, is_c
    except: pass
    return None, None, None

def escape_md(text):
    symbols = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for s in symbols: text = text.replace(s, f'\\{s}')
    return text

async def post_now():
    image_url, prompt, is_car = get_ai_content()
    if image_url:
        try:
            russian_desc = translate_to_russian(prompt)
            display_prompt = prompt if len(prompt) < 850 else prompt[:850] + "..."
            clean_prompt = escape_md(display_prompt)
            clean_ru = escape_md(russian_desc)
            
            icon = "🏎️" if is_car else "👤"
            tags = "\\#cars \\#auto" if is_car else "\\#people \\#portrait"
            tags += " \\#ai \\#prompts"

            caption = (
                f"📝 *Описание:* {clean_ru}\n\n"
                f"{icon} *Detailed Prompt:* \n`{clean_prompt}`\n\n"
                f"✨ @iPromt\\_AI\n"
                f"{tags}"
            )
            
            kb = [
                [types.InlineKeyboardButton(text="🔥 Подписаться", url="https://t.me/iPromt_AI")],
                [types.InlineKeyboardButton(text="📋 Скопировать промт", callback_data="copy_prompt")]
            ]
            
            res = requests.get(image_url, timeout=15)
            if res.status_code == 200:
                photo = types.BufferedInputFile(res.content, filename="art.jpg")
                await bot.send_photo(CHANNEL_ID, photo, caption=caption, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
        except Exception as e: logging.error(f"Post error: {e}")

async def main():
    await start_web_server()
    scheduler.add_job(post_now, 'interval', seconds=INTERVAL_SECONDS)
    scheduler.start()
    
    # Сразу первый пост
    await post_now()
    
    # Запуск обработки кнопок (polling)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
