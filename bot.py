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
# Совет: Лучше сбросить токен в BotFather и вставить новый здесь
API_TOKEN = '8309438145:AAEGBACLyLh2H_OyUk6ScDYpvNJU9_OaQyQ'
GEMINI_API_KEY = 'AIzaSyAJngwLCzOjjqFe_EkxQctwm1QT-vZEbrc'
CHANNEL_ID = '@iPromt_AI'

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
scheduler = AsyncIOScheduler()
posted_urls = set()

async def get_ai_generated_prompt(image_url):
    try:
        response = requests.get(image_url, timeout=15)
        if response.status_code != 200: return None
        image_parts = [{"mime_type": "image/jpeg", "data": response.content}]
        instruction = (
            "Analyze this image and write a professional, highly detailed AI art prompt. "
            "Describe the subject, clothing, background, lighting, and camera settings. "
            "Output ONLY the English prompt."
        )
        ai_response = model.generate_content([instruction, image_parts[0]])
        return ai_response.text.strip()
    except Exception as e:
        logging.error(f"Gemini error: {e}")
        return None

def escape_md(text):
    symbols = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for s in symbols: text = text.replace(s, f'\\{s}')
    return text

async def post_now():
    # Список сабреддитов, где точно есть картинки
    subs = ['Midjourney', 'StableDiffusion', 'AIArt', 'DigitalArt']
    sub = random.choice(subs)
    # Используем старый добрый .rss или подставляем другой User-Agent
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit=50"
    headers = {'User-Agent': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) {random.randint(1,100)}'}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            logging.error(f"Reddit Error {response.status_code}")
            return False
            
        data = response.json()
        posts = data.get('data', {}).get('children', [])
        
        if not posts:
            logging.error("No posts found on Reddit")
            return False

        random.shuffle(posts)
        for post in posts:
            p_data = post.get('data', {})
            img_url = p_data.get('url', '')
            
            # Проверяем, что это прямая ссылка на картинку
            if any(img_url.endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                if img_url not in posted_urls:
                    smart_prompt = await get_ai_generated_prompt(img_url)
                    if smart_prompt:
                        posted_urls.add(img_url)
                        caption = (
                            f"🖼 *Visual AI Analysis*\n\n"
                            f"👤 *Detailed Prompt:* \n`{escape_md(smart_prompt)}`\n\n"
                            f"✨ @iPromt\\_AI\n"
                            f"\\#ai \\#prompts \\#gemini"
                        )
                        kb = [[types.InlineKeyboardButton(text="📋 Скопировать", callback_data="copy")]]
                        img_res = requests.get(img_url)
                        photo = types.BufferedInputFile(img_res.content, "art.jpg")
                        await bot.send_photo(CHANNEL_ID, photo, caption=caption, 
                                             reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
                        return True
    except Exception as e:
        logging.error(f"Main Loop error: {e}")
    return False

@dp.callback_query(F.data == "copy")
async def copy_p(call: CallbackQuery):
    try:
        t = call.message.caption
        p = t[t.find("`")+1:t.rfind("`")]
        await call.message.answer(f"Промпт:\n\n`{p}`")
        await call.answer()
    except: await call.answer("Ошибка")

async def handle(request): return web.Response(text="Bot is Live")

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000))).start()

    # КРИТИЧЕСКИ ВАЖНО для исправления Conflict:
    await bot.delete_webhook(drop_pending_updates=True)
    
    scheduler.add_job(post_now, 'interval', minutes=30)
    scheduler.start()
    
    # Запускаем первую попытку через 5 секунд, чтобы сервер успел "продышаться"
    asyncio.create_task(post_now())
    
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
