import asyncio
import logging
import requests
import random
import os
from google import genai
from google.genai import types as genai_types
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8309438145:AAFTjTJ9OHgn1tVjqLneqDLT3Q8odMrryLo'
GEMINI_API_KEY = 'AIzaSyAJngwLCzOjjqFe_EkxQctwm1QT-vZEbrc'
CHANNEL_ID = '@iPromt_AI'

# Инициализация нового клиента Google AI
client = genai.Client(api_key=GEMINI_API_KEY)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
scheduler = AsyncIOScheduler()
posted_urls = set()

async def get_ai_generated_prompt(image_url):
    try:
        response = requests.get(image_url, timeout=15)
        if response.status_code != 200: return None
        
        # Новый способ отправки изображения в Gemini 1.5 Flash
        prompt_text = "Analyze this image and write a detailed AI art prompt. Output ONLY the prompt text."
        
        ai_res = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=[
                prompt_text,
                genai_types.Part.from_bytes(data=response.content, mime_type="image/jpeg")
            ]
        )
        return ai_res.text.strip()
    except Exception as e:
        logging.error(f"Gemini AI Error: {e}")
        return None

def escape_md(text):
    for s in r'_*[]()~`>#+-=|{}.!':
        text = text.replace(s, f'\\{s}')
    return text

async def post_now():
    subs = ['Midjourney', 'StableDiffusion', 'AIArt', 'DigitalArt']
    url = f"https://www.reddit.com/r/{random.choice(subs)}/hot.json?limit=30"
    headers = {'User-Agent': f'BananahBot/5.0_{random.randint(1,999)}'}
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        posts = r.json().get('data', {}).get('children', [])
        random.shuffle(posts)
        
        for post in posts:
            data = post.get('data', {})
            img_url = data.get('url', '')
            
            if any(img_url.lower().endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                if img_url not in posted_urls:
                    prompt = await get_ai_generated_prompt(img_url)
                    if prompt:
                        posted_urls.add(img_url)
                        caption = (
                            f"🖼 *Visual AI Analysis*\n\n"
                            f"👤 *Detailed Prompt:* \n`{escape_md(prompt)}`\n\n"
                            f"✨ @iPromt\\_AI\n"
                            f"\\#ai \\#prompts \\#gemini"
                        )
                        
                        img_data = requests.get(img_url).content
                        photo = types.BufferedInputFile(img_data, "art.jpg")
                        
                        await bot.send_photo(CHANNEL_ID, photo, caption=caption, 
                                             reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                                                 [types.InlineKeyboardButton(text="📋 Скопировать", callback_data="copy")]
                                             ]))
                        logging.info("Post successful!")
                        return True
    except Exception as e:
        logging.error(f"Reddit/Post error: {e}")
    return False

@dp.callback_query(F.data == "copy")
async def copy_p(call: types.CallbackQuery):
    try:
        t = call.message.caption
        p = t[t.find("`")+1:t.rfind("`")]
        await call.message.answer(f"Промпт:\n\n`{p}`")
        await call.answer()
    except: await call.answer()

async def handle(request): return web.Response(text="Bot is Live")

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000))).start()

    # ЖЕСТКИЙ СБРОС КОНФЛИКТА
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(2) # Даем Telegram время «забыть» старое соединение

    scheduler.add_job(post_now, 'interval', minutes=25)
    scheduler.start()
    
    asyncio.create_task(post_now())
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
