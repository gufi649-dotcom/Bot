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

def translate_to_russian(text):
    try:
        base_url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ru&dt=t&q="
        response = requests.get(base_url + urllib.parse.quote(text), timeout=5)
        if response.status_code == 200:
            return response.json()[0][0][0]
    except:
        pass
    return text

async def handle(request):
    return web.Response(text="Only People & Cars Mode Active")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

def get_ai_content():
    subreddits = [
        'midjourney', 'StableDiffusion', 'AI_Car_Design', 
        'civitai', 'PromptHero', 'lexica'
    ]
    sub = random.choice(subreddits)
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit=100"
    headers = {'User-agent': 'AI-People-Cars-Only-v11'}
    
    # ТОЛЬКО люди и машины
    people_keys = ['woman', 'girl', 'man', 'boy', 'portrait', 'face', 'model', 'lady', 'beauty', 'human']
    car_keys = ['car', 'supercar', 'auto', 'vehicle', 'porsche', 'ferrari', 'lamborghini', 'audi', 'bmw', 'sedan']
    
    bad_keywords = ['cat', 'dog', 'animal', 'landscape', 'building', 'architecture', 'interior', 'house', 'room', 'nature', 'tree', 'flower']
    
    try:
        response = requests.get(url, headers=headers).json()
        posts = response['data']['children']
        random.shuffle(posts)
        
        for post in posts:
            data = post['data']
            title = data.get('title', '').lower()
            img_url = data.get('url', '')
            
            if any(img_url.endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                if img_url not in posted_urls:
                    # Проверяем, есть ли человек ИЛИ машина
                    is_person = any(word in title for word in people_keys)
                    is_car = any(word in title for word in car_keys)
                    # Проверяем, нет ли запрещенных слов
                    has_bad = any(word in title for word in bad_keywords)
                    
                    if (is_person or is_car) and not has_bad:
                        posted_urls.add(img_url)
                        return img_url, data.get('title', ''), sub, is_car
    except Exception as e:
        logging.error(f"Error: {e}")
    return None, None, None, None

def escape_md(text):
    symbols = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for s in symbols: text = text.replace(s, f'\\{s}')
    return text

async def post_now():
    image, prompt, source_sub, is_car = get_ai_content()
    
    if image:
        try:
            russian_desc = translate_to_russian(prompt)
            clean_prompt = escape_md(prompt)
            clean_ru = escape_md(russian_desc)
            
            # Динамические теги
            if is_car:
                tags = "\\#cars \\#auto \\#design \\#prompts"
                icon = "🏎️"
            else:
                tags = "\\#people \\#portrait \\#ai \\#prompts"
                icon = "👤"

            caption = (
                f"📝 *Описание:* {clean_ru}\n\n"
                f"{icon} *Prompt \\(copy\\):*\n`{clean_prompt}`\n\n"
                f"✨ *Community:* @iPromt\\_AI\n"
                f"{tags}"
            )
            
            kb = [[types.InlineKeyboardButton(text="🔥 Подписаться на iPromt AI", url="https://t.me/iPromt_AI")]]
            await bot.send_photo(
                chat_id=CHANNEL_ID, 
                photo=image, 
                caption=caption,
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
            )
        except Exception as e:
            logging.error(f"Post error: {e}")

async def main():
    await start_web_server()
    scheduler.add_job(post_now, 'interval', seconds=INTERVAL_SECONDS)
    scheduler.start()
    await post_now()
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
