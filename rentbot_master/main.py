"""
MASTER BOT — asosiy ishga tushiruvchi fayl.
"""
import asyncio
import logging
import httpx
import os
import sys

from telegram.ext import ApplicationBuilder

from config import MASTER_BOT_TOKEN, PORT, WEBHOOK_BASE_URL, USE_WEBHOOK
from master_db import init_master_db
from user_flow import register_user_flow_handlers
from master_admin import register_admin_panel_handlers
import child_bot_manager as cbm
from scheduler import run_scheduler_loop

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def keep_alive_ping():
    """
    Render serverini hadep o'chib qolmasligi uchun har 10 daqiqada uyg'otib turuvchi funksiya.
    """
    url = WEBHOOK_BASE_URL or os.environ.get("WEBHOOK_BASE_URL")
    if url:
        if not url.startswith("http"):
            url = f"https://{url}"
        url = url.rstrip('/')
        await asyncio.sleep(30)
        while True:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, timeout=10)
                    logger.info(f"⏰ Anti-Sleep ping muvaffaqiyatli: Status {response.status_code}")
            except Exception as e:
                logger.warning(f"⚠️ Anti-Sleep pingda xatolik: {e}")
            await asyncio.sleep(600)


async def main_async():
    if MASTER_BOT_TOKEN == "vghvhj":
        sys.exit("❗ MASTER_BOT_TOKEN o'rnatilmagan. config.py yoki Environment Variable orqali bering.")

    app = ApplicationBuilder().token(MASTER_BOT_TOKEN).build()

    register_user_flow_handlers(app)
    register_admin_panel_handlers(app)

    await init_master_db()
    logger.info("Master DB tayyor.")

    await app.initialize()
    await app.start()

    is_render = os.environ.get("RENDER") is not None or os.environ.get("PORT") is not None
    render_url = WEBHOOK_BASE_URL or os.environ.get("WEBHOOK_BASE_URL")

    if USE_WEBHOOK or (is_render and render_url):
        render_port = int(os.environ.get("PORT", PORT or 10000))
        
        # MUHIM: URL manzilini tekshiramiz va formatlaymiz
        render_url = render_url.strip().rstrip('/')
        if not render_url.startswith("http://") and not render_url.startswith("https://"):
            render_url = f"https://{render_url}"
            
        full_webhook_url = f"{render_url}/webhook"
        logger.info(f"🚀 Master bot WEBHOOK rejimida {render_port}-portda ishga tushmoqda...")
        logger.info(f"🔗 Telegram'ga yuborilayotgan Webhook URL: {full_webhook_url}")
        
        try:
            await app.updater.start_webhook(
                listen="0.0.0.0",
                port=render_port,
                url_path="webhook",
                webhook_url=full_webhook_url,
                allowed_updates=["message", "callback_query"],
            )
        except Exception as webhook_err:
            logger.error(f"❌ Webhook ishga tushishda xatolik berdi: {webhook_err}")
            logger.info("🔄 Polling rejimiga majburiy o'tilmoqda (Lokal rejim)...")
            await app.updater.start_polling(allowed_updates=["message", "callback_query"])
    else:
        logger.info("🤖 Master bot POLLING rejimida ishga tushdi (lokal test).")
        await app.updater.start_polling(allowed_updates=["message", "callback_query"])

    asyncio.create_task(cbm.restart_all_active_bots())
    asyncio.create_task(run_scheduler_loop(app.bot))
    asyncio.create_task(keep_alive_ping())

    logger.info("✅ Barcha fon vazifalari va bot muvaffaqiyatli ishga tushdi.")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Bot to'xtatilyapti...")
    finally:
        if app.updater and app.updater.running:
            await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Dastur majburan to'xtatildi.")
