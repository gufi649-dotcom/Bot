import asyncio
import logging
import requests
import random
import os
import urllib.parse
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler as AsyncioScheduler
except ImportError:
    from apscheduler.schedulers.asyncio import AsyncIOWithNextRunTimeScheduler as AsyncioScheduler

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8309438145:AAEGBACLyLh2H_OyUk6ScDYpvNJU9_OaQyQ'
CHANNEL_ID = '@iPromt_AI'
POSTS_PER_DAY = 50 
INTERVAL_SECONDS = (24 * 60 * 60) // POSTS_PER_DAY 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
scheduler = AsyncioScheduler()
posted_urls = set()

# --- ФУНКЦИЯ ПЕРЕВОДА ---
def translate_to_russian(text):
    if not text or len(text) < 5: return "Эстетичный AI арт"
    try:
        # Берем только начало для краткого описания
        short_text = (text[:150] + '...') if len(text) > 150 else text
        base_url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ru&dt=t&q="
        response = requests.get(base_url + urllib.parse.quote(short_text), timeout=5)
        if response.status_code == 200:
            return response.json()[0][0][0]
    except: pass
    return "Детализированный AI промт"

# --- WEB SERVER ---
async def handle(request):
    return web.Response(text="Bot is Live: Pinterest, Lexica, CivitAI sources added.")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- ЛОГИКА ПОИСКА ПРОМТОВ ---
def get_ai_content():
    # Список источников, включая зеркала Pinterest, Lexica и CivitAI
    subreddits = [
        'AiGeminiPhotoPrompts', # Промты как на твоих скриншотах
        'PromptHero',           # База с prompthero.com
        'lexica',               # База с lexica.art
        'civitai',              # База с civitai.com
        'StableDiffusion',      # Профессиональные сложные промты
        'AI_Car_Design',        # Только машины
        'PinterestAI'           # Эстетика Pinterest
    ]
    sub = random.choice(subreddits)
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit=100"
    headers = {'User-agent': 'AI-Mega-Prompt-Bot-v16'}
    
    people_keys = ['woman', 'girl', 'man', 'portrait', 'model', 'human', 'face', 'lady']
    car_keys = ['car', 'supercar', 'vehicle', 'auto', 'porsche', 'ferrari', 'lamborghini']

    try:
        response = requests.get(url, headers=headers).json()
        posts = response['data']['children']
        random.shuffle(posts)
        
        for post in posts:
            data = post['data']
            img_url = data.get('url', '')
            title = data.get('title', '')
            body_text = data.get('selftext', '') # Текст внутри поста (там обычно лежат длинные промты)
            
            # Выбираем самый длинный текст (заголовок или описание)
            full_prompt = body_text if len(body_text) > len(title) else title
            
            # Фильтр: это картинка? Промт достаточно длинный (как на скринах)?
            if any(img_url.endswith(ext) for ext in ['.jpg', '.png', '.jpeg']) and len(full_prompt) > 35:
                if img_url not in posted_urls:
                    low_prompt = full_prompt.lower()
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

# --- ПУБЛИКАЦИЯ ---
async def post_now():
    image_url, prompt, is_car = get_ai_content()
    
    if image_url:
        try:
            russian_desc = translate_to_russian(prompt)
            # Телеграм ограничивает подпись к фото 1024 символами. Обрезаем, если промт слишком гигантский.
            display_prompt = prompt if len(prompt) < 850 else prompt[:850] + "..."
            
            clean_prompt = escape_md(display_prompt)
            clean_ru = escape_md(russian_desc)
            
            icon = "🏎️" if is_car else "👤"
            tags = "\\#cars \\#auto" if is_car else "\\#people \\#portrait"
            tags += " \\#ai \\#prompts \\#detailed"

            caption = (
                f"📝 *Описание:* {clean_ru}\n\n"
                f"{icon} *Detailed Prompt:* \n`{clean_prompt}`\n\n"
                f"✨ @iPromt\\_AI\n"
                f"{tags}"
            )
            
            kb = [[types.InlineKeyboardButton(text="🔥 Подписаться", url="https://t.me/iPromt_AI")]]
            
            res = requests.get(image_url, timeout=15)
            if res.status_code == 200:
                photo = types.BufferedInputFile(res.content, filename="art.jpg")
                await bot.send_photo(
                    CHANNEL_ID, 
                    photo=photo, 
                    caption=caption, 
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
                )
        except Exception as e: logging.error(f"Post error: {e}")

async def main():
    await start_web_server()
    scheduler.add_job(post_now, 'interval', seconds=INTERVAL_SECONDS)
    scheduler.start()
    await post_now()
    while True: await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
