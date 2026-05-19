#!/usr/bin/env python3
import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, logger

# Створюємо бота та диспетчер
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

async def on_startup():
    logger.info("🚀 Bot starting...")

async def on_shutdown():
    logger.info("🛑 Bot shutting down...")
    await bot.session.close()

async def main():
    # Імпортуємо хендлери після створення bot
    from handlers import router
    from services import close_downloader
    
    dp.include_router(router)
    
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    try:
        bot_info = await bot.get_me()
        logger.info(f"🤖 Bot: @{bot_info.username}")
        await dp.start_polling(bot, allowed_updates=["message"])
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await close_downloader()

if __name__ == "__main__":
    asyncio.run(main())