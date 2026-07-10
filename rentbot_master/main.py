"""
MASTER BOT — asosiy ishga tushiruvchi fayl.

Bu bot:
1. Mijozlarni qabul qiladi (forma to'ldirish, to'lov)
2. Har bir mijoz uchun child-botni dinamik ishga tushiradi (child_bot_manager orqali)
3. Fon vazifasi (scheduler) orqali muddati tugaganlarni avtomatik to'xtatadi
4. Server qayta ishga tushganda barcha aktiv mijozlarning botlarini qayta ko'taradi

Ishga tushirish:
    python main.py
"""
import asyncio
import logging

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


async def post_init(application):
    await init_master_db()
    logger.info("Master DB tayyor.")

    # Server qayta ishga tushganda (deploy, restart) barcha aktiv mijozlarning
    # child-botlarini avtomatik qayta ko'taramiz.
    asyncio.create_task(cbm.restart_all_active_bots())

    # Fon vazifasi: muddati tugaganlarni tekshirish va eslatma yuborish
    asyncio.create_task(run_scheduler_loop(application.bot))


def main():
    if MASTER_BOT_TOKEN == "vghvhj":
        raise SystemExit(
            "❗ MASTER_BOT_TOKEN o'rnatilmagan. config.py yoki Environment Variable orqali bering."
        )

    app = ApplicationBuilder().token(MASTER_BOT_TOKEN).post_init(post_init).build()

    register_user_flow_handlers(app)
    register_admin_panel_handlers(app)

    if USE_WEBHOOK:
        logger.info(f"Master bot WEBHOOK rejimida ishga tushdi: {WEBHOOK_BASE_URL}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="webhook",
            webhook_url=f"{WEBHOOK_BASE_URL}/webhook",
            allowed_updates=["message", "callback_query"],
        )
    else:
        logger.info("Master bot POLLING rejimida ishga tushdi (lokal test).")
        app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
