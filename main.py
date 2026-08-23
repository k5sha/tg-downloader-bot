import logging
import sys
from aiohttp import web
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import (
    BASE_WEBHOOK_URL,
    BOT_TOKEN,
    WEB_SERVER_HOST,
    WEB_SERVER_PORT,
    WEBHOOK_PATH,
    WEBHOOK_SECRET,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

async def set_commands(bot: Bot):
    """Sets default bot commands in Telegram UI"""
    commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="help", description="Get help"),
    ]
    await bot.set_my_commands(commands)

async def on_startup(bot: Bot):
    """Executes on web server startup"""
    logger.info("🚀 Bot starting webhook...")
    bot_info = await bot.get_me()
    logger.info(f"🤖 Bot: @{bot_info.username} (ID: {bot_info.id})")
    
    await set_commands(bot)
    
    webhook_url = f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}"
    await bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET,
        allowed_updates=["message"],
        drop_pending_updates=True,
    )
    logger.info(f"🔗 Webhook successfully set to {webhook_url}")

async def on_shutdown(bot: Bot):
    """Executes on graceful shutdown (SIGTERM/SIGINT)"""
    logger.info("🛑 Bot shutting down...")
    from services import close_downloader
    
    await close_downloader()
    await bot.session.close()

async def healthcheck(request: web.Request) -> web.Response:
    """Endpoint for Kubernetes liveness and readiness probes"""
    return web.Response(text="OK", status=200)

async def metrics_handler(request: web.Request) -> web.Response:
    """Prometheus metrics endpoint"""
    return web.Response(
        body=generate_latest(),
        headers={"Content-Type": CONTENT_TYPE_LATEST}
    )

def main():
    from handlers import router
    
    dp.include_router(router)
    
    # Register aiogram lifecycle hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Initialize aiohttp web application
    app = web.Application()
    
    # Kubernetes health probe route
    app.router.add_get("/healthz", healthcheck)
    app.router.add_get("/metrics", metrics_handler)
    
    # Register Telegram webhook handler with secret verification
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    # Integrate aiogram dispatcher with aiohttp app lifecycle
    setup_application(app, dp, bot=bot)
    
    # Start web server
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)