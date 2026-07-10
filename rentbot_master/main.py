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
    """
    Asosiy asinxron ishga tushiruvchi funksiya.
    Barcha jarayonlar bitta umumiy event loop ichida ishlaydi.
    """
    if MASTER_BOT_TOKEN == "vghvhj":
        sys.exit("❗ MASTER_BOT_TOKEN o'rnatilmagan. config.py yoki Environment Variable orqali bering.")

    # 1. Application yaratish (bu yerda post_init shart emas, pastda qo'lda bajaramiz)
    app = ApplicationBuilder().token(MASTER_BOT_TOKEN).build()

    register_user_flow_handlers(app)
    register_admin_panel_handlers(app)

    # 2. Ma'lumotlar bazasini noldan ko'tarish
    await init_master_db()
    logger.info("Master DB tayyor.")

    # 3. Botni va uning tarkibiy qismlarini boshlash
    await app.initialize()
    await app.start()

    # Muhitni aniqlash
    is_render = os.environ.get("RENDER") is not None or os.environ.get("PORT") is not None
    render_url = WEBHOOK_BASE_URL or os.environ.get("WEBHOOK_BASE_URL")

    # 4. Tarmoq rejimini (Webhook yoki Polling) qo'lda boshqarish
    if USE_WEBHOOK or (is_render and render_url):
        render_port = int(os.environ.get("PORT", PORT or 10000))
        logger.info(f"🚀 Master bot WEBHOOK rejimida {render_port}-portda ishga tushmoqda...")
        
        await app.updater.start_webhook(
            listen="0.0.0.0",
            port=render_port,
            url_path="webhook",
            webhook_url=f"{render_url.rstrip('/')}/webhook",
            allowed_updates=["message", "callback_query"],
        )
    else:
        logger.info("🤖 Master bot POLLING rejimida ishga tushdi (lokal test).")
        await app.updater.start_polling(allowed_updates=["message", "callback_query"])

    # 5. Fon vazifalarini shu yerdagi faol va tirik event loop ichida ishga tushiramiz
    asyncio.create_task(cbm.restart_all_active_bots())
    asyncio.create_task(run_scheduler_loop(app.bot))
    asyncio.create_task(keep_alive_ping())

    logger.info("✅ Barcha fon vazifalari va bot muvaffaqiyatli ishga tushdi.")

    # 6. Dastur yopilib ketmasligi uchun va to'xtatish signallarini kutish uchun cheksiz tsikl
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Bot to'xtatilyapti...")
    finally:
        # Botni xavfsiz va toza yopish
        if app.updater.running:
            await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    # Python 3.14 dagi har qanday asinxron ziddiyatlarni chetlab o'tish uchun
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Dastur majburan to'xtatildi.")
