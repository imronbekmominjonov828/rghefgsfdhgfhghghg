"""
MASTER BOT — asosiy ishga tushiruvchi fayl.
"""
import asyncio
import logging
import httpx
import os

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


async def keep_alive_ping(application):
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


async def post_init(application):
    await init_master_db()
    logger.info("Master DB tayyor.")

    # MUHIM O'ZGARISH: Fon vazifalarini PTB'ning o'zining event loop boshqaruviga topshiramiz.
    # Bu orqali run_webhook loopni yangilasa ham, ushbu tasklar o'lib qolmaydi.
    application.create_task(cbm.restart_all_active_bots())
    application.create_task(run_scheduler_loop(application.bot))
    application.create_task(keep_alive_ping(application))


def main():
    if MASTER_BOT_TOKEN == "vghvhj":
        raise SystemExit(
            "❗ MASTER_BOT_TOKEN o'rnatilmagan. config.py yoki Environment Variable orqali bering."
        )

    app = ApplicationBuilder().token(MASTER_BOT_TOKEN).post_init(post_init).build()

    register_user_flow_handlers(app)
    register_admin_panel_handlers(app)

    is_render = os.environ.get("RENDER") is not None or os.environ.get("PORT") is not None

    if USE_WEBHOOK or is_render:
        render_port = int(os.environ.get("PORT", PORT or 10000))
        render_url = WEBHOOK_BASE_URL or os.environ.get("WEBHOOK_BASE_URL")
        
        if not render_url:
            logger.error("❌ WEBHOOK_BASE_URL topilmadi! Render muhit sozlamalariga kiriting.")
            app.run_polling(allowed_updates=["message", "callback_query"])
            return

        logger.info(f"🚀 Master bot WEBHOOK rejimida {render_port}-portda ishga tushmoqda...")
        
        app.run_webhook(
            listen="0.0.0.0",
            port=render_port,
            url_path="webhook",
            webhook_url=f"{render_url.rstrip('/')}/webhook",
            allowed_updates=["message", "callback_query"],
        )
    else:
        logger.info("🤖 Master bot POLLING rejimida ishga tushdi (lokal test).")
        app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    # Python 3.14+ uyg'unligi uchun toza asinxron muhit yaratish
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        main()
    finally:
        loop.close()
