import asyncio
import logging
import requests
import random
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# Исправленный импорт планировщика с проверкой версий
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler as AsyncioScheduler
except ImportError:
    from apscheduler.schedulers.asyncio import AsyncIOWithNextRunTimeScheduler as AsyncioScheduler

# --- ТВОИ ДАННЫЕ ---
API_TOKEN = '8309438145:AAEGBACLyLh2H_OyUk6ScDYpvNJU9_OaQyQ'
CHANNEL_ID = '@iPromt_AI'
POSTS_PER_DAY = 20
INTERVAL_SECONDS = (24 * 60 * 60) // POSTS_PER_DAY 

logging.basicConfig(level=logging.INFO)

# Инициализация бота для aiogram 3.x
bot = Bot(
    token=API_TOKEN, 
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
)
dp = Dispatcher()
scheduler = AsyncioScheduler()

posted_urls = set()

def get_ai_content():
    # Список источников
    subreddits = ['midjourney', 'StableDiffusion', 'DALL-E', 'aiArt']
    sub = random.choice(subreddits)
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit=50"
    headers = {'User-agent': 'AI-Prompt-Bot-v4'}
    
    # Ключевые слова для поиска людей/пар
    keywords = ['woman', 'man', 'couple', 'girl', 'boy', 'portrait', 'people', 'love', 'human', 'beauty', 'lady']
    
    try:
        response = requests.get(url, headers=headers).json()
        posts = response['data']['children']
        random.shuffle(posts)
        
        for post in posts:
            data = post['data']
            title = data.get('title', '')
            img_url = data.get('url', '')
            
            # Проверяем расширение и не постили ли мы это раньше
            if any(img_url.endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                if img_url not in posted_urls:
                    if any(word in title.lower() for word in keywords):
                        posted_urls.add(img_url)
                        return img_url, title
    except Exception as e:
        logging.error(f"Ошибка парсинга: {e}")
    return None, None

def escape_md(text):
    # Экранирование спецсимволов для MarkdownV2
    symbols = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for s in symbols:
        text = text.replace(s, f'\\{s}')
    return text

async def post_now():
    image, prompt = get_ai_content()
    if image:
        try:
            clean_prompt = escape_md(prompt)
            
            caption = (
                f"👤 *Prompt \\(click to copy\\):*\n"
                f"`{clean_prompt}`\n\n"
                f"✨ *Community:* @iPromt\\_AI\n"
                f"\\#ai \\#people \\#prompts"
            )
            
            # Кнопка под постом
            kb = [[types.InlineKeyboardButton(text="🔥 Подписаться на iPromt AI", url="https://t.me/iPromt_AI")]]
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=kb)

            await bot.send_photo(
                chat_id=CHANNEL_ID, 
                photo=image, 
                caption=caption,
                reply_markup=keyboard
            )
            logging.info("Пост успешно опубликован!")
        except Exception as e:
            logging.error(f"Ошибка отправки: {e}")

async def main():
    # Запуск планировщика
    scheduler.add_job(post_now, 'interval', seconds=INTERVAL_SECONDS)
    scheduler.start()
    
    # Делаем первый пост сразу при запуске
    await post_now()
    
    # Бесконечный цикл работы
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
