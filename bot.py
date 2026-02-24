import asyncio
import logging
import requests
import random
import os
import io
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8309438145:AAEGBACLyLh2H_OyUk6ScDYpvNJU9_OaQyQ'
GEMINI_API_KEY = 'AIzaSyAJngwLCzOjjqFe_EkxQctwm1QT-vZEbrc'
CHANNEL_ID = '@iPromt_AI'

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
scheduler = AsyncIOScheduler()
posted_urls = set()

# --- ЛОГИКА ИИ ---

async def analyze_image_with_gemini(image_url):
    """ИИ смотрит на картинку и пишет профессиональный промпт."""
    try:
        response = requests.get(image_url)
        if response.status_code != 200: return None
        
        image_data = [{"mime_type": "image/jpeg", "data": response.content}]
        
        # Инструкция для ИИ, чтобы он писал именно промпт для генерации
        instruction = (
            "Write a high-quality, professional AI art prompt for this image. "
            "Focus on: subject details, clothing, lighting (cinematic, soft), camera settings (35mm, 85mm, f/1.8), "
            "and artistic style (photorealistic, masterpiece). "
            "Output ONLY the English prompt text without any introductory words."
        )
        
        ai_response = model.generate_content([instruction, image_data[0]])
        return ai_response.text.strip()
    except Exception as e:
        logging.error(f"Gemini Error: {e}")
        return None

def translate_prompt(text):
    """Короткий перевод для описания."""
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ru&dt=t&q={text[:100]}"
        res = requests.get(url).json()
        return res[0][0][0]
    except: return "Профессиональная генерация"

# --- РАБОТА С КОНТЕНТОМ ---

async def post_now():
    subs = ['AiGeminiPhotoPrompts', 'PromptHero', 'StableDiffusion', 'midjourney']
    url = f"https://www.reddit.com/r/{random.choice(subs)}/hot.json?limit=30"
    headers = {'User-agent': 'Bananah-Pro-v3'}
    
    try:
        res = requests.get(url, headers=headers).json()
        posts = res['data']['children']
        random.shuffle(posts)
        
        for post in posts:
            data = post['data']
            img_url = data.get('url', '')
            
            if data.get('post_hint') == 'image' and img_url not in posted_urls:
                # ГЛАВНОЕ: ИИ создает промпт по картинке
                smart_prompt = await analyze_image_with_gemini(img_url)
                
                if smart_prompt and len(smart_prompt) > 50:
                    posted_urls.add(img_url)
                    ru_desc = translate_prompt(smart_prompt)
                    
                    # Экранируем символы для MarkdownV2
                    def escape(t):
                        for s in r'_*[]()~`>#+-=|{}.!': t = t.replace(s, f'\\{s}')
                        return t

                    caption = (
                        f"📝 *Описание:* {escape(ru_desc)}\n\n"
                        f"👤 *Detailed Prompt:* \n`{escape(smart_prompt)}`\n\n"
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
        logging.error(f"Post Error: {e}")
    return False

# --- WEB СЕРВЕР И ЗАПУСК ---

async def handle(request): return web.Response(text="Bananah-AI is Live!")

@dp.callback_query(F.data == "copy")
async def copy_call(callback: types.CallbackQuery):
    try:
        text = callback.message.caption
        start = text.find("`") + 1
        end = text.rfind("`")
        await callback.message.answer(f"Текст промпта:\n\n`{text[start:end]}`")
        await callback.answer()
    except: await callback.answer("Ошибка")

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()

    scheduler.add_job(post_now, 'interval', minutes=20) # Пост каждые 20 минут
    scheduler.start()
    await post_now()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
