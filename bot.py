import asyncio
import logging
import requests
import random
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncioScheduler

# --- ТВОИ ДАННЫЕ ---
API_TOKEN = '8309438145:AAEGBACLyLh2H_OyUk6ScDYpvNJU9_OaQyQ'
CHANNEL_ID = '@iPromt_AI'
POSTS_PER_DAY = 20
INTERVAL_SECONDS = (24 * 60 * 60) // POSTS_PER_DAY 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncioScheduler()

posted_urls = set()

def get_ai_content():
    subreddits = ['midjourney', 'StableDiffusion', 'DALL-E', 'aiArt']
    sub = random.choice(subreddits)
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit=50"
    headers = {'User-agent': 'AI-Prompt-Bot-v3'}
    keywords = ['woman', 'man', 'couple', 'girl', 'boy', 'portrait', 'people', 'love', 'model', 'human']
    
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
            # Очистка текста для MarkdownV2 (простой вариант)
            clean_prompt = prompt.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
            
            caption = (
                f"👤 **Prompt (click to copy):**\n"
                f"`{clean_prompt}`\n\n"
                f"✨ **Community:** @iPromt_AI\n"
                f"#ai #people #prompts"
            )
            
            kb = [[types.InlineKeyboardButton(text="🔥 Подписаться на iPromt AI", url="https://t.me/iPromt_AI")]]
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=kb)

            await bot.send_photo(
                chat_id=CHANNEL_ID, 
                photo=image, 
                caption=caption, 
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=keyboard
            )
            logging.info("Пост опубликован!")
        except Exception as e:
            logging.error(f"Ошибка отправки: {e}")

async def main():
    await post_now() # Первый пост
    scheduler.add_job(post_now, 'interval', seconds=INTERVAL_SECONDS)
    scheduler.start()
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
 