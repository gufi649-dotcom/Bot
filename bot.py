import asyncio
import logging
import requests
import random
from aiogram import Bot, types
from aiogram.utils import markdown
from apscheduler.schedulers.asyncio import AsyncioScheduler

# --- ТВОИ ДАННЫЕ ---
API_TOKEN = '8309438145:AAEGBACLyLh2H_OyUk6ScDYpvNJU9_OaQyQ'
CHANNEL_ID = '@iPromt_AI'
POSTS_PER_DAY = 20
INTERVAL_SECONDS = (24 * 60 * 60) // POSTS_PER_DAY 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
scheduler = AsyncioScheduler(timezone="UTC")

posted_urls = set()

def get_ai_content():
    # Список сабреддитов для разнообразия
    subreddits = ['midjourney', 'StableDiffusion', 'DALL-E', 'aiArt']
    sub = random.choice(subreddits)
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit=50"
    headers = {'User-agent': 'AI-Prompt-Bot-v2'}
    
    # Ключевые слова для людей и пар
    keywords = ['woman', 'man', 'couple', 'girl', 'boy', 'portrait', 'people', 'love', 'model', 'human', 'beauty']
    
    try:
        response = requests.get(url, headers=headers).json()
        posts = response['data']['children']
        random.shuffle(posts)
        
        for post in posts:
            data = post['data']
            title = data.get('title', '')
            img_url = data.get('url', '')
            
            if img_url.endswith(('.jpg', '.png', '.jpeg')) and img_url not in posted_urls:
                if any(word in title.lower() for word in keywords):
                    posted_urls.add(img_url)
                    return img_url, title
    except Exception as e:
        logging.error(f"Ошибка парсинга: {e}")
    return None, None

async def post_now():
    image, prompt = get_ai_content()
    if image:
        try:
            # Форматируем текст: промпт в коде `text` для копирования одним кликом
            caption = (
                f"👤 **Prompt (click to copy):**\n"
                f"`{prompt}`\n\n"
                f"✨ **Community:** @iPromt_AI\n"
                f"#ai #people #prompts"
            )
            
            # Добавляем кнопку-ссылку на сам канал или на обсуждение
            keyboard = types.InlineKeyboardMarkup()
            button = types.InlineKeyboardButton(text="🔥 Подписаться на iPromt AI", url="https://t.me/iPromt_AI")
            keyboard.add(button)

            await bot.send_photo(
                chat_id=CHANNEL_ID, 
                photo=image, 
                caption=caption, 
                parse_mode="MarkdownV2", # Используем V2 для лучшей поддержки моноширинного текста
                reply_markup=keyboard
            )
            logging.info("Пост с кнопкой отправлен!")
        except Exception as e:
            logging.error(f"Ошибка отправки: {e}")

async def main():
    # Первый пост сразу
    await post_now()
    
    # Расписание
    scheduler.add_job(post_now, 'interval', seconds=INTERVAL_SECONDS)
    scheduler.start()
    
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass