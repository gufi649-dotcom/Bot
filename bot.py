import asyncio
import logging
import requests
import random
import os
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler as AsyncioScheduler
except ImportError:
    from apscheduler.schedulers.asyncio import AsyncIOWithNextRunTimeScheduler as AsyncioScheduler

# --- ДАННЫЕ ---
API_TOKEN = '8309438145:AAEGBACLyLh2H_OyUk6ScDYpvNJU9_OaQyQ'
CHANNEL_ID = '@iPromt_AI'
POSTS_PER_DAY = 20
INTERVAL_SECONDS = (24 * 60 * 60) // POSTS_PER_DAY 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
scheduler = AsyncioScheduler()
posted_urls = set()

# --- ФУНКЦИЯ ОБМАНА RENDER (Dummy Web Server) ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render дает порт в переменной окружения PORT
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Web server started on port {port}")

# --- ЛОГИКА БОТА ---
def get_ai_content():
    subreddits = ['midjourney', 'aiArt', 'StableDiffusion']
    sub = random.choice(subreddits)
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit=40"
    headers = {'User-agent': 'AI-Prompt-Bot-v6'}
    try:
        response = requests.get(url, headers=headers).json()
        posts = response['data']['children']
        random.shuffle(posts)
        for post in posts:
            data = post['data']
            img_url = data.get('url', '')
            if any(img_url.endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                if img_url not in posted_urls:
                    posted_urls.add(img_url)
                    return img_url, data.get('title', 'AI Art')
    except Exception as e:
        logging.error(f"Reddit error: {e}")
    return None, None

def escape_md(text):
    symbols = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for s in symbols: text = text.replace(s, f'\\{s}')
    return text

async def post_now():
    logging.info("Starting post attempt...")
    image, prompt = get_ai_content()
    if image:
        try:
            clean_prompt = escape_md(prompt)
            caption = f"👤 *Prompt:* `{clean_prompt}`\n\n✨ @iPromt\\_AI"
            kb = [[types.InlineKeyboardButton(text="🔥 Подписаться", url="https://t.me/iPromt_AI")]]
            await bot.send_photo(chat_id=CHANNEL_ID, photo=image, caption=caption, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
            logging.info("SUCCESS: Posted to Telegram!")
        except Exception as e:
            logging.error(f"Telegram error: {e}")

async def main():
    # Запускаем "обманку" для Render
    await start_web_server()
    
    # Запускаем планировщик
    scheduler.add_job(post_now, 'interval', seconds=INTERVAL_SECONDS)
    scheduler.start()
    
    # Первый пост сразу
    await post_now()
    
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
