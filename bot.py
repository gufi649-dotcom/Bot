async def post_now():
    # Расширенный список сабреддитов и надежный User-Agent
    subs = ['Midjourney', 'StableDiffusion', 'AIArt', 'ImaginaryLandscapes', 'DigitalArt']
    url = f"https://www.reddit.com/r/{random.choice(subs)}/hot.json?limit=15"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            logging.error(f"Reddit rejected with status {r.status_code}")
            return False
            
        posts = r.json().get('data', {}).get('children', [])
        random.shuffle(posts)
        
        for post in posts:
            data = post.get('data', {})
            img_url = data.get('url', '')
            if any(img_url.lower().endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                if img_url not in posted_urls:
                    logging.info(f"Generating prompt for: {img_url}")
                    prompt = await get_ai_generated_prompt(img_url)
                    if prompt:
                        posted_urls.add(img_url)
                        caption = f"🖼 *Visual AI Analysis*\n\n👤 *Prompt:* `{escape_md(prompt)}`"
                        photo = types.BufferedInputFile(requests.get(img_url).content, "art.jpg")
                        await bot.send_photo(CHANNEL_ID, photo, caption=caption)
                        logging.info("!!! POST SUCCESSFUL !!!")
                        return True
        logging.warning("No new images found in this sweep.")
    except Exception as e:
        logging.error(f"Post error: {e}")
    return False

async def main():
    # 1. Запуск веб-сервера (Render будет доволен)
    await start_webserver()
    
    # 2. Очистка вебхуков и ПАУЗА, чтобы старый инстанс отвалился
    logging.info("Clearing Telegram Webhooks and waiting for old instances to clear...")
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(40) # Даем Render 40 секунд на убийство старого контейнера
    
    # 3. Setup Scheduler
    scheduler.add_job(post_now, 'interval', minutes=25)
    scheduler.start()
    
    # 4. Initial Run
    asyncio.create_task(post_now())
    
    # 5. Start Polling с пропуском накопленных обновлений
    logging.info("Starting Bot Polling...")
    await dp.start_polling(bot, skip_updates=True)

