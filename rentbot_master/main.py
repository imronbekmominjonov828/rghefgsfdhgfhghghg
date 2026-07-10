"""
MASTER BOT — asosiy ishga tushiruvchi fayl.
"""
import asyncio
import logging
import httpx
import os  # Render muhitini to'g'ridan-to'g'ri tekshirish uchun

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
    # Agarda webhook ishlayotgan bo'lsa o'zini ping qiladi
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

    # Child-botlarni qayta ko'tarish va scheduler
    asyncio.create_task(cbm.restart_all_active_bots())
    asyncio.create_task(run_scheduler_loop(application.bot))
    asyncio.create_task(keep_alive_ping())


def main():
    if MASTER_BOT_TOKEN == "vghvhj":
        raise SystemExit(
            "❗ MASTER_BOT_TOKEN o'rnatilmagan. config.py yoki Environment Variable orqali bering."
        )

    app = ApplicationBuilder().token(MASTER_BOT_TOKEN).post_init(post_init).build()

    register_user_flow_handlers(app)
    register_admin_panel_handlers(app)

    # RENDER_PORT yoki oddij PORT borligini tekshiramiz. Render'da IS_RENDER yoki PORT har doim bo'ladi.
    # Bu joyda config'dan kelayotgan USE_WEBHOOK har doim True bo'lishini majburlaymiz agar Render'da bo'lsak.
    is_render = os.environ.get("RENDER") is not None or os.environ.get("PORT") is not None

    if USE_WEBHOOK or is_render:
        # Portni Render muhitidan aniq o'qib olamiz (agar configda xato bo'lsa)
        render_port = int(os.environ.get("PORT", PORT or 10000))
        render_url = WEBHOOK_BASE_URL or os.environ.get("WEBHOOK_BASE_URL")
        
        if not render_url:
            logger.error("❌ WEBHOOK_BASE_URL topilmadi! Render muhit sozlamalariga kiriting.")
            # Webhook URL bo'lmasa majburan lokal ishga tushadi, lekin render o'chirib yuboradi
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
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        main()
    finally:
        loop.close()
